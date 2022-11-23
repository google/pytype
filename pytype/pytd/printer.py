"""Printer to output pytd trees in pyi format."""

import collections
import copy
import keyword
import logging
import re

from pytype import utils
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
    self.in_constant = False
    self.in_signature = False
    self.multiline_args = multiline_args

    self._unit = None
    self._local_names = {}
    self._class_members = set()
    self._typing_import_counts = collections.defaultdict(int)
    self._module_aliases = {}
    self._alias_imports = collections.defaultdict(set)

  def Print(self, node):
    return node.Visit(copy.deepcopy(self))

  def _IsEmptyTuple(self, t: pytd.GenericType) -> bool:
    """Check if it is an empty tuple."""
    return isinstance(t, pytd.TupleType) and not t.parameters

  def _NeedsTupleEllipsis(self, t: pytd.GenericType) -> bool:
    """Do we need to use Tuple[x, ...] instead of Tuple[x]?"""
    if isinstance(t, pytd.TupleType):
      return False  # TupleType is always heterogeneous.
    return t.base_type == "tuple"

  def _NeedsCallableEllipsis(self, t: pytd.GenericType) -> bool:
    """Check if it is typing.Callable type."""
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
    imports = self.imports.copy()
    for k in self._alias_imports:
      imports[k] = imports[k] | self._alias_imports[k]
    for module in sorted(imports):
      names = set(imports[module])
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
      return name in members or (
          self._unit and f"{self._unit.name}.{name}" in members)

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
    if self._unit and self._unit.name:
      full_name = f"{self._unit.name}.{name}"
    else:
      full_name = name
    # `name` is a typing construct that is not supported in all Python versions.
    if (self._local_names.get(name) == "alias" or
        self._local_names.get(full_name) == "alias"):
      # A typing_extensions import is parsed as Alias(X, typing_extensions.X).
      # If we see an alias to `name`, assume it's been explicitly imported from
      # typing_extensions due to the current Python version not supporting it.
      return name
    else:
      return self._FromTyping(name)

  def _StripUnitPrefix(self, name):
    if self._unit:
      return utils.strip_prefix(name, f"{self._unit.name}.")
    else:
      return name

  def EnterTypeDeclUnit(self, unit):
    self._unit = unit
    for definitions, label in [(unit.classes, "class"),
                               (unit.functions, "function"),
                               (unit.constants, "constant"),
                               (unit.type_params, "type_param"),
                               (unit.aliases, "alias")]:
      for defn in definitions:
        self._local_names[defn.name] = label
    for alias in unit.aliases:
      # Modules are represented as NamedTypes in partially resolved asts and
      # sometimes as LateTypes in asts modified for pickling.
      if isinstance(alias.type, pytd.Module):
        module_name = alias.type.module_name
      elif isinstance(alias.type, (pytd.NamedType, pytd.LateType)):
        module_name = alias.type.name
      else:
        continue
      name = self._StripUnitPrefix(alias.name)
      self._module_aliases[module_name] = name

  def LeaveTypeDeclUnit(self, _):
    self._unit = None
    self._local_names = {}

  def VisitTypeDeclUnit(self, node):
    """Convert the AST for an entire module back to a string."""
    if node.type_params:
      self._FromTyping("TypeVar")

    aliases = []
    imports = set(self._GenerateImportStrings())
    for alias in filter(None, node.aliases):
      if alias.startswith(("from ", "import ")):
        imports.add(alias)
      else:
        aliases.append(alias)

    # Sort import lines lexicographically and ensure import statements come
    # before from-import statements.
    imports = sorted(imports, key=lambda s: (s.startswith("from "), s))

    # Remove deleted constants
    constants = [c for c in node.constants if "<deleted>" not in c]

    sections = [
        imports,
        aliases,
        constants,
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

  def EnterConstant(self, node):
    self.in_constant = True

  def LeaveConstant(self, node):
    self.in_constant = False

  def _DropTypingConstant(self, node):
    # Hack to account for a corner case in late annotation handling.
    # If we have a top-level constant of the exact form
    #   Foo: Type[typing.Foo]
    # we drop the constant and rewrite it to
    #   from typing import Foo
    if self.class_names or node.value:
      return False
    if node.type == f"Type[typing.{node.name}]":
      self._RequireImport("typing", node.name)
      self._typing_import_counts["Type"] -= 1
      del self._local_names[node.name]
      return True

  def VisitConstant(self, node):
    """Convert a class-level or module-level constant to a string."""
    if self.in_literal:
      # This should be either True, False or an enum. For the booleans, strip
      # off the module name. For enums, print the whole name.
      if "builtins." in node.name:
        _, _, name = node.name.partition(".")
        return name
      else:
        return node.name
    # Decrement Any, since the actual value is never printed.
    if node.value == "Any":
      self._typing_import_counts["Any"] -= 1
    if self._DropTypingConstant(node):
      return "<deleted>"
    # Whether the constant has a default value is important for fields in
    # generated classes like namedtuples.
    suffix = " = ..." if node.value else ""
    return f"{node.name}: {node.type}{suffix}"

  def EnterAlias(self, _):
    self.old_imports = self.imports.copy()

  def VisitAlias(self, node):
    """Convert an import or alias to a string (or None if handled elsewhere)."""
    if (isinstance(self.old_node.type,
                   (pytd.NamedType, pytd.ClassType, pytd.LateType)) and
        not self.in_constant and not self.in_signature):
      full_name = self.old_node.type.name
      suffix = ""
      module, _, name = full_name.rpartition(".")
      if module:
        alias_name = self._StripUnitPrefix(self.old_node.name)
        if name not in ("*", alias_name):
          suffix += f" as {alias_name}"
        self.imports = self.old_imports  # undo unnecessary imports change
        self._alias_imports[module].add(f"{name}{suffix}")
        # Return None here since we do not want to emit the import statement
        # from both self._alias_imports and unit.aliases
        return None
    elif isinstance(self.old_node.type, (pytd.Constant, pytd.Function)):
      return self.Print(self.old_node.type.Replace(name=node.name))
    elif isinstance(self.old_node.type, pytd.Module):
      return node.type
    return f"{node.name} = {node.type}"

  def EnterClass(self, node):
    """Entering a class - record class name for children's use."""
    n = node.name
    if node.template:
      n += f"[{', '.join(self.Print(t) for t in node.template)}]"
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
    bases = node.bases
    if bases == ("TypedDict",):
      constants = {}
      for c in node.constants:
        name, typ = c.split(": ")
        constants[name] = typ
      if any(keyword.iskeyword(name) for name in constants):
        # We output the TypedDict in functional form, since using the class form
        # would produce a parse error when the pyi file is ingested.
        fields = "{%s}" % ", ".join(f"{name!r}: {typ}"
                                    for name, typ in constants.items())
        return f"{node.name} = TypedDict('{node.name}', {fields})"
    # If object is the only base, we don't need to list any bases.
    if bases == ("object",):
      bases = ()
    if node.metaclass is not None:
      bases += ("metaclass=" + node.metaclass,)
    bases_str = f"({', '.join(bases)})" if bases else ""
    header = [f"class {node.name}{bases_str}:"]
    if node.slots is not None:
      slots_str = ", ".join(f"\"{s}\"" for s in node.slots)
      slots = [self.INDENT + f"__slots__ = [{slots_str}]"]
    else:
      slots = []
    decorators = ["@" + self.VisitNamedType(d)
                  for d in self.old_node.decorators]
    # Our handling of class decorators is a bit hacky (see output.py); this
    # makes sure that typing classes read in directly from a pyi file and then
    # reemitted (e.g. in assertTypesMatchPytd) have their required module
    # imports handled correctly.
    for d in self.old_node.decorators:
      if d.type.name.startswith("typing."):
        self.VisitNamedType(d.type)
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
    if node.is_final:
      decorators += "@" + self._FromTyping("final") + "\n"
    if (node.kind == pytd.MethodKind.STATICMETHOD and
        function_name != "__new__"):
      decorators += "@staticmethod\n"
    elif (node.kind == pytd.MethodKind.CLASSMETHOD and
          function_name != "__init_subclass__"):
      decorators += "@classmethod\n"
    elif node.kind == pytd.MethodKind.PROPERTY:
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

  def _FormatContainerContents(self, node: pytd.Parameter) -> str:
    """Print out the last type parameter of a container. Used for *args/**kw."""
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

  def EnterSignature(self, node):
    self.in_signature = True

  def LeaveSignature(self, node):
    self.in_signature = False

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
    params = []
    for i, p in enumerate(node.params):
      if self.old_node.params[i].kind == pytd.ParameterKind.KWONLY:
        assert all(p.kind == pytd.ParameterKind.KWONLY
                   for p in self.old_node.params[i:])
        params.append("*" + starargs)
        params.extend(node.params[i:])
        break
      params.append(p)
      if (self.old_node.params[i].kind == pytd.ParameterKind.POSONLY and
          (i == len(node.params)-1 or
           self.old_node.params[i+1].kind != pytd.ParameterKind.POSONLY)):
        params.append("/")
    else:
      if starargs:
        params.append(f"*{starargs}")
    if self.old_node.starstarargs is not None:
      starstarargs = self._FormatContainerContents(self.old_node.starstarargs)
      params.append(f"**{starstarargs}")

    body = []
    # Handle Mutable parameters
    # pylint: disable=no-member
    # (old_node is set in parse/node.py)
    mutable_params = [(p.name, p.mutated_type) for p in self.old_node.params
                      if p.mutated_type is not None]
    # pylint: enable=no-member
    for name, new_type in mutable_params:
      body.append(f"\n{self.INDENT}{name} = {self.Print(new_type)}")
    for exc in node.exceptions:
      body.append(f"\n{self.INDENT}raise {exc}()")
    if not body:
      body.append(" ...")

    if self.multiline_args:
      indent = "\n" + self.INDENT
      params = ",".join([indent + p for p in params])
      return f"({params}\n){ret}:{''.join(body)}"
    else:
      params = ", ".join(params)
      return f"({params}){ret}:{''.join(body)}"

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
        node.type == f"Type[{self.class_names[-1]}]"):
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

  def _UseExistingModuleAlias(self, name):
    prefix, suffix = name.rsplit(".", 1)
    while prefix:
      if prefix in self._module_aliases:
        return f"{self._module_aliases[prefix]}.{suffix}"
      prefix, _, remainder = prefix.rpartition(".")
      suffix = f"{remainder}.{suffix}"
    return None

  def _GuessModule(self, maybe_module):
    """Guess which part of the given name is the module prefix."""
    if "." not in maybe_module:
      return maybe_module, ""
    prefix, suffix = maybe_module.rsplit(".", 1)
    # Heuristic: modules are typically lowercase, classes uppercase.
    if suffix[0].islower():
      return maybe_module, ""
    else:
      module, rest = self._GuessModule(prefix)
      return module, f"{rest}.{suffix}" if rest else suffix

  def VisitNamedType(self, node):
    """Convert a type to a string."""
    prefix, _, suffix = node.name.rpartition(".")
    if self._IsBuiltin(prefix) and not self._NameCollision(suffix):
      node_name = suffix
    elif prefix == "typing":
      node_name = self._FromTyping(suffix)
    elif prefix == "typing_extensions":
      node_name = self._ImportTypingExtension(suffix)
    elif "." not in node.name:
      node_name = node.name
    else:
      if self._unit:
        try:
          pytd.LookupItemRecursive(self._unit, self._StripUnitPrefix(node.name))
        except KeyError:
          aliased_name = self._UseExistingModuleAlias(node.name)
          if aliased_name:
            node_name = aliased_name
          else:
            module, rest = self._GuessModule(prefix)
            module_alias = module
            while self._NameCollision(module_alias):
              module_alias = f"_{module_alias}"
            if module_alias == module:
              self._RequireImport(module)
              node_name = node.name
            else:
              self._RequireImport(f"{module} as {module_alias}")
              node_name = ".".join(filter(bool, (module_alias, rest, suffix)))
        else:
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
    if self.in_constant or self.in_signature:
      return "module"
    elif not node.is_aliased:
      return f"import {node.module_name}"
    elif "." in node.module_name:
      # `import x.y as z` and `from x import y as z` are equivalent, but the
      # latter is a bit prettier.
      prefix, suffix = node.module_name.rsplit(".", 1)
      imp = f"from {prefix} import {suffix}"
      if node.name != suffix:
        imp += f" as {node.name}"
      return imp
    else:
      return f"import {node.module_name} as {node.name}"

  def MaybeCapitalize(self, name):
    """Capitalize a generic type, if necessary."""
    if name in pep484.BUILTIN_TO_TYPING:
      return self._FromTyping(pep484.BUILTIN_TO_TYPING[name])
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
      param = self.old_node.parameters[0]
      # Callable[Any, X] is rewritten to Callable[..., X].
      if isinstance(param, pytd.AnythingType):
        self._typing_import_counts["Any"] -= 1
      else:
        assert isinstance(param, (pytd.NothingType, pytd.TypeParameter)), param
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
    type_list = dict.fromkeys(node.type_list)
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
      new_type_list.append(f"Literal[{', '.join(literals)}]")
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
