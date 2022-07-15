"""Abstract representation of functions defined in the module under analysis."""

import collections
import contextlib
import hashlib
import itertools
import logging

from pytype.abstract import _classes
from pytype.abstract import _function_base
from pytype.abstract import _instance_base
from pytype.abstract import _instances
from pytype.abstract import _singletons
from pytype.abstract import _typing
from pytype.abstract import abstract_utils
from pytype.abstract import class_mixin
from pytype.abstract import function
from pytype.pytd import pytd
from pytype.typegraph import cfg_utils

log = logging.getLogger(__name__)
_isinstance = abstract_utils._isinstance  # pylint: disable=protected-access


def _matches_generator_helper(type_obj, allowed_types):
  """Check if type_obj matches a Generator/AsyncGenerator type."""
  if isinstance(type_obj, _typing.Union):
    return all(_matches_generator_helper(sub_type, allowed_types)
               for sub_type in type_obj.options)
  else:
    base_cls = type_obj
    if isinstance(type_obj, _classes.ParameterizedClass):
      base_cls = type_obj.base_cls
    return ((isinstance(base_cls, _classes.PyTDClass) and
             base_cls.name in allowed_types) or
            _isinstance(base_cls, "AMBIGUOUS_OR_EMPTY"))


def _matches_generator(type_obj):
  allowed_types = ("generator", "Iterable", "Iterator")
  return _matches_generator_helper(type_obj, allowed_types)


def _matches_async_generator(type_obj):
  allowed_types = ("asyncgenerator", "AsyncIterable", "AsyncIterator")
  return _matches_generator_helper(type_obj, allowed_types)


def _hash_dict(vardict, names):
  """Hash a dictionary.

  This contains the keys and the full hashes of the data in the values.

  Arguments:
    vardict: A dictionary mapping str to Variable.
    names: If this is non-None, the snapshot will include only those
      dictionary entries whose keys appear in names.

  Returns:
    A hash of the dictionary.
  """
  if names is not None:
    vardict = {name: vardict[name] for name in names.intersection(vardict)}
  m = hashlib.md5()
  for name, var in sorted(vardict.items()):
    m.update(str(name).encode("utf-8"))
    for value in var.bindings:
      m.update(value.data.get_fullhash())
  return m.digest()


def _hash_all_dicts(*hash_args):
  """Convenience method for hashing a sequence of dicts."""
  return hashlib.md5(b"".join(_hash_dict(*args) for args in hash_args)).digest()


def _check_classes(var, check):
  """Check whether the cls of each value in `var` is a class and passes `check`.

  Args:
    var: A cfg.Variable or empty.
    check: (BaseValue) -> bool.

  Returns:
    Whether the check passes.
  """
  if not var:
    return False
  for v in var.data:
    if isinstance(v, class_mixin.Class):
      if not check(v):
        return False
    elif isinstance(v.cls, class_mixin.Class) and v.cls != v:
      if not check(v.cls):
        return False
  return True


class SignedFunction(_function_base.Function):
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
    posonly_names = set(sig.posonly_params)
    for key in set(positional) - posonly_names:
      if key in kws:
        raise function.DuplicateKeyword(sig, args, self.ctx, key)
    kwnames = set(kws)
    extra_kws = kwnames.difference(sig.param_names + sig.kwonly_params)
    if extra_kws and not sig.kwargs_name:
      if function.has_visible_namedarg(node, args, extra_kws):
        raise function.WrongKeywordArgs(sig, args, self.ctx, extra_kws)
    posonly_kws = kwnames & posonly_names
    # If a function has a **kwargs parameter, then keyword arguments with the
    # same name as a positional-only argument are allowed, e.g.:
    #   def f(x, /, **kwargs): ...
    #   f(0, x=1)  # ok
    if posonly_kws and not sig.kwargs_name:
      raise function.WrongKeywordArgs(sig, args, self.ctx, posonly_kws)
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
        k = _instances.Dict(self.ctx)
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

  def _match_args_sequentially(self, node, args, alias_map, match_all_views):
    for name, arg, formal in self.signature.iter_args(args):
      if formal is None:
        continue
      if name in (self.signature.varargs_name, self.signature.kwargs_name):
        # The annotation is Tuple or Dict, but the passed arg only has to be
        # Iterable or Mapping.
        formal = self.ctx.convert.widen_type(formal)
      match_result = self.ctx.matcher(node).bad_matches(arg, formal)
      if not function.match_succeeded(match_result, match_all_views, self.ctx):
        bad_arg = function.BadParam(
            name=name, expected=formal, error_details=match_result[0][0][1])
        raise function.WrongArgTypes(
            self.signature, args, self.ctx, bad_param=bad_arg)
    return [{}]

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
        inst = abstract_utils.get_atomic_value(
            first_arg, _instance_base.Instance)
      except abstract_utils.ConversionError:
        return
      if inst.cls.template:
        for subst in substs:
          for k, v in subst.items():
            if k in inst.instance_type_parameters:
              value = inst.instance_type_parameters[k].AssignToNewVariable(node)
              if all(isinstance(val, _singletons.Unknown) for val in v.data):
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


