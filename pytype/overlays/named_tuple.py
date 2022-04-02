"""Implementation of named tuples."""

import dataclasses
import keyword

from typing import Any, List, Optional

from pytype import overlay_utils
from pytype import utils
from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.abstract import class_mixin
from pytype.abstract import function
from pytype.overlays import classgen
from pytype.pytd import escape
from pytype.pytd import pytd
from pytype.pytd import visitors


# type alias
Param = overlay_utils.Param


# This module has classes and methods which benefit from extended docstrings,
# but whose argument list documentation is trivial and only adds clutter.
# Disable the lint check rather than convert the extended docstrings to
# one-line docstrings + comments.
# pylint: disable=g-doc-args
# pylint: disable=g-doc-return-or-yield
# pylint: disable=g-doc-exception


@dataclasses.dataclass
class Field:
  """A namedtuple field."""

  name: str
  typ: Any
  default: Any = None


@dataclasses.dataclass
class NamedTupleProperties:
  """Collection of properties used to construct a namedtuple."""

  name: str
  fields: List[Field]
  bases: List[Any]

  @classmethod
  def from_field_names(cls, name, field_names, ctx):
    """Make a NamedTupleProperties from field names with no types."""
    fields = [Field(n, ctx.convert.unsolvable, None) for n in field_names]
    return cls(name, fields, [])

  def validate_and_rename_fields(self, rename):
    """Validate and rename self.fields.

    namedtuple field names have some requirements:
    - must not be a Python keyword
    - must consist of only alphanumeric characters and "_"
    - must not start with "_" or a digit

    Basically, they're valid Python identifiers that don't start with "_" or a
    digit. Also, there can be no duplicate field names.

    If rename is true, any invalid field names are changed to "_%d". For
    example, "abc def ghi abc" becomes "abc _1 def _3" because "def" is a
    keyword and "abc" is a duplicate.

    Also validates self.name, which has the same requirements, except it can
    start with "_", and cannot be changed.
    """
    def invalid_name(field_name):
      return (not all(c.isalnum() or c == "_" for c in field_name)
              or keyword.iskeyword(field_name)
              or not field_name  # catches empty string, etc.
              or field_name[0].isdigit())

    if invalid_name(self.name):
      raise ValueError(self.name)

    seen = set()
    for idx, f in enumerate(self.fields):
      if invalid_name(f.name) or f.name.startswith("_") or f.name in seen:
        if rename:
          f.name = "_%d" % idx
        else:
          raise ValueError(f.name)
      seen.add(f.name)


@dataclasses.dataclass
class _Args:
  """Args for both collections.namedtuple and typing.NamedTuple."""

  name: str
  field_names: List[str]
  field_types: Optional[List[Any]] = None
  defaults: Optional[List[Any]] = None
  rename: bool = False


class _ArgsError(Exception):
  pass


class _FieldMatchError(Exception):
  """Errors when postprocessing field args, to be converted to WrongArgTypes."""

  def __init__(self, param):
    super().__init__()
    self.param = param


