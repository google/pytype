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
import difflib
import gzip
import itertools
import os
import pickletools
import re
import sys

from pytype import pytype_source_utils
from pytype import utils
from pytype.pytd import pytd
from pytype.pytd import pytd_visitors
import six
from six.moves import cPickle


_PICKLE_PROTOCOL = cPickle.HIGHEST_PROTOCOL
_PICKLE_RECURSION_LIMIT_AST = 40000


ANON_PARAM = re.compile(r"_[0-9]+")


def UnpackUnion(t):
  """Return the type list for union type, or a list with the type itself."""
  if isinstance(t, pytd.UnionType):
    return t.type_list
  else:
    return [t]


def MakeClassOrContainerType(base_type, type_arguments, homogeneous):
  """If we have type params, build a generic type, a normal type otherwise."""
  if not type_arguments:
    return base_type
  if homogeneous:
    container_type = pytd.GenericType
  elif base_type.name == "typing.Callable":
    container_type = pytd.CallableType
  elif base_type.name in ("__builtin__.tuple", "typing.Tuple"):
    container_type = pytd.TupleType
  else:
    container_type = pytd.GenericType
  return container_type(base_type, tuple(type_arguments))


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
  return n.Visit(
      pytd_visitors.CanonicalOrderingVisitor(sort_signatures=sort_signatures))


def GetAllSubClasses(ast):
  """Compute a class->subclasses mapping.

  Args:
    ast: Parsed PYTD.

  Returns:
    A dictionary, mapping instances of pytd.Type (types) to lists of
    pytd.Class (the derived classes).
  """
  hierarchy = ast.Visit(pytd_visitors.ExtractSuperClasses())
  hierarchy = {cls: list(superclasses)
               for cls, superclasses in hierarchy.items()}
  return utils.invert_dict(hierarchy)


def Print(ast, multiline_args=False):
  return ast.Visit(pytd_visitors.PrintVisitor(multiline_args))


def CreateModule(name="<empty>", **kwargs):
  module = pytd.TypeDeclUnit(
      name, type_params=(), constants=(), classes=(), functions=(), aliases=())
  return module.Replace(**kwargs)


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
          raise ValueError("Can't combine %s and %s" % (
              item.kind, functions[item.name].kind))
        functions[item.name] = pytd.Function(
            item.name, functions[item.name].signatures + item.signatures,
            item.kind)
      else:
        functions[item.name] = item
    elif isinstance(item, pytd.Class):
      if item.name in classes:
        raise NameError("Duplicate top level class: %r" % item.name)
      classes[item.name] = item
    elif isinstance(item, pytd.Constant):
      constants[item.name].add_type(item.type)
    elif isinstance(item, pytd.Alias):
      if item.name in aliases:
        raise NameError("Duplicate top level alias or import: %r" % item.name)
      aliases[item.name] = item
    elif isinstance(item, pytd.TypeParameter):
      if item.name in typevars:
        raise NameError("Duplicate top level type parameter: %r" % item.name)
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
  """Check for duplicate identifiers."""
  items = set(items1) & set(items2)
  if items:
    if len(items) == 1:
      raise NameError("Top level identifier %r is both %s and %s" %
                      (list(items)[0], name1, name2))
    max_items = 5  # an arbitrary value
    if len(items) > max_items:
      raise NameError("Top level identifiers %s, ... are both %s and %s" %
                      ", ".join(map(repr, sorted(items)[:max_items])),
                      name1, name2)
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

  def __bool__(self):
    return not isinstance(self.union, pytd.NothingType)

  # For running under Python 2
  __nonzero__ = __bool__


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
  Note that we don't wrap has_key, which was removed in Python 3.

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

      def copy(self):
        return self.{member_name}.copy()

      def __iter__(self):
        return iter(self.{member_name})

      def items(self):
        return self.{member_name}.items()

      def iteritems(self):
        return six.iteritems(self.{member_name})

      def iterkeys(self):
        return six.iterkeys(self.{member_name})

      def itervalues(self):
        return six.itervalues(self.{member_name})

      def keys(self):
        return self.{member_name}.keys()

      def values(self):
        return self.{member_name}.values()

      def viewitems(self):
        return six.viewitems(self.{member_name})

      def viewkeys(self):
        return six.viewkeys(self.{member_name})

      def viewvalues(self):
        return six.viewvalues(self.{member_name})
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

  namespace = {"six": six}
  exec(src, namespace)  # pylint: disable=exec-used
  return namespace["WrapsDict"]  # pytype: disable=key-error


def GetPredefinedFile(pytd_subdir, module, extension=".pytd",
                      as_package=False):
  """Get the contents of a predefined PyTD, typically with a file name *.pytd.

  Arguments:
    pytd_subdir: the directory, typically "builtins" or "stdlib"
    module: module name (e.g., "sys" or "__builtins__")
    extension: either ".pytd" or ".py"
    as_package: try the module as a directory with an __init__ file
  Returns:
    The contents of the file
  Raises:
    IOError: if file not found
  """
  parts = module.split(".")
  if as_package:
    parts.append("__init__")
  mod_path = os.path.join(*parts) + extension
  path = os.path.join("pytd", pytd_subdir, mod_path)
  return path, pytype_source_utils.load_pytype_file(path)


