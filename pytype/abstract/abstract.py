"""The abstract values used by vm.py.

This file contains BaseValue and its subclasses. Mixins such as Class
are in mixin.py, and other abstract logic is in abstract_utils.py.
"""

# Because pytype takes too long:
# pytype: skip-file

# Because of false positives:
# pylint: disable=unpacking-non-sequence
# pylint: disable=abstract-method

import collections
import contextlib
import inspect
import itertools
import logging

from pytype import utils
from pytype.abstract import _base
from pytype.abstract import _classes
from pytype.abstract import _instance_base
from pytype.abstract import _instances
from pytype.abstract import _singletons
from pytype.abstract import _typing
from pytype.abstract import abstract_utils
from pytype.abstract import class_mixin
from pytype.abstract import function
from pytype.abstract import mixin
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors
from pytype.typegraph import cfg_utils

log = logging.getLogger(__name__)

# For simplicity, we pretend all abstract values are defined in abstract.py.
BaseValue = _base.BaseValue

BuildClass = _classes.BuildClass
InterpreterClass = _classes.InterpreterClass
PyTDClass = _classes.PyTDClass
FunctionPyTDClass = _classes.FunctionPyTDClass
TypedDictClass = _classes.TypedDictClass
ParameterizedClass = _classes.ParameterizedClass
CallableClass = _classes.CallableClass
LiteralClass = _classes.LiteralClass
TupleClass = _classes.TupleClass

SimpleValue = _instance_base.SimpleValue
Instance = _instance_base.Instance

LazyConcreteDict = _instances.LazyConcreteDict
ConcreteValue = _instances.ConcreteValue
Module = _instances.Module
Coroutine = _instances.Coroutine
Iterator = _instances.Iterator
BaseGenerator = _instances.BaseGenerator
AsyncGenerator = _instances.AsyncGenerator
Generator = _instances.Generator
Tuple = _instances.Tuple
List = _instances.List
Dict = _instances.Dict
TypedDict = _instances.TypedDict
AnnotationsDict = _instances.AnnotationsDict

Unknown = _singletons.Unknown
Singleton = _singletons.Singleton
Empty = _singletons.Empty
Deleted = _singletons.Deleted
Unsolvable = _singletons.Unsolvable

AnnotationClass = _typing.AnnotationClass
AnnotationContainer = _typing.AnnotationContainer
TypeParameter = _typing.TypeParameter
TypeParameterInstance = _typing.TypeParameterInstance
Union = _typing.Union
LateAnnotation = _typing.LateAnnotation


class Function(SimpleValue):
  """Base class for function objects (NativeFunction, InterpreterFunction).

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    ctx: context.Context instance.
  """

  def __init__(self, name, ctx):
    super().__init__(name, ctx)
    self.cls = FunctionPyTDClass(self, ctx)
    self.is_attribute_of_class = False
    self.is_classmethod = False
    self.is_abstract = False
    self.members["func_name"] = self.ctx.convert.build_string(
        self.ctx.root_node, name)

  def property_get(self, callself, is_class=False):
    if self.name == "__new__" or not callself or is_class:
      return self
    self.is_attribute_of_class = True
    # We'd like to cache this, but we can't. "callself" contains Variables
    # that would be tied into a BoundFunction instance. However, those
    # Variables aren't necessarily visible from other parts of the CFG binding
    # this function. See test_duplicate_getproperty() in tests/test_flow.py.
    return self.bound_class(callself, self)

  def _get_cell_variable_name(self, var):
    """Get the python variable name of a pytype Variable."""
    f = self.ctx.vm.frame
    if not f:
      # Should not happen but does in some contrived test cases.
      return None
    for name, v in zip(f.f_code.co_freevars, f.cells):
      if v == var:
        return name
    return None

  def match_args(self, node, args, alias_map=None, match_all_views=False):
    """Check whether the given arguments can match the function signature."""
    for a in args.posargs:
      if not a.bindings:
        # The only way to get an unbound variable here is to reference a closure
        # cellvar before it is assigned to in the outer scope.
        name = self._get_cell_variable_name(a)
        assert name is not None, "Closure variable lookup failed."
        raise function.UndefinedParameterError(name)
    error = None
    matched = []
    arg_variables = args.get_variables()
    views = abstract_utils.get_views(arg_variables, node)
    skip_future = None
    while True:
      try:
        view = views.send(skip_future)
      except StopIteration:
        break
      log.debug("args in view: %r", [(a.bindings and view[a].data)
                                     for a in args.posargs])
      try:
        match = self._match_view(node, args, view, alias_map)
      except function.FailedFunctionCall as e:
        if e > error and node.HasCombination(list(view.values())):
          # Add the name of the caller if possible.
          if hasattr(self, "parent"):
            e.name = "%s.%s" % (self.parent.name, e.name)
          error = e
          skip_future = True
        else:
          # This error was ignored, but future ones with the same accessed
          # subset may need to be recorded, so we can't skip them.
          skip_future = False
        if match_all_views:
          raise e
      else:
        matched.append(match)
        skip_future = True
    if not matched and error:
      raise error  # pylint: disable=raising-bad-type
    return matched

  def _match_view(self, node, args, view, alias_map):
    raise NotImplementedError(self.__class__.__name__)

  def __repr__(self):
    return self.full_name + "(...)"

  def _extract_defaults(self, defaults_var):
    """Extracts defaults from a Variable, used by set_function_defaults.

    Args:
      defaults_var: Variable containing potential default values.

    Returns:
      A tuple of default values, if one could be extracted, or None otherwise.
    """
    # Case 1: All given data are tuple constants. Use the longest one.
    if all(isinstance(d, Tuple) for d in defaults_var.data):
      return max((d.pyval for d in defaults_var.data), key=len)
    else:
      # Case 2: Data are entirely Tuple Instances, Unknown or Unsolvable. Make
      # all parameters except self/cls optional.
      # Case 3: Data is anything else. Same as Case 2, but emit a warning.
      if not (all(isinstance(d, (Instance, Unknown, Unsolvable))
                  for d in defaults_var.data) and
              all(d.full_name == "builtins.tuple"
                  for d in defaults_var.data if isinstance(d, Instance))):
        self.ctx.errorlog.bad_function_defaults(self.ctx.vm.frames, self.name)
      # The ambiguous case is handled by the subclass.
      return None

  def set_function_defaults(self, node, defaults_var):
    raise NotImplementedError(self.__class__.__name__)


class ClassMethod(BaseValue):
  """Implements @classmethod methods in pyi."""

  def __init__(self, name, method, callself, ctx):
    super().__init__(name, ctx)
    self.cls = self.ctx.convert.function_type
    self.method = method
    self.method.is_attribute_of_class = True
    # Rename to callcls to make clear that callself is the cls parameter.
    self._callcls = callself
    self.signatures = self.method.signatures

  def call(self, node, func, args, alias_map=None):
    return self.method.call(
        node, func, args.replace(posargs=(self._callcls,) + args.posargs))

  def to_bound_function(self):
    return BoundPyTDFunction(self._callcls, self.method)


class StaticMethod(BaseValue):
  """Implements @staticmethod methods in pyi."""

  def __init__(self, name, method, _, ctx):
    super().__init__(name, ctx)
    self.cls = self.ctx.convert.function_type
    self.method = method
    self.signatures = self.method.signatures

  def call(self, *args, **kwargs):
    return self.method.call(*args, **kwargs)


class Property(BaseValue):
  """Implements @property methods in pyi.

  If a getter's return type depends on the type of the class, it needs to be
  resolved as a function, not as a constant.
  """

  def __init__(self, name, method, callself, ctx):
    super().__init__(name, ctx)
    self.cls = self.ctx.convert.function_type
    self.method = method
    self._callself = callself
    self.signatures = self.method.signatures

  def call(self, node, func, args, alias_map=None):
    func = func or self.to_binding(node)
    args = args or function.Args(posargs=(self._callself,))
    return self.method.call(node, func, args.replace(posargs=(self._callself,)))


