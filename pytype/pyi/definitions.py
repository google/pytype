"""Construct and collect pytd definitions to build a TypeDeclUnit."""

import collections
import dataclasses
import sys

from typing import Any, Dict, List, Optional, Union

from pytype.pyi import classdef
from pytype.pyi import metadata
from pytype.pyi import types
from pytype.pyi.types import ParseError  # pylint: disable=g-importing-member
from pytype.pytd import escape
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors
from pytype.pytd.codegen import function
from pytype.pytd.codegen import namedtuple
from pytype.pytd.codegen import pytdgen
from pytype.pytd.parse import node as pytd_node

# pylint: disable=g-import-not-at-top
if sys.version_info >= (3, 8):
  import ast as ast3
else:
  from typed_ast import ast3
# pylint: enable=g-import-not-at-top


# Typing members that represent sets of types.
_TYPING_SETS = ("typing.Intersection", "typing.Optional", "typing.Union")

# Aliases for some typing.X types
_ANNOTATED_TYPES = ("typing.Annotated", "typing_extensions.Annotated")
_CALLABLE_TYPES = ("typing.Callable", "collections.abc.Callable")
_CONCATENATE_TYPES = ("typing.Concatenate", "typing_extensions.Concatenate")
_LITERAL_TYPES = ("typing.Literal", "typing_extensions.Literal")
_TUPLE_TYPES = ("tuple", "builtins.tuple", "typing.Tuple")


class StringParseError(ParseError):
  pass


def _split_definitions(defs: List[Any]):
  """Return [constants], [functions] given a mixed list of definitions."""
  constants = []
  functions = []
  aliases = []
  slots = None
  classes = []
  for d in defs:
    if isinstance(d, pytd.Class):
      classes.append(d)
    elif isinstance(d, pytd.Constant):
      if d.name == "__slots__":
        pass  # ignore definitions of __slots__ as a type
      else:
        constants.append(d)
    elif isinstance(d, function.NameAndSig):
      functions.append(d)
    elif isinstance(d, pytd.Alias):
      aliases.append(d)
    elif isinstance(d, types.SlotDecl):
      if slots is not None:
        raise ParseError("Duplicate __slots__ declaration")
      slots = d.slots
    elif isinstance(d, types.Ellipsis):
      pass
    elif isinstance(d, ast3.Expr):
      raise ParseError("Unexpected expression").at(d)
    else:
      msg = "Unexpected definition"
      lineno = None
      if isinstance(d, ast3.AST):
        lineno = getattr(d, "lineno", None)
      raise ParseError(msg, line=lineno)
  return constants, functions, aliases, slots, classes


def _maybe_resolve_alias(alias, name_to_class, name_to_constant):
  """Resolve the alias if possible.

  Args:
    alias: A pytd.Alias
    name_to_class: A class map used for resolution.
    name_to_constant: A constant map used for resolution.

  Returns:
    None, if the alias pointed to an un-aliasable type.
    The resolved value, if the alias was resolved.
    The alias, if it was not resolved.
  """
  if not isinstance(alias.type, pytd.NamedType):
    return alias
  if alias.type.name in _TYPING_SETS:
    # Filter out aliases to `typing` members that don't appear in typing.pytd
    # to avoid lookup errors.
    return None
  if "." not in alias.type.name:
    # We'll handle nested classes specially, since they need to be represented
    # as constants to distinguish them from imports.
    return alias
  parts = alias.type.name.split(".")
  if parts[0] not in name_to_class and parts[0] not in name_to_constant:
    return alias
  prev_value = None
  value = name_to_class.get(parts[0]) or name_to_constant[parts[0]]
  for part in parts[1:]:
    prev_value = value
    # We can immediately return upon encountering an error, as load_pytd will
    # complain when it can't resolve the alias.
    if isinstance(value, pytd.Constant):
      if (not isinstance(value.type, pytd.NamedType) or
          value.type.name not in name_to_class):
        return alias
      value = name_to_class[value.type.name]
    if not isinstance(value, pytd.Class):
      return alias
    if part in value:
      value = value.Lookup(part)
    else:
      for base in value.bases:
        if base.name not in name_to_class:
          # If the base is unknown, we don't know whether it contains 'part',
          # so it cannot be resolved.
          return alias
        if part in name_to_class[base.name]:
          value = name_to_class[base.name].Lookup(part)
          break  # else continue up the MRO
      else:
        return alias  # unresolved
  if isinstance(value, pytd.Class):
    return pytd.Constant(
        alias.name, pytdgen.pytd_type(pytd.NamedType(alias.type.name)))
  elif isinstance(value, pytd.Function):
    return pytd.AliasMethod(
        value.Replace(name=alias.name),
        from_constant=isinstance(prev_value, pytd.Constant))
  else:
    return value.Replace(name=alias.name)


