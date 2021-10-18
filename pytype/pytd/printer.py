"""Printer to output pytd trees in pyi format."""

import collections
import copy
import logging
import re

from pytype.pytd import base_visitor
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd.parse import parser_constants


class PrintVisitor(base_visitor.Visitor):
  """Visitor for converting ASTs back to pytd source code."""
  visits_all_node_types = True
  unchecked_node_names = base_visitor.ALL_NODE_NAMES

  INDENT = " " * 4
  _RESERVED = frozenset(parser_constants.RESERVED +
                        parser_constants.RESERVED_PYTHON)

  def __init__(self, multiline_args=False):
    super().__init__()
    self.class_names = []  # allow nested classes
    self.imports = collections.defaultdict(set)
    self.in_alias = False
    self.in_parameter = False
    self.in_literal = False
    self._unit_name = None
    self._local_names = {}
    self._class_members = set()
    self._typing_import_counts = collections.defaultdict(int)
    self.multiline_args = multiline_args

  def Print(self, node):
    return node.Visit(copy.deepcopy(self))

  def _IsEmptyTuple(self, t):
    """Check if it is an empty tuple."""
    assert isinstance(t, pytd.GenericType)
    return isinstance(t, pytd.TupleType) and not t.parameters

  def _NeedsTupleEllipsis(self, t):
    """Do we need to use Tuple[x, ...] instead of Tuple[x]?"""
    assert isinstance(t, pytd.GenericType)
    if isinstance(t, pytd.TupleType):
      return False  # TupleType is always heterogeneous.
    return t.base_type == "tuple"

  def _NeedsCallableEllipsis(self, t):
    """Check if it is typing.Callable type."""
    assert isinstance(t, pytd.GenericType)
    return t.name == "typing.Callable"

  def _RequireImport(self, module, name=None):
    """Register that we're using name from module.

    Args:
      module: string identifier.
      name: if None, means we want 'import module'. Otherwise string identifier
       that we want to import.
    """
    self.imports[module].add(name)

  def _GenerateImportStrings(self):
    """Generate import statements needed by the nodes we've visited so far.

    Returns:
      List of strings.
    """
    ret = []
    for module in sorted(self.imports):
      names = set(self.imports[module])
      if module == "typing":
        need_typing = False
        for (name, count) in self._typing_import_counts.items():
          if count:
            need_typing = True
          else:
            names.discard(name)
        if not need_typing:
          names.discard(None)
      if None in names:
        ret.append(f"import {module}")
        names.remove(None)

      if names:
        name_str = ", ".join(sorted(names))
        ret.append(f"from {module} import {name_str}")

    return ret

  def _IsBuiltin(self, module):
    return module == "builtins"

  def _FormatTypeParams(self, type_params):
    formatted_type_params = []
    for t in type_params:
      args = [f"'{t.name}'"]
      args += [self.Print(c) for c in t.constraints]
      if t.bound:
        args.append(f"bound={self.Print(t.bound)}")
      formatted_type_params.append(f"{t.name} = TypeVar({', '.join(args)})")
    return sorted(formatted_type_params)

  def _NameCollision(self, name):

    def name_in(members):
      return name in members or f"{self._unit_name}.{name}" in members

    return name_in(self._class_members) or name_in(self._local_names)

  def _FromTyping(self, name):
    self._typing_import_counts[name] += 1
    if self._NameCollision(name):
      self._RequireImport("typing")
      return f"typing.{name}"
    else:
      self._RequireImport("typing", name)
      return name

  def _ImportTypingExtension(self, name):
    # `name` is a typing construct that is not supported in all Python versions.
    if self._local_names.get(name) == "alias":
      # A typing_extensions import is parsed as Alias(X, typing_extensions.X).
      # If we see an alias to `name`, assume it's been explicitly imported from
      # typing_extensions due to the current Python version not supporting it.
      return name
    else:
      return self._FromTyping(name)

  def EnterTypeDeclUnit(self, unit):
    self._unit_name = unit.name
    for definitions, label in [(unit.classes, "class"),
                               (unit.functions, "function"),
                               (unit.constants, "constant"),
                               (unit.type_params, "type_param"),
                               (unit.aliases, "alias")]:
      for defn in definitions:
        self._local_names[defn.name] = label

  def LeaveTypeDeclUnit(self, _):
    self._unit_name = None
    self._local_names = {}

  def VisitTypeDeclUnit(self, node):
    """Convert the AST for an entire module back to a string."""
    if node.type_params:
      self._FromTyping("TypeVar")

    aliases = []
    imports = set(self._GenerateImportStrings())
    for alias in node.aliases:
      if alias.startswith(("from ", "import ")):
        imports.add(alias)
      else:
        aliases.append(alias)

    # Sort import lines lexicographically and ensure import statements come
    # before from-import statements.
    imports = sorted(imports, key=lambda s: (s.startswith("from "), s))

    sections = [
        imports,
        aliases,
        node.constants,
        self._FormatTypeParams(self.old_node.type_params),
        node.classes,
        node.functions,
    ]

    # We put one blank line after every class,so we need to strip the blank line
    # after the last class.
    sections_as_string = ("\n".join(section_suite).rstrip()
                          for section_suite in sections
                          if section_suite)
    return "\n\n".join(sections_as_string)

  def VisitConstant(self, node):
    """Convert a class-level or module-level constant to a string."""
    if self.in_literal:
      module, _, name = node.name.partition(".")
      assert module == "builtins", module
      assert name in ("True", "False"), name
      return name
    else:
      return f"{node.name}: {node.type}"

  def EnterAlias(self, _):
    self.old_imports = self.imports.copy()

  def VisitAlias(self, node):
    """Convert an import or alias to a string."""
    if isinstance(self.old_node.type, (pytd.NamedType, pytd.ClassType)):
      full_name = self.old_node.type.name
      suffix = ""
      module, _, name = full_name.rpartition(".")
      if module:
        alias_name = self.old_node.name
        if alias_name.startswith(f"{self._unit_name}."):
          alias_name = alias_name[len(self._unit_name)+1:]
        if name not in ("*", alias_name):
          suffix += f" as {alias_name}"
        self.imports = self.old_imports  # undo unnecessary imports change
        return f"from {module} import {name}{suffix}"
    elif isinstance(self.old_node.type, (pytd.Constant, pytd.Function)):
      return self.Print(self.old_node.type.Replace(name=node.name))
    elif isinstance(self.old_node.type, pytd.Module):
      return node.type
    return f"{node.name} = {node.type}"

  def EnterClass(self, node):
    """Entering a class - record class name for children's use."""
    n = node.name
    if node.template:
      n += "[{}]".format(", ".join(self.Print(t) for t in node.template))
    for member in node.methods + node.constants:
      self._class_members.add(member.name)
    self.class_names.append(n)
    # Class decorators are resolved to their underlying functions, but all we
    # output is '@{decorator.name}', so we do not want to visit the Function()
    # node and collect types etc. (In particular, we would add a spurious import
    # of 'Any' when generating a decorator for an InterpreterClass.)
    return {"decorators"}

  def LeaveClass(self, unused_node):
    self._class_members.clear()
    self.class_names.pop()

  def VisitClass(self, node):
    """Visit a class, producing a multi-line, properly indented string."""
    parents = node.parents
    # If object is the only parent, we don't need to list any parents.
    if parents == ("object",):
      parents = ()
    if node.metaclass is not None:
      parents += ("metaclass=" + node.metaclass,)
    parents_str = f"({', '.join(parents)})" if parents else ""
    header = [f"class {node.name}{parents_str}:"]
    if node.slots is not None:
      slots_str = ", ".join(f"\"{s}\"" for s in node.slots)
      slots = [self.INDENT + f"__slots__ = [{slots_str}]"]
    else:
      slots = []
    decorators = ["@" + self.VisitNamedType(d)
                  for d in self.old_node.decorators]
    if node.classes or node.methods or node.constants or slots:
      # We have multiple methods, and every method has multiple signatures
      # (i.e., the method string will have multiple lines). Combine this into
      # an array that contains all the lines, then indent the result.
      class_lines = sum((m.splitlines() for m in node.classes), [])
      classes = [self.INDENT + m for m in class_lines]
      constants = [self.INDENT + m for m in node.constants]
      method_lines = sum((m.splitlines() for m in node.methods), [])
      methods = [self.INDENT + m for m in method_lines]
    else:
      header[-1] += " ..."
      constants = []
      classes = []
      methods = []
    lines = decorators + header + slots + classes + constants + methods
    return "\n".join(lines) + "\n"

  def VisitFunction(self, node):
    """Visit function, producing multi-line string (one for each signature)."""
    function_name = node.name
    decorators = ""
    if (node.kind == pytd.MethodTypes.STATICMETHOD and
        function_name != "__new__"):
      decorators += "@staticmethod\n"
    elif (node.kind == pytd.MethodTypes.CLASSMETHOD and
          function_name != "__init_subclass__"):
      decorators += "@classmethod\n"
    elif node.kind == pytd.MethodTypes.PROPERTY:
      decorators += "@property\n"
    if node.is_abstract:
      decorators += "@abstractmethod\n"
    if node.is_coroutine:
      decorators += "@coroutine\n"
    if len(node.signatures) > 1:
      decorators += "@" + self._FromTyping("overload") + "\n"
    signatures = "\n".join(decorators + "def " + function_name + sig
                           for sig in node.signatures)
    return signatures

  def _FormatContainerContents(self, node):
    """Print out the last type parameter of a container. Used for *args/**kw."""
    assert isinstance(node, pytd.Parameter)
    if isinstance(node.type, pytd.GenericType):
      container_name = node.type.name.rpartition(".")[2]
      assert container_name in ("tuple", "dict")
      self._typing_import_counts[container_name.capitalize()] -= 1
      # If the type is "Any", e.g. `**kwargs: Any`, decrement Any to avoid an
      # extraneous import of typing.Any. Any was visited before this function
      # transformed **kwargs, so it was incremented at least once already.
      if isinstance(node.type.parameters[-1], pytd.AnythingType):
        self._typing_import_counts["Any"] -= 1
      return self.Print(
          node.Replace(type=node.type.parameters[-1], optional=False))
    else:
      return self.Print(node.Replace(type=pytd.AnythingType(), optional=False))

  def VisitSignature(self, node):
    """Visit a signature, producing a string."""
    if node.return_type == "nothing":
      return_type = "NoReturn"  # a prettier alias for nothing
      self._FromTyping(return_type)
    else:
      return_type = node.return_type
    ret = f" -> {return_type}"

    # Put parameters in the right order:
    # (arg1, arg2, *args, kwonly1, kwonly2, **kwargs)
    if self.old_node.starargs is not None:
      starargs = self._FormatContainerContents(self.old_node.starargs)
    else:
      # We don't have explicit *args, but we might need to print "*", for
      # kwonly params.
      starargs = ""
    params = node.params
    for i, p in enumerate(params):
      if self.old_node.params[i].kwonly:
        assert all(p.kwonly for p in self.old_node.params[i:])
        params = params[0:i] + ("*"+starargs,) + params[i:]
        break
    else:
      if starargs:
        params += (f"*{starargs}",)
    if self.old_node.starstarargs is not None:
      starstarargs = self._FormatContainerContents(self.old_node.starstarargs)
      params += (f"**{starstarargs}",)

    body = []
    # Handle Mutable parameters
    # pylint: disable=no-member
    # (old_node is set in parse/node.py)
    mutable_params = [(p.name, p.mutated_type) for p in self.old_node.params
                      if p.mutated_type is not None]
    # pylint: enable=no-member
    for name, new_type in mutable_params:
      body.append("\n{indent}{name} = {new_type}".format(
          indent=self.INDENT, name=name, new_type=self.Print(new_type)))
    for exc in node.exceptions:
      body.append("\n{indent}raise {exc}()".format(indent=self.INDENT, exc=exc))
    if not body:
      body.append(" ...")

    if self.multiline_args:
      indent = "\n" + self.INDENT
      params = ",".join([indent + p for p in params])
      return "({params}\n){ret}:{body}".format(
          params=params, ret=ret, body="".join(body))
    else:
      params = ", ".join(params)
      return "({params}){ret}:{body}".format(
          params=params, ret=ret, body="".join(body))

  def EnterParameter(self, unused_node):
    assert not self.in_parameter
    self.in_parameter = True

  def LeaveParameter(self, unused_node):
    assert self.in_parameter
    self.in_parameter = False

  def VisitParameter(self, node):
    """Convert a function parameter to a string."""
    suffix = " = ..." if node.optional else ""
    if node.type == "Any":
      # Abbreviated form. "Any" is the default.
      self._typing_import_counts["Any"] -= 1
      return node.name + suffix
    # For parameterized class, for example: ClsName[T, V].
    # Its name is `ClsName` before `[`.
    elif node.name == "self" and self.class_names and (
        self.class_names[-1].split("[")[0] == node.type.split("[")[0]):
      if "[" in node.type:
        elided = node.type.split("[", 1)[-1]
        for k in self._typing_import_counts:
          if re.search(r"(^|\W)%s($|\W)" % k, elided):
            self._typing_import_counts[k] -= 1
      return node.name + suffix
    elif node.name == "cls" and self.class_names and (
        node.type == "Type[%s]" % self.class_names[-1]):
      self._typing_import_counts["Type"] -= 1
      return node.name + suffix
    elif node.type is None:
      logging.warning("node.type is None")
      return node.name
    else:
      return node.name + ": " + node.type + suffix

  def VisitTemplateItem(self, node):
    """Convert a template to a string."""
    return node.type_param

  def VisitNamedType(self, node):
    """Convert a type to a string."""
    prefix, _, suffix = node.name.rpartition(".")
    if self._IsBuiltin(prefix) and not self._NameCollision(suffix):
      node_name = suffix
    elif prefix == "typing":
      node_name = self._FromTyping(suffix)
    elif (prefix and
          prefix != self._unit_name and
          prefix not in self._local_names):
      if self.class_names and "." in self.class_names[-1]:
        # We've already fully qualified the class names.
        class_prefix = self.class_names[-1]
      else:
        class_prefix = ".".join(self.class_names)
      if self._unit_name:
        class_prefixes = {class_prefix, f"{self._unit_name}.{class_prefix}"}
      else:
        class_prefixes = {class_prefix}
      if prefix not in class_prefixes:
        # If the prefix doesn't match the class scope, then it's an import.
        self._RequireImport(prefix)
      node_name = node.name
    else:
      node_name = node.name
    if node_name == "NoneType":
      # PEP 484 allows this special abbreviation.
      return "None"
    else:
      return node_name

  def VisitLateType(self, node):
    return self.VisitNamedType(node)

  def VisitClassType(self, node):
    return self.VisitNamedType(node)

  def VisitStrictType(self, node):
    # 'StrictType' is defined, and internally used, by booleq.py. We allow it
    # here so that booleq.py can use pytd_utils.Print().
    return self.VisitNamedType(node)

  def VisitAnythingType(self, unused_node):
    """Convert an anything type to a string."""
    return self._FromTyping("Any")

  def VisitNothingType(self, unused_node):
    """Convert the nothing type to a string."""
    return "nothing"

  def VisitTypeParameter(self, node):
    return node.name

  def VisitModule(self, node):
    if node.is_aliased:
      return f"import {node.module_name} as {node.name}"
    else:
      return f"import {node.module_name}"

  def MaybeCapitalize(self, name):
    """Capitalize a generic type, if necessary."""
    capitalized = pep484.PEP484_MaybeCapitalize(name)
    if capitalized:
      return self._FromTyping(capitalized)
    else:
      return name

  def VisitGenericType(self, node):
    """Convert a generic type to a string."""
    parameters = node.parameters
    if self._IsEmptyTuple(node):
      parameters = ("()",)
    elif self._NeedsTupleEllipsis(node):
      parameters += ("...",)
    elif self._NeedsCallableEllipsis(self.old_node):
      # Callable[Any, X] is rewritten to Callable[..., X].
      self._typing_import_counts["Any"] -= 1
      parameters = ("...",) + parameters[1:]
    return (self.MaybeCapitalize(node.base_type) +
            "[" + ", ".join(parameters) + "]")

  def VisitCallableType(self, node):
    typ = self.MaybeCapitalize(node.base_type)
    args = ", ".join(node.args)
    return f"{typ}[[{args}], {node.ret}]"

  def VisitTupleType(self, node):
    return self.VisitGenericType(node)

  def VisitUnionType(self, node):
    """Convert a union type ("x or y") to a string."""
    type_list = self._FormSetTypeList(node)
    return self._BuildUnion(type_list)

  def VisitIntersectionType(self, node):
    """Convert a intersection type ("x and y") to a string."""
    type_list = self._FormSetTypeList(node)
    return self._BuildIntersection(type_list)

  def _FormSetTypeList(self, node):
    """Form list of types within a set type."""
    type_list = collections.OrderedDict.fromkeys(node.type_list)
    if self.in_parameter:
      # Parameter's set types are merged after as a follow up to the
      # ExpandCompatibleBuiltins visitor.
      for compat, name in pep484.COMPAT_ITEMS:
        # name can replace compat.
        if compat in type_list and name in type_list:
          del type_list[compat]
    return type_list

  def _BuildUnion(self, type_list):
    """Builds a union of the types in type_list.

    Args:
      type_list: A list of strings representing types.

    Returns:
      A string representing the union of the types in type_list. Simplifies
      Union[X] to X and Union[X, None] to Optional[X].
    """
    # Collect all literals, so we can print them using the Literal[x1, ..., xn]
    # syntactic sugar.
    literals = []
    new_type_list = []
    for t in type_list:
      match = re.fullmatch(r"Literal\[(?P<content>.*)\]", t)
      if match:
        literals.append(match.group("content"))
      else:
        new_type_list.append(t)
    if literals:
      new_type_list.append("Literal[%s]" % ", ".join(literals))
    if len(new_type_list) == 1:
      return new_type_list[0]
    elif "None" in new_type_list:
      return (self._FromTyping("Optional") + "[" +
              self._BuildUnion(t for t in new_type_list if t != "None") + "]")
    else:
      return self._FromTyping("Union") + "[" + ", ".join(new_type_list) + "]"

  def _BuildIntersection(self, type_list):
    """Builds a intersection of the types in type_list.

    Args:
      type_list: A list of strings representing types.

    Returns:
      A string representing the intersection of the types in type_list.
      Simplifies Intersection[X] to X and Intersection[X, None] to Optional[X].
    """
    type_list = tuple(type_list)
    if len(type_list) == 1:
      return type_list[0]
    else:
      return " and ".join(type_list)

  def EnterLiteral(self, _):
    assert not self.in_literal
    self.in_literal = True

  def LeaveLiteral(self, _):
    assert self.in_literal
    self.in_literal = False

  def VisitLiteral(self, node):
    base = self._ImportTypingExtension("Literal")
    return f"{base}[{node.value}]"

  def VisitAnnotated(self, node):
    base = self._ImportTypingExtension("Annotated")
    annotations = ", ".join(node.annotations)
    return f"{base}[{node.base_type}, {annotations}]"
