"""Load and link .pyi files."""

import collections
import logging
import os

from pytype import file_utils
from pytype import module_utils
from pytype import utils
from pytype.pyi import parser
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import typeshed
from pytype.pytd import visitors
from pytype.pytd.parse import builtins
from six.moves import cPickle

log = logging.getLogger(__name__)


LOADER_ATTR_TO_CONFIG_OPTION_MAP = {
    "base_module": "module_name",
    "python_version": "python_version",
    "pythonpath": "pythonpath",
    "imports_map": "imports_map",
    "use_typeshed": "typeshed",
}


PICKLE_EXT = ".pickled"


# Allow a file to be used as the designated default pyi for blacklisted files
DEFAULT_PYI_PATH_SUFFIX = None


def is_pickle(filename):
  return os.path.splitext(filename)[1].startswith(PICKLE_EXT)


def _is_default_pyi(path):
  return DEFAULT_PYI_PATH_SUFFIX and path.endswith(DEFAULT_PYI_PATH_SUFFIX)


def create_loader(options):
  """Create a pytd loader."""
  kwargs = {attr: getattr(options, opt)
            for attr, opt in LOADER_ATTR_TO_CONFIG_OPTION_MAP.items()}
  if options.precompiled_builtins:
    return PickledPyiLoader.load_from_pickle(
        options.precompiled_builtins, **kwargs)
  elif options.use_pickled_files:
    return PickledPyiLoader(**kwargs)
  else:
    return Loader(**kwargs)


def get_module_name(filename, pythonpath):
  """Get the module name, or None if we can't determine it."""
  if filename:
    filename = os.path.normpath(filename)
    # Keep path '' as is; infer_module will handle it.
    pythonpath = [path and os.path.normpath(path) for path in pythonpath]
    return module_utils.infer_module(filename, pythonpath).name


ResolvedModule = collections.namedtuple(
    "ResolvedModule", ("module_name", "filename", "ast"))


class Module(object):
  """Represents a parsed module.

  Attributes:
    module_name: The module name, e.g. "numpy.fft.fftpack".
    filename: The filename of the pytd that describes the module. Needs to be
      unique. Will be in one of the following formats:
      - "pytd:{module_name}" for pytd files that ship with pytype.
      - "pytd:{filename}" for pyi files that ship with typeshed.
      - "{filename}" for other pyi files.
    ast: The parsed PyTD. Internal references will be resolved, but
      NamedType nodes referencing other modules might still be unresolved.
    pickle: The AST as a pickled string. As long as this field is not None, the
      ast will be None.
    dirty: The initial value of the dirty attribute.
  """

  def __init__(self, module_name, filename, ast,
               pickle=None, dirty=True):
    self.module_name = module_name
    self.filename = filename
    self.ast = ast
    self.pickle = pickle
    self.dirty = dirty

  def needs_unpickling(self):
    return bool(self.pickle)


class BadDependencyError(Exception):
  """If we can't resolve a module referenced by the one we're trying to load."""

  def __init__(self, module_error, src=None):
    referenced = ", referenced from %r" % src if src else ""
    super(BadDependencyError, self).__init__(module_error + referenced)

  def __str__(self):
    return utils.message(self)


