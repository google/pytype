"""Utilities for parsing typeshed files."""

import collections
import os
import re

from pytype import module_utils
from pytype import pytype_source_utils
from pytype import utils
from pytype.pyi import parser
from pytype.pytd import builtins

import toml


def _get_module_names_in_path(lister, path, python_version):
  """Get module names for all .pyi files in the given path."""
  names = set()
  try:
    contents = list(lister(path, python_version))
  except pytype_source_utils.NoSuchDirectory:
    pass
  else:
    for filename in contents:
      names.add(module_utils.path_to_module_name(filename))
  return names


class Typeshed:
  """A typeshed installation.

  The location is either retrieved from the environment variable
  "TYPESHED_HOME" (if set) or otherwise assumed to be directly under
  pytype (i.e., /{some_path}/pytype/typeshed).
  """

  # Text file of typeshed entries that will not be loaded.
  # The path is relative to typeshed's root directory, e.g. if you set this to
  # "missing.txt" you need to create $TYPESHED_HOME/missing.txt or
  # pytype/typeshed/missing.txt
  # For testing, this file must contain the entry 'stdlib/3/pytypecanary'.
  MISSING_FILE = None

  def __init__(self):
    self._env_home = home = os.getenv("TYPESHED_HOME")
    if home:
      if not os.path.isdir(home):
        raise IOError("Could not find a typeshed installation in "
                      "$TYPESHED_HOME directory %s" % home)
      self._root = home
    else:
      self._root = pytype_source_utils.get_full_path("typeshed")
    self._missing = frozenset(self._load_missing())
    self._stdlib_versions = self._load_stdlib_versions()
    self._third_party_packages = self._load_third_party_packages()

  def _load_file(self, path):
    if self._env_home:
      filename = os.path.join(self._env_home, path)
      with open(filename, "r") as f:
        return filename, f.read()
    else:
      filepath = os.path.join(self._root, path)
      return filepath, pytype_source_utils.load_text_file(filepath)

  def _file_exists(self, relpath):
    """Checks whether the given path, relative to the typeshed root, exists."""
    if self._env_home:
      return os.path.exists(os.path.join(self._root, relpath))
    try:
      # For a non-par pytype installation, load_text_file will either succeed,
      # raise FileNotFoundError, or raise IsADirectoryError.
      # For a par installation, load_text_file will raise FileNotFoundError for
      # both a nonexistent file and a directory.
      pytype_source_utils.load_text_file(os.path.join("typeshed", relpath))
    except FileNotFoundError:
      try:
        # For a non-par installation, we know at this point that relpath does
        # not exist, so _list_files will always raise NoSuchDirectory. For a par
        # installation, we use _list_files to check whether the directory
        # exists; a non-existent directory will produce an empty generator.
        next(self._list_files(relpath))
      except (pytype_source_utils.NoSuchDirectory, StopIteration):
        return False
    except IsADirectoryError:
      return True
    return True

  def _list_files(self, basedir):
    """Lists files recursively in a basedir relative to typeshed root."""
    if self._env_home:
      return pytype_source_utils.list_files(os.path.join(self._root, basedir))
    else:
      return pytype_source_utils.list_pytype_files(
          os.path.join("typeshed", basedir))

  def _load_missing(self):
    if not self.MISSING_FILE:
      return set()
    _, text = self._load_file(self.MISSING_FILE)
    return {line.strip() for line in text.split("\n") if line}

  def _load_stdlib_versions(self):
    """Loads the contents of typeshed/stdlib/VERSIONS.

    VERSIONS lists the stdlib modules with the Python version in which they were
    first added, in the format `{module}: {min_major}.{min_minor}-` or
    `{module}: {min_major}.{min_minor}-{max_major}.{max_minor}`.

    Returns:
      A mapping from module name to ((min_major, min_minor),
      (max_major, max_minor), use_python2) Python version.
      The max tuple can be `None`. The use_python2 member indicates
      whether stubs are present in the @python2 directory. If so,
      stubs outside @python2 should not be used. This is relevant
      if a package contains more files in Python 3 than it did in
      Python 2.
    """
    _, text = self._load_file(os.path.join("stdlib", "VERSIONS"))
    versions = {}
    for line in text.splitlines():
      line2 = line.split("#")[0].strip()
      if not line2:
        continue
      match = re.fullmatch(r"(.+): (\d)\.(\d+)(?:-(?:(\d)\.(\d))?)?", line2)
      assert match
      module, min_major, min_minor, max_major, max_minor = match.groups()
      minimum = (int(min_major), int(min_minor))
      maximum = ((int(max_major), int(max_minor))
                 if max_major is not None and max_minor is not None
                 else None)
      versions[module] = minimum, maximum, False
    for path in self._list_files(os.path.join("stdlib", "@python2")):
      mod, _ = os.path.splitext(path.split(os.path.sep, 1)[0])
      if mod in versions:
        (min_major, min_minor), maximum, _ = versions[mod]
        if min_major == 2:
          versions[mod] = (min_major, min_minor), maximum, True
    return versions

  def _load_third_party_packages(self):
    """Loads package and Python version information for typeshed/stubs/.

    stubs/ contains type information for third-party packages. Each top-level
    directory corresponds to one PyPI package and contains one or more modules,
    plus a metadata file (METADATA.toml). If there are separate Python 2 stubs,
    they live in an @python2 subdirectory. METADATA.toml
    takes @python2 into account, so if a package has both foo.pyi and
    @python2/foo.pyi, METADATA.toml will contain `python2 = True`.

    Returns:
      A mapping from module name to a set of
      (package name, major_python_version) tuples.
    """
    metadata = {}
    modules = collections.defaultdict(set)
    for third_party_file in self._list_files("stubs"):
      parts = third_party_file.split(os.path.sep)
      if parts[-1] == "METADATA.toml":  # {package}/METADATA.toml
        _, metadata_file = self._load_file(
            os.path.join("stubs", third_party_file))
        metadata[parts[0]] = toml.loads(metadata_file)
      elif "@python2" not in parts:  # {package}/{module}
        name, _ = os.path.splitext(parts[1])
        modules[parts[0]].add(name)
    packages = collections.defaultdict(set)
    for package, names in modules.items():
      for name in names:
        # When not specified, packages are Python 3-only
        if metadata[package].get("python2", False):
          packages[name].add((package, 2))
        if metadata[package].get("python3", True):
          packages[name].add((package, 3))
    return packages

  @property
  def missing(self):
    """Set of known-missing typeshed modules, as strings of paths."""
    return self._missing

  @property
  def root(self):
    """Path of typeshed's root directory.

    Returns:
      Base of filenames returned by get_module_file(). Not guaranteed to exist
      if typeshed is bundled with pytype.
    """
    return self._root

  def _ignore(self, module, version):
    """Return True if we ignore a file in typeshed."""
    if module == "builtins" and version[0] == 2:
      # The Python 2 version of "builtin" is a mypy artifact. This module
      # doesn't actually exist, in Python 2.7.
      return True
    return False

  def get_module_file(self, toplevel, module, version):
    """Get the contents of a typeshed .pyi file.

    Arguments:
      toplevel: the top-level directory within typeshed/, "builtins", "stdlib",
        or "third_party". "builtins" doesn't exist but is requested because
        there exists a pytype pyi directory with this name, and "third_party"
        corresponds to the the typeshed/stubs/ directory.
      module: module name (e.g., "sys" or "__builtins__"). Can contain dots, if
        it's a submodule.
      version: The Python version. (major, minor)

    Returns:
      A tuple with the filename and contents of the file
    Raises:
      IOError: if file not found
    """
    module_parts = module.split(".")
    module_path = os.path.join(*module_parts)
    paths = []
    if toplevel == "stdlib":
      # stubs for the stdlib 'foo' module are located in either stdlib/foo or
      # (for Python 2) stdlib/@python2/foo. The VERSIONS file tells us whether
      # stdlib/foo exists and what versions it targets; we always have to check
      # @python2 first for Python 2 stubs.
      path = os.path.join(toplevel, module_path)
      if version[0] == 2:
        paths.append(os.path.join(toplevel, "@python2", module_path))
      if (self._is_module_in_typeshed(module_parts[0], version) or
          path in self.missing):
        paths.append(path)
    elif toplevel == "third_party":
      # For third-party modules, we grab the alphabetically first package that
      # provides a module with the specified name in the right version.
      # TODO(rechen): It would be more correct to check what packages are
      # currently installed and only consider those.
      if module_parts[0] in self._third_party_packages:
        for package, v in sorted(self._third_party_packages[module_parts[0]]):
          if v == version[0]:
            if v == 2:
              # In packages that support Python 2, if @python2/ exists, then it
              # contains the Python 2 stubs; otherwise, the top-level stubs are
              # Python 2and3.
              paths.append(
                  os.path.join("stubs", package, "@python2", module_path))
            paths.append(os.path.join("stubs", package, module_path))
    for path_rel in paths:
      # Give precedence to MISSING_FILE
      if path_rel in self.missing:
        return (os.path.join(self._root, "nonexistent", path_rel + ".pyi"),
                builtins.DEFAULT_SRC)
      # TODO(mdemello): handle this in the calling code.
      for path in [os.path.join(path_rel, "__init__.pyi"), path_rel + ".pyi"]:
        try:
          name, src = self._load_file(path)
          return name, src
        except IOError:
          pass
    raise IOError("Couldn't find %s" % module)

  def _is_module_in_typeshed(self, name, version):
    if name not in self._stdlib_versions:
      return False
    min_version, max_version, _ = self._stdlib_versions[name]
    return (min_version <= version and
            (max_version is None or max_version >= version))

  def get_typeshed_paths(self, python_version):
    """Gets the paths to typeshed's version-specific pyi files."""
    major, _ = python_version
    typeshed_subdirs = []
    if major == 2:
      typeshed_subdirs.append(os.path.join("stdlib", "@python2"))
    typeshed_subdirs.append("stdlib")
    for packages in self._third_party_packages.values():
      for package, v in packages:
        if v == major:
          py2only_dir = os.path.join("stubs", package, "@python2")
          if v == 2 and self._file_exists(py2only_dir):
            typeshed_subdirs.append(os.path.join(py2only_dir))
          else:
            typeshed_subdirs.append(os.path.join("stubs", package))
    return [os.path.join(self._root, d) for d in typeshed_subdirs]

  def get_pytd_paths(self, python_version):
    """Gets the paths to pytype's version-specific pytd files."""
    # TODO(mdemello): Should we add 2and3 here too and stop symlinking?
    return [pytype_source_utils.get_full_path(d) for d in [
        "stubs/builtins/%d" % python_version[0],
        "stubs/stdlib/%d" % python_version[0]]]

  def _list_modules(self, path, python_version):
    """Lists modules for _get_module_names_in_path."""
    for filename in self._list_files(path):
      if filename.startswith("@python2/"):
        # When Python 2 is requested, relative paths that already have the
        # @python2/ prefix stripped are separately listed, so we should always
        # skip paths that start with @python2/.
        continue
      if filename == "VERSIONS" or filename == "METADATA.toml":
        # stdlib/VERSIONS, stubs/{package}/METADATA.toml are metadata files.
        continue
      parts = path.split("/")
      if "stdlib" in parts:
        if "@python2" in parts:
          # stdlib/@python2/ stubs are Python 2-only.
          if python_version[0] != 2:
            continue
        else:
          # Check supported versions for stubs directly in stdlib/.
          module = os.path.splitext(filename)[0].split("/", 1)[0]
          if not self._is_module_in_typeshed(module, python_version):
            continue
      yield filename

  def get_all_module_names(self, python_version):
    """Get the names of all modules in typeshed or bundled with pytype."""
    module_names = set()
    for abspath in self.get_typeshed_paths(python_version):
      relpath = abspath.rpartition("typeshed/")[-1]
      module_names |= _get_module_names_in_path(
          self._list_modules, relpath, python_version)
    for abspath in self.get_pytd_paths(python_version):
      relpath = abspath.rpartition("pytype/")[-1]
      module_names |= _get_module_names_in_path(
          lambda path, unused_ver: pytype_source_utils.list_pytype_files(path),
          relpath, python_version)
    # Also load modules not in typeshed, so that we have a dummy entry for them.
    for f in self.missing:
      parts = f.split("/")
      if ("@python2" in parts) != (python_version[0] == 2):
        continue
      if parts[0] == "stdlib":
        start_index = 1  # remove stdlib/ prefix
      else:
        assert parts[0] == "stubs"
        start_index = 2  # remove stubs/{package}/ prefix
      if parts[start_index] == "@python2":
        start_index += 1
      filename = "/".join(parts[start_index:])
      module_names.add(filename.replace("/", "."))
    assert "ctypes" in module_names  # sanity check
    return module_names

  def read_blacklist(self):
    """Read the typeshed blacklist."""
    _, text = self._load_file(os.path.join("tests", "pytype_exclude_list.txt"))
    for line in text.splitlines():
      if "#" in line:
        line = line[:line.index("#")]
      line = line.strip()
      if line:
        yield line

  def blacklisted_modules(self, python_version):
    """Return the blacklist, as a list of module names. E.g. ["x", "y.z"]."""
    for full_filename in self.read_blacklist():
      filename = os.path.splitext(full_filename)[0]
      path = filename.split(os.path.sep)  # E.g. ["stdlib", "html", "parser"]
      if python_version[0] in self.get_python_major_versions(full_filename):
        yield module_utils.path_to_module_name(os.path.sep.join(path[2:]))

  def get_python_major_versions(self, filename):
    """Gets the Python major versions targeted by the given .pyi file."""
    if os.path.sep + "@python2" + os.path.sep in filename:
      return (2,)
    parts = filename.split(os.path.sep)
    if parts[0] == "stdlib":
      min_version, _, use_python2 = self._stdlib_versions[
          os.path.splitext(parts[1])[0]]
      # If use_python2 is true, we just use the stubs in @python2
      if min_version >= (3, 0) or use_python2:
        return (3,)
      else:
        return (2, 3)
    else:
      assert parts[0] == "stubs"
      package, module = parts[1], os.path.splitext(parts[2])[0]
      versions = []
      for p, v in self._third_party_packages[module]:
        if p != package or v == 2 and self._file_exists(
            os.path.join("stubs", p, "@python2")):
          # If a dedicated @python2 subdirectory exists, then the top-level
          # stubs are Python 3-only.
          continue
        versions.append(v)
      return tuple(versions)


_typeshed = None


def _get_typeshed():
  """Get the global Typeshed instance."""
  global _typeshed
  if _typeshed is None:
    try:
      _typeshed = Typeshed()
    except IOError as e:
      # This happens if typeshed is not available. Which is a setup error
      # and should be propagated to the user. The IOError is catched further up
      # in the stack.
      raise utils.UsageError("Couldn't initalize typeshed:\n %s" % str(e))
  return _typeshed


def parse_type_definition(pyi_subdir, module, python_version):
  """Load and parse a *.pyi from typeshed.

  Args:
    pyi_subdir: the directory where the module should be found.
    module: the module name (without any file extension)
    python_version: sys.version_info[:2]

  Returns:
    None if the module doesn't have a definition.
    Else a tuple of the filename and the AST of the module.
  """
  assert python_version
  typeshed = _get_typeshed()
  try:
    filename, src = typeshed.get_module_file(
        pyi_subdir, module, python_version)
  except IOError:
    return None

  ast = parser.parse_string(src, filename=filename, name=module,
                            python_version=python_version)
  return filename, ast
