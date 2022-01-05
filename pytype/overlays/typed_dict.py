"""Implementation of TypedDict."""

import dataclasses

from typing import Any, Dict, Set

from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.abstract import function
from pytype.overlays import classgen


@dataclasses.dataclass
class TypedDictProperties:
  """Collection of typed dict properties passed between various stages."""

  name: str
  fields: Dict[str, Any]
  required: Set[str]
  total: bool

  @property
  def keys(self):
    return set(self.fields.keys())

  @property
  def optional(self):
    return self.keys - self.required

  def add(self, k, v, total):
    self.fields[k] = v
    if total:
      self.required.add(k)

  def check_keys(self, keys):
    keys = set(keys)
    missing = (self.keys - keys) & self.required
    extra = keys - self.keys
    return missing, extra


class TypedDictBuilder(abstract.PyTDClass):
  """Factory for creating typing.TypedDict classes."""

  def __init__(self, ctx):
    typing_ast = ctx.loader.import_name("typing")
    pyval = typing_ast.Lookup("typing._TypedDict")
    pyval = pyval.Replace(name="typing.TypedDict")
    super().__init__("TypedDict", pyval, ctx)

  def call(self, node, *args):
    details = ("Use the class definition form of TypedDict instead.")
    self.ctx.errorlog.not_supported_yet(
        self.ctx.vm.frames, "TypedDict functional constructor", details)
    return node, self.ctx.new_unsolvable(node)

  def _validate_bases(self, cls_name, bases):
    """Check that all base classes are valid."""
    for base_var in bases:
      for base in base_var.data:
        if not isinstance(base, (TypedDictClass, TypedDictBuilder)):
          details = (f"TypedDict {cls_name} cannot inherit from "
                     "a non-TypedDict class.")
          self.ctx.errorlog.base_class_error(
              self.ctx.vm.frames, base_var, details)

  def _merge_base_class_fields(self, bases, props):
    """Add the merged list of base class fields to the fields dict."""
    # Updates props in place, raises an error if a duplicate key is encountered.
    provenance = {k: props.name for k in props.fields}
    for base_var in bases:
      for base in base_var.data:
        if not isinstance(base, TypedDictClass):
          continue
        for k, v in base.props.fields.items():
          if k in props.fields:
            classes = f"{base.name} and {provenance[k]}"
            details = f"Duplicate TypedDict key {k} in classes {classes}"
            self.ctx.errorlog.base_class_error(
                self.ctx.vm.frames, base_var, details)
          else:
            props.add(k, v, base.props.total)
            provenance[k] = base.name

  def _make_init(self, node, props):
    # __init__ method for type checking signatures.
    # We construct this here and pass it to TypedDictClass because we need
    # access to abstract.SignedFunction.
    sig = function.Signature.from_param_names(
        f"{props.name}.__init__", props.fields.keys(), kwonly=True)
    sig.annotations = {k: abstract_utils.get_atomic_value(v)
                       for k, v in props.fields.items()}
    sig.defaults = {k: self.ctx.new_unsolvable(node)
                    for k in props.optional}
    return abstract.SignedFunction(sig, self.ctx)

  def make_class(self, node, bases, f_locals, total):
    # If BuildClass.call() hits max depth, f_locals will be [unsolvable]
    # See comment in NamedTupleClassBuilder.make_class(); equivalent logic
    # applies here.
    if isinstance(f_locals.data[0], abstract.Unsolvable):
      return node, self.ctx.new_unsolvable(node)

    f_locals = abstract_utils.get_atomic_python_constant(f_locals)

    # retrieve __qualname__ to get the name of class
    name_var = f_locals["__qualname__"]
    cls_name = abstract_utils.get_atomic_python_constant(name_var)
    if "." in cls_name:
      cls_name = cls_name.rsplit(".", 1)[-1]

    if total is None:
      total = True
    else:
      total = abstract_utils.get_atomic_python_constant(total, bool)
    props = TypedDictProperties(
        name=cls_name, fields={}, required=set(), total=total)

    # Collect the key types defined in the current class.
    cls_locals = classgen.get_class_locals(
        cls_name,
        allow_methods=False,
        ordering=classgen.Ordering.FIRST_ANNOTATE,
        ctx=self.ctx)
    for k, local in cls_locals.items():
      assert local.typ
      props.add(k, local.typ, total)

    # Process base classes and generate the __init__ signature.
    self._validate_bases(cls_name, bases)
    self._merge_base_class_fields(bases, props)
    init_method = self._make_init(node, props)

    cls = TypedDictClass(props, init_method, self, self.ctx)
    cls_var = cls.to_variable(node)
    return node, cls_var