class PyTDFunction(Function):
  """A PyTD function (name + list of signatures).

  This represents (potentially overloaded) functions.
  """

  @classmethod
  def make(cls, name, ctx, module, pyval=None, pyval_name=None):
    """Create a PyTDFunction.

    Args:
      name: The function name.
      ctx: The abstract context.
      module: The module that the function is in.
      pyval: Optionally, the pytd.Function object to use. Otherwise, it is
        fetched from the loader.
      pyval_name: Optionally, the name of the pytd.Function object to look up,
        if it is different from the function name.

    Returns:
      A new PyTDFunction.
    """
    assert not pyval or not pyval_name  # there's never a reason to pass both
    if not pyval:
      pyval_name = module + "." + (pyval_name or name)
      if module not in ("builtins", "typing"):
        pyval = ctx.loader.import_name(module).Lookup(pyval_name)
      else:
        pyval = ctx.loader.lookup_builtin(pyval_name)
    if isinstance(pyval, pytd.Alias) and isinstance(pyval.type, pytd.Function):
      pyval = pyval.type
    f = ctx.convert.constant_to_value(pyval, {}, ctx.root_node)
    self = cls(name, f.signatures, pyval.kind, ctx)
    self.module = module
    return self

  def __init__(self, name, signatures, kind, ctx):
    super().__init__(name, ctx)
    assert signatures
    self.kind = kind
    self.bound_class = BoundPyTDFunction
    self.signatures = signatures
    self._signature_cache = {}
    self._return_types = {sig.pytd_sig.return_type for sig in signatures}
    for sig in signatures:
      for param in sig.pytd_sig.params:
        if param.mutated_type is not None:
          self._has_mutable = True
          break
      else:
        self._has_mutable = False
    for sig in signatures:
      sig.function = self
      sig.name = self.name

  def property_get(self, callself, is_class=False):
    if self.kind == pytd.MethodTypes.STATICMETHOD:
      if is_class:
        # Binding the function to None rather than not binding it tells
        # output.py to infer the type as a Callable rather than reproducing the
        # signature, including the @staticmethod decorator, which is
        # undesirable for module-level aliases.
        callself = None
      return StaticMethod(self.name, self, callself, self.ctx)
    elif self.kind == pytd.MethodTypes.CLASSMETHOD:
      if not is_class:
        callself = abstract_utils.get_atomic_value(
            callself, default=self.ctx.convert.unsolvable)
        if isinstance(callself, TypeParameterInstance):
          callself = abstract_utils.get_atomic_value(
              callself.instance.get_instance_type_parameter(callself.name),
              default=self.ctx.convert.unsolvable)
        # callself is the instance, and we want to bind to its class.
        callself = callself.cls.to_variable(self.ctx.root_node)
      return ClassMethod(self.name, self, callself, self.ctx)
    elif self.kind == pytd.MethodTypes.PROPERTY and not is_class:
      return Property(self.name, self, callself, self.ctx)
    else:
      return super().property_get(callself, is_class)

  def argcount(self, _):
    return min(sig.signature.mandatory_param_count() for sig in self.signatures)

  def _log_args(self, arg_values_list, level=0, logged=None):
    """Log the argument values."""
    if log.isEnabledFor(logging.DEBUG):
      if logged is None:
        logged = set()
      for i, arg_values in enumerate(arg_values_list):
        arg_values = list(arg_values)
        if level:
          if arg_values and any(v.data not in logged for v in arg_values):
            log.debug("%s%s:", "  " * level, arg_values[0].variable.id)
        else:
          log.debug("Arg %d", i)
        for value in arg_values:
          if value.data not in logged:
            log.debug("%s%s [var %d]", "  " * (level + 1), value.data,
                      value.variable.id)
            self._log_args(value.data.unique_parameter_values(), level + 2,
                           logged | {value.data})

  def call(self, node, func, args, alias_map=None):
    # TODO(b/159052609): We should be passing function signatures to simplify.
    if len(self.signatures) == 1:
      args = args.simplify(node, self.ctx, self.signatures[0].signature)
    else:
      args = args.simplify(node, self.ctx)
    self._log_args(arg.bindings for arg in args.posargs)
    ret_map = {}
    retvar = self.ctx.program.NewVariable()
    all_mutations = {}
    # The following line may raise function.FailedFunctionCall
    possible_calls = self.match_args(node, args, alias_map)
    # It's possible for the substitution dictionary computed for a particular
    # view of 'args' to contain references to variables not in the view because
    # of optimizations that copy bindings directly into subst without going
    # through the normal matching process. Thus, we create a combined view that
    # is guaranteed to contain an entry for every variable in every view for use
    # by the match_var_against_type() call in 'compatible_with' below.
    combined_view = {}
    for view, signatures in possible_calls:
      if len(signatures) > 1:
        ret = self._call_with_signatures(node, func, args, view, signatures)
      else:
        (sig, arg_dict, subst), = signatures
        ret = sig.call_with_args(
            node, func, arg_dict, subst, ret_map, alias_map)
      node, result, mutations = ret
      retvar.PasteVariable(result, node)
      for mutation in mutations:
        # This may overwrite a previous view, which is fine: we just want any
        # valid view to pass to match_var_against_type() later.
        all_mutations[mutation] = view
      combined_view.update(view)

    # Don't check container types if the function has multiple bindings.
    # This is a hack to prevent false positives when we call a method on a
    # variable with multiple bindings, since we don't always filter rigorously
    # enough in get_views.
    # See tests/test_annotations:test_list for an example that would break
    # if we removed the len(bindings) check.
    if all_mutations and len(func.variable.Bindings(node)) == 1:
      # Raise an error if:
      # - An annotation has a type param that is not ambigious or empty
      # - The mutation adds a type that is not ambiguous or empty
      def should_check(value):
        return not isinstance(value, AMBIGUOUS_OR_EMPTY)

      def compatible_with(new, existing, view):
        """Check whether a new type can be added to a container."""
        new_key = view[new].data.get_type_key()
        for data in existing:
          k = (new_key, data.get_type_key())
          if k not in compatible_with_cache:
            # This caching lets us skip duplicate matching work. Very
            # unfortunately, it is also needed for correctness because
            # cfg_utils.deep_variable_product() ignores bindings to values with
            # duplicate type keys when generating views.
            compatible_with_cache[k] = self.ctx.matcher(
                node).match_var_against_type(new, data.cls, {}, view)
          if compatible_with_cache[k] is not None:
            return True
        return False

      compatible_with_cache = {}
      filtered_mutations = []
      errors = collections.defaultdict(dict)

      for (obj, name, values), view in all_mutations.items():
        if obj.from_annotation:
          params = obj.get_instance_type_parameter(name)
          ps = {v for v in params.data if should_check(v)}
          if ps:
            filtered_values = self.ctx.program.NewVariable()
            # check if the container type is being broadened.
            new = []
            for b in values.bindings:
              if not should_check(b.data) or b.data in ps:
                filtered_values.PasteBinding(b)
                continue
              new_view = {**combined_view, **view, values: b}
              if not compatible_with(values, ps, new_view):
                if not node.HasCombination([b]):
                  # Since HasCombination is expensive, we don't use it to
                  # pre-filter bindings, but once we think we have an error, we
                  # should double-check that the binding is actually visible. We
                  # also drop non-visible bindings from filtered_values.
                  continue
                filtered_values.PasteBinding(b)
                new.append(b.data)
            # By updating filtered_mutations only when ps is non-empty, we
            # filter out mutations to parameters with type Any.
            filtered_mutations.append((obj, name, filtered_values))
            if new:
              formal = name.split(".")[-1]
              errors[obj][formal] = (params, values, obj.from_annotation)
        else:
          filtered_mutations.append((obj, name, values))

      all_mutations = filtered_mutations

      for obj, errs in errors.items():
        names = {name for _, _, name in errs.values()}
        name = list(names)[0] if len(names) == 1 else None
        self.ctx.errorlog.container_type_mismatch(self.ctx.vm.frames, obj, errs,
                                                  name)

    node = abstract_utils.apply_mutations(node, all_mutations.__iter__)
    return node, retvar

  def _get_mutation_to_unknown(self, node, values):
    """Mutation for making all type parameters in a list of instances "unknown".

    This is used if we call a function that has mutable parameters and
    multiple signatures with unknown parameters.

    Args:
      node: The current CFG node.
      values: A list of instances of BaseValue.

    Returns:
      A list of function.Mutation instances.
    """
    mutations = []
    for v in values:
      if isinstance(v, SimpleValue):
        for name in v.instance_type_parameters:
          mutations.append(
              function.Mutation(
                  v, name,
                  self.ctx.convert.create_new_unknown(
                      node, action="type_param_" + name)))
    return mutations

  def _can_match_multiple(self, args, view):
    # If we're calling an overloaded pytd function with an unknown as a
    # parameter, we can't tell whether it matched or not. Hence, if multiple
    # signatures are possible matches, we don't know which got called. Check
    # if this is the case.
    if len(self.signatures) <= 1:
      return False
    if any(isinstance(view[arg].data, AMBIGUOUS_OR_EMPTY)
           for arg in args.get_variables()):
      return True
    for arg in (args.starargs, args.starstarargs):
      # An opaque *args or **kwargs behaves like an unknown.
      if arg and not isinstance(arg, mixin.PythonConstant):
        return True
    return False

  def _match_view(self, node, args, view, alias_map=None):
    if self._can_match_multiple(args, view):
      signatures = tuple(self._yield_matching_signatures(
          node, args, view, alias_map))
    else:
      # We take the first signature that matches, and ignore all after it.
      # This is because in the pytds for the standard library, the last
      # signature(s) is/are fallback(s) - e.g. list is defined by
      # def __init__(self: x: list)
      # def __init__(self, x: iterable)
      # def __init__(self, x: generator)
      # def __init__(self, x: object)
      # with the last signature only being used if none of the others match.
      sig = next(self._yield_matching_signatures(node, args, view, alias_map))
      signatures = (sig,)
    return (view, signatures)

  def _call_with_signatures(self, node, func, args, view, signatures):
    """Perform a function call that involves multiple signatures."""
    ret_type = self._combine_multiple_returns(signatures)
    if (self.ctx.options.protocols and isinstance(ret_type, pytd.AnythingType)):
      # We can infer a more specific type.
      log.debug("Creating unknown return")
      result = self.ctx.convert.create_new_unknown(node, action="pytd_call")
    else:
      log.debug("Unknown args. But return is %s", pytd_utils.Print(ret_type))
      result = self.ctx.convert.constant_to_var(
          abstract_utils.AsReturnValue(ret_type), {}, node)
    for i, arg in enumerate(args.posargs):
      if isinstance(view[arg].data, Unknown):
        for sig, _, _ in signatures:
          if (len(sig.param_types) > i and
              isinstance(sig.param_types[i], TypeParameter)):
            # Change this parameter from unknown to unsolvable to prevent the
            # unknown from being solved to a type in another signature. For
            # instance, with the following definitions:
            #  def f(x: T) -> T
            #  def f(x: int) -> T
            # the type of x should be Any, not int.
            view[arg] = arg.AddBinding(self.ctx.convert.unsolvable, [], node)
            break
    if self._has_mutable:
      # TODO(b/159055015): We only need to whack the type params that appear in
      # a mutable parameter.
      mutations = self._get_mutation_to_unknown(
          node, (view[p].data for p in itertools.chain(
              args.posargs, args.namedargs.values())))
    else:
      mutations = []
    self.ctx.vm.trace_call(
        node, func, tuple(sig[0] for sig in signatures),
        [view[arg] for arg in args.posargs],
        {name: view[arg] for name, arg in args.namedargs.items()}, result)
    return node, result, mutations

  def _combine_multiple_returns(self, signatures):
    """Combines multiple return types.

    Args:
      signatures: The candidate signatures.

    Returns:
      The combined return type.
    """
    options = []
    for sig, _, _ in signatures:
      t = sig.pytd_sig.return_type
      params = pytd_utils.GetTypeParameters(t)
      if params:
        replacement = {}
        for param_type in params:
          replacement[param_type] = pytd.AnythingType()
        replace_visitor = visitors.ReplaceTypeParameters(replacement)
        t = t.Visit(replace_visitor)
      options.append(t)
    if len(set(options)) == 1:
      return options[0]
    # Optimizing and then removing unions allows us to preserve as much
    # precision as possible while avoiding false positives.
    ret_type = optimize.Optimize(pytd_utils.JoinTypes(options))
    return ret_type.Visit(visitors.ReplaceUnionsWithAny())

  def _yield_matching_signatures(self, node, args, view, alias_map):
    """Try, in order, all pytd signatures, yielding matches."""
    error = None
    matched = False
    # Once a constant has matched a literal type, it should no longer be able to
    # match non-literal types. For example, with:
    #   @overload
    #   def f(x: Literal['r']): ...
    #   @overload
    #   def f(x: str): ...
    # f('r') should match only the first signature.
    literal_matches = set()
    for sig in self.signatures:
      if any(not abstract_utils.is_literal(sig.signature.annotations.get(name))
             for name in literal_matches):
        continue
      try:
        arg_dict, subst = sig.substitute_formal_args(
            node, args, view, alias_map)
      except function.FailedFunctionCall as e:
        if e > error:
          error = e
      else:
        matched = True
        for name, binding in arg_dict.items():
          if (isinstance(binding.data, mixin.PythonConstant) and
              abstract_utils.is_literal(sig.signature.annotations.get(name))):
            literal_matches.add(name)
        yield sig, arg_dict, subst
    if not matched:
      raise error  # pylint: disable=raising-bad-type

  def set_function_defaults(self, unused_node, defaults_var):
    """Attempts to set default arguments for a function's signatures.

    If defaults_var is not an unambiguous tuple (i.e. one that can be processed
    by abstract_utils.get_atomic_python_constant), every argument is made
    optional and a warning is issued. This function emulates __defaults__.

    If this function is part of a class (or has a parent), that parent is
    updated so the change is stored.

    Args:
      unused_node: the node that defaults are being set at. Not used here.
      defaults_var: a Variable with a single binding to a tuple of default
                    values.
    """
    defaults = self._extract_defaults(defaults_var)
    new_sigs = []
    for sig in self.signatures:
      if defaults:
        new_sigs.append(sig.set_defaults(defaults))
      else:
        d = sig.param_types
        # If we have a parent, we have a "self" or "cls" parameter. Do NOT make
        # that one optional!
        if hasattr(self, "parent"):
          d = d[1:]
        new_sigs.append(sig.set_defaults(d))
    self.signatures = new_sigs
    # Update our parent's AST too, if we have a parent.
    # 'parent' is set by PyTDClass._convert_member
    if hasattr(self, "parent"):
      self.parent._member_map[self.name] = self.generate_ast()  # pylint: disable=protected-access

  def generate_ast(self):
    return pytd.Function(
        name=self.name,
        signatures=tuple(s.pytd_sig for s in self.signatures),
        kind=self.kind,
        flags=pytd.MethodFlags.abstract_flag(self.is_abstract))


