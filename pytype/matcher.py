"""Matching logic for abstract values."""
import collections
import contextlib
import dataclasses
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pytype import datatypes
from pytype import special_builtins
from pytype import utils
from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.abstract import function
from pytype.overlays import dataclass_overlay
from pytype.overlays import typed_dict
from pytype.overlays import typing_overlay
from pytype.pytd import pep484
from pytype.pytd import pytd_utils
from pytype.typegraph import cfg


log = logging.getLogger(__name__)


_COMPATIBLE_BUILTINS = [
    ("builtins." + compatible_builtin, "builtins." + builtin)
    for compatible_builtin, builtin in pep484.COMPAT_ITEMS
]

_SubstType = datatypes.AliasingDict[str, cfg.Variable]
_ViewType = datatypes.AccessTrackingDict[cfg.Variable, cfg.Binding]

# For _UniqueMatches
_ViewKeyType = Tuple[Tuple[int, Any], ...]
_SubstKeyType = Dict[cfg.Variable, Any]


def _is_callback_protocol(typ):
  return (isinstance(typ, abstract.Class) and typ.is_protocol and
          "__call__" in typ.protocol_attributes)


class NonIterableStrError(Exception):
  """Error for matching `str` against `Iterable[str]`/`Sequence[str]`/etc."""

  def __init__(self, left_type, other_type):
    super().__init__()
    self.left_type = left_type
    self.other_type = other_type


class ProtocolError(Exception):

  def __init__(self, left_type, other_type):
    super().__init__()
    self.left_type = left_type
    self.other_type = other_type


class ProtocolMissingAttributesError(ProtocolError):

  def __init__(self, left_type, other_type, missing):
    super().__init__(left_type, other_type)
    self.missing = missing


class ProtocolTypeError(ProtocolError):

  def __init__(self, left_type, other_type, attribute, actual, expected):
    super().__init__(left_type, other_type)
    self.attribute_name = attribute
    self.actual_type = actual
    self.expected_type = expected


class TypedDictError(Exception):

  def __init__(self, bad, extra, missing):
    super().__init__()
    self.bad = bad
    self.missing = missing
    self.extra = extra


@dataclasses.dataclass
class ErrorDetails:
  protocol: Optional[ProtocolError] = None
  noniterable_str: Optional[NonIterableStrError] = None
  typed_dict: Optional[TypedDictError] = None


@dataclasses.dataclass(eq=True, frozen=True)
class GoodMatch:
  """A correct type/actual value match."""

  view: _ViewType
  subst: _SubstType

  @classmethod
  def default(cls):
    return cls(datatypes.AccessTrackingDict(), datatypes.HashableDict())

  @classmethod
  def merge(cls, old_match, new_match, combined_subst):
    view = datatypes.AccessTrackingDict.merge(old_match.view, new_match.view)
    return cls(view, datatypes.HashableDict(combined_subst))


@dataclasses.dataclass(eq=True, frozen=True)
class BadMatch:
  """An expected type/actual value mismatch."""

  view: _ViewType
  expected: abstract_utils.BadType
  actual: cfg.Variable

  @property
  def actual_binding(self):
    return self.view[self.actual]

  @property
  def error_details(self):
    return self.expected.error_details


@dataclasses.dataclass(eq=True, frozen=True)
class MatchResult:
  """The result of a compute_one_match call."""

  success: bool
  good_matches: List[GoodMatch]
  bad_matches: List[BadMatch]


class _UniqueMatches:
  """A collection of matches that discards duplicates."""

  def __init__(self, node, keep_all_views):
    self._node = node
    self._keep_all_views = keep_all_views
    self._data: Dict[
        _ViewKeyType, List[Tuple[_SubstKeyType, _ViewType, _SubstType]]
    ] = collections.defaultdict(list)

  def insert(self, view, subst):
    """Insert a subst with associated data."""
    if self._keep_all_views:
      view_key = tuple(sorted((k.id, v.data.get_type_key())
                              for k, v in view.accessed_subset.items()))
    else:
      view_key = ()
    subst_key = {k: {v.get_type_key() for v in var.data}
                 for k, var in subst.items()}
    data_item = (subst_key, view, subst)
    for i, prev_data_item in enumerate(self._data[view_key]):
      prev_subst_key, prev_view, prev_subst = prev_data_item
      if all(k in prev_subst_key and subst_key[k] <= prev_subst_key[k]
             for k in subst_key):
        # A previous substitution is a superset of this one, so we do not need
        # to keep this one. We do copy over the view and origins.
        prev_view.update(view)
        for k, v in subst.items():
          prev_subst[k].PasteVariable(v)
        break
      if all(k in subst_key and prev_subst_key[k] <= subst_key[k]
             for k in prev_subst_key):
        # This substitution is a superset of a previous one, so we replace the
        # previous subst with this one. We do copy over the view and origins.
        self._data[view_key][i] = data_item
        view.update(prev_view)
        for k, v in prev_subst.items():
          subst[k].PasteVariable(v)
        break
    else:
      self._data[view_key].append(data_item)

  def unique(self) -> Iterable[Tuple[_ViewType, _SubstType]]:
    for values in self._data.values():
      for _, view, subst in values:
        yield (view, subst)


class _TypeParams:
  """Collection of TypeParameter objects encountered during matching."""

  def __init__(self):
    self.seen = set()
    self._mutually_exclusive = collections.defaultdict(set)

  def add_mutually_exclusive_groups(self, groups):
    """Adds groups of mutually exclusive type parameters.

    For example, [{"T1", "T2"}, {"T3", "T4"}] would mean that the following
    pairs are mutually exclusive: (T1, T3), (T1, T4), (T2, T3), (T2, T4).

    Args:
      groups: The mutually exclusive groups.
    """
    all_params = set.union(*groups)
    for group in groups:
      mutually_exclusive = all_params - group
      for name in group:
        self._mutually_exclusive[name].update(mutually_exclusive)

  def has_mutually_exclusive(self, name, subst):
    """Whether 'subst' has a param that is mutually exclusive with 'name'."""
    return bool(self._mutually_exclusive[name].intersection(subst))


