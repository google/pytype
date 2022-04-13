"""Support for dataclasses."""

# TODO(mdemello):
# - Raise an error if we see a duplicate annotation, even though python allows
#     it, since there is no good reason to do that.

import logging

from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.abstract import function
from pytype.overlays import classgen
from pytype.overlays import overlay

log = logging.getLogger(__name__)


class DataclassOverlay(overlay.Overlay):
  """A custom overlay for the 'dataclasses' module."""

  def __init__(self, ctx):
    member_map = {
        "dataclass": Dataclass.make,
        "field": FieldFunction.make,
    }
    ast = ctx.loader.import_name("dataclasses")
    super().__init__(ctx, "dataclasses", member_map, ast)


class Dataclass(classgen.Decorator):
  """Implements the @dataclass decorator."""

  @classmethod
  def make(cls, ctx, mod="dataclasses"):
    return super().make("dataclass", ctx, mod)

  def _handle_initvar(self, node, cls, name, typ, orig):
    """Unpack or delete an initvar in the class annotations."""
    initvar = match_initvar(typ)
    if not initvar:
      return None
    # The InitVar annotation is not retained as a class member, but any default
    # value is retained.
    if orig is None:
      # If an initvar does not have a default, it will not be a class member
      # variable, so delete it from the annotated locals. Otherwise, leave the
      # annotation as InitVar[...].
      del self.ctx.vm.annotated_locals[cls.name][name]
    else:
      classgen.add_member(node, cls, name, initvar)
    return initvar

  def get_class_locals(self, node, cls):
    del node
    return classgen.get_class_locals(
        cls.name,
        allow_methods=True,
        ordering=classgen.Ordering.FIRST_ANNOTATE,
        ctx=self.ctx)

  def decorate(self, node, cls):
    """Processes class members."""

    # Collect classvars to convert them to attrs. @dataclass collects vars with
    # an explicit type annotation, in order of annotation, so that e.g.
    # class A:
    #   x: int
    #   y: str = 'hello'
    #   x = 10
    # would have init(x:int = 10, y:str = 'hello')
    own_attrs = []
    cls_locals = self.get_class_locals(node, cls)
    for name, local in cls_locals.items():
      typ, orig = local.get_type(node, name), local.orig
      kind = ""
      assert typ
      if match_classvar(typ):
        continue
      initvar_typ = self._handle_initvar(node, cls, name, typ, orig)
      if initvar_typ:
        typ = initvar_typ
        init = True
        kind = classgen.AttributeKinds.INITVAR
      else:
        if not orig:
          classgen.add_member(node, cls, name, typ)
        if is_field(orig):
          field = orig.data[0]
          orig = field.default
          init = field.init
        else:
          init = True

      if orig and orig.data == [self.ctx.convert.none]:
        # vm._apply_annotation mostly takes care of checking that the default
        # matches the declared type. However, it allows None defaults, and
        # dataclasses do not.
        self.ctx.check_annotation_type_mismatch(
            node, name, typ, orig, local.stack, allow_none=False)

      attr = classgen.Attribute(
          name=name, typ=typ, init=init, kw_only=False, default=orig, kind=kind)
      own_attrs.append(attr)

    cls.record_attr_ordering(own_attrs)
    attrs = cls.compute_attr_metadata(own_attrs, "dataclasses.dataclass")

    # Add an __init__ method if one doesn't exist already (dataclasses do not
    # overwrite an explicit __init__ method).
    if ("__init__" not in cls.members and self.args[cls] and
        self.args[cls]["init"]):
      init_method = self.make_init(node, cls, attrs)
      cls.members["__init__"] = init_method

    # Add the __dataclass_fields__ attribute, the presence of which
    # dataclasses.is_dataclass uses to determine if an object is a dataclass (or
    # an instance of one).
    attr_types = self.ctx.convert.merge_values({attr.typ for attr in attrs})
    dataclass_ast = self.ctx.loader.import_name("dataclasses")
    generic_field = abstract.ParameterizedClass(
        self.ctx.convert.name_to_value("dataclasses.Field", ast=dataclass_ast),
        {abstract_utils.T: attr_types}, self.ctx)
    dataclass_fields_params = {
        abstract_utils.K: self.ctx.convert.str_type,
        abstract_utils.V: generic_field
    }
    dataclass_fields_typ = abstract.ParameterizedClass(
        self.ctx.convert.dict_type, dataclass_fields_params, self.ctx)
    classgen.add_member(node, cls, "__dataclass_fields__", dataclass_fields_typ)

    annotations_dict = classgen.get_or_create_annotations_dict(
        cls.members, self.ctx)
    annotations_dict.annotated_locals["__dataclass_fields__"] = (
        abstract_utils.Local(node, None, dataclass_fields_typ, None, self.ctx))

    if isinstance(cls, abstract.InterpreterClass):
      cls.decorators.append("dataclasses.dataclass")
      # Fix up type parameters in methods added by the decorator.
      cls.update_method_type_params()


class FieldInstance(abstract.SimpleValue):
  """Return value of a field() call."""

  def __init__(self, ctx, init, default):
    super().__init__("field", ctx)
    self.init = init
    self.default = default
    self.cls = ctx.convert.unsolvable


class FieldFunction(classgen.FieldConstructor):
  """Implements dataclasses.field."""

  @classmethod
  def make(cls, ctx):
    return super().make("field", ctx, "dataclasses")

  def call(self, node, unused_func, args):
    """Returns a type corresponding to a field."""
    args = args.simplify(node, self.ctx)
    self.match_args(node, args)
    node, default_var = self._get_default_var(node, args)
    init = self.get_kwarg(args, "init", True)
    typ = FieldInstance(self.ctx, init, default_var).to_variable(node)
    return node, typ

  def _get_default_var(self, node, args):
    if "default" in args.namedargs and "default_factory" in args.namedargs:
      # The pyi signatures should prevent this; check left in for safety.
      raise function.DuplicateKeyword(self.signatures[0].signature, args,
                                      self.ctx, "default")
    elif "default" in args.namedargs:
      default_var = args.namedargs["default"]
    elif "default_factory" in args.namedargs:
      factory_var = args.namedargs["default_factory"]
      factory, = factory_var.data
      f_args = function.Args(posargs=())
      node, default_var = factory.call(node, factory_var.bindings[0], f_args)
    else:
      default_var = None

    return node, default_var


def is_field(var):
  return var and isinstance(var.data[0], FieldInstance)


def match_initvar(var):
  """Unpack the type parameter from InitVar[T]."""
  return abstract_utils.match_type_container(var, "dataclasses.InitVar")


def match_classvar(var):
  """Unpack the type parameter from ClassVar[T]."""
  return abstract_utils.match_type_container(var, "typing.ClassVar")
