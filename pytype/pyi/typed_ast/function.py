"""Function definitions in pyi files."""

import collections
import textwrap

from typing import Any, Dict, List, Optional, Tuple

import dataclasses

from pytype import utils
from pytype.pyi.typed_ast import types
from pytype.pyi.typed_ast.types import ParseError  # pylint: disable=g-importing-member
from pytype.pytd import pytd
from pytype.pytd import visitors
from pytype.pytd.parse import node as pytd_node

from typed_ast import ast3


class OverloadedDecoratorError(ParseError):
  """Inconsistent decorators on an overloaded function."""

  def __init__(self, name, typ, *args, **kwargs):
    msg = "Overloaded signatures for %s disagree on %sdecorators" % (
        name, (typ + " " if typ else ""))
    super().__init__(msg, *args, **kwargs)


# Strategies for combining a new decorator with an existing one
_MERGE, _REPLACE, _DISCARD = 1, 2, 3


class Mutator(visitors.Visitor):
  """Visitor for adding a mutated_type to parameters.

  We model the parameter x in
    def f(x: old_type):
      x = new_type
  as
    Parameter(name=x, type=old_type, mutated_type=new_type)
  .
  This visitor applies the body "x = new_type" to the function signature.
  """

  def __init__(self, name, new_type):
    super().__init__()
    self.name = name
    self.new_type = new_type
    self.successful = False

  def VisitParameter(self, p):
    if p.name == self.name:
      self.successful = True
      if p.optional:
        raise NotImplementedError(
            "Argument %s can not be both mutable and optional" % p.name)
      return p.Replace(mutated_type=self.new_type)
    else:
      return p

  def __repr__(self):
    return f"Mutator<{self.name} -> {self.new_type}>"

  __str__ = __repr__


@dataclasses.dataclass
class Param:
  """Internal representation of function parameters."""

  name: str
  type: Optional[str] = None
  default: Any = None
  kwonly: bool = False

  @classmethod
  def from_arg(cls, arg: ast3.AST, kwonly=False) -> "Param":
    """Constructor from an ast.argument node."""
    p = cls(arg.arg)
    if arg.annotation:
      p.type = arg.annotation
    p.kwonly = kwonly
    return p

  def to_pytd(self) -> pytd.Parameter:
    """Return a pytd.Parameter object for a normal argument."""
    if self.default is not None:
      default_type = self.default
      if self.type is None and default_type != pytd.NamedType("NoneType"):
        self.type = default_type
    if self.type is None:
      self.type = pytd.AnythingType()

    optional = self.default is not None
    return pytd.Parameter(self.name, self.type, self.kwonly, optional, None)


@dataclasses.dataclass(frozen=True)
class NameAndSig:
  """Internal representation of function signatures."""

  name: str
  signature: pytd.Signature
  decorator: Optional[str] = None
  is_abstract: bool = False
  is_coroutine: bool = False
  is_overload: bool = False

  @classmethod
  def from_function(cls, function: ast3.AST, is_async: bool) -> "NameAndSig":
    """Constructor from an ast.FunctionDef node."""
    name = function.name

    # decorators
    decorators = set(function.decorator_list)
    abstracts = {"abstractmethod", "abc.abstractmethod"}
    coroutines = {"coroutine", "asyncio.coroutine", "coroutines.coroutine"}
    overload = {"overload"}
    ignored = {"type_check_only"}
    is_abstract = bool(decorators & abstracts)
    is_coroutine = bool(decorators & coroutines)
    is_overload = bool(decorators & overload)
    decorators -= abstracts
    decorators -= coroutines
    decorators -= overload
    decorators -= ignored
    # TODO(mdemello): do we need this limitation?
    if len(decorators) > 1:
      raise ParseError("Too many decorators for %s" % name)
    decorator, = decorators if decorators else (None,)

    exceptions = []
    mutators = []
    for i, x in enumerate(function.body):
      if isinstance(x, types.Raise):
        exceptions.append(x.exception)
      elif isinstance(x, Mutator):
        mutators.append(x)
      elif isinstance(x, types.Ellipsis):
        pass
      elif (isinstance(x, ast3.Expr) and
            isinstance(x.value, ast3.Str) and
            i == 0):
        # docstring
        pass
      else:
        msg = textwrap.dedent("""
            Unexpected statement in function body.
            Only `raise` statements and type mutations are valid
        """).lstrip()
        if isinstance(x, ast3.AST):
          raise ParseError(msg).at(x)
        else:
          raise ParseError(msg)

    # exceptions
    sig = _pytd_signature(function, is_async, exceptions=exceptions)

    # mutators
    for mutator in mutators:
      try:
        sig = sig.Visit(mutator)
      except NotImplementedError as e:
        raise ParseError(utils.message(e)) from e
      if not mutator.successful:
        raise ParseError("No parameter named %s" % mutator.name)

    return cls(name, sig, decorator, is_abstract, is_coroutine, is_overload)

  @classmethod
  def make(
      cls,
      name: str,
      args: List[Tuple[str, pytd_node.Node]],
      return_type: pytd_node.Node
  ) -> "NameAndSig":
    """Make a new NameAndSig from an argument list."""
    params = tuple(Param(n, t).to_pytd() for (n, t) in args)
    sig = pytd.Signature(params=params, return_type=return_type,
                         starargs=None, starstarargs=None,
                         exceptions=(), template=())
    return cls(name, sig)


