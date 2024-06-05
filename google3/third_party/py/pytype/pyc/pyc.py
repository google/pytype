"""Functions for generating, reading and parsing pyc."""

import copy

from pycnite import pyc

from pytype import utils
from pytype.pyc import compiler


# Reexport since we have exposed this error publicly as pyc.CompileError
CompileError = compiler.CompileError


def parse_pyc_string(data):
  """Parse pyc data from a string.

  Args:
    data: pyc data

  Returns:
    An instance of pycnite.types.CodeTypeBase.
  """
  return pyc.loads(data)


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
    An instance of pycnite.types.CodeTypeBase.

  Raises:
    UsageError: If python_exe and python_version are mismatched.
  """
  pyc_data = compiler.compile_src_string_to_pyc_string(
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
    k = (id(c), visitor)
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
