"""Representation of Python function headers and calls."""

import collections
import logging

from pytype import abstract_utils
from pytype import datatypes
from pytype import utils
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors

import six

log = logging.getLogger(__name__)


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
    annotations: A dictionary of type annotations. (string to type)
    excluded_types: A set of type names that will be ignored when checking the
      count of type parameters.
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
      for k, annot in six.iteritems(self.annotations):
        self.annotations[k] = self._postprocess_annotation(k, annot)

  @property
  def has_return_annotation(self):
    return "return" in self.annotations

  @property
  def has_param_annotations(self):
    return bool(six.viewkeys(self.annotations) - {"return"})

  def add_scope(self, module):
    """Add scope for type parameters in annotations."""
    annotations = {}
    for key, val in self.annotations.items():
      annotations[key] = val.vm.annotations_util.add_scope(
          val, self.excluded_types, module)
    self.annotations = annotations

  def _postprocess_annotation(self, name, annotation):
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
    """Check the count of type parameters in function."""
    c = collections.Counter()
    for annot in self.annotations.values():
      c.update(annot.vm.annotations_util.get_type_parameters(annot))
    for param, count in six.iteritems(c):
      if param.name in self.excluded_types:
        # skip all the type parameters in `excluded_types`
        continue
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
    def param_to_var(p):
      return vm.convert.constant_to_var(
          p.type, subst=datatypes.AliasingDict(), node=vm.root_cfg_node)
    return cls(
        name=name,
        param_names=tuple(p.name for p in sig.params if not p.kwonly),
        varargs_name=None if sig.starargs is None else sig.starargs.name,
        kwonly_params=set(p.name for p in sig.params if p.kwonly),
        kwargs_name=None if sig.starstarargs is None else sig.starstarargs.name,
        defaults={p.name: param_to_var(p) for p in sig.params if p.optional},
        annotations={name: vm.convert.constant_to_value(
            typ, subst=datatypes.AliasingDict(), node=vm.root_cfg_node)
                     for name, typ in pytd_annotations},
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
        kwonly_params=set(),
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
        kwonly_params=set(),
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

  def check_defaults(self):
    """Returns the first non-default param following a default."""
    # TODO(mdemello): We should raise an error here, analogous to
    # the python-compiler-error we would get if analyzing the signature from a
    # source file, but this class does not have access to the vm, and the
    # exception hierarchy in this module derives from FailedFunctionCall.
    has_default = False
    for name in self.param_names:
      if name in self.defaults:
        has_default = True
      elif has_default:
        return name
    return None

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
    return super(Args, cls).__new__(
        cls, posargs=posargs, namedargs=namedargs or {}, starargs=starargs,
        starstarargs=starstarargs)

  def starargs_as_tuple(self, node, vm):
    try:
      args = self.starargs and abstract_utils.get_atomic_python_constant(
          self.starargs, tuple)
    except abstract_utils.ConversionError:
      args = None
    if not args:
      return args
    return tuple(var if var.bindings else vm.convert.empty.to_variable(node)
                 for var in args)

  def starstarargs_as_dict(self):
    try:
      args = self.starstarargs and abstract_utils.get_atomic_python_constant(
          self.starstarargs, dict)
    except abstract_utils.ConversionError:
      args = None
    return args

  def simplify(self, node, vm, match_signature=None):
    """Try to insert part of *args, **kwargs into posargs / namedargs."""
    # TODO(rechen): When we have type information about *args/**kwargs,
    # we need to check it before doing this simplification.
    posargs = self.posargs
    namedargs = self.namedargs
    starargs = self.starargs
    starstarargs = self.starstarargs
    starargs_as_tuple = self.starargs_as_tuple(node, vm)
    if starargs_as_tuple is not None:
      if match_signature:
        # As we have the function signature we will attempt to adjust the
        # starargs into the missing posargs.
        missing_posarg_count = len(match_signature.param_names) - len(posargs)
        starargs_list = list(starargs_as_tuple)
        for _ in range(missing_posarg_count):
          if starargs_list:
            posargs += (starargs_list.pop(0),)
          else:
            break
        starargs = vm.convert.tuple_to_value(starargs_list).to_variable(node)
      else:
        posargs += starargs_as_tuple
        starargs = None
    starstarargs_as_dict = self.starstarargs_as_dict()
    if starstarargs_as_dict is not None:
      # TODO(sivachandra): Similar to adjusting varargs in to missing positional
      # args, there might be a benefit in adjusting starstarargs in to named
      # args if function signature has matching param_names.
      if namedargs is None:
        namedargs = starstarargs_as_dict
      else:
        namedargs.update(node, starstarargs_as_dict)
      starstarargs = None
    return Args(posargs, namedargs, starargs, starstarargs)

  def get_variables(self):
    variables = list(self.posargs) + list(self.namedargs.values())
    if self.starargs is not None:
      variables.append(self.starargs)
    if self.starstarargs is not None:
      variables.append(self.starstarargs)
    return variables


class ReturnValueMixin(object):
  """Mixin for exceptions that hold a return node and variable."""

  def __init__(self):
    super(ReturnValueMixin, self).__init__()
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
    super(NotCallable, self).__init__()
    self.obj = obj


class UndefinedParameterError(FailedFunctionCall):
  """Function called with an undefined variable."""

  def __init__(self, name):
    super(UndefinedParameterError, self).__init__()
    self.name = name


class DictKeyMissing(Exception, ReturnValueMixin):
  """When retrieving a key that does not exist in a dict."""

  def __init__(self, name):
    super(DictKeyMissing, self).__init__()
    self.name = name

  def __gt__(self, other):
    return other is None


BadCall = collections.namedtuple("_", ["sig", "passed_args", "bad_param"])


BadParam = collections.namedtuple("_", ["name", "expected"])


class InvalidParameters(FailedFunctionCall):
  """Exception for functions called with an incorrect parameter combination."""

  def __init__(self, sig, passed_args, vm, bad_param=None):
    super(InvalidParameters, self).__init__()
    self.name = sig.name
    passed_args = [(name, vm.merge_values(arg.data))
                   for name, arg, _ in sig.iter_args(passed_args)]
    self.bad_call = BadCall(sig=sig, passed_args=passed_args,
                            bad_param=bad_param)


class WrongArgTypes(InvalidParameters):
  """For functions that were called with the wrong types."""

  def __gt__(self, other):
    return other is None or (isinstance(other, FailedFunctionCall) and
                             not isinstance(other, WrongArgTypes))


class WrongArgCount(InvalidParameters):
  """E.g. if a function expecting 4 parameters is called with 3."""


class WrongKeywordArgs(InvalidParameters):
  """E.g. an arg "x" is passed to a function that doesn't have an "x" param."""

  def __init__(self, sig, passed_args, vm, extra_keywords):
    super(WrongKeywordArgs, self).__init__(sig, passed_args, vm)
    self.extra_keywords = tuple(extra_keywords)


class DuplicateKeyword(InvalidParameters):
  """E.g. an arg "x" is passed to a function as both a posarg and a kwarg."""

  def __init__(self, sig, passed_args, vm, duplicate):
    super(DuplicateKeyword, self).__init__(sig, passed_args, vm)
    self.duplicate = duplicate


class MissingParameter(InvalidParameters):
  """E.g. a function requires parameter 'x' but 'x' isn't passed."""

  def __init__(self, sig, passed_args, vm, missing_parameter):
    super(MissingParameter, self).__init__(sig, passed_args, vm)
    self.missing_parameter = missing_parameter
# pylint: enable=g-bad-exception-name


class Mutation(collections.namedtuple("_", ["instance", "name", "value"])):

  def __eq__(self, other):
    return (self.instance == other.instance and
            self.name == other.name and
            frozenset(self.value.data) == frozenset(other.value.data))

  def __hash__(self):
    return hash((self.instance, self.name, frozenset(self.value.data)))


class PyTDSignature(utils.VirtualMachineWeakrefMixin):
  """A PyTD function type (signature).

  This represents instances of functions with specific arguments and return
  type.
  """

  def __init__(self, name, pytd_sig, vm):
    super(PyTDSignature, self).__init__(vm)
    self.name = name
    self.pytd_sig = pytd_sig
    self.param_types = [
        self.vm.convert.constant_to_value(
            p.type, subst=datatypes.AliasingDict(), node=self.vm.root_cfg_node)
        for p in self.pytd_sig.params]
    self.signature = Signature.from_pytd(vm, name, pytd_sig)

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
      raise WrongArgCount(self.signature, args, self.vm)
    # Extra positional args are passed via the *args argument.
    varargs_type = self.signature.annotations.get(self.signature.varargs_name)
    if varargs_type and varargs_type.isinstance_ParameterizedClass():
      for (i, vararg) in enumerate(args.posargs[num_expected_posargs:]):
        name = argname(num_expected_posargs + i)
        arg_dict[name] = view[vararg]
        formal_args.append(
            (name, varargs_type.get_formal_type_parameter(abstract_utils.T)))

    # named args
    for name, arg in args.namedargs.items():
      if name in arg_dict:
        raise DuplicateKeyword(self.signature, args, self.vm, name)
      arg_dict[name] = view[arg]
    extra_kwargs = set(args.namedargs) - {p.name for p in self.pytd_sig.params}
    if extra_kwargs and not self.pytd_sig.starstarargs:
      raise WrongKeywordArgs(self.signature, args, self.vm, extra_kwargs)
    # Extra keyword args are passed via the **kwargs argument.
    kwargs_type = self.signature.annotations.get(self.signature.kwargs_name)
    if kwargs_type and kwargs_type.isinstance_ParameterizedClass():
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
        typ = self.vm.convert.widen_type(self.signature.annotations[name])
        formal_args.append((name, typ))

    return formal_args, arg_dict

  def _fill_in_missing_parameters(self, node, args, arg_dict):
    for p in self.pytd_sig.params:
      if p.name not in arg_dict:
        if (not p.optional and args.starargs is None and
            args.starstarargs is None):
          raise MissingParameter(self.signature, args, self.vm, p.name)
        # Assume the missing parameter is filled in by *args or **kwargs.
        # Unfortunately, we can't easily use *args or **kwargs to fill in
        # something more precise, since we need a Value, not a Variable.
        arg_dict[p.name] = self.vm.convert.unsolvable.to_binding(node)

  def substitute_formal_args(self, node, args, view, alias_map):
    """Substitute matching args into this signature. Used by PyTDFunction."""
    formal_args, arg_dict = self._map_args(args, view)
    self._fill_in_missing_parameters(node, args, arg_dict)
    subst, bad_arg = self.vm.matcher.compute_subst(
        node, formal_args, arg_dict, view, alias_map)
    if subst is None:
      if self.signature.has_param(bad_arg.name):
        signature = self.signature
      else:
        signature = self.signature.insert_varargs_and_kwargs(arg_dict)
      raise WrongArgTypes(signature, args, self.vm, bad_param=bad_arg)
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
    if (not isinstance(return_type, pytd.GenericType) or
        return_type.base_type.name != "__builtin__.type"):
      for param in pytd_utils.GetTypeParameters(return_type):
        if param.full_name in subst:
          node = self.vm.call_init(node, subst[param.full_name])
    try:
      ret = self.vm.convert.constant_to_var(
          abstract_utils.AsReturnValue(return_type), subst, node,
          source_sets=[sources])
    except self.vm.convert.TypeParameterError:
      # The return type contains a type parameter without a substitution.
      subst = subst.copy()
      visitor = visitors.CollectTypeParameters()
      return_type.Visit(visitor)

      for t in visitor.params:
        if t.full_name not in subst:
          subst[t.full_name] = self.vm.convert.empty.to_variable(node)
      return node, self.vm.convert.constant_to_var(
          abstract_utils.AsReturnValue(return_type), subst, node,
          source_sets=[sources])
    if not ret.bindings and isinstance(return_type, pytd.TypeParameter):
      ret.AddBinding(self.vm.convert.empty, [], node)
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
    mutations = self._get_mutation(node, arg_dict, subst)
    self.vm.trace_call(node, func, (self,),
                       tuple(arg_dict[p.name] for p in self.pytd_sig.params),
                       {}, ret_map[t])
    return node, ret_map[t], mutations

  def _get_mutation(self, node, arg_dict, subst):
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
    Returns:
      A list of Mutation instances.
    Raises:
      ValueError: If the pytd contains invalid information for mutated params.
    """
    # Handle mutable parameters using the information type parameters
    mutations = []
    for formal in self.pytd_sig.params:
      actual = arg_dict[formal.name]
      arg = actual.data
      if (formal.mutated_type is not None and
          arg.isinstance_SimpleAbstractValue()):
        if (isinstance(formal.type, pytd.GenericType) and
            isinstance(formal.mutated_type, pytd.GenericType) and
            formal.type.base_type == formal.mutated_type.base_type and
            isinstance(formal.type.base_type, pytd.ClassType) and
            formal.type.base_type.cls):
          names_actuals = zip(formal.mutated_type.base_type.cls.template,
                              formal.mutated_type.parameters)
          for tparam, type_actual in names_actuals:
            log.info("Mutating %s to %s",
                     tparam.name,
                     pytd_utils.Print(type_actual))
            type_actual_val = self.vm.convert.constant_to_var(
                abstract_utils.AsInstance(type_actual), subst, node,
                discard_concrete_values=True)
            mutations.append(Mutation(arg, tparam.full_name, type_actual_val))
        else:
          log.error("Old: %s", pytd_utils.Print(formal.type))
          log.error("New: %s", pytd_utils.Print(formal.mutated_type))
          log.error("Actual: %r", actual)
          raise ValueError("Mutable parameters setting a type to a "
                           "different base type is not allowed.")
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
        self.vm.convert.constant_to_value(
            p.type, subst=datatypes.AliasingDict(), node=self.vm.root_cfg_node)
        for p in self.pytd_sig.params]
    self.signature = Signature.from_pytd(self.vm, self.name, self.pytd_sig)
    return self

  def __repr__(self):
    return pytd_utils.Print(self.pytd_sig)
