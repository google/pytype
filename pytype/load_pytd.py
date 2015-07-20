"""Code for dealing with import paths."""

import logging
import os


from pytype import utils
from pytype.pytd import utils as pytd_utils

log = logging.getLogger(__name__)


def module_name_to_pytd(module_name,
                        level,  # TODO(pludemann): use this
                        python_version,
                        pythonpath=(),
                        pytd_import_ext=None,
                        import_drop_prefixes=()):
  """Convert a name like 'sys' to the corresponding pytd.

  Args:
    module_name: Name of a module. The "abc" in "import abc".
    level: Relative level (see below).
    python_version: The Python version to import the module for. Used for
      builtin modules.
    pythonpath: list of directory names to be tried.
    pytd_import_ext: file extension for import PyTD (ignored for builtins)
    import_drop_prefixes: list of prefixes to drop when resolving
                          module name to file name

  Returns:
    The parsed pytd. Instance of pytd.TypeDeclUnit.

  Raises:
    IOError: If we couldn't find this module.

  The module_name and level are used to figure out the path to the PyTD file
  (together wth pythonpath, pytd_import_ext).
  Level is described in
      https://docs.python.org/2/library/functions.html#__import__
      https://docs.python.org/3/library/functions.html#__import__
   and takes these values (-1 is not supported for Python 3.3 and later):
     -1: for normal imports (try both absolute and relative imports)
      0: for absolute imports
      1: "from . import abc"
      2: "from .. import abc"
      etc.
   If level is not -1, module_name will be "".
  """
  # TODO(pludemann): handle absolute, relative imports
  if level not in (-1, 0):
    raise NotImplementedError("Relative paths aren't handled yet: %s" % level)
  # TODO(pludemannn): Add unit tests for Python version 3.1 and 3.3,
  #                   when semantics changed. (e.g., -1 is no longer generated).

  # Builtin modules (but not standard library modules!) take precedence
  # over modules in PYTHONPATH.
  mod = _load_predefined_pytd("builtins", module_name, python_version)
  if mod:
    return mod

  module_name_split = module_name.split(".")
  for prefix in import_drop_prefixes:
    module_name_split = utils.list_strip_prefix(module_name_split,
                                                prefix.split("."))

  for searchdir in pythonpath:
    path = os.path.join(searchdir, *module_name_split)
    if os.path.isdir(path):
      # TODO(pludemann): need test case (esp. for empty __init__.py)
      init_filename = "__init__" + pytd_import_ext
      init_pytd = os.path.join(path, init_filename)
      if os.path.isfile(init_pytd):
        return pytd_utils.ParsePyTD(filename=init_pytd,
                                    module=module_name,
                                    python_version=python_version)
      else:
        # We allow directories to not have an __init__ file.
        # The module's empty, but you can still load submodules.
        log.warn("No %s in %s", init_filename, path)
        return pytd_utils.EmptyModule()
    elif os.path.isfile(path + pytd_import_ext):
      return pytd_utils.ParsePyTD(filename=path + pytd_import_ext,
                                  module=module_name,
                                  python_version=python_version)

  # The standard library is (typically) at the end of PYTHONPATH.
  return _load_predefined_pytd("stdlib", module_name, python_version)


def _load_predefined_pytd(pytd_subdir, module, python_version):
  """Load and parse a *.pytd from pytype/pytd/.

  Args:
    pytd_subdir: the directory where the module should be found
    module: the module name (without any file extension)
    python_version: sys.version_info[:2]

  Returns:
    The AST of the module; None if the module doesn't exist in pytd_subdir.
  """
  try:
    src = pytd_utils.GetPredefinedFile(pytd_subdir, module)
  except IOError:
    return None
  return pytd_utils.ParsePyTD(
      src,
      filename=os.path.join(pytd_subdir, module + ".pytd"),
      python_version=python_version)
