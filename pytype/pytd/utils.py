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

import collections
import os


from pytype.pytd import abc_hierarchy
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd.parse import visitors


def GetDataFile(filename=""):
    full_filename = os.path.abspath(
        os.path.join(os.path.dirname(pytd.__file__), filename))
    with open(full_filename, "rb") as fi:
      return fi.read()


def UnpackUnion(t):
  """Return the type list for union type, or a list with the type itself."""
  if isinstance(t, pytd.UnionType):
    return t.type_list
  else:
    return [t]


def Concat(pytd1, pytd2):
  """Concatenate two pytd ASTs."""
  assert isinstance(pytd1, pytd.TypeDeclUnit)
  assert isinstance(pytd2, pytd.TypeDeclUnit)
  return pytd.TypeDeclUnit(name=pytd1.name + " + " + pytd2.name,
                           constants=pytd1.constants + pytd2.constants,
                           classes=pytd1.classes + pytd2.classes,
                           functions=pytd1.functions + pytd2.functions,
                           modules=pytd1.modules + pytd2.modules)


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


class TypeMatcher(object):
  """Base class for modules that match types against each other.

  Maps pytd node types (<type1>, <type2>) to a method "match_<type1>_<type2>".
  So e.g. to write a matcher that compares Functions by name, you would write:

    class MyMatcher(TypeMatcher):

      def match_FunctionWithSignatures_FunctionWithSignatures(self, f1, f2):
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


def CanonicalOrdering(n):
  """Convert a PYTD node to a canonical (sorted) ordering."""
  # TODO(pludemann): use the original .py to decide the ordering rather
  #                  than an arbitrary sort order
  return n.Visit(visitors.CanonicalOrderingVisitor())


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
