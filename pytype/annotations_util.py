"""Utilities for inline type annotations."""

import sys

from pytype import abstract
from pytype import abstract_utils
from pytype import mixin
from pytype import utils
from pytype.overlays import typing_overlay


class AnnotationsUtil(utils.VirtualMachineWeakrefMixin):
  """Utility class for inline type annotations."""

  def sub_annotations(self, node, annotations, substs, instantiate_unbound):
    """Apply type parameter substitutions to a dictionary of annotations."""
    if substs and all(substs):
      return {name: self.sub_one_annotation(node, annot, substs,
                                            instantiate_unbound)
              for name, annot in annotations.items()}
    return annotations

  def sub_one_annotation(self, node, annot, substs, instantiate_unbound=True):
    """Apply type parameter substitutions to an annotation."""
    if isinstance(annot, abstract.TypeParameter):
      def contains(subst, annot):
        return (annot.full_name in subst and subst[annot.full_name].bindings and
                not any(isinstance(v, abstract.AMBIGUOUS_OR_EMPTY)
                        for v in subst[annot.full_name].data))
      if all(contains(subst, annot) for subst in substs):
        vals = sum((subst[annot.full_name].data for subst in substs), [])
      elif instantiate_unbound:
        vals = annot.instantiate(node).data
      else:
        vals = [annot]
      return self.vm.convert.merge_classes(vals)
    elif isinstance(annot, abstract.ParameterizedClass):
      type_parameters = {
          name: self.sub_one_annotation(
              node, param, substs, instantiate_unbound)
          for name, param in annot.formal_type_parameters.items()}
      # annot may be a subtype of ParameterizedClass, such as TupleClass.
      if isinstance(annot, abstract.LiteralClass):
        # We can't create a LiteralClass because we don't have a concrete value.
        typ = abstract.ParameterizedClass
      else:
        typ = annot.__class__
      return typ(annot.base_cls, type_parameters, self.vm, annot.template)
    elif isinstance(annot, abstract.Union):
      options = tuple(self.sub_one_annotation(node, o, substs,
                                              instantiate_unbound)
                      for o in annot.options)
      return annot.__class__(options, self.vm)
    return annot

  def remove_late_annotations(self, annot):
    """Replace unresolved late annotations with unsolvables."""
    if annot.is_late_annotation() and not annot.resolved:
      return self.vm.convert.unsolvable
    elif isinstance(annot, abstract.ParameterizedClass):
      type_parameters = {
          name: self.remove_late_annotations(param)
          for name, param in annot.formal_type_parameters.items()}
      # annot may be a subtype of ParameterizedClass, such as TupleClass.
      if isinstance(annot, abstract.LiteralClass):
        # We can't create a LiteralClass because we don't have a concrete value.
        typ = abstract.ParameterizedClass
      else:
        typ = annot.__class__
      return typ(annot.base_cls, type_parameters, self.vm, annot.template)
    elif isinstance(annot, abstract.Union):
      options = tuple(self.remove_late_annotations(o) for o in annot.options)
      return annot.__class__(options, self.vm)
    return annot

  def add_scope(self, annot, types, module):
    """Add scope for type parameters.

    In original type class, all type parameters that should be added a scope
    will be replaced with a new copy.

    Args:
      annot: The type class.
      types: A type name list that should be added a scope.
      module: Module name.

    Returns:
      The type with fresh type parameters that have been added the scope.
    """
    if isinstance(annot, abstract.TypeParameter):
      if annot.name in types:
        new_annot = annot.copy()
        new_annot.module = module
        return new_annot
      return annot
    elif isinstance(annot, abstract.TupleClass):
      annot.formal_type_parameters[abstract_utils.T] = self.add_scope(
          annot.formal_type_parameters[abstract_utils.T], types, module)
      return annot
    elif isinstance(annot, abstract.ParameterizedClass):
      for key, val in annot.formal_type_parameters.items():
        annot.formal_type_parameters[key] = self.add_scope(val, types, module)
      return annot
    elif isinstance(annot, abstract.Union):
      annot.options = tuple(self.add_scope(option, types, module)
                            for option in annot.options)
      return annot
    return annot

  def get_type_parameters(self, annot, seen=None):
    """Returns all the TypeParameter instances that appear in the annotation.

    Note that if you just need to know whether or not the annotation contains
    type parameters, you can check its `.formal` attribute.

    Args:
      annot: An annotation.
      seen: A seen set.
    """
    seen = seen or set()
    if annot in seen:
      return []
    if isinstance(annot, abstract.ParameterizedClass):
      # We track parameterized classes to avoid recursion errors when a class
      # contains itself.
      seen = seen | {annot}
    if isinstance(annot, abstract.TypeParameter):
      return [annot]
    elif isinstance(annot, abstract.TupleClass):
      return self.get_type_parameters(
          annot.formal_type_parameters[abstract_utils.T], seen)
    elif isinstance(annot, abstract.ParameterizedClass):
      return sum((self.get_type_parameters(p, seen)
                  for p in annot.formal_type_parameters.values()), [])
    elif isinstance(annot, abstract.Union):
      return sum((self.get_type_parameters(o, seen) for o in annot.options), [])
    return []

  def convert_function_type_annotation(self, name, typ):
    visible = typ.data
    if len(visible) > 1:
      self.vm.errorlog.ambiguous_annotation(self.vm.frames, visible, name)
      return None
    else:
      return visible[0]

  def convert_function_annotations(self, node, raw_annotations):
    """Convert raw annotations to a {name: annotation} dict."""
    if raw_annotations:
      # {"i": int, "return": str} is stored as (int, str, ("i", "return"))
      names = abstract_utils.get_atomic_python_constant(raw_annotations[-1])
      type_list = raw_annotations[:-1]
      annotations_list = []
      for name, t in zip(names, type_list):
        name = abstract_utils.get_atomic_python_constant(name)
        t = self.convert_function_type_annotation(name, t)
        annotations_list.append((name, t))
      return self.convert_annotations_list(node, annotations_list)
    else:
      return {}

  def convert_annotations_list(self, node, annotations_list):
    """Convert a (name, raw_annot) list to a {name: annotation} dict."""
    annotations = {}
    for name, t in annotations_list:
      if t is None:
        continue
      annot = self._process_one_annotation(
          node, t, name, self.vm.simple_stack())
      if annot is not None:
        annotations[name] = annot
    return annotations

  def convert_class_annotations(self, node, raw_annotations):
    """Convert a name -> raw_annot dict to annotations."""
    annotations = {}
    raw_items = raw_annotations.items()
    if sys.version_info[:2] < (3, 6):
      # Make sure annotation errors are reported in a deterministic order.
      raw_items = sorted(raw_items, key=str)
    for name, t in raw_items:
      # Don't use the parameter name, since it's often something unhelpful
      # like `0`.
      annot = self._process_one_annotation(
          node, t, None, self.vm.simple_stack())
      annotations[name] = annot or self.vm.convert.unsolvable
    return annotations

  def apply_annotation(self, state, op, name, value):
    """If there is an annotation for the op, return its value."""
    assert op is self.vm.frame.current_opcode
    if op.code.co_filename != self.vm.filename:
      return None, value
    if not op.annotation:
      return None, value
    annot = op.annotation
    frame = self.vm.frame
    var, errorlog = abstract_utils.eval_expr(
        self.vm, state.node, frame.f_globals, frame.f_locals, annot)
    if errorlog:
      self.vm.errorlog.invalid_annotation(
          self.vm.frames, annot, details=errorlog.details)
    typ = self.extract_annotation(
        state.node, var, name, self.vm.simple_stack(), is_var=True)
    _, value = self.vm.init_class(state.node, typ)
    return typ, value

  def extract_annotation(self, node, var, name, stack, is_var=False):
    try:
      typ = abstract_utils.get_atomic_value(var)
    except abstract_utils.ConversionError:
      self.vm.errorlog.ambiguous_annotation(self.vm.frames, None, name)
      return self.vm.convert.unsolvable
    typ = self._process_one_annotation(node, typ, name, stack)
    if not typ:
      return self.vm.convert.unsolvable
    if typ.formal and is_var:
      self.vm.errorlog.not_supported_yet(
          stack, "using type parameter in variable annotation")
      return self.vm.convert.unsolvable
    return typ

  def eval_multi_arg_annotation(self, node, func, annot, stack):
    """Evaluate annotation for multiple arguments (from a type comment)."""
    args, errorlog = self._eval_expr_as_tuple(node, annot, stack)
    if errorlog:
      self.vm.errorlog.invalid_function_type_comment(
          stack, annot, details=errorlog.details)
    code = func.code
    expected = code.get_arg_count()
    names = code.co_varnames

    # This is a hack.  Specifying the type of the first arg is optional in
    # class and instance methods.  There is no way to tell at this time
    # how the function will be used, so if the first arg is self or cls we
    # make it optional.  The logic is somewhat convoluted because we don't
    # want to count the skipped argument in an error message.
    if len(args) != expected:
      if expected and names[0] in ["self", "cls"]:
        expected -= 1
        names = names[1:]

    if len(args) != expected:
      self.vm.errorlog.invalid_function_type_comment(
          stack, annot,
          details="Expected %d args, %d given" % (expected, len(args)))
      return
    for name, arg in zip(names, args):
      resolved = self._process_one_annotation(node, arg, name, stack)
      if resolved is not None:
        func.signature.set_annotation(name, resolved)

  def _process_one_annotation(self, node, annotation, name, stack, seen=None):
    """Change annotation / record errors where required."""
    # Make sure we pass in a frozen snapshot of the frame stack, rather than the
    # actual stack, since late annotations need to snapshot the stack at time of
    # creation in order to get the right line information for error messages.
    assert isinstance(stack, tuple), "stack must be an immutable sequence"

    # Check for recursive type annotations so we can emit an error message
    # rather than crashing.
    if seen is None:
      seen = set()
    if annotation.is_late_annotation():
      if annotation in seen:
        self.vm.errorlog.not_supported_yet(
            stack, "Recursive type annotations",
            details="In annotation '%s' on %s" % (annotation.expr, name))
        return None
      seen = seen | {annotation}

    if isinstance(annotation, abstract.AnnotationContainer):
      annotation = annotation.base_cls

    if isinstance(annotation, typing_overlay.Union):
      self.vm.errorlog.invalid_annotation(
          stack, annotation, "Needs options", name)
      return None
    elif (name is not None and name != "return"
          and isinstance(annotation, typing_overlay.NoReturn)):
      self.vm.errorlog.invalid_annotation(
          stack, annotation, "NoReturn is not allowed", name)
      return None
    elif isinstance(annotation, abstract.Instance) and (
        annotation.cls == self.vm.convert.str_type or
        annotation.cls == self.vm.convert.unicode_type
    ):
      # String annotations : Late evaluation
      if isinstance(annotation, mixin.PythonConstant):
        expr = annotation.pyval
        if not expr:
          self.vm.errorlog.invalid_annotation(
              stack, annotation, "Cannot be an empty string", name)
          return None
        frame = self.vm.frame
        # Immediately try to evaluate the reference, generating LateAnnotation
        # objects as needed. We don't store the entire string as a
        # LateAnnotation because:
        # - Starting in 3.8, or in 3.7 with __future__.annotations, all
        #   annotations look like forward references - most of them don't need
        #   to be late evaluated.
        # - Given an expression like "Union[str, NotYetDefined]", we want to
        #   evaluate the union immediately so we don't end up with a complex
        #   LateAnnotation, which can lead to bugs when instantiated.
        with self.vm.generate_late_annotations(stack):
          v, errorlog = abstract_utils.eval_expr(
              self.vm, node, frame.f_globals, frame.f_locals, expr)
        if errorlog:
          self.vm.errorlog.copy_from(errorlog.errors, stack)
        if len(v.data) == 1:
          return self._process_one_annotation(
              node, v.data[0], name, stack, seen)
      self.vm.errorlog.ambiguous_annotation(stack, [annotation], name)
      return None
    elif annotation.cls == self.vm.convert.none_type:
      # PEP 484 allows to write "NoneType" as "None"
      return self.vm.convert.none_type
    elif isinstance(annotation, abstract.ParameterizedClass):
      for param_name, param in annotation.formal_type_parameters.items():
        processed = self._process_one_annotation(node, param, name, stack, seen)
        if processed is None:
          return None
        elif isinstance(processed, typing_overlay.NoReturn):
          self.vm.errorlog.invalid_annotation(
              stack, param, "NoReturn is not allowed as inner type", name)
          return None
        annotation.formal_type_parameters[param_name] = processed
      return annotation
    elif isinstance(annotation, abstract.Union):
      options = []
      for option in annotation.options:
        processed = self._process_one_annotation(
            node, option, name, stack, seen)
        if processed is None:
          return None
        elif isinstance(processed, typing_overlay.NoReturn):
          self.vm.errorlog.invalid_annotation(
              stack, option, "NoReturn is not allowed as inner type", name)
          return None
        options.append(processed)
      annotation.options = tuple(options)
      return annotation
    elif isinstance(annotation, (mixin.Class,
                                 abstract.AMBIGUOUS_OR_EMPTY,
                                 abstract.TypeParameter,
                                 typing_overlay.NoReturn)):
      return annotation
    else:
      self.vm.errorlog.invalid_annotation(stack, annotation, "Not a type", name)
      return None

  def _eval_expr_as_tuple(self, node, expr, stack):
    """Evaluate an expression as a tuple."""
    if not expr:
      return (), None

    f_globals, f_locals = self.vm.frame.f_globals, self.vm.frame.f_locals
    with self.vm.generate_late_annotations(stack):
      result_var, errorlog = abstract_utils.eval_expr(
          self.vm, node, f_globals, f_locals, expr)
    result = abstract_utils.get_atomic_value(result_var)
    # If the result is a tuple, expand it.
    if (isinstance(result, mixin.PythonConstant) and
        isinstance(result.pyval, tuple)):
      return (tuple(abstract_utils.get_atomic_value(x) for x in result.pyval),
              errorlog)
    else:
      return (result,), errorlog

  def deformalize(self, value):
    # type() gets the type of an object for runtime use, which requires a way to
    # turn a formal value into a non-formal one.
    while value.formal:
      if isinstance(value, abstract.ParameterizedClass):
        value = value.base_cls
      else:
        value = self.vm.convert.unsolvable
    return value
