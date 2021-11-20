"""Implementation of types from Python 2's collections library."""

from keyword import iskeyword  # pylint: disable=g-importing-member
import textwrap

from pytype import overlay
from pytype import utils
from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.pyi import parser
from pytype.pytd import escape
from pytype.pytd import pytd
from pytype.pytd import visitors


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


class CollectionsOverlay(overlay.Overlay):
  """A custom overlay for the 'collections' module."""

  def __init__(self, ctx):
    """Initializes the CollectionsOverlay.

    This function loads the AST for the collections module, which is used to
    access type information for any members that are not explicitly provided by
    the overlay. See get_attribute in attribute.py for how it's used.

    Args:
      ctx: An instance of context.Context.
    """
    # collections_overlay contains all the members that have special definitions
    member_map = collections_overlay.copy()
    ast = ctx.loader.import_name("collections")
    super().__init__(ctx, "collections", member_map, ast)


class NamedTupleBuilder(abstract.PyTDFunction):
  """Factory for creating collections.namedtuple typing information."""

  @classmethod
  def make(cls, name, ctx, pyval=None):
    # Loading the ast should be memoized after the import in CollectionsOverlay
    collections_ast = ctx.loader.import_name("collections")
    # Subclasses of NamedTupleBuilder need a different pyval.
    if not pyval:
      pyval = collections_ast.Lookup("collections.namedtuple")
    self = super().make(name, ctx, "collections", pyval=pyval)
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

    # Small helper function for checking typename and field names.
    def not_valid(field_name):
      return (not all(c.isalnum() or c == "_" for c in field_name)
              or iskeyword(field_name)
              or not field_name  # catches empty string, etc.
              or field_name[0].isdigit())

    if not_valid(typename):
      raise ValueError(typename)

    valid_fields = list(field_names)
    seen = set()
    for idx, name in enumerate(field_names):
      if not_valid(name) or name.startswith("_") or name in seen:
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
      If a abstract_utils.ConversionError occurs or if field names are invalid,
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


collections_overlay = {
    "namedtuple": overlay.build("namedtuple", NamedTupleBuilder.make),
}