class AbstractMatcher(utils.ContextWeakrefMixin):
  """Matcher for abstract values."""

  # This class is nested inside AbstractMatcher because matcher.py can't be
  # imported in many of the places that the matcher is used.
  class MatchError(Exception):

    def __init__(self, bad_type: abstract_utils.BadType, *args, **kwargs):
      self.bad_type = bad_type
      super().__init__(bad_type, *args, **kwargs)

  def __init__(self, node, ctx):
    super().__init__(ctx)
    self._node = node
    self._protocol_cache = set()
    # Map from (actual value, expected recursive type) pairs to whether matching
    # the value against the type succeeds.
    self._recursive_annots_cache: Dict[
        Tuple[abstract.BaseValue, abstract.BaseValue], bool] = {}
    self._error_subst = None
    self._type_params = _TypeParams()
    self._reset_errors()

  def _reset_errors(self):
    self._protocol_error = None
    self._noniterable_str_error = None
    self._typed_dict_error = None

  @contextlib.contextmanager
  def _track_partially_matched_protocols(self):
    """Context manager for handling the protocol cache.

    Some protocols have methods that return instances of the protocol, e.g.
    Iterator.next returns Iterator. This will cause an infinite loop, which can
    be avoided by tracking partially matched protocols. To prevent collisions,
    keys are removed from the cache as soon as match is completed.

    Yields:
      Into the protocol matching context.
    """
    old_protocol_cache = set(self._protocol_cache)
    yield
    self._protocol_cache = old_protocol_cache

  def _error_details(self):
    """Package up additional error details."""
    return ErrorDetails(
        protocol=self._protocol_error,
        noniterable_str=self._noniterable_str_error,
        typed_dict=self._typed_dict_error
    )

  def _get_bad_type(
      self, name: Optional[str], expected: abstract.BaseValue
  ) -> abstract_utils.BadType:
    return abstract_utils.BadType(
        name=name,
        typ=self.ctx.annotation_utils.sub_one_annotation(
            self._node, expected, [self._error_subst or {}]),
        error_details=self._error_details())

  # TODO(b/63407497): We were previously enforcing --strict_parameter_checks
  # in compute_one_match, which didn't play nicely with overloads. Instead,
  # enforcement should be pushed to callers of compute_matches.
  def compute_matches(
      self, args: List[function.Arg], match_all_views: bool,
      keep_all_views: bool = False,
      alias_map: Optional[datatypes.UnionFind] = None) -> List[GoodMatch]:
    """Compute information about type parameters using one-way unification.

    Given the arguments of a function call, try to find substitutions that match
    them against their expected types.

    Args:
      args: A sequence of function arguments.
      match_all_views: If True, every possible match must succeed for the
        overall match to be considered a success. Otherwise, the overall match
        succeeds as long as at least one possible match succeeds.
      keep_all_views: If True, avoid optimizations that discard views.
      alias_map: Optionally, a datatypes.UnionFind, which stores all the type
        renaming information, mapping of type parameter name to its
        representative.
    Returns:
      A sequence of GoodMatch results containing the computed substitutions.
    Raises:
      MatchError: if any of the arguments does not match its expected type.
    """
    matches = None
    has_self = args and args[0].name == "self"
    for arg in args:
      match_result = self.compute_one_match(
          arg.value, arg.typ, arg.name, match_all_views,
          keep_all_views, alias_map)
      if not match_result.success:
        if matches:
          self._error_subst = matches[0].subst
          bad_param = self._get_bad_type(arg.name, arg.typ)
        else:
          bad_param = match_result.bad_matches[0].expected
        raise self.MatchError(bad_param)
      if keep_all_views or any(m.subst for m in match_result.good_matches):
        matches = self._merge_matches(
            arg.name, arg.typ, matches, match_result.good_matches, has_self)
    return matches if matches else [GoodMatch.default()]

  def compute_one_match(
      self, var, other_type, name=None, match_all_views=True,
      keep_all_views=False, alias_map=None) -> MatchResult:
    """Match a Variable against a type.

    Args:
      var: A cfg.Variable, containing instances.
      other_type: An instance of BaseValue.
      name: Optionally, the variable name.
      match_all_views: If True, every possible match must succeed for the
        overall match to be considered a success. Otherwise, the overall match
        succeeds as long as at least one possible match succeeds.
      keep_all_views: If True, avoid optimizations that discard views.
      alias_map: Optionally, a datatypes.UnionFind, which stores all the type
        renaming information, mapping of type parameter name to its
        representative.
    Returns:
      The match result.
    """
    bad_matches = []
    good_matches = _UniqueMatches(self._node, keep_all_views)
    views = abstract_utils.get_views([var], self._node)
    skip_future = None
    while True:
      try:
        view = views.send(skip_future)
      except StopIteration:
        break
      subst = datatypes.AliasingDict(aliases=alias_map)
      subst = self.match_var_against_type(var, other_type, subst, view)
      if subst is None:
        if self._node.CanHaveCombination(list(view.values())):
          bad_matches.append(BadMatch(
              view=view,
              expected=self._get_bad_type(name, other_type),
              actual=var))
        # To get complete error messages, we need to collect all bad views, so
        # we can't skip any.
        skip_future = False
      else:
        skip_future = True
        good_matches.insert(view, subst)
    good_matches = [GoodMatch(view, datatypes.HashableDict(subst))
                    for view, subst in good_matches.unique()]
    if (good_matches and not match_all_views) or not bad_matches:
      success = True
    elif good_matches:
      # Use HasCombination, which is much more expensive than
      # CanHaveCombination, to re-filter bad matches.
      bad_matches = [m for m in bad_matches
                     if self._node.HasCombination(list(m.view.values()))]
      success = not bad_matches
    else:
      success = False
    return MatchResult(
        success=success, good_matches=good_matches, bad_matches=bad_matches)

  def match_from_mro(self, left, other_type, allow_compat_builtins=True):
    """Checks a type's MRO for a match for a formal type.

    Args:
      left: The type.
      other_type: The formal type.
      allow_compat_builtins: Whether to allow compatible builtins to match -
        e.g., int against float.

    Returns:
      The match, if any, None otherwise.
    """
    for base in left.mro:
      if isinstance(base, abstract.ParameterizedClass):
        base_cls = base.base_cls
      else:
        base_cls = base
      if isinstance(base_cls, abstract.Class):
        if other_type.full_name == base_cls.full_name or (
            isinstance(other_type, abstract.ParameterizedClass) and
            other_type.base_cls is base_cls) or (allow_compat_builtins and (
                (base_cls.full_name,
                 other_type.full_name) in _COMPATIBLE_BUILTINS)):
          return base
      elif isinstance(base_cls, abstract.AMBIGUOUS):
        # Note that this is a different logic than in pytd/type_match.py, which
        # assumes that ambiguous base classes never match, to keep the list of
        # types from exploding. Here, however, we want an instance of, say,
        # "class Foo(Any)" to match against everything.
        return base_cls
      elif isinstance(base_cls, abstract.Empty):
        continue
      else:
        # Ignore other types of base classes (Callable etc.). These typically
        # make it into our system through Union types, since during class
        # construction, only one of the entries in a Union needs to be a valid
        # base class.
        log.warning("Invalid base class %r", base_cls)
        continue

  def match_var_against_type(self, var, other_type, subst, view):
    """Match a variable against a type."""
    self._reset_errors()
    if var.bindings:
      return self._match_value_against_type(view[var], other_type, subst, view)
    else:  # Empty set of values. The "nothing" type.
      if isinstance(other_type, abstract.TupleClass):
        other_type = other_type.get_formal_type_parameter(abstract_utils.T)
      if isinstance(other_type, abstract.Union):
        right_side_options = other_type.options
      else:
        right_side_options = [other_type]
      for right in right_side_options:
        if isinstance(right, abstract.TypeParameter):
          self._type_params.seen.add(right)
          # If we have a union like "K or V" and we match both against
          # nothing, that will fill in both K and V.
          if right.full_name not in subst:
            subst = subst.copy()
            subst[right.full_name] = var.program.NewVariable()
      # If this type is empty, we can match it against anything.
      return subst

  def _match_type_param_against_type_param(self, t1, t2, subst, view):
    """Match a TypeVar against another TypeVar."""
    if t2.constraints:
      assert not t2.bound  # constraints and bounds are mutually exclusive
      # We only check the constraints for t1, not the bound. We wouldn't know
      # all the possible subtypes of a bound, so we can't verify against the
      # constraints even if t1 is bounded.
      if not t1.constraints:
        return None  # t1 is unconstrained, t2 has constraints
      if set(t1.constraints) - set(t2.constraints):
        return None  # t1 is more permissive than t2
    elif t2.bound:
      if t1.bound:
        new_subst = self._instantiate_and_match(t1.bound, t2.bound, subst, view)
        if new_subst is not None:
          return new_subst
      # Even if t1 doesn't have a bound, maybe it's constrained to subtypes of
      # t2's bound.
      if not t1.constraints:
        return None
      for t in t1.constraints:
        new_subst = self._instantiate_and_match(t, t2.bound, subst, view)
        if new_subst is None:
          return None  # a constraint option isn't allowed by the bound
    return subst

  def _match_value_against_type(
      self, value: cfg.Binding, other_type: abstract.BaseValue,
      subst: _SubstType, view: _ViewType
  ) -> Optional[_SubstType]:
    """One-way unify value into pytd type given a substitution.

    Args:
      value: A cfg.Binding.
      other_type: A BaseValue instance.
      subst: The current substitution. This dictionary is not modified.
      view: A mapping of Variable to Value.
    Returns:
      A new (or unmodified original) substitution dict if the matching
      succeeded, None otherwise.
    """
    left = value.data

    # Unwrap Final[T] here
    left = abstract_utils.unwrap_final(left)
    other_type = abstract_utils.unwrap_final(other_type)

    # Make sure we don't recurse infinitely when matching recursive types.
    is_recursive = abstract_utils.is_recursive_annotation(other_type)
    if is_recursive:
      key = (left, other_type)
      if key in self._recursive_annots_cache:
        return subst if self._recursive_annots_cache[key] else None
      self._recursive_annots_cache[key] = True

    subst = self._match_nonfinal_value_against_type(
        left, value, other_type, subst, view)
    if is_recursive:
      self._recursive_annots_cache[key] = subst is not None
    return subst

  def _match_nonfinal_value_against_type(
      self, left: abstract.BaseValue, value: cfg.Binding,
      other_type: abstract.BaseValue, subst: _SubstType,
      view: _ViewType
  ) -> Optional[_SubstType]:
    """Match after unwrapping any `Final` annotations."""
    if left.formal:
      # 'left' contains a TypeParameter. The code under analysis is likely doing
      # some sort of runtime processing of type annotations. We replace all type
      # parameters with 'object' so that they don't match concrete types like
      # 'int' but still match things like 'Any'.
      type_params = self.ctx.annotation_utils.get_type_parameters(left)
      obj_var = self.ctx.convert.primitive_class_instances[object].to_variable(
          self._node)
      left = self.ctx.annotation_utils.sub_one_annotation(
          self._node, left, [{p.full_name: obj_var for p in type_params}])
    assert not left.formal, left

    if isinstance(left, abstract.TypeParameterInstance) and (
        isinstance(left.instance, (abstract.CallableClass,
                                   function.Signature)) or
        left.instance is abstract_utils.DUMMY_CONTAINER):
      if isinstance(other_type, abstract.TypeParameter):
        self._type_params.seen.add(other_type)
        new_subst = self._match_type_param_against_type_param(
            left.param, other_type, subst, view)
        if new_subst is not None:
          subst = new_subst.copy()
          # NOTE: This is pretty imprecise, there might be something better to
          # do here.
          subst[other_type.full_name] = self.ctx.program.NewVariable([], [],
                                                                     self._node)
          return subst
        else:
          left_dummy = left.param.instantiate(self.ctx.root_node,
                                              abstract_utils.DUMMY_CONTAINER)
          right_dummy = left.param.instantiate(self.ctx.root_node,
                                               abstract_utils.DUMMY_CONTAINER)
          self._error_subst = self._merge_substs(subst, [{
              left.param.name: left_dummy, other_type.name: right_dummy}])
          return None
      elif isinstance(left.instance, abstract.CallableClass):
        # We're doing argument-matching against a callable. We flipped the
        # argument types to enforce contravariance, but if the expected type is
        # a type parameter, we need it on the right in order to fill in subst.
        return self._instantiate_and_match(other_type, left.param, subst, view)
      else:
        # We're doing return type matching against a callable. The type on the
        # right isn't a type parameter, so we instantiate the parameter on the
        # left to its upper bound.
        return self._instantiate_and_match(left.param, other_type, subst, view)
    elif isinstance(other_type, abstract.TypeParameter):
      self._type_params.seen.add(other_type)
      for c in other_type.constraints:
        new_subst = self._match_value_against_type(value, c, subst, view)
        if new_subst is not None:
          break
      else:
        if other_type.constraints:
          self._error_subst = subst
          return None
      if other_type.bound:
        new_subst = self._match_value_against_type(
            value, other_type.bound, subst, view)
        if new_subst is None:
          new_subst = {other_type.full_name:
                       other_type.bound.instantiate(
                           self._node, abstract_utils.DUMMY_CONTAINER)}
          self._error_subst = self._merge_substs(subst, [new_subst])
          return None
      new_var, has_error = self._check_type_param_consistency(
          left, value, other_type, subst)
      if has_error:
        self._error_subst = subst
        return None
      subst = subst.copy()
      subst[other_type.full_name] = new_var
      return subst
    elif (isinstance(other_type, typing_overlay.NoReturn) or
          isinstance(left, typing_overlay.NoReturn)):
      # `NoReturn` can only matches itself, `Any`, or `abstract.TypeParameter`.
      # For the latter case, it will be used in byte code `STORE_ANNOTATION`
      # to store the `NoReturn` annotation in a dict.
      if (left == other_type or
          isinstance(other_type, abstract.AMBIGUOUS_OR_EMPTY) or
          isinstance(left, abstract.AMBIGUOUS_OR_EMPTY)):
        return subst
      else:
        return None
    elif isinstance(other_type, abstract.Class):
      # Accumulate substitutions in "subst", or break in case of error:
      return self._match_type_against_type(left, other_type, subst, view)
    elif isinstance(other_type, abstract.Union):
      # If `value` matches a union option that contains no type parameters, it
      # is not allowed to match options that do contain type parameters. For
      # example, for `(x: Optional[T]) -> T`, matching `None` against `x` should
      # not result in `None` being a valid substitution for `T`. We order the
      # options so that ones without type parameters are checked first, so we
      # can break early if any of them match.
      matched = False
      # By sorting first by whether the option contains type parameters and then
      # by its index, we move options without type parameters to the front and
      # otherwise preserve the original order.
      options = sorted(enumerate(other_type.options),
                       key=lambda itm: (itm[1].formal, itm[0]))
      new_substs = []
      type_param_groups = []
      for _, t in options:
        new_subst = self._match_value_against_type(value, t, subst, view)
        if new_subst is None:
          continue
        matched = True
        if isinstance(value.data, abstract.AMBIGUOUS_OR_EMPTY) or t.formal:
          new_substs.append(new_subst)
          type_param_groups.append(set(new_subst).difference(subst))
          continue
        # Since options without type parameters do not modify subst, we can
        # break after the first match rather than finding all matches. We still
        # need to fill in subst with *something* so that
        # annotation_utils.sub_one_annotation can tell that all annotations have
        # been fully matched.
        subst = self._subst_with_type_parameters_from(new_subst, other_type)
        break
      if not matched:
        return None
      if not new_substs:
        return subst
      self._type_params.add_mutually_exclusive_groups(type_param_groups)
      return self._merge_substs(subst, new_substs)
    elif (isinstance(other_type, (abstract.Unknown, abstract.Unsolvable)) or
          isinstance(left, (abstract.Unknown, abstract.Unsolvable))):
      # We can match anything against unknown types, and unknown types against
      # anything.
      assert not isinstance(other_type, abstract.ParameterizedClass)
      return subst
    elif isinstance(other_type, abstract.Empty):
      return self._match_type_against_type(left, other_type, subst, view)
    else:
      log.error("Invalid type: %s", type(other_type))
      return None

  def _check_type_param_consistency(
      self, new_value: abstract.BaseValue, new_value_binding: cfg.Binding,
      t: abstract.TypeParameter, subst: _SubstType
  ) -> Tuple[cfg.Variable, bool]:
    if t.full_name in subst:
      # Merge the two variables.
      new_var = subst[t.full_name].AssignToNewVariable(self._node)
      new_var.AddBinding(new_value, [], self._node)
    else:
      new_var = self.ctx.program.NewVariable()
      new_var.AddBinding(
          self.ctx.convert.get_maybe_abstract_instance(new_value),
          {new_value_binding}, self._node)
    type_key = new_value.get_type_key()
    # Every value with this type key produces the same result when matched
    # against t, so they can all be added to this substitution rather than
    # matched separately.
    for other_value in new_value_binding.variable.bindings:
      if (other_value is not new_value_binding and
          other_value.data.get_type_key() == type_key):
        new_var.AddBinding(other_value.data, {other_value}, self._node)
    if t.constraints:
      new_values = self._discard_ambiguous_values(new_var.data)
      has_error = not self._satisfies_single_type(new_values)
      if not has_error and new_values and len(new_values) < len(new_var.data):
        # We can filter out ambiguous values because we've already found the
        # single concrete type allowed for this variable.
        new_var = self.ctx.program.NewVariable(new_values, [], self._node)
    else:
      if t.full_name in subst:
        has_error = False
        old_values = subst[t.full_name].data
        # If _discard_ambiguous_values does not discard 'new_value', then it is
        # a concrete value that we need to match.
        if old_values and self._discard_ambiguous_values([new_value]):
          old_concrete_values = self._discard_ambiguous_values(old_values)
          # If any of the previous TypeVar values were ambiguous, then we
          # treat the match as a success. Otherwise, 'new_value' needs to match
          # at least one of them.
          if len(old_values) == len(old_concrete_values):
            has_error = True
            for old_value in old_concrete_values:
              if self._satisfies_common_superclass([new_value, old_value]):
                has_error = False
              elif old_value.cls.is_protocol:
                with self._track_partially_matched_protocols():
                  protocol_subst = datatypes.AliasingDict(subst)
                  has_error = self._match_against_protocol(
                      new_value, old_value.cls, protocol_subst, {}) is None
              if not has_error:
                break
      else:
        has_error = not self._satisfies_common_superclass(
            self._discard_ambiguous_values(new_var.data))
    return new_var, has_error

  def _match_type_against_type(self, left, other_type, subst, view):
    """Checks whether a type is compatible with a (formal) type.

    Args:
      left: A type.
      other_type: A formal type. E.g. abstract.Class or abstract.Union.
      subst: The current type parameter assignment.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    if (isinstance(left, abstract.Empty) and
        isinstance(other_type, abstract.Empty)):
      return subst
    elif isinstance(left, abstract.AMBIGUOUS_OR_EMPTY):
      params = self.ctx.annotation_utils.get_type_parameters(other_type)
      if isinstance(left, abstract.Empty):
        value = self.ctx.convert.empty
      else:
        value = self.ctx.convert.unsolvable
      return self._mutate_type_parameters(params, value, subst)
    elif isinstance(left, abstract.Class):
      if (other_type.full_name == "builtins.type" and
          isinstance(other_type, abstract.ParameterizedClass)):
        other_type = other_type.get_formal_type_parameter(abstract_utils.T)
        return self._instantiate_and_match(left, other_type, subst, view)
      elif (other_type.full_name == "typing.Callable" and
            isinstance(other_type, abstract.ParameterizedClass)):
        # TODO(rechen): Check left's constructor against the callable's params.
        other_type = other_type.get_formal_type_parameter(abstract_utils.RET)
        return self._instantiate_and_match(left, other_type, subst, view)
      elif other_type.full_name in [
          "builtins.type", "builtins.object", "typing.Callable",
          "typing.Hashable"]:
        return subst
      elif _is_callback_protocol(other_type):
        return self._match_type_against_callback_protocol(
            left, other_type, subst, view)
      else:
        return self._match_instance_against_type(left, other_type, subst, view)
    elif isinstance(left, abstract.Module):
      if other_type.full_name in [
          "builtins.module", "builtins.object", "types.ModuleType",
          "typing.Hashable"]:
        return subst
      elif (isinstance(other_type, abstract.Class) and
            other_type.has_protocol_base()):
        return self._match_instance_against_type(
            left, other_type, subst, view)
      else:
        return None
    elif isinstance(left, abstract.FUNCTION_TYPES):
      if other_type.full_name == "builtins.object":
        return subst
      elif other_type.full_name == "typing.Callable":
        if not isinstance(other_type, abstract.ParameterizedClass):
          # The callable has no parameters, so any function matches it.
          return subst
        if isinstance(left, abstract.NativeFunction):
          # If we could get the class on which 'left' is defined (perhaps by
          # using bound_class?), we could get the argument and return types
          # from the underlying PyTDFunction, but we wouldn't get much value
          # out of that additional matching, since most NativeFunction objects
          # are magic methods like __getitem__ which aren't likely to be passed
          # as function arguments.
          return subst
        signatures = function.get_signatures(left)
        new_substs = []
        for sig in signatures:
          new_subst = self._match_signature_against_callable(
              sig, other_type, subst, view)
          if new_subst is not None:
            new_substs.append(new_subst)
        if new_substs:
          return self._merge_substs(subst, new_substs)
        else:
          return None
      elif _is_callback_protocol(other_type):
        return self._match_type_against_callback_protocol(
            left, other_type, subst, view)
      else:
        return self._match_type_against_type(
            abstract.Instance(left.cls, self.ctx), other_type, subst, view)
    elif isinstance(left, dataclass_overlay.FieldInstance) and left.default:
      return self._match_all_bindings(left.default, other_type, subst, view)
    elif isinstance(left, abstract.SimpleValue):
      return self._match_instance_against_type(left, other_type, subst, view)
    elif isinstance(left, special_builtins.SuperInstance):
      instance = left.super_obj or abstract.Instance(left.super_cls, self.ctx)
      return self._match_instance_against_type(
          instance, other_type, subst, view)
    elif isinstance(left, abstract.ClassMethod):
      if other_type.full_name in [
          "builtins.classmethod", "builtins.object"]:
        return subst
      return self._match_type_against_type(
          left.to_bound_function(), other_type, subst, view)
    elif isinstance(left, abstract.StaticMethod):
      if other_type.full_name in [
          "builtins.staticmethod", "builtins.object"]:
        return subst
      return self._match_type_against_type(left.method, other_type, subst, view)
    elif isinstance(left, abstract.Union):
      for o in left.options:
        new_subst = self._match_type_against_type(o, other_type, subst, view)
        if new_subst is not None:
          return new_subst
    elif isinstance(left, abstract.TypeParameterInstance):
      if isinstance(left.instance, abstract.BaseValue):
        param = left.instance.get_instance_type_parameter(left.param.name)
        # If left resolves to itself
        # (see tests/test_enums:EnumOverlayTest.test_unique_enum_in_dict),
        # calling _match_all_bindings would lead to an infinite recursion error.
        if param.bindings and not any(v is left for v in param.data):
          return self._match_all_bindings(param, other_type, subst, view)
      return self._instantiate_and_match(left.param, other_type, subst, view)
    else:
      raise NotImplementedError("Matching not implemented for %s against %s" %
                                (type(left), type(other_type)))

  def _match_type_against_callback_protocol(
      self, left, other_type, subst, view):
    """See https://www.python.org/dev/peps/pep-0544/#callback-protocols."""
    _, method_var = self.ctx.attribute_handler.get_attribute(
        self._node, other_type, "__call__")
    if not method_var or not method_var.data or any(
        not isinstance(v, abstract.Function) for v in method_var.data):
      return None
    new_substs = []
    for expected_method in method_var.data:
      signatures = function.get_signatures(expected_method)
      for sig in signatures:
        sig = sig.drop_first_parameter()  # drop `self`
        expected_callable = (self.ctx.pytd_convert.signature_to_callable(sig))
        new_subst = self._match_type_against_type(
            left, expected_callable, subst, view)
        if new_subst is not None:
          # For a set of overloaded signatures, only one needs to match.
          new_substs.append(new_subst)
          break
      else:
        # Every method_var binding must have a matching signature.
        return None
    return self._merge_substs(subst, new_substs)

  def _mutate_type_parameters(self, params, value, subst):
    self._type_params.seen.update(params)
    new_subst = {p.full_name: value.to_variable(self._node) for p in params}
    return self._merge_substs(subst, [new_subst])

  def _get_param_matcher(self, callable_type):
    """Helper for matching the parameters of a callable.

    Args:
      callable_type: The callable being matched against.

    Returns:
      A special param matcher: (left, right, subst) -> Optional[subst].
        left: An argument to be matched against a parameter of callable_type.
        right: A parameter of callable_type.
        subst: The current substitution dictionary.
      If the matcher returns a non-None subst dict, then the match has succeeded
      via special matching rules for single TypeVars. Otherwise, the caller
      should next attempt normal matching on the inputs. (See
      _match_signature_against_callable for a usage example.)
    """
    # Any type parameter should match an unconstrained, unbounded type parameter
    # that appears exactly once in a callable, in order for matching to succeed
    # in cases like:
    #   def f(x: AnyStr) -> AnyStr: ...
    #   def g(f: Callable[[T], Any], x: T): ...
    #   g(f)
    # Normally, we would treat the `T` in `Callable[[T], Any]` as meaning that
    # the callable must accept any argument, but here, it means that the
    # argument must be the same type as `x`.
    callable_param_count = collections.Counter(
        self.ctx.annotation_utils.get_type_parameters(callable_type))
    if isinstance(callable_type, abstract.CallableClass):
      # In CallableClass, type parameters in arguments are double-counted
      # because ARGS contains the union of the individual arguments.
      callable_param_count.subtract(
          self.ctx.annotation_utils.get_type_parameters(
              callable_type.get_formal_type_parameter(abstract_utils.ARGS)))
    def match(left, right, subst):
      if (not isinstance(left, abstract.TypeParameter) or
          not isinstance(right, abstract.TypeParameter) or
          right.constraints or right.bound or callable_param_count[right] != 1):
        return None
      self._type_params.seen.add(right)
      subst = subst.copy()
      # We don't know what to fill in here, since we have a TypeVar matching a
      # TypeVar, but we have to add *something* to indicate the match succeeded.
      subst[right.full_name] = self.ctx.program.NewVariable(
          [self.ctx.convert.empty], [], self._node)
      return subst
    return match

  def _match_signature_against_callable(self, sig, other_type, subst, view):
    """Match a function.Signature against a parameterized callable."""
    # a special type param against type param matcher that takes priority over
    # normal matching
    param_match = self._get_param_matcher(other_type)
    ret_type = sig.annotations.get("return", self.ctx.convert.unsolvable)
    other_ret_type = other_type.get_formal_type_parameter(abstract_utils.RET)
    new_subst = param_match(ret_type, other_ret_type, subst)
    if new_subst is None:
      subst = self._instantiate_and_match(
          ret_type, other_ret_type, subst, view, container=sig)
      if subst is None:
        return subst
    else:
      subst = new_subst
    if not isinstance(other_type, abstract.CallableClass):
      # other_type does not specify argument types, so any arguments are fine.
      return subst
    if sig.mandatory_param_count() > other_type.num_args:
      return None
    max_argcount = sig.maximum_param_count()
    if max_argcount is not None and max_argcount < other_type.num_args:
      return None
    for name, expected_arg in zip(sig.param_names,
                                  (other_type.formal_type_parameters[i]
                                   for i in range(other_type.num_args))):
      actual_arg = sig.annotations.get(name, self.ctx.convert.unsolvable)
      new_subst = param_match(actual_arg, expected_arg, subst)
      if new_subst is None:
        # Flip actual and expected, since argument types are contravariant.
        subst = self._instantiate_and_match(
            expected_arg, actual_arg, subst, view, container=other_type)
        if subst is None:
          return None
      else:
        subst = new_subst
    return subst

  def _merge_substs(self, subst, new_substs):
    subst = subst.copy()
    for new_subst in new_substs:
      for name, var in new_subst.items():
        if name not in subst:
          subst[name] = var
        elif subst[name] is not var:
          subst[name].PasteVariable(var)
    return subst

  def _merge_matches(
      self, name: str, formal: abstract.BaseValue,
      old_matches: Optional[List[GoodMatch]], new_matches: List[GoodMatch],
      has_self: bool) -> List[GoodMatch]:
    if not old_matches:
      return new_matches
    if not new_matches:
      return old_matches
    combined_matches = []
    matched = False
    bad_param = None
    for new_match in new_matches:
      cur_types = datatypes.AliasingDict(
          {t.full_name: t for t in self._type_params.seen},
          aliases=new_match.subst.aliases)
      for old_match in old_matches:
        combined_subst = self._match_subst_against_subst(
            old_match.subst, new_match.subst, cur_types, has_self)
        if combined_subst is None:
          if not bad_param:
            self._error_subst = old_match.subst
            bad_param = self._get_bad_type(name, formal)
          continue
        combined_matches.append(
            GoodMatch.merge(old_match, new_match, combined_subst))
        matched = True
    if not matched:
      raise self.MatchError(bad_param)
    return combined_matches

  def _match_subst_against_subst(
      self, old_subst, new_subst, type_param_map, has_self):
    subst = datatypes.AliasingDict(aliases=old_subst.aliases)
    for t in new_subst:
      if t not in old_subst or not old_subst[t].bindings:
        subst[t] = new_subst[t]
        continue
      if not new_subst[t].bindings:
        subst[t] = old_subst[t]
        continue
      # Any type parameters in old subst that were matched from a 'self' arg are
      # class parameters whose values have been declared by the user, e.g.:
      #   x = Container[int](__any_object__)
      # We should keep the 'int' value rather than using Union[int, Unknown].
      # Note that we still need to check that the new values are consistent with
      # the old ones.
      keep_old_values = has_self and any(not isinstance(v, abstract.Empty)
                                         for v in old_subst[t].data)
      for b1 in old_subst[t].bindings:
        for b2 in new_subst[t].bindings:
          new_var, has_error = self._check_type_param_consistency(
              b2.data, b2, type_param_map[t],
              old_subst.copy(t=b1.AssignToNewVariable(self._node)))
          # If new_subst contains a TypeVar that is mutually exclusive with t,
          # then we can ignore this error because it is legal for t to not be
          # present in new_subst.
          ignore_error = self._type_params.has_mutually_exclusive(t, new_subst)
          if has_error and not ignore_error:
            continue
          keep_old = keep_old_values or ignore_error
          if t not in subst:
            subst[t] = old_subst[t] if keep_old else new_var
          elif not keep_old:
            subst[t].PasteVariable(new_var, self._node)
      if t not in subst:
        return None
    for t in old_subst:
      if t not in subst:
        subst[t] = old_subst[t]
    return subst

  def _instantiate_and_match(self, left, other_type, subst, view,
                             container=None):
    """Instantiate and match an abstract value."""
    instance = left.instantiate(self._node, container=container)
    return self._match_all_bindings(instance, other_type, subst, view)

  def _match_all_bindings(self, var, other_type, subst, view):
    """Matches all of var's bindings against other_type."""
    new_substs = []
    for new_view in abstract_utils.get_views([var], self._node):
      # When new_view and view have entries in common, we want to use the
      # entries from the old view.
      new_view.update(view)
      new_subst = self.match_var_against_type(var, other_type, subst, new_view)
      if new_subst is not None:
        new_substs.append(new_subst)
    if new_substs:
      return self._merge_substs(subst, new_substs)
    elif var.Filter(self._node):
      # Filter() is expensive, so we delay calling it until we need to check the
      # visibility of a failed match.
      return None
    else:
      # If no matches, successful or not, are visible, we assume success and
      # manually fill in the substitution dictionary.
      return self._subst_with_type_parameters_from(subst, other_type)

  def _match_instance_against_type(self, left, other_type, subst, view):
    """Checks whether an instance of a type is compatible with a (formal) type.

    Args:
      left: An instance of a type.
      other_type: A formal type. E.g. abstract.Class or abstract.Union.
      subst: The current type parameter assignment.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    if isinstance(other_type, abstract.LiteralClass):
      other_value = other_type.value
      if isinstance(left, abstract.ConcreteValue) and isinstance(
          other_value, abstract.ConcreteValue):
        return subst if left.pyval == other_value.pyval else None
      elif (isinstance(left, abstract.Instance) and left.cls.is_enum and
            isinstance(other_value, abstract.Instance) and
            other_value.cls.is_enum):
        names_match = left.name == other_value.name
        clses_match = left.cls == other_value.cls
        return subst if names_match and clses_match else None
      else:
        return None
    elif isinstance(other_type, typed_dict.TypedDictClass):
      if not self._match_dict_against_typed_dict(left, other_type):
        return None
      return subst
    elif isinstance(other_type, abstract.Class):
      if not self._satisfies_noniterable_str(left.cls, other_type):
        self._noniterable_str_error = NonIterableStrError(left.cls, other_type)
        return None
      base = self.match_from_mro(left.cls, other_type)
      if base is None:
        if other_type.is_protocol:
          with self._track_partially_matched_protocols():
            return self._match_against_protocol(left, other_type, subst, view)
        elif other_type.has_protocol_base():
          # 'is_protocol' returns True only if the protocol has at least one
          # attribute that needs checking. In the edge case of a protocol being
          # completely empty, everything should match.
          return subst
        return None
      elif isinstance(base, abstract.AMBIGUOUS_OR_EMPTY):
        # An ambiguous base class matches everything.
        # _match_maybe_parameterized_instance puts the right params in `subst`.
        return self._match_maybe_parameterized_instance(
            base, left, other_type, subst, view)
      else:
        return self._match_instance(base, left, other_type, subst, view)
    elif isinstance(other_type, abstract.Empty):
      return None
    else:
      raise NotImplementedError(
          f"Can't match {left!r} against {other_type!r}")

  def _match_instance(self, left, instance, other_type, subst, view):
    """Used by _match_instance_against_type. Matches one MRO entry.

    Called after the instance has been successfully matched against a
    formal type to do any remaining matching special to the type.

    Args:
      left: The instance type, which may be different from instance.cls
        depending on where in the mro the match happened.
      instance: The instance.
      other_type: The formal type that was successfully matched against.
      subst: The current type parameter assignment.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    if (isinstance(left, abstract.TupleClass) or
        isinstance(instance, abstract.Tuple) or
        isinstance(other_type, abstract.TupleClass)):
      return self._match_heterogeneous_tuple_instance(
          left, instance, other_type, subst, view)
    elif (isinstance(left, abstract.CallableClass) or
          isinstance(other_type, abstract.CallableClass)):
      return self._match_callable_instance(
          left, instance, other_type, subst, view)
    return self._match_maybe_parameterized_instance(
        left, instance, other_type, subst, view)

  def _match_maybe_parameterized_instance(self, left, instance, other_type,
                                          subst, view):
    """Used by _match_instance."""
    def assert_classes_match(cls1, cls2):
      # We need the somewhat complex assertion below to allow internal
      # subclasses of abstract classes to act as their base classes.
      assert isinstance(cls1, type(cls2)) or isinstance(cls2, type(cls1))

    if isinstance(other_type, abstract.ParameterizedClass):
      if isinstance(left, abstract.ParameterizedClass):
        assert_classes_match(left.base_cls, other_type.base_cls)
      elif isinstance(left, abstract.AMBIGUOUS_OR_EMPTY):
        return self._subst_with_type_parameters_from(subst, other_type)
      else:
        # Parameterized classes can rename type parameters, which is why we need
        # the instance type for lookup. But if the instance type is not
        # parameterized, then it is safe to use the param names in other_type.
        assert_classes_match(left, other_type.base_cls)
        left = other_type
      for type_param in left.template:
        class_param = other_type.get_formal_type_parameter(type_param.name)
        instance_param = instance.get_instance_type_parameter(
            type_param.full_name, self._node)
        instance_type_param = left.get_formal_type_parameter(type_param.name)
        if (not instance_param.bindings and isinstance(
            instance_type_param, abstract.TypeParameter) and
            instance_type_param.name != type_param.name):
          # This type parameter was renamed!
          instance_param = instance.get_instance_type_parameter(
              type_param.full_name, self._node)
        if instance_param.bindings and instance_param not in view:
          binding, = instance_param.bindings
          assert isinstance(binding.data, abstract.Unsolvable), binding.data
          view = view.copy()
          view[instance_param] = binding
        subst = self.match_var_against_type(instance_param, class_param,
                                            subst, view)
        if subst is None:
          return None
    return subst

  def _match_heterogeneous_tuple_instance(self, left, instance, other_type,
                                          subst, view):
    """Used by _match_instance."""
    if isinstance(instance, abstract.Tuple):
      if isinstance(other_type, abstract.TupleClass):
        if instance.tuple_length == other_type.tuple_length:
          for i in range(instance.tuple_length):
            instance_param = instance.pyval[i]
            class_param = other_type.formal_type_parameters[i]
            subst = self.match_var_against_type(
                instance_param, class_param, subst, view)
            if subst is None:
              return None
        else:
          return None
      elif isinstance(other_type, abstract.ParameterizedClass):
        class_param = other_type.get_formal_type_parameter(abstract_utils.T)
        # Copying the parameters directly preserves literal values. In most
        # cases, we shouldn't assume that objects with the same type have the
        # same value, but substituting from a concrete tuple into an abstract
        # one typically happens during operations like tuple iteration, when
        # values are indeed preserved. See
        # tests.test_typing2.LiteralTest.test_iterate for a case in which
        # this is important.
        copy_params_directly = (
            class_param.full_name == f"{left.full_name}.{abstract_utils.T}")
        # If we merge in the new substitution results prematurely, then we'll
        # accidentally violate _satisfies_common_superclass.
        new_substs = []
        for instance_param in instance.pyval:
          if copy_params_directly and instance_param.bindings:
            new_subst = {class_param.full_name: view[
                instance_param].AssignToNewVariable(self._node)}
          else:
            new_subst = self.match_var_against_type(
                instance_param, class_param, subst, view)
            if new_subst is None:
              return None
          new_substs.append(new_subst)
        if new_substs:
          subst = self._merge_substs(subst, new_substs)
      if not instance.pyval:
        # This call puts the right param names (with empty values) into subst.
        subst = self._match_maybe_parameterized_instance(
            left, instance, other_type, subst, view)
    elif isinstance(left, abstract.TupleClass):
      # We have an instance of a subclass of tuple.
      return self._instantiate_and_match(left, other_type, subst, view)
    else:
      assert isinstance(other_type, abstract.TupleClass)
      if isinstance(instance, abstract.SimpleValue):
        instance_param = instance.get_instance_type_parameter(
            abstract_utils.T, self._node)
        for i in range(other_type.tuple_length):
          class_param = other_type.formal_type_parameters[i]
          subst = self.match_var_against_type(
              instance_param, class_param, subst, view)
          if subst is None:
            return None
    return subst

  def _match_callable_instance(self, left, instance, other_type, subst, view):
    """Used by _match_instance."""
    if (not isinstance(instance, abstract.SimpleValue) or
        not isinstance(other_type, abstract.ParameterizedClass)):
      return subst
    subst = self.match_var_against_type(
        instance.get_instance_type_parameter(abstract_utils.RET, self._node),
        other_type.get_formal_type_parameter(abstract_utils.RET), subst, view)
    if subst is None:
      return None
    if (not isinstance(left, abstract.CallableClass) or
        not isinstance(other_type, abstract.CallableClass)):
      # One of the types doesn't specify arg types, so no need to check them.
      return subst
    if left.num_args != other_type.num_args:
      return None
    param_match = self._get_param_matcher(other_type)
    for i in range(left.num_args):
      left_arg = left.formal_type_parameters[i]
      right_arg = other_type.formal_type_parameters[i]
      new_subst = param_match(left_arg, right_arg, subst)
      if new_subst is None:
        # Flip actual and expected to enforce contravariance of argument types.
        subst = self._instantiate_and_match(
            right_arg, left_arg, subst, view, container=other_type)
      else:
        subst = new_subst
      if subst is None:
        return None
    return subst

  def _match_dict_against_typed_dict(
      self, left: abstract.BaseValue, other_type: typed_dict.TypedDictClass
  ) -> bool:
    if not isinstance(left, abstract.Dict):
      return False
    missing, extra = other_type.props.check_keys(left.pyval.keys())
    bad = []
    fields = other_type.props.fields
    for k, v in left.pyval.items():
      if k not in fields:
        continue
      typ = abstract_utils.get_atomic_value(fields[k])
      match_result = self.compute_one_match(v, typ)
      if not match_result.success:
        bad.append((k, match_result.bad_matches))
    if missing or extra or bad:
      self._typed_dict_error = TypedDictError(bad, extra, missing)
      return False
    return True

  def _get_attribute_names(self, left):
    """Get the attributes implemented (or implicit) on a type."""
    left_attributes = set()
    if isinstance(left, abstract.Module):
      _ = left.items()  # loads all attributes into members
    if isinstance(left, abstract.SimpleValue):
      left_attributes.update(left.members)
    left_attributes.update(*(cls.get_own_attributes() for cls in left.cls.mro
                             if isinstance(cls, abstract.Class)))
    if "__getitem__" in left_attributes and "__iter__" not in left_attributes:
      # If a class has a __getitem__ method, it also (implicitly) has a
      # __iter__: Python will emulate __iter__ by calling __getitem__ with
      # increasing integers until it throws IndexError.
      left_attributes.add("__iter__")
    return left_attributes

  def _match_against_protocol(self, left, other_type, subst, view):
    """Checks whether a type is compatible with a protocol.

    Args:
      left: An instance of a type.
      other_type: A protocol.
      subst: The current type parameter assignment.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    if isinstance(left.cls, abstract.AMBIGUOUS_OR_EMPTY):
      return subst
    elif left.cls.is_dynamic:  # pytype: disable=attribute-error
      return self._subst_with_type_parameters_from(subst, other_type)
    elif (self.ctx.options.mapping_is_not_sequence and
          other_type.full_name == "typing.Sequence" and
          any(cls.full_name == "typing.Mapping" for cls in left.cls.mro)):
      # A mapping should not be considered a sequence, even though pytype says
      # that dict[int | slice, str] satisfies the Sequence[str] protocol:
      # https://docs.python.org/3/c-api/sequence.html#c.PySequence_Check
      return None
    left_attributes = self._get_attribute_names(left)
    missing = other_type.protocol_attributes - left_attributes
    if missing:  # not all protocol attributes are implemented by 'left'
      self._protocol_error = ProtocolMissingAttributesError(
          left.cls, other_type, missing)
      return None
    key = (left.cls, other_type)
    if key in self._protocol_cache:
      return subst
    self._protocol_cache.add(key)
    new_substs = []
    for attribute in other_type.protocol_attributes:
      new_subst = self._match_protocol_attribute(
          left, other_type, attribute, subst, view)
      if new_subst is None:
        # _match_protocol_attribute already set _protocol_error.
        return None
      new_substs.append(new_subst)
    return self._merge_substs(subst, new_substs)

  def _get_attribute_for_protocol_matching(self, cls, name, instance=None):
    # For protocol matching, we want to look up attributes on classes (not
    # instances) so that we get unbound methods. This means that we have to
    # manually call __get__ on property instances
    _, attribute = self.ctx.attribute_handler.get_attribute(
        self._node, cls, name, cls.to_binding(self._node))
    if not attribute:
      return attribute
    elif any(isinstance(attr, special_builtins.PropertyInstance)
             for attr in attribute.data):
      return self._resolve_property_attribute(cls, attribute, instance)
    else:
      return attribute

  def _resolve_property_attribute(self, cls, attribute, instance):
    instance = instance or abstract.Instance(cls, self.ctx)
    resolved_attribute = self.ctx.program.NewVariable()
    for b in attribute.bindings:
      if isinstance(b.data, special_builtins.PropertyInstance):
        fget = self.ctx.vm.bind_method(self._node, b.data.fget,
                                       instance.to_variable(self._node))
        _, ret = function.call_function(self.ctx, self._node, fget,
                                        function.Args(()))
        resolved_attribute.PasteVariable(ret)
      else:
        resolved_attribute.PasteBinding(b)
    return resolved_attribute

  def _get_type(self, value):
    cls = value.cls
    if (not isinstance(cls, (abstract.PyTDClass, abstract.InterpreterClass)) or
        not cls.template):
      return cls
    parameters = {}
    for param in cls.template:
      param_value = value.get_instance_type_parameter(param.name)
      types = list(filter(None, (self._get_type(v) for v in param_value.data)))
      if not types:
        break
      parameters[param.name] = self.ctx.convert.merge_values(types)
    else:
      # If 'value' provides non-empty values for all of its class's parameters,
      # then we construct a ParameterizedClass so that the parameter values are
      # considered in matching.
      return abstract.ParameterizedClass(cls, parameters, self.ctx)
    return cls

  def _get_attribute_types(self, other_type, attribute):
    if not abstract_utils.is_callable(attribute):
      typ = self._get_type(attribute)
      if typ:
        yield typ
      return
    converter = self.ctx.pytd_convert
    for signature in function.get_signatures(attribute):
      callable_signature = converter.signature_to_callable(signature)
      if isinstance(callable_signature, abstract.CallableClass):
        # Prevent the matcher from trying to enforce contravariance on 'self'.
        callable_signature.formal_type_parameters[0] = (
            self.ctx.convert.unsolvable)
      if isinstance(other_type, abstract.ParameterizedClass):
        if isinstance(other_type.base_cls, abstract.Class):
          aliases = other_type.base_cls.all_formal_type_parameters.aliases
        else:
          aliases = None
        annotation_subst = datatypes.AliasingDict(aliases=aliases)
        for (param, value) in other_type.get_formal_type_parameters().items():
          annotation_subst[param] = value.instantiate(
              self._node, abstract_utils.DUMMY_CONTAINER)
        callable_signature = self.ctx.annotation_utils.sub_one_annotation(
            self._node, callable_signature, [annotation_subst])
      yield callable_signature

  def _match_protocol_attribute(self, left, other_type, attribute, subst, view):
    """Checks whether left and other_type are compatible in the given attribute.

    Args:
      left: An instance of a type.
      other_type: A protocol.
      attribute: An attribute name.
      subst: The current type parameter assignment.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    left_attribute = self._get_attribute_for_protocol_matching(
        left.cls, attribute, left)
    if left_attribute is None:
      if attribute == "__iter__":
        # See _get_attribute_names: left has an implicit __iter__ method
        # implemented using __getitem__ under the hood.
        left_attribute = self.ctx.convert.constant_to_var(
            pytd_utils.DummyMethod("__iter__", "self"))
      else:
        _, left_attribute = self.ctx.attribute_handler.get_attribute(
            self._node, left, attribute)
    assert left_attribute
    protocol_attribute_var = self._get_attribute_for_protocol_matching(
        other_type, attribute)
    if (any(abstract_utils.is_callable(v) for v in left_attribute.data) and
        all(abstract_utils.is_callable(protocol_attribute)
            for protocol_attribute in protocol_attribute_var.data) and
        not isinstance(other_type, abstract.ParameterizedClass)):
      # TODO(rechen): Even if other_type isn't parameterized, we should run
      # _match_protocol_attribute to catch mismatches in method signatures.
      return subst
    # Every binding of left_attribute needs to match at least one binding of
    # protocol_attribute_var.
    new_substs = []
    for new_view in abstract_utils.get_views([left_attribute], self._node):
      new_view.update(view)
      bad_matches = []
      for protocol_attribute in protocol_attribute_var.data:
        # For this binding of left_attribute to match this binding of
        # protocol_attribute_var, *all* options in protocol_attribute_types need
        # to match.
        protocol_attribute_types = list(
            self._get_attribute_types(other_type, protocol_attribute))
        for protocol_attribute_type in protocol_attribute_types:
          match_result = self.match_var_against_type(
              left_attribute, protocol_attribute_type, subst, new_view)
          if match_result is None:
            bad_matches.append(
                (new_view[left_attribute].data, protocol_attribute))
            break
          else:
            new_substs.append(match_result)
        else:
          # We've successfully matched all options in protocol_attribute_types.
          break
      else:
        # This binding of left_attribute has not matched any binding of
        # protocol_attribute_var.
        bad_left, bad_right = zip(*bad_matches)
        self._protocol_error = ProtocolTypeError(
            left.cls, other_type, attribute,
            self.ctx.convert.merge_values(bad_left),
            self.ctx.convert.merge_values(bad_right))
        return None
    return self._merge_substs(subst, new_substs)

  def _discard_ambiguous_values(self, values):
    # TODO(rechen): For type parameter instances, we should extract the concrete
    # value from v.instance so that we can check it, rather than ignoring the
    # value altogether.
    concrete_values = []
    for v in values:
      # TODO(b/200220895): This is probably wrong; we should expand unions
      # instead of ignoring them.
      if not isinstance(v, (abstract.AMBIGUOUS_OR_EMPTY, abstract.Union,
                            abstract.TypeParameterInstance)):
        if not isinstance(v.cls, abstract.AMBIGUOUS_OR_EMPTY):
          concrete_values.append(v)
    return concrete_values

  def _satisfies_single_type(self, values):
    """Enforce that the variable contains only one concrete type."""
    class_names = {v.cls.full_name for v in values}
    for compat_name, name in _COMPATIBLE_BUILTINS:
      if {compat_name, name} <= class_names:
        class_names.remove(compat_name)
    # We require all occurrences to be of the same type, no subtyping allowed.
    return len(class_names) <= 1

  def _satisfies_common_superclass(self, values):
    """Enforce that the variable's values share a superclass below object."""
    common_classes = None
    object_in_values = False
    for v in values:
      object_in_values |= v.cls == self.ctx.convert.object_type
      superclasses = {c.full_name for c in v.cls.mro}
      for compat_name, name in _COMPATIBLE_BUILTINS:
        if compat_name in superclasses:
          superclasses.add(name)
      if common_classes is None:
        common_classes = superclasses
      else:
        common_classes = common_classes.intersection(superclasses)
    if object_in_values:
      ignored_superclasses = {}
    else:
      ignored_superclasses = {"builtins.object",
                              "typing.Generic",
                              "typing.Protocol"}
    if values:
      assert common_classes is not None
      if common_classes.issubset(ignored_superclasses):
        return False
    return True

  def _satisfies_noniterable_str(self, left, other_type):
    """Enforce a str to NOT be matched against a conflicting iterable type."""
    conflicting_iter_types = ["typing.Iterable", "typing.Sequence",
                              "typing.Collection", "typing.Container",]
    str_types = ["builtins.str", "builtins.unicode",]

    if (other_type.full_name not in conflicting_iter_types
        or left.full_name not in str_types):
      return True  # Reject uninterested type combinations
    if isinstance(other_type, abstract.ParameterizedClass):
      type_param = other_type.get_formal_type_parameter("_T").full_name
      return type_param not in str_types

    return True  # Don't enforce against Iterable[Any]

  def _subst_with_type_parameters_from(self, subst, typ):
    subst = subst.copy()
    for param in self.ctx.annotation_utils.get_type_parameters(typ):
      self._type_params.seen.add(param)
      if param.full_name not in subst:
        subst[param.full_name] = self.ctx.convert.empty.to_variable(self._node)
    return subst
