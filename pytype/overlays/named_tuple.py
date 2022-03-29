"""Implementation of named tuples."""

import dataclasses
from keyword import iskeyword  # pylint: disable=g-importing-member
import textwrap

from typing import Any, List

from pytype import overlay_utils
from pytype import utils
from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.abstract import function
from pytype.overlays import classgen
from pytype.pyi import parser
from pytype.pytd import escape
from pytype.pytd import pytd
from pytype.pytd import visitors


# type alias
Param = overlay_utils.Param


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

  def validate_and_rename_fields(self, rename):
    """Validate and rename self.fields."""
    # namedtuple field names have some requirements:
    # - must not be a Python keyword
    # - must consist of only alphanumeric characters and "_"
    # - must not start with "_" or a digit
    # Basically, they're valid Python identifiers that don't start with "_" or a
    # digit. Also, there can be no duplicate field names.
    # Typename has the same requirements, except it can start with "_".
    # If rename is true, any invalid field names are changed to "_%d". For
    # example, "abc def ghi abc" becomes "abc _1 def _3" because "def" is a
    # keyword and "abc" is a duplicate.
    # The typename cannot be changed.

    if _invalid_name(self.name):
      raise ValueError(self.name)

    seen = set()
    for idx, f in enumerate(self.fields):
      if _invalid_name(f.name) or f.name.startswith("_") or f.name in seen:
        if rename:
          f.name = "_%d" % idx
        else:
          raise ValueError(f.name)
      seen.add(f.name)


def _repeat_type(type_str, n):
  return ", ".join((type_str,) * n) if n else "()"


def namedtuple_ast(name, fields, defaults, options):
  """Make an AST with a namedtuple definition for the given name and fields.

  Args:
    name: The namedtuple name.
    fields: The namedtuple fields.
    defaults: Sequence of booleans, whether each field has a default.
    options: A config.Options object.

  Returns:
    A pytd.TypeDeclUnit with the namedtuple definition in its classes.
  """

  typevar = visitors.CreateTypeParametersForSignatures.PREFIX + name
  num_fields = len(fields)
  field_defs = "\n  ".join(
      "%s = ...  # type: typing.Any" % field for field in fields)
  fields_as_parameters = "".join(
      ", " + field + (" = ..." if default else "")
      for field, default in zip(fields, defaults))
  field_names_as_strings = ", ".join(repr(field) for field in fields)
  if options.strict_namedtuple_checks:
    tuple_superclass_type = "typing.Tuple[{}]".format(
        _repeat_type("typing.Any", num_fields))
  else:
    tuple_superclass_type = "tuple"

  nt = textwrap.dedent("""
    {typevar} = TypeVar("{typevar}", bound={name})
    class {name}({tuple_superclass_type}):
      __dict__ = ...  # type: collections.OrderedDict[str, typing.Any]
      __slots__ = [{field_names_as_strings}]
      _fields = ...  # type: typing.Tuple[{repeat_str}]
      {field_defs}
      def __getnewargs__(self) -> typing.Tuple[{repeat_any}]: ...
      def __getstate__(self) -> None: ...
      def __init__(self, *args, **kwargs) -> None: ...
      def __new__(
          cls: typing.Type[{typevar}]{fields_as_parameters}) -> {typevar}: ...
      def _asdict(self) -> collections.OrderedDict[str, typing.Any]: ...
      @classmethod
      def _make(cls: typing.Type[{typevar}],
                iterable: typing.Iterable,
                new = ...,
                len: typing.Callable[[typing.Sized], int] = ...
      ) -> {typevar}: ...
      def _replace(self: {typevar}, **kwds) -> {typevar}: ...
  """).format(
      typevar=typevar,
      name=name,
      repeat_str=_repeat_type("str", num_fields),
      tuple_superclass_type=tuple_superclass_type,
      field_defs=field_defs,
      repeat_any=_repeat_type("typing.Any", num_fields),
      fields_as_parameters=fields_as_parameters,
      field_names_as_strings=field_names_as_strings)
  return parser.parse_string(
      nt, options=parser.PyiOptions.from_toplevel_options(options))