class NativeFunction(Function):
  """An abstract value representing a native function.

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    func: An object with a __call__ method.
    ctx: context.Context instance.
  """

  def __init__(self, name, func, ctx):
    super().__init__(name, ctx)
    self.func = func
    self.bound_class = lambda callself, underlying: self

  def argcount(self, _):
    return self.func.func_code.co_argcount

  def call(self, node, _, args, alias_map=None):
    sig = None
    if isinstance(self.func.__self__, CallableClass):
      sig = function.Signature.from_callable(self.func.__self__)
    args = args.simplify(node, self.ctx, match_signature=sig)
    posargs = [u.AssignToNewVariable(node) for u in args.posargs]
    namedargs = {k: u.AssignToNewVariable(node)
                 for k, u in args.namedargs.items()}
    try:
      inspect.signature(self.func).bind(node, *posargs, **namedargs)
    except ValueError as e:
      # Happens for, e.g.,
      #   def f((x, y)): pass
      #   f((42,))
      raise NotImplementedError("Wrong number of values to unpack") from e
    except TypeError as e:
      # The possible errors here are:
      #   (1) wrong arg count
      #   (2) duplicate keyword
      #   (3) unexpected keyword
      # The way we constructed namedargs rules out (2).
      if "keyword" in utils.message(e):
        # Happens for, e.g.,
        #   def f(*args): pass
        #   f(x=42)
        raise NotImplementedError("Unexpected keyword") from e
      # The function was passed the wrong number of arguments. The signature is
      # ([self, ]node, ...). The length of "..." tells us how many variables
      # are expected.
      expected_argcount = len(inspect.getfullargspec(self.func).args) - 1
      if inspect.ismethod(self.func) and self.func.__self__ is not None:
        expected_argcount -= 1
      actual_argcount = len(posargs) + len(namedargs)
      if (actual_argcount > expected_argcount or
          (not args.starargs and not args.starstarargs)):
        # If we have too many arguments, or starargs and starstarargs are both
        # empty, then we can be certain of a WrongArgCount error.
        argnames = tuple("_" + str(i) for i in range(expected_argcount))
        sig = function.Signature(
            self.name, argnames, None, set(), None, {}, {}, {})
        raise function.WrongArgCount(sig, args, self.ctx)
      assert actual_argcount < expected_argcount
      # Assume that starargs or starstarargs fills in the missing arguments.
      # Instead of guessing where these arguments should go, overwrite all of
      # the arguments with a list of unsolvables of the correct length, which
      # is guaranteed to give us a correct (but imprecise) analysis.
      posargs = [
          self.ctx.new_unsolvable(node) for _ in range(expected_argcount)
      ]
      namedargs = {}
    return self.func(node, *posargs, **namedargs)

  def get_positional_names(self):
    code = self.func.func_code
    return list(code.co_varnames[:code.co_argcount])


