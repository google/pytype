"""Fast PYI parser."""

import collections

from pytype.pyi import parser_ext
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd.parse import parser as legacy_parser
from pytype.pytd.parse import visitors

# This module will eventually replace pytype/pytd/parse/parser.py.  In general
# the action code in _Parser mimics that of similar methods in _TypeDeclParser,
# including odd corner cases and TODOs.  Maintaining a similar structure
# reduces the chance of introducing new errors.  Once the migration is complete
# and the legacy parser is removed we can consider other cleanups.  For now
# any such potential fixes should be marked as TODOs.
#
# TODO(dbaum): Remove the preceding comment once the parser is complete.

_DEFAULT_VERSION = (2, 7, 6)


_Params = collections.namedtuple("_", ["required",
                                       "starargs", "starstarargs",
                                       "has_bare_star"])

_NameAndSig = collections.namedtuple("_", ["name", "signature",
                                           "decorators", "external_code"])


# We are currently re-using a handful of helper methods from the legacy parser.
# Once the grammar is complete the methods can be cleaned up and ported to
# this module.  The methods are instance methods on _TypeDeclParser but do
# not require any state from actual parsing (they could have just as easily
# been written as @staticmethods or module functions).
# TODO(dbaum): Get rid of this.
_LEGACY = legacy_parser._TypeDeclParser()  # pylint: disable=protected-access


_COMPARES = {
    "==": lambda x, y: x == y,
    "!=": lambda x, y: x != y,
    "<": lambda x, y: x < y,
    "<=": lambda x, y: x <= y,
    ">": lambda x, y: x > y,
    ">=": lambda x, y: x >= y,
}


class _ConditionScope(object):
  """State associated with a condition if/elif/else block."""

  def __init__(self, parent):
    self._parent = parent
    if parent is None:
      self._active = True
      # The value of _can_trigger doesn't really matter since apply_condition
      # shouldn't be called on the top scope.
      self._can_trigger = False
    else:
      # By default new scopes are inactive and can be triggered iff the
      # parent is active.
      self._active = False
      self._can_trigger = parent.active

  def apply_condition(self, value):
    """Apply the value to this scope.

    If the scope can be triggered and value is true, then the scope
    becomes active, otherwise the scope is not active.  Note that a scope
    can trigger at most once since triggering also clears _can_trigger.

    Args:
      value: a bool.
    """
    assert self._parent is not None
    if self._can_trigger and value:
      self._active = True
      self._can_trigger = False
    else:
      self._active = False

  @property
  def active(self):
    return self._active

  @property
  def parent(self):
    return self._parent


class ParseError(Exception):

  def __init__(self, msg, line=None):
    super(ParseError, self).__init__(msg)
    self._line = line

  @property
  def line(self):
    return self._line

  def __str__(self):
    s = self.message
    if self._line is not None:
      s += ", line %d" % self._line
    return s


