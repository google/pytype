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
import os

from pytype.pytd import abc_hierarchy
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd.parse import builtins
from pytype.pytd.parse import parser
from pytype.pytd.parse import visitors


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
  full_filename = os.path.abspath(
      os.path.join(os.path.dirname(pytd.__file__),
                   pytd_subdir, module + extension))
  with open(full_filename, "rb") as fi:
    return fi.read()


def UnpackUnion(t):
  """Return the type list for union type, or a list with the type itself."""
  if isinstance(t, pytd.UnionType):
    return t.type_list
  else:
    return [t]


def MakeClassOrContainerType(base_type, type_arguments):
  """If we have type params, build a generic type, a normal type otherwise."""
  if len(type_arguments) == 0:
    return base_type
  elif len(type_arguments) == 1:
    return pytd.HomogeneousContainerType(base_type, tuple(type_arguments))
  else:
    return pytd.GenericType(base_type, tuple(type_arguments))


def Concat(*args, **kwargs):
  """Concatenate two or more pytd ASTs."""
  assert all(isinstance(arg, pytd.TypeDeclUnit) for arg in args)
  name = kwargs.get("name")
  return pytd.TypeDeclUnit(
      name=name or " + ".join(arg.name for arg in args),
      constants=sum((arg.constants for arg in args), ()),
      classes=sum((arg.classes for arg in args), ()),
      functions=sum((arg.functions for arg in args), ()))


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
    f = getattr(self, "match_" + name1 + "_against_" + name2,
                None)
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


# TODO(kramm): Move to transforms.py.
def RemoveMutableParameters(ast):
  """Change all mutable parameters in a pytd AST to a non-mutable form."""
  # transforms
  #   class list<T>:
  #     def append<T2>(self, v: T2) -> NoneType:
  #       self := T or T2
  # to
  #   class list<T'>:
  #     def append<T'>(self, V:T') -> NoneType
  # by creating a *new* template variable T' that propagates the
  # mutations to the outermost level (in this example, T' = T or T2)

  # late import, because optimize uses utils.py.
  from pytype.pytd import optimize  # pylint: disable=g-import-not-at-top
  ast = ast.Visit(optimize.AbsorbMutableParameters())
  ast = ast.Visit(optimize.CombineContainers())
  ast = ast.Visit(optimize.MergeTypeParameters())
  ast = ast.Visit(visitors.AdjustSelf(force=True))
  return ast


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


OUTPUT_FORMATS = {
    "pytd", "pep484stub"
}


def Print(ast, print_format=None):
  if print_format and print_format not in OUTPUT_FORMATS:
    raise ValueError("Invalid format %s" % print_format)
  if print_format == "pytd" or print_format is None:
    res = ast.Visit(visitors.PrintVisitor())
  elif print_format == "pep484stub":
    res = ast.Visit(pep484.Print484StubVisitor())
  return res


def EmptyModule(name="<empty>"):
  return pytd.TypeDeclUnit(name, constants=(), classes=(), functions=())


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
  for item in items:
    if isinstance(item, pytd.Function):
      if item.name in functions:
        functions[item.name] = pytd.Function(
            item.name,
            functions[item.name].signatures + item.signatures)
      else:
        functions[item.name] = item
    elif isinstance(item, pytd.Class):
      if item.name in classes:
        raise NameError("Duplicate top level class: %r", item.name)
      classes[item.name] = item
    elif isinstance(item, pytd.Constant):
      constants[item.name].add_type(item.type)
    else:
      raise ValueError("Invalid top level pytd item: %r" % type(item))

  _check_intersection(functions, classes, "function", "class")
  _check_intersection(classes, constants, "class", "constant")
  _check_intersection(functions, constants, "functions", "class")
  return pytd.TypeDeclUnit(
      name,
      tuple(pytd.Constant(name, t.build())
            for name, t in sorted(constants.items())),
      tuple(classes.values()),
      tuple(functions.values()))


def _check_intersection(items1, items2, name1, name2):
  items = set(items1) & set(items2)
  if items:
    if len(items) == 1:
      raise NameError("Top level identifier %r is both %s and %s" % (
          list(items)[0], name1, name2))
    max_items = 5  # an arbitrary value
    if len(items) > max_items:
      raise NameError("Top level identifiers %s, ... are both %s and %s" % (
          ", ".join(map(repr, sorted(items[:max_items]))), name1, name2))
    raise NameError("Top level identifiers %s are both %s and %s" % (
        ", ".join(map(repr, sorted(items))), name1, name2))


def ParsePyTD(src=None, filename=None, python_version=None, module=None):
  """Parse pytd sourcecode and do name lookup for builtins.

  This loads a pytd and also makes sure that all names are resolved (i.e.,
  that all primitive types in the AST are ClassType, and not NameType).

  Args:
    src: PyTD source code.
    filename: The filename the source code is from.
    python_version: The Python version to parse the pytd for.
    module: The name of the module we're parsing.

  Returns:
    A pytd.TypeDeclUnit.
  """
  assert python_version
  if src is None:
    with open(filename, "rb") as fi:
      src = fi.read()
  ast = parser.parse_string(src, filename=filename, name=module,
                            python_version=python_version)
  if module is not None:  # Allow "" as module name
    ast = ast.Visit(visitors.AddNamePrefix(ast.name + "."))
  ast = visitors.LookupClasses(ast, builtins.GetBuiltinsPyTD())
  return ast


def ParsePredefinedPyTD(pytd_subdir, module, python_version):
  """Load and parse a *.pytd from "pytd/{pytd_subdir}/{module}.pytd".

  Args:
    pytd_subdir: the directory where the module should be found
    module: the module name (without any file extension)
    python_version: sys.version_info[:2]

  Returns:
    The AST of the module; None if the module doesn't exist in pytd_subdir.
  """
  try:
    src = GetPredefinedFile(pytd_subdir, module)
  except IOError:
    return None
  return ParsePyTD(src, filename=os.path.join(pytd_subdir, module + ".pytd"),
                   module=module,
                   python_version=python_version).Replace(name=module)


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


def ExternalOrNamedOrClassType(name, cls):
  """Create Classtype / NamedType / ExternalType."""
  if "." in name:
    module, name = name.rsplit(".", 1)
    return pytd.ExternalType(name, module, cls)
  elif cls is None:
    return pytd.NamedType(name)
  else:
    return pytd.ClassType(name, cls)


def NamedOrExternalType(name, module=None):
  """Create NamedType / ExternalType, depending on whether we have a module."""
  if module is None:
    return pytd.NamedType(name)
  else:
    return pytd.ExternalType(name, module)


class OrderedSet(collections.OrderedDict):
  """A simple ordered set."""

  def __init__(self, iterable=None):
    super(OrderedSet, self).__init__((item, None) for item in (iterable or []))

  def add(self, item):
    self[item] = None
