"""Utilities for parsing typeshed files."""

import os


from pytype import utils
from pytype.pytd.parse import builtins


class Typeshed(object):
  """A typeshed installation.

  The location is either retrieved from the environment variable
  "TYPESHED_HOME" (if set) or otherwise assumed to be directly under
  pytype (i.e., /{some_path}/pytype/typeshed).
  """

  def __init__(self):
    home = os.getenv("TYPESHED_HOME")
    if home and not os.path.isdir(home):
      raise IOError("No typeshed directory %s" % home)

    if home:
      self._typeshed_path = home
    else:
      # Not guaranteed to really exist (.egg, etc)
      pytype_base = os.path.split(os.path.dirname(__file__))[0]
      self._typeshed_path = os.path.join(pytype_base, "typeshed")

    self._env_home = home
    self._missing = frozenset(self._load_missing())

  def _load_file(self, path):
    if self._env_home:
      filename = os.path.join(self._env_home, path)
      with open(filename, "rb") as f:
        return filename, f.read()
    else:
      # Use typeshed bundled with pytype
      filename = os.path.join(self._typeshed_path, path)
      data = utils.load_pytype_file(filename)
      return filename, data

  def _load_missing(self):
    return set()

  @property
  def missing(self):
    """Set of known-missing typeshed modules, as strings of paths."""
    return self._missing

  @property
  def typeshed_path(self):
    """Path of typeshed's root directory.

    Returns:
      Base of filenames returned by get_module_file(). Not guaranteed to exist
      if typeshed is bundled with pytype.
    """
    return self._typeshed_path

  def get_module_file(self, toplevel, module, version):
    """Get the contents of a typeshed file, typically with a file name *.pyi.

    Arguments:
      toplevel: the top-level directory within typeshed/, typically "builtins",
        "stdlib" or "third_party".
      module: module name (e.g., "sys" or "__builtins__"). Can contain dots, if
        it's a submodule.
      version: The Python version. (major, minor)

    Returns:
      A tuple with the filename and contents of the file
    Raises:
      IOError: if file not found
    """
    module_path = os.path.join(*module.split("."))
    versions = ["%d.%d" % (version[0], minor)
                for minor in range(version[1], -1, -1)]
    # E.g. for Python 3.5, try 3.5/, 3.4/, 3.3/, ..., 3.0/, 3/, 2and3.
    # E.g. for Python 2.7, try 2.7/, 2.6/, ..., 2/, 2and3.
    # The order is the same as that of mypy. See default_lib_path in
    # https://github.com/JukkaL/mypy/blob/master/mypy/build.py#L249
    for v in versions + [str(version[0]), "2and3"]:
      path_rel = os.path.join(toplevel, v, module_path)

      # Give precedence to missing.txt
      if path_rel in self._missing:
        return (os.path.join(self._typeshed_path, "nonexistent",
                             path_rel + ".pyi"),
                builtins.DEFAULT_SRC)

      for path in [os.path.join(path_rel, "__init__.pyi"), path_rel + ".pyi"]:
        try:
          return self._load_file(path)
        except IOError:
          pass

    raise IOError("Couldn't find %s" % module)


_typeshed = None


def parse_type_definition(pyi_subdir, module, python_version):
  """Load and parse a *.pyi from typeshed.

  Args:
    pyi_subdir: the directory where the module should be found
    module: the module name (without any file extension)
    python_version: sys.version_info[:2]

  Returns:
    The AST of the module; None if the module doesn't have a definition.
  """
  global _typeshed
  if _typeshed is None:
    _typeshed = Typeshed()

  try:
    filename, src = _typeshed.get_module_file(pyi_subdir,
                                              module,
                                              python_version)
  except IOError:
    return None
  return builtins.ParsePyTD(src, filename=filename, module=module,
                            python_version=python_version).Replace(name=module)
