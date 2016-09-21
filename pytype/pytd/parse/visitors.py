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

import collections
import itertools
import logging
import re


from pytype.pytd import pytd
from pytype.pytd.parse import parser_constants  # pylint: disable=g-importing-member


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


class Visitor(object):
  """Base class for visitors.

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
  """
  visits_all_node_types = False
  unchecked_node_names = set()

  _visitor_functions_cache = {}

  def __init__(self):
    cls = self.__class__

    if cls in Visitor._visitor_functions_cache:
      enter_fns, visit_fns, leave_fns = Visitor._visitor_functions_cache[cls]
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
      Visitor._visitor_functions_cache[cls] = (enter_fns, visit_fns, leave_fns)

    self.enter_functions = enter_fns
    self.visit_functions = visit_fns
    self.leave_functions = leave_fns

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
  PEP484_CAPITALIZED = {
      # The PEP 484 definition of built-in types.
      # E.g. "typing.List" is used to represent the "list" type.
      "List", "Dict", "Tuple", "Set", "Generator", "Iterator"
  }

  def __init__(self):
    super(PrintVisitor, self).__init__()
    self.class_names = []  # allow nested classes
    self.imports = collections.defaultdict(set)
    self.in_alias = False
    self.in_parameter = False
    self._local_names = set()
    self._class_members = set()

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
    assert isinstance(t, pytd.HomogeneousContainerType)
    return t.base_type == "tuple"

  def _RequireImport(self, module, name=None):
    """Register that we're using name from module.

    Args:
      module: string identifier.
      name: if None, means we want 'import module'. Otherwise string identifier
       that we want to import.
    """
    if not self.in_alias:
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
      if None in names:
        ret.append("import %s" % module)
        names.remove(None)

      if names:
        name_str = ", ".join(sorted(names))
        ret.append("from %s import %s" % (module, name_str))

    return ret

  def _IsBuiltin(self, module, name):
    return module == "__builtin__" and name not in self._local_names

  def _FormatTypeParams(self, type_params):
    return ["%s = TypeVar('%s')" % (t, t) for t in type_params]

  def EnterTypeDeclUnit(self, unit):
    definitions = (unit.classes + unit.functions + unit.constants +
                   unit.type_params + unit.aliases)
    self._local_names = {c.name for c in definitions}

  def LeaveTypeDeclUnit(self, _):
    self._local_names = set()

  def VisitTypeDeclUnit(self, node):
    """Convert the AST for an entire module back to a string."""
    if node.type_params:
      self._RequireTypingImport("TypeVar")
    sections = [self._GenerateImportStrings(), node.aliases, node.constants,
                self._FormatTypeParams(node.type_params), node.functions,
                node.classes]

    sections_as_string = ("\n".join(section_suite)
                          for section_suite in sections
                          if section_suite)
    return "\n\n".join(sections_as_string)

  def VisitConstant(self, node):
    """Convert a class-level or module-level constant to a string."""
    return self._SafeName(node.name) + " = ...  # type: " + node.type

  def VisitAlias(self, node):
    """Convert an import or alias to a string."""
    if isinstance(self.old_node.type, pytd.NamedType):
      full_name = self.old_node.type.name
      suffix = ""
      module, _, name = full_name.rpartition(".")
      if module:
        if name != self.old_node.name:
          suffix += " as " + self.old_node.name
        return "from " + module + " import " + name + suffix
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

  def EnterAlias(self, unused_node):
    assert not self.in_alias
    self.in_alias = True

  def LeaveAlias(self, unused_node):
    assert self.in_alias
    self.in_alias = False

  def VisitClass(self, node):
    """Visit a class, producing a multi-line, properly indented string."""
    parents = node.parents
    # If classobj is the only parent, then this is an old-style class, don't
    # list any parents.
    if parents == ("classobj",):
      parents = ()
    parents_str = "(" + ", ".join(parents) + ")" if parents else ""
    header = "class " + self._SafeName(node.name) + parents_str + ":"
    if node.methods or node.constants:
      # We have multiple methods, and every method has multiple signatures
      # (i.e., the method string will have multiple lines). Combine this into
      # an array that contains all the lines, then indent the result.
      constants = [self.INDENT + m for m in node.constants]
      method_lines = sum((m.splitlines() for m in node.methods), [])
      methods = [self.INDENT + m for m in method_lines]
    else:
      constants = []
      methods = [self.INDENT + "pass"]
    return "\n".join([header] + constants + methods) + "\n"

  def VisitFunction(self, node):
    """Visit function, producing multi-line string (one for each signature)."""
    function_name = self._EscapedName(node.name)
    decorators = ""
    if node.kind == pytd.STATICMETHOD and function_name != "__new__":
      decorators += "@staticmethod\n"
    elif node.kind == pytd.CLASSMETHOD:
      decorators += "@classmethod\n"
    signatures = "\n".join(decorators + "def " + function_name + sig
                           for sig in node.signatures)
    return signatures

  def VisitExternalFunction(self, node):
    """Visit function defined with PYTHONCODE."""
    return "def " + self._SafeName(node.name) + " PYTHONCODE"

  def _FormatContainerContents(self, node):
    """Print out the last type parameter of a container. Used for *args/**kw."""
    assert isinstance(node, pytd.Parameter)
    if isinstance(node.type, pytd.GenericType):
      return node.Replace(type=node.type.parameters[-1], optional=False).Visit(
          PrintVisitor())
    else:
      return node.Replace(type=pytd.NamedType("object"), optional=False).Visit(
          PrintVisitor())

  def VisitSignature(self, node):
    """Visit a signature, producing a string."""
    # TODO(pludemann): might want special handling for __init__(...) -> NoneType
    # Design decision: we used to allow the return type to default to "?"  (see
    # comments in parser.py for the "return" rule) but that led to confusion, so
    # we now require all function signatures to have a return type.
    ret = " -> " + node.return_type

    exc = " raises " + ", ".join(node.exceptions) if node.exceptions else ""

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

    # Handle Mutable parameters
    # pylint: disable=no-member
    # (old_node is set in parse/node.py)
    mutable_params = [(p.name, p.mutated_type) for p in self.old_node.params
                      if p.mutated_type is not None]
    # pylint: enable=no-member
    if mutable_params:
      body = ":\n" + "\n".join("{indent}{name} := {new_type}".format(
          indent=self.INDENT, name=name,
          new_type=new_type.Visit(PrintVisitor()))
                               for name, new_type in mutable_params)
    else:
      body = ": ..."

    return "({params}){ret}{exc}{body}".format(
        params=", ".join(params),
        ret=ret, exc=exc, body=body)

  def EnterParameter(self, unused_node):
    assert not self.in_parameter
    self.in_parameter = True

  def LeaveParameter(self, unused_node):
    assert self.in_parameter
    self.in_parameter = False

  def VisitParameter(self, node):
    """Convert a function parameter to a string."""
    suffix = " = ..." if node.optional else ""
    if node.type == "object" or node.type == "Any":
      # Abbreviated form. "object" or "Any" is the default.
      return node.name + suffix
    elif node.name == "self" and self.class_names and (
        node.type == self.class_names[-1]):
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
    module, _, suffix = node.name.partition(".")
    if self._IsBuiltin(module, suffix):
      node_name = suffix
      if node_name == "function":
        node_name = "typing.Callable"
    else:
      node_name = node.name
    if node_name == "NoneType":
      # PEP 484 allows this special abbreviation.
      return "None"
    else:
      name = self._SafeName(node_name)
      if "." in name:
        module = name[:name.rfind(".")]
        self._RequireImport(module)
      return name

  def VisitClassType(self, node):
    return self.VisitNamedType(node)

  def VisitStrictType(self, node):
    # 'StrictType' is defined, and internally used, by booleq.py. We allow it
    # here so that booleq.py can use pytd.Print().
    return self.VisitNamedType(node)

  def VisitFunctionType(self, unused_node):
    """Convert a function type to a string."""
    self._RequireTypingImport("Callable")
    return "Callable"

  def VisitAnythingType(self, unused_node):
    """Convert an anything type to a string."""
    self._RequireTypingImport("Any")
    return "Any"

  def VisitNothingType(self, unused_node):
    """Convert the nothing type to a string."""
    return "nothing"

  def VisitTypeParameter(self, node):
    return self._SafeName(node.name)

  def MaybeCapitalize(self, name):
    """Capitalize a generic type, if necessary."""
    capitalized = name.capitalize()
    if capitalized in self.PEP484_CAPITALIZED:
      if (capitalized in self._local_names or
          capitalized in self._class_members):
        self._RequireTypingImport()
        return "typing." + capitalized
      else:
        self._RequireTypingImport(capitalized)
        return capitalized
    else:
      return name

  def VisitHomogeneousContainerType(self, node):
    """Convert a homogeneous container type to a string."""
    ellipsis = ", ..." if self._NeedsTupleEllipsis(node) else ""
    return (self.MaybeCapitalize(node.base_type) +
            "[" + node.element_type + ellipsis + "]")

  def VisitGenericType(self, node):
    """Convert a generic type (E.g. list[int]) to a string."""
    param_str = ", ".join(node.parameters)
    return (self.MaybeCapitalize(node.base_type) +
            "[" + param_str + "]")

  def VisitUnionType(self, node):
    """Convert a union type ("x or y") to a string."""
    if self.in_parameter:
      # Parameter's union types are merged after as a follow up to the
      # ExpandCompatibleBuiltins visitor.
      # Import here due to circular import.
      from pytype.pytd import pep484  # pylint: disable=g-import-not-at-top
      type_list = collections.OrderedDict.fromkeys(node.type_list)
      for compat, name in pep484.COMPAT_MAP.iteritems():
        # name can replace compat.
        if compat in type_list and name in type_list:
          del type_list[compat]
      type_list = tuple(type_list)
    else:
      type_list = node.type_list

    if len(type_list) == 1:
      return type_list[0]
    else:
      self._RequireTypingImport("Union")
      return "Union[" + ", ".join(type_list) + "]"


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


