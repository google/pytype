"""Representation of Python function headers and calls."""

import abc
import collections
import dataclasses
import itertools
import logging
from typing import Dict, Optional, Sequence, Tuple

import attrs

from pytype import datatypes
from pytype.abstract import _base
from pytype.abstract import abstract_utils
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils

log = logging.getLogger(__name__)
_isinstance = abstract_utils._isinstance  # pylint: disable=protected-access
_make = abstract_utils._make  # pylint: disable=protected-access


def argname(i):
  """Get a name for an unnamed positional argument, given its position."""
  return "_" + str(i)


def get_signatures(func):
  """Gets the given function's signatures."""
  if _isinstance(func, "PyTDFunction"):
    return [sig.signature for sig in func.signatures]
  elif _isinstance(func, "InterpreterFunction"):
    return [f.signature for f in func.signature_functions()]
  elif _isinstance(func, "BoundFunction"):
    sigs = get_signatures(func.underlying)
    return [sig.drop_first_parameter() for sig in sigs]  # drop "self"
  elif _isinstance(func, ("ClassMethod", "StaticMethod")):
    return get_signatures(func.method)
  elif _isinstance(func, "SignedFunction"):
    return [func.signature]
  elif _isinstance(func, "AMBIGUOUS_OR_EMPTY"):
    return [Signature.from_any()]
  elif func.__class__.__name__ == "PropertyInstance":
    # NOTE: We typically do not want to treat a PropertyInstance as a callable.
    # This check is here due to a crash in the matcher when applying a method
    # decorator to a property, e.g.
    #   @abstractmethod
    #   @property
    #   def f()...
    return []
  elif _isinstance(func.cls, "CallableClass"):
    return [Signature.from_callable(func.cls)]
  else:
    unwrapped = abstract_utils.maybe_unwrap_decorated_function(func)
    if unwrapped:
      return list(itertools.chain.from_iterable(
          get_signatures(f) for f in unwrapped.data))
    if _isinstance(func, "Instance"):
      _, call_var = func.ctx.attribute_handler.get_attribute(
          func.ctx.root_node, func, "__call__",
          func.to_binding(func.ctx.root_node))
      if call_var and len(call_var.data) == 1:
        return get_signatures(call_var.data[0])
    raise NotImplementedError(func.__class__.__name__)


def _print(t):
  return pytd_utils.Print(t.get_instance_type())