class NamedTupleBuilder(abstract.PyTDFunction):
  """Factory for creating collections.namedtuple typing information."""

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

  def _get_builtin_classtype(self, name):
    fullname = "builtins.%s" % name
    return pytd.ClassType(fullname, self.ctx.loader.builtins.Lookup(fullname))

  def _get_typing_classtype(self, name):
    fullname = "typing.%s" % name
    return pytd.ClassType(fullname, self.ctx.loader.typing.Lookup(fullname))

  def _get_known_types_mapping(self):
    # The mapping includes only the types needed to define a namedtuple.
    builtin_classes = (
        "dict", "int", "NoneType", "object", "str", "tuple", "type")
    typing_classes = ("Callable", "Iterable", "Sized")
    d = {c: self._get_builtin_classtype(c) for c in builtin_classes}
    for c in typing_classes:
      d["typing." + c] = self._get_typing_classtype(c)
    d["collections.OrderedDict"] = pytd.ClassType(
        "collections.OrderedDict",
        self.collections_ast.Lookup("collections.OrderedDict"))
    return d

  def _getargs(self, node, args):
    """Extracts the typename, field_names and rename arguments.

    collections.namedtuple takes potentially 4 arguments, but we only care about
    three of them. This function checks the argument count and ensures multiple
    values aren't passed for 'verbose' and 'rename'.

    Args:
      node: The current CFG node. Used by match_args.
      args: A function.Args object

    Returns:
      A tuple containing the typename, field_names, defaults, and rename
      arguments passed to this call to collections.namedtuple. defaults is
      postprocessed from a sequence of defaults to a sequence of bools
      describing whether each field has a default (e.g., for
        collections.namedtuple('X', field_names=['a', 'b'], defaults=[0])
      this method will return [False, True] for defaults to indicate that 'a'
      does not have a default while 'b' does).

    Raises:
      function.FailedFunctionCall: The arguments do not match those needed by
        the function call. See also: abstract.PyTDFunction.match_args().
      abstract_utils.ConversionError: One of the args could not be extracted.
        Typically occurs if typename or one of the field names is in unicode.
    """

    # abstract.PyTDFunction.match_args checks the args for this call.
    self.match_args(node, args)

    # namedtuple only has one signature
    sig, = self.signatures
    callargs = {name: var for name, var, _ in sig.signature.iter_args(args)}

    # The name of the namedtuple class is the first arg (a Variable)
    # We need the actual Variable later, so we'll just return name_var and
    # extract the name itself later.
    name_var = callargs["typename"]

    # The fields are also a Variable, which stores the field names as Variables.
    # Extract the list itself, we don't need the wrapper.
    fields_var = callargs["field_names"]
    fields = abstract_utils.get_atomic_python_constant(fields_var)
    # namedtuple fields can be given as a single string, e.g. "a, b, c" or as a
    # list [Variable('a'), Variable('b'), Variable('c')].
    # We just want a list of strings.
    if isinstance(fields, (bytes, str)):
      fields = utils.native_str(fields)
      field_names = fields.replace(",", " ").split()
    else:
      field_names = [abstract_utils.get_atomic_python_constant(f)
                     for f in fields]
      field_names = [utils.native_str(f) for f in field_names]

    if "defaults" in callargs:
      default_vars = abstract_utils.get_atomic_python_constant(
          callargs["defaults"])
      num_defaults = len(default_vars)
      defaults = [False] * (len(fields) - num_defaults) + [True] * num_defaults
    else:
      defaults = [False] * len(fields)

    # namedtuple also takes a "verbose" argument, but we don't care about that.

    # rename will take any problematic field names and give them a new name.
    # Like the other args, it's stored as a Variable, but we want just a bool.
    if "rename" in callargs:
      rename = abstract_utils.get_atomic_python_constant(callargs["rename"])
    else:
      rename = False

    return name_var, field_names, defaults, rename

  def _validate_and_rename_args(self, typename, field_names, rename):
    # See comment in NamedTupleProperties.validate_and_rename_fields

    if _invalid_name(typename):
      raise ValueError(typename)

    valid_fields = list(field_names)
    seen = set()
    for idx, name in enumerate(field_names):
      if _invalid_name(name) or name.startswith("_") or name in seen:
        if rename:
          valid_fields[idx] = "_%d" % idx
        else:
          raise ValueError(name)
      seen.add(name)
    return valid_fields

  def call(self, node, _, args):
    """Creates a namedtuple class definition.

    Performs the same argument checking as collections.namedtuple, e.g. making
    sure field names don't start with _ or digits, making sure no keywords are
    used for the typename or field names, and so on. Because the methods of the
    class have to be changed to match the number and names of the fields, we
    construct pytd.Function and pytd.Constant instances for each member of the
    class. Finally, the pytd.Class is wrapped in an abstract.PyTDClass.

    If incorrect arguments are passed, a subclass of function.FailedFunctionCall
    will be raised. Other cases may raise abstract_utils.ConversionError
    exceptions, such as when the arguments are in unicode or any of the
    arguments have multiple bindings, but these are caught and return Any. This
    also occurs if an argument to namedtuple is invalid, e.g. a keyword is used
    as a field name and rename is False.

    Arguments:
      node: the current CFG node
      _: the func binding, ignored.
      args: a function.Args instance

    Returns:
      a tuple of the given CFG node and an abstract.PyTDClass instance (wrapped
      in a Variable) representing the constructed namedtuple class.
      If an abstract_utils.ConversionError occurs or if field names are invalid,
      this function returns Unsolvable (in a Variable) instead of a PyTDClass.

    Raises:
      function.FailedFunctionCall: Raised by _getargs if any of the arguments
        do not match the function signature.
    """
    # If we can't extract the arguments, we take the easy way out and return Any
    try:
      name_var, field_names, defaults, rename = self._getargs(node, args)
    except abstract_utils.ConversionError:
      return node, self.ctx.new_unsolvable(node)

    # We need the bare name for a few things, so pull that out now.
    # The same unicode issue can strike here, so again return Any.
    try:
      name = abstract_utils.get_atomic_python_constant(name_var)
    except abstract_utils.ConversionError:
      return node, self.ctx.new_unsolvable(node)

    # namedtuple does some checking and optionally renaming of field names,
    # so we do too.
    try:
      field_names = self._validate_and_rename_args(name, field_names, rename)
    except ValueError as e:
      self.ctx.errorlog.invalid_namedtuple_arg(self.ctx.vm.frames,
                                               utils.message(e))
      return node, self.ctx.new_unsolvable(node)

    name = escape.pack_namedtuple(name, field_names)
    ast = namedtuple_ast(name, field_names, defaults, options=self.ctx.options)
    mapping = self._get_known_types_mapping()

    # A truly well-formed pyi for the namedtuple will have references to the new
    # namedtuple class itself for all `self` params and as the return type for
    # methods like __new__, _replace and _make. In order to do that, we need a
    # ClassType.
    cls_type = pytd.ClassType(name)
    mapping[name] = cls_type

    cls = ast.Lookup(name).Visit(visitors.ReplaceTypes(mapping))
    cls_type.cls = cls

    # Make sure all NamedType nodes have been replaced by ClassType nodes with
    # filled cls pointers.
    cls.Visit(visitors.VerifyLookup())

    # We can't build the PyTDClass directly, and instead must run it through
    # convert.constant_to_value first, for caching.
    instance = self.ctx.convert.constant_to_value(cls, {}, self.ctx.root_node)
    self.ctx.vm.trace_namedtuple(instance)
    return node, instance.to_variable(node)


