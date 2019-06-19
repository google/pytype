"""Implementation of the types in Python 3's typing.py."""

# pylint's detection of this is error-prone:
# pylint: disable=unpacking-non-sequence

from pytype import abstract
from pytype import abstract_utils
from pytype import collections_overlay
from pytype import compat
from pytype import function
from pytype import mixin
from pytype import overlay
from pytype import overlay_utils
from pytype import utils
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd import visitors
import six
from six import moves


# type alias
Param = overlay_utils.Param


class TypingOverlay(overlay.Overlay):
  """A representation of the 'typing' module that allows custom overlays."""

  def __init__(self, vm):
    # Make sure we have typing available as a dependency
    if not vm.loader.can_see("typing"):
      vm.errorlog.import_error(vm.frames, "typing")
    member_map = typing_overload.copy()
    ast = vm.loader.typing
    for cls in ast.classes:
      _, name = cls.name.rsplit(".", 1)
      if name not in member_map and pytd.IsContainer(cls) and cls.template:
        member_map[name] = TypingContainer
    super(TypingOverlay, self).__init__(vm, "typing", member_map, ast)


class Union(abstract.AnnotationClass):
  """Implementation of typing.Union[...]."""

  def __init__(self, name, vm, options=()):
    super(Union, self).__init__(name, vm)
    self.options = options

  def _build_value(self, node, inner, ellipses):
    self.vm.errorlog.invalid_ellipses(self.vm.frames, ellipses, self.name)
    return abstract.Union(self.options + inner, self.vm)


class TypingContainer(abstract.AnnotationContainer):

  def __init__(self, name, vm):
    if name in pep484.PEP484_CAPITALIZED:
      pytd_name = "__builtin__." + name.lower()
    else:
      pytd_name = "typing." + name
    base = vm.convert.name_to_value(pytd_name)
    super(TypingContainer, self).__init__(name, vm, base)


class Tuple(TypingContainer):
  """Implementation of typing.Tuple."""

  def _get_value_info(self, inner, ellipses):
    if ellipses:
      # An ellipsis may appear at the end of the parameter list as long as it is
      # not the only parameter.
      return super(Tuple, self)._get_value_info(
          inner, ellipses, allowed_ellipses={len(inner) - 1} - {0})
    else:
      template = list(moves.range(len(inner))) + [abstract_utils.T]
      inner += (self.vm.merge_values(inner),)
      return template, inner, abstract.TupleClass


class Callable(TypingContainer):
  """Implementation of typing.Callable[...]."""

  def getitem_slot(self, node, slice_var):
    content = abstract_utils.maybe_extract_tuple(slice_var)
    inner, ellipses = self._build_inner(content)
    args = inner[0]
    if isinstance(args, abstract.List) and not args.could_contain_anything:
      inner[0], inner_ellipses = self._build_inner(args.pyval)
      self.vm.errorlog.invalid_ellipses(
          self.vm.frames, inner_ellipses, args.name)
    else:
      if args.cls and args.cls.full_name == "__builtin__.list":
        self.vm.errorlog.invalid_annotation(
            self.vm.frames, args, "Must be constant")
      elif 0 not in ellipses or not isinstance(args, abstract.Unsolvable):
        self.vm.errorlog.invalid_annotation(
            self.vm.frames, args, ("First argument to Callable must be a list"
                                   " of argument types or ellipsis."))
      inner[0] = self.vm.convert.unsolvable
    value = self._build_value(node, tuple(inner), ellipses)
    return node, value.to_variable(node)

  def _get_value_info(self, inner, ellipses):
    if isinstance(inner[0], list):
      template = (list(moves.range(len(inner[0]))) +
                  [t.name for t in self.base_cls.template])
      combined_args = self.vm.merge_values(inner[0])
      inner = tuple(inner[0]) + (combined_args,) + inner[1:]
      self.vm.errorlog.invalid_ellipses(self.vm.frames, ellipses, self.name)
      return template, inner, abstract.Callable
    else:
      # An ellipsis may take the place of the ARGS list.
      return super(Callable, self)._get_value_info(
          inner, ellipses, allowed_ellipses={0})


