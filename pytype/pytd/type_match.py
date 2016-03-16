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


"""Match pytd types against each other.

"Matching" x against y means roughly: If we have a function f(param: y) and
a type x, would we be able to pass (an instance of) x to f. (I.e.,
"execute f(x)"). So for example, str would "match" against basestring, and
list[int] would match against list[Number].

This is used for converting structural types to nominal types during type
inference, but could also be used when merging pytd files, to match existing
signatures against new inference results.
"""

import logging


from pytype.pytd import abc_hierarchy
from pytype.pytd import booleq
from pytype.pytd import pytd
from pytype.pytd import utils
from pytype.pytd.parse import node
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)


# Might not be needed anymore once pytd has builtin support for ~unknown.
def is_unknown(t):
  """Return True if this is an ~unknown."""
  if isinstance(t, (pytd.ClassType, pytd.NamedType, pytd.Class, StrictType)):
    return t.name.startswith("~unknown")
  elif isinstance(t, str):
    return t.startswith("~unknown")
  else:
    return False


# Might not be needed anymore once pytd has Interface types.
def is_complete(cls):
  """Return True if this class is complete."""
  # Incomplete classes are marked with "~". E.g. "class ~int".
  if isinstance(cls, str):
    return not cls.startswith("~")
  else:
    return not cls.name.startswith("~")


def is_partial(cls):
  """Returns True if this is a partial class, e.g. "~list"."""
  if isinstance(cls, str):
    return cls.startswith("~")
  elif hasattr(cls, "name"):
    return cls.name.startswith("~")
  else:
    return False


def unpack_name_of_partial(name):
  """Convert e.g. "~int" to "int"."""
  assert isinstance(name, str)
  assert name.startswith("~")
  return name.lstrip("~").replace("~", ".")


def get_all_subclasses(asts):
  """Compute a class->subclasses mapping.

  Args:
    asts: A list of ASTs.

  Returns:
    A dictionary, mapping instances of pytd.TYPE (types) to lists of
    pytd.Class (the derived classes).
  """
  hierarchy = {}
  for ast in asts:
    hierarchy.update(ast.Visit(visitors.ExtractSuperClasses()))
  hierarchy = {cls: [superclass for superclass in superclasses
                     if (hasattr(superclass, "name") and
                         is_complete(superclass))]
               for cls, superclasses in hierarchy.items()
               if is_complete(cls)}
  # typically this is a fairly short list, e.g.:
  #  [ClassType(basestring), ClassType(int), ClassType(object)]
  return abc_hierarchy.Invert(hierarchy)


class StrictType(node.Node("name")):
  """A type that doesn't allow sub- or superclasses to match.

  For example, "int" is considered a valid argument for a function that accepts
  "object", but StrictType("int") is not.
  """

  def __str__(self):
    return self.name


