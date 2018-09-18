"""Fast PYI parser."""

import collections
import hashlib

from pytype import file_utils
from pytype import module_utils
from pytype import utils
from pytype.pyi import parser_ext
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd import visitors
from pytype.pytd.parse import parser_constants  # pylint: disable=g-importing-member

_DEFAULT_VERSION = (2, 7, 6)
_DEFAULT_PLATFORM = "linux"


_Params = collections.namedtuple("_", ["required",
                                       "starargs", "starstarargs",
                                       "has_bare_star"])

_NameAndSig = collections.namedtuple("_", ["name", "signature",
                                           "decorator", "is_abstract",
                                           "is_coroutine"])

_SlotDecl = collections.namedtuple("_", ["slots"])

_Property = collections.namedtuple("_", ["precedence", "arity"])


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

  """Exceptions raised by the parser."""

  def __init__(self, msg, line=None, filename=None, column=None, text=None):
    super(ParseError, self).__init__(msg)
    self._line = line
    self._filename = filename
    self._column = column
    self._text = text

  @property
  def line(self):
    return self._line

  def __str__(self):
    lines = []
    if self._filename or self._line is not None:
      lines.append('  File: "%s", line %s' % (self._filename, self._line))
    if self._column and self._text:
      indent = 4
      stripped = self._text.lstrip()
      lines.append("%*s%s" % (indent, "", stripped))
      # Output a pointer below the error column, adjusting for stripped spaces.
      pos = indent + (self._column - 1) - (len(self._text) - len(stripped))
      lines.append("%*s^" % (pos, ""))
    lines.append("%s: %s" % (type(self).__name__, utils.message(self)))
    return "\n".join(lines)


class OverloadedDecoratorError(ParseError):
  """Inconsistent decorators on an overloaded function."""

  def __init__(self, name, typ, *args, **kwargs):
    msg = "Overloaded signatures for %s disagree on %sdecorators" % (
        name, (typ + " " if typ else ""))
    super(OverloadedDecoratorError, self).__init__(msg, *args, **kwargs)


class _Mutator(visitors.Visitor):
  """Visitor for changing parameters to BeforeAfterType instances.

  We model
    def f(x: old_type):
      x = new_type
  as
    def f(x: BeforeAfterType(old_type, new_type))
  .
  This visitor applies the body "x = new_type" to the function signature.
  """

  def __init__(self, name, new_type):
    super(_Mutator, self).__init__()
    self.name = name
    self.new_type = new_type
    self.successful = False

  def VisitParameter(self, p):
    if p.name == self.name:
      self.successful = True
      if p.optional:
        raise NotImplementedError(
            "Argument %s can not be both mutable and optional" % p.name)
      return p.Replace(mutated_type=self.new_type)
    else:
      return p


class _InsertTypeParameters(visitors.Visitor):
  """Visitor for inserting TypeParameter instances."""

  def EnterTypeDeclUnit(self, node):
    self.type_params = {p.name: p for p in node.type_params}

  def LeaveTypeDeclUnit(self, node):
    self.type_params = None

  def VisitNamedType(self, node):
    if node.name in self.type_params:
      return self.type_params[node.name]
    else:
      return node


class _ContainsAnyType(visitors.Visitor):
  """Check if a pytd object contains a type of any of the given names."""

  def __init__(self, type_names):
    super(_ContainsAnyType, self).__init__()
    self._type_names = set(type_names)
    self.found = False

  def EnterNamedType(self, node):
    if node.name in self._type_names:
      self.found = True


def _contains_any_type(ast, type_names):
  """Convenience wrapper for _ContainsAnyType."""
  out = _ContainsAnyType(type_names)
  ast.Visit(out)
  return out.found


