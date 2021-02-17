# python3

"""Parse a pyi file using typed_ast."""

import hashlib
import sys

import typing
from typing import Any, List, Optional, Tuple, Union

import dataclasses

from pytype import utils
from pytype.ast import debug
from pytype.pyi.typed_ast import classdef
from pytype.pyi.typed_ast import conditions
from pytype.pyi.typed_ast import definitions
from pytype.pyi.typed_ast import function
from pytype.pyi.typed_ast import modules
from pytype.pyi.typed_ast import types
from pytype.pyi.typed_ast import visitor
from pytype.pyi.typed_ast.types import ParseError  # pylint: disable=g-importing-member
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd import visitors
from pytype.pytd.codegen import pytdgen

from typed_ast import ast3


_DEFAULT_PLATFORM = "linux"


#------------------------------------------------------
# imports


def _tuple_of_import(alias: ast3.AST) -> Tuple[str, str]:
  """Convert a typedast import into one that add_import expects."""
  if alias.asname is None:
    return alias.name
  return alias.name, alias.asname


def _import_from_module(module: Optional[str], level: int) -> str:
  """Convert a typedast import's 'from' into one that add_import expects."""
  if module is None:
    return {1: "__PACKAGE__", 2: "__PARENT__"}[level]
  prefix = "." * level
  return prefix + module


#------------------------------------------------------
# typevars


@dataclasses.dataclass
class _TypeVar:
  """Internal representation of typevars."""

  name: str
  bound: Optional[str]
  constraints: List[Any]

  @classmethod
  def from_call(cls, node: ast3.AST) -> "_TypeVar":
    """Construct a _TypeVar from an ast.Call node."""
    name, *constraints = node.args
    bound = None
    # 'bound' is the only keyword argument we currently use.
    # TODO(rechen): We should enforce the PEP 484 guideline that
    # len(constraints) != 1. However, this guideline is currently violated
    # in typeshed (see https://github.com/python/typeshed/pull/806).
    kws = {x.arg for x in node.keywords}
    extra = kws - {"bound", "covariant", "contravariant"}
    if extra:
      raise ParseError("Unrecognized keyword(s): %s" % ", ".join(extra))
    for kw in node.keywords:
      if kw.arg == "bound":
        bound = kw.value
    return cls(name, bound, constraints)


#------------------------------------------------------
# pytd utils

#------------------------------------------------------
# Main tree visitor and generator code


def _attribute_to_name(node: ast3.Attribute) -> ast3.Name:
  """Recursively convert Attributes to Names."""
  val = node.value
  if isinstance(val, ast3.Name):
    prefix = val.id
  elif isinstance(val, ast3.Attribute):
    prefix = _attribute_to_name(val).id
  elif isinstance(val, (pytd.NamedType, pytd.Module)):
    prefix = val.name
  else:
    msg = "Unexpected attribute access on %r [%s]" % (val, type(val))
    raise ParseError(msg)
  return ast3.Name(prefix + "." + node.attr)


class AnnotationVisitor(visitor.BaseVisitor):
  """Converts typed_ast annotations to pytd."""

  def show(self, node):
    print(debug.dump(node, ast3, include_attributes=False))

  def convert_late_annotation(self, annotation):
    try:
      # Late annotations may need to be parsed into an AST first
      if annotation.isalpha():
        return self.defs.new_type(annotation)
      a = ast3.parse(annotation)
      # Unwrap the module the parser puts around the source string
      typ = a.body[0].value
      return self.visit(typ)
    except ParseError as e:
      # Clear out position information since it is relative to the typecomment
      e.clear_position()
      raise e

  def visit_Tuple(self, node):
    return tuple(node.elts)

  def visit_List(self, node):
    return list(node.elts)

  def visit_Name(self, node):
    if self.subscripted and (node is self.subscripted[-1]):
      # This is needed because
      #   Foo[X]
      # parses to
      #   Subscript(Name(id = Foo), Name(id = X))
      # so we see visit_Name(Foo) before visit_Subscript(Foo[X]).
      # If Foo resolves to a generic type we want to know if it is being passed
      # params in this context (in which case we simply resolve the type here,
      # and create a new type when we get the param list in visit_Subscript) or
      # if it is just being used as a bare Foo, in which case we need to create
      # the new type Foo[Any] below.
      return self.defs.resolve_type(node.id)
    else:
      return self.defs.new_type(node.id)

  def enter_Subscript(self, node):
    if isinstance(node.value, ast3.Attribute):
      node.value = _attribute_to_name(node.value).id
    self.subscripted.append(node.value)

  def visit_Subscript(self, node):
    params = node.slice.value
    if type(params) is not tuple:  # pylint: disable=unidiomatic-typecheck
      params = (params,)
    return self.defs.new_type(node.value, params)

  def leave_Subscript(self, node):
    self.subscripted.pop()

  def visit_Attribute(self, node):
    annotation = _attribute_to_name(node).id
    return self.defs.new_type(annotation)

  def visit_BoolOp(self, node):
    if isinstance(node.op, ast3.Or):
      raise ParseError("Deprecated syntax `x or y`; use `Union[x, y]` instead")
    else:
      raise ParseError(f"Unexpected operator {node.op}")


