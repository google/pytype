"""Load and link .pyi files."""

import collections
import logging
import os
import pickle

from typing import Dict, Iterable, Optional, Tuple

from pytype import module_utils
from pytype import utils
from pytype.pyi import parser
from pytype.pytd import builtins
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import typeshed
from pytype.pytd import visitors

log = logging.getLogger(__name__)


LOADER_ATTR_TO_CONFIG_OPTION_MAP = {
    "base_module": "module_name",
    "imports_map": "imports_map",
    "open_function": "open_function",
    "python_version": "python_version",
    "pythonpath": "pythonpath",
    "use_typeshed": "typeshed",
}


PICKLE_EXT = ".pickled"


# Allow a file to be used as the designated default pyi for blacklisted files
DEFAULT_PYI_PATH_SUFFIX = None


# Always load this module from typeshed, even if we have it in the imports map
_ALWAYS_PREFER_TYPESHED = frozenset({"typing_extensions"})


# Type alias
_AST = pytd.TypeDeclUnit


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

  def __init__(self, python_version, modules=None):
    self.python_version = python_version
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
    bltins, typing = builtins.GetBuiltinsAndTyping()
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

  def __init__(self, imports_map, pythonpath):
    self.imports_map = imports_map
    self.pythonpath = pythonpath

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
    for searchdir in self.pythonpath:
      path = os.path.join(searchdir, *module_name_split)
      # See if this is a directory with a "__init__.py" defined.
      # (These also get automatically created in imports_map_loader.py)
      init_path = os.path.join(path, "__init__")
      full_path = self.get_pyi_path(init_path)
      if full_path is not None:
        log.debug("Found module %r with path %r", module_name, init_path)
        return full_path, True
      elif self.imports_map is None and os.path.isdir(path):
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
      return full_path
    else:
      return None

  def log_module_not_found(self, module_name):
    log.warning("Couldn't import module %s %r in (path=%r) imports_map: %s",
                module_name, module_name, self.pythonpath,
                "%d items" % len(self.imports_map) if
                self.imports_map is not None else "none")
    if log.isEnabledFor(logging.DEBUG) and self.imports_map:
      for module, path in self.imports_map.items():
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


# TODO(mdemello): move this to pytd.builtins
class _BuiltinLoader:
  """Load builtins from the pytype source tree."""

  def __init__(self, python_version):
    self.python_version = python_version

  def _parse_predefined(self, pytd_subdir, module, as_package=False):
    """Parse a pyi/pytd file in the pytype source tree."""
    try:
      filename, src = pytd_utils.GetPredefinedFile(
          pytd_subdir, module, as_package=as_package)
    except IOError:
      return None
    ast = parser.parse_string(src, filename=filename, name=module,
                              python_version=self.python_version)
    assert ast.name == module
    return ast

  def get_builtin(self, builtin_dir, module_name):
    """Load a stub that ships with pytype."""
    mod = self._parse_predefined(builtin_dir, module_name)
    # For stubs in pytype's stubs/ directory, we use the module name prefixed
    # with "pytd:" for the filename. Package filenames need an "/__init__.pyi"
    # suffix for Module.is_package to recognize them.
    if mod:
      filename = module_name
    else:
      mod = self._parse_predefined(builtin_dir, module_name, as_package=True)
      filename = os.path.join(module_name, "__init__.pyi")
    return filename, mod


class Loader:
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
    open_function: A custom file opening function.
  """

  PREFIX = "pytd:"  # for pytd files that ship with pytype

  def __init__(self,
               base_module,
               python_version,
               pythonpath=(),
               imports_map=None,
               use_typeshed=True,
               modules=None,
               open_function=open):
    self.python_version = utils.normalize_version(python_version)
    self._modules = _ModuleMap(self.python_version, modules)
    self.builtins = self._modules["builtins"].ast
    self.typing = self._modules["typing"].ast
    self.base_module = base_module
    self._path_finder = _PathFinder(imports_map, pythonpath)
    self._builtin_loader = _BuiltinLoader(self.python_version)
    self._resolver = _Resolver(self.builtins)
    self.use_typeshed = use_typeshed
    self.open_function = open_function
    self._import_name_cache = {}  # performance cache
    self._aliases = {}
    self._prefixes = set()
    # Paranoid verification that pytype.main properly checked the flags:
    if imports_map is not None:
      assert pythonpath == [""], pythonpath

  # Delegate some attributes
  @property
  def pythonpath(self):
    return self._path_finder.pythonpath

  @pythonpath.setter
  def pythonpath(self, val):
    self._path_finder.pythonpath = val

  @property
  def imports_map(self):
    return self._path_finder.imports_map

  @imports_map.setter
  def imports_map(self, val):
    self._path_finder.imports_map = val

  def save_to_pickle(self, filename):
    """Save to a pickle. See PickledPyiLoader.load_from_pickle for reverse."""
    # We assume that the Loader is in a consistent state here. In particular, we
    # assume that for every module in _modules, all the transitive dependencies
    # have been loaded.
    items = tuple(
        (name, serialize_ast.StoreAst(
            module.ast, open_function=self.open_function))
        for name, module in sorted(self._modules.items()))
    # Preparing an ast for pickling clears its class pointers, making it
    # unsuitable for reuse, so we have to discard the builtins cache.
    builtins.InvalidateCache()
    # Now pickle the pickles. We keep the "inner" modules as pickles as a
    # performance optimization - unpickling is slow.
    pytd_utils.SavePickle(
        items, filename, compress=True, open_function=self.open_function)

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
      with self.open_function(filename, "r") as f:
        mod_ast = parser.parse_string(
            f.read(), filename=filename, name=module_name,
            python_version=self.python_version)
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
    if self.base_module is None:
      raise ValueError("Attempting relative import in non-package.")
    path = self.base_module.split(".")[:-1]
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
    if self.base_module is None:
      raise ValueError("Attempting relative import in non-package.")
    components = self.base_module.split(".")
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
    if self.use_typeshed:
      return self._load_typeshed_builtin(subdir, module_name)
    return None

  def _load_typeshed_builtin(self, subdir, module_name):
    """Load a pyi from typeshed."""
    loaded = typeshed.parse_type_definition(
        subdir, module_name, self.python_version)
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

    Loops over self.pythonpath, taking care of the semantics for
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


class PickledPyiLoader(Loader):
  """A Loader which always loads pickle instead of PYI, for speed."""

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  @classmethod
  def load_from_pickle(cls, filename, base_module, **kwargs):
    """Load a pytd module from a pickle file."""
    items = pytd_utils.LoadPickle(
        filename, compress=True,
        open_function=kwargs.get("open_function", open))
    modules = {
        name: Module(name, filename=None, ast=None, pickle=pickle,
                     has_unresolved_pointers=False)
        for name, pickle in items
    }
    return cls(base_module=base_module, modules=modules, **kwargs)

  def load_file(self, module_name, filename, mod_ast=None):
    """Load (or retrieve from cache) a module and resolve its dependencies."""
    if not is_pickle(filename):
      return super().load_file(module_name, filename, mod_ast)
    existing = self._modules.get_existing_ast(module_name)
    if existing:
      return existing
    loaded_ast = pytd_utils.LoadPickle(
        filename, open_function=self.open_function)
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