def LoadPickle(filename, compress=False):
  if compress:
    with gzip.GzipFile(filename, "rb") as fi:
      # TODO(b/117797409): Remove the disable once the typeshed bug is fixed.
      return cPickle.load(fi)  # pytype: disable=wrong-arg-types
  else:
    with open(filename, "rb") as fi:
      return cPickle.load(fi)


def SavePickle(data, filename=None, compress=False):
  """Pickle the data."""
  recursion_limit = sys.getrecursionlimit()
  sys.setrecursionlimit(_PICKLE_RECURSION_LIMIT_AST)
  assert not compress or filename, "gzip only supported with a filename"
  try:
    if compress:
      with open(filename, mode="wb") as fi:
        # We blank the filename and set the mtime explicitly to produce
        # deterministic gzip files.
        with gzip.GzipFile(filename="", mode="wb",
                           fileobj=fi, mtime=1.0) as zfi:
          # TODO(b/117797409): Remove disable once typeshed bug is fixed.
          cPickle.dump(data, zfi, _PICKLE_PROTOCOL)  # pytype: disable=wrong-arg-types
    elif filename is not None:
      with open(filename, "wb") as fi:
        cPickle.dump(data, fi, _PICKLE_PROTOCOL)
    else:
      return cPickle.dumps(data, _PICKLE_PROTOCOL)
  finally:
    sys.setrecursionlimit(recursion_limit)


def ASTeq(ast1, ast2):
  return (ast1.constants == ast2.constants and
          ast1.type_params == ast2.type_params and
          ast1.classes == ast2.classes and
          ast1.functions == ast2.functions and
          ast1.aliases == ast2.aliases)


def ASTdiff(ast1, ast2):
  return difflib.ndiff(Print(ast1).splitlines(), Print(ast2).splitlines())


def DiffNamedPickles(named_pickles1, named_pickles2):
  """Diff two lists of (name, pickled_module)."""
  len1, len2 = len(named_pickles1), len(named_pickles2)
  if len1 != len2:
    return ["different number of pyi files: %d, %d" % (len1, len2)]
  diff = []
  for (name1, pickle1), (name2, pickle2) in zip(named_pickles1, named_pickles2):
    if name1 != name2:
      diff.append("different ordering of pyi files: %s, %s" % (name1, name2))
    elif pickle1 != pickle2:
      ast1, ast2 = cPickle.loads(pickle1), cPickle.loads(pickle2)
      if ASTeq(ast1.ast, ast2.ast):
        diff.append("asts match but pickles differ: %s" % name1)
        p1 = six.StringIO()
        p2 = six.StringIO()
        pickletools.dis(pickle1, out=p1)
        pickletools.dis(pickle2, out=p2)
        diff.extend(difflib.unified_diff(
            p1.getvalue().splitlines(),
            p2.getvalue().splitlines()))
      else:
        diff.append("asts differ: %s" % name1)
        diff.append("-" * 50)
        diff.extend(ASTdiff(ast1.ast, ast2.ast))
        diff.append("-" * 50)
  return diff


def GetTypeParameters(node):
  collector = pytd_visitors.CollectTypeParameters()
  node.Visit(collector)
  return collector.params


def DummyMethod(name, *params):
  """Create a simple method using only "Any"s as types.

  Arguments:
    name: The name of the method
    *params: The parameter names.
  Returns:
    A pytd.Function.
  """
  def make_param(param):
    return pytd.Parameter(param, type=pytd.AnythingType(), kwonly=False,
                          optional=False, mutated_type=None)
  sig = pytd.Signature(tuple(make_param(param) for param in params),
                       starargs=None, starstarargs=None,
                       return_type=pytd.AnythingType(),
                       exceptions=(), template=())
  return pytd.Function(name=name,
                       signatures=(sig,),
                       kind=pytd.METHOD,
                       flags=0)


def MergeBaseClass(cls, base):
  """Merge a base class into a subclass.

  Arguments:
    cls: The subclass to merge values into. pytd.Class.
    base: The superclass whose values will be merged. pytd.Class.

  Returns:
    a pytd.Class of the two merged classes.
  """
  bases = tuple(b for b in cls.parents if b != base)
  bases += tuple(b for b in base.parents if b not in bases)
  method_names = [m.name for m in cls.methods]
  methods = cls.methods + tuple(m for m in base.methods
                                if m.name not in method_names)
  constant_names = [c.name for c in cls.constants]
  constants = cls.constants + tuple(c for c in base.constants
                                    if c.name not in constant_names)
  class_names = [c.name for c in cls.classes]
  classes = cls.classes + tuple(c for c in base.classes
                                if c.name not in class_names)
  if cls.slots:
    slots = cls.clots + tuple(s for s in base.slots or () if s not in cls.slots)
  else:
    slots = base.slots
  return pytd.Class(name=cls.name,
                    metaclass=cls.metaclass or base.metaclass,
                    parents=bases,
                    methods=methods,
                    constants=constants,
                    classes=classes,
                    slots=slots,
                    template=cls.template or base.template)
