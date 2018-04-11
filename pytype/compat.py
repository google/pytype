"""Python 2 and 3 compatibility functions."""

import sys
import types

import six


def int_array_to_bytes(int_array):
  if sys.version_info[0] == 2:
    return b"".join(map(chr, int_array))
  else:
    return bytes(int_array)


def bytestring(obj):
  """Like the builtin str() but always returns a utf-8 encoded bytestring."""
  out = str(obj)
  if isinstance(out, six.text_type):
    return out.encode("utf-8")
  else:
    return out


# bytes and str are the same class in Python 2, and different classes in
# Python 3, so we need a way to mark Python 3 bytestrings.
class BytesPy3(bytes):
  pass


class OldStyleClassPy3(object):
  pass


class IteratorType(object):
  pass


# Native types that we test pyval against. six does not quite do what we want
# here.

NoneType = type(None)
EllipsisType = type(Ellipsis)  # pylint: disable=invalid-name

if sys.version_info[0] == 2:
  BytesType = BytesPy3
  UnicodeType = unicode
  LongType = long
  OldStyleClassType = types.ClassType
elif sys.version_info[0] == 3:
  BytesType = bytes
  UnicodeType = str
  LongType = int
  OldStyleClassType = OldStyleClassPy3
