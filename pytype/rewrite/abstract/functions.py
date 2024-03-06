"""Abstract representations of functions."""

from typing import Dict, Mapping, Optional, Sequence, Tuple

import immutabledict
from pytype.blocks import blocks
from pytype.rewrite.abstract import base

_EMPTY_MAP = immutabledict.immutabledict()


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

  def map_args(
      self, args: Sequence[base.AbstractVariableType],
  ) -> Dict[str, base.AbstractVariableType]:
    # TODO(b/241479600): Implement this properly, with error detection.
    return dict(zip(self.param_names, args))

  def make_fake_args(self) -> Dict[str, base.AbstractVariableType]:
    names = list(self.param_names + self.kwonly_params)
    if self.varargs_name:
      names.append(self.varargs_name)
    if self.kwargs_name:
      names.append(self.kwargs_name)
    return {name: base.ANY.to_variable() for name in names}


class BaseFunction(base.BaseValue):
  """Base function representation."""

  def __init__(
      self,
      name: str,
      signatures: Tuple[Signature, ...],
  ):
    self.name = name
    self.signatures = signatures

  def map_args(
      self, args: Sequence[base.AbstractVariableType],
  ) -> Dict[str, base.AbstractVariableType]:
    # TODO(b/241479600): Handle arg mapping failure.
    for sig in self.signatures:
      return sig.map_args(args)
    raise NotImplementedError('No signature matched passed args')


class InterpreterFunction(BaseFunction):
  """Function with a code object."""

  def __init__(
      self,
      name: str,
      code: blocks.OrderedCode,
      enclosing_scope: Tuple[str, ...],
  ):
    super().__init__(
        name=name,
        signatures=(Signature.from_code(name, code),),
    )
    self.code = code
    self.enclosing_scope = enclosing_scope

  def __repr__(self):
    return f'InterpreterFunction({self.name})'
