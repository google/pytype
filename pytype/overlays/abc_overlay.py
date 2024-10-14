"""Implementation of special members of Python's abc library."""

from typing import Any, TypeVar
from pytype.abstract import abstract
from pytype.overlays import overlay
from pytype.overlays import special_builtins

_T0 = TypeVar("_T0")
_TAbstractClassMethod = TypeVar(
    "_TAbstractClassMethod", bound="AbstractClassMethod"
)
_TAbstractMethod = TypeVar("_TAbstractMethod", bound="AbstractMethod")
_TAbstractProperty = TypeVar("_TAbstractProperty", bound="AbstractProperty")
_TAbstractStaticMethod = TypeVar(
    "_TAbstractStaticMethod", bound="AbstractStaticMethod"
)


def _set_abstract(args, argname):
  if args.posargs:
    func_var = args.posargs[0]
  else:
    func_var = args.namedargs[argname]
  for func in func_var.data:
    if isinstance(func, abstract.FUNCTION_TYPES):
      func.is_abstract = True
  return func_var


class ABCOverlay(overlay.Overlay):
  """A custom overlay for the 'abc' module."""

  def __init__(self, ctx) -> None:
    member_map = {
        "abstractclassmethod": AbstractClassMethod.make,
        "abstractmethod": AbstractMethod.make,
        "abstractproperty": AbstractProperty.make,
        "abstractstaticmethod": AbstractStaticMethod.make,
        "ABCMeta": overlay.add_name(
            "ABCMeta", special_builtins.Type.make_alias
        ),
    }
    ast = ctx.loader.import_name("abc")
    super().__init__(ctx, "abc", member_map, ast)


class AbstractClassMethod(special_builtins.ClassMethod):
  """Implements abc.abstractclassmethod."""

  @classmethod
  def make(
      cls: type[_TAbstractClassMethod], ctx, module
  ) -> _TAbstractClassMethod:
    return super().make_alias("abstractclassmethod", ctx, module)

  def call(self, node: _T0, func, args, alias_map=None) -> tuple[_T0, Any]:
    _ = _set_abstract(args, "callable")
    return super().call(node, func, args, alias_map)


class AbstractMethod(abstract.PyTDFunction):
  """Implements the @abc.abstractmethod decorator."""

  @classmethod
  def make(cls: type[_TAbstractMethod], ctx, module) -> _TAbstractMethod:
    return super().make("abstractmethod", ctx, module)

  def call(self, node: _T0, func, args, alias_map=None) -> tuple[_T0, Any]:
    """Marks that the given function is abstract."""
    del func, alias_map  # unused
    self.match_args(node, args)
    return node, _set_abstract(args, "funcobj")


class AbstractProperty(special_builtins.Property):
  """Implements the @abc.abstractproperty decorator."""

  @classmethod
  def make(cls: type[_TAbstractProperty], ctx, module) -> _TAbstractProperty:
    return super().make_alias("abstractproperty", ctx, module)

  def call(self, node: _T0, func, args, alias_map=None) -> tuple[_T0, Any]:
    property_args = self._get_args(args)
    for v in property_args.values():
      for b in v.bindings:
        f = b.data
        # If this check fails, we will raise a 'property object is not callable'
        # error down the line.
        # TODO(mdemello): This is in line with what python does, but we could
        # have a more precise error message that insisted f was a class method.
        if isinstance(f, abstract.Function):
          f.is_abstract = True
    return node, special_builtins.PropertyInstance(
        self.ctx, self.name, self, **property_args
    ).to_variable(node)


class AbstractStaticMethod(special_builtins.StaticMethod):
  """Implements abc.abstractstaticmethod."""

  @classmethod
  def make(
      cls: type[_TAbstractStaticMethod], ctx, module
  ) -> _TAbstractStaticMethod:
    return super().make_alias("abstractstaticmethod", ctx, module)

  def call(self, node: _T0, func, args, alias_map=None) -> tuple[_T0, Any]:
    _ = _set_abstract(args, "callable")
    return super().call(node, func, args, alias_map)
