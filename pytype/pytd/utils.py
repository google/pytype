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
"""Utilities for pytd.

This provides a utility function to access data files in a way that works either
locally or within a larger repository.
"""

# len(x) == 0 is clearer in some places:
# pylint: disable=g-explicit-length-test

import collections
import itertools
import os

from pytype.pyi import parser
from pytype.pytd import abc_hierarchy
from pytype.pytd import pytd
from pytype.pytd.parse import visitors
import pytype.utils


def UnpackUnion(t):
  """Return the type list for union type, or a list with the type itself."""
  if isinstance(t, pytd.UnionType):
    return t.type_list
  else:
    return [t]


def MakeClassOrContainerType(base_type, type_arguments, homogeneous):
  """If we have type params, build a generic type, a normal type otherwise."""
  if homogeneous:
    assert len(type_arguments) == 1
    return pytd.HomogeneousContainerType(base_type, tuple(type_arguments))
  elif base_type.name in ("__builtin__.tuple", "typing.Tuple"):
    return pytd.TupleType(base_type, tuple(type_arguments))
  elif not type_arguments:
    return base_type
  else:
    return pytd.GenericType(base_type, tuple(type_arguments))


def Concat(*args, **kwargs):
  """Concatenate two or more pytd ASTs."""
  assert all(isinstance(arg, pytd.TypeDeclUnit) for arg in args)
  name = kwargs.get("name")
  return pytd.TypeDeclUnit(
      name=name or " + ".join(arg.name for arg in args),
      constants=sum((arg.constants for arg in args), ()),
      type_params=sum((arg.type_params for arg in args), ()),
      classes=sum((arg.classes for arg in args), ()),
      functions=sum((arg.functions for arg in args), ()),
      aliases=sum((arg.aliases for arg in args), ()))


def JoinTypes(types):
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


# pylint: disable=invalid-name
def prevent_direct_instantiation(cls, *args, **kwargs):
  """Mix-in method for creating abstract (base) classes.

  Use it like this to prevent instantiation of classes:

    class Foo(object):
      __new__ = prevent_direct_instantiation

  This will apply to the class itself, not its subclasses, so it can be used to
  create base classes that are abstract, but will become concrete once inherited
  from.

  Arguments:
    cls: The class to instantiate, passed to __new__.
    *args: Additional arguments, passed to __new__.
    **kwargs: Additional keyword arguments, passed to __new__.
  Returns:
    A new instance.
  Raises:
    AssertionError: If something tried to instantiate the base class.
  """
  new = cls.__dict__.get("__new__")
  if getattr(new, "__func__", None) == prevent_direct_instantiation:
    raise AssertionError("Can't instantiate %s directly" % cls.__name__)
  return object.__new__(cls, *args, **kwargs)


def disabled_function(*unused_args, **unused_kwargs):
  """Disable a function.

  Disable a previously defined function foo as follows:

    foo = disabled_function

  Any later calls to foo will raise an AssertionError.  This is used, e.g.,
  in cfg.Program to prevent the addition of more nodes after we have begun
  solving the graph.

  Raises:
    AssertionError: If something tried to call the disabled function.
  """

  raise AssertionError("Cannot call disabled function.")


class TypeMatcher(object):
  """Base class for modules that match types against each other.

  Maps pytd node types (<type1>, <type2>) to a method "match_<type1>_<type2>".
  So e.g. to write a matcher that compares Functions by name, you would write:

    class MyMatcher(TypeMatcher):

      def match_Function_Function(self, f1, f2):
        return f1.name == f2.name
  """

  def default_match(self, t1, t2):
    return t1 == t2

  def match(self, t1, t2, *args, **kwargs):
    name1 = t1.__class__.__name__
    name2 = t2.__class__.__name__
    f = getattr(self, "match_" + name1 + "_against_" + name2, None)
    if f:
      return f(t1, t2, *args, **kwargs)
    else:
      return self.default_match(t1, t2, *args, **kwargs)


def CanonicalOrdering(n, sort_signatures=False):
  """Convert a PYTD node to a canonical (sorted) ordering."""
  # TODO(pludemann): use the original .py to decide the ordering rather
  #                  than an arbitrary sort order
  return n.Visit(
      visitors.CanonicalOrderingVisitor(sort_signatures=sort_signatures))


def GetAllSubClasses(ast):
  """Compute a class->subclasses mapping.

  Args:
    ast: Parsed PYTD.

  Returns:
    A dictionary, mapping instances of pytd.TYPE (types) to lists of
    pytd.Class (the derived classes).
  """
  hierarchy = ast.Visit(visitors.ExtractSuperClasses())
  hierarchy = {cls: [superclass for superclass in superclasses]
               for cls, superclasses in hierarchy.items()}
  return abc_hierarchy.Invert(hierarchy)


def Print(ast):
  return ast.Visit(visitors.PrintVisitor())