class TypeVarError(Exception):
  """Raised if an error is encountered while initializing a TypeVar."""

  def __init__(self, message, bad_call=None):
    super(TypeVarError, self).__init__(message)
    self.bad_call = bad_call


class TypeVar(abstract.PyTDFunction):
  """Representation of typing.TypeVar, as a function."""

  # See b/74212131: we allow Any for bounds and constraints.
  _CLASS_TYPE = (abstract.AbstractOrConcreteValue, mixin.Class,
                 abstract.Unsolvable)

  def _get_class_or_constant(self, var, name, arg_type, arg_type_desc=None):
    if arg_type is self._CLASS_TYPE:
      convert_func = abstract_utils.get_atomic_value
      type_desc = arg_type_desc or "an unambiguous type"
    else:
      convert_func = abstract_utils.get_atomic_python_constant
      type_desc = arg_type_desc or "a constant " + arg_type.__name__
    try:
      ret = convert_func(var, arg_type)
      # If we have a class type as an AbstractOrConcreteValue, we want to return
      # it as a string.
      if isinstance(ret, abstract.AbstractOrConcreteValue):
        ret = abstract_utils.get_atomic_python_constant(var, str)
        if not ret:
          raise TypeVarError("%s cannot be an empty string" % name)
      return ret
    except abstract_utils.ConversionError:
      raise TypeVarError("%s must be %s" % (name, type_desc))

  def _get_namedarg(self, args, name, arg_type, default_value):
    if name in args.namedargs:
      value = self._get_class_or_constant(args.namedargs[name], name, arg_type)
      if name != "bound":
        self.vm.errorlog.not_supported_yet(
            self.vm.frames, "argument \"%s\" to TypeVar" % name)
      return value
    return default_value

  def _get_typeparam(self, node, args):
    args = args.simplify(node)
    try:
      self.match_args(node, args)
    except function.InvalidParameters as e:
      raise TypeVarError("wrong arguments", e.bad_call)
    except function.FailedFunctionCall:
      # It is currently impossible to get here, since the only
      # FailedFunctionCall that is not an InvalidParameters is NotCallable.
      raise TypeVarError("initialization failed")
    name = self._get_class_or_constant(args.posargs[0], "name",
                                       six.string_types,
                                       arg_type_desc="a constant str")
    constraints = tuple(self._get_class_or_constant(
        c, "constraint", self._CLASS_TYPE) for c in args.posargs[1:])
    if len(constraints) == 1:
      raise TypeVarError("the number of constraints must be 0 or more than 1")
    bound = self._get_namedarg(args, "bound", self._CLASS_TYPE, None)
    covariant = self._get_namedarg(args, "covariant", bool, False)
    contravariant = self._get_namedarg(args, "contravariant", bool, False)
    if constraints and bound:
      raise TypeVarError("constraints and a bound are mutually exclusive")
    extra_kwargs = set(args.namedargs) - {"bound", "covariant", "contravariant"}
    if extra_kwargs:
      raise TypeVarError("extra keyword arguments: " + ", ".join(extra_kwargs))
    if args.starargs:
      raise TypeVarError("*args must be a constant tuple")
    if args.starstarargs:
      raise TypeVarError("ambiguous **kwargs not allowed")
    return abstract.TypeParameter(name, self.vm, constraints=constraints,
                                  bound=bound, covariant=covariant,
                                  contravariant=contravariant)

  def call(self, node, _, args):
    """Call typing.TypeVar()."""
    try:
      param = self._get_typeparam(node, args)
    except TypeVarError as e:
      self.vm.errorlog.invalid_typevar(
          self.vm.frames, utils.message(e), e.bad_call)
      return node, self.vm.new_unsolvable(node)
    if param.has_late_types():
      self.vm.params_with_late_types.append((param, self.vm.simple_stack()))
    return node, param.to_variable(node)


class Cast(abstract.PyTDFunction):
  """Implements typing.cast."""

  def call(self, node, func, args):
    if args.posargs:
      try:
        annot = self.vm.annotations_util.process_annotation_var(
            args.posargs[0], "typing.cast", self.vm.frames, node)
      except self.vm.annotations_util.LateAnnotationError:
        self.vm.errorlog.invalid_annotation(
            self.vm.frames, self.vm.merge_values(args.posargs[0].data),
            "Forward references not allowed in typing.cast.\n"
            "Consider switching to a type comment.")
        annot = self.vm.new_unsolvable(node)
      args = args.replace(posargs=(annot,) + args.posargs[1:])
    return super(Cast, self).call(node, func, args)


