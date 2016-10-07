"""Representation of Python function headers and calls."""

import collections



LateAnnotation = collections.namedtuple(
    "LateAnnotation", ["expr", "name", "opcode"])


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
               kwargs_name, defaults, annotations, late_annotations):
    self.name = name
    self.param_names = param_names
    self.varargs_name = varargs_name
    self.kwonly_params = kwonly_params
    self.kwargs_name = kwargs_name
    self.defaults = defaults
    self.annotations = annotations
    self.late_annotations = late_annotations
    self.has_return_annotation = (("return" in annotations) or
                                  ("return" in late_annotations))
    self.has_param_annotations = bool(annotations.viewkeys() - {"return"})

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
    )

  def mandatory_param_count(self):
    num = len([name
               for name in self.param_names if name not in self.defaults])
    num += len([name
                for name in self.kwonly_params if name not in self.defaults])
    return num

  @classmethod
  def from_pytd(cls, vm, name, sig):
    # TODO(kramm): templates
    return cls(
        name=name,
        param_names=tuple(p.name for p in sig.params if not p.kwonly),
        varargs_name="args" if sig.has_optional else None,
        kwonly_params=set(p.name for p in sig.params if p.kwonly),
        kwargs_name="kwargs" if sig.has_optional else None,
        defaults=[p.name
                  for p in sig.params
                  if p.optional],
        annotations={p.name: vm.convert.convert_constant_to_value(
            p.name, p.type, subst={}, node=vm.root_cfg_node)
                     for p in sig.params},
        late_annotations={}
    )

  def __str__(self):
    def default_suffix(name):
      return " = ..." if name in self.defaults else ""
    def annotate(name):
      if name in self.annotations:
        return name + ": " + str(self.annotations[name]) + default_suffix(name)
      else:
        return name + default_suffix(name)
    s = []
    for name in self.param_names:
      s.append(annotate(name))
    if self.varargs_name is not None:
      s.append("*" + annotate(self.varargs_name))
    elif self.kwonly_params:
      s.append("*")
    for name in self.kwonly_params:
      s.append(annotate(name))
    if self.kwargs_name is not None:
      s.append("**" + annotate(self.kwargs_name))
    return ", ".join(s)

  def iter_args(self, posargs, namedargs, starargs, starstarargs):
    for name, posarg in zip(self.param_names, posargs):
      yield (name, posarg, self.annotations.get(name))
    for name, namedarg in namedargs.items():
      yield (name, namedarg, self.annotations.get(name))
    if self.varargs_name is not None and starargs is not None:
      yield (self.varargs_name, starargs,
             self.annotations.get(self.varargs_name))
    if self.kwargs_name is not None and starstarargs is not None:
      yield (self.kwargs_name, starstarargs,
             self.annotations.get(self.kwargs_name))
