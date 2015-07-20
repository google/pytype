"""Code for loading and linking .pytd files."""

import logging
import os

from pytype import utils
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import visitors


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

  base_module: The full name of the module we're based in (i.e., the module
    that's importing other modules using this loader).
  python_version: The Python version to import the module for. Used for
    builtin modules.
  pythonpath: list of directory names to be tried.
  pytd_import_ext: file extension(s) for import PyTD. A string.
    (Builtins always use ".pytd" and ignore this option.)
  import_drop_prefixes: list of prefixes to drop when resolving
    module name to file name.
  _modules: A map, filename to Module, for caching modules already loaded.
  """

  def __init__(self, base_module, python_version, pythonpath=(),
               pytd_import_ext=".pytd", import_drop_prefixes=()):
    assert pytd_import_ext.startswith(".")
    self.base_module = base_module
    self.python_version = python_version
    self.pythonpath = pythonpath
    self.pytd_import_ext = pytd_import_ext
    self.import_drop_prefixes = import_drop_prefixes
    self._modules = {}  # filename to Module

  def _resolve_all(self):
    module_map = {name: module.ast
                  for name, module in self._modules.items()}
    for module in self._modules.values():
      if module.dirty:
        module.ast.Visit(visitors.LookupExternalClasses(module_map, True))
        module.dirty = False

  def _create_empty(self, module_name, filename):
    return self._load_file(module_name,
                           filename,
                           pytd_utils.EmptyModule(module_name))

  def _load_file(self, module_name, filename, ast=None):
    """Load (or retrieve from cache) a module and resolve its dependencies."""
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
    if deps.modules:
      module.dirty = True
    for name in deps.modules:
      if name not in self._modules:
        self.import_name(name)
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
    logging.info("Trying to import %s", module_name)
    # Builtin modules (but not standard library modules!) take precedence
    # over modules in PYTHONPATH.
    mod = pytd_utils.ParsePredefinedPyTD("builtins", module_name,
                                         self.python_version)
    if mod:
      return self._load_file(filename="builtin:"+module_name,
                             module_name=module_name, ast=mod)

    module_name_split = module_name.split(".")
    for prefix in self.import_drop_prefixes:
      module_name_split = utils.list_strip_prefix(module_name_split,
                                                  prefix.split("."))

    for searchdir in self.pythonpath:
      path = os.path.join(searchdir, *module_name_split)
      if os.path.isdir(path):
        # TODO(pludemann): need test case (esp. for empty __init__.py)
        init_filename = "__init__" + self.pytd_import_ext
        init_pytd = os.path.join(path, init_filename)
        if os.path.isfile(init_pytd):
          return self._load_file(filename=init_pytd, module_name=module_name)
        else:
          # We allow directories to not have an __init__ file.
          # The module's empty, but you can still load submodules.
          return self._create_empty(filename=init_pytd, module_name=module_name)
      elif os.path.isfile(path + self.pytd_import_ext):
        return self._load_file(filename=path + self.pytd_import_ext,
                               module_name=module_name)

    # The standard library is (typically) at the end of PYTHONPATH.
    mod = pytd_utils.ParsePredefinedPyTD("stdlib", module_name,
                                         self.python_version)
    if mod:
      return self._load_file(filename="stdlib:"+module_name,
                             module_name=module_name, ast=mod)
