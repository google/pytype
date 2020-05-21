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

from pytype import utils
from pytype.pytd import abc_hierarchy
from pytype.pytd import booleq
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import type_match
from pytype.pytd import visitors
import six

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
    return node.Replace(
        signatures=tuple(pytd_utils.OrderedSet(node.signatures)))


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
    self.match = type_match.TypeMatch(hierarchy.GetSuperClasses(),
                                      any_also_is_bottom=False)
    self.subst = {}

  def EnterClass(self, cls):
    # Preserve the identify of each type parameter, and don't
    # allow them to match against anything by themselves.
    self.subst = {p.type_param: pytd.NamedType("$" + p.name)
                  for p in cls.template}

  def LeaveClass(self, _):
    self.subst = {}

  def VisitFunction(self, node):
    new_signatures = []
    matches = set()
    # We keep track of which signature matched which other signatures, purely
    # for optimization - that way we don't have to query the reverse direction.
    for i, s1 in enumerate(node.signatures):
      for j, s2 in enumerate(node.signatures):
        if i != j and (j, i) not in matches:
          if s1.exceptions or s2.exceptions:
            # We don't support matching of exceptions.
            continue
          if s1.template:
            # type_match doesn't support polymorphic functions on the
            # left side yet.
            continue
          if self.match.match(s1, s2, self.subst) == booleq.TRUE:
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
    return pytd_utils.JoinTypes(union.type_list)


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
    def f(x: int) -> float:
      raise OverflowError()
    def f(x: int) -> int:
      raise IndexError()
  to
    def f(x: int) -> float or int:
      raise IndexError()
      raise OverflowError()
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
      ret = pytd_utils.JoinTypes(ret_exc.return_types)
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

  _CONTAINER_NAMES = {
      pytd.TupleType: ("__builtin__.tuple", "typing.Tuple"),
      pytd.CallableType: ("typing.Callable",),
  }

  def _key(self, t):
    if isinstance(t, (pytd.CallableType, pytd.TupleType)):
      return (t.base_type, len(t.parameters))
    else:
      return t.base_type

  def _should_merge(self, pytd_type, union):
    """Determine whether pytd_type values in the union should be merged.

    If the union contains the homogeneous flavor of pytd_type (e.g.,
    GenericType(base_type=tuple) when pytd_type is TupleType), or pytd_type
    values of different lengths, we want to turn all of the pytd_type values
    into homogeneous ones so that they can be merged into a single container.

    Args:
      pytd_type: The pytd type, either TupleType or CallableType.
      union: a pytd.UnionType

    Returns:
      True if the pytd_type values should be merged, False otherwise.
    """
    names = self._CONTAINER_NAMES[pytd_type]
    length = None
    for t in union.type_list:
      if isinstance(t, pytd_type):
        if length is None:
          length = len(t.parameters)
        elif length != len(t.parameters):
          return True
      elif (isinstance(t, pytd.GenericType) and
            t.base_type.name in names):
        return True
    return False

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
    union = pytd_utils.JoinTypes(union.type_list)  # flatten
    if not isinstance(union, pytd.UnionType):
      union = pytd.UnionType((union,))
    merge_tuples = self._should_merge(pytd.TupleType, union)
    merge_callables = self._should_merge(pytd.CallableType, union)
    if merge_tuples or merge_callables:
      type_list = []
      for t in union.type_list:
        if merge_tuples and isinstance(t, pytd.TupleType):
          t = pytd.GenericType(base_type=t.base_type,
                               parameters=(pytd.UnionType(t.parameters),))
        elif merge_callables and isinstance(t, pytd.CallableType):
          t = pytd.GenericType(base_type=t.base_type,
                               parameters=(pytd.AnythingType(), t.ret))
        type_list.append(t)
      union = union.Replace(type_list=tuple(type_list))
    collect = {}
    has_redundant_base_types = False
    for t in union.type_list:
      if isinstance(t, pytd.GenericType):
        key = self._key(t)
        if key in collect:
          has_redundant_base_types = True
          collect[key] = tuple(
              pytd_utils.JoinTypes([p1, p2])
              for p1, p2 in zip(collect[key], t.parameters))
        else:
          collect[key] = t.parameters
    if not has_redundant_base_types:
      return union
    result = pytd.NothingType()
    done = set()
    for t in union.type_list:
      if isinstance(t, pytd.GenericType):
        key = self._key(t)
        if key in done:
          continue  # already added
        parameters = collect[key]
        add = t.Replace(parameters=tuple(p.Visit(CombineContainers())
                                         for p in parameters))
        done.add(key)
      else:
        add = t
      result = pytd_utils.JoinTypes([result, add])
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
      if sig.params[i].mutated_type is not None:
        # We can't group mutable parameters. Leave this signature alone.
        groups[sig] = None
        continue

      # Set type of parameter i to None
      params = list(sig.params)
      param_i = params[i]
      params[i] = param_i.Replace(type=None)

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

    for i in six.moves.xrange(max_argument_count):
      new_sigs = []
      for sig, types in self._GroupByOmittedArg(signatures, i):
        if types:
          # One or more options for argument <i>:
          new_params = list(sig.params)
          new_params[i] = sig.params[i].Replace(
              type=pytd_utils.JoinTypes(types))
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

    for i in six.moves.xrange(param_count):
      if sig.params[0:i] in optional_arg_sigs:
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
    optional_arg_sigs = frozenset(s.params
                                  for s in f.signatures
                                  if s.has_optional)

    new_signatures = (s for s in f.signatures
                      if not self._HasShorterVersion(s, optional_arg_sigs))
    return f.Replace(signatures=tuple(new_signatures))


