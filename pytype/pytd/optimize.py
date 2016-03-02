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


"""Functions for optimizing pytd syntax trees.

   pytd files come from various sources, and are typically redundant (duplicate
   functions, different signatures saying the same thing, overlong type
   disjunctions). The Visitors in this file remove various forms of these
   redundancies.
"""

import collections
import logging

from pytype.pytd import abc_hierarchy
from pytype.pytd import booleq
from pytype.pytd import pytd
from pytype.pytd import utils
from pytype.pytd.parse import builtins
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)


class RenameUnknowns(visitors.Visitor):
  """Give unknowns that map to the same set of concrete types the same name."""

  def __init__(self, mapping):
    super(RenameUnknowns, self).__init__()
    self.name_to_cls = {name: hash(cls) for name, cls in mapping.items()}
    self.cls_to_canonical_name = {
        cls: name for name, cls in self.name_to_cls.items()}

  def VisitClassType(self, node):
    if node.name.startswith("~unknown"):
      return pytd.ClassType(
          self.cls_to_canonical_name[self.name_to_cls[node.name]], None)
    else:
      return node


class RemoveDuplicates(visitors.Visitor):
  """Remove duplicate function signatures.

  For example, this transforms
    def f(x: int) -> float
    def f(x: int) -> float
  to
    def f(x: int) -> float
  In order to be removed, a signature has to be exactly identical to an
  existing one.
  """

  def VisitFunction(self, node):
    # We remove duplicates, but keep existing entries in the same order.
    return node.Replace(signatures=tuple(utils.OrderedSet(node.signatures)))


class RemoveRedundantSignatures(visitors.Visitor):
  """Remove duplicate function signatures.

  For example, this transforms
    def f(x: int) -> float
    def f(x: int or float) -> float
  to
    def f(x: int or float) -> float
  In order to be removed, a signature has to be "contained" (a subclass of)
  an existing one.
  """

  def __init__(self, hierarchy):
    super(RemoveRedundantSignatures, self).__init__()
    # TODO(kramm): fix circular import
    from pytype.pytd import type_match  # pylint: disable=g-import-not-at-top
    self.match = type_match.TypeMatch(hierarchy.GetSuperClasses())

  def VisitFunction(self, node):
    new_signatures = []
    # We keep track of which signature matched which other signatures, purely
    # for optimization - that way we don't have to query the reverse direction.
    matches = set()
    for i, s1 in enumerate(node.signatures):
      for j, s2 in enumerate(node.signatures):
        if (i != j and (j, i) not in matches
            and not s1.exceptions and not s2.exceptions
            and self.match.match(s1, s2, {}) == booleq.TRUE):
          matches.add((i, j))
          break
      else:
        new_signatures.append(s1)
    return node.Replace(signatures=tuple(new_signatures))


class SimplifyUnions(visitors.Visitor):
  """Remove duplicate or redundant entries in union types.

  For example, this transforms
    a: int or int
    b: int or ?
    c: int or (int or float)
  to
    a: int
    b: ?
    c: int or float
  """

  def VisitUnionType(self, union):
    return utils.JoinTypes(union.type_list)


class _ReturnsAndExceptions(object):
  """Mutable class for collecting return types and exceptions of functions.

  The collecting is stable: Items are kept in the order in which they were
  encountered.

  Attributes:
    return_types: Return types seen so far.
    exceptions: Exceptions seen so far.
  """

  def __init__(self):
    self.return_types = []
    self.exceptions = []

  def Update(self, signature):
    """Add the return types / exceptions of a signature to this instance."""

    if signature.return_type not in self.return_types:
      self.return_types.append(signature.return_type)

    self.exceptions.extend(exception
                           for exception in signature.exceptions
                           if exception not in self.exceptions)