class FillInModuleClasses(Visitor):
  """Fill in ClassType pointers using a symbol table.

  This is an in-place visitor! It modifies the original tree. This is
  necessary because we introduce loops.
  """

  def __init__(self, lookup_map):
    """Create this visitor.

    You're expected to then pass this instance to node.Visit().

    Args:
      lookup_map: An iterable of symbol tables (i.e., objects that have a
        "Lookup" function)
    """
    super(FillInModuleClasses, self).__init__()
    self._lookup_map = lookup_map

  def EnterClassType(self, node):
    """Fills in a class type.

    Args:
      node: A ClassType. This node will have a name, which we use for lookup.

    Returns:
      The same ClassType. We will have filled in its "cls" attribute.

    Raises:
      KeyError: If we can't find a given class.
    """
    module, _, _ = node.name.rpartition(".")
    if module:
      modules_to_try = [("", module)]
    else:
      modules_to_try = [("", ""),
                        ("", "__builtin__"),
                        ("__builtin__.", "__builtin__")]
    for prefix, module in modules_to_try:
      mod_ast = self._lookup_map.get(module)
      if mod_ast:
        try:
          cls = mod_ast.Lookup(prefix + node.name)
        except KeyError:
          pass
        else:
          if isinstance(cls, pytd.Class):
            node.cls = cls
            return
          else:
            logging.warning("Couldn't resolve %s: Not a class: %s",
                            prefix + node.name, type(cls))


