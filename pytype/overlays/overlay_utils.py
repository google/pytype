"""Utilities for writing overlays."""

from pytype.abstract import abstract
from pytype.abstract import function
from pytype.pytd import pytd
from pytype.typegraph import cfg


# Various types accepted by the annotations dictionary.
# Runtime type checking of annotations, since if we do have an unexpected type
# being stored in annotations, we should catch that as soon as possible, and add
# it to the list if valid.
PARAM_TYPES = (
    cfg.Variable,
    abstract.Class,
    abstract.TypeParameter,
    abstract.Union,
    abstract.Unsolvable,
)


class Param:
  """Internal representation of method parameters."""

  def __init__(self, name, typ=None, default=None):
    if typ:
      assert isinstance(typ, PARAM_TYPES), (typ, type(typ))
    self.name = name
    self.typ = typ
    self.default = default

  def unsolvable(self, ctx, node):
    """Replace None values for typ and default with unsolvable."""
    self.typ = self.typ or ctx.convert.unsolvable
    self.default = self.default or ctx.new_unsolvable(node)
    return self

  def __repr__(self):
    return f"Param({self.name}, {self.typ!r}, {self.default!r})"


def make_method(ctx,
                node,
                name,
                params=None,
                posonly_count=0,
                kwonly_params=None,
                return_type=None,
                self_param=None,
                varargs=None,
                kwargs=None,
                kind=pytd.MethodKind.METHOD):
  """Make a method from params.

  Args:
    ctx: The context
    node: Node to create the method variable at
    name: The method name
    params: Positional params [type: [Param]]
    posonly_count: Number of positional-only parameters
    kwonly_params: Keyword only params [type: [Param]]
    return_type: Return type [type: PARAM_TYPES]
    self_param: Self param [type: Param, defaults to self: Any]
    varargs: Varargs param [type: Param, allows *args to be named and typed]
    kwargs: Kwargs param [type: Param, allows **kwargs to be named and typed]
    kind: The method kind

  Returns:
    A new method wrapped in a variable.
  """

  def _process_annotation(param):
    """Process a single param into annotations."""
    if not param.typ:
      return
    elif isinstance(param.typ, cfg.Variable):
      types = param.typ.data  # pytype: disable=attribute-error
      if len(types) == 1:
        annotations[param.name] = types[0].cls
      else:
        t = abstract.Union([t.cls for t in types], ctx)
        annotations[param.name] = t
    else:
      annotations[param.name] = param.typ

  # Set default values
  params = params or []
  kwonly_params = kwonly_params or []
  if kind in (pytd.MethodKind.METHOD, pytd.MethodKind.PROPERTY):
    self_param = [self_param or Param("self", None, None)]
  elif kind == pytd.MethodKind.CLASSMETHOD:
    self_param = [Param("cls", None, None)]
  else:
    assert kind == pytd.MethodKind.STATICMETHOD
    self_param = []
  annotations = {}

  params = self_param + params

  return_param = Param("return", return_type, None) if return_type else None
  special_params = [x for x in (return_param, varargs, kwargs) if x]
  for param in special_params + params + kwonly_params:
    _process_annotation(param)

  names = lambda xs: tuple(x.name for x in xs)
  param_names = names(params)
  kwonly_names = names(kwonly_params)
  defaults = {x.name: x.default for x in params + kwonly_params if x.default}
  varargs_name = varargs.name if varargs else None
  kwargs_name = kwargs.name if kwargs else None

  ret = abstract.SimpleFunction.build(
      name=name,
      param_names=param_names,
      posonly_count=posonly_count,
      varargs_name=varargs_name,
      kwonly_params=kwonly_names,
      kwargs_name=kwargs_name,
      defaults=defaults,
      annotations=annotations,
      ctx=ctx)

  # Check that the constructed function has a valid signature
  ret.signature.check_defaults(ctx)

  retvar = ret.to_variable(node)
  if kind in (pytd.MethodKind.METHOD, pytd.MethodKind.PROPERTY):
    return retvar
  if kind == pytd.MethodKind.CLASSMETHOD:
    decorator = ctx.vm.load_special_builtin("classmethod")
  else:
    assert kind == pytd.MethodKind.STATICMETHOD
    decorator = ctx.vm.load_special_builtin("staticmethod")
  args = function.Args(posargs=(retvar,))
  return decorator.call(node, funcv=None, args=args)[1]


def add_base_class(node, cls, base_cls):
  """Inserts base_cls into the MRO of cls."""
  # The class's MRO is constructed from its bases at the moment the class is
  # created, so both need to be updated.
  bases = cls.bases()
  # If any class in base_cls's MRO already exists in the list of bases, base_cls
  # needs to be inserted before it, otherwise we put it at the end.
  base_cls_mro = {x.full_name for x in base_cls.mro}
  cls_bases = [x.data[0].full_name for x in bases]
  cls_mro = [x.full_name for x in cls.mro]
  bpos = [i for i, x in enumerate(cls_bases) if x in base_cls_mro]
  mpos = [i for i, x in enumerate(cls_mro) if x in base_cls_mro]
  if bpos:
    bpos, mpos = bpos[0], mpos[0]
    bases.insert(bpos, base_cls.to_variable(node))
    cls.mro = cls.mro[:mpos] + (base_cls,) + cls.mro[mpos:]
  else:
    bases.append(base_cls.to_variable(node))
    cls.mro = cls.mro + (base_cls,)


def not_supported_yet(name, ctx, ast, details=None):
  full_name = f"{ast.name}.{name}"
  ctx.errorlog.not_supported_yet(ctx.vm.frames, full_name, details=details)
  pytd_type = pytd.ToType(ast.Lookup(full_name), True, True, True)
  return ctx.convert.constant_to_value(pytd_type, node=ctx.root_node)

