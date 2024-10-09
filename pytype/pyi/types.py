"""Common datatypes and pytd utilities."""

import ast as astlib
import dataclasses
from typing import Any, TypeVar

from pytype.pytd import pytd

_TParseError = TypeVar("_TParseError", bound="ParseError")
_TPyval = TypeVar("_TPyval", bound="Pyval")

_STRING_TYPES: tuple[str, str, str] = ("str", "bytes", "unicode")


def node_position(node) -> tuple[Any, Any]:
  # NOTE: ast.Module has no position info, and will be the `node` when
  # build_type_decl_unit() is called, so we cannot call `node.lineno`
  return getattr(node, "lineno", None), getattr(node, "col_offset", None)


class ParseError(Exception):
  """Exceptions raised by the parser."""

  def __init__(
      self, msg, line=None, filename=None, column=None, text=None
  ) -> None:
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

  def at(
      self: _TParseError, node, filename=None, src_code=None
  ) -> _TParseError:
    """Add position information from `node` if it doesn't already exist."""
    if not self._line:
      self._line, self._column = node_position(node)
    if not self._filename:
      self._filename = filename
    if self._line and src_code:
      try:
        self._text = src_code.splitlines()[self._line - 1]
      except IndexError:
        pass
    return self

  def clear_position(self) -> None:
    self._line = None

  @property
  def line(self):
    return self._line

  def __str__(self) -> str:
    lines = []
    if self._filename or self._line is not None:
      lines.append(f'  File: "{self._filename}", line {self._line}')
    if self._column is not None and self._text:
      indent = 4
      stripped = self._text.strip()
      lines.append("%*s%s" % (indent, "", stripped))
      # Output a pointer below the error column, adjusting for stripped spaces.
      pos = indent + (self._column - 1) - (len(self._text) - len(stripped))
      lines.append("%*s^" % (pos, ""))
    lines.append(f"{type(self).__name__}: {self.args[0]}")
    return "\n".join(lines)


class Ellipsis:  # pylint: disable=redefined-builtin
  pass


@dataclasses.dataclass
class Raise:
  exception: pytd.NamedType


@dataclasses.dataclass
class SlotDecl:
  slots: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Pyval(astlib.AST):
  """Literal constants in pyi files."""

  # Inherits from ast.AST so it can be visited by ast visitors.

  type: str
  value: Any
  lineno: int | None
  col_offset: int | None

  @classmethod
  def from_const(cls, node: astlib.Constant):
    return cls(type(node.value).__name__, node.value, *node_position(node))

  def to_pytd(self) -> pytd.NamedType:
    return pytd.NamedType(self.type)

  def repr_str(self) -> str:
    """String representation with prefixes."""
    if self.type == "unicode":
      val = f"u{self.value!r}"
    else:
      val = repr(self.value)
    return val

  def to_pytd_literal(self) -> pytd.Literal | pytd.NamedType:
    """Make a pytd node from Literal[self.value]."""
    if self.type == "NoneType":
      return pytd.NamedType("NoneType")
    if self.type in _STRING_TYPES:
      val = self.repr_str()
    elif self.type == "float":
      raise ParseError(f"Invalid type `float` in Literal[{self.value}].")
    else:
      val = self.value
    return pytd.Literal(val)

  def negated(self: _TPyval) -> _TPyval:
    """Return a new constant with value -self.value."""
    if self.type in ("int", "float"):
      return Pyval(self.type, -self.value, self.lineno, self.col_offset)
    raise ParseError("Unary `-` can only apply to numeric literals.")

  @classmethod
  def is_str(cls, value) -> bool:
    return isinstance(value, cls) and value.type in _STRING_TYPES

  def __repr__(self) -> str:
    return f"LITERAL({self.repr_str()})"


def builtin_keyword_constants():
  # We cannot define these in a pytd file because assigning to a keyword breaks
  # the python parser.
  defs = [
      ("True", "bool"),
      ("False", "bool"),
      ("None", "NoneType"),
      ("__debug__", "bool"),
  ]
  return [pytd.Constant(name, pytd.NamedType(typ)) for name, typ in defs]