class _PropertyToConstant(visitors.Visitor):
  """Convert some properties to constant types."""

  def EnterTypeDeclUnit(self, node):
    self.type_param_names = [x.name for x in node.type_params]
    self.const_properties = None

  def LeaveTypeDeclUnit(self, node):
    self.type_param_names = None

  def EnterClass(self, node):
    self.const_properties = []

  def LeaveClass(self, node):
    self.const_properties = None

  def VisitClass(self, node):
    constants = list(node.constants)
    for fn in self.const_properties:
      types = [x.return_type for x in fn.signatures]
      constants.append(pytd.Constant(name=fn.name, type=join_types(types)))
    methods = [x for x in node.methods if x not in self.const_properties]
    return node.Replace(constants=tuple(constants), methods=tuple(methods))

  def EnterFunction(self, node):
    if (self.const_properties is not None and
        node.kind == pytd.PROPERTY and
        not self._is_parametrised(node)):
      self.const_properties.append(node)

  def _is_parametrised(self, method):
    for sig in method.signatures:
      if _contains_any_type(sig.return_type, self.type_param_names):
        return True


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
    BYTESTRING
    UNICODESTRING
    TUPLE

  Methods used in AST construction:
    new_constant()
    add_alias_or_constant()
    add_import()
    new_class()
    new_type()
    new_union_type()
    new_function()
    new_named_tuple()
    regiser_class_name()
    add_type_var()
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
  with current location information, then the call to parse_ext.parse()
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

  See _eval_condition for a description of conditions.
  """

  # Values for the parsing context.
  ELLIPSIS = object()  # Special object to signal ELLIPSIS as a parameter.
  PARSE_ERROR = ParseError  # The class object (not an instance of it).
  NOTHING = pytd.NothingType()
  ANYTHING = pytd.AnythingType()
  BYTESTRING = pytd.NamedType("bytes")
  UNICODESTRING = pytd.NamedType("unicode")
  TUPLE = pytd.NamedType("tuple")

  # Attributes that all namedtuple instances have.
  _NAMEDTUPLE_MEMBERS = ("_asdict", "__dict__", "_fields", "__getnewargs__",
                         "__getstate__", "_make", "_replace")

  def __init__(self, version, platform):
    """Initialize the parser.

    Args:
      version: A version tuple.
      platform: A platform string.
    """
    assert version
    self._used = False
    self._error_location = None
    self._version = _three_tuple(version or _DEFAULT_VERSION)
    self._platform = platform or _DEFAULT_PLATFORM
    # Fields initialized in self.parse().
    self._filename = None  # type: str
    self._ast_name = None  # type: str
    self._package_name = None  # type: str
    self._type_map = None  # type: dict
    # The condition stack, start with a default scope that will always be
    # active.
    self._current_condition = _ConditionScope(None)
    # These fields accumulate definitions that are used to build the
    # final TypeDeclUnit.
    self._constants = []
    self._aliases = []
    self._type_params = []
    self._module_path_map = {}
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

    self._filename = filename
    self._ast_name = name
    self._type_map = {}

    is_package = file_utils.is_pyi_directory_init(filename)
    self._package_name = module_utils.get_package_name(name, is_package)

    try:
      defs = parser_ext.parse(self, src)
      ast = self._build_type_decl_unit(defs)
    except ParseError as e:
      if self._error_location:
        line = e.line or self._error_location[0]
        try:
          text = src.splitlines()[line-1]
        except IndexError:
          text = None
        raise ParseError(utils.message(e), line=line, filename=self._filename,
                         column=self._error_location[1], text=text)
      else:
        raise e

    ast = ast.Visit(_PropertyToConstant())
    ast = ast.Visit(_InsertTypeParameters())
    # TODO(kramm): This is in the wrong place- it should happen after resolving
    # local names, in load_pytd.
    ast = ast.Visit(pep484.ConvertTypingToNative(name))

    if name:
      ast = ast.Replace(name=name)
      ast = ast.Visit(visitors.AddNamePrefix())
    else:
      # If there's no unique name, hash the sourcecode.
      ast = ast.Replace(name=hashlib.md5(src.encode("utf-8")).hexdigest())
    ast = ast.Visit(visitors.StripExternalNamePrefix())

    # Typeshed files that explicitly import and refer to "builtins" need to have
    # that rewritten to __builtin__
    return ast.Visit(visitors.RenameBuiltinsPrefix())

  def _build_type_decl_unit(self, defs):
    """Return a pytd.TypeDeclUnit for the given defs (plus parser state)."""
    # defs contains both constant and function definitions.
    constants, functions, aliases, slots, classes = _split_definitions(defs)
    assert not slots  # slots aren't allowed on the module level
    assert not aliases  # We handle top-level aliases in add_alias_or_constant.
    constants.extend(self._constants)

    generated_classes = [x for class_list in self._generated_classes.values()
                         for x in class_list]

    classes = generated_classes + classes
    functions = _merge_method_signatures(functions)

    name_to_class = {c.name: c for c in classes}
    aliases = []
    for a in self._aliases:
      t = _maybe_resolve_alias(a, name_to_class)
      if isinstance(t, pytd.Function):
        functions.append(t)
      elif isinstance(t, pytd.Constant):
        constants.append(t)
      else:
        assert isinstance(t, pytd.Alias)
        aliases.append(t)

    all_names = ([f.name for f in functions] +
                 [c.name for c in constants] +
                 [c.name for c in self._type_params] +
                 [c.name for c in classes] +
                 [c.name for c in aliases])
    duplicates = [name
                  for name, count in collections.Counter(all_names).items()
                  if count >= 2]
    if duplicates:
      raise ParseError(
          "Duplicate top-level identifier(s): " + ", ".join(duplicates))

    properties = [x for x in functions if x.kind == pytd.PROPERTY]
    if properties:
      prop_names = ", ".join(p.name for p in properties)
      raise ParseError(
          "Module-level functions with property decorators: " + prop_names)

    return pytd.TypeDeclUnit(name=None,
                             constants=tuple(constants),
                             type_params=tuple(self._type_params),
                             functions=tuple(functions),
                             classes=tuple(classes),
                             aliases=tuple(aliases))

  def set_error_location(self, location):
    """Record the location of the current error.

    Args:
      location: A tuple (first_line, first_column, last_line, last_column).
    """
    self._error_location = location

  def _eval_condition(self, condition):
    """Evaluate a condition and return a bool.

    Args:
      condition: A condition tuple of (left, op, right). If op is "or" or "and",
      then left and right are conditions. Otherwise, left is a name, op is one
      of the comparison strings in _COMPARES, and right is the expected value.

    Returns:
      The boolean result of evaluating the condition.

    Raises:
      ParseError: If the condition cannot be evaluated.
    """
    left, op, right = condition
    if op == "or":
      return self._eval_condition(left) or self._eval_condition(right)
    elif op == "and":
      return self._eval_condition(left) and self._eval_condition(right)
    else:
      return self._eval_comparison(left, op, right)

  def _eval_comparison(self, ident, op, value):
    """Evaluate a comparison and return a bool.

    Args:
      ident: A tuple of a dotted name string and an optional __getitem__ key
        (int or slice).
      op: One of the comparison operator strings in _COMPARES.
      value: Either a string, an integer, or a tuple of integers.

    Returns:
      The boolean result of the comparison.

    Raises:
      ParseError: If the comparison cannot be evaluated.
    """
    name, key = ident
    if name == "sys.version_info":
      if key is None:
        key = slice(None, None, None)
      assert isinstance(key, (int, slice))
      if isinstance(key, int) and not isinstance(value, int):
        raise ParseError(
            "an element of sys.version_info must be compared to an integer")
      if isinstance(key, slice) and not _is_int_tuple(value):
        raise ParseError(
            "sys.version_info must be compared to a tuple of integers")
      try:
        actual = self._version[key]
      except IndexError as e:
        raise ParseError(utils.message(e))
      if isinstance(key, slice):
        actual = _three_tuple(actual)
        value = _three_tuple(value)
    elif name == "sys.platform":
      if not isinstance(value, str):
        raise ParseError("sys.platform must be compared to a string")
      if op not in ["==", "!="]:
        raise ParseError("sys.platform must be compared using == or !=")
      actual = self._platform
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
    elif isinstance(value, float):
      if value != 0.0:
        raise ParseError("Only '0.0' allowed as float literal")
      t = pytd.NamedType("float")
    else:
      t = value
    return pytd.Constant(name, t)

  def new_alias_or_constant(self, name_and_value):
    name, value = name_and_value
    if name == "__slots__":
      return _SlotDecl(value)
    elif value in [pytd.NamedType("True"), pytd.NamedType("False")]:
      return pytd.Constant(name, pytd.NamedType("bool"))
    else:
      return pytd.Alias(name, value)

  def add_alias_or_constant(self, name_and_value):
    """Add an alias or constant.

    Args:
      name_and_value: The name and value of the alias or constant.

    Raises:
      ParseError: For an invalid __slots__ declaration.
    """
    if not self._current_condition.active:
      return
    # TODO(dbaum): Consider merging this with new_constant().
    alias_or_constant = self.new_alias_or_constant(name_and_value)
    if isinstance(alias_or_constant, pytd.Constant):
      self._constants.append(alias_or_constant)
    elif isinstance(alias_or_constant, _SlotDecl):
      # At this point, bison might not have full location information yet, so
      # supply an explicit line number.
      raise ParseError("__slots__ only allowed on the class level", line=1)
    elif isinstance(alias_or_constant, pytd.Alias):
      name, value = name_and_value
      self._type_map[name] = value
      self._aliases.append(alias_or_constant)
    else:
      assert False, "Unknown type of assignment"

  def add_import(self, from_package, import_list):
    """Add an import.

    Args:
      from_package: A dotted package name if this is a "from" statement, or None
          if it is an "import" statement.
      import_list: A list of imported items, which are either strings or pairs
          of strings.  Pairs are used when items are renamed during import
          using "as".
    """
    if not self._current_condition.active:
      return
    if from_package:
      # from a.b.c import d, ...
      for item in import_list:
        if isinstance(item, tuple):
          name, new_name = item
        else:
          name = new_name = item
        qualified_name = self._qualify_name("%s.%s" % (from_package, name))
        if from_package == "__PACKAGE__" and isinstance(item, str):
          # This will always be a simple module import (from . cannot import a
          # NamedType, and without 'as' the name will not be reexported).
          t = pytd.Module(name=new_name, module_name=qualified_name)
        else:
          # We should ideally not need this check, but we have typing
          # special-cased in some places.
          if not qualified_name.startswith("typing.") and name != "*":
            # Mark this as an externally imported type, so that AddNamePrefix
            # does not prefix it with the current package name.
            qualified_name = (parser_constants.EXTERNAL_NAME_PREFIX +
                              qualified_name)
          t = pytd.NamedType(qualified_name)
        if name == "*":
          # A star import is stored as
          # 'imported_mod.* = imported_mod.*'. The imported module needs to be
          # in the alias name so that multiple star imports are handled
          # properly. LookupExternalTypes() replaces the alias with the
          # contents of the imported module.
          assert new_name == name
          new_name = t.name
        self._type_map[new_name] = t
        if from_package != "typing" or self._ast_name == "protocols":
          self._aliases.append(pytd.Alias(new_name, t))
          self._module_path_map[name] = qualified_name
    else:
      # import a, b as c, ...
      for item in import_list:
        if isinstance(item, tuple):
          name, new_name = item
          t = pytd.Module(name=self._qualify_name(new_name),
                          module_name=self._qualify_name(name))
          self._aliases.append(pytd.Alias(new_name, t))
        else:
          # We don't care about imports that are not aliased.
          pass

  def new_type(self, name, parameters=None):
    """Return the AST for a type.

    Args:
      name: The name of the type.
      parameters: List of type parameters.

    Returns:
      A pytd type node.

    Raises:
      ParseError: if parameters are not supplied for a base_type that requires
          parameters, such as Union.
    """
    base_type = self._type_map.get(name)
    if base_type is None:
      module, dot, tail = name.partition(".")
      full_name = self._module_path_map.get(module, module) + dot + tail
      base_type = pytd.NamedType(full_name)
    if parameters is not None:
      return self._parameterized_type(base_type, parameters)
    else:
      if (isinstance(base_type, pytd.NamedType) and
          base_type.name in ["typing.Union",
                             "typing.Intersection",
                             "typing.Optional"]):
        raise ParseError("Missing options to %s" % base_type.name)
      return base_type

  def _is_tuple_base_type(self, t):
    return isinstance(t, pytd.NamedType) and (
        t.name == "tuple" or
        (self._ast_name != "__builtin__" and t.name == "__builtin__.tuple") or
        (self._ast_name == "typing" and t.name == "Tuple") or
        (self._ast_name != "typing" and t.name == "typing.Tuple"))

  def _is_callable_base_type(self, t):
    return isinstance(t, pytd.NamedType) and (
        (self._ast_name == "typing" and t.name == "Callable") or
        (self._ast_name != "typing" and t.name == "typing.Callable"))

  def _heterogeneous_tuple(self, base_type, parameters):
    if parameters:
      return pytd.TupleType(base_type=base_type, parameters=parameters)
    else:
      return pytd.GenericType(base_type=base_type,
                              parameters=(pytd.NothingType(),))

  def _is_empty_tuple(self, t):
    return (isinstance(t, pytd.GenericType) and
            self._is_tuple_base_type(t.base_type) and
            t.parameters == (pytd.NothingType(),))

  def _is_heterogeneous_tuple(self, t):
    # An empty tuple is represented as a GenericType rather than a TupleType,
    # but we still consider it heterogeneous because we know exactly what the
    # parameters are (there are none).
    return isinstance(t, pytd.TupleType) or self._is_empty_tuple(t)

  def _is_any(self, t):
    return isinstance(t, pytd.AnythingType) or t == pytd.NamedType("typing.Any")

  def _is_parameterized_protocol(self, t):
    return (isinstance(t, pytd.GenericType) and
            t.base_type.name == "typing.Protocol")

  def _parameterized_type(self, base_type, parameters):
    """Return a parameterized type."""
    if self._is_any(base_type):
      return pytd.AnythingType()
    elif len(parameters) == 2 and parameters[-1] is self.ELLIPSIS and (
        not self._is_callable_base_type(base_type)):
      element_type = parameters[0]
      if element_type is self.ELLIPSIS:
        raise ParseError("[..., ...] not supported")
      return pytd.GenericType(base_type=base_type,
                              parameters=(element_type,))
    else:
      parameters = tuple(pytd.AnythingType() if p is self.ELLIPSIS else p
                         for p in parameters)
      if self._is_tuple_base_type(base_type):
        return self._heterogeneous_tuple(base_type, parameters)
      elif (self._is_callable_base_type(base_type) and
            self._is_heterogeneous_tuple(parameters[0])):
        if len(parameters) > 2:
          raise ParseError(
              "Expected 2 parameters to Callable, got %d" % len(parameters))
        if len(parameters) == 1:
          # We're usually happy to treat omitted parameters as "Any", but we
          # need a return type for CallableType, or we wouldn't know whether the
          # last parameter is an argument or return type.
          parameters += (pytd.AnythingType(),)
        if self._is_empty_tuple(parameters[0]):
          parameters = parameters[1:]
        else:
          parameters = parameters[0].parameters + parameters[1:]
        return pytd.CallableType(base_type=base_type, parameters=parameters)
      else:
        assert parameters
        if (self._is_callable_base_type(base_type) and
            not self._is_any(parameters[0])):
          raise ParseError(
              "First argument to Callable must be a list of argument types")
        return pytd.GenericType(base_type=base_type, parameters=parameters)

  def new_union_type(self, types):
    """Return a new UnionType composed of the specified types."""
    # UnionType flattens any contained UnionType's.
    return pytd.UnionType(tuple(types))

  def new_intersection_type(self, types):
    """Return a new IntersectionType composed of the specified types."""
    # IntersectionType flattens any contained IntersectionType's.
    return pytd.IntersectionType(tuple(types))

  def new_function(self, decorators, name, param_list, return_type, body):
    """Return a _NameAndSig object for the function.

    Args:
      decorators: List of decorator names.
      name: Name of function.
      param_list: List of parameters, where a paremeter is either a tuple
        (name, type, default) or the ELLIPSIS special object.  See
        _validate_params for a more detailed description of allowed parameters.
      return_type: A pytd type object.
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

    exceptions = []
    mutators = []
    for stmt in body:
      if isinstance(stmt, pytd.Type):
        exceptions.append(stmt)  # raise stmt
        continue
      assert isinstance(stmt, tuple) and len(stmt) == 2, stmt
      mutators.append(_Mutator(stmt[0], stmt[1]))

    signature = pytd.Signature(params=tuple(params.required), return_type=ret,
                               starargs=params.starargs,
                               starstarargs=params.starstarargs,
                               exceptions=tuple(exceptions), template=())
    for mutator in mutators:
      try:
        signature = signature.Visit(mutator)
      except NotImplementedError as e:
        raise ParseError(utils.message(e))
      if not mutator.successful:
        raise ParseError("No parameter named %s" % mutator.name)

    # Remove ignored decorators, raise ParseError for invalid decorators.
    decorators = {d for d in decorators if _keep_decorator(d)}
    # Extract out abstractmethod and coroutine decorators, there should be at
    # most one remaining decorator.
    def _check_decorator(decorators, decorator_set):
      exists = any([x in decorators for x in decorator_set])
      if exists:
        decorators -= decorator_set
      return exists
    is_abstract = _check_decorator(
        decorators, {"abstractmethod", "abc.abstractmethod"})
    is_coroutine = _check_decorator(
        decorators, {"coroutine", "async.coroutine", "coroutines.coroutine"})
    # TODO(acaceres): if not inside a class, any decorator should be an error
    if len(decorators) > 1:
      raise ParseError("Too many decorators for %s" % name)
    decorator, = decorators if decorators else (None,)

    return _NameAndSig(name=name, signature=signature,
                       decorator=decorator,
                       is_abstract=is_abstract,
                       is_coroutine=is_coroutine)

  def _namedtuple_new(self, name, fields):
    """Build a __new__ method for a namedtuple with the given fields.

    For a namedtuple defined as NamedTuple("_", [("foo", int), ("bar", str)]),
    generates the method
      def __new__(cls: Type[_T], foo: int, bar: str) -> _T: ...
    where _T is a TypeVar bounded by the class type.

    Args:
      name: The class name.
      fields: A list of (name, type) pairs representing the namedtuple fields.

    Returns:
      A _NameAndSig object for a __new__ method.
    """
    type_param = pytd.TypeParameter("_T" + name, bound=pytd.NamedType(name))
    self._type_params.append(type_param)
    cls_arg = (
        "cls", pytd.GenericType(pytd.NamedType("type"), (type_param,)), None)
    args = [cls_arg] + [(n, t, None) for n, t in fields]
    return self.new_function((), "__new__", args, type_param, ())

  def _namedtuple_init(self):
    """Build an __init__ method for a namedtuple.

    Builds a dummy __init__ that accepts any arguments. Needed because our
    model of __builtin__.tuple uses __init__.

    Returns:
      A _NameAndSig object for an __init__ method.
    """
    args = [(name, pytd.AnythingType(), None)
            for name in ("self", "*args", "**kwargs")]
    ret = pytd.NamedType("NoneType")
    return self.new_function((), "__init__", args, ret, ())

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
    class_name = "namedtuple-%s-%d" % (base_name, len(prev_list))
    class_parent = self._heterogeneous_tuple(pytd.NamedType("tuple"),
                                             tuple(t for _, t in fields))
    class_constants = tuple(pytd.Constant(n, t) for n, t in fields)
    # Since the user-defined fields are the only namedtuple attributes commonly
    # used, we define all the other attributes as Any for simplicity.
    class_constants += tuple(pytd.Constant(name, pytd.AnythingType())
                             for name in self._NAMEDTUPLE_MEMBERS)
    methods = _merge_method_signatures(
        [self._namedtuple_new(class_name, fields), self._namedtuple_init()])
    nt_class = pytd.Class(name=class_name,
                          metaclass=None,
                          parents=(class_parent,),
                          methods=tuple(methods),
                          constants=class_constants,
                          slots=tuple(n for n, _ in fields),
                          template=())

    self._generated_classes[base_name].append(nt_class)
    return pytd.NamedType(nt_class.name)

  def register_class_name(self, class_name):
    """Register a class name so that it can shadow aliases."""
    if not self._current_condition.active:
      return
    self._type_map[class_name] = pytd.NamedType(class_name)

  def new_class(self, class_name, parent_args, defs):
    """Create a new class.

    Args:
      class_name: The name of the class (a string).
      parent_args: A list of parent types and (keyword, value) tuples.
          Parent types must be instances of pytd.Type.  Keyword tuples must
          appear at the end of the list.  Currently the only supported keyword
          is 'metaclass'.
      defs: A list of constant (pytd.Constant), function (_NameAndSig), alias
          (pytd.Alias), slot (_SlotDecl), and class (pytd.Class) definitions.

    Returns:
      None if the class definition is inside a non-active conditional,
      otherwise a new pytd.Class.
    Raises:
      ParseError: if defs contains duplicate names (excluding multiple
          definitions of a function, which is allowed).
    """
    # Process parent_args, extracting parents and possibly a metaclass.
    parents = []
    metaclass = None
    for i, p in enumerate(parent_args):
      if self._is_parameterized_protocol(p):
        # From PEP 544: "`Protocol[T, S, ...]` is allowed as a shorthand for
        # `Protocol, Generic[T, S, ...]`."
        # https://www.python.org/dev/peps/pep-0544/#generic-protocols
        parents.append(p.base_type)
        parents.append(p.Replace(base_type=pytd.NamedType("typing.Generic")))
      elif isinstance(p, pytd.Type):
        parents.append(p)
      else:
        keyword, value = p
        if i != len(parent_args) - 1:
          raise ParseError("metaclass must be last argument")
        if keyword != "metaclass":
          raise ParseError("Only 'metaclass' allowed as classdef kwarg")
        metaclass = value

    constants, methods, aliases, slots, classes = _split_definitions(defs)
    # TODO(rechen): retain more information about nested classes.
    for cls in classes:
      constants.append(self.new_constant(cls.name, pytd.NamedType("type")))

    all_names = (list(set(f.name for f in methods)) +
                 [c.name for c in constants] +
                 [a.name for a in aliases])
    duplicates = [name
                  for name, count in collections.Counter(all_names).items()
                  if count >= 2]
    if duplicates:
      # TODO(kramm): raise a syntax error right when the identifier is defined.
      raise ParseError("Duplicate identifier(s): " + ", ".join(duplicates))

    # This check is performed after the above error checking so that errors
    # will be spotted even in non-active conditional code.
    if not self._current_condition.active:
      # Returning early is safe because if_end() takes care of discarding
      # definitions inside non-active conditions.
      return

    if aliases:
      vals_dict = {val.name: val for val in constants + aliases + methods}
      for val in aliases:
        name = val.name
        while isinstance(val, pytd.Alias):
          if (not isinstance(val.type, pytd.NamedType) or
              val.type.name not in vals_dict):
            raise ParseError(
                "Illegal value for alias %r. Value must be an attribute "
                "or method on the same class." % val.name)
          val = vals_dict[val.type.name]
        if isinstance(val, _NameAndSig):
          methods.append(val._replace(name=name))
        else:
          constants.append(pytd.Constant(name, val.type))

    # TODO(dbaum): Is NothingType even legal here?  The grammar accepts it but
    # perhaps it should be a ParseError.
    parents = [p for p in parents if not isinstance(p, pytd.NothingType)]
    methods = _merge_method_signatures(methods)
    # Ensure that old style classes inherit from classobj.
    if not parents and class_name not in ["classobj", "object"]:
      parents = (pytd.NamedType("classobj"),)
    return pytd.Class(name=class_name, metaclass=metaclass,
                      parents=tuple(parents),
                      methods=tuple(methods),
                      constants=tuple(constants),
                      slots=slots,
                      template=())

  def add_type_var(self, name, name_arg, args):
    """Add a type variable, <name> = TypeVar(<name_arg>, <args>)."""
    if name != name_arg:
      raise ParseError("TypeVar name needs to be %r (not %r)" % (
          name_arg, name))
    # 'bound' is the only keyword argument we currently use.
    # TODO(rechen): We should enforce the PEP 484 guideline that
    # len(constraints) != 1. However, this guideline is currently violated
    # in typeshed (see https://github.com/python/typeshed/pull/806).
    constraints, named_args = args
    named_args = dict(named_args) if named_args else {}
    extra = set(named_args) - {"bound", "covariant", "contravariant"}
    if extra:
      raise ParseError("Unrecognized keyword(s): %s" % ", ".join(extra))
    if not self._current_condition.active:
      return
    self._type_params.append(pytd.TypeParameter(
        name=name,
        constraints=() if constraints is None else tuple(constraints),
        bound=named_args.get("bound")))

  def _qualify_name(self, orig_name):
    """Qualify an import name."""
    # Doing the "builtins" rename here ensures that we catch alias names.
    orig_name = visitors.RenameBuiltinsPrefixInName(orig_name)
    if not self._package_name:
      return orig_name
    # Generated from "from . import foo" - see parser.y
    prefix, package, name = orig_name.partition("__PACKAGE__.")
    if not prefix and package:
      return self._package_name + "." + name
    if orig_name.startswith("."):
      name = module_utils.get_absolute_name(self._package_name, orig_name)
      if name is None:
        raise ParseError(
            "Cannot resolve relative import %s" % orig_name.rsplit(".", 1)[0])
      return name
    return orig_name


