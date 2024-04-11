"""Abstract representations of functions.

All functions have four attributes:
* name: a name,
* signatures: a sequence of signatures,
* call: a method that calls the function with fixed arguments,
* analyze: a method that generates fake arguments for the function based on its
  signatures and calls it with those.

Most types of functions are subclasses of `SimpleFunction`, which requires
subclasses to implement a `call_with_mapped_args` method, which takes a mapping
of parameter names to argument values (e.g., `{x: 0}` when a function
`def f(x): ...` is called as `f(0)`) and calls the function. `SimpleFunction`
provides a `map_args` method to map function arguments. It uses these two
methods to implement `call` and `analyze`.
"""

import abc
import dataclasses
import logging
from typing import Dict, Generic, Mapping, Optional, Protocol, Sequence, Tuple, TypeVar

import immutabledict
from pytype.blocks import blocks
from pytype.pytd import pytd
from pytype.rewrite.abstract import base

log = logging.getLogger(__name__)

_EMPTY_MAP = immutabledict.immutabledict()
_ArgDict = Dict[str, base.AbstractVariableType]


class FrameType(Protocol):
  """Protocol for a VM frame."""

  name: str
  final_locals: Mapping[str, base.BaseValue]
  stack: Sequence['FrameType']

  def make_child_frame(
      self,
      func: 'InterpreterFunction',
      initial_locals: Mapping[str, base.AbstractVariableType],
  ) -> 'FrameType': ...

  def run(self) -> None: ...

  def get_return_value(self) -> base.BaseValue: ...


_FrameT = TypeVar('_FrameT', bound=FrameType)


@dataclasses.dataclass
class Args(Generic[_FrameT]):
  """Arguments to one function call."""
  posargs: Tuple[base.AbstractVariableType, ...] = ()
  kwargs: Mapping[str, base.AbstractVariableType] = _EMPTY_MAP
  starargs: Optional[base.AbstractVariableType] = None
  starstarargs: Optional[base.AbstractVariableType] = None
  frame: Optional[_FrameT] = None


@dataclasses.dataclass
class MappedArgs(Generic[_FrameT]):
  """Function call args that have been mapped to a signature and param names."""
  signature: 'Signature'
  argdict: _ArgDict
  frame: Optional[_FrameT] = None


class _HasReturn(Protocol):

  def get_return_value(self) -> base.BaseValue: ...


_HasReturnT = TypeVar('_HasReturnT', bound=_HasReturn)


class SimpleReturn:

  def __init__(self, return_value: base.BaseValue):
    self._return_value = return_value

  def get_return_value(self):
    return self._return_value


