"""Support for the 'attrs' library."""

from pytype import abstract
from pytype import annotations_util
from pytype import overlay


class AttrOverlay(overlay.Overlay):
  """A custom overlay for the 'attr' module."""

  def __init__(self, vm):
    member_map = {
        "s": Attrs.make,
        "ib": Attrib.make,
    }
    ast = vm.loader.import_name("attr")
    super(AttrOverlay, self).__init__(vm, "attr", member_map, ast)


class Attrs(abstract.PyTDFunction):
  """Implements the @attr.s decorator."""

  @classmethod
  def make(cls, name, vm):
    return super(Attrs, cls).make(name, vm, "attr")

  def _make_init(self, node, attrs):
    # attrs removes leading underscores from attrib names when
    # generating kwargs for __init__.
    attrs = [(name.lstrip("_"), typ, orig) for name, typ, orig in attrs]
    params = [name for name, _, _ in attrs]
    annotations = {}
    late_annotations = {}
    for name, typ, _ in attrs:
      if is_late_annotation(typ):
        late_annotations[name] = typ
      elif all(t.cls for t in typ.data):
        if len(typ.data) == 1:
          annotations[name] = typ.data[0].cls
        else:
          t = abstract.Union([t.cls for t in typ.data], self.vm)
          annotations[name] = t
    init = abstract.SimpleFunction(
        name="__init__",
        param_names=("self",) + tuple(params),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations=annotations,
        late_annotations=late_annotations,
        vm=self.vm)
    # TODO(mdemello): Should we move this to the SimpleFunction constructor?
    if late_annotations:
      self.vm.functions_with_late_annotations.append(init)
    return init.to_variable(node)

  def call(self, node, unused_func, args):
    """Processes the attrib members of a class."""
    self.match_args(node, args)
    cls_var = args.posargs[0]
    # We should only have a single binding here
    cls, = cls_var.data

    # Collect classvars to convert them to attrs.
    #
    # TODO(mdemello): This is incomplete; we need to dig through the attrs
    # code/docs and see which classvars get converted by @attr.s.  For now, we
    # only record attrs that are explicitly created using attr.ib, but when we
    # add support for auto_attribs those will convert all classvars except for
    # those tagged with typing.ClassVar
    ordered_attrs = []
    for name, value, orig in self.vm.ordered_locals[cls.name]:
      if is_attrib(orig):
        if not is_attrib(value) and orig.data[0].has_type:
          # We cannot have both a type annotation and a type argument.
          if is_late_annotation(value):
            err = value.expr
          else:
            err = value.data[0].cls
          self.vm.errorlog.invalid_annotation(self.vm.frames, err)
        else:
          if is_late_annotation(value):
            # TODO(b/134687045): Resolve the type later. We will just set it to
            # the attr.ib type (which should be Any) for now, but preserve the
            # type in the constructor. e.g.
            #   class Foo
            #     x = attr.ib() # type: 'Foo'
            # will annotate as
            #   class Foo
            #     x: Any
            #     def __init__(x: Foo): ...
            typ = value
            cls.members[name] = orig.data[0].typ
          elif is_attrib(value):
            # Replace the attrib in the class dict with its type.
            typ = value.data[0].typ
            cls.members[name] = typ
          else:
            typ = value
          ordered_attrs.append((name, typ, orig))

    # Add an __init__ method
    init_method = self._make_init(node, ordered_attrs)
    cls.members["__init__"] = init_method

    return node, cls_var


class AttribInstance(abstract.SimpleAbstractValue):
  """Return value of an attr.ib() call."""

  def __init__(self, vm, typ, has_type):
    super(AttribInstance, self).__init__("attrib", vm)
    self.typ = typ
    self.has_type = has_type


class Attrib(abstract.PyTDFunction):
  """Implements attr.ib."""

  @classmethod
  def make(cls, name, vm):
    return super(Attrib, cls).make(name, vm, "attr")

  def call(self, node, unused_func, args):
    """Returns a type corresponding to an attr."""
    self.match_args(node, args)
    type_var = args.namedargs.get("type")
    has_type = type_var is not None
    if type_var:
      typ = type_var.data[0].instantiate(node)
    else:
      typ = self.vm.new_unsolvable(node)
    typ = AttribInstance(self.vm, typ, has_type).to_variable(node)
    return node, typ


def is_attrib(var):
  if is_late_annotation(var):
    return False
  return isinstance(var.data[0], AttribInstance)


def is_late_annotation(val):
  return isinstance(val, annotations_util.LateAnnotation)