class LookupFullNames(Visitor):
  """Fill in ClassType pointers using a symbol table, using the full names."""

  def __init__(self, lookup_list):
    super(LookupFullNames, self).__init__()
    self._lookup_list = lookup_list

  def EnterClassType(self, node):
    for lookup in self._lookup_list:
      try:
        cls = lookup.Lookup(node.name)
      except KeyError:
        try:
          cls = lookup.Lookup("__builtin__." + node.name)
        except KeyError:
          continue
      if not isinstance(cls, pytd.Class):
        raise KeyError("%s is not a class: %s" % (node.name, type(cls)))
      node.cls = cls
      return


def _ToType(item, allow_constants=True):
  """Convert a pytd AST item into a type."""
  if isinstance(item, pytd.TYPE):
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
    raise


class DefaceUnresolved(Visitor):
  """Replace all types not in a symbol table with AnythingType."""

  unchecked_node_names = ("GenericType",)

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
        logging.error("Setting %s to ?", name)
      return pytd.AnythingType()

  def VisitHomogeneousContainerType(self, node):
    if isinstance(node.base_type, pytd.AnythingType):
      return node.base_type
    else:
      return node

  def VisitGenericType(self, node):
    if isinstance(node.base_type, pytd.AnythingType):
      return node.base_type
    else:
      return node

  def VisitClassType(self, node):
    return self.VisitNamedType(node)


