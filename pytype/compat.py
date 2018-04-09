"""Python 2 and 3 compatibility functions."""

import sys


def int_array_to_bytes(int_array):
  major = sys.version_info[0]
  if major == 2:
    return b"".join(map(chr, int_array))
  else:
    return bytes(int_array)
