# -*- coding:utf-8; python-indent:2; indent-tabs-mode:nil -*-

# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Visitor(s) for walking ASTs.

This module contains broadly useful basic visitors. Visitors that are more
specialized to pytype are in visitors.py. If you see a visitor there that you'd
like to use, feel free to propose moving it here.
"""

import collections
import logging

from pytype.pytd import pytd
from pytype.pytd.parse import parser_constants
from pytype.typegraph import cfg_utils


# A convenient value for unchecked_node_classnames if a visitor wants to
# use unchecked nodes everywhere.
ALL_NODE_NAMES = type(
    "contains_everything",
    (),
    {"__contains__": lambda *args: True})()


class _NodeClassInfo(object):
  """Representation of a node class in the precondition graph."""

  def __init__(self, cls):
    self.cls = cls  # The class object.
    self.name = cls.__name__
    # The set of NodeClassInfo objects that may appear below this particular
    # type of node.  Initially empty, filled in by examining preconditions.
    self.outgoing = set()


def _FindNodeClasses():
  """Yields _NodeClassInfo objects for each node found in pytd."""
  for name in dir(pytd):
    value = getattr(pytd, name)
    if isinstance(value, type) and hasattr(value, "_CHECKER"):
      yield _NodeClassInfo(value)


_IGNORED_TYPENAMES = set(["str", "bool", "int", "NoneType"])
_ancestor_map = None  # Memoized ancestors map.


def _GetAncestorMap():
  """Return a map of node class names to a set of ancestor class names."""

  global _ancestor_map
  if _ancestor_map is None:
    # Map from name to _NodeClassInfo.
    node_classes = {i.name: i for i in _FindNodeClasses()}

    # Update _NodeClassInfo.outgoing based on preconditions.
    for info in node_classes.values():
      for allowed in info.cls._CHECKER.allowed_types():  # pylint: disable=protected-access
        if isinstance(allowed, type):
          # All subclasses of the type are allowed.
          info.outgoing.update(
              [i for i in node_classes.values() if issubclass(i.cls, allowed)])
        elif allowed in node_classes:
          info.outgoing.add(node_classes[allowed])
        elif allowed not in _IGNORED_TYPENAMES:
          # This means preconditions list a typename that is unknown.  If it
          # is a node then make sure _FindNodeClasses() can discover it.  If it
          # is not a node, then add the typename to _IGNORED_TYPENAMES.
          raise AssertionError("Unknown precondition typename: %s" % allowed)

    predecessors = cfg_utils.compute_predecessors(node_classes.values())
    # Convert predecessors keys and values to use names instead of info objects.
    get_names = lambda v: {n.name for n in v}
    _ancestor_map = {k.name: get_names(v) for k, v in predecessors.items()}
  return _ancestor_map


class Visitor(object):
  """Base class for visitors.

  Each class inheriting from visitor SHOULD have a fixed set of methods,
  otherwise it might break the caching in this class.

  Attributes:
    visits_all_node_types: Whether the visitor can visit every node type.
    unchecked_node_names: Contains the names of node classes that are unchecked
      when constructing a new node from visited children.  This is useful
      if a visitor returns data in part or all of its walk that would violate
      node preconditions.
    enter_functions: A dictionary mapping node class names to the
      corresponding Enter functions.
    visit_functions: A dictionary mapping node class names to the
      corresponding Visit functions.
    leave_functions: A dictionary mapping node class names to the
      corresponding Leave functions.
    visit_class_names: A set of node class names that must be visited.  This is
      constructed based on the enter/visit/leave functions and precondition
      data about legal ASTs.  As an optimization, the visitor will only visit
      nodes under which some actionable node can appear.
  """
  visits_all_node_types = False
  unchecked_node_names = set()

  _visitor_functions_cache = {}

  def __init__(self):
    cls = self.__class__

    # The set of method names for each visitor implementation is assumed to
    # be fixed. Therefore this introspection can be cached.
    if cls in Visitor._visitor_functions_cache:
      enter_fns, visit_fns, leave_fns, visit_class_names = (
          Visitor._visitor_functions_cache[cls])
    else:
      enter_fns = {}
      enter_prefix = "Enter"
      enter_len = len(enter_prefix)

      visit_fns = {}
      visit_prefix = "Visit"
      visit_len = len(visit_prefix)

      leave_fns = {}
      leave_prefix = "Leave"
      leave_len = len(leave_prefix)

      for attr in dir(cls):
        if attr.startswith(enter_prefix):
          enter_fns[attr[enter_len:]] = getattr(cls, attr)
        elif attr.startswith(visit_prefix):
          visit_fns[attr[visit_len:]] = getattr(cls, attr)
        elif attr.startswith(leave_prefix):
          leave_fns[attr[leave_len:]] = getattr(cls, attr)

      ancestors = _GetAncestorMap()
      visit_class_names = set()
      # A custom Enter/Visit/Leave requires visiting all types of nodes.
      visit_all = (cls.Enter != Visitor.Enter or
                   cls.Visit != Visitor.Visit or
                   cls.Leave != Visitor.Leave)
      for node in set(enter_fns) | set(visit_fns) | set(leave_fns):
        if node in ancestors:
          visit_class_names.update(ancestors[node])
        elif node:
          # Visiting an unknown non-empty node means the visitor has defined
          # behavior on nodes that are unknown to the ancestors list.  To be
          # safe, visit everything.
          #
          # TODO(dbaum): Consider making this an error.  The only wrinkle is
          # that StrictType is unknown to _FindNodeClasses(), does not appear
          # in any preconditions, but has defined behavior in PrintVisitor.
          visit_all = True
      if visit_all:
        visit_class_names = ALL_NODE_NAMES
      Visitor._visitor_functions_cache[cls] = (
          enter_fns, visit_fns, leave_fns, visit_class_names)

    self.enter_functions = enter_fns
    self.visit_functions = visit_fns
    self.leave_functions = leave_fns
    self.visit_class_names = visit_class_names

  def Enter(self, node, *args, **kwargs):
    return self.enter_functions[node.__class__.__name__](
        self, node, *args, **kwargs)

  def Visit(self, node, *args, **kwargs):
    return self.visit_functions[node.__class__.__name__](
        self, node, *args, **kwargs)

  def Leave(self, node, *args, **kwargs):
    self.leave_functions[node.__class__.__name__](self, node, *args, **kwargs)


class CanonicalOrderingVisitor(Visitor):
  """Visitor for converting ASTs back to canonical (sorted) ordering."""

  def __init__(self, sort_signatures=False):
    super(CanonicalOrderingVisitor, self).__init__()
    self.sort_signatures = sort_signatures

  def VisitTypeDeclUnit(self, node):
    return pytd.TypeDeclUnit(name=node.name,
                             constants=tuple(sorted(node.constants)),
                             type_params=tuple(sorted(node.type_params)),
                             functions=tuple(sorted(node.functions)),
                             classes=tuple(sorted(node.classes)),
                             aliases=tuple(sorted(node.aliases)))

  def VisitClass(self, node):
    return pytd.Class(
        name=node.name,
        metaclass=node.metaclass,
        parents=node.parents,
        methods=tuple(sorted(node.methods)),
        constants=tuple(sorted(node.constants)),
        classes=tuple(sorted(node.classes)),
        slots=tuple(sorted(node.slots)) if node.slots is not None else None,
        template=node.template)

  def VisitFunction(self, node):
    # Typically, signatures should *not* be sorted because their order
    # determines lookup order. But some pytd (e.g., inference output) doesn't
    # have that property, in which case self.sort_signatures will be True.
    if self.sort_signatures:
      return node.Replace(signatures=tuple(sorted(node.signatures)))
    else:
      return node

  def VisitSignature(self, node):
    return node.Replace(
        template=tuple(sorted(node.template)),
        exceptions=tuple(sorted(node.exceptions)))

  def VisitUnionType(self, node):
    return pytd.UnionType(tuple(sorted(node.type_list)))


class ClassTypeToNamedType(Visitor):
  """Change all ClassType objects to NameType objects."""

  def VisitClassType(self, node):
    return pytd.NamedType(node.name)


class CollectTypeParameters(Visitor):
  """Visitor that accumulates type parameters in its "params" attribute."""

  def __init__(self):
    super(CollectTypeParameters, self).__init__()
    self.params = set()

  def EnterTypeParameter(self, p):
    self.params.add(p)


class ExtractSuperClasses(Visitor):
  """Visitor for extracting all superclasses (i.e., the class hierarchy).

  When called on a TypeDeclUnit, this yields a dictionary mapping pytd.Class
  to lists of pytd.Type.
  """

  def __init__(self):
    super(ExtractSuperClasses, self).__init__()
    self._superclasses = {}

  def _Key(self, node):
    return node

  def VisitTypeDeclUnit(self, module):
    del module
    return self._superclasses

  def EnterClass(self, cls):
    parents = []
    for p in cls.parents:
      parent = self._Key(p)
      if parent is not None:
        parents.append(parent)
    # TODO(kramm): This uses the entire class node as a key, instead of just
    # its id.
    self._superclasses[self._Key(cls)] = parents


class PrintVisitor(Visitor):
  """Visitor for converting ASTs back to pytd source code."""
  visits_all_node_types = True
  unchecked_node_names = ALL_NODE_NAMES

  INDENT = " " * 4
  _RESERVED = frozenset(parser_constants.RESERVED +
                        parser_constants.RESERVED_PYTHON)

  def __init__(self, multiline_args=False):
    super(PrintVisitor, self).__init__()
    self.class_names = []  # allow nested classes
    self.imports = collections.defaultdict(set)
    self.in_alias = False
    self.in_parameter = False
    self._unit_name = None
    self._local_names = set()
    self._class_members = set()
    self._typing_import_counts = collections.defaultdict(int)
    self.multiline_args = multiline_args

  def _EscapedName(self, name):
    """Name, possibly escaped with backticks.

    If a name is a reserved PyTD token or contains special characters, it is
    enclosed in backticks.  See parser.Pylexer.t_NAME for legal names that
    require backticks.

    Args:
      name: A name, typically an identifier in the PyTD.

    Returns:
      The escaped name, or the original name if it doesn't need escaping.
    """
    if parser_constants.BACKTICK_NAME.search(name) or name in self._RESERVED:
      # We can do this because name will never contain backticks. Everything
      # we process here came in through the pytd parser, and the pytd syntax
      # doesn't allow escaping backticks themselves.
      return r"`" + name + "`"
    else:
      return name

  def _SafeName(self, name):
    split_name = name.split(".")
    split_result = (self._EscapedName(piece) for piece in split_name)
    return ".".join(split_result)

  def _IsEmptyTuple(self, t):
    """Check if it is an empty tuple."""
    assert isinstance(t, pytd.GenericType)
    return t.base_type == "tuple" and t.parameters == ("nothing",)

  def _NeedsTupleEllipsis(self, t):
    """Do we need to use Tuple[x, ...] instead of Tuple[x]?"""
    assert isinstance(t, pytd.GenericType)
    if isinstance(t, pytd.TupleType):
      return False  # TupleType is always heterogeneous.
    return t.base_type == "tuple"

  def _NeedsCallableEllipsis(self, t):
    """Check if it is typing.Callable type."""
    assert isinstance(t, pytd.GenericType)
    base = t.base_type
    return isinstance(base, pytd.ClassType) and base.name == "typing.Callable"

  def _RequireImport(self, module, name=None):
    """Register that we're using name from module.

    Args:
      module: string identifier.
      name: if None, means we want 'import module'. Otherwise string identifier
       that we want to import.
    """
    self.imports[module].add(name)

  def _RequireTypingImport(self, name=None):
    """Convenience function, wrapper for _RequireImport("typing", name)."""
    self._RequireImport("typing", name)

  def _GenerateImportStrings(self):
    """Generate import statements needed by the nodes we've visited so far.

    Returns:
      List of strings.
    """
    ret = []
    for module in sorted(self.imports):
      names = set(self.imports[module])
      if module == "typing":
        for (name, count) in self._typing_import_counts.items():
          if not count:
            names.discard(name)
      if None in names:
        ret.append("import %s" % module)
        names.remove(None)

      if names:
        name_str = ", ".join(sorted(names))
        ret.append("from %s import %s" % (module, name_str))

    return ret

  def _IsBuiltin(self, module):
    return module == "__builtin__"

  def _FormatTypeParams(self, type_params):
    formatted_type_params = []
    for t in type_params:
      args = ["'%s'" % t.name]
      args += [c.Visit(PrintVisitor()) for c in t.constraints]
      if t.bound:
        args.append("bound=" + t.bound.Visit(PrintVisitor()))
      formatted_type_params.append(
          "%s = TypeVar(%s)" % (t.name, ", ".join(args)))
    return sorted(formatted_type_params)

  def _NameCollision(self, name):
    return name in self._class_members or name in self._local_names

  def _FromTyping(self, name):
    self._typing_import_counts[name] += 1
    if self._NameCollision(name):
      self._RequireTypingImport(None)
      return "typing." + name
    else:
      self._RequireTypingImport(name)
      return name

  def EnterTypeDeclUnit(self, unit):
    self._unit_name = unit.name
    definitions = (unit.classes + unit.functions + unit.constants +
                   unit.type_params + unit.aliases)
    self._local_names = {c.name for c in definitions}

  def LeaveTypeDeclUnit(self, _):
    self._unit_name = None
    self._local_names = set()

  def VisitTypeDeclUnit(self, node):
    """Convert the AST for an entire module back to a string."""
    if node.type_params:
      self._FromTyping("TypeVar")
    sections = [self._GenerateImportStrings(), node.aliases, node.constants,
                self._FormatTypeParams(self.old_node.type_params), node.classes,
                node.functions]

    # We put one blank line after every class,so we need to strip the blank line
    # after the last class.
    sections_as_string = ("\n".join(section_suite).rstrip()
                          for section_suite in sections
                          if section_suite)
    return "\n\n".join(sections_as_string)

  def VisitConstant(self, node):
    """Convert a class-level or module-level constant to a string."""
    return self._SafeName(node.name) + ": " + node.type

  def EnterAlias(self, _):
    self.old_imports = self.imports.copy()

  def VisitAlias(self, node):
    """Convert an import or alias to a string."""
    if isinstance(self.old_node.type, pytd.NamedType):
      full_name = self.old_node.type.name
      suffix = ""
      module, _, name = full_name.rpartition(".")
      if module:
        if name not in ("*", self.old_node.name):
          suffix += " as " + self.old_node.name
        self.imports = self.old_imports  # undo unnecessary imports change
        return "from " + module + " import " + name + suffix
    elif isinstance(self.old_node.type, pytd.Module):
      return node.type
    return self._SafeName(node.name) + " = " + node.type

  def EnterClass(self, node):
    """Entering a class - record class name for children's use."""
    n = self._SafeName(node.name)
    if node.template:
      n += "[{}]".format(
          ", ".join(t.Visit(PrintVisitor()) for t in node.template))
    for member in node.methods + node.constants:
      self._class_members.add(member.name)
    self.class_names.append(n)

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
    parents_str = "(" + ", ".join(parents) + ")" if parents else ""
    header = ["class " + self._SafeName(node.name) + parents_str + ":"]
    if node.slots is not None:
      slots_str = ", ".join("\"%s\"" % s for s in node.slots)
      slots = [self.INDENT + "__slots__ = [" + slots_str + "]"]
    else:
      slots = []
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
    return "\n".join(header + slots + classes + constants + methods) + "\n"

  def VisitFunction(self, node):
    """Visit function, producing multi-line string (one for each signature)."""
    function_name = self._EscapedName(node.name)
    decorators = ""
    if node.kind == pytd.STATICMETHOD and function_name != "__new__":
      decorators += "@staticmethod\n"
    elif node.kind == pytd.CLASSMETHOD:
      decorators += "@classmethod\n"
    elif node.kind == pytd.PROPERTY:
      decorators += "@property\n"
    if node.is_abstract:
      decorators += "@abstractmethod\n"
    if node.is_coroutine:
      decorators += "@coroutine\n"
    if len(node.signatures) > 1:
      decorators += "@overload\n"
    signatures = "\n".join(decorators + "def " + function_name + sig
                           for sig in node.signatures)
    return signatures

  def _FormatContainerContents(self, node):
    """Print out the last type parameter of a container. Used for *args/**kw."""
    assert isinstance(node, pytd.Parameter)
    if isinstance(node.type, pytd.GenericType):
      container_name = node.type.base_type.name.rpartition(".")[2]
      assert container_name in ("tuple", "dict")
      self._typing_import_counts[container_name.capitalize()] -= 1
      # If the type is "Any", e.g. `**kwargs: Any`, decrement Any to avoid an
      # extraneous import of typing.Any. Any was visited before this function
      # transformed **kwargs, so it was incremented at least once already.
      if isinstance(node.type.parameters[-1], pytd.AnythingType):
        self._typing_import_counts["Any"] -= 1
      return node.Replace(type=node.type.parameters[-1], optional=False).Visit(
          PrintVisitor())
    else:
      return node.Replace(type=pytd.AnythingType(), optional=False).Visit(
          PrintVisitor())

  def VisitSignature(self, node):
    """Visit a signature, producing a string."""
    if node.return_type == "nothing":
      return_type = "NoReturn"  # a prettier alias for nothing
      self._FromTyping(return_type)
    else:
      return_type = node.return_type
    ret = " -> " + return_type

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
        params += ("*" + starargs,)
    if self.old_node.starstarargs is not None:
      starstarargs = self._FormatContainerContents(self.old_node.starstarargs)
      params += ("**" + starstarargs,)

    body = []
    # Handle Mutable parameters
    # pylint: disable=no-member
    # (old_node is set in parse/node.py)
    mutable_params = [(p.name, p.mutated_type) for p in self.old_node.params
                      if p.mutated_type is not None]
    # pylint: enable=no-member
    for name, new_type in mutable_params:
      body.append("\n{indent}{name} = {new_type}".format(
          indent=self.INDENT, name=name,
          new_type=new_type.Visit(PrintVisitor())))
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
        self.class_names[-1].split("[")[0] == node.type):
      return self._SafeName(node.name) + suffix
    elif node.name == "cls" and self.class_names and (
        node.type == "Type[%s]" % self.class_names[-1]):
      self._typing_import_counts["Type"] -= 1
      return self._SafeName(node.name) + suffix
    elif node.type is None:
      logging.warning("node.type is None")
      return self._SafeName(node.name)
    else:
      return self._SafeName(node.name) + ": " + node.type + suffix

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
      if prefix != class_prefix:
        # If the prefix doesn't match the class scope, then it's an import.
        self._RequireImport(prefix)
      node_name = node.name
    else:
      node_name = node.name
    if node_name == "NoneType":
      # PEP 484 allows this special abbreviation.
      return "None"
    else:
      return self._SafeName(node_name)

  def VisitLateType(self, node):
    return self.VisitNamedType(node)

  def VisitClassType(self, node):
    return self.VisitNamedType(node)

  def VisitStrictType(self, node):
    # 'StrictType' is defined, and internally used, by booleq.py. We allow it
    # here so that booleq.py can use pytd_utils.Print().
    return self.VisitNamedType(node)

  def VisitFunctionType(self, unused_node):
    """Convert a function type to a string."""
    return self._FromTyping("Callable")

  def VisitAnythingType(self, unused_node):
    """Convert an anything type to a string."""
    return self._FromTyping("Any")

  def VisitNothingType(self, unused_node):
    """Convert the nothing type to a string."""
    return "nothing"

  def VisitTypeParameter(self, node):
    return self._SafeName(node.name)

  def VisitModule(self, node):
    if node.is_aliased:
      return "import %s as %s" % (node.module_name, node.name)
    else:
      return "import %s" % node.module_name

  def MaybeCapitalize(self, name):
    """Capitalize a generic type, if necessary."""
    # Import here due to circular import.
    from pytype.pytd import pep484  # pylint: disable=g-import-not-at-top
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
      parameters = ("...",) + parameters[1:]
    return (self.MaybeCapitalize(node.base_type) +
            "[" + ", ".join(parameters) + "]")

  def VisitCallableType(self, node):
    return "%s[[%s], %s]" % (self.MaybeCapitalize(node.base_type),
                             ", ".join(node.args), node.ret)

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
      # Import here due to circular import.
      from pytype.pytd import pep484  # pylint: disable=g-import-not-at-top
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
    type_list = tuple(type_list)
    if len(type_list) == 1:
      return type_list[0]
    elif "None" in type_list:
      return (self._FromTyping("Optional") + "[" +
              self._BuildUnion(t for t in type_list if t != "None") + "]")
    else:
      return self._FromTyping("Union") + "[" + ", ".join(type_list) + "]"

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

  def VisitLiteral(self, node):
    base = "Literal"
    # Check whether Literal is already imported from typing_extensions.
    if base not in self._local_names:
      base = self._FromTyping(base)
    return "%s[%s]" % (base, node.value)