def parse_string(src, name=None, filename=None, python_version=None,
                 platform=None):
  return _Parser(version=python_version, platform=platform).parse(
      src, name, filename)


def parse_file(filename=None, name=None, python_version=None,
               platform=None):
  with open(filename, "r") as fi:
    src = fi.read()
  return _Parser(version=python_version, platform=platform).parse(
      src, name, filename)


def join_types(types):
  """Combine a list of types into a union type, if needed.

  Leaves singular return values alone, or wraps a UnionType around them if there
  are multiple ones, or if there are no elements in the list (or only
  NothingType) return NothingType.

  Arguments:
    types: A list of types. This list might contain other UnionTypes. If
    so, they are flattened.

  Returns:
    A type that represents the union of the types passed in. Order is preserved.
  """
  queue = collections.deque(types)
  seen = set()
  new_types = []
  while queue:
    t = queue.popleft()
    if isinstance(t, pytd.UnionType):
      queue.extendleft(reversed(t.type_list))
    elif isinstance(t, pytd.NothingType):
      pass
    elif t not in seen:
      new_types.append(t)
      seen.add(t)

  if len(new_types) == 1:
    return new_types.pop()
  elif any(isinstance(t, pytd.AnythingType) for t in new_types):
    return pytd.AnythingType()
  elif new_types:
    return pytd.UnionType(tuple(new_types))  # tuple() to make unions hashable
  else:
    return pytd.NothingType()