def _pytd_signature(
    function: ast3.AST,
    is_async: bool,
    exceptions: Optional[List[pytd_node.Node]] = None
) -> pytd.Signature:
  """Construct a pytd signature from an ast.FunctionDef node."""
  name = function.name
  args = function.args
  pos_params = [Param.from_arg(a, False) for a in args.args]
  kwonly_params = [Param.from_arg(a, True) for a in args.kwonlyargs]
  _apply_defaults(pos_params, args.defaults)
  _apply_defaults(kwonly_params, args.kw_defaults)
  all_params = pos_params + kwonly_params
  params = tuple([x.to_pytd() for x in all_params])
  starargs = _pytd_star_param(args.vararg)
  starstarargs = _pytd_starstar_param(args.kwarg)
  ret = _pytd_return_type(name, function.returns, is_async)
  exceptions = exceptions or []
  return pytd.Signature(params=params,
                        return_type=ret,
                        starargs=starargs,
                        starstarargs=starstarargs,
                        exceptions=tuple(exceptions), template=())


def _pytd_return_type(
    name: str,
    return_type: Optional[pytd_node.Node],
    is_async: bool
) -> pytd_node.Node:
  """Convert function return type to pytd."""
  if name == "__init__":
    if (return_type is None or
        isinstance(return_type, pytd.AnythingType)):
      ret = pytd.NamedType("NoneType")
    else:
      ret = return_type
  elif is_async:
    base = pytd.NamedType("typing.Coroutine")
    params = (pytd.AnythingType(), pytd.AnythingType(), return_type)
    ret = pytd.GenericType(base, params)
  elif return_type is None:
    ret = pytd.AnythingType()
  else:
    ret = return_type
  return ret


def pytd_default_star_param() -> pytd.Parameter:
  return pytd.Parameter("args", pytd.NamedType("tuple"), False, True, None)


def pytd_default_starstar_param() -> pytd.Parameter:
  return pytd.Parameter("kwargs", pytd.NamedType("dict"), False, True, None)


def _pytd_star_param(arg: ast3.AST) -> Optional[pytd.Parameter]:
  """Return a pytd.Parameter for a *args argument."""
  if not arg:
    return None
  name = arg.arg
  if arg.annotation is None:
    param_type = pytd.NamedType("tuple")
  else:
    param_type = pytd.GenericType(
        pytd.NamedType("tuple"), (arg.annotation,))
  return pytd.Parameter(name, param_type, False, True, None)


def _pytd_starstar_param(arg: ast3.AST) -> Optional[pytd.Parameter]:
  """Return a pytd.Parameter for a **kwargs argument."""
  if not arg:
    return None
  name = arg.arg
  if arg.annotation is None:
    param_type = pytd.NamedType("dict")
  else:
    param_type = pytd.GenericType(
        pytd.NamedType("dict"), (pytd.NamedType("str"),
                                 arg.annotation))
  return pytd.Parameter(name, param_type, False, True, None)


def _apply_defaults(params: List[Param], defaults: List[Any]) -> None:
  for p, d in zip(reversed(params), reversed(defaults)):
    if d is None:
      continue
    elif isinstance(d, types.Constant):
      p.default = d.to_pytd()
    else:
      p.default = pytd.AnythingType()


