"""Load and link .pyi files."""

import logging
import os


from pytype import utils
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import typeshed
from pytype.pytd.parse import builtins
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)


class Module(object):
  """Represents a parsed module.

  Attributes:
    module_name: The module name, e.g. "numpy.fft.fftpack".
    filename: The filename of the pytd that describes the module. Needs to be
      unique.
    ast: The parsed PyTD. Internal references will be resolved, but
      NamedType nodes referencing other modules might still be unresolved.
    dirty: The initial value of the dirty attribute.
  """

  def __init__(self, module_name, filename, ast, dirty=True):
    self.module_name = module_name
    self.filename = filename
    self.ast = ast
    self.dirty = dirty


class BadDependencyError(Exception):
  """If we can't resolve a module referenced by the one we're trying to load."""

  def __init__(self, module_error, src=None):
    referenced = ", referenced from %r" % src if src else ""
    super(BadDependencyError, self).__init__(module_error + referenced)

  def __str__(self):
    return self.message


class Loader(object):
  """A cache for loaded PyTD files.

  Typically, you'll have one instance of this class, per module.

  Attributes:
    base_module: The full name of the module we're based in (i.e., the module
      that's importing other modules using this loader).
    options: config.Options object
    _modules: A map, filename to Module, for caching modules already loaded.
    _concatenated: A concatenated pytd of all the modules. Refreshed when
                   necessary.
  """

  PREFIX = "pytd:"  # for pytd files that ship with pytype

  def __init__(self,
               base_module,
               python_version,
               pythonpath=(),
               imports_map=None,
               use_typeshed=True,
               typeshed_location="typeshed"):
    self.base_module = base_module
    self.python_version = python_version
    self.pythonpath = pythonpath
    self.imports_map = imports_map
    self.use_typeshed = use_typeshed
    self.typeshed_location = typeshed_location
    self.builtins, self.typing = builtins.GetBuiltinsAndTyping(python_version)
    self._modules = {
        "__builtin__":
        Module("__builtin__", self.PREFIX + "__builtin__", self.builtins,
               dirty=False),
        "typing":
        Module("typing", self.PREFIX + "typing", self.typing,
               dirty=False)
    }
    self._concatenated = None
    self._import_name_cache = {}  # performance cache
    # Paranoid verification that pytype.main properly checked the flags:
    if imports_map is not None:
      assert pythonpath == [""], pythonpath

  def _postprocess_pyi(self, ast):
    """Apply all the PYI transformations we need."""
    package_name = utils.get_pyi_package_name(ast.name, ast.is_package)
    if package_name:
      ast = ast.Visit(visitors.QualifyRelativeNames(package_name))
    ast = ast.Visit(visitors.LookupBuiltins(self.builtins, full_names=False))
    ast = ast.Visit(visitors.ExpandCompatibleBuiltins(self.builtins))
    dependencies, soft_dependencies = self._collect_ast_dependencies(ast)
    if dependencies or soft_dependencies:
      self._load_ast_dependencies(dependencies, soft_dependencies, ast)
      ast = self._resolve_external_types(ast)
    ast = ast.Visit(visitors.LookupLocalTypes())
    return ast

  def _create_empty(self, module_name, filename):
    ast = self.load_file(module_name, filename,
                         pytd_utils.EmptyModule(module_name))
    return ast.Replace(is_package=utils.is_pyi_directory_init(filename))

  def _get_existing_ast(self, module_name, filename):
    existing = self._modules.get(module_name)
    if existing:
      if existing.filename != filename:
        raise AssertionError("%s exists as both %s and %s" %
                             (module_name, filename, existing.filename))
      return existing.ast
    return None

  def load_file(self, module_name, filename, ast=None):
    """Load (or retrieve from cache) a module and resolve its dependencies."""
    self._concatenated = None  # invalidate
    # Check for an existing ast first
    existing = self._get_existing_ast(module_name, filename)
    if existing:
      return existing
    if not ast:
      ast = builtins.ParsePyTD(filename=filename,
                               module=module_name,
                               python_version=self.python_version)
    return self._process_module(module_name, filename, ast)

  def _process_module(self, module_name, filename, ast):
    """Create a module from a loaded ast and save it to the loader cache.

    Args:
      module_name: The fully qualified name of the module being imported.
      filename: The file the ast was generated from.
      ast: The pytd.TypeDeclUnit representing the module.

    Returns:
      The ast (pytd.TypeDeclUnit) as represented in this loader.
    """
    module = Module(module_name, filename, ast)
    self._modules[module_name] = module
    try:
      module.ast = self._postprocess_pyi(module.ast)
      # Now that any imported TypeVar instances have been resolved, adjust type
      # parameters in classes and functions.
      module.ast = module.ast.Visit(visitors.AdjustTypeParameters())
      # Now we can fill in internal cls pointers to ClassType nodes in the
      # module. This code executes when the module is first loaded, which
      # happens before any others use it to resolve dependencies, so there are
      # no external pointers into the module at this point.
      module.ast.Visit(
          visitors.FillInLocalPointers({"": module.ast,
                                        module_name: module.ast}))
    except:
      # don't leave half-resolved modules around
      del self._modules[module_name]
      raise
    return module.ast

  def _collect_ast_dependencies(self, ast):
    """Goes over an ast and returns all references module names."""
    deps = visitors.CollectDependencies()
    ast.Visit(deps)
    return deps.modules, deps.maybe_modules

  def _load_ast_dependencies(self, dependencies, soft_dependencies,
                             ast, ast_name=None):
    """Fill in all ClassType.cls pointers and load reexported modules."""
    for name in (dependencies or ()):
      if name not in self._modules:
        other_ast = self._import_name(name)
        if other_ast is None:
          error = "Can't find pyi for %r" % name
          raise BadDependencyError(error, ast_name or ast.name)
    for name in (soft_dependencies or ()):
      if name not in self._modules:
        # We ignore any errors here; what we're trying to import might not exist
        self._import_name(name, log_failure=False)

  def _resolve_external_types(self, ast):
    try:
      ast = ast.Visit(visitors.LookupExternalTypes(
          self._get_module_map(), full_names=True, self_name=ast.name))
    except KeyError as e:
      raise BadDependencyError(e.message, ast.name)
    return ast

  def _finish_ast(self, ast):
    module_map = self._get_module_map()
    module_map[""] = ast  # The module itself (local lookup)
    ast.Visit(visitors.FillInLocalPointers(module_map))

  def _verify_ast(self, ast):
    try:
      ast.Visit(visitors.VerifyLookup(ignore_late_types=True))
    except ValueError as e:
      raise BadDependencyError(e.message)
    ast.Visit(visitors.VerifyContainers())

  def resolve_ast(self, ast):
    """Resolve the dependencies of an AST, without adding it to our modules."""
    ast = self._postprocess_pyi(ast)
    self._lookup_all_classes()
    self._finish_ast(ast)
    self._verify_ast(ast)
    return ast

  def _lookup_all_classes(self):
    for module in self._modules.values():
      if module.dirty:
        self._finish_ast(module.ast)
        module.dirty = False

  def import_relative_name(self, name):
    """IMPORT_NAME with level=-1. A name relative to the current directory."""
    if self.base_module is None:
      raise ValueError("Attempting relative import in non-package.")
    path = self.base_module.split(".")[:-1]
    path.append(name)
    ast = self._import_name(".".join(path))
    self._lookup_all_classes()
    if ast:
      self._verify_ast(ast)
    return ast

  def import_relative(self, level):
    """Import a module relative to our base module.

    Args:
      level: Relative level:
        https://docs.python.org/2/library/functions.html#__import__
        E.g.
          1: "from . import abc"
          2: "from .. import abc"
          etc.
        Since you'll use import_name() for -1 and 0, this function expects the
        level to be >= 1.
    Returns:
      The parsed pytd. Instance of pytd.TypeDeclUnit. None if we can't find the
      module.
    Raises:
      ValueError: If we don't know the name of the base module.
    """
    assert level >= 1
    if self.base_module is None:
      raise ValueError("Attempting relative import in non-package.")
    components = self.base_module.split(".")
    sub_module = ".".join(components[0:-level])
    ast = self._import_name(sub_module)
    self._lookup_all_classes()
    if ast:
      self._verify_ast(ast)
    return ast

  def import_name(self, module_name):
    # This method is used by convert.py for LateType, so memoize results early:
    if module_name in self._import_name_cache:
      return self._import_name_cache[module_name]
    ast = self._import_name(module_name)
    self._lookup_all_classes()
    if ast:
      self._verify_ast(ast)
    self._import_name_cache[module_name] = ast
    return ast

  def _load_builtin(self, subdir, module_name, third_party_only=False):
    """Load a pytd/pyi that ships with pytype or typeshed."""
    # Try our own type definitions first.
    if not third_party_only:
      builtin_dir = utils.get_versioned_path(subdir, self.python_version)
      mod = builtins.ParsePredefinedPyTD(
          builtin_dir, module_name, self.python_version)
      if not mod:
        mod = builtins.ParsePredefinedPyTD(
            builtin_dir, module_name, self.python_version,
            as_package=True)
      if mod:
        return self.load_file(filename=self.PREFIX + module_name,
                              module_name=module_name,
                              ast=mod)
    if self.use_typeshed:
      return self._load_typeshed_builtin(subdir, module_name)
    return None

  def _load_typeshed_builtin(self, subdir, module_name):
    """Load a pyi from typeshed."""
    mod = typeshed.parse_type_definition(
        subdir, module_name, self.python_version,
        self.typeshed_location, use_pickled=False)
    if mod:
      return self.load_file(filename=self.PREFIX + module_name,
                            module_name=module_name,
                            ast=mod)
    return None

  def _import_name(self, module_name, log_failure=True):
    """Load a name like 'sys' or 'foo.bar.baz'.

    Args:
      module_name: The name of the module. May contain dots.

    Returns:
      The parsed file, instance of pytd.TypeDeclUnit, or None if we
      the module wasn't found.
    """
    assert os.sep not in module_name, (os.sep, module_name)
    log.debug("Trying to import %r", module_name)
    # Builtin modules (but not standard library modules!) take precedence
    # over modules in PYTHONPATH.
    # Note: while typeshed no longer has a builtins subdir, the pytd
    # tree still does, and order is important here.
    mod = self._load_builtin("builtins", module_name)
    if mod:
      return mod

    file_ast = self._import_file(module_name, module_name.split("."))
    if file_ast:
      return file_ast

    # The standard library is (typically) towards the end of PYTHONPATH.
    mod = self._load_builtin("stdlib", module_name)
    if mod:
      return mod

    # Third party modules from typeshed (typically site-packages) come last.
    if not self.imports_map:
      mod = self._load_builtin(
          "third_party", module_name, third_party_only=True)
      if mod:
        return mod

    if log_failure:
      log.warning("Couldn't import module %s %r in (path=%r) imports_map: %s",
                  module_name, module_name, self.pythonpath,
                  "%d items" % len(self.imports_map) if
                  self.imports_map else "none")
      if log.isEnabledFor(logging.DEBUG) and self.imports_map:
        for module, path in self.imports_map.items():
          log.debug("%s -> %s", module, path)

    return None

  def _import_file(self, module_name, module_name_split):
    """Helper for import_relative: try to load an AST, using pythonpath.

    Loops over self.pythonpath, taking care of the semantics for
    __init__, and pretending there's an empty __init__ if the path (derived from
    module_name_split) is a directory.

    Args:
      module_name: The name of the module. May contain dots.
      module_name_split: module_name.split(".")
    Returns:
      The parsed file (AST) if found, otherwise None.

    """
    for searchdir in self.pythonpath:
      path = os.path.join(searchdir, *module_name_split)
      # See if this is a directory with a "__init__.py" defined.
      # (These also get automatically created in imports_map_loader.py)
      init_path = os.path.join(path, "__init__")
      init_ast = self._load_pyi(init_path, module_name)
      if init_ast is not None:
        log.debug("Found module %r with path %r", module_name, init_path)
        return init_ast
      elif self.imports_map is None and os.path.isdir(path):
        # We allow directories to not have an __init__ file.
        # The module's empty, but you can still load submodules.
        log.debug("Created empty module %r with path %r",
                  module_name, init_path)
        return self._create_empty(filename=os.path.join(path, "__init__.pyi"),
                                  module_name=module_name)
      else:  # Not a directory
        file_ast = self._load_pyi(path, module_name)
        if file_ast is not None:
          log.debug("Found module %r in path %r", module_name, path)
          return file_ast
    return None

  def _load_pyi(self, path, module_name):
    """Load a pyi from the path.

    Args:
      path: Path to the file (without '.pyi' or similar extension).
      module_name: Name of the module (may contain dots).
    Returns:
      The parsed pyi, instance of pytd.TypeDeclUnit, or None if we didn't
      find the module.
    """
    if self.imports_map is not None:
      if path in self.imports_map:
        full_path = self.imports_map[path]
      else:
        return None
    else:
      full_path = path + ".pyi"

    # We have /dev/null entries in the import_map - os.path.isfile() returns
    # False for those. However, we *do* want to load them. Hence exists / isdir.
    if os.path.exists(full_path) and not os.path.isdir(full_path):
      return self.load_file(filename=full_path, module_name=module_name)
    else:
      return None

  def concat_all(self):
    if not self._concatenated:
      self._concatenated = pytd_utils.Concat(
          *(module.ast for module in self._modules.values()),
          name="<all>")
    return self._concatenated

  def _get_module_map(self):
    return {name: module.ast for name, module in self._modules.items()}

  def can_see(self, module):
    """Reports whether the Loader can find the module."""
    # Assume that if there is no imports_map that any module can be found.
    if not self.imports_map:
      return True
    return (module in self.imports_map or
            "%s/__init__" % module in self.imports_map)