class CombineReturnsAndExceptions(visitors.Visitor):
  """Group function signatures that only differ in exceptions or return values.

  For example, this transforms
    def f(x: int) -> float raises OverflowError
    def f(x: int) -> int raises IndexError
  to
    def f(x: int) -> float or int raises IndexError, OverflowError
  """

  def _GroupByArguments(self, signatures):
    """Groups signatures by arguments.

    Arguments:
      signatures: A list of function signatures (Signature instances).

    Returns:
      A dictionary mapping signatures (without return and exceptions) to
      a tuple of return values and exceptions.
    """
    groups = collections.OrderedDict()  # Signature -> ReturnsAndExceptions
    for sig in signatures:
      stripped_signature = sig.Replace(return_type=None, exceptions=None)

      ret = groups.get(stripped_signature)
      if not ret:
        ret = _ReturnsAndExceptions()
        groups[stripped_signature] = ret

      ret.Update(sig)

    return groups

  def VisitFunction(self, f):
    """Merge signatures of a function.

    This groups signatures by arguments and then for each group creates a
    single signature that joins the return values / exceptions using "or".

    Arguments:
      f: A pytd.Function instance

    Returns:
      Function with simplified / combined signatures.
    """
    groups = self._GroupByArguments(f.signatures)

    new_signatures = []
    for stripped_signature, ret_exc in groups.items():
      ret = utils.JoinTypes(ret_exc.return_types)
      exc = tuple(ret_exc.exceptions)

      new_signatures.append(
          stripped_signature.Replace(return_type=ret, exceptions=exc)
      )
    return f.Replace(signatures=tuple(new_signatures))


class CombineContainers(visitors.Visitor):
  """Change unions of containers to containers of unions.

  For example, this transforms
    list[int] or list[float]
  to
    list[int or float]
  .
  """

  def VisitUnionType(self, union):
    """Push unions down into containers.

    This collects similar container types in unions and merges them into
    single instances with the union type pushed down to the element_type level.

    Arguments:
      union: A pytd.Union instance. Might appear in a parameter, a return type,
        a constant type, etc.

    Returns:
      A simplified pytd.Union.
    """
    if not any(isinstance(t, pytd.GenericType) for t in union.type_list):
      # Optimization: If we're not going to change anything, return original.
      return union
    union = utils.JoinTypes(union.type_list)  # flatten
    if not isinstance(union, pytd.UnionType):
      union = pytd.UnionType((union,))
    collect = {}
    has_redundant_base_types = False
    for t in union.type_list:
      if isinstance(t, pytd.GenericType):
        if t.base_type in collect:
          has_redundant_base_types = True
          collect[t.base_type] = tuple(
              utils.JoinTypes([p1, p2])
              for p1, p2 in zip(collect[t.base_type], t.parameters))
        else:
          collect[t.base_type] = t.parameters
    if not has_redundant_base_types:
      return union
    result = pytd.NothingType()
    done = set()
    for t in union.type_list:
      if isinstance(t, pytd.GenericType):
        if t.base_type in done:
          continue  # already added
        parameters = collect[t.base_type]
        add = t.Replace(parameters=tuple(p.Visit(CombineContainers())
                                         for p in parameters))
        done.add(t.base_type)
      else:
        add = t
      result = utils.JoinTypes([result, add])
    return result


class Factorize(visitors.Visitor):
  """Opposite of ExpandSignatures. Factorizes cartesian products of functions.

  For example, this transforms
    def f(x: int, y: int)
    def f(x: int, y: float)
    def f(x: float, y: int)
    def f(x: float, y: float)
  to
    def f(x: int or float, y: int or float)
  """

  def _GroupByOmittedArg(self, signatures, i):
    """Group functions that are identical if you ignore one of the arguments.

    Arguments:
      signatures: A list of function signatures
      i: The index of the argument to ignore during comparison.

    Returns:
      A list of tuples (signature, types). "signature" is a signature with
      argument i omitted, "types" is the list of types that argument was
      found to have. signatures that don't have argument i are represented
      as (original, None).
    """
    groups = collections.OrderedDict()
    for sig in signatures:
      if i >= len(sig.params):
        # We can't omit argument i, because this signature has too few
        # arguments. Represent this signature as (original, None).
        groups[sig] = None
        continue
      if isinstance(sig.params[i], pytd.MutableParameter):
        # We can't group mutable parameters. Leave this signature alone.
        groups[sig] = None
        continue

      # Set type of parameter i to None
      params = list(sig.params)
      param_i = params[i]
      params[i] = pytd.Parameter(param_i.name, None)

      stripped_signature = sig.Replace(params=tuple(params))
      existing = groups.get(stripped_signature)
      if existing:
        existing.append(param_i.type)
      else:
        groups[stripped_signature] = [param_i.type]
    return groups.items()

  def VisitFunction(self, f):
    """Shrink a function, by factorizing cartesian products of arguments.

    Greedily groups signatures, looking at the arguments from left to right.
    This algorithm is *not* optimal. But it does the right thing for the
    typical cases.

    Arguments:
      f: An instance of pytd.Function. If this function has more
          than one signature, we will try to combine some of these signatures by
          introducing union types.

    Returns:
      A new, potentially optimized, instance of pytd.Function.

    """
    max_argument_count = max(len(s.params) for s in f.signatures)
    signatures = f.signatures

    for i in xrange(max_argument_count):
      new_sigs = []
      for sig, types in self._GroupByOmittedArg(signatures, i):
        if types:
          # One or more options for argument <i>:
          new_params = list(sig.params)
          new_params[i] = pytd.Parameter(sig.params[i].name,
                                         utils.JoinTypes(types))
          sig = sig.Replace(params=tuple(new_params))
          new_sigs.append(sig)
        else:
          # Signature doesn't have argument <i>, so we store the original:
          new_sigs.append(sig)
      signatures = new_sigs

    return f.Replace(signatures=tuple(signatures))