class TypedDictClass(abstract.PyTDClass):
  """A template for typed dicts."""

  def __init__(self, props, init_method, base_cls, ctx):
    self.props = props
    self.init_method = init_method
    self._base_cls = base_cls  # TypedDictBuilder for constructing subclasses
    super().__init__(props.name, ctx.convert.dict_type.pytd_cls, ctx)

  def __repr__(self):
    return f"TypedDictClass({self.name})"

  def _new_instance(self, container, node, args):
    self.init_method.match_and_map_args(node, args, {})
    ret = TypedDict(self.props, self.ctx)
    for (k, v) in args.namedargs.items():
      ret.set_str_item(node, k, v)
    return ret

  def make_class(self, *args, **kwargs):
    return self._base_cls.make_class(*args, **kwargs)


class TypedDict(abstract.Dict):
  """Representation of TypedDict instances.

  Internally, a TypedDict is a dict with a restricted set of string keys
  allowed, each with a fixed type. We implement it as a subclass of Dict, with
  some type checks wrapped around key accesses. If a check fails, we simply add
  an error to the logs and then continue processing the method as though it were
  a regular dict.
  """

  def __init__(self, props, ctx):
    super().__init__(ctx)
    self.props = props
    self.set_slot("__delitem__", self.delitem_slot)

  @property
  def fields(self):
    return self.props.fields

  @property
  def class_name(self):
    return self.props.name

  def __repr__(self):
    return f"<TypedDict {self.class_name}>"

  def _check_str_key(self, name):
    if name not in self.fields:
      self.ctx.errorlog.typed_dict_error(self.ctx.vm.frames, self, name)
      return False
    return True

  def _check_str_key_value(self, node, name, value_var):
    if not self._check_str_key(name):
      return
    typ = abstract_utils.get_atomic_value(self.fields[name])
    bad = self.ctx.matcher(node).bad_matches(value_var, typ)
    for view, error_details in bad:
      binding = view[value_var]
      self.ctx.errorlog.annotation_type_mismatch(
          self.ctx.vm.frames, typ, binding, name, error_details,
          typed_dict=self
      )

  def _check_key(self, name_var):
    """Check that key is in the typed dict."""
    try:
      name = abstract_utils.get_atomic_python_constant(name_var, str)
    except abstract_utils.ConversionError:
      self.ctx.errorlog.typed_dict_error(self.ctx.vm.frames, self, name=None)
      return False
    return self._check_str_key(name)

  def _check_value(self, node, name_var, value_var):
    """Check that value has the right type."""
    # We have already called check_key so name is in fields
    name = abstract_utils.get_atomic_python_constant(name_var, str)
    self._check_str_key_value(node, name, value_var)

  def getitem_slot(self, node, name_var):
    self._check_key(name_var)
    return super().getitem_slot(node, name_var)

  def setitem_slot(self, node, name_var, value_var):
    if self._check_key(name_var):
      self._check_value(node, name_var, value_var)
    return super().setitem_slot(node, name_var, value_var)

  def set_str_item(self, node, name, value_var):
    self._check_str_key_value(node, name, value_var)
    return super().set_str_item(node, name, value_var)

  def delitem_slot(self, node, name_var):
    self._check_key(name_var)
    return self.call_pytd(node, "__delitem__", name_var)

  def pop_slot(self, node, key_var, default_var=None):
    self._check_key(key_var)
    return super().pop_slot(node, key_var, default_var)
