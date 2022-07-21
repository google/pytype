"""Base abstract representations of functions."""

import contextlib
import inspect
import logging
from typing import Type

from pytype import utils
from pytype.abstract import _base
from pytype.abstract import _classes
from pytype.abstract import _instance_base
from pytype.abstract import _instances
from pytype.abstract import _singletons
from pytype.abstract import _typing
from pytype.abstract import abstract_utils
from pytype.abstract import function

log = logging.getLogger(__name__)
_isinstance = abstract_utils._isinstance  # pylint: disable=protected-access


class Function(_instance_base.SimpleValue):
  """Base class for function objects (NativeFunction, InterpreterFunction).

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    ctx: context.Context instance.
  """

  bound_class: Type["BoundFunction"]

  def __init__(self, name, ctx):
    super().__init__(name, ctx)
    self.cls = _classes.FunctionPyTDClass(self, ctx)
    self.is_attribute_of_class = False
    self.is_classmethod = False
    self.is_abstract = False
    self.is_method = "." in name
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
    # The implementation of match_args is currently rather convoluted because we
    # have two different implementations:
    # * Old implementation: `_match_views` matches 'args' against 'self' one
    #   view at a time, where a view is a mapping of every variable in args to a
    #   particular binding. This handles generics but scales poorly with the
    #   number of bindings per variable.
    # * New implementation: `_match_args_sequentially` matches 'args' one at a
    #   time. This scales better but cannot yet handle generics.
    # Subclasses should implement the following:
    # * _match_view(node, args, view, alias_map): this will be called repeatedly
    #   by _match_views.
    # * _match_args_sequentially(node, args, alias_map, match_all_views): A
    #   sequential matching implementation.
    # TODO(b/228241343): Get rid of _match_views and simplify match_args once
    # _match_args_sequentially can handle generics.
    if self._is_generic_call(args):
      return self._match_views(node, args, alias_map, match_all_views)
    return self._match_args_sequentially(node, args, alias_map, match_all_views)

  def _is_generic_call(self, args):
    for sig in function.get_signatures(self):
      for t in sig.annotations.values():
        stack = [t]
        seen = set()
        while stack:
          cur = stack.pop()
          if cur in seen:
            continue
          seen.add(cur)
          if cur.formal or cur.template:
            return True
          if _isinstance(cur, "Union"):
            stack.extend(cur.options)
    if self.is_attribute_of_class and args.posargs:
      for self_val in args.posargs[0].data:
        for cls in self_val.cls.mro:
          if cls.template:
            return True
    return False

  def _match_views(self, node, args, alias_map, match_all_views):
    """Matches all views of the given args against this function."""
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
        if not node.HasCombination(list(view.values())) or e <= error:
          # This error was ignored, but future ones with the same accessed
          # subset may need to be recorded, so we can't skip them.
          skip_future = False
        else:
          # Add the name of the caller if possible.
          if hasattr(self, "parent"):
            e.name = f"{self.parent.name}.{e.name}"
          if match_all_views or self.ctx.options.strict_parameter_checks:
            raise e
          error = e
          skip_future = True
      else:
        matched.append(match)
        skip_future = True
    if not matched and error:
      raise error  # pylint: disable=raising-bad-type
    return matched

  def _match_view(self, node, args, view, alias_map):
    raise NotImplementedError(self.__class__.__name__)

  def _match_args_sequentially(self, node, args, alias_map, match_all_views):
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
    if all(isinstance(d, _instances.Tuple) for d in defaults_var.data):
      return max((d.pyval for d in defaults_var.data), key=len)
    else:
      # Case 2: Data are entirely Tuple Instances, Unknown or Unsolvable. Make
      # all parameters except self/cls optional.
      # Case 3: Data is anything else. Same as Case 2, but emit a warning.
      if not (all(isinstance(d, (
          _instance_base.Instance, _singletons.Unknown, _singletons.Unsolvable))
                  for d in defaults_var.data) and
              all(d.full_name == "builtins.tuple"
                  for d in defaults_var.data
                  if isinstance(d, _instance_base.Instance))):
        self.ctx.errorlog.bad_function_defaults(self.ctx.vm.frames, self.name)
      # The ambiguous case is handled by the subclass.
      return None

  def set_function_defaults(self, node, defaults_var):
    raise NotImplementedError(self.__class__.__name__)


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
    if isinstance(self.func.__self__, _classes.CallableClass):
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
            self.name, argnames, 0, None, set(), None, {}, {}, {})
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


class BoundFunction(_base.BaseValue):
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
    if self.underlying.should_replace_self_annot():
      self.replace_self_annot = abstract_utils.get_generic_type(inst)
    if isinstance(inst, _instance_base.SimpleValue):
      self.alias_map = inst.instance_type_parameters.uf
    elif isinstance(inst, _typing.TypeParameterInstance):
      self.alias_map = inst.instance.instance_type_parameters.uf
    else:
      self.alias_map = None

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
        e.name = f"{self._callself.data[0].name}.{e.name}"
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


class ClassMethod(_base.BaseValue):
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


class StaticMethod(_base.BaseValue):
  """Implements @staticmethod methods in pyi."""

  def __init__(self, name, method, _, ctx):
    super().__init__(name, ctx)
    self.cls = self.ctx.convert.function_type
    self.method = method
    self.signatures = self.method.signatures

  def call(self, *args, **kwargs):
    return self.method.call(*args, **kwargs)


class Property(_base.BaseValue):
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


class Splat(_base.BaseValue):
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
    return f"splat({self.iterable.data!r})"
