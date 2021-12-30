"""Constructs related to type annotations."""

import logging
import typing
from typing import Mapping, Tuple, Type, Union as _Union

from pytype import utils
from pytype.abstract import _base
from pytype.abstract import _classes
from pytype.abstract import _instance_base
from pytype.abstract import abstract_utils
from pytype.abstract import function
from pytype.abstract import mixin
from pytype.pytd import pytd_utils

log = logging.getLogger(__name__)


class AnnotationClass(_instance_base.SimpleValue, mixin.HasSlots):
  """Base class of annotations that can be parameterized."""

  def __init__(self, name, ctx):
    super().__init__(name, ctx)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)

  def getitem_slot(self, node, slice_var):
    """Custom __getitem__ implementation."""
    slice_content = abstract_utils.maybe_extract_tuple(slice_var)
    inner, ellipses = self._build_inner(slice_content)
    value = self._build_value(node, tuple(inner), ellipses)
    return node, value.to_variable(node)

  def _build_inner(self, slice_content):
    """Build the list of parameters.

    Args:
      slice_content: The iterable of variables to extract parameters from.

    Returns:
      A tuple of a list of parameters and a set of indices at which an ellipsis
        was replaced with Any.
    """
    inner = []
    ellipses = set()
    for var in slice_content:
      if len(var.bindings) > 1:
        self.ctx.errorlog.ambiguous_annotation(self.ctx.vm.frames, var.data)
        inner.append(self.ctx.convert.unsolvable)
      else:
        val = var.bindings[0].data
        if val is self.ctx.convert.ellipsis:
          # Ellipses are allowed only in special cases, so turn them into Any
          # but record the indices so we can check if they're legal.
          ellipses.add(len(inner))
          inner.append(self.ctx.convert.unsolvable)
        else:
          inner.append(val)
    return inner, ellipses

  def _build_value(self, node, inner, ellipses):
    raise NotImplementedError(self.__class__.__name__)

  def __repr__(self):
    return "AnnotationClass(%s)" % self.name

  def _get_class(self):
    return self.ctx.convert.type_type