class ApplyOptionalArguments(visitors.Visitor):
  """Removes functions that are instances of a more specific case.

  For example, this reduces
    def f(x: int, ...)    # [1]
    def f(x: int, y: int) # [2]
  to just
    def f(x: int, ...)

  Because "..." makes it possible to pass any additional arguments to [1],
  it encompasses both declarations, hence we can omit [2].
  """

  def _HasShorterVersion(self, sig, optional_arg_sigs):
    """Find a shorter signature with optional arguments for a longer signature.

    Arguments:
      sig: The function signature we'd like to shorten
      optional_arg_sigs: A set of function signatures with optional arguments
        that will be matched against sig.

    Returns:
      True if there is a shorter signature that generalizes sig, but is not
          identical to sig.
    """

    param_count = len(sig.params)

    if not sig.has_optional:
      param_count += 1  # also consider f(x, y, ...) for f(x, y)

    for i in xrange(param_count):
      shortened = sig.Replace(params=sig.params[0:i], has_optional=True)
      if shortened in optional_arg_sigs:
        return True
    return False

  def VisitFunction(self, f):
    """Remove all signatures that have a shorter version.

    We use signatures with optional argument (has_opt=True) as template
    and then match all signatures against those templates, removing those
    that match.

    Arguments:
      f: An instance of pytd.Function

    Returns:
      A potentially simplified instance of pytd.Function.
    """

    # Set of signatures that can replace longer ones. Only used for matching,
    # hence we can use an unordered data structure.
    optional_arg_sigs = frozenset(s for s in f.signatures if s.has_optional)

    new_signatures = (s for s in f.signatures
                      if not self._HasShorterVersion(s, optional_arg_sigs))
    return f.Replace(signatures=tuple(new_signatures))


class SuperClassHierarchy(object):
  """Utility class for optimizations working with superclasses."""

  def __init__(self, superclasses):
    self._superclasses = superclasses
    self._subclasses = abc_hierarchy.Invert(self._superclasses)

  def GetSuperClasses(self):
    return self._superclasses

  def _CollectSuperclasses(self, type_name, collect):
    """Recursively collect super classes for a type.

    Arguments:
      type_name: A string, the type's name.
      collect: A set() of strings, modified to contain all superclasses.
    """
    collect.add(type_name)
    superclasses = [name
                    for name in self._superclasses.get(type_name, [])]

    # The superclasses might have superclasses of their own, so recurse.
    for superclass in superclasses:
      self._CollectSuperclasses(superclass, collect)

  def ExpandSuperClasses(self, t):
    """Generate a list of all (known) superclasses for a type.

    Arguments:
      t: A type name. E.g. "int".

    Returns:
      A set of types. This set includes t as well as all its superclasses. For
      example, this will return "bool", "int" and "object" for "bool".
    """
    superclasses = set()
    self._CollectSuperclasses(t, superclasses)
    return superclasses

  def ExpandSubClasses(self, t):
    """Generate a set of all (known) subclasses for a type.

    Arguments:
      t: A type. E.g. NamedType("int").

    Returns:
      A set of types. This set includes t as well as all its subclasses. For
      example, this will return "int" and "bool" for "int".
    """
    queue = [t]
    seen = set()
    while queue:
      item = queue.pop()
      if item not in seen:
        seen.add(item)
        queue.extend(self._subclasses[item])
    return seen

  def HasSubClassInSet(self, cls, known):
    """Queries whether a subclass of a type is present in a given set."""
    return any(sub in known
               for sub in self._subclasses[cls])

  def HasSuperClassInSet(self, cls, known):
    """Queries whether a superclass of a type is present in a given set."""
    return any(sub in known
               for sub in self._superclasses[cls])


