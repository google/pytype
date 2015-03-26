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

# pylint: disable=g-importing-member

import collections
import re


from pytype.pytd import pytd


class PrintVisitor(object):
  """Visitor for converting ASTs back to pytd source code."""
  implements_all_node_types = True

  INDENT = " " * 4
  _VALID_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

  def __init__(self):
    self.class_names = []  # allow nested classes

  def _SafeName(self, name):
    if not self._VALID_NAME.match(name):
      # We can do this because name will never contain backticks. Everything
      # we process here came in through the pytd parser, and the pytd syntax
      # doesn't allow escaping backticks themselves.
      return r"`" + name + r"`"
    else:
      return name

  def VisitTypeDeclUnit(self, node):
    """Convert the AST for an entire module back to a string."""
    sections = [node.constants, node.functions,
                node.classes, node.modules]
    sections_as_string = ("\n".join(section_suite)
                          for section_suite in sections
                          if section_suite)
    return "\n\n".join(sections_as_string)

  def VisitConstant(self, node):
    """Convert a class-level or module-level constant to a string."""
    return self._SafeName(node.name) + ": " + node.type

  def EnterClass(self, node):
    """Entering a class - record class name for children's use."""
    n = self._SafeName(node.name)
    if node.template:
      n += "<{}>".format(
          ", ".join(t.Visit(PrintVisitor()) for t in node.template))
    self.class_names.append(n)

  def LeaveClass(self, unused_node):
    self.class_names.pop()

  def VisitClass(self, node):
    """Visit a class, producing a multi-line, properly indented string."""
    if node.parents == ("object",):
      parents = ""  # object is the default superclass
    elif node.parents:
      parents = "(" + ", ".join(node.parents) + ")"
    else:
      parents = "(nothing)"
    template = "<" + ", ".join(node.template) + ">" if node.template else ""
    header = "class " + self._SafeName(node.name) + template + parents + ":"
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

  def VisitFunctionWithSignatures(self, node):
    """Visit function, producing multi-line string (one for each signature)."""
    function_name = self._SafeName(node.name)
    return "\n".join("def " + function_name + sig for sig in node.signatures)

  def VisitFunctionWithCode(self, node):
    """Visit function defined with PYTHONCODE."""
    return "def " + self._SafeName(node.name) + " PYTHONCODE"

  def VisitSignature(self, node):
    """Visit a signature, producing a string."""
    template = "<" + ", ".join(node.template) + ">" if node.template else ""

    # TODO(pludemann): might want special handling for __init__(...) -> NoneType
    # Design decision: we used to allow the return type to default to "?"  (see
    # comments in parser.py for the "return" rule) but that led to confusion, so
    # we now require all function signatures to have a return type.
    ret = " -> " + node.return_type

    exc = " raises " + ", ".join(node.exceptions) if node.exceptions else ""
    optional = ("...",) if node.has_optional else ()

    # pylint: disable=no-member
    #     (old_node is set in parse/node.py)
    mutable_params = [(p.name, p.new_type) for p in self.old_node.params
                      if isinstance(p, pytd.MutableParameter)]
    # pylint: enable=no-member
    if mutable_params:
      body = ":\n" + "\n".join("{indent}{name} := {new_type}".format(
          indent=self.INDENT, name=name,
          new_type=new_type.Visit(PrintVisitor()))
                               for name, new_type in mutable_params)
    else:
      body = ""

    return "{template}({params}){ret}{exc}{body}".format(
        template=template, params=", ".join(node.params + optional),
        ret=ret, exc=exc, body=body)

  def VisitParameter(self, node):
    """Convert a function parameter to a string."""
    if node.type == "object":
      # Abbreviated form. "object" is the default.
      return node.name
    elif node.name == "self" and self.class_names and (
        node.type == self.class_names[-1]):
      return self._SafeName(node.name)
    else:
      return self._SafeName(node.name) + ": " + node.type

  def VisitMutableParameter(self, node):
    """Convert a mutable function parameter to a string."""
    return self.VisitParameter(node)

  def VisitTemplateItem(self, node):
    """Convert a template to a string."""
    return node.type_param

  def VisitNamedType(self, node):
    """Convert a type to a string."""
    return self._SafeName(node.name)

  def VisitNativeType(self, node):
    """Convert a native type to a string."""
    return self._SafeName(node.python_type.__name__)

  def VisitAnythingType(self, unused_node):
    """Convert an anything type to a string."""
    return "?"

  def VisitNothingType(self, unused_node):
    """Convert the nothing type to a string."""
    return "nothing"

  def VisitClassType(self, node):
    return self._SafeName(node.name)

  def VisitTypeParameter(self, node):
    return self._SafeName(node.name)

  def VisitHomogeneousContainerType(self, node):
    """Convert a homogeneous container type to a string."""
    return node.base_type + "<" + node.element_type + ">"

  def VisitGenericType(self, node):
    """Convert a generic type (E.g. list<int>) to a string."""
    # The syntax for a parameterized type with one parameter is "X<T,>"
    # (E.g. "tuple<int,>")
    param_str = node.parameters[0] + ", " + ", ".join(node.parameters[1:])
    return node.base_type + "<" + param_str + ">"

  def VisitUnionType(self, node):
    """Convert a union type ("x or y") to a string."""
    # TODO(kramm): insert parentheses if necessary (i.e., if the parent is
    # an intersection.)
    return " or ".join(node.type_list)

  def VisitIntersectionType(self, node):
    """Convert an intersection type ("x and y") to a string."""
    return " and ".join(node.type_list)