def _flatten_splices(body: List[Any]) -> List[Any]:
  """Flatten a list with nested Splices."""
  if not any(isinstance(x, Splice) for x in body):
    return body
  out = []
  for x in body:
    if isinstance(x, Splice):
      # This technically needn't be recursive because of how we build Splices
      # but better not to have the class assume that.
      out.extend(_flatten_splices(x.body))
    else:
      out.append(x)
  return out


class Splice:
  """Splice a list into a node body."""

  def __init__(self, body):
    self.body = _flatten_splices(body)

  def __str__(self):
    return "Splice(\n" + ",\n  ".join([str(x) for x in self.body]) + "\n)"

  def __repr__(self):
    return str(self)


class GeneratePytdVisitor(visitor.BaseVisitor):
  """Converts a typed_ast tree to a pytd tree."""

  def __init__(self, src, filename, module_name, version, platform):
    defs = definitions.Definitions(modules.Module(filename, module_name))
    super().__init__(defs=defs, filename=filename)
    self.src_code = src
    self.module_name = module_name
    self.version = version
    self.platform = platform or _DEFAULT_PLATFORM
    self.level = 0
    self.in_function = False  # pyi will not have nested defs
    self.annotation_visitor = AnnotationVisitor(defs=defs, filename=filename)

  def show(self, node):
    print(debug.dump(node, ast3, include_attributes=False))

  def convert_node(self, node):
    # Converting a node via a visitor will convert the subnodes, but if the
    # argument node itself needs conversion, we need to use the pattern
    #   node = annotation_visitor.visit(node)
    # However, the AnnotationVisitor returns None if it does not trigger on the
    # root node it is passed, so call it via this method instead.
    ret = self.annotation_visitor.visit(node)
    return ret if ret is not None else node

  def convert_node_annotations(self, node):
    """Transform type annotations to pytd."""
    if getattr(node, "annotation", None):
      node.annotation = self.convert_node(node.annotation)
    elif getattr(node, "type_comment", None):
      node.type_comment = self.annotation_visitor.convert_late_annotation(
          node.type_comment)

  def resolve_name(self, name):
    """Resolve an alias or create a NamedType."""
    return self.defs.type_map.get(name) or pytd.NamedType(name)

  def visit_Module(self, node):
    node.body = _flatten_splices(node.body)
    return self.defs.build_type_decl_unit(node.body)

  def visit_Pass(self, node):
    return self.defs.ELLIPSIS

  def visit_Expr(self, node):
    # Handle some special cases of expressions that can occur in class and
    # module bodies.
    if node.value == self.defs.ELLIPSIS:
      # class x: ...
      return node.value
    elif types.Constant.is_str(node.value):
      # docstrings
      return Splice([])

  def visit_arg(self, node):
    self.convert_node_annotations(node)

  def _preprocess_decorator_list(self, node):
    decorators = []
    for d in node.decorator_list:
      if isinstance(d, ast3.Name):
        decorators.append(d.id)
      elif isinstance(d, ast3.Attribute):
        decorators.append(f"{d.value.id}.{d.attr}")
      else:
        raise ParseError(f"Unexpected decorator: {d}")
    node.decorator_list = decorators

  def _preprocess_function(self, node):
    node.args = self.convert_node(node.args)
    node.returns = self.convert_node(node.returns)
    self._preprocess_decorator_list(node)
    node.body = _flatten_splices(node.body)

  def visit_FunctionDef(self, node):
    self._preprocess_function(node)
    return function.NameAndSig.from_function(node, False)

  def visit_AsyncFunctionDef(self, node):
    self._preprocess_function(node)
    return function.NameAndSig.from_function(node, True)

  def new_alias_or_constant(self, name, value):
    """Build an alias or constant."""
    # This is here rather than in _Definitions because we need to build a
    # constant or alias from a partially converted typed_ast subtree.
    if name == "__slots__":
      if not (isinstance(value, ast3.List) and
              all(types.Constant.is_str(x) for x in value.elts)):
        raise ParseError("__slots__ must be a list of strings")
      return types.SlotDecl(tuple([x.value for x in value.elts]))
    elif isinstance(value, types.Constant):
      return pytd.Constant(name, value.to_pytd())
    elif isinstance(value, types.Ellipsis):
      return pytd.Constant(name, pytd.AnythingType())
    elif isinstance(value, pytd.NamedType):
      res = self.defs.resolve_type(value.name)
      return pytd.Alias(name, res)
    elif isinstance(value, ast3.List):
      if name != "__all__":
        raise ParseError("Only __slots__ and __all__ can be literal lists")
      return pytd.Constant(name, pytdgen.pytd_list("str"))
    elif isinstance(value, ast3.Tuple):
      # TODO(mdemello): Consistent with the current parser, but should it
      # properly be Tuple[Type]?
      return pytd.Constant(name, pytd.NamedType("tuple"))
    elif isinstance(value, ast3.Name):
      value = self.defs.resolve_type(value.id)
      return pytd.Alias(name, value)
    else:
      # TODO(mdemello): add a case for TypeVar()
      # Convert any complex type aliases
      value = self.convert_node(value)
      return pytd.Alias(name, value)

  def enter_AnnAssign(self, node):
    self.convert_node_annotations(node)

  def visit_AnnAssign(self, node):
    name = node.target.id
    typ = node.annotation
    val = self.convert_node(node.value)
    if val and not types.is_any(val):
      msg = f"Default value for {name}: {typ.name} can only be '...', got {val}"
      raise ParseError(msg)
    return pytd.Constant(name, typ)

  def visit_Assign(self, node):
    targets = node.targets
    if len(targets) > 1 or isinstance(targets[0], ast3.Tuple):
      msg = "Assignments must be of the form 'name = value'"
      raise ParseError(msg)
    self.convert_node_annotations(node)
    target = targets[0]
    name = target.id

    # Record and erase typevar definitions.
    if isinstance(node.value, _TypeVar):
      self.defs.add_type_var(name, node.value)
      return Splice([])

    if node.type_comment:
      # TODO(mdemello): can pyi files have aliases with typecomments?
      ret = pytd.Constant(name, node.type_comment)
    else:
      ret = self.new_alias_or_constant(name, node.value)

    if self.in_function:
      # Should never happen, but this keeps pytype happy.
      if isinstance(ret, types.SlotDecl):
        raise ParseError("Cannot change the type of __slots__")
      return function.Mutator(name, ret.type)

    if self.level == 0:
      self.defs.add_alias_or_constant(ret)
    return ret

  def visit_ClassDef(self, node):
    class_name = node.name
    self.defs.type_map[class_name] = pytd.NamedType(class_name)

    # Convert decorators to named types
    self._preprocess_decorator_list(node)
    decorators = classdef.get_decorators(
        node.decorator_list, self.defs.type_map)

    self.annotation_visitor.visit(node.bases)
    self.annotation_visitor.visit(node.keywords)
    defs = _flatten_splices(node.body)
    return self.defs.build_class(
        class_name, node.bases, node.keywords, decorators, defs)

  def enter_If(self, node):
    # Evaluate the test and preemptively remove the invalid branch so we don't
    # waste time traversing it.
    node.test = conditions.evaluate(node.test, self.version, self.platform)
    if not isinstance(node.test, bool):
      raise ParseError("Unexpected if statement" + debug.dump(node, ast3))

    if node.test:
      node.orelse = []
    else:
      node.body = []

  def visit_If(self, node):
    if not isinstance(node.test, bool):
      raise ParseError("Unexpected if statement" + debug.dump(node, ast3))

    if node.test:
      return Splice(node.body)
    else:
      return Splice(node.orelse)

  def visit_Import(self, node):
    if self.level > 0:
      raise ParseError("Import statements need to be at module level")
    imports = [_tuple_of_import(x) for x in node.names]
    self.defs.add_import(None, imports)
    return Splice([])

  def visit_ImportFrom(self, node):
    if self.level > 0:
      raise ParseError("Import statements need to be at module level")
    imports = [_tuple_of_import(x) for x in node.names]
    module = _import_from_module(node.module, node.level)
    self.defs.add_import(module, imports)
    return Splice([])

  def _convert_newtype_args(self, node):
    if len(node.args) != 2:
      msg = "Wrong args: expected NewType(name, [(field, type), ...])"
      raise ParseError(msg)
    name, typ = node.args
    typ = self.convert_node(typ)
    node.args = [name.s, typ]

  def _convert_typing_namedtuple_args(self, node):
    # TODO(mdemello): handle NamedTuple("X", a=int, b=str, ...)
    if len(node.args) != 2:
      msg = "Wrong args: expected NamedTuple(name, [(field, type), ...])"
      raise ParseError(msg)
    name, fields = node.args
    fields = self.convert_node(fields)
    fields = [(types.string_value(n), t) for (n, t) in fields]
    node.args = [name.s, fields]

  def _convert_collections_namedtuple_args(self, node):
    if len(node.args) != 2:
      msg = "Wrong args: expected namedtuple(name, [field, ...])"
      raise ParseError(msg)
    name, fields = node.args
    fields = self.convert_node(fields)
    fields = [(types.string_value(n), pytd.AnythingType()) for n in fields]
    node.args = [name.s, fields]

  def _convert_typevar_args(self, node):
    self.annotation_visitor.visit(node.keywords)
    if not node.args:
      raise ParseError("Missing arguments to TypeVar")
    name, *rest = node.args
    if not isinstance(name, ast3.Str):
      raise ParseError("Bad arguments to TypeVar")
    node.args = [name.s] + [self.convert_node(x) for x in rest]
    # Special-case late types in bound since typeshed uses it.
    for kw in node.keywords:
      if kw.arg == "bound":
        if isinstance(kw.value, types.Constant):
          val = types.string_value(kw.value, context="TypeVar bound")
          kw.value = self.annotation_visitor.convert_late_annotation(val)

  def _convert_typed_dict_args(self, node):
    # TODO(b/157603915): new_typed_dict currently doesn't do anything with the
    # args, so we don't bother converting them fully.
    msg = "Wrong args: expected TypedDict(name, {field: type, ...})"
    if len(node.args) != 2:
      raise ParseError(msg)
    name, fields = node.args
    if not (isinstance(name, ast3.Str) and isinstance(fields, ast3.Dict)):
      raise ParseError(msg)

  def enter_Call(self, node):
    # Some function arguments need to be converted from strings to types when
    # entering the node, rather than bottom-up when they would already have been
    # converted to types.Constant.
    # We also convert some literal string nodes that are not meant to be types
    # (e.g. the first arg to TypeVar()) to their bare values since we are
    # passing them to internal functions directly in visit_Call.
    if isinstance(node.func, ast3.Attribute):
      node.func = _attribute_to_name(node.func)
    if node.func.id in ("TypeVar", "typing.TypeVar"):
      self._convert_typevar_args(node)
    elif node.func.id in ("NamedTuple", "typing.NamedTuple"):
      self._convert_typing_namedtuple_args(node)
    elif node.func.id in ("namedtuple", "collections.namedtuple"):
      self._convert_collections_namedtuple_args(node)
    elif node.func.id in ("TypedDict", "typing.TypedDict",
                          "typing_extensions.TypedDict"):
      self._convert_typed_dict_args(node)
    elif node.func.id in ("NewType", "typing.NewType"):
      return self._convert_newtype_args(node)

  def visit_Call(self, node):
    if node.func.id in ("TypeVar", "typing.TypeVar"):
      if self.level > 0:
        raise ParseError("TypeVars need to be defined at module level")
      return _TypeVar.from_call(node)
    elif node.func.id in ("NamedTuple", "typing.NamedTuple",
                          "namedtuple", "collections.namedtuple"):
      return self.defs.new_named_tuple(*node.args)
    elif node.func.id in ("TypedDict", "typing.TypedDict",
                          "typing_extensions.TypedDict"):
      return self.defs.new_typed_dict(*node.args, total=False)
    elif node.func.id in ("NewType", "typing.NewType"):
      return self.defs.new_new_type(*node.args)
    # Convert all other calls to NamedTypes; for example:
    # * typing.pyi uses things like
    #     List = _Alias()
    # * pytd extensions allow both
    #     raise Exception
    #   and
    #     raise Exception()
    return pytd.NamedType(node.func.id)

  def visit_Raise(self, node):
    ret = self.convert_node(node.exc)
    return types.Raise(ret)

  # Track nesting level

  def enter_FunctionDef(self, node):
    self.level += 1
    self.in_function = True

  def leave_FunctionDef(self, node):
    self.level -= 1
    self.in_function = False

  def enter_AsyncFunctionDef(self, node):
    self.enter_FunctionDef(node)

  def leave_AsyncFunctionDef(self, node):
    self.leave_FunctionDef(node)

  def enter_ClassDef(self, node):
    self.level += 1

  def leave_ClassDef(self, node):
    self.level -= 1