class AnnotationContainer(AnnotationClass):
  """Implementation of X[...] for annotations."""

  def __init__(self, name, ctx, base_cls):
    super().__init__(name, ctx)
    self.base_cls = base_cls

  def _sub_annotation(
      self, annot: _base.BaseValue, subst: Mapping[str, _base.BaseValue]
  ) -> _base.BaseValue:
    """Apply type parameter substitutions to an annotation."""
    # This is very similar to annotation_utils.sub_one_annotation, but a couple
    # differences make it more convenient to maintain two separate methods:
    # - subst here is a str->BaseValue mapping rather than str->Variable, and it
    #   would be wasteful to create variables just to match sub_one_annotation's
    #   expected input type.
    # - subst contains the type to be substituted in, not an instance of it.
    #   Again, instantiating the type just to later get the type of the instance
    #   is unnecessary extra work.
    if isinstance(annot, TypeParameter):
      if annot.full_name in subst:
        return subst[annot.full_name]
      else:
        return self.ctx.convert.unsolvable
    elif isinstance(annot, mixin.NestedAnnotation):
      inner_types = [(key, self._sub_annotation(val, subst))
                     for key, val in annot.get_inner_types()]
      return annot.replace(inner_types)
    return annot

  def _get_value_info(
      self, inner, ellipses, allowed_ellipses=frozenset()
  ) -> Tuple[Tuple[_Union[int, str], ...], Tuple[_base.BaseValue, ...],
             Type[_classes.ParameterizedClass]]:
    """Get information about the container's inner values.

    Args:
      inner: The list of parameters from _build_inner().
      ellipses: The set of ellipsis indices from _build_inner().
      allowed_ellipses: Optionally, a set of indices at which ellipses are
        allowed. If omitted, ellipses are assumed to be never allowed.

    Returns:
      A tuple of the template, the parameters, and the container class.
    """
    if self.base_cls.full_name == "typing.Protocol":
      return abstract_utils.build_generic_template(inner, self) + (
          _classes.ParameterizedClass,)  # pytype: disable=bad-return-type
    if isinstance(self.base_cls, _classes.TupleClass):
      template = tuple(range(self.base_cls.tuple_length))
    elif isinstance(self.base_cls, _classes.CallableClass):
      template = tuple(range(self.base_cls.num_args)) + (abstract_utils.RET,)
    else:
      template = tuple(t.name for t in self.base_cls.template)
    self.ctx.errorlog.invalid_ellipses(self.ctx.vm.frames,
                                       ellipses - allowed_ellipses, self.name)
    last_index = len(inner) - 1
    if last_index and last_index in ellipses and len(inner) > len(template):
      # Even if an ellipsis is not allowed at this position, strip it off so
      # that we report only one error for something like 'List[int, ...]'
      inner = inner[:-1]
    if isinstance(self.base_cls, _classes.ParameterizedClass):
      # We're dealing with a generic type alias, e.g.:
      #   X = Dict[T, str]
      #   def f(x: X[int]): ...
      # We construct `inner` using both the new inner values and the ones
      # already in X, to end up with a final result of:
      #   template=(_K, _V)
      #   inner=(int, str)
      new_inner = []
      inner_idx = 0
      subst = {}
      # Note that we ignore any missing or extra values in inner for now; the
      # problem will be reported later by _validate_inner.
      for k in template:
        v = self.base_cls.formal_type_parameters[k]
        if v.formal:
          params = self.ctx.annotation_utils.get_type_parameters(v)
          for param in params:
            # If there are too few parameters, we ignore the problem for now;
            # it'll be reported when _build_value checks that the lengths of
            # template and inner match.
            if param.full_name not in subst and inner_idx < len(inner):
              subst[param.full_name] = inner[inner_idx]
              inner_idx += 1
          new_inner.append(self._sub_annotation(v, subst))
        else:
          new_inner.append(v)
      inner = tuple(new_inner)
      if isinstance(self.base_cls, _classes.TupleClass):
        template += (abstract_utils.T,)
        inner += (self.ctx.convert.merge_values(inner),)
      elif isinstance(self.base_cls, _classes.CallableClass):
        template = template[:-1] + (abstract_utils.ARGS,) + template[-1:]
        args = inner[:-1]
        inner = args + (self.ctx.convert.merge_values(args),) + inner[-1:]
      abstract_class = type(self.base_cls)
    else:
      abstract_class = _classes.ParameterizedClass
    return template, inner, abstract_class

  def _validate_inner(self, template, inner, raw_inner):
    """Check that the passed inner values are valid for the given template."""
    if (isinstance(self.base_cls, _classes.ParameterizedClass) and
        not abstract_utils.is_generic_protocol(self.base_cls)):
      # For a generic type alias, we check that the number of typevars in the
      # alias matches the number of raw parameters provided.
      template_length = raw_template_length = len(
          set(self.ctx.annotation_utils.get_type_parameters(self.base_cls)))
      inner_length = len(raw_inner)
      base_cls = self.base_cls.base_cls
    else:
      # In all other cases, we check that the final template length and
      # parameter count match, after any adjustments like flattening the inner
      # argument list in a Callable.
      template_length = len(template)
      raw_template_length = len(self.base_cls.template)
      inner_length = len(inner)
      base_cls = self.base_cls
    if inner_length != template_length:
      if not template:
        self.ctx.errorlog.not_indexable(
            self.ctx.vm.frames, base_cls.name, generic_warning=True)
      else:
        # Use the unprocessed values of `template` and `inner` so that the error
        # message matches what the user sees.
        if isinstance(self.base_cls, _classes.ParameterizedClass):
          error_template = None
        else:
          error_template = (t.name for t in base_cls.template)
        self.ctx.errorlog.wrong_annotation_parameter_count(
            self.ctx.vm.frames, self.base_cls, raw_inner, raw_template_length,
            error_template)
    else:
      if len(inner) == 1:
        val, = inner
        # It's a common mistake to index a container class rather than an
        # instance (e.g., list[0]).
        # We only check the "int" case, since string literals are allowed for
        # late annotations.
        if (isinstance(val, _instance_base.Instance) and
            val.cls == self.ctx.convert.int_type):
          # Don't report this error again.
          inner = (self.ctx.convert.unsolvable,)
          self.ctx.errorlog.not_indexable(self.ctx.vm.frames, self.name)
    return inner

  def _build_value(self, node, inner, ellipses):
    if self.base_cls.is_late_annotation():
      # A parameterized LateAnnotation should be converted to another
      # LateAnnotation to delay evaluation until the first late annotation is
      # resolved. We don't want to create a ParameterizedClass immediately
      # because (1) ParameterizedClass expects its base_cls to be a
      # class_mixin.Class, and (2) we have to postpone error-checking anyway so
      # we might as well postpone the entire evaluation.
      printed_params = []
      for i, param in enumerate(inner):
        if i in ellipses:
          printed_params.append("...")
        else:
          printed_params.append(pytd_utils.Print(param.get_instance_type(node)))
      expr = "%s[%s]" % (self.base_cls.expr, ", ".join(printed_params))
      annot = LateAnnotation(expr, self.base_cls.stack, self.ctx)
      self.ctx.vm.late_annotations[self.base_cls.expr].append(annot)
      return annot
    template, processed_inner, abstract_class = self._get_value_info(
        inner, ellipses)
    if isinstance(self.base_cls, _classes.ParameterizedClass):
      base_cls = self.base_cls.base_cls
    else:
      base_cls = self.base_cls
    if base_cls.full_name in ("typing.Generic", "typing.Protocol"):
      # Generic is unique in that parameterizing it defines a new template;
      # usually, the parameterized class inherits the base class's template.
      # Protocol[T, ...] is a shorthand for Protocol, Generic[T, ...].
      template_params = [
          param.with_module(base_cls.full_name)
          for param in typing.cast(Tuple[TypeParameter, ...], processed_inner)]
    else:
      template_params = None
    processed_inner = self._validate_inner(template, processed_inner, inner)
    params = {
        name: (processed_inner[i]
               if i < len(processed_inner) else self.ctx.convert.unsolvable)
        for i, name in enumerate(template)
    }

    # For user-defined generic types, check if its type parameter matches
    # its corresponding concrete type
    if isinstance(base_cls, _classes.InterpreterClass) and base_cls.template:
      for formal_param in base_cls.template:
        root_node = self.ctx.root_node
        param_value = params[formal_param.name]
        if (isinstance(formal_param, TypeParameter) and
            not formal_param.is_generic() and
            isinstance(param_value, TypeParameter)):
          if formal_param.name == param_value.name:
            # We don't need to check if a TypeParameter matches itself.
            continue
          else:
            actual = param_value.instantiate(
                root_node, container=abstract_utils.DUMMY_CONTAINER)
        else:
          actual = param_value.instantiate(root_node)
        bad = self.ctx.matcher(root_node).bad_matches(actual, formal_param)
        if bad:
          if not isinstance(param_value, TypeParameter):
            # If param_value is not a TypeVar, we substitute in TypeVar bounds
            # and constraints in formal_param for a more helpful error message.
            formal_param = self.ctx.annotation_utils.sub_one_annotation(
                root_node, formal_param, [{}])
            details = None
          elif isinstance(formal_param, TypeParameter):
            details = (f"TypeVars {formal_param.name} and {param_value.name} "
                       "have incompatible bounds or constraints.")
          else:
            details = None
          self.ctx.errorlog.bad_concrete_type(
              self.ctx.vm.frames, root_node, formal_param, actual, bad, details)
          return self.ctx.convert.unsolvable

    try:
      return abstract_class(base_cls, params, self.ctx, template_params)
    except abstract_utils.GenericTypeError as e:
      self.ctx.errorlog.invalid_annotation(self.ctx.vm.frames, e.annot, e.error)
      return self.ctx.convert.unsolvable