def merge_method_signatures(
    signatures: List[NameAndSig]
) -> List[pytd.Function]:
  """Group the signatures by name, turning each group into a function."""
  name_to_signatures = collections.OrderedDict()
  name_to_decorator = {}
  name_to_is_abstract = {}
  name_to_is_coroutine = {}
  for sig in signatures:
    if sig.name not in name_to_signatures:
      name_to_signatures[sig.name] = []
      name_to_decorator[sig.name] = sig.decorator
    old_decorator = name_to_decorator[sig.name]
    check = _check_decorator_overload(sig.name, old_decorator, sig.decorator)
    if check == _MERGE:
      name_to_signatures[sig.name].append(sig.signature)
    elif check == _REPLACE:
      name_to_signatures[sig.name] = [sig.signature]
      name_to_decorator[sig.name] = sig.decorator
    _add_flag_overload(
        name_to_is_abstract, sig.name, sig.is_abstract, "abstractmethod")
    _add_flag_overload(
        name_to_is_coroutine, sig.name, sig.is_coroutine, "coroutine")
  methods = []
  for name, sigs in name_to_signatures.items():
    decorator = name_to_decorator[name]
    is_abstract = name_to_is_abstract[name]
    is_coroutine = name_to_is_coroutine[name]
    if name == "__new__" or decorator == "staticmethod":
      kind = pytd.STATICMETHOD
    elif name == "__init_subclass__" or decorator == "classmethod":
      kind = pytd.CLASSMETHOD
    elif _is_property(name, decorator, sigs[0]):
      kind = pytd.PROPERTY
      # If we have only setters and/or deleters, replace them with a single
      # method foo(...) -> Any, so that we infer a constant `foo: Any` even if
      # the original method signatures are all `foo(...) -> None`. (If we have a
      # getter we use its return type, but in the absence of a getter we want to
      # fall back on Any since we cannot say anything about what the setter sets
      # the type of foo to.)
      if decorator.endswith(".setter") or decorator.endswith(".deleter"):
        sigs = [sigs[0].Replace(return_type=pytd.AnythingType())]
    else:
      kind = pytd.METHOD
    flags = 0
    if is_abstract:
      flags |= pytd.Function.IS_ABSTRACT
    if is_coroutine:
      flags |= pytd.Function.IS_COROUTINE
    methods.append(pytd.Function(name, tuple(sigs), kind, flags))
  return methods


@dataclasses.dataclass
class _Property:
  precedence: int
  arity: int


def _property_decorators(name: str) -> Dict[str, _Property]:
  """Generates the property decorators for a method name.

  Used internally by other methods.

  Args:
    name: method name

  Returns:
    A dictionary of decorators to precedence and required arity
  """
  return {
      "property": _Property(2, 1),
      (name + ".getter"): _Property(2, 1),
      (name + ".setter"): _Property(1, 2),
      (name + ".deleter"): _Property(1, 1)
  }


def _check_decorator_overload(name: str, old: str, new: str) -> int:
  """Conditions for a decorator to overload an existing one."""
  properties = _property_decorators(name)
  if old == new:
    return _MERGE
  elif old in properties and new in properties:
    p_old, p_new = properties[old].precedence, properties[new].precedence
    if p_old > p_new:
      return _DISCARD
    elif p_old == p_new:
      return _MERGE
    else:
      return _REPLACE
  raise OverloadedDecoratorError(name, "")


def _add_flag_overload(
    mapping: Dict[str, bool], name: str, val: bool, flag: str
) -> None:
  if name not in mapping:
    mapping[name] = val
  elif mapping[name] != val:
    raise OverloadedDecoratorError(name, flag)


def _is_property(name: str, decorator: str, signature: pytd.Signature) -> bool:
  """Parse a signature as a property getter, setter, or deleter.

  Checks that the decorator name matches one of {@property, @foo.getter,
  @foo.setter, @foo.deleter} and that the corresponding signature is valid.

  NOTE: This function assumes that all other recognised decorators have already
  been handled, and will therefore raise if decorator is not a property.

  Args:
    name: method name
    decorator: decorator
    signature: method signature
  Returns:
    True: If we have a valid property decorator
    False: If decorator is None
  Raises:
    ParseError: If we have a non-property decorator.
  """
  if not decorator:
    return False
  sigs = _property_decorators(name)
  if decorator in sigs and sigs[decorator].arity == len(signature.params):
    return True
  raise ParseError("Unhandled decorator: %s" % decorator)