class _Parser(object):
  """A class used to parse a single PYI file.

  The PYI parser is split into two parts: a low level parser implemented in
  in C++, and the high level parser written in Python.

  The low level parser calls the lexer (also in C++) determines which
  reductions to make, and performs simple actions such as building up lists or
  strings.  It relies on a "peer" to perform more complicated actions
  associated with construction of the AST.

  This class is the high level parser, which invokes the low level parser and
  serves as the peer for AST construction.  Thus it is both the caller and
  callee of the low level parser.

  The low level parser expects the following interface in its peer.

  Attributes that return constant objects:
    ELLIPSIS
    PARSE_ERROR
    NOTHING
    ANYTHING

  Methods used in AST construction:
    new_constant()
    add_alias_or_constant()
    add_import()
    new_type()
    new_union_type()
    new_function()
    new_external_function()
    new_named_tuple()
    regiser_class_name()
    add_class()
    if_begin()
    if_elif()
    if_else()
    if_end()

  Other methods:
    set_error_location()


  Error handling is a bit tricky because it is important to associate
  location information with errors, but undesireable to move location
  information around for every call between the low level parser and the
  peer.  As a compromise, when errors are detected (either by the low level
  parser or by the peer raising an exception), set_error_location() is called
  with current location information, then the the call to parse_ext.parse()
  raises an exception (either a ParseError or whatever else was raised by
  the peer in the first place).  The high level parser can thus save location
  information from set_error_location(), catch the exception raised by
  parse_ext.parse(), and raise a new exception that includes a location.

  Conditional pyi code (under an "if" statement) is handled similar to a
  preprocessor, discarding any statements under False conditions rather than
  representing the entire "if" tree in the AST.  This approach allows methods
  such as add_alias_or_constant() to have side effects provided that they
  first check to see if the enclosing scope is active.  There are four
  peer calls used to support conditions:

  if_begin(self, condition): This should be invoked after parsing the initial
      condition but before processing any enclosed definitions.  It establishes
      a new _ConditionScope based on the evaluation of condition.  It returns
      a bool indicating if the scope will now be active.

  if_elif(self, condition): This should be invoked after parsing the condition
      following an "elif", but before any subsequent definitions.  It evaluates
      the condition and changes the scope's state appropriately.  It returns
      a bool indicating if the scope will now be active.

  if_else(self): This should be invoked after parsing "else" but before any
      subsequent definitions.  The scope will become active if it hasn't
      triggered on any previous conditions.  It returns a bool indicating
      if the scope will now be active.

  if_end(self, clauses): This should be called at the end of the entire if
      statement where clauses is a list of (active, defs) pairs.  Active is
      the return value of the corresponding if_begin/if_elif/if_else call, and
      defs is a list of definitions within that block.  The function returns
      the list of defs that should be processed (i.e. the defs in the tuple
      where active was True, or [] if no such tuple is present).

  Conditions are represented by tuples (name, op, value), where name is a
  dotted name string, op is one of six comparisson strings ("==", "!=", "<",
  "<=", ">", ">="), and value is either a string or a tuple of three integers.
  """

  # Values for the parsing context.
  ELLIPSIS = object()  # Special object to signal ELLIPSIS as a parameter.
  PARSE_ERROR = ParseError  # The class object (not an instance of it).
  NOTHING = pytd.NothingType()
  ANYTHING = pytd.AnythingType()

  def __init__(self, version):
    """Initialize the parser.

    Args:
      version: A version tuple.
    """
    # TODO(dbaum): add PEP484_TRANSLATIONS
    self._type_map = {
        name: pytd.NamedType("typing." + name) for name in pep484.PEP484_NAMES}
    self._used = False
    self._error_location = None
    self._version = version
    # The condition stack, start with a default scope that will always be
    # active.
    self._current_condition = _ConditionScope(None)
    # These fields accumulate definitions that are used to build the
    # final TypeDeclUnit.
    self._constants = []
    self._aliases = []
    self._classes = []
    self._generated_classes = collections.defaultdict(list)

  def parse(self, src, name, filename):
    """Parse a PYI file and return the corresponding AST.

    Note that parse() should be called exactly once per _Parser instance.  It
    holds aggregated state during parsing and is not designed to be reused.

    Args:
      src: The source text to parse.
      name: The name of the module to be created.
      filename: The name of the source file.

    Returns:
      A pytd.TypeDeclUnit() representing the parsed pyi.

    Raises:
      ParseError: If the PYI source could not be parsed.
    """
    # Ensure instances do not get reused.
    assert not self._used
    self._used = True

    # TODO(dbaum): What should we do with filename?
    del filename
    try:
      defs = parser_ext.parse(self, src)
    except ParseError as e:
      if self._error_location:
        raise ParseError(e.message, self._error_location[0])
      else:
        raise e

    # defs contains both constant and function definitions.
    constants, functions = _split_definitions(defs)
    constants.extend(self._constants)

    generated_classes = [x for class_list in self._generated_classes.values()
                         for x in class_list]

    classes = generated_classes + self._classes

    all_names = (list(set(f.name for f in functions)) +
                 [c.name for c in constants] +
                 # TODO(dbaum): Add type_params and classes to the check.
                 # [c.name for c in type_params] +
                 [c.name for c in classes] +
                 [c.name for c in self._aliases])
    duplicates = [name
                  for name, count in collections.Counter(all_names).items()
                  if count >= 2]
    if duplicates:
      raise ParseError(
          "Duplicate top-level identifier(s): " + ", ".join(duplicates))

    functions, properties = _LEGACY.MergeSignatures(functions)
    if properties:
      prop_names = ", ".join(p.name for p in properties)
      raise ParseError(
          "Module-level functions with property decorators: " + prop_names)

    # TODO(dbaum): Add support for type_params, classes.
    # TODO(dbaum): Use a real module name.
    ast = pytd.TypeDeclUnit("?",
                            constants=tuple(constants),
                            type_params=(),
                            functions=tuple(functions),
                            classes=tuple(classes),
                            aliases=tuple(self._aliases))

    # TODO(dbaum): Add various AST transformations used in the legacy parser.
    # The code below was copied from the legacy parser, but sections that are
    # not currently tested are commented out.

    # ast = ast.Visit(InsertTypeParameters())

    ast = ast.Visit(pep484.ConvertTypingToNative(name))

    # if name:
    #   ast = ast.Replace(name=name)
    #   return ast.Visit(visitors.AddNamePrefix())
    # else:
    #   # If there's no unique name, hash the sourcecode.
    #   return ast.Replace(name=hashlib.md5(src).hexdigest())

    return ast

  def set_error_location(self, location):
    """Record the location of the current error.

    Args:
      location: A tuple (first_line, first_column, last_line, last_column).
    """
    self._error_location = location

  def _eval_condition(self, condition):
    """Evaluate a condition tuple (name, op value) and return a bool."""
    name, op, value = condition
    if name == "sys.version_info":
      if not isinstance(value, tuple):
        raise ParseError("sys.version_info must be compared to a tuple")
      if not all(isinstance(v, int) for v in value):
        raise ParseError("only integers are allowed in version tuples")
      # Append zeros and slice to normalize the tuple to a three-tuple.
      actual = (self._version + (0, 0))[:3]
    elif name == "sys.platform":
      if not isinstance(value, str):
        raise ParseError("sys.platform must be compared to a string")
      if op not in ["==", "!="]:
        raise ParseError("sys.platform must be compared using == or !=")
      actual = "linux"
    else:
      raise ParseError("Unsupported condition: '%s'." % name)
    return _COMPARES[op](actual, value)

  def if_begin(self, condition):
    """Begin an "if" statement using the specified condition."""
    self._current_condition = _ConditionScope(self._current_condition)
    self._current_condition.apply_condition(self._eval_condition(condition))
    return self._current_condition.active

  def if_elif(self, condition):
    """Start an "elif" clause using the specified condition."""
    self._current_condition.apply_condition(self._eval_condition(condition))
    return self._current_condition.active

  def if_else(self):
    """Start an "else" clause using the specified condition."""
    self._current_condition.apply_condition(True)
    return self._current_condition.active

  def if_end(self, clauses):
    """Finish an "if" statement given a list of (active, defs) clauses."""
    self._current_condition = self._current_condition.parent
    for cond_value, stmts in clauses:
      if cond_value:
        return stmts
    return []

  def new_constant(self, name, value):
    """Return a Constant.

    Args:
      name: The name of the constant.
      value: None, 0, or a  pytd type.

    Returns:
      A Constant object.

    Raises:
      ParseError: if value is an int other than 0.
    """
    if value is None:
      t = pytd.AnythingType()
    elif isinstance(value, int):
      if value != 0:
        raise ParseError("Only '0' allowed as int literal")
      t = pytd.NamedType("int")
    else:
      t = value
    return pytd.Constant(name, t)

  def add_alias_or_constant(self, name, value):
    """Add an alias or constant.

    Args:
      name: The name of the alias or constant.
      value: A pytd type.  If the type is NamedType("True") or
          NamedType("False") the name becomes a constant of type bool,
          otherwise it becomes an alias.
    """
    if not self._current_condition.active:
      return
    # TODO(dbaum): Consider merging this with new_constant().
    if value in [pytd.NamedType("True"), pytd.NamedType("False")]:
      self._constants.append(pytd.Constant(name, pytd.NamedType("bool")))
    else:
      self._type_map[name] = value
      self._aliases.append(pytd.Alias(name, value))

  def add_import(self, from_package, import_list):
    """Add an import.

    Args:
      from_package: A dotted package name if this is a "from" statement, or None
          if it is an "import" statement.
      import_list: A list of imported items, which are either strings or pairs
          of strings.  Pairs are used when items are renamed during import
          using "as".

    Raises:
      ParseError: If an import statement uses a rename.
    """
    if from_package:
      if not self._current_condition.active:
        return
      # from a.b.c import d, ...
      for item in import_list:
        if isinstance(item, tuple):
          name, new_name = item
        else:
          name = new_name = item
        if name != "*":
          t = pytd.NamedType("%s.%s" % (from_package, name))
          self._type_map[new_name] = t
          if from_package != "typing":
            self._aliases.append(pytd.Alias(new_name, t))
        else:
          pass  # TODO(kramm): Handle '*' imports in pyi
    else:
      # No need to check _current_condition since there are no side effects.
      # import a, b as c, ...
      for item in import_list:
        # simple import, no impact on pyi, but check for unsupported rename.
        if isinstance(item, tuple):
          raise ParseError(
              "Renaming of modules not supported. Use 'from' syntax.")

  def new_type(self, name, parameters=None):
    """Return the AST for a type.

    Args:
      name: The name of the type.
      parameters: List of type parameters.

    Returns:
      A pytd type node.
    """
    base_type = self._type_map.get(name)
    if base_type is None:
      base_type = pytd.NamedType(name)
    if parameters is not None:
      return self._parameterized_type(base_type, parameters)
    else:
      return base_type

  def _parameterized_type(self, base_type, parameters):
    """Return a parameterized type."""
    if base_type == pytd.NamedType("typing.Callable"):
      # TODO(kramm): Support Callable[[params], ret].
      return base_type
    elif len(parameters) == 2 and parameters[-1] is self.ELLIPSIS:
      element_type = parameters[0]
      if element_type is self.ELLIPSIS:
        raise ParseError("[..., ...] not supported")
      return pytd.HomogeneousContainerType(base_type=base_type,
                                           parameters=(element_type,))
    else:
      parameters = tuple(pytd.AnythingType() if p is self.ELLIPSIS else p
                         for p in parameters)
      if base_type == pytd.NamedType("typing.Tuple"):
        # Since we only support homogeneous tuples, convert heterogeneous
        # tuples to tuples of a union.
        if len(parameters) > 1:
          element_type = pytd.UnionType(parameters)
        else:
          element_type, = parameters
        return pytd.HomogeneousContainerType(base_type=base_type,
                                             parameters=(element_type,))
      else:
        return pytd.GenericType(base_type=base_type, parameters=parameters)

  def new_union_type(self, types):
    """Return a new UnionType composed of the specified types."""
    # UnionType flattens any contained UnionType's.
    return pytd.UnionType(tuple(types))

  def new_function(self, decorators, name, param_list, return_type, raises,
                   body):
    """Return a _NameAndSig object for the function.

    Args:
      decorators: List of decorator names.
      name: Name of funciton.
      param_list: List of parameters, where a paremeter is either a tuple
        (name, type, default) or the ELLIPSIS special object.  See
        _validate_params for a more detailed description of allowed parameters.
      return_type: A pytd type object.
      raises: ?
      body: ?

    Returns:
      A _NameAndSig object.

    Raises:
      ParseError: if any validity checks fail.
    """
    if name == "__init__" and isinstance(return_type, pytd.AnythingType):
      ret = pytd.NamedType("NoneType")
    else:
      ret = return_type
    params = _validate_params(param_list)
    signature = pytd.Signature(params=tuple(params.required), return_type=ret,
                               starargs=params.starargs,
                               starstarargs=params.starstarargs,
                               exceptions=tuple(raises), template=())

    for stmt in body:
      if stmt is None:
        # TODO(kramm) : process raise statement
        continue  # raise stmt
      mutator = legacy_parser.Mutator(stmt[0], stmt[1])
      try:
        signature = signature.Visit(mutator)
      except NotImplementedError as e:
        raise ParseError(e.message)
      if not mutator.successful:
        raise ParseError("No parameter named %s" % mutator.name)

    # Remove ignored decorators, raise ParseError for invalid decorators.
    decorators = [d for d in decorators if _keep_decorator(d)]
    # TODO(acaceres): if not inside a class, any decorator should be an error
    if len(decorators) > 1:
      raise ParseError("Too many decorators for %s" % name)

    return _NameAndSig(name=name, signature=signature,
                       decorators=tuple(sorted(decorators)),
                       external_code=False)

  def new_external_function(self, decorators, name):
    """Return a _NameAndSig for an external code function."""
    del decorators
    return _NameAndSig(
        name=name,
        # signature is for completeness - it's ignored
        signature=pytd.Signature(params=(),
                                 starargs=None, starstarargs=None,
                                 return_type=pytd.NothingType(),
                                 exceptions=(),
                                 template=()),
        decorators=(),
        external_code=True)

  def new_named_tuple(self, base_name, fields):
    """Return a type for a named tuple (implicitly generates a class).

    Args:
      base_name: The named tuple's name.
      fields: A list of (name, type) tuples.

    Returns:
      A NamedType() for the generated class that describes the named tuple.
    """
    # Handle previously defined NamedTuples with the same name
    prev_list = self._generated_classes[base_name]
    name_dedup = "~%d" % len(prev_list) if prev_list else ""
    class_name = "`%s%s`" % (base_name, name_dedup)

    # Like for typing.Tuple, heterogeneous NamedTuples get converted to
    # homogeneous ones:
    # NamedTuple[("x", X), ("y", Y)] -> Tuple[X, Y] -> Tuple[Union[X, Y], ...]
    types = tuple(t for _, t in fields)
    container_param = (pytd.UnionType(type_list=types) if types
                       else pytd.AnythingType())

    class_parent = pytd.HomogeneousContainerType(
        base_type=pytd.NamedType("tuple"),
        parameters=(container_param,))

    class_constants = tuple(pytd.Constant(n, t) for n, t in fields)
    nt_class = pytd.Class(name=class_name,
                          metaclass=None,
                          parents=(class_parent,),
                          methods=(),
                          constants=class_constants,
                          template=())

    self._generated_classes[base_name].append(nt_class)
    return pytd.NamedType(nt_class.name)

  def register_class_name(self, class_name):
    """Register a class name so that it can shadow aliases."""
    if not self._current_condition.active:
      return
    self._type_map[class_name] = pytd.NamedType(class_name)

  def add_class(self, class_name, parent_args, defs):
    """Add a class to the module.

    Args:
      class_name: The name of the class (a string).
      parent_args: A list of parent types and (keyword, value) tuples.
          Parent types must be instances of pytd.Type.  Keyword tuples must
          appear at the end of the list.  Currently the only supported keyword
          is 'metaclass'.
      defs: A list of constant (pytd.Constant) and function (_NameAndSig)
          definitions.

    Raises:
      ParseError: if defs contains duplicate names (excluding multiple
          definitions of a function, which is allowed).
    """
    # Process parent_args, extracting parents and possibly a metaclass.
    parents = []
    metaclass = None
    for i, p in enumerate(parent_args):
      if isinstance(p, pytd.Type):
        parents.append(p)
      else:
        keyword, value = p
        if i != len(parent_args) - 1:
          raise ParseError("metaclass must be last argument")
        if keyword != "metaclass":
          raise ParseError("Only 'metaclass' allowed as classdef kwarg")
        metaclass = value

    constants, methods = _split_definitions(defs)

    all_names = (list(set(f.name for f in methods)) +
                 [c.name for c in constants])
    duplicates = [name
                  for name, count in collections.Counter(all_names).items()
                  if count >= 2]
    if duplicates:
      # TODO(kramm): raise a syntax error right when the identifier is defined.
      raise ParseError("Duplicate identifier(s): " + ", ".join(duplicates))

    # This check is performed after the above error checking so that errors
    # will be spotted even in non-active conditional code.
    if not self._current_condition.active:
      return

    # TODO(dbaum): Is NothingType even legal here?  The grammar accepts it but
    # perhaps it should be a ParseError.
    parents = [p for p in parents if not isinstance(p, pytd.NothingType)]
    methods, properties = _LEGACY.MergeSignatures(methods)
    # Ensure that old style classes inherit from classobj.
    if not parents and class_name not in ["classobj", "object"]:
      parents = (pytd.NamedType("classobj"),)
    cls = pytd.Class(name=class_name, metaclass=metaclass,
                     parents=tuple(parents),
                     methods=tuple(methods),
                     constants=tuple(constants + properties),
                     template=())
    self._classes.append(cls)


