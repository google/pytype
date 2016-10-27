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


class ParseError(Exception):

  def __init__(self, msg, line=None):
    super(ParseError, self).__init__(msg)
    self._line = line

  @property
  def line(self):
    return self._line


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
    add_constant()
    add_alias_or_constant()
    add_import()
    new_type()
    new_union_type()
    new_function()
    add_function()

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
  """

  # Values for the parsing context.
  ELLIPSIS = object()  # Special object to signal ELLIPSIS as a parameter.
  PARSE_ERROR = ParseError  # The class object (not an instance of it).
  NOTHING = pytd.NothingType()
  ANYTHING = pytd.AnythingType()

  def __init__(self):
    # TODO(dbaum): add PEP484_TRANSLATIONS
    self._type_map = {
        name: pytd.NamedType("typing." + name) for name in pep484.PEP484_NAMES}
    self._used = False
    self._error_location = None
    # These fields accumulate definitions that are used to build the
    # final TypeDeclUnit.
    self._constants = []
    self._aliases = []
    self._functions = []

  def parse(self, src, name, filename, version):
    """Parse a PYI file and return the corresponding AST.

    Note that parse() should be called exactly once per _Parser instance.  It
    holds aggregated state during parsing and is not designed to be reused.

    Args:
      src: The source text to parse.
      name: The name of the module to be created.
      filename: The name of the source file.
      version: A version tuple.

    Returns:
      A pytd.TypeDeclUnit() representing the parsed pyi.

    Raises:
      ParseError: If the PYI source could not be parsed.
    """
    # Ensure instances do not get reused.
    assert not self._used
    self._used = True

    # TODO(dbaum): What should we do with filename and version?
    del filename
    del version
    try:
      parser_ext.parse(self, src)
    except ParseError as e:
      if self._error_location:
        raise ParseError(e.message, self._error_location[0])
      else:
        raise e

    all_names = (list(set(f.name for f in self._functions)) +
                 [c.name for c in self._constants] +
                 # TODO(dbaum): Add type_params and classes to the check.
                 # [c.name for c in type_params] +
                 # [c.name for c in classes] +
                 [c.name for c in self._aliases])
    duplicates = [name
                  for name, count in collections.Counter(all_names).items()
                  if count >= 2]
    if duplicates:
      raise ParseError(
          "Duplicate top-level identifier(s): " + ", ".join(duplicates))

    functions, properties = _LEGACY.MergeSignatures(self._functions)
    if properties:
      prop_names = ", ".join(p.name for p in properties)
      raise ParseError(
          "Module-level functions with property decorators: " + prop_names)

    # TODO(dbaum): Add support for type_params, classes.
    # TODO(dbaum): Use a real module name.
    ast = pytd.TypeDeclUnit("?",
                            constants=tuple(self._constants),
                            type_params=(),
                            functions=tuple(functions),
                            classes=(),
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

  def add_constant(self, name, value):
    """Add a constant.

    Args:
      name: The name of the constant.
      value: None, 0, or a  pytd type.

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
    self._constants.append(pytd.Constant(name, t))

  def add_alias_or_constant(self, name, value):
    """Add an alias or constant.

    Args:
      name: The name of the alias or constant.
      value: A pytd type.  If the type is NamedType("True") or
          NamedType("False") the name becomes a constant of type bool,
          otherwise it becomes an alias.
    """
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

  def add_function(self, name_and_sig):
    self._functions.append(name_and_sig)


def parse_string(src, name=None, filename=None,
                 python_version=_DEFAULT_VERSION):
  return _Parser().parse(src, name, filename, version=python_version)


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