class StripSelf(object):
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


class _FillInClasses(object):
  """Fill in ClassType pointers using a symbol table.

  This is an in-place visitor! It modifies the original tree. This is
  necessary because we introduce loops.
  """

  def __init__(self, local_lookup, global_lookup):
    """Create this visitor.

    You're expected to then pass this instance to node.Visit().

    Args:
      local_lookup: Usually, the local module. Tried first when looking up
        names.
      global_lookup: Global symbols. Tried if a name doesn't exist locally.
    """
    self._local_lookup = local_lookup
    self._global_lookup = global_lookup

  def VisitClassType(self, node):
    """Fills in a class type.

    Args:
      node: A ClassType. This node will have a name, which we use for lookup.

    Returns:
      The same ClassType. We will have filled in its "cls" attribute.

    Raises:
      KeyError: If we can't find a given class.
    """
    if node.cls is None:
      try:
        node.cls = self._local_lookup.Lookup(node.name)
      except KeyError:
        try:  # TODO(pludemann): Remove this try/pass
          node.cls = (self._global_lookup.Lookup and
                      self._global_lookup.Lookup(node.name))
        except KeyError:
          if self._global_lookup.Lookup:
            pass  # TODO(pludemann): Shouldn't be needed
          else:
            raise
    return node


class ClearClassTypePointers(object):
  """For ClassType nodes: Set their cls pointer to None."""

  def EnterClassType(self, node):
    node.cls = None


class NamedTypeToClassType(object):
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


class ClassTypeToNamedType(object):
  """Change all ClassType objects to NameType objects.
  """

  def VisitClassType(self, node):
    """Converts a class type to a named type.

    Args:
      node: The ClassType.

    Returns:
      A NamedType.
    """
    return pytd.NamedType(node.name)


def FillInClasses(target, global_module=None):
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

  if hasattr(target, "modules"):
    for submodule in target.modules:
      FillInClasses(submodule, global_module)

  # Fill in classes for this module, bottom up.
  # TODO(kramm): Node.Visit() should support blacklisting of attributes so
  # we don't recurse into submodules multiple times.
  if isinstance(target, pytd.TypeDeclUnit):
    target.Visit(_FillInClasses(target, global_module))
  else:
    target.Visit(_FillInClasses(global_module, global_module))


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
    # Set cls pointers to None so that FillInClasses is allowed to set them.
    module = module.Visit(ClearClassTypePointers())
  FillInClasses(module, global_module)
  module.Visit(VerifyLookup())
  return module


class VerifyLookup(object):
  """Utility class for testing visitors.LookupClasses."""

  def VisitNamedType(self, node):
    raise ValueError("Unreplaced NamedType: %r" % node.name)

  def VisitClassType(self, node):
    # TODO(pludemann): Can we give more context for this error? It's not very
    #                  useful when it says that "T" is unresolved (e.g., from
    #                  "def foo(x: list<T>))" ... it would be nice to know what
    #                  it's inside.
    if node.cls is None:
      raise ValueError("Unresolved class: %r" % node.name)


