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

"""Visitor(s) for walking ASTs."""

# Because pytype takes too long:
# pytype: skip-file

import collections
import itertools
import logging
import re

from pytype import datatypes
from pytype import module_utils
from pytype import utils
from pytype.pytd import mro
from pytype.pytd import pytd
from pytype.pytd.parse import parser_constants  # pylint: disable=g-importing-member
from pytype.typegraph import cfg_utils

import six


class ContainerError(Exception):
  pass


class SymbolLookupError(Exception):
  pass


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
    _ancestor_map = {
        k.name: {n.name for n in v} for k, v in predecessors.items()}
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


def InventStarArgParams(existing_names):
  """Try to find names for *args, **kwargs that aren't taken already."""
  names = {x if isinstance(x, str) else x.name
           for x in existing_names}
  args, kwargs = "args", "kwargs"
  while args in names:
    args = "_" + args
  while kwargs in names:
    kwargs = "_" + kwargs
  return (pytd.Parameter(args, pytd.NamedType("tuple"), False, True, None),
          pytd.Parameter(kwargs, pytd.NamedType("dict"), False, True, None))


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
    definitions = (unit.classes + unit.functions + unit.constants +
                   unit.type_params + unit.aliases)
    self._local_names = {c.name for c in definitions}

  def LeaveTypeDeclUnit(self, _):
    self._local_names = set()

  def VisitTypeDeclUnit(self, node):
    """Convert the AST for an entire module back to a string."""
    if node.type_params:
      self._FromTyping("TypeVar")
    sections = [self._GenerateImportStrings(), node.aliases, node.constants,
                self._FormatTypeParams(self.old_node.type_params), node.classes,
                node.functions]

    sections_as_string = ("\n".join(section_suite)
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
    # If classobj is the only parent, then this is an old-style class, don't
    # list any parents.
    if parents == ("classobj",):
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
      constants = []
      classes = []
      methods = [self.INDENT + "pass"]
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
    module, _, suffix = node.name.rpartition(".")
    if self._IsBuiltin(module) and not self._NameCollision(suffix):
      node_name = suffix
    elif module == "typing":
      node_name = self._FromTyping(suffix)
    elif module:
      self._RequireImport(module)
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
    # here so that booleq.py can use pytd.Print().
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
    if self._NeedsTupleEllipsis(node):
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


class StripSelf(Visitor):
  """Transforms the tree into one where methods don't have the "self" parameter.

  This is useful for certain kinds of postprocessing and testing.
  """

  def VisitClass(self, node):
    """Visits a Class, and removes "self" from all its methods."""
    return node.Replace(methods=tuple(self._StripFunction(m)
                                      for m in node.methods))

  def _StripFunction(self, node):
    """Remove "self" from all signatures of a method."""
    return node.Replace(signatures=tuple(self.StripSignature(s)
                                         for s in node.signatures))

  def StripSignature(self, node):
    """Remove "self" from a Signature. Assumes "self" is the first argument."""
    return node.Replace(params=node.params[1:])


class FillInLocalPointers(Visitor):
  """Fill in ClassType and FunctionType pointers using symbol tables.

  This is an in-place visitor! It modifies the original tree. This is
  necessary because we introduce loops.
  """

  def __init__(self, lookup_map, fallback=None):
    """Create this visitor.

    You're expected to then pass this instance to node.Visit().

    Args:
      lookup_map: A map from names to symbol tables (i.e., objects that have a
        "Lookup" function).
      fallback: A symbol table to be tried if lookup otherwise fails.
    """
    super(FillInLocalPointers, self).__init__()
    if fallback is not None:
      lookup_map["*"] = fallback
    self._lookup_map = lookup_map

  def _Lookup(self, node):
    """Look up a node by name."""
    module, _, _ = node.name.rpartition(".")
    if module:
      modules_to_try = [("", module)]
    else:
      modules_to_try = [("", ""),
                        ("", "__builtin__"),
                        ("__builtin__.", "__builtin__")]
    modules_to_try += [("", "*"), ("__builtin__.", "*")]
    for prefix, module in modules_to_try:
      mod_ast = self._lookup_map.get(module)
      if mod_ast:
        try:
          item = mod_ast.Lookup(prefix + node.name)
        except KeyError:
          pass
        else:
          yield prefix, item

  def EnterClassType(self, node):
    """Fills in a class type.

    Args:
      node: A ClassType. This node will have a name, which we use for lookup.

    Returns:
      The same ClassType. We will have done our best to fill in its "cls"
      attribute. Call VerifyLookup() on your tree if you want to be sure that
      all of the cls pointers have been filled in.
    """
    for prefix, cls in self._Lookup(node):
      if isinstance(cls, pytd.Class):
        node.cls = cls
        return
      else:
        logging.warning("Couldn't resolve %s: Not a class: %s",
                        prefix + node.name, type(cls))

  def EnterFunctionType(self, node):
    for prefix, func in self._Lookup(node):
      if isinstance(func, pytd.Function):
        node.function = func
        return
      else:
        logging.warning("Couldn't resolve %s: Not a function: %s",
                        prefix + node.name, type(func))


def ToType(item, allow_constants=True):
  """Convert a pytd AST item into a type."""
  if isinstance(item, pytd.TYPE):
    return item
  elif isinstance(item, pytd.Module):
    return item
  elif isinstance(item, pytd.Class):
    return pytd.ClassType(item.name, item)
  elif isinstance(item, pytd.Function):
    return pytd.FunctionType(item.name, item)
  elif isinstance(item, pytd.Constant):
    if allow_constants:
      # TODO(kramm): This is wrong. It would be better if we resolve pytd.Alias
      # in the same way we resolve pytd.NamedType.
      return item
    else:
      # TODO(kramm): We should be more picky here. In particular, we shouldn't
      # allow pyi like this:
      #  object = ...  # type: int
      #  def f(x: object) -> Any
      return pytd.AnythingType()
  elif isinstance(item, pytd.Alias):
    return item.type
  else:
    raise NotImplementedError("Can't convert %s: %s" % (type(item), item))


class RemoveTypeParametersFromGenericAny(Visitor):
  """Adjusts GenericType nodes to handle base type changes."""

  unchecked_node_names = ("GenericType",)

  def VisitGenericType(self, node):
    if isinstance(node.base_type, (pytd.AnythingType, pytd.Constant)):
      # TODO(rechen): Raise an exception if the base type is a constant whose
      # type isn't Any.
      return node.base_type
    else:
      return node


class DefaceUnresolved(RemoveTypeParametersFromGenericAny):
  """Replace all types not in a symbol table with AnythingType."""

  def __init__(self, lookup_list, do_not_log_prefix=None):
    """Create this visitor.

    Args:
      lookup_list: An iterable of symbol tables (i.e., objects that have a
        "lookup" function)
      do_not_log_prefix: If given, don't log error messages for classes with
        this prefix.
    """
    super(DefaceUnresolved, self).__init__()
    self._lookup_list = lookup_list
    self._do_not_log_prefix = do_not_log_prefix

  def VisitNamedType(self, node):
    """Do replacement on a pytd.NamedType."""
    name = node.name
    for lookup in self._lookup_list:
      try:
        cls = lookup.Lookup(name)
        if isinstance(cls, pytd.Class):
          return node
      except KeyError:
        pass
    if "." in node.name:
      return node
    else:
      if (self._do_not_log_prefix is None or
          not name.startswith(self._do_not_log_prefix)):
        logging.warning("Setting %s to ?", name)
      return pytd.AnythingType()

  def VisitCallableType(self, node):
    return self.VisitGenericType(node)

  def VisitTupleType(self, node):
    return self.VisitGenericType(node)

  def VisitClassType(self, node):
    return self.VisitNamedType(node)


class NamedTypeToClassType(Visitor):
  """Change all NamedType objects to ClassType objects.
  """

  def VisitNamedType(self, node):
    """Converts a named type to a class type, to be filled in later.

    Args:
      node: The NamedType. This type only has a name.

    Returns:
      A ClassType. This ClassType will (temporarily) only have a name.
    """
    return pytd.ClassType(node.name)


class ClassTypeToNamedType(Visitor):
  """Change all ClassType objects to NameType objects.
  """

  def VisitClassType(self, node):
    return pytd.NamedType(node.name)


class DropBuiltinPrefix(Visitor):
  """Drop '__builtin__.' prefix."""

  def VisitClassType(self, node):
    _, _, name = node.name.rpartition("__builtin__.")
    return pytd.NamedType(name)

  def VisitNamedType(self, node):
    return self.VisitClassType(node)


# TODO(b/110164593): Get rid of this hack.
def RenameBuiltinsPrefixInName(name):
  if name.startswith("builtins."):
    name = "__builtin__." + name[len("builtins."):]
  return name


class RenameBuiltinsPrefix(Visitor):
  """Rename 'builtins' to '__builtin__' at import time."""

  def VisitClassType(self, node):
    return pytd.NamedType(RenameBuiltinsPrefixInName(node.name))

  def VisitNamedType(self, node):
    return self.VisitClassType(node)


def LookupClasses(target, global_module=None, ignore_late_types=False):
  """Converts a PyTD object from one using NamedType to ClassType.

  Args:
    target: The PyTD object to process. If this is a TypeDeclUnit it will also
      be used for lookups.
    global_module: Global symbols. Required if target is not a TypeDeclUnit.
    ignore_late_types: If True, raise an error if we encounter a LateType.

  Returns:
    A new PyTD object that only uses ClassType. All ClassType instances will
    point to concrete classes.

  Raises:
    ValueError: If we can't find a class.
  """
  target = target.Visit(NamedTypeToClassType())
  module_map = {}
  if global_module is None:
    assert isinstance(target, pytd.TypeDeclUnit)
    global_module = target
  elif isinstance(target, pytd.TypeDeclUnit):
    module_map[""] = target
  target.Visit(FillInLocalPointers(module_map, fallback=global_module))
  target.Visit(VerifyLookup(ignore_late_types))
  return target


class VerifyLookup(Visitor):
  """Utility class for testing visitors.LookupClasses."""

  def __init__(self, ignore_late_types=False):
    super(VerifyLookup, self).__init__()
    self.ignore_late_types = ignore_late_types

  def EnterLateType(self, node):
    if not self.ignore_late_types:
      raise ValueError("Unresolved LateType: %r" % node.name)

  def EnterNamedType(self, node):
    raise ValueError("Unreplaced NamedType: %r" % node.name)

  def EnterClassType(self, node):
    if node.cls is None:
      raise ValueError("Unresolved class: %r" % node.name)


class LookupBuiltins(Visitor):
  """Look up built-in NamedTypes and give them fully-qualified names."""

  def __init__(self, builtins, full_names=True):
    """Create this visitor.

    Args:
      builtins: The builtins module.
      full_names: Whether to use fully qualified names for lookup.
    """
    super(LookupBuiltins, self).__init__()
    self._builtins = builtins
    self._full_names = full_names

  def EnterTypeDeclUnit(self, unit):
    self._current_unit = unit
    self._prefix = unit.name + "." if self._full_names else ""

  def LeaveTypeDeclUnit(self, _):
    del self._current_unit
    del self._prefix

  def VisitNamedType(self, t):
    """Do lookup on a pytd.NamedType."""
    if "." in t.name:
      return t
    try:
      self._current_unit.Lookup(self._prefix + t.name)
    except KeyError:
      # We can't find this identifier in our current module, and it isn't fully
      # qualified (doesn't contain a dot). Now check whether it's a builtin.
      try:
        item = self._builtins.Lookup(self._builtins.name + "." + t.name)
      except KeyError:
        return t
      else:
        return ToType(item)
    else:
      return t


class LookupExternalTypes(RemoveTypeParametersFromGenericAny):
  """Look up NamedType pointers using a symbol table."""

  def __init__(self, module_map, self_name=None, module_alias_map=None):
    """Create this visitor.

    Args:
      module_map: A dictionary mapping module names to symbol tables.
      self_name: The name of the current module. If provided, then the visitor
        will ignore nodes with this module name.
      module_alias_map: A dictionary mapping module aliases to real module
        names. If the source contains "import X as Y", module_alias_map should
        contain an entry mapping "Y": "X".
    """
    super(LookupExternalTypes, self).__init__()
    self._module_map = module_map
    self._module_alias_map = module_alias_map or {}
    self.name = self_name
    self._in_constant = False
    self._alias_name = None
    self._star_imports = set()

  def _ResolveUsingGetattr(self, module_name, module):
    """Try to resolve an identifier using the top level __getattr__ function."""
    try:
      g = module.Lookup(module_name + ".__getattr__")
    except KeyError:
      return None
    # TODO(kramm): Make parser.py actually enforce this:
    assert len(g.signatures) == 1
    return g.signatures[0].return_type

  def EnterConstant(self, _):
    assert not self._in_constant
    self._in_constant = True

  def LeaveConstant(self, _):
    assert self._in_constant
    self._in_constant = False

  def EnterAlias(self, t):
    assert not self._alias_name
    self._alias_name = t.name

  def LeaveAlias(self, _):
    assert self._alias_name
    self._alias_name = None

  def _LookupModuleName(self, name):
    if name in self._module_map:
      # If we have loaded this, return the ast
      return self._module_map[name]
    else:
      raise KeyError("Unknown module %s" % name)

  def VisitNamedType(self, t):
    """Try to look up a NamedType.

    Args:
      t: An instance of pytd.NamedType
    Returns:
      The same node t.
    Raises:
      KeyError: If we can't find a module, or an identifier in a module, or
        if an identifier in a module isn't a class.
    """
    if t.name in self._module_map:
      if self._alias_name and "." in self._alias_name:
        # Module aliases appear only in asts that use fully-qualified names.
        return ToType(pytd.Module(name=t.name, module_name=t.name))
      else:
        # We have a class with the same name as a module.
        return t
    module_name, dot, name = t.name.rpartition(".")
    if not dot or module_name == self.name:
      # Nothing to do here. This visitor will only look up nodes in other
      # modules.
      return t
    if module_name in self._module_alias_map:
      module_name = self._module_alias_map[module_name]
    module = self._LookupModuleName(module_name)
    try:
      if name == "*":
        self._star_imports.add(module_name)
        item = t  # VisitTypeDeclUnit will remove this unneeded item.
      else:
        item = module.Lookup(module_name + "." + name)
    except KeyError:
      item = self._ResolveUsingGetattr(module_name, module)
      if item is None:
        raise KeyError("No %s in module %s" % (name, module_name))
    return ToType(item, allow_constants=not self._in_constant)

  def VisitClassType(self, t):
    new_type = self.VisitNamedType(t)
    if isinstance(new_type, pytd.ClassType):
      t.cls = new_type.cls
      return t
    else:
      return new_type

  def _ModulePrefix(self):
    return self.name + "." if self.name else ""

  def _ImportAll(self, module):
    """Get the new members that would result from a star import of the module.

    Args:
      module: The module name.

    Returns:
      A tuple of:
      - a list of new aliases,
      - a set of new __getattr__ functions.
    """
    aliases = []
    getattrs = set()
    ast = self._module_map[module]
    for member in sum((ast.constants, ast.type_params, ast.classes,
                       ast.functions, ast.aliases), ()):
      _, _, member_name = member.name.rpartition(".")
      new_name = self._ModulePrefix() + member_name
      if isinstance(member, pytd.Function) and member_name == "__getattr__":
        # def __getattr__(name) -> Any needs to be imported directly rather
        # than aliased.
        getattrs.add(member.Replace(name=new_name))
      else:
        aliases.append(pytd.Alias(new_name, ToType(member)))
    return aliases, getattrs

  def _DiscardExistingNames(self, node, potential_members):
    new_members = []
    for m in potential_members:
      try:
        node.Lookup(m.name)
      except KeyError:
        new_members.append(m)
    return new_members

  def _HandleDuplicates(self, new_aliases):
    """Handle duplicate module-level aliases.

    Aliases pointing to qualified names could be the result of importing the
    same entity through multiple import paths, which should not count as an
    error; instead we just deduplicate them.

    Args:
      new_aliases: The list of new aliases to deduplicate

    Returns:
      A deduplicated list of aliases.

    Raises:
      KeyError: If there is a name clash.
    """
    name_to_alias = {}
    out = []
    for a in new_aliases:
      if a.name in name_to_alias:
        existing = name_to_alias[a.name]
        if existing != a:
          raise KeyError("Duplicate top level items: %r, %r" % (
              existing.type.name, a.type.name))
      else:
        name_to_alias[a.name] = a
        out.append(a)
    return out

  def VisitTypeDeclUnit(self, node):
    """Add star imports to the ast.

    Args:
      node: A pytd.TypeDeclUnit instance.

    Returns:
      The pytd.TypeDeclUnit instance, with star imports added.

    Raises:
      KeyError: If a duplicate member is found during import.
    """
    if not self._star_imports:
      return node
    # Discard the 'importing_mod.imported_mod.* = imported_mod.*' aliases.
    star_import_names = set()
    p = self._ModulePrefix()
    for x in self._star_imports:
      # Allow for the case of foo/__init__ importing foo.bar
      if x.startswith(p):
        star_import_names.add(x + ".*")
      star_import_names.add(p + x + ".*")
    new_aliases = []
    new_getattrs = set()
    for module in self._star_imports:
      aliases, getattrs = self._ImportAll(module)
      new_aliases.extend(aliases)
      new_getattrs.update(getattrs)
    # Allow local definitions to shadow imported definitions.
    new_aliases = self._DiscardExistingNames(node, new_aliases)
    new_getattrs = self._DiscardExistingNames(node, new_getattrs)
    # Don't allow imported definitions to conflict with one another.
    new_aliases = self._HandleDuplicates(new_aliases)
    if len(new_getattrs) > 1:
      raise KeyError("Multiple __getattr__ definitions")
    return node.Replace(
        functions=node.functions + tuple(new_getattrs),
        aliases=(
            tuple(a for a in node.aliases if a.name not in star_import_names) +
            tuple(new_aliases)))


class LookupLocalTypes(RemoveTypeParametersFromGenericAny):
  """Look up local identifiers. Must be called on a TypeDeclUnit."""

  def EnterTypeDeclUnit(self, unit):
    self.unit = unit

  def LeaveTypeDeclUnit(self, _):
    del self.unit

  def VisitNamedType(self, node):
    """Do lookup on a pytd.NamedType."""
    module_name, dot, _ = node.name.rpartition(".")
    if not dot:
      try:
        item = self.unit.Lookup(self.unit.name + "." + node.name)
      except KeyError:
        # Happens for infer calling load_pytd.resolve_ast() for the final pyi
        try:
          item = self.unit.Lookup(node.name)
        except KeyError:
          raise SymbolLookupError("Couldn't find %s in %s" % (
              node.name, self.unit.name))
      return ToType(item, allow_constants=False)
    elif module_name == self.unit.name:
      return ToType(self.unit.Lookup(node.name), allow_constants=False)
    else:
      return node


class ReplaceTypes(Visitor):
  """Visitor for replacing types in a tree.

  This replaces both NamedType and ClassType nodes that have a name in the
  mapping. The two cases are not distinguished.
  """

  def __init__(self, mapping, record=None):
    """Initialize this visitor.

    Args:
      mapping: A dictionary, mapping strings to node instances. Any NamedType
        or ClassType with a name in this dictionary will be replaced with
        the corresponding value.
      record: Optional. A set. If given, this records which entries in
        the map were used.
    """
    super(ReplaceTypes, self).__init__()
    self.mapping = mapping
    self.record = record

  def VisitNamedType(self, node):
    if node.name in self.mapping:
      if self.record is not None:
        self.record.add(node.name)
      return self.mapping[node.name]
    return node

  def VisitClassType(self, node):
    return self.VisitNamedType(node)

  # We do *not* want to have 'def VisitClass' because that will replace a class
  # definition with itself, which is almost certainly not what is wanted,
  # because runing pytd.Print on it will result in output that's just a list of
  # class names with no contents.


class ExtractSuperClasses(Visitor):
  """Visitor for extracting all superclasses (i.e., the class hierarchy).

  When called on a TypeDeclUnit, this yields a dictionary mapping pytd.Class
  to lists of pytd.TYPE.
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


class ExtractSuperClassesByName(ExtractSuperClasses):
  """Visitor for extracting all superclasses (i.e., the class hierarchy).

  This returns a mapping by name, e.g. {
    "bool": ["int"],
    "int": ["object"],
    ...
  }.
  """

  def _Key(self, node):
    if isinstance(node, pytd.GenericType):
      return node.base_type.name
    elif isinstance(node, (pytd.GENERIC_BASE_TYPE, pytd.Class)):
      return node.name


class ReplaceTypeParameters(Visitor):
  """Visitor for replacing type parameters with actual types."""

  def __init__(self, mapping):
    super(ReplaceTypeParameters, self).__init__()
    self.mapping = mapping

  def VisitTypeParameter(self, p):
    return self.mapping[p]


class CollectTypeParameters(Visitor):
  """Visitor that accumulates type parameters in its "params" attribute."""

  def __init__(self):
    super(CollectTypeParameters, self).__init__()
    self.params = set()

  def EnterTypeParameter(self, p):
    self.params.add(p)


def ClassAsType(cls):
  """Converts a pytd.Class to an instance of pytd.TYPE."""
  params = tuple(item.type_param for item in cls.template)
  if not params:
    return pytd.NamedType(cls.name)
  else:
    return pytd.GenericType(pytd.NamedType(cls.name), params)


class AdjustSelf(Visitor):
  """Visitor for setting the correct type on self.

  So
    class A:
      def f(self: object)
  becomes
    class A:
      def f(self: A)
  .
  (Notice the latter won't be printed like this, as printing simplifies the
   first argument to just "self")
  """

  def __init__(self, force=False):
    super(AdjustSelf, self).__init__()
    self.class_types = []  # allow nested classes
    self.force = force

  def EnterClass(self, cls):
    self.class_types.append(ClassAsType(cls))

  def LeaveClass(self, unused_node):
    self.class_types.pop()

  def VisitClass(self, node):
    return node

  def VisitParameter(self, p):
    """Adjust all parameters called "self" to have their parent class type.

    But do this only if their original type is unoccupied ("object" or,
    if configured, "?").

    Args:
      p: pytd.Parameter instance.

    Returns:
      Adjusted pytd.Parameter instance.
    """
    if not self.class_types:
      # We're not within a class, so this is not a parameter of a method.
      return p
    if p.name == "self" and (
        self.force or isinstance(p.type, pytd.AnythingType)):
      return p.Replace(type=self.class_types[-1])
    else:
      return p


class RemoveUnknownClasses(Visitor):
  """Visitor for converting ClassTypes called ~unknown* to just AnythingType.

  For example, this will change
    def f(x: ~unknown1) -> ~unknown2
    class ~unknown1:
      ...
    class ~unknown2:
      ...
  to
    def f(x) -> ?
  """

  def __init__(self):
    super(RemoveUnknownClasses, self).__init__()
    self.parameter = None

  def EnterParameter(self, p):
    self.parameter = p

  def LeaveParameter(self, p):
    assert self.parameter is p
    self.parameter = None

  def VisitClassType(self, t):
    if t.name.startswith("~unknown"):
      return pytd.AnythingType()
    else:
      return t

  def VisitNamedType(self, t):
    if t.name.startswith("~unknown"):
      return pytd.AnythingType()
    else:
      return t

  def VisitTypeDeclUnit(self, u):
    return u.Replace(classes=tuple(
        cls for cls in u.classes if not cls.name.startswith("~unknown")))


class _CountUnknowns(Visitor):
  """Visitor for counting how often given unknowns occur in a type."""

  def __init__(self):
    super(_CountUnknowns, self).__init__()
    self.counter = collections.Counter()
    self.position = {}

  def EnterNamedType(self, t):
    _, is_unknown, suffix = t.name.partition("~unknown")
    if is_unknown:
      if suffix not in self.counter:
        # Also record the order in which we see the ~unknowns
        self.position[suffix] = len(self.position)
      self.counter[suffix] += 1

  def EnterClassType(self, t):
    return self.EnterNamedType(t)


class CreateTypeParametersForSignatures(Visitor):
  """Visitor for inserting type parameters into signatures.

  This visitor replaces re-occurring ~unknowns and class types (when necessary)
  with type parameters.

  For example, this will change
  1.
    class ~unknown1:
      ...
    def f(x: ~unknown1) -> ~unknown1
  to
    _T1 = TypeVar("_T1")
    def f(x: _T1) -> _T1
  2.
    class Foo:
      def __new__(cls: Type[Foo]) -> Foo
  to
    _TFoo = TypeVar("_TFoo", bound=Foo)
    class Foo:
      def __new__(cls: Type[_TFoo]) -> _TFoo
  3.
    class Foo:
      def __enter__(self) -> Foo
  to
    _TFoo = TypeVar("_TFoo", bound=Foo)
    class Foo:
      def __enter__(self: _TFoo) -> _TFoo
  """

  PREFIX = "_T"  # Prefix for new type params

  def __init__(self):
    super(CreateTypeParametersForSignatures, self).__init__()
    self.parameter = None
    self.class_name = None
    self.function_name = None

  def _IsIncomplete(self, name):
    return name and name.startswith("~")

  def EnterClass(self, node):
    self.class_name = node.name

  def LeaveClass(self, _):
    self.class_name = None

  def EnterFunction(self, node):
    self.function_name = node.name

  def LeaveFunction(self, _):
    self.function_name = None

  def _NeedsClassParam(self, sig):
    """Whether the signature needs a bounded type param for the class.

    We detect the signatures
      (cls: Type[X][, ...]) -> X
    and
      (self: X[, ...]) -> X
    so that we can replace X with a bounded TypeVar. This heuristic
    isn't perfect; for example, in this naive copy method:
      class X(object):
        def copy(self):
          return X()
    we should have left X alone. But it prevents a number of false
    positives by enabling us to infer correct types for common
    implementations of __new__ and __enter__.

    Args:
      sig: A pytd.Signature.

    Returns:
      True if the signature needs a class param, False otherwise.
    """
    if self.class_name and self.function_name and sig.params:
      # Printing the class name escapes illegal characters.
      safe_class_name = pytd.Print(pytd.NamedType(self.class_name))
      return (pytd.Print(sig.return_type) == safe_class_name and
              pytd.Print(sig.params[0].type) in (
                  "Type[%s]" % safe_class_name, safe_class_name))
    return False

  def VisitSignature(self, sig):
    """Potentially replace ~unknowns with type parameters, in a signature."""
    if (self._IsIncomplete(self.class_name) or
        self._IsIncomplete(self.function_name)):
      # Leave unknown classes and call traces as-is, they'll never be part of
      # the output.
      # TODO(kramm): We shouldn't run on call traces in the first place.
      return sig
    counter = _CountUnknowns()
    sig.Visit(counter)
    replacements = {}
    for suffix, count in counter.counter.items():
      if count > 1:
        # We don't care whether it actually occurs in different parameters. That
        # way, e.g. "def f(Dict[T, T])" works, too.
        type_param = pytd.TypeParameter(
            self.PREFIX + str(counter.position[suffix]))
        replacements["~unknown"+suffix] = type_param
    if self._NeedsClassParam(sig):
      type_param = pytd.TypeParameter(
          self.PREFIX + self.class_name, bound=pytd.NamedType(self.class_name))
      replacements[self.class_name] = type_param
    if replacements:
      self.added_new_type_params = True
      sig = sig.Visit(ReplaceTypes(replacements))
    return sig

  def EnterTypeDeclUnit(self, _):
    self.added_new_type_params = False

  def VisitTypeDeclUnit(self, unit):
    if self.added_new_type_params:
      return unit.Visit(AdjustTypeParameters())
    else:
      return unit


# TODO(kramm): The `~unknown` functionality is becoming more important. Should
#              we have support for this on the pytd level? (That would mean
#              changing Class.name to a TYPE). Also, should we just use ~X
#              instead of ~unknownX?
class RaiseIfContainsUnknown(Visitor):
  """Find any 'unknown' Class or ClassType (not: pytd.AnythingType!) in a class.

  It throws HasUnknown on the first occurrence.
  """

  class HasUnknown(Exception):
    """Used for aborting the RaiseIfContainsUnknown visitor early."""
    pass

  # COV_NF_START
  def EnterNamedType(self, _):
    raise AssertionError("This visitor needs the AST to be resolved.")
  # COV_NF_END

  def EnterClassType(self, t):
    if t.name.startswith("~unknown"):
      raise RaiseIfContainsUnknown.HasUnknown()

  def EnterClass(self, cls):
    if cls.name.startswith("~unknown"):
      raise RaiseIfContainsUnknown.HasUnknown()


class VerifyVisitor(Visitor):
  """Visitor for verifying pytd ASTs. For tests."""

  def __init__(self):
    super(VerifyVisitor, self).__init__()
    self._valid_param_name = re.compile(r"[a-zA-Z_]\w*$")

  def Enter(self, node):
    super(VerifyVisitor, self).Enter(node)
    node.Validate()

  def _AssertNoDuplicates(self, node, attrs):
    """Checks that we don't have duplicate top-level names."""

    attr_to_set = {attr: {entry.name for entry in getattr(node, attr)}
                   for attr in attrs}
    # Do a quick sanity check first, and a deeper check if that fails.
    total1 = len(set.union(*attr_to_set.values()))  # all distinct names
    total2 = sum(map(len, attr_to_set.values()), 0)  # all names
    if total1 != total2:
      for a1, a2 in itertools.combinations(attrs, 2):
        both = attr_to_set[a1] & attr_to_set[a2]
        if both:
          raise AssertionError("Duplicate name(s) %s in both %s and %s" % (
              list(both), a1, a2))

  def EnterTypeDeclUnit(self, node):
    self._AssertNoDuplicates(node, ["constants", "type_params", "classes",
                                    "functions", "aliases"])
    self._all_templates = set()

  def LeaveTypeDeclUnit(self, node):
    declared_type_params = {n.name for n in node.type_params}
    for t in self._all_templates:
      if t.name not in declared_type_params:
        raise AssertionError("Type parameter %r used, but not declared. "
                             "Did you call AdjustTypeParameters?" % t.name)

  def EnterClass(self, node):
    self._AssertNoDuplicates(node, ["methods", "constants"])

  def EnterFunction(self, node):
    assert node.signatures, node

  def EnterSignature(self, node):
    assert isinstance(node.has_optional, bool), node

  def EnterTemplateItem(self, node):
    self._all_templates.add(node)

  def EnterParameter(self, node):
    assert self._valid_param_name.match(node.name), node.name

  def EnterCallableType(self, node):
    self.EnterGenericType(node)

  def EnterTupleType(self, node):
    self.EnterGenericType(node)

  def EnterGenericType(self, node):
    assert node.parameters, node


class CanonicalOrderingVisitor(Visitor):
  """Visitor for converting ASTs back to canonical (sorted) ordering.
  """

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


class RemoveFunctionsAndClasses(Visitor):
  """Visitor for removing unwanted functions or classes."""

  def __init__(self, names):
    super(RemoveFunctionsAndClasses, self).__init__()
    self.names = names

  def VisitTypeDeclUnit(self, node):
    return node.Replace(functions=tuple(f for f in node.functions
                                        if f.name not in self.names),
                        classes=tuple(c for c in node.classes
                                      if c.name not in self.names))


class StripExternalNamePrefix(Visitor):
  """Strips off the prefix the parser uses to mark external types.

  The prefix needs to be present for AddNamePrefix, and stripped off afterwards.
  """

  def VisitNamedType(self, node):
    new_name = utils.strip_prefix(node.name,
                                  parser_constants.EXTERNAL_NAME_PREFIX)
    return node.Replace(name=new_name)


class AddNamePrefix(Visitor):
  """Visitor for making names fully qualified.

  This will change
    class Foo:
      pass
    def bar(x: Foo) -> Foo
  to (e.g. using prefix "baz"):
    class baz.Foo:
      pass
    def bar(x: baz.Foo) -> baz.Foo
  """

  def __init__(self):
    super(AddNamePrefix, self).__init__()
    self.cls_stack = []
    self.classes = None
    self.prefix = None
    self.name = None

  def EnterTypeDeclUnit(self, node):
    self.classes = {cls.name for cls in node.classes}
    self.name = node.name
    self.prefix = node.name + "."

  def EnterClass(self, cls):
    self.cls_stack.append(cls)

  def LeaveClass(self, cls):
    assert self.cls_stack[-1] is cls
    self.cls_stack.pop()

  def VisitClassType(self, node):
    if node.cls is not None:
      raise ValueError("AddNamePrefix visitor called after resolving")
    return self.VisitNamedType(node)

  def VisitNamedType(self, node):
    """Prefix a pytd.NamedType."""
    if node.name.startswith(parser_constants.EXTERNAL_NAME_PREFIX):
      # This is an external type; do not prefix it. StripExternalNamePrefix will
      # remove it later.
      return node
    elif node.name.split(".")[0] in self.classes:
      # We need to check just the first part, in case we have a class constant
      # like Foo.BAR, or some similarly nested name.
      return node.Replace(name=self.prefix + node.name)
    else:
      return node

  def VisitClass(self, node):
    name = self.prefix + ".".join(x.name for x in self.cls_stack)
    return node.Replace(name=name)

  def VisitTypeParameter(self, node):
    if node.scope is not None:
      return node.Replace(scope=self.prefix + node.scope)
    # Give the type parameter the name of the module it is in as its scope.
    # Module-level type parameters will keep this scope, but others will get a
    # more specific one in AdjustTypeParameters. The last character in the
    # prefix is the dot appended by EnterTypeDeclUnit, so omit that.
    return node.Replace(scope=self.name)

  def _VisitNamedNode(self, node):
    if self.cls_stack:
      # class attribute
      return node
    else:
      # global constant. Handle leading . for relative module names.
      return node.Replace(
          name=module_utils.get_absolute_name(self.name, node.name))

  def VisitFunction(self, node):
    return self._VisitNamedNode(node)

  def VisitConstant(self, node):
    return self._VisitNamedNode(node)

  def VisitAlias(self, node):
    return self._VisitNamedNode(node)

  def VisitModule(self, node):
    return self._VisitNamedNode(node)


class CollectDependencies(Visitor):
  """Visitor for retrieving module names from external types.

  Needs to be called on a TypeDeclUnit.
  """

  def __init__(self):
    super(CollectDependencies, self).__init__()
    self.modules = set()
    self.late_modules = set()

  def _ProcessName(self, name, modules):
    """Retrieve a module name from a node name."""
    module_name, dot, unused_name = name.rpartition(".")
    if dot:
      if module_name:
        modules.add(module_name)
      else:
        # If we have a relative import that did not get qualified (usually due
        # to an empty package_name), don't insert module_name='' into the
        # dependencies; we get a better error message if we filter it out here
        # and fail later on.
        logging.warning("Empty package name: %s", name)

  def EnterClassType(self, node):
    self._ProcessName(node.name, self.modules)

  def EnterNamedType(self, node):
    self._ProcessName(node.name, self.modules)

  def EnterFunctionType(self, node):
    self._ProcessName(node.name, self.modules)

  def EnterLateType(self, node):
    self._ProcessName(node.name, self.late_modules)


def ExpandSignature(sig):
  """Expand a single signature.

  For argument lists that contain disjunctions, generates all combinations
  of arguments. The expansion will be done right to left.
  E.g., from (a or b, c or d), this will generate the signatures
  (a, c), (a, d), (b, c), (b, d). (In that order)

  Arguments:
    sig: A pytd.Signature instance.

  Returns:
    A list. The visit function of the parent of this node (VisitFunction) will
    process this list further.
  """
  params = []
  for param in sig.params:
    if isinstance(param.type, pytd.UnionType):
      # multiple types
      params.append([param.Replace(type=t) for t in param.type.type_list])
    else:
      # single type
      params.append([param])

  new_signatures = [sig.Replace(params=tuple(combination))
                    for combination in itertools.product(*params)]

  return new_signatures  # Hand list over to VisitFunction


class ExpandSignatures(Visitor):
  """Expand to Cartesian product of parameter types.

  For example, this transforms
    def f(x: int or float, y: int or float) -> str or unicode
  to
    def f(x: int, y: int) -> str or unicode
    def f(x: int, y: float) -> str or unicode
    def f(x: float, y: int) -> str or unicode
    def f(x: float, y: float) -> str or unicode

  The expansion by this class is typically *not* an optimization. But it can be
  the precursor for optimizations that need the expanded signatures, and it can
  simplify code generation, e.g. when generating type declarations for a type
  inferencer.
  """

  def VisitFunction(self, f):
    """Rebuild the function with the new signatures.

    This is called after its children (i.e. when VisitSignature has already
    converted each signature into a list) and rebuilds the function using the
    new signatures.

    Arguments:
      f: A pytd.Function instance.

    Returns:
      Function with the new signatures.
    """

    # concatenate return value(s) from VisitSignature
    signatures = sum([ExpandSignature(s) for s in f.signatures], [])
    return f.Replace(signatures=tuple(signatures))


class AdjustTypeParameters(Visitor):
  """Visitor for adjusting type parameters.

  * Inserts class templates.
  * Inserts signature templates.
  * Adds scopes to type parameters.
  """

  def __init__(self):
    super(AdjustTypeParameters, self).__init__()
    self.class_typeparams = set()
    self.function_typeparams = None
    self.class_template = []
    self.class_name = None
    self.function_name = None
    self.constant_name = None
    self.all_typeparams = set()

  def _GetTemplateItems(self, param):
    """Get a list of template items from a parameter."""
    items = []
    if isinstance(param, pytd.GenericType):
      for p in param.parameters:
        items.extend(self._GetTemplateItems(p))
    elif isinstance(param, pytd.UnionType):
      for p in param.type_list:
        items.extend(self._GetTemplateItems(p))
    elif isinstance(param, pytd.TypeParameter):
      items.append(pytd.TemplateItem(param))
    return items

  def VisitTypeDeclUnit(self, node):
    type_params_to_add = set()
    declared_type_params = {n.name for n in node.type_params}
    # Sorting all_typeparams helps keep pickling deterministic.
    for t in sorted(self.all_typeparams):
      if t.name not in declared_type_params:
        logging.debug("Adding definition for type parameter %r", t.name)
        type_params_to_add.add(t.Replace(scope=None))
    new_type_params = node.type_params + tuple(type_params_to_add)
    return node.Replace(type_params=new_type_params)

  def _CheckDuplicateNames(self, params, class_name):
    seen = set()
    for x in params:
      if x.name in seen:
        raise ContainerError(
            "Duplicate type parameter %s in typing.Generic parent of class %s" %
            (x.name, class_name))
      seen.add(x.name)

  def EnterClass(self, node):
    """Establish the template for the class."""
    templates = []
    generic_template = None

    for parent in node.parents:
      if isinstance(parent, pytd.GenericType):
        params = sum((self._GetTemplateItems(param)
                      for param in parent.parameters), [])
        if parent.base_type.name in ["typing.Generic", "Generic"]:
          # TODO(mdemello): Do we need "Generic" in here or is it guaranteed
          # to be replaced by typing.Generic by the time this visitor is called?
          self._CheckDuplicateNames(params, node.name)
          if generic_template:
            raise ContainerError(
                "Cannot inherit from Generic[...] multiple times in class %s"
                % node.name)
          else:
            generic_template = params
        else:
          templates.append(params)
    if generic_template:
      for params in templates:
        for param in params:
          if param not in generic_template:
            raise ContainerError(
                ("Some type variables (%s) are not listed in Generic of"
                 " class %s") % (param.type_param.name, node.name))
      templates = [generic_template]

    try:
      template = mro.MergeSequences(templates)
    except ValueError:
      raise ContainerError(
          "Illegal type parameter order in class %s" % node.name)

    self.class_template.append(template)

    for t in template:
      assert isinstance(t.type_param, pytd.TypeParameter)
      self.class_typeparams.add(t.name)

    self.class_name = node.name

  def LeaveClass(self, node):
    del node
    for t in self.class_template[-1]:
      if t.name in self.class_typeparams:
        self.class_typeparams.remove(t.name)
    self.class_name = None
    self.class_template.pop()

  def VisitClass(self, node):
    """Builds a template for the class from its GenericType parents."""
    # The template items will not have been properly scoped because they were
    # stored outside of the ast and not visited while processing the class
    # subtree.  They now need to be scoped similar to VisitTypeParameter,
    # except we happen to know they are all bound by the class.
    template = [pytd.TemplateItem(t.type_param.Replace(scope=node.name))
                for t in self.class_template[-1]]
    node = node.Replace(template=tuple(template))
    return node.Visit(AdjustSelf()).Visit(NamedTypeToClassType())

  def EnterSignature(self, unused_node):
    assert self.function_typeparams is None
    self.function_typeparams = set()

  def LeaveSignature(self, unused_node):
    self.function_typeparams = None

  def VisitSignature(self, node):
    # Sorting the template in CanonicalOrderingVisitor is enough to guarantee
    # pyi determinism, but we need to sort here as well for pickle determinism.
    return node.Replace(template=tuple(sorted(self.function_typeparams)))

  def EnterFunction(self, node):
    self.function_name = node.name

  def LeaveFunction(self, unused_node):
    self.function_name = None

  def EnterConstant(self, node):
    self.constant_name = node.name

  def LeaveConstant(self, unused_node):
    self.constant_name = None

  def _GetFullName(self, name):
    return ".".join(n for n in [self.class_name, name] if n)

  def _GetScope(self, name):
    if name in self.class_typeparams:
      return self.class_name
    return self._GetFullName(self.function_name)

  def VisitTypeParameter(self, node):
    """Add scopes to type parameters, track unbound params."""
    if self.constant_name and (not self.class_name or
                               node.name not in self.class_typeparams):
      raise ContainerError("Unbound type parameter %s in %s" % (
          node.name, self._GetFullName(self.constant_name)))
    scope = self._GetScope(node.name)
    if scope:
      node = node.Replace(scope=scope)
    else:
      # This is a top-level type parameter (TypeDeclUnit.type_params).
      # AddNamePrefix gave it the right scope, so leave it alone.
      pass

    if (self.function_typeparams is not None and
        node.name not in self.class_typeparams):
      self.function_typeparams.add(pytd.TemplateItem(node))
    self.all_typeparams.add(node)

    return node


class VerifyContainers(Visitor):
  """Visitor for verifying containers.

  Every container (except typing.Generic) must inherit from typing.Generic and
  have an explicitly parameterized parent that is also a container. The
  parameters on typing.Generic must all be TypeVar instances. A container must
  have at most as many parameters as specified in its template.

  Raises:
    ContainerError: If a problematic container definition is encountered.
  """

  def EnterGenericType(self, node):
    """Verify a pytd.GenericType."""
    base_type = node.base_type
    if isinstance(base_type, pytd.LateType):
      return  # We can't verify this yet
    if not pytd.IsContainer(base_type.cls):
      raise ContainerError("Class %s is not a container" % base_type.name)
    elif base_type.name == "typing.Generic":
      for t in node.parameters:
        if not isinstance(t, pytd.TypeParameter):
          raise ContainerError("Name %s must be defined as a TypeVar" % t.name)
    elif not isinstance(node, (pytd.CallableType, pytd.TupleType)):
      max_param_count = len(base_type.cls.template)
      actual_param_count = len(node.parameters)
      if actual_param_count > max_param_count:
        raise ContainerError(
            "Too many parameters on %s: expected %s, got %s" % (
                base_type.name, max_param_count, actual_param_count))

  def EnterCallableType(self, node):
    self.EnterGenericType(node)

  def EnterTupleType(self, node):
    self.EnterGenericType(node)

  def _GetGenericBasesLookupMap(self, node):
    """Get a lookup map for the generic bases of a class.

    Gets a map from a pytd.ClassType to the list of pytd.GenericType bases of
    the node that have that class as their base. This method does depth-first
    traversal of the bases, which ensures that the order of elements in each
    list is consistent with the node's MRO.

    Args:
      node: A pytd.Class node.

    Returns:
      A pytd.ClassType -> List[pytd.GenericType] map.
    """
    mapping = collections.defaultdict(list)
    seen_bases = set()
    bases = list(reversed(node.parents))
    while bases:
      base = bases.pop()
      if base in seen_bases:
        continue
      seen_bases.add(base)
      if (isinstance(base, pytd.GenericType) and
          isinstance(base.base_type, pytd.ClassType)):
        mapping[base.base_type].append(base)
        bases.extend(reversed(base.base_type.cls.parents))
      elif isinstance(base, pytd.ClassType):
        bases.extend(reversed(base.cls.parents))
    return mapping

  def _UpdateParamToValuesMapping(self, mapping, param, value):
    """Update the given mapping of parameter names to values."""
    param_name = param.type_param.full_name
    if isinstance(value, pytd.TypeParameter):
      value_name = value.full_name
      assert param_name != value_name
      # A TypeVar has been aliased, e.g.,
      #   class MyList(List[U]): ...
      #   class List(Sequence[T]): ...
      # Register the alias. May raise AliasingDictConflictError.
      mapping.add_alias(param_name, value_name, set.union)
    else:
      # A TypeVar has been given a concrete value, e.g.,
      #   class MyList(List[str]): ...
      # Register the value.
      if param_name not in mapping:
        mapping[param_name] = set()
      mapping[param_name].add(value)

  def _TypeCompatibilityCheck(self, type_params):
    """Check if the types are compatible.

    It is used to handle the case:
      class A(Sequence[A]): pass
      class B(A, Sequence[B]): pass
      class C(B, Sequence[C]): pass
    In class `C`, the type parameter `_T` of Sequence could be `A`, `B` or `C`.
    Next we will check they have a linear inheritance relationship:
    `A` -> `B` -> `C`.

    Args:
      type_params: The class type params.

    Returns:
      True if all the types are compatible.
    """
    type_params = {t for t in type_params
                   if not isinstance(t, pytd.AnythingType)}
    if not all(isinstance(t, pytd.ClassType) for t in type_params):
      return False
    mro_list = [set(mro.GetBasesInMRO(t.cls)) for t in type_params]
    mro_list.sort(key=len)
    prev = set()
    for cur in mro_list:
      if not cur.issuperset(prev):
        return False
      prev = cur
    return True

  def EnterClass(self, node):
    """Check for conflicting type parameter values in the class's bases."""
    # Get the bases in MRO, since we need to know the order in which type
    # parameters are aliased or assigned values.
    try:
      classes = mro.GetBasesInMRO(node)
    except mro.MROError:
      # TODO(rechen): We should report this, but VerifyContainers() isn't the
      # right place to check for mro errors.
      return
    # GetBasesInMRO gave us the pytd.ClassType for each base. Map class types
    # to generic types so that we can iterate through the latter in MRO.
    cls_to_bases = self._GetGenericBasesLookupMap(node)
    param_to_values = datatypes.AliasingDict()
    ambiguous_aliases = set()
    for base in sum((cls_to_bases[cls] for cls in classes), []):
      for param, value in zip(base.base_type.cls.template, base.parameters):
        try:
          self._UpdateParamToValuesMapping(param_to_values, param, value)
        except datatypes.AliasingDictConflictError:
          ambiguous_aliases.add(param.type_param.full_name)
    for param_name, values in param_to_values.items():
      if any(param_to_values[alias] is values for alias in ambiguous_aliases):
        # Any conflict detected for this type parameter might be a false
        # positive, since a conflicting value assigned through an ambiguous
        # alias could have been meant for a different type parameter.
        continue
      elif len(values) > 1 and not self._TypeCompatibilityCheck(values):
        raise ContainerError(
            "Conflicting values for TypeVar %s: %s" % (
                param_name, ", ".join(str(v) for v in values)))
    for t in node.template:
      if t.type_param.full_name in param_to_values:
        value, = param_to_values[t.type_param.full_name]
        raise ContainerError(
            "Conflicting value %s for TypeVar %s" % (value,
                                                     t.type_param.full_name))


class ExpandCompatibleBuiltins(Visitor):
  """Ad-hoc inheritance.

  In parameters, replaces
    ClassType('__builtin__.float')
  with
    Union[ClassType('__builtin__.float'), ClassType('__builtin__.int')]

  And similarly for unicode->(unicode, str, bytes) and bool->(bool, None).

  Used to allow a function requiring a float to accept an int without making
  int inherit from float.

  NOTE: We do not do this for type parameter constraints.

  See https://www.python.org/dev/peps/pep-0484/#the-numeric-tower
  """

  def __init__(self, builtins):
    super(ExpandCompatibleBuiltins, self).__init__()
    self.in_parameter = False
    self.in_type_parameter = False
    self.replacements = self._BuildReplacementMap(builtins)

  @staticmethod
  def _BuildReplacementMap(builtins):
    """Dict[str, UnionType[ClassType, ...]] map."""
    prefix = builtins.name + "."
    rmap = collections.defaultdict(list)
    # Import here due to circular import.
    from pytype.pytd import pep484  # pylint: disable=g-import-not-at-top

    # compat_list :: [(compat, name)], where name is the more generalized
    # type and compat is the less generalized one. (eg: name = float, compat =
    # int)
    compat_list = itertools.chain(
        set((v, v) for _, v in pep484.COMPAT_ITEMS), pep484.COMPAT_ITEMS)

    for compat, name in compat_list:
      prefix = builtins.name + "."
      full_name = prefix + compat
      t = builtins.Lookup(full_name)
      if isinstance(t, pytd.Class):
        # Depending on python version, bytes can be an Alias, if so don't
        # want it in our union
        rmap[prefix + name].append(pytd.ClassType(full_name, t))

    return {k: pytd.UnionType(tuple(v)) for k, v in six.iteritems(rmap)}

  def EnterParameter(self, _):
    assert not self.in_parameter
    self.in_parameter = True

  def LeaveParameter(self, _):
    assert self.in_parameter
    self.in_parameter = False

  def EnterTypeParameter(self, _):
    assert not self.in_type_parameter
    self.in_type_parameter = True

  def LeaveTypeParameter(self, _):
    assert self.in_type_parameter
    self.in_type_parameter = False

  def VisitClassType(self, node):
    if self.in_parameter and not self.in_type_parameter:
      return self.replacements.get(node.name, node)
    else:
      return node


class ClearClassPointers(Visitor):
  """Set .cls pointers to 'None'."""

  def EnterClassType(self, node):
    node.cls = None


class ReplaceModulesWithAny(RemoveTypeParametersFromGenericAny):
  """Replace all references to modules in a list with AnythingType."""

  def __init__(self, module_list):
    super(ReplaceModulesWithAny, self).__init__()
    assert isinstance(module_list, list)
    self._any_modules = module_list

  def VisitNamedType(self, n):
    if any(n.name.startswith(module) for module in self._any_modules):
      return pytd.AnythingType()
    return n

  def VisitLateType(self, n):
    return self.VisitNamedType(n)

  def VisitClassType(self, n):
    return self.VisitNamedType(n)


class ReplaceUnionsWithAny(Visitor):

  def VisitUnionType(self, _):
    return pytd.AnythingType()


class ClassTypeToLateType(Visitor):
  """Convert ClassType to LateType."""

  def __init__(self, ignore):
    """Initialize the visitor.

    Args:
      ignore: A list of prefixes to ignore. Typically, this list includes
        things something like like "__builtin__.", since we don't want to
        convert builtin types to late types. (And, more generally, types of
        modules that are always loaded by pytype don't need to be late types)
    """
    super(ClassTypeToLateType, self).__init__()
    self._ignore = ignore

  def VisitClassType(self, n):
    for prefix in self._ignore:
      if n.name.startswith(prefix) and "." not in n.name[len(prefix):]:
        return n
    return pytd.LateType(n.name)


class LateTypeToClassType(Visitor):
  """Convert LateType to (unresolved) ClassType."""

  def VisitLateType(self, t):
    return pytd.ClassType(t.name, None)


class DropMutableParameters(Visitor):
  """Drops all mutable parameters.

  Drops all mutable parameters. This visitor differs from
  transforms.RemoveMutableParameters in that the latter absorbs mutable
  parameters into the signature, while this one blindly drops them.
  """

  def VisitParameter(self, p):
    return p.Replace(mutated_type=None)