class TypeParameter(_base.BaseValue):
  """Parameter of a type."""

  formal = True

  def __init__(self,
               name,
               ctx,
               constraints=(),
               bound=None,
               covariant=False,
               contravariant=False,
               module=None):
    super().__init__(name, ctx)
    self.constraints = constraints
    self.bound = bound
    self.covariant = covariant
    self.contravariant = contravariant
    self.module = module

  def is_generic(self):
    return not self.constraints and not self.bound

  def copy(self):
    return TypeParameter(self.name, self.ctx, self.constraints, self.bound,
                         self.covariant, self.contravariant, self.module)

  def with_module(self, module):
    res = self.copy()
    res.module = module
    return res

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return (self.name == other.name and
              self.constraints == other.constraints and
              self.bound == other.bound and
              self.covariant == other.covariant and
              self.contravariant == other.contravariant and
              self.module == other.module)
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def __hash__(self):
    return hash((self.name, self.constraints, self.bound, self.covariant,
                 self.contravariant))

  def __repr__(self):
    return "TypeParameter(%r, constraints=%r, bound=%r, module=%r)" % (
        self.name, self.constraints, self.bound, self.module)

  def instantiate(self, node, container=None):
    var = self.ctx.program.NewVariable()
    if container and (not isinstance(container, _instance_base.SimpleValue) or
                      self.full_name in container.all_template_names):
      instance = TypeParameterInstance(self, container, self.ctx)
      return instance.to_variable(node)
    else:
      for c in self.constraints:
        var.PasteVariable(c.instantiate(node, container))
      if self.bound:
        var.PasteVariable(self.bound.instantiate(node, container))
    if not var.bindings:
      var.AddBinding(self.ctx.convert.unsolvable, [], node)
    return var

  def update_official_name(self, name):
    if self.name != name:
      message = "TypeVar(%r) must be stored as %r, not %r" % (
          self.name, self.name, name)
      self.ctx.errorlog.invalid_typevar(self.ctx.vm.frames, message)

  def call(self, node, func, args, alias_map=None):
    return node, self.instantiate(node)


