"""Utilities for inline type annotations."""

import collections

from pytype import abstract
from pytype import function
from pytype import typing
from pytype import utils
from pytype.pyc import pyc

import six


class EvaluationError(Exception):
  """Used to signal an errorlog error during type comment evaluation."""
  pass


LateAnnotation = collections.namedtuple(
    "LateAnnotation", ["expr", "name", "stack"])


class AnnotationsUtil(object):
  """Utility class for inline type annotations."""

  # Define this error inside AnnotationsUtil so that it is exposed to typing.py.
  class LateAnnotationError(Exception):
    """Used to break out of annotation evaluation if we discover a string."""
    pass

  # A dummy container object for use in instantiating type parameters.
  DUMMY_CONTAINER = object()

  def __init__(self, vm):
    self.vm = vm

  def instantiate_for_sub(self, node, typ):
    """Instantiate this type for use only in sub_(one_)annotation(s).

    Instantiate a type using a dummy container so that it can be put in a
    substitution dictionary for use in sub_annotations or sub_one_annotation.
    The container is needed to preserve type parameters.

    Args:
      node: A cfg node.
      typ: A type.
    Returns:
      A variable of an instance of the type.
    """
    return typ.instantiate(node, container=self.DUMMY_CONTAINER)

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
      if all(annot.name in subst and subst[annot.name].bindings and
             not any(isinstance(v, abstract.AMBIGUOUS_OR_EMPTY)
                     for v in subst[annot.name].data)
             for subst in substs):
        vals = sum((subst[annot.name].data for subst in substs), [])
      elif instantiate_unbound:
        vals = annot.instantiate(node).data
      else:
        vals = [annot]
      return self.vm.convert.merge_classes(node, vals)
    elif isinstance(annot, abstract.ParameterizedClass):
      type_parameters = {name: self.sub_one_annotation(node, param, substs,
                                                       instantiate_unbound)
                         for name, param in annot.type_parameters.items()}
      # annot may be a subtype of ParameterizedClass, such as TupleClass.
      return type(annot)(annot.base_cls, type_parameters, self.vm)
    elif isinstance(annot, abstract.Union):
      options = tuple(self.sub_one_annotation(node, o, substs,
                                              instantiate_unbound)
                      for o in annot.options)
      return type(annot)(options, self.vm)
    return annot

  def get_type_parameters(self, annot):
    """Get all the TypeParameter instances that appear in the annotation."""
    if isinstance(annot, abstract.TypeParameter):
      return [annot]
    elif isinstance(annot, abstract.TupleClass):
      return self.get_type_parameters(annot.type_parameters[abstract.T])
    elif isinstance(annot, abstract.ParameterizedClass):
      return sum((self.get_type_parameters(p)
                  for p in annot.type_parameters.values()), [])
    elif isinstance(annot, abstract.Union):
      return sum((self.get_type_parameters(o) for o in annot.options), [])
    return []

  def convert_function_type_annotation(self, name, typ):
    visible = typ.data
    if len(visible) > 1:
      self.vm.errorlog.ambiguous_annotation(self.vm.frames, visible, name)
      return None
    else:
      return visible[0]

  def convert_function_annotations(self, raw_annotations):
    """Convert raw annotations to dicts of annotations and late annotations."""
    if raw_annotations:
      # {"i": int, "return": str} is stored as (int, str, ("i", "return"))
      names = abstract.get_atomic_python_constant(raw_annotations[-1])
      type_list = raw_annotations[:-1]
      annotations_list = []
      for name, t in zip(names, type_list):
        name = abstract.get_atomic_python_constant(name)
        t = self.convert_function_type_annotation(name, t)
        annotations_list.append((name, t))
      return self.convert_annotations_list(annotations_list)
    else:
      return {}, {}

  def convert_annotations_list(self, annotations_list):
    """Convert a (name, raw_annot) list to annotations and late annotations."""
    annotations = {}
    late_annotations = {}
    for name, t in annotations_list:
      if t is None:
        continue
      try:
        annot = self._process_one_annotation(t, name, self.vm.frames)
      except self.LateAnnotationError:
        late_annotations[name] = LateAnnotation(t, name, self.vm.simple_stack())
      else:
        if annot is not None:
          annotations[name] = annot
    return annotations, late_annotations

  def eval_late_annotations(self, node, func, f_globals, f_locals):
    """Resolves an instance of LateAnnotation's expression."""
    for name, annot in six.iteritems(func.signature.late_annotations):
      if name == function.MULTI_ARG_ANNOTATION:
        try:
          self._eval_multi_arg_annotation(node, func, f_globals, f_locals,
                                          annot)
        except EvaluationError as e:
          self.vm.errorlog.invalid_function_type_comment(
              annot.stack, annot.expr, details=utils.message(e))
        except abstract.ConversionError:
          self.vm.errorlog.invalid_function_type_comment(
              annot.stack, annot.expr, details="Must be constant.")
      else:
        resolved = self._process_one_annotation(
            annot.expr, annot.name, annot.stack, node, f_globals, f_locals)
        if resolved is not None:
          func.signature.set_annotation(name, resolved)
    func.signature.check_type_parameter_count(
        self.vm.simple_stack(func.get_first_opcode()))

  def apply_type_comment(self, state, op, name, value):
    """If there is a type comment for the op, return its value."""
    assert op is self.vm.frame.current_opcode
    if op.code.co_filename != self.vm.filename:
      return value
    if not op.type_comment:
      return value
    comment = op.type_comment
    try:
      var = self._eval_expr(state.node, self.vm.frame.f_globals,
                            self.vm.frame.f_locals, comment)
    except EvaluationError as e:
      self.vm.errorlog.invalid_type_comment(
          self.vm.frames, comment, details=utils.message(e))
      value = self.vm.convert.create_new_unsolvable(state.node)
    else:
      try:
        typ = abstract.get_atomic_value(var)
      except abstract.ConversionError:
        self.vm.errorlog.invalid_type_comment(
            self.vm.frames, comment, details="Must be constant.")
        value = self.vm.convert.create_new_unsolvable(state.node)
      else:
        if self.get_type_parameters(typ):
          self.vm.errorlog.not_supported_yet(
              self.vm.frames, "using type parameter in type comment")
        try:
          value = self.init_annotation(typ, name, self.vm.frames, state.node)
        except self.LateAnnotationError:
          value = LateAnnotation(typ, name, self.vm.simple_stack())
    return value

  def init_annotation(self, annot, name, stack, node, f_globals=None,
                      f_locals=None):
    processed = self._process_one_annotation(
        annot, name, stack, node, f_globals, f_locals)
    if processed is None:
      value = self.vm.convert.unsolvable.to_variable(node)
    else:
      _, _, value = self.vm.init_class(node, processed)
    return value

  def process_annotation_var(self, var, name, stack, node):
    new_var = self.vm.program.NewVariable()
    for b in var.bindings:
      annot = self._process_one_annotation(b.data, name, stack)
      if annot is None:
        return self.vm.convert.create_new_unsolvable(node)
      new_var.AddBinding(annot, {b}, node)
    return new_var

  def _eval_multi_arg_annotation(self, node, func, f_globals, f_locals, annot):
    """Evaluate annotation for multiple arguments (from a type comment)."""
    args = self._eval_expr_as_tuple(node, f_globals, f_locals, annot.expr)
    code = func.code
    expected = abstract.InterpreterFunction.get_arg_count(code)
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
          annot.stack, annot.expr,
          details="Expected %d args, %d given" % (expected, len(args)))
      return
    for name, arg in zip(names, args):
      resolved = self._process_one_annotation(arg, name, annot.stack)
      if resolved is not None:
        func.signature.set_annotation(name, resolved)

  def _process_one_annotation(self, annotation, name, stack,
                              node=None, f_globals=None, f_locals=None):
    """Change annotation / record errors where required."""
    if isinstance(annotation, abstract.AnnotationContainer):
      annotation = annotation.base_cls

    if isinstance(annotation, typing.Union):
      self.vm.errorlog.invalid_annotation(
          stack, annotation, "Needs options", name)
      return None
    elif isinstance(annotation, abstract.Instance) and (
        annotation.cls.data == [self.vm.convert.str_type] or
        annotation.cls.data == [self.vm.convert.unicode_type]
    ):
      # String annotations : Late evaluation
      if isinstance(annotation, abstract.PythonConstant):
        if f_globals is None:
          raise self.LateAnnotationError()
        else:
          try:
            v = self._eval_expr(node, f_globals, f_locals, annotation.pyval)
          except EvaluationError as e:
            self.vm.errorlog.invalid_annotation(
                stack, annotation, utils.message(e))
            return None
          if len(v.data) == 1:
            return self._process_one_annotation(
                v.data[0], name, stack, node, f_globals, f_locals)
      self.vm.errorlog.invalid_annotation(
          stack, annotation, "Must be constant", name)
      return None
    elif annotation.cls and annotation.cls.data == [self.vm.convert.none_type]:
      # PEP 484 allows to write "NoneType" as "None"
      return self.vm.convert.none_type
    elif isinstance(annotation, abstract.ParameterizedClass):
      for param_name, param in annotation.type_parameters.items():
        processed = self._process_one_annotation(
            param, name, stack, node, f_globals, f_locals)
        if processed is None:
          return None
        annotation.type_parameters[param_name] = processed
      return annotation
    elif isinstance(annotation, abstract.Union):
      options = []
      for option in annotation.options:
        processed = self._process_one_annotation(
            option, name, stack, node, f_globals, f_locals)
        if processed is None:
          return None
        options.append(processed)
      annotation.options = tuple(options)
      return annotation
    elif isinstance(annotation, (abstract.Class,
                                 abstract.AMBIGUOUS_OR_EMPTY,
                                 abstract.TypeParameter,
                                 typing.NoReturn)):
      return annotation
    else:
      self.vm.errorlog.invalid_annotation(stack, annotation, "Not a type", name)
      return None

  def _eval_expr(self, node, f_globals, f_locals, expr):
    """Evaluate and expression with the given node and globals."""
    # We don't chain node and f_globals as we want to remain in the context
    # where we've just finished evaluating the module. This would prevent
    # nasty things like:
    #
    # def f(a: "A = 1"):
    #   pass
    #
    # def g(b: "A"):
    #   pass
    #
    # Which should simply complain at both annotations that 'A' is not defined
    # in both function annotations. Chaining would cause 'b' in 'g' to yield a
    # different error message.

    # Any errors logged here will have a filename of None and a linenumber of 1
    # when what we really want is to allow the caller to handle/log the error
    # themselves.  Thus we checkpoint the errorlog and then restore and raise
    # an exception if anything was logged.
    checkpoint = self.vm.errorlog.save()
    prior_errors = len(self.vm.errorlog)
    try:
      code = self.vm.compile_src(expr, mode="eval")
    except pyc.CompileError as e:
      # We only want the error, not the full message, which includes a
      # temporary filename and line number.
      raise EvaluationError(e.error)
    if not f_locals:
      f_locals = self.vm.convert_locals_or_globals({}, "locals")
    _, _, _, ret = self.vm.run_bytecode(node, code, f_globals, f_locals)
    if len(self.vm.errorlog) > prior_errors:
      # Annotations are constants, so tracebacks aren't needed.
      new_messages = [self.vm.errorlog[i].drop_traceback().message
                      for i in range(prior_errors, len(self.vm.errorlog))]
      self.vm.errorlog.revert_to(checkpoint)
      raise EvaluationError("\n".join(new_messages))
    return ret

  def _eval_expr_as_tuple(self, node, f_globals, f_locals, expr):
    """Evaluate an expression as a tuple."""
    if not expr:
      return ()

    result = abstract.get_atomic_value(
        self._eval_expr(node, f_globals, f_locals, expr))
    # If the result is a tuple, expand it.
    if (isinstance(result, abstract.PythonConstant) and
        isinstance(result.pyval, tuple)):
      return tuple(abstract.get_atomic_value(x) for x in result.pyval)
    else:
      return (result,)