class NamedTupleBuilderBase(abstract.PyTDFunction):
  """Base class that handles namedtuple function args processing.

  Performs the same argument checking as collections.namedtuple, e.g. making
  sure field names don't start with _ or digits, making sure no keywords are
  used for the typename or field names, and so on.

  If incorrect arguments are passed, a subclass of function.FailedFunctionCall
  will be raised. Other cases (e.g. if any of the arguments have multiple
  bindings) raise _ArgsError(). This also occurs if an argument value is
  invalid, e.g. a keyword is used as a field name and rename is False.
  Subclasses catch _ArgsError() and return Any in place of a named tuple class.
  """

  # Args are processed in several stages:
  #   raw_args: The incoming function.Args passed to the constructor.
  #   callargs: A dict of {key: unwrapped arg value}
  #   _Args: Postprocessed arg values struct, unifies collections.namedtuple and
  #     the typing.NamedTuple functional constructor
  #   NamedTupleProperties: The final list of properties passed to the class
  #     builder. Unifies the functional constructors with the subclass
  #     constructor (which has class annotations rather than function args).

  def extract_args(self, node, callargs):
    """Extract callargs into an _Args object.

    Subclasses should implement extract_args for their specific args.
    """
    raise NotImplementedError()

  def process_args(self, node, raw_args):
    """Convert namedtuple call args into a NamedTupleProperties.

    Returns both the NamedTupleProperties and an _Args struct in case the caller
    wants to do any more args processing before calling the class builder.
    """

    # Check the args against the pytd signature
    self.match_args(node, raw_args)

    # namedtuple only has one signature
    sig, = self.signatures

    try:
      callargs = {name: abstract_utils.get_atomic_python_constant(var)
                  for name, var, _ in sig.signature.iter_args(raw_args)}
      args = self.extract_args(node, callargs)
    except abstract_utils.ConversionError:
      raise _ArgsError()  # pylint: disable=raise-missing-from
    except _FieldMatchError as e:
      raise function.WrongArgTypes(sig.signature, raw_args, self.ctx, e.param)

    props = NamedTupleProperties.from_field_names(
        args.name, args.field_names, self.ctx)
    try:
      props.validate_and_rename_fields(args.rename)
    except ValueError as e:
      self.ctx.errorlog.invalid_namedtuple_arg(
          self.ctx.vm.frames, utils.message(e))
      raise _ArgsError()  # pylint: disable=raise-missing-from

    if args.defaults:
      for f, d in zip(props.fields, args.defaults):
        f.default = self.ctx.new_unsolvable(node) if d else None

    return args, props


class NamedTupleBuilder(NamedTupleBuilderBase):
  """Factory for creating collections.namedtuple classes."""

  collections_ast: pytd.TypeDeclUnit

  @classmethod
  def make(cls, name, ctx, pyval=None):
    # Loading the ast should be memoized after the import in CollectionsOverlay
    collections_ast = ctx.loader.import_name("collections")
    # Subclasses of NamedTupleBuilder need a different pyval.
    if not pyval:
      pyval = collections_ast.Lookup("collections.namedtuple")
    self = super().make(name, ctx, "collections", pyval=pyval)  # pytype: disable=wrong-arg-types
    self.collections_ast = collections_ast
    return self

  def extract_args(self, node, callargs):
    """Extracts the typename, field_names and rename arguments.

    collections.namedtuple takes a 'verbose' argument too but we don't care
    about that.

    The 'defaults' arg is postprocessed from a sequence of defaults to a
    sequence of bools describing whether each field has a default (e.g., for
    collections.namedtuple('X', field_names=['a', 'b'], defaults=[0]) this
    method will return [False, True] for defaults to indicate that 'a' does not
    have a default while 'b' does).
    """
    name = callargs["typename"]

    # namedtuple fields can be given as a single string, e.g. "a, b, c" or as a
    # list [Variable('a'), Variable('b'), Variable('c')].
    # We just want a list of strings.
    fields = callargs["field_names"]
    if isinstance(fields, (bytes, str)):
      fields = utils.native_str(fields)
      field_names = fields.replace(",", " ").split()
    else:
      field_names = [abstract_utils.get_atomic_python_constant(f)
                     for f in fields]
      field_names = [utils.native_str(f) for f in field_names]

    if "defaults" in callargs:
      default_vars = callargs["defaults"]
      num_defaults = len(default_vars)
      defaults = [False] * (len(fields) - num_defaults) + [True] * num_defaults
    else:
      defaults = [False] * len(fields)

    # rename will take any problematic field names and give them a new name.
    rename = callargs.get("rename", False)

    return _Args(
        name=name, field_names=field_names, defaults=defaults, rename=rename)

  def call(self, node, _, args):
    """Creates a namedtuple class definition."""
    # If we can't extract the arguments, we take the easy way out and return Any
    try:
      _, props = self.process_args(node, args)
    except _ArgsError:
      return node, self.ctx.new_unsolvable(node)

    node, cls_var = _build_namedtuple(props, node, self.ctx)
    return node, cls_var


