"""Implementation of special members of Python 2's abc library."""

from pytype import special_builtins
from pytype.abstract import abstract
from pytype.overlays import overlay


class ABCOverlay(overlay.Overlay):
  """A custom overlay for the 'abc' module."""

  def __init__(self, ctx):
    member_map = {
        "abstractmethod": AbstractMethod.make,
        "abstractproperty": AbstractProperty
    }
    ast = ctx.loader.import_name("abc")
    super().__init__(ctx, "abc", member_map, ast)


class AbstractMethod(abstract.PyTDFunction):
  """Implements the @abc.abstractmethod decorator."""

  @classmethod
  def make(cls, ctx):
    return super().make("abstractmethod", ctx, "abc")

  def call(self, node, unused_func, args):
    """Marks that the given function is abstract."""
    self.match_args(node, args)

    # Since we have only 1 argument, it's easy enough to extract.
    if args.posargs:
      func_var = args.posargs[0]
    else:
      func_var = args.namedargs["function"]

    for func in func_var.data:
      if isinstance(func, abstract.FUNCTION_TYPES):
        func.is_abstract = True

    return node, func_var


class AbstractProperty(special_builtins.PropertyTemplate):
  """Implements the @abc.abstractproperty decorator."""

  def __init__(self, ctx):
    super().__init__(ctx, "abstractproperty", "abc")

  def call(self, node, funcv, args):
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
        self.ctx, self.name, self, **property_args).to_variable(node)