class SimplifyUnionsWithSuperclasses(visitors.Visitor):
  """Simplify Unions with superclasses.

  E.g., this changes
    int or bool
  to
    int
  since bool is a subclass of int.

  (Interpreting types as "sets of values", this simplification is sound since
   A union B = A, if B is a subset of A.)
  """

  def __init__(self, hierarchy):
    super(SimplifyUnionsWithSuperclasses, self).__init__()
    self.hierarchy = hierarchy

  def VisitUnionType(self, union):
    c = collections.Counter()
    for t in set(union.type_list):
      if isinstance(t, pytd.GENERIC_BASE_TYPE):
        c += collections.Counter(self.hierarchy.ExpandSubClasses(str(t)))
        # TODO(kramm): Handle GenericType et al

    # Below, c[str[t]] can be zero - that's the default for non-existent items
    # in collections.Counter. It'll happen for types that are not
    # instances of GENERIC_BASE_TYPE, like container types.
    new_type_list = [t for t in union.type_list
                     if c[str(t)] <= 1
                    ]
    return utils.JoinTypes(new_type_list)


class FindCommonSuperClasses(visitors.Visitor):
  """Find common super classes. Optionally also uses abstract base classes.

  E.g., this changes
    def f(x: list or tuple, y: frozenset or set) -> int or float
  to
    def f(x: Sequence, y: Set) -> Real
  """

  def __init__(self, hierarchy):
    super(FindCommonSuperClasses, self).__init__()
    self.hierarchy = hierarchy

  def VisitUnionType(self, union):
    """Given a union type, try to find a simplification by using superclasses.

    This is a lossy optimization that tries to map a list of types to a common
    base type. For example, int and bool are both base classes of int, so it
    would convert "int or bool" to "int".

    Arguments:
      union: A union type.

    Returns:
      A simplified type, if available.
    """
    intersection = self.hierarchy.ExpandSuperClasses(str(union.type_list[0]))

    for t in union.type_list[1:]:
      intersection.intersection_update(
          self.hierarchy.ExpandSuperClasses(str(t)))

    # Remove "redundant" superclasses, by removing everything from the tree
    # that's not a leaf. I.e., we don't need "object" if we have more
    # specialized types.
    new_type_list = tuple(
        cls for cls in intersection
        if not self.hierarchy.HasSubClassInSet(cls, intersection))

    return utils.JoinTypes(new_type_list)


class CollapseLongUnions(visitors.Visitor):
  """Shortens long unions to object (or "?").

  Poor man's version of FindCommonSuperClasses. Shorten types like
  "str or unicode or int or float or list" to just "object" or "?".

  Additionally, if the union already contains at least one "object", we also
  potentially replace the entire union with just "object".

  Attributes:
    max_length: The maximum number of types to allow in a union. If there are
      more types than this, it is shortened.
    generic_type: What type to treat as the generic "object" type.
  """

  def __init__(self, max_length=7, generic_type=None):
    assert isinstance(max_length, (int, long))
    super(CollapseLongUnions, self).__init__()
    if generic_type is None:
      self.generic_type = pytd.NamedType("object")
    else:
      self.generic_type = generic_type
    self.max_length = max_length

  def VisitUnionType(self, union):
    if len(union.type_list) > self.max_length:
      return self.generic_type
    elif self.generic_type in union.type_list:
      return self.generic_type
    else:
      return union