class Signature:
  """Representation of a Python function signature.

  Attributes:
    name: Name of the function.
    param_names: A tuple of positional parameter names. This DOES include
      positional-only parameters and does NOT include keyword-only parameters.
    posonly_count: Number of positional-only parameters. (Python 3.8)
    varargs_name: Name of the varargs parameter. (The "args" in *args)
    kwonly_params: Tuple of keyword-only parameters. (Python 3)
      E.g. ("x", "y") for "def f(a, *, x, y=2)". These do NOT appear in
      param_names. Ordered like in the source file.
    kwargs_name: Name of the kwargs parameter. (The "kwargs" in **kwargs)
    defaults: Dictionary, name to value, for all parameters with default values.
    annotations: A dictionary of type annotations. (string to type)
    excluded_types: A set of type names that will be ignored when checking the
      count of type parameters.
    type_params: The set of type parameter names that appear in annotations.
    has_return_annotation: Whether the function has a return annotation.
    has_param_annotations: Whether the function has parameter annotations.
    posonly_params: Tuple of positional-only parameters (i.e., the first
      posonly_count names in param_names).
  """

  def __init__(self, name, param_names, posonly_count, varargs_name,
               kwonly_params, kwargs_name, defaults, annotations,
               postprocess_annotations=True):
    self.name = name
    self.param_names = param_names
    self.posonly_count = posonly_count
    self.varargs_name = varargs_name
    self.kwonly_params = kwonly_params
    self.kwargs_name = kwargs_name
    self.defaults = defaults
    self.annotations = annotations
    self.excluded_types = set()
    if postprocess_annotations:
      for k, annot in self.annotations.items():
        self.annotations[k] = self._postprocess_annotation(k, annot)
    self.type_params = set()
    for annot in self.annotations.values():
      self.type_params.update(
          p.name for p in annot.ctx.annotation_utils.get_type_parameters(annot))

  @property
  def has_return_annotation(self):
    return "return" in self.annotations

  @property
  def has_param_annotations(self):
    return bool(self.annotations.keys() - {"return"})

  @property
  def posonly_params(self):
    return self.param_names[:self.posonly_count]

  def add_scope(self, module):
    """Add scope for type parameters in annotations."""
    annotations = {}
    for key, val in self.annotations.items():
      annotations[key] = val.ctx.annotation_utils.add_scope(
          val, self.excluded_types, module)
    self.annotations = annotations

  def _postprocess_annotation(self, name, annotation):
    """Postprocess the given annotation."""
    ctx = annotation.ctx
    if name == self.varargs_name:
      return _make("ParameterizedClass",
                   ctx.convert.tuple_type, {abstract_utils.T: annotation}, ctx)
    elif name == self.kwargs_name:
      params = {abstract_utils.K: ctx.convert.str_type,
                abstract_utils.V: annotation}
      return _make("ParameterizedClass", ctx.convert.dict_type, params, ctx)
    else:
      return annotation

  def set_annotation(self, name, annotation):
    self.annotations[name] = self._postprocess_annotation(name, annotation)

  def del_annotation(self, name):
    del self.annotations[name]  # Raises KeyError if annotation does not exist.

  def check_type_parameter_count(self, stack):
    """Check the count of type parameters in function."""
    c = collections.Counter()
    for annot in self.annotations.values():
      c.update(annot.ctx.annotation_utils.get_type_parameters(annot))
    for param, count in c.items():
      if param.name in self.excluded_types:
        # skip all the type parameters in `excluded_types`
        continue
      if count == 1 and not (param.constraints or param.bound or
                             param.covariant or param.contravariant):
        param.ctx.errorlog.invalid_annotation(
            stack, param, (f"TypeVar {param.name!r} appears only once in the "
                           "function signature"))

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
  def from_pytd(cls, ctx, name, sig):
    """Construct an abstract signature from a pytd signature."""
    pytd_annotations = [(p.name, p.type)
                        for p in sig.params + (sig.starargs, sig.starstarargs)
                        if p is not None]
    pytd_annotations.append(("return", sig.return_type))
    def param_to_var(p):
      return ctx.convert.constant_to_var(
          p.type, subst=datatypes.AliasingDict(), node=ctx.root_node)

    param_names = []
    posonly_count = 0
    kwonly_params = []
    for p in sig.params:
      if p.kind == pytd.ParameterKind.KWONLY:
        kwonly_params.append(p.name)
        continue
      param_names.append(p.name)
      posonly_count += p.kind == pytd.ParameterKind.POSONLY
    return cls(
        name=name,
        param_names=tuple(param_names),
        posonly_count=posonly_count,
        varargs_name=None if sig.starargs is None else sig.starargs.name,
        kwonly_params=tuple(kwonly_params),
        kwargs_name=None if sig.starstarargs is None else sig.starstarargs.name,
        defaults={p.name: param_to_var(p) for p in sig.params if p.optional},
        annotations={
            name: ctx.convert.constant_to_value(
                typ, subst=datatypes.AliasingDict(), node=ctx.root_node)
            for name, typ in pytd_annotations
        },
        postprocess_annotations=False,
    )

  @classmethod
  def from_callable(cls, val):
    annotations = {argname(i): val.formal_type_parameters[i]
                   for i in range(val.num_args)}
    param_names = tuple(sorted(annotations))
    annotations["return"] = val.formal_type_parameters[abstract_utils.RET]
    return cls(
        name="<callable>",
        param_names=param_names,
        posonly_count=0,
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations=annotations,
    )

  @classmethod
  def from_param_names(cls, name, param_names, kind=pytd.ParameterKind.REGULAR):
    """Construct a minimal signature from a name and a list of param names."""
    names = tuple(param_names)
    if kind == pytd.ParameterKind.REGULAR:
      param_names = names
      posonly_count = 0
      kwonly_params = ()
    elif kind == pytd.ParameterKind.POSONLY:
      param_names = names
      posonly_count = len(names)
      kwonly_params = ()
    else:
      assert kind == pytd.ParameterKind.KWONLY
      param_names = ()
      posonly_count = 0
      kwonly_params = names
    return cls(
        name=name,
        param_names=param_names,
        posonly_count=posonly_count,
        varargs_name=None,
        kwonly_params=kwonly_params,
        kwargs_name=None,
        defaults={},
        annotations={},
    )

  @classmethod
  def from_any(cls):
    """Treat `Any` as `f(...) -> Any`."""
    return cls(
        name="<callable>",
        param_names=(),
        posonly_count=0,
        varargs_name="args",
        kwonly_params=(),
        kwargs_name="kwargs",
        defaults={},
        annotations={},
    )

  def has_param(self, name):
    return name in self.param_names or name in self.kwonly_params or (
        name == self.varargs_name or name == self.kwargs_name)

  def insert_varargs_and_kwargs(self, args):
    """Insert varargs and kwargs from args into the signature.

    Args:
      args: An iterable of passed arg names.

    Returns:
      A copy of this signature with the passed varargs and kwargs inserted.
    """
    varargs_names = []
    kwargs_names = []
    for name in args:
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
    return type(self)(**kwargs)

  def iter_args(self, args):
    """Iterates through the given args, attaching names and expected types."""
    for i, posarg in enumerate(args.posargs):
      if i < len(self.param_names):
        name = self.param_names[i]
        yield (name, posarg, self.annotations.get(name))
      elif self.varargs_name and self.varargs_name in self.annotations:
        varargs_type = self.annotations[self.varargs_name]
        formal = varargs_type.ctx.convert.get_element_type(varargs_type)
        yield (argname(i), posarg, formal)
      else:
        yield (argname(i), posarg, None)
    for name in sorted(args.namedargs):
      namedarg = args.namedargs[name]
      if name in self.param_names[:self.posonly_count]:
        formal = None
      else:
        formal = self.annotations.get(name)
      if formal is None and self.kwargs_name:
        kwargs_type = self.annotations.get(self.kwargs_name)
        if kwargs_type:
          formal = kwargs_type.ctx.convert.get_element_type(kwargs_type)
      yield (name, namedarg, formal)
    if self.varargs_name is not None and args.starargs is not None:
      yield (self.varargs_name, args.starargs,
             self.annotations.get(self.varargs_name))
    if self.kwargs_name is not None and args.starstarargs is not None:
      yield (self.kwargs_name, args.starstarargs,
             self.annotations.get(self.kwargs_name))

  def check_defaults(self, ctx):
    """Raises an error if a non-default param follows a default."""
    has_default = False
    for name in self.param_names:
      if name in self.defaults:
        has_default = True
      elif has_default:
        msg = (f"In method {self.name}, non-default argument {name} "
               "follows default argument")
        ctx.errorlog.invalid_function_definition(ctx.vm.frames, msg)
        return

  def _yield_arguments(self):
    """Yield all the function arguments."""
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
    return _print(self.annotations[name]) if name in self.annotations else None

  def _print_default(self, name):
    if name in self.defaults:
      values = self.defaults[name].data
      if len(values) > 1:
        return "..."
      else:
        return abstract_utils.show_constant(values[0])
    else:
      return None

  def __repr__(self):
    args = list(self._yield_arguments())
    if self.posonly_count:
      args = args[:self.posonly_count] + ["/"] + args[self.posonly_count:]
    args = ", ".join(args)
    ret = self._print_annot("return")
    return f"def {self.name}({args}) -> {ret if ret else 'Any'}"

  def get_self_arg(self, callargs):
    """Returns the 'self' or 'cls' arg, if any."""
    if self.param_names and self.param_names[0] in ("self", "cls"):
      return callargs.get(self.param_names[0])
    else:
      return None

  def get_first_arg(self, callargs):
    """Returns the first non-self/cls arg, if any."""
    if not self.param_names:
      return None
    elif self.param_names[0] not in ("self", "cls"):
      name = self.param_names[0]
    elif len(self.param_names) > 1:
      name = self.param_names[1]
    else:
      return None
    return callargs.get(name)