class SuperClassHierarchy(object):
  """Utility class for optimizations working with superclasses."""

  def __init__(self, superclasses):
    self._superclasses = superclasses
    self._subclasses = utils.invert_dict(self._superclasses)

  def GetSuperClasses(self):
    return self._superclasses

  def _CollectSuperclasses(self, type_name, collect):
    """Recursively collect super classes for a type.

    Arguments:
      type_name: A string, the type's name.
      collect: A set() of strings, modified to contain all superclasses.
    """
    collect.add(type_name)
    # The superclasses might have superclasses of their own, so recurse.
    for superclass in self._superclasses.get(type_name, []):
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
      # TODO(rechen): How can we make this work with GenericType?
      if isinstance(t, pytd.GENERIC_BASE_TYPE):
        c += collections.Counter(self.hierarchy.ExpandSubClasses(str(t)))
    # Below, c[str[t]] can be zero - that's the default for non-existent items
    # in collections.Counter. It'll happen for types that are not
    # instances of GENERIC_BASE_TYPE, like container types.
    new_type_list = [t for t in union.type_list if c[str(t)] <= 1]
    return pytd_utils.JoinTypes(new_type_list)


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
        pytd.NamedType(cls) for cls in intersection
        if not self.hierarchy.HasSubClassInSet(cls, intersection))

    if not new_type_list:
      return union  # if types don't intersect, leave them alone

    return pytd_utils.JoinTypes(new_type_list)


class CollapseLongUnions(visitors.Visitor):
  """Shortens long unions to object (or "?").

  Poor man's version of FindCommonSuperClasses. Shorten types like
  "str or unicode or int or float or list" to just "object" or "?".

  Additionally, if the union already contains at least one "object", we also
  potentially replace the entire union with just "object".

  Attributes:
    max_length: The maximum number of types to allow in a union. If there are
      more types than this, it is shortened.
  """

  def __init__(self, max_length=7):
    assert isinstance(max_length, six.integer_types)
    super(CollapseLongUnions, self).__init__()
    self.generic_type = pytd.AnythingType()
    self.max_length = max_length

  def VisitUnionType(self, union):
    if len(union.type_list) > self.max_length:
      return self.generic_type
    elif self.generic_type in union.type_list:
      return self.generic_type
    else:
      return union


class AdjustGenericType(visitors.Visitor):
  """Changes the generic type from "object" to "Any"."""

  def __init__(self):
    super(AdjustGenericType, self).__init__()
    self.old_generic_type = pytd.ClassType("__builtin__.object")
    self.new_generic_type = pytd.AnythingType()

  def VisitClassType(self, t):
    if t == self.old_generic_type:
      return self.new_generic_type
    else:
      return t


