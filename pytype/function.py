"""Representation of Python function headers and calls."""

import collections

from pytype.pytd import pytd_utils
import six


# Used as a key in Signature.late_annotations to indicate an annotation
# for multiple arguments.  This is used for function type comments.
MULTI_ARG_ANNOTATION = "$multi$"


def argname(i):
  """Get a name for an unnamed positional argument, given its position."""
  return "_" + str(i)


def _print(t):
  return pytd_utils.Print(t.get_instance_type())


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
    if postprocess_annotations:
      for name, annot in six.iteritems(self.annotations):
        self.annotations[name] = self._postprocess_annotation(name, annot)

  @property
  def has_return_annotation(self):
    return "return" in self.annotations

  @property
  def has_param_annotations(self):
    return bool(six.viewkeys(self.annotations) - {"return"})

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

  def del_annotation(self, name):
    del self.annotations[name]  # Raises KeyError if annotation does not exist.

  def check_type_parameter_count(self, stack):
    c = collections.Counter()
    for annot in self.annotations.values():
      c.update(annot.vm.annotations_util.get_type_parameters(annot))
    for param, count in six.iteritems(c):
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
        name="<callable>",
        param_names=tuple(sorted(annotations)),
        varargs_name=None,
        kwonly_params=set(),
        kwargs_name=None,
        defaults={},
        annotations=annotations,
        late_annotations={}
    )

  @classmethod
  def from_param_names(cls, name, param_names):
    """Construct a minimal signature from a name and a list of param names."""
    return cls(
        name=name,
        param_names=tuple(param_names),
        varargs_name=None,
        kwonly_params=set(),
        kwargs_name=None,
        defaults={},
        annotations={},
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
      elif self.varargs_name and self.varargs_name in self.annotations:
        varargs_type = self.annotations[self.varargs_name]
        formal = varargs_type.vm.convert.get_element_type(varargs_type)
        yield (argname(i), posarg, formal)
      else:
        yield (argname(i), posarg, None)
    for name, namedarg in sorted(args.namedargs.items()):
      formal = self.annotations.get(name)
      if formal is None and self.kwargs_name:
        kwargs_type = self.annotations.get(self.kwargs_name)
        if kwargs_type:
          formal = kwargs_type.vm.convert.get_element_type(kwargs_type)
      yield (name, namedarg, formal)
    if self.varargs_name is not None and args.starargs is not None:
      yield (self.varargs_name, args.starargs,
             self.annotations.get(self.varargs_name))
    if self.kwargs_name is not None and args.starstarargs is not None:
      yield (self.kwargs_name, args.starstarargs,
             self.annotations.get(self.kwargs_name))

  def _yield_arguments(self):
    names = list(self.param_names)
    if self.varargs_name:
      names.append("*" + self.varargs_name)
    elif self.kwonly_params:
      names.append("*")
    names.extend(sorted(self.kwonly_params))
    if self.kwargs_name:
      names.append("**" + self.kwargs_name)
    for name in names:
      base_name = name.lstrip("*")
      annot = self._print_annot(base_name)
      default = self._print_default(base_name)
      yield name + (": " + annot if annot else "") + (
          " = " + default if default else "")

  def _print_annot(self, name):
    if name in self.annotations:
      return _print(self.annotations[name])
    elif name in self.late_annotations:
      return repr(self.late_annotations[name].expr)
    else:
      return None

  def _print_default(self, name):
    if name in self.defaults:
      values = self.defaults[name].data
      if len(values) > 1:
        return "Union[%s]" % ", ".join(_print(v) for v in values)
      else:
        return _print(values[0])
    else:
      return None

  def __repr__(self):
    args = ", ".join(self._yield_arguments())
    ret = self._print_annot("return")
    return "def {name}({args}) -> {ret}".format(
        name=self.name, args=args, ret=ret if ret else "Any")