class NamedTupleFuncBuilder(NamedTupleBuilderBase):
  """Factory for creating typing.NamedTuples via the function constructor."""

  _fields_param: function.BadParam

  @classmethod
  def make(cls, ctx):
    typing_ast = ctx.loader.import_name("typing")
    # Because NamedTuple is a special case for the pyi parser, typing.pytd has
    # "_NamedTuple" instead. Replace the name of the returned function so that
    # error messages will correctly display "typing.NamedTuple".
    pyval = typing_ast.Lookup("typing._NamedTuple")
    pyval = pyval.Replace(name="typing.NamedTuple")
    self = super().make("NamedTuple", ctx, "typing", pyval)
    # NamedTuple's fields arg has type Sequence[Sequence[Union[str, type]]],
    # which doesn't provide precise enough type-checking, so we have to do
    # some of our own in _getargs. _NamedTupleFields is an alias to
    # List[Tuple[str, type]], which gives a more understandable error message.
    fields_pyval = typing_ast.Lookup("typing._NamedTupleFields").type
    fields_type = ctx.convert.constant_to_value(fields_pyval, {}, ctx.root_node)
    # pylint: disable=protected-access
    self._fields_param = function.BadParam(name="fields", expected=fields_type)
    return self

  def _is_str_instance(self, val):
    return (isinstance(val, abstract.Instance) and
            val.full_name in ("builtins.str", "builtins.unicode"))

  def extract_args(self, node, callargs):
    """Extracts the typename and fields arguments.

    fields is postprocessed into field_names and field_types.

    typing.NamedTuple doesn't support rename, it will default to False
    """

    cls_name = callargs["typename"]

    fields = callargs["fields"]
    if isinstance(fields, str):
      # Since str matches Sequence, we have to manually check for it.
      raise _FieldMatchError(self._fields_param)
    # The fields is a list of tuples, so we need to deeply unwrap them.
    fields = [abstract_utils.get_atomic_python_constant(t) for t in fields]
    # We need the actual string for the field names and the BaseValue
    # for the field types.
    names = []
    types = []
    for field in fields:
      if isinstance(field, str):
        # Since str matches Sequence, we have to manually check for it.
        raise _FieldMatchError(self._fields_param)
      if (len(field) != 2 or
          any(not self._is_str_instance(v) for v in field[0].data)):
        # Note that we don't need to check field[1] because both 'str'
        # (forward reference) and 'type' are valid for it.
        raise _FieldMatchError(self._fields_param)
      name, typ = field
      name_py_constant = abstract_utils.get_atomic_python_constant(name)
      names.append(name_py_constant)
      allowed_type_params = (
          self.ctx.annotation_utils.get_callable_type_parameter_names(typ))
      annot = self.ctx.annotation_utils.extract_annotation(
          node,
          typ,
          name_py_constant,
          self.ctx.vm.simple_stack(),
          allowed_type_params=allowed_type_params)
      types.append(annot)

    return _Args(name=cls_name, field_names=names, field_types=types)

  def call(self, node, _, args):
    try:
      args, props = self.process_args(node, args)
    except _ArgsError:
      return node, self.ctx.new_unsolvable(node)

    # fill in field types from annotations
    annots = self.ctx.annotation_utils.convert_annotations_list(
        node, zip(args.field_names, args.field_types))
    for f in props.fields:
      f.typ = annots.get(f.name, self.ctx.convert.unsolvable)

    node, cls_var = _build_namedtuple(props, node, self.ctx)
    return node, cls_var


