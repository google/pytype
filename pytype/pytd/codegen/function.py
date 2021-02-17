"""Function definitions in pyi files."""

import collections

from typing import Any, Dict, List, Optional, Tuple

import dataclasses

from pytype.pytd import pytd


class OverloadedDecoratorError(Exception):
  """Inconsistent decorators on an overloaded function."""

  def __init__(self, name, typ):
    msg = "Overloaded signatures for %s disagree on %sdecorators" % (
        name, (typ + " " if typ else ""))
    super().__init__(msg)


# Strategies for combining a new decorator with an existing one
_MERGE, _REPLACE, _DISCARD = 1, 2, 3


@dataclasses.dataclass
class Param:
  """Internal representation of function parameters."""

  name: str
  type: Optional[pytd.Type] = None
  default: Any = None
  kwonly: bool = False

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
  def make(
      cls,
      name: str,
      args: List[Tuple[str, pytd.Type]],
      return_type: pytd.Type
  ) -> "NameAndSig":
    """Make a new NameAndSig from an argument list."""
    params = tuple(Param(n, t).to_pytd() for (n, t) in args)
    sig = pytd.Signature(params=params, return_type=return_type,
                         starargs=None, starstarargs=None,
                         exceptions=(), template=())
    return cls(name, sig)


def pytd_return_type(
    name: str,
    return_type: Optional[pytd.Type],
    is_async: bool
) -> pytd.Type:
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


def pytd_star_param(name: str, annotation: pytd.Type) -> pytd.Parameter:
  """Return a pytd.Parameter for a *args argument."""
  if annotation is None:
    param_type = pytd.NamedType("tuple")
  else:
    param_type = pytd.GenericType(
        pytd.NamedType("tuple"), (annotation,))
  return pytd.Parameter(name, param_type, False, True, None)


def pytd_starstar_param(
    name: str, annotation: pytd.Type
) -> pytd.Parameter:
  """Return a pytd.Parameter for a **kwargs argument."""
  if annotation is None:
    param_type = pytd.NamedType("dict")
  else:
    param_type = pytd.GenericType(
        pytd.NamedType("dict"), (pytd.NamedType("str"), annotation))
  return pytd.Parameter(name, param_type, False, True, None)


def merge_method_signatures(
    signatures: List[NameAndSig],
    check_unhandled_decorator: bool = True
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
    elif decorator and _is_property(name, decorator, sigs[0]):
      kind = pytd.PROPERTY
      # If we have only setters and/or deleters, replace them with a single
      # method foo(...) -> Any, so that we infer a constant `foo: Any` even if
      # the original method signatures are all `foo(...) -> None`. (If we have a
      # getter we use its return type, but in the absence of a getter we want to
      # fall back on Any since we cannot say anything about what the setter sets
      # the type of foo to.)
      if decorator.endswith(".setter") or decorator.endswith(".deleter"):
        sigs = [sigs[0].Replace(return_type=pytd.AnythingType())]
    elif decorator and check_unhandled_decorator:
      raise ValueError("Unhandled decorator: %s" % decorator)
    else:
      # Other decorators do not affect the kind
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
    False: If we have a non-property decorator.
  """
  sigs = _property_decorators(name)
  return (decorator in sigs and
          sigs[decorator].arity == len(signature.params))
