"""Matching logic for abstract values."""
import collections
import contextlib
import logging

from pytype import abstract
from pytype import abstract_utils
from pytype import compat
from pytype import datatypes
from pytype import function
from pytype import mixin
from pytype import special_builtins
from pytype import utils
from pytype.overlays import dataclass_overlay
from pytype.overlays import typing_overlay
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd.parse import parser_constants


log = logging.getLogger(__name__)


_COMPATIBLE_BUILTINS = [
    ("__builtin__." + compatible_builtin, "__builtin__." + builtin)
    for compatible_builtin, builtin in pep484.COMPAT_ITEMS
]


def _is_callback_protocol(typ):
  return (isinstance(typ, mixin.Class) and typ.is_protocol and
          "__call__" in typ.protocol_methods)


class AbstractMatcher(utils.VirtualMachineWeakrefMixin):
  """Matcher for abstract values."""

  def __init__(self, vm):
    super(AbstractMatcher, self).__init__(vm)
    self._protocol_cache = set()

  def _set_error_subst(self, subst):
    """Set the substitution used by compute_subst in the event of an error."""
    self._error_subst = subst

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

  def compute_subst(self, node, formal_args, arg_dict, view, alias_map=None):
    """Compute information about type parameters using one-way unification.

    Given the arguments of a function call, try to find a substitution that
    matches them against the specified formal parameters.

    Args:
      node: The current CFG node.
      formal_args: An iterable of (name, value) pairs of formal arguments.
      arg_dict: A map of strings to pytd.Bindings instances.
      view: A mapping of Variable to Value.
      alias_map: Optionally, a datatypes.UnionFind, which stores all the type
        renaming information, mapping of type parameter name to its
        representative.
    Returns:
      A tuple (subst, name), with "subst" the datatypes.HashableDict if we found
      a working substition, None otherwise, and "name" the bad parameter in case
      subst=None.
    """
    if not arg_dict:
      # A call with no arguments always succeeds.
      assert not formal_args
      return datatypes.AliasingDict(), None
    subst = datatypes.AliasingDict()
    if alias_map:
      subst.uf = alias_map
    self._set_error_subst(None)
    for name, formal in formal_args:
      actual = arg_dict[name]
      subst = self._match_value_against_type(actual, formal, subst, node, view)
      if subst is None:
        formal = self.vm.annotations_util.sub_one_annotation(
            node, formal, [self._error_subst or {}])
        return None, function.BadParam(name=name, expected=formal)
    return datatypes.HashableDict(subst), None

  def bad_matches(self, var, other_type, node):
    """Match a Variable against a type. Return views that don't match.

    Args:
      var: A cfg.Variable, containing instances.
      other_type: An instance of AtomicAbstractValue.
      node: A cfg.CFGNode. The position in the CFG from which we "observe" the
        match.
    Returns:
      A list of all the views of var that didn't match.
    """
    bad = []
    if (var.data == [self.vm.convert.unsolvable] or
        other_type == self.vm.convert.unsolvable):
      # An unsolvable matches everything. Since bad_matches doesn't need to
      # compute substitutions, we can return immediately.
      return bad
    views = abstract_utils.get_views([var], node)
    skip_future = None
    while True:
      try:
        view = views.send(skip_future)
      except StopIteration:
        break
      if self.match_var_against_type(var, other_type, {}, node, view) is None:
        if node.HasCombination(list(view.values())):
          bad.append(view)
        # To get complete error messages, we need to collect all bad views, so
        # we can't skip any.
        skip_future = False
      else:
        skip_future = True
    return bad

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
      if isinstance(base_cls, mixin.Class):
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

  def match_var_against_type(self, var, other_type, subst, node, view):
    """Match a variable against a type."""
    if var.bindings:
      return self._match_value_against_type(
          view[var], other_type, subst, node, view)
    else:  # Empty set of values. The "nothing" type.
      if isinstance(other_type, abstract.TupleClass):
        other_type = other_type.get_formal_type_parameter(abstract_utils.T)
      if isinstance(other_type, abstract.Union):
        right_side_options = other_type.options
      else:
        right_side_options = [other_type]
      for right in right_side_options:
        if isinstance(right, abstract.TypeParameter):
          # If we have a union like "K or V" and we match both against
          # nothing, that will fill in both K and V.
          if right.full_name not in subst:
            subst = subst.copy()
            subst[right.full_name] = var.program.NewVariable()
      # If this type is empty, we can match it against anything.
      return subst

  def _match_type_param_against_type_param(self, t1, t2, subst, node, view):
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
        new_subst = self._instantiate_and_match(t1.bound, t2.bound,
                                                subst, node, view)
        if new_subst is not None:
          return new_subst
      # Even if t1 doesn't have a bound, maybe it's constrained to subtypes of
      # t2's bound.
      if not t1.constraints:
        return None
      for t in t1.constraints:
        new_subst = self._instantiate_and_match(t, t2.bound,
                                                subst, node, view)
        if new_subst is None:
          return None  # a constraint option isn't allowed by the bound
    return subst

  def _match_value_against_type(self, value, other_type, subst, node, view):
    """One-way unify value into pytd type given a substitution.

    Args:
      value: A cfg.Binding.
      other_type: An AtomicAbstractValue instance.
      subst: The current substitution. This dictionary is not modified.
      node: Current location (CFG node)
      view: A mapping of Variable to Value.
    Returns:
      A new (or unmodified original) substitution dict if the matching succeded,
      None otherwise.
    """
    left = value.data
    assert isinstance(left, abstract.AtomicAbstractValue), left
    assert not left.formal, left
    assert isinstance(other_type, abstract.AtomicAbstractValue), other_type

    if isinstance(left, abstract.TypeParameterInstance) and (
        isinstance(left.instance, (abstract.CallableClass,
                                   function.Signature))):
      if isinstance(other_type, abstract.TypeParameter):
        new_subst = self._match_type_param_against_type_param(
            left.param, other_type, subst, node, view)
        if new_subst is not None:
          subst = new_subst.copy()
          # TODO(kramm): Can we put in something more precise?
          subst[other_type.full_name] = node.program.NewVariable([], [], node)
          return subst
        else:
          left_dummy = left.param.instantiate(
              self.vm.root_cfg_node, abstract_utils.DUMMY_CONTAINER)
          right_dummy = left.param.instantiate(
              self.vm.root_cfg_node, abstract_utils.DUMMY_CONTAINER)
          self._set_error_subst(
              self._merge_substs(subst, [{
                  left.param.name: left_dummy,
                  other_type.name: right_dummy}]))
          return None
      elif isinstance(left.instance, abstract.CallableClass):
        # We're doing argument-matching against a callable. We flipped the
        # argument types to enforce contravariance, but if the expected type is
        # a type parameter, we need it on the right in order to fill in subst.
        return self._instantiate_and_match(
            other_type, left.param, subst, node, view)
      else:
        # We're doing return type matching against a callable. The type on the
        # right isn't a type parameter, so we instantiate the parameter on the
        # left to its upper bound.
        return self._instantiate_and_match(
            left.param, other_type, subst, node, view)
    elif isinstance(other_type, abstract.TypeParameter):
      for c in other_type.constraints:
        new_subst = self._match_value_against_type(value, c, subst, node, view)
        if new_subst is not None:
          break
      else:
        if other_type.constraints:
          self._set_error_subst(subst)
          return None
      if other_type.bound:
        new_subst = self._match_value_against_type(
            value, other_type.bound, subst, node, view)
        if new_subst is None:
          new_subst = {other_type.full_name:
                       other_type.bound.instantiate(
                           node, abstract_utils.DUMMY_CONTAINER)}
          self._set_error_subst(self._merge_substs(subst, [new_subst]))
          return None
      if other_type.full_name in subst:
        # Merge the two variables.
        new_var = subst[other_type.full_name].AssignToNewVariable(node)
        new_var.AddBinding(left, [], node)
      else:
        new_left = self.vm.convert.get_maybe_abstract_instance(left)
        new_var = self.vm.program.NewVariable()
        new_var.AddBinding(new_left, {value}, node)

      type_key = left.get_type_key()
      # Every value with this type key produces the same result when matched
      # against other_type, so they can all be added to this substitution rather
      # than matched separately.
      for other_value in value.variable.bindings:
        if (other_value is not value and
            other_value.data.get_type_key() == type_key):
          new_var.AddBinding(other_value.data, {other_value}, node)
      if other_type.constraints:
        new_var = self._enforce_single_type(new_var, node)
      else:
        new_var = self._enforce_common_superclass(new_var)
      if new_var is None:
        self._set_error_subst(subst)
        return None
      subst = subst.copy()
      subst[other_type.full_name] = new_var
      return subst
    elif (isinstance(other_type, typing_overlay.NoReturn) or
          isinstance(left, typing_overlay.NoReturn)):
      # `NoReturn` can only matches itself, `Any`, or `abstract.TypeParameter`.
      # For the latter case, it will be used in byte code `STORE_ANNOTATION`
      # to store the `NoReturn` annotation in a dict.
      if (left == other_type or isinstance(other_type, abstract.Unsolvable) or
          isinstance(left, abstract.Unsolvable)):
        return subst
      else:
        return None
    elif isinstance(other_type, mixin.Class):
      # Accumulate substitutions in "subst", or break in case of error:
      return self._match_type_against_type(left, other_type, subst, node, view)
    elif isinstance(other_type, abstract.Union):
      matched = False
      for t in other_type.options:
        new_subst = self._match_value_against_type(value, t, subst, node, view)
        if new_subst is not None:
          matched = True
          subst = new_subst
      return subst if matched else None
    elif (isinstance(other_type, (abstract.Unknown, abstract.Unsolvable)) or
          isinstance(left, (abstract.Unknown, abstract.Unsolvable))):
      # We can match anything against unknown types, and unknown types against
      # anything.
      # TODO(kramm): Do we want to record what we matched them against?
      assert not isinstance(other_type, abstract.ParameterizedClass)
      return subst
    elif isinstance(other_type, abstract.Empty):
      return self._match_type_against_type(left, other_type, subst, node, view)
    else:
      log.error("Invalid type: %s", type(other_type))
      return None

  def _match_type_against_type(self, left, other_type, subst, node, view):
    """Checks whether a type is compatible with a (formal) type.

    Args:
      left: A type.
      other_type: A formal type. E.g. mixin.Class or abstract.Union.
      subst: The current type parameter assignment.
      node: The current CFG node.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    if (isinstance(left, abstract.Empty) and
        isinstance(other_type, abstract.Empty)):
      return subst
    elif isinstance(left, abstract.AMBIGUOUS_OR_EMPTY):
      params = self.vm.annotations_util.get_type_parameters(other_type)
      if isinstance(left, abstract.Empty):
        value = self.vm.convert.empty
      else:
        value = self.vm.convert.unsolvable
      return self._mutate_type_parameters(params, value, subst, node)
    elif isinstance(left, mixin.Class):
      if (other_type.full_name == "__builtin__.type" and
          isinstance(other_type, abstract.ParameterizedClass)):
        other_type = other_type.get_formal_type_parameter(abstract_utils.T)
        return self._instantiate_and_match(left, other_type, subst, node, view)
      elif (other_type.full_name == "typing.Callable" and
            isinstance(other_type, abstract.ParameterizedClass)):
        # TODO(rechen): Check left's constructor against the callable's params.
        other_type = other_type.get_formal_type_parameter(abstract_utils.RET)
        return self._instantiate_and_match(left, other_type, subst, node, view)
      elif other_type.full_name in [
          "__builtin__.type", "__builtin__.object", "typing.Callable"]:
        return subst
      elif _is_callback_protocol(other_type):
        return self._match_type_against_callback_protocol(
            left, other_type, subst, node, view)
      elif left.cls:
        return self._match_instance_against_type(
            left, other_type, subst, node, view)
    elif isinstance(left, abstract.Module):
      if other_type.full_name in [
          "__builtin__.module", "__builtin__.object", "types.ModuleType"]:
        return subst
    elif isinstance(left, abstract.FUNCTION_TYPES):
      if other_type.full_name == "typing.Callable":
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
        signatures = abstract_utils.get_signatures(left)
        for sig in signatures:
          new_subst = self._match_signature_against_callable(
              sig, other_type, subst, node, view)
          if new_subst is not None:
            return new_subst
        return None
      elif _is_callback_protocol(other_type):
        return self._match_type_against_callback_protocol(
            left, other_type, subst, node, view)
      else:
        return None
    elif isinstance(left, dataclass_overlay.FieldInstance) and left.default:
      return self._match_all_bindings(
          left.default, other_type, subst, node, view)
    elif isinstance(left, abstract.SimpleAbstractValue):
      return self._match_instance_against_type(
          left, other_type, subst, node, view)
    elif isinstance(left, special_builtins.SuperInstance):
      return self._match_class_and_instance_against_type(
          left.super_cls, left.super_obj, other_type, subst, node, view)
    elif isinstance(left, abstract.ClassMethod):
      if other_type.full_name in [
          "__builtin__.classmethod", "__builtin__.object"]:
        return subst
      return self._match_type_against_type(
          left.to_bound_function(), other_type, subst, node, view)
    elif isinstance(left, abstract.StaticMethod):
      if other_type.full_name in [
          "__builtin__.staticmethod", "__builtin__.object"]:
        return subst
      return self._match_type_against_type(
          left.method, other_type, subst, node, view)
    elif isinstance(left, abstract.Union):
      for o in left.options:
        new_subst = self._match_type_against_type(
            o, other_type, subst, node, view)
        if new_subst is not None:
          return new_subst
    elif isinstance(left, abstract.TypeParameterInstance):
      return self._instantiate_and_match(
          left.param, other_type, subst, node, view)
    else:
      raise NotImplementedError("Matching not implemented for %s against %s" %
                                (type(left), type(other_type)))

  def _match_type_against_callback_protocol(
      self, left, other_type, subst, node, view):
    """See https://www.python.org/dev/peps/pep-0544/#callback-protocols."""
    _, method_var = self.vm.attribute_handler.get_attribute(
        node, other_type, "__call__")
    if not method_var or not method_var.data or any(
        not isinstance(v, abstract.Function) for v in method_var.data):
      return None
    new_substs = []
    for expected_method in method_var.data:
      signatures = abstract_utils.get_signatures(expected_method)
      for sig in signatures:
        sig = sig.drop_first_parameter()  # drop `self`
        expected_callable = (
            self.vm.convert.pytd_convert.signature_to_callable(sig))
        new_subst = self._match_type_against_type(
            left, expected_callable, subst, node, view)
        if new_subst is not None:
          # For a set of overloaded signatures, only one needs to match.
          new_substs.append(new_subst)
          break
      else:
        # Every method_var binding must have a matching signature.
        return None
    return self._merge_substs(subst, new_substs)

  def _mutate_type_parameters(self, params, value, subst, node):
    new_subst = {p.full_name: value.to_variable(node) for p in params}
    return self._merge_substs(subst, [new_subst])

  def _get_param_matcher(self, callable_type):
    """Helper for _match_signature_against_callable."""
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
        self.vm.annotations_util.get_type_parameters(callable_type))
    if isinstance(callable_type, abstract.CallableClass):
      # In CallableClass, type parameters in arguments are double-counted
      # because ARGS contains the union of the individual arguments.
      callable_param_count.subtract(
          self.vm.annotations_util.get_type_parameters(
              callable_type.get_formal_type_parameter(abstract_utils.ARGS)))
    def match(left, right, subst, node):
      if (not isinstance(left, abstract.TypeParameter) or
          not isinstance(right, abstract.TypeParameter) or
          right.constraints or right.bound or callable_param_count[right] != 1):
        return None
      subst = subst.copy()
      subst[right.full_name] = node.program.NewVariable([], [], node)
      return subst
    return match

  def _match_signature_against_callable(
      self, sig, other_type, subst, node, view):
    """Match a function.Signature against a parameterized callable."""
    # a special type param against type param matcher that takes priority over
    # normal matching
    param_match = self._get_param_matcher(other_type)
    ret_type = sig.annotations.get("return", self.vm.convert.unsolvable)
    other_ret_type = other_type.get_formal_type_parameter(abstract_utils.RET)
    new_subst = param_match(ret_type, other_ret_type, subst, node)
    if new_subst is None:
      subst = self._instantiate_and_match(
          ret_type, other_ret_type, subst, node, view, container=sig)
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
      actual_arg = sig.annotations.get(name, self.vm.convert.unsolvable)
      new_subst = param_match(actual_arg, expected_arg, subst, node)
      if new_subst is None:
        # Flip actual and expected, since argument types are contravariant.
        subst = self._instantiate_and_match(
            expected_arg, actual_arg, subst, node, view, container=other_type)
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

  def _instantiate_and_match(self, left, other_type, subst, node, view,
                             container=None):
    """Instantiate and match an abstract value."""
    instance = left.instantiate(node, container=container)
    return self._match_all_bindings(instance, other_type, subst, node, view)

  def _match_all_bindings(self, var, other_type, subst, node, view):
    """Matches all of var's bindings against other_type."""
    new_substs = []
    for new_view in abstract_utils.get_views([var], node):
      # When new_view and view have entries in common, we want to use the
      # entries from the old view.
      new_view.update(view)
      new_subst = self.match_var_against_type(
          var, other_type, subst, node, new_view)
      if new_subst is not None:
        new_substs.append(new_subst)
    if new_substs:
      return self._merge_substs(subst, new_substs)
    else:
      return None

  def _match_instance_against_type(self, left, other_type, subst, node, view):
    left_type = left.get_class()
    assert left_type
    return self._match_class_and_instance_against_type(
        left_type, left, other_type, subst, node, view)

  def _match_instance(self, left, instance, other_type, subst, node, view):
    """Used by _match_class_and_instance_against_type. Matches one MRO entry.

    Called after the instance has been successfully matched against a
    formal type to do any remaining matching special to the type.

    Args:
      left: The instance type, which may be different from instance.cls
        depending on where in the mro the match happened.
      instance: The instance.
      other_type: The formal type that was successfully matched against.
      subst: The current type parameter assignment.
      node: The current CFG node.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    if (isinstance(left, abstract.TupleClass) or
        isinstance(instance, abstract.Tuple) or
        isinstance(other_type, abstract.TupleClass)):
      return self._match_heterogeneous_tuple_instance(
          left, instance, other_type, subst, node, view)
    elif (isinstance(left, abstract.CallableClass) or
          isinstance(other_type, abstract.CallableClass)):
      return self._match_callable_instance(
          left, instance, other_type, subst, node, view)
    return self._match_maybe_parameterized_instance(
        left, instance, other_type, subst, node, view)

  def _match_maybe_parameterized_instance(self, left, instance, other_type,
                                          subst, node, view):
    """Used by _match_instance."""
    if isinstance(other_type, abstract.ParameterizedClass):
      if isinstance(left, abstract.ParameterizedClass):
        assert left.base_cls is other_type.base_cls
      elif isinstance(left, abstract.AMBIGUOUS_OR_EMPTY):
        for type_param in other_type.template:
          value = other_type.get_formal_type_parameter(type_param.name)
          if isinstance(value, abstract.TypeParameter):
            subst[value.full_name] = self.vm.new_unsolvable(
                self.vm.root_cfg_node)
        return subst
      else:
        # Parameterized classes can rename type parameters, which is why we need
        # the instance type for lookup. But if the instance type is not
        # parameterized, then it is safe to use the param names in other_type.
        assert left is other_type.base_cls
        left = other_type
      for type_param in left.template:
        class_param = other_type.get_formal_type_parameter(type_param.name)
        instance_param = instance.get_instance_type_parameter(
            type_param.full_name, node)
        instance_type_param = left.get_formal_type_parameter(type_param.name)
        if (not instance_param.bindings and isinstance(
            instance_type_param, abstract.TypeParameter) and
            instance_type_param.name != type_param.name):
          # This type parameter was renamed!
          instance_param = instance.get_instance_type_parameter(
              type_param.full_name, node)
        if instance_param.bindings and instance_param not in view:
          binding, = instance_param.bindings
          assert isinstance(binding.data, abstract.Unsolvable)
          view = view.copy()
          view[instance_param] = binding
        subst = self.match_var_against_type(instance_param, class_param,
                                            subst, node, view)
        if subst is None:
          return None
    return subst

  def _match_heterogeneous_tuple_instance(self, left, instance, other_type,
                                          subst, node, view):
    """Used by _match_instance."""
    if isinstance(instance, abstract.Tuple):
      if isinstance(other_type, abstract.TupleClass):
        if instance.tuple_length == other_type.tuple_length:
          for i in range(instance.tuple_length):
            instance_param = instance.pyval[i]
            class_param = other_type.formal_type_parameters[i]
            subst = self.match_var_against_type(
                instance_param, class_param, subst, node, view)
            if subst is None:
              return None
        else:
          return None
      elif isinstance(other_type, abstract.ParameterizedClass):
        class_param = other_type.get_formal_type_parameter(abstract_utils.T)
        # If we merge in the new substitution results prematurely, then we'll
        # accidentally trigger _enforce_common_superclass.
        new_substs = []
        for instance_param in instance.pyval:
          new_subst = self.match_var_against_type(
              instance_param, class_param, subst, node, view)
          if new_subst is None:
            return None
          new_substs.append(new_subst)
        if new_substs:
          subst = self._merge_substs(subst, new_substs)
      if not instance.pyval:
        # This call puts the right param names (with empty values) into subst.
        subst = self._match_maybe_parameterized_instance(
            left, instance, other_type, subst, node, view)
    elif isinstance(left, abstract.TupleClass):
      # We have an instance of a subclass of tuple.
      return self._instantiate_and_match(left, other_type, subst, node, view)
    else:
      assert isinstance(other_type, abstract.TupleClass)
      if isinstance(instance, abstract.SimpleAbstractValue):
        instance_param = instance.get_instance_type_parameter(
            abstract_utils.T, node)
        for i in range(other_type.tuple_length):
          class_param = other_type.formal_type_parameters[i]
          subst = self.match_var_against_type(
              instance_param, class_param, subst, node, view)
          if subst is None:
            return None
    return subst

  def _match_callable_instance(
      self, left, instance, other_type, subst, node, view):
    """Used by _match_instance."""
    if (not isinstance(instance, abstract.SimpleAbstractValue) or
        not isinstance(other_type, abstract.ParameterizedClass)):
      return subst
    subst = self.match_var_against_type(
        instance.get_instance_type_parameter(abstract_utils.RET, node),
        other_type.get_formal_type_parameter(
            abstract_utils.RET), subst, node, view)
    if subst is None:
      return None
    if (not isinstance(left, abstract.CallableClass) or
        not isinstance(other_type, abstract.CallableClass)):
      # One of the types doesn't specify arg types, so no need to check them.
      return subst
    if left.num_args != other_type.num_args:
      return None
    for i in range(left.num_args):
      # Flip actual and expected to enforce contravariance of argument types.
      subst = self._instantiate_and_match(
          other_type.formal_type_parameters[i], left.formal_type_parameters[i],
          subst, node, view, container=other_type)
      if subst is None:
        return None
    return subst

  def _match_pyval_against_string(self, pyval, string, subst):
    """Matches a concrete value against a string literal."""
    assert isinstance(string, str)

    if pyval.__class__ is str:  # native str
      left_type = "bytes" if self.vm.PY2 else "unicode"
    elif isinstance(pyval, compat.BytesType):
      left_type = "bytes"
    elif isinstance(pyval, compat.UnicodeType):
      left_type = "unicode"
    else:
      return None
    # needs to be native str to match `string`
    left_value = compat.native_str(pyval)

    right_prefix, right_value = (
        parser_constants.STRING_RE.match(string).groups()[:2])
    if "b" in right_prefix or "u" not in right_prefix and self.vm.PY2:
      right_type = "bytes"
    else:
      right_type = "unicode"
    right_value = right_value[1:-1]  # remove quotation marks

    if left_type == right_type and left_value == right_value:
      return subst
    return None

  def _match_class_and_instance_against_type(
      self, left, instance, other_type, subst, node, view):
    """Checks whether an instance of a type is compatible with a (formal) type.

    Args:
      left: A type.
      instance: An instance of the type. An abstract.Instance.
      other_type: A formal type. E.g. mixin.Class or abstract.Union.
      subst: The current type parameter assignment.
      node: The current CFG node.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    if isinstance(other_type, abstract.LiteralClass):
      other_value = other_type.value
      if other_value and isinstance(instance, abstract.AbstractOrConcreteValue):
        if isinstance(other_value.pyval, str):
          return self._match_pyval_against_string(
              instance.pyval, other_value.pyval, subst)
        return subst if instance.pyval == other_value.pyval else None
      elif other_value:
        # `instance` does not contain a concrete value. Literal overloads are
        # always followed by at least one non-literal fallback, so we should
        # fail here.
        return None
      else:
        # TODO(b/123775699): Remove this workaround once we can match against
        # literal enums.
        return self._match_type_against_type(
            instance, other_type.formal_type_parameters[abstract_utils.T],
            subst, node, view)
    elif isinstance(other_type, mixin.Class):
      base = self.match_from_mro(left, other_type)
      if base is None:
        if other_type.is_protocol:
          with self._track_partially_matched_protocols():
            return self._match_against_protocol(left, other_type, subst, node,
                                                view)
        return None
      elif isinstance(base, abstract.AMBIGUOUS_OR_EMPTY):
        # An ambiguous base class matches everything.
        # _match_maybe_parameterized_instance puts the right params in `subst`.
        return self._match_maybe_parameterized_instance(
            base, instance, other_type, subst, node, view)
      else:
        return self._match_instance(
            base, instance, other_type, subst, node, view)
    elif isinstance(other_type, abstract.Empty):
      return None
    else:
      raise NotImplementedError(
          "Can't match instance %r against %r" % (left, other_type))

  def _fill_in_implicit_protocol_methods(self, methods):
    if "__getitem__" in methods and "__iter__" not in methods:
      # If a class has a __getitem__ method, it also (implicitly) has a
      # __iter__: Python will emulate __iter__ by calling __getitem__ with
      # increasing integers until it throws IndexError.
      methods["__iter__"] = pytd_utils.DummyMethod("__iter__", "self")

  def _get_methods_dict(self, left):
    """Get the methods implemented (or implicit) on a type."""
    left_methods = {}
    for cls in reversed(left.mro):
      if isinstance(cls, abstract.ParameterizedClass):
        cls = cls.base_cls
      # We add newly discovered methods to the methods dict and remove from the
      # dict the names of non-method members, since that means the method was
      # overwritten with something else.
      if isinstance(cls, abstract.PyTDClass):
        left_methods.update({m.name: m for m in cls.pytd_cls.methods})
        for c in cls.pytd_cls.constants:
          left_methods.pop(c.name, None)
      elif isinstance(cls, abstract.InterpreterClass):
        for name, member in cls.members.items():
          if any(isinstance(data, abstract.Function) for data in member.data):
            left_methods[name] = member
          else:
            left_methods.pop(name, None)
    self._fill_in_implicit_protocol_methods(left_methods)
    return left_methods

  def unimplemented_protocol_methods(self, left, other_type):
    """Get a list of the protocol methods not implemented by `left`."""
    assert other_type.is_protocol
    if left.cls:
      methods = self._get_methods_dict(left.cls)
      unimplemented = [
          method for method in other_type.protocol_methods
          if method not in methods]
      if unimplemented:
        return unimplemented
    return []

  def _match_against_protocol(self, left, other_type, subst, node, view):
    """Checks whether a type is compatible with a protocol.

    Args:
      left: A type.
      other_type: A protocol.
      subst: The current type parameter assignment.
      node: The current CFG node.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    if isinstance(left, abstract.AMBIGUOUS_OR_EMPTY):
      return subst
    elif len(left.template) == 1 and other_type.full_name == "typing.Mapping":
      # TODO(rechen): This check is a workaround to prevent List from matching
      # against Mapping. What we should actually do is detect the mismatch
      # between the type parameters in List's and Mapping's abstract methods,
      # but that's tricky to do.
      return None
    left_methods = self._get_methods_dict(left)
    method_names_matched = all(
        method in left_methods for method in other_type.protocol_methods)
    if method_names_matched and isinstance(other_type,
                                           abstract.ParameterizedClass):
      key = (node, left, other_type)
      if key in self._protocol_cache:
        return subst
      self._protocol_cache.add(key)
      return self._match_parameterized_protocol(left_methods, other_type, subst,
                                                node, view)
    elif method_names_matched:
      return subst
    else:
      return None

  def _match_parameterized_protocol(self, left_methods, other_type, subst, node,
                                    view):
    """Checks whether left_methods is compatible with a parameterized protocol.

    Args:
      left_methods: A dictionary name -> method. method can either be a
        Variable or a pytd.Function.
      other_type: A formal type of type abstract.ParameterizedClass.
      subst: The current type parameter assignment.
      node: The current CFG node.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    new_substs = []
    for name in other_type.protocol_methods:
      abstract_method = other_type.get_method(name)
      if name in left_methods:
        matching_left_method = left_methods[name]
      else:
        return None
      converter = self.vm.convert.pytd_convert
      for signature in abstract_method.signatures:
        callable_signature = converter.signature_to_callable(
            signature.signature)
        if isinstance(callable_signature, abstract.CallableClass):
          # Prevent the matcher from trying to enforce contravariance on 'self'.
          callable_signature.formal_type_parameters[0] = (
              self.vm.convert.unsolvable)
        annotation_subst = datatypes.AliasingDict()
        if isinstance(other_type.base_cls, mixin.Class):
          annotation_subst.uf = (
              other_type.base_cls.all_formal_type_parameters.uf)
        for (param, value) in other_type.get_formal_type_parameters().items():
          annotation_subst[param] = value.instantiate(
              node, abstract_utils.DUMMY_CONTAINER)
        annotated_callable = self.vm.annotations_util.sub_one_annotation(
            node, callable_signature, [annotation_subst])
        if isinstance(matching_left_method, pytd.Function):
          matching_left_method = self.vm.convert.constant_to_var(
              matching_left_method)
        for m in matching_left_method.data:
          match_result = self._match_type_against_type(
              m, annotated_callable, subst, node, view)
          if match_result is None:
            return None
          else:
            new_substs.append(match_result)
    return self._merge_substs(subst, new_substs)

  def _get_concrete_values_and_classes(self, var):
    # TODO(rechen): For type parameter instances, we should extract the concrete
    # value from v.instance so that we can check it, rather than ignoring the
    # value altogether.
    values = []
    classes = []
    for v in var.data:
      if not isinstance(v, (abstract.AMBIGUOUS_OR_EMPTY,
                            abstract.TypeParameterInstance)):
        cls = v.get_class()
        if not isinstance(cls, abstract.AMBIGUOUS_OR_EMPTY):
          values.append(v)
          classes.append(cls)
    return values, classes

  def _enforce_single_type(self, var, node):
    """Enforce that the variable contains only one concrete type."""
    concrete_values, classes = self._get_concrete_values_and_classes(var)
    if len(set(classes)) > 1:
      # We require all occurrences to be of the same type, no subtyping allowed.
      return None
    if concrete_values and len(concrete_values) < len(var.data):
      # We can filter out ambiguous values because we've already found the
      # single concrete type allowed for this variable.
      return node.program.NewVariable(concrete_values, [], node)
    return var

  def _enforce_common_superclass(self, var):
    """Enforce that the variable's values share a superclass below object."""
    concrete_values, classes = self._get_concrete_values_and_classes(var)
    common_classes = None
    object_in_values = False
    for cls in classes:
      object_in_values |= cls == self.vm.convert.object_type
      superclasses = {c.full_name for c in cls.mro}
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
      ignored_superclasses = {"__builtin__.object",
                              "typing.Generic",
                              "typing.Protocol"}
    if concrete_values and common_classes.issubset(ignored_superclasses):
      return None
    return var
