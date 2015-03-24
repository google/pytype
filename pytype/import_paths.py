"""Code for dealing with import paths."""

import os


from pytype import abstract
from pytype.pytd import utils


def module_name_to_pytd(module_name, level, python_version):  # pylint: disable=unused-argument
  """Convert a name like 'sys' to the corresponding pytd source code.

  Args:
    module_name: Name of a module. The "abc" in "import abc".
    level: For normal imports, -1. If the Python syntax was "from . import abc",
      this will be 1. For "from .. import abc", it'll be 2, and so on.
    python_version: The Python version to import the module for. Used for
      builtin modules.

  Returns:
    The parsed pytd. Instance of pytd.TypeDeclUnit.

  Raises:
    IOError: If we couldn't find this module.
  """
  filename = os.path.join("builtins", module_name + ".pytd")
  src = utils.GetDataFile(filename)
  return abstract.parse_pytd(src, filename=filename, version=python_version)