class Signature:
  """Representation of a Python function signature.

  Attributes:
    name: Name of the function.
    param_names: A tuple of positional parameter names. This DOES include
      positional-only parameters and does NOT include keyword-only parameters.
    posonly_count: Number of positional-only parameters.
    varargs_name: Name of the varargs parameter. (The "args" in *args)
    kwonly_params: Tuple of keyword-only parameters.
      E.g. ("x", "y") for "def f(a, *, x, y=2)". These do NOT appear in
      param_names. Ordered like in the source file.
    kwargs_name: Name of the kwargs parameter. (The "kwargs" in **kwargs)
    defaults: Dictionary, name to value, for all parameters with default values.
    annotations: A dictionary of type annotations. (string to type)
    posonly_params: Tuple of positional-only parameters (i.e., the first
      posonly_count names in param_names).
  """

  def __init__(
      self,
      ctx: base.ContextType,
      name: str,
      param_names: Tuple[str, ...],
      *,
      posonly_count: int = 0,
      varargs_name: Optional[str] = None,
      kwonly_params: Tuple[str, ...] = (),
      kwargs_name: Optional[str] = None,
      defaults: Mapping[str, base.BaseValue] = _EMPTY_MAP,
      annotations: Mapping[str, base.BaseValue] = _EMPTY_MAP,
  ):
    self._ctx = ctx
    self.name = name
    self.param_names = param_names
    self.posonly_count = posonly_count
    self.varargs_name = varargs_name
    self.kwonly_params = kwonly_params
    self.kwargs_name = kwargs_name
    self.defaults = defaults
    self.annotations = annotations

  @property
  def posonly_params(self):
    return self.param_names[:self.posonly_count]

  @classmethod
  def from_code(
      cls, ctx: base.ContextType, name: str, code: blocks.OrderedCode,
  ) -> 'Signature':
    """Builds a signature from a code object."""
    nonstararg_count = code.argcount + code.kwonlyargcount
    if code.has_varargs():
      varargs_name = code.varnames[nonstararg_count]
      kwargs_pos = nonstararg_count + 1
    else:
      varargs_name = None
      kwargs_pos = nonstararg_count
    if code.has_varkeywords():
      kwargs_name = code.varnames[kwargs_pos]
    else:
      kwargs_name = None
    return cls(
        ctx=ctx,
        name=name,
        param_names=tuple(code.varnames[:code.argcount]),
        posonly_count=code.posonlyargcount,
        varargs_name=varargs_name,
        kwonly_params=tuple(code.varnames[code.argcount:nonstararg_count]),
        kwargs_name=kwargs_name,
        # TODO(b/241479600): Fill these in.
        defaults={},
        annotations={},
    )

  @classmethod
  def from_pytd(
      cls, ctx: base.ContextType, name: str, pytd_sig: pytd.Signature,
  ) -> 'Signature':
    """Builds a signature from a pytd signature."""
    param_names = []
    posonly_count = 0
    kwonly_params = []
    for p in pytd_sig.params:
      if p.kind == pytd.ParameterKind.KWONLY:
        kwonly_params.append(p.name)
        continue
      param_names.append(p.name)
      posonly_count += p.kind == pytd.ParameterKind.POSONLY

    defaults = {
        p.name: ctx.abstract_converter.pytd_type_to_value(p.type).instantiate()
        for p in pytd_sig.params if p.optional}

    pytd_annotations = [
        (p.name, p.type)
        for p in pytd_sig.params + (pytd_sig.starargs, pytd_sig.starstarargs)
        if p is not None]
    pytd_annotations.append(('return', pytd_sig.return_type))
    annotations = {name: ctx.abstract_converter.pytd_type_to_value(typ)
                   for name, typ in pytd_annotations}

    return cls(
        ctx=ctx,
        name=name,
        param_names=tuple(param_names),
        posonly_count=posonly_count,
        varargs_name=pytd_sig.starargs and pytd_sig.starargs.name,
        kwonly_params=tuple(kwonly_params),
        kwargs_name=pytd_sig.starstarargs and pytd_sig.starstarargs.name,
        defaults=defaults,
        annotations=annotations,
    )

  def __repr__(self):
    pp = self._ctx.errorlog.pretty_printer

    def fmt(param_name):
      if param_name in self.annotations:
        typ = pp.print_type_of_instance(self.annotations[param_name])
        s = f'{param_name}: {typ}'
      else:
        s = param_name
      if param_name in self.defaults:
        default = pp.show_constant(self.defaults[param_name])
        return f'{s} = {default}'
      else:
        return s

    params = [fmt(param_name) for param_name in self.param_names]
    if self.posonly_count:
      params.insert(self.posonly_count, '/')
    if self.varargs_name:
      params.append('*' + fmt(self.varargs_name))
    elif self.kwonly_params:
      params.append('*')
    params.extend(self.kwonly_params)
    if self.kwargs_name:
      params.append('**' + fmt(self.kwargs_name))
    if 'return' in self.annotations:
      ret = pp.print_type_of_instance(self.annotations['return'])
    else:
      ret = 'Any'
    return f'def {self.name}({", ".join(params)}) -> {ret}'

  def map_args(self, args: Args[_FrameT]) -> MappedArgs[_FrameT]:
    # TODO(b/241479600): Implement this properly, with error detection.
    argdict = dict(zip(self.param_names, args.posargs))
    argdict.update(args.kwargs)
    return MappedArgs(signature=self, argdict=argdict, frame=args.frame)

  def make_fake_args(self) -> MappedArgs[FrameType]:
    names = list(self.param_names + self.kwonly_params)
    if self.varargs_name:
      names.append(self.varargs_name)
    if self.kwargs_name:
      names.append(self.kwargs_name)
    argdict = {}
    for name in names:
      typ = self.annotations.get(name, self._ctx.consts.Any)
      argdict[name] = typ.instantiate().to_variable()
    return MappedArgs(signature=self, argdict=argdict)


class BaseFunction(base.BaseValue, abc.ABC, Generic[_HasReturnT]):
  """Base function representation."""

  @property
  @abc.abstractmethod
  def name(self) -> str:
    """The function name."""

  @property
  @abc.abstractmethod
  def signatures(self) -> Tuple[Signature, ...]:
    """The function's signatures."""

  @abc.abstractmethod
  def call(self, args: Args[FrameType]) -> _HasReturnT:
    """Calls this function with the given arguments.

    Args:
      args: The function arguments.

    Returns:
      An object with information about the result of the function call, with a
      get_return_value() method that retrieves the return value.
    """

  @abc.abstractmethod
  def analyze(self) -> Sequence[_HasReturnT]:
    """Calls every signature of this function with appropriate fake arguments.

    Returns:
      A sequence of objects with information about the result of calling the
      function with each of its signatures, with get_return_value() methods
      that retrieve the return values.
    """


