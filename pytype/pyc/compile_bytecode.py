"""Compiles a single .py to a .pyc and writes it to stdout."""

# These are C modules built into Python. Don't add any modules that are
# implemented in a .py:
import imp
import marshal
import sys


MAGIC = imp.get_magic()


def _write32(f, w):
  f.write(bytearray([
      (w >> 0) & 0xff,
      (w >> 8) & 0xff,
      (w >> 16) & 0xff,
      (w >> 24) & 0xff]))


def write_pyc(f, codeobject, source_size=0, timestamp=0):
  f.write(MAGIC)
  _write32(f, timestamp)
  if tuple(sys.version_info[:2]) >= (3, 3):
    _write32(f, source_size)
  f.write(marshal.dumps(codeobject))


def compile_to_pyc(data_file, filename, output, mode="exec"):
  """Compile the source code to byte code."""
  with open(data_file, "r") as fi:
    src = fi.read()
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