def parse_string(src, name=None, filename=None,
                 python_version=_DEFAULT_VERSION):
  return _Parser(version=python_version).parse(src, name, filename)


def _keep_decorator(decorator):
  """Return True iff the decorator requires processing."""
  if decorator in ["overload", "abstractmethod"]:
    # These are legal but ignored.
    return False
  elif (decorator in ["staticmethod", "classmethod", "property"] or
        "." in decorator):
    # Dotted name decorators need more context to be validated, done in
    # TryParseSignatureAsProperty
    return True
  else:
    raise ParseError("Decorator %s not supported" % decorator)


def _validate_params(param_list):
  """Validate and convert a param_list.

  Validate and convert parameter tuples to a _Params object.  This performs
  a number of checks that are easier to do after parsing rather than
  incorporating them into the grammar itself.

  Parameters are specified as either ELLIPSIS objects or (name, type, default)
  tuples, where name is a string, type is a pytd type or None, and default
  is a string, number or None.

  (name, None, None): A required parameter with no type information.
  (name, type, None): A parameter of the specified type.
  (name, None, default): An optional parameter.  In some cases, type information
      is derived from default (see _type_for_default).
  (name, type, default): An optional parameter with type information.  If
      default is the string "None" then the parameter type is widened to include
      both the specified type and NoneType.

  (*, None, None): A bare * parameter.
  (*name, None, None): A *args style argument of type tuple.
  (*name, type, None): A *args style argument of type tuple[type].
  (**name, None, None): A **kwargs style argument of type dict.
  (**name, type, None): A **kwargs style argument of type dict[str, type].
  ELLIPSIS: Syntactic sugar that adds both *args and *kwargs parameters.

  Args:
    param_list: list of (name, type, default) tuples and ELLIPSIS objects.

  Returns:
    A _Params instance.

  Raises:
    ParseError: if special arguments are present in the wrong positions or
        combinations.
  """
  # TODO(kramm): Disallow "self" and "cls" as names for param (if it's not
  # the first parameter).

  params = []
  has_bare_star = False
  stararg = None
  starstararg = None

  for i, param in enumerate(param_list):
    is_last = i == len(param_list) - 1
    if param is _Parser.ELLIPSIS:
      if not is_last:
        raise ParseError("ellipsis (...) must be last parameter")
      if has_bare_star:
        raise ParseError("ellipsis (...) not compatible with bare *")
      # TODO(dbaum): Shouldn't we pass the existing paramter names to
      # InventStarArgParams()?  The legacy parser doesn't, so leaving the
      # code idenentical to legacy for now.
      stararg, starstararg = visitors.InventStarArgParams([])
      continue

    name, param_type, default = param
    if name.startswith("**"):
      # **kwargs
      if not is_last:
        raise ParseError("%s must be last parameter" % name)
      starstararg = _starstar_param(name[2:], param_type)
    elif name.startswith("*"):
      # *args or *
      if stararg or has_bare_star:
        raise ParseError("Unexpected second *")
      if name == "*" and is_last:
        raise ParseError("Named arguments must follow bare *")
      if name == "*":
        has_bare_star = True
      else:
        stararg = _star_param(name[1:], param_type)
    else:
      kwonly = stararg or has_bare_star
      params.append(_normal_param(name, param_type, default, kwonly))

  return _Params(params,
                 stararg,
                 starstararg,
                 has_bare_star=has_bare_star)