class NamedTupleFuncBuilder(NamedTupleBuilder):
  """Factory for creating typing.NamedTuple classes."""

  _fields_param: function.BadParam

  @classmethod
  def make(cls, ctx):
    typing_ast = ctx.loader.import_name("typing")
    # Because NamedTuple is a special case for the pyi parser, typing.pytd has
    # "_NamedTuple" instead. Replace the name of the returned function so that
    # error messages will correctly display "typing.NamedTuple".
    pyval = typing_ast.Lookup("typing._NamedTuple")
    pyval = pyval.Replace(name="typing.NamedTuple")
    self = super().make("NamedTuple", ctx, pyval)
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
      raise function.WrongArgTypes(sig.signature, args, self.ctx,
                                   self._fields_param)
    # The fields is a list of tuples, so we need to deeply unwrap them.
    fields = [abstract_utils.get_atomic_python_constant(t) for t in fields]
    # We need the actual string for the field names and the BaseValue
    # for the field types.
    names = []
    types = []
    for field in fields:
      if isinstance(field, str):
        # Since str matches Sequence, we have to manually check for it.
        raise function.WrongArgTypes(sig.signature, args, self.ctx,
                                     self._fields_param)
      if (len(field) != 2 or
          any(not self._is_str_instance(v) for v in field[0].data)):
        # Note that we don't need to check field[1] because both 'str'
        # (forward reference) and 'type' are valid for it.
        raise function.WrongArgTypes(sig.signature, args, self.ctx,
                                     self._fields_param)
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
    return name_var, names, types

  def call(self, node, _, args, bases=None):
    try:
      name_var, field_names, field_types = self._getargs(node, args)
    except abstract_utils.ConversionError:
      return node, self.ctx.new_unsolvable(node)

    try:
      name = abstract_utils.get_atomic_python_constant(name_var)
    except abstract_utils.ConversionError:
      return node, self.ctx.new_unsolvable(node)

    try:
      field_names = self._validate_and_rename_args(name, field_names, False)
    except ValueError as e:
      self.ctx.errorlog.invalid_namedtuple_arg(self.ctx.vm.frames,
                                               utils.message(e))
      return node, self.ctx.new_unsolvable(node)

    annots = self.ctx.annotation_utils.convert_annotations_list(
        node, zip(field_names, field_types))
    field_types = [
        annots.get(field_name, self.ctx.convert.unsolvable)
        for field_name in field_names
    ]
    fields = [Field(n, t) for n, t in zip(field_names, field_types)]
    props = NamedTupleProperties(name, fields, bases)
    node, cls_var = _build_namedtuple(props, node, self.ctx)

    self.ctx.vm.trace_classdef(cls_var)
    return node, cls_var


