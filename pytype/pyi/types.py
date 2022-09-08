"""Common datatypes and pytd utilities."""

import dataclasses
import sys
from typing import Any, Tuple

from pytype import utils
from pytype.pytd import pytd
from pytype.pytd.codegen import pytdgen

# pylint: disable=g-import-not-at-top
if sys.version_info >= (3, 8):
  import ast as ast3
else:
  from typed_ast import ast3
# pylint: enable=g-import-not-at-top


_STRING_TYPES = ("str", "bytes", "unicode")


class ParseError(Exception):
  """Exceptions raised by the parser."""

  def __init__(self, msg, line=None, filename=None, column=None, text=None):
    super().__init__(msg)
    self._line = line
    self._filename = filename
    self._column = column
    self._text = text

  @classmethod
  def from_exc(cls, exc) -> "ParseError":
    if isinstance(exc, cls):
      return exc
    elif exc.args:
      return cls(exc.args[0])
    else:
      return cls(repr(exc))

  def at(self, node, filename=None, src_code=None):
    """Add position information from `node` if it doesn't already exist."""
    # NOTE: ast3.Module has no position info, and will be the `node` when
    # build_type_decl_unit() is called, so we cannot call `node.lineno`
    if not self._line:
      self._line = getattr(node, "lineno", None)
      self._column = getattr(node, "col_offset", None)
    if not self._filename:
      self._filename = filename
    if self._line and src_code:
      try:
        self._text = src_code.splitlines()[self._line-1]
      except IndexError:
        pass
    return self

  def clear_position(self):
    self._line = None

  @property
  def line(self):
    return self._line

  def __str__(self):
    lines = []
    if self._filename or self._line is not None:
      lines.append(f'  File: "{self._filename}", line {self._line}')
    if self._column and self._text:
      indent = 4
      stripped = self._text.lstrip()
      lines.append("%*s%s" % (indent, "", stripped))
      # Output a pointer below the error column, adjusting for stripped spaces.
      pos = indent + (self._column - 1) - (len(self._text) - len(stripped))
      lines.append("%*s^" % (pos, ""))
    lines.append(f"{type(self).__name__}: {utils.message(self)}")
    return "\n".join(lines)


class Ellipsis:  # pylint: disable=redefined-builtin
  pass


@dataclasses.dataclass
class Raise:
  exception: pytd.NamedType


@dataclasses.dataclass
class SlotDecl:
  slots: Tuple[str, ...]


@dataclasses.dataclass
class Pyval(ast3.AST):
  """Literal constants in pyi files."""
  # Inherits from ast3.AST so it can be visited by ast visitors.

  type: str
  value: Any

  @classmethod
  def from_num(cls, node: ast3.Num):
    if isinstance(node.n, int):
      return cls("int", node.n)
    else:
      return cls("float", node.n)

  @classmethod
  def from_str(cls, node: ast3.Str):
    if node.kind == "b":
      return cls("bytes", node.s)
    elif node.kind == "u":
      return cls("unicode", node.s)
    else:
      return cls("str", node.s)

  @classmethod
  def from_const(cls, node: ast3.NameConstant):
    if node.value is None:
      return pytd.NamedType("None")
    return cls(type(node.value).__name__, node.value)

  def to_pytd(self):
    return pytd.NamedType(self.type)

  def repr_str(self):
    """String representation with prefixes."""
    if self.type == "unicode":
      val = f"u{self.value!r}"
    else:
      val = repr(self.value)
    return val

  def to_pytd_literal(self):
    """Make a pytd node from Literal[self.value]."""
    if self.value is None:
      return pytd.NamedType("None")
    if self.type in _STRING_TYPES:
      val = self.repr_str()
    elif self.type == "float":
      raise ParseError(f"Invalid type `float` in Literal[{self.value}].")
    else:
      val = self.value
    return pytd.Literal(val)

  def negated(self):
    """Return a new constant with value -self.value."""
    if self.type in ("int", "float"):
      return Pyval(self.type, -self.value)
    raise ParseError("Unary `-` can only apply to numeric literals.")

  @classmethod
  def is_str(cls, value):
    return isinstance(value, cls) and value.type in _STRING_TYPES

  def __repr__(self):
    return f"LITERAL({self.repr_str()})"


def string_value(val, context=None) -> str:
  """Convert a Pyval(str) to a string if needed."""
  if isinstance(val, str):
    return val
  elif Pyval.is_str(val):
    return str(val.value)
  else:
    if context:
      msg = f"Type mismatch in {context}"
    else:
      msg = "Type mismatch"
    raise ParseError(f"{msg}: Expected str, got {val}")


def is_any(val) -> bool:
  if isinstance(val, Ellipsis):
    return True
  return pytdgen.is_any(val)


def builtin_keyword_constants():
  # We cannot define these in a pytd file because assigning to a keyword breaks
  # the python parser.
  defs = [
      ("True", "bool"),
      ("False", "bool"),
      ("None", "NoneType"),
      ("__debug__", "bool")
  ]
  return [pytd.Constant(name, pytd.NamedType(typ)) for name, typ in defs]
