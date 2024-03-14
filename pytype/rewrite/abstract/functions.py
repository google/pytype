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
from typing import Dict, Generic, Mapping, Optional, Protocol, Sequence, Tuple, TypeVar

import immutabledict
from pytype.blocks import blocks
from pytype.rewrite.abstract import base

_EMPTY_MAP = immutabledict.immutabledict()
_ArgDict = Dict[str, base.AbstractVariableType]


@dataclasses.dataclass
class Args:
  """Arguments to one function call."""
  posargs: Sequence[base.AbstractVariableType] = ()


@dataclasses.dataclass
class MappedArgs:
  """Function call args that have been mapped to a signature and param names."""
  signature: 'Signature'
  argdict: _ArgDict


class _HasReturn(Protocol):

  def get_return_value(self) -> base.BaseValue: ...


_HasReturnT = TypeVar('_HasReturnT', bound=_HasReturn)


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
  def from_code(cls, name: str, code: blocks.OrderedCode) -> 'Signature':
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

  def __repr__(self):
    params = list(self.param_names)
    if self.posonly_count:
      params.insert(self.posonly_count, '/')
    if self.varargs_name:
      params.append('*' + self.varargs_name)
    elif self.kwonly_params:
      params.append('*')
    params.extend(self.kwonly_params)
    if self.kwargs_name:
      params.append('**' + self.kwargs_name)
    return f'def {self.name}({", ".join(params)})'

  def map_args(self, args: Args) -> _ArgDict:
    # TODO(b/241479600): Implement this properly, with error detection.
    return dict(zip(self.param_names, args.posargs))

  def make_fake_args(self) -> _ArgDict:
    names = list(self.param_names + self.kwonly_params)
    if self.varargs_name:
      names.append(self.varargs_name)
    if self.kwargs_name:
      names.append(self.kwargs_name)
    return {name: base.ANY.to_variable() for name in names}


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
  def call(self, args: Args) -> _HasReturnT:
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

  def __init__(self, name: str, signatures: Tuple[Signature, ...]):
    self._name = name
    self._signatures = signatures

  @property
  def name(self):
    return self._name

  @property
  def signatures(self):
    return self._signatures

  def map_args(self, args: Args) -> MappedArgs:
    # TODO(b/241479600): Handle arg mapping failure.
    for sig in self.signatures:
      return MappedArgs(sig, sig.map_args(args))
    raise NotImplementedError('No signature matched passed args')

  @abc.abstractmethod
  def call_with_mapped_args(self, mapped_args: MappedArgs) -> _HasReturnT:
    """Calls this function with the given mapped arguments.

    Args:
      mapped_args: The function arguments mapped to parameter names.

    Returns:
      An object with information about the result of the function call, with a
      get_return_value() method that retrieves the return value.
    """

  def call(self, args: Args) -> _HasReturnT:
    return self.call_with_mapped_args(self.map_args(args))

  def analyze(self) -> Sequence[_HasReturnT]:
    return [self.call_with_mapped_args(MappedArgs(sig, sig.make_fake_args()))
            for sig in self.signatures]


class _Frame(Protocol):
  """Protocol for a VM frame."""

  final_locals: Mapping[str, base.BaseValue]

  def make_child_frame(
      self,
      func: 'InterpreterFunction',
      initial_locals: Mapping[str, base.AbstractVariableType],
  ) -> '_Frame': ...

  def run(self) -> None: ...

  def get_return_value(self) -> base.BaseValue: ...


_FrameT = TypeVar('_FrameT', bound=_Frame)


class InterpreterFunction(SimpleFunction[_FrameT]):
  """Function with a code object."""

  def __init__(
      self,
      name: str,
      code: blocks.OrderedCode,
      enclosing_scope: Tuple[str, ...],
      parent_frame: _FrameT,
  ):
    super().__init__(
        name=name,
        signatures=(Signature.from_code(name, code),),
    )
    self.code = code
    self.enclosing_scope = enclosing_scope
    # A function saves a pointer to the frame it's defined in so that it has all
    # the context needed to call itself.
    self._parent_frame = parent_frame

  def __repr__(self):
    return f'InterpreterFunction({self.name})'

  def call_with_mapped_args(self, mapped_args: MappedArgs) -> _FrameT:
    frame = self._parent_frame.make_child_frame(self, mapped_args.argdict)
    frame.run()
    return frame

  def bind_to(self, callself: base.BaseValue) -> 'BoundFunction[_FrameT]':
    return BoundFunction(callself, self)


class BoundFunction(BaseFunction[_HasReturnT]):
  """Function bound to a self or cls object."""

  def __init__(
      self, callself: base.BaseValue, underlying: SimpleFunction[_HasReturnT]):
    self.callself = callself
    self.underlying = underlying

  def __repr__(self):
    return f'BoundFunction({self.callself!r}, {self.underlying!r})'

  @property
  def name(self):
    return self.underlying.name

  @property
  def signatures(self):
    raise NotImplementedError('BoundFunction.signatures')

  def _bind_mapped_args(self, mapped_args: MappedArgs) -> MappedArgs:
    argdict = dict(mapped_args.argdict)
    argdict[mapped_args.signature.param_names[0]] = self.callself.to_variable()
    return MappedArgs(mapped_args.signature, argdict)

  def call(self, args: Args) -> _HasReturnT:
    mapped_args = self._bind_mapped_args(self.underlying.map_args(args))
    return self.underlying.call_with_mapped_args(mapped_args)

  def analyze(self) -> Sequence[_HasReturnT]:
    return [
        self.underlying.call_with_mapped_args(
            self._bind_mapped_args(MappedArgs(sig, sig.make_fake_args())))
        for sig in self.underlying.signatures
    ]
