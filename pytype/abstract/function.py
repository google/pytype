"""Representation of Python function headers and calls."""

import collections
import itertools
import logging

from pytype import datatypes
from pytype import utils
from pytype.abstract import abstract_utils
from pytype.pytd import pytd
from pytype.pytd import pytd_utils

log = logging.getLogger(__name__)
_isinstance = abstract_utils._isinstance  # pylint: disable=protected-access


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
  elif _isinstance(func, "SimpleFunction"):
    return [func.signature]
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
    param_names: A tuple of positional parameter names.
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
  """

  def __init__(self, name, param_names, varargs_name, kwonly_params,
               kwargs_name, defaults, annotations,
               postprocess_annotations=True):
    self.name = name
    self.param_names = param_names
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

  def add_scope(self, module):
    """Add scope for type parameters in annotations."""
    annotations = {}
    for key, val in self.annotations.items():
      annotations[key] = val.ctx.annotation_utils.add_scope(
          val, self.excluded_types, module)
    self.annotations = annotations

  def _postprocess_annotation(self, name, annotation):
    if name == self.varargs_name:
      return annotation.ctx.convert.create_new_varargs_value(annotation)
    elif name == self.kwargs_name:
      return annotation.ctx.convert.create_new_kwargs_value(annotation)
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
  def from_pytd(cls, ctx, name, sig):
    """Construct an abstract signature from a pytd signature."""
    pytd_annotations = [(p.name, p.type)
                        for p in sig.params + (sig.starargs, sig.starstarargs)
                        if p is not None]
    pytd_annotations.append(("return", sig.return_type))
    def param_to_var(p):
      return ctx.convert.constant_to_var(
          p.type, subst=datatypes.AliasingDict(), node=ctx.root_node)

    return cls(
        name=name,
        param_names=tuple(p.name for p in sig.params if not p.kwonly),
        varargs_name=None if sig.starargs is None else sig.starargs.name,
        kwonly_params=tuple(p.name for p in sig.params if p.kwonly),
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
    return cls(
        name="<callable>",
        param_names=tuple(sorted(annotations)),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations=annotations,
    )

  @classmethod
  def from_param_names(cls, name, param_names):
    """Construct a minimal signature from a name and a list of param names."""
    return cls(
        name=name,
        param_names=tuple(param_names),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations={},
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
    for name, namedarg in sorted(args.namedargs.items()):
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

  def get_first_arg(self, callargs):
    return callargs.get(self.param_names[0]) if self.param_names else None


class Args(collections.namedtuple(
    "Args", ["posargs", "namedargs", "starargs", "starstarargs"])):
  """Represents the parameters of a function call."""

  def __new__(cls, posargs, namedargs=None, starargs=None, starstarargs=None):
    """Create arguments for a function under analysis.

    Args:
      posargs: The positional arguments. A tuple of cfg.Variable.
      namedargs: The keyword arguments. A dictionary, mapping strings to
        cfg.Variable.
      starargs: The *args parameter, or None.
      starstarargs: The **kwargs parameter, or None.
    Returns:
      An Args instance.
    """
    assert isinstance(posargs, tuple), posargs
    cls.replace = cls._replace
    return super().__new__(
        cls,
        posargs=posargs,
        namedargs=namedargs or {},
        starargs=starargs,
        starstarargs=starstarargs)

  def has_namedargs(self):
    if isinstance(self.namedargs, dict):
      return bool(self.namedargs)
    else:
      return bool(self.namedargs.pyval)

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
      if self.namedargs is None:
        namedargs = starstarargs_as_dict
      else:
        namedargs.update(node, starstarargs_as_dict)

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
          cls = ctx.convert.build_map_class(node, params)
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
    return Args(posargs, namedargs, starargs, starstarargs)

  def get_variables(self):
    variables = list(self.posargs) + list(self.namedargs.values())
    if self.starargs is not None:
      variables.append(self.starargs)
    if self.starstarargs is not None:
      variables.append(self.starstarargs)
    return variables

  def replace_posarg(self, pos, val):
    new_posargs = self.posargs[:pos] + (val,) + self.posargs[pos + 1:]
    return self._replace(posargs=new_posargs)

  def replace_namedarg(self, name, val):
    new_namedargs = dict(self.namedargs)
    new_namedargs[name] = val
    return self._replace(namedargs=new_namedargs)

  def delete_namedarg(self, name):
    new_namedargs = {k: v for k, v in self.namedargs.items() if k != name}
    return self._replace(namedargs=new_namedargs)


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


BadCall = collections.namedtuple("_", ["sig", "passed_args", "bad_param"])


class BadParam(
    collections.namedtuple("_", ["name", "expected", "protocol_error",
                                 "noniterable_str_error"])):

  def __new__(cls, name, expected, protocol_error=None,
              noniterable_str_error=None):
    return super().__new__(cls, name, expected, protocol_error,
                           noniterable_str_error)


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


class Mutation(collections.namedtuple("_", ["instance", "name", "value"])):

  def __eq__(self, other):
    return (self.instance == other.instance and
            self.name == other.name and
            frozenset(self.value.data) == frozenset(other.value.data))

  def __hash__(self):
    return hash((self.instance, self.name, frozenset(self.value.data)))


class PyTDSignature(utils.ContextWeakrefMixin):
  """A PyTD function type (signature).

  This represents instances of functions with specific arguments and return
  type.
  """

  def __init__(self, name, pytd_sig, ctx):
    super().__init__(ctx)
    self.name = name
    self.pytd_sig = pytd_sig
    self.param_types = [
        self.ctx.convert.constant_to_value(
            p.type, subst=datatypes.AliasingDict(), node=self.ctx.root_node)
        for p in self.pytd_sig.params
    ]
    self.signature = Signature.from_pytd(ctx, name, pytd_sig)

  def _map_args(self, args, view):
    """Map the passed arguments to a name->binding dictionary.

    Args:
      args: The passed arguments.
      view: A variable->binding dictionary.

    Returns:
      A tuple of:
        a list of formal arguments, each a (name, abstract value) pair;
        a name->binding dictionary of the passed arguments.

    Raises:
      InvalidParameters: If the passed arguments don't match this signature.
    """
    formal_args = [(p.name, self.signature.annotations[p.name])
                   for p in self.pytd_sig.params]
    arg_dict = {}

    # positional args
    for name, arg in zip(self.signature.param_names, args.posargs):
      arg_dict[name] = view[arg]
    num_expected_posargs = len(self.signature.param_names)
    if len(args.posargs) > num_expected_posargs and not self.pytd_sig.starargs:
      raise WrongArgCount(self.signature, args, self.ctx)
    # Extra positional args are passed via the *args argument.
    varargs_type = self.signature.annotations.get(self.signature.varargs_name)
    if _isinstance(varargs_type, "ParameterizedClass"):
      for (i, vararg) in enumerate(args.posargs[num_expected_posargs:]):
        name = argname(num_expected_posargs + i)
        arg_dict[name] = view[vararg]
        formal_args.append(
            (name, varargs_type.get_formal_type_parameter(abstract_utils.T)))

    # named args
    for name, arg in args.namedargs.items():
      if name in arg_dict:
        raise DuplicateKeyword(self.signature, args, self.ctx, name)
      arg_dict[name] = view[arg]
    extra_kwargs = set(args.namedargs) - {p.name for p in self.pytd_sig.params}
    if extra_kwargs and not self.pytd_sig.starstarargs:
      raise WrongKeywordArgs(self.signature, args, self.ctx, extra_kwargs)
    # Extra keyword args are passed via the **kwargs argument.
    kwargs_type = self.signature.annotations.get(self.signature.kwargs_name)
    if _isinstance(kwargs_type, "ParameterizedClass"):
      # We sort the kwargs so that matching always happens in the same order.
      for name in sorted(extra_kwargs):
        formal_args.append(
            (name, kwargs_type.get_formal_type_parameter(abstract_utils.V)))

    # packed args
    packed_args = [("starargs", self.signature.varargs_name),
                   ("starstarargs", self.signature.kwargs_name)]
    for arg_type, name in packed_args:
      actual = getattr(args, arg_type)
      pytd_val = getattr(self.pytd_sig, arg_type)
      if actual and pytd_val:
        arg_dict[name] = view[actual]
        # The annotation is Tuple or Dict, but the passed arg only has to be
        # Iterable or Mapping.
        typ = self.ctx.convert.widen_type(self.signature.annotations[name])
        formal_args.append((name, typ))

    return formal_args, arg_dict

  def _fill_in_missing_parameters(self, node, args, arg_dict):
    for p in self.pytd_sig.params:
      if p.name not in arg_dict:
        if (not p.optional and args.starargs is None and
            args.starstarargs is None):
          raise MissingParameter(self.signature, args, self.ctx, p.name)
        # Assume the missing parameter is filled in by *args or **kwargs.
        # Unfortunately, we can't easily use *args or **kwargs to fill in
        # something more precise, since we need a Value, not a Variable.
        arg_dict[p.name] = self.ctx.convert.unsolvable.to_binding(node)

  def substitute_formal_args(self, node, args, view, alias_map):
    """Substitute matching args into this signature. Used by PyTDFunction."""
    formal_args, arg_dict = self._map_args(args, view)
    self._fill_in_missing_parameters(node, args, arg_dict)
    subst, bad_arg = self.ctx.matcher(node).compute_subst(
        formal_args, arg_dict, view, alias_map)
    if subst is None:
      if self.signature.has_param(bad_arg.name):
        signature = self.signature
      else:
        signature = self.signature.insert_varargs_and_kwargs(arg_dict)
      raise WrongArgTypes(signature, args, self.ctx, bad_param=bad_arg)
    if log.isEnabledFor(logging.DEBUG):
      log.debug("Matched arguments against sig%s",
                pytd_utils.Print(self.pytd_sig))
    for nr, p in enumerate(self.pytd_sig.params):
      log.info("param %d) %s: %s <=> %s", nr, p.name, p.type, arg_dict[p.name])
    for name, var in sorted(subst.items()):
      log.debug("Using %s=%r %r", name, var, var.data)

    return arg_dict, subst

  def instantiate_return(self, node, subst, sources):
    return_type = self.pytd_sig.return_type
    # Type parameter values, which are instantiated by the matcher, will end up
    # in the return value. Since the matcher does not call __init__, we need to
    # do that now. The one exception is that Type[X] does not instantiate X, so
    # we do not call X.__init__.
    if return_type.name != "builtins.type":
      for param in pytd_utils.GetTypeParameters(return_type):
        if param.full_name in subst:
          node = self.ctx.vm.call_init(node, subst[param.full_name])
    try:
      ret = self.ctx.convert.constant_to_var(
          abstract_utils.AsReturnValue(return_type),
          subst,
          node,
          source_sets=[sources])
    except self.ctx.convert.TypeParameterError:
      # The return type contains a type parameter without a substitution.
      subst = subst.copy()
      for t in pytd_utils.GetTypeParameters(return_type):
        if t.full_name not in subst:
          subst[t.full_name] = self.ctx.convert.empty.to_variable(node)
      return node, self.ctx.convert.constant_to_var(
          abstract_utils.AsReturnValue(return_type),
          subst,
          node,
          source_sets=[sources])
    if not ret.bindings and isinstance(return_type, pytd.TypeParameter):
      ret.AddBinding(self.ctx.convert.empty, [], node)
    return node, ret

  def call_with_args(self, node, func, arg_dict,
                     subst, ret_map, alias_map=None):
    """Call this signature. Used by PyTDFunction."""
    t = (self.pytd_sig.return_type, subst)
    sources = [func] + list(arg_dict.values())
    if t not in ret_map:
      node, ret_map[t] = self.instantiate_return(node, subst, sources)
    else:
      # add the new sources
      for data in ret_map[t].data:
        ret_map[t].AddBinding(data, sources, node)
    mutations = self._get_mutation(node, arg_dict, subst, ret_map[t])
    self.ctx.vm.trace_call(
        node, func, (self,),
        tuple(arg_dict[p.name] for p in self.pytd_sig.params), {}, ret_map[t])
    return node, ret_map[t], mutations

  @classmethod
  def _collect_mutated_parameters(cls, typ, mutated_type):
    if (isinstance(typ, pytd.UnionType) and
        isinstance(mutated_type, pytd.UnionType)):
      if len(typ.type_list) != len(mutated_type.type_list):
        raise ValueError(
            "Type list lengths do not match:\nOld: %s\nNew: %s" %
            (typ.type_list, mutated_type.type_list))
      return itertools.chain.from_iterable(
          cls._collect_mutated_parameters(t1, t2)
          for t1, t2 in zip(typ.type_list, mutated_type.type_list))
    if typ == mutated_type and isinstance(typ, pytd.ClassType):
      return []  # no mutation needed
    if (not isinstance(typ, pytd.GenericType) or
        not isinstance(mutated_type, pytd.GenericType) or
        typ.base_type != mutated_type.base_type or
        not isinstance(typ.base_type, pytd.ClassType)):
      raise ValueError("Unsupported mutation:\n%r ->\n%r" %
                       (typ, mutated_type))
    return [zip(mutated_type.base_type.cls.template, mutated_type.parameters)]

  def _get_mutation(self, node, arg_dict, subst, retvar):
    """Mutation for changing the type parameters of mutable arguments.

    This will adjust the type parameters as needed for pytd functions like:
      def append_float(x: list[int]):
        x = list[int or float]
    This is called after all the signature matching has succeeded, and we
    know we're actually calling this function.

    Args:
      node: The current CFG node.
      arg_dict: A map of strings to pytd.Bindings instances.
      subst: Current type parameters.
      retvar: A variable of the return value.
    Returns:
      A list of Mutation instances.
    Raises:
      ValueError: If the pytd contains invalid information for mutated params.
    """
    # Handle mutable parameters using the information type parameters
    mutations = []
    # It's possible that the signature contains type parameters that are used
    # in mutations but are not filled in by the arguments, e.g. when starargs
    # and starstarargs have type parameters but are not in the args. Check that
    # subst has an entry for every type parameter, adding any that are missing.
    if any(f.mutated_type for f in self.pytd_sig.params):
      subst = subst.copy()
      for t in pytd_utils.GetTypeParameters(self.pytd_sig):
        if t.full_name not in subst:
          subst[t.full_name] = self.ctx.convert.empty.to_variable(node)
    for formal in self.pytd_sig.params:
      actual = arg_dict[formal.name]
      arg = actual.data
      if (formal.mutated_type is not None and _isinstance(arg, "SimpleValue")):
        try:
          all_names_actuals = self._collect_mutated_parameters(
              formal.type, formal.mutated_type)
        except ValueError as e:
          log.error("Old: %s", pytd_utils.Print(formal.type))
          log.error("New: %s", pytd_utils.Print(formal.mutated_type))
          log.error("Actual: %r", actual)
          raise ValueError("Mutable parameters setting a type to a "
                           "different base type is not allowed.") from e
        for names_actuals in all_names_actuals:
          for tparam, type_actual in names_actuals:
            log.info("Mutating %s to %s",
                     tparam.name,
                     pytd_utils.Print(type_actual))
            type_actual_val = self.ctx.convert.constant_to_var(
                abstract_utils.AsInstance(type_actual),
                subst,
                node,
                discard_concrete_values=True)
            mutations.append(Mutation(arg, tparam.full_name, type_actual_val))
    if self.name == "__new__":
      # This is a constructor, so check whether the constructed instance needs
      # to be mutated.
      for ret in retvar.data:
        if ret.cls.full_name != "builtins.type":
          for t in ret.cls.template:
            if t.full_name in subst:
              mutations.append(Mutation(ret, t.full_name, subst[t.full_name]))
    return mutations

  def get_positional_names(self):
    return [p.name for p in self.pytd_sig.params
            if not p.kwonly]

  def set_defaults(self, defaults):
    """Set signature's default arguments. Requires rebuilding PyTD signature.

    Args:
      defaults: An iterable of function argument defaults.

    Returns:
      Self with an updated signature.
    """
    defaults = list(defaults)
    params = []
    for param in reversed(self.pytd_sig.params):
      if defaults:
        defaults.pop()  # Discard the default. Unless we want to update type?
        params.append(pytd.Parameter(
            name=param.name,
            type=param.type,
            kwonly=param.kwonly,
            optional=True,
            mutated_type=param.mutated_type
        ))
      else:
        params.append(pytd.Parameter(
            name=param.name,
            type=param.type,
            kwonly=param.kwonly,
            optional=False,  # Reset any previously-set defaults
            mutated_type=param.mutated_type
        ))
    new_sig = pytd.Signature(
        params=tuple(reversed(params)),
        starargs=self.pytd_sig.starargs,
        starstarargs=self.pytd_sig.starstarargs,
        return_type=self.pytd_sig.return_type,
        exceptions=self.pytd_sig.exceptions,
        template=self.pytd_sig.template
    )
    # Now update self
    self.pytd_sig = new_sig
    self.param_types = [
        self.ctx.convert.constant_to_value(
            p.type, subst=datatypes.AliasingDict(), node=self.ctx.root_node)
        for p in self.pytd_sig.params
    ]
    self.signature = Signature.from_pytd(self.ctx, self.name, self.pytd_sig)
    return self

  def __repr__(self):
    return pytd_utils.Print(self.pytd_sig)


def _splats_to_any(seq, ctx):
  return tuple(
      ctx.new_unsolvable(ctx.root_node) if abstract_utils.is_var_splat(v) else v
      for v in seq)


def call_function(ctx,
                  node,
                  func_var,
                  args,
                  fallback_to_unsolvable=True,
                  allow_noreturn=False):
  """Call a function.

  Args:
    ctx: The abstract context.
    node: The current CFG node.
    func_var: A variable of the possible functions to call.
    args: The arguments to pass. See function.Args.
    fallback_to_unsolvable: If the function call fails, create an unknown.
    allow_noreturn: Whether typing.NoReturn is allowed in the return type.
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
      if e > error:
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
        all(abstract_utils.func_name_is_class_init(func.name)
            for func in func_var.data)):
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
      node, result = func.signatures[0].instantiate_return(node, {}, [funcb])
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
  if nodes:
    return node, result
  elif fallback_to_unsolvable:
    if not isinstance(error, DictKeyMissing):
      ctx.errorlog.invalid_function_call(ctx.vm.stack(func_var.data[0]), error)
    return node, result
  else:
    # We were called by something that does its own error handling.
    assert error
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
              "Mismatched parameter %s not found in passed_args" %
              arg_name) from e
      else:
        # This is not an InvalidParameters error.
        raise
    else:
      needs_checking = False

  return args, errors