class TypeParameterInstance(_base.BaseValue):
  """An instance of a type parameter."""

  def __init__(self, param, instance, ctx):
    super().__init__(param.name, ctx)
    self.cls = self.param = param
    self.instance = instance
    self.module = param.module

  def call(self, node, func, args, alias_map=None):
    var = self.instance.get_instance_type_parameter(self.name)
    if var.bindings:
      return function.call_function(self.ctx, node, var, args)
    else:
      return node, self.ctx.convert.empty.to_variable(self.ctx.root_node)

  def __repr__(self):
    return "TypeParameterInstance(%r)" % self.name

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return self.param == other.param and self.instance == other.instance
    return NotImplemented

  def __hash__(self):
    return hash((self.param, self.instance))


class Union(_base.BaseValue, mixin.NestedAnnotation, mixin.HasSlots):
  """A list of types.

  Used for parameter matching.

  Attributes:
    options: Iterable of instances of BaseValue.
  """

  def __init__(self, options, ctx):
    super().__init__("Union", ctx)
    assert options
    self.options = list(options)
    self.cls = self._get_class()
    self.formal = any(t.formal for t in self.options)
    mixin.NestedAnnotation.init_mixin(self)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)
    self._printing = False

  def __repr__(self):
    if self._printing:  # recursion detected
      printed_contents = "..."
    else:
      self._printing = True
      printed_contents = ", ".join(repr(o) for o in self.options)
      self._printing = False
    return "%s[%s]" % (self.name, printed_contents)

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return self.options == other.options
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def __hash__(self):
    return hash(tuple(self.options))

  def _unique_parameters(self):
    return [o.to_variable(self.ctx.root_node) for o in self.options]

  def _get_type_params(self):
    params = self.ctx.annotation_utils.get_type_parameters(self)
    params = [x.full_name for x in params]
    return utils.unique_list(params)

  def _get_class(self):
    classes = {o.cls for o in self.options}
    if len(classes) > 1:
      return self.ctx.convert.unsolvable
    else:
      return classes.pop()

  def getitem_slot(self, node, slice_var):
    """Custom __getitem__ implementation."""
    slice_content = abstract_utils.maybe_extract_tuple(slice_var)
    params = self._get_type_params()
    # Check that we are instantiating all the unbound type parameters
    if len(params) != len(slice_content):
      self.ctx.errorlog.wrong_annotation_parameter_count(
          self.ctx.vm.frames, self, [v.data[0] for v in slice_content],
          len(params))
      return node, self.ctx.new_unsolvable(node)
    concrete = []
    for var in slice_content:
      value = var.data[0]
      concrete.append(
          value.instantiate(node, container=abstract_utils.DUMMY_CONTAINER))
    substs = [dict(zip(params, concrete))]
    new = self.ctx.annotation_utils.sub_one_annotation(node, self, substs)
    return node, new.to_variable(node)

  def instantiate(self, node, container=None):
    var = self.ctx.program.NewVariable()
    for option in self.options:
      var.PasteVariable(option.instantiate(node, container), node)
    return var

  def call(self, node, func, args, alias_map=None):
    var = self.ctx.program.NewVariable(self.options, [], node)
    return function.call_function(self.ctx, node, var, args)

  def get_formal_type_parameter(self, t):
    new_options = [option.get_formal_type_parameter(t)
                   for option in self.options]
    return Union(new_options, self.ctx)

  def get_inner_types(self):
    return enumerate(self.options)

  def update_inner_type(self, key, typ):
    self.options[key] = typ

  def replace(self, inner_types):
    return self.__class__((v for _, v in sorted(inner_types)), self.ctx)