def post_process_ast(ast, src, name=None):
  """Post-process the parsed AST."""
  ast = definitions.finalize_ast(ast)
  ast = ast.Visit(pep484.ConvertTypingToNative(name))

  if name:
    ast = ast.Replace(name=name)
    ast = ast.Visit(visitors.AddNamePrefix())
  else:
    # If there's no unique name, hash the sourcecode.
    ast = ast.Replace(name=hashlib.md5(src.encode("utf-8")).hexdigest())
  ast = ast.Visit(visitors.StripExternalNamePrefix())

  # Typeshed files that explicitly import and refer to "__builtin__" need to
  # have that rewritten to builtins
  return ast.Visit(visitors.RenameBuiltinsPrefix())


def _parse(src: str, feature_version: int, filename: str = ""):
  """Call the typed_ast parser with the appropriate feature version."""
  try:
    ast_root_node = ast3.parse(src, filename, feature_version=feature_version)
  except SyntaxError as e:
    raise ParseError(e.msg, line=e.lineno, filename=filename) from e
  return ast_root_node


# Python version input type.
VersionType = Union[int, Tuple[int, ...]]


def _feature_version(python_version: VersionType) -> int:
  """Get the python feature version for the parser."""
  def from_major(v):
    # We only use this to set the feature version, and all pyi files need to
    # parse as at least python 3.6
    if v == 2:
      return 6
    else:
      # We don't support host python2, so sys.version = 3.x
      return sys.version_info.minor
  if isinstance(python_version, int):
    return from_major(python_version)
  else:
    python_version = typing.cast(Tuple[int, ...], python_version)
    if len(python_version) == 1:
      return from_major(python_version[0])
    else:
      if python_version[0] == 2:
        return 6
      return python_version[1]