class ClearClassTypePointers(Visitor):
  """For ClassType nodes: Set their cls pointer to None."""

  def EnterClassType(self, node):
    node.cls = None


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


def InPlaceFillInClasses(target, global_module=None):
  """Fill in class pointers in ClassType nodes for a PyTD object.

  This will adjust the "cls" pointer for existing ClassType nodes so that they
  point to their named class. It will only do this for cls pointers that are
  None, otherwise it will keep the old value.  Use the NamedTypeToClassType
  visitor to create the ClassType nodes in the first place. Use the
  ClearClassTypePointers visitor to set the "cls" pointers for already existing
  ClassType nodes back to None.

  Args:
    target: The PyTD object to operate on. Changes will happen in-place. If this
      is a TypeDeclUnit it will also be used for lookups.
    global_module: Global symbols. Tried if a name doesn't exist locally. This
      is required if target is not a TypeDeclUnit.
  """
  if global_module is None:
    global_module = target

  # Fill in classes for this module, bottom up.
  # TODO(kramm): Node.Visit() should support blacklisting of attributes so
  # we don't recurse into submodules multiple times.
  if isinstance(target, pytd.TypeDeclUnit):
    # "" is the module itself (local lookup)
    target.Visit(FillInModuleClasses({"": target,
                                      "__builtin__": global_module}))
  else:
    target.Visit(FillInModuleClasses({"__builtin__": global_module}))


def LookupClasses(module, global_module=None, overwrite=False):
  """Converts a module from one using NamedType to ClassType.

  Args:
    module: The module to process.
    global_module: The global (builtins) module for name lookup. Can be None.
    overwrite: If we should overwrite the "cls" pointer of existing ClassType
      nodes. Otherwise, "cls" pointers of existing ClassType nodes will only
      be written if they are None.

  Returns:
    A new module that only uses ClassType. All ClassType instances will point
    to concrete classes.

  Throws:
    KeyError: If we can't find a class.
  """
  module = module.Visit(NamedTypeToClassType())
  if overwrite:
    # Set cls pointers to None so that InPlaceFillInClasses can set them.
    module = module.Visit(ClearClassTypePointers())
  InPlaceFillInClasses(module, global_module)
  module.Visit(VerifyLookup())
  return module


class VerifyLookup(Visitor):
  """Utility class for testing visitors.LookupClasses."""

  def EnterNamedType(self, node):
    raise ValueError("Unreplaced NamedType: %r" % node.name)

  def EnterClassType(self, node):
    # TODO(pludemann): Can we give more context for this error? It's not very
    #                  useful when it says that "T" is unresolved (e.g., from
    #                  "def foo(x: list[T]))" ... it would be nice to know what
    #                  it's inside.
    if node.cls is None:
      raise ValueError("Unresolved class: %r" % node.name)


class LookupBuiltins(Visitor):
  """Look up built-in NamedTypes and give them fully-qualified names."""

  def __init__(self, builtins):
    """Create this visitor.

    Args:
      builtins: The builtins module.
    """
    super(LookupBuiltins, self).__init__()
    self._builtins = builtins

  def EnterTypeDeclUnit(self, unit):
    self._current_unit = unit
    self._prefix = unit.name + "."

  def LeaveTypeDeclUnit(self, _):
    del self._current_unit
    del self._prefix

  def VisitNamedType(self, t):
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
        return _ToType(item)
    else:
      return t


