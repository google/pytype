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


def _get_module_names_in_path(lister, path):
  names = set()
  try:
    contents = list(lister(path))
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
    # See https://github.com/google/pytype/issues/820. typeshed's directory
    # structure significantly changed in January 2021. We need to support both
    # the old and the new structures until our bundled typeshed is updated past
    # the restructuring commit.
    self._use_new_structure = os.path.exists(
        os.path.join(self._root, "stdlib", "VERSIONS"))
    if self._use_new_structure:
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

  def _load_missing(self):
    if not self.MISSING_FILE:
      return set()
    _, text = self._load_file(self.MISSING_FILE)
    return {line.strip() for line in text.split("\n") if line}

  def _load_stdlib_versions(self):
    """Loads the contents of typeshed/stdlib/VERSIONS.

    VERSIONS lists the stdlib modules with the Python version in which they were
    first added, in the format `{module}: {major}.{minor}`. Note that this file
    ignores the stdlib/@python2 subdirectory! If stdlib/foo.pyi targets Python
    3.6+ and stdlib/@python2/foo.pyi, 2.7, VERSIONS will contain `foo: 3.6`.

    Returns:
      A mapping from module name to (major, minor) Python version.
    """
    _, text = self._load_file(os.path.join("stdlib", "VERSIONS"))
    versions = {}
    for line in text.splitlines():
      match = re.fullmatch(r"(.+): (\d)\.(\d+)", line)
      assert match
      module, major, minor = match.groups()
      versions[module] = (int(major), int(minor))
    return versions

  def _load_third_party_packages(self):
    """Loads package and Python version information for typeshed/stubs/.

    stubs/ contains type information for third-party packages. Each top-level
    directory corresponds to one PyPI package and contains one or more modules,
    plus a metadata file (METADATA.toml). If there are separate Python 2 stubs,
    they live in an @python2 subdirectory. Unlike stdlib/VERSIONS, METADATA.toml
    does take @python2 into account, so if a package has both foo.pyi and
    @python2/foo.pyi, METADATA.toml will contain `python2 = True`.

    Returns:
      A mapping from module name to a set of
      (package name, major_python_version) tuples.
    """
    third_party_root = os.path.join(self._root, "stubs")
    packages = collections.defaultdict(set)
    for package in os.listdir(third_party_root):
      _, metadata = self._load_file(
          os.path.join(third_party_root, package, "METADATA.toml"))
      metadata = toml.loads(metadata)
      for name in os.listdir(os.path.join(third_party_root, package)):
        if name in ("METADATA.toml", "@python2"):
          continue
        name, _ = os.path.splitext(name)
        # When not specified, packages are Python 3-only.
        if metadata.get("python2", False):
          packages[name].add((package, 2))
        if metadata.get("python3", True):
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
    if self._use_new_structure:
      return self._get_module_file(toplevel, module, version)
    else:
      return self._get_module_file_old(toplevel, module, version)

  def _get_module_file(self, toplevel, module, version):
    """get_module_file for typeshed's new directory structure."""
    module_parts = module.split(".")
    module_path = os.path.join(*module_parts)
    paths = []
    if toplevel == "stdlib":
      # stubs for the stdlib 'foo' module are located in either stdlib/foo or
      # (for Python 2) stdlib/@python2/foo. The VERSIONS file tells us whether
      # stdlib/foo exists and what versions it targets; we also have to
      # separately check for stdlib/@python2/foo.
      if (module_parts[0] in self._stdlib_versions and
          self._stdlib_versions[module_parts[0]] <= version):
        paths.append(os.path.join(toplevel, module_path))
      elif version[0] == 2:
        paths.append(os.path.join(toplevel, "@python2", module_path))
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

  def _get_module_file_old(self, toplevel, module, version):
    """get_module_file for typeshed's old directory structure."""
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

  def get_typeshed_paths(self, python_version):
    """Gets the paths to typeshed's version-specific pyi files."""
    if self._use_new_structure:
      return self._get_typeshed_paths(python_version)
    else:
      return self._get_typeshed_paths_old(python_version)

  def _get_typeshed_paths(self, python_version):
    """get_typeshed_paths for typeshed's new directory structure."""
    major, _ = python_version
    typeshed_subdirs = ["stdlib"]
    if major == 2:
      typeshed_subdirs.append(os.path.join("stdlib", "@python2"))
    for packages in self._third_party_packages.values():
      for package, v in packages:
        if v == major:
          typeshed_subdirs.append(os.path.join("stubs", package))
          if v == 2:
            typeshed_subdirs.append(os.path.join("stubs", package, "@python2"))
    return [os.path.join(self._root, d) for d in typeshed_subdirs]

  def _get_typeshed_paths_old(self, python_version):
    """get_typeshed_paths for typeshed's old directory structure."""
    major, minor = python_version
    typeshed_subdirs = ["stdlib/%d" % major,
                        "stdlib/2and3",
                        "third_party/%d" % major,
                        "third_party/2and3",
                       ]
    if major == 3:
      for i in range(0, minor + 1):
        # iterate over 3.0, 3.1, 3.2, ...
        typeshed_subdirs.append("stdlib/3.%d" % i)
    return [os.path.join(self._root, d) for d in typeshed_subdirs]

  def get_pytd_paths(self, python_version):
    """Gets the paths to pytype's version-specific pytd files."""
    # TODO(mdemello): Should we add 2and3 here too and stop symlinking?
    return [pytype_source_utils.get_full_path(d) for d in [
        "stubs/builtins/%d" % python_version[0],
        "stubs/stdlib/%d" % python_version[0]]]

  def get_all_module_names(self, python_version):
    """Get the names of all modules in typeshed or bundled with pytype."""
    module_names = set()
    typeshed_paths = self.get_typeshed_paths(python_version)
    pytd_paths = self.get_pytd_paths(python_version)
    if self._env_home:
      for p in typeshed_paths:
        module_names |= _get_module_names_in_path(
            pytype_source_utils.list_files, p)
      pytype_paths = pytd_paths
    else:
      pytype_paths = typeshed_paths + pytd_paths
    subdirs = [d.rpartition("pytype/")[-1] for d in pytype_paths]
    for subdir in subdirs:
      module_names |= _get_module_names_in_path(
          pytype_source_utils.list_pytype_files, subdir)
    # Also load modules not in typeshed, so that we have a dummy entry for them.
    for f in self.missing:
      parts = f.split("/")
      if parts[1].startswith(str(python_version[0])):
        filename = "/".join(parts[2:])  # remove prefixes like stdlib/2.7
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
    if self._use_new_structure:
      return self._get_python_major_versions(filename)
    else:
      return self._get_python_major_versions_old(filename)

  def _get_python_major_versions(self, filename):
    """get_python_major_versions for the new typeshed directory structure."""
    if os.path.sep + "@python2" + os.path.sep in filename:
      return (2,)
    parts = filename.split(os.path.sep)
    if parts[0] == "stdlib":
      if self._stdlib_versions[os.path.splitext(parts[1])[0]] >= (3, 0):
        return (3,)
      else:
        return (2, 3)
    else:
      assert parts[0] == "stubs"
      package, module = parts[1], os.path.splitext(parts[2])[0]
      versions = []
      for p, v in self._third_party_packages[module]:
        if p != package or v == 2 and os.path.exists(
            os.path.join(self._root, "stubs", p, "@python2")):
          # If a dedicated @python2 subdirectory exists, then the top-level
          # stubs are Python 3-only.
          continue
        versions.append(v)
      return tuple(versions)

  def _get_python_major_versions_old(self, filename):
    """get_python_major_versions for the old typeshed directory structure."""
    path = filename.split(os.path.sep)
    if path[1] == "2and3":
      return (2, 3)
    else:
      return (int(path[1][0]),)


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