class ReplaceTypes(object):
  """Visitor for replacing types in a tree.

  This replaces both NamedType and ClassType nodes that have a name in the
  mapping. The two cases are not distinguished.
  """

  def __init__(self, mapping):
    self.mapping = mapping

  def VisitNamedType(self, node):
    return self.mapping.get(node.name, node)

  def VisitClassType(self, node):
    return self.mapping.get(node.name, node)

  # We do *not* want to have 'def VisitClass' because that will replace a class
  # definition with itself, which is almost certainly not what is wanted,
  # because runing pytd.Print on it will result in output that's just a list of
  # class names with no contents.


class ExtractSuperClassesByName(object):
  """Visitor for extracting all superclasses (i.e., the class hierarchy).

  This returns a mapping by name, e.g. {
    "bool": ["int"],
    "int": ["object"],
    ...
  }.
  """

  def VisitTypeDeclUnit(self, module):
    result = {base_class: superclasses
              for base_class, superclasses in module.classes}
    for submodule in module.modules:
      # pylint: disable=no-member
      result.update(
          {self.old_node.name + "." + name: superclasses
           for name, superclasses in submodule.items()})
    return result

  def VisitClass(self, cls):
    return (cls.name, [parent.name for parent in cls.parents])


class ExtractSuperClasses(object):
  """Visitor for extracting all superclasses (i.e., the class hierarchy).

  When called on a TypeDeclUnit, this yields a dictionary mapping pytd.Class
  to lists of pytd.TYPE.
  """

  def VisitTypeDeclUnit(self, module):
    # TODO(kramm): This uses the entire class node as a key, instead of just
    # its id.
    result = {base_class: superclasses
              for base_class, superclasses in module.classes}
    for submodule in module.modules:
      result.update({cls: superclasses
                     for cls, superclasses in submodule.items()})
    return result

  def VisitNamedType(self, _):
    raise AssertionError(
        "This visitor needs a resolved AST. Call LookupClasses() before.")

  def VisitClass(self, cls):
    return (cls, cls.parents)


class ReplaceTypeParameters(object):
  """Visitor for replacing type parameters with actual types."""

  def __init__(self, mapping):
    self.mapping = mapping

  def VisitTypeParameter(self, p):
    return self.mapping[p]


class InstantiateTemplatesVisitor(object):
  """Tries to remove templates by instantiating the corresponding types.

  It will create classes that are named "base_type<element_type>", so e.g.
  a list of integers will literally be named "list<int>".

  Attributes:
    symbol_table: Symbol table for looking up templated classes.
  """

  def __init__(self):
    self.classes_to_instantiate = collections.OrderedDict()

  def _InstantiatedClass(self, name, node, symbol_table):
    cls = symbol_table.Lookup(node.base_type.name)
    mapping = {t.type_param: e for t, e in zip(cls.template, node.parameters)}
    return cls.Replace(name=name, template=()).Visit(
        ReplaceTypeParameters(mapping))

  def InstantiatedClasses(self, symbol_table):
    return [self._InstantiatedClass(name, node, symbol_table)
            for name, node in self.classes_to_instantiate.items()]

  def VisitHomogeneousContainerType(self, node):
    """Converts a template type (container type) to a concrete class.

    This works by looking up the actual Class (using the lookup table passed
    when initializing the visitor) and substituting the parameters of the
    template everywhere in its definition. The new class is appended to the
    list of classes of this module. (Later on, the template we used is removed.)

    Args:
      node: An instance of HomogeneousContainerType

    Returns:
      A new NamedType pointing to an instantiation of the class.
    """
    name = pytd.Print(node)
    if name not in self.classes_to_instantiate:
      self.classes_to_instantiate[name] = node
    return pytd.NamedType(name)

  def VisitGenericType(self, node):
    """Converts a parameter-based template type (e.g. dict<str,int>) to a class.

    This works by looking up the actual Class (using the lookup table passed
    when initializing the visitor) and substituting the parameters of the
    template everywhere in its definition. The new class is appended to the
    list of classes of this module. (Later on, also all templates are removed.)

    Args:
      node: An instance of GenericType.

    Returns:
      A new NamedType pointing to an instantiation of the class.
    """
    name = pytd.Print(node)
    if name not in self.classes_to_instantiate:
      self.classes_to_instantiate[name] = node
    return pytd.NamedType(name)


