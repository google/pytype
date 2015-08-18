"""Code for loading and linking .pytd files."""

import glob
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
    pythonpath: list of directory names to be tried.
    find_pytd_import_ext: file extension pattern for finding an import PyTD.
      A string. (Builtins always use ".pytd" and ignore this option.)
    import_drop_prefixes: list of prefixes to drop when resolving
      module name to file name.
   import_error_is_fatal: whether a load_pytd (for importing a dependency)
     should generate a fatal error or just a regular error.
     See main option --import_error_is_fatal
    _modules: A map, filename to Module, for caching modules already loaded.
    _concatenated: A concatenated pytd of all the modules. Refreshed when
      necessary.
  """

  PREFIX = "pytd:"  # for pytd files that ship with pytype

  def __init__(self, base_module, python_version, pythonpath=(),
               find_pytd_import_ext=".pytd",
               import_drop_prefixes=(), import_error_is_fatal=False):
    self.base_module = base_module
    self.python_version = python_version
    self.pythonpath = pythonpath
    self.find_pytd_import_ext = find_pytd_import_ext
    self.import_drop_prefixes = import_drop_prefixes
    self.import_error_is_fatal = import_error_is_fatal
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
        module.ast.Visit(visitors.InPlaceLookupExternalClasses(module_map,
                                                               True))
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
    ast = ast or pytd_utils.ParsePyTD(filename=filename,
                                      module=module_name,
                                      python_version=self.python_version)
    module = Module(module_name, filename, ast)
    self._modules[module_name] = module
    deps = visitors.CollectDependencies()
    ast.Visit(deps)
    for name in deps.modules:
      if name not in self._modules:
        self.import_name(name)
    if deps.modules:
      module.dirty = True
    self._resolve_all()
    return ast

  def import_relative(self, level):
    """Import a module relative to our base module.

    Args:
      level: Relative level:
        https://docs.python.org/2/library/functions.html#__import__
        https://docs.python.org/3/library/functions.html#__import__
        E.g.
         -1: (Python <= 3.1) "Normal" import. Try both absolute and relative.
          0: Absolute import.
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
      The parsed pytd, instance of pytd.TypeDeclUnit, or None if we didn't
      find the module.
    """
    assert "/" not in module_name
    log.debug("Trying to import %s", module_name)
    # Builtin modules (but not standard library modules!) take precedence
    # over modules in PYTHONPATH.
    mod = pytd_utils.ParsePredefinedPyTD("builtins", module_name,
                                         self.python_version)
    if mod:
      log.debug("Found builtins %s", module_name)
      return self._load_file(filename=self.PREFIX + module_name,
                             module_name=module_name, ast=mod)

    module_name_split = module_name.split(".")
    for prefix in self.import_drop_prefixes:
      module_name_split = utils.list_strip_prefix(module_name_split,
                                                  prefix.split("."))

    for searchdir in self.pythonpath:
      path = os.path.join(searchdir, *module_name_split)
      if os.path.isdir(path):
        # TODO(pludemann): need test case (esp. for empty __init__.py)
        init_ast = self._load_pytd_from_glob(os.path.join(path, "__init__"),
                                             module_name)
        if init_ast is not None:
          log.debug("Found module %s/__init__ in path %s", module_name, path)
          return init_ast
        else:
          # We allow directories to not have an __init__ file.
          # The module's empty, but you can still load submodules.
          return self._create_empty(
              filename=os.path.join(path, "__init__.pytd"),
              module_name=module_name)
      else:
        file_ast = self._load_pytd_from_glob(path, module_name)
        if file_ast is not None:
          log.debug("Found module %s in path %s", module_name, path)
          return file_ast

    # The standard library is (typically) at the end of PYTHONPATH.
    mod = pytd_utils.ParsePredefinedPyTD("stdlib", module_name,
                                         self.python_version)
    if mod:
      log.debug("Found stdlib %s", module_name)
      return self._load_file(filename="stdlib:"+module_name,
                             module_name=module_name, ast=mod)
    elif self.import_error_is_fatal:
      log.critical("Couldn't import module %s", module_name)
      # TODO(pludemann): sys.exit(-1) ?
    else:
      log.error("Couldn't import module %s", module_name)
    return None

  def _load_pytd_from_glob(self, path, module_name):
    """Load a pytd from the path, using '*'-expansion.

    Args:
      path: Path to the file (without '.pytd' or similar extension).
      module_name: Name of the module (may contain dots).
    Returns:
      The parsed pytd, instance of pytd.TypeDeclUnit, or None if we didn't
      find the module.
    """
    pytd_path = path + self.find_pytd_import_ext
    files = sorted(glob.glob(pytd_path))
    if files:
      if len(files) > 1:
        # TODO(pludemann): Check whether the contents differ?
        # MOE:strip_line TODO(pludemann): Prioritize "#" items (see pytype.bzl).
        log.warn("Multiple files for %s: %s", pytd_path, files)
      return self._load_file(filename=files[0], module_name=module_name)
    else:
      return None

  def concat_all(self):
    if not self._concatenated:
      self._concatenated = pytd_utils.Concat(
          *(module.ast for module in self._modules.values()),
          name="<all>")
    return self._concatenated