class SignedFunction(Function):
  """An abstract base class for functions represented by function.Signature.

  Subclasses should define call(self, node, f, args) and set self.bound_class.
  """

  def __init__(self, signature, ctx):
    super().__init__(signature.name, ctx)
    self.signature = signature
    # Track whether we've annotated `self` with `set_self_annot`, since
    # annotating `self` in `__init__` is otherwise illegal.
    self._has_self_annot = False

  @contextlib.contextmanager
  def set_self_annot(self, annot_class):
    """Set the annotation for `self` in a class."""
    self_name = self.signature.param_names[0]
    old_self = self.signature.annotations.get(self_name)
    old_has_self_annot = self._has_self_annot
    self.signature.annotations[self_name] = annot_class
    self._has_self_annot = True
    try:
      yield
    finally:
      if old_self:
        self.signature.annotations[self_name] = old_self
      else:
        del self.signature.annotations[self_name]
      self._has_self_annot = old_has_self_annot

  def argcount(self, _):
    return len(self.signature.param_names)

  def get_nondefault_params(self):
    return ((n, n in self.signature.kwonly_params)
            for n in self.signature.param_names
            if n not in self.signature.defaults)

  def match_and_map_args(self, node, args, alias_map):
    """Calls match_args() and _map_args()."""
    return self.match_args(node, args, alias_map), self._map_args(node, args)

  def _map_args(self, node, args):
    """Map call args to function args.

    This emulates how Python would map arguments of function calls. It takes
    care of keyword parameters, default parameters, and *args and **kwargs.

    Args:
      node: The current CFG node.
      args: The arguments.

    Returns:
      A dictionary, mapping strings (parameter names) to cfg.Variable.

    Raises:
      function.FailedFunctionCall: If the caller supplied incorrect arguments.
    """
    # Originate a new variable for each argument and call.
    posargs = [u.AssignToNewVariable(node)
               for u in args.posargs]
    kws = {k: u.AssignToNewVariable(node)
           for k, u in args.namedargs.items()}
    sig = self.signature
    callargs = {
        name: self.ctx.program.NewVariable(default.data, [], node)
        for name, default in sig.defaults.items()
    }
    positional = dict(zip(sig.param_names, posargs))
    for key in positional:
      if key in kws:
        raise function.DuplicateKeyword(sig, args, self.ctx, key)
    extra_kws = set(kws).difference(sig.param_names + sig.kwonly_params)
    if extra_kws and not sig.kwargs_name:
      raise function.WrongKeywordArgs(sig, args, self.ctx, extra_kws)
    callargs.update(positional)
    callargs.update(kws)
    for key, kwonly in self.get_nondefault_params():
      if key not in callargs:
        if args.starstarargs or (args.starargs and not kwonly):
          # We assume that because we have *args or **kwargs, we can use these
          # to fill in any parameters we might be missing.
          callargs[key] = self.ctx.new_unsolvable(node)
        else:
          raise function.MissingParameter(sig, args, self.ctx, key)
    for key in sig.kwonly_params:
      if key not in callargs:
        raise function.MissingParameter(sig, args, self.ctx, key)
    if sig.varargs_name:
      varargs_name = sig.varargs_name
      extraneous = posargs[self.argcount(node):]
      if args.starargs:
        if extraneous:
          log.warning("Not adding extra params to *%s", varargs_name)
        callargs[varargs_name] = args.starargs.AssignToNewVariable(node)
      else:
        callargs[varargs_name] = self.ctx.convert.build_tuple(node, extraneous)
    elif len(posargs) > self.argcount(node):
      raise function.WrongArgCount(sig, args, self.ctx)
    if sig.kwargs_name:
      kwargs_name = sig.kwargs_name
      # Build a **kwargs dictionary out of the extraneous parameters
      if args.starstarargs:
        callargs[kwargs_name] = args.starstarargs.AssignToNewVariable(node)
      else:
        omit = sig.param_names + sig.kwonly_params
        k = Dict(self.ctx)
        k.update(node, args.namedargs, omit=omit)
        callargs[kwargs_name] = k.to_variable(node)
    return callargs

  def _match_view(self, node, args, view, alias_map=None):
    arg_dict = {}
    formal_args = []
    for name, arg, formal in self.signature.iter_args(args):
      arg_dict[name] = view[arg]
      if formal is not None:
        if name in (self.signature.varargs_name, self.signature.kwargs_name):
          # The annotation is Tuple or Dict, but the passed arg only has to be
          # Iterable or Mapping.
          formal = self.ctx.convert.widen_type(formal)
        formal_args.append((name, formal))
    subst, bad_arg = self.ctx.matcher(node).compute_subst(
        formal_args, arg_dict, view, alias_map)
    if subst is None:
      raise function.WrongArgTypes(
          self.signature, args, self.ctx, bad_param=bad_arg)
    return subst

  def get_first_opcode(self):
    return None

  def set_function_defaults(self, node, defaults_var):
    """Attempts to set default arguments of a function.

    If defaults_var is not an unambiguous tuple (i.e. one that can be processed
    by abstract_utils.get_atomic_python_constant), every argument is made
    optional and a warning is issued. This function emulates __defaults__.

    Args:
      node: The node where default arguments are being set. Needed if we cannot
            get a useful value from defaults_var.
      defaults_var: a Variable with a single binding to a tuple of default
                    values.
    """
    defaults = self._extract_defaults(defaults_var)
    if defaults is None:
      defaults = [
          self.ctx.new_unsolvable(node) for _ in self.signature.param_names
      ]
    defaults = dict(zip(self.signature.param_names[-len(defaults):], defaults))
    self.signature.defaults = defaults

  def _mutations_generator(self, node, first_arg, substs):
    def generator():
      """Yields mutations."""
      if (not (self.is_attribute_of_class or self.name == "__new__") or
          not first_arg or not substs):
        return
      try:
        inst = abstract_utils.get_atomic_value(first_arg, Instance)
      except abstract_utils.ConversionError:
        return
      if inst.cls.template:
        for subst in substs:
          for k, v in subst.items():
            if k in inst.instance_type_parameters:
              value = inst.instance_type_parameters[k].AssignToNewVariable(node)
              if all(isinstance(val, Unknown) for val in v.data):
                for param in inst.cls.template:
                  if subst.same_name(k, param.full_name):
                    value.PasteVariable(param.instantiate(node), node)
                    break
                else:
                  # See GenericFeatureTest.test_reinherit_generic in
                  # tests/test_generic2. This can happen if one generic class
                  # inherits from another and separately reuses a TypeVar.
                  value.PasteVariable(v, node)
              else:
                value.PasteVariable(v, node)
              yield function.Mutation(inst, k, value)
    # Optimization: return a generator to avoid iterating over the mutations an
    # extra time.
    return generator