class NoReturn(abstract.AtomicAbstractValue):

  def __init__(self, vm):
    super(NoReturn, self).__init__("NoReturn", vm)

  def get_class(self):
    return self

  def compute_mro(self):
    return self.default_mro()


def build_any(name, vm):
  del name
  return vm.convert.unsolvable


class NamedTupleFuncBuilder(collections_overlay.NamedTupleBuilder):
  """Factory for creating typing.NamedTuple classes."""

  @classmethod
  def make(cls, name, vm):
    typing_ast = vm.loader.import_name("typing")
    # Because NamedTuple is a special case for the pyi parser, typing.pytd has
    # "_NamedTuple" instead. Replace the name of the returned function so that
    # error messages will correctly display "typing.NamedTuple".
    pyval = typing_ast.Lookup("typing._NamedTuple")
    pyval = pyval.Replace(name="typing.NamedTuple")
    self = super(NamedTupleFuncBuilder, cls).make(name, vm, pyval)
    # NamedTuple's fields arg has type Sequence[Sequence[Union[str, type]]],
    # which doesn't provide precise enough type-checking, so we have to do
    # some of our own in _getargs. _NamedTupleFields is an alias to
    # List[Tuple[str, type]], which gives a more understandable error message.
    fields_pyval = typing_ast.Lookup("typing._NamedTupleFields").type
    fields_type = vm.convert.constant_to_value(
        fields_pyval, {}, vm.root_cfg_node)
    # pylint: disable=protected-access
    self._fields_param = function.BadParam(name="fields", expected=fields_type)
    return self

  def _is_str_instance(self, val):
    return (isinstance(val, abstract.Instance) and
            val.full_name in ("__builtin__.str", "__builtin__.unicode"))

  def _getargs(self, node, args):
    self.match_args(node, args)
    sig, = self.signatures
    callargs = {name: var for name, var, _ in sig.signature.iter_args(args)}
    # typing.NamedTuple doesn't support rename or verbose
    name_var = callargs["typename"]
    fields_var = callargs["fields"]
    fields = abstract_utils.get_atomic_python_constant(fields_var)
    if isinstance(fields, six.string_types):
      # Since str matches Sequence, we have to manually check for it.
      raise function.WrongArgTypes(
          sig.signature, args, self.vm, self._fields_param)
    # The fields is a list of tuples, so we need to deeply unwrap them.
    fields = [abstract_utils.get_atomic_python_constant(t) for t in fields]
    # We need the actual string for the field names and the AtomicAbstractValue
    # for the field types.
    names = []
    types = []
    for field in fields:
      if isinstance(field, six.string_types):
        # Since str matches Sequence, we have to manually check for it.
        raise function.WrongArgTypes(
            sig.signature, args, self.vm, self._fields_param)
      if (len(field) != 2 or
          any(not self._is_str_instance(v) for v in field[0].data)):
        # Note that we don't need to check field[1] because both 'str'
        # (forward reference) and 'type' are valid for it.
        raise function.WrongArgTypes(
            sig.signature, args, self.vm, self._fields_param)
      name, typ = field
      name_py_constant = abstract_utils.get_atomic_python_constant(name)
      if name_py_constant.__class__ is compat.UnicodeType:
        # Unicode values should be ASCII.
        name_py_constant = compat.native_str(name_py_constant.encode("ascii"))
      names.append(name_py_constant)
      types.append(abstract_utils.get_atomic_value(typ))
    return name_var, names, types

  def _build_namedtuple(self, name, field_names, field_types, node):
    # Build an InterpreterClass representing the namedtuple.
    if field_types:
      field_types_union = abstract.Union(field_types, self.vm)
    else:
      field_types_union = self.vm.convert.none_type

    members = {n: t.instantiate(node)
               for n, t in moves.zip(field_names, field_types)}
    # collections.namedtuple has: __dict__, __slots__ and _fields.
    # typing.NamedTuple adds: _field_types, __annotations__ and _field_defaults.
    # __slots__ and _fields are tuples containing the names of the fields.
    slots = tuple(self.vm.convert.build_string(node, f) for f in field_names)
    members["__slots__"] = abstract.Tuple(slots, self.vm).to_variable(node)
    members["_fields"] = abstract.Tuple(slots, self.vm).to_variable(node)
    # __dict__ and _field_defaults are both collections.OrderedDicts that map
    # field names (strings) to objects of the field types.
    ordered_dict_cls = self.vm.convert.name_to_value("collections.OrderedDict",
                                                     ast=self.collections_ast)

    # In Python 2, keys can be `str` or `unicode`; support both.
    # In Python 3, `str_type` and `unicode_type` are the same.
    field_keys_union = abstract.Union([self.vm.convert.str_type,
                                       self.vm.convert.unicode_type], self.vm)

    # Normally, we would use abstract_utils.K and abstract_utils.V, but
    # collections.pyi doesn't conform to that standard.
    field_dict_cls = abstract.ParameterizedClass(
        ordered_dict_cls,
        {"K": field_keys_union, "V": field_types_union},
        self.vm)
    members["__dict__"] = field_dict_cls.instantiate(node)
    members["_field_defaults"] = field_dict_cls.instantiate(node)
    # _field_types and __annotations__ are both collections.OrderedDicts
    # that map field names (strings) to the types of the fields.
    field_types_cls = abstract.ParameterizedClass(
        ordered_dict_cls,
        {"K": field_keys_union, "V": self.vm.convert.type_type},
        self.vm)
    members["_field_types"] = field_types_cls.instantiate(node)
    members["__annotations__"] = field_types_cls.instantiate(node)

    # __new__
    # We set the bound on this TypeParameter later. This gives __new__ the
    # signature: def __new__(cls: Type[_Tname], ...) -> _Tname, i.e. the same
    # signature that visitor.CreateTypeParametersForSignatures would create.
    # This allows subclasses of the NamedTuple to get the correct type from
    # their constructors.
    cls_type_param = abstract.TypeParameter(
        visitors.CreateTypeParametersForSignatures.PREFIX + name,
        self.vm, bound=None)
    cls_type = abstract.ParameterizedClass(
        self.vm.convert.type_type, {abstract_utils.T: cls_type_param}, self.vm)
    params = [Param(n, t) for n, t in moves.zip(field_names, field_types)]
    members["__new__"] = overlay_utils.make_method(
        self.vm, node,
        name="__new__",
        self_param=Param("cls", cls_type),
        params=params,
        return_type=cls_type_param
    )

    # __init__
    members["__init__"] = overlay_utils.make_method(
        self.vm, node,
        name="__init__",
        varargs=Param("args"),
        kwargs=Param("kwargs"))

    # _make
    # _make is a classmethod, so it needs to be wrapped by
    # specialibuiltins.ClassMethodInstance.
    # Like __new__, it uses the _Tname TypeVar.
    sized_cls = self.vm.convert.name_to_value("typing.Sized")
    iterable_type = abstract.ParameterizedClass(
        self.vm.convert.name_to_value("typing.Iterable"),
        {abstract_utils.T: field_types_union}, self.vm)
    cls_type = abstract.ParameterizedClass(
        self.vm.convert.type_type,
        {abstract_utils.T: cls_type_param}, self.vm)
    len_type = abstract.Callable(
        self.vm.convert.name_to_value("typing.Callable"),
        {0: sized_cls,
         abstract_utils.ARGS: sized_cls,
         abstract_utils.RET: self.vm.convert.int_type},
        self.vm)
    params = [
        Param("iterable", iterable_type),
        Param("new").unsolvable(self.vm, node),
        Param("len", len_type).unsolvable(self.vm, node)]
    make = overlay_utils.make_method(
        self.vm, node,
        name="_make",
        params=params,
        self_param=Param("cls", cls_type),
        return_type=cls_type_param)
    make_args = function.Args(posargs=(make,))
    _, members["_make"] = self.vm.special_builtins["classmethod"].call(
        node, None, make_args)

    # _replace
    # Like __new__, it uses the _Tname TypeVar. We have to annotate the `self`
    # param to make sure the TypeVar is substituted correctly.
    members["_replace"] = overlay_utils.make_method(
        self.vm, node,
        name="_replace",
        self_param=Param("self", cls_type_param),
        return_type=cls_type_param,
        kwargs=Param("kwds", field_types_union))

    # __getnewargs__
    getnewargs_tuple_params = dict(
        tuple(enumerate(field_types)) +
        ((abstract_utils.T, field_types_union),))
    getnewargs_tuple = abstract.TupleClass(self.vm.convert.tuple_type,
                                           getnewargs_tuple_params, self.vm)
    members["__getnewargs__"] = overlay_utils.make_method(
        self.vm, node,
        name="__getnewargs__",
        return_type=getnewargs_tuple)

    # __getstate__
    members["__getstate__"] = overlay_utils.make_method(
        self.vm, node, name="__getstate__")

    # _asdict
    members["_asdict"] = overlay_utils.make_method(
        self.vm, node,
        name="_asdict",
        return_type=field_dict_cls)

    # Finally, make the class.
    abs_membs = abstract.Dict(self.vm)
    abs_membs.update(node, members)
    if name.__class__ is compat.UnicodeType:
      # Unicode values should be ASCII.
      name = compat.native_str(name.encode("ascii"))
    node, cls_var = self.vm.make_class(
        node=node,
        name_var=self.vm.convert.build_string(node, name),
        bases=[self.vm.convert.tuple_type.to_variable(node)],
        class_dict_var=abs_membs.to_variable(node),
        cls_var=None)

    # Now that the class has been made, we can complete the TypeParameter used
    # by __new__, _make and _replace.
    cls_type_param.bound = cls_var.data[0]
    return node, cls_var

  def call(self, node, _, args):
    try:
      name_var, field_names, field_types = self._getargs(node, args)
    except abstract_utils.ConversionError:
      return node, self.vm.new_unsolvable(node)

    try:
      name = abstract_utils.get_atomic_python_constant(name_var)
    except abstract_utils.ConversionError:
      return node, self.vm.new_unsolvable(node)

    try:
      field_names = self._validate_and_rename_args(name, field_names, False)
    except ValueError as e:
      self.vm.errorlog.invalid_namedtuple_arg(self.vm.frames, utils.message(e))
      return node, self.vm.new_unsolvable(node)

    annots, late_annots = self.vm.annotations_util.convert_annotations_list(
        moves.zip(field_names, field_types))
    if late_annots:
      # We currently don't support forward references. Report if we find any,
      # then continue by using Unsolvable instead.
      self.vm.errorlog.not_supported_yet(
          self.vm.frames, "Forward references in typing.NamedTuple")
    field_types = [annots.get(field_name, self.vm.convert.unsolvable)
                   for field_name in field_names]
    node, cls_var = self._build_namedtuple(name, field_names, field_types, node)
    self.vm.trace_classdef(cls_var)
    return node, cls_var


