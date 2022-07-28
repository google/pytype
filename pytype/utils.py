"""Generic functions."""

import atexit
import collections
import contextlib
import itertools
import os
import re
import subprocess
import sys
import tempfile
import threading
import traceback
from typing import Iterable, List
import weakref

from pytype import pytype_source_utils
from pytype.platform_utils import path_utils


# We disable the check that keeps pytype from running on not-yet-supported
# versions when we detect that a pytype test is executing, in order to be able
# to test upcoming versions.
def _validate_python_version_upper_bound():
  for frame_summary in traceback.extract_stack():
    head, tail = path_utils.split(frame_summary.filename)
    if "/pytype/" in head + "/" and (
        tail.startswith("test_") or tail.endswith("_test.py")):
      return False
  return True


_VALIDATE_PYTHON_VERSION_UPPER_BOUND = _validate_python_version_upper_bound()


def message(error):
  """A convenience function which extracts a message from an exception.

  Use this to replace exception.message, which is deprecated in python2 and
  removed in python3.

  Args:
    error: The exception.

  Returns:
    A message string.
  """
  return error.args[0] if error.args else ""


class UsageError(Exception):
  """Raise this for top-level usage errors."""


def format_version(python_version):
  """Format a version tuple into a dotted version string."""
  return ".".join(str(x) for x in python_version)


def version_from_string(version_string):
  """Parse a version string like "3.7" into a tuple."""
  return tuple(map(int, version_string.split(".")))


def validate_version(python_version):
  """Raise an exception if the python version is unsupported."""
  if len(python_version) != 2:
    # This is typically validated in the option parser, but check here too in
    # case we get python_version via a different entry point.
    raise UsageError("python_version must be <major>.<minor>: %r" %
                     format_version(python_version))
  elif python_version <= (2, 7):
    raise UsageError("Python version %r is not supported. "
                     "Use pytype release 2021.08.03 for Python 2 support." %
                     format_version(python_version))
  elif (2, 8) <= python_version < (3, 0):
    raise UsageError("Python version %r is not a valid Python version." %
                     format_version(python_version))
  elif (3, 0) <= python_version <= (3, 6):
    raise UsageError(
        "Python versions 3.0 - 3.6 are not supported. Use 3.7 and higher.")
  elif python_version > (3, 10) and _VALIDATE_PYTHON_VERSION_UPPER_BOUND:
    # We have an explicit per-minor-version mapping in opcodes.py
    raise UsageError("Python versions > 3.10 are not yet supported.")


def strip_prefix(string, prefix):
  """Strip off prefix if it exists."""
  if string.startswith(prefix):
    return string[len(prefix):]
  return string


def maybe_truncate(s, length=30):
  """Truncate long strings (and append '...'), but leave short strings alone."""
  s = str(s)
  if len(s) > length-3:
    return s[0:length-3] + "..."
  else:
    return s


def pretty_conjunction(conjunction):
  """Pretty-print a conjunction. Use parentheses as necessary.

  E.g. ["a", "b"] -> "(a & b)"

  Args:
    conjunction: List of strings.
  Returns:
    A pretty-printed string.
  """
  if not conjunction:
    return "true"
  elif len(conjunction) == 1:
    return conjunction[0]
  else:
    return "(" + " & ".join(conjunction) + ")"


def pretty_dnf(dnf):
  """Pretty-print a disjunctive normal form (disjunction of conjunctions).

  E.g. [["a", "b"], ["c"]] -> "(a & b) | c".

  Args:
    dnf: A list of list of strings. (Disjunction of conjunctions of strings)
  Returns:
    A pretty-printed string.
  """
  if not dnf:
    return "false"
  else:
    return " | ".join(pretty_conjunction(c) for c in dnf)


def numeric_sort_key(s):
  return tuple((int(e) if e.isdigit() else e) for e in re.split(r"(\d+)", s))


def concat_tuples(tuples):
  return tuple(itertools.chain.from_iterable(tuples))


def native_str(s, errors="strict"):
  """Convert a bytes object to the native str type."""
  if isinstance(s, str):
    return s
  else:
    assert isinstance(s, bytes)
    return s.decode("utf-8", errors)


def _load_data_file(path):
  """Get the contents of a data file."""
  loader = globals().get("__loader__", None)
  if loader:
    # For an explanation of the args to loader.get_data, see
    # https://www.python.org/dev/peps/pep-0302/#optional-extensions-to-the-importer-protocol
    # https://docs.python.org/3/library/importlib.html#importlib.abc.ResourceLoader.get_data
    return loader.get_data(path)
  with open(path, "rb") as fi:
    return fi.read()


def _path_to_custom_exe(relative_path):
  """Get the full path to a custom python exe in the pytype/ src directory."""
  path = pytype_source_utils.get_full_path(relative_path)
  if os.path.exists(path):
    return path
  data = _load_data_file(path)
  with tempfile.NamedTemporaryFile(delete=False, suffix="python") as fi:
    fi.write(data)
    fi.close()
    exe_file = fi.name
    os.chmod(exe_file, 0o750)
    atexit.register(lambda: os.unlink(exe_file))
  return exe_file


