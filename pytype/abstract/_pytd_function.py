"""Abstract representation of a function loaded from a type stub."""

import collections
import itertools
import logging
from typing import Optional

from pytype.abstract import _base
from pytype.abstract import _classes
from pytype.abstract import _function_base
from pytype.abstract import _instance_base
from pytype.abstract import _singletons
from pytype.abstract import _typing
from pytype.abstract import abstract_utils
from pytype.abstract import function
from pytype.abstract import mixin
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors

log = logging.getLogger(__name__)
_isinstance = abstract_utils._isinstance  # pylint: disable=protected-access


def _is_literal(annot: Optional[_base.BaseValue]):
  if isinstance(annot, _typing.Union):
    return all(_is_literal(o) for o in annot.options)
  return isinstance(annot, _classes.LiteralClass)


class PyTDFunction(_function_base.Function):
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
    self.bound_class = _function_base.BoundPyTDFunction
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
      return _function_base.StaticMethod(self.name, self, callself, self.ctx)
    elif self.kind == pytd.MethodTypes.CLASSMETHOD:
      if not is_class:
        callself = abstract_utils.get_atomic_value(
            callself, default=self.ctx.convert.unsolvable)
        if isinstance(callself, _typing.TypeParameterInstance):
          callself = abstract_utils.get_atomic_value(
              callself.instance.get_instance_type_parameter(callself.name),
              default=self.ctx.convert.unsolvable)
        # callself is the instance, and we want to bind to its class.
        callself = callself.cls.to_variable(self.ctx.root_node)
      return _function_base.ClassMethod(self.name, self, callself, self.ctx)
    elif self.kind == pytd.MethodTypes.PROPERTY and not is_class:
      return _function_base.Property(self.name, self, callself, self.ctx)
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
      # - An annotation has a type param that is not ambiguous or empty
      # - The mutation adds a type that is not ambiguous or empty
      def should_check(value):
        return not _isinstance(value, "AMBIGUOUS_OR_EMPTY")

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
      if isinstance(v, _instance_base.SimpleValue):
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
    if any(_isinstance(view[arg].data, "AMBIGUOUS_OR_EMPTY")
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
      if isinstance(view[arg].data, _singletons.Unknown):
        for sig, _, _ in signatures:
          if (len(sig.param_types) > i and
              isinstance(sig.param_types[i], _typing.TypeParameter)):
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
      if any(not _is_literal(sig.signature.annotations.get(name))
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
              _is_literal(sig.signature.annotations.get(name))):
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
