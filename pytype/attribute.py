"""Abstract attribute handling."""
import logging


from pytype import abstract
from pytype import typing
from pytype.pytd import cfg as typegraph

log = logging.getLogger(__name__)


class AbstractAttributeHandler(object):
  """Handler for abstract attributes."""

  def __init__(self, vm):
    self.vm = vm

  def get_attribute_generic(self, node, obj, name, val):
    if isinstance(obj, abstract.ParameterizedClass):
      return self.get_attribute_generic(node, obj.base_cls, name, val)
    elif isinstance(obj, abstract.Class):
      return self.get_attribute(node, obj, name, valcls=val)
    else:
      return self.get_attribute(node, obj, name, valself=val)

  def get_attribute(self, node, obj, name, valself=None, valcls=None):
    """Get the named attribute from the given object.

    Args:
      node: The current CFG node.
      obj: The object.
      name: The name of the attribute to retrieve.
      valself: A typegraph.Binding, This is the self reference to use when
        getting the attribute.
      valcls: A typegraph.Binding. This is the cls reference to use when getting
        the attribute. If valself is given then valcls will be ignored. Note
        that most implementations of this method ignore this value as only class
        objects need it (PyTDClass and InterpreterClass)

    Returns:
      A tuple (CFGNode, typegraph.Variable). If this attribute doesn't exist,
      the Variable will be None.
    """
    # Some objects have special attributes, like "__get__" or "__iter__"
    special_attribute = obj.get_special_attribute(node, name)
    if special_attribute is not None:
      return node, special_attribute
    if isinstance(obj, abstract.ValueWithSlots):
      return self.get_instance_attribute(
          node, obj, name, valself, valcls)
    elif isinstance(obj, abstract.Function):
      if name == "__get__":
        # The pytd for "function" has a __get__ attribute, but if we already
        # have a function we don't want to be treated as a descriptor.
        return node, None
      else:
        return self.get_instance_attribute(
            node, obj, name, valself, valcls)
    elif isinstance(obj, abstract.ParameterizedClass):
      return self.get_attribute(
          node, obj.base_cls, name, valself, valcls)
    elif isinstance(obj, abstract.Class):
      return self.get_class_attribute(
          node, obj, name, valself, valcls)
    elif isinstance(obj, typing.TypingOverlay):
      return self.get_module_attribute(
          node, obj.get_module(name), name, valself, valcls)
    elif isinstance(obj, abstract.Module):
      return self.get_module_attribute(
          node, obj, name, valself, valcls)
    elif isinstance(obj, abstract.SimpleAbstractValue):
      return self.get_instance_attribute(
          node, obj, name, valself, valcls)
    elif isinstance(obj, abstract.Union):
      nodes = []
      ret = self.vm.program.NewVariable()
      for o in obj.options:
        node2, attr = self.get_attribute(
            node, o, name, valself, valcls)
        if attr is not None:
          ret.PasteVariable(attr, node2)
          nodes.append(node2)
      if ret.bindings:
        return self.vm.join_cfg_nodes(nodes), ret
      else:
        return node, None
    elif isinstance(obj, abstract.SuperInstance):
      if obj.super_obj:
        valself = obj.super_obj.to_variable(node).bindings[0]
      valcls = obj.super_cls.to_variable(node).bindings[0]
      return node, self._lookup_from_mro(
          node, obj.super_cls, name, valself, valcls, skip=obj.super_cls)
    elif isinstance(obj, abstract.Super):
      # In Python 3, you can do "super.__init__".
      raise NotImplementedError("Python 3 super not implemented yet")
    elif isinstance(obj, abstract.BoundFunction):
      return self.get_attribute(
          node, obj.underlying, name, valself, valcls)
    elif isinstance(obj, abstract.Nothing):
      return node, None
    else:
      return node, None

  def get_module_attribute(self, node, module, name, valself=None, valcls=None):
    """Get an attribute from a module."""
    assert isinstance(module, abstract.Module)
    # Local variables in __init__.py take precedence over submodules.
    node, var = self.get_instance_attribute(
        node, module, name, valself, valcls)
    if var is None:
      var = module.get_submodule(node, name)
    return node, var

  def get_class_attribute(self, node, cls, name, valself=None, valcls=None):
    """Get an attribute from a class."""
    assert isinstance(cls, abstract.Class)
    getter = lambda cls: self._class_getter(node, cls, name, valself, valcls)
    if valself:
      meta = None
      variableself = valself
    else:
      # We treat a class as an instance of its metaclass, but only if we are
      # looking for a class rather than an instance attribute. (So, for
      # instance, if we're analyzing int.mro(), we want to retrieve the mro
      # method on the type class, but for 3.mro(), we want to report that the
      # method does not exist.)
      meta = cls.get_class()
      variableself = cls.to_variable(node).bindings[0]
    return self._get_value_or_class_attribute(
        node, cls, name, variableself, meta, getter)

  def get_instance_attribute(self, node, obj, name, valself=None, valcls=None):
    """Get an attribute from an instance."""
    del valcls  # unused
    assert isinstance(obj, abstract.SimpleAbstractValue)
    getter = lambda obj: self._get_member(node, obj, name, valself)
    return self._get_value_or_class_attribute(
        node, obj, name, valself, obj.cls, getter)

  def set_attribute(self, node, obj, name, value):
    """Set an attribute on an object.

    The attribute might already have a Variable in it and in that case we cannot
    overwrite it and instead need to add the elements of the new variable to the
    old variable.

    Args:
      node: The current CFG node.
      obj: The object.
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
      return self._set_member(node, obj, name, value)
    elif isinstance(obj, abstract.BoundFunction):
      return self.set_attribute(node, obj.underlying, name, value)
    elif isinstance(obj, abstract.Nothing):
      raise AttributeError("Object %r has no attribute %s" % (obj, name))
    elif isinstance(obj, abstract.Unsolvable):
      return node
    elif isinstance(obj, abstract.Unknown):
      if name in obj.members:
        obj.members[name].PasteVariable(value, node)
      else:
        obj.members[name] = value.AssignToNewVariable(node)
      return node
    else:
      raise NotImplementedError(obj.__class__.__name__)

  def _get_value_or_class_attribute(self, node, obj, name, valself, clsvar,
                                    get_from_value):
    """Get an attribute from a value or its class.

    Args:
      node: The current node.
      obj: The value.
      name: The name of the attribute.
      valself: The object binding.
      clsvar: A variable of the object class.
      get_from_value: A function that looks up the attribute on a value.

    Returns:
      A tuple of the node and the attribute, or None if it was not found.
    """
    def computer(clsval):
      return self._get_attribute_computed(
          node, clsval.data, name, valself, clsval,
          compute_function="__getattribute__")
    node, candidates = self._get_candidates_from_var(node, clsvar, computer)
    if not candidates or len(candidates) < len(clsvar.bindings):
      node, attr = get_from_value(obj)
      if attr is None:
        def getter(clsval):
          new_node, new_attr = self.get_attribute(
              node, clsval.data, name, valself, clsval)
          if new_attr is None:
            new_node, new_attr = self._get_attribute_computed(
                node, clsval.data, name, valself, clsval,
                compute_function="__getattr__")
          return new_node, new_attr
        node, new_candidates = self._get_candidates_from_var(
            node, clsvar, getter)
        candidates.extend(new_candidates)
      else:
        candidates.append(attr)
    attr = self._filter_and_merge_candidates(node, candidates)
    if attr is None and obj.maybe_missing_members:
      # The VM hit maximum depth while initializing this instance, so it may
      # have attributes that we don't know about.
      attr = self.vm.convert.unsolvable.to_variable(node)
    return node, attr

  def _class_getter(self, node, cls, name, valself, valcls):
    """Retrieve an attribute by looking at the MRO of this class."""
    attr = self._lookup_from_mro(node, cls, name, valself, valcls)
    if not attr.bindings:
      return node, None
    if isinstance(cls, abstract.InterpreterClass):
      result = self.vm.program.NewVariable()
      nodes = []
      # Deal with descriptors as a potential additional level of indirection.
      for v in attr.Bindings(node):
        value = v.data
        node2, getter = self.get_attribute(node, value, "__get__", v)
        if getter is not None:
          posargs = []
          if valself:
            posargs.append(valself.variable)
          if valcls:
            if not valself:
              posargs.append(self.vm.convert.none.to_variable(node))
            posargs.append(valcls.variable)
          node2, get_result = self.vm.call_function(
              node2, getter, abstract.FunctionArgs(tuple(posargs)))
          for getter in get_result.bindings:
            result.AddBinding(getter.data, [getter], node2)
        else:
          result.AddBinding(value, [v], node2)
        nodes.append(node2)
      if nodes:
        return self.vm.join_cfg_nodes(nodes), result
    return node, attr

  def _get_candidates_from_var(self, node, var, getter):
    """Convenience method for calling get_x on a variable."""
    candidates = []
    if var:
      nodes = []
      for val in var.bindings:
        new_node, candidate = getter(val)
        nodes.append(new_node)
        if candidate is not None:
          candidates.append(candidate)
      node = self.vm.join_cfg_nodes(nodes)
    return node, candidates

  def _computable(self, name):
    return not (name.startswith("__") and name.endswith("__"))

  def _get_attribute_computed(self, node, cls, name, valself, valcls,
                              compute_function):
    """Call compute_function (if defined) to compute an attribute."""
    assert isinstance(cls, (abstract.Class, abstract.AMBIGUOUS_OR_EMPTY))
    if (valself and not isinstance(valself.data, abstract.Module) and
        self._computable(name)):
      attr_var = self._lookup_from_mro(
          node, cls, compute_function, valself, valcls,
          skip=self.vm.convert.object_type.data[0])
      if attr_var and attr_var.bindings:
        vm = self.vm  # pytype: disable=attribute-error
        name_var = abstract.AbstractOrConcreteValue(
            name, vm.convert.str_type, vm, node).to_variable(node)
        return vm.call_function(
            node, attr_var, abstract.FunctionArgs((name_var,)))
    return node, None

  def _lookup_from_mro(self, node, obj, name, valself, valcls, skip=None):
    """Find an identifier in the MRO of the class."""
    ret = self.vm.program.NewVariable()
    add_origins = []
    variableself = variablecls = None
    if valself:
      assert isinstance(valself, typegraph.Binding)
      variableself = valself.AssignToNewVariable(node)
      add_origins.append(valself)
    if valcls:
      assert isinstance(valcls, typegraph.Binding)
      variablecls = valcls.AssignToNewVariable(node)
      add_origins.append(valcls)

    for base in obj.mro:
      # Potentially skip start of MRO, for super()
      if base is skip:
        continue
      node, var = self._get_attribute_flat(node, base, name)
      if var is None or not var.bindings:
        continue
      for varval in var.bindings:
        value = varval.data
        if variableself or variablecls:
          value = value.property_get(variableself, variablecls)
        ret.AddBinding(value, [varval] + add_origins, node)
      break  # we found a class which has this attribute
    return ret

  def _get_attribute_flat(self, node, obj, name):
    if isinstance(obj, abstract.ParameterizedClass):
      return self._get_attribute_flat(node, obj.base_cls, name)
    elif isinstance(obj, abstract.Class):
      node, attr = self._get_member(node, obj, name)
      if attr is not None:
        attr = self._filter_and_merge_candidates(node, [attr])
      return node, attr
    elif isinstance(obj, (abstract.Unknown, abstract.Unsolvable)):
      # The object doesn't have an MRO, so this is the same as get_attribute
      return self.get_attribute(node, obj, name)
    else:
      return node, None

  def _get_member(self, node, obj, name, valself=None):
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
        self._maybe_load_as_instance_attribute(node, obj, name)

    # Retrieve instance attribute
    if name in obj.members:
      # Allow an instance attribute to shadow a class attribute, but only
      # if there's a path through the CFG that actually assigns it.
      # TODO(kramm): It would be more precise to check whether there's NOT any
      # path that DOESN'T have it.
      if obj.members[name].Bindings(node):
        return node, obj.members[name]
    return node, None

  def _filter_and_merge_candidates(self, node, candidates):
    """Merge the given candidates into one variable, filtered by the node."""
    ret = self.vm.program.NewVariable()
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
            ret.AddBinding(self.vm.convert.empty, [], node)
        else:
          sources = {binding}
          ret.AddBinding(val, sources, node)
    if ret.bindings:
      return ret
    else:
      return None

  def _maybe_load_as_instance_attribute(self, node, obj, name):
    assert isinstance(obj, abstract.SimpleAbstractValue)
    for cls in obj.cls.data:
      if isinstance(cls, abstract.Class):
        var = self._get_as_instance_attribute(node, cls, name, obj)
        if var is not None:
          if name in obj.members:
            obj.members[name].PasteVariable(var, node)
          else:
            obj.members[name] = var

  def _get_as_instance_attribute(self, node, cls, name, instance):
    assert isinstance(cls, abstract.Class)
    for base in cls.mro:
      if isinstance(base, abstract.ParameterizedClass):
        base = base.base_cls
      if isinstance(base, abstract.PyTDClass):
        var = base.convert_as_instance_attribute(node, name, instance)
        if var is not None:
          return var

  def _set_member(self, node, obj, name, var):
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
      self._maybe_load_as_instance_attribute(self.vm.root_cfg_node, obj, name)

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
      variable = var.AssignToNewVariable(node)
      obj.members[name] = variable
    return node
