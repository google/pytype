"""Support for dataclasses."""

# TODO(mdemello):
# - Raise an error if we see a duplicate annotation, even though python allows
#     it, since there is no good reason to do that.

import logging

from pytype import abstract
from pytype import abstract_utils
from pytype import function
from pytype import overlay
from pytype.overlays import classgen

log = logging.getLogger(__name__)


_DATACLASS_METADATA_KEY = "__dataclass_fields__"


class DataclassOverlay(overlay.Overlay):
  """A custom overlay for the 'dataclasses' module."""

  def __init__(self, vm):
    member_map = {
        "dataclass": Dataclass.make,
        "field": Field.make,
    }
    ast = vm.loader.import_name("dataclasses")
    super().__init__(vm, "dataclasses", member_map, ast)


class Dataclass(classgen.Decorator):
  """Implements the @dataclass decorator."""

  @classmethod
  def make(cls, vm, mod="dataclasses"):
    return super().make("dataclass", vm, mod)

  def _handle_initvar(self, node, cls, name, typ, orig):
    """Unpack or delete an initvar in the class annotations."""
    initvar = match_initvar(typ)
    if not initvar:
      return None
    # The InitVar annotation is not retained as a class member, but any default
    # value is retained.
    del self.vm.annotated_locals[cls.name][name]
    if orig is not None:
      cls.members[name] = classgen.instantiate(node, name, initvar)
    return initvar

  def get_class_locals(self, node, cls):
    del node
    return classgen.get_class_locals(
        cls.name, allow_methods=True, ordering=classgen.Ordering.FIRST_ANNOTATE,
        vm=self.vm)

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
      assert typ
      if match_classvar(typ):
        continue
      initvar_typ = self._handle_initvar(node, cls, name, typ, orig)
      if initvar_typ:
        typ = initvar_typ
        init = True
      else:
        if not orig:
          cls.members[name] = classgen.instantiate(node, name, typ)
        if is_field(orig):
          field = orig.data[0]
          orig = field.default
          init = field.init
        else:
          init = True

      # TODO(b/74434237): The first check can be removed once
      # --check-variable-types is on by default.
      if ((not self.vm.options.check_variable_types and
           local.last_op and
           local.last_op.line in self.vm.director.type_comments) or
          orig and orig.data == [self.vm.convert.none]):
        # vm._apply_annotation mostly takes care of checking that the default
        # matches the declared type. However, it allows None defaults, and
        # dataclasses do not.
        self.vm.check_annotation_type_mismatch(
            node, name, typ, orig, local.stack, allow_none=False)

      attr = classgen.Attribute(
          name=name, typ=typ, init=init, kw_only=False, default=orig)
      own_attrs.append(attr)

    base_attrs = self.get_base_class_attrs(
        cls, own_attrs, _DATACLASS_METADATA_KEY)
    attrs = base_attrs + own_attrs
    # Stash attributes in class metadata for subclasses.
    cls.metadata[_DATACLASS_METADATA_KEY] = attrs

    # Add an __init__ method if one doesn't exist already (dataclasses do not
    # overwrite an explicit __init__ method).
    if "__init__" not in cls.members and self.args[cls]["init"]:
      init_method = self.make_init(node, cls, attrs)
      cls.members["__init__"] = init_method


class FieldInstance(abstract.SimpleAbstractValue):
  """Return value of a field() call."""

  def __init__(self, vm, init, default):
    super().__init__("field", vm)
    self.init = init
    self.default = default
    self.cls = vm.convert.unsolvable


class Field(classgen.FieldConstructor):
  """Implements dataclasses.field."""

  @classmethod
  def make(cls, vm):
    return super().make("field", vm, "dataclasses")

  def call(self, node, unused_func, args):
    """Returns a type corresponding to a field."""
    self.match_args(node, args)
    node, default_var = self._get_default_var(node, args)
    init = self.get_kwarg(args, "init", True)
    typ = FieldInstance(self.vm, init, default_var).to_variable(node)
    return node, typ

  def _get_default_var(self, node, args):
    if "default" in args.namedargs and "default_factory" in args.namedargs:
      # The pyi signatures should prevent this; check left in for safety.
      raise function.DuplicateKeyword(self.signatures[0].signature, args,
                                      self.vm, "default")
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