class InterpreterFunction(SignedFunction):
  """An abstract value representing a user-defined function.

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    code: A code object.
    closure: Tuple of cells (cfg.Variable) containing the free variables
      this closure binds to.
    ctx: context.Context instance.
  """

  _function_cache = {}

  @classmethod
  def make(cls, name, code, f_locals, f_globals, defaults, kw_defaults, closure,
           annotations, ctx):
    """Get an InterpreterFunction.

    Things like anonymous functions and generator expressions are created
    every time the corresponding code executes. Caching them makes it easier
    to detect when the environment hasn't changed and a function call can be
    optimized away.

    Arguments:
      name: Function name.
      code: A code object.
      f_locals: The locals used for name resolution.
      f_globals: The globals used for name resolution.
      defaults: Default arguments.
      kw_defaults: Default arguments for kwonly parameters.
      closure: The free variables this closure binds to.
      annotations: Function annotations. Dict of name -> BaseValue.
      ctx: context.Context instance.

    Returns:
      An InterpreterFunction.
    """
    annotations = annotations or {}
    if "return" in annotations:
      # Check Generator/AsyncGenerator return type
      ret_type = annotations["return"]
      if code.has_generator():
        if not abstract_utils.matches_generator(ret_type):
          ctx.errorlog.bad_yield_annotation(
              ctx.vm.frames, name, ret_type, is_async=False)
      elif code.has_async_generator():
        if not abstract_utils.matches_async_generator(ret_type):
          ctx.errorlog.bad_yield_annotation(
              ctx.vm.frames, name, ret_type, is_async=True)
    overloads = ctx.vm.frame.overloads[name]
    key = (name, code,
           abstract_utils.hash_all_dicts(
               (f_globals.members, set(code.co_names)),
               (f_locals.members,
                set(f_locals.members) - set(code.co_varnames)), ({
                    key: ctx.program.NewVariable([value], [], ctx.root_node)
                    for key, value in annotations.items()
                }, None), (dict(
                    enumerate(
                        ctx.program.NewVariable([f], [], ctx.root_node)
                        for f in overloads)), None),
               (dict(enumerate(defaults)), None),
               (dict(enumerate(closure or ())), None)))
    if key not in cls._function_cache:
      cls._function_cache[key] = cls(name, code, f_locals, f_globals, defaults,
                                     kw_defaults, closure, annotations,
                                     overloads, ctx)
    return cls._function_cache[key]

  def __init__(self, name, code, f_locals, f_globals, defaults, kw_defaults,
               closure, annotations, overloads, ctx):
    log.debug("Creating InterpreterFunction %r for %r", name, code.co_name)
    self.bound_class = BoundInterpreterFunction
    self.doc = code.co_consts[0] if code.co_consts else None
    self.code = code
    self.f_globals = f_globals
    self.f_locals = f_locals
    self.defaults = tuple(defaults)
    self.kw_defaults = kw_defaults
    self.closure = closure
    self._call_cache = {}
    self._call_records = []
    # TODO(b/78034005): Combine this and PyTDFunction.signatures into a single
    # way to handle multiple signatures that SignedFunction can also use.
    self._overloads = overloads
    self.has_overloads = bool(overloads)
    self.is_overload = False  # will be set by typing_overlay.Overload.call
    self.nonstararg_count = self.code.co_argcount
    if self.code.co_kwonlyargcount >= 0:  # This is usually -1 or 0 (fast call)
      self.nonstararg_count += self.code.co_kwonlyargcount
    signature = self._build_signature(name, annotations)
    super().__init__(signature, ctx)
    self._update_signature_scope()
    self.last_frame = None  # for BuildClass
    self._store_call_records = False
    self.is_class_builder = False  # Will be set by BuildClass.
    if name.endswith(".__init_subclass__"):
      # __init_subclass__ is automatically promoted to a classmethod
      self.is_classmethod = True

  @contextlib.contextmanager
  def record_calls(self):
    """Turn on recording of function calls. Used by analyze.py."""
    old = self._store_call_records
    self._store_call_records = True
    yield
    self._store_call_records = old

  def _build_signature(self, name, annotations):
    """Build a function.Signature object representing this function."""
    vararg_name = None
    kwarg_name = None
    kwonly = set(self.code.co_varnames[
        self.code.co_argcount:self.nonstararg_count])
    arg_pos = self.nonstararg_count
    if self.has_varargs():
      vararg_name = self.code.co_varnames[arg_pos]
      arg_pos += 1
    if self.has_kwargs():
      kwarg_name = self.code.co_varnames[arg_pos]
      arg_pos += 1
    defaults = dict(zip(
        self.get_positional_names()[-len(self.defaults):], self.defaults))
    defaults.update(self.kw_defaults)
    return function.Signature(
        name,
        tuple(self.code.co_varnames[:self.code.co_argcount]),
        vararg_name,
        tuple(kwonly),
        kwarg_name,
        defaults,
        annotations)

  def _update_signature_scope(self):
    # If this is a nested function in an instance method and the nested function
    # accesses 'self', then the first variable in the closure is 'self'. We use
    # 'self' to update the scopes of any type parameters in the nested method's
    # signature to the containing class.
    if not self.closure:
      return
    maybe_instance = self.closure[0]
    try:
      instance = abstract_utils.get_atomic_value(maybe_instance, Instance)
    except abstract_utils.ConversionError:
      return
    if isinstance(instance.cls, InterpreterClass):
      instance.cls.update_signature_scope(self)

  def get_first_opcode(self):
    return self.code.first_opcode

  def argcount(self, _):
    return self.code.co_argcount

  def match_args(self, node, args, alias_map=None, match_all_views=False):
    if not self.signature.has_param_annotations:
      return
    return super().match_args(node, args, alias_map, match_all_views)

  def _inner_cls_check(self, last_frame):
    """Check if the function and its nested class use same type parameter."""
    # get all type parameters from function annotations
    all_type_parameters = []
    for annot in self.signature.annotations.values():
      params = self.ctx.annotation_utils.get_type_parameters(annot)
      all_type_parameters.extend(itm.with_module(None) for itm in params)

    if all_type_parameters:
      for key, value in last_frame.f_locals.pyval.items():
        value = abstract_utils.get_atomic_value(
            value, default=self.ctx.convert.unsolvable)
        if (isinstance(value, InterpreterClass) and value.template and
            key == value.name):
          # `value` is a nested class definition.
          inner_cls_types = value.collect_inner_cls_types()
          inner_cls_types.update([(value, item.with_module(None))
                                  for item in value.template])
          # Report errors in a deterministic order.
          for cls, item in sorted(inner_cls_types, key=lambda typ: typ[1].name):
            if item in all_type_parameters:
              self.ctx.errorlog.invalid_annotation(
                  self.ctx.vm.simple_stack(self.get_first_opcode()), item,
                  ("Function [%s] and its nested generic class [%s] cannot use "
                   "the same type variable %s") %
                  (self.full_name, cls.full_name, item.name))

  def signature_functions(self):
    """Get the functions that describe this function's signature."""
    return self._overloads or [self]

  def iter_signature_functions(self):
    """Loop through signatures, setting each as the primary one in turn."""
    if not self._overloads:
      yield self
      return
    for f in self._overloads:
      old_overloads = self._overloads
      self._overloads = [f]
      try:
        yield f
      finally:
        self._overloads = old_overloads

  def _find_matching_sig(self, node, args, alias_map):
    error = None
    for f in self.signature_functions():
      try:
        # match_args and _map_args both do some matching, so together they fully
        # type-check the arguments.
        substs, callargs = f.match_and_map_args(node, args, alias_map)
      except function.FailedFunctionCall as e:
        if e > error:
          error = e
      else:
        # We use the first matching overload.
        return f.signature, substs, callargs
    raise error  # pylint: disable=raising-bad-type

  def _set_callself_maybe_missing_members(self):
    if self.ctx.callself_stack:
      for b in self.ctx.callself_stack[-1].bindings:
        b.data.maybe_missing_members = True

  def _fix_args_for_unannotated_contextmanager_exit(self, node, func, args):
    """Adjust argument types for a contextmanager's __exit__ method."""
    # When a contextmanager is used in a 'with' statement, its __exit__ method
    # is implicitly called with either (None, None, None) or
    # (exc_type, exc_value, traceback) depending on whether an exception is
    # encountered. These two cases generate different bytecode, and our VM
    # always assumes no exception. But for analyzing __exit__, we should allow
    # for both possibilities.
    if not (isinstance(func.data, BoundInterpreterFunction) and
            self.name.endswith(".__exit__") and len(args.posargs) == 4 and
            not args.has_namedargs() and not args.starargs and
            not args.starstarargs and not self.signature.has_param_annotations):
      return args
    exception_type = self.ctx.convert.name_to_value("builtins.BaseException")
    arg1 = self.ctx.program.NewVariable(
        [exception_type, self.ctx.convert.none], [], node)
    arg2 = exception_type.instantiate(node)
    arg2.AddBinding(self.ctx.convert.none, [], node)
    arg3 = self.ctx.program.NewVariable(
        [self.ctx.convert.unsolvable, self.ctx.convert.none], [], node)
    return function.Args(posargs=(args.posargs[0], arg1, arg2, arg3))

  def call(self, node, func, args, new_locals=False, alias_map=None,
           frame_substs=()):
    if self.is_overload:
      raise function.NotCallable(self)
    if (self.ctx.vm.is_at_maximum_depth() and
        not abstract_utils.func_name_is_class_init(self.name)):
      log.info("Maximum depth reached. Not analyzing %r", self.name)
      self._set_callself_maybe_missing_members()
      return node, self.ctx.new_unsolvable(node)
    args = self._fix_args_for_unannotated_contextmanager_exit(node, func, args)
    args = args.simplify(node, self.ctx, self.signature)
    sig, substs, callargs = self._find_matching_sig(node, args, alias_map)
    if sig is not self.signature:
      # We've matched an overload; remap the callargs using the implementation
      # so that optional parameters, etc, are correctly defined.
      callargs = self._map_args(node, args)
    first_arg = sig.get_first_arg(callargs)
    annotation_substs = substs
    # Adds type parameter substitutions from all containing classes. Note that
    # lower frames (ones closer to the end of self.ctx.vm.frames) take
    # precedence over higher ones.
    for frame in reversed(self.ctx.vm.frames):
      annotation_substs = abstract_utils.combine_substs(
          frame.substs, annotation_substs)
    # Keep type parameters without substitutions, as they may be needed for
    # type-checking down the road.
    annotations = self.ctx.annotation_utils.sub_annotations(
        node, sig.annotations, annotation_substs, instantiate_unbound=False)
    if sig.has_param_annotations:
      if first_arg and sig.param_names[0] == "self":
        try:
          maybe_container = abstract_utils.get_atomic_value(first_arg)
        except abstract_utils.ConversionError:
          container = None
        else:
          cls = maybe_container.cls
          if (isinstance(cls, InterpreterClass) or
              isinstance(cls, ParameterizedClass) and
              isinstance(cls.base_cls, InterpreterClass)):
            container = maybe_container
          else:
            container = None
      else:
        container = None
      for name in callargs:
        if (name in annotations and (not self.is_attribute_of_class or
                                     self.argcount(node) == 0 or
                                     name != sig.param_names[0])):
          extra_key = (self.get_first_opcode(), name)
          node, callargs[name] = self.ctx.annotation_utils.init_annotation(
              node,
              name,
              annotations[name],
              container=container,
              extra_key=extra_key)
    mutations = self._mutations_generator(node, first_arg, substs)
    node = abstract_utils.apply_mutations(node, mutations)
    if substs:
      frame_substs = tuple(itertools.chain(frame_substs, substs))
    try:
      frame = self.ctx.vm.make_frame(
          node,
          self.code,
          self.f_globals,
          self.f_locals,
          callargs,
          self.closure,
          new_locals=new_locals,
          func=func,
          first_arg=first_arg,
          substs=frame_substs)
    except self.ctx.vm.VirtualMachineRecursionError:
      # If we've encountered recursion in a constructor, then we have another
      # incompletely initialized instance of the same class (or a subclass) at
      # the same node. (See, e.g., testRecursiveConstructor and
      # testRecursiveConstructorSubclass in test_classes.ClassesTest.) If we
      # allow the VirtualMachineRecursionError to be raised, initialization of
      # that first instance will be aborted. Instead, mark this second instance
      # as incomplete.
      self._set_callself_maybe_missing_members()
      return node, self.ctx.new_unsolvable(node)
    caller_is_abstract = abstract_utils.check_classes(
        first_arg, lambda cls: cls.is_abstract)
    caller_is_protocol = abstract_utils.check_classes(
        first_arg, lambda cls: cls.is_protocol)
    # We should avoid checking the return value against any return annotation
    # when we are analyzing an attribute of a protocol or an abstract class's
    # abstract method.
    check_return = (not (self.is_attribute_of_class and caller_is_protocol) and
                    not (caller_is_abstract and self.is_abstract))
    if sig.has_return_annotation or not check_return:
      frame.allowed_returns = annotations.get("return",
                                              self.ctx.convert.unsolvable)
      frame.check_return = check_return
    if self.ctx.options.skip_repeat_calls:
      callkey = abstract_utils.hash_all_dicts(
          (callargs, None),
          (frame.f_globals.members, set(self.code.co_names)),
          (frame.f_locals.members,
           set(frame.f_locals.members) - set(self.code.co_varnames)))
    else:
      # Make the callkey the number of times this function has been called so
      # that no call has the same key as a previous one.
      callkey = len(self._call_cache)
    if callkey in self._call_cache:
      old_ret, old_remaining_depth = self._call_cache[callkey]
      # Optimization: This function has already been called, with the same
      # environment and arguments, so recycle the old return value.
      # We would want to skip this optimization and reanalyze the call if we can
      # traverse the function deeper.
      if self.ctx.vm.remaining_depth() > old_remaining_depth:
        # TODO(rechen): Reanalysis is necessary only if the VM was unable to
        # completely analyze the call with old_remaining_depth. For now, we can
        # get away with not checking for completion because of how severely
        # --quick constrains the maximum depth.
        log.info(
            "Reanalyzing %r because we can traverse deeper; "
            "remaining_depth = %d, old_remaining_depth = %d", self.name,
            self.ctx.vm.remaining_depth(), old_remaining_depth)
      else:
        ret = old_ret.AssignToNewVariable(node)
        if self._store_call_records:
          # Even if the call is cached, we might not have been recording it.
          self._call_records.append((callargs, ret, node))
        return node, ret
    if self.code.has_generator():
      generator = Generator(frame, self.ctx)
      # Run the generator right now, even though the program didn't call it,
      # because we need to know the contained type for futher matching.
      node2, _ = generator.run_generator(node)
      if self.is_coroutine():
        # This function is a generator-based coroutine. We convert the return
        # value here even though byte_GET_AWAITABLE repeats the conversion so
        # that matching against a typing.Awaitable annotation succeeds.
        var = generator.get_instance_type_parameter(abstract_utils.V)
        ret = Coroutine(self.ctx, var, node2).to_variable(node2)
      else:
        ret = generator.to_variable(node2)
      node_after_call = node2
    elif self.code.has_async_generator():
      async_generator = AsyncGenerator(frame, self.ctx)
      node2, _ = async_generator.run_generator(node)
      node_after_call, ret = node2, async_generator.to_variable(node2)
    else:
      # If any parameters are annotated as Any, we add the annotations to the
      # new frame's dictionary of local variable annotations, so that
      # vm._apply_annotation will treat these as explicit Any annotations that
      # disable inference.
      annotated_locals = {}
      for name, annot in annotations.items():
        if name != "return" and annot == self.ctx.convert.unsolvable:
          annotated_locals[name] = abstract_utils.Local(node,
                                                        self.get_first_opcode(),
                                                        annot,
                                                        callargs.get(name),
                                                        self.ctx)
      node2, ret = self.ctx.vm.run_frame(frame, node, annotated_locals)
      if self.is_coroutine():
        ret = Coroutine(self.ctx, ret, node2).to_variable(node2)
      node_after_call = node2
    self._inner_cls_check(frame)
    self._call_cache[callkey] = ret, self.ctx.vm.remaining_depth()
    if self._store_call_records or self.ctx.store_all_calls:
      self._call_records.append((callargs, ret, node_after_call))
    self.last_frame = frame
    return node_after_call, ret

  def get_call_combinations(self, node):
    """Get this function's call records."""
    all_combinations = []
    signature_data = set()
    for callargs, ret, node_after_call in self._call_records:
      try:
        combinations = cfg_utils.variable_product_dict(callargs)
      except cfg_utils.TooComplexError:
        combination = {
            name: self.ctx.convert.unsolvable.to_binding(node_after_call)
            for name in callargs
        }
        combinations = [combination]
        ret = self.ctx.new_unsolvable(node_after_call)
      for combination in combinations:
        for return_value in ret.bindings:
          values = list(combination.values()) + [return_value]
          data = tuple(v.data for v in values)
          if data in signature_data:
            # This combination yields a signature we already know is possible
            continue
          # Optimization: when only one combination exists, assume it's visible.
          if (len(combinations) == 1 and len(ret.bindings) == 1 or
              node_after_call.HasCombination(values)):
            signature_data.add(data)
            all_combinations.append(
                (node_after_call, combination, return_value))
    if not all_combinations:
      # Fallback: Generate signatures only from the definition of the
      # method, not the way it's being used.
      param_binding = self.ctx.convert.unsolvable.to_binding(node)
      params = collections.defaultdict(lambda: param_binding)
      ret = self.ctx.convert.unsolvable.to_binding(node)
      all_combinations.append((node, params, ret))
    return all_combinations

  def get_positional_names(self):
    return list(self.code.co_varnames[:self.code.co_argcount])

  def get_nondefault_params(self):
    for i in range(self.nonstararg_count):
      yield self.code.co_varnames[i], i >= self.code.co_argcount

  def get_kwonly_names(self):
    return list(
        self.code.co_varnames[self.code.co_argcount:self.nonstararg_count])

  def get_parameters(self):
    default_pos = self.code.co_argcount - len(self.defaults)
    i = 0
    for name in self.get_positional_names():
      yield name, False, i >= default_pos
      i += 1
    for name in self.get_kwonly_names():
      yield name, True, name in self.kw_defaults
      i += 1

  def has_varargs(self):
    return self.code.has_varargs()

  def has_kwargs(self):
    return self.code.has_varkeywords()

  def property_get(self, callself, is_class=False):
    if (abstract_utils.func_name_is_class_init(self.name) and
        self.signature.param_names):
      self_name = self.signature.param_names[0]
      # If `_has_self_annot` is True, then we've intentionally temporarily
      # annotated `self`; otherwise, a `self` annotation is illegal.
      if not self._has_self_annot and self_name in self.signature.annotations:
        self.ctx.errorlog.invalid_annotation(
            self.ctx.vm.simple_stack(self.get_first_opcode()),
            self.signature.annotations[self_name],
            details="Cannot annotate self argument of __init__",
            name=self_name)
        self.signature.del_annotation(self_name)
    return super().property_get(callself, is_class)

  def is_coroutine(self):
    return self.code.has_coroutine() or self.code.has_iterable_coroutine()

  def has_empty_body(self):
    # TODO(mdemello): Optimise this.
    ops = list(self.code.code_iter)
    if len(ops) != 2:
      # This check isn't strictly necessary but prevents us from wastefully
      # building a list of opcode names for a long method.
      return False
    if [op.name for op in ops] != ["LOAD_CONST", "RETURN_VALUE"]:
      return False
    return self.code.co_consts[ops[0].arg] is None