class CollapseLongParameterUnions(visitors.Visitor):
  """Shortens long unions in parameters to object.

  This is a lossy optimization that changes overlong disjunctions in arguments
  to just "object".
  Some signature extractions generate signatures like
    class str:
      def __init__(self, obj: str or unicode or int or float or list)
  We shorten that to
    class str:
      def __init__(self, obj: object)
  In other words, if there are too many types "or"ed together, we just replace
  the entire thing with "object".

  Attributes:
    max_length: The maximum number of types to allow in a parameter. See
      CollapseLongUnions.
  """

  def __init__(self, max_length=7):
    super(CollapseLongParameterUnions, self).__init__()
    self.max_length = max_length

  def VisitParameter(self, param):
    return param.Visit(CollapseLongUnions(self.max_length))

  def VisitOptionalParameter(self, param):
    return param.Visit(CollapseLongUnions(self.max_length))

  def VisitMutableParameter(self, param):
    return param.Visit(CollapseLongUnions(self.max_length))


class CollapseLongReturnUnions(visitors.Visitor):
  """Shortens long unions in return types to ?.

  This is a lossy optimization that changes overlong disjunctions in returns
  to just "object".
  Some signature extractions generate signatures like
    class str:
      def __init__(self) -> str or unicode or int or float or list
  We shorten that to
    class str:
      def __init__(self) -> ?
  In other words, if there are too many types "or"ed together, we just replace
  the entire thing with "?" (AnythingType).

  Attributes:
    max_length: The maximum number of types to allow in a return type. See
      CollapseLongUnions.
  """

  def __init__(self, max_length=7):
    super(CollapseLongReturnUnions, self).__init__()
    self.max_length = max_length

  def VisitSignature(self, sig):
    return sig.Replace(return_type=sig.return_type.Visit(
        CollapseLongUnions(self.max_length, pytd.AnythingType())))


class CollapseLongConstantUnions(visitors.Visitor):
  """Shortens long unions in constants to ?.

  This is a lossy optimization that changes overlong constants to "?".
  So
    class str:
      x: str or unicode or int or float or list
  would be shortened to
    class str:
      x: ?

  Attributes:
    max_length: The maximum number of types to allow in a constant. See
      CollapseLongUnions.
  """

  def __init__(self, max_length=7):
    super(CollapseLongConstantUnions, self).__init__()
    self.max_length = max_length

  def VisitConstant(self, c):
    return c.Replace(type=c.type.Visit(
        CollapseLongUnions(self.max_length, pytd.AnythingType())))


class AddInheritedMethods(visitors.Visitor):
  """Copy methods and constants from base classes into their derived classes.

  E.g. this changes
      class Bar:
        [methods and constants of Bar]
      class Foo(Bar):
        [methods and constants of Foo]
  to
      class Bar:
        [methods and constants of Bar]
      class Foo(Bar):
        [methods and constants of Bar]
        [methods and constants of Foo]
  .
  This is not an optimization by itself, but it can help with other
  optimizations (like signature merging), and is also useful as preprocessor
  for type matching.
  """

  def VisitClass(self, cls):
    """Add superclass methods and constants to this Class."""
    if any(base for base in cls.parents if isinstance(base, pytd.NamedType)):
      raise AssertionError("AddInheritedMethods needs a resolved AST")
    # Filter out only the types we can reason about.
    # TODO(kramm): Do we want handle UnionTypes and GenericTypes at some point?
    bases = [base.cls
             for base in cls.parents
             if isinstance(base, pytd.ClassType)]
    # Don't pull in methods that are named the same as existing methods in
    # this class, local methods override parent class methods.
    names = {m.name for m in cls.methods} | {c.name for c in cls.constants}
    # TODO(kramm): This should do full-blown MRO.
    new_methods = cls.methods + tuple(
        m for base in bases for m in base.methods
        if m.name not in names)
    new_constants = cls.constants + tuple(
        c for base in bases for c in base.constants
        if c.name not in names)
    cls = cls.Replace(methods=new_methods, constants=new_constants)
    return cls.Visit(visitors.AdjustSelf(force=True))


