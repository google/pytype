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

  def __init__(self, typeshed_location, use_pickled):
    home = os.getenv("TYPESHED_HOME")
    if home and not os.path.isdir(home):
      raise IOError("No typeshed directory %s" % home)

    self._use_pickled = use_pickled  # deprecated
    self._raw_typeshed_location = typeshed_location
    if home:
      self._typeshed_path = home
    else:
      if os.path.isabs(typeshed_location):
        self._typeshed_path = typeshed_location
      else:
        # Not guaranteed to really exist (.egg, etc)
        pytype_base = os.path.split(os.path.dirname(__file__))[0]
        self._typeshed_path = os.path.join(pytype_base, typeshed_location)
    self._env_home = home
    self._missing = frozenset(self._load_missing())

  @property
  def use_pickled(self):
    return self._use_pickled

  def _load_file(self, path):
    if self._env_home:
      filename = os.path.join(self._env_home, path)
      with open(filename, "rb") as f:
        return filename, f.read()
    else:
      data = utils.load_pytype_file(os.path.join(
          self._typeshed_path, path))
      return os.path.join(self._typeshed_path, path), data

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

  def _ignore(self, module, version):
    """Return True if we ignore a file in typeshed."""
    if module == "builtins" and version[0] == 2:
      # The Python 2 version of "builtin" is a mypy artifact. This module
      # doesn't actually exist, in Python 2.7.
      return True
    return False

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
    if self._ignore(module, version):
      raise IOError("Couldn't find %s" % module)
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

      # TODO(mdemello): handle this in the calling code.
      for path in [os.path.join(path_rel, "__init__.pyi"), path_rel + ".pyi"]:
        try:
          if self._use_pickled:
            name, src = self._load_file(
                utils.replace_extension(path, ".pickled"))
          else:
            name, src = self._load_file(path)
          return name, src
        except IOError:
          pass

    raise IOError("Couldn't find %s" % module)

  def get_all_stdlib_module_names(self, python_version):
    """Get the names of all modules in typeshed and pytype/pytd/builtins."""
    if self._env_home:
      raise NotImplementedError("Not implemented: Can't scan external typeshed")
    if self._raw_typeshed_location != "typeshed":
      raise NotImplementedError("Can't scan typeshed not in ./typeshed")
    major = python_version[0]
    subdirs = [os.path.join("pytd/builtins/%d" % major),
               os.path.join("pytd/stdlib/%d" % major),
               "typeshed/stdlib/%d" % major,
               "typeshed/stdlib/2and3",
               "typeshed/third_party/2and3",
              ]
    if major == 3:
      for i in range(0, python_version[1] + 1):
        # iterate over 3.0, 3.1, 3.2, ...
        subdirs.append("typeshed/stdlib/3.%d" % i)
    module_names = set()
    for subdir in subdirs:
      try:
        contents = list(utils.list_pytype_files(subdir))
      except utils.NoSuchDirectory:
        pass
      else:
        for filename in contents:
          module_names.add(utils.path_to_module_name(filename))
    assert "ctypes" in module_names  # sanity check
    return module_names

  def read_blacklist(self):
    """Read the typeshed blacklist."""
    if self._env_home or self._raw_typeshed_location != "typeshed":
      raise NotImplementedError("Can't read blacklist outside ./typeshed")
    data = utils.load_pytype_file("typeshed/tests/pytype_blacklist.txt")
    for line in data.splitlines():
      line = line[:line.find("#")].strip()
      if line:
        yield line

  def blacklisted_modules(self, python_version):
    """Return the blacklist, as a list of module names. E.g. ["x", "y.z"]."""
    for full_filename in self.read_blacklist():
      filename = os.path.splitext(full_filename)[0]
      path = filename.split("/")  # E.g. ["stdlib", "2", "html", "parser.pyi"]
      # It's possible that something is blacklisted with a more
      # specific version (e.g. stdlib/3.4/...). That usually just means
      # that this module didn't exist in earlier Python versions. So
      # we can still just use python_version[0].
      if (path[1].startswith(str(python_version[0])) or
          path[1] == "2and3"):
        yield utils.path_to_module_name("/".join(path[2:]))


_typeshed = None


def _get_typeshed(typeshed_location, use_pickled):
  """Get the global Typeshed instance."""
  global _typeshed
  if _typeshed is None:
    try:
      _typeshed = Typeshed(typeshed_location, use_pickled)
    except IOError as e:
      # This happens if typeshed is not available. Which is a setup error
      # and should be propagated to the user. The IOError is catched further up
      # in the stack.
      raise AssertionError("Couldn't create Typeshed: %s" % str(e))
  assert _typeshed.use_pickled == use_pickled
  return _typeshed


def get_type_definition_filename(
    pyi_subdir, module, python_version, typeshed_location, use_pickled):
  """Load and return the contents of a typeshed module.

  Args:
    pyi_subdir: the directory where the module should be found.
    module: the module name (without any file extension)
    python_version: sys.version_info[:2]
    typeshed_location: Location of the typeshed interface definitions.
    use_pickled: A boolean, iff True typeshed will try to load pickled files.

  Returns:
    The filename containing the definition.
  """
  typeshed = _get_typeshed(typeshed_location, use_pickled)
  return typeshed.get_module_file(pyi_subdir, module, python_version)[0]


def parse_type_definition(
    pyi_subdir, module, python_version, typeshed_location, use_pickled):
  """Load and parse a *.pyi from typeshed.

  Args:
    pyi_subdir: the directory where the module should be found.
    module: the module name (without any file extension)
    python_version: sys.version_info[:2]
    typeshed_location: Location of the typeshed interface definitions.
    use_pickled: A boolean, iff True typeshed will try to load pickled files.

  Returns:
    The AST of the module; None if the module doesn't have a definition.
  """
  typeshed = _get_typeshed(typeshed_location, use_pickled)
  try:
    filename, src = typeshed.get_module_file(
        pyi_subdir, module, python_version)
  except IOError:
    return None

  ast = builtins.ParsePyTD(src, filename=filename, module=module,
                           python_version=python_version).Replace(name=module)
  return ast
