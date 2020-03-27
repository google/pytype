"""Functions for generating, reading and parsing pyc."""

import copy
import os
import re
import subprocess
import tempfile

from pytype import compat
from pytype import pytype_source_utils
from pytype import utils
from pytype.pyc import compile_bytecode
from pytype.pyc import loadmarshal
from pytype.pyc import magic
import six


COMPILE_SCRIPT = "pyc/compile_bytecode.py"
COMPILE_ERROR_RE = re.compile(r"^(.*) \((.*), line (\d+)\)$")


class CompileError(Exception):
  """A compilation error."""

  def __init__(self, msg):
    super(CompileError, self).__init__(msg)
    match = COMPILE_ERROR_RE.match(msg)
    if match:
      self.error = match.group(1)
      self.filename = match.group(2)
      self.lineno = int(match.group(3))
    else:
      self.error = msg
      self.filename = None
      self.lineno = 1


def compile_src_string_to_pyc_string(src, filename, python_version, python_exe,
                                     mode="exec"):
  """Compile Python source code to pyc data.

  This may use py_compile if the src is for the same version as we're running,
  or else it spawns an external process to produce a .pyc file. The generated
  bytecode (.pyc file) is read and both it and any temporary files are deleted.

  Args:
    src: Python sourcecode
    filename: Name of the source file. For error messages.
    python_version: Python version, (major, minor).
    python_exe: Tuple of a path to a Python interpreter and command-line flags.
    mode: Same as __builtin__.compile: "exec" if source consists of a
      sequence of statements, "eval" if it consists of a single expression,
      or "single" if it consists of a single interactive statement.

  Returns:
    The compiled pyc file as a binary string.
  Raises:
    CompileError: If we find a syntax error in the file.
    IOError: If our compile script failed.
  """

  if utils.can_compile_bytecode_natively(python_version):
    output = six.BytesIO()
    compile_bytecode.compile_src_to_pyc(src, filename or "<>", output, mode)
    bytecode = output.getvalue()
  else:
    tempfile_options = {"mode": "w", "suffix": ".py", "delete": False}
    if six.PY3:
      tempfile_options.update({"encoding": "utf-8"})
    else:
      tempfile_options.update({"mode": "wb"})
    fi = tempfile.NamedTemporaryFile(**tempfile_options)
    try:
      if six.PY3:
        fi.write(src)
      else:
        fi.write(src.encode("utf-8"))
      fi.close()
      # In order to be able to compile pyc files for a different Python version
      # from the one we're running under, we spawn an external process.
      # We pass -E to ignore the environment so that PYTHONPATH and
      # sitecustomize on some people's systems don't mess with the interpreter.
      exe, flags = python_exe
      cmd = [exe] + flags + ["-E", "-", fi.name, filename or fi.name, mode]

      compile_script_src = pytype_source_utils.load_pytype_file(COMPILE_SCRIPT)

      p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
      bytecode, _ = p.communicate(compile_script_src)
      assert p.poll() == 0, "Child process failed"
    finally:
      os.unlink(fi.name)
  first_byte = six.indexbytes(bytecode, 0)
  if first_byte == 0:  # compile OK
    return bytecode[1:]
  elif first_byte == 1:  # compile error
    code = bytecode[1:]  # type: bytes
    raise CompileError(compat.native_str(code))
  else:
    raise IOError("_compile.py produced invalid result")


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
  if crlf != b"\r\n":
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
  return parse_pyc_stream(six.BytesIO(data))


class AdjustFilename(object):
  """Visitor for changing co_filename in a code object."""

  def __init__(self, filename):
    self.filename = filename

  def visit_code(self, code):
    code.co_filename = self.filename
    return code


def compile_src(src, filename, python_version, python_exe, mode="exec"):
  """Compile a string to pyc, and then load and parse the pyc.

  Args:
    src: Python source code.
    filename: The filename the sourcecode is from.
    python_version: Python version, (major, minor).
    python_exe: Tuple of the path to Python interpreter and command-line flags.
    mode: "exec", "eval" or "single".

  Returns:
    An instance of loadmarshal.CodeType.

  Raises:
    UsageError: If python_exe and python_version are mismatched.
  """
  pyc_data = compile_src_string_to_pyc_string(
      src, filename, python_version, python_exe, mode)
  code = parse_pyc_string(pyc_data)
  if code.python_version != python_version:
    raise utils.UsageError(
        "python_exe version %s does not match python version %s" %
        (utils.format_version(code.python_version),
         utils.format_version(python_version)))
  visit(code, AdjustFilename(filename))
  return code


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
