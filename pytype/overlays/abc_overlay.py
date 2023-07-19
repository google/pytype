"""Implementation of special members of Python's abc library."""

from pytype.abstract import abstract
from pytype.overlays import overlay
from pytype.overlays import special_builtins


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

  def __init__(self, ctx):
    member_map = {
        "abstractclassmethod": AbstractClassMethod,
        "abstractmethod": AbstractMethod.make,
        "abstractproperty": AbstractProperty,
        "abstractstaticmethod": AbstractStaticMethod,
        "ABCMeta": ABCMeta,
    }
    ast = ctx.loader.import_name("abc")
    super().__init__(ctx, "abc", member_map, ast)


class AbstractClassMethod(special_builtins.ClassMethodTemplate):
  """Implements abc.abstractclassmethod."""

  def __init__(self, ctx):
    super().__init__(ctx, "abstractclassmethod", "abc")

  def call(self, node, func, args, alias_map=None):
    _ = _set_abstract(args, "callable")
    return super().call(node, func, args, alias_map)


class AbstractMethod(abstract.PyTDFunction):
  """Implements the @abc.abstractmethod decorator."""

  @classmethod
  def make(cls, ctx):
    return super().make("abstractmethod", ctx, "abc")

  def call(self, node, func, args, alias_map=None):
    """Marks that the given function is abstract."""
    del func, alias_map  # unused
    self.match_args(node, args)
    return node, _set_abstract(args, "funcobj")


class AbstractProperty(special_builtins.PropertyTemplate):
  """Implements the @abc.abstractproperty decorator."""

  def __init__(self, ctx):
    super().__init__(ctx, "abstractproperty", "abc")

  def call(self, node, func, args, alias_map=None):
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


class AbstractStaticMethod(special_builtins.StaticMethodTemplate):
  """Implements abc.abstractstaticmethod."""

  def __init__(self, ctx):
    super().__init__(ctx, "abstractstaticmethod", "abc")

  def call(self, node, func, args, alias_map=None):
    _ = _set_abstract(args, "callable")
    return super().call(node, func, args, alias_map)


class ABCMeta(special_builtins.TypeTemplate):

  def __init__(self, ctx):
    super().__init__(ctx, "ABCMeta", "abc")