class Loader(object):
  """A cache for loaded PyTD files.

  Typically, you'll have one instance of this class, per module.

  Attributes:
    builtins: The builtins ast.
    typing: The typing ast.
    base_module: The full name of the module we're based in (i.e., the module
      that's importing other modules using this loader).
    python_version: The target Python version.
    pythonpath: The PYTHONPATH.
    imports_map: A short_path -> full_name mapping for imports.
    use_typeshed: Whether to use https://github.com/python/typeshed.
  """

  PREFIX = "pytd:"  # for pytd files that ship with pytype

  def __init__(self,
               base_module,
               python_version,
               pythonpath=(),
               imports_map=None,
               use_typeshed=True,
               modules=None):
    self.python_version = utils.normalize_version(python_version)
    self._modules = modules or self._base_modules(self.python_version)
    if self._modules["__builtin__"].needs_unpickling():
      self._unpickle_module(self._modules["__builtin__"])
    if self._modules["typing"].needs_unpickling():
      self._unpickle_module(self._modules["typing"])
    self.builtins = self._modules["__builtin__"].ast
    self.typing = self._modules["typing"].ast
    self.base_module = base_module
    self.pythonpath = pythonpath
    self.imports_map = imports_map
    self.use_typeshed = use_typeshed
    self._concatenated = None
    self._import_name_cache = {}  # performance cache
    self._aliases = {}
    self._prefixes = set()
    # Paranoid verification that pytype.main properly checked the flags:
    if imports_map is not None:
      assert pythonpath == [""], pythonpath

  def save_to_pickle(self, filename):
    """Save to a pickle. See PickledPyiLoader.load_from_pickle for reverse."""
    # We assume that the Loader is in a consistent state here. In particular, we
    # assume that for every module in _modules, all the transitive dependencies
    # have been loaded.
    items = tuple((name, serialize_ast.StoreAst(module.ast))
                  for name, module in sorted(self._modules.items()))
    # Preparing an ast for pickling clears its class pointers, making it
    # unsuitable for reuse, so we have to discard the builtins cache.
    builtins.InvalidateCache(self.python_version)
    # Now pickle the pickles. We keep the "inner" modules as pickles as a
    # performance optimization - unpickling is slow.
    pytd_utils.SavePickle(items, filename, compress=True)

  def _unpickle_module(self, module):
    raise NotImplementedError()  # overwritten in PickledPyiLoader

  def _base_modules(self, python_version):
    bltins, typing = builtins.GetBuiltinsAndTyping(python_version)
    return {
        "__builtin__":
        Module("__builtin__", self.PREFIX + "__builtin__", bltins, dirty=False),
        "typing":
        Module("typing", self.PREFIX + "typing", typing, dirty=False)
    }

  def _parse_predefined(self, pytd_subdir, module, as_package=False):
    """Parse a pyi/pytd file in the pytype source tree."""
    try:
      filename, src = pytd_utils.GetPredefinedFile(pytd_subdir, module,
                                                   as_package=as_package)
    except IOError:
      return None
    ast = parser.parse_string(src, filename=filename, name=module,
                              python_version=self.python_version)
    assert ast.name == module
    return ast

  def _resolve_builtins(self, pyval, ast=None):
    builtins_lookup = visitors.LookupBuiltins(self.builtins, full_names=False)
    if ast:
      builtins_lookup.EnterTypeDeclUnit(ast)
    pyval = pyval.Visit(builtins_lookup)
    pyval = pyval.Visit(visitors.ExpandCompatibleBuiltins(self.builtins))
    return pyval

  def _resolve_external_and_local_types(self, pyval, ast=None):
    dependencies = self._collect_ast_dependencies(pyval)
    if dependencies:
      self._load_ast_dependencies(dependencies, ast or pyval)
      pyval = self._resolve_external_types(pyval, ast and ast.name)
    local_lookup = visitors.LookupLocalTypes()
    if ast:
      local_lookup.EnterTypeDeclUnit(ast)
    pyval = pyval.Visit(local_lookup)
    return pyval

  def _postprocess_pyi(self, pyval, ast):
    """Apply all the PYI transformations we need."""
    pyval = self._resolve_builtins(pyval, ast)
    pyval = self._resolve_external_and_local_types(pyval, ast)
    return pyval

  def _create_empty(self, module_name, filename):
    return self.load_file(module_name, filename,
                          pytd_utils.CreateModule(module_name))

  def _get_existing_ast(self, module_name):
    existing = self._modules.get(module_name)
    if existing:
      if existing.needs_unpickling():
        self._unpickle_module(existing)
      return existing.ast
    return None

  def load_file(self, module_name, filename, ast=None):
    """Load (or retrieve from cache) a module and resolve its dependencies."""
    self._concatenated = None  # invalidate
    # Check for an existing ast first
    existing = self._get_existing_ast(module_name)
    if existing:
      return existing
    if not ast:
      ast = parser.parse_file(filename=filename, name=module_name,
                              python_version=self.python_version)
    return self._process_module(module_name, filename, ast)

  def _process_module(self, module_name, filename, ast):
    """Create a module from a loaded ast and save it to the loader cache.

    Args:
      module_name: The fully qualified name of the module being imported.
        May be None.
      filename: The file the ast was generated from. May be None.
      ast: The pytd.TypeDeclUnit representing the module.

    Returns:
      The ast (pytd.TypeDeclUnit) as represented in this loader.
    """
    module = Module(module_name, filename, ast)
    # Builtins need to be resolved before the module is cached so that they are
    # not mistaken for local types. External types can be left unresolved
    # because they are unambiguous.
    module.ast = self._resolve_builtins(module.ast)
    self._modules[module_name] = module
    try:
      module.ast = self._resolve_external_and_local_types(module.ast)
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
    if module_name:
      self.add_module_prefixes(module_name)
    return module.ast

  def _collect_ast_dependencies(self, ast):
    """Goes over an ast and returns all references module names."""
    deps = visitors.CollectDependencies()
    ast.Visit(deps)
    return deps.dependencies

  def _resolve_module_alias(self, name, ast, ast_name=None):
    """Check if a given name is an alias and resolve it if so."""
    # name is bare, but aliases are stored as "ast_name.alias".
    if ast is None:
      return name
    key = "%s.%s" % (ast_name or ast.name, name)
    for alias, value in ast.aliases:
      if alias == key and isinstance(value, pytd.Module):
        return value.module_name
    return name

  def _load_ast_dependencies(self, dependencies, ast, ast_name=None):
    """Fill in all ClassType.cls pointers and load reexported modules."""
    for dep_name in dependencies:
      name = self._resolve_module_alias(dep_name, ast, ast_name)
      if dep_name != name:
        # We have an alias. Store it in the aliases map.
        self._aliases[dep_name] = name
      if name in self._modules and self._modules[name].ast:
        other_ast = self._modules[name].ast
      else:
        other_ast = self._import_name(name)
        if other_ast is None:
          prefix = name
          while "." in prefix:
            prefix, _ = prefix.rsplit(".", 1)
            other_ast = self._import_name(prefix)
            if other_ast:
              break
          if other_ast:
            # If any prefix is a valid module, then we'll assume that we're
            # importing a nested class.
            continue
          else:
            error = "Can't find pyi for %r" % name
            raise BadDependencyError(error, ast_name or ast.name)
      # If `name` is a package, try to load any base names not defined in
      # __init__ as submodules.
      if (not self._modules[name].filename or
          os.path.basename(self._modules[name].filename) != "__init__.pyi"):
        continue
      try:
        other_ast.Lookup("__getattr__")
      except KeyError:
        for base_name in dependencies[dep_name]:
          if base_name == "*":
            continue
          full_name = "%s.%s" % (name, base_name)
          try:
            other_ast.Lookup(full_name)
          except KeyError:
            # Don't check the import result - _resolve_external_types will raise
            # a better error.
            self._import_name(full_name)

  def _resolve_external_types(self, pyval, ast_name=None):
    name = ast_name or pyval.name
    try:
      pyval = pyval.Visit(visitors.LookupExternalTypes(
          self._get_module_map(), self_name=name,
          module_alias_map=self._aliases))
    except KeyError as e:
      raise BadDependencyError(utils.message(e), name)
    return pyval

  def _finish_pyi(self, pyval, ast=None):
    module_map = self._get_module_map()
    module_map[""] = ast or pyval  # The module itself (local lookup)
    pyval.Visit(visitors.FillInLocalPointers(module_map))

  def _verify_pyi(self, pyval, ast_name=None):
    try:
      pyval.Visit(visitors.VerifyLookup(ignore_late_types=True))
    except ValueError as e:
      raise BadDependencyError(utils.message(e), ast_name or pyval.name)
    pyval.Visit(visitors.VerifyContainers())

  def resolve_type(self, pyval, ast):
    """Resolve a pytd value, using the given ast for local lookup."""
    pyval = self._postprocess_pyi(pyval, ast)
    self._lookup_all_classes()
    self._finish_pyi(pyval, ast)
    self._verify_pyi(pyval, ast.name)
    return pyval

  def resolve_ast(self, ast):
    """Resolve the dependencies of an AST, without adding it to our modules."""
    return self.resolve_type(ast, ast)

  def _lookup_all_classes(self):
    for module in self._modules.values():
      if module.dirty:
        self._finish_pyi(module.ast)
        module.dirty = False

  def import_relative_name(self, name):
    """IMPORT_NAME with level=-1. A name relative to the current directory."""
    if self.base_module is None:
      raise ValueError("Attempting relative import in non-package.")
    path = self.base_module.split(".")[:-1]
    path.append(name)
    ast = self._import_name(".".join(path))
    self._lookup_all_classes()
    ast = self.finish_and_verify_ast(ast)
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
    ast = self.finish_and_verify_ast(ast)
    return ast

  def import_name(self, module_name):
    # This method is used by convert.py for LateType, so memoize results early:
    if module_name in self._import_name_cache:
      return self._import_name_cache[module_name]
    ast = self._import_name(module_name)
    self._lookup_all_classes()
    ast = self.finish_and_verify_ast(ast)
    self._import_name_cache[module_name] = ast
    return ast

  def finish_and_verify_ast(self, ast):
    """Verify the ast, doing external type resolution first if necessary."""
    if ast:
      try:
        self._verify_pyi(ast)
      except BadDependencyError:
        # In the case of a circular import, an external type may be left
        # unresolved. As long as the module containing the unresolved type does
        # not also contain a circular import, an extra lookup should resolve it.
        ast = self._resolve_external_types(ast)
        self._verify_pyi(ast)
    return ast

  def add_module_prefixes(self, module_name):
    for prefix in module_utils.get_all_prefixes(module_name):
      self._prefixes.add(prefix)

  def has_module_prefix(self, prefix):
    return prefix in self._prefixes

  def _load_builtin(self, subdir, module_name, third_party_only=False):
    """Load a pytd/pyi that ships with pytype or typeshed."""
    # Try our own type definitions first.
    if not third_party_only:
      builtin_dir = file_utils.get_versioned_path(subdir, self.python_version)
      mod = self._parse_predefined(builtin_dir, module_name)
      if not mod:
        mod = self._parse_predefined(builtin_dir, module_name, as_package=True)
      if mod:
        return self.load_file(filename=self.PREFIX + module_name,
                              module_name=module_name,
                              ast=mod)
    if self.use_typeshed:
      return self._load_typeshed_builtin(subdir, module_name)
    return None

  def _load_typeshed_builtin(self, subdir, module_name):
    """Load a pyi from typeshed."""
    loaded = typeshed.parse_type_definition(
        subdir, module_name, self.python_version)
    if loaded:
      filename, mod = loaded
      return self.load_file(filename=self.PREFIX + filename,
                            module_name=module_name, ast=mod)
    return None

  def _import_name(self, module_name):
    """Load a name like 'sys' or 'foo.bar.baz'.

    Args:
      module_name: The name of the module. May contain dots.

    Returns:
      The parsed file, instance of pytd.TypeDeclUnit, or None if we
      the module wasn't found.
    """
    existing = self._get_existing_ast(module_name)
    if existing:
      return existing

    assert os.sep not in module_name, (os.sep, module_name)
    log.debug("Trying to import %r", module_name)
    # Builtin modules (but not standard library modules!) take precedence
    # over modules in PYTHONPATH.
    # Note: while typeshed no longer has a builtins subdir, the pytd
    # tree still does, and order is important here.
    mod = self._load_builtin("builtins", module_name)
    if mod:
      return mod

    file_ast, path = self._import_file(module_name, module_name.split("."))
    if file_ast:
      if _is_default_pyi(path):
        # Remove the default module from the cache; we will return it later if
        # nothing else supplies the module AST.
        default = self._modules.get(module_name)
        del self._modules[module_name]
      else:
        return file_ast

    # The standard library is (typically) towards the end of PYTHONPATH.
    mod = self._load_builtin("stdlib", module_name)
    if mod:
      return mod

    # Third party modules from typeshed (typically site-packages) come last.
    mod = self._load_builtin("third_party", module_name, third_party_only=True)
    if mod:
      return mod

    # Now return the default module if we have found nothing better.
    if file_ast:
      self._modules[module_name] = default
      return file_ast

    log.warning("Couldn't import module %s %r in (path=%r) imports_map: %s",
                module_name, module_name, self.pythonpath,
                "%d items" % len(self.imports_map) if
                self.imports_map is not None else "none")
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
      The parsed file (AST) and file path if found, otherwise None.

    """
    for searchdir in self.pythonpath:
      path = os.path.join(searchdir, *module_name_split)
      # See if this is a directory with a "__init__.py" defined.
      # (These also get automatically created in imports_map_loader.py)
      init_path = os.path.join(path, "__init__")
      init_ast, full_path = self._load_pyi(init_path, module_name)
      if init_ast is not None:
        log.debug("Found module %r with path %r", module_name, init_path)
        return init_ast, full_path
      elif self.imports_map is None and os.path.isdir(path):
        # We allow directories to not have an __init__ file.
        # The module's empty, but you can still load submodules.
        log.debug("Created empty module %r with path %r",
                  module_name, init_path)
        filename = os.path.join(path, "__init__.pyi")
        ast = self._create_empty(filename=filename, module_name=module_name)
        return ast, filename
      else:  # Not a directory
        file_ast, full_path = self._load_pyi(path, module_name)
        if file_ast is not None:
          log.debug("Found module %r in path %r", module_name, path)
          return file_ast, full_path
    return None, None

  def _load_pyi(self, path, module_name):
    """Load a pyi from the path.

    Args:
      path: Path to the file (without '.pyi' or similar extension).
      module_name: Name of the module (may contain dots).
    Returns:
      The parsed pyi, instance of pytd.TypeDeclUnit, and full path, or None if
      we didn't find the module.
    """
    if self.imports_map is not None:
      if path in self.imports_map:
        full_path = self.imports_map[path]
      else:
        return None, None
    else:
      full_path = path + ".pyi"

    # We have /dev/null entries in the import_map - os.path.isfile() returns
    # False for those. However, we *do* want to load them. Hence exists / isdir.
    if os.path.exists(full_path) and not os.path.isdir(full_path):
      ast = self.load_file(filename=full_path, module_name=module_name)
      return ast, full_path
    else:
      return None, None

  def concat_all(self):
    if not self._concatenated:
      self._concatenated = pytd_utils.Concat(
          *(module.ast for module in self._modules.values()
            if module.ast),
          name="<all>")
    return self._concatenated

  def _get_module_map(self):
    return {name: module.ast for name, module in self._modules.items()
            if module.ast}

  def can_see(self, module):
    """Reports whether the Loader is allowed to use the module."""
    # If there is no imports_map or we are allowed to look up modules in
    # typeshed, then any module that can be found can be used.
    if self.imports_map is None or self.use_typeshed:
      return True
    return (module in self.imports_map or
            "%s/__init__" % module in self.imports_map)

  def get_resolved_modules(self):
    """Gets a name -> ResolvedModule map of the loader's resolved modules."""
    resolved_modules = {}
    for name, mod in self._modules.items():
      if not mod.dirty:
        resolved_modules[name] = ResolvedModule(
            mod.module_name, mod.filename, mod.ast)
    return resolved_modules