class LookupExternalTypes(Visitor):
  """Look up NamedType pointers using a symbol table."""

  def __init__(self, module_map, full_names=False, self_name=None):
    """Create this visitor.

    Args:
      module_map: A dictionary mapping module names to symbol tables.
      full_names: If True, then the modules in the module_map use fully
        qualified names ("collections.OrderedDict" instead of "OrderedDict")
      self_name: The name of the current module. If provided, then the visitor
        will ignore nodes with this module name.
    """
    super(LookupExternalTypes, self).__init__()
    self._module_map = module_map
    self.full_names = full_names
    self.name = self_name

  def _ResolveUsingGetattr(self, module_name, module):
    """Try to resolve an identifier using the top level __getattr__ function."""
    try:
      if self.full_names:
        g = module.Lookup(module_name + ".__getattr__")
      else:
        g = module.Lookup("__getattr__")
    except KeyError:
      return None
    # TODO(kramm): Make parser.py actually enforce this:
    assert len(g.signatures) == 1
    return g.signatures[0].return_type

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
    module_name, dot, name = t.name.rpartition(".")
    if not dot or module_name == self.name:
      # Nothing to do here. This visitor will only look up nodes in other
      # modules.
      return t
    module = self._module_map[module_name]
    try:
      if self.full_names:
        item = module.Lookup(module_name + "." + name)
      else:
        item = module.Lookup(name)
    except KeyError:
      item = self._ResolveUsingGetattr(module_name, module)
      if item is None:
        raise KeyError("No %s in module %s" % (name, module_name))
    return _ToType(item)

  def VisitClassType(self, t):
    return self.VisitNamedType(t)


class LookupLocalTypes(Visitor):
  """Look up local identifiers. Must be called on a TypeDeclUnit."""

  def EnterTypeDeclUnit(self, unit):
    self.unit = unit

  def LeaveTypeDeclUnit(self, _):
    del self.unit

  def VisitNamedType(self, node):
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
      return _ToType(item, allow_constants=False)
    elif module_name == self.unit.name:
      return _ToType(self.unit.Lookup(node.name), allow_constants=False)
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


class ExtractSuperClassesByName(Visitor):
  """Visitor for extracting all superclasses (i.e., the class hierarchy).

  This returns a mapping by name, e.g. {
    "bool": ["int"],
    "int": ["object"],
    ...
  }.
  """

  def __init__(self):
    super(ExtractSuperClassesByName, self).__init__()
    self._superclasses = {}

  def VisitTypeDeclUnit(self, module):
    del module
    return self._superclasses

  def EnterClass(self, cls):
    parent_names = []
    for parent in cls.parents:
      if isinstance(parent, pytd.GenericType):
        parent_names.append(parent.base_type.name)
      elif isinstance(parent, pytd.GENERIC_BASE_TYPE):
        parent_names.append(parent.name)
    self._superclasses[cls.name] = parent_names


class ExtractSuperClasses(Visitor):
  """Visitor for extracting all superclasses (i.e., the class hierarchy).

  When called on a TypeDeclUnit, this yields a dictionary mapping pytd.Class
  to lists of pytd.TYPE.
  """

  def __init__(self):
    super(ExtractSuperClasses, self).__init__()
    self._superclasses = {}

  def VisitTypeDeclUnit(self, module):
    del module
    return self._superclasses

  def EnterNamedType(self, _):
    raise AssertionError(
        "This visitor needs a resolved AST. Call LookupClasses() before.")

  def EnterClass(self, cls):
    # TODO(kramm): This uses the entire class node as a key, instead of just
    # its id.
    self._superclasses[cls] = cls.parents


