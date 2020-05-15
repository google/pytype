"""Abstract attribute handling."""
import logging

from pytype import abstract
from pytype import abstract_utils
from pytype import function
from pytype import mixin
from pytype import overlay
from pytype import special_builtins
from pytype import utils
from pytype.typegraph import cfg

log = logging.getLogger(__name__)


class AbstractAttributeHandler(utils.VirtualMachineWeakrefMixin):
  """Handler for abstract attributes."""

  def get_attribute(self, node, obj, name, valself=None):
    """Get the named attribute from the given object.

    Args:
      node: The current CFG node.
      obj: The object.
      name: The name of the attribute to retrieve.
      valself: A cfg.Binding to a self reference to include in the attribute's
        origins. If obj is a mixin.Class, valself can be a binding to:
        * an instance of obj - obj will be treated strictly as a class.
        * obj itself - obj will be treated as an instance of its metaclass.
        * None - if name == "__getitem__", obj is a type annotation; else, obj
            is strictly a class, but the attribute is left unbound.
        Else, valself is optional and should be a binding to obj when given.

    Returns:
      A tuple (CFGNode, cfg.Variable). If this attribute doesn't exist,
      the Variable will be None.
    """
    # Some objects have special attributes, like "__get__" or "__iter__"
    special_attribute = obj.get_special_attribute(node, name, valself)
    if special_attribute is not None:
      return node, special_attribute
    if isinstance(obj, abstract.Function):
      if name == "__get__":
        # The pytd for "function" has a __get__ attribute, but if we already
        # have a function we don't want to be treated as a descriptor.
        return node, None
      else:
        return self._get_instance_attribute(node, obj, name, valself)
    elif isinstance(obj, abstract.ParameterizedClass):
      return self.get_attribute(node, obj.base_cls, name, valself)
    elif isinstance(obj, mixin.Class):
      return self._get_class_attribute(node, obj, name, valself)
    elif isinstance(obj, overlay.Overlay):
      return self._get_module_attribute(
          node, obj.get_module(name), name, valself)
    elif isinstance(obj, abstract.Module):
      return self._get_module_attribute(node, obj, name, valself)
    elif isinstance(obj, abstract.SimpleAbstractValue):
      return self._get_instance_attribute(node, obj, name, valself)
    elif isinstance(obj, abstract.Union):
      nodes = []
      ret = self.vm.program.NewVariable()
      for o in obj.options:
        node2, attr = self.get_attribute(node, o, name, valself)
        if attr is not None:
          ret.PasteVariable(attr, node2)
          nodes.append(node2)
      if ret.bindings:
        return self.vm.join_cfg_nodes(nodes), ret
      else:
        return node, None
    elif isinstance(obj, special_builtins.SuperInstance):
      if obj.super_obj:
        cls = obj.super_cls
        valself = obj.super_obj.to_binding(node)
        skip = obj.super_cls
      else:
        cls = self.vm.convert.super_type
        skip = None
      return self._lookup_from_mro_and_handle_descriptors(
          node, cls, name, valself, skip)
    elif isinstance(obj, special_builtins.Super):
      return self.get_attribute(node, self.vm.convert.super_type, name, valself)
    elif isinstance(obj, abstract.BoundFunction):
      return self.get_attribute(node, obj.underlying, name, valself)
    elif isinstance(obj, abstract.TypeParameterInstance):
      param_var = obj.instance.get_instance_type_parameter(obj.name)
      if not param_var.bindings:
        param_var = obj.param.instantiate(self.vm.root_cfg_node)
      results = []
      nodes = []
      for v in param_var.data:
        node2, ret = self.get_attribute(node, v, name, valself)
        if ret is None:
          return node, None
        else:
          results.append(ret)
          nodes.append(node2)
      node = self.vm.join_cfg_nodes(nodes)
      return node, self.vm.join_variables(node, results)
    elif isinstance(obj, abstract.Empty):
      return node, None
    else:
      return node, None

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
    if not self._check_writable(obj, name):
      # We ignore the write of an attribute that's not in __slots__, since it
      # wouldn't happen in the Python interpreter, either.
      return node
    assert isinstance(value, cfg.Variable)
    if self.vm.frame is not None and obj is self.vm.frame.f_globals:
      for v in value.data:
        v.update_official_name(name)
    if isinstance(obj, abstract.Empty):
      return node
    elif isinstance(obj, abstract.Module):
      # Assigning attributes on modules is pretty common. E.g.
      # sys.path, sys.excepthook.
      log.warning("Ignoring overwrite of %s.%s", obj.name, name)
      return node
    elif isinstance(obj, (abstract.StaticMethod, abstract.ClassMethod)):
      return self.set_attribute(node, obj.method, name, value)
    elif isinstance(obj, abstract.SimpleAbstractValue):
      return self._set_member(node, obj, name, value)
    elif isinstance(obj, abstract.BoundFunction):
      return self.set_attribute(node, obj.underlying, name, value)
    elif isinstance(obj, abstract.Unsolvable):
      return node
    elif isinstance(obj, abstract.Unknown):
      if name in obj.members:
        obj.members[name].PasteVariable(value, node)
      else:
        obj.members[name] = value.AssignToNewVariable(node)
      return node
    elif isinstance(obj, abstract.TypeParameterInstance):
      nodes = []
      for v in obj.instance.get_instance_type_parameter(obj.name).data:
        nodes.append(self.set_attribute(node, v, name, value))
      return self.vm.join_cfg_nodes(nodes) if nodes else node
    elif isinstance(obj, abstract.Union):
      for option in obj.options:
        node = self.set_attribute(node, option, name, value)
      return node
    else:
      raise NotImplementedError(obj.__class__.__name__)

  def _check_writable(self, obj, name):
    """Verify that a given attribute is writable. Log an error if not."""
    if obj.cls is None:
      # "Any" etc.
      return True
    for baseclass in obj.cls.mro:
      if baseclass.full_name == "__builtin__.object":
        # It's not possible to set an attribute on object itself.
        # (object has __setattr__, but that honors __slots__.)
        continue
      if (isinstance(baseclass, abstract.SimpleAbstractValue) and
          ("__setattr__" in baseclass or name in baseclass)):
        return True  # This is a programmatic attribute.
      if baseclass.slots is None or name in baseclass.slots:
        return True  # Found a slot declaration; this is an instance attribute
    self.vm.errorlog.not_writable(self.vm.frames, obj, name)
    return False

  def _is_simple_module(self, var):
    # A simple module is an abstract.Instance(module). It returns Any for all
    # attribute accesses (unlike an abstract.Module, which does ast lookups).
    cls = self.vm.convert.merge_classes(var.data)
    if cls != self.vm.convert.module_type:
      return False
    return not any(isinstance(v, abstract.Module) for v in var.data)

  def _get_module_attribute(self, node, module, name, valself=None):
    """Get an attribute from a module."""
    assert isinstance(module, abstract.Module)

    # Local variables in __init__.py take precedence over submodules.
    node, var = self._get_instance_attribute(node, module, name, valself)
    if var is not None and not self._is_simple_module(var):
      # If `var` is a simple module, then we want to try get_submodule, to see
      # if it can find a more precise value.
      return node, var

    # And finally, look for a submodule. If none is found, then return `var`
    # instead, which may be a submodule that appears only in __init__.
    return node, module.get_submodule(node, name) or var

  def _get_class_attribute(self, node, cls, name, valself=None):
    """Get an attribute from a class."""
    assert isinstance(cls, mixin.Class)
    if (not valself or not abstract_utils.equivalent_to(valself, cls) or
        cls == self.vm.convert.type_type):
      # Since type(type) == type, the type_type check prevents an infinite loop.
      meta = None
    else:
      # We treat a class as an instance of its metaclass, but only if we are
      # looking for a class rather than an instance attribute. (So, for
      # instance, if we're analyzing int.mro(), we want to retrieve the mro
      # method on the type class, but for (3).mro(), we want to report that the
      # method does not exist.)
      meta = cls.get_class()
    return self._get_attribute(node, cls, meta, name, valself)

  def _get_instance_attribute(self, node, obj, name, valself=None):
    """Get an attribute from an instance."""
    assert isinstance(obj, abstract.SimpleAbstractValue)
    return self._get_attribute(node, obj, obj.cls, name, valself)

  def _get_attribute(self, node, obj, cls, name, valself):
    """Get an attribute from an object or its class.

    The underlying method called by all of the (_)get_(x_)attribute methods.
    Attempts to resolve an attribute first with __getattribute__, then by
    fetching it from the object, then by fetching it from the class, and
    finally with __getattr__.

    Arguments:
      node: The current node.
      obj: The object.
      cls: The object's class, may be None.
      name: The attribute name.
      valself: The binding to the self reference.

    Returns:
      A tuple of the node and the attribute, or None if it was not found.
    """
    if cls:
      # A __getattribute__ on the class controls all attribute access.
      node, attr = self._get_attribute_computed(
          node, cls, name, valself, compute_function="__getattribute__")
    else:
      attr = None
    if attr is None:
      # Check for the attribute on the instance.
      if isinstance(obj, mixin.Class):
        # A class is an instance of its metaclass.
        node, attr = self._lookup_from_mro_and_handle_descriptors(
            node, obj, name, valself, skip=None)
      else:
        node, attr = self._get_member(node, obj, name)
    if attr is None and cls:
      # Check for the attribute on the class.
      node, attr = self.get_attribute(node, cls, name, valself)
      if attr is None:
        # Fall back to __getattr__ if the attribute doesn't otherwise exist.
        node, attr = self._get_attribute_computed(
            node, cls, name, valself, compute_function="__getattr__")
    if attr is None:
      annots = abstract_utils.get_annotations_dict(obj.members)
      if annots:
        typ = annots.get_type(node, name)
        if typ:
          # An attribute has been declared but not defined, e.g.,
          #   class Foo:
          #     bar: int
          _, attr = self.vm.init_class(node, typ)
    if attr is not None:
      attr = self._filter_var(node, attr)
    if attr is None and obj.maybe_missing_members:
      # The VM hit maximum depth while initializing this instance, so it may
      # have attributes that we don't know about.
      attr = self.vm.new_unsolvable(node)
    return node, attr

  def _lookup_from_mro_and_handle_descriptors(
      self, node, cls, name, valself, skip):
    attr = self._lookup_from_mro(node, cls, name, valself, skip)
    if not attr.bindings:
      return node, None
    if isinstance(cls, abstract.InterpreterClass):
      result = self.vm.program.NewVariable()
      nodes = []
      # Deal with descriptors as a potential additional level of indirection.
      for v in attr.bindings:
        value = v.data
        node2, getter = self.get_attribute(node, value, "__get__", v)
        if getter is not None:
          posargs = []
          if valself:
            posargs.append(valself.AssignToNewVariable())
          else:
            posargs.append(self.vm.convert.none.to_variable(node))
          posargs.append(cls.to_variable(node))
          node2, get_result = self.vm.call_function(
              node2, getter, function.Args(tuple(posargs)))
          for getter in get_result.bindings:
            result.AddBinding(getter.data, [getter], node2)
        else:
          result.AddBinding(value, [v], node2)
        nodes.append(node2)
      if nodes:
        return self.vm.join_cfg_nodes(nodes), result
    return node, attr

  def _computable(self, name):
    return not (name.startswith("__") and name.endswith("__"))

  def _get_attribute_computed(self, node, cls, name, valself, compute_function):
    """Call compute_function (if defined) to compute an attribute."""
    assert isinstance(cls, (mixin.Class, abstract.AMBIGUOUS_OR_EMPTY)), cls
    if (valself and not isinstance(valself.data, abstract.Module) and
        self._computable(name)):
      attr_var = self._lookup_from_mro(node, cls, compute_function, valself,
                                       skip=self.vm.convert.object_type)
      if attr_var and attr_var.bindings:
        name_var = abstract.AbstractOrConcreteValue(
            name, self.vm.convert.str_type, self.vm).to_variable(node)
        return self.vm.call_function(node, attr_var, function.Args((name_var,)))
    return node, None

  def _lookup_from_mro(self, node, cls, name, valself, skip):
    """Find an identifier in the MRO of the class."""
    if isinstance(cls, (abstract.Unknown, abstract.Unsolvable)):
      # We don't know the object's MRO, so it's possible that one of its
      # bases has the attribute.
      return self.vm.new_unsolvable(node)
    ret = self.vm.program.NewVariable()
    add_origins = [valself] if valself else []
    for base in cls.mro:
      # Potentially skip start of MRO, for super()
      if base is skip:
        continue
      # When a special attribute is defined on a class buried in the MRO,
      # get_attribute (which calls get_special_attribute) is never called on
      # that class, so we have to call get_special_attribute here as well.
      var = base.get_special_attribute(node, name, valself)
      if var is None:
        node, var = self._get_attribute_flat(node, base, name)
      if var is None or not var.bindings:
        continue
      for varval in var.bindings:
        value = varval.data
        if valself:
          # Check if we got a PyTDFunction from an InterpreterClass. If so,
          # then we must have aliased an imported function inside a class, so
          # we shouldn't bind the function to the class.
          if (not isinstance(value, abstract.PyTDFunction) or
              not isinstance(base, abstract.InterpreterClass)):
            # See AtomicAbstractValue.property_get for an explanation of the
            # parameters we're passing here.
            value = value.property_get(
                valself.AssignToNewVariable(node),
                abstract_utils.equivalent_to(valself, cls))
          if isinstance(value, abstract.Property):
            node, value = value.call(node, None, None)
            final_values = value.data
          else:
            final_values = [value]
        else:
          final_values = [value]
        for final_value in final_values:
          ret.AddBinding(final_value, [varval] + add_origins, node)
      break  # we found a class which has this attribute
    return ret

  def _get_attribute_flat(self, node, cls, name):
    """Flat attribute retrieval (no mro lookup)."""
    if isinstance(cls, abstract.ParameterizedClass):
      return self._get_attribute_flat(node, cls.base_cls, name)
    elif isinstance(cls, mixin.Class):
      node, attr = self._get_member(node, cls, name)
      if attr is not None:
        attr = self._filter_var(node, attr)
      return node, attr
    elif isinstance(cls, (abstract.Unknown, abstract.Unsolvable)):
      # The object doesn't have an MRO, so this is the same as get_attribute
      return self.get_attribute(node, cls, name)
    else:
      return node, None

  def _get_member(self, node, obj, name):
    """Get a member of an object."""
    if obj.is_lazy:
      obj.load_lazy_attribute(name)

    # If we are looking up a member that we can determine is an instance
    # rather than a class attribute, add it to the instance's members.
    if isinstance(obj, abstract.Instance):
      if name not in obj.members or not obj.members[name].bindings:
        # See test_generic.testInstanceAttributeVisible for an example of an
        # attribute in self.members needing to be reloaded.
        self._maybe_load_as_instance_attribute(node, obj, name)

    # Retrieve member
    if name in obj.members and obj.members[name].Bindings(node):
      return node, obj.members[name]
    return node, None

  def _filter_var(self, node, var):
    """Filter the variable by the node.

    Filters the variable data, including recursively expanded type parameter
    instances, by visibility at the node. A type parameter instance needs to be
    filtered at the moment of access because its value may change later.

    Args:
      node: The current node.
      var: A variable to filter.
    Returns:
      The filtered variable.
    """
    # First, check if we need to do any filtering at all. This method is
    # heavily called, so creating the `ret` variable judiciously reduces the
    # number of variables per pytype run by as much as 20%.
    bindings = var.Bindings(node, strict=False)
    if not bindings:
      return None
    if len(bindings) == len(var.bindings) and not any(
        isinstance(b.data, abstract.TypeParameterInstance) for b in bindings):
      return var
    ret = self.vm.program.NewVariable()
    for binding in bindings:
      val = binding.data
      if isinstance(val, abstract.TypeParameterInstance):
        var = val.instance.get_instance_type_parameter(val.name)
        # If this type parameter has visible values, we add those to the
        # return value. Otherwise, if it has constraints, we add those as an
        # upper bound on the values. When all else fails, we add an empty
        # value as a placeholder that can be passed around and converted to
        # Any after analysis.
        var_bindings = var.Bindings(node)
        if var_bindings:
          bindings.extend(var_bindings)
        elif val.param.constraints:
          constraints = self.vm.merge_values(val.param.constraints)
          ret.PasteVariable(constraints.instantiate(node))
        else:
          ret.AddBinding(self.vm.convert.empty, [], node)
      else:
        ret.AddBinding(val, {binding}, node)
    if ret.bindings:
      return ret
    else:
      return None

  def _maybe_load_as_instance_attribute(self, node, obj, name):
    assert isinstance(obj, abstract.SimpleAbstractValue)
    if not isinstance(obj.cls, mixin.Class):
      return
    for base in obj.cls.mro:
      if isinstance(base, abstract.ParameterizedClass):
        base = base.base_cls
      if isinstance(base, abstract.PyTDClass):
        var = base.convert_as_instance_attribute(name, obj)
        if var is not None:
          if name in obj.members:
            obj.members[name].PasteVariable(var, node)
          else:
            obj.members[name] = var
          return

  def _set_member(self, node, obj, name, var):
    """Set a member on an object."""
    assert isinstance(var, cfg.Variable)

    if obj.is_lazy:
      obj.load_lazy_attribute(name)

    if name == "__class__":
      return obj.set_class(node, var)

    if (isinstance(obj, (abstract.PyTDFunction, abstract.SignedFunction)) and
        name == "__defaults__"):
      log.info("Setting defaults for %s to %r", obj.name, var)
      obj.set_function_defaults(node, var)
      return node

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
