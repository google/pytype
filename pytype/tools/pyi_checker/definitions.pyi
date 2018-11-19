# Pyptype cannot currently analyze dataclasses, so this pyi file is necessary.
from typing import ClassVar, Dict, List, Optional, Type, TypeVar, Union
from typed_ast import ast3

class Definition:
  name: str
  source: str
  lineno: int
  col_offset: int
  full_name: str
  location: str
  kind: ClassVar[str]
  def __init__(self, name: str, lineno: int, col_offset: int) -> None: ...

_TArgument = TypeVar("_TArgument", bound=Argument)
class Argument(Definition):
  has_default: bool
  def __init__(self, name: str, source: str, lineno: int, col_offset: int, has_default: bool) -> None: ...
  @classmethod
  def from_node(cls: Type[_TArgument], node: ast3.arg, source: str=...) -> _TArgument

_TFunction = TypeVar("_TFunction", bound=Function)
class Function(Definition):
  params: List[Argument]
  vararg: Optional[Argument]
  kwonlyargs: List[Argument]
  kwarg: Optional[Argument]
  decorators: List[str]
  is_async: bool
  def __init__(self, name: str, source: str, lineno: int, col_offset: int, params: List[Argument], vararg: Optional[Argument],
    kwonlyargs: List[Argument], kwarg: Optional[Argument], decorators: List[str], is_async: bool) -> None: ...
  @classmethod
  def from_node(cls: Type[_TFunction], node: Union[ast3.FunctionDef, ast3.AsyncFunctionDef], source: str=...) -> _TFunction: ...

_TVariable = TypeVar("_TVariable", bound=Variable)
class Variable(Definition):
  @classmethod
  def from_node(cls: Type[_TVariable], node: ast3.Name, source: str=...) -> _TVariable: ...

_TClass = TypeVar("_TClass", bound=Class)
class Class(Definition):
  bases: List[str]
  keyword_bases: Dict[str, str]
  decorators: List[str]
  fields: List[Variable]
  methods: List[Function]
  nested_classes: List[Class]
  def __init__(self, name: str, source: str, lineno: int, col_offset: int, bases: List[str], keyword_bases: Dict[str, str],
    decorators: List[str], fields: List[Variable], methods: List[Function], nested_classes: List[Class]) -> None: ...
  @classmethod
  def from_node(cls: Type[_TClass], node: ast3.ClassDef, fields: List[Variable], methods: List[Function],
    nested_classes: List[Class], source: str=...) -> _TClass: ...
