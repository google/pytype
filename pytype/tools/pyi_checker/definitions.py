# python3
"""Definitions for Python AST objects.

AST nodes are not very convenient for comparing two files. Instead, they should
be parsed into these definitions. Each Definition subclass exposes the
attributes of a particular kind of AST node.
"""
from typing import ClassVar, Dict, Optional, List, Union

import dataclasses
from typed_ast import ast3


@dataclasses.dataclass
class Definition:
  """Base class for AST definitions.

  Definition tracks the basic information of AST nodes, namely the identifier
  and location of the node. The location is useful for reporting errors.

  Attributes:
    name: The node's identifier.
    source: The source file that contains the definition.
    lineno: The line in the source file that contains the definition.
    col_offset: The column offset within the line of the source definition.
  """
  name: str
  source: str
  lineno: int
  col_offset: int
  kind: ClassVar[str]

  def __post_init__(self):
    # This method is automatically called by __init__. Subclasses override it
    # to set full_name to "%{kind} %{name}", e.g. "function doThing".
    self.full_name = f"{self.kind} {self.name}"
    self.location = f"{self.source}:{self.lineno}"


@dataclasses.dataclass
class Argument(Definition):
  """Represents an argument in a function definition.

  While Argument records the existence of a default value, it does not track the
  actual default value. The value is not needed for checking type stubs.

  Attributes:
    has_default: Whether a default value is provided for the argument.
  """
  has_default: bool
  kind: ClassVar[str] = "argument"

  @classmethod
  def from_node(cls, node: ast3.arg, source: str = ""):
    return cls(node.arg, source, node.lineno, node.col_offset, False)


@dataclasses.dataclass
class Function(Definition):
  """Represents a function definition.

  Example function definition:
    @some_dec
    def f(a, b=1, *c, d, e=2, **f): ...
  See Attributes below for which parts of the definition correspond to
  attributes in this class.

  Attributes:
    params: The list of positional parameters. e.g. [a, b]
    vararg: The variable-length argument. e.g. c
    kwonlyargs: The list of keyword-only arguments. e.g. [d, e]
    kwarg: The keyword argument. e.g. f
    decorators: The list of names of decorators on this function.
      e.g. ["some_dec"]
    is_async: Tracks whether this function is marked async.
  """
  params: List[Argument]
  vararg: Optional[Argument]
  kwonlyargs: List[Argument]
  kwarg: Optional[Argument]
  decorators: List[str]
  is_async: bool
  kind: ClassVar[str] = "function"

  @classmethod
  def from_node(cls, node: Union[ast3.FunctionDef, ast3.AsyncFunctionDef],
                source: str = ""):
    """Transform an AST function node into a Function definition.

    Arguments:
      node: The ast3.FunctionDef or ast3.AsyncFunctionDef to transform.
      source: (Optional) The source file of this definition.

    Returns:
      A Function derived from the given AST node.
    """
    params = [Argument.from_node(arg) for arg in node.args.args]
    # If there are n parameters and m default arguments, m <= n, then each param
    # in params[n-m:n] has a default argument.
    for i in range(1, len(node.args.defaults)+1):
      params[-i].has_default = True
    kwonlyargs = [Argument.from_node(arg) for arg in node.args.kwonlyargs]
    # kw_defaults has an entry for each keyword-only argument, with either None
    # or the parsed value.
    for i, default in enumerate(node.args.kw_defaults):
      kwonlyargs[i].has_default = default is not None
    if node.args.vararg:
      vararg = Argument.from_node(node.args.vararg)
    else:
      vararg = None
    if node.args.kwarg:
      kwarg = Argument.from_node(node.args.kwarg)
    else:
      kwarg = None
    # Decorators are expressions, but we only care about their names. We can
    # discard the decorators that don't have names, which shouldn't happen.
    decorators = _find_all_names(node.decorator_list)
    return cls(name=node.name,
               source=source,
               lineno=node.lineno,
               col_offset=node.col_offset,
               params=params,
               vararg=vararg,
               kwonlyargs=kwonlyargs,
               kwarg=kwarg,
               decorators=decorators,
               is_async=isinstance(node, ast3.AsyncFunctionDef))


@dataclasses.dataclass
class Variable(Definition):
  """Represents a variable definition.

  Variables that appear in type stubs are either global variables or class
  attributes.
  """
  kind: ClassVar[str] = "variable"

  @classmethod
  def from_node(cls, node: ast3.Name, source: str = ""):
    return cls(node.id, source, node.lineno, node.col_offset)


@dataclasses.dataclass
class Class(Definition):
  """Represents a class.

  Attributes:
    bases: List of base classes by name.
    keyword_bases: Dictionary of key to class name. This is used for constructs
      like Python 3's metaclasses: class A(metaclass=B): ...
    decorators: List of decorators on this class by name.
    fields: List of class and method attributes. Type stubs do not differentiate
      between the two types.
    methods: List of functions defined in the class.
    nested_classes: List of nested classes.
  """
  bases: List[str]
  keyword_bases: Dict[str, str]
  decorators: List[str]
  fields: List[Variable]
  methods: List[Function]
  nested_classes: List["Class"]
  kind: ClassVar[str] = "class"

  @classmethod
  def from_node(cls, node: ast3.ClassDef, fields: List[Variable],
                methods: List[Function], nested_classes: List["Class"],
                source: str = ""):
    """Transform an ast3.ClassDef into a Class definition.

    Due to the complexity of parsing classes, the caller must provide the
    attributes of the class separately.

    Arguments:
      node: The ClassDef itself.
      fields: List of fields in the class.
      methods: List of functions defined in the class.
      nested_classes: List of nested classes defined in the class.
      source: (Optional) The source file of this definition.

    Returns:
      A Class definition representing the ast3.ClassDef and its attributes.
    """
    bases = _find_all_names(node.bases)
    keyword_bases = _find_all_names(node.keywords)
    decorators = _find_all_names(node.decorator_list)
    return cls(name=node.name,
               source=source,
               lineno=node.lineno,
               col_offset=node.col_offset,
               bases=bases,
               keyword_bases=keyword_bases,
               decorators=decorators,
               fields=fields,
               methods=methods,
               nested_classes=nested_classes)


def _find_name(root: ast3.AST) -> Optional[str]:
  """Returns the first "name" field or ast3.Name expression in the AST."""
  for node in ast3.walk(root):
    if isinstance(node, ast3.Name):
      return node.id
    if isinstance(node, ast3.Attribute):
      # value.attr, e.g. self.x. We want attr.
      return node.attr
    if isinstance(node, ast3.Subscript):
      # value[slice], e.g. x[1] or x[1:2]. We want value.
      return _find_name(node.value)
    name = getattr(node, "name", None)
    if name:
      return name
  return None


def _find_all_names(nodes: List[ast3.AST]) -> List[str]:
  """Finds every name in a list of nodes. Ignores nodes with no name."""
  names = (_find_name(node) for node in nodes)
  return [name for name in names if name]