class SimpleFunction(SignedFunction):
  """An abstract value representing a function with a particular signature.

  Unlike InterpreterFunction, a SimpleFunction has a set signature and does not
  record calls or try to infer types.
  """

  def __init__(self, name, param_names, varargs_name, kwonly_params,
               kwargs_name, defaults, annotations, ctx):
    """Create a SimpleFunction.

    Args:
      name: Name of the function as a string
      param_names: Tuple of parameter names as strings.
      varargs_name: The "args" in "*args". String or None.
      kwonly_params: Tuple of keyword-only parameters as strings. These do NOT
        appear in param_names.
      kwargs_name: The "kwargs" in "**kwargs". String or None.
      defaults: Dictionary of string names to values of default arguments.
      annotations: Dictionary of string names to annotations (strings or types).
      ctx: The abstract context for this function.
    """
    annotations = dict(annotations)
    # Every parameter must have an annotation. Defaults to unsolvable.
    for n in itertools.chain(param_names, [varargs_name, kwargs_name],
                             kwonly_params):
      if n and n not in annotations:
        annotations[n] = ctx.convert.unsolvable
    if not isinstance(defaults, dict):
      defaults = dict(zip(param_names[-len(defaults):], defaults))
    signature = function.Signature(name, param_names, varargs_name,
                                   kwonly_params, kwargs_name, defaults,
                                   annotations)
    super().__init__(signature, ctx)
    self.bound_class = BoundFunction

  @classmethod
  def from_signature(cls, signature, ctx):
    """Create a SimpleFunction from a function.Signature."""
    return cls(
        name=signature.name,
        param_names=signature.param_names,
        varargs_name=signature.varargs_name,
        kwonly_params=signature.kwonly_params,
        kwargs_name=signature.kwargs_name,
        defaults=signature.defaults,
        annotations=signature.annotations,
        ctx=ctx)

  def call(self, node, _, args, alias_map=None):
    # We only simplify args for _map_args, because that simplifies checking.
    # This allows match_args to typecheck varargs and kwargs.
    callargs = self._map_args(node, args.simplify(node, self.ctx))
    substs = self.match_args(node, args, alias_map)
    # Substitute type parameters in the signature's annotations.
    annotations = self.ctx.annotation_utils.sub_annotations(
        node, self.signature.annotations, substs, instantiate_unbound=False)
    if self.signature.has_return_annotation:
      ret_type = annotations["return"]
      ret = ret_type.instantiate(node)
    else:
      ret = self.ctx.convert.none.to_variable(node)
    if self.name == "__new__":
      self_arg = ret
    else:
      self_arg = self.signature.get_first_arg(callargs)
    mutations = self._mutations_generator(node, self_arg, substs)
    node = abstract_utils.apply_mutations(node, mutations)
    return node, ret