def _normal_param(name, param_type, default, kwonly):
  """Return a pytd.Parameter object for a normal argument."""
  if default is not None:
    default_type = _type_for_default(default)
    if param_type is None:
      param_type = default_type
    elif default_type == pytd.NamedType("NoneType"):
      param_type = pytd.UnionType((param_type, default_type))
  if param_type is None:
    # TODO(kramm): We should use __builtin__.object. (And other places)
    param_type = pytd.NamedType("object")

  optional = default is not None
  return pytd.Parameter(name, param_type, kwonly, optional, None)


def _star_param(name, param_type):
  """Return a pytd.Parameter for a *args argument."""
  if param_type is None:
    param_type = pytd.NamedType("tuple")
  else:
    param_type = pytd.HomogeneousContainerType(
        pytd.NamedType("tuple"), (param_type,))
  return pytd.Parameter(name, param_type, False, True, None)


def _starstar_param(name, param_type):
  """Return a pytd.Parameter for a **kwargs argument."""
  if param_type is None:
    param_type = pytd.NamedType("dict")
  else:
    param_type = pytd.GenericType(
        pytd.NamedType("dict"), (pytd.NamedType("str"), param_type))
  return pytd.Parameter(name, param_type, False, True, None)


def _type_for_default(default):
  """Return a pytd type object for the given default value."""
  # TODO(kramm): We should use __builtin__ types here. (And other places)
  if default == "None":
    return pytd.NamedType("NoneType")
  elif isinstance(default, float):
    return pytd.NamedType("float")
  elif isinstance(default, int):
    return pytd.NamedType("int")
  else:
    # ELLIPSIS or NAMEs other than None are treated as object.
    return pytd.NamedType("object")


def _split_definitions(defs):
  """Return [constants], [functions] given a mixed list of definitions."""
  constants = []
  functions = []
  for d in defs:
    if isinstance(d, pytd.Constant):
      constants.append(d)
    elif isinstance(d, _NameAndSig):
      functions.append(d)
    else:
      raise TypeError("Unexpected definition type %s", type(d))
  return constants, functions
