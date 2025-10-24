"""Overlay for functools."""

from __future__ import annotations

from collections.abc import Sequence
import threading
from typing import Any, TYPE_CHECKING

from pytype.abstract import abstract
from pytype.abstract import function
from pytype.abstract import mixin
from pytype.overlays import overlay
from pytype.overlays import special_builtins
from pytype.typegraph import cfg
from typing_extensions import Self

if TYPE_CHECKING:
  from pytype import context  # pylint: disable=g-import-not-at-top


_MODULE_NAME = "functools"


class FunctoolsOverlay(overlay.Overlay):
  """An overlay for the functools std lib module."""

  def __init__(self, ctx):
    member_map = {
        "cached_property": overlay.add_name(
            "cached_property", special_builtins.Property.make_alias
        ),
    }
    if ctx.options.use_functools_partial_overlay:
      member_map["partial"] = Partial
    ast = ctx.loader.import_name(_MODULE_NAME)
    super().__init__(ctx, _MODULE_NAME, member_map, ast)


class Partial(abstract.PyTDClass, mixin.HasSlots):
  """Implementation of functools.partial."""

  def __init__(self, ctx: "context.Context", module: str):
    pytd_cls = ctx.loader.lookup_pytd(module, "partial")
    super().__init__("partial", pytd_cls, ctx)
    mixin.HasSlots.init_mixin(self)

    self._pytd_new = self.pytd_cls.Lookup("__new__")

  def new_slot(
      self, node, cls, *args, **kwargs
  ) -> tuple[cfg.CFGNode, cfg.Variable]:
    # Make sure the call is well typed before binding the partial
    new = self.ctx.convert.convert_pytd_function(self._pytd_new)
    _, specialized_obj = function.call_function(
        self.ctx,
        node,
        new.to_variable(node),
        function.Args(
            (cls, *args),
            kwargs,
            call_context.starargs,
            call_context.starstarargs,
        ),
        fallback_to_unsolvable=False,
    )
    [specialized_obj] = specialized_obj.data
    type_arg = specialized_obj.get_formal_type_parameter("_T")
    [cls] = cls.data
    cls = abstract.ParameterizedClass(cls, {"_T": type_arg}, self.ctx)
    obj = bind_partial(node, cls, args, kwargs, self.ctx)
    return node, obj.to_variable(node)

  def get_own_new(self, node, value) -> tuple[cfg.CFGNode, cfg.Variable]:
    new = NativeFunction("__new__", self.new_slot, self.ctx)
    return node, new.to_variable(node)


def bind_partial(node, cls, args, kwargs, ctx) -> BoundPartial:
  del node  # Unused.
  obj = BoundPartial(ctx, cls)
  obj.underlying = args[0]
  obj.args = args[1:]
  obj.kwargs = kwargs
  obj.starargs = call_context.starargs
  obj.starstarargs = call_context.starstarargs
  return obj


class CallContext(threading.local):
  """A thread-local context for ``NativeFunction.call``."""

  starargs: cfg.Variable | None = None
  starstarargs: cfg.Variable | None = None

  def forward(
      self, starargs: cfg.Variable | None, starstarargs: cfg.Variable | None
  ) -> Self:
    self.starargs = starargs
    self.starstarargs = starstarargs
    return self

  def __enter__(self) -> Self:
    return self

  def __exit__(self, *exc_info) -> None:
    self.starargs = None
    self.starstarargs = None


call_context = CallContext()


