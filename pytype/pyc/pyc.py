"""Functions for generating, reading and parsing pyc."""

import copy
import io
import os
import re
import subprocess
from typing import List

from pytype import pytype_source_utils
from pytype import utils
from pytype.platform_utils import tempfile as compatible_tempfile
from pytype.pyc import compile_bytecode
from pytype.pyc import loadmarshal
from pytype.pyc import magic

COMPILE_SCRIPT = "pyc/compile_bytecode.py"
COMPILE_ERROR_RE = re.compile(r"^(.*) \((.*), line (\d+)\)$")


class CompileError(Exception):
  """A compilation error."""

  def __init__(self, msg):
    super().__init__(msg)
    match = COMPILE_ERROR_RE.match(msg)
    if match:
      self.error = match.group(1)
      self.filename = match.group(2)
      self.lineno = int(match.group(3))
    else:
      self.error = msg
      self.filename = None
      self.lineno = 1


def compile_src_string_to_pyc_string(
    src, filename, python_version, python_exe: List[str], mode="exec"):
  """Compile Python source code to pyc data.

  This may use py_compile if the src is for the same version as we're running,
  or else it spawns an external process to produce a .pyc file. The generated
  bytecode (.pyc file) is read and both it and any temporary files are deleted.

  Args:
    src: Python sourcecode
    filename: Name of the source file. For error messages.
    python_version: Python version, (major, minor).
    python_exe: A path to a Python interpreter.
    mode: Same as builtins.compile: "exec" if source consists of a
      sequence of statements, "eval" if it consists of a single expression,
      or "single" if it consists of a single interactive statement.

  Returns:
    The compiled pyc file as a binary string.
  Raises:
    CompileError: If we find a syntax error in the file.
    IOError: If our compile script failed.
  """

  if utils.can_compile_bytecode_natively(python_version):
    output = io.BytesIO()
    compile_bytecode.compile_src_to_pyc(src, filename or "<>", output, mode)
    bytecode = output.getvalue()
  else:
    tempfile_options = {"mode": "w", "suffix": ".py", "delete": False}
    tempfile_options.update({"encoding": "utf-8"})
    fi = compatible_tempfile.NamedTemporaryFile(**tempfile_options)  # pylint: disable=consider-using-with
    try:
      fi.write(src)
      fi.close()
      # In order to be able to compile pyc files for a different Python version
      # from the one we're running under, we spawn an external process.
      # We pass -E to ignore the environment so that PYTHONPATH and
      # sitecustomize on some people's systems don't mess with the interpreter.
      cmd = python_exe + ["-E", "-", fi.name, filename or fi.name, mode]

      compile_script_src = pytype_source_utils.load_binary_file(COMPILE_SCRIPT)

      with subprocess.Popen(
          cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as p:
        bytecode, _ = p.communicate(compile_script_src)
        assert p.poll() == 0, "Child process failed"
    finally:
      os.unlink(fi.name)
  first_byte = bytecode[0]
  if first_byte == 0:  # compile OK
    return bytecode[1:]
  elif first_byte == 1:  # compile error
    code = bytecode[1:]  # type: bytes
    raise CompileError(utils.native_str(code))
  else:
    raise OSError("_compile.py produced invalid result")


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
    raise OSError("Malformed pyc file")
  fi.read(4)  # timestamp
  fi.read(4)  # raw size
  return loadmarshal.loads(fi.read(), python_version)


def parse_pyc_string(data):
  """Parse pyc data from a string.

  Args:
    data: pyc data

  Returns:
    An instance of loadmarshal.CodeType.
  """
  return parse_pyc_stream(io.BytesIO(data))


class AdjustFilename:
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
    python_exe: The path to Python interpreter.
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


# This cache is needed to avoid visiting the same code object twice, since some
# visitors mutate the input object.
_VISIT_CACHE = {}


def visit(c, visitor):
  """Recursively process constants in a pyc using a visitor."""
  if hasattr(c, "co_consts"):
    # This is a CodeType object (because it has co_consts). Visit co_consts,
    # and then the CodeType object itself.
    k = (c, visitor)
    if k not in _VISIT_CACHE:
      new_consts = []
      changed = False
      for const in c.co_consts:
        new_const = visit(const, visitor)
        changed |= new_const is not const
        new_consts.append(new_const)
      if changed:
        c = copy.copy(c)
        c.co_consts = new_consts
      _VISIT_CACHE[k] = visitor.visit_code(c)
    return _VISIT_CACHE[k]
  else:
    return c