def pytd_literal(
    parameters: List[Any], aliases: Dict[str, pytd.Alias]) -> pytd.Type:
  """Create a pytd.Literal."""
  literal_parameters = []
  for p in parameters:
    if pytdgen.is_none(p):
      literal_parameters.append(p)
    elif isinstance(p, pytd.NamedType):
      prefix = p.name.rsplit(".", 1)[0]
      # If prefix is a module name, then p is an alias to a Literal in another
      # module. Otherwise, prefix is an enum type and p is a member of the enum.
      if prefix in aliases and isinstance(aliases[prefix].type, pytd.Module):
        literal_parameters.append(p)
      else:
        literal_parameters.append(pytd.Literal(
            pytd.Constant(name=p.name, type=pytd.NamedType(prefix))
        ))
    elif isinstance(p, types.Pyval):
      literal_parameters.append(p.to_pytd_literal())
    elif isinstance(p, pytd.Literal):
      literal_parameters.append(p)
    elif isinstance(p, pytd.UnionType):
      for t in p.type_list:
        if isinstance(t, pytd.Literal):
          literal_parameters.append(t)
        else:
          raise ParseError(f"Literal[{t}] not supported")
    else:
      raise ParseError(f"Literal[{p}] not supported")
  return pytd_utils.JoinTypes(literal_parameters)


def _convert_annotated(x):
  """Convert everything to a string to store it in pytd.Annotated."""
  if isinstance(x, types.Pyval):
    return x.repr_str()
  elif isinstance(x, dict):
    return metadata.to_string(x)
  elif isinstance(x, tuple):
    fn, posargs, kwargs = x
    return metadata.call_to_annotation(fn, posargs=posargs, kwargs=kwargs)
  else:
    raise ParseError(f"Cannot convert metadata {x}")


def pytd_annotated(parameters: List[Any]) -> pytd.Type:
  """Create a pytd.Annotated."""
  if len(parameters) < 2:
    raise ParseError(
        "typing.Annotated takes at least two parameters: "
        "Annotated[type, annotation, ...].")
  typ, *annotations = parameters
  annotations = tuple(map(_convert_annotated, annotations))
  return pytd.Annotated(typ, annotations)


class _InsertTypeParameters(visitors.Visitor):
  """Visitor for inserting TypeParameter instances."""

  def __init__(self, type_params):
    super().__init__()
    self.type_params = {p.name: p for p in type_params}

  def VisitNamedType(self, node):
    if node.name in self.type_params:
      return self.type_params[node.name]
    else:
      return node


