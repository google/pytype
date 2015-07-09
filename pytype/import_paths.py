"""Code for dealing with import paths."""

import logging
import os


from pytype.pytd import utils as pytd_utils

log = logging.getLogger(__name__)


def _load_integrated_pytd(filename, python_version):
  """Load and parse a *.pytd from pytype/pytd/."""
  try:
    src = pytd_utils.GetDataFile(filename)
  except IOError:
    return None
  return pytd_utils.ParsePyTD(src, filename=filename,
                              python_version=python_version)


def module_name_to_pytd(module_name,
                        level,  # TODO(pludemann): use this
                        python_version,
                        pythonpath):  # pylint: disable=unused-argument
  """Convert a name like 'sys' to the corresponding pytd.

  Args:
    module_name: Name of a module. The "abc" in "import abc".
    level: For normal imports, -1. If the Python syntax was "from . import abc",
      this will be 1. For "from .. import abc", it'll be 2, and so on. If this
      is not -1, module_name will be "".
    python_version: The Python version to import the module for. Used for
      builtin modules.

  Returns:
    The parsed pytd. Instance of pytd.TypeDeclUnit.

  Raises:
    IOError: If we couldn't find this module.
  """

  # Builtin modules (but not standard library modules!) take precedence
  # over modules in PYTHONPATH.
  mod = _load_integrated_pytd(os.path.join("builtins", module_name + ".pytd"),
                              python_version)
  if mod:
    return mod

  for searchdir in pythonpath:
    path = os.path.join(searchdir, module_name.replace(".", "/"))
    if os.path.isdir(path):
      init_pytd = os.path.join(path, "__init__.pytd")
      if os.path.isfile(init_pytd):
        return pytd_utils.ParsePyTD(filename=init_pytd,
                                    python_version=python_version)
      else:
        # We allow directories to not have an __init__ file.
        # The module's empty, but you can still load submodules.
        log.warn("No __init__.pytd in %s", path)
        return pytd_utils.EmptyModule()
    elif os.path.isfile(path + ".pytd"):
      return pytd_utils.ParsePyTD(filename=path + ".pytd",
                                  python_version=python_version)

  # The standard library is (typically) at the end of PYTHONPATH.
  return _load_integrated_pytd(os.path.join("stdlib", module_name + ".pytd"),
                               python_version)

