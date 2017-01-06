"""Tools for output generation."""

import collections
import logging


from pytype import abstract
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)

TOP_LEVEL_IGNORE = {
    "__builtins__",
    "__doc__",
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

  def _get_values(self, node, var, view):
    if var.bindings and view is not None:
      return [view[var].data]
    else:
      return var.Data(node)

  def _value_to_parameter_types(self, node, v, instance, template, seen, view):
    if instance is None and isinstance(v, abstract.ParameterizedClass):
      return [self.value_instance_to_pytd_type(
          node, v.type_parameters[t.name], None, seen, view) for t in template]
    elif isinstance(instance, abstract.Tuple):
      assert len(template) == 1 and template[0].name == abstract.T, template
      # Since we didn't include the pyval variables when computing the view,
      # we can't use it here, so just pass in None for the view instead.
      return [pytd_utils.JoinTypes(self.value_to_pytd_type(node, p, seen, None)
                                   for p in param.Data(node))
              for param in instance.pyval]
    elif isinstance(instance, abstract.SimpleAbstractValue):
      type_arguments = []
      for t in template:
        if t.name in instance.type_parameters:
          param_values = self._get_values(
              node, instance.type_parameters[t.name], view)
          type_arguments.append(pytd_utils.JoinTypes(
              self.value_to_pytd_type(node, p, seen, view)
              for p in param_values))
        else:
          type_arguments.append(pytd.AnythingType())
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
    elif isinstance(v, abstract.Class):
      if v.official_name is None:
        return pytd.AnythingType()
      if seen is None:
        seen = set()
      type_params = v.template
      if instance in seen:
        # We have a circular dependency in our types (e.g., lst[0] == lst). Stop
        # descending into the type parameters.
        type_params = ()
      if instance is not None:
        seen.add(instance)
      type_arguments = self._value_to_parameter_types(
          node, v, instance, type_params, seen, view)
      base = pytd_utils.NamedTypeWithModule(v.official_name, v.module)
      if isinstance(instance, abstract.Tuple):
        if type_arguments:
          return pytd.TupleType(base, tuple(type_arguments))
        else:
          type_arguments = [pytd.NothingType()]
      return pytd_utils.MakeClassOrContainerType(base, type_arguments)
    elif isinstance(v, abstract.TypeVariable):
      return pytd.TypeParameter(v.name, None)
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
      if (v.name in v.instance.type_parameters and
          v.instance.type_parameters[v.name].bindings):
        return pytd_utils.JoinTypes(
            self.value_to_pytd_type(node, p, seen, view)
            for p in v.instance.type_parameters[v.name].data)
      else:
        # The type parameter was never initialized
        return pytd.AnythingType()
    elif isinstance(v, (abstract.Function, abstract.IsInstance,
                        abstract.BoundFunction)):
      return pytd.NamedType("__builtin__.function")
    elif isinstance(v, abstract.Class):
      return pytd.GenericType(base_type=pytd.NamedType("__builtin__.type"),
                              parameters=(pytd.NamedType(v.full_name),))
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
        visitors.InPlaceFillInClasses(ret, v.vm.loader.builtins)
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
    elif isinstance(v, abstract.SuperInstance):
      return pytd.NamedType("__builtin__.super")
    elif isinstance(v, abstract.Unsolvable):
      return pytd.AnythingType()
    elif isinstance(v, abstract.Unknown):
      return pytd.NamedType(v.class_name)
    else:
      raise NotImplementedError(v.__class__.__name__)

  def value_to_pytd_def(self, node, v, name):
    """Get a PyTD definition for this object.

    Args:
      node: The node.
      v: The object.
      name: The object name.

    Returns:
      A PyTD definition.
    """
    if isinstance(v, abstract.PyTDFunction):
      return pytd.Function(
          name, tuple(sig.pytd_sig for sig in v.signatures), pytd.METHOD)
    elif isinstance(v, abstract.InterpreterFunction):
      return self._function_to_def(node, v, name)
    elif isinstance(v, abstract.ParameterizedClass):
      return pytd.Alias(name, v.get_instance_type(node))
    elif isinstance(v, abstract.PyTDClass):
      # This happens if a module does e.g. "from x import y as z", i.e., copies
      # something from another module to the local namespace. We *could*
      # reproduce the entire class, but we choose a more dense representation.
      return v.to_type(node)
    elif isinstance(v, abstract.InterpreterClass):
      return self._class_to_def(node, v, name)
    elif isinstance(v, abstract.TypeVariable):
      return pytd.TypeParameter(name, None)
    elif isinstance(v, abstract.Unsolvable):
      return pytd.Constant(name, v.to_type(node))
    else:
      raise NotImplementedError(v.__class__.__name__)

  def _function_to_def(self, node, v, function_name):
    """Convert an InterpreterFunction to a PyTD definition."""
    signatures = []
    combinations = tuple(v.get_call_combinations())
    if not combinations:
      # Fallback: Generate a PyTD signature only from the definition of the
      # method, not the way it's being  used.
      param = v.vm.convert.primitive_class_instances[object].to_variable(node)
      ret = v.vm.convert.create_new_unsolvable(node)
      combinations = ((node, collections.defaultdict(lambda: param.bindings[0]),
                       ret.bindings[0]),)
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
      if "return" in v.signature.annotations:
        ret = v.signature.annotations["return"].get_instance_type(node_after)
      else:
        ret = return_value.data.to_type(node_after)
      if isinstance(ret, pytd.NothingType) and len(combinations) == 1:
        assert isinstance(return_value.data, abstract.Empty)
        ret = pytd.AnythingType()
      if v.has_varargs():
        starargs = pytd.Parameter(v.signature.varargs_name,
                                  pytd.NamedType("__builtin__.tuple"),
                                  False, True, None)
      else:
        starargs = None
      if v.has_kwargs():
        starstarargs = pytd.Parameter(v.signature.kwargs_name,
                                      pytd.NamedType("__builtin__.dict"),
                                      False, True, None)
      else:
        starstarargs = None
      signatures.append(pytd.Signature(
          params=tuple(params),
          starargs=starargs,
          starstarargs=starstarargs,
          return_type=ret,
          exceptions=(),  # TODO(kramm): record exceptions
          template=()))
    return pytd.Function(function_name, tuple(signatures), pytd.METHOD)

  def _class_to_def(self, node, v, class_name):
    """Convert an InterpreterClass to a PyTD definition."""
    methods = {}
    constants = collections.defaultdict(pytd_utils.TypeBuilder)

    # class-level attributes
    for name, member in v.members.items():
      if name not in CLASS_LEVEL_IGNORE:
        for value in member.FilteredData(v.vm.exitpoint):
          if isinstance(value, abstract.Function):
            val = self.value_to_pytd_def(node, value, name)
            if isinstance(val, pytd.Function):
              methods[name] = val
            elif isinstance(v, pytd.TYPE):
              constants[name].add_type(val)
            else:
              raise AssertionError(str(type(val)))
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
             if basevar is not v.vm.convert.oldstyleclass_type]
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
