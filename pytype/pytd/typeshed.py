"""Utilities for parsing typeshed files."""

import os


from pytype.pytd import utils


def get_typeshed_file(toplevel, module, version, typeshed_dir=None):
  """Get the contents of a typeshed file, typically with a file name *.pyi.

  Arguments:
    toplevel: the top-level directory within typeshed/, typically "builtins",
      "stdlib" or "third_party".
    module: module name (e.g., "sys" or "__builtins__"). Can contain dots, if
      it's a submodule.
    version: The Python version. (major, minor)
    typeshed_dir: Optional. The directory of typeshed. If this isn't passed,
      the directory is either retrieved from the environment variable
      "TYPESHED_HOME" (if that is set) or otherwise assumed to be
      directly under pytype (i.e., /{some_path}/pytype/typeshed).

  Returns:
    The contents of the file
  Raises:
    IOError: if file not found
  """
  loader = globals().get("__loader__", None)
  if typeshed_dir is None:
    typeshed_dir = os.getenv("TYPESHED_HOME")
  if typeshed_dir is not None:
    prefix = os.path.join(typeshed_dir, toplevel)
  else:
    prefix = os.path.join(os.path.dirname(__file__), "..", "typeshed", toplevel)
  if not os.path.isdir(prefix):
    # typeshed doesn't have 'builtins' anymore:
    # https://github.com/python/typeshed/pull/42
    assert toplevel == "builtins"
    raise IOError("No directory %s" % prefix)
  filename = os.path.join(*module.split(".")) + ".pyi"
  versions = ["%d.%d" % (version[0], minor)
              for minor in range(version[1], -1, -1)]
  # E.g. for Python 3.5, try 3.5/, 3.4/, 3.3/, ..., 3.0/, 3/, 2and3.
  # E.g. for Python 2.7, try 2.7/, 2.6/, ..., 2/, 2and3.
  # The order is the same as that of mypy. See default_lib_path in
  # https://github.com/JukkaL/mypy/blob/master/mypy/build.py#L249
  for v in versions + [str(version[0]), "2and3"]:
    path = os.path.join(prefix, v, filename)
    if loader and typeshed_dir is None:
      # PEP 302 loader API
      data = loader.get_data(path)  # See GetPredefinedFile in utils.py
      if data:
        return data
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