def _convert_namedargs(namedargs):
  return {} if namedargs is None else namedargs


@attrs.frozen(eq=True)
class Args:
  """Represents the parameters of a function call.

  Attributes:
    posargs: The positional arguments. A tuple of cfg.Variable.
    namedargs: The keyword arguments. A dictionary, mapping strings to
      cfg.Variable.
    starargs: The *args parameter, or None.
    starstarargs: The **kwargs parameter, or None.

  """

  posargs: Tuple[cfg.Variable, ...]
  namedargs: Dict[str, cfg.Variable] = attrs.field(converter=_convert_namedargs,
                                                   default=None)
  starargs: Optional[cfg.Variable] = None
  starstarargs: Optional[cfg.Variable] = None

  def has_namedargs(self):
    return bool(self.namedargs)

  def has_non_namedargs(self):
    return bool(self.posargs or self.starargs or self.starstarargs)

  def is_empty(self):
    return not (self.has_namedargs() or self.has_non_namedargs())

  def starargs_as_tuple(self, node, ctx):
    try:
      args = self.starargs and abstract_utils.get_atomic_python_constant(
          self.starargs, tuple)
    except abstract_utils.ConversionError:
      args = None
    if not args:
      return args
    return tuple(
        var if var.bindings else ctx.convert.empty.to_variable(node)
        for var in args)

  def starstarargs_as_dict(self):
    """Return **args as a python dict."""
    # NOTE: We can't use get_atomic_python_constant here because starstarargs
    # could have could_contain_anything set.
    if not self.starstarargs or len(self.starstarargs.data) != 1:
      return None
    kwdict, = self.starstarargs.data
    if not _isinstance(kwdict, "Dict"):
      return None
    return kwdict.pyval

  def _expand_typed_star(self, ctx, node, star, count):
    """Convert *xs: Sequence[T] -> [T, T, ...]."""
    if not count:
      return []
    p = abstract_utils.merged_type_parameter(node, star, abstract_utils.T)
    if not p.bindings:
      # TODO(b/159052609): This shouldn't happen. For some reason,
      # namedtuple instances don't have any bindings in T; see
      # tests/test_unpack:TestUnpack.test_unpack_namedtuple.
      return [ctx.new_unsolvable(node) for _ in range(count)]
    return [p.AssignToNewVariable(node) for _ in range(count)]

  def _unpack_and_match_args(self, node, ctx, match_signature, starargs_tuple):
    """Match args against a signature with unpacking."""
    posargs = self.posargs
    namedargs = self.namedargs
    # As we have the function signature we will attempt to adjust the
    # starargs into the missing posargs.
    pre = []
    post = []
    stars = collections.deque(starargs_tuple)
    while stars and not abstract_utils.is_var_splat(stars[0]):
      pre.append(stars.popleft())
    while stars and not abstract_utils.is_var_splat(stars[-1]):
      post.append(stars.pop())
    post.reverse()
    n_matched = len(posargs) + len(pre) + len(post)
    required_posargs = 0
    for p in match_signature.param_names:
      if p in namedargs or p in match_signature.defaults:
        break
      required_posargs += 1
    posarg_delta = required_posargs - n_matched

    if stars and not post:
      star = stars[-1]
      if match_signature.varargs_name:
        # If the invocation ends with `*args`, return it to match against *args
        # in the function signature. For f(<k args>, *xs, ..., *ys), transform
        # to f(<k args>, *ys) since ys is an indefinite tuple anyway and will
        # match against all remaining posargs.
        return posargs + tuple(pre), abstract_utils.unwrap_splat(star)
      else:
        # If we do not have a `*args` in match_signature, just expand the
        # terminal splat to as many args as needed and then drop it.
        mid = self._expand_typed_star(ctx, node, star, posarg_delta)
        return posargs + tuple(pre + mid), None
    elif posarg_delta <= len(stars):
      # We have too many args; don't do *xs expansion. Go back to matching from
      # the start and treat every entry in starargs_tuple as length 1.
      n_params = len(match_signature.param_names)
      all_args = posargs + starargs_tuple
      if not match_signature.varargs_name:
        # If the function sig has no *args, return everything in posargs
        pos = _splats_to_any(all_args, ctx)
        return pos, None
      # Don't unwrap splats here because f(*xs, y) is not the same as f(xs, y).
      # TODO(mdemello): Ideally, since we are matching call f(*xs, y) against
      # sig f(x, y) we should raise an error here.
      pos = _splats_to_any(all_args[:n_params], ctx)
      star = []
      for var in all_args[n_params:]:
        if abstract_utils.is_var_splat(var):
          star.append(
              abstract_utils.merged_type_parameter(node, var, abstract_utils.T))
        else:
          star.append(var)
      if star:
        return pos, ctx.convert.tuple_to_value(star).to_variable(node)
      else:
        return pos, None
    elif stars:
      if len(stars) == 1:
        # Special case (<pre>, *xs) and (*xs, <post>) to fill in the type of xs
        # in every remaining arg.
        mid = self._expand_typed_star(ctx, node, stars[0], posarg_delta)
      else:
        # If we have (*xs, <k args>, *ys) remaining, and more than k+2 params to
        # match, don't try to match the intermediate params to any range, just
        # match all k+2 to Any
        mid = [ctx.new_unsolvable(node) for _ in range(posarg_delta)]
      return posargs + tuple(pre + mid + post), None
    else:
      # We have **kwargs but no *args in the invocation
      return posargs + tuple(pre), None

  def simplify(self, node, ctx, match_signature=None):
    """Try to insert part of *args, **kwargs into posargs / namedargs."""
    # TODO(rechen): When we have type information about *args/**kwargs,
    # we need to check it before doing this simplification.
    posargs = self.posargs
    namedargs = self.namedargs
    starargs = self.starargs
    starstarargs = self.starstarargs
    # Unpack starstarargs into namedargs. We need to do this first so we can see
    # what posargs are still required.
    starstarargs_as_dict = self.starstarargs_as_dict()
    if starstarargs_as_dict is not None:
      # Unlike varargs below, we do not adjust starstarargs into namedargs when
      # the function signature has matching param_names because we have not
      # found a benefit in doing so.
      if namedargs is None:
        namedargs = {}
      abstract_utils.update_args_dict(namedargs, starstarargs_as_dict, node)

      # We have pulled out all the named args from the function call, so we need
      # to delete them from starstarargs. If the original call contained
      # **kwargs, starstarargs will have could_contain_anything set to True, so
      # preserve it as an abstract dict. If not, we just had named args packed
      # into starstarargs, so set starstarargs to None.
      kwdict = starstarargs.data[0]
      if _isinstance(kwdict, "Dict") and kwdict.could_contain_anything:
        cls = kwdict.cls
        if _isinstance(cls, "PyTDClass"):
          # If cls is not already parameterized with the key and value types, we
          # parameterize it now to preserve them.
          params = {
              name: ctx.convert.merge_classes(
                  kwdict.get_instance_type_parameter(name, node).data)
              for name in (abstract_utils.K, abstract_utils.V)
          }
          cls = _make("ParameterizedClass", ctx.convert.dict_type, params, ctx)
        starstarargs = cls.instantiate(node)
      else:
        starstarargs = None
    starargs_as_tuple = self.starargs_as_tuple(node, ctx)
    if starargs_as_tuple is not None:
      if match_signature:
        posargs, starargs = self._unpack_and_match_args(node, ctx,
                                                        match_signature,
                                                        starargs_as_tuple)
      elif (starargs_as_tuple and
            abstract_utils.is_var_splat(starargs_as_tuple[-1])):
        # If the last arg is an indefinite iterable keep it in starargs. Convert
        # any other splats to Any.
        # TODO(mdemello): If there are multiple splats should we just fall
        # through to the next case (setting them all to Any), and only hit this
        # case for a *single* splat in terminal position?
        posargs = self.posargs + _splats_to_any(starargs_as_tuple[:-1], ctx)
        starargs = abstract_utils.unwrap_splat(starargs_as_tuple[-1])
      else:
        # Don't try to unpack iterables in any other position since we don't
        # have a signature to match. Just set all splats to Any.
        posargs = self.posargs + _splats_to_any(starargs_as_tuple, ctx)
        starargs = None
    simplify = lambda var: abstract_utils.simplify_variable(var, node, ctx)
    return Args(tuple(simplify(posarg) for posarg in posargs),
                {k: simplify(namedarg) for k, namedarg in namedargs.items()},
                simplify(starargs), simplify(starstarargs))

  def get_variables(self):
    variables = list(self.posargs) + list(self.namedargs.values())
    if self.starargs is not None:
      variables.append(self.starargs)
    if self.starstarargs is not None:
      variables.append(self.starstarargs)
    return variables

  def replace_posarg(self, pos, val):
    new_posargs = self.posargs[:pos] + (val,) + self.posargs[pos + 1:]
    return self.replace(posargs=new_posargs)

  def replace_namedarg(self, name, val):
    new_namedargs = dict(self.namedargs)
    new_namedargs[name] = val
    return self.replace(namedargs=new_namedargs)

  def delete_namedarg(self, name):
    new_namedargs = {k: v for k, v in self.namedargs.items() if k != name}
    return self.replace(namedargs=new_namedargs)

  def replace(self, **kwargs):
    return attrs.evolve(self, **kwargs)

  def has_opaque_starargs_or_starstarargs(self):
    return any(arg and not _isinstance(arg, "PythonConstant")
               for arg in (self.starargs, self.starstarargs))


