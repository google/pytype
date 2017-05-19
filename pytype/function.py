"""Representation of Python function headers and calls."""

import collections

from pytype.pytd import utils as pytd_utils


# Used as a key in Signature.late_annotations to indicate an annotation
# for multiple arguments.  This is used for function type comments.
MULTI_ARG_ANNOTATION = "$multi$"


def argname(i):
  """Get a name for an unnamed positional argument, given its position."""
  return "_" + str(i)


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
    if (name in self.defaults and
        self.defaults[name].data == [annotation.vm.convert.none]):
      annotation = annotation.vm.convert.optionalize(annotation)
    if name == self.varargs_name:
      return annotation.vm.convert.create_new_varargs_value(annotation)
    elif name == self.kwargs_name:
      return annotation.vm.convert.create_new_kwargs_value(annotation)
    else:
      return annotation

  def set_annotation(self, name, annotation):
    self.annotations[name] = self._postprocess_annotation(name, annotation)
    if name == "return":
      self.has_return_annotation = True
    else:
      self.has_param_annotations = True

  def check_type_parameter_count(self, stack):
    c = collections.Counter()
    for annot in self.annotations.values():
      c.update(annot.vm.annotations_util.get_type_parameters(annot))
    for param, count in c.iteritems():
      if count == 1 and not (param.constraints or param.bound or
                             param.covariant or param.contravariant):
        param.vm.errorlog.invalid_annotation(
            stack, param, "Appears only once in the signature")

  def drop_first_parameter(self):
    return self._replace(param_names=self.param_names[1:])

  def mandatory_param_count(self):
    num = len([name
               for name in self.param_names if name not in self.defaults])
    num += len([name
                for name in self.kwonly_params if name not in self.defaults])
    return num

  def maximum_param_count(self):
    if self.varargs_name or self.kwargs_name:
      return None
    return len(self.param_names) + len(self.kwonly_params)

  @classmethod
  def from_pytd(cls, vm, name, sig):
    """Construct an abstract signature from a pytd signature."""
    # TODO(kramm): templates
    pytd_annotations = [(p.name, p.type)
                        for p in sig.params + (sig.starargs, sig.starstarargs)
                        if p is not None]
    pytd_annotations.append(("return", sig.return_type))
    return cls(
        name=name,
        param_names=tuple(p.name for p in sig.params if not p.kwonly),
        varargs_name=None if sig.starargs is None else sig.starargs.name,
        kwonly_params=set(p.name for p in sig.params if p.kwonly),
        kwargs_name=None if sig.starstarargs is None else sig.starstarargs.name,
        defaults={p.name: vm.convert.constant_to_var(
            p.type, subst={}, node=vm.root_cfg_node)
                  for p in sig.params
                  if p.optional},
        annotations={name: vm.convert.constant_to_value(
            typ, subst={}, node=vm.root_cfg_node)
                     for name, typ in pytd_annotations},
        late_annotations={},
        postprocess_annotations=False,
    )

  @classmethod
  def from_callable(cls, val):
    annotations = {argname(i): val.type_parameters[i]
                   for i in range(val.num_args)}
    return cls(
        name=val.name,
        param_names=tuple(sorted(annotations)),
        varargs_name=None,
        kwonly_params=set(),
        kwargs_name=None,
        defaults={},
        annotations=annotations,
        late_annotations={}
    )

  def has_param(self, name):
    return name in self.param_names or name in self.kwonly_params or (
        name == self.varargs_name or name == self.kwargs_name)

  def insert_varargs_and_kwargs(self, arg_dict):
    """Insert varargs and kwargs from arg_dict into the signature.

    Args:
      arg_dict: A name->binding dictionary of passed args.

    Returns:
      A copy of this signature with the passed varargs and kwargs inserted.
    """
    varargs_names = []
    kwargs_names = []
    for name in arg_dict:
      if self.has_param(name):
        continue
      if pytd_utils.ANON_PARAM.match(name):
        varargs_names.append(name)
      else:
        kwargs_names.append(name)
    new_param_names = (self.param_names + tuple(sorted(varargs_names)) +
                       tuple(sorted(kwargs_names)))
    return self._replace(param_names=new_param_names)

  _ATTRIBUTES = (
      set(__init__.__code__.co_varnames[:__init__.__code__.co_argcount]) -
      {"self", "postprocess_annotations"})

  def _replace(self, **kwargs):
    """Returns a copy of the signature with the specified values replaced."""
    assert not set(kwargs) - self._ATTRIBUTES
    for attr in self._ATTRIBUTES:
      if attr not in kwargs:
        kwargs[attr] = getattr(self, attr)
    kwargs["postprocess_annotations"] = False
    return type(self)(**kwargs)  # pytype: disable=missing-parameter

  def iter_args(self, args):
    """Iterates through the given args, attaching names and expected types."""
    for i, posarg in enumerate(args.posargs):
      if i < len(self.param_names):
        name = self.param_names[i]
        yield (name, posarg, self.annotations.get(name))
      else:
        yield (argname(i), posarg, None)
    for name, namedarg in sorted(args.namedargs.items()):
      yield (name, namedarg, self.annotations.get(name))
    if self.varargs_name is not None and args.starargs is not None:
      yield (self.varargs_name, args.starargs,
             self.annotations.get(self.varargs_name))
    if self.kwargs_name is not None and args.starstarargs is not None:
      yield (self.kwargs_name, args.starstarargs,
             self.annotations.get(self.kwargs_name))
