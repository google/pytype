"""Tools for output generation."""

import collections
import contextlib
import logging


from pytype import abstract
from pytype import special_builtins
from pytype import typing
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)

TOP_LEVEL_IGNORE = {
    "__builtins__",
    "__doc__",
    "__file__",
    "__future__",
    "__module__",
    "__name__",
}

CLASS_LEVEL_IGNORE = {
    "__builtins__",
    "__class__",
    "__module__",
    "__name__",
    "__qualname__",
}


class Converter(object):
  """Functions for converting abstract classes into PyTD."""

  def __init__(self):
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
    else:
      return var.Data(node)

  def _is_tuple(self, v, instance):
    return (isinstance(v, abstract.TupleClass) or
            isinstance(instance, abstract.Tuple))

  def _value_to_parameter_types(self, node, v, instance, template, seen, view):
    """Get PyTD types for the parameters of an instance of an abstract value."""
    if isinstance(v, abstract.Callable):
      assert template == (abstract.ARGS, abstract.RET), template
      template = range(v.num_args) + [template[1]]
    if self._is_tuple(v, instance):
      assert len(template) == 1 and template[0] == abstract.T, template
      if isinstance(v, abstract.TupleClass):
        template = range(v.tuple_length)
      else:
        template = range(instance.tuple_length)
    if instance is None and isinstance(v, abstract.ParameterizedClass):
      return [self.value_instance_to_pytd_type(
          node, v.type_parameters[t], None, seen, view) for t in template]
    elif isinstance(instance, abstract.SimpleAbstractValue):
      type_arguments = []
      for t in template:
        if isinstance(instance, abstract.Tuple):
          param_values = self._get_values(node, instance.pyval[t], view)
        elif t in instance.type_parameters:
          param_values = self._get_values(
              node, instance.type_parameters[t], view)
        elif isinstance(v, abstract.Callable):
          param_values = v.type_parameters[t].instantiate(
              node or v.vm.root_cfg_node).data
        else:
          param_values = [v.vm.convert.unsolvable]
        type_arguments.append(pytd_utils.JoinTypes(
            self.value_to_pytd_type(node, p, seen, view) for p in param_values))
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
    elif isinstance(v, abstract.Class):
      if not self._detailed and v.official_name is None:
        return pytd.AnythingType()
      if seen is None:
        seen = set()
      if instance in seen:
        # We have a circular dependency in our types (e.g., lst[0] == lst). Stop
        # descending into the type parameters.
        type_params = ()
      else:
        type_params = tuple(t.name for t in v.template)
      if instance is not None:
        seen.add(instance)
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
        homogeneous = not isinstance(v, abstract.Callable)
      else:
        homogeneous = len(type_arguments) == 1
      return pytd_utils.MakeClassOrContainerType(
          base, type_arguments, homogeneous)
    elif isinstance(v, abstract.TypeParameter):
      # We generate the full definition because, if this type parameter is
      # imported, we will need the definition in order to declare it later.
      return self._typeparam_to_def(node, v, v.name)
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
    if isinstance(v, (abstract.Empty, abstract.Nothing)):
      return pytd.NothingType()
    elif isinstance(v, abstract.TypeParameterInstance):
      if v.instance.type_parameters[v.name].bindings:
        # The type parameter was initialized.
        return pytd_utils.JoinTypes(
            self.value_to_pytd_type(node, p, seen, view)
            for p in v.instance.type_parameters[v.name].data)
      elif v.param.constraints:
        return pytd_utils.JoinTypes(
            self.value_instance_to_pytd_type(node, p, None, seen, view)
            for p in v.param.constraints)
      else:
        return pytd.AnythingType()
    elif isinstance(v, typing.TypeVar):
      return pytd.NamedType("__builtin__.type")
    elif isinstance(v, (abstract.InterpreterFunction,
                        abstract.BoundInterpreterFunction)):
      sig, = abstract.get_signatures(v)
      return self.value_instance_to_pytd_type(
          node, self.signature_to_callable(sig, v.vm), None, seen, view)
    elif isinstance(v, (abstract.PyTDFunction, abstract.BoundPyTDFunction)):
      signatures = abstract.get_signatures(v)
      if len(signatures) == 1:
        val = self.signature_to_callable(signatures[0], v.vm)
        if not v.vm.annotations_util.get_type_parameters(val):
          # This is a workaround to make sure we don't put unexpected type
          # parameters in call traces.
          return self.value_instance_to_pytd_type(node, val, None, seen, view)
      return pytd.NamedType("typing.Callable")
    elif isinstance(v, (special_builtins.IsInstance, abstract.ClassMethod,
                        abstract.StaticMethod)):
      return pytd.NamedType("typing.Callable")
    elif isinstance(v, abstract.Class):
      param = self.value_instance_to_pytd_type(node, v, None, seen, view)
      return pytd.GenericType(base_type=pytd.NamedType("__builtin__.type"),
                              parameters=(param,))
    elif isinstance(v, abstract.Module):
      return pytd.NamedType("__builtin__.module")
    elif isinstance(v, abstract.SimpleAbstractValue):
      if v.cls:
        classvalues = self._get_values(node, v.cls, view)
        cls_types = []
        for cls in classvalues:
          cls_types.append(self.value_instance_to_pytd_type(
              node, cls, v, seen=seen, view=view))
        ret = pytd_utils.JoinTypes(cls_types)
        ret.Visit(visitors.FillInLocalPointers(
            {"__builtin__": v.vm.loader.builtins}))
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
    elif isinstance(v, abstract.Unsolvable):
      return pytd.AnythingType()
    elif isinstance(v, abstract.Unknown):
      return pytd.NamedType(v.class_name)
    else:
      raise NotImplementedError(v.__class__.__name__)

  def signature_to_callable(self, sig, vm):
    base_cls = vm.convert.function_type
    ret = sig.annotations.get("return", vm.convert.unsolvable)
    if self._detailed or (
        sig.mandatory_param_count() == sig.maximum_param_count()):
      # If self._detailed is false, we throw away the argument types if the
      # function takes a variable number of arguments, which is correct for pyi
      # generation but undesirable for, say, error message printing.
      args = [sig.annotations.get(name, vm.convert.unsolvable)
              for name in sig.param_names]
      params = {abstract.ARGS: abstract.merge_values(args, vm, formal=True),
                abstract.RET: ret}
      params.update(enumerate(args))
      return abstract.Callable(base_cls, params, vm)
    else:
      # The only way to indicate a variable number of arguments in a Callable
      # is to not specify argument types at all.
      params = {abstract.ARGS: vm.convert.unsolvable, abstract.RET: ret}
      return abstract.ParameterizedClass(base_cls, params, vm)

  def value_to_pytd_def(self, node, v, name):
    """Get a PyTD definition for this object.

    Args:
      node: The node.
      v: The object.
      name: The object name.

    Returns:
      A PyTD definition.
    """
    if (isinstance(v, abstract.PyTDFunction) and
        not isinstance(v, typing.TypeVar)):
      return pytd.Function(
          name=name,
          signatures=tuple(sig.pytd_sig for sig in v.signatures),
          kind=v.kind,
          is_abstract=v.is_abstract)
    elif isinstance(v, abstract.InterpreterFunction):
      return self._function_to_def(node, v, name)
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

  def _function_call_to_return_type(self, node, v, seen_return, num_returns):
    if v.signature.has_return_annotation:
      ret = v.signature.annotations["return"].get_instance_type(node)
    else:
      ret = seen_return.data.to_type(node)
    if isinstance(ret, pytd.NothingType) and num_returns == 1:
      assert isinstance(seen_return.data, abstract.Empty)
      ret = pytd.AnythingType()
    return ret

  def _function_to_def(self, node, v, function_name):
    """Convert an InterpreterFunction to a PyTD definition."""
    signatures = []
    combinations = v.get_call_combinations(node)
    for node_after, combination, return_value in combinations:
      params = []
      for i, (name, kwonly, optional) in enumerate(v.get_parameters()):
        if i < v.nonstararg_count and name in v.signature.annotations:
          t = v.signature.annotations[name].get_instance_type(node_after)
        else:
          t = combination[name].data.to_type(node_after)
        # Python uses ".0" etc. for the names of parameters that are tuples,
        # like e.g. in: "def f((x,  y), z)".
        params.append(
            pytd.Parameter(name.replace(".", "_"), t, kwonly, optional, None))
      ret = self._function_call_to_return_type(
          node_after, v, return_value, len(combinations))
      if v.has_varargs():
        if v.signature.varargs_name in v.signature.annotations:
          annot = v.signature.annotations[v.signature.varargs_name]
          typ = annot.get_instance_type(node_after)
        else:
          typ = pytd.NamedType("__builtin__.tuple")
        starargs = pytd.Parameter(
            v.signature.varargs_name, typ, False, True, None)
      else:
        starargs = None
      if v.has_kwargs():
        if v.signature.kwargs_name in v.signature.annotations:
          annot = v.signature.annotations[v.signature.kwargs_name]
          typ = annot.get_instance_type(node_after)
        else:
          typ = pytd.NamedType("__builtin__.dict")
        starstarargs = pytd.Parameter(
            v.signature.kwargs_name, typ, False, True, None)
      else:
        starstarargs = None
      signatures.append(pytd.Signature(
          params=tuple(params),
          starargs=starargs,
          starstarargs=starstarargs,
          return_type=ret,
          exceptions=(),  # TODO(kramm): record exceptions
          template=()))
    return pytd.Function(name=function_name,
                         signatures=tuple(signatures),
                         kind=pytd.METHOD,
                         is_abstract=v.is_abstract)

  def _property_to_types(self, node, v):
    """Convert a property to a list of PyTD types."""
    if not v.fget:
      return [pytd.AnythingType()]
    getter_options = v.fget.FilteredData(v.vm.exitpoint)
    if not all(isinstance(o, abstract.Function) for o in getter_options):
      return [pytd.AnythingType()]
    types = []
    for val in getter_options:
      combinations = val.get_call_combinations(node)
      for node_after, _, return_value in combinations:
        types.append(self._function_call_to_return_type(
            node_after, val, return_value, len(combinations)))
    return types

  def _special_method_to_def(self, node, v, name, kind):
    """Convert a staticmethod or classmethod to a PyTD definition."""
    # This line may raise abstract.ConversionError
    func = abstract.get_atomic_value(v.members["__func__"], abstract.Function)
    return self.value_to_pytd_def(node, func, name).Replace(kind=kind)

  def _is_instance(self, value, cls_name):
    return (isinstance(value, abstract.Instance) and
            all(cls.full_name == cls_name for cls in value.cls.data))

  def _class_to_def(self, node, v, class_name):
    """Convert an InterpreterClass to a PyTD definition."""
    methods = {}
    constants = collections.defaultdict(pytd_utils.TypeBuilder)

    # class-level attributes
    for name, member in v.members.items():
      if name in CLASS_LEVEL_IGNORE:
        continue
      for value in member.FilteredData(v.vm.exitpoint):
        if isinstance(value, special_builtins.PropertyInstance):
          # For simplicity, output properties as constants, since our parser
          # turns them into constants anyway.
          for typ in self._property_to_types(node, value):
            constants[name].add_type(typ)
        elif self._is_instance(value, "__builtin__.staticmethod"):
          try:
            methods[name] = self._special_method_to_def(
                node, value, name, pytd.STATICMETHOD)
          except abstract.ConversionError:
            constants[name].add_type(pytd.AnythingType())
        elif self._is_instance(value, "__builtin__.classmethod"):
          try:
            methods[name] = self._special_method_to_def(
                node, value, name, pytd.CLASSMETHOD)
          except abstract.ConversionError:
            constants[name].add_type(pytd.AnythingType())
        elif isinstance(value, abstract.Function):
          methods[name] = self.value_to_pytd_def(node, value, name)
        else:
          constants[name].add_type(value.to_type(node))

    # instance-level attributes
    for instance in v.instances:
      for name, member in instance.members.items():
        if name not in CLASS_LEVEL_IGNORE:
          for value in member.FilteredData(v.vm.exitpoint):
            constants[name].add_type(value.to_type(node))

    for name in list(methods):
      if name in constants:
        # If something is both a constant and a method, it means that the class
        # is, at some point, overwriting its own methods with an attribute.
        del methods[name]
        constants[name].add_type(pytd.AnythingType())

    bases = [pytd_utils.JoinTypes(b.get_instance_type(node)
                                  for b in basevar.data)
             for basevar in v.bases()
             if basevar.data != [v.vm.convert.oldstyleclass_type]]
    constants = [pytd.Constant(name, builder.build())
                 for name, builder in constants.items() if builder]
    metaclass = v.metaclass(node)
    if metaclass is not None:
      metaclass = metaclass.get_instance_type(node)
    return pytd.Class(name=class_name,
                      metaclass=metaclass,
                      parents=tuple(bases),
                      methods=tuple(methods.values()),
                      constants=tuple(constants),
                      template=())

  def _typeparam_to_def(self, node, v, name):
    constraints = tuple(c.get_instance_type(node) for c in v.constraints)
    bound = v.bound and v.bound.get_instance_type(node)
    return pytd.TypeParameter(name, constraints=constraints, bound=bound)