def EmptyModule(name="<empty>"):
  return pytd.TypeDeclUnit(
      name, type_params=(), constants=(), classes=(), functions=(), aliases=())


def WrapTypeDeclUnit(name, items):
  """Given a list (classes, functions, etc.), wrap a pytd around them.

  Args:
    name: The name attribute of the resulting TypeDeclUnit.
    items: A list of items. Can contain pytd.Class, pytd.Function and
      pytd.Constant.
  Returns:
    A pytd.TypeDeclUnit.
  Raises:
    ValueError: In case of an invalid item in the list.
    NameError: For name conflicts.
  """

  functions = collections.OrderedDict()
  classes = collections.OrderedDict()
  constants = collections.defaultdict(TypeBuilder)
  aliases = collections.OrderedDict()
  typevars = collections.OrderedDict()
  for item in items:
    if isinstance(item, pytd.Function):
      if item.name in functions:
        if item.kind != functions[item.name].kind:
          raise ValueError("Can't combine %s and %s", item.kind,
                           functions[item.name].kind)
        functions[item.name] = pytd.Function(
            item.name, functions[item.name].signatures + item.signatures,
            item.kind)
      else:
        functions[item.name] = item
    elif isinstance(item, pytd.Class):
      if item.name in classes:
        raise NameError("Duplicate top level class: %r", item.name)
      classes[item.name] = item
    elif isinstance(item, pytd.Constant):
      constants[item.name].add_type(item.type)
    elif isinstance(item, pytd.Alias):
      if item.name in aliases:
        raise NameError("Duplicate top level alias or import: %r", item.name)
      aliases[item.name] = item
    elif isinstance(item, pytd.TypeParameter):
      if item.name in typevars:
        raise NameError("Duplicate top level type parameter: %r", item.name)
      typevars[item.name] = item
    else:
      raise ValueError("Invalid top level pytd item: %r" % type(item))

  categories = {"function": functions, "class": classes, "constant": constants,
                "alias": aliases, "typevar": typevars}
  for c1, c2 in itertools.combinations(categories, 2):
    _check_intersection(categories[c1], categories[c2], c1, c2)

  return pytd.TypeDeclUnit(
      name=name,
      constants=tuple(
          pytd.Constant(name, t.build())
          for name, t in sorted(constants.items())),
      type_params=tuple(typevars.values()),
      classes=tuple(classes.values()),
      functions=tuple(functions.values()),
      aliases=tuple(aliases.values()))


def _check_intersection(items1, items2, name1, name2):
  items = set(items1) & set(items2)
  if items:
    if len(items) == 1:
      raise NameError("Top level identifier %r is both %s and %s" %
                      (list(items)[0], name1, name2))
    max_items = 5  # an arbitrary value
    if len(items) > max_items:
      raise NameError("Top level identifiers %s, ... are both %s and %s" %
                      (", ".join(map(repr, sorted(items[:max_items]))), name1,
                       name2))
    raise NameError("Top level identifiers %s are both %s and %s" %
                    (", ".join(map(repr, sorted(items))), name1, name2))


class TypeBuilder(object):
  """Utility class for building union types."""

  def __init__(self):
    self.union = pytd.NothingType()

  def add_type(self, other):
    """Add a new pytd type to the types represented by this TypeBuilder."""
    self.union = JoinTypes([self.union, other])

  def build(self):
    """Get a union of all the types added so far."""
    return self.union

  def __nonzero__(self):
    return not isinstance(self.union, pytd.NothingType)


def NamedOrClassType(name, cls):
  """Create Classtype / NamedType."""
  if cls is None:
    return pytd.NamedType(name)
  else:
    return pytd.ClassType(name, cls)


def NamedTypeWithModule(name, module=None):
  """Create NamedType, dotted if we have a module."""
  if module is None:
    return pytd.NamedType(name)
  else:
    return pytd.NamedType(module + "." + name)


class OrderedSet(collections.OrderedDict):
  """A simple ordered set."""

  def __init__(self, iterable=None):
    super(OrderedSet, self).__init__((item, None) for item in (iterable or []))

  def add(self, item):
    self[item] = None