class NativeFunction(abstract.NativeFunction):
  """A native function that forwards *args and **kwargs to the underlying function."""

  def call(
      self,
      node: cfg.CFGNode,
      func: cfg.Binding,
      args: function.Args,
      alias_map: Any | None = None,
  ) -> tuple[cfg.CFGNode, cfg.Variable]:
    # ``NativeFunction.call`` does not forward *args and **kwargs to the
    # underlying function, so we do it here to avoid changing core pytype APIs.
    #
    # The simplification below ensures that the *args/**kwargs cannot in fact
    # be split into individual arguments. This logic follow the implementation
    # in the base class.
    sig = None
    if isinstance(
        self.func.__self__,  # pytype: disable=attribute-error
        abstract.CallableClass,
    ):
      sig = function.Signature.from_callable(
          self.func.__self__  # pytype: disable=attribute-error
      )
    args = args.simplify(node, self.ctx, match_signature=sig)
    del sig

    starargs = args.starargs
    starstarargs = args.starstarargs
    if starargs is not None:
      starargs = starargs.AssignToNewVariable(node)
    if starstarargs is not None:
      starstarargs = starstarargs.AssignToNewVariable(node)
    with call_context.forward(starargs, starstarargs):
      return super().call(node, func, args, alias_map)


class BoundPartial(abstract.Instance, mixin.HasSlots):
  """An instance of functools.partial."""

  underlying: cfg.Variable
  args: tuple[cfg.Variable, ...]
  kwargs: dict[str, cfg.Variable]
  starargs: cfg.Variable | None
  starstarargs: cfg.Variable | None

  def __init__(self, ctx, cls, container=None):
    super().__init__(cls, ctx, container)
    mixin.HasSlots.init_mixin(self)
    self.set_slot(
        "__call__", NativeFunction("__call__", self.call_slot, self.ctx)
    )

  def get_signatures(self) -> Sequence[function.Signature]:
    sigs = []
    args = function.Args(
        self.args, self.kwargs, self.starargs, self.starstarargs
    )
    for data in self.underlying.data:
      for sig in function.get_signatures(data):
        # Use the partial arguments as defaults in the signature, making them
        # optional but overwritable.
        defaults = sig.defaults.copy()
        kwonly_params = [*sig.kwonly_params]
        bound_param_names = set()
        pos_only_count = sig.posonly_count
        for name, value, _ in sig.iter_args(args):
          if value is None:
            continue
          if name == sig.varargs_name or name == sig.kwargs_name:
            continue  # Nothing to do for packed parameters.
          if (
              name not in sig.param_names or
              sig.param_names.index(name) < sig.posonly_count
          ):
            # The parameter is positional-only, meaning that it cannot be
            # overwritten via a keyword argument. Remove it.
            bound_param_names.add(name)
            sig.posonly_count -= 1
            continue
          if name not in sig.kwonly_params:
            # The parameter can be overwritten via a keyword argument. Note
            # that we still have to remove it from ``param_names`` to make
            # sure it cannot be bound by position.
            bound_param_names.add(name)
            kwonly_params.append(name)

          defaults[name] = value

        sigs.append(
            sig._replace(
                param_names=tuple(
                    n for n in sig.param_names if n not in bound_param_names
                ),
                posonly_count=pos_only_count,
                kwonly_params=tuple(kwonly_params),
                defaults=defaults,
            )
        )
    return sigs

  def call_slot(self, node: cfg.CFGNode, *args, **kwargs):
    if self.starargs and call_context.starargs:
      combined_starargs = self.ctx.convert.build_tuple(
          node,
          (
              abstract.Splat(self.ctx, self.starargs).to_variable(node),
              abstract.Splat(self.ctx, call_context.starargs).to_variable(node),
          ),
      )
    else:
      combined_starargs = call_context.starargs or self.starargs

    if self.starstarargs and call_context.starstarargs:
      d = abstract.Dict(self.ctx)
      d.update(node, self.starstarargs.data[0])  # pytype: disable=attribute-error
      d.update(node, call_context.starstarargs.data[0])
      combined_starstarargs = d.to_variable(node)
    else:
      combined_starstarargs = call_context.starstarargs or self.starstarargs

    return function.call_function(
        self.ctx,
        node,
        self.underlying,
        function.Args(
            (*self.args, *args),
            {**self.kwargs, **kwargs},
            combined_starargs,
            combined_starstarargs,
        ),
        fallback_to_unsolvable=False,
    )
