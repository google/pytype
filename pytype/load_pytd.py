"""Load and link .pyi files."""

import collections
import logging
import os
import pickle

from typing import Dict, Iterable, Optional, Tuple

from pytype import module_utils
from pytype import utils
from pytype.pyi import parser
from pytype.pytd import builtin_stubs
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import typeshed
from pytype.pytd import visitors

log = logging.getLogger(__name__)

# Allow a file to be used as the designated default pyi for blacklisted files
DEFAULT_PYI_PATH_SUFFIX = None

# Always load this module from typeshed, even if we have it in the imports map
_ALWAYS_PREFER_TYPESHED = frozenset({"typing_extensions"})

# Type alias
_AST = pytd.TypeDeclUnit


def _is_default_pyi(path):
  return DEFAULT_PYI_PATH_SUFFIX and path.endswith(DEFAULT_PYI_PATH_SUFFIX)


def create_loader(options):
  """Create a pytd loader."""
  if options.precompiled_builtins:
    return PickledPyiLoader.load_from_pickle(
        options.precompiled_builtins, options)
  elif options.use_pickled_files:
    return PickledPyiLoader(options)
  else:
    return Loader(options)


ResolvedModule = collections.namedtuple(
    "ResolvedModule", ("module_name", "filename", "ast"))