class ReplaceTypeParameters(Visitor):
  """Visitor for replacing type parameters with actual types."""

  def __init__(self, mapping):
    super(ReplaceTypeParameters, self).__init__()
    self.mapping = mapping

  def VisitTypeParameter(self, p):
    return self.mapping[p]


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
    self.replaced_self_types = (pytd.NamedType("object"),
                                pytd.ClassType("object"),
                                pytd.ClassType("__builtin__.object"))

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
    if p.name == "self" and (self.force or p.type in self.replaced_self_types):
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
      if self.parameter:
        return pytd.NamedType("__builtin__.object")
      else:
        return pytd.AnythingType()
    else:
      return t

  def VisitNamedType(self, t):
    if t.name.startswith("~unknown"):
      if self.parameter:
        return pytd.NamedType("__builtin__.object")
      else:
        return pytd.AnythingType()
    else:
      return t

  def VisitTypeDeclUnit(self, u):
    return u.Replace(classes=tuple(
        cls for cls in u.classes if not cls.name.startswith("~unknown")))


# TODO(kramm): The `~unknown` functionality is becoming more important. Should
#              we have support for this on the pytd level? (That would mean
#              changing Class.name to a TYPE). Also, should we just use ~X
#              instead of ~unknownX?
class RaiseIfContainsUnknown(Visitor):
  """Find any 'unknown' Class or ClassType (not: pytd.AnythingType!) in a class.

  It throws HasUnknown on the first occurence.
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

  def EnterFunction(self, node):
    assert node.signatures, node

  def EnterExternalFunction(self, node):
    assert node.signatures == (), node  # pylint: disable=g-explicit-bool-comparison

  def EnterSignature(self, node):
    assert isinstance(node.has_optional, bool), node

  def EnterParameter(self, node):
    assert self._valid_param_name.match(node.name), node.name

  def EnterHomogeneousContainerType(self, node):
    assert len(node.parameters) == 1, node


class CanonicalOrderingVisitor(Visitor):
  """Visitor for converting ASTs back to canonical (sorted) ordering.
  """

  def __init__(self, sort_signatures=False):
    super(CanonicalOrderingVisitor, self).__init__()
    self.sort_signatures = sort_signatures

  # TODO(pludemann): might want to add __new__ defns to the various types here
  #                  to ensure the args are tuple, and can then remove the
  #                  tuple(...) wrappers here ...

  def VisitTypeDeclUnit(self, node):
    return pytd.TypeDeclUnit(name=node.name,
                             constants=tuple(sorted(node.constants)),
                             type_params=tuple(sorted(node.type_params)),
                             functions=tuple(sorted(node.functions)),
                             classes=tuple(sorted(node.classes)),
                             aliases=tuple(sorted(node.aliases)))

  def VisitClass(self, node):
    return pytd.Class(name=node.name,
                      parents=node.parents,
                      methods=tuple(sorted(node.methods)),
                      constants=tuple(sorted(node.constants)),
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
    return node.Replace(exceptions=tuple(sorted(node.exceptions)))

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
  .
  """

  def __init__(self):
    super(AddNamePrefix, self).__init__()
    self.cls = None
    self.prefix = None

  def EnterTypeDeclUnit(self, node):
    self.prefix = node.name + "."
    self.classes = {cls.name for cls in node.classes}

  def EnterClass(self, cls):
    self.cls = cls

  def LeaveClass(self, cls):
    assert self.cls is cls
    self.cls = None

  def VisitClassType(self, _):
    raise ValueError("AddNamePrefix visitor called after resolving")

  def VisitNamedType(self, node):
    if node.name in self.classes:
      return node.Replace(name=self.prefix + node.name)
    else:
      return node

  def VisitClass(self, node):
    return node.Replace(name=self.prefix + node.name)

  def VisitTypeParameter(self, node):
    if node.scope is not None:
      raise ValueError("AddNamePrefix called after AddTypeParameterScopes")
    # Give the type parameter the name of the module it is in as its scope.
    # Module-level type parameters will keep this scope, but others will get a
    # more specific one in AddTypeParameterScopes. The last character in the
    # prefix is the dot appended by EnterTypeDeclUnit, so omit that.
    return node.Replace(scope=self.prefix[:-1])

  def _VisitNamedNode(self, node):
    if self.cls:
      # class attribute
      return node
    else:
      # global constant
      return node.Replace(name=self.prefix + node.name)

  def VisitFunction(self, node):
    return self._VisitNamedNode(node)

  def VisitExternalFunction(self, node):
    return self._VisitNamedNode(node)

  def VisitConstant(self, node):
    return self._VisitNamedNode(node)

  def VisitAlias(self, node):
    return self._VisitNamedNode(node)