def WrapsDict(member_name, writable=False, implement_len=False):
  """Returns a mixin class for wrapping a dictionary.

  This can be used like this:
    class MyClass(WrapsDict("inner_dict")):
      def __init__(self):
        self.inner_dict = {}
  The resulting class will delegate all dictionary operations to inner_dict.

  Args:
    member_name: Name of the attribute that contains the wrapped dictionary.
    writable: Whether to implement operations that modify the dict, like "del".
    implement_len: Whether the parent class should have a __len__ method that
      maps to the inner dictionary.
  Returns:
    A type.
  """
  src = "if True:\n"  # To allow the code below to be indented
  src += """
    class WrapsDict(object):

      def __getitem__(self, key):
        return self.{member_name}[key]

      def get(self, key, default=None):
        return self.{member_name}.get(key, default)

      def __contains__(self, key):
        return key in self.{member_name}

      def has_key(self, key):
        return self.{member_name}.has_key(key)

      def copy(self):
        return self.{member_name}.copy()

      def __iter__(self):
        return iter(self.{member_name})

      def items(self):
        return self.{member_name}.items()

      def iteritems(self):
        return self.{member_name}.iteritems()

      def iterkeys(self):
        return self.{member_name}.iterkeys()

      def itervalues(self):
        return self.{member_name}.itervalues()

      def keys(self):
        return self.{member_name}.keys()

      def values(self):
        return self.{member_name}.values()

      def viewitems(self):
        return self.{member_name}.viewitems()

      def viewkeys(self):
        return self.{member_name}.viewkeys()

      def viewvalues(self):
        return self.{member_name}.viewvalues()
  """.format(member_name=member_name)

  if writable:
    src += """
      def pop(self, key):
        return self.{member_name}.pop(key)

      def popitem(self):
        return self.{member_name}.popitem()

      def setdefault(self, key, value=None):
        return self.{member_name}.setdefault(key, value)

      def update(self, other_dict):
        return self.{member_name}.update(other_dict)

      def clear(self):
        return self.{member_name}.clear()

      def __setitem__(self, key, value):
        self.{member_name}[key] = value

      def __delitem__(self, key):
        del self.{member_name}[key]
    """.format(member_name=member_name)

  if implement_len:
    src += """
      def __len__(self):
        return len(self.{member_name})
    """.format(member_name=member_name)

  namespace = {}
  exec src in namespace  # pylint: disable=exec-used
  return namespace["WrapsDict"]


def Dedup(seq):
  """Return a sequence in the same order, but with duplicates removed."""
  seen = set()
  result = []
  for s in seq:
    if s not in seen:
      result.append(s)
    seen.add(s)
  return result


class MROError(Exception):

  def __init__(self, seqs):
    super(MROError, self).__init__()
    self.mro_seqs = seqs


def MROMerge(input_seqs):
  """Merge a sequence of MROs into a single resulting MRO.

  Args:
    input_seqs: A sequence of MRO sequences.

  Returns:
    A single resulting MRO.

  Raises:
    MROError: If we discovered an illegal inheritance.
  """
  seqs = [Dedup(s) for s in input_seqs]
  try:
    return visitors.MergeSequences(seqs)
  except ValueError:
    raise MROError(input_seqs)


def _GetClass(t, lookup_ast):
  if t.cls:
    return t.cls
  if lookup_ast:
    return lookup_ast.Lookup(t.name)
  raise AttributeError("Class not found: %s" % t.name)


def _Degenerify(types):
  return [t.base_type if isinstance(t, pytd.GenericType) else t for t in types]


def _ComputeMRO(t, mros, lookup_ast):
  if isinstance(t, pytd.ClassType):
    if t not in mros:
      mros[t] = None
      parent_mros = []
      for parent in _GetClass(t, lookup_ast).parents:
        if parent in mros:
          if mros[parent] is None:
            raise MROError([[t]])
          else:
            parent_mro = mros[parent]
        else:
          parent_mro = _ComputeMRO(parent, mros, lookup_ast)
        parent_mros.append(parent_mro)
      mros[t] = tuple(
          MROMerge([[t]] + parent_mros + [_Degenerify(
              _GetClass(t, lookup_ast).parents)]))
    return mros[t]
  elif isinstance(t, pytd.GenericType):
    return _ComputeMRO(t.base_type, mros, lookup_ast)
  else:
    return [t]


def GetBasesInMRO(cls, lookup_ast=None):
  """Get the given class's bases in Python's method resolution order."""
  mros = {}
  parent_mros = []
  for p in cls.parents:
    parent_mros.append(_ComputeMRO(p, mros, lookup_ast))
  return tuple(MROMerge(parent_mros + [_Degenerify(cls.parents)]))


def canonical_pyi(pyi):
  ast = parser.parse_string(pyi)
  ast = ast.Visit(visitors.ClassTypeToNamedType())
  ast = ast.Visit(visitors.CanonicalOrderingVisitor(sort_signatures=True))
  ast.Visit(visitors.VerifyVisitor())
  return pytd.Print(ast)


def GetPredefinedFile(pytd_subdir, module, extension=".pytd"):
  """Get the contents of a predefined PyTD, typically with a file name *.pytd.

  Arguments:
    pytd_subdir: the directory, typically "builtins" or "stdlib"
    module: module name (e.g., "sys" or "__builtins__")
    extension: either ".pytd" or ".py"
  Returns:
    The contents of the file
  Raises:
    IOError: if file not found
  """
  path = os.path.join("pytd", pytd_subdir,
                      os.path.join(*module.split(".")) + extension)
  return pytype.utils.load_pytype_file(path)