class Module:
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
    has_unresolved_pointers: Whether all ClassType pointers have been filled in
  """

  # pylint: disable=redefined-outer-name
  def __init__(self, module_name, filename, ast,
               pickle=None, has_unresolved_pointers=True):
    self.module_name = module_name
    self.filename = filename
    self.ast = ast
    self.pickle = pickle
    self.has_unresolved_pointers = has_unresolved_pointers
  # pylint: enable=redefined-outer-name

  def needs_unpickling(self):
    return bool(self.pickle)

  def is_package(self):
    if self.filename == os.devnull:
      # imports_map_loader adds os.devnull entries for __init__.py files in
      # intermediate directories.
      return True
    return self.filename and os.path.basename(self.filename) == "__init__.pyi"


class BadDependencyError(Exception):
  """If we can't resolve a module referenced by the one we're trying to load."""

  def __init__(self, module_error, src=None):
    referenced = ", referenced from %r" % src if src else ""
    super().__init__(module_error + referenced)

  def __str__(self):
    return utils.message(self)


class _ModuleMap:
  """A map of fully qualified module name -> Module."""

  PREFIX = "pytd:"  # for pytd files that ship with pytype

  def __init__(self, options, modules):
    self.options = options
    self._modules: Dict[str, Module] = modules or self._base_modules()
    if self._modules["builtins"].needs_unpickling():
      self._unpickle_module(self._modules["builtins"])
    if self._modules["typing"].needs_unpickling():
      self._unpickle_module(self._modules["typing"])
    self._concatenated = None

  def __getitem__(self, key):
    return self._modules[key]

  def __setitem__(self, key, val):
    self._modules[key] = val

  def __delitem__(self, key):
    del self._modules[key]

  def __contains__(self, key):
    return key in self._modules

  def items(self):
    return self._modules.items()

  def values(self):
    return self._modules.values()

  def get(self, key):
    return self._modules.get(key)

  def get_existing_ast(self, module_name: str) -> Optional[_AST]:
    existing = self._modules.get(module_name)
    if existing:
      if existing.needs_unpickling():
        self._unpickle_module(existing)
      return existing.ast
    return None

  def defined_asts(self) -> Iterable[_AST]:
    """All module ASTs that are not None."""
    return (module.ast for module in self._modules.values() if module.ast)

  def get_module_map(self) -> Dict[str, _AST]:
    """Get a {name: ast} map of all modules with a filled-in ast."""
    return {name: module.ast for name, module in self._modules.items()
            if module.ast}

  def get_resolved_modules(self) -> Dict[str, ResolvedModule]:
    """Get a {name: ResolvedModule} map of all resolved modules."""
    resolved_modules = {}
    for name, mod in self._modules.items():
      if not mod.has_unresolved_pointers:
        resolved_modules[name] = ResolvedModule(
            mod.module_name, mod.filename, mod.ast)
    return resolved_modules

  def _base_modules(self):
    bltins, typing = builtin_stubs.GetBuiltinsAndTyping(
        parser.PyiOptions.from_toplevel_options(self.options))
    return {
        "builtins":
        Module("builtins", self.PREFIX + "builtins", bltins,
               has_unresolved_pointers=False),
        "typing":
        Module("typing", self.PREFIX + "typing", typing,
               has_unresolved_pointers=False)
    }

  def _unpickle_module(self, module):
    """Unpickle a pickled ast and its dependncies."""
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
      loaded_ast = pickle.loads(m.pickle)
      deps = [d for d, _ in loaded_ast.dependencies if d != loaded_ast.ast.name]
      loaded_ast = serialize_ast.EnsureAstName(loaded_ast, m.module_name)
      assert m.module_name in self._modules
      todo.extend(self._modules[dependency] for dependency in deps)
      newly_loaded_asts.append(loaded_ast)
      m.ast = loaded_ast.ast
      m.pickle = None
    module_map = self.get_module_map()
    for loaded_ast in newly_loaded_asts:
      serialize_ast.FillLocalReferences(loaded_ast, module_map)
    assert module.ast

  def concat_all(self):
    if not self._concatenated:
      self._concatenated = pytd_utils.Concat(*self.defined_asts(), name="<all>")
    return self._concatenated

  def invalidate_concatenated(self):
    self._concatenated = None


class _PathFinder:
  """Find a filepath for a module."""

  def __init__(self, options):
    self.options = options

  def find_import(self, module_name: str) -> Tuple[Optional[str], bool]:
    """Search through pythonpath for a module.

    Args:
      module_name: module name

    Returns:
      - (path, file_exists) if we find a path (file_exists will be false if we
        have found a directory where we need to create an __init__.pyi)
      - None if we cannot find a full path
    """
    module_name_split = module_name.split(".")
    for searchdir in self.options.pythonpath:
      path = os.path.join(searchdir, *module_name_split)
      # See if this is a directory with a "__init__.py" defined.
      # (These also get automatically created in imports_map_loader.py)
      init_path = os.path.join(path, "__init__")
      full_path = self.get_pyi_path(init_path)
      if full_path is not None:
        log.debug("Found module %r with path %r", module_name, init_path)
        return full_path, True
      elif self.options.imports_map is None and os.path.isdir(path):
        # We allow directories to not have an __init__ file.
        # The module's empty, but you can still load submodules.
        log.debug("Created empty module %r with path %r",
                  module_name, init_path)
        full_path = os.path.join(path, "__init__.pyi")
        return full_path, False
      else:  # Not a directory
        full_path = self.get_pyi_path(path)
        if full_path is not None:
          log.debug("Found module %r in path %r", module_name, path)
          return full_path, True
    return None, None

  def get_pyi_path(self, path: str) -> Optional[str]:
    """Get a pyi file from path if it exists."""
    if self.options.imports_map is not None:
      if path in self.options.imports_map:
        full_path = self.options.imports_map[path]
      else:
        return None
    else:
      full_path = path + ".pyi"

    # We have /dev/null entries in the import_map - os.path.isfile() returns
    # False for those. However, we *do* want to load them. Hence exists / isdir.
    if os.path.exists(full_path) and not os.path.isdir(full_path):
      return full_path
    else:
      return None

  def log_module_not_found(self, module_name):
    log.warning("Couldn't import module %s %r in (path=%r) imports_map: %s",
                module_name, module_name, self.options.pythonpath,
                "%d items" % len(self.options.imports_map) if
                self.options.imports_map is not None else "none")
    if log.isEnabledFor(logging.DEBUG) and self.options.imports_map:
      for module, path in self.options.imports_map.items():
        log.debug("%s -> %s", module, path)


class _Resolver:
  """Resolve symbols in a pytd tree."""

  def __init__(self, builtins_ast):
    self.builtins_ast = builtins_ast
    self.allow_singletons = False

  def _lookup(self, visitor, mod_ast, lookup_ast):
    if lookup_ast:
      visitor.EnterTypeDeclUnit(lookup_ast)
    mod_ast = mod_ast.Visit(visitor)
    return mod_ast

  def resolve_local_types(self, mod_ast, *, lookup_ast=None):
    local_lookup = visitors.LookupLocalTypes(self.allow_singletons)
    return self._lookup(local_lookup, mod_ast, lookup_ast)

  def resolve_builtin_types(self, mod_ast, *, lookup_ast=None):
    bltn_lookup = visitors.LookupBuiltins(
        self.builtins_ast, full_names=False,
        allow_singletons=self.allow_singletons)
    mod_ast = self._lookup(bltn_lookup, mod_ast, lookup_ast)
    mod_ast = mod_ast.Visit(
        visitors.ExpandCompatibleBuiltins(self.builtins_ast))
    return mod_ast

  def resolve_external_types(self, mod_ast, module_map, aliases, *,
                             mod_name=None):
    name = mod_name or mod_ast.name
    try:
      mod_ast = mod_ast.Visit(visitors.LookupExternalTypes(
          module_map, self_name=name, module_alias_map=aliases))
    except KeyError as e:
      raise BadDependencyError(utils.message(e), name) from e
    return mod_ast

  def resolve_module_alias(self, name, *, lookup_ast=None,
                           lookup_ast_name=None):
    """Check if a given name is an alias and resolve it if so."""
    # name is bare, but aliases are stored as "ast_name.alias".
    if lookup_ast is None:
      return name
    ast_name = lookup_ast_name or lookup_ast.name
    key = f"{ast_name}.{name}"
    for alias, value in lookup_ast.aliases:
      if alias == key and isinstance(value, pytd.Module):
        return value.module_name
    return name

  def verify(self, mod_ast, *, mod_name=None):
    try:
      mod_ast.Visit(visitors.VerifyLookup(ignore_late_types=True))
    except ValueError as e:
      name = mod_name or mod_ast.name
      raise BadDependencyError(utils.message(e), name) from e
    mod_ast.Visit(visitors.VerifyContainers())

  @classmethod
  def collect_dependencies(cls, mod_ast):
    """Goes over an ast and returns all references module names."""
    deps = visitors.CollectDependencies()
    mod_ast.Visit(deps)
    return deps.dependencies


class Loader:
  """A cache for loaded PyTD files.

  Typically, you'll have one instance of this class, per module.

  Attributes:
    options: A config.Options object.
    builtins: The builtins ast.
    typing: The typing ast.
  """

  PREFIX = "pytd:"  # for pytd files that ship with pytype

  def __init__(self, options, modules=None):
    self.options = options
    self._modules = _ModuleMap(options, modules)
    self.builtins = self._modules["builtins"].ast
    self.typing = self._modules["typing"].ast
    self._path_finder = _PathFinder(options)
    self._builtin_loader = builtin_stubs.BuiltinLoader(
        parser.PyiOptions.from_toplevel_options(options))
    self._resolver = _Resolver(self.builtins)
    self._import_name_cache = {}  # performance cache
    self._aliases = {}
    self._prefixes = set()
    # Paranoid verification that pytype.main properly checked the flags:
    if options.imports_map is not None:
      assert options.pythonpath == [""], options.pythonpath

  def get_default_ast(self):
    return builtin_stubs.GetDefaultAst(
        parser.PyiOptions.from_toplevel_options(self.options))

  def save_to_pickle(self, filename):
    """Save to a pickle. See PickledPyiLoader.load_from_pickle for reverse."""
    # We assume that the Loader is in a consistent state here. In particular, we
    # assume that for every module in _modules, all the transitive dependencies
    # have been loaded.
    items = tuple(
        (name, serialize_ast.StoreAst(
            module.ast, open_function=self.options.open_function))
        for name, module in sorted(self._modules.items()))
    # Preparing an ast for pickling clears its class pointers, making it
    # unsuitable for reuse, so we have to discard the builtins cache.
    builtin_stubs.InvalidateCache()
    # Now pickle the pickles. We keep the "inner" modules as pickles as a
    # performance optimization - unpickling is slow.
    pytd_utils.SavePickle(items, filename, compress=True,
                          open_function=self.options.open_function)

  def _resolve_external_and_local_types(self, mod_ast, lookup_ast=None):
    dependencies = self._resolver.collect_dependencies(mod_ast)
    if dependencies:
      lookup_ast = lookup_ast or mod_ast
      self._load_ast_dependencies(dependencies, lookup_ast)
      mod_ast = self._resolve_external_types(
          mod_ast, lookup_ast and lookup_ast.name)
    mod_ast = self._resolver.resolve_local_types(mod_ast, lookup_ast=lookup_ast)
    return mod_ast

  def _create_empty(self, module_name, filename):
    return self.load_file(module_name, filename,
                          pytd_utils.CreateModule(module_name))

  def load_file(self, module_name, filename, mod_ast=None):
    """Load (or retrieve from cache) a module and resolve its dependencies."""
    # TODO(mdemello): Should we do this in _ModuleMap.__setitem__? Also, should
    # we only invalidate concatenated if existing = None?
    self._modules.invalidate_concatenated()
    # Check for an existing ast first
    existing = self._modules.get_existing_ast(module_name)
    if existing:
      return existing
    if not mod_ast:
      with self.options.open_function(filename, "r") as f:
        mod_ast = parser.parse_string(
            f.read(), filename=filename, name=module_name,
            options=parser.PyiOptions.from_toplevel_options(self.options))
    return self._process_module(module_name, filename, mod_ast)

  def _process_module(self, module_name, filename, mod_ast):
    """Create a module from a loaded ast and save it to the loader cache.

    Args:
      module_name: The fully qualified name of the module being imported.
        May be None.
      filename: The file the ast was generated from. May be None.
      mod_ast: The pytd.TypeDeclUnit representing the module.

    Returns:
      The ast (pytd.TypeDeclUnit) as represented in this loader.
    """
    module = Module(module_name, filename, mod_ast)
    # Builtins need to be resolved before the module is cached so that they are
    # not mistaken for local types. External types can be left unresolved
    # because they are unambiguous.
    self._resolver.allow_singletons = False
    module.ast = self._resolver.resolve_builtin_types(module.ast)
    self._modules[module_name] = module
    try:
      self._resolver.allow_singletons = True
      module.ast = self._resolve_external_and_local_types(module.ast)
      # We need to resolve builtin singletons after we have made sure they are
      # not shadowed by a local or a star import.
      module.ast = self._resolver.resolve_builtin_types(module.ast)
      self._resolver.allow_singletons = False
      # Now that any imported TypeVar instances have been resolved, adjust type
      # parameters in classes and functions.
      module.ast = module.ast.Visit(visitors.AdjustTypeParameters())
      # Now we can fill in internal cls pointers to ClassType nodes in the
      # module. This code executes when the module is first loaded, which
      # happens before any others use it to resolve dependencies, so there are
      # no external pointers into the module at this point.
      module_map = {"": module.ast, module_name: module.ast}
      module.ast.Visit(visitors.FillInLocalPointers(module_map))
    except:
      # don't leave half-resolved modules around
      del self._modules[module_name]
      raise
    if module_name:
      self.add_module_prefixes(module_name)
    return module.ast

  def _try_import_prefix(self, name: str) -> Optional[_AST]:
    """Try importing all prefixes of name, returning the first valid module."""
    prefix = name
    while "." in prefix:
      prefix, _ = prefix.rsplit(".", 1)
      ast = self._import_module_by_name(prefix)
      if ast:
        return ast
    return None

  def _load_ast_dependencies(self, dependencies, lookup_ast,
                             lookup_ast_name=None):
    """Fill in all ClassType.cls pointers and load reexported modules."""
    ast_name = lookup_ast_name or lookup_ast.name
    for dep_name in dependencies:
      name = self._resolver.resolve_module_alias(
          dep_name, lookup_ast=lookup_ast, lookup_ast_name=lookup_ast_name)
      if dep_name != name:
        # We have an alias. Store it in the aliases map.
        self._aliases[dep_name] = name
      if name in self._modules and self._modules[name].ast:
        dep_ast = self._modules[name].ast
      else:
        dep_ast = self._import_module_by_name(name)
        if dep_ast is None:
          dep_ast = self._try_import_prefix(name)
          if dep_ast or f"{ast_name}.{name}" in lookup_ast:
            # If any prefix is a valid module, then we'll assume that we're
            # importing a nested class. If name is in lookup_ast, then it is a
            # local reference and not an import at all.
            continue
          else:
            self._path_finder.log_module_not_found(name)
            raise BadDependencyError("Can't find pyi for %r" % name, ast_name)
      # If `name` is a package, try to load any base names not defined in
      # __init__ as submodules.
      if not self._modules[name].is_package() or "__getattr__" in dep_ast:
        continue
      for base_name in dependencies[dep_name]:
        if base_name == "*":
          continue
        full_name = "%s.%s" % (name, base_name)
        # Check whether full_name is a submodule based on whether it is
        # defined in the __init__ file.
        try:
          attr = dep_ast.Lookup(full_name)
        except KeyError:
          attr = None
        # 'from . import submodule as submodule' produces
        # Alias(submodule, NamedType(submodule)).
        if attr is None or (
            isinstance(attr, pytd.Alias) and attr.name == attr.type.name):
          if not self._import_module_by_name(full_name):
            # Add logging to make debugging easier but otherwise ignore the
            # result - resolve_external_types will raise a better error.
            self._path_finder.log_module_not_found(full_name)

  def _resolve_external_types(self, mod_ast, mod_name=None):
    module_map = self._modules.get_module_map()
    mod_ast = self._resolver.resolve_external_types(
        mod_ast, module_map, self._aliases, mod_name=mod_name)
    return mod_ast

  def _resolve_classtype_pointers(self, mod_ast, *, lookup_ast=None):
    module_map = self._modules.get_module_map()
    module_map[""] = lookup_ast or mod_ast  # The module itself (local lookup)
    mod_ast.Visit(visitors.FillInLocalPointers(module_map))

  def resolve_pytd(self, pytd_node, lookup_ast):
    """Resolve and verify pytd value, using the given ast for local lookup."""
    # NOTE: Modules of dependencies will be loaded into the cache
    pytd_node = self._resolver.resolve_builtin_types(
        pytd_node, lookup_ast=lookup_ast)
    pytd_node = self._resolve_external_and_local_types(
        pytd_node, lookup_ast=lookup_ast)
    self._resolve_classtype_pointers_for_all_modules()
    self._resolve_classtype_pointers(pytd_node, lookup_ast=lookup_ast)
    self._resolver.verify(pytd_node, mod_name=lookup_ast.name)
    return pytd_node

  def resolve_ast(self, ast):
    """Resolve the dependencies of an AST, without adding it to our modules."""
    # NOTE: Modules of dependencies will be loaded into the cache
    return self.resolve_pytd(ast, ast)

  def _resolve_classtype_pointers_for_all_modules(self):
    for module in self._modules.values():
      if module.has_unresolved_pointers:
        self._resolve_classtype_pointers(module.ast)
        module.has_unresolved_pointers = False

  def import_relative_name(self, name: str) -> _AST:
    """IMPORT_NAME with level=-1. A name relative to the current directory."""
    if self.options.module_name is None:
      raise ValueError("Attempting relative import in non-package.")
    path = self.options.module_name.split(".")[:-1]
    path.append(name)
    return self.import_name(".".join(path))

  def import_relative(self, level: int) -> _AST:
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
    if self.options.module_name is None:
      raise ValueError("Attempting relative import in non-package.")
    components = self.options.module_name.split(".")
    sub_module = ".".join(components[0:-level])
    return self.import_name(sub_module)

  def import_name(self, module_name: str) -> _AST:
    if module_name in self._import_name_cache:
      return self._import_name_cache[module_name]
    mod_ast = self._import_module_by_name(module_name)
    if not mod_ast:
      self._path_finder.log_module_not_found(module_name)
    self._resolve_classtype_pointers_for_all_modules()
    mod_ast = self.finish_and_verify_ast(mod_ast)
    self._import_name_cache[module_name] = mod_ast
    return mod_ast

  def finish_and_verify_ast(self, mod_ast):
    """Verify the ast, doing external type resolution first if necessary."""
    if mod_ast:
      try:
        self._resolver.verify(mod_ast)
      except BadDependencyError:
        # In the case of a circular import, an external type may be left
        # unresolved. As long as the module containing the unresolved type does
        # not also contain a circular import, an extra lookup should resolve it.
        mod_ast = self._resolve_external_types(mod_ast)
        self._resolver.verify(mod_ast)
    return mod_ast

  def add_module_prefixes(self, module_name):
    for prefix in module_utils.get_all_prefixes(module_name):
      self._prefixes.add(prefix)

  def has_module_prefix(self, prefix):
    return prefix in self._prefixes

  def _load_builtin(self, subdir, module_name, third_party_only=False):
    """Load a pytd/pyi that ships with pytype or typeshed."""
    # Try our own type definitions first.
    if not third_party_only:
      filename, mod_ast = self._builtin_loader.get_builtin(subdir, module_name)
      if mod_ast:
        return self.load_file(filename=self.PREFIX + filename,
                              module_name=module_name, mod_ast=mod_ast)
    if self.options.typeshed:
      return self._load_typeshed_builtin(subdir, module_name)
    return None

  def _load_typeshed_builtin(self, subdir, module_name):
    """Load a pyi from typeshed."""
    loaded = typeshed.parse_type_definition(
        subdir, module_name,
        parser.PyiOptions.from_toplevel_options(self.options))
    if loaded:
      filename, mod_ast = loaded
      return self.load_file(filename=self.PREFIX + filename,
                            module_name=module_name, mod_ast=mod_ast)
    return None

  def _import_module_by_name(self, module_name):
    """Load a name like 'sys' or 'foo.bar.baz'.

    Args:
      module_name: The name of the module. May contain dots.

    Returns:
      The parsed file, instance of pytd.TypeDeclUnit, or None if we
      the module wasn't found.
    """
    existing = self._modules.get_existing_ast(module_name)
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

    file_ast, path = self._import_file(module_name)
    if file_ast:
      if _is_default_pyi(path) or path == os.devnull:
        # Remove the default module from the cache; we will return it later if
        # nothing else supplies the module AST.
        default = self._modules.get(module_name)
        del self._modules[module_name]
      elif module_name in _ALWAYS_PREFER_TYPESHED:
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
      assert default
      self._modules[module_name] = default
      return file_ast

    return None

  def _import_file(self, module_name):
    """Helper for import_relative: try to load an AST, using pythonpath.

    Loops over self.options.pythonpath, taking care of the semantics for
    __init__, and pretending there's an empty __init__ if the path (derived from
    module_name) is a directory.

    Args:
      module_name: The name of the module. May contain dots.
    Returns:
      The parsed file (AST) and file path if found, otherwise None.
    """
    full_path, file_exists = self._path_finder.find_import(module_name)
    if full_path is None:
      return None, None
    if file_exists:
      mod_ast = self.load_file(filename=full_path, module_name=module_name)
    else:
      mod_ast = self._create_empty(filename=full_path, module_name=module_name)
    assert mod_ast is not None, full_path
    return mod_ast, full_path

  def concat_all(self):
    return self._modules.concat_all()

  def get_resolved_modules(self):
    """Gets a name -> ResolvedModule map of the loader's resolved modules."""
    return self._modules.get_resolved_modules()

  def lookup_builtin(self, name):
    try:
      return self.builtins.Lookup(name)
    except KeyError:
      return self.typing.Lookup(name)