class CollectDependencies(Visitor):
  """Visitor for retrieving module names from external types."""

  def __init__(self):
    super(CollectDependencies, self).__init__()
    self.modules = set()

  def EnterNamedType(self, t):
    module_name, dot, unused_name = t.name.rpartition(".")
    if dot:
      self.modules.add(module_name)

  def EnterClassType(self, t):
    self.EnterNamedType(t)


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


def MergeSequences(seqs):
  """Merge a sequence of sequences into a single sequence.

  This code is copied from https://www.python.org/download/releases/2.3/mro/
  with print statements removed and modified to take a sequence of sequences.
  We use it to merge both MROs and class templates.

  Args:
    seqs: A sequence of sequences.

  Returns:
    A single sequence in which every element of the input sequences appears
    exactly once and local precedence order is preserved.

  Raises:
    ValueError: If the merge is impossible.
  """
  res = []
  while True:
    if not any(seqs):  # any empty subsequence left?
      return res
    for seq in seqs:  # find merge candidates among seq heads
      if not seq:
        continue
      cand = seq[0]
      if getattr(cand, "SINGLETON", False):
        # Special class. Cycles are allowed. Emit and remove duplicates.
        seqs = [[s for s in seq if s != cand]
                for seq in seqs]
        break
      if any(s for s in seqs if cand in s[1:] and s is not seq):
        cand = None  # reject candidate
      else:
        # Remove and emit. The candidate can be head of more than one list.
        for seq in seqs:
          if seq and seq[0] == cand:
            del seq[0]
        break
    if cand is None:
      raise ValueError
    res.append(cand)


class InsertClassTemplates(Visitor):
  """Visitor for inserting class templates."""

  def VisitClass(self, node):
    """Builds a template for the class from its GenericType parents."""
    templates = []
    for parent in node.parents:
      if isinstance(parent, pytd.GenericType):
        templates.append([pytd.TemplateItem(param)
                          for param in parent.parameters
                          if isinstance(param, pytd.TypeParameter)])
    try:
      template = MergeSequences(templates)
    except ValueError:
      raise ContainerError(
          "Illegal type parameter order in class %s" % node.name)
    # This point is the earliest at which AdjustSelf can be called, since self
    # needs the template for mutations
    return node.Replace(template=tuple(template)).Visit(AdjustSelf()).Visit(
        NamedTypeToClassType())

  def VisitNamedType(self, unused_node):
    # Type parameter adjustment should happen after all external types have
    # been resolved, since TypeVar instances can be imported.
    raise ValueError(
        "Tried to adjust type parameters before converting to class types")


class InsertSignatureTemplates(Visitor):
  """Visitor for inserting function templates."""

  def __init__(self):
    super(InsertSignatureTemplates, self).__init__()
    self.bound_typeparams = set()
    self.template_typeparams = None

  def EnterClass(self, node):
    for t in node.template:
      assert isinstance(t.type_param, pytd.TypeParameter)
      if t.name in self.bound_typeparams:
        raise ContainerError(
            "Duplicate type parameter %s in class %s" % (t.name, node.name))
      self.bound_typeparams.add(t.name)

  def LeaveClass(self, node):
    for t in node.template:
      self.bound_typeparams.remove(t.name)

  def EnterSignature(self, unused_node):
    assert self.template_typeparams is None
    self.template_typeparams = set()

  def LeaveSignature(self, unused_node):
    self.template_typeparams = None

  def VisitTypeParameter(self, node):
    if (self.template_typeparams is not None and
        node.name not in self.bound_typeparams):
      self.template_typeparams.add(pytd.TemplateItem(node))
    return node

  def VisitSignature(self, node):
    return node.Replace(template=tuple(self.template_typeparams))