class SimpleFunction(BaseFunction[_HasReturnT]):
  """Signature-based function implementation."""

  def __init__(
      self,
      ctx: base.ContextType,
      name: str,
      signatures: Tuple[Signature, ...],
      module: Optional[str] = None,
  ):
    super().__init__(ctx)
    self._name = name
    self._signatures = signatures
    self.module = module

  def __repr__(self):
    return f'SimpleFunction({self.full_name})'

  @property
  def name(self):
    return self._name

  @property
  def full_name(self):
    if self.module:
      return f'{self.module}.{self._name}'
    else:
      return self._name

  @property
  def signatures(self):
    return self._signatures

  @property
  def _attrs(self):
    return (self._name, self._signatures)

  def map_args(self, args: Args[_FrameT]) -> MappedArgs[_FrameT]:
    # TODO(b/241479600): Handle arg mapping failure.
    for sig in self.signatures:
      return sig.map_args(args)
    raise NotImplementedError('No signature matched passed args')

  @abc.abstractmethod
  def call_with_mapped_args(
      self, mapped_args: MappedArgs[FrameType]) -> _HasReturnT:
    """Calls this function with the given mapped arguments.

    Args:
      mapped_args: The function arguments mapped to parameter names.

    Returns:
      An object with information about the result of the function call, with a
      get_return_value() method that retrieves the return value.
    """

  def call(self, args: Args[FrameType]) -> _HasReturnT:
    return self.call_with_mapped_args(self.map_args(args))

  def analyze_signature(self, sig: Signature) -> _HasReturnT:
    assert sig in self.signatures
    return self.call_with_mapped_args(sig.make_fake_args())

  def analyze(self) -> Sequence[_HasReturnT]:
    return [self.analyze_signature(sig) for sig in self.signatures]


class InterpreterFunction(SimpleFunction[_FrameT]):
  """Function with a code object."""

  def __init__(
      self,
      ctx: base.ContextType,
      name: str,
      code: blocks.OrderedCode,
      enclosing_scope: Tuple[str, ...],
      parent_frame: _FrameT,
  ):
    super().__init__(
        ctx=ctx,
        name=name,
        signatures=(Signature.from_code(ctx, name, code),),
    )
    self.code = code
    self.enclosing_scope = enclosing_scope
    # A function saves a pointer to the frame it's defined in so that it has all
    # the context needed to call itself.
    self._parent_frame = parent_frame
    self._call_cache = {}

  def __repr__(self):
    return f'InterpreterFunction({self.name})'

  @property
  def _attrs(self):
    return (self.name, self.code)

  def call_with_mapped_args(self, mapped_args: MappedArgs[_FrameT]) -> _FrameT:
    log.info('Calling function:\n  Sig:  %s\n  Args: %s',
             mapped_args.signature, mapped_args.argdict)
    parent_frame = mapped_args.frame or self._parent_frame
    if parent_frame.final_locals is None:
      k = None
    else:
      # If the parent frame has finished running, then the context of this call
      # will not change, so we can cache the return value.
      k = (parent_frame.name, immutabledict.immutabledict(mapped_args.argdict))
      if k in self._call_cache:
        log.info('Reusing cached return value of function %s', self.name)
        return self._call_cache[k]
    frame = parent_frame.make_child_frame(self, mapped_args.argdict)
    frame.run()
    if k:
      self._call_cache[k] = frame
    return frame

  def bind_to(self, callself: base.BaseValue) -> 'BoundFunction[_FrameT]':
    return BoundFunction(self._ctx, callself, self)


class PytdFunction(SimpleFunction[SimpleReturn]):

  def call_with_mapped_args(
      self, mapped_args: MappedArgs[FrameType]) -> SimpleReturn:
    ret = mapped_args.signature.annotations['return'].instantiate()
    return SimpleReturn(ret)


class BoundFunction(BaseFunction[_HasReturnT]):
  """Function bound to a self or cls object."""

  def __init__(
      self, ctx: base.ContextType, callself: base.BaseValue,
      underlying: SimpleFunction[_HasReturnT]):
    super().__init__(ctx)
    self.callself = callself
    self.underlying = underlying

  def __repr__(self):
    return f'BoundFunction({self.callself!r}, {self.underlying!r})'

  @property
  def _attrs(self):
    return (self.callself, self.underlying)

  @property
  def name(self):
    return self.underlying.name

  @property
  def signatures(self):
    return self.underlying.signatures

  def call(self, args: Args[FrameType]) -> _HasReturnT:
    new_posargs = (self.callself.to_variable(),) + args.posargs
    args = dataclasses.replace(args, posargs=new_posargs)
    return self.underlying.call(args)

  def analyze_signature(self, sig: Signature) -> _HasReturnT:
    assert sig in self.underlying.signatures
    mapped_args = sig.make_fake_args()
    argdict = dict(mapped_args.argdict)
    argdict[mapped_args.signature.param_names[0]] = self.callself.to_variable()
    bound_args = dataclasses.replace(mapped_args, argdict=argdict)
    return self.underlying.call_with_mapped_args(bound_args)

  def analyze(self) -> Sequence[_HasReturnT]:
    return [self.analyze_signature(sig) for sig in self.underlying.signatures]
