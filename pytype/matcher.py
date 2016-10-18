"""Matching logic for abstract values."""
import logging


from pytype import abstract
from pytype import typing
from pytype import utils
from pytype.pytd import pep484


log = logging.getLogger(__name__)


class AbstractMatcher(object):
  """Matcher for abstract values."""

  def match_var_against_type(self, var, other_type, subst, node, view):
    if isinstance(other_type, typing.Union):
      for element in other_type.elements:
        new_subst = self.match_var_against_type(
            var, element, subst, node, view)
        if new_subst is not None:
          return new_subst
    elif isinstance(other_type, typing.Container):
      new_subst = None
      for cls in [c for clsv in other_type.concrete_classes
                  for c in clsv.data]:
        new_subst = self.match_var_against_type(var, cls, subst, node, view)
        if new_subst is not None:
          subst = new_subst
          break
      else:
        return None
      if other_type.inner:
        v = view[var].data
        if (isinstance(v, abstract.SimpleAbstractValue) and
            all(param in v.type_parameters
                for param in other_type.type_param_names)):
          for param_name, type_param in zip(other_type.type_param_names,
                                            other_type.inner):
            inner = v.type_parameters[param_name]
            for formal in type_param.data:
              new_subst = self.match_var_against_type(
                  inner, formal, subst, node, view)
              if new_subst is not None:
                subst = new_subst
                break
            else:
              return None
            return new_subst
        elif isinstance(v, abstract.AMBIGUOUS_OR_EMPTY):
          return subst
      else:
        return subst
    elif var.bindings:
      return self.match_value_against_type(
          view[var], other_type, subst, node, view)
    else:  # Empty set of values. The "nothing" type.
      if isinstance(other_type, abstract.Union):
        right_side_options = other_type.options
      else:
        right_side_options = [other_type]
      for right in right_side_options:
        if isinstance(right, abstract.Class):
          # If this type is empty, the only thing we can match it against is
          # object (for pytd convenience).
          if right.full_name == "__builtin__.object":
            return subst
        elif isinstance(right, abstract.Nothing):
          # Matching nothing against nothing is fine.
          return subst
        elif isinstance(right, abstract.TypeParameter):
          # If we have a union like "K or V" and we match both against
          # nothing, that will fill in both K and V.
          if right.name not in subst:
            subst = subst.copy()
            subst[right.name] = var.program.NewVariable("empty")
          return subst

  def match_value_against_type(self, value, other_type, subst, node, view):
    """One-way unify value into pytd type given a substitution.

    Args:
      value: A typegraph.Binding.
      other_type: An AtomicAbstractValue instance.
      subst: The current substitution. This dictionary is not modified.
      node: Current location (typegraph CFG node)
      view: A mapping of Variable to Value.
    Returns:
      A new (or unmodified original) substitution dict if the matching succeded,
      None otherwise.
    """
    left = value.data
    assert isinstance(left, abstract.AtomicAbstractValue), left
    assert not left.formal

    # TODO(kramm): Use view
    if isinstance(other_type, abstract.Class):
      # Accumulate substitutions in "subst", or break in case of error:
      return self._match_type_against_type(left, other_type, subst, node, view)
    elif isinstance(other_type, abstract.Union):
      for t in other_type.options:
        new_subst = self.match_value_against_type(value, t, subst, node, view)
        if new_subst is not None:
          # TODO(kramm): What if more than one type matches?
          return new_subst
    elif isinstance(other_type, abstract.TypeParameter):
      if other_type.name in subst:
        # Merge the two variables.
        subst = subst.copy()
        new_var = subst[other_type.name].AssignToNewVariable(other_type.name,
                                                             node)
        new_var.AddBinding(left, [], node)
        subst[other_type.name] = new_var
      else:
        subst = subst.copy()
        subst[other_type.name] = new_var = value.AssignToNewVariable(
            other_type.name, node)
      type_key = left.get_type_key()
      # Every value with this type key produces the same result when matched
      # against other_type, so they can all be added to this substitution rather
      # than matched separately.
      for other_value in value.variable.bindings:
        if (other_value is not value and
            other_value.data.get_type_key() == type_key):
          new_var.AddBinding(other_value.data, {other_value}, node)
      return subst
    elif (isinstance(other_type, (abstract.Unknown, abstract.Unsolvable)) or
          isinstance(left, (abstract.Unknown, abstract.Unsolvable))):
      # We can match anything against unknown types, and unknown types against
      # anything.
      # TODO(kramm): Do we want to record what we matched them against?
      assert not isinstance(other_type, abstract.ParameterizedClass)
      return subst
    elif isinstance(other_type, abstract.Nothing):
      return self._match_type_against_type(left, other_type, subst, node, view)
    else:
      log.error("Invalid type: %s", type(other_type))
      return None

  def bad_matches(self, var, other_type, node, subst=None):
    """Match a Variable against a type. Return bindings that don't match.

    Args:
      var: A cfg.Variable, containing instances.
      other_type: An instance of AtomicAbstractValue.
      node: A cfg.CFGNode. The position in the CFG from which we "observe" the
        match.
      subst: Type parameter substitutions.
    Returns:
      A list of all the bindings of var that didn't match.
    """
    subst = subst or {}
    bad = []
    for combination in utils.deep_variable_product([var]):
      view = {value.variable: value for value in combination}
      if self.match_var_against_type(var, other_type, subst,
                                     node, view) is None:
        bad.append(view[var])
    return bad

  def _match_type_against_type(self, left, other_type, subst, node, view):
    """Checks whether a type is compatible with a (formal) type.

    Args:
      left: A type.
      other_type: A formal type. E.g. abstract.Class or abstract.Union.
      subst: The current type parameter assignment.
      node: The current CFG node.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    if (isinstance(left, abstract.Empty) and
        isinstance(other_type, abstract.Nothing)):
      return subst
    elif isinstance(left, abstract.AMBIGUOUS_OR_EMPTY):
      return self._match_instance(
          other_type, left, other_type, subst, node, view)
    elif isinstance(left, abstract.Class):
      if (other_type.full_name == "__builtin__.type" and
          isinstance(other_type, abstract.ParameterizedClass)):
        other_type = other_type.type_parameters["T"]
        if other_type.formal:
          value = left.instantiate(node).bindings[0]
          return self.match_value_against_type(
              value, other_type, subst, node, view)
        else:
          base = self._match_from_mro(left, other_type)
          if base is not None:
            # TODO(rechen): We should match type parameters when base and
            # other_type are both parameterized classes.
            return subst
      elif other_type.full_name in [
          "__builtin__.type", "__builtin__.object", "typing.Callable"]:
        return subst
      elif left.cls:
        return self._match_instance_against_type(
            left, other_type, subst, node, view)
    elif isinstance(left, abstract.SimpleAbstractValue):
      return self._match_instance_against_type(
          left, other_type, subst, node, view)
    elif isinstance(left, abstract.SuperInstance):
      return self._match_class_and_instance_against_type(
          left.super_cls, left.super_obj, other_type, subst, node, view)
    elif isinstance(left, (abstract.Function, abstract.BoundFunction)):
      if other_type.full_name in [
          "__builtin__.function", "__builtin__.object", "typing.Callable"]:
        return subst
    elif isinstance(left, abstract.ClassMethod):
      if other_type.full_name in [
          "__builtin__.classmethod", "__builtin__.object"]:
        return subst
    elif isinstance(left, abstract.StaticMethod):
      if other_type.full_name in [
          "__builtin__.staticmethod", "__builtin__.object"]:
        return subst
    elif isinstance(left, abstract.Nothing):
      if isinstance(other_type, abstract.Nothing):
        return subst
    elif isinstance(left, abstract.Module):
      if other_type.full_name in ["__builtin__.module", "__builtin__.object"]:
        return subst
    else:
      raise NotImplementedError("Matching not implemented for %s", type(left))

  def _match_instance_against_type(self, left, other_type, subst, node, view):
    left_type = left.get_class()
    assert left_type
    for left_cls in left_type.data:
      subst = self._match_class_and_instance_against_type(
          left_cls, left, other_type, subst, node, view)
      if subst is None:
        return None
    return subst

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
    if isinstance(other_type, abstract.ParameterizedClass):
      if isinstance(left, abstract.ParameterizedClass):
        assert left.base_cls is other_type.base_cls
      else:
        # Parameterized classes can rename type parameters, which is why we need
        # the instance type for lookup. But if the instance type is not
        # parameterized, then it is safe to use the param names in other_type.
        assert left is other_type.base_cls
        left = other_type
      for type_param in left.base_cls.pytd_cls.template:
        class_param = other_type.type_parameters[type_param.name]
        instance_param = instance.get_type_parameter(node, type_param.name)
        instance_type_param = left.type_parameters[type_param.name]
        if (not instance_param.bindings and isinstance(
            instance_type_param, abstract.TypeParameter) and
            instance_type_param.name != type_param.name):
          # This type parameter was renamed!
          instance_param = instance.get_type_parameter(
              node, instance_type_param.name)
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

  def _match_from_mro(self, left, other_type):
    """Checks a type's MRO for a match for a formal type.

    Args:
      left: The type.
      other_type: The formal type.

    Returns:
      The match, if any, None otherwise.
    """
    for base in left.mro:
      if isinstance(base, abstract.ParameterizedClass):
        base_cls = base.base_cls
      else:
        base_cls = base
      if isinstance(base_cls, abstract.Class):
        if other_type is base_cls or (
            isinstance(other_type, abstract.ParameterizedClass) and
            other_type.base_cls is base_cls):
          return base
      elif isinstance(base_cls, abstract.AMBIGUOUS_OR_EMPTY):
        # See match_Function_against_Class in type_match.py. Even though it's
        # possible that this Unknown is of type other_type, our class would
        # then be a match for *everything*. Hence, return False, to keep
        # the list of possible types from exploding.
        return None
      else:
        raise AssertionError("Bad base class %r", base_cls)

  def _match_class_and_instance_against_type(
      self, left, instance, other_type, subst, node, view):
    """Checks whether an instance of a type is compatible with a (formal) type.

    Args:
      left: A type.
      instance: An instance of the type. An abstract.Instance.
      other_type: A formal type. E.g. abstract.Class or abstract.Union.
      subst: The current type parameter assignment.
      node: The current CFG node.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    if other_type.full_name == "__builtin__.object":
      return subst

    compatible_builtins = {
        "__builtin__." + k: "__builtin__." + v
        for k, v in pep484.COMPAT_MAP.iteritems()
    }
    if compatible_builtins.get(left.full_name) == other_type.full_name:
      return subst

    if isinstance(other_type, abstract.Class):
      base = self._match_from_mro(left, other_type)
      if base is None:
        return None
      else:
        return self._match_instance(
            base, instance, other_type, subst, node, view)
    elif isinstance(other_type, abstract.Nothing):
      return None
    else:
      raise NotImplementedError(
          "Can't match instance %r against %r", left, other_type)
