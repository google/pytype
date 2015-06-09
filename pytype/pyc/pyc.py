"""Functions for generating, reading and parsing pyc."""

import copy
import os
import StringIO
import subprocess
import tempfile

from pytype.pyc import loadmarshal
from pytype.pyc import magic


def compile_src_string_to_pyc_string(src, python_version):
  """Compile Python source code to pyc data.

  This will spawn an external process to produce a .pyc file, and then read
  that.

  Args:
    src: Python sourcecode
    python_version: Python version, (major, minor). E.g. (2, 7). Will be used
      to determine the Python executable to call.

  Returns:
    The compiled pyc file as a binary string.
  """
  fi = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
  basename, py = os.path.splitext(fi.name)
  assert py == ".py", fi.name
  pyc_name = basename + ".pyc"
  try:
    fi.write(src)
    fi.close()
    # In order to be able to compile pyc files for both Python 2 and Python 3,
    # we spawn an external process.
    exe = "python" + ".".join(map(str, python_version))
    subprocess.check_call([exe, "-mpy_compile", fi.name])
    with open(pyc_name, "rb") as output:
      return output.read()
  finally:
    os.unlink(fi.name)
    if os.path.isfile(pyc_name):
      os.unlink(pyc_name)


def parse_pyc_stream(fi):
  """Parse pyc data from a file.

  Args:
    fi: A file-like object.

  Returns:
    An instance of loadmarshal.CodeType.

  Raises:
    IOError: If we can't read the file or the file is malformed.
  """
  magic_word = fi.read(2)
  python_version = magic.magic_word_to_version(magic_word)
  crlf = fi.read(2)  # cr, lf
  if crlf != "\r\n":
    raise IOError("Malformed pyc file")
  fi.read(4)  # timestamp
  if python_version >= (3, 3):
    # This field was introduced in Python 3.3
    fi.read(4)  # raw size
  return loadmarshal.loads(fi.read(), python_version)


def parse_pyc_string(data):
  """Parse pyc data from a string.

  Args:
    data: pyc data

  Returns:
    An instance of loadmarshal.CodeType.
  """
  return parse_pyc_stream(StringIO.StringIO(data))


class AdjustFilename(object):
  """Visitor for changing co_filename in a code object."""

  def __init__(self, filename):
    self.filename = filename

  def visit_code(self, code):
    code.co_filename = self.filename
    return code


def compile_src(src, python_version, filename=None):
  """Compile a string to pyc, and then load and parse the pyc.

  Args:
    src: Python source code.
    python_version: Python version, (major, minor).
    filename: The filename the sourcecode is from.

  Returns:
    An instance of loadmarshal.CodeType.
  """
  pyc_data = compile_src_string_to_pyc_string(src, python_version)
  code = parse_pyc_string(pyc_data)
  assert code.python_version == python_version
  visit(code, AdjustFilename(filename))
  return code


def compile_file(filename, python_version):
  """Compile a file to pyc, return the parsed pyc.

  Args:
    filename: Python (.py) file to compile.
    python_version: The Python version to use for compiling this file.

  Returns:
    An instance of loadmarshal.CodeType.
  """
  with open(filename, "rb") as fi:
    return compile_src(fi.read(), python_version, filename)


def visit(c, visitor):
  """Recursively process constants in a pyc using a visitor."""
  if hasattr(c, "co_consts"):
    # This is a CodeType object (because it has co_consts). Visit co_consts,
    # and then the CodeType object itself.
    new_consts = []
    changed = False
    for const in c.co_consts:
      new_const = visit(const, visitor)
      changed |= new_const is not const
      new_consts.append(new_const)
    if changed:
      c = copy.copy(c)
      c.co_consts = new_consts
    return visitor.visit_code(c)
  else:
    return c