class RemoveInheritedMethods(visitors.Visitor):
  """Removes methods from classes if they also exist in their superclass.

  E.g. this changes
        class A:
            def f(self, y: int) -> bool
        class B(A):
            def f(self, y: int) -> bool
  to
        class A:
            def f(self, y: int) -> bool
        class B(A):
            pass
  .
  """

  def __init__(self):
    super(RemoveInheritedMethods, self).__init__()
    self.class_to_stripped_signatures = {}
    self.function = None
    self.class_stack = []

  def EnterClass(self, cls):
    self.class_stack.append(cls)

  def LeaveClass(self, _):
    self.class_stack.pop()

  def EnterFunction(self, function):
    self.function = function

  def LeaveFunction(self, _):
    self.function = None

  def _StrippedSignatures(self, t):
    """Given a class, list method name + signature without "self".

    Args:
      t: A pytd.TYPE.

    Returns:
      A set of name + signature tuples, with the self parameter of the
      signature removed.
    """
    if not isinstance(t, pytd.ClassType):
      # For union types, generic types etc., inheritance is more complicated.
      # Be conservative and default to not removing methods inherited from
      # those.
      return frozenset()

    stripped_signatures = set()
    for method in t.cls.methods:
      for sig in method.signatures:
        if (sig.params and
            sig.params[0].name == "self" and
            isinstance(sig.params[0].type, pytd.ClassType)):
          stripped_signatures.add((method.name,
                                   sig.Replace(params=sig.params[1:])))
    return stripped_signatures

  def _FindSigAndName(self, t, sig_and_name):
    """Find a tuple(name, signature) in all methods of a type/class."""
    if t not in self.class_to_stripped_signatures:
      self.class_to_stripped_signatures[t] = self._StrippedSignatures(t)
    if sig_and_name in self.class_to_stripped_signatures[t]:
      return True
    if isinstance(t, pytd.ClassType):
      for base in t.cls.parents:
        if self._FindSigAndName(base, sig_and_name):
          return True
    return False

  def VisitSignature(self, sig):
    """Visit a Signature and return None if we can remove it."""
    if (not self.class_stack or
        not sig.params or
        sig.params[0].name != "self" or
        not isinstance(sig.params[0].type, pytd.ClassType)):
      return sig  # Not a method
    cls = sig.params[0].type.cls
    if cls is None:
      # TODO(kramm): Remove once pytype stops generating ClassType(name, None).
      return sig
    sig_and_name = (self.function.name, sig.Replace(params=sig.params[1:]))
    if any(self._FindSigAndName(base, sig_and_name) for base in cls.parents):
      return None  # remove (see VisitFunction)
    return sig

  def VisitFunction(self, f):
    """Visit a Function and return None if we can remove it."""
    signatures = tuple(sig for sig in f.signatures if sig)
    if signatures:
      return f.Replace(signatures=signatures)
    else:
      return None  # delete function

  def VisitClass(self, cls):
    return cls.Replace(methods=tuple(m for m in cls.methods if m))


class PullInMethodClasses(visitors.Visitor):
  """Simplifies classes with only a __call__ function to just a method.

  This transforms
    class Foo:
      m: Bar
    class Bar:
      def __call__(self: Foo, ...)
  to
    class Foo:
      def m(self, ...)
  .
  """

  def __init__(self):
    super(PullInMethodClasses, self).__init__()
    self._module = None
    self._total_count = collections.defaultdict(int)
    self._processed_count = collections.defaultdict(int)

  def _MaybeLookup(self, t):
    if isinstance(t, pytd.NamedType):
      try:
        return self._module.Lookup(t.name)
      except KeyError:
        return None
    elif isinstance(t, pytd.ClassType):
      return t.cls
    else:
      return None

  def _HasSelf(self, sig):
    """True if a signature has a self parameter.

    This only checks for the name, since the type can be too many different
    things (type of the method, type of the parent class, object, unknown etc.)
    and doesn't carry over to the simplified version, anyway.

    Arguments:
      sig: Function signature (instance of pytd.Signature)
    Returns:
      True if the signature has "self".
    """
    return sig.params and sig.params[0].name == "self"

  def _IsSimpleCall(self, t):
    """Returns whether a type has only one method, "__call__"."""
    if not isinstance(t, (pytd.NamedType, pytd.ClassType)):
      # We only do this for simple types.
      return False
    cls = self._MaybeLookup(t)
    if not isinstance(cls, pytd.Class):
      # This is not a class or it doesn't exist, so assume it's not a method.
      return False
    if [f.name for f in cls.methods] != ["__call__"]:
      return False
    method, = cls.methods
    return all(self._HasSelf(sig)
               for sig in method.signatures)

  def _CanDelete(self, cls):
    """Checks whether this class can be deleted.

    Returns whether all occurences of this class as a type were due to
    constants we removed.

    Arguments:
      cls: A pytd.Class.
    Returns:
      True if we can delete this class.
    """
    if not self._processed_count[cls.name]:
      # Leave standalone classes alone. E.g. the pytd files in
      # pytd/builtins/ defines classes not used by anything else.
      return False
    return self._processed_count[cls.name] == self._total_count[cls.name]

  def EnterTypeDeclUnit(self, module):
    # Since modules are hierarchical, we enter TypeDeclUnits multiple times-
    # but we only want to record the top-level one.
    if not self._module:
      self._module = module

  def VisitTypeDeclUnit(self, unit):
    return unit.Replace(classes=tuple(c for c in unit.classes
                                      if not self._CanDelete(c)))

  def VisitClassType(self, t):
    self._total_count[t.name] += 1
    return t

  def VisitNamedType(self, t):
    self._total_count[t.name] += 1
    return t

  def VisitClass(self, cls):
    """Visit a class, and change constants to methods where possible."""
    new_constants = []
    new_methods = list(cls.methods)
    for const in cls.constants:
      if self._IsSimpleCall(const.type):
        c = self._MaybeLookup(const.type)
        signatures = c.methods[0].signatures
        self._processed_count[c.name] += 1
        new_methods.append(
            pytd.Function(const.name, signatures, c.methods[0].kind))
      else:
        new_constants.append(const)  # keep
    cls = cls.Replace(constants=tuple(new_constants),
                      methods=tuple(new_methods))
    return cls.Visit(visitors.AdjustSelf(force=True))


