"""Load and link .pytd files."""

import logging
import os


from pytype import utils
from pytype.pytd import utils as pytd_utils
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
      ExternalType nodes might still be dangling, in which case the Module is
      marked "dirty".
    dirty: Whether this module is fully resolved.
  """

  def __init__(self, module_name, filename, ast):
    self.module_name = module_name
    self.filename = filename
    self.ast = ast
    self.dirty = False


class Loader(object):
  """A cache for loaded PyTD files.

  Typically, you'll have one instance of this class, per module.

  Attributes:
    base_module: The full name of the module we're based in (i.e., the module
      that's importing other modules using this loader).
    python_version: The Python version to import the module for. Used for
      builtin modules.
    imports_map: map of .py file name to corresponding pytd file. These will
                 have been created by separate invocations of pytype -- that is,
                 the situation is similar to javac using .class files that have
                 been created by other invocations of javac.
                 imports_map may be None, which is different from {} -- None
                 means that there was no imports_map whereas {} means it's
                 empty.

    pythonpath: list of directory names to be tried.
    find_pytd_import_ext: file extension pattern for finding an import PyTD.
                          A string. (Builtins always use ".pytd" and ignore
                          this option.)
    import_drop_prefixes: list of prefixes to drop when resolving
                          module name to file name.
    _modules: A map, filename to Module, for caching modules already loaded.
    _concatenated: A concatenated pytd of all the modules. Refreshed when
                   necessary.
  """

  PREFIX = "pytd:"  # for pytd files that ship with pytype

  def __init__(self, base_module, python_version,
               imports_map=None, pythonpath=(),
               find_pytd_import_ext=".pytd",
               import_drop_prefixes=()):
    self.base_module = base_module
    self.python_version = python_version
    self.imports_map = imports_map
    self.pythonpath = pythonpath
    self.find_pytd_import_ext = find_pytd_import_ext
    self.import_drop_prefixes = import_drop_prefixes
    self.builtins = builtins.GetBuiltinsPyTD()
    self._modules = {
        "__builtin__":
        Module("__builtin__", self.PREFIX + "__builtin__", self.builtins)
    }
    self._concatenated = None

  def _resolve_all(self):
    module_map = {name: module.ast
                  for name, module in self._modules.items()}
    for module in self._modules.values():
      if module.dirty:
        module.ast.Visit(
            visitors.InPlaceLookupExternalClasses(module_map, True))
        module.dirty = False

  def _create_empty(self, module_name, filename):
    return self._load_file(module_name,
                           filename,
                           pytd_utils.EmptyModule(module_name))

  def _load_file(self, module_name, filename, ast=None):
    """Load (or retrieve from cache) a module and resolve its dependencies."""
    self._concatenated = None  # invalidate
    existing = self._modules.get(module_name)
    if existing:
      if existing.filename != filename:
        raise AssertionError("%s exists as both %s and %s" % (
            module_name, filename, existing.filename))
      return existing.ast
    if not ast:
      ast = pytd_utils.ParsePyTD(filename=filename,
                                 module=module_name,
                                 python_version=self.python_version)
    module = Module(module_name, filename, ast)
    self._modules[module_name] = module
    self.resolve_ast(ast)
    module.dirty = False
    return ast

  def resolve_ast(self, ast):
    """Fill in all ExternalType.cls pointers."""
    deps = visitors.CollectDependencies()
    ast.Visit(deps)
    if deps.modules:
      for name in deps.modules:
        if name not in self._modules:
          self.import_name(name)
      self._resolve_all()
      module_map = {name: module.ast
                    for name, module in self._modules.items()}
      ast.Visit(
          visitors.InPlaceLookupExternalClasses(module_map, True))
    return ast

  def import_relative_name(self, name):
    """IMPORT_NAME with level=-1. A name relative to the current directory."""
    if self.base_module is None:
      raise ValueError("Attempting relative import in non-package.")
    path = self.base_module.split(".")[:-1]
    path.append(name)
    return self.import_name(".".join(path))

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
    return self.import_name(sub_module)

  def import_name(self, module_name):
    """Load a name like 'sys' or 'foo.bar.baz'.

    Args:
      module_name: The name of the module. May contain dots.

    Returns:
      The parsed pytd, instance of pytd.TypeDeclUnit, or None if we
      the module wasn't found.
    """
    assert os.sep not in module_name, (os.sep, module_name)
    log.debug("Trying to import %r", module_name)
    # Builtin modules (but not standard library modules!) take precedence
    # over modules in PYTHONPATH.
    mod = pytd_utils.ParsePredefinedPyTD("builtins", module_name,
                                         self.python_version)
    if mod:
      log.debug("Found builtins %r", module_name)
      return self._load_file(filename=self.PREFIX + module_name,
                             module_name=module_name, ast=mod)

    module_name_split = module_name.split(".")
    for prefix in self.import_drop_prefixes:
      module_name_split = utils.list_strip_prefix(module_name_split,
                                                  prefix.split("."))
    file_ast = self._import_file(module_name, module_name_split)
    if file_ast:
      return file_ast

    # The standard library is (typically) at the end of PYTHONPATH.
    mod = pytd_utils.ParsePredefinedPyTD("stdlib", module_name,
                                         self.python_version)
    if mod:
      return self._load_file(filename="stdlib:"+module_name,
                             module_name=module_name, ast=mod)
    else:
      log.warning(
          "Couldn't import module %s %r in (path=%r) imports_map: %s",
          module_name, module_name_split, self.pythonpath,
          "%d items" % len(self.imports_map) if self.imports_map else "none")
      if self.imports_map is not None:
        for short_path, long_path in self.imports_map.items():
          log.debug("%r => %r", short_path, long_path)
    return None

  def _import_file(self, module_name, module_name_split):
    """Helper for import_relative: try to load an AST, using pythonpath.

    Loops over self.pythonpath, taking care of the semantics for __init__, and
    pretending there's an empty __init__ if the path (derived from
    module_name_split) is a directory.

    Args:
      module_name: The name of the module. May contain dots.
      module_name_split: module_name.split(".")
    Returns:
      The parsed pytd (AST) if found, otherwise None.
    """
    for searchdir in self.pythonpath:
      path = os.path.join(searchdir, *module_name_split)
      # See if this is a directory with a "__init__.py" defined.
# MOE:strip_line For Bazel, have already created a __init__.py file
      init_path = os.path.join(path, "__init__")
      init_ast = self._load_pytd(init_path, module_name)
      if init_ast is not None:
        log.debug("Found module %r with path %r", module_name, init_path)
        return init_ast
      elif os.path.isdir(path):
        # We allow directories to not have an __init__ file.
        # The module's empty, but you can still load submodules.
        # TODO(pludemann): remove this? - it's not standard Python.
        log.debug("Created empty module %r with path %r",
                  module_name, init_path)
        return self._create_empty(
            filename=os.path.join(path, "__init__.pytd"),
            module_name=module_name)
      else:  # Not a directory
        file_ast = self._load_pytd(path, module_name)
        if file_ast is not None:
          log.debug("Found module %r in path %r", module_name, path)
          return file_ast
    return None

  def _load_pytd(self, path, module_name):
    """Load a pytd from the path, using '*'-expansion.

    Args:
      path: Path to the file (without '.pytd' or similar extension).
      module_name: Name of the module (may contain dots).
    Returns:
      The parsed pytd, instance of pytd.TypeDeclUnit, or None if we didn't
      find the module.
    """
    pytd_path = path + self.find_pytd_import_ext
    if self.imports_map is not None:
      if pytd_path in self.imports_map:
        pytd_path = self.imports_map.get(pytd_path)
      else:
        return None
    if os.path.isfile(pytd_path):
      return self._load_file(filename=pytd_path, module_name=module_name)
    else:
      return None

  def concat_all(self):
    if not self._concatenated:
      self._concatenated = pytd_utils.Concat(
          *(module.ast for module in self._modules.values()),
          name="<all>")
    return self._concatenated
