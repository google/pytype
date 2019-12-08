"""Compiles a single .py to a .pyc and writes it to stdout."""

# These are C modules built into Python. Don't add any modules that are
# implemented in a .py:
import marshal
import re
import sys

# pylint: disable=g-import-not-at-top
if sys.version_info[0] == 2:
  import imp
  MAGIC = imp.get_magic()
else:
  import importlib.util
  MAGIC = importlib.util.MAGIC_NUMBER
# pylint: enable=g-import-not-at-top

# This pattern is as per PEP-263.
ENCODING_PATTERN = "^[ \t\v]*#.*?coding[:=][ \t]*([-_.a-zA-Z0-9]+)"


def is_comment_only(line):
  return re.match("[ \t\v]*#.*", line) is not None


def _write32(f, w):
  f.write(bytearray([
      (w >> 0) & 0xff,
      (w >> 8) & 0xff,
      (w >> 16) & 0xff,
      (w >> 24) & 0xff]))


def write_pyc(f, codeobject, source_size=0, timestamp=0):
  f.write(MAGIC)
  _write32(f, timestamp)
  if sys.version_info[:2] >= (3, 3):
    _write32(f, source_size)
  f.write(marshal.dumps(codeobject))


def compile_to_pyc(data_file, filename, output, mode):
  """Compile the source code to byte code."""
  if sys.version_info[0] >= 3:
    with open(data_file, "r", encoding="utf-8") as fi:  # pytype: disable=wrong-keyword-args
      src = fi.read()
  else:
    with open(data_file, "r") as fi:
      src = fi.read().decode("utf-8")
  compile_src_to_pyc(src, filename, output, mode)


def strip_encoding(src):
  """Strip encoding from a src string assumed to be read from a file."""
  # Python 2's compile function does not like the line specifying the encoding.
  # So, we strip it off if it is present, replacing it with an empty comment to
  # preserve the original line numbering. As per PEP-263, the line specifying
  # the encoding can occur only in the first or the second line.
  if "\n" not in src:
    return src
  l1, rest = src.split("\n", 1)
  if re.match(ENCODING_PATTERN, l1.rstrip()):
    return "#\n" + rest
  elif "\n" not in rest:
    return src
  l2, rest = rest.split("\n", 1)
  if is_comment_only(l1) and re.match(ENCODING_PATTERN, l2.rstrip()):
    return "#\n#\n" + rest
  return src


def compile_src_to_pyc(src, filename, output, mode):
  """Compile a string of source code."""
  if sys.version_info.major == 2:
    src = strip_encoding(src)
  try:
    codeobject = compile(src, filename, mode)
  except Exception as err:  # pylint: disable=broad-except
    output.write(b"\1")
    if sys.version_info[0] == 3:
      output.write(str(err).encode("utf-8"))
    else:
      output.write(str(err))
  else:
    output.write(b"\0")
    write_pyc(output, codeobject)


def main():
  if len(sys.argv) != 4:
    sys.exit(1)
  # TODO(b/31819797): Remove the pytype disable and enable.
  # pytype: disable=attribute-error
  output = sys.stdout.buffer if hasattr(sys.stdout, "buffer") else sys.stdout
  # pytype: enable=attribute-error
  compile_to_pyc(data_file=sys.argv[1], filename=sys.argv[2],
                 output=output, mode=sys.argv[3])


if __name__ == "__main__":
  main()