class BoundFunction(BaseValue):
  """An function type which has had an argument bound into it."""

  def __init__(self, callself, underlying):
    super().__init__(underlying.name, underlying.ctx)
    self.cls = underlying.cls
    self._callself = callself
    self.underlying = underlying
    self.is_attribute_of_class = False
    self.is_class_builder = False

    # If the function belongs to `ParameterizedClass`, we will annotate the
    # `self` when do argument matching
    self.replace_self_annot = None
    inst = abstract_utils.get_atomic_value(
        self._callself, default=self.ctx.convert.unsolvable)
    if self._should_replace_self_annot():
      if (isinstance(inst.cls, class_mixin.Class) and
          inst.cls.full_name != "builtins.type"):
        for cls in inst.cls.mro:
          if isinstance(cls, ParameterizedClass):
            base_cls = cls.base_cls
          else:
            base_cls = cls
          if isinstance(base_cls, class_mixin.Class) and base_cls.template:
            self.replace_self_annot = (
                ParameterizedClass.get_generic_instance_type(base_cls))
            break
    if isinstance(inst, SimpleValue):
      self.alias_map = inst.instance_type_parameters.uf
    elif isinstance(inst, TypeParameterInstance):
      self.alias_map = inst.instance.instance_type_parameters.uf
    else:
      self.alias_map = None

  def _should_replace_self_annot(self):
    # To do argument matching for custom generic classes, the 'self' annotation
    # needs to be replaced with a generic type.
    f = self.underlying
    if not isinstance(f, SignedFunction) or not f.signature.param_names:
      # no 'self' to replace
      return False
    if isinstance(f, InterpreterFunction):
      # always replace for user-defined methods
      return True
    # SimpleFunctions are methods we construct internally for generated classes
    # like namedtuples.
    if not isinstance(f, SimpleFunction):
      return False
    # We don't want to clobber our own generic annotations.
    return (f.signature.param_names[0] not in f.signature.annotations or
            not f.signature.annotations[f.signature.param_names[0]].formal)

  def argcount(self, node):
    return self.underlying.argcount(node) - 1  # account for self

  @property
  def signature(self):
    return self.underlying.signature.drop_first_parameter()

  @property
  def callself(self):
    return self._callself

  def call(self, node, func, args, alias_map=None):
    if abstract_utils.func_name_is_class_init(self.name):
      self.ctx.callself_stack.append(self._callself)
    # The "self" parameter is automatically added to the list of arguments, but
    # only if the function actually takes any arguments.
    if self.argcount(node) >= 0:
      args = args.replace(posargs=(self._callself,) + args.posargs)
    try:
      if self.replace_self_annot:
        with self.underlying.set_self_annot(self.replace_self_annot):
          node, ret = self.underlying.call(node, func, args,
                                           alias_map=self.alias_map)
      else:
        node, ret = self.underlying.call(node, func, args,
                                         alias_map=self.alias_map)
    except function.InvalidParameters as e:
      if self._callself and self._callself.bindings:
        if "." in e.name:
          # match_args will try to prepend the parent's name to the error name.
          # Overwrite it with _callself instead, which may be more exact.
          _, _, e.name = e.name.rpartition(".")
        e.name = "%s.%s" % (self._callself.data[0].name, e.name)
      raise
    finally:
      if abstract_utils.func_name_is_class_init(self.name):
        self.ctx.callself_stack.pop()
    return node, ret

  def get_positional_names(self):
    return self.underlying.get_positional_names()

  def has_varargs(self):
    return self.underlying.has_varargs()

  def has_kwargs(self):
    return self.underlying.has_kwargs()

  @property
  def is_abstract(self):
    return self.underlying.is_abstract

  @is_abstract.setter
  def is_abstract(self, value):
    self.underlying.is_abstract = value

  @property
  def is_classmethod(self):
    return self.underlying.is_classmethod

  def repr_names(self, callself_repr=None):
    """Names to use in the bound function's string representation.

    This function can return multiple names because there may be multiple
    bindings in callself.

    Args:
      callself_repr: Optionally, a repr function for callself.

    Returns:
      A non-empty iterable of string names.
    """
    callself_repr = callself_repr or (lambda v: v.name)
    if self._callself and self._callself.bindings:
      callself_names = [callself_repr(v) for v in self._callself.data]
    else:
      callself_names = ["<class>"]
    # We don't need to recursively call repr_names() because we replace the
    # parent name with the callself.
    underlying = self.underlying.name
    if underlying.count(".") > 0:
      underlying = underlying.split(".", 1)[-1]
    return [callself + "." + underlying for callself in callself_names]

  def __repr__(self):
    return self.repr_names()[0] + "(...)"