class AdjustReturnAndConstantGenericType(visitors.Visitor):
  """Changes "object" to "Any" in return and constant types."""

  def VisitSignature(self, sig):
    return sig.Replace(return_type=sig.return_type.Visit(AdjustGenericType()))

  def VisitConstant(self, c):
    return c.Replace(type=c.type.Visit(AdjustGenericType()))


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

  def VisitLateType(self, _):
    raise NotImplementedError("Can't use AddInheritedMethods with LateType.")

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
    adjust_self = visitors.AdjustSelf(force=True)
    adjust_self.class_types.append(visitors.ClassAsType(cls))
    new_methods = list(cls.methods)
    for base in bases:
      for m in base.methods:
        if m.name not in names:
          new_methods.append(m.Visit(adjust_self))
    new_constants = list(cls.constants)
    for base in bases:
      for c in base.constants:
        if c.name not in names:
          new_constants.append(c)
    return cls.Replace(methods=tuple(new_methods),
                       constants=tuple(new_constants))


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

  def _LookupIfSimpleCall(self, t):
    """Looks up the type if it has only one method, "__call__"."""
    if not isinstance(t, (pytd.NamedType, pytd.ClassType)):
      # We only do this for simple types.
      return None
    cls = self._MaybeLookup(t)
    if not isinstance(cls, pytd.Class):
      # This is not a class or it doesn't exist, so assume it's not a method.
      return None
    if [f.name for f in cls.methods] != ["__call__"]:
      return None
    method, = cls.methods
    return cls if all(self._HasSelf(sig) for sig in method.signatures) else None

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
    adjust_self = visitors.AdjustSelf(force=True)
    adjust_self.class_types.append(visitors.ClassAsType(cls))
    for const in cls.constants:
      c = self._LookupIfSimpleCall(const.type)
      if c:
        signatures = c.methods[0].signatures
        self._processed_count[c.name] += 1
        new_method = pytd.Function(const.name, signatures, c.methods[0].kind)
        new_methods.append(new_method.Visit(adjust_self))
      else:
        new_constants.append(const)  # keep
    return cls.Replace(constants=tuple(new_constants),
                       methods=tuple(new_methods))


class AbsorbMutableParameters(visitors.Visitor):
  """Converts mutable parameters to unions. This is lossy.

  For example, this will change
    def f(x: list[int]):
      x = list[int or float]
  to
    def f(x: list[int] or list[int or float])
  .
  (Use optimize.CombineContainers to then change x to list[int or float].)

  This also works for methods - it will then potentially change the type of
  "self". The resulting AST is temporary and needs careful handling.
  """

  def VisitParameter(self, p):
    if p.mutated_type is None:
      return p
    else:
      return p.Replace(type=pytd_utils.JoinTypes([p.type, p.mutated_type]),
                       mutated_type=None)