class AbsorbMutableParameters(visitors.Visitor):
  """Converts mutable parameters to unions. This is lossy.

  For example, this will change
    def f(x: list[int]):
      x := list[int or float]
  to
    def f(x: list[int] or list[int or float])
  .
  (Use optimize.CombineContainers to then change x to list[int or float].)

  This also works for methods - it will then potentially change the type of
  "self". The resulting AST is temporary and needs careful handling.
  """

  def VisitMutableParameter(self, p):
    return pytd.Parameter(p.name, utils.JoinTypes([p.type, p.new_type]))


class TypeParameterScope(visitors.Visitor):
  """Common superclass for optimizations that track type parameters."""

  def __init__(self):
    super(TypeParameterScope, self).__init__()
    self.type_params_stack = [{}]

  def EnterClass(self, cls):
    new = self.type_params_stack[-1].copy()
    new.update({t.type_param: cls for t in cls.template})
    self.type_params_stack.append(new)

  def EnterSignature(self, sig):
    new = self.type_params_stack[-1].copy()
    new.update({t.type_param: sig for t in sig.template})
    self.type_params_stack.append(new)

  def IsClassTypeParameter(self, type_param):
    class_or_sig = self.type_params_stack[-1].get(type_param)
    return isinstance(class_or_sig, pytd.Class)

  def IsFunctionTypeParameter(self, type_param):
    class_or_sig = self.type_params_stack[-1].get(type_param)
    return isinstance(class_or_sig, pytd.Signature)

  def LeaveClass(self, _):
    self.type_params_stack.pop()

  def LeaveSignature(self, _):
    self.type_params_stack.pop()