class NamedTupleClassBuilder(abstract.PyTDClass):
  """Factory for creating typing.NamedTuple classes."""

  # attributes prohibited to set in NamedTuple class syntax
  _prohibited = ("__new__", "__init__", "__slots__", "__getnewargs__",
                 "_fields", "_field_defaults", "_field_types",
                 "_make", "_replace", "_asdict", "_source")

  _special = ("__module__", "__name__", "__qualname__", "__annotations__")

  def __init__(self, name, vm):
    typing_ast = vm.loader.import_name("typing")
    pyval = typing_ast.Lookup("typing._NamedTupleClass")
    pyval = pyval.Replace(name="typing.NamedTuple")
    super(NamedTupleClassBuilder, self).__init__(name, pyval, vm)
    # Prior to python 3.6, NamedTuple is a function. Although NamedTuple is a
    # class in python 3.6+, we can still use it like a function. Hold the
    # an instance of 'NamedTupleFuncBuilder' so that we can reuse the
    # old implementation to implement the NamedTuple in python 3.6+
    self.namedtuple = NamedTupleFuncBuilder.make(name, vm)

  def call(self, node, _, args):
    posargs = args.posargs
    if isinstance(args.namedargs, dict):
      namedargs = args.namedargs
    else:
      namedargs = self.vm.convert.value_to_constant(args.namedargs, dict)
    if namedargs and self.vm.python_version < (3, 6):
      errmsg = "Keyword syntax for NamedTuple is only supported in Python 3.6+"
      self.vm.errorlog.invalid_namedtuple_arg(self.vm.frames, err_msg=errmsg)
    if namedargs and len(posargs) == 1:
      namedargs = [abstract.Tuple(
          (self.vm.convert.build_string(node, k), v), self.vm).to_variable(node)
                   for k, v in namedargs.items()]
      namedargs = abstract.List(namedargs, self.vm).to_variable(node)
      posargs += (namedargs,)
      args = function.Args(posargs)
    elif namedargs:
      errmsg = ("Either list of fields or keywords can be provided to "
                "NamedTuple, not both")
      self.vm.errorlog.invalid_namedtuple_arg(self.vm.frames, err_msg=errmsg)
    return self.namedtuple.call(node, None, args)

  def make_class(self, node, f_locals):
    f_locals = abstract_utils.get_atomic_python_constant(f_locals)

    # retrieve __qualname__ to get the name of class
    name = f_locals["__qualname__"]
    # retrieve __annotations__ to get the dict
    # with key-value pair of (variable, type)
    anno = f_locals.get("__annotations__", {})
    if anno:
      anno = abstract_utils.get_atomic_value(anno)

    # assemble the arguments that are compatible with NamedTupleFuncBuilder.call
    field_list = []
    defaults = []
    for k, v in anno.items():
      if k in f_locals:
        defaults.append(f_locals.get(k))
        # TODO(ahxun): check if the value matches the declared type
      k = self.vm.convert.constant_to_var(k, node=node)
      field_list.append(self.vm.convert.build_tuple(node, (k, v)))
    anno = self.vm.convert.build_list(node, field_list)
    posargs = (name, anno)
    args = function.Args(posargs=posargs)
    node, cls_var = self.namedtuple.call(node, None, args)
    cls_val = abstract_utils.get_atomic_value(cls_var)

    if not isinstance(cls_val, abstract.Unsolvable):
      # set __new__.__defaults__
      defaults = abstract.Tuple(tuple(defaults), self.vm).to_variable(node)
      node, new_attr = self.vm.attribute_handler.get_attribute(
          node, cls_val, "__new__")
      new_attr = abstract_utils.get_atomic_value(new_attr)
      node = self.vm.attribute_handler.set_attribute(
          node, new_attr, "__defaults__", defaults)

      # set the attribute without overriding special namedtuple attributes
      node, fields = self.vm.attribute_handler.get_attribute(
          node, cls_val, "_fields")
      fields = abstract_utils.get_atomic_python_constant(fields, tuple)
      fields = [abstract_utils.get_atomic_python_constant(field, str)
                for field in fields]
      for key in f_locals:
        if key in self._prohibited:
          self.vm.errorlog.not_writable(self.vm.frames, cls_val, key)
        if key not in self._special and  key not in fields:
          node = self.vm.attribute_handler.set_attribute(
              node, cls_val, key, f_locals[key])

    return node, cls_var


