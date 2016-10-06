"""Abstract attribute handling."""
import logging


from pytype import abstract
from pytype import typing
from pytype.pytd import cfg as typegraph

log = logging.getLogger(__name__)


class AbstractAttributeHandler(object):
  """Handler for abstract attributes."""

  def get_attribute_generic(self, obj, node, name, val):
    if isinstance(obj, abstract.ParameterizedClass):
      return self.get_attribute_generic(obj.base_cls, node, name, val)
    elif isinstance(obj, abstract.Class):
      return self.get_attribute(obj, node, name, valcls=val)
    else:
      return self.get_attribute(obj, node, name, valself=val)

  def get_attribute(self, obj, node, name, valself=None, valcls=None,
                    condition=None):
    """Get the named attribute from the given object.

    Args:
      obj: The object.
      node: The current CFG node.
      name: The name of the attribute to retrieve.
      valself: A typegraph.Binding, This is the self reference to use when
        getting the attribute.
      valcls: A typegraph.Binding. This is the cls reference to use when getting
        the attribute. If valself is given then valcls will be ignored. Note
        that most implementations of this method ignore this value as only class
        objects need it (PyTDClass and InterpreterClass)
      condition: A Condition object or None.

    Returns:
      A tuple (CFGNode, typegraph.Variable). If this attribute doesn't exist,
      the Variable will be None.
    """
    # Some objects have special attributes, like "__get__" or "__iter__"
    special_attribute = obj.get_special_attribute(node, name, valself)
    if special_attribute is not None:
      return node, special_attribute
    if isinstance(obj, abstract.ValueWithSlots):
      return self.get_instance_attribute(
          obj, node, name, valself, valcls, condition)
    elif isinstance(obj, abstract.Function):
      if name == "__get__":
        # The pytd for "function" has a __get__ attribute, but if we already
        # have a function we don't want to be treated as a descriptor.
        return node, None
      else:
        return self.get_instance_attribute(
            obj, node, name, valself, valcls, condition)
    elif isinstance(obj, abstract.ParameterizedClass):
      return self.get_attribute(
          obj.base_cls, node, name, valself, valcls, condition)
    elif isinstance(obj, abstract.Class):
      return self.get_class_attribute(
          obj, node, name, valself, valcls, condition)
    elif isinstance(obj, typing.TypingOverlay):
      return self.get_module_attribute(
          obj.get_module(name), node, name, valself, valcls, condition)
    elif isinstance(obj, abstract.Module):
      return self.get_module_attribute(
          obj, node, name, valself, valcls, condition)
    elif isinstance(obj, abstract.SimpleAbstractValue):
      return self.get_instance_attribute(
          obj, node, name, valself, valcls, condition)
    elif isinstance(obj, abstract.SuperInstance):
      if obj.super_obj:
        valself = obj.super_obj.to_variable(node, "self").bindings[0]
      valcls = obj.super_cls.to_variable(node, "cls").bindings[0]
      return node, self._lookup_from_mro(
          obj.super_cls, node, name, valself, valcls, skip=obj.super_cls)
    elif isinstance(obj, abstract.Super):
      # In Python 3, you can do "super.__init__".
      raise NotImplementedError("Python 3 super not implemented yet")
    elif isinstance(obj, abstract.BoundFunction):
      return self.get_attribute(
          obj.underlying, node, name, valself, valcls, condition)
    elif isinstance(obj, abstract.Nothing):
      return node, None
    else:
      return node, None

  def get_module_attribute(self, module, node, name, valself=None, valcls=None,
                           condition=None):
    """Get an attribute from a module."""
    assert isinstance(module, abstract.Module)
    # Local variables in __init__.py take precedence over submodules.
    node, var = self.get_instance_attribute(
        module, node, name, valself, valcls, condition)
    if var is None:
      var = module.get_submodule(node, name)
    return node, var

  def get_class_attribute(self, cls, node, name, valself=None, valcls=None,
                          condition=None):
    """Retrieve an attribute by looking at the MRO of this class."""
    del condition  # unused arg.
    assert isinstance(cls, abstract.Class)
    if cls.cls and not valself:
      # TODO(rechen): Use valcls instead of creating a dummy instance.
      variableself, = abstract.Instance(
          cls.cls, cls.vm, node).to_variable(node).bindings
      variablecls, = cls.cls.bindings
      node, attr = self.get_attribute(
          variableself.data, node, name, variableself, variablecls)
      if attr is not None:
        return node, attr
    node, attr = self._get_attribute_computed(
        cls, node, name, valself, valcls, compute_function="__getattribute__")
    if attr is None:
      # _lookup_from_mro always returns a Variable.
      attr = self._lookup_from_mro(cls, node, name, valself, valcls)
    if not attr.bindings:
      node, attr = self._get_attribute_computed(
          cls, node, name, valself, valcls, compute_function="__getattr__")
    if isinstance(cls, abstract.InterpreterClass) and attr is not None:
      result = cls.vm.program.NewVariable(name)
      nodes = []
      # Deal with descriptors as a potential additional level of indirection.
      for v in attr.Bindings(node):
        value = v.data
        node2, getter = self.get_attribute(value, node, "__get__", v)
        if getter is not None:
          posargs = []
          if valself:
            posargs.append(valself.variable)
          if valcls:
            if not valself:
              posargs.append(cls.vm.convert.none.to_variable(node, "None"))
            posargs.append(valcls.variable)
          node2, get_result = cls.vm.call_function(
              node2, getter, abstract.FunctionArgs(tuple(posargs)))
          for getter in get_result.bindings:
            result.AddBinding(getter.data, [getter], node2)
        else:
          result.AddBinding(value, [v], node2)
        nodes.append(node2)
      if nodes:
        return cls.vm.join_cfg_nodes(nodes), result
    return node, attr

  def get_instance_attribute(self, obj, node, name, valself=None, valcls=None,
                             condition=None):
    """Get an attribute from an instance."""
    del valcls  # unused
    assert isinstance(obj, abstract.SimpleAbstractValue)
    node, attr = self._get_member(obj, node, name, valself)
    if attr is None:
      candidates = []
      if obj.cls:
        nodes = []
        for clsval in obj.cls.bindings:
          cls = clsval.data
          new_node, attr = self.get_attribute(cls, node, name, valself, clsval)
          nodes.append(new_node)
          if attr is not None:
            candidates.append(attr)
        node = obj.vm.join_cfg_nodes(nodes)
    else:
      candidates = [attr]
    return node, self._filter_and_merge_candidates(
        obj, node, name, candidates, condition)

  def set_attribute(self, obj, node, name, value):
    """Set an attribute on an object.

    The attribute might already have a Variable in it and in that case we cannot
    overwrite it and instead need to add the elements of the new variable to the
    old variable.

    Args:
      obj: The object.
      node: The current CFG node.
      name: The name of the attribute to set.
      value: The Variable to store in it.
    Returns:
      A (possibly changed) CFG node.
    Raises:
      AttributeError: If the attribute cannot be set.
      NotImplementedError: If attribute setting is not implemented for obj.
    """
    if isinstance(obj, abstract.Empty):
      return node
    elif isinstance(obj, abstract.Module):
      # Assigning attributes on modules is pretty common. E.g.
      # sys.path, sys.excepthook.
      log.warning("Ignoring overwrite of %s.%s", obj.name, name)
      return node
    elif isinstance(obj, abstract.SimpleAbstractValue):
      return self._set_member(obj, node, name, value)
    elif isinstance(obj, abstract.BoundFunction):
      return self.set_attribute(obj.underlying, node, name, value)
    elif isinstance(obj, abstract.Nothing):
      raise AttributeError("Object %r has no attribute %s" % (obj, name))
    elif isinstance(obj, abstract.Unsolvable):
      return node
    elif isinstance(obj, abstract.Unknown):
      if name in obj.members:
        obj.members[name].PasteVariable(value, node)
      else:
        obj.members[name] = value.AssignToNewVariable(
            obj.name + "." + name, node)
      return node
    else:
      raise NotImplementedError(obj.__class__.__name__)

  def _get_attribute_computed(self, cls, node, name, valself, valcls,
                              compute_function):
    """Call compute_function (if defined) to compute an attribute."""
    assert isinstance(cls, abstract.Class)
    if (valself and not isinstance(valself.data, abstract.Module) and
        name != "__init__"):
      attr_var = self._lookup_from_mro(
          cls, node, compute_function, valself, valcls,
          skip=cls.vm.convert.object_type.data[0])
      if attr_var and attr_var.bindings:
        vm = cls.vm  # pytype: disable=attribute-error
        name_var = abstract.AbstractOrConcreteValue(
            name, vm.convert.str_type, vm, node).to_variable(node, name)
        return vm.call_function(
            node, attr_var, abstract.FunctionArgs((name_var,)))
    return node, None

  def _lookup_from_mro(self, obj, node, name, valself, valcls, skip=None):
    """Find an identifier in the MRO of the class."""
    ret = obj.vm.program.NewVariable(name)
    add_origins = []
    variableself = variablecls = None
    if valself:
      assert isinstance(valself, typegraph.Binding)
      variableself = valself.AssignToNewVariable(valself.variable.name, node)
      add_origins.append(valself)
    if valcls:
      assert isinstance(valcls, typegraph.Binding)
      variablecls = valcls.AssignToNewVariable(valcls.variable.name, node)
      add_origins.append(valcls)

    for base in obj.mro:
      # Potentially skip start of MRO, for super()
      if base is skip:
        continue
      node, var = self._get_attribute_flat(base, node, name)
      if var is None or not var.bindings:
        continue
      for varval in var.bindings:
        value = varval.data
        if variableself or variablecls:
          value = value.property_get(variableself, variablecls)
        ret.AddBinding(value, [varval] + add_origins, node)
      break  # we found a class which has this attribute
    return ret

  def _get_attribute_flat(self, obj, node, name):
    if isinstance(obj, abstract.ParameterizedClass):
      return self._get_attribute_flat(obj.base_cls, node, name)
    elif isinstance(obj, abstract.Class):
      node, attr = self._get_member(obj, node, name)
      if attr is not None:
        attr = self._filter_and_merge_candidates(obj, node, name, [attr])
      return node, attr
    elif isinstance(obj, (abstract.Unknown, abstract.Unsolvable)):
      # The object doesn't have an MRO, so this is the same as get_attribute
      return self.get_attribute(obj, node, name)
    else:
      return node, None

  def _get_member(self, obj, node, name, valself=None):
    """Get a member of an object."""
    node, attr = obj.load_special_attribute(node, name)
    if attr is not None:
      return node, attr

    if obj.is_lazy:
      obj.load_lazy_attribute(name)

    # If we are looking up a member that we can determine is an instance
    # rather than a class attribute, add it to the instance's members.
    if valself:
      assert isinstance(obj, abstract.Instance)
      if name not in obj.members or not obj.members[name].Bindings(node):
        # See test_generic.testInstanceAttributeVisible for an example of an
        # attribute in self.members needing to be reloaded.
        self._maybe_load_as_instance_attribute(obj, node, name)

    # Retrieve instance attribute
    if name in obj.members:
      # Allow an instance attribute to shadow a class attribute, but only
      # if there's a path through the CFG that actually assigns it.
      # TODO(kramm): It would be more precise to check whether there's NOT any
      # path that DOESN'T have it.
      if obj.members[name].Bindings(node):
        return node, obj.members[name]
    return node, None

  def _filter_and_merge_candidates(self, obj, node, name, candidates,
                                   condition=None):
    """Merge the given candidates into one variable, filtered by the node."""
    ret = obj.vm.program.NewVariable(name)
    for candidate in candidates:
      for binding in candidate.Bindings(node):
        val = binding.data
        if isinstance(val, abstract.TypeParameterInstance):
          var = val.instance.type_parameters[val.name]
          # If this type parameter has visible values, we add those to the
          # return value. Otherwise, we add an empty value as a placeholder
          # that can be passed around and converted to Any after analysis.
          if var.Bindings(node):
            candidates.append(var)
          else:
            ret.AddBinding(obj.vm.convert.empty, [], node)
        else:
          sources = {binding}
          if condition:
            sources.add(condition.binding)
          ret.AddBinding(val, sources, node)
    if ret.bindings:
      return ret
    else:
      return None

  def _maybe_load_as_instance_attribute(self, obj, node, name):
    assert isinstance(obj, abstract.SimpleAbstractValue)
    for cls in obj.cls.data:
      if isinstance(cls, abstract.Class):
        var = self._get_as_instance_attribute(cls, node, name, obj)
        if var is not None:
          if name in obj.members:
            obj.members[name].PasteVariable(var, node)
          else:
            obj.members[name] = var

  def _get_as_instance_attribute(self, cls, node, name, instance):
    assert isinstance(cls, abstract.Class)
    for base in cls.mro:
      if isinstance(base, abstract.ParameterizedClass):
        base = base.base_cls
      if isinstance(base, abstract.PyTDClass):
        var = base.convert_as_instance_attribute(node, name, instance)
        if var is not None:
          return var

  def _set_member(self, obj, node, name, var):
    """Set a member on an object."""
    assert isinstance(var, typegraph.Variable)

    if obj.is_lazy:
      obj.load_lazy_attribute(name)

    if name == "__class__":
      return obj.set_class(node, var)

    if isinstance(obj, abstract.Instance) and name not in obj.members:
      # The previous value needs to be loaded at the root node so that
      # (1) it is overwritten by the current value and (2) it is still
      # visible on branches where the current value is not
      self._maybe_load_as_instance_attribute(obj, obj.vm.root_cfg_node, name)

    variable = obj.members.get(name)
    if variable:
      old_len = len(variable.bindings)
      variable.PasteVariable(var, node)
      log.debug("Adding choice(s) to %s: %d new values (%d total)", name,
                len(variable.bindings) - old_len, len(variable.bindings))
    else:
      # TODO(kramm): Under what circumstances can we just reuse var?
      #              (variable = self.members[name] = var)?
      log.debug("Setting %s to the %d values in %r",
                name, len(var.bindings), var)
      long_name = obj.name + "." + name
      variable = var.AssignToNewVariable(long_name, node)
      obj.members[name] = variable
    return node