class BoundInterpreterFunction(BoundFunction):
  """The method flavor of InterpreterFunction."""

  @contextlib.contextmanager
  def record_calls(self):
    with self.underlying.record_calls():
      yield

  def get_first_opcode(self):
    return self.underlying.code.first_opcode

  @property
  def has_overloads(self):
    return self.underlying.has_overloads

  @property
  def is_overload(self):
    return self.underlying.is_overload

  @is_overload.setter
  def is_overload(self, value):
    self.underlying.is_overload = value

  @property
  def defaults(self):
    return self.underlying.defaults

  def iter_signature_functions(self):
    for f in self.underlying.iter_signature_functions():
      yield self.underlying.bound_class(self._callself, f)


class BoundPyTDFunction(BoundFunction):
  pass


class Splat(BaseValue):
  """Representation of unpacked iterables."""

  def __init__(self, ctx, iterable):
    super().__init__("splat", ctx)
    # When building a tuple for a function call, we preserve splats as elements
    # in a concrete tuple (e.g. f(x, *ys, z) gets called with the concrete tuple
    # (x, *ys, z) in starargs) and let the arg matcher in function.py unpack
    # them. Constructing the tuple accesses its class as a side effect; ideally
    # we would specialise abstract.Tuple for function calls and not bother
    # constructing an associated TupleClass for a function call tuple, but for
    # now we just set the class to Any here.
    self.cls = ctx.convert.unsolvable
    self.iterable = iterable

  def __repr__(self):
    return "splat(%r)" % self.iterable.data


AMBIGUOUS = (Unknown, Unsolvable)
AMBIGUOUS_OR_EMPTY = AMBIGUOUS + (Empty,)
FUNCTION_TYPES = (BoundFunction, Function)
INTERPRETER_FUNCTION_TYPES = (BoundInterpreterFunction, InterpreterFunction)
PYTD_FUNCTION_TYPES = (BoundPyTDFunction, PyTDFunction)