class AddTypeParameterScopes(Visitor):
  """Visitor for scoping type parameters."""

  def __init__(self):
    super(AddTypeParameterScopes, self).__init__()
    self.class_name = None
    self.function_name = None
    self.constant_name = None
    self.bound_by_class = ()

  def EnterClass(self, node):
    self.class_name = node.name
    self.bound_by_class = {n.type_param.name for n in node.template}

  def LeaveClass(self, unused_node):
    self.class_name = None
    self.bound_by_class = ()

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
    if name in self.bound_by_class:
      return self.class_name
    return self._GetFullName(self.function_name)

  def VisitTypeParameter(self, node):
    if self.constant_name and (not self.class_name or
                               node.name not in self.bound_by_class):
      raise ContainerError("Unbound type parameter %s in %s" % (
          node.name, self._GetFullName(self.constant_name)))
    scope = self._GetScope(node.name)
    if scope:
      return node.Replace(scope=scope)
    else:
      # This is a top-level type parameter (TypeDeclUnit.type_params).
      # AddNamePrefix gave it the right scope, so leave it alone.
      return node


def AdjustTypeParameters(ast):
  ast = ast.Visit(InsertClassTemplates())
  ast = ast.Visit(InsertSignatureTemplates())
  ast = ast.Visit(AddTypeParameterScopes())
  return ast


class VerifyContainers(Visitor):
  """Visitor for verifying containers.

  Every container (except typing.Generic) must inherit from typing.Generic and
  have an explicitly parameterized parent that is also a container. The
  parameters on typing.Generic must all be TypeVar instances.

  Raises:
    ContainerError: If a problematic container definition is encountered.
  """

  def _IsContainer(self, t):
    if t.name == "typing.Generic":
      return True
    for p in t.parents:
      if isinstance(p, pytd.GenericType):
        base = p.base_type
        if isinstance(base, pytd.ClassType) and self._IsContainer(base.cls):
          return True
    return False

  def EnterGenericType(self, node):
    if not self._IsContainer(node.base_type.cls):
      raise ContainerError("Class %s is not a container" % node.base_type.name)
    elif node.base_type.name == "typing.Generic":
      for t in node.parameters:
        if not isinstance(t, pytd.TypeParameter):
          raise ContainerError("Name %s must be defined as a TypeVar" % t.name)

  def EnterHomogeneousContainerType(self, node):
    self.EnterGenericType(node)


class ExpandCompatibleBuiltins(Visitor):
  """Ad-hoc inheritance.

  In parameters, replaces
    ClassType('__builtin__.float')
  with
    Union[ClassType('__builtin__.float'), ClassType('__builtin__.int')]

  And similarly for unicode->(unicode, str, bytes) and bool->(bool, None).

  Used to allow a function requiring a float to accept an int without making
  int inherit from float.

  See https://www.python.org/dev/peps/pep-0484/#the-numeric-tower
  """

  def __init__(self, builtins):
    super(ExpandCompatibleBuiltins, self).__init__()
    self.in_parameter = False
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
        ((v, v) for v in set(pep484.COMPAT_MAP.values())),
        pep484.COMPAT_MAP.iteritems())

    for compat, name in compat_list:
      prefix = builtins.name + "."
      full_name = prefix + compat
      t = builtins.Lookup(full_name)
      if isinstance(t, pytd.Class):
        # Depending on python version, bytes can be an Alias, if so don't
        # want it in our union
        rmap[prefix + name].append(pytd.ClassType(full_name, t))

    return {k: pytd.UnionType(tuple(v))
            for k, v in rmap.iteritems()}

  def EnterParameter(self, _):
    assert not self.in_parameter
    self.in_parameter = True

  def LeaveParameter(self, _):
    assert self.in_parameter
    self.in_parameter = False

  def VisitClassType(self, node):
    if self.in_parameter:
      return self.replacements.get(node.name, node)
    else:
      return node