# To aid with testing a pytype against a new Python version, you can build a
# *hermetic* Python runtime executable and drop it in the pytype/ src directory,
# then add an entry for it here, like:
#     (3, 10): "python3.10",
# This would mean that when -V3.10 is passed to pytype, it will use the exe at
# pytype/python3.10 to compile the code under analysis. Remember to add the new
# file to the pytype_main_deps target!
_CUSTOM_PYTHON_EXES = {}


def get_python_exes(python_version) -> Iterable[List[str]]:
  """Find possible python executables to use.

  Arguments:
    python_version: the version tuple (e.g. (3, 7))
  Yields:
    The path to the executable
  """
  if python_version in _CUSTOM_PYTHON_EXES:
    yield [_path_to_custom_exe(_CUSTOM_PYTHON_EXES[python_version])]
    return
  for version in (format_version(python_version), "3"):
    if sys.platform == "win32":
      python_exe = ["py", f"-{version}"]
    else:
      python_exe = [f"python{version}"]
    yield python_exe


def get_python_exe_version(python_exe: List[str]):
  """Determine the major and minor version of given Python executable.

  Arguments:
    python_exe: absolute path to the Python executable
  Returns:
    Version as (major, minor) tuple.
  """
  try:
    python_exe_version = subprocess.check_output(
        python_exe + ["-V"], stderr=subprocess.STDOUT).decode()
  except (subprocess.CalledProcessError, FileNotFoundError):
    return None

  return parse_exe_version_string(python_exe_version)


def parse_exe_version_string(version_str):
  """Parse the version string of a Python executable.

  Arguments:
    version_str: Version string as emitted by running `PYTHON_EXE -V`
  Returns:
    Version as (major, minor) tuple.
  """
  # match the major.minor part of the version string, ignore the micro part
  matcher = re.search(r"Python (\d+\.\d+)\.\d+", version_str)

  if matcher:
    return version_from_string(matcher.group(1))
  else:
    return None


def can_compile_bytecode_natively(python_version):
  # Optimization: calling compile_bytecode directly is faster than spawning a
  # subprocess and lets us avoid extracting a large Python executable into /tmp.
  # We can do this only when the host and target versions match.
  return python_version == sys.version_info[:2]


def list_startswith(l, prefix):
  """Like str.startswith, but for lists."""
  return l[:len(prefix)] == prefix


def list_strip_prefix(l, prefix):
  """Remove prefix, if it's there."""
  return l[len(prefix):] if list_startswith(l, prefix) else l


def _arg_names(f):
  """Return the argument names of a function."""
  return f.__code__.co_varnames[:f.__code__.co_argcount]


def invert_dict(d):
  """Invert a dictionary.

  Converts a dictionary (mapping strings to lists of strings) to a dictionary
  that maps into the other direction.

  Arguments:
    d: Dictionary to be inverted

  Returns:
    A dictionary n with the property that if "y in d[x]", then "x in n[y]".
  """

  inverted = collections.defaultdict(list)
  for key, value_list in d.items():
    for val in value_list:
      inverted[val].append(key)
  return inverted


def unique_list(xs):
  """Return a unique list from an iterable, preserving order."""
  seen = set()
  out = []
  for x in xs:
    if x not in seen:
      seen.add(x)
      out.append(x)
  return out


class DynamicVar:
  """A dynamically scoped variable.

  This is a per-thread dynamic variable, with an initial value of None.
  The bind() call establishes a new value that will be in effect for the
  duration of the resulting context manager.  This is intended to be used
  in conjunction with a decorator.
  """

  def __init__(self):
    self._local = threading.local()

  def _values(self):
    values = getattr(self._local, "values", None)
    if values is None:
      values = [None]  # Stack of bindings, with an initial default of None.
      self._local.values = values
    return values

  @contextlib.contextmanager
  def bind(self, value):
    """Bind the dynamic variable to the supplied value."""
    values = self._values()
    try:
      values.append(value)  # Push the new binding.
      yield
    finally:
      values.pop()  # Pop the binding.

  def get(self):
    """Return the current value of the dynamic variable."""
    return self._values()[-1]


class AnnotatingDecorator:
  """A decorator for storing function attributes.

  Attributes:
    lookup: maps functions to their attributes.
  """

  def __init__(self):
    self.lookup = {}

  def __call__(self, value):
    def decorate(f):
      self.lookup[f.__name__] = value
      return f
    return decorate


class ContextWeakrefMixin:

  __slots__ = ["ctx_weakref"]

  def __init__(self, ctx):
    self.ctx_weakref = weakref.ref(ctx)

  @property
  def ctx(self):
    return self.ctx_weakref()