class NamedTupleClassBuilder(abstract.PyTDClass):
  """Factory for creating typing.NamedTuples by subclassing NamedTuple."""

  # attributes prohibited to set in NamedTuple class syntax
  _prohibited = ("__new__", "__init__", "__slots__", "__getnewargs__",
                 "_fields", "_field_defaults", "_field_types",
                 "_make", "_replace", "_asdict", "_source")

  def __init__(self, ctx):
    typing_ast = ctx.loader.import_name("typing")
    pyval = typing_ast.Lookup("typing._NamedTupleClass")
    pyval = pyval.Replace(name="typing.NamedTuple")
    super().__init__("NamedTuple", pyval, ctx)
    # Prior to python 3.6, NamedTuple is a function. Although NamedTuple is a
    # class in python 3.6+, we can still use it like a function. Hold the
    # an instance of 'NamedTupleFuncBuilder' so that we can reuse the
    # old implementation to implement the NamedTuple in python 3.6+
    self.namedtuple = NamedTupleFuncBuilder.make(ctx)

  def call(self, node, _, args):
    posargs = args.posargs
    if isinstance(args.namedargs, dict):
      namedargs = args.namedargs
    else:
      namedargs = self.ctx.convert.value_to_constant(args.namedargs, dict)
    if namedargs and len(posargs) == 1:
      namedargs = [
          self.ctx.convert.build_tuple(
              node, (self.ctx.convert.build_string(node, k), v))
          for k, v in namedargs.items()
      ]
      namedargs = abstract.List(namedargs, self.ctx).to_variable(node)
      posargs += (namedargs,)
      args = function.Args(posargs)
    elif namedargs:
      errmsg = ("Either list of fields or keywords can be provided to "
                "NamedTuple, not both")
      self.ctx.errorlog.invalid_namedtuple_arg(
          self.ctx.vm.frames, err_msg=errmsg)
    return self.namedtuple.call(node, None, args)

  def make_class(self, node, bases, f_locals):
    # If BuildClass.call() hits max depth, f_locals will be [unsolvable]
    # Since we don't support defining NamedTuple subclasses in a nested scope
    # anyway, we can just return unsolvable here to prevent a crash, and let the
    # invalid namedtuple error get raised later.
    if isinstance(f_locals.data[0], abstract.Unsolvable):
      return node, self.ctx.new_unsolvable(node)

    f_locals = abstract_utils.get_atomic_python_constant(f_locals)

    # retrieve __qualname__ to get the name of class
    name = f_locals["__qualname__"]
    name = abstract_utils.get_atomic_python_constant(name)
    if "." in name:
      name = name.rsplit(".", 1)[-1]

    # Construct a NamedTupleProperties to pass to the builder function.
    cls_locals = classgen.get_class_locals(
        name,
        allow_methods=True,
        ordering=classgen.Ordering.FIRST_ANNOTATE,
        ctx=self.ctx)
    props = NamedTupleProperties(name=name, fields=[], bases=bases)
    stack = tuple(self.ctx.vm.frames)
    for k, local in cls_locals.items():
      assert local.typ
      t = self.ctx.annotation_utils.extract_annotation(
          node, local.typ, k, stack)
      props.fields.append(Field(name=k, typ=t, default=f_locals.get(k)))

    # typing.NamedTuple doesn't support rename; invalid fields are an error.
    try:
      props.validate_and_rename_fields(rename=False)
    except ValueError as e:
      self.ctx.errorlog.invalid_namedtuple_arg(
          self.ctx.vm.frames, utils.message(e))
      return node, self.ctx.new_unsolvable(node)

    node, cls_var = _build_namedtuple(props, node, self.ctx)
    cls_val = abstract_utils.get_atomic_value(cls_var)

    if not isinstance(cls_val, abstract.Unsolvable):

      # set the attribute without overriding special namedtuple attributes
      node, fields = self.ctx.attribute_handler.get_attribute(
          node, cls_val, "_fields")
      fields = abstract_utils.get_atomic_python_constant(fields, tuple)
      fields = [abstract_utils.get_atomic_python_constant(field, str)
                for field in fields]
      for key in f_locals:
        if key in self._prohibited:
          self.ctx.errorlog.not_writable(self.ctx.vm.frames, cls_val, key)
        if key not in abstract_utils.CLASS_LEVEL_IGNORE and  key not in fields:
          node = self.ctx.attribute_handler.set_attribute(
              node, cls_val, key, f_locals[key])

    return node, cls_var