class TypeMatch(utils.TypeMatcher):
  """Class for matching types against other types."""

  def __init__(self, direct_subclasses=None, any_also_is_bottom=True):
    """Construct.

    Args:
      direct_subclasses: A dictionary, mapping pytd.TYPE to lists of pytd.TYPE.
      any_also_is_bottom: Whether we should, (if True) consider
        pytd.AnythingType() to also be at the bottom of the type hierarchy,
        thus making it a subclass of everything, or (if False) to be only
        at the top.
    """
    self.direct_subclasses = direct_subclasses or {}
    self.any_also_is_bottom = any_also_is_bottom
    self.solver = booleq.Solver()
    self._implications = {}

  def default_match(self, t1, t2, *unused_args, **unused_kwargs):
    # Don't allow utils.TypeMatcher to do default matching.
    raise AssertionError("Can't compare %s and %s",
                         type(t1).__name__,
                         type(t2).__name__)

  def get_superclasses(self, t):
    """Get all base classes of this type.

    Args:
        t: A pytd.TYPE
    Returns:
        A list of pytd.TYPE.
    """
    if isinstance(t, pytd.ClassType):
      return sum((self.get_superclasses(c) for c in t.cls.parents), [t])
    elif isinstance(t, pytd.AnythingType):
      # All types, even "?", inherit from object.
      return [pytd.NamedType("__builtin__.object")]
    elif isinstance(t, pytd.GenericType):
      return self.get_superclasses(t.base_type)
    else:
      log.warning("Can't extract superclasses from %s", type(t))
      return [pytd.NamedType("object")]

  def get_subclasses(self, t):
    """Get all classes derived from this type.

    Args:
        t: A pytd.TYPE
    Returns:
        A list of pytd.TYPE.
    """
    if isinstance(t, pytd.ClassType):
      subclasses = self.direct_subclasses.get(t, [])
      return sum((self.get_subclasses(pytd.ClassType(c.name, c))
                  for c in subclasses), [t])
    else:
      raise NotImplementedError("Can't extract subclasses from %s", type(t))

  def type_parameter(self, unknown, base_class, item):
    """This generates the type parameter when matching against a generic type.

    For example, when we match ~unknown1 against list[T], we need an additional
    type to model the T in "~unknown1[T]". This type would have the name
    "~unknown1.list.T".

    Args:
      unknown: An unknown type. This is the type that's matched against
        base_class[T]
      base_class: The base class of the generic we're matching the unknown
        against. E.g. "list".
      item: The pytd.TemplateItem, i.e., the actual type parameter. ("T" in
        the examples above)
    Returns:
      A type (pytd.Node) to represent this type parameter.
    """
    assert is_unknown(unknown)
    assert isinstance(base_class, pytd.Class)
    name = unknown.name + "." + base_class.name + "." + item.type_param.name
    # We do *not* consider subclasses or superclasses when matching type
    # parameters.
    # So for example, if we pass list[int] to f(x: list[T]), we assume that
    # T can only be "int", not "int + object". This might be considered
    # incorrect, but typically gives us more intuitive results.
    # Note that this only happens if we match ~unknown against generic types,
    # not for matching of "known" types against each other.
    return StrictType(name)

  def match_Generic_against_Generic(self, t1, t2, subst):  # pylint: disable=invalid-name
    """Match a pytd.GenericType against another pytd.GenericType."""
    assert isinstance(t1.base_type, pytd.ClassType)
    assert isinstance(t2.base_type, pytd.ClassType)
    # We don't do inheritance for base types, since right now, inheriting from
    # instantiations of templated types is not supported by pytd.
    if (is_complete(t1.base_type.cls) and is_complete(t2.base_type.cls) and
        t1.base_type.cls.name != t2.base_type.cls.name):
      # Optimization: If the base types are incompatible, these two generic
      # types can never match.
      base_type_cmp = booleq.FALSE
    else:
      base_type_cmp = booleq.Eq(t1.base_type.cls.name, t2.base_type.cls.name)
    if base_type_cmp is booleq.FALSE:
      return booleq.FALSE
    assert len(t1.parameters) == len(t2.parameters), t1.base_type.cls.name
    # Type parameters are covariant:
    # E.g. passing list[int] as argument for list[object] succeeds.
    param_cmp = [self.match_type_against_type(p1, p2, subst)
                 for p1, p2 in zip(t1.parameters, t2.parameters)]
    return booleq.And([base_type_cmp] + param_cmp)

  def match_Unknown_against_Generic(self, t1, t2, subst):  # pylint: disable=invalid-name
    assert isinstance(t2.base_type, pytd.ClassType)
    # No inheritance for base classes - you can only inherit from an
    # instantiated template, but not from a template itself.
    base_match = booleq.Eq(t1.name, t2.base_type.cls.name)
    type_params = [self.type_parameter(t1, t2.base_type.cls, item)
                   for item in t2.base_type.cls.template]
    for type_param in type_params:
      self.solver.register_variable(type_param.name)
    params = [self.match_type_against_type(p1, p2, subst)
              for p1, p2 in zip(type_params, t2.parameters)]
    return booleq.And([base_match] + params)

  def match_Generic_against_Unknown(self, t1, t2, subst):  # pylint: disable=invalid-name
    # Note: This flips p1 and p2 above.
    return self.match_Unknown_against_Generic(t2, t1, subst)

  def maybe_lookup_type_param(self, t, subst):
    while isinstance(t, pytd.TypeParameter):
      # We can only have type parameters in a class, and if so, we should have
      # added them to the type paramter substitution map (subst) beforehand:
      assert t in subst
      if subst[t] is None:
        # Function type parameter. Can be anything.
        t = pytd.AnythingType()
      else:
        t = subst[t]
    return t

  def unclass(self, t):
    """Prevent further subclass or superclass expansion for this type."""
    if isinstance(t, pytd.ClassType):
      return pytd.NamedType(t.name)
    else:
      return t

  def expand_superclasses(self, t):
    class_and_superclasses = self.get_superclasses(t)
    return [self.unclass(t) for t in class_and_superclasses]

  def expand_subclasses(self, t):
    class_and_subclasses = self.get_subclasses(t)
    return [self.unclass(t) for t in class_and_subclasses]

  def match_type_against_type(self, t1, t2, subst):
    types = (t1, t2, frozenset(subst.items()))
    if types in self._implications:
      return self._implications[types]
    implication = self._implications[types] = self._match_type_against_type(
        t1, t2, subst)
    return implication

  def _full_name(self, t):
    return t.name

  def _match_type_against_type(self, t1, t2, subst):
    """Match a pytd.TYPE against another pytd.TYPE."""
    t1 = self.maybe_lookup_type_param(t1, subst)
    t2 = self.maybe_lookup_type_param(t2, subst)
    # TODO(kramm): Use utils:TypeMatcher to simplify this?
    if isinstance(t1, pytd.ExternalType) or isinstance(t2, pytd.ExternalType):
      # These are unresolved. Only happens when type_matcher is called from
      # outside the type inferencer (e.g. by optimize.py)
      return booleq.TRUE
    elif isinstance(t1, pytd.AnythingType) or isinstance(t2, pytd.AnythingType):
      # We can match anything against AnythingType
      return booleq.TRUE
    elif isinstance(t2, pytd.AnythingType):
      # We can match anything against AnythingType. (It's like top)
      return booleq.TRUE
    elif isinstance(t1, pytd.AnythingType):
      if self.any_also_is_bottom:
        # We can match AnythingType against everything. (It's like bottom)
        return booleq.TRUE
      else:
        return booleq.FALSE
    elif isinstance(t1, pytd.NothingType) and isinstance(t2, pytd.NothingType):
      # nothing matches against nothing.
      return booleq.TRUE
    elif isinstance(t1, pytd.NothingType) or isinstance(t2, pytd.NothingType):
      # We can't match anything against nothing. (Except nothing itself, above)
      return booleq.FALSE
    elif isinstance(t1, pytd.UnionType):
      return booleq.And(self.match_type_against_type(u, t2, subst)
                        for u in t1.type_list)
    elif isinstance(t2, pytd.UnionType):
      return booleq.Or(self.match_type_against_type(t1, u, subst)
                       for u in t2.type_list)
    elif (isinstance(t1, pytd.ClassType) and isinstance(t2, StrictType) or
          isinstance(t1, StrictType) and isinstance(t2, pytd.ClassType)):
      # For strict types, avoid subclasses of the left side.
      return booleq.Eq(self._full_name(t1), self._full_name(t2))
    elif (isinstance(t1, pytd.ClassType) and hasattr(t2, "name") and
          t2.name == "__builtin__.object"):
      return booleq.TRUE
    elif isinstance(t1, pytd.ClassType):
      # ClassTypes are similar to Unions, except they're disjunctions: We can
      # match the type or any of its base classes against the formal parameter.
      return booleq.Or(self.match_type_against_type(t, t2, subst)
                       for t in self.expand_superclasses(t1))
    elif isinstance(t2, pytd.ClassType):
      # ClassTypes on the right are exactly like Unions: We can match against
      # this type or any of its subclasses.
      return booleq.Or(self.match_type_against_type(t1, t, subst)
                       for t in self.expand_subclasses(t2))
    assert not isinstance(t1, pytd.ClassType)
    assert not isinstance(t2, pytd.ClassType)
    if is_unknown(t1) and isinstance(t2, pytd.GenericType):
      return self.match_Unknown_against_Generic(t1, t2, subst)
    elif isinstance(t1, pytd.GenericType) and is_unknown(t2):
      return self.match_Generic_against_Unknown(t1, t2, subst)
    elif isinstance(t1, pytd.GenericType) and isinstance(t2, pytd.GenericType):
      return self.match_Generic_against_Generic(t1, t2, subst)
    elif isinstance(t1, pytd.GenericType):
      # E.g. list[...] matches against list, or even object.
      return self.match_type_against_type(t1.base_type, t2, subst)
    elif isinstance(t2, pytd.GenericType):
      if self.any_also_is_bottom:
        # E.g. list (a.k.a. list[Any]) matches against list[str]
        return self.match_type_against_type(t1, t2.base_type, subst)
      else:
        return booleq.FALSE
    elif is_unknown(t1) and is_unknown(t2):
      return booleq.Eq(t1.name, t2.name)
    elif (isinstance(t1, (pytd.NamedType, StrictType)) and
          isinstance(t2, (pytd.NamedType, StrictType))):
      if is_complete(t1) and is_complete(t2) and t1.name != t2.name:
        # Optimization: If we know these two can never be equal, just return
        # false right away.
        return booleq.FALSE
      else:
        return booleq.Eq(t1.name, t2.name)
    else:
      raise AssertionError("Don't know how to match %s against %s" % (
          type(t1), type(t2)))

  # pylint: disable=invalid-name
  def match_Signature_against_Signature(self, sig1, sig2, subst,
                                        skip_self=False):
    """Match a pytd.Signature against another pytd.Signature.

    Args:
      sig1: The caller
      sig2: The callee
      subst: Current type parameters.
      skip_self: If True, doesn't compare the first paramter, which is
        considered (and verified) to be "self".
    Returns:
      An instance of booleq.BooleanTerm, i.e. a boolean formula.
    """
    assert not sig1.template
    # Signatures have type parameters, too. We ignore them, since they can
    # be anything. (See maybe_lookup_type_param())
    subst.update({p.type_param: None for p in sig2.template})
    if sig1.has_optional and sig2.has_optional:
      m = max(len(sig1.params), len(sig2.params))
      params1 = sig1.params[:m]
      params2 = sig2.params[:m]
    elif sig1.has_optional:
      params1 = sig1.params
      params2 = sig2.params[:len(sig1.params)]
    elif sig2.has_optional:
      params1 = sig1.params[:len(sig2.params)]
      params2 = sig2.params
    else:
      params1 = sig1.params
      params2 = sig2.params
    if skip_self:
      # Methods in an ~unknown need to declare their methods with "self"
      assert (params1 and params1[0].name == "self") or sig2.has_optional
      if params1 and params1[0].name == "self":
        params1 = params1[1:]
      # For loaded pytd, we allow methods to omit the "self" parameter.
      if params2 and params2[0].name == "self":
        params2 = params2[1:]
    if len(params1) == len(params2):
      equalities = []
      for p1, p2 in zip(params1, params2):
        equalities.append(self.match_type_against_type(p1.type, p2.type, subst))
      equalities.append(
          self.match_type_against_type(
              sig1.return_type, sig2.return_type, subst))
      return booleq.And(equalities)
    else:
      return booleq.FALSE

  def match_Signature_against_Function(self, sig, f, subst, skip_self=False):  # pylint: disable=invalid-name
    return booleq.And(
        booleq.Or(
            self.match_Signature_against_Signature(inner, s, subst, skip_self)
            for s in f.signatures)
        for inner in sig.Visit(visitors.ExpandSignatures()))

  def match_Function_against_Function(self, f1, f2, subst, skip_self=False):  # pylint: disable=invalid-name
    return booleq.And(
        self.match_Signature_against_Function(s1, f2, subst, skip_self)
        for s1 in f1.signatures)

  def match_Function_against_Class(self, f1, cls2, subst, cache):
    cls2_methods = cache.get(id(cls2))
    if cls2_methods is None:
      cls2_methods = cache[id(cls2)] = {f.name: f for f in cls2.methods}
    if f1.name not in cls2_methods:
      # The class itself doesn't have this method, but base classes might.
      # TODO(kramm): This should do MRO order, not depth-first.
      for base in cls2.parents:
        if isinstance(base, pytd.AnythingType):
          # AnythingType can contain any method. However, that would mean that
          # a class that inherits from AnythingType contains any method
          # imaginable, and hence is a match for anything. To prevent the bad
          # results caused by that, return FALSE here.
          return booleq.FALSE
        elif isinstance(base, pytd.ClassType):
          cls = base.cls
          implication = self.match_Function_against_Class(f1, cls, subst, cache)
          if implication is not booleq.FALSE:
            return implication
        elif isinstance(base, pytd.GenericType):
          cls = base.base_type.cls
          subst = subst.copy()
          for param, value in zip(cls.template, base.parameters):
            subst[param.type_param] = value
          implication = self.match_Function_against_Class(f1, cls, subst, cache)
          if implication is not booleq.FALSE:
            return implication
        else:
          # Funky types like GenericType, UnionType, etc. are hard (or
          # impossible) to match against (and shouldn't appear as a base class)
          # so we treat them as catch-all.
          log.warning("Assuming that %s has method %s",
                      pytd.Print(base), f1.name)
          return booleq.TRUE
      return booleq.FALSE
    else:
      f2 = cls2_methods[f1.name]
      return self.match_Function_against_Function(
          f1, f2, subst, skip_self=True)

  def match_Class_against_Class(self, cls1, cls2, subst):  # pylint: disable=invalid-name
    """Match a pytd.Class against another pytd.Class."""
    implications = []
    cache = {}
    for f1 in cls1.methods:
      implication = self.match_Function_against_Class(f1, cls2, subst, cache)
      implications.append(implication)
      if implication is booleq.FALSE:
        break
    # TODO(kramm): class attributes
    return booleq.And(implications)
