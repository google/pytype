"""Function definitions in pyi files."""

import dataclasses

from typing import Any, Dict, Iterable, List, Optional, Tuple

from pytype.pytd import pytd


class OverloadedDecoratorError(Exception):
  """Inconsistent decorators on an overloaded function."""

  def __init__(self, name, typ):
    msg = "Overloaded signatures for {} disagree on {}decorators".format(
        name, (typ + " " if typ else ""))
    super().__init__(msg)


class PropertyDecoratorError(Exception):
  """Inconsistent property decorators on an overloaded function."""

  def __init__(self, name):
    msg = (f"Invalid property decorators for method `{name}` "
           "(need at most one each of @property, "
           f"@{name}.setter and @{name}.deleter)")
    super().__init__(msg)


@dataclasses.dataclass
class Param:
  """Internal representation of function parameters."""

  name: str
  type: Optional[pytd.Type] = None
  default: Any = None
  kind: pytd.ParameterKind = pytd.ParameterKind.REGULAR

  def to_pytd(self) -> pytd.Parameter:
    """Return a pytd.Parameter object for a normal argument."""
    if self.default is not None:
      default_type = self.default
      if self.type is None and default_type != pytd.NamedType("NoneType"):
        self.type = default_type
    if self.type is None:
      self.type = pytd.AnythingType()

    optional = self.default is not None
    return pytd.Parameter(self.name, self.type, self.kind, optional, None)


@dataclasses.dataclass(frozen=True)
class NameAndSig:
  """Internal representation of function signatures."""

  name: str
  signature: pytd.Signature
  decorator: Optional[str] = None
  is_abstract: bool = False
  is_coroutine: bool = False
  is_final: bool = False
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
  return pytd.Parameter(
      "args", pytd.NamedType("tuple"), pytd.ParameterKind.REGULAR, True, None)


def pytd_default_starstar_param() -> pytd.Parameter:
  return pytd.Parameter(
      "kwargs", pytd.NamedType("dict"), pytd.ParameterKind.REGULAR, True, None)


def pytd_star_param(name: str, annotation: pytd.Type) -> pytd.Parameter:
  """Return a pytd.Parameter for a *args argument."""
  if annotation is None:
    param_type = pytd.NamedType("tuple")
  else:
    param_type = pytd.GenericType(
        pytd.NamedType("tuple"), (annotation,))
  return pytd.Parameter(
      name, param_type, pytd.ParameterKind.REGULAR, True, None)


def pytd_starstar_param(
    name: str, annotation: pytd.Type
) -> pytd.Parameter:
  """Return a pytd.Parameter for a **kwargs argument."""
  if annotation is None:
    param_type = pytd.NamedType("dict")
  else:
    param_type = pytd.GenericType(
        pytd.NamedType("dict"), (pytd.NamedType("str"), annotation))
  return pytd.Parameter(
      name, param_type, pytd.ParameterKind.REGULAR, True, None)


def _make_param(attr: pytd.Constant) -> pytd.Parameter:
  return Param(name=attr.name, type=attr.type, default=attr.value).to_pytd()


def generate_init(fields: Iterable[pytd.Constant]) -> pytd.Function:
  """Build an __init__ method from pytd class constants."""
  self_arg = Param("self").to_pytd()
  params = (self_arg,) + tuple(_make_param(c) for c in fields)
  # We call this at 'runtime' rather than from the parser, so we need to use the
  # resolved type of None, rather than NamedType("NoneType")
  ret = pytd.ClassType("builtins.NoneType")
  sig = pytd.Signature(params=params, return_type=ret,
                       starargs=None, starstarargs=None,
                       exceptions=(), template=())
  return pytd.Function("__init__", (sig,), kind=pytd.MethodKind.METHOD)


# -------------------------------------------
# Method signature merging


@dataclasses.dataclass
class _Property:
  type: str
  arity: int


def _property_decorators(name: str) -> Dict[str, _Property]:
  """Generates the property decorators for a method name."""
  return {
      "property": _Property("getter", 1),
      (name + ".setter"): _Property("setter", 2),
      (name + ".deleter"): _Property("deleter", 1)
  }


@dataclasses.dataclass
class _Properties:
  """Function property decorators."""

  getter: Optional[pytd.Signature] = None
  setter: Optional[pytd.Signature] = None
  deleter: Optional[pytd.Signature] = None

  def set(self, prop, sig, name):
    assert hasattr(self, prop), prop
    if getattr(self, prop):
      raise PropertyDecoratorError(name)
    setattr(self, prop, sig)