def InstantiateTemplates(node):
  """Adds the instantiated classes to the module. Removes templates.

  This will add the instantiated classes to the module the original was
  defined in.

  Args:
    node: Module to process. The elements of this module will already be
      processed once this method is called.

  Returns:
    A module that contains extra classes for all the templated classes
    we encountered within this module.
  """
  v = InstantiateTemplatesVisitor()
  node = node.Visit(v)
  old_classes = [c for c in node.classes if not c.template]
  new_classes = v.InstantiatedClasses(node)
  return node.Replace(classes=old_classes + new_classes)


def ClassAsType(cls):
  """Converts a pytd.Class to an instance of pytd.Type."""
  params = tuple(item.type_param for item in cls.template)
  if not params:
    return pytd.NamedType(cls.name)
  elif len(params) == 1:
    return pytd.HomogeneousContainerType(pytd.NamedType(cls.name),
                                         params)
  else:  # len(cls.template) >= 2
    return pytd.GenericType(pytd.NamedType(cls.name), params)


class AdjustSelf(object):
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

  def __init__(self, replace_unknown=False, force=False):
    self.class_types = []  # allow nested classes
    self.force = force
    self.replaced_self_types = (pytd.NamedType("object"),
                                pytd.ClassType("object"))
    if replace_unknown:
      self.replaced_self_types += (pytd.AnythingType(),)

  def EnterClass(self, cls):
    self.class_types.append(ClassAsType(cls))

  def LeaveClass(self, unused_node):
    self.class_types.pop()

  def VisitClass(self, node):
    return node

  def VisitMutableParameter(self, p):
    p2 = self.VisitParameter(p)
    # pylint: disable=maybe-no-member
    return pytd.MutableParameter(p2.name, p2.type, p.new_type)

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
      return pytd.Parameter("self", self.class_types[-1])
    else:
      return p


class RemoveUnknownClasses(object):
  """Visitor for converting ClassTypes called ~unknown* to just AnythingType.

  For example, this will change
    def f() -> ~unknown1
    class ~unknown1:
      ...
  to
    def f() -> ?
  """

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

  def VisitClass(self, cls):
    if cls.name.startswith("~unknown"):
      return None
    return cls

  def VisitTypeDeclUnit(self, u):
    return u.Replace(classes=tuple(cls for cls in u.classes if cls is not None))


# TODO(kramm): The `~unknown` functionality is becoming more important. Should
#              we have support for this on the pytd level? (That would mean
#              changing Class.name to a TYPE). Also, should we just use ~X
#              instead of ~unknownX?
class RaiseIfContainsUnknown(object):
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


