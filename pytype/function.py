"""Representation of Python function headers and calls."""

import collections



LateAnnotation = collections.namedtuple(
    "LateAnnotation", ["expr", "name", "opcode"])


# Used as a key in Signature.late_annotations to indicate an annotation
# for multiple arguments.  This is used for function type comments.
MULTI_ARG_ANNOTATION = "$multi$"


# TODO(kramm): This class is deprecated and should be folded into
# abstract.InterpreterFunction and/or pytd.Signature.
class Signature(object):
  """Representation of a Python function signature.

  Attributes:
    name: Name of the function.
    param_names: A tuple of positional parameter names.
    varargs_name: Name of the varargs parameter. (The "args" in *args)
    kwonly_params: Tuple of keyword-only parameters. (Python 3)
      E.g. ("x", "y") for "def f(a, *, x, y=2)". These do NOT appear in
      param_names. Ordered like in the source file.
    kwargs_name: Name of the kwargs parameter. (The "kwargs" in **kwargs)
    defaults: Dictionary, name to value, for all parameters with default values.
    annotations: A dictionary of type annotations (string to type)
  """

  def __init__(self, name, param_names, varargs_name, kwonly_params,
               kwargs_name, defaults, annotations, late_annotations,
               postprocess_annotations=True):
    self.name = name
    self.param_names = param_names
    self.varargs_name = varargs_name
    self.kwonly_params = kwonly_params
    self.kwargs_name = kwargs_name
    self.defaults = defaults
    self.annotations = annotations
    self.late_annotations = late_annotations
    self.has_return_annotation = "return" in annotations
    self.has_param_annotations = bool(annotations.viewkeys() - {"return"})
    if postprocess_annotations:
      for name, annot in self.annotations.iteritems():
        self.annotations[name] = self._postprocess_annotation(name, annot)

  def _postprocess_annotation(self, name, annotation):
    convert = annotation.vm.convert
    if name == self.varargs_name:
      return convert.create_new_varargs_value(annotation)
    elif name == self.kwargs_name:
      return convert.create_new_kwargs_value(annotation)
    else:
      return annotation

  def set_annotation(self, name, annotation):
    self.annotations[name] = self._postprocess_annotation(name, annotation)
    if name == "return":
      self.has_return_annotation = True
    else:
      self.has_param_annotations = True

  def drop_first_parameter(self):
    return self.__class__(
        self.name,
        self.param_names[1:],
        self.varargs_name,
        self.kwonly_params,
        self.kwargs_name,
        self.defaults,
        self.annotations,
        self.late_annotations,
        postprocess_annotations=False,
    )

  def mandatory_param_count(self):
    num = len([name
               for name in self.param_names if name not in self.defaults])
    num += len([name
                for name in self.kwonly_params if name not in self.defaults])
    return num

  @classmethod
  def from_pytd(cls, vm, name, sig):
    """Construct an abstract signature from a pytd signature."""
    # TODO(kramm): templates
    return cls(
        name=name,
        param_names=tuple(p.name for p in sig.params if not p.kwonly),
        varargs_name=None if sig.starargs is None else sig.starargs.name,
        kwonly_params=set(p.name for p in sig.params if p.kwonly),
        kwargs_name=None if sig.starstarargs is None else sig.starstarargs.name,
        defaults=[p.name
                  for p in sig.params
                  if p.optional],
        annotations={p.name: vm.convert.constant_to_value(
            p.name, p.type, subst={}, node=vm.root_cfg_node)
                     for p in sig.params + (sig.starargs, sig.starstarargs)
                     if p is not None},
        late_annotations={}
    )

  def iter_args(self, args):
    """Iterates through the given args, attaching names and expected types."""
    for i, posarg in enumerate(args.posargs):
      if i < len(self.param_names):
        name = self.param_names[i]
        yield (name, posarg, self.annotations.get(name))
      else:
        yield ("_" + str(i), posarg, None)
    for name, namedarg in args.namedargs.items():
      yield (name, namedarg, self.annotations.get(name))
    if self.varargs_name is not None and args.starargs is not None:
      yield (self.varargs_name, args.starargs,
             self.annotations.get(self.varargs_name))
    if self.kwargs_name is not None and args.starstarargs is not None:
      yield (self.kwargs_name, args.starstarargs,
             self.annotations.get(self.kwargs_name))