class ReturnValueMixin:
  """Mixin for exceptions that hold a return node and variable."""

  def __init__(self):
    super().__init__()
    self.return_node = None
    self.return_variable = None

  def set_return(self, node, var):
    self.return_node = node
    self.return_variable = var

  def get_return(self, state):
    return state.change_cfg_node(self.return_node), self.return_variable


# These names are chosen to match pytype error classes.
# pylint: disable=g-bad-exception-name
class FailedFunctionCall(Exception, ReturnValueMixin):
  """Exception for failed function calls."""

  def __gt__(self, other):
    return other is None

  def __le__(self, other):
    return not self.__gt__(other)


class NotCallable(FailedFunctionCall):
  """For objects that don't have __call__."""

  def __init__(self, obj):
    super().__init__()
    self.obj = obj


class UndefinedParameterError(FailedFunctionCall):
  """Function called with an undefined variable."""

  def __init__(self, name):
    super().__init__()
    self.name = name


class DictKeyMissing(Exception, ReturnValueMixin):
  """When retrieving a key that does not exist in a dict."""

  def __init__(self, name):
    super().__init__()
    self.name = name

  def __gt__(self, other):
    return other is None

  def __le__(self, other):
    return not self.__gt__(other)


@dataclasses.dataclass(eq=True, frozen=True)
class BadCall:
  sig: Signature
  passed_args: Sequence[Tuple[str, _base.BaseValue]]
  bad_param: Optional[abstract_utils.BadType]


