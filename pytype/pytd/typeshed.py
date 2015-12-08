"""Utilities for parsing typeshed files."""

import os


from pytype.pytd import utils


def get_typeshed_file(toplevel, module, version):
  """Get the contents of a typeshed file, typically with a file name *.pyi.

  Arguments:
    toplevel: the top-level directory, typically "builtins", "stdlib" or
        "third_party".
    module: module name (e.g., "sys" or "__builtins__"). Can contain dots, if
      it's a submodule.
    version: The Python version. (major, minor)
  Returns:
    The contents of the file
  Raises:
    IOError: if file not found
  """
  prefix = os.path.join(os.path.dirname(__file__), "..", "typeshed", toplevel)
  assert os.path.isdir(prefix)
  filename = os.path.join(*module.split(".")) + ".pyi"
  versions = ["%d.%d" % (version[0], minor)
              for minor in range(version[1], -1, -1)]
  # E.g. for Python 3.5, try 2and3/, then 3/, then 3.5/, 3.4/, 3.3/, ..., 3.0/.
  # E.g. for Python 2.7  try 2and3/, then 2/, then 2.7/, 2.6/, ...
  # The order is the same as that of mypy. See default_lib_path in
  # https://github.com/JukkaL/mypy/blob/master/mypy/build.py#L249
  for v in ["2and3", str(version[0])] + versions:
    path = os.path.join(prefix, v, filename)
    if os.path.isfile(path):
      with open(path, "rb") as fi:
        return fi.read()
  raise IOError("Couldn't find %s" % filename)


def parse_type_definition(pyi_subdir, module, python_version):
  """Load and parse a *.pyi from typeshed.

  Args:
    pyi_subdir: the directory where the module should be found
    module: the module name (without any file extension)
    python_version: sys.version_info[:2]

  Returns:
    The AST of the module; None if the module doesn't have a definition.
  """
  try:
    src = get_typeshed_file(pyi_subdir, module, python_version)
  except IOError:
    return None
  name = os.path.join(str(python_version), module + ".pyi")  # for debugging
  return utils.ParsePyTD(src, filename=name, module=module,
                         python_version=python_version).Replace(name=module)