class LateAnnotation:
  """A late annotation.

  A late annotation stores a string expression and a snapshot of the VM stack at
  the point where the annotation was introduced. Once the expression is
  resolved, the annotation pretends to be the resolved type; before that, it
  pretends to be an unsolvable. This effect is achieved by delegating attribute
  lookup with __getattribute__.

  Note that for late annotation x, `isinstance(x, ...)` and `x.__class__` will
  use the type that x is pretending to be; `type(x)` will reveal x's true type.
  Use `x.is_late_annotation()` to check whether x is a late annotation.
  """

  def __init__(self, expr, stack, ctx):
    self.expr = expr
    self.stack = stack
    self.ctx = ctx
    self.resolved = False
    self._type = ctx.convert.unsolvable  # the resolved type of `expr`
    self._unresolved_instances = set()
    # _attribute_names needs to be defined last! This contains the names of all
    # of LateAnnotation's attributes, discovered by looking at
    # LateAnnotation.__dict__ and self.__dict__. These names are used in
    # __getattribute__ and __setattr__ to determine whether a given get/setattr
    # call should operate on the LateAnnotation itself or its resolved type.
    self._attribute_names = (
        set(LateAnnotation.__dict__) |
        set(super().__getattribute__("__dict__")))

  def __repr__(self):
    return "LateAnnotation(%r, resolved=%r)" % (
        self.expr, self._type if self.resolved else None)

  # __hash__ and __eq__ need to be explicitly defined for Python to use them in
  # set/dict comparisons.

  def __hash__(self):
    return hash(self._type) if self.resolved else hash(self.expr)

  def __eq__(self, other):
    return hash(self) == hash(other)

  def __getattribute__(self, name):
    if name == "_attribute_names" or name in self._attribute_names:
      return super().__getattribute__(name)
    return self._type.__getattribute__(name)  # pytype: disable=attribute-error

  def __setattr__(self, name, value):
    if not hasattr(self, "_attribute_names") or name in self._attribute_names:
      return super().__setattr__(name, value)
    return self._type.__setattr__(name, value)

  def resolve(self, node, f_globals, f_locals):
    """Resolve the late annotation."""
    if self.resolved:
      return
    self.resolved = True
    var, errorlog = abstract_utils.eval_expr(self.ctx, node, f_globals,
                                             f_locals, self.expr)
    if errorlog:
      self.ctx.errorlog.copy_from(errorlog.errors, self.stack)
    self._type = self.ctx.annotation_utils.extract_annotation(
        node, var, None, self.stack)
    if self._type != self.ctx.convert.unsolvable:
      # We may have tried to call __init__ on instances of this annotation.
      # Since the annotation was unresolved at the time, we need to call
      # __init__ again to define any instance attributes.
      for instance in self._unresolved_instances:
        if isinstance(instance.cls, Union):
          # Having instance.cls be a Union type will crash in attribute.py.
          # Setting it to Any picks up the annotation in another code path.
          instance.cls = self.ctx.convert.unsolvable
        else:
          self.ctx.vm.reinitialize_if_initialized(node, instance)
    log.info("Resolved late annotation %r to %r", self.expr, self._type)

  def set_type(self, typ):
    # Used by annotation_utils.sub_one_annotation to substitute values into
    # recursive aliases.
    assert not self.resolved
    self.resolved = True
    self._type = typ

  def to_variable(self, node):
    if self.resolved:
      return self._type.to_variable(node)
    else:
      return _base.BaseValue.to_variable(self, node)  # pytype: disable=wrong-arg-types

  def instantiate(self, node, container=None):
    """Instantiate the pointed-to class, or record a placeholder instance."""
    if self.resolved:
      return self._type.instantiate(node, container)
    else:
      instance = _instance_base.Instance(self, self.ctx)
      self._unresolved_instances.add(instance)
      return instance.to_variable(node)

  def get_special_attribute(self, node, name, valself):
    if name == "__getitem__" and not self.resolved:
      container = _base.BaseValue.to_annotation_container(self)  # pytype: disable=wrong-arg-types
      return container.get_special_attribute(node, name, valself)
    return self._type.get_special_attribute(node, name, valself)

  def is_late_annotation(self):
    return True

  def is_recursive(self):
    """Check whether this is a recursive type."""
    if not self.resolved:
      return False
    seen = {id(self)}
    stack = [self._type]
    while stack:
      t = stack.pop()
      if t.is_late_annotation():
        if id(t) in seen:
          return True
        seen.add(id(t))
      if isinstance(t, mixin.NestedAnnotation):
        stack.extend(child for _, child in t.get_inner_types())
    return False