@dataclasses.dataclass(eq=True, frozen=True)
class Arg:
  name: str
  value: cfg.Variable
  typ: _base.BaseValue


class InvalidParameters(FailedFunctionCall):
  """Exception for functions called with an incorrect parameter combination."""

  def __init__(self, sig, passed_args, ctx, bad_param=None):
    super().__init__()
    self.name = sig.name
    passed_args = [(name, ctx.convert.merge_values(arg.data))
                   for name, arg, _ in sig.iter_args(passed_args)]
    self.bad_call = BadCall(sig=sig, passed_args=passed_args,
                            bad_param=bad_param)


class WrongArgTypes(InvalidParameters):
  """For functions that were called with the wrong types."""

  def __gt__(self, other):
    if other is None:
      return True
    if not isinstance(other, WrongArgTypes):
      # WrongArgTypes should take precedence over other FailedFunctionCall
      # subclasses but not over unrelated errors like DictKeyMissing.
      return isinstance(other, FailedFunctionCall)
    # The signature that has fewer *args/**kwargs tends to be more precise.
    def starcount(err):
      return (bool(err.bad_call.sig.varargs_name) +
              bool(err.bad_call.sig.kwargs_name))
    return starcount(self) < starcount(other)

  def __le__(self, other):
    return not self.__gt__(other)