class _VerifyMutators(visitors.Visitor):
  """Visitor for verifying TypeParameters used in mutations are in scope."""

  def __init__(self):
    super().__init__()
    # A stack of type parameters introduced into the scope. The top of the stack
    # contains the currently accessible parameter set.
    self.type_params_in_scope = [set()]
    self.current_function = None

  def _AddParams(self, params):
    top = self.type_params_in_scope[-1]
    self.type_params_in_scope.append(top | params)

  def _GetTypeParameters(self, node):
    params = pytd_utils.GetTypeParameters(node)
    return {x.name for x in params}

  def EnterClass(self, node):
    params = set()
    for cls in node.bases:
      params |= self._GetTypeParameters(cls)
    self._AddParams(params)

  def LeaveClass(self, _):
    self.type_params_in_scope.pop()

  def EnterFunction(self, node):
    self.current_function = node
    params = set()
    for sig in node.signatures:
      for arg in sig.params:
        params |= self._GetTypeParameters(arg.type)
      if sig.starargs:
        params |= self._GetTypeParameters(sig.starargs.type)
      if sig.starstarargs:
        params |= self._GetTypeParameters(sig.starstarargs.type)
    self._AddParams(params)

  def LeaveFunction(self, _):
    self.type_params_in_scope.pop()
    self.current_function = None

  def EnterParameter(self, node):
    if isinstance(node.mutated_type, pytd.GenericType):
      params = self._GetTypeParameters(node.mutated_type)
      extra = params - self.type_params_in_scope[-1]
      if extra:
        fn = pytd_utils.Print(self.current_function)
        msg = "Type parameter(s) {{{}}} not in scope in\n\n{}".format(
            ", ".join(sorted(extra)), fn)
        raise ParseError(msg)


class _ContainsAnyType(visitors.Visitor):
  """Check if a pytd object contains a type of any of the given names."""

  def __init__(self, type_names):
    super().__init__()
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

  type_param_names: List[str]
  const_properties: List[List[pytd.Function]]

  def EnterTypeDeclUnit(self, node):
    self.type_param_names = [x.name for x in node.type_params]
    self.const_properties = []

  def LeaveTypeDeclUnit(self, node):
    self.type_param_names = None

  def EnterClass(self, node):
    self.const_properties.append([])

  def LeaveClass(self, node):
    self.const_properties.pop()

  def VisitClass(self, node):
    constants = list(node.constants)
    for fn in self.const_properties[-1]:
      ptypes = [x.return_type for x in fn.signatures]
      prop = pytd.Annotated(base_type=pytd_utils.JoinTypes(ptypes),
                            annotations=("'property'",))
      constants.append(pytd.Constant(name=fn.name, type=prop))
    methods = [x for x in node.methods if x not in self.const_properties[-1]]
    return node.Replace(constants=tuple(constants), methods=tuple(methods))

  def EnterFunction(self, node):
    if (self.const_properties and
        node.kind == pytd.MethodKind.PROPERTY and
        not self._is_parametrised(node)):
      self.const_properties[-1].append(node)

  def _is_parametrised(self, method):
    for sig in method.signatures:
      # 'method' is definitely parametrised if its return type contains a type
      # parameter defined in the current TypeDeclUnit. It's also likely
      # parametrised with an imported TypeVar if 'self' is annotated. ('self' is
      # given a type of Any when unannotated.)
      if (_contains_any_type(sig.return_type, self.type_param_names) or
          sig.params and not isinstance(sig.params[0].type, pytd.AnythingType)):
        return True


