"""Implementation of the types in Python 3's typing.py."""

# pylint's detection of this is error-prone:
# pylint: disable=unpacking-non-sequence

from pytype import abstract
from pytype import abstract_utils
from pytype import compat
from pytype import function
from pytype import overlay
from pytype import overlay_utils
from pytype import utils
from pytype.overlays import classgen
from pytype.overlays import collections_overlay
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd import visitors
from six import moves


# type alias
Param = overlay_utils.Param


class TypingOverlay(overlay.Overlay):
  """A representation of the 'typing' module that allows custom overlays."""

  def __init__(self, vm):
    # Make sure we have typing available as a dependency
    if vm.python_version < (3, 5) and not vm.loader.can_see("typing"):
      vm.errorlog.import_error(vm.frames, "typing")
    member_map = typing_overlay.copy()
    ast = vm.loader.typing
    for cls in ast.classes:
      _, name = cls.name.rsplit(".", 1)
      if name not in member_map and pytd.IsContainer(cls) and cls.template:
        member_map[name] = overlay.build(name, TypingContainer)
    super().__init__(vm, "typing", member_map, ast)


class Union(abstract.AnnotationClass):
  """Implementation of typing.Union[...]."""

  def __init__(self, vm, options=()):
    super().__init__("Union", vm)
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
    super().__init__(name, vm, base)