class WrongArgCount(InvalidParameters):
  """E.g. if a function expecting 4 parameters is called with 3."""


class WrongKeywordArgs(InvalidParameters):
  """E.g. an arg "x" is passed to a function that doesn't have an "x" param."""

  def __init__(self, sig, passed_args, ctx, extra_keywords):
    super().__init__(sig, passed_args, ctx)
    self.extra_keywords = tuple(extra_keywords)


class DuplicateKeyword(InvalidParameters):
  """E.g. an arg "x" is passed to a function as both a posarg and a kwarg."""

  def __init__(self, sig, passed_args, ctx, duplicate):
    super().__init__(sig, passed_args, ctx)
    self.duplicate = duplicate


class MissingParameter(InvalidParameters):
  """E.g. a function requires parameter 'x' but 'x' isn't passed."""

  def __init__(self, sig, passed_args, ctx, missing_parameter):
    super().__init__(sig, passed_args, ctx)
    self.missing_parameter = missing_parameter
# pylint: enable=g-bad-exception-name


@dataclasses.dataclass(frozen=True)
class Mutation:
  """A type mutation."""

  instance: _base.BaseValue
  name: str
  value: cfg.Variable

  def __eq__(self, other):
    return (self.instance == other.instance and
            self.name == other.name and
            frozenset(self.value.data) == frozenset(other.value.data))

  def __hash__(self):
    return hash((self.instance, self.name, frozenset(self.value.data)))


class _ReturnType(abc.ABC):

  @property
  @abc.abstractmethod
  def name(self):
    ...

  @abc.abstractmethod
  def instantiate_parameter(self, node, param_name):
    ...


class AbstractReturnType(_ReturnType):
  """An abstract return type."""

  def __init__(self, t, ctx):
    self._type = t
    self._ctx = ctx

  @property
  def name(self):
    return self._type.full_name

  def instantiate_parameter(self, node, param_name):
    param = self._type.get_formal_type_parameter(param_name)
    _, param_instance = self._ctx.vm.init_class(node, param)
    return param_instance