class SimpleFunction(SignedFunction):
  """An abstract value representing a function with a particular signature.

  Unlike InterpreterFunction, a SimpleFunction has a set signature and does not
  record calls or try to infer types.
  """

  def __init__(self, signature, ctx):
    super().__init__(signature, ctx)
    self.bound_class = _function_base.BoundFunction

  @classmethod
  def build(cls, name, param_names, posonly_count, varargs_name, kwonly_params,
            kwargs_name, defaults, annotations, ctx):
    """Returns a SimpleFunction.

    Args:
      name: Name of the function as a string
      param_names: Tuple of parameter names as strings. This DOES include
        positional-only parameters and does NOT include keyword-only parameters.
      posonly_count: Number of positional-only parameters.
      varargs_name: The "args" in "*args". String or None.
      kwonly_params: Tuple of keyword-only parameters as strings.
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
    signature = function.Signature(name, param_names, posonly_count,
                                   varargs_name, kwonly_params, kwargs_name,
                                   defaults, annotations)
    return cls(signature, ctx)

  def call(self, node, _, args, alias_map=None):
    args = args.simplify(node, self.ctx)
    callargs = self._map_args(node, args)
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
  def make(cls, name, *, def_opcode, code, f_locals, f_globals, defaults,
           kw_defaults, closure, annotations, ctx):
    """Get an InterpreterFunction.

    Things like anonymous functions and generator expressions are created
    every time the corresponding code executes. Caching them makes it easier
    to detect when the environment hasn't changed and a function call can be
    optimized away.

    Arguments:
      name: Function name.
      def_opcode: The opcode for the def statement
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
        if not _matches_generator(ret_type):
          ctx.errorlog.bad_yield_annotation(
              ctx.vm.frames, name, ret_type, is_async=False)
      elif code.has_async_generator():
        if not _matches_async_generator(ret_type):
          ctx.errorlog.bad_yield_annotation(
              ctx.vm.frames, name, ret_type, is_async=True)
    overloads = ctx.vm.frame.overloads[name]
    key = (name, code,
           _hash_all_dicts(
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
      cls._function_cache[key] = cls(name, def_opcode, code, f_locals,
                                     f_globals, defaults, kw_defaults, closure,
                                     annotations,
                                     overloads, ctx)
    elif closure:
      # Reusing the old closure variables would lead to the closure containing
      # future values, such as Deleted.
      cls._function_cache[key].closure = closure
    return cls._function_cache[key]

  def __init__(self, name, def_opcode, code, f_locals, f_globals, defaults,
               kw_defaults, closure, annotations, overloads, ctx):
    log.debug("Creating InterpreterFunction %r for %r", name, code.co_name)
    self.bound_class = _function_base.BoundInterpreterFunction
    self.doc = code.co_consts[0] if code.co_consts else None
    self.def_opcode = def_opcode
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
    self.posonlyarg_count = max(self.code.co_posonlyargcount, 0)
    self.nonstararg_count = self.code.co_argcount
    if self.code.co_kwonlyargcount >= 0:  # This is usually -1 or 0 (fast call)
      self.nonstararg_count += self.code.co_kwonlyargcount
    signature = self._build_signature(name, annotations)
    super().__init__(signature, ctx)
    self._check_annotations(name, annotations)
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

  def _check_annotations(self, name, annotations):
    """Validate function annotations."""
    for ann in annotations.values():
      if isinstance(ann, _typing.FinalAnnotation):
        self.ctx.errorlog.invalid_final_type(
            self.ctx.vm.simple_stack(self.def_opcode))

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
        self.posonlyarg_count,
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
      instance = abstract_utils.get_atomic_value(
          maybe_instance, _instance_base.Instance)
    except abstract_utils.ConversionError:
      return
    if isinstance(instance.cls, _classes.InterpreterClass):
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
        if (isinstance(value, _classes.InterpreterClass) and value.template and
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
    if not (isinstance(func.data, _function_base.BoundInterpreterFunction) and
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

  def call(self, node, func, args, alias_map=None, new_locals=False,
           frame_substs=()):
    if self.is_overload:
      raise function.NotCallable(self)
    if (self.ctx.vm.is_at_maximum_depth() and
        not abstract_utils.func_name_is_class_init(self.name)):
      log.info("Maximum depth reached. Not analyzing %r", self.name)
      self._set_callself_maybe_missing_members()
      if self.signature.annotations.get("return") == self.ctx.convert.no_return:
        # TODO(b/147230757): Use all return annotations, not just NoReturn.
        ret = self.signature.annotations["return"]
      else:
        ret = self.ctx.convert.unsolvable
      return node, ret.to_variable(node)
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
          if (isinstance(cls, _classes.InterpreterClass) or
              isinstance(cls, _classes.ParameterizedClass) and
              isinstance(cls.base_cls, _classes.InterpreterClass)):
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
    caller_is_abstract = _check_classes(first_arg, lambda cls: cls.is_abstract)
    caller_is_protocol = _check_classes(first_arg, lambda cls: cls.is_protocol)
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
      callkey = _hash_all_dicts(
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
      generator = _instances.Generator(frame, self.ctx)
      # Run the generator right now, even though the program didn't call it,
      # because we need to know the contained type for further matching.
      node2, _ = generator.run_generator(node)
      if self.is_coroutine():
        # This function is a generator-based coroutine. We convert the return
        # value here even though byte_GET_AWAITABLE repeats the conversion so
        # that matching against a typing.Awaitable annotation succeeds.
        var = generator.get_instance_type_parameter(abstract_utils.V)
        ret = _instances.Coroutine(self.ctx, var, node2).to_variable(node2)
      else:
        ret = generator.to_variable(node2)
      node_after_call = node2
    elif self.code.has_async_generator():
      async_generator = _instances.AsyncGenerator(frame, self.ctx)
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
        ret = _instances.Coroutine(self.ctx, ret, node2).to_variable(node2)
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
      if i < self.posonlyarg_count:
        kind = pytd.ParameterKind.POSONLY
      else:
        kind = pytd.ParameterKind.REGULAR
      yield name, kind, i >= default_pos
      i += 1
    for name in self.get_kwonly_names():
      yield name, pytd.ParameterKind.KWONLY, name in self.kw_defaults
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