class NewType(abstract.PyTDFunction):
  """Implementation of typing.NewType as a function."""

  def __init__(self, name, signatures, kind, vm):
    super(NewType, self).__init__(name, signatures, kind, vm)
    assert len(self.signatures) == 1, "NewType has more than one signature."
    signature = self.signatures[0].signature
    self._name_arg_name = signature.param_names[0]
    self._type_arg_name = signature.param_names[1]
    self._internal_name_counter = 0

  @property
  def internal_name_counter(self):
    val = self._internal_name_counter
    self._internal_name_counter += 1
    return val

  def call(self, node, func, args):
    args = args.simplify(node)
    self.match_args(node, args, match_all_views=True)
    # As long as the types match we do not really care about the actual
    # class name. But, if we have a string literal value as the name arg,
    # we will use it.
    name_arg = args.namedargs.get(self._name_arg_name) or args.posargs[0]
    try:
      _ = abstract_utils.get_atomic_python_constant(name_arg, str)
    except abstract_utils.ConversionError:
      name_arg = self.vm.convert.constant_to_var(
          "_NewType_Internal_Class_Name_%d_" % self.internal_name_counter)
    type_arg = args.namedargs.get(self._type_arg_name) or args.posargs[1]
    try:
      type_value = abstract_utils.get_atomic_value(type_arg)
    except abstract_utils.ConversionError:
      # We need the type arg to be an atomic value. If not, we just
      # silently return unsolvable.
      return node, self.vm.new_unsolvable(node)
    value_arg_name = "val"
    constructor = overlay_utils.make_method(
        self.vm, node,
        name="__init__",
        params=[Param(value_arg_name, type_value)])
    members = abstract.Dict(self.vm)
    members.set_str_item(node, "__init__", constructor)
    return self.vm.make_class(node, name_arg, (type_arg,),
                              members.to_variable(node), None)