@dataclasses.dataclass
class _DecoratedFunction:
  """A mutable builder for pytd.Function values."""

  name: str
  sigs: List[pytd.Signature]
  is_abstract: bool = False
  is_coroutine: bool = False
  is_final: bool = False
  decorator: Optional[str] = None
  properties: Optional[_Properties] = dataclasses.field(init=False)
  prop_names: Dict[str, _Property] = dataclasses.field(init=False)

  @classmethod
  def make(cls, fn: NameAndSig):
    return cls(
        name=fn.name,
        sigs=[fn.signature],
        is_abstract=fn.is_abstract,
        is_coroutine=fn.is_coroutine,
        is_final=fn.is_final,
        decorator=fn.decorator)

  def __post_init__(self):
    self.prop_names = _property_decorators(self.name)
    if self.decorator in self.prop_names:
      self.properties = _Properties()
      self.add_property(self.decorator, self.sigs[0])
    else:
      self.properties = None

  def add_property(self, decorator, sig):
    prop = self.prop_names[decorator]
    if prop.arity == len(sig.params):
      self.properties.set(prop.type, sig, self.name)
    else:
      raise TypeError("Property decorator @%s needs %d param(s), got %d" %
                      (decorator, prop.arity, len(sig.params)))

  def add_overload(self, fn: NameAndSig):
    """Add an overloaded signature to a function."""
    # Check for decorator consistency. Note that we currently limit pyi files to
    # one decorator per function, other than @abstractmethod and @coroutine
    # which are special-cased.
    if (self.properties and fn.decorator in self.prop_names):
      # For properties, we can have at most one of setter, getter and deleter,
      # and no other overloads
      self.add_property(fn.decorator, fn.signature)
      # For properties, it's fine if, e.g., the getter is abstract but the
      # setter is not, so we skip the @abstractmethod and  @coroutine
      # consistency checks.
      return
    elif self.decorator == fn.decorator:
      # For other decorators, we can have multiple overloads but they need to
      # all have the same decorator
      self.sigs.append(fn.signature)
    else:
      raise OverloadedDecoratorError(self.name, None)
    # @abstractmethod and @coroutine can be combined with other decorators, but
    # they need to be consistent for all overloads
    if self.is_abstract != fn.is_abstract:
      raise OverloadedDecoratorError(self.name, "abstractmethod")
    if self.is_coroutine != fn.is_coroutine:
      raise OverloadedDecoratorError(self.name, "coroutine")


def merge_method_signatures(
    name_and_sigs: List[NameAndSig],
    check_unhandled_decorator: bool = False
) -> List[pytd.Function]:
  """Group the signatures by name, turning each group into a function."""
  functions = {}
  for fn in name_and_sigs:
    if fn.name not in functions:
      functions[fn.name] = _DecoratedFunction.make(fn)
    else:
      functions[fn.name].add_overload(fn)
  methods = []
  for name, fn in functions.items():
    if name == "__new__" or fn.decorator == "staticmethod":
      kind = pytd.MethodKind.STATICMETHOD
    elif name == "__init_subclass__" or fn.decorator == "classmethod":
      kind = pytd.MethodKind.CLASSMETHOD
    elif fn.properties:
      kind = pytd.MethodKind.PROPERTY
      # If we have only setters and/or deleters, replace them with a single
      # method foo(...) -> Any, so that we infer a constant `foo: Any` even if
      # the original method signatures are all `foo(...) -> None`. (If we have a
      # getter we use its return type, but in the absence of a getter we want to
      # fall back on Any since we cannot say anything about what the setter sets
      # the type of foo to.)
      if fn.properties.getter:
        fn.sigs = [fn.properties.getter]
      else:
        sig = fn.properties.setter or fn.properties.deleter
        fn.sigs = [sig.Replace(return_type=pytd.AnythingType())]
    elif fn.decorator and check_unhandled_decorator:
      raise ValueError(f"Unhandled decorator: {fn.decorator}")
    else:
      # Other decorators do not affect the kind
      kind = pytd.MethodKind.METHOD
    flags = pytd.MethodFlag.NONE
    if fn.is_abstract:
      flags |= pytd.MethodFlag.ABSTRACT
    if fn.is_coroutine:
      flags |= pytd.MethodFlag.COROUTINE
    if fn.is_final:
      flags |= pytd.MethodFlag.FINAL
    methods.append(pytd.Function(name, tuple(fn.sigs), kind, flags))
  return methods
