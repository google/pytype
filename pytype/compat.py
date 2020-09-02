"""Python 2 and 3 compatibility functions."""

import glob
import os
import sys
import types


def recursive_glob(path):
  """Version-agnostic recursive glob.

  Implements the Python 3.5+ glob module's recursive glob for Python 2.7+.
  Recursive glob emulates the bash shell's globstar feature, which is enabled
  with `shopt -s globstar`.

  Args:
    path: A path that may contain `**` and `*` ("magic").
  Returns:
    The expanded list of paths with magic removed.
  """
  if "*" not in path:
    # Glob isn't needed.
    return [path]
  elif "**" not in path:
    # Recursive glob isn't needed.
    return glob.glob(path)
  elif sys.version_info >= (3, 5):
    # Recursive glob is supported.
    # TODO(b/110380447): Remove the pytype disable.
    # Pylint doesn't respect the version check.
    # pytype: disable=wrong-keyword-args
    # pylint: disable=unexpected-keyword-arg
    return glob.glob(path, recursive=True)
    # pylint: enable=unexpected-keyword-arg
    # pytype: enable=wrong-keyword-args
  # Simulate recursive glob with os.walk.
  left, right = path.split("**", 1)
  if not left:
    left = "." + os.sep
  right = right.lstrip(os.sep)
  paths = []
  for d, _, _ in os.walk(left):
    # Don't recurse into hidden directories. Note that the current directory
    # ends with '/', giving it a basename of '', which prevents this check
    # from accidentally skipping it.
    if not os.path.basename(d).startswith("."):
      paths += recursive_glob(os.path.join(d, right))
  return paths


def int_array_to_bytes(int_array):
  if sys.version_info[0] == 2:
    return b"".join(map(chr, int_array))
  else:
    return bytes(int_array)


def bytestring(obj):
  """Like the builtin str() but always returns a utf-8 encoded bytestring."""
  out = str(obj)
  if isinstance(out, str):
    return out.encode("utf-8")
  else:
    return out


def native_str(s, errors="strict"):
  """Convert a bytes or unicode object to the native str type."""
  if isinstance(s, str):
    return s
  elif sys.version_info[0] < 3:
    return s.encode("utf-8", errors)
  else:
    return s.decode("utf-8", errors)


# bytes and str are the same class in Python 2, and different classes in
# Python 3, so we need a way to mark bytestrings when analyzing Python 3 while
# running under Python 2.
class BytesPy3(bytes):
  pass


# str and unicode are the same class in Python 3, and different classes in
# Python 2, so we need a way to mark unicode strings when analyzing Python 2
# while running under Python 3.
class UnicodePy2(str):
  pass


class OldStyleClassPy3:
  pass


class IteratorType:
  pass


class CoroutineType:
  pass


class AwaitableType:
  pass


class AsyncGeneratorType:
  pass


# Native types that we test pyval against. six does not quite do what we want
# here.

# Because pylint doesn't like type aliases (b/62879736):
# pylint: disable=invalid-name
NoneType = type(None)
EllipsisType = type(Ellipsis)

if sys.version_info[0] == 2:
  # Because pylint doesn't respect version checks:
  # pylint: disable=undefined-variable
  BytesType = BytesPy3
  UnicodeType = unicode
  LongType = long
  OldStyleClassType = types.ClassType
  # pylint: enable=undefined-variable
elif sys.version_info[0] == 3:
  BytesType = bytes
  UnicodeType = UnicodePy2
  LongType = int
  OldStyleClassType = OldStyleClassPy3
# pylint: enable=invalid-name