class MergeTypeParameters(TypeParameterScope):
  """Remove all function type parameters in a union with a class type param.

  For example, this will change
    class A(typing.Generic(T)):
      T2 = TypeVar('T2')
      def append(self, T or T2) -> T2
  to
    class A(typing.Generic(T)):
      def append(self, T) -> T
  .
  Use this visitor after using AbsorbMutableParameters.

  As another example, the combination of AbsorbMutableParameters and
  MergeTypeParameters transforms
    class list(typing.Generic(T)):
      T2 = TypeVar('T2')
      def append(self, v: T2) -> NoneType:
        self := T or T2
  to
    class list(typing.Generic(T')):
      def append(self, V:T') -> NoneType
  by creating a *new* template variable T' that propagates the
  mutations to the outermost level (in this example, T' = T or T2)
  """

  def __init__(self):
    super(MergeTypeParameters, self).__init__()
    self.type_param_union = collections.defaultdict(list)

  def _AppendNew(self, l1, l2):
    """Appends all items to l1 that are not in l2."""
    # l1 and l2 are small (2-3 elements), so just use two loops.
    l1.extend(e2 for e2 in l2 if not any(e1 is e2 for e1 in l1))

  def VisitUnionType(self, u):
    type_params = [t for t in u.type_list if isinstance(t, pytd.TypeParameter)]
    for t in type_params:
      if self.IsFunctionTypeParameter(t):
        self._AppendNew(self.type_param_union[id(t)], type_params)
    return u

  def _AllContaining(self, type_param, seen=None):
    """Gets all type parameters that are in a union with the passed one."""
    seen = seen or set()
    result = [type_param]
    for other in self.type_param_union[id(type_param)]:
      if other in seen:
        continue  # break cycles
      seen.add(other)
      self._AppendNew(result, self._AllContaining(other, seen) or [other])
    return result

  def _ReplaceByOuterIfNecessary(self, item, substitutions):
    """Potentially replace a function type param with a class type param.

    Args:
      item: A pytd.TemplateItem
      substitutions: A dictionary to update with what we replaced.
    Returns:
      Either [item] or [].
    """
    containing_union = self._AllContaining(item.type_param)
    if not containing_union:
      return [item]
    class_type_parameters = [type_param
                             for type_param in containing_union
                             if self.IsClassTypeParameter(type_param)]
    if class_type_parameters:
      substitutions[item.type_param] = utils.JoinTypes(class_type_parameters)
      return []
    else:
      # It's a function type parameter that appears in a union with other
      # function type parameters.
      # TODO(kramm): We could merge those, too.
      return [item]

  def VisitSignature(self, sig):
    new_template = []
    substitutions = {k: k for k in self.type_params_stack[-1].keys()}
    for item in sig.template:
      new_template += self._ReplaceByOuterIfNecessary(item, substitutions)
    if sig.template == new_template:
      return sig  # Nothing changed.
    else:
      return sig.Replace(template=tuple(new_template)).Visit(
          visitors.ReplaceTypeParameters(substitutions)).Visit(SimplifyUnions())


def Optimize(node,
             lossy=False,
             use_abcs=False,
             max_union=7,
             remove_mutable=False):
  """Optimize a PYTD tree.

  Tries to shrink a PYTD tree by applying various optimizations.

  Arguments:
    node: A pytd node to be optimized. It won't be modified - this function
        will return a new node.
    lossy: Allow optimizations that change the meaning of the pytd.
    use_abcs: Use abstract base classes to represent unions like
        e.g. "float or int" as "Real"
    max_union: How many types we allow in a union before we simplify
        it to just "object".
    remove_mutable: Whether to simplify mutable parameters to normal
        parameters.

  Returns:
    An optimized node.
  """
  node = node.Visit(RemoveDuplicates())
  node = node.Visit(SimplifyUnions())
  node = node.Visit(CombineReturnsAndExceptions())
  node = node.Visit(Factorize())
  node = node.Visit(ApplyOptionalArguments())
  node = node.Visit(CombineContainers())
  superclasses = builtins.GetBuiltinsPyTD().Visit(
      visitors.ExtractSuperClassesByName())
  superclasses.update(node.Visit(
      visitors.ExtractSuperClassesByName()))
  if use_abcs:
    superclasses.update(abc_hierarchy.GetSuperClasses())
  hierarchy = SuperClassHierarchy(superclasses)
  node = node.Visit(SimplifyUnionsWithSuperclasses(hierarchy))
  if lossy:
    node = node.Visit(
        FindCommonSuperClasses(hierarchy)
    )
  if max_union:
    node = node.Visit(CollapseLongParameterUnions(max_union))
    node = node.Visit(CollapseLongReturnUnions(max_union))
    node = node.Visit(CollapseLongConstantUnions(max_union))
  if remove_mutable:
    node = node.Visit(AbsorbMutableParameters())
    node = node.Visit(CombineContainers())
    node = node.Visit(MergeTypeParameters())
    node = node.Visit(visitors.AdjustSelf(force=True))
  node = visitors.LookupClasses(node, builtins.GetBuiltinsPyTD())
  node = node.Visit(RemoveInheritedMethods())
  node = node.Visit(RemoveRedundantSignatures(hierarchy))
  return node