class Tuple(TypingContainer):
  """Implementation of typing.Tuple."""

  def _get_value_info(self, inner, ellipses):
    if ellipses:
      # An ellipsis may appear at the end of the parameter list as long as it is
      # not the only parameter.
      return super()._get_value_info(
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
        self.vm.errorlog.ambiguous_annotation(self.vm.frames, [args])
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
      return template, inner, abstract.CallableClass
    else:
      # An ellipsis may take the place of the ARGS list.
      return super()._get_value_info(inner, ellipses, allowed_ellipses={0})


class TypeVarError(Exception):
  """Raised if an error is encountered while initializing a TypeVar."""

  def __init__(self, message, bad_call=None):
    super().__init__(message)
    self.bad_call = bad_call


class TypeVar(abstract.PyTDFunction):
  """Representation of typing.TypeVar, as a function."""

  def _get_constant(self, var, name, arg_type, arg_type_desc=None):
    try:
      ret = abstract_utils.get_atomic_python_constant(var, arg_type)
    except abstract_utils.ConversionError as e:
      raise TypeVarError(
          "%s must be %s" %
          (name, arg_type_desc or "a constant " + arg_type.__name__)) from e
    return ret

  def _get_annotation(self, node, var, name):
    with self.vm.errorlog.checkpoint() as record:
      annot = self.vm.annotations_util.extract_annotation(
          node, var, name, self.vm.simple_stack())
    if record.errors:
      raise TypeVarError("\n".join(error.message for error in record.errors))
    return annot

  def _get_namedarg(self, node, args, name, default_value):
    if name not in args.namedargs:
      return default_value
    if name == "bound":
      return self._get_annotation(node, args.namedargs[name], name)
    else:
      ret = self._get_constant(args.namedargs[name], name, bool)
      # This error is logged only if _get_constant succeeds.
      self.vm.errorlog.not_supported_yet(
          self.vm.frames, "argument \"%s\" to TypeVar" % name)
      return ret

  def _get_typeparam(self, node, args):
    args = args.simplify(node, self.vm)
    try:
      self.match_args(node, args)
    except function.InvalidParameters as e:
      raise TypeVarError("wrong arguments", e.bad_call) from e
    except function.FailedFunctionCall as e:
      # It is currently impossible to get here, since the only
      # FailedFunctionCall that is not an InvalidParameters is NotCallable.
      raise TypeVarError("initialization failed") from e
    name = self._get_constant(args.posargs[0], "name", str,
                              arg_type_desc="a constant str")
    constraints = tuple(
        self._get_annotation(node, c, "constraint") for c in args.posargs[1:])
    if len(constraints) == 1:
      raise TypeVarError("the number of constraints must be 0 or more than 1")
    bound = self._get_namedarg(node, args, "bound", None)
    covariant = self._get_namedarg(node, args, "covariant", False)
    contravariant = self._get_namedarg(node, args, "contravariant", False)
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
    return node, param.to_variable(node)


class Cast(abstract.PyTDFunction):
  """Implements typing.cast."""

  def call(self, node, func, args):
    if args.posargs:
      annot = self.vm.annotations_util.extract_annotation(
          node, args.posargs[0], "typing.cast", self.vm.simple_stack())
      if annot.formal:
        self.vm.errorlog.invalid_typevar(
            self.vm.frames, "cannot pass a TypeVar to a function")
        return node, self.vm.new_unsolvable(node)
      return self.vm.init_class(node, annot)
    return super().call(node, func, args)


class NoReturn(abstract.Singleton):
  """Implements typing.NoReturn as a singleton."""

  def __init__(self, vm):
    super().__init__("NoReturn", vm)


def build_any(vm):
  return vm.convert.unsolvable


class NamedTupleFuncBuilder(collections_overlay.NamedTupleBuilder):
  """Factory for creating typing.NamedTuple classes."""

  @classmethod
  def make(cls, vm):
    typing_ast = vm.loader.import_name("typing")
    # Because NamedTuple is a special case for the pyi parser, typing.pytd has
    # "_NamedTuple" instead. Replace the name of the returned function so that
    # error messages will correctly display "typing.NamedTuple".
    pyval = typing_ast.Lookup("typing._NamedTuple")
    pyval = pyval.Replace(name="typing.NamedTuple")
    self = super().make("NamedTuple", vm, pyval)
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
    if isinstance(fields, str):
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
      if isinstance(field, str):
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
      # TODO(mdemello): Fix this to support late types.
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
        return_type=cls_type_param,
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
    len_type = abstract.CallableClass(
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
    cls_dict = abstract.Dict(self.vm)
    cls_dict.update(node, members)
    if name.__class__ is compat.UnicodeType:
      # Unicode values should be ASCII.
      name = compat.native_str(name.encode("ascii"))

    node, cls_var = self.vm.make_class(
        node=node,
        name_var=self.vm.convert.build_string(node, name),
        bases=[self.vm.convert.tuple_type.to_variable(node)],
        class_dict_var=cls_dict.to_variable(node),
        cls_var=None)
    cls = cls_var.data[0]

    # Now that the class has been made, we can complete the TypeParameter used
    # by __new__, _make and _replace.
    cls_type_param.bound = cls

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

    annots = self.vm.annotations_util.convert_annotations_list(
        node, moves.zip(field_names, field_types))
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

  def __init__(self, vm):
    typing_ast = vm.loader.import_name("typing")
    pyval = typing_ast.Lookup("typing._NamedTupleClass")
    pyval = pyval.Replace(name="typing.NamedTuple")
    super().__init__("NamedTuple", pyval, vm)
    # Prior to python 3.6, NamedTuple is a function. Although NamedTuple is a
    # class in python 3.6+, we can still use it like a function. Hold the
    # an instance of 'NamedTupleFuncBuilder' so that we can reuse the
    # old implementation to implement the NamedTuple in python 3.6+
    self.namedtuple = NamedTupleFuncBuilder.make(vm)

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
    # If BuildClass.call() hits max depth, f_locals will be [unsolvable]
    # Since we don't support defining NamedTuple subclasses in a nested scope
    # anyway, we can just return unsolvable here to prevent a crash, and let the
    # invalid namedtuple error get raised later.
    if f_locals.data[0].isinstance_Unsolvable():
      return node, self.vm.new_unsolvable(node)

    f_locals = abstract_utils.get_atomic_python_constant(f_locals)

    # retrieve __qualname__ to get the name of class
    name = f_locals["__qualname__"]

    # assemble the arguments that are compatible with NamedTupleFuncBuilder.call
    field_list = []
    defaults = []
    cls_locals = classgen.get_class_locals(
        abstract_utils.get_atomic_python_constant(name), allow_methods=True,
        ordering=classgen.Ordering.FIRST_ANNOTATE, vm=self.vm)
    for k, local in cls_locals.items():
      assert local.typ
      if k in f_locals:
        defaults.append(f_locals[k])
      k = self.vm.convert.constant_to_var(k, node=node)
      field_list.append(self.vm.convert.build_tuple(node, (k, local.typ)))
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
    super().__init__(name, signatures, kind, vm)
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
    args = args.simplify(node, self.vm)
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

    template = [item.name for item in inner]

    if len(set(template)) != len(template):
      self.vm.errorlog.invalid_annotation(
          self.vm.frames, self,
          "Parameters to Generic[...] must all be unique")

    return template, inner, abstract.ParameterizedClass


class Optional(abstract.AnnotationClass):
  """Implementation of typing.Optional."""

  def _build_value(self, node, inner, ellipses):
    self.vm.errorlog.invalid_ellipses(self.vm.frames, ellipses, self.name)
    if len(inner) != 1:
      error = "typing.Optional can only contain one type parameter"
      self.vm.errorlog.invalid_annotation(self.vm.frames, self, error)
    return abstract.Union((self.vm.convert.none_type,) + inner, self.vm)


class Literal(TypingContainer):
  """Implementation of typing.Literal."""

  def _build_value(self, node, inner, ellipses):
    values = []
    errors = []
    for i, param in enumerate(inner):
      # TODO(b/123775699): Once pytype has proper support for enums, we should
      # stop allowing unsolvable and handle enums here.
      if (param == self.vm.convert.none or
          isinstance(param, abstract.LiteralClass) or
          param == self.vm.convert.unsolvable and i not in ellipses):
        value = param
      elif (isinstance(param, abstract.AbstractOrConcreteValue) and
            isinstance(param.pyval, (int, str, bytes))):
        value = abstract.LiteralClass(param, self.vm)
      else:
        if i in ellipses:
          invalid_param = "..."
        else:
          invalid_param = param.name
        errors.append((invalid_param, i))
        value = self.vm.convert.unsolvable
      values.append(value)
    if errors:
      self.vm.errorlog.invalid_annotation(
          self.vm.frames, self,
          "\n".join("Bad parameter %r at index %d" % e for e in errors))
    return self.vm.merge_values(values)


def not_supported_yet(name, vm):
  vm.errorlog.not_supported_yet(vm.frames, "typing." + name)
  return vm.convert.unsolvable


def build_namedtuple(vm):
  if vm.python_version < (3, 6):
    return NamedTupleFuncBuilder.make(vm)
  else:
    return NamedTupleClassBuilder(vm)


def build_newtype(vm):
  return NewType.make("NewType", vm, "typing")


def build_noreturn(vm):
  return vm.convert.no_return


def build_overload(vm):
  return Overload.make("overload", vm, "typing")


def build_typevar(vm):
  return TypeVar.make("TypeVar", vm, "typing", pyval_name="_typevar_new")


def build_typechecking(vm):
  return vm.convert.true


def build_cast(vm):
  return Cast.make("cast", vm, "typing")


typing_overlay = {
    "Any": build_any,
    "Callable": overlay.build("Callable", Callable),
    "Generic": overlay.build("Generic", Generic),
    "Literal": overlay.build("Literal", Literal),
    "NamedTuple": build_namedtuple,
    "NewType": build_newtype,
    "NoReturn": build_noreturn,
    "Optional": overlay.build("Optional", Optional),
    "Tuple": overlay.build("Tuple", Tuple),
    "TypeVar": build_typevar,
    "Union": Union,
    "TYPE_CHECKING": build_typechecking,
    "cast": build_cast,
    "overload": build_overload,
}
