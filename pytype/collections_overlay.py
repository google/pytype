"""Implementation of types from Python 2's collections library."""
import collections
import inspect
# TODO(tsudol): Python 2 and Python 3 have different keyword lists.
from keyword import iskeyword

from pytype import abstract
from pytype import overlay
from pytype.pytd import pytd


class CollectionsOverlay(overlay.Overlay):
  """A custom overlay for the 'collections' module."""

  is_lazy = True  # uses our _convert_member method.

  def __init__(self, vm):
    """Initializes the CollectionsOverlay.

    This function loads the AST for the collections module, which is used to
    access type information for any members that are not explicitly provided by
    the overlay. See get_attribute in attribute.py for how it's used.

    Args:
      vm: An instance of vm.VirtualMachine.
    """
    # collections_overlay contains all the members that have special definitions
    member_map = collections_overlay.copy()
    ast = vm.loader.import_name("collections")
    super(CollectionsOverlay, self).__init__(vm, "collections", member_map, ast)


class NamedTupleInstance(abstract.PyTDClass):
  """Protects the underlying class from having its official name changed.

  We consider it bad practice to store namedtuples in variables with
  different names than the namedtuple itself, e.g.:
  >>> Foo = collections.namedtuple("Bar", ...)

  This ends up erasing type information. In order to enforce this rule, this
  class overrides update_official_name to enforce the namedtuple's given
  name, and then logs an error to alert the user.
  """

  def __init__(self, name, pytd_cls, vm):
    super(NamedTupleInstance, self).__init__(name, pytd_cls, vm)

  def to_pytd_def(self, unused_node, unused_name):
    return self.pytd_cls

  def update_official_name(self, new_name):
    if new_name != self.name:
      self.vm.errorlog.invalid_namedtuple_name(self.vm.frames, self.name,
                                               new_name)