class PickledPyiLoader(Loader):
  """A Loader which always loads pickle instead of PYI, for speed."""

  def __init__(self, *args, **kwargs):
    super(PickledPyiLoader, self).__init__(*args, **kwargs)

  @classmethod
  def load_from_pickle(cls, filename, base_module, **kwargs):
    items = pytd_utils.LoadPickle(filename, compress=True)
    modules = {
        name: Module(name, filename=None, ast=None, pickle=pickle, dirty=False)
        for name, pickle in items
    }
    return cls(base_module=base_module, modules=modules, **kwargs)

  def _unpickle_module(self, module):
    if not module.pickle:
      return
    todo = [module]
    seen = set()
    newly_loaded_asts = []
    while todo:
      m = todo.pop()
      if m in seen:
        continue
      else:
        seen.add(m)
      if not m.pickle:
        continue
      loaded_ast = cPickle.loads(m.pickle)
      deps = [d for d, _ in loaded_ast.dependencies if d != loaded_ast.ast.name]
      loaded_ast = serialize_ast.EnsureAstName(loaded_ast, m.module_name)
      assert m.module_name in self._modules
      todo.extend(self._modules[dependency] for dependency in deps)
      newly_loaded_asts.append(loaded_ast)
      m.ast = loaded_ast.ast
      m.pickle = None
    module_map = self._get_module_map()
    for loaded_ast in newly_loaded_asts:
      unused_new_serialize_ast = serialize_ast.FillLocalReferences(
          loaded_ast, module_map)
    assert module.ast

  def load_file(self, module_name, filename, ast=None):
    """Load (or retrieve from cache) a module and resolve its dependencies."""
    if not is_pickle(filename):
      return super(PickledPyiLoader, self).load_file(module_name, filename, ast)
    existing = self._get_existing_ast(module_name)
    if existing:
      # TODO(kramm): When does this happen?
      return existing
    loaded_ast = pytd_utils.LoadPickle(filename)
    # At this point ast.name and module_name could be different.
    # They are later synced in ProcessAst.
    dependencies = {d: names for d, names in loaded_ast.dependencies
                    if d != loaded_ast.ast.name}
    loaded_ast = serialize_ast.EnsureAstName(loaded_ast, module_name, fix=True)
    self._modules[module_name] = Module(module_name, filename, loaded_ast.ast)
    self._load_ast_dependencies(dependencies, ast, module_name)
    try:
      ast = serialize_ast.ProcessAst(loaded_ast, self._get_module_map())
    except serialize_ast.UnrestorableDependencyError as e:
      del self._modules[module_name]
      raise BadDependencyError(utils.message(e), module_name)
    # Mark all the module's late dependencies as explicitly imported.
    for d, _ in loaded_ast.late_dependencies:
      if d != loaded_ast.ast.name:
        self.add_module_prefixes(d)

    self._modules[module_name].ast = ast
    self._modules[module_name].pickle = None
    self._modules[module_name].dirty = False
    return ast
