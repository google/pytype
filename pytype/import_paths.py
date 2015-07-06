"""Code for dealing with import paths."""

import os


from pytype.pytd import utils as pytd_utils


def module_name_to_pytd(module_name,
                        level,  # TODO(pludemann): use this
                        python_version,
                        pythonpath):  # pylint: disable=unused-argument
  """Convert a name like 'sys' to the corresponding pytd source code.

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
  # TODO(pludemann): use pythonpath

  filename = os.path.join("builtins", module_name + ".pytd")
  src = pytd_utils.GetDataFile(filename)
  return pytd_utils.ParsePyTD(src, filename=filename,
                              python_version=python_version)