class RenameModuleVisitor(Visitor):
  """Renames a TypeDeclUnit."""

  def __init__(self, old_module_name, new_module_name):
    """Constructor.

    Args:
      old_module_name: The old name of the module as a string,
        e.g. "foo.bar.module1"
      new_module_name: The new name of the module as a string,
        e.g. "barfoo.module2"

    Raises:
      ValueError: If the old_module name is an empty string.
    """
    super(RenameModuleVisitor, self).__init__()
    if not old_module_name:
      raise ValueError("old_module_name must be a non empty string.")
    assert not old_module_name.endswith(".")
    assert not new_module_name.endswith(".")
    self._module_name = new_module_name
    self._old = old_module_name + "." if old_module_name else ""
    self._new = new_module_name + "." if new_module_name else ""

  def _MaybeNewName(self, name):
    """Decides if a name should be replaced.

    Args:
      name: A name for which a prefix should be changed.

    Returns:
      If name is local to the module described by old_module_name the
      old_module_part will be replaced by new_module_name and returned,
      otherwise node.name will be returned.
    """
    if not name:
      return name
    before, match, after = name.partition(self._old)
    if match and not before and "." not in after:
      return self._new + after
    else:
      return name

  def _ReplaceModuleName(self, node):
    new_name = self._MaybeNewName(node.name)
    if new_name != node.name:
      return node.Replace(name=new_name)
    else:
      return node

  def VisitClassType(self, node):
    new_name = self._MaybeNewName(node.name)
    if new_name != node.name:
      return pytd.ClassType(new_name, node.cls)
    else:
      return node

  def VisitTypeDeclUnit(self, node):
    return node.Replace(name=self._module_name)

  def VisitTypeParameter(self, node):
    new_scope = self._MaybeNewName(node.scope)
    if new_scope != node.scope:
      return node.Replace(scope=new_scope)
    return node

  VisitConstant = _ReplaceModuleName  # pylint: disable=invalid-name
  VisitAlias = _ReplaceModuleName  # pylint: disable=invalid-name
  VisitClass = _ReplaceModuleName  # pylint: disable=invalid-name
  VisitFunction = _ReplaceModuleName  # pylint: disable=invalid-name
  VisitStrictType = _ReplaceModuleName  # pylint: disable=invalid-name
  VisitNamedType = _ReplaceModuleName  # pylint: disable=invalid-name
