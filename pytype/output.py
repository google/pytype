"""Tools for output generation."""

import collections
import contextlib
import logging

from pytype import abstract
from pytype import abstract_utils
from pytype import mixin
from pytype import special_builtins
from pytype import utils
from pytype.overlays import typing_overlay
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors
from six import moves

log = logging.getLogger(__name__)

TOP_LEVEL_IGNORE = {
    "__builtins__",
    "__doc__",
    "__file__",
    "__future__",
    "__module__",
    "__name__",
    "__annotations__",
    "google_type_annotations",
}

CLASS_LEVEL_IGNORE = {
    "__builtins__",
    "__class__",
    "__module__",
    "__name__",
    "__qualname__",
    "__slots__",
    "__annotations__",
}


class Converter(utils.VirtualMachineWeakrefMixin):
  """Functions for converting abstract classes into PyTD."""

  def __init__(self, vm):
    super(Converter, self).__init__(vm)
    self._detailed = False

  @contextlib.contextmanager
  def produce_detailed_output(self):
    """Produce more detailed pytd types, which may be unsafe for pyi files.

    With this setting, the converter will do things like using the names of
    inner classes rather than Any and including the known argument types for a
    callable even if the argument count is unknown. Useful for error messages.

    Yields:
      None.
    """
    old = self._detailed
    self._detailed = True
    yield
    self._detailed = old

  def _get_values(self, node, var, view):
    if var.bindings and view is not None:
      return [view[var].data]
    elif node:
      return var.FilteredData(node, strict=False)
    else:
      return var.data

  def _is_tuple(self, v, instance):
    return (isinstance(v, abstract.TupleClass) or
            isinstance(instance, abstract.Tuple))

  def _value_to_parameter_types(self, node, v, instance, template, seen, view):
    """Get PyTD types for the parameters of an instance of an abstract value."""
    if isinstance(v, abstract.CallableClass):
      assert template == (abstract_utils.ARGS, abstract_utils.RET), template
      template = list(moves.range(v.num_args)) + [template[1]]
    if self._is_tuple(v, instance):
      if isinstance(v, abstract.TupleClass):
        new_template = range(v.tuple_length)
      else:
        new_template = range(instance.tuple_length)
      if template:
        assert len(template) == 1 and template[0] == abstract_utils.T, template
      else:
        # We have a recursive type. By erasing the instance and value
        # information, we'll return Any for all of the tuple elements.
        v = instance = None
      template = new_template
    if instance is None and isinstance(v, abstract.ParameterizedClass):
      return [self.value_instance_to_pytd_type(
          node, v.get_formal_type_parameter(t), None, seen, view)
              for t in template]
    elif isinstance(instance, abstract.SimpleAbstractValue):
      type_arguments = []
      for t in template:
        if isinstance(instance, abstract.Tuple):
          param_values = self._get_values(node, instance.pyval[t], view)
        elif instance.has_instance_type_parameter(t):
          param_values = self._get_values(
              node, instance.get_instance_type_parameter(t), view)
        elif isinstance(v, abstract.CallableClass):
          param_values = v.get_formal_type_parameter(t).instantiate(
              node or self.vm.root_cfg_node).data
        else:
          param_values = [self.vm.convert.unsolvable]
        if (param_values == [self.vm.convert.unsolvable] and
            isinstance(v, abstract.ParameterizedClass) and
            not v.get_formal_type_parameter(t).formal):
          # When the instance's parameter value is unsolvable, we can get a
          # more precise type from the class. Note that we need to be careful
          # not to introduce unbound type parameters.
          arg = self.value_instance_to_pytd_type(
              node, v.get_formal_type_parameter(t), None, seen, view)
        else:
          arg = pytd_utils.JoinTypes(self.value_to_pytd_type(
              node, p, seen, view) for p in param_values)
        type_arguments.append(arg)
      return type_arguments
    else:
      return [pytd.AnythingType() for _ in template]

  def value_instance_to_pytd_type(self, node, v, instance, seen, view):
    """Get the PyTD type an instance of this object would have.

    Args:
      node: The node.
      v: The object.
      instance: The instance.
      seen: Already seen instances.
      view: A Variable -> binding map.

    Returns:
      A PyTD type.
    """
    if isinstance(v, abstract.Union):
      return pytd.UnionType(tuple(
          self.value_instance_to_pytd_type(node, t, instance, seen, view)
          for t in v.options))
    elif isinstance(v, abstract.AnnotationContainer):
      return self.value_instance_to_pytd_type(
          node, v.base_cls, instance, seen, view)
    elif isinstance(v, mixin.Class):
      if not self._detailed and v.official_name is None:
        return pytd.AnythingType()
      if seen is None:
        # We make the set immutable to ensure that the seen instances for
        # different parameter values don't interfere with one another.
        seen = frozenset()
      if instance in seen:
        # We have a circular dependency in our types (e.g., lst[0] == lst). Stop
        # descending into the type parameters.
        type_params = ()
      else:
        type_params = tuple(t.name for t in v.template)
      if instance is not None:
        seen |= {instance}
      type_arguments = self._value_to_parameter_types(
          node, v, instance, type_params, seen, view)
      base = pytd_utils.NamedTypeWithModule(v.official_name or v.name, v.module)
      if self._is_tuple(v, instance):
        if type_arguments:
          homogeneous = False
        else:
          homogeneous = True
          type_arguments = [pytd.NothingType()]
      elif v.full_name == "typing.Callable":
        homogeneous = not isinstance(v, abstract.CallableClass)
      else:
        homogeneous = len(type_arguments) == 1
      return pytd_utils.MakeClassOrContainerType(
          base, type_arguments, homogeneous)
    elif isinstance(v, abstract.TypeParameter):
      # We generate the full definition because, if this type parameter is
      # imported, we will need the definition in order to declare it later.
      return self._typeparam_to_def(node, v, v.name)
    elif isinstance(v, typing_overlay.NoReturn):
      return pytd.NothingType()
    else:
      log.info("Using ? for instance of %s", v.name)
      return pytd.AnythingType()

  def value_to_pytd_type(self, node, v, seen, view):
    """Get a PyTD type representing this object, as seen at a node.

    Args:
      node: The node from which we want to observe this object.
      v: The object.
      seen: The set of values seen before while computing the type.
      view: A Variable -> binding map.

    Returns:
      A PyTD type.
    """
    if isinstance(v, (abstract.Empty, typing_overlay.NoReturn)):
      return pytd.NothingType()
    elif isinstance(v, abstract.TypeParameterInstance):
      if v.instance.get_instance_type_parameter(v.full_name).bindings:
        # The type parameter was initialized. Set the view to None, since we
        # don't include v.instance in the view.
        return pytd_utils.JoinTypes(
            self.value_to_pytd_type(node, p, seen, None)
            for p in v.instance.get_instance_type_parameter(v.full_name).data)
      elif v.param.constraints:
        return pytd_utils.JoinTypes(
            self.value_instance_to_pytd_type(node, p, None, seen, view)
            for p in v.param.constraints)
      elif v.param.bound:
        return self.value_instance_to_pytd_type(
            node, v.param.bound, None, seen, view)
      else:
        return pytd.AnythingType()
    elif isinstance(v, typing_overlay.TypeVar):
      return pytd.NamedType("__builtin__.type")
    elif isinstance(v, abstract.FUNCTION_TYPES):
      try:
        signatures = abstract_utils.get_signatures(v)
      except NotImplementedError:
        return pytd.NamedType("typing.Callable")
      if len(signatures) == 1:
        val = self.signature_to_callable(signatures[0])
        if not isinstance(v, abstract.PYTD_FUNCTION_TYPES) or not val.formal:
          # This is a workaround to make sure we don't put unexpected type
          # parameters in call traces.
          return self.value_instance_to_pytd_type(node, val, None, seen, view)
      return pytd.NamedType("typing.Callable")
    elif isinstance(v, (abstract.ClassMethod, abstract.StaticMethod)):
      return self.value_to_pytd_type(node, v.method, seen, view)
    elif isinstance(v, (special_builtins.IsInstance,
                        special_builtins.ClassMethodCallable)):
      return pytd.NamedType("typing.Callable")
    elif isinstance(v, mixin.Class):
      param = self.value_instance_to_pytd_type(node, v, None, seen, view)
      return pytd.GenericType(base_type=pytd.NamedType("__builtin__.type"),
                              parameters=(param,))
    elif isinstance(v, abstract.Module):
      return pytd.NamedType("__builtin__.module")
    elif isinstance(v, abstract.SimpleAbstractValue):
      if v.cls:
        ret = self.value_instance_to_pytd_type(
            node, v.cls, v, seen=seen, view=view)
        ret.Visit(visitors.FillInLocalPointers(
            {"__builtin__": self.vm.loader.builtins}))
        return ret
      else:
        # We don't know this type's __class__, so return AnythingType to
        # indicate that we don't know anything about what this is.
        # This happens e.g. for locals / globals, which are returned from the
        # code in class declarations.
        log.info("Using ? for %s", v.name)
        return pytd.AnythingType()
    elif isinstance(v, abstract.Union):
      return pytd.UnionType(tuple(self.value_to_pytd_type(node, o, seen, view)
                                  for o in v.options))
    elif isinstance(v, special_builtins.SuperInstance):
      return pytd.NamedType("__builtin__.super")
    elif isinstance(v, abstract.TypeParameter):
      # Arguably, the type of a type parameter is NamedType("typing.TypeVar"),
      # but pytype doesn't know how to handle that, so let's just go with Any
      # unless self._detailed is set.
      if self._detailed:
        return pytd.NamedType("typing.TypeVar")
      else:
        return pytd.AnythingType()
    elif isinstance(v, abstract.Unsolvable):
      return pytd.AnythingType()
    elif isinstance(v, abstract.Unknown):
      return pytd.NamedType(v.class_name)
    elif isinstance(v, abstract.BuildClass):
      return pytd.NamedType("typing.Callable")
    else:
      raise NotImplementedError(v.__class__.__name__)

  def signature_to_callable(self, sig):
    """Converts a function.Signature object into a callable object.

    Args:
      sig: The signature to convert.

    Returns:
      An abstract.CallableClass representing the signature, or an
      abstract.ParameterizedClass if the signature has a variable number of
      arguments.
    """
    base_cls = self.vm.convert.function_type
    ret = sig.annotations.get("return", self.vm.convert.unsolvable)
    if self._detailed or (
        sig.mandatory_param_count() == sig.maximum_param_count()):
      # If self._detailed is false, we throw away the argument types if the
      # function takes a variable number of arguments, which is correct for pyi
      # generation but undesirable for, say, error message printing.
      args = [sig.annotations.get(name, self.vm.convert.unsolvable)
              for name in sig.param_names]
      params = {abstract_utils.ARGS: self.vm.merge_values(args),
                abstract_utils.RET: ret}
      params.update(enumerate(args))
      return abstract.CallableClass(base_cls, params, self.vm)
    else:
      # The only way to indicate a variable number of arguments in a Callable
      # is to not specify argument types at all.
      params = {abstract_utils.ARGS: self.vm.convert.unsolvable,
                abstract_utils.RET: ret}
      return abstract.ParameterizedClass(base_cls, params, self.vm)

  def value_to_pytd_def(self, node, v, name):
    """Get a PyTD definition for this object.

    Args:
      node: The node.
      v: The object.
      name: The object name.

    Returns:
      A PyTD definition.
    """
    if isinstance(v, abstract.BoundFunction):
      d = self.value_to_pytd_def(node, v.underlying, name)
      assert isinstance(d, pytd.Function)
      sigs = tuple(sig.Replace(params=sig.params[1:]) for sig in d.signatures)
      return d.Replace(signatures=sigs)
    elif (isinstance(v, abstract.PyTDFunction) and
          not isinstance(v, typing_overlay.TypeVar)):
      return pytd.Function(
          name=name,
          signatures=tuple(sig.pytd_sig for sig in v.signatures),
          kind=v.kind,
          flags=pytd.Function.abstract_flag(v.is_abstract))
    elif isinstance(v, abstract.InterpreterFunction):
      return self._function_to_def(node, v, name)
    elif isinstance(v, abstract.SimpleFunction):
      return self._simple_func_to_def(node, v, name)
    elif isinstance(v, abstract.ParameterizedClass):
      return pytd.Alias(name, v.get_instance_type(node))
    elif isinstance(v, abstract.PyTDClass) and v.module:
      # This happens if a module does e.g. "from x import y as z", i.e., copies
      # something from another module to the local namespace. We *could*
      # reproduce the entire class, but we choose a more dense representation.
      return v.to_type(node)
    elif isinstance(v, abstract.PyTDClass):  # a namedtuple instance
      assert name != v.name
      return pytd.Alias(name, pytd.NamedType(v.name))
    elif isinstance(v, abstract.InterpreterClass):
      if v.official_name is None or name == v.official_name:
        return self._class_to_def(node, v, name)
      else:
        return pytd.Alias(name, pytd.NamedType(v.official_name))
    elif isinstance(v, abstract.TypeParameter):
      return self._typeparam_to_def(node, v, name)
    elif isinstance(v, abstract.Unsolvable):
      return pytd.Constant(name, v.to_type(node))
    else:
      raise NotImplementedError(v.__class__.__name__)

  def annotations_to_instance_types(self, node, annots):
    """Get instance types for annotations not present in the members map."""
    if annots:
      for name, typ in annots.get_annotations(node):
        contained_type = abstract_utils.match_type_container(
            typ, "typing.ClassVar")
        if contained_type:
          typ = contained_type
        yield name, typ.get_instance_type(node)

  def _function_call_to_return_type(self, node, v, seen_return, num_returns):
    """Get a function call's pytd return type."""
    if v.signature.has_return_annotation:
      if v.is_coroutine():
        ret = abstract.Coroutine.make(self.vm, v, node).to_type(node)
      else:
        ret = v.signature.annotations["return"].get_instance_type(node)
    else:
      ret = seen_return.data.to_type(node)
      if isinstance(ret, pytd.NothingType) and num_returns == 1:
        if isinstance(seen_return.data, abstract.Empty):
          ret = pytd.AnythingType()
        else:
          assert isinstance(seen_return.data, typing_overlay.NoReturn)
    return ret

  def _function_call_combination_to_signature(
      self, func, call_combination, num_combinations):
    node_after, combination, return_value = call_combination
    params = []
    for i, (name, kwonly, optional) in enumerate(func.get_parameters()):
      if i < func.nonstararg_count and name in func.signature.annotations:
        t = func.signature.annotations[name].get_instance_type(node_after)
      else:
        t = combination[name].data.to_type(node_after)
      # Python uses ".0" etc. for the names of parameters that are tuples,
      # like e.g. in: "def f((x,  y), z)".
      params.append(
          pytd.Parameter(name.replace(".", "_"), t, kwonly, optional, None))
    ret = self._function_call_to_return_type(
        node_after, func, return_value, num_combinations)
    if func.has_varargs():
      if func.signature.varargs_name in func.signature.annotations:
        annot = func.signature.annotations[func.signature.varargs_name]
        typ = annot.get_instance_type(node_after)
      else:
        typ = pytd.NamedType("__builtin__.tuple")
      starargs = pytd.Parameter(
          func.signature.varargs_name, typ, False, True, None)
    else:
      starargs = None
    if func.has_kwargs():
      if func.signature.kwargs_name in func.signature.annotations:
        annot = func.signature.annotations[func.signature.kwargs_name]
        typ = annot.get_instance_type(node_after)
      else:
        typ = pytd.NamedType("__builtin__.dict")
      starstarargs = pytd.Parameter(
          func.signature.kwargs_name, typ, False, True, None)
    else:
      starstarargs = None
    return pytd.Signature(
        params=tuple(params),
        starargs=starargs,
        starstarargs=starstarargs,
        return_type=ret,
        exceptions=(),  # TODO(kramm): record exceptions
        template=())

  def _function_to_def(self, node, v, function_name):
    """Convert an InterpreterFunction to a PyTD definition."""
    signatures = []
    for func in v.signature_functions():
      combinations = func.get_call_combinations(node)
      num_combinations = len(combinations)
      signatures.extend(
          self._function_call_combination_to_signature(
              func, combination, num_combinations)
          for combination in combinations)
    return pytd.Function(name=function_name,
                         signatures=tuple(signatures),
                         kind=pytd.METHOD,
                         flags=pytd.Function.abstract_flag(v.is_abstract))

  def _simple_func_to_def(self, node, v, name):
    """Convert a SimpleFunction to a PyTD definition."""
    sig = v.signature
    def get_parameter(p, kwonly):
      return pytd.Parameter(p, sig.annotations[p].get_instance_type(node),
                            kwonly, p in sig.defaults, None)
    params = [get_parameter(p, False) for p in sig.param_names]
    kwonly = [get_parameter(p, True) for p in sig.kwonly_params]
    if sig.varargs_name:
      star = pytd.Parameter(
          sig.varargs_name,
          sig.annotations[sig.varargs_name].get_instance_type(node),
          False, False, None)
    else:
      star = None
    if sig.kwargs_name:
      starstar = pytd.Parameter(
          sig.kwargs_name,
          sig.annotations[sig.kwargs_name].get_instance_type(node),
          False, False, None)
    else:
      starstar = None
    if sig.has_return_annotation:
      ret_type = sig.annotations["return"].get_instance_type(node)
    else:
      ret_type = pytd.NamedType("__builtin__.NoneType")
    pytd_sig = pytd.Signature(
        params=tuple(params+kwonly),
        starargs=star,
        starstarargs=starstar,
        return_type=ret_type,
        exceptions=(),
        template=())
    return pytd.Function(name, (pytd_sig,), pytd.METHOD)

  def _function_to_return_types(self, node, fvar):
    """Convert a function variable to a list of PyTD return types."""
    options = fvar.FilteredData(self.vm.exitpoint, strict=False)
    if not all(isinstance(o, abstract.Function) for o in options):
      return [pytd.AnythingType()]
    types = []
    for val in options:
      if isinstance(val, abstract.InterpreterFunction):
        combinations = val.get_call_combinations(node)
        for node_after, _, return_value in combinations:
          types.append(self._function_call_to_return_type(
              node_after, val, return_value, len(combinations)))
      elif isinstance(val, abstract.PyTDFunction):
        types.extend(sig.pytd_sig.return_type for sig in val.signatures)
      else:
        types.append(pytd.AnythingType())
    safe_types = []  # types without type parameters
    for t in types:
      collector = visitors.CollectTypeParameters()
      t.Visit(collector)
      t = t.Visit(visitors.ReplaceTypeParameters(
          {p: p.upper_value for p in collector.params}))
      safe_types.append(t)
    return safe_types

  def _class_method_to_def(self, node, v, name, kind):
    """Convert a classmethod to a PyTD definition."""
    # This line may raise abstract_utils.ConversionError
    func = abstract_utils.get_atomic_value(v.func, abstract.Function)
    return self.value_to_pytd_def(node, func, name).Replace(kind=kind)

  def _static_method_to_def(self, node, v, name, kind):
    """Convert a staticmethod to a PyTD definition."""
    # This line may raise abstract_utils.ConversionError
    func = abstract_utils.get_atomic_value(v.func, abstract.Function)
    return self.value_to_pytd_def(node, func, name).Replace(kind=kind)

  def _is_instance(self, value, cls_name):
    return (isinstance(value, abstract.Instance) and
            value.cls.full_name == cls_name)

  def _class_to_def(self, node, v, class_name):
    """Convert an InterpreterClass to a PyTD definition."""
    methods = {}
    constants = collections.defaultdict(pytd_utils.TypeBuilder)

    annots = abstract_utils.get_annotations_dict(v.members)

    for name, t in self.annotations_to_instance_types(node, annots):
      constants[name].add_type(t)

    # class-level attributes
    for name, member in v.members.items():
      if name in CLASS_LEVEL_IGNORE or name in constants:
        continue
      for value in member.FilteredData(self.vm.exitpoint, strict=False):
        if isinstance(value, special_builtins.PropertyInstance):
          # For simplicity, output properties as constants, since our parser
          # turns them into constants anyway.
          if value.fget:
            for typ in self._function_to_return_types(node, value.fget):
              constants[name].add_type(typ)
          else:
            constants[name].add_type(pytd.AnythingType())
        elif isinstance(value, special_builtins.StaticMethodInstance):
          try:
            methods[name] = self._static_method_to_def(
                node, value, name, pytd.STATICMETHOD)
          except abstract_utils.ConversionError:
            constants[name].add_type(pytd.AnythingType())
        elif isinstance(value, special_builtins.ClassMethodInstance):
          try:
            methods[name] = self._class_method_to_def(
                node, value, name, pytd.CLASSMETHOD)
          except abstract_utils.ConversionError:
            constants[name].add_type(pytd.AnythingType())
        elif isinstance(value, abstract.Function):
          # TODO(rechen): Removing mutations altogether won't work for generic
          # classes. To support those, we'll need to change the mutated type's
          # base to the current class, rename aliased type parameters, and
          # replace any parameter not in the class or function template with
          # its upper value.
          methods[name] = self.value_to_pytd_def(node, value, name).Visit(
              visitors.DropMutableParameters())
        else:
          cls = self.vm.convert.merge_classes([value])
          node, attr = self.vm.attribute_handler.get_attribute(
              node, cls, "__get__")
          if attr:
            # This attribute is a descriptor. Its type is the return value of
            # its __get__ method.
            for typ in self._function_to_return_types(node, attr):
              constants[name].add_type(typ)
          else:
            constants[name].add_type(value.to_type(node))

    # instance-level attributes
    for instance in set(v.instances):
      for name, member in instance.members.items():
        if name not in CLASS_LEVEL_IGNORE:
          for value in member.FilteredData(self.vm.exitpoint, strict=False):
            constants[name].add_type(value.to_type(node))

    for name in list(methods):
      if name in constants:
        # If something is both a constant and a method, it means that the class
        # is, at some point, overwriting its own methods with an attribute.
        del methods[name]
        constants[name].add_type(pytd.AnythingType())

    constants = [pytd.Constant(name, builder.build())
                 for name, builder in constants.items() if builder]

    metaclass = v.metaclass(node)
    if metaclass is not None:
      metaclass = metaclass.get_instance_type(node)

    # Some of the class's bases may not be in global scope, so they won't show
    # up in the output. In that case, fold the base class's type information
    # into this class's pytd.
    bases = []
    missing_bases = []
    for basevar in v.bases():
      if basevar.data == [self.vm.convert.oldstyleclass_type]:
        continue
      elif len(basevar.bindings) == 1:
        b, = basevar.data
        if b.official_name is None and isinstance(b, abstract.InterpreterClass):
          missing_bases.append(b)
        else:
          bases.append(b.get_instance_type(node))
      else:
        bases.append(pytd_utils.JoinTypes(b.get_instance_type(node)
                                          for b in basevar.data))

    # Collect nested classes
    # TODO(mdemello): We cannot put these in the output yet; they fail in
    # load_dependencies because of the dotted class name (google/pytype#150)
    classes = [self._class_to_def(node, x, x.name)
               for x in v.get_inner_classes()]
    classes = [x.Replace(name=class_name + "." + x.name) for x in classes]

    cls = pytd.Class(name=class_name,
                     metaclass=metaclass,
                     parents=tuple(bases),
                     methods=tuple(methods.values()),
                     constants=tuple(constants),
                     classes=(),
                     slots=v.slots,
                     template=())
    for base in missing_bases:
      base_cls = self.value_to_pytd_def(node, base, base.name)
      cls = pytd_utils.MergeBaseClass(cls, base_cls)
    return cls

  def _typeparam_to_def(self, node, v, name):
    constraints = tuple(c.get_instance_type(node) for c in v.constraints)
    bound = v.bound and v.bound.get_instance_type(node)
    return pytd.TypeParameter(name, constraints=constraints, bound=bound)