class Overload(abstract.PyTDFunction):
  """Implementation of typing.overload."""

  def call(self, node, unused_func, args):
    """Marks that the given function is an overload."""
    self.match_args(node, args)

    # Since we have only 1 argument, it's easy enough to extract.
    func_var = args.posargs[0] if args.posargs else args.namedargs["func"]

    for func in func_var.data:
      if isinstance(func, abstract.INTERPRETER_FUNCTION_TYPES):
        func.is_overload = True
        self.vm.frame.overloads[func.name].append(func)

    return node, func_var


class Generic(TypingContainer):
  """Implementation of typing.Generic."""

  def _get_value_info(self, inner, ellipses):
    if not all(isinstance(item, abstract.TypeParameter) for item in inner):
      self.vm.errorlog.invalid_annotation(
          self.vm.frames, self,
          "Parameters to Generic[...] must all be type variables")
      inner = [item for item in inner
               if isinstance(item, abstract.TypeParameter)]

    template = [item.full_name for item in inner]

    if len(set(template)) != len(template):
      self.vm.errorlog.invalid_annotation(
          self.vm.frames, self,
          "Parameters to Generic[...] must all be unique")

    # `self.base_cls.template` will change each time, it is used to initialize
    # the template in ParameterizedClass.
    tp = [param.with_module(self.base_cls.full_name) for param in inner]
    self.base_cls._template = tp  # pylint: disable=protected-access

    return template, inner, abstract.ParameterizedClass