class PyTDReturnType(_ReturnType):
  """A PyTD return type."""

  def __init__(self, t, subst, sources, ctx):
    self._type = t
    self._subst = subst
    self._sources = sources
    self._ctx = ctx

  @property
  def name(self):
    return self._type.name

  def instantiate_parameter(self, node, param_name):
    _, instance_var = self.instantiate(node)
    instance = abstract_utils.get_atomic_value(instance_var)
    return instance.get_instance_type_parameter(param_name)

  def instantiate(self, node):
    """Instantiate the pytd return type."""
    # Type parameter values, which are instantiated by the matcher, will end up
    # in the return value. Since the matcher does not call __init__, we need to
    # do that now. The one exception is that Type[X] does not instantiate X, so
    # we do not call X.__init__.
    if self._type.name != "builtins.type":
      for param in pytd_utils.GetTypeParameters(self._type):
        if param.full_name in self._subst:
          node = self._ctx.vm.call_init(node, self._subst[param.full_name])
    try:
      ret = self._ctx.convert.constant_to_var(
          abstract_utils.AsReturnValue(self._type),
          self._subst,
          node,
          source_sets=[self._sources])
    except self._ctx.convert.TypeParameterError:
      # The return type contains a type parameter without a substitution.
      subst = abstract_utils.with_empty_substitutions(
          self._subst, self._type, node, self._ctx)
      return node, self._ctx.convert.constant_to_var(
          abstract_utils.AsReturnValue(self._type),
          subst,
          node,
          source_sets=[self._sources])
    if not ret.bindings and isinstance(self._type, pytd.TypeParameter):
      ret.AddBinding(self._ctx.convert.empty, [], node)
    return node, ret


def _splats_to_any(seq, ctx):
  return tuple(
      ctx.new_unsolvable(ctx.root_node) if abstract_utils.is_var_splat(v) else v
      for v in seq)


def call_function(
    ctx, node, func_var, args, fallback_to_unsolvable=True,
    allow_noreturn=False, strict_filter=True):
  """Call a function.

  Args:
    ctx: The abstract context.
    node: The current CFG node.
    func_var: A variable of the possible functions to call.
    args: The arguments to pass. See function.Args.
    fallback_to_unsolvable: If the function call fails, create an unknown.
    allow_noreturn: Whether typing.NoReturn is allowed in the return type.
    strict_filter: Whether function bindings should be strictly filtered.
  Returns:
    A tuple (CFGNode, Variable). The Variable is the return value.
  Raises:
    DictKeyMissing: if we retrieved a nonexistent key from a dict and
      fallback_to_unsolvable is False.
    FailedFunctionCall: if the call fails and fallback_to_unsolvable is False.
  """
  assert func_var.bindings
  result = ctx.program.NewVariable()
  nodes = []
  error = None
  has_noreturn = False
  for funcb in func_var.bindings:
    func = funcb.data
    one_result = None
    try:
      new_node, one_result = func.call(node, funcb, args)
    except (DictKeyMissing, FailedFunctionCall) as e:
      if e > error and ((not strict_filter and len(func_var.bindings) == 1) or
                        funcb.IsVisible(node)):
        error = e
    else:
      if ctx.convert.no_return in one_result.data:
        if allow_noreturn:
          # Make sure NoReturn was the only thing returned.
          assert len(one_result.data) == 1
          has_noreturn = True
        else:
          for b in one_result.bindings:
            if b.data != ctx.convert.no_return:
              result.PasteBinding(b)
      else:
        result.PasteVariable(one_result, new_node, {funcb})
      nodes.append(new_node)
  if nodes:
    node = ctx.join_cfg_nodes(nodes)
    if not result.bindings:
      v = ctx.convert.no_return if has_noreturn else ctx.convert.unsolvable
      result.AddBinding(v, [], node)
  elif (isinstance(error, FailedFunctionCall) and
        all(func.name.endswith(".__init__") for func in func_var.data)):
    # If the function failed with a FailedFunctionCall exception, try calling
    # it again with fake arguments. This allows for calls to __init__ to
    # always succeed, ensuring pytype has a full view of the class and its
    # attributes. If the call still fails, call_with_fake_args will return
    # abstract.Unsolvable.
    node, result = ctx.vm.call_with_fake_args(node, func_var)
  elif ctx.options.precise_return and len(func_var.bindings) == 1:
    funcb, = func_var.bindings
    func = funcb.data
    if _isinstance(func, "BoundFunction"):
      func = func.underlying
    if _isinstance(func, "PyTDFunction"):
      node, result = PyTDReturnType(
          func.signatures[0].pytd_sig.return_type, datatypes.HashableDict(),
          [funcb], ctx).instantiate(node)
    elif _isinstance(func, "InterpreterFunction"):
      sig = func.signature_functions()[0].signature
      ret = sig.annotations.get("return", ctx.convert.unsolvable)
      node, result = ctx.vm.init_class(node, ret)
    else:
      result = ctx.new_unsolvable(node)
  else:
    result = ctx.new_unsolvable(node)
  ctx.vm.trace_opcode(None, func_var.data[0].name.rpartition(".")[-1],
                      (func_var, result))
  if (nodes and not ctx.options.strict_parameter_checks) or not error:
    return node, result
  elif fallback_to_unsolvable:
    ctx.errorlog.invalid_function_call(ctx.vm.stack(func_var.data[0]), error)
    return node, result
  else:
    # We were called by something that does its own error handling.
    error.set_return(node, result)
    raise error  # pylint: disable=raising-bad-type