def _is_property_decorator(decorator):
  # Property decorators are the only ones where dotted names are accepted.
  return decorator and (decorator == "property" or "." in decorator)


def _keep_decorator(decorator):
  """Return True iff the decorator requires processing."""
  if decorator in ["overload"]:
    # These are legal but ignored.
    return False
  elif (decorator in ["staticmethod", "classmethod", "abstractmethod",
                      "coroutine"] or
        _is_property_decorator(decorator)):
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
      # TODO(dbaum): Shouldn't we pass the existing parameter names to
      # InventStarArgParams()?  The legacy parser doesn't, so leaving the
      # code identical to legacy for now.
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
      kwonly = bool(stararg or has_bare_star)
      params.append(_normal_param(name, param_type, default, kwonly))

  return _Params(params,
                 stararg,
                 starstararg,
                 has_bare_star=has_bare_star)


def _normal_param(name, param_type, default, kwonly):
  """Return a pytd.Parameter object for a normal argument."""
  if default is not None:
    default_type = _type_for_default(default)
    if default_type == pytd.NamedType("NoneType"):
      if param_type is not None:
        param_type = pytd.UnionType((param_type, default_type))
    elif param_type is None:
      param_type = default_type
  if param_type is None:
    param_type = pytd.AnythingType()

  optional = default is not None
  return pytd.Parameter(name, param_type, kwonly, optional, None)