class Optional(abstract.AnnotationClass):
  """Implementation of typing.Optional."""

  def _build_value(self, node, inner, ellipses):
    self.vm.errorlog.invalid_ellipses(self.vm.frames, ellipses, self.name)
    if len(inner) != 1:
      error = "typing.Optional can only contain one type parameter"
      self.vm.errorlog.invalid_annotation(self.vm.frames, self, error)
    return abstract.Union((self.vm.convert.none_type,) + inner, self.vm)


def not_supported_yet(name, vm):
  vm.errorlog.not_supported_yet(vm.frames, "typing." + name)
  return vm.convert.unsolvable


def build_namedtuple(name, vm):
  if vm.python_version < (3, 6):
    return NamedTupleFuncBuilder.make(name, vm)
  else:
    return NamedTupleClassBuilder(name, vm)


def build_newtype(name, vm):
  return NewType.make(name, vm, "typing")


def build_noreturn(name, vm):
  del name
  return vm.convert.no_return


def build_overload(name, vm):
  return Overload.make(name, vm, "typing")


def build_typevar(name, vm):
  return TypeVar.make(name, vm, "typing", pyval_name="_typevar_new")


def build_typechecking(name, vm):
  del name
  return vm.convert.true


def build_cast(name, vm):
  return Cast.make(name, vm, "typing")


typing_overload = {
    "Any": build_any,
    "Callable": Callable,
    "ClassVar": not_supported_yet,
    "Generic": Generic,
    "NamedTuple": build_namedtuple,
    "NewType": build_newtype,
    "NoReturn": build_noreturn,
    "Optional": Optional,
    "Tuple": Tuple,
    "TypeVar": build_typevar,
    "Union": Union,
    "TYPE_CHECKING": build_typechecking,
    "cast": build_cast,
    "overload": build_overload,
}