def match_all_args(ctx, node, func, args):
  """Call match_args multiple times to find all type errors.

  Args:
    ctx: The abstract context.
    node: The current CFG node.
    func: An abstract function
    args: An Args object to match against func

  Returns:
    A tuple of (new_args, errors)
      where new_args = args with all incorrectly typed values set to Any
            errors = a list of [(type mismatch error, arg name, value)]

  Reraises any error that is not function.InvalidParameters
  """
  positional_names = func.get_positional_names()
  needs_checking = True
  errors = []
  while needs_checking:
    try:
      func.match_args(node, args)
    except FailedFunctionCall as e:
      if isinstance(e, WrongKeywordArgs):
        errors.append((e, e.extra_keywords[0], None))
        for i in e.extra_keywords:
          args = args.delete_namedarg(i)
      elif isinstance(e, DuplicateKeyword):
        errors.append((e, e.duplicate, None))
        args = args.delete_namedarg(e.duplicate)
      elif isinstance(e, MissingParameter):
        errors.append((e, e.missing_parameter, None))
        args = args.replace_namedarg(
            e.missing_parameter, ctx.new_unsolvable(node))
      elif isinstance(e, WrongArgTypes):
        arg_name = e.bad_call.bad_param.name
        for name, value in e.bad_call.passed_args:
          if name != arg_name:
            continue
          errors.append((e, name, value))
          try:
            pos = positional_names.index(name)
          except ValueError:
            args = args.replace_namedarg(name, ctx.new_unsolvable(node))
          else:
            args = args.replace_posarg(pos, ctx.new_unsolvable(node))
          break
        else:
          raise AssertionError(
              f"Mismatched parameter {arg_name} not found in passed_args"
          ) from e
      else:
        # This is not an InvalidParameters error.
        raise
    else:
      needs_checking = False

  return args, errors


def has_visible_namedarg(node, args, names):
  # Note: this method should be called judiciously, as HasCombination is
  # potentially very expensive.
  namedargs = {args.namedargs[name] for name in names}
  variables = [v for v in args.get_variables() if v not in namedargs]
  for name in names:
    for view in cfg_utils.variable_product(variables + [args.namedargs[name]]):
      if node.HasCombination(list(view)):
        return True
  return False


def handle_typeguard(node, ret: _ReturnType, first_arg, ctx, func_name=None):
  """Returns a variable of the return value of a typeguard function.

  Args:
    node: The current node.
    ret: The function's return value.
    first_arg: The first argument to the function.
    ctx: The current context.
    func_name: Optionally, the function name, for better error messages.
  """
  frame = ctx.vm.frame
  if not hasattr(frame, "f_locals"):
    return None  # no need to apply TypeGuard if we're in a dummy frame
  if ret.name != "typing.TypeGuard":
    return None

  # Get the local/global variable that first_arg comes from, and add new
  # bindings for the TypeGuard type.
  target_name = ctx.vm.get_var_name(first_arg)
  if not target_name:
    desc = f" function {func_name!r}" if func_name else ""
    ctx.errorlog.not_supported_yet(
        ctx.vm.frames, f"Using TypeGuard{desc} with an arbitrary expression",
        "Please assign the expression to a local variable.")
    return None
  target = frame.lookup_name(target_name)
  # Forward all the target's bindings to the current node, so we don't have
  # visibility problems later.
  target.PasteVariable(target, node)
  old_data = set(target.data)
  new_instance = ret.instantiate_parameter(node, abstract_utils.T)
  for b in new_instance.bindings:
    if b.data not in target.data:
      target.PasteBinding(b, node)

  # Create a boolean return variable with True bindings for values that
  # originate from the TypeGuard type and False for the rest.
  typeguard_return = ctx.program.NewVariable()
  for b in target.bindings:
    boolvals = {b.data not in old_data} | {b.data in new_instance.data}
    for v in boolvals:
      typeguard_return.AddBinding(ctx.convert.bool_values[v], {b}, node)
  return typeguard_return