class SimplifyContainers(visitors.Visitor):
  """Simplifies containers whose type parameters are all Any.

  For example, this will change
    def f() -> List[any]
  to
    def f() -> list
  Note that we don't simplify TupleType or CallableType, since they have
  variable-length parameters, and the parameter length is meaningful even when
  the parameters are all Any.
  """

  def _Simplify(self, t):
    if all(isinstance(p, pytd.AnythingType) for p in t.parameters):
      return t.base_type
    else:
      return t

  def VisitGenericType(self, t):
    return self._Simplify(t)


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
      def append(self, T or T2) -> T2
  to
    class A(typing.Generic(T)):
      def append(self, T) -> T
  .
  Use this visitor after using AbsorbMutableParameters.

  As another example, the combination of AbsorbMutableParameters and
  MergeTypeParameters transforms
    class list(typing.Generic(T)):
      def append(self, v: T2) -> NoneType:
        self = T or T2
  to
    class list(typing.Generic(T')):
      def append(self, V:T') -> NoneType
  by creating a *new* template variable T' that propagates the
  mutations to the outermost level (in this example, T' = T or T2)
  """

  def __init__(self):
    super(MergeTypeParameters, self).__init__()
    self.type_param_union = None

  def _AppendNew(self, l1, l2):
    """Appends all items to l1 that are not in l2."""
    # l1 and l2 are small (2-3 elements), so just use two loops.
    for e2 in l2:
      if not any(e1 is e2 for e1 in l1):
        l1.append(e2)

  def EnterSignature(self, node):
    # Necessary because TypeParameterScope also defines this function
    super(MergeTypeParameters, self).EnterSignature(node)
    assert self.type_param_union is None
    self.type_param_union = collections.defaultdict(list)

  def LeaveSignature(self, node):
    # Necessary because TypeParameterScope also defines this function
    super(MergeTypeParameters, self).LeaveSignature(node)
    self.type_param_union = None

  def VisitUnionType(self, u):
    type_params = [t for t in u.type_list if isinstance(t, pytd.TypeParameter)]
    for t in type_params:
      if self.IsFunctionTypeParameter(t):
        self._AppendNew(self.type_param_union[t.name], type_params)
    return u

  def _AllContaining(self, type_param, seen=None):
    """Gets all type parameters that are in a union with the passed one."""
    seen = seen or set()
    result = [type_param]
    for other in self.type_param_union[type_param.name]:
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
      substitutions[item.type_param] = pytd_utils.JoinTypes(
          class_type_parameters)
      return []
    else:
      # It's a function type parameter that appears in a union with other
      # function type parameters.
      # TODO(kramm): We could merge those, too.
      return [item]

  def VisitSignature(self, sig):
    new_template = []
    substitutions = {k: k for k in self.type_params_stack[-1]}
    for item in sig.template:
      new_template += self._ReplaceByOuterIfNecessary(item, substitutions)
    if sig.template == new_template:
      return sig  # Nothing changed.
    else:
      return sig.Replace(template=tuple(new_template)).Visit(
          visitors.ReplaceTypeParameters(substitutions)).Visit(SimplifyUnions())


def Optimize(node,
             builtins=None,
             lossy=False,
             use_abcs=False,
             max_union=7,
             remove_mutable=False,
             can_do_lookup=True):
  """Optimize a PYTD tree.

  Tries to shrink a PYTD tree by applying various optimizations.

  Arguments:
    node: A pytd node to be optimized. It won't be modified - this function
        will return a new node.
    builtins: Definitions of all of the external types in node.
    lossy: Allow optimizations that change the meaning of the pytd.
    use_abcs: Use abstract base classes to represent unions like
        e.g. "float or int" as "Real".
    max_union: How many types we allow in a union before we simplify
        it to just "object".
    remove_mutable: Whether to simplify mutable parameters to normal
        parameters.
    can_do_lookup: True: We're either allowed to try to resolve NamedType
        instances in the AST, or the AST is already resolved. False: Skip any
        optimizations that would require NamedTypes to be resolved.

  Returns:
    An optimized node.
  """
  node = node.Visit(RemoveDuplicates())
  node = node.Visit(SimplifyUnions())
  node = node.Visit(CombineReturnsAndExceptions())
  node = node.Visit(Factorize())
  node = node.Visit(ApplyOptionalArguments())
  node = node.Visit(CombineContainers())
  node = node.Visit(SimplifyContainers())
  if builtins:
    superclasses = builtins.Visit(visitors.ExtractSuperClassesByName())
    superclasses.update(node.Visit(visitors.ExtractSuperClassesByName()))
    if use_abcs:
      superclasses.update(abc_hierarchy.GetSuperClasses())
    hierarchy = SuperClassHierarchy(superclasses)
    node = node.Visit(SimplifyUnionsWithSuperclasses(hierarchy))
    if lossy:
      node = node.Visit(FindCommonSuperClasses(hierarchy))
  if max_union:
    node = node.Visit(CollapseLongUnions(max_union))
  node = node.Visit(AdjustReturnAndConstantGenericType())
  if remove_mutable:
    node = node.Visit(AbsorbMutableParameters())
    node = node.Visit(CombineContainers())
    node = node.Visit(MergeTypeParameters())
    node = node.Visit(visitors.AdjustSelf())
  node = node.Visit(SimplifyContainers())
  if builtins and can_do_lookup:
    node = visitors.LookupClasses(node, builtins, ignore_late_types=True)
    node = node.Visit(RemoveRedundantSignatures(hierarchy))
  return node