def parse_string(
    src: str,
    python_version: VersionType,
    name: Optional[str] = None,
    filename: Optional[str] = None,
    platform: Optional[str] = None
):
  return parse_pyi(src, filename=filename, module_name=name,
                   platform=platform, python_version=python_version)


def parse_pyi(
    src: str,
    filename: Optional[str],
    module_name: str,
    python_version: VersionType,
    platform: Optional[str] = None
) -> pytd.TypeDeclUnit:
  """Parse a pyi string."""
  filename = filename or ""
  feature_version = _feature_version(python_version)
  python_version = utils.normalize_version(python_version)
  root = _parse(src, feature_version, filename)
  gen_pytd = GeneratePytdVisitor(
      src, filename, module_name, python_version, platform)
  root = gen_pytd.visit(root)
  root = post_process_ast(root, src, module_name)
  return root


def parse_pyi_debug(
    src: str,
    filename: str,
    module_name: str,
    python_version: VersionType,
    platform: Optional[str] = None
) -> Tuple[pytd.TypeDeclUnit, GeneratePytdVisitor]:
  """Debug version of parse_pyi."""
  feature_version = _feature_version(python_version)
  python_version = utils.normalize_version(python_version)
  root = _parse(src, feature_version, filename)
  print(debug.dump(root, ast3, include_attributes=False))
  gen_pytd = GeneratePytdVisitor(
      src, filename, module_name, python_version, platform)
  root = gen_pytd.visit(root)
  print("---transformed parse tree--------------------")
  print(root)
  root = post_process_ast(root, src, module_name)
  print("---post-processed---------------------")
  print(root)
  print("------------------------")
  print(gen_pytd.defs.type_map)
  print(gen_pytd.defs.module_path_map)
  return root, gen_pytd