class _DictBuilder:
  """Construct OrderedDict abstract classes for namedtuple members."""

  def __init__(self, ctx):
    self.ctx = ctx
    collections_ast = ctx.loader.import_name("collections")
    self.ordered_dict_cls = ctx.convert.name_to_value(
        "collections.OrderedDict", ast=collections_ast)

  def make(self, typ):
    # Normally, we would use abstract_utils.K and abstract_utils.V, but
    # collections.pyi doesn't conform to that standard.
    return abstract.ParameterizedClass(self.ordered_dict_cls, {
        "K": self.ctx.convert.str_type,
        "V": typ
    }, self.ctx)


def _build_namedtuple(props, node, ctx):
  """Build an InterpreterClass representing the namedtuple."""

  # TODO(mdemello): Fix this to support late types.
  if props.fields and props.fields[0].typ:
    field_types_union = abstract.Union([f.typ for f in props.fields], ctx)
  else:
    field_types_union = ctx.convert.none_type

  members = {f.name: f.typ.instantiate(node) for f in props.fields}

  # NOTE: We add the full list of private methods to all namedtuples.
  # Technically collections.namedtuple has a smaller set.
  # collections.namedtuple has: __dict__, __slots__ and _fields.
  # typing.NamedTuple adds: _field_types, __annotations__ and _field_defaults.
  # __slots__ and _fields are tuples containing the names of the fields.
  slots = tuple(ctx.convert.build_string(node, f.name) for f in props.fields)
  members["__slots__"] = ctx.convert.build_tuple(node, slots)
  members["_fields"] = ctx.convert.build_tuple(node, slots)

  odict = _DictBuilder(ctx)
  # __dict__ and _field_defaults are both OrderedDicts of
  # { field_name: field_type_instance }
  field_dict_cls = odict.make(field_types_union)
  members["__dict__"] = field_dict_cls.instantiate(node)
  members["_field_defaults"] = field_dict_cls.instantiate(node)

  # _field_types and __annotations__ are both OrderedDicts of
  # { field_name: field_type }
  # Note that ctx.make_class will take care of adding the __annotations__
  # member.
  field_types_cls = odict.make(ctx.convert.type_type)
  members["_field_types"] = field_types_cls.instantiate(node)

  # __new__
  # We set the bound on this TypeParameter later. This gives __new__ the
  # signature: def __new__(cls: Type[_Tname], ...) -> _Tname, i.e. the same
  # signature that visitor.CreateTypeParametersForSignatures would create.
  # This allows subclasses of the NamedTuple to get the correct type from
  # their constructors.
  # The TypeParameter name is built from the class name and field names to avoid
  # name clashes with other namedtuples.
  cls_type_param_name = (
      visitors.CreateTypeParametersForSignatures.PREFIX +
      escape.pack_namedtuple(props.name, [f.name for f in props.fields]))
  cls_type_param = abstract.TypeParameter(cls_type_param_name, ctx, bound=None)
  cls_type = abstract.ParameterizedClass(ctx.convert.type_type,
                                         {abstract_utils.T: cls_type_param},
                                         ctx)

  params = [Param(f.name, f.typ) for f in props.fields]
  members["__new__"] = overlay_utils.make_method(
      ctx,
      node,
      name="__new__",
      self_param=Param("cls", cls_type),
      params=params,
      return_type=cls_type_param,
  )

  # __init__
  members["__init__"] = overlay_utils.make_method(
      ctx,
      node,
      name="__init__",
      varargs=Param("args"),
      kwargs=Param("kwargs"))

  heterogeneous_tuple_type_params = dict(enumerate(f.typ for f in props.fields))
  heterogeneous_tuple_type_params[abstract_utils.T] = field_types_union
  # Representation of the to-be-created NamedTuple as a typing.Tuple.
  heterogeneous_tuple_type = abstract.TupleClass(
      ctx.convert.tuple_type, heterogeneous_tuple_type_params, ctx)

  # _make
  # _make is a classmethod, so it needs to be wrapped by
  # special_builtins.ClassMethodInstance.
  # Like __new__, it uses the _Tname TypeVar.
  sized_cls = ctx.convert.name_to_value("typing.Sized")
  iterable_type = abstract.ParameterizedClass(
      ctx.convert.name_to_value("typing.Iterable"),
      {abstract_utils.T: field_types_union}, ctx)
  cls_type = abstract.ParameterizedClass(ctx.convert.type_type,
                                         {abstract_utils.T: cls_type_param},
                                         ctx)
  len_type = abstract.CallableClass(
      ctx.convert.name_to_value("typing.Callable"), {
          0: sized_cls,
          abstract_utils.ARGS: sized_cls,
          abstract_utils.RET: ctx.convert.int_type
      }, ctx)
  params = [
      Param("iterable", iterable_type),
      Param("new").unsolvable(ctx, node),
      Param("len", len_type).unsolvable(ctx, node)
  ]
  make = overlay_utils.make_method(
      ctx,
      node,
      name="_make",
      params=params,
      self_param=Param("cls", cls_type),
      return_type=cls_type_param)
  make_args = function.Args(posargs=(make,))
  _, members["_make"] = ctx.special_builtins["classmethod"].call(
      node, None, make_args)

  # _replace
  # Like __new__, it uses the _Tname TypeVar. We have to annotate the `self`
  # param to make sure the TypeVar is substituted correctly.
  members["_replace"] = overlay_utils.make_method(
      ctx,
      node,
      name="_replace",
      self_param=Param("self", cls_type_param),
      return_type=cls_type_param,
      kwargs=Param("kwds", field_types_union))

  # __getnewargs__
  members["__getnewargs__"] = overlay_utils.make_method(
      ctx,
      node,
      name="__getnewargs__",
      return_type=heterogeneous_tuple_type)

  # __getstate__
  members["__getstate__"] = overlay_utils.make_method(
      ctx, node, name="__getstate__")

  # _asdict
  members["_asdict"] = overlay_utils.make_method(
      ctx, node, name="_asdict", return_type=field_dict_cls)

  # Finally, make the class.
  cls_dict = abstract.Dict(ctx)
  cls_dict.update(node, members)

  if ctx.options.strict_namedtuple_checks:
    # Enforces type checking like Tuple[...]
    superclass_of_new_type = heterogeneous_tuple_type.to_variable(node)
  else:
    superclass_of_new_type = ctx.convert.tuple_type.to_variable(node)
  if props.bases:
    final_bases = []
    for base in props.bases:
      if any(b.full_name == "typing.NamedTuple" for b in base.data):
        final_bases.append(superclass_of_new_type)
      else:
        final_bases.append(base)
  else:
    final_bases = [superclass_of_new_type]
    # This NamedTuple is being created via a function call. We manually
    # construct an annotated_locals entry for it so that __annotations__ is
    # initialized properly for the generated class.
    ctx.vm.annotated_locals[props.name] = {
        f.name: abstract_utils.Local(node, None, f.typ, None, ctx)
        for f in props.fields
    }

  cls_props = class_mixin.ClassBuilderProperties(
      name_var=ctx.convert.build_string(node, props.name),
      bases=final_bases,
      class_dict_var=cls_dict.to_variable(node))
  node, cls_var = ctx.make_class(node, cls_props)
  cls = cls_var.data[0]

  # Now that the class has been made, we can complete the TypeParameter used
  # by __new__, _make and _replace.
  cls_type_param.bound = cls

  # set __new__.__defaults__
  defaults = [f.default for f in props.fields if f.default is not None]
  defaults = ctx.convert.build_tuple(node, defaults)
  node, new_attr = ctx.attribute_handler.get_attribute(
      node, cls, "__new__")
  new_attr = abstract_utils.get_atomic_value(new_attr)
  node = ctx.attribute_handler.set_attribute(
      node, new_attr, "__defaults__", defaults)

  ctx.vm.trace_classdef(cls_var)
  return node, cls_var