class NamedTupleClass(abstract.PyTDClass):
  """Representation of NamedTuple classes."""

  def __init__(self, props, ctx):
    self.props = props
    typing_ast = ctx.loader.import_name("typing")
    # Because NamedTuple is a special case for the pyi parser, typing.pytd has
    # "_NamedTuple" instead. Replace the name of the returned function so that
    # error messages will correctly display "typing.NamedTuple".
    pyval = typing_ast.Lookup("typing._NamedTuple")
    pyval = pyval.Replace(name="typing.NamedTuple")
    super().__init__(props.name, pyval, ctx)
    self.init_method = self._make_init(props)

  def __repr__(self):
    return f"NamedTupleClass({self.name})"


class NamedTupleClassBuilder(abstract.PyTDClass):
  """Factory for creating typing.NamedTuple classes."""

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
      # set __new__.__defaults__
      defaults = [f.default for f in props.fields if f.default is not None]
      defaults = self.ctx.convert.build_tuple(node, defaults)
      node, new_attr = self.ctx.attribute_handler.get_attribute(
          node, cls_val, "__new__")
      new_attr = abstract_utils.get_atomic_value(new_attr)
      node = self.ctx.attribute_handler.set_attribute(
          node, new_attr, "__defaults__", defaults)

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


# Small helper function for checking typename and field names.
def _invalid_name(field_name):
  return (not all(c.isalnum() or c == "_" for c in field_name)
          or iskeyword(field_name)
          or not field_name  # catches empty string, etc.
          or field_name[0].isdigit())


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
  cls_type_param = abstract.TypeParameter(
      visitors.CreateTypeParametersForSignatures.PREFIX + props.name,
      ctx,
      bound=None)
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

  node, cls_var = ctx.make_class(
      node=node,
      name_var=ctx.convert.build_string(node, props.name),
      bases=final_bases,
      class_dict_var=cls_dict.to_variable(node),
      cls_var=None)
  cls = cls_var.data[0]

  # Now that the class has been made, we can complete the TypeParameter used
  # by __new__, _make and _replace.
  cls_type_param.bound = cls

  return node, cls_var