def _star_param(name, param_type):
  """Return a pytd.Parameter for a *args argument."""
  if param_type is None:
    param_type = pytd.NamedType("tuple")
  else:
    param_type = pytd.GenericType(
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
    return pytd.AnythingType()


def _split_definitions(defs):
  """Return [constants], [functions] given a mixed list of definitions."""
  constants = []
  functions = []
  aliases = []
  slots = None
  classes = []
  for d in defs:
    if isinstance(d, pytd.Constant):
      if d.name == "__slots__":
        pass  # ignore definitions of __slots__ as a type
      else:
        constants.append(d)
    elif isinstance(d, _NameAndSig):
      functions.append(d)
    elif isinstance(d, pytd.Alias):
      aliases.append(d)
    elif isinstance(d, _SlotDecl):
      if slots is not None:
        raise ParseError("Duplicate __slots__ declaration")
      # Empty tuples are stored as (pytd.NothingType(),).
      if not all(isinstance(p, (pytd.NamedType, pytd.NothingType))
                 for p in d.slots.parameters):
        raise ParseError("Entries in __slots__ can only be strings")
      slots = tuple(p.name for p in d.slots.parameters
                    if isinstance(p, pytd.NamedType))
    elif isinstance(d, pytd.Class):
      classes.append(d)
    else:
      raise TypeError("Unexpected definition type %s" % type(d))
  return constants, functions, aliases, slots, classes


def _is_int_tuple(value):
  """Return whether the value is a tuple of integers."""
  return isinstance(value, tuple) and all(isinstance(v, int) for v in value)


def _three_tuple(value):
  """Append zeros and slice to normalize the tuple to a three-tuple."""
  return (value + (0, 0))[:3]


def _property_decorators(name):
  """Generates the property decorators for a method name.

  Used internally by other methods.

  Args:
    name: method name

  Returns:
    A dictionary of decorators to precedence and required arity
  """
  return {
      "property": _Property(2, 1),
      (name + ".getter"): _Property(2, 1),
      (name + ".setter"): _Property(1, 2),
      (name + ".deleter"): _Property(1, 1)
  }


def _is_property(name, decorator, signature):
  """Parse a signature as a property getter, setter, or deleter.

  Checks that the decorator name matches one of {@property, @foo.getter,
  @foo.setter, @foo.deleter} and that the corresponding signature is valid.

  NOTE: This function assumes that all other recognised decorators have already
  been handled, and will therefore raise if decorator is not a property.

  Args:
    name: method name
    decorator: decorator
    signature: method signature
  Returns:
    True: If we have a valid property decorator
    False: If decorator is None
  Raises:
    ParseError: If we have a non-property decorator.
  """
  if not decorator:
    return False
  sigs = _property_decorators(name)
  if decorator in sigs and sigs[decorator].arity == len(signature.params):
    return True
  raise ParseError("Unhandled decorator: %s" % decorator)


# Strategies for combining a new decorator with an existing one
_MERGE, _REPLACE, _DISCARD = 1, 2, 3


def _check_decorator_overload(name, old, new):
  """Conditions for a decorator to overload an existing one."""
  properties = _property_decorators(name)
  if old == new:
    return _MERGE
  elif old in properties and new in properties:
    p_old, p_new = properties[old].precedence, properties[new].precedence
    if p_old > p_new:
      return _DISCARD
    elif p_old == p_new:
      return _MERGE
    else:
      return _REPLACE
  raise OverloadedDecoratorError(name, "")


def _add_flag_overload(mapping, name, val, flag):
  if name not in mapping:
    mapping[name] = val
  elif mapping[name] != val:
    raise OverloadedDecoratorError(name, flag)


def _merge_method_signatures(signatures):
  """Group the signatures by name, turning each group into a function."""
  name_to_signatures = collections.OrderedDict()
  name_to_decorator = {}
  name_to_is_abstract = {}
  name_to_is_coroutine = {}
  for name, signature, decorator, is_abstract, is_coroutine in signatures:
    if name not in name_to_signatures:
      name_to_signatures[name] = []
      name_to_decorator[name] = decorator
    old_decorator = name_to_decorator[name]
    check = _check_decorator_overload(name, old_decorator, decorator)
    if check == _MERGE:
      name_to_signatures[name].append(signature)
    elif check == _REPLACE:
      name_to_signatures[name] = [signature]
      name_to_decorator[name] = decorator
    _add_flag_overload(name_to_is_abstract, name, is_abstract, "abstractmethod")
    _add_flag_overload(name_to_is_coroutine, name, is_coroutine, "coroutine")
  methods = []
  for name, signatures in name_to_signatures.items():
    decorator = name_to_decorator[name]
    is_abstract = name_to_is_abstract[name]
    is_coroutine = name_to_is_coroutine[name]
    if name == "__new__" or decorator == "staticmethod":
      kind = pytd.STATICMETHOD
    elif decorator == "classmethod":
      kind = pytd.CLASSMETHOD
    elif _is_property(name, decorator, signatures[0]):
      kind = pytd.PROPERTY
      # If we have only setters and/or deleters, replace them with a single
      # method foo(...) -> Any, so that we infer a constant `foo: Any` even if
      # the original method signatures are all `foo(...) -> None`. (If we have a
      # getter we use its return type, but in the absence of a getter we want to
      # fall back on Any since we cannot say anything about what the setter sets
      # the type of foo to.)
      if decorator.endswith(".setter") or decorator.endswith(".deleter"):
        signatures = [signatures[0].Replace(return_type=pytd.AnythingType())]
    else:
      kind = pytd.METHOD
    flags = 0
    if is_abstract:
      flags |= pytd.Function.IS_ABSTRACT
    if is_coroutine:
      flags |= pytd.Function.IS_COROUTINE
    methods.append(pytd.Function(name, tuple(signatures), kind, flags))
  return methods


def _maybe_resolve_alias(alias, name_to_class):
  """If possible, resolve the alias from the class map."""
  if isinstance(alias.type, pytd.NamedType):
    prefix, dot, remainder = alias.type.name.partition(".")
    if dot and prefix in name_to_class:
      try:
        value = name_to_class[prefix].Lookup(remainder)
      except KeyError:
        # There's no need to report an error here, as load_pytd will
        # complain if it can't resolve `prefix`.
        pass
      else:
        return value.Replace(name=alias.name)
  return alias
