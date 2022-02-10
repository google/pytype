"""Function definitions in pyi files."""

import sys
import textwrap

from typing import Any, List, Optional

from pytype import utils
from pytype.pyi import types
from pytype.pyi.types import ParseError  # pylint: disable=g-importing-member
from pytype.pytd import pytd
from pytype.pytd import visitors
from pytype.pytd.codegen import function as pytd_function

# pylint: disable=g-import-not-at-top
if sys.version_info >= (3, 8):
  import ast as ast3
else:
  from typed_ast import ast3
# pylint: enable=g-import-not-at-top


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
            f"Argument {p.name!r} cannot be both mutable and optional")
      return p.Replace(mutated_type=self.new_type)
    else:
      return p

  def __repr__(self):
    return f"Mutator<{self.name} -> {self.new_type}>"

  __str__ = __repr__


class Param(pytd_function.Param):
  """Internal representation of function parameters."""

  @classmethod
  def from_arg(cls, arg: ast3.arg, kind: pytd.ParameterKind) -> "Param":
    """Constructor from an ast.argument node."""
    p = cls(arg.arg)
    if arg.annotation:
      p.type = arg.annotation
    p.kind = kind
    return p


class NameAndSig(pytd_function.NameAndSig):
  """Internal representation of function signatures."""

  @classmethod
  def from_function(
      cls, function: ast3.FunctionDef, is_async: bool) -> "NameAndSig":
    """Constructor from an ast.FunctionDef node."""
    name = function.name

    # decorators
    decorators = set(function.decorator_list)
    abstracts = {"abstractmethod", "abc.abstractmethod"}
    coroutines = {"coroutine", "asyncio.coroutine", "coroutines.coroutine"}
    overload = {"overload"}
    final = {"final"}
    ignored = {"type_check_only"}
    is_abstract = bool(decorators & abstracts)
    is_coroutine = bool(decorators & coroutines)
    is_overload = bool(decorators & overload)
    is_final = bool(decorators & final)
    decorators -= (abstracts | coroutines | overload | final | ignored)
    # TODO(mdemello): do we need this limitation?
    if len(decorators) > 1:
      raise ParseError(f"Too many decorators for {name}")
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
    # If `self` is generic, a type parameter is being mutated.
    if (sig.params and sig.params[0].name == "self" and
        isinstance(sig.params[0].type, pytd.GenericType)):
      mutators.append(Mutator("self", sig.params[0].type))
    for mutator in mutators:
      try:
        sig = sig.Visit(mutator)
      except NotImplementedError as e:
        raise ParseError(utils.message(e)) from e
      if not mutator.successful:
        raise ParseError(f"No parameter named {mutator.name!r}")

    return cls(name, sig, decorator, is_abstract, is_coroutine, is_final,
               is_overload)


def _pytd_signature(
    function: ast3.FunctionDef,
    is_async: bool,
    exceptions: Optional[List[pytd.Type]] = None
) -> pytd.Signature:
  """Construct a pytd signature from an ast.FunctionDef node."""
  name = function.name
  args = function.args
  # Positional-only parameters are new in Python 3.8.
  posonly_params = [Param.from_arg(a, pytd.ParameterKind.POSONLY)
                    for a in getattr(args, "posonlyargs", ())]
  pos_params = [Param.from_arg(a, pytd.ParameterKind.REGULAR)
                for a in args.args]
  kwonly_params = [Param.from_arg(a, pytd.ParameterKind.KWONLY)
                   for a in args.kwonlyargs]
  _apply_defaults(posonly_params + pos_params, args.defaults)
  _apply_defaults(kwonly_params, args.kw_defaults)
  all_params = posonly_params + pos_params + kwonly_params
  params = tuple(x.to_pytd() for x in all_params)
  starargs = _pytd_star_param(args.vararg)
  starstarargs = _pytd_starstar_param(args.kwarg)
  ret = pytd_function.pytd_return_type(name, function.returns, is_async)
  exceptions = exceptions or []
  return pytd.Signature(params=params,
                        return_type=ret,
                        starargs=starargs,
                        starstarargs=starstarargs,
                        exceptions=tuple(exceptions), template=())


def _pytd_star_param(arg: ast3.arg) -> Optional[pytd.Parameter]:
  """Return a pytd.Parameter for a *args argument."""
  if not arg:
    return None
  return pytd_function.pytd_star_param(arg.arg, arg.annotation)


def _pytd_starstar_param(
    arg: Optional[ast3.arg]) -> Optional[pytd.Parameter]:
  """Return a pytd.Parameter for a **kwargs argument."""
  if not arg:
    return None
  return pytd_function.pytd_starstar_param(arg.arg, arg.annotation)


def _apply_defaults(params: List[Param], defaults: List[Any]) -> None:
  for p, d in zip(reversed(params), reversed(defaults)):
    if d is None:
      continue
    elif isinstance(d, types.Pyval):
      p.default = d.to_pytd()
    else:
      p.default = pytd.AnythingType()