class NamedTupleBuilder(abstract.Function):
  """Factory for creating collections.namedtuple typing information."""

  def __init__(self, name, vm):
    super(NamedTupleBuilder, self).__init__(name, vm)
    # Loading the ast should be memoized after the import in CollectionsOverlay
    self.collections_ast = vm.loader.import_name("collections")
    self.namedtuple_members = {
        "_asdict": self._asdict,
        "__dict__": self._dict,
        "_fields": self._fields,
        "__getnewargs__": self._getnewargs,
        "__getstate__": self._getstate,
        "_make": self._make,
        "__new__": self._new,
        "_replace": self._replace,
        "__slots__": self._slots,
    }

  def _get_builtin_classtype(self, name):
    fullname = "__builtin__.%s" % name
    return pytd.ClassType(fullname, self.vm.loader.builtins.Lookup(fullname))

  def _get_typing_classtype(self, name):
    fullname = "typing.%s" % name
    return pytd.ClassType(fullname, self.vm.loader.typing.Lookup(fullname))

  def _build_tupletype(self, *param_types):
    if not param_types:
      param_types = (pytd.NothingType(),)
    inner = self._get_builtin_classtype("tuple")
    return pytd.TupleType(inner, param_types)

  def _build_param(self, name, typ, kwonly=False, optional=False, mutated=None):
    return pytd.Parameter(name, typ, kwonly, optional, mutated)

  def _build_sig(self, params, ret_type, star=None, starstar=None, exc=(),
                 template=()):
    return pytd.Signature(params, star, starstar, ret_type, exc, template)

  def _selfparam(self, typ=None):
    return self._build_param("self", typ or pytd.AnythingType())

  def _getargs(self, node, args):
    """Extracts the typename, field_names and rename arguments.

    collections.namedtuple takes potentially 4 arguments, but we only care about
    three of them. This function checks the argument count and ensures multiple
    values aren't passed for 'verbose' and 'rename'.

    Args:
      node: The current CFG node. Used by _match_args.
      args: An abstract.FunctionArgs object

    Returns:
      A tuple containing the typename, field_names and rename arguments passed
      to this call to collections.namedtuple.

    Raises:
      abstract.FailedFunctionCall: The arguments do not match those needed by
        the function call. See also: abstract.PyTDFunction._match_args().
      abstract.ConversionError: One of the arguments could not be extracted.
        Typically occurs if typename or one of the field names is in unicode.
    """

    # abstract.PyTDFunction._match_args checks the args for this call.
    namedtuple_func = self.vm.convert.constant_to_value(
        self.collections_ast.Lookup("collections.namedtuple"), (), node)
    namedtuple_func._match_args(node, args)  # pylint: disable=protected-access

    # inspect.callargs returns a dictionary mapping the argument names to
    # the values in args.posargs and args.namedargs (or False if there is no
    # value given).
    callargs = inspect.getcallargs(collections.namedtuple, *args.posargs,
                                   **args.namedargs)

    # The name of the namedtuple class is the first arg (a Variable)
    # We need the actual Variable later, so we'll just return name_var and
    # extract the name itself later.
    name_var = callargs["typename"]

    # The fields are also a Variable, which stores the field names as Variables.
    # Extract the list itself, we don't need the wrapper.
    fields_var = callargs["field_names"]
    fields = abstract.get_atomic_python_constant(fields_var)
    # namedtuple fields can be given as a single string, e.g. "a, b, c" or as a
    # list [Variable('a'), Variable('b'), Variable('c')].
    # We just want a list of strings.
    if isinstance(fields, (str, unicode)):
      field_names = fields.replace(",", " ").split()
    else:
      field_names = [abstract.get_atomic_python_constant(f) for f in fields]

    # namedtuple also takes a "verbose" argument, but we don't care about that.

    # rename will take any problematic field names and give them a new name.
    # Like the other args, it's stored as a Variable, but we want just a bool.
    if callargs["rename"]:
      rename = abstract.get_atomic_python_constant(callargs["rename"])
    else:
      rename = False

    return name_var, field_names, rename

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
    class. Finally, the pytd.Class is wrapped in a NamedTupleInstance, a
    specialized subclass of abstract.PyTDClass.

    If incorrect arguments are passed, a subclass of abstract.FailedFunctionCall
    will be raised. Other cases may raise abstract.ConversionError exceptions,
    such as when the arguments are in unicode or any of the arguments have
    multiple bindings, but these are caught and return Any. This also occurs if
    an argument to namedtuple is invalid, e.g. a keyword is used as a field name
    and rename is False.

    Arguments:
      node: the current CFG node
      _: the func binding, ignored.
      args: an abstract.FunctionArgs instance

    Returns:
      a tuple of the given CFG node and a NamedTupleInstance instance (wrapped
      in a Variable) representing the constructed namedtuple class.
      If a abstract.ConversionError occurs or if field names are invalid, this
      function returns Unsolvable (in a Variable) instead of a
      NamedTupleInstance

    Raises:
      abstract.FailedFunctionCall: Raised by _getargs if any of the arguments
        do not match the function signature.
    """
    # If we can't extract the arguments, we take the easy way out and return Any
    try:
      name_var, field_names, rename = self._getargs(node, args)
    except abstract.ConversionError:
      return node, self.vm.convert.unsolvable.to_variable(node)

    # We need the bare name for a few things, so pull that out now.
    # The same unicode issue can strike here, so again return Any.
    try:
      name = abstract.get_atomic_python_constant(name_var)
    except abstract.ConversionError:
      return node, self.vm.convert.unsolvable.to_variable(node)

    # namedtuple does some checking and optionally renaming of field names,
    # so we do too.
    try:
      field_names = self._validate_and_rename_args(name, field_names, rename)
    except ValueError as e:
      self.vm.errorlog.invalid_namedtuple_arg(self.vm.frames, e.message)
      return node, self.vm.convert.unsolvable.to_variable(node)

    # A truly well-formed pyi for the namedtuple will have references to the new
    # namedtuple class itself for all `self` params and as the return type for
    # methods like __new__, _replace and _make. In order to do that, we need a
    # ClassType.
    cls_type = pytd.ClassType(name)

    # Use a dictionary to store all members, which are either pytd.Constant or
    # pytd.Function. This makes it easy to build the pytd.Class
    members = {mem: self.namedtuple_members[mem](field_names, cls_type)
               for mem in self.namedtuple_members}
    # Each namedtuple field should be a @property, but in pyi files those are
    # just represented as Constants. We know nothing about their types.
    for field in field_names:
      members[field] = pytd.Constant(field, pytd.AnythingType())

    cls = pytd.Class(
        name=name,
        metaclass=None,
        parents=(self._get_builtin_classtype("tuple"),),
        methods=tuple(members[mem] for mem in members
                      if isinstance(members[mem], pytd.Function)),
        constants=tuple(members[mem] for mem in members
                        if isinstance(members[mem], pytd.Constant)),
        template=(),
    )
    cls_type.cls = cls

    instance = NamedTupleInstance(name, cls, self.vm)
    return node, instance.to_variable(node)

  # The following functions are for making the members of namedtuples.
  # Each one returns the AST for a member (either a Constant or a Function)
  # that's been customized for this particular namedtuple.
  def _asdict(self, field_names, cls_type):
    params = (self._selfparam(cls_type),)
    ret_type = pytd.GenericType(
        pytd.ClassType(
            "collections.OrderedDict",
            self.collections_ast.Lookup("collections.OrderedDict")),
        (self._get_builtin_classtype("str"), pytd.AnythingType()))
    sig = self._build_sig(params, ret_type)
    return pytd.Function("_asdict", (sig,), pytd.METHOD)

  def _dict(self, field_names, cls_type):
    # Can't really do @property()s with pytd, unfortunately
    dict_type = pytd.GenericType(
        pytd.ClassType(
            "collections.OrderedDict",
            self.collections_ast.Lookup("collections.OrderedDict")),
        (self._get_builtin_classtype("str"), pytd.AnythingType()))
    return pytd.Constant("__dict__", dict_type)

  def _slots(self, field_names, cls_type):
    return pytd.Constant("__slots__", self._build_tupletype())

  def _fields(self, field_names, cls_type):
    str_type = self._get_builtin_classtype("str")
    typ = self._build_tupletype(*([str_type] * len(field_names)))
    return pytd.Constant("_fields", typ)

  def _getnewargs(self, field_names, cls_type):
    params = (self._selfparam(cls_type),)
    # If there are no fields, the return type is Tuple[nothing]
    if not field_names:
      ret_type = self._build_tupletype()
    else:
      p = [pytd.AnythingType() for _ in field_names]
      ret_type = self._build_tupletype(*p)
    sig = self._build_sig(params, ret_type)
    return pytd.Function("__getnewargs__", (sig,), pytd.METHOD)

  def _getstate(self, field_names, cls_type):
    params = (self._selfparam(cls_type),)
    ret_type = self._get_builtin_classtype("NoneType")
    sig = self._build_sig(params, ret_type)
    return pytd.Function("__getstate__", (sig,), pytd.METHOD)

  def _replace(self, field_names, cls_type):
    params = (self._selfparam(cls_type),)
    kwdparam = self._build_param("kwds", pytd.AnythingType(), optional=True)
    sig = self._build_sig(params, cls_type, starstar=kwdparam)
    return pytd.Function("_replace", (sig,), pytd.METHOD)

  def _make(self, field_names, cls_type):
    # "new" should be something like Callable[[type, Iterable], object] (where
    # the result is an object of the type given in the first argument). But
    # all that really matters is that it's Callable.
    # TODO(tsudol): "new" should be a Callable (or Callable[[Any, Iterable],
    # object])
    new_param = self._build_param("new", pytd.AnythingType(), optional=True)
    len_param = self._build_param(
        "len",
        pytd.CallableType(
            self._get_typing_classtype("Callable"),
            (self._get_typing_classtype("Iterable"),
             self._get_builtin_classtype("int")),
        ),
        optional=True)
    params = (
        # This should be Type[cls_type]
        self._build_param("cls", pytd.AnythingType()),
        self._build_param("iterable", self._get_typing_classtype("Iterable")),
        new_param, len_param)
    sig = self._build_sig(params, cls_type)
    return pytd.Function("_make", (sig,), pytd.CLASSMETHOD)

  def _new(self, field_names, cls_type):
    fields = tuple([
        self._build_param(name, pytd.AnythingType())
        for name in field_names
    ])
    params = (
        self._build_param("cls", pytd.AnythingType()),
    ) + fields
    sig = self._build_sig(params, cls_type)
    return pytd.Function("__new__", (sig,), pytd.STATICMETHOD)


collections_overlay = {
    "namedtuple": NamedTupleBuilder,
}