class VerifyVisitor(object):
  """Visitor for verifying pytd ASTs. For tests."""

  implements_all_node_types = True

  def EnterTypeDeclUnit(self, node):
    assert isinstance(node.constants, (list, tuple)), node
    assert all(isinstance(c, pytd.Constant) for c in node.constants)
    assert isinstance(node.functions, (list, tuple)), node
    assert all(isinstance(f, pytd.FUNCTION) for f in node.functions)
    assert isinstance(node.classes, (list, tuple)), node
    assert all(isinstance(cls, pytd.Class) for cls in node.classes)
    assert isinstance(node.modules, (list, tuple)), node
    assert all(isinstance(m, pytd.TypeDeclUnit) for m in node.modules)

  def EnterConstant(self, node):
    assert isinstance(node.name, str), node
    assert isinstance(node.type, pytd.TYPE), node

  def EnterClass(self, node):
    assert isinstance(node.parents, tuple), node
    assert all(isinstance(p, pytd.TYPE) for p in node.parents)
    assert isinstance(node.methods, tuple), node
    assert all(isinstance(f, pytd.FUNCTION) for f in node.methods)
    assert isinstance(node.constants, tuple), node
    assert all(isinstance(c, pytd.Constant) for c in node.constants)
    assert isinstance(node.template, tuple), node
    assert all(isinstance(t, pytd.TemplateItem) for t in node.template)

  def EnterFunctionWithSignatures(self, node):
    assert isinstance(node.name, str), node
    assert node.signatures, node
    assert isinstance(node.signatures, tuple), node
    assert all(isinstance(sig, pytd.Signature) for sig in node.signatures)

  def EnterFunctionWithCode(self, node):
    assert isinstance(node.name, str), node
    # TODO(pludemann): implement FunctionWithCode.code
    assert node.code is None, node

  def EnterSignature(self, node):
    assert isinstance(node.params, tuple), node
    assert all(isinstance(p, (pytd.Parameter, pytd.MutableParameter))
               for p in node.params)
    assert isinstance(node.return_type, pytd.TYPE), node
    assert isinstance(node.exceptions, tuple), node
    assert all(isinstance(e, pytd.TYPE) for e in node.exceptions)
    assert isinstance(node.template, tuple), node
    assert all(isinstance(t, pytd.TemplateItem) for t in node.template)
    assert isinstance(node.has_optional, bool), node

  def EnterParameter(self, node):
    assert isinstance(node.name, str), node
    assert isinstance(node.type, pytd.TYPE), node

  def EnterMutableParameter(self, node):
    assert isinstance(node.name, str), node
    assert isinstance(node.type, pytd.TYPE), node
    assert isinstance(node.new_type, pytd.TYPE), node

  def EnterTemplateItem(self, node):
    assert isinstance(node.type_param, pytd.TypeParameter), node

  def EnterNamedType(self, node):
    assert isinstance(node.name, str), node

  def EnterNativeType(self, node):
    assert isinstance(node.python_type, type), node

  def EnterAnythingType(self, unused_node):
    pass

  def EnterNothingType(self, unused_node):
    pass

  def EnterClassType(self, node):
    assert isinstance(node.name, str), node

  def EnterTypeParameter(self, node):
    assert isinstance(node.name, str), node

  def EnterHomogeneousContainerType(self, node):
    assert isinstance(node.base_type, pytd.TYPE), node
    assert isinstance(node.parameters, tuple), node
    assert len(node.parameters) == 1, node
    assert all(isinstance(p, pytd.TYPE) for p in node.parameters), node

  def EnterGenericType(self, node):
    assert isinstance(node.base_type, pytd.TYPE), node
    assert isinstance(node.parameters, tuple), node
    assert all(isinstance(p, pytd.TYPE) for p in node.parameters), node

  def EnterUnionType(self, node):
    assert isinstance(node.type_list, tuple), node
    assert all(isinstance(t, pytd.TYPE) for t in node.type_list), node

  def EnterIntersectionType(self, node):
    assert isinstance(node.type_list, tuple), node
    assert all(isinstance(t, pytd.TYPE) for t in node.type_list), node

  def EnterScalar(self, node):
    pass


class CanonicalOrderingVisitor(object):
  """Visitor for converting ASTs back to canonical (sorted) ordering.
  """

  def __init__(self, sort_signatures=False):
    self.sort_signatures = sort_signatures

  # TODO(pludemann): might want to add __new__ defns to the various types here
  #                  to ensure the args are tuple, and can then remove the
  #                  tuple(...) wrappers here ...

  def VisitTypeDeclUnit(self, node):
    return pytd.TypeDeclUnit(name=node.name,
                             constants=tuple(sorted(node.constants)),
                             functions=tuple(sorted(node.functions)),
                             classes=tuple(sorted(node.classes)),
                             modules=tuple(sorted(node.modules)))

  def VisitClass(self, node):
    return pytd.Class(name=node.name,
                      parents=node.parents,
                      methods=tuple(sorted(node.methods)),
                      constants=tuple(sorted(node.constants)),
                      template=node.template)

  def VisitFunctionWithSignatures(self, node):
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

  def VisitIntersectionType(self, node):
    return pytd.IntersectionType(tuple(sorted(node.type_list)))


class PythonTypeNameVisitor(object):
  """A name that Python's type(...).__name__ would return (for testing)."""

  def VisitNamedType(self, t):
    return t.name

  def VisitNativeType(self, t):
    return t.python_type.__name__

  def VisitClassType(self, t):
    return t.name

  def VisitGenericType(self, t):
    return t.base_type

  def VisitHomogeneousContainerType(self, t):
    return t.base_type


class RemoveFunctionsAndClasses(object):
  """Visitor for removing unwanted functions or classes."""

  def __init__(self, names):
    self.names = names

  def VisitTypeDeclUnit(self, node):
    return node.Replace(functions=tuple(f for f in node.functions
                                        if f.name not in self.names),
                        classes=tuple(c for c in node.classes
                                      if c.name not in self.names))
