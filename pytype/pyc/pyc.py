"""Functions for generating, reading and parsing pyc."""

import copy
import os
import StringIO
import subprocess
import sys
import tempfile

from pytype.pyc import loadmarshal
from pytype.pyc import magic


def python_pyc_name(py_filename, python_version):
  """Convert a py filename to the filename of the compiled pyc file.

  E.g. this converts
    /tmp/tmpqF9GFq.py
  to:
    /tmp/tmpqF9GFq.pyc [Python 2, 3.0, 3.1]
    /tmp/__pycache__/tmpqF9GFq.cpython-34.pyc [Python >= 3.2]
  .

  Args:
    py_filename: A path to a .py file.
    python_version: Python version, (major, minor).
  Returns:
    Path to the .pyc file.
  """
  if python_version < (3, 2):
    basename, py = os.path.splitext(py_filename)
    assert py == ".py", py_filename
    return basename + ".pyc"
  else:
    path, basename = os.path.split(py_filename)
    body, _ = os.path.splitext(basename)
    short_version = "".join(map(str, python_version))
    return os.path.join(path, "__pycache__",
                        body + ".cpython-" + short_version + ".pyc")


def compile_src_string_to_pyc_string(src, python_version, python_exe):
  """Compile Python source code to pyc data.

  This may use py_compile if the src is for the same version as we're running,
  or else it spawns an external process to produce a .pyc file. The generated
  bytecode (.pyc file) is read and both it and any temporary files are deleted.

  Args:
    src: Python sourcecode
    python_version: Python version, (major, minor). E.g. (2, 7). Will be used
      to determine the Python executable to call.
    python_exe: Path to a Python interpreter, or None.

  Returns:
    The compiled pyc file as a binary string.
  """
  fi = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
  pyc_name = python_pyc_name(fi.name, python_version)

  if python_exe is None:
    python_exe = os.getenv("PYTYPE_PYTHON_EXE")
    if python_exe:
      print >>sys.stderr, "[Using PYTYPE_PYTHON_EXE from environment]"

  try:
    fi.write(src)
    fi.close()
    # In order to be able to compile pyc files for both Python 2 and Python 3,
    # we spawn an external process.
    if python_exe:
      # Allow python_exe to contain parameters (E.g. "-T")
      subprocess.check_call(python_exe.split() + ["-mpy_compile", fi.name])
    # The following code has been removed because it might not use the
    # same subdirectory as the regular compiler (see python_pyc_name).
    # And the slight performance gain probably isn't worth it.
    # Or we could use sys.executable with the subprocess.
    # -- elif python_version[:2] == sys.version_info[:2]:
    # --   py_compile.compile(fi.name, cfile=pyc_name, doraise=True)
    else:
# MOE:strip_line  TODO(b/26068255)
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


def compile_src(src, python_version, python_exe, filename=None):
  """Compile a string to pyc, and then load and parse the pyc.

  Args:
    src: Python source code.
    python_version: Python version, (major, minor).
    python_exe: Path to Python interpreter, or None.
    filename: The filename the sourcecode is from.

  Returns:
    An instance of loadmarshal.CodeType.
  """
  pyc_data = compile_src_string_to_pyc_string(
      src, python_version, python_exe)
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
