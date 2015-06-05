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
list<int> would match against list<Number>.

This is used for converting structural types to nominal types during type
inference, but could also be used when merging pytd files, to match existing
signatures against new inference results.
"""


from pytype.pytd import booleq
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import utils
from pytype.pytd.parse import node


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
  return name.lstrip("~")


class StrictType(node.Node("name")):
  """A type that doesn't allow sub- or superclasses to match.

  For example, "int" is considered a valid argument for a function that accepts
  "object", but StrictType("int") is not.
  """
  pass


class TypeMatch(utils.TypeMatcher):
  """Class for matching types against other types."""

  def __init__(self, direct_subclasses=None):
    self.direct_subclasses = direct_subclasses or {}

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
      return []
    else:
      raise NotImplementedError("Can't extract superclasses from %s", type(t))

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

    For example, when we match ~unknown1 against list<T>, we need an additional
    type to model the T in "~unknown1<T>". This type would have the name
    "~unknown1.list.T".

    Args:
      unknown: An unknown type. This is the type that's matched against
        base_class<T>
      base_class: The base class of the generic we're matching the unknown
        against. E.g. "list".
      item: The pytd.TemplateItem, i.e., the actual type parameter. ("T" in
        the examples above)
    Returns:
      A type (pytd.Node) to represent this type parameter.
    """
    assert is_unknown(unknown)
    name = unknown.name + "." + base_class.name + "." + item.type_param.name
    # We do *not* consider subclasses or superclasses when matching type
    # parameters.
    # So for example, if we pass list<int> to f(x: list<T>), we assume that
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
      base_type_cmp = booleq.Eq(t1.base_type.name, t2.base_type.name)
    if base_type_cmp == booleq.FALSE:
      return booleq.FALSE
    assert len(t1.parameters) == len(t2.parameters), t1.base_type.name
    # Type parameters are covariant:
    # E.g. passing list<int> as argument for list<object> succeeds.
    param_cmp = [self.match_type_against_type(p1, p2, subst)
                 for p1, p2 in zip(t1.parameters, t2.parameters)]
    return booleq.And([base_type_cmp] + param_cmp)

  def match_Unknown_against_Generic(self, t1, t2, subst):  # pylint: disable=invalid-name
    assert isinstance(t2.base_type, pytd.ClassType)
    # No inheritance for base classes - you can only inherit from an
    # instantiated template, but not from a template itself.
    base_match = booleq.Eq(t1.name, t2.base_type.name)
    type_params = [self.type_parameter(t1, t2.base_type.cls, item)
                   for item in t2.base_type.cls.template]
    params = [self.match_type_against_type(p1, p2, subst)
              for p1, p2 in zip(type_params, t2.parameters)]
    return booleq.And([base_match] + params)

  def match_Generic_against_Unknown(self, t1, t2, subst):  # pylint: disable=invalid-name
    assert isinstance(t1.base_type, pytd.ClassType)
    base_match = booleq.Eq(t1.base_type.name, t2.name)
    type_params = [self.type_parameter(t2, t1.base_type.cls, item)
                   for item in t1.base_type.cls.template]
    params = [self.match_type_against_type(p1, p2, subst)
              for p1, p2 in zip(t1.parameters, type_params)]
    return booleq.And([base_match] + params)

  def maybe_lookup_type_param(self, t, subst):
    if not isinstance(t, pytd.TypeParameter):
      return t
    # We can only have type parameters in a class, and if so, we should have
    # added them to the type paramter substitution map (subst) beforehand:
    assert t in subst
    if subst[t] is None:
      # Function type parameter. Can be anything.
      return pytd.AnythingType()
    else:
      return subst[t]

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
    """Match a pytd.TYPE against another pytd.TYPE."""
    t1 = self.maybe_lookup_type_param(t1, subst)
    t2 = self.maybe_lookup_type_param(t2, subst)
    # TODO(kramm): Use utils:TypeMatcher to simplify this?
    if isinstance(t1, pytd.AnythingType) or isinstance(t2, pytd.AnythingType):
      # We can match anything against AnythingType
      return booleq.TRUE
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
    elif isinstance(t1, pytd.ClassType) and isinstance(t2, StrictType):
      # For strict types, avoid subclasses of the left side.
      return booleq.Eq(t1.name, t2.name)
    elif isinstance(t1, pytd.ClassType):
      # ClassTypes are similar to Unions, except they're disjunctions: We can
      # match the type or any of its base classes against the formal parameter.
      return booleq.Or(self.match_type_against_type(t, t2, subst)
                       for t in self.expand_superclasses(t1))
    elif isinstance(t2, pytd.ClassType):
      # ClassTypes on the right are exactly like Unions: We can match against
      # this type or any of its subclasses.
      # TODO(pludemann):
      #    if not allow_subclass:
      #      return self.match_type_against_type(t1, self.unclass(t2), subst)
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
      # E.g. list<...> matches against list, or even object.
      return self.match_type_against_type(t1.base_type, t2, subst)
    elif isinstance(t2, pytd.GenericType):
      assert t1 != t2.base_type
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

  def match_Signature_against_Signature(self, sig1, sig2, subst, skip_self):  # pylint: disable=invalid-name
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
    assert not sig1.has_optional
    # Signatures have type parameters, too. We ignore them, since they can
    # be anything. (See maybe_lookup_type_param())
    subst.update({p.type_param: None for p in sig2.template})
    params2 = sig2.params
    params1 = sig1.params[:len(params2)] if sig2.has_optional else sig1.params
    if skip_self:
      assert params1[0].name == "self"
      assert params2[0].name == "self"
      params1 = params1[1:]
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

  def match_Signature_against_FunctionWithSignatures(self, sig, f, subst,
                                                     skip_self=False):  # pylint: disable=invalid-name
    return booleq.And(
        booleq.Or(
            self.match_Signature_against_Signature(sig, s, subst, skip_self)
            for s in f.signatures)
        for inner_sig in sig.Visit(optimize.ExpandSignatures()))

  def match_FunctionWithSignatures_against_FunctionWithSignatures(  # pylint: disable=invalid-name
      self, f1, f2, subst, skip_self=False):
    return booleq.And(
        self.match_Signature_against_FunctionWithSignatures(
            s1, f2, subst, skip_self)
        for s1 in f1.signatures)

  def match_Class_against_Class(self, cls1, cls2, subst):  # pylint: disable=invalid-name
    """Match a pytd.Class against another pytd.Class."""
    implications = []
    cls2_methods = {f.name: f for f in cls2.methods}
    for f1 in cls1.methods:
      if f1.name not in cls2_methods:
        # The class we're matching against doesn't even have this method. This
        # is the easiest and most common case.
        # TODO(kramm): Search base classes
        implication = booleq.FALSE
      else:
        f2 = cls2_methods[f1.name]
        implication = (
            self.match_FunctionWithSignatures_against_FunctionWithSignatures(
                f1, f2, subst, skip_self=True))
      implications.append(implication)
      if implication is booleq.FALSE:
        break
    # TODO(kramm): class attributes
    return booleq.And(implications)
