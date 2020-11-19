"""Generic functions."""

import collections
import contextlib
import itertools
import os.path
import re
import subprocess
import sys
import threading
import traceback
import types
from typing import List, Tuple
import weakref

from pytype import pytype_source_utils


# Set this value to True to indicate that pytype is running under a 2.7
# interpreter with the type annotations patch applied.
USE_ANNOTATIONS_BACKPORT = False


# We disable the check that keeps pytype from running on not-yet-supported
# versions when we detect that a pytype test is executing, in order to be able
# to test upcoming versions.
def _validate_python_version_upper_bound():
  for frame_summary in traceback.extract_stack():
    head, tail = os.path.split(frame_summary.filename)
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
  """Parse a version string like "2" or "2.7" into a tuple."""
  try:
    version_int = int(version_string)
  except ValueError:
    return tuple(map(int, version_string.split(".")))
  return full_version_from_major(version_int)


def full_version_from_major(major_version):
  """Get a (major, minor) Python version tuple from a major version int."""
  if major_version == sys.version_info.major:
    return sys.version_info[:2]
  elif major_version == 2:
    return (2, 7)
  else:
    raise UsageError(
        "Cannot infer Python minor version for major version %d. "
        "Specify the version as <major>.<minor>." % major_version)


def normalize_version(version):
  """Gets a version tuple from either a major version int or a version tuple."""
  if isinstance(version, int):
    return full_version_from_major(version)
  else:
    return version


def validate_version(python_version):
  """Raise an exception if the python version is unsupported."""
  if len(python_version) != 2:
    # This is typically validated in the option parser, but check here too in
    # case we get python_version via a different entry point.
    raise UsageError("python_version must be <major>.<minor>: %r" %
                     format_version(python_version))
  elif python_version < (2, 7):
    raise UsageError("Python version %r is not supported." %
                     format_version(python_version))
  elif (2, 8) <= python_version < (3, 0):
    raise UsageError("Python version %r is not a valid Python version." %
                     format_version(python_version))
  elif (3, 0) <= python_version <= (3, 4):
    # These have odd __build_class__ parameters, store co_code.co_name fields
    # as unicode, and don't yet have the extra qualname parameter to
    # MAKE_FUNCTION. Jumping through these extra hoops is not worth it, given
    # that typing.py isn't introduced until 3.5, anyway.
    raise UsageError(
        "Python versions 3.0 - 3.4 are not supported. Use 3.5 and higher.")
  elif python_version > (3, 8) and _VALIDATE_PYTHON_VERSION_UPPER_BOUND:
    # We have an explicit per-minor-version mapping in opcodes.py
    raise UsageError("Python versions > 3.8 are not yet supported.")


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


def get_python_exe(python_version) -> Tuple[List[str], List[str]]:
  """Find a python executable to use.

  Arguments:
    python_version: the version tuple (e.g. (2, 7))
  Returns:
    A tuple of the path to the executable and any command-line flags
  """
  # Use custom interpreters, if provided, in preference to the ones in $PATH
  custom_python_exe = pytype_source_utils.get_custom_python_exe(python_version)
  if custom_python_exe:
    python_exe = [custom_python_exe]
  elif sys.platform == "win32":
    python_exe = ["py", "-%d.%d" % python_version]
  else:
    python_exe = ["python%d.%d" % python_version]
  if USE_ANNOTATIONS_BACKPORT and python_version == (2, 7):
    flags = ["-T"]
  else:
    flags = []
  return python_exe, flags


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
  except subprocess.CalledProcessError:
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
  # We can do this only when the host and target versions match and we don't
  # need the patched 2.7 interpreter.
  return python_version == sys.version_info[:2] and (
      sys.version_info.major != 2 or not USE_ANNOTATIONS_BACKPORT)


def list_startswith(l, prefix):
  """Like str.startswith, but for lists."""
  return l[:len(prefix)] == prefix


def list_strip_prefix(l, prefix):
  """Remove prefix, if it's there."""
  return l[len(prefix):] if list_startswith(l, prefix) else l


def _arg_names(f):
  """Return the argument names of a function."""
  return f.__code__.co_varnames[:f.__code__.co_argcount]


class memoize:  # pylint: disable=invalid-name
  """A memoizing decorator that supports expressions as keys.

  Use it like this:
    @memoize
    def f(x):
      ...
  or
    @memoize("(id(x), y)")
    def f(x, y, z):
      ...
  .
  Careful with methods. If you have code like
    @memoize("x")
    def f(self, x):
      ...
  then memoized values will be shared across instances.

  This decorator contains some speed optimizations that make it not thread-safe.
  """

  def __new__(cls, key_or_function):
    if isinstance(key_or_function, types.FunctionType):
      f = key_or_function
      key = "(" + ", ".join(_arg_names(f)) + ")"
      return memoize(key)(f)
    else:
      key = key_or_function
      return object.__new__(cls)

  def __init__(self, key):
    self.key = key

  def __call__(self, f):
    key_program = compile(self.key, filename=__name__, mode="eval")
    argnames = _arg_names(f)
    memoized = {}
    no_result = object()
    if f.__defaults__:
      defaults = dict(zip(argnames[-len(f.__defaults__):], f.__defaults__))
    else:
      defaults = {}
    pos_and_arg_tuples = list(zip(range(f.__code__.co_argcount), argnames))
    shared_dict = {}
    # TODO(b/159037011): Use functools.wraps or functools.update_wrapper to
    # preserve the metadata of the original function.
    def call(*posargs, **kwargs):
      """Call a memoized function."""
      if kwargs or defaults:
        # Slower version; for default arguments, we need two dictionaries.
        args = defaults.copy()
        args.update(dict(zip(argnames, posargs)))
        args.update(kwargs)
        key = eval(key_program, args)  # pylint: disable=eval-used
      else:
        # Faster version, if we have no default args.
        for pos, arg in pos_and_arg_tuples:
          # We know we write *all* the values, so we can re-use the dictionary.
          shared_dict[arg] = posargs[pos]
        key = eval(key_program, shared_dict)  # pylint: disable=eval-used
      result = memoized.get(key, no_result)
      if result is no_result:
        # Call the actual function.
        result = f(*posargs, **kwargs)
        memoized[key] = result
      return result
    return call


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


class VirtualMachineWeakrefMixin:

  __slots__ = ["vm_weakref"]

  def __init__(self, vm):
    self.vm_weakref = weakref.ref(vm)

  @property
  def vm(self):
    return self.vm_weakref()