class PickledPyiLoader(Loader):
  """A Loader which always loads pickle instead of PYI, for speed."""

  def __init__(self, use_pickled_typeshed=True, *args, **kwargs):
    super(PickledPyiLoader, self).__init__(*args, **kwargs)
    self._use_pickled_typeshed = use_pickled_typeshed

  def _load_typeshed_builtin(self, subdir, module_name):
    if not self._use_pickled_typeshed:
      return super(PickledPyiLoader, self)._load_typeshed_builtin(
          subdir, module_name)
    try:
      filename, _ = typeshed.get_type_definition_filename(
          subdir, module_name, self.python_version,
          self.typeshed_location, use_pickled=True)
    except IOError:
      return None
    else:
      return self.load_file(module_name, filename)

  def load_file(self, module_name, filename, ast=None):
    """Load (or retrieve from cache) a module and resolve its dependencies."""
    if not os.path.splitext(filename)[1].startswith(".pickled"):
      return super(PickledPyiLoader, self).load_file(module_name, filename, ast)
    existing = self._get_existing_ast(module_name, filename)
    if existing:
      return existing
    loaded_ast = pytd_utils.LoadPickle(filename)
    # At this point ast.name and module_name could be different.
    # They are later synced in ProcessAst.
    dependencies = [d for d in loaded_ast.dependencies
                    if d != loaded_ast.ast.name]
    soft_dependencies = [d for d in loaded_ast.soft_dependencies
                         if d != loaded_ast.ast.name]
    loaded_ast = serialize_ast.EnsureAstName(loaded_ast, module_name)
    self._modules[module_name] = Module(module_name, filename, loaded_ast.ast)
    self._load_ast_dependencies(dependencies, soft_dependencies,
                                ast, module_name)
    try:
      ast = serialize_ast.ProcessAst(loaded_ast, self._get_module_map())
    except serialize_ast.UnrestorableDependencyError as e:
      del self._modules[module_name]
      raise BadDependencyError(e.message, module_name)
    self._modules[module_name].ast = ast
    self._modules[module_name].dirty = False
    return ast