class PickledPyiLoader(Loader):
  """A Loader which always loads pickle instead of PYI, for speed."""

  @classmethod
  def load_from_pickle(cls, filename, options):
    """Load a pytd module from a pickle file."""
    items = pytd_utils.LoadPickle(filename, compress=True,
                                  open_function=options.open_function)
    modules = {
        name: Module(name, filename=None, ast=None, pickle=pickle,
                     has_unresolved_pointers=False)
        for name, pickle in items
    }
    return cls(options, modules=modules)

  def load_file(self, module_name, filename, mod_ast=None):
    """Load (or retrieve from cache) a module and resolve its dependencies."""
    if not pytd_utils.IsPickle(filename):
      return super().load_file(module_name, filename, mod_ast)
    existing = self._modules.get_existing_ast(module_name)
    if existing:
      return existing
    loaded_ast = pytd_utils.LoadPickle(
        filename, open_function=self.options.open_function)
    # At this point ast.name and module_name could be different.
    # They are later synced in ProcessAst.
    dependencies = {d: names for d, names in loaded_ast.dependencies
                    if d != loaded_ast.ast.name}
    loaded_ast = serialize_ast.EnsureAstName(loaded_ast, module_name, fix=True)
    self._modules[module_name] = Module(module_name, filename, loaded_ast.ast)
    self._load_ast_dependencies(dependencies, lookup_ast=mod_ast,
                                lookup_ast_name=module_name)
    try:
      ast = serialize_ast.ProcessAst(loaded_ast, self._modules.get_module_map())
    except serialize_ast.UnrestorableDependencyError as e:
      del self._modules[module_name]
      raise BadDependencyError(utils.message(e), module_name) from e
    # Mark all the module's late dependencies as explicitly imported.
    for d, _ in loaded_ast.late_dependencies:
      if d != loaded_ast.ast.name:
        self.add_module_prefixes(d)

    self._modules[module_name].ast = ast
    self._modules[module_name].pickle = None
    self._modules[module_name].has_unresolved_pointers = False
    return ast