class Definitions:
  """Collect definitions used to build a TypeDeclUnit."""

  ELLIPSIS = types.Ellipsis()  # Object to signal ELLIPSIS as a parameter.

  def __init__(self, module_info):
    self.module_info = module_info
    self.type_map: Dict[str, Any] = {}
    self.constants = []
    self.aliases = {}
    self.type_params = []
    self.param_specs = []
    self.all = ()
    self.generated_classes = collections.defaultdict(list)
    self.module_path_map = {}

  def add_alias_or_constant(self, alias_or_constant):
    """Add an alias or constant.

    Args:
      alias_or_constant: the top-level definition to add.

    Raises:
      ParseError: For an invalid __slots__ declaration.
    """
    if isinstance(alias_or_constant, pytd.Constant):
      self.constants.append(alias_or_constant)
    elif isinstance(alias_or_constant, types.SlotDecl):
      raise ParseError("__slots__ only allowed on the class level")
    elif isinstance(alias_or_constant, pytd.Alias):
      name, value = alias_or_constant.name, alias_or_constant.type
      self.type_map[name] = value
      self.aliases[name] = alias_or_constant
    else:
      assert False, "Unknown type of assignment"

  def new_new_type(self, name, typ):
    """Returns a type for a NewType."""
    args = [("self", pytd.AnythingType()), ("val", typ)]
    ret = pytd.NamedType("NoneType")
    methods = function.merge_method_signatures(
        [function.NameAndSig.make("__init__", args, ret)])
    cls_name = escape.pack_newtype_base_class(
        name, len(self.generated_classes[name]))
    cls = pytd.Class(name=cls_name,
                     metaclass=None,
                     bases=(typ,),
                     methods=tuple(methods),
                     constants=(),
                     decorators=(),
                     classes=(),
                     slots=None,
                     template=())
    self.generated_classes[name].append(cls)
    return pytd.NamedType(cls_name)

  def new_named_tuple(self, base_name, fields):
    """Return a type for a named tuple (implicitly generates a class).

    Args:
      base_name: The named tuple's name.
      fields: A list of (name, type) tuples.

    Returns:
      A NamedType() for the generated class that describes the named tuple.
    """
    nt = namedtuple.NamedTuple(base_name, fields, self.generated_classes)
    self.generated_classes[base_name].append(nt.cls)
    self.add_import("typing", ["NamedTuple"])
    return pytd.NamedType(nt.name)

  def new_typed_dict(self, name, items, total):
    """Returns a type for a TypedDict.

    This method is currently called only for TypedDict objects defined via
    the following function-based syntax:

      Foo = TypedDict('Foo', {'a': int, 'b': str}, total=False)

    rather than the recommended class-based syntax.

    Args:
      name: the name of the TypedDict instance, e.g., "'Foo'".
      items: a {key: value_type} dict, e.g., {"'a'": "int", "'b'": "str"}.
      total: A tuple of a single kwarg, e.g., ("total", NamedType("False")), or
        None when no kwarg is passed.
    """
    # TODO(rechen): support total (https://github.com/google/pytype/issues/1195)
    del total  # unused
    cls_name = escape.pack_typeddict_base_class(
        name, len(self.generated_classes[name]))
    constants = tuple(pytd.Constant(k, v) for k, v in items.items())
    cls = pytd.Class(name=cls_name,
                     metaclass=None,
                     bases=(pytd.NamedType("typing.TypedDict"),),
                     methods=(),
                     constants=constants,
                     decorators=(),
                     classes=(),
                     slots=None,
                     template=())
    self.generated_classes[name].append(cls)
    self.add_import("typing", ["TypedDict"])
    return pytd.NamedType(cls_name)

  def add_type_var(self, name, typevar):
    """Add a type variable, <name> = TypeVar(<name_arg>, <args>)."""
    if name != typevar.name:
      raise ParseError(f"TypeVar name needs to be {typevar.name!r} "
                       f"(not {name!r})")
    bound = typevar.bound
    if isinstance(bound, str):
      bound = pytd.NamedType(bound)
    constraints = tuple(typevar.constraints) if typevar.constraints else ()
    self.type_params.append(pytd.TypeParameter(
        name=name, constraints=constraints, bound=bound))

  def add_param_spec(self, name, paramspec):
    if name != paramspec.name:
      raise ParseError(f"ParamSpec name needs to be {paramspec.name!r} "
                       f"(not {name!r})")
    # ParamSpec should probably be represented with its own pytd class, like
    # TypeVar. This is just a quick, hacky way for us to keep track of which
    # names refer to ParamSpecs so we can replace them with Any in
    # _parameterized_type().
    self.param_specs.append(pytd.NamedType(name))

  def add_import(self, from_package, import_list):
    """Add an import.

    Args:
      from_package: A dotted package name if this is a "from" statement, or None
          if it is an "import" statement.
      import_list: A list of imported items, which are either strings or pairs
          of strings.  Pairs are used when items are renamed during import
          using "as".
    """
    if from_package:
      # from a.b.c import d, ...
      for item in import_list:
        t = self.module_info.process_from_import(from_package, item)
        self.type_map[t.new_name] = t.pytd_node
        if (isinstance(item, tuple) or
            from_package != "typing" or
            self.module_info.module_name == "protocols"):
          self.aliases[t.new_name] = t.pytd_alias()
          if t.new_name != "typing":
            # We don't allow the typing module to be mapped to another module,
            # since that would lead to 'from typing import ...' statements to be
            # resolved incorrectly.
            self.module_path_map[t.new_name] = t.qualified_name
    else:
      # import a, b as c, ...
      for item in import_list:
        t = self.module_info.process_import(item)
        if t:
          self.aliases[t.new_name] = t.pytd_alias()

  def _matches_full_name(self, t, full_name):
    """Whether t.name matches full_name in format {module}.{member}."""
    return pytd_utils.MatchesFullName(
        t, full_name, self.module_info.module_name, self.aliases)

  def _matches_named_type(self, t, names):
    """Whether t is a NamedType matching any of names."""
    if not isinstance(t, pytd.NamedType):
      return False
    for name in names:
      if "." in name:
        if self._matches_full_name(t, name):
          return True
      else:
        if t.name == name:
          return True
    return False

  def _is_empty_tuple(self, t):
    return isinstance(t, pytd.TupleType) and not t.parameters

  def _is_heterogeneous_tuple(self, t):
    return isinstance(t, pytd.TupleType)

  def _verify_no_literal_parameters(self, base_type, parameters):
    """Raises an error if 'parameters' contains any literal types."""
    if any(isinstance(p, types.Pyval) for p in parameters):
      if all(not isinstance(p, types.Pyval) or
             p.type == "str" and p.value for p in parameters):
        error_cls = StringParseError
      else:
        error_cls = ParseError
      parameters = ", ".join(
          p.repr_str() if isinstance(p, types.Pyval) else "_"
          for p in parameters)
      raise error_cls(
          f"{pytd_utils.Print(base_type)}[{parameters}] not supported")

  def _is_builtin_or_typing_member(self, t):
    if t.name is None:
      return False
    module, _, name = t.name.rpartition(".")
    return (not module and name in pep484.BUILTIN_TO_TYPING or
            module == "typing" and name in pep484.ALL_TYPING_NAMES)

  def _remove_unsupported_features(self, base_type, parameters):
    """Returns a copy of 'parameters' with unsupported features removed."""
    processed_parameters = []
    # We do not yet support PEP 612, Parameter Specification Variables.
    # To avoid blocking typeshed from adopting this PEP, we convert new
    # features to approximations that only use supported features.
    for p in parameters:
      if p is self.ELLIPSIS:
        processed = pytd.AnythingType()
      elif (p in self.param_specs and
            self._matches_full_name(base_type, "typing.Generic")):
        # Replacing a ParamSpec with a TypeVar isn't correct, but it'll work
        # for simple cases in which the filled value is also a ParamSpec.
        if not any(t.name == p.name for t in self.type_params):
          self.type_params.append(pytd.TypeParameter(p.name))
        processed = p
      elif (p in self.param_specs or
            (isinstance(p, pytd.GenericType) and
             self._matches_full_name(p, _CONCATENATE_TYPES))):
        processed = pytd.AnythingType()
      else:
        processed = p
      processed_parameters.append(processed)
    return tuple(processed_parameters)

  def _parameterized_type(self, base_type: Any, parameters):
    """Return a parameterized type."""
    if self._matches_named_type(base_type, _LITERAL_TYPES):
      return pytd_literal(parameters, self.aliases)
    elif self._matches_named_type(base_type, _ANNOTATED_TYPES):
      return pytd_annotated(parameters)
    self._verify_no_literal_parameters(base_type, parameters)
    if self._matches_named_type(base_type, _TUPLE_TYPES):
      if len(parameters) == 2 and parameters[1] is self.ELLIPSIS:
        parameters = parameters[:1]
        builder = pytd.GenericType
      else:
        builder = pytdgen.heterogeneous_tuple
    elif self._matches_named_type(base_type, _CALLABLE_TYPES):
      if parameters[0] is self.ELLIPSIS:
        parameters = (pytd.AnythingType(),) + parameters[1:]
      builder = pytdgen.pytd_callable
    elif pytdgen.is_any(base_type):
      builder = lambda *_: pytd.AnythingType()
    else:
      assert parameters
      builder = pytd.GenericType
    if (self._is_builtin_or_typing_member(base_type) and
        any(p is self.ELLIPSIS for p in parameters)):
      # TODO(b/217789659): We can only check builtin and typing names for now,
      # since `...` can fill in for a ParamSpec.
      raise ParseError("Unexpected ellipsis parameter")
    parameters = self._remove_unsupported_features(base_type, parameters)
    return builder(base_type, parameters)

  def resolve_type(self, name: Union[str, pytd_node.Node]) -> pytd.Type:
    """Return the fully resolved name for an alias.

    Args:
      name: The name of the type or alias.

    Returns:
      A pytd.NamedType with the fully resolved and qualified name.
    """
    if isinstance(name, (pytd.GenericType, pytd.AnythingType)):
      return name
    if isinstance(name, pytd.NamedType):
      name = name.name
    assert isinstance(name, str)
    if name == "nothing":
      return pytd.NothingType()
    base_type = self.type_map.get(name)
    if base_type is None:
      module, dot, tail = name.partition(".")
      full_name = self.module_path_map.get(module, module) + dot + tail
      base_type = pytd.NamedType(full_name)
    return base_type

  def new_type(
      self,
      name: Union[str, pytd_node.Node],
      parameters: Optional[List[pytd.Type]] = None
  ) -> pytd.Type:
    """Return the AST for a type.

    Args:
      name: The name of the type.
      parameters: List of type parameters.

    Returns:
      A pytd type node.

    Raises:
      ParseError: if the wrong number of parameters is supplied for the
        base_type - e.g., 2 parameters to Optional or no parameters to Union.
    """
    base_type = self.resolve_type(name)
    for p in self.param_specs:
      if base_type.name.startswith(f"{p.name}."):
        _, attr = base_type.name.split(".", 1)
        if attr not in ("args", "kwargs"):
          raise ParseError(f"Unrecognized ParamSpec attribute: {attr}")
        # We do not yet support typing.ParamSpec, so replace references to its
        # args and kwargs attributes with Any.
        return pytd.AnythingType()
    if not isinstance(base_type, pytd.NamedType):
      # We assume that all type parameters have been defined. Since pytype
      # orders type parameters to appear before classes and functions, this
      # assumption is generally safe. AnyStr is special-cased because imported
      # type parameters aren't recognized.
      type_params = self.type_params + [pytd.TypeParameter("typing.AnyStr")]
      base_type = base_type.Visit(_InsertTypeParameters(type_params))
      try:
        resolved_type = visitors.MaybeSubstituteParameters(
            base_type, parameters)
      except ValueError as e:
        raise ParseError(str(e)) from e
      if resolved_type:
        return resolved_type
    if parameters is not None:
      if (len(parameters) > 1 and isinstance(base_type, pytd.NamedType) and
          base_type.name == "typing.Optional"):
        raise ParseError(f"Too many options to {base_type.name}")
      return self._parameterized_type(base_type, parameters)
    else:
      if (isinstance(base_type, pytd.NamedType) and
          base_type.name in _TYPING_SETS):
        raise ParseError(f"Missing options to {base_type.name}")
      return base_type

  def build_class(
      self, class_name, bases, keywords, decorators, defs
  ) -> pytd.Class:
    """Build a pytd.Class from definitions collected from an ast node."""
    bases = classdef.get_bases(bases)
    metaclass = classdef.get_metaclass(keywords)
    constants, methods, aliases, slots, classes = _split_definitions(defs)

    # Make sure we don't have duplicate definitions.
    classdef.check_for_duplicate_defs(methods, constants, aliases)

    if aliases:
      vals_dict = {val.name: val
                   for val in constants + aliases + methods + classes}
      for val in aliases:
        name = val.name
        seen_names = set()
        while isinstance(val, pytd.Alias):
          if isinstance(val.type, pytd.NamedType):
            _, _, base_name = val.type.name.rpartition(".")
            if base_name in seen_names:
              # This happens in cases like:
              # class X:
              #   Y = something.Y
              # Since we try to resolve aliases immediately, we don't know what
              # type to fill in when the alias value comes from outside the
              # class. The best we can do is Any.
              val = pytd.Constant(name, pytd.AnythingType())
              continue
            seen_names.add(base_name)
            if base_name in vals_dict:
              val = vals_dict[base_name]
              continue
          # The alias value comes from outside the class. The best we can do is
          # to fill in Any.
          val = pytd.Constant(name, pytd.AnythingType())
        if isinstance(val, function.NameAndSig):
          val = dataclasses.replace(val, name=name)
          methods.append(val)
        else:
          if isinstance(val, pytd.Class):
            t = pytdgen.pytd_type(pytd.NamedType(class_name + "." + val.name))
          else:
            t = val.type
          constants.append(pytd.Constant(name, t))

    bases = [p for p in bases if not isinstance(p, pytd.NothingType)]
    methods = function.merge_method_signatures(methods)
    if not bases and class_name not in ["classobj", "object"]:
      # A bases-less class inherits from classobj in Python 2 and from object
      # in Python 3. typeshed assumes the Python 3 behavior for all stubs, so we
      # do the same here.
      bases = (pytd.NamedType("object"),)

    return pytd.Class(name=class_name, metaclass=metaclass,
                      bases=tuple(bases),
                      methods=tuple(methods),
                      constants=tuple(constants),
                      classes=tuple(classes),
                      decorators=tuple(decorators),
                      slots=slots,
                      template=())

  def build_type_decl_unit(self, defs) -> pytd.TypeDeclUnit:
    """Return a pytd.TypeDeclUnit for the given defs (plus parser state)."""
    # defs contains both constant and function definitions.
    constants, functions, aliases, slots, classes = _split_definitions(defs)
    assert not slots  # slots aren't allowed on the module level

    # TODO(mdemello): alias/constant handling is broken in some weird manner.
    # assert not aliases # We handle top-level aliases in add_alias_or_constant
    # constants.extend(self.constants)

    if self.module_info.module_name == "builtins":
      constants.extend(types.builtin_keyword_constants())

    if self.all:
      constants.append(
          pytd.Constant("__all__", pytdgen.pytd_list("str"), self.all))

    generated_classes = sum(self.generated_classes.values(), [])

    classes = generated_classes + classes
    functions = function.merge_method_signatures(functions)
    _check_module_functions(functions)

    name_to_class = {c.name: c for c in classes}
    name_to_constant = {c.name: c for c in constants}
    aliases = []
    for a in self.aliases.values():
      t = _maybe_resolve_alias(a, name_to_class, name_to_constant)
      if t is None:
        continue
      elif isinstance(t, pytd.Function):
        functions.append(t)
      elif isinstance(t, pytd.Constant):
        constants.append(t)
      else:
        assert isinstance(t, pytd.Alias)
        aliases.append(t)

    all_names = ([f.name for f in functions] +
                 [c.name for c in constants] +
                 [c.name for c in self.type_params] +
                 [c.name for c in classes] +
                 [c.name for c in aliases])
    duplicates = [name
                  for name, count in collections.Counter(all_names).items()
                  if count >= 2]
    if duplicates:
      raise ParseError(
          "Duplicate top-level identifier(s): " + ", ".join(duplicates))

    return pytd.TypeDeclUnit(name=None,
                             constants=tuple(constants),
                             type_params=tuple(self.type_params),
                             functions=tuple(functions),
                             classes=tuple(classes),
                             aliases=tuple(aliases))


def finalize_ast(ast: pytd.TypeDeclUnit):
  ast = ast.Visit(_PropertyToConstant())
  ast = ast.Visit(_InsertTypeParameters(ast.type_params))
  ast = ast.Visit(_VerifyMutators())
  return ast


def _check_module_functions(functions):
  """Validate top-level module functions."""
  # module.__getattr__ should have a unique signature
  g = [f for f in functions if f.name == "__getattr__"]
  if g and len(g[0].signatures) > 1:
    raise ParseError("Multiple signatures for module __getattr__")

  # module-level functions cannot be properties
  properties = [x for x in functions if x.kind == pytd.MethodKind.PROPERTY]
  if properties:
    prop_names = ", ".join(p.name for p in properties)
    raise ParseError(
        "Module-level functions with property decorators: " + prop_names)
