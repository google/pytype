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
import hashlib
import inspect
import itertools
import logging
from typing import Mapping

import attr
from pytype import datatypes
from pytype import utils
from pytype.abstract import _base
from pytype.abstract import abstract_utils
from pytype.abstract import class_mixin
from pytype.abstract import function
from pytype.abstract import mixin
from pytype.pytd import escape
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors
from pytype.pytd.codegen import decorate
from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils

log = logging.getLogger(__name__)

# For simplicity, we pretend all abstract values are defined in abstract.py.
BaseValue = _base.BaseValue


class Singleton(BaseValue):
  """A Singleton class must only be instantiated once.

  This is essentially an ABC for Unsolvable, Empty, and others.
  """

  _instance = None

  def __new__(cls, *args, **kwargs):
    # If cls is a subclass of a subclass of Singleton, cls._instance will be
    # filled by its parent. cls needs to be given its own instance.
    if not cls._instance or type(cls._instance) != cls:  # pylint: disable=unidiomatic-typecheck
      log.debug("Singleton: Making new instance for %s", cls)
      cls._instance = super().__new__(cls)
    return cls._instance

  def get_special_attribute(self, node, name, valself):
    del name, valself
    return self.to_variable(node)

  def compute_mro(self):
    return self.default_mro()

  def call(self, node, func, args, alias_map=None):
    del func, args
    return node, self.to_variable(node)

  def instantiate(self, node, container=None):
    return self.to_variable(node)


class Empty(Singleton):
  """An empty value.

  These values represent items extracted from empty containers. Because of false
  positives in flagging containers as empty (consider:
    x = []
    def initialize():
      populate(x)
    def f():
      iterate(x)
  ), we treat these values as placeholders that we can do anything with, similar
  to Unsolvable, with the difference that they eventually convert to
  NothingType so that cases in which they are truly empty are discarded (see:
    x = ...  # type: List[nothing] or Dict[int, str]
    y = [i for i in x]  # The type of i is int; y is List[int]
  ). On the other hand, if Empty is the sole type candidate, we assume that the
  container was populated elsewhere:
    x = []
    def initialize():
      populate(x)
    def f():
      return x[0]  # Oops! The return type should be Any rather than nothing.
  The nothing -> anything conversion happens in
  convert.Converter._function_to_def and tracer_vm.CallTracer.pytd_for_types.
  """

  def __init__(self, ctx):
    super().__init__("empty", ctx)


class Deleted(Empty):
  """Assigned to variables that have del called on them."""

  def __init__(self, ctx):
    super().__init__(ctx)
    self.name = "deleted"

  def get_special_attribute(self, node, name, valself):
    del name, valself  # unused
    return self.ctx.new_unsolvable(node)


class TypeParameter(BaseValue):
  """Parameter of a type."""

  formal = True

  def __init__(self,
               name,
               ctx,
               constraints=(),
               bound=None,
               covariant=False,
               contravariant=False,
               module=None):
    super().__init__(name, ctx)
    self.constraints = constraints
    self.bound = bound
    self.covariant = covariant
    self.contravariant = contravariant
    self.module = module

  def is_generic(self):
    return not self.constraints and not self.bound

  def copy(self):
    return TypeParameter(self.name, self.ctx, self.constraints, self.bound,
                         self.covariant, self.contravariant, self.module)

  def with_module(self, module):
    res = self.copy()
    res.module = module
    return res

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return (self.name == other.name and
              self.constraints == other.constraints and
              self.bound == other.bound and
              self.covariant == other.covariant and
              self.contravariant == other.contravariant and
              self.module == other.module)
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def __hash__(self):
    return hash((self.name, self.constraints, self.bound, self.covariant,
                 self.contravariant))

  def __repr__(self):
    return "TypeParameter(%r, constraints=%r, bound=%r, module=%r)" % (
        self.name, self.constraints, self.bound, self.module)

  def instantiate(self, node, container=None):
    var = self.ctx.program.NewVariable()
    if container and (not isinstance(container, SimpleValue) or
                      self.full_name in container.all_template_names):
      instance = TypeParameterInstance(self, container, self.ctx)
      return instance.to_variable(node)
    else:
      for c in self.constraints:
        var.PasteVariable(c.instantiate(node, container))
      if self.bound:
        var.PasteVariable(self.bound.instantiate(node, container))
    if not var.bindings:
      var.AddBinding(self.ctx.convert.unsolvable, [], node)
    return var

  def update_official_name(self, name):
    if self.name != name:
      message = "TypeVar(%r) must be stored as %r, not %r" % (
          self.name, self.name, name)
      self.ctx.errorlog.invalid_typevar(self.ctx.vm.frames, message)

  def call(self, node, func, args, alias_map=None):
    return node, self.instantiate(node)


class TypeParameterInstance(BaseValue):
  """An instance of a type parameter."""

  def __init__(self, param, instance, ctx):
    super().__init__(param.name, ctx)
    self.cls = self.param = param
    self.instance = instance
    self.module = param.module

  def call(self, node, func, args, alias_map=None):
    var = self.instance.get_instance_type_parameter(self.name)
    if var.bindings:
      return function.call_function(self.ctx, node, var, args)
    else:
      return node, self.ctx.convert.empty.to_variable(self.ctx.root_node)

  def __repr__(self):
    return "TypeParameterInstance(%r)" % self.name

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return self.param == other.param and self.instance == other.instance
    return NotImplemented

  def __hash__(self):
    return hash((self.param, self.instance))


class SimpleValue(BaseValue):
  """A basic abstract value that represents instances.

  This class implements instances in the Python sense. Instances of the same
  class may vary.

  Note that the cls attribute will point to another abstract value that
  represents the class object itself, not to some special type representation.

  Attributes:
    members: A name->value dictionary of the instance's attributes.
  """

  def __init__(self, name, ctx):
    """Initialize a SimpleValue.

    Args:
      name: Name of this value. For debugging and error reporting.
      ctx: The abstract context.
    """
    super().__init__(name, ctx)
    self._cls = None  # lazily loaded 'cls' attribute
    self.members = datatypes.MonitorDict()
    # Lazily loaded to handle recursive types.
    # See Instance._load_instance_type_parameters().
    self._instance_type_parameters = datatypes.AliasingMonitorDict()
    # This attribute depends on self.cls, which isn't yet set to its true value.
    self._maybe_missing_members = None
    # The latter caches the result of get_type_key. This is a recursive function
    # that has the potential to generate too many calls for large definitions.
    self._cached_type_key = (
        (self.members.changestamp, self._instance_type_parameters.changestamp),
        None)

  @property
  def instance_type_parameters(self):
    return self._instance_type_parameters

  @property
  def maybe_missing_members(self):
    if self._maybe_missing_members is None:
      self._maybe_missing_members = isinstance(
          self.cls, (InterpreterClass, PyTDClass)) and self.cls.is_dynamic
    return self._maybe_missing_members

  @maybe_missing_members.setter
  def maybe_missing_members(self, v):
    self._maybe_missing_members = v

  def has_instance_type_parameter(self, name):
    """Check if the key is in `instance_type_parameters`."""
    name = abstract_utils.full_type_name(self, name)
    return name in self.instance_type_parameters

  def get_children_maps(self):
    return (self.instance_type_parameters, self.members)

  def get_instance_type_parameter(self, name, node=None):
    name = abstract_utils.full_type_name(self, name)
    param = self.instance_type_parameters.get(name)
    if not param:
      log.info("Creating new empty type param %s", name)
      if node is None:
        node = self.ctx.root_node
      param = self.ctx.program.NewVariable([], [], node)
      self.instance_type_parameters[name] = param
    return param

  def merge_instance_type_parameter(self, node, name, value):
    """Set the value of a type parameter.

    This will always add to the type parameter unlike set_attribute which will
    replace value from the same basic block. This is because type parameters may
    be affected by a side effect so we need to collect all the information
    regardless of multiple assignments in one basic block.

    Args:
      node: Optionally, the current CFG node.
      name: The name of the type parameter.
      value: The value that is being used for this type parameter as a Variable.
    """
    name = abstract_utils.full_type_name(self, name)
    log.info("Modifying type param %s", name)
    if name in self.instance_type_parameters:
      self.instance_type_parameters[name].PasteVariable(value, node)
    else:
      self.instance_type_parameters[name] = value

  def call(self, node, _, args, alias_map=None):
    node, var = self.ctx.attribute_handler.get_attribute(
        node, self, "__call__", self.to_binding(node))
    if var is not None and var.bindings:
      return function.call_function(self.ctx, node, var, args)
    else:
      raise function.NotCallable(self)

  def argcount(self, node):
    node, var = self.ctx.attribute_handler.get_attribute(
        node, self, "__call__", self.to_binding(node))
    if var and var.bindings:
      return min(v.argcount(node) for v in var.data)
    else:
      # It doesn't matter what we return here, since any attempt to call this
      # value will lead to a not-callable error anyways.
      return 0

  def __repr__(self):
    return "<%s [%r]>" % (self.name, self.cls)

  def _get_class(self):
    if isinstance(self, InterpreterClass):
      return ParameterizedClass(self.ctx.convert.type_type,
                                {abstract_utils.T: self}, self.ctx)
    elif isinstance(self, (AnnotationClass, class_mixin.Class)):
      return self.ctx.convert.type_type
    else:
      return self.ctx.convert.unsolvable

  @property
  def cls(self):
    if not self.ctx.converter_minimally_initialized:
      return self.ctx.convert.unsolvable
    if not self._cls:
      self._cls = self.ctx.convert.unsolvable  # prevent infinite recursion
      self._cls = self._get_class()
    return self._cls

  @cls.setter
  def cls(self, cls):
    self._cls = cls

  def set_class(self, node, var):
    """Set the __class__ of an instance, for code that does "x.__class__ = y."""
    # Simplification: Setting __class__ is done rarely, and supporting this
    # action would complicate pytype considerably by forcing us to track the
    # class in a variable, so we instead fall back to Any.
    try:
      new_cls = abstract_utils.get_atomic_value(var)
    except abstract_utils.ConversionError:
      self.cls = self.ctx.convert.unsolvable
    else:
      if self.cls != new_cls:
        self.cls = self.ctx.convert.unsolvable
    return node

  def get_type_key(self, seen=None):
    cached_changestamps, saved_key = self._cached_type_key
    if saved_key and cached_changestamps == (
        self.members.changestamp,
        self.instance_type_parameters.changestamp):
      return saved_key
    if not seen:
      seen = set()
    seen.add(self)
    key = {self.cls}
    for name, var in self.instance_type_parameters.items():
      subkey = frozenset(
          value.data.get_default_type_key()  # pylint: disable=g-long-ternary
          if value.data in seen else value.data.get_type_key(seen)
          for value in var.bindings)
      key.add((name, subkey))
    if key:
      type_key = frozenset(key)
    else:
      type_key = super().get_type_key()
    self._cached_type_key = (
        (self.members.changestamp, self.instance_type_parameters.changestamp),
        type_key)
    return type_key

  def _unique_parameters(self):
    parameters = super()._unique_parameters()
    parameters.extend(self.instance_type_parameters.values())
    return parameters

  def instantiate(self, node, container=None):
    return Instance.from_value(self, container).to_variable(node)


class Instance(SimpleValue):
  """An instance of some object."""

  @classmethod
  def from_value(cls, value, container=None):
    return cls(value, value.ctx, container=container)

  def __init__(self, cls, ctx, container=None):
    super().__init__(cls.name, ctx)
    self.cls = cls
    self._instance_type_parameters_loaded = False
    self._container = container
    cls.register_instance(self)

  def _load_instance_type_parameters(self):
    if self._instance_type_parameters_loaded:
      return
    all_formal_type_parameters = datatypes.AliasingMonitorDict()
    abstract_utils.parse_formal_type_parameters(
        self.cls, None, all_formal_type_parameters, self._container)
    self._instance_type_parameters.uf = all_formal_type_parameters.uf
    for name, param in all_formal_type_parameters.items():
      if param is None:
        value = self.ctx.program.NewVariable()
        log.info("Initializing type param %s: %r", name, value)
        self._instance_type_parameters[name] = value
      else:
        self._instance_type_parameters[name] = param.instantiate(
            self.ctx.root_node, self._container or self)
    # We purposely set this flag at the very end so that accidentally accessing
    # instance_type_parameters during loading will trigger an obvious crash due
    # to infinite recursion, rather than silently returning an incomplete dict.
    self._instance_type_parameters_loaded = True

  @property
  def full_name(self):
    return self.cls.full_name

  @property
  def instance_type_parameters(self):
    self._load_instance_type_parameters()
    return self._instance_type_parameters


class List(Instance, mixin.HasSlots, mixin.PythonConstant):
  """Representation of Python 'list' objects."""

  def __init__(self, content, ctx):
    super().__init__(ctx.convert.list_type, ctx)
    self._instance_cache = {}
    mixin.PythonConstant.init_mixin(self, content)
    mixin.HasSlots.init_mixin(self)
    combined_content = ctx.convert.build_content(content)
    self.merge_instance_type_parameter(None, abstract_utils.T, combined_content)
    self.could_contain_anything = False
    self.set_slot("__getitem__", self.getitem_slot)
    self.set_slot("__getslice__", self.getslice_slot)

  def str_of_constant(self, printer):
    return "[%s]" % ", ".join(" or ".join(abstract_utils.var_map(printer, val))
                              for val in self.pyval)

  def __repr__(self):
    if self.could_contain_anything:
      return Instance.__repr__(self)
    else:
      return mixin.PythonConstant.__repr__(self)

  def merge_instance_type_parameter(self, node, name, value):
    self.could_contain_anything = True
    super().merge_instance_type_parameter(node, name, value)

  def getitem_slot(self, node, index_var):
    """Implements __getitem__ for List.

    Arguments:
      node: The current CFG node.
      index_var: The Variable containing the index value, the i in lst[i].

    Returns:
      Tuple of (node, return_variable). node may be the same as the argument.
      return_variable is a Variable with bindings of the possible return values.
    """
    results = []
    unresolved = False
    node, ret = self.call_pytd(node, "__getitem__", index_var)
    if not self.could_contain_anything:
      for val in index_var.bindings:
        try:
          index = self.ctx.convert.value_to_constant(val.data, int)
        except abstract_utils.ConversionError:
          unresolved = True
        else:
          self_len = len(self.pyval)
          if -self_len <= index < self_len:
            results.append(self.pyval[index])
          else:
            unresolved = True
    if unresolved or self.could_contain_anything:
      results.append(ret)
    return node, self.ctx.join_variables(node, results)

  def _get_index(self, data):
    """Helper function for getslice_slot that extracts int or None from data.

    If data is an Instance of int, None is returned.

    Args:
      data: The object to extract from. Usually a ConcreteValue or an
        Instance.

    Returns:
      The value (an int or None) of the index.

    Raises:
      abstract_utils.ConversionError: If the data could not be converted.
    """
    if isinstance(data, ConcreteValue):
      return self.ctx.convert.value_to_constant(data, (int, type(None)))
    elif isinstance(data, Instance):
      if data.cls != self.ctx.convert.int_type:
        raise abstract_utils.ConversionError()
      else:
        return None
    else:
      raise abstract_utils.ConversionError()

  def getslice_slot(self, node, start_var, end_var):
    """Implements __getslice__ for List.

    Arguments:
      node: The current CFG node.
      start_var: A Variable containing the i in lst[i:j].
      end_var: A Variable containing the j in lst[i:j].

    Returns:
      Tuple of (node, return_variable). node may be the same as the argument.
      return_variable is a Variable with bindings of the possible return values.
    """
    # call_pytd will typecheck start_var and end_var.
    node, ret = self.call_pytd(node, "__getslice__", start_var, end_var)
    results = []
    unresolved = False
    if not self.could_contain_anything:
      for start_val, end_val in cfg_utils.variable_product([start_var,
                                                            end_var]):
        try:
          start = self._get_index(start_val.data)
          end = self._get_index(end_val.data)
        except abstract_utils.ConversionError:
          unresolved = True
        else:
          results.append(
              List(self.pyval[start:end], self.ctx).to_variable(node))
    if unresolved or self.could_contain_anything:
      results.append(ret)
    return node, self.ctx.join_variables(node, results)


class Tuple(Instance, mixin.PythonConstant):
  """Representation of Python 'tuple' objects."""

  def __init__(self, content, ctx):
    combined_content = ctx.convert.build_content(content)
    class_params = {
        name: ctx.convert.merge_classes(instance_param.data)
        for name, instance_param in tuple(enumerate(content)) +
        ((abstract_utils.T, combined_content),)
    }
    cls = TupleClass(ctx.convert.tuple_type, class_params, ctx)
    super().__init__(cls, ctx)
    self.merge_instance_type_parameter(None, abstract_utils.T, combined_content)
    mixin.PythonConstant.init_mixin(self, content)
    self.tuple_length = len(self.pyval)
    self._hash = None  # memoized due to expensive computation
    # set this to true when creating a function arg tuple
    self.is_unpacked_function_args = False

  def str_of_constant(self, printer):
    content = ", ".join(" or ".join(abstract_utils.var_map(printer, val))
                        for val in self.pyval)
    if self.tuple_length == 1:
      content += ","
    return "(%s)" % content

  def _unique_parameters(self):
    parameters = super()._unique_parameters()
    parameters.extend(self.pyval)
    return parameters

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return (self.tuple_length == other.tuple_length and
              all(e.data == other_e.data
                  for e, other_e in zip(self.pyval, other.pyval)))
    return NotImplemented

  def __hash__(self):
    if self._hash is None:
      # Descending into pyval would trigger infinite recursion in the case of a
      # tuple containing itself, so we approximate the inner values with their
      # full names.
      approximate_hash = lambda var: tuple(v.full_name for v in var.data)
      self._hash = hash((self.tuple_length,) +
                        tuple(approximate_hash(e) for e in self.pyval))
    return self._hash


class Dict(Instance, mixin.HasSlots, mixin.PythonDict):
  """Representation of Python 'dict' objects.

  It works like builtins.dict, except that, for string keys, it keeps track
  of what got stored.
  """

  def __init__(self, ctx):
    super().__init__(ctx.convert.dict_type, ctx)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__contains__", self.contains_slot)
    self.set_slot("__getitem__", self.getitem_slot)
    self.set_slot("__setitem__", self.setitem_slot)
    self.set_slot("pop", self.pop_slot)
    self.set_slot("setdefault", self.setdefault_slot)
    self.set_slot("update", self.update_slot)
    self.could_contain_anything = False
    # Use OrderedDict instead of dict, so that it can be compatible with
    # where needs ordered dict.
    # For example: f_locals["__annotations__"]
    mixin.PythonDict.init_mixin(self, collections.OrderedDict())

  def str_of_constant(self, printer):
    return str({name: " or ".join(abstract_utils.var_map(printer, value))
                for name, value in self.pyval.items()})

  def __repr__(self):
    if not hasattr(self, "could_contain_anything"):
      return "Dict (not fully initialized)"
    elif self.could_contain_anything:
      return Instance.__repr__(self)
    else:
      return mixin.PythonConstant.__repr__(self)

  def getitem_slot(self, node, name_var):
    """Implements the __getitem__ slot."""
    results = []
    unresolved = False
    if not self.could_contain_anything:
      for val in name_var.bindings:
        try:
          name = self.ctx.convert.value_to_constant(val.data, str)
        except abstract_utils.ConversionError:
          unresolved = True
        else:
          try:
            results.append(self.pyval[name])
          except KeyError as e:
            unresolved = True
            raise function.DictKeyMissing(name) from e
    node, ret = self.call_pytd(node, "__getitem__", name_var)
    if unresolved or self.could_contain_anything:
      # We *do* know the overall type of the values through the "V" type
      # parameter, even if we don't know the exact type of self[name]. So let's
      # just use the (less accurate) value from pytd.
      results.append(ret)
    return node, self.ctx.join_variables(node, results)

  def set_str_item(self, node, name, value_var):
    self.merge_instance_type_parameter(
        node, abstract_utils.K, self.ctx.convert.build_string(node, name))
    self.merge_instance_type_parameter(node, abstract_utils.V, value_var)
    if name in self.pyval:
      self.pyval[name].PasteVariable(value_var, node)
    else:
      self.pyval[name] = value_var
    return node

  def setitem(self, node, name_var, value_var):
    assert isinstance(name_var, cfg.Variable)
    assert isinstance(value_var, cfg.Variable)
    for val in name_var.bindings:
      try:
        name = self.ctx.convert.value_to_constant(val.data, str)
      except abstract_utils.ConversionError:
        # Now the dictionary is abstract: We don't know what it contains
        # anymore. Note that the below is not a variable, so it'll affect
        # all branches.
        self.could_contain_anything = True
        continue
      if name in self.pyval:
        self.pyval[name].PasteVariable(value_var, node)
      else:
        self.pyval[name] = value_var

  def setitem_slot(self, node, name_var, value_var):
    """Implements the __setitem__ slot."""
    self.setitem(node, name_var, value_var)
    return self.call_pytd(node, "__setitem__", name_var, value_var)

  def setdefault_slot(self, node, name_var, value_var=None):
    if value_var is None:
      value_var = self.ctx.convert.build_none(node)
    # We don't have a good way of modelling the exact setdefault behavior -
    # whether the key already exists might depend on a code path, so setting it
    # again should depend on an if-splitting condition, but we don't support
    # negative conditions.
    self.setitem(node, name_var, value_var)
    return self.call_pytd(node, "setdefault", name_var, value_var)

  def contains_slot(self, node, key_var):
    if self.could_contain_anything:
      value = None
    else:
      try:
        str_key = abstract_utils.get_atomic_python_constant(key_var, str)
      except abstract_utils.ConversionError:
        value = None
      else:
        value = str_key in self.pyval
    return node, self.ctx.convert.build_bool(node, value)

  def pop_slot(self, node, key_var, default_var=None):
    try:
      str_key = abstract_utils.get_atomic_python_constant(key_var, str)
    except abstract_utils.ConversionError:
      self.could_contain_anything = True
    if self.could_contain_anything:
      if default_var:
        return self.call_pytd(node, "pop", key_var, default_var)
      else:
        return self.call_pytd(node, "pop", key_var)
    if default_var:
      return node, self.pyval.pop(str_key, default_var)
    else:
      try:
        return node, self.pyval.pop(str_key)
      except KeyError as e:
        raise function.DictKeyMissing(str_key) from e

  def update_slot(self, node, *args, **kwargs):
    posargs_handled = False
    if len(args) == 1:
      arg_data = args[0].data
      if len(arg_data) == 1:
        self.update(node, arg_data[0])
        posargs_handled = True
    elif not args:
      posargs_handled = True
    self.update(node, kwargs)
    if not posargs_handled:
      self.could_contain_anything = True
      return self.call_pytd(node, "update", *args)
    else:
      return node, self.ctx.convert.none.to_variable(node)

  def update(self, node, other_dict, omit=()):
    if isinstance(other_dict, (Dict, dict)):
      for key, value in other_dict.items():
        if key not in omit:
          self.set_str_item(node, key, value)
      if isinstance(other_dict, Dict):
        k = other_dict.get_instance_type_parameter(abstract_utils.K, node)
        v = other_dict.get_instance_type_parameter(abstract_utils.V, node)
        self.merge_instance_type_parameter(node, abstract_utils.K, k)
        self.merge_instance_type_parameter(node, abstract_utils.V, v)
        self.could_contain_anything |= other_dict.could_contain_anything
    else:
      assert isinstance(other_dict, BaseValue)
      if (isinstance(other_dict, Instance) and
          other_dict.full_name == "builtins.dict"):
        k = other_dict.get_instance_type_parameter(abstract_utils.K, node)
        v = other_dict.get_instance_type_parameter(abstract_utils.V, node)
      else:
        k = v = self.ctx.new_unsolvable(node)
      self.merge_instance_type_parameter(node, abstract_utils.K, k)
      self.merge_instance_type_parameter(node, abstract_utils.V, v)
      self.could_contain_anything = True


class AnnotationsDict(Dict):
  """__annotations__ dict."""

  def __init__(self, annotated_locals, ctx):
    super().__init__(ctx)
    self.annotated_locals = annotated_locals

  def get_type(self, node, name):
    if name not in self.annotated_locals:
      return None
    return self.annotated_locals[name].get_type(node, name)

  def get_annotations(self, node):
    for name, local in self.annotated_locals.items():
      typ = local.get_type(node, name)
      if typ:
        yield name, typ

  def __repr__(self):
    return repr(self.annotated_locals)


class LateAnnotation:
  """A late annotation.

  A late annotation stores a string expression and a snapshot of the VM stack at
  the point where the annotation was introduced. Once the expression is
  resolved, the annotation pretends to be the resolved type; before that, it
  pretends to be an unsolvable. This effect is achieved by delegating attribute
  lookup with __getattribute__.

  Note that for late annotation x, `isinstance(x, ...)` and `x.__class__` will
  use the type that x is pretending to be; `type(x)` will reveal x's true type.
  Use `x.is_late_annotation()` to check whether x is a late annotation.
  """

  def __init__(self, expr, stack, ctx):
    self.expr = expr
    self.stack = stack
    self.ctx = ctx
    self.resolved = False
    self._type = ctx.convert.unsolvable  # the resolved type of `expr`
    self._unresolved_instances = set()
    # _attribute_names needs to be defined last!
    self._attribute_names = (
        set(LateAnnotation.__dict__) |
        set(super().__getattribute__("__dict__")))

  def __repr__(self):
    return "LateAnnotation(%r, resolved=%r)" % (
        self.expr, self._type if self.resolved else None)

  # __hash__ and __eq__ need to be explicitly defined for Python to use them in
  # set/dict comparisons.

  def __hash__(self):
    return hash(self._type) if self.resolved else hash(self.expr)

  def __eq__(self, other):
    return hash(self) == hash(other)

  def __getattribute__(self, name):
    if name == "_attribute_names" or name in self._attribute_names:
      return super().__getattribute__(name)
    return self._type.__getattribute__(name)

  def resolve(self, node, f_globals, f_locals):
    """Resolve the late annotation."""
    if self.resolved:
      return
    self.resolved = True
    var, errorlog = abstract_utils.eval_expr(self.ctx, node, f_globals,
                                             f_locals, self.expr)
    if errorlog:
      self.ctx.errorlog.copy_from(errorlog.errors, self.stack)
    self._type = self.ctx.annotation_utils.extract_annotation(
        node, var, None, self.stack)
    if self._type != self.ctx.convert.unsolvable:
      # We may have tried to call __init__ on instances of this annotation.
      # Since the annotation was unresolved at the time, we need to call
      # __init__ again to define any instance attributes.
      for instance in self._unresolved_instances:
        if isinstance(instance.cls, Union):
          # Having instance.cls be a Union type will crash in attribute.py.
          # Setting it to Any picks up the annotation in another code path.
          instance.cls = self.ctx.convert.unsolvable
        else:
          self.ctx.vm.reinitialize_if_initialized(node, instance)
    log.info("Resolved late annotation %r to %r", self.expr, self._type)

  def set_type(self, typ):
    # Used by annotation_utils.sub_one_annotation to substitute values into
    # recursive aliases.
    assert not self.resolved
    self.resolved = True
    self._type = typ

  def to_variable(self, node):
    if self.resolved:
      return self._type.to_variable(node)
    else:
      return BaseValue.to_variable(self, node)

  def instantiate(self, node, container=None):
    """Instantiate the pointed-to class, or record a placeholder instance."""
    if self.resolved:
      return self._type.instantiate(node, container)
    else:
      instance = Instance(self, self.ctx)
      self._unresolved_instances.add(instance)
      return instance.to_variable(node)

  def get_special_attribute(self, node, name, valself):
    if name == "__getitem__" and not self.resolved:
      container = AnnotationContainer.from_value(self)
      return container.get_special_attribute(node, name, valself)
    return self._type.get_special_attribute(node, name, valself)

  def is_late_annotation(self):
    return True


class AnnotationClass(SimpleValue, mixin.HasSlots):
  """Base class of annotations that can be parameterized."""

  def __init__(self, name, ctx):
    super().__init__(name, ctx)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)

  def getitem_slot(self, node, slice_var):
    """Custom __getitem__ implementation."""
    slice_content = abstract_utils.maybe_extract_tuple(slice_var)
    inner, ellipses = self._build_inner(slice_content)
    value = self._build_value(node, tuple(inner), ellipses)
    return node, value.to_variable(node)

  def _build_inner(self, slice_content):
    """Build the list of parameters.

    Args:
      slice_content: The iterable of variables to extract parameters from.

    Returns:
      A tuple of a list of parameters and a set of indices at which an ellipsis
        was replaced with Any.
    """
    inner = []
    ellipses = set()
    for var in slice_content:
      if len(var.bindings) > 1:
        self.ctx.errorlog.ambiguous_annotation(self.ctx.vm.frames, var.data)
        inner.append(self.ctx.convert.unsolvable)
      else:
        val = var.bindings[0].data
        if val is self.ctx.convert.ellipsis:
          # Ellipses are allowed only in special cases, so turn them into Any
          # but record the indices so we can check if they're legal.
          ellipses.add(len(inner))
          inner.append(self.ctx.convert.unsolvable)
        else:
          inner.append(val)
    return inner, ellipses

  def _build_value(self, node, inner, ellipses):
    raise NotImplementedError(self.__class__.__name__)

  def __repr__(self):
    return "AnnotationClass(%s)" % self.name


class AnnotationContainer(AnnotationClass):
  """Implementation of X[...] for annotations."""

  @classmethod
  def from_value(cls, value):
    if isinstance(value, PyTDClass) and value.full_name == "builtins.tuple":
      # If we are parameterizing builtins.tuple, replace it with typing.Tuple so
      # that heterogeneous tuple annotations work. We need the isinstance()
      # check to distinguish PyTDClass(tuple) from ParameterizedClass(tuple);
      # the latter appears here when a generic type alias is being substituted.
      typing = value.ctx.vm.import_module("typing", "typing",
                                          0).get_module("Tuple")
      typing.load_lazy_attribute("Tuple")
      return abstract_utils.get_atomic_value(typing.members["Tuple"])
    return cls(value.name, value.ctx, value)

  def __init__(self, name, ctx, base_cls):
    super().__init__(name, ctx)
    self.base_cls = base_cls

  def _sub_annotation(
      self, annot: BaseValue, subst: Mapping[str, BaseValue]) -> BaseValue:
    """Apply type parameter substitutions to an annotation."""
    # This is very similar to annotation_utils.sub_one_annotation, but a couple
    # differences make it more convenient to maintain two separate methods:
    # - subst here is a str->BaseValue mapping rather than str->Variable, and it
    #   would be wasteful to create variables just to match sub_one_annotation's
    #   expected input type.
    # - subst contains the type to be substituted in, not an instance of it.
    #   Again, instantiating the type just to later get the type of the instance
    #   is unnecessary extra work.
    if isinstance(annot, TypeParameter):
      if annot.full_name in subst:
        return subst[annot.full_name]
      else:
        return self.ctx.convert.unsolvable
    elif isinstance(annot, mixin.NestedAnnotation):
      inner_types = [(key, self._sub_annotation(val, subst))
                     for key, val in annot.get_inner_types()]
      return annot.replace(inner_types)
    return annot

  def _get_value_info(self, inner, ellipses, allowed_ellipses=frozenset()):
    """Get information about the container's inner values.

    Args:
      inner: The list of parameters from _build_inner().
      ellipses: The set of ellipsis indices from _build_inner().
      allowed_ellipses: Optionally, a set of indices at which ellipses are
        allowed. If omitted, ellipses are assumed to be never allowed.

    Returns:
      A tuple of the template, the parameters, and the container class.
    """
    if self.base_cls.full_name == "typing.Protocol":
      return abstract_utils.build_generic_template(inner, self) + (
          ParameterizedClass,)
    if isinstance(self.base_cls, TupleClass):
      template = tuple(range(self.base_cls.tuple_length))
    elif isinstance(self.base_cls, CallableClass):
      template = tuple(range(self.base_cls.num_args)) + (abstract_utils.RET,)
    else:
      template = tuple(t.name for t in self.base_cls.template)
    self.ctx.errorlog.invalid_ellipses(self.ctx.vm.frames,
                                       ellipses - allowed_ellipses, self.name)
    last_index = len(inner) - 1
    if last_index and last_index in ellipses and len(inner) > len(template):
      # Even if an ellipsis is not allowed at this position, strip it off so
      # that we report only one error for something like 'List[int, ...]'
      inner = inner[:-1]
    if isinstance(self.base_cls, ParameterizedClass):
      # We're dealing with a generic type alias, e.g.:
      #   X = Dict[T, str]
      #   def f(x: X[int]): ...
      # We construct `inner` using both the new inner values and the ones
      # already in X, to end up with a final result of:
      #   template=(_K, _V)
      #   inner=(int, str)
      new_inner = []
      inner_idx = 0
      subst = {}
      # Note that we ignore any missing or extra values in inner for now; the
      # problem will be reported later by _validate_inner.
      for k in template:
        v = self.base_cls.formal_type_parameters[k]
        if v.formal:
          params = self.ctx.annotation_utils.get_type_parameters(v)
          for param in params:
            # If there are too few parameters, we ignore the problem for now;
            # it'll be reported when _build_value checks that the lengths of
            # template and inner match.
            if param.full_name not in subst and inner_idx < len(inner):
              subst[param.full_name] = inner[inner_idx]
              inner_idx += 1
          new_inner.append(self._sub_annotation(v, subst))
        else:
          new_inner.append(v)
      inner = tuple(new_inner)
      if isinstance(self.base_cls, TupleClass):
        template += (abstract_utils.T,)
        inner += (self.ctx.convert.merge_values(inner),)
      elif isinstance(self.base_cls, CallableClass):
        template = template[:-1] + (abstract_utils.ARGS,) + template[-1:]
        args = inner[:-1]
        inner = args + (self.ctx.convert.merge_values(args),) + inner[-1:]
      abstract_class = type(self.base_cls)
    else:
      abstract_class = ParameterizedClass
    return template, inner, abstract_class

  def _validate_inner(self, template, inner, raw_inner):
    """Check that the passed inner values are valid for the given template."""
    if (isinstance(self.base_cls, ParameterizedClass) and
        not abstract_utils.is_generic_protocol(self.base_cls)):
      # For a generic type alias, we check that the number of typevars in the
      # alias matches the number of raw parameters provided.
      template_length = raw_template_length = len(
          set(self.ctx.annotation_utils.get_type_parameters(self.base_cls)))
      inner_length = raw_inner_length = len(raw_inner)
      base_cls = self.base_cls.base_cls
    else:
      # In all other cases, we check that the final template length and
      # parameter count match, after any adjustments like flattening the inner
      # argument list in a Callable.
      template_length = len(template)
      raw_template_length = len(self.base_cls.template)
      inner_length = len(inner)
      raw_inner_length = len(raw_inner)
      base_cls = self.base_cls
    if inner_length != template_length:
      if not template:
        self.ctx.errorlog.not_indexable(
            self.ctx.vm.frames, base_cls.name, generic_warning=True)
      else:
        # Use the unprocessed values of `template` and `inner` so that the error
        # message matches what the user sees.
        name = "%s[%s]" % (
            self.full_name, ", ".join(t.name for t in base_cls.template))
        error = "Expected %d parameter(s), got %d" % (
            raw_template_length, raw_inner_length)
        self.ctx.errorlog.invalid_annotation(self.ctx.vm.frames, None, error,
                                             name)
    else:
      if len(inner) == 1:
        val, = inner
        # It's a common mistake to index a container class rather than an
        # instance (e.g., list[0]).
        # We only check the "int" case, since string literals are allowed for
        # late annotations.
        if (isinstance(val, Instance) and val.cls == self.ctx.convert.int_type):
          # Don't report this error again.
          inner = (self.ctx.convert.unsolvable,)
          self.ctx.errorlog.not_indexable(self.ctx.vm.frames, self.name)
    return inner

  def _build_value(self, node, inner, ellipses):
    if self.base_cls.is_late_annotation():
      # A parameterized LateAnnotation should be converted to another
      # LateAnnotation to delay evaluation until the first late annotation is
      # resolved. We don't want to create a ParameterizedClass immediately
      # because (1) ParameterizedClass expects its base_cls to be a
      # class_mixin.Class, and (2) we have to postpone error-checking anyway so
      # we might as well postpone the entire evaluation.
      printed_params = []
      for i, param in enumerate(inner):
        if i in ellipses:
          printed_params.append("...")
        else:
          printed_params.append(pytd_utils.Print(param.get_instance_type(node)))
      expr = "%s[%s]" % (self.base_cls.expr, ", ".join(printed_params))
      annot = LateAnnotation(expr, self.base_cls.stack, self.ctx)
      self.ctx.vm.late_annotations[self.base_cls.expr].append(annot)
      return annot
    template, processed_inner, abstract_class = self._get_value_info(
        inner, ellipses)
    if isinstance(self.base_cls, ParameterizedClass):
      base_cls = self.base_cls.base_cls
    else:
      base_cls = self.base_cls
    if base_cls.full_name in ("typing.Generic", "typing.Protocol"):
      # Generic is unique in that parameterizing it defines a new template;
      # usually, the parameterized class inherits the base class's template.
      # Protocol[T, ...] is a shorthand for Protocol, Generic[T, ...].
      template_params = [
          param.with_module(base_cls.full_name) for param in processed_inner]
    else:
      template_params = None
    processed_inner = self._validate_inner(template, processed_inner, inner)
    params = {
        name: (processed_inner[i]
               if i < len(processed_inner) else self.ctx.convert.unsolvable)
        for i, name in enumerate(template)
    }

    # For user-defined generic types, check if its type parameter matches
    # its corresponding concrete type
    if isinstance(base_cls, InterpreterClass) and base_cls.template:
      for formal_param in base_cls.template:
        root_node = self.ctx.root_node
        param_value = params[formal_param.name]
        if (isinstance(formal_param, TypeParameter) and
            not formal_param.is_generic() and
            isinstance(param_value, TypeParameter)):
          if formal_param.name == param_value.name:
            # We don't need to check if a TypeParameter matches itself.
            continue
          else:
            actual = param_value.instantiate(
                root_node, container=abstract_utils.DUMMY_CONTAINER)
        else:
          actual = param_value.instantiate(root_node)
        bad = self.ctx.matcher(root_node).bad_matches(actual, formal_param)
        if bad:
          if not isinstance(param_value, TypeParameter):
            # If param_value is not a TypeVar, we substitute in TypeVar bounds
            # and constraints in formal_param for a more helpful error message.
            formal_param = self.ctx.annotation_utils.sub_one_annotation(
                root_node, formal_param, [{}])
            details = None
          elif isinstance(formal_param, TypeParameter):
            details = (f"TypeVars {formal_param.name} and {param_value.name} "
                       "have incompatible bounds or constraints.")
          else:
            details = None
          self.ctx.errorlog.bad_concrete_type(
              self.ctx.vm.frames, root_node, formal_param, actual, bad, details)
          return self.ctx.convert.unsolvable

    try:
      return abstract_class(base_cls, params, self.ctx, template_params)
    except abstract_utils.GenericTypeError as e:
      self.ctx.errorlog.invalid_annotation(self.ctx.vm.frames, e.annot, e.error)
      return self.ctx.convert.unsolvable


class ConcreteValue(Instance, mixin.PythonConstant):
  """Abstract value with a concrete fallback."""

  def __init__(self, pyval, cls, ctx):
    super().__init__(cls, ctx)
    mixin.PythonConstant.init_mixin(self, pyval)


class LazyConcreteDict(SimpleValue, mixin.PythonConstant, mixin.LazyMembers):
  """Dictionary with lazy values."""

  def __init__(self, name, member_map, ctx):
    super().__init__(name, ctx)
    mixin.PythonConstant.init_mixin(self, self.members)
    mixin.LazyMembers.init_mixin(self, member_map)

  def _convert_member(self, member, subst=None):
    return self.ctx.convert.constant_to_var(member)

  def is_empty(self):
    return not bool(self._member_map)


class Union(BaseValue, mixin.NestedAnnotation, mixin.HasSlots):
  """A list of types.

  Used for parameter matching.

  Attributes:
    options: Iterable of instances of BaseValue.
  """

  def __init__(self, options, ctx):
    super().__init__("Union", ctx)
    assert options
    self.options = list(options)
    self.cls = self._get_class()
    self.formal = any(t.formal for t in self.options)
    mixin.NestedAnnotation.init_mixin(self)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)
    self._printing = False

  def __repr__(self):
    if self._printing:  # recursion detected
      printed_contents = "..."
    else:
      self._printing = True
      printed_contents = ", ".join(repr(o) for o in self.options)
      self._printing = False
    return "%s[%s]" % (self.name, printed_contents)

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return self.options == other.options
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def __hash__(self):
    return hash(tuple(self.options))

  def _unique_parameters(self):
    return [o.to_variable(self.ctx.root_node) for o in self.options]

  def _get_type_params(self):
    params = self.ctx.annotation_utils.get_type_parameters(self)
    params = [x.full_name for x in params]
    return utils.unique_list(params)

  def _get_class(self):
    classes = {o.cls for o in self.options}
    if len(classes) > 1:
      return self.ctx.convert.unsolvable
    else:
      return classes.pop()

  def getitem_slot(self, node, slice_var):
    """Custom __getitem__ implementation."""
    slice_content = abstract_utils.maybe_extract_tuple(slice_var)
    params = self._get_type_params()
    # Check that we are instantiating all the unbound type parameters
    if len(params) != len(slice_content):
      details = ("Union has %d type parameters but was instantiated with %d" %
                 (len(params), len(slice_content)))
      self.ctx.errorlog.invalid_annotation(
          self.ctx.vm.frames, self, details=details)
      return node, self.ctx.new_unsolvable(node)
    concrete = []
    for var in slice_content:
      value = var.data[0]
      if value.formal:
        concrete.append(value.to_variable(node))
      else:
        concrete.append(value.instantiate(node))
    substs = [dict(zip(params, concrete))]
    new = self.ctx.annotation_utils.sub_one_annotation(node, self, substs)
    return node, new.to_variable(node)

  def instantiate(self, node, container=None):
    var = self.ctx.program.NewVariable()
    for option in self.options:
      var.PasteVariable(option.instantiate(node, container), node)
    return var

  def call(self, node, func, args, alias_map=None):
    var = self.ctx.program.NewVariable(self.options, [], node)
    return function.call_function(self.ctx, node, var, args)

  def get_formal_type_parameter(self, t):
    new_options = [option.get_formal_type_parameter(t)
                   for option in self.options]
    return Union(new_options, self.ctx)

  def get_inner_types(self):
    return enumerate(self.options)

  def update_inner_type(self, key, typ):
    self.options[key] = typ

  def replace(self, inner_types):
    return self.__class__((v for _, v in sorted(inner_types)), self.ctx)


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


class ParameterizedClass(BaseValue, class_mixin.Class, mixin.NestedAnnotation):
  """A class that contains additional parameters.

  E.g. a container.

  Attributes:
    cls: A PyTDClass representing the base type.
    formal_type_parameters: An iterable of BaseValue, one for each type
      parameter.
  """

  @classmethod
  def get_generic_instance_type(cls, base_cls):
    """This is used to annotate the `self` in a class."""
    assert base_cls.template
    formal_type_parameters = {}
    for item in base_cls.template:
      formal_type_parameters[item.name] = item
    return cls(base_cls, formal_type_parameters, base_cls.ctx)

  def __init__(self, base_cls, formal_type_parameters, ctx, template=None):
    # A ParameterizedClass is created by converting a pytd.GenericType, whose
    # base type is restricted to NamedType and ClassType.
    assert isinstance(base_cls, (PyTDClass, InterpreterClass))
    self.base_cls = base_cls
    super().__init__(base_cls.name, ctx)
    self._cls = None  # lazily loaded 'cls' attribute
    self.module = base_cls.module
    # Lazily loaded to handle recursive types.
    # See the formal_type_parameters() property.
    self._formal_type_parameters = formal_type_parameters
    self._formal_type_parameters_loaded = False
    self._hash = None  # memoized due to expensive computation
    self.official_name = self.base_cls.official_name
    if template is None:
      self._template = self.base_cls.template
    else:
      # The ability to create a new template different from the base class's is
      # needed for typing.Generic.
      self._template = template
    self.slots = self.base_cls.slots
    self.is_dynamic = self.base_cls.is_dynamic
    class_mixin.Class.init_mixin(
        self, base_cls.cls, Instance, AnnotationContainer)
    mixin.NestedAnnotation.init_mixin(self)
    self.type_param_check()

  def __repr__(self):
    return "ParameterizedClass(cls=%r params=%s)" % (
        self.base_cls,
        self.formal_type_parameters)

  def type_param_check(self):
    """Throw exception for invalid type parameters."""
    # It will cause infinite recursion if `formal_type_parameters` is
    # `LazyFormalTypeParameters`
    if not isinstance(self._formal_type_parameters,
                      abstract_utils.LazyFormalTypeParameters):
      tparams = datatypes.AliasingMonitorDict()
      abstract_utils.parse_formal_type_parameters(self, None, tparams)

  def get_formal_type_parameters(self):
    return {abstract_utils.full_type_name(self, k): v
            for k, v in self.formal_type_parameters.items()}

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return self.base_cls == other.base_cls and (
          self.formal_type_parameters == other.formal_type_parameters)
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def __hash__(self):
    if self._hash is None:
      if isinstance(self._formal_type_parameters,
                    abstract_utils.LazyFormalTypeParameters):
        items = tuple(self._raw_formal_type_parameters())
      else:
        # Use the names of the parameter values to approximate a hash, to avoid
        # infinite recursion on recursive type annotations.
        items = tuple((name, val.full_name)
                      for name, val in self.formal_type_parameters.items())
      self._hash = hash((self.base_cls, items))
    return self._hash

  def __contains__(self, name):
    return name in self.base_cls

  def _raw_formal_type_parameters(self):
    assert isinstance(self._formal_type_parameters,
                      abstract_utils.LazyFormalTypeParameters)
    template, parameters, _ = self._formal_type_parameters
    for i, name in enumerate(template):
      # TODO(rechen): A missing parameter should be an error.
      yield name, parameters[i] if i < len(parameters) else None

  def get_own_attributes(self):
    return self.base_cls.get_own_attributes()

  def get_own_abstract_methods(self):
    return self.base_cls.get_own_abstract_methods()

  @property
  def members(self):
    return self.base_cls.members

  @property
  def formal(self):
    # We can't compute self.formal in __init__ because doing so would force
    # evaluation of our type parameters during initialization, possibly
    # leading to an infinite loop.
    return any(t.formal for t in self.formal_type_parameters.values())

  @property
  def formal_type_parameters(self):
    self._load_formal_type_parameters()
    return self._formal_type_parameters

  def _load_formal_type_parameters(self):
    if self._formal_type_parameters_loaded:
      return
    if isinstance(self._formal_type_parameters,
                  abstract_utils.LazyFormalTypeParameters):
      formal_type_parameters = {}
      for name, param in self._raw_formal_type_parameters():
        if param is None:
          formal_type_parameters[name] = self.ctx.convert.unsolvable
        else:
          formal_type_parameters[name] = self.ctx.convert.constant_to_value(
              param, self._formal_type_parameters.subst, self.ctx.root_node)
      self._formal_type_parameters = formal_type_parameters
    # Hack: we'd like to evaluate annotations at the currently active node so
    # that imports, etc., are visible. The last created node is usually the
    # active one.
    self._formal_type_parameters = (
        self.ctx.annotation_utils.convert_class_annotations(
            self.ctx.program.cfg_nodes[-1], self._formal_type_parameters))
    self._formal_type_parameters_loaded = True

  def compute_mro(self):
    return (self,) + self.base_cls.mro[1:]

  def instantiate(self, node, container=None):
    if self.full_name == "builtins.type":
      # deformalize removes TypeVars.
      instance = self.ctx.annotation_utils.deformalize(
          self.formal_type_parameters[abstract_utils.T])
      return instance.to_variable(node)
    elif self.full_name == "typing.ClassVar":
      return self.formal_type_parameters[abstract_utils.T].instantiate(
          node, container)
    else:
      return self._new_instance(container, node, None).to_variable(node)

  @property
  def cls(self):
    if not self.ctx.converter_minimally_initialized:
      return self.ctx.convert.unsolvable
    if not self._cls:
      self._cls = self.base_cls.cls
    return self._cls

  @cls.setter
  def cls(self, cls):
    self._cls = cls

  def set_class(self, node, var):
    self.base_cls.set_class(node, var)

  def _is_callable(self):
    if not isinstance(self.base_cls, (InterpreterClass, PyTDClass)):
      # We don't know how to instantiate this base_cls.
      return False
    if self.from_annotation:
      # A user-provided annotation is always instantiable.
      return True
    # Otherwise, non-abstract classes are instantiable. The exception is
    # typing classes; for example,
    #   from typing import List
    #   print(List[str]())
    # produces 'TypeError: Type List cannot be instantiated; use list() instead'
    # at runtime. We also disallow the builtins module because pytype represents
    # concrete typing classes like List with their builtins equivalents.
    return not self.is_abstract and self.module not in ("builtins", "typing")

  def call(self, node, func, args, alias_map=None):
    if not self._is_callable():
      raise function.NotCallable(self)
    else:
      return class_mixin.Class.call(self, node, func, args)

  def get_formal_type_parameter(self, t):
    return self.formal_type_parameters.get(t, self.ctx.convert.unsolvable)

  def get_inner_types(self):
    return self.formal_type_parameters.items()

  def update_inner_type(self, key, typ):
    self.formal_type_parameters[key] = typ

  def replace(self, inner_types):
    inner_types = dict(inner_types)
    if isinstance(self, LiteralClass):
      if inner_types == self.formal_type_parameters:
        # If the type hasn't changed, we can return a copy of this class.
        return LiteralClass(self._instance, self.ctx, self.template)
      # Otherwise, we can't create a LiteralClass because we don't have a
      # concrete value.
      typ = ParameterizedClass
    else:
      typ = self.__class__
    return typ(self.base_cls, inner_types, self.ctx, self.template)


class TupleClass(ParameterizedClass, mixin.HasSlots):
  """The class of a heterogeneous tuple.

  The formal_type_parameters attribute stores the types of the individual tuple
  elements under their indices and the overall element type under "T". So for
    Tuple[str, int]
  formal_type_parameters is
    {0: str, 1: int, T: str or int}.
  Note that we can't store the individual types as a mixin.PythonConstant as we
  do for Tuple, since we can't evaluate type parameters during initialization.
  """

  def __init__(self, base_cls, formal_type_parameters, ctx, template=None):
    super().__init__(base_cls, formal_type_parameters, ctx, template)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)
    if isinstance(self._formal_type_parameters,
                  abstract_utils.LazyFormalTypeParameters):
      num_parameters = len(self._formal_type_parameters.template)
    else:
      num_parameters = len(self._formal_type_parameters)
    # We subtract one to account for "T".
    self.tuple_length = num_parameters - 1
    self._instance = None
    self.slots = ()  # tuples don't have any writable attributes

  def __repr__(self):
    return "TupleClass(%s)" % self.formal_type_parameters

  def compute_mro(self):
    # ParameterizedClass removes the base PyTDClass(tuple) from the mro; add it
    # back here so that isinstance(tuple) checks work.
    return (self,) + self.base_cls.mro

  def get_formal_type_parameters(self):
    return {abstract_utils.full_type_name(self, abstract_utils.T):
            self.formal_type_parameters[abstract_utils.T]}

  def instantiate(self, node, container=None):
    if self._instance:
      return self._instance.to_variable(node)
    content = []
    for i in range(self.tuple_length):
      p = self.formal_type_parameters[i]
      if container is abstract_utils.DUMMY_CONTAINER or (
          isinstance(container, SimpleValue) and
          isinstance(p, TypeParameter) and
          p.full_name in container.all_template_names):
        content.append(p.instantiate(self.ctx.root_node, container))
      else:
        content.append(p.instantiate(self.ctx.root_node))
    return Tuple(tuple(content), self.ctx).to_variable(node)

  def _instantiate_index(self, node, index):
    if self._instance:
      return self._instance.pyval[index]
    else:
      index %= self.tuple_length  # fixes negative indices
      return self.formal_type_parameters[index].instantiate(node)

  def register_instance(self, instance):
    # A TupleClass can never have more than one registered instance because the
    # only direct instances of TupleClass are Tuple objects, which create their
    # own class upon instantiation. We store the instance in order to track
    # changes in the types of the elements (see TupleTest.testMutableItem).
    assert not self._instance
    self._instance = instance

  def getitem_slot(self, node, index_var):
    """Implementation of tuple.__getitem__."""
    try:
      index = self.ctx.convert.value_to_constant(
          abstract_utils.get_atomic_value(index_var), (int, slice))
    except abstract_utils.ConversionError:
      pass
    else:
      if isinstance(index, slice):
        if self._instance:
          slice_content = self._instance.pyval[index]
          return node, self.ctx.convert.build_tuple(node, slice_content)
        else:
          # Constructing the tuple directly is faster than calling call_pytd.
          instance = Instance(self.ctx.convert.tuple_type, self.ctx)
          node, contained_type = self.ctx.vm.init_class(
              node, self.formal_type_parameters[abstract_utils.T])
          instance.merge_instance_type_parameter(
              node, abstract_utils.T, contained_type)
          return node, instance.to_variable(node)
      if -self.tuple_length <= index < self.tuple_length:
        # Index out of bounds is not a pytype error because of the high
        # likelihood of false positives, e.g.,
        #   tup = []
        #   idx = 0
        #   if idx < len(tup):
        #     tup[idx]
        return node, self._instantiate_index(node, index)
    return self.call_pytd(
        node, "__getitem__", self.instantiate(node), index_var)

  def get_special_attribute(self, node, name, valself):
    if (valself and not abstract_utils.equivalent_to(valself, self) and
        name in self._slots):
      return mixin.HasSlots.get_special_attribute(self, node, name, valself)
    return super().get_special_attribute(node, name, valself)


class CallableClass(ParameterizedClass, mixin.HasSlots):
  """A Callable with a list of argument types.

  The formal_type_parameters attribute stores the types of the individual
  arguments under their indices, the overall argument type under "ARGS", and the
  return type under "RET". So for
    CallableClass[[int, bool], str]
  formal_type_parameters is
    {0: int, 1: bool, ARGS: int or bool, RET: str}
  When there are no args (CallableClass[[], ...]), ARGS contains abstract.Empty.
  """

  def __init__(self, base_cls, formal_type_parameters, ctx, template=None):
    super().__init__(base_cls, formal_type_parameters, ctx, template)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__call__", self.call_slot)
    # We subtract two to account for "ARGS" and "RET".
    self.num_args = len(self.formal_type_parameters) - 2

  def __repr__(self):
    return "CallableClass(%s)" % self.formal_type_parameters

  def get_formal_type_parameters(self):
    return {
        abstract_utils.full_type_name(self, abstract_utils.ARGS): (
            self.formal_type_parameters[abstract_utils.ARGS]),
        abstract_utils.full_type_name(self, abstract_utils.RET): (
            self.formal_type_parameters[abstract_utils.RET])}

  def call_slot(self, node, *args, **kwargs):
    """Implementation of CallableClass.__call__."""
    if kwargs:
      raise function.WrongKeywordArgs(
          function.Signature.from_callable(self),
          function.Args(posargs=args, namedargs=kwargs), self.ctx,
          kwargs.keys())
    if len(args) != self.num_args:
      raise function.WrongArgCount(
          function.Signature.from_callable(self), function.Args(posargs=args),
          self.ctx)
    formal_args = [(function.argname(i), self.formal_type_parameters[i])
                   for i in range(self.num_args)]
    substs = [datatypes.AliasingDict()]
    bad_param = None
    for view in abstract_utils.get_views(args, node):
      arg_dict = {function.argname(i): view[args[i]]
                  for i in range(self.num_args)}
      subst, bad_param = self.ctx.matcher(node).compute_subst(
          formal_args, arg_dict, view, None)
      if subst is not None:
        substs = [subst]
        break
    else:
      if bad_param:
        raise function.WrongArgTypes(
            function.Signature.from_callable(self),
            function.Args(posargs=args),
            self.ctx,
            bad_param=bad_param)
    ret = self.ctx.annotation_utils.sub_one_annotation(
        node, self.formal_type_parameters[abstract_utils.RET], substs)
    node, retvar = self.ctx.vm.init_class(node, ret)
    return node, retvar

  def get_special_attribute(self, node, name, valself):
    if (valself and not abstract_utils.equivalent_to(valself, self) and
        name in self._slots):
      return mixin.HasSlots.get_special_attribute(self, node, name, valself)
    return super().get_special_attribute(node, name, valself)


class LiteralClass(ParameterizedClass):
  """The class of a typing.Literal."""

  def __init__(self, instance, ctx, template=None):
    base_cls = ctx.convert.name_to_value("typing.Literal")
    formal_type_parameters = {abstract_utils.T: instance.cls}
    super().__init__(base_cls, formal_type_parameters, ctx, template)
    self._instance = instance

  def __repr__(self):
    return "LiteralClass(%s)" % self._instance

  def __eq__(self, other):
    if isinstance(other, LiteralClass):
      if self.value and other.value:
        return self.value.pyval == other.value.pyval
    return super().__eq__(other)

  def __hash__(self):
    return hash((super().__hash__(), self._instance))

  @property
  def value(self):
    if isinstance(self._instance, ConcreteValue):
      return self._instance
    # TODO(b/173742489): Remove this workaround once we support literal enums.
    return None

  def instantiate(self, node, container=None):
    return self._instance.to_variable(node)


class PyTDClass(SimpleValue, class_mixin.Class, mixin.LazyMembers):
  """An abstract wrapper for PyTD class objects.

  These are the abstract values for class objects that are described in PyTD.

  Attributes:
    cls: A pytd.Class
    mro: Method resolution order. An iterable of BaseValue.
  """

  def __init__(self, name, pytd_cls, ctx):
    # Apply decorators first, in case they set any properties that later
    # initialization code needs to read.
    self.has_explicit_init = any(x.name == "__init__" for x in pytd_cls.methods)
    pytd_cls, decorated = decorate.process_class(pytd_cls)
    self.pytd_cls = pytd_cls
    super().__init__(name, ctx)
    mm = {}
    for val in pytd_cls.constants:
      if isinstance(val.type, pytd.Annotated):
        mm[val.name] = val.Replace(type=val.type.base_type)
      else:
        mm[val.name] = val
    for val in pytd_cls.methods:
      mm[val.name] = val
    for val in pytd_cls.classes:
      mm[val.name.rsplit(".", 1)[-1]] = val
    if pytd_cls.metaclass is None:
      metaclass = None
    else:
      metaclass = self.ctx.convert.constant_to_value(
          pytd_cls.metaclass,
          subst=datatypes.AliasingDict(),
          node=self.ctx.root_node)
    self.official_name = self.name
    self.slots = pytd_cls.slots
    mixin.LazyMembers.init_mixin(self, mm)
    self.is_dynamic = self.compute_is_dynamic()
    class_mixin.Class.init_mixin(self, metaclass, Instance, AnnotationContainer)
    if decorated:
      self._populate_decorator_metadata()

  def _populate_decorator_metadata(self):
    """Fill in class attribute metadata for decorators like @dataclass."""
    key = None
    keyed_decorator = None
    for decorator in self.pytd_cls.decorators:
      decorator_name = decorator.type.name
      decorator_key = class_mixin.get_metadata_key(decorator_name)
      if decorator_key:
        if key:
          error = f"Cannot apply both @{keyed_decorator} and @{decorator}."
          self.ctx.errorlog.invalid_annotation(self.ctx.vm.frames, self, error)
        else:
          key, keyed_decorator = decorator_key, decorator
          self._init_attr_metadata_from_pytd(decorator_name)
          self._recompute_init_from_metadata(key)

  def _init_attr_metadata_from_pytd(self, decorator):
    """Initialise metadata[key] with a list of Attributes."""
    # Use the __init__ function as the source of truth for dataclass fields; if
    # this is a generated module we will have already processed ClassVar and
    # InitVar attributes to generate __init__, so the fields we want to add to
    # the subclass __init__ are the init params rather than the full list of
    # class attributes.
    # We also need to use the list of class constants to restore names of the
    # form `_foo`, which get replaced by `foo` in __init__.
    init = next(x for x in self.pytd_cls.methods if x.name == "__init__")
    protected = {x.name[1:]: x.name for x in self.pytd_cls.constants
                 if x.name.startswith("_")}
    params = []
    for p in init.signatures[0].params[1:]:
      if p.name in protected:
        params.append(attr.evolve(p, name=protected[p.name]))
      else:
        params.append(p)
    with self.ctx.allow_recursive_convert():
      own_attrs = [
          class_mixin.Attribute.from_param(p, self.ctx) for p in params
      ]
    self.compute_attr_metadata(own_attrs, decorator)

  def _recompute_init_from_metadata(self, key):
    # Some decorated classes (dataclasses e.g.) have their __init__ function
    # set via traversing the MRO to collect initializers from decorated parent
    # classes as well. Since we don't have access to the MRO when initially
    # decorating the class, we recalculate the __init__ signature from the
    # combined attribute list in the metadata.
    if self.has_explicit_init:
      # Do not override an __init__ from the pyi file
      return
    attrs = self.metadata[key]
    fields = [x.to_pytd_constant() for x in attrs]
    self.pytd_cls = decorate.add_init_from_fields(self.pytd_cls, fields)
    init = self.pytd_cls.Lookup("__init__")
    self._member_map["__init__"] = init

  def get_own_attributes(self):
    return {name for name, member in self._member_map.items()}

  def get_own_abstract_methods(self):
    return {name for name, member in self._member_map.items()
            if isinstance(member, pytd.Function) and member.is_abstract}

  def bases(self):
    convert = self.ctx.convert
    return [
        convert.constant_to_var(
            base, subst=datatypes.AliasingDict(), node=self.ctx.root_node)
        for base in self.pytd_cls.bases
    ]

  def load_lazy_attribute(self, name, subst=None):
    try:
      super().load_lazy_attribute(name, subst)
    except self.ctx.convert.TypeParameterError as e:
      self.ctx.errorlog.unbound_type_param(self.ctx.vm.frames, self, name,
                                           e.type_param_name)
      self.members[name] = self.ctx.new_unsolvable(self.ctx.root_node)

  def _convert_member(self, member, subst=None):
    """Convert a member as a variable. For lazy lookup."""
    subst = subst or datatypes.AliasingDict()
    node = self.ctx.root_node
    if isinstance(member, pytd.Constant):
      return self.ctx.convert.constant_to_var(
          abstract_utils.AsInstance(member.type), subst, node)
    elif isinstance(member, pytd.Function):
      c = self.ctx.convert.constant_to_value(member, subst=subst, node=node)
      c.parent = self
      return c.to_variable(node)
    elif isinstance(member, pytd.Class):
      return self.ctx.convert.constant_to_var(member, subst=subst, node=node)
    else:
      raise AssertionError("Invalid class member %s" % pytd_utils.Print(member))

  def _new_instance(self, container, node, args):
    if self.full_name == "builtins.tuple" and args.is_empty():
      value = Tuple((), self.ctx)
    else:
      value = Instance(
          self.ctx.convert.constant_to_value(self.pytd_cls), self.ctx)
    for type_param in self.template:
      name = type_param.full_name
      if name not in value.instance_type_parameters:
        value.instance_type_parameters[name] = self.ctx.program.NewVariable()
    return value

  def instantiate(self, node, container=None):
    return self.ctx.convert.constant_to_var(
        abstract_utils.AsInstance(self.pytd_cls), {}, node)

  def __repr__(self):
    return "PyTDClass(%s)" % self.name

  def __contains__(self, name):
    return name in self._member_map

  def convert_as_instance_attribute(self, name, instance):
    """Convert `name` as an instance attribute.

    This method is used by attribute.py to lazily load attributes on instances
    of this PyTDClass. Calling this method directly should be avoided. Doing so
    will create multiple copies of the same attribute, leading to subtle bugs.

    Args:
      name: The attribute name.
      instance: An instance of this PyTDClass.

    Returns:
      The converted attribute.
    """
    try:
      c = self.pytd_cls.Lookup(name)
    except KeyError:
      return None
    if isinstance(c, pytd.Constant):
      try:
        self._convert_member(c)
      except self.ctx.convert.TypeParameterError:
        # Constant c cannot be converted without type parameter substitutions,
        # so it must be an instance attribute.
        subst = datatypes.AliasingDict()
        for itm in self.pytd_cls.template:
          subst[itm.full_name] = self.ctx.convert.constant_to_value(
              itm.type_param, {}).instantiate(
                  self.ctx.root_node, container=instance)
        return self._convert_member(c, subst)

  def generate_ast(self):
    """Generate this class's AST, including updated members."""
    return pytd.Class(
        name=self.name,
        metaclass=self.pytd_cls.metaclass,
        bases=self.pytd_cls.bases,
        methods=tuple(self._member_map[m.name] for m in self.pytd_cls.methods),
        constants=self.pytd_cls.constants,
        classes=self.pytd_cls.classes,
        decorators=self.pytd_cls.decorators,
        slots=self.pytd_cls.slots,
        template=self.pytd_cls.template)


class FunctionPyTDClass(PyTDClass):
  """PyTDClass(Callable) subclass to support annotating higher-order functions.

  In InterpreterFunction calls, type parameter annotations are handled by
  getting the types of the parameters from the arguments and instantiating them
  in the return value. To handle a signature like (func: T) -> T, we need to
  save the value of `func`, not just its type of Callable.
  """

  def __init__(self, func, ctx):
    super().__init__("typing.Callable", ctx.convert.function_type.pytd_cls, ctx)
    self.func = func

  def instantiate(self, node, container=None):
    del container  # unused
    return self.func.to_variable(node)


class InterpreterClass(SimpleValue, class_mixin.Class):
  """An abstract wrapper for user-defined class objects.

  These are the abstract value for class objects that are implemented in the
  program.
  """

  def __init__(self, name, bases, members, cls, ctx):
    assert isinstance(name, str)
    assert isinstance(bases, list)
    assert isinstance(members, dict)
    self._bases = bases
    super().__init__(name, ctx)
    self.members = datatypes.MonitorDict(members)
    class_mixin.Class.init_mixin(self, cls, Instance, AnnotationContainer)
    self.instances = set()  # filled through register_instance
    # instances created by analyze.py for the purpose of analyzing this class,
    # a subset of 'instances'. Filled through register_canonical_instance.
    self.canonical_instances = set()
    self.slots = self._convert_slots(members.get("__slots__"))
    self.is_dynamic = self.compute_is_dynamic()
    log.info("Created class: %r", self)
    self.type_param_check()
    self.decorators = []

  def update_signature_scope(self, method):
    method.signature.excluded_types.update(
        [t.name for t in self.template])
    method.signature.add_scope(self.full_name)

  def update_method_type_params(self):
    if self.template:
      # For function type parameters check
      for mbr in self.members.values():
        m = abstract_utils.get_atomic_value(
            mbr, default=self.ctx.convert.unsolvable)
        if isinstance(m, SignedFunction):
          self.update_signature_scope(m)
        elif mbr.data and all(
            x.__class__.__name__ == "PropertyInstance" for x in mbr.data):
          # We generate a new variable every time we add a property slot, so we
          # take the last one (which contains bindings for all defined slots).
          prop = mbr.data[-1]
          for slot in (prop.fget, prop.fset, prop.fdel):
            if slot:
              for d in slot.data:
                if isinstance(d, SignedFunction):
                  self.update_signature_scope(d)

  def type_param_check(self):
    """Throw exception for invalid type parameters."""
    self.update_method_type_params()
    if self.template:
      # nested class can not use the same type parameter
      # in current generic class
      inner_cls_types = self.collect_inner_cls_types()
      for cls, item in inner_cls_types:
        nitem = item.with_module(self.full_name)
        if nitem in self.template:
          raise abstract_utils.GenericTypeError(
              self, ("Generic class [%s] and its nested generic class [%s] "
                     "cannot use the same type variable %s.")
              % (self.full_name, cls.full_name, item.name))

    self._load_all_formal_type_parameters()  # Throw exception if there is error
    for t in self.template:
      if t.full_name in self.all_formal_type_parameters:
        raise abstract_utils.GenericTypeError(
            self, "Conflicting value for TypeVar %s" % t.full_name)

  def collect_inner_cls_types(self, max_depth=5):
    """Collect all the type parameters from nested classes."""
    templates = set()
    if max_depth > 0:
      for mbr in self.members.values():
        mbr = abstract_utils.get_atomic_value(
            mbr, default=self.ctx.convert.unsolvable)
        if isinstance(mbr, InterpreterClass) and mbr.template:
          templates.update([(mbr, item.with_module(None))
                            for item in mbr.template])
          templates.update(mbr.collect_inner_cls_types(max_depth - 1))
    return templates

  def get_inner_classes(self):
    """Return the list of top-level nested classes."""
    values = [
        abstract_utils.get_atomic_value(
            mbr, default=self.ctx.convert.unsolvable)
        for mbr in self.members.values()
    ]
    return [x for x in values if isinstance(x, InterpreterClass) and x != self]

  def get_own_attributes(self):
    attributes = set(self.members)
    annotations_dict = abstract_utils.get_annotations_dict(self.members)
    if annotations_dict:
      attributes.update(annotations_dict.annotated_locals)
    return attributes - abstract_utils.CLASS_LEVEL_IGNORE

  def get_own_abstract_methods(self):
    def _can_be_abstract(var):
      return any(isinstance(v, Function) and v.is_abstract for v in var.data)
    return {name for name, var in self.members.items() if _can_be_abstract(var)}

  def _mangle(self, name):
    """Do name-mangling on an attribute name.

    See https://goo.gl/X85fHt.  Python automatically converts a name like
    "__foo" to "_ClassName__foo" in the bytecode. (But "forgets" to do so in
    other places, e.g. in the strings of __slots__.)

    Arguments:
      name: The name of an attribute of the current class. E.g. "__foo".

    Returns:
      The mangled name. E.g. "_MyClass__foo".
    """
    if name.startswith("__") and not name.endswith("__"):
      return "_" + self.name + name
    else:
      return name

  def _convert_slots(self, slots_var):
    """Convert __slots__ from a Variable to a tuple."""
    if slots_var is None:
      return None
    if len(slots_var.bindings) != 1:
      # Ambiguous slots
      return None  # Treat "unknown __slots__" and "no __slots__" the same.
    val = slots_var.data[0]
    if isinstance(val, mixin.PythonConstant):
      if isinstance(val.pyval, (list, tuple)):
        entries = val.pyval
      else:
        return None  # Happens e.g. __slots__ = {"foo", "bar"}. Not an error.
    else:
      return None  # Happens e.g. for __slots__ = dir(Foo)
    try:
      names = [abstract_utils.get_atomic_python_constant(v) for v in entries]
    except abstract_utils.ConversionError:
      return None  # Happens e.g. for __slots__ = ["x" if b else "y"]
    # Slot names should be strings.
    for s in names:
      if not isinstance(s, str):
        self.ctx.errorlog.bad_slots(self.ctx.vm.frames,
                                    "Invalid __slot__ entry: %r" % str(s))
        return None
    return tuple(self._mangle(s) for s in names)

  def register_instance(self, instance):
    self.instances.add(instance)

  def register_canonical_instance(self, instance):
    self.canonical_instances.add(instance)

  def bases(self):
    return self._bases

  def metaclass(self, node):
    if (self.cls.full_name != "builtins.type" and
        self.cls is not self._get_inherited_metaclass()):
      return self.ctx.convert.merge_classes([self])
    else:
      return None

  def instantiate(self, node, container=None):
    if self.ctx.vm.frame and self.ctx.vm.frame.current_opcode:
      return self._new_instance(container, node, None).to_variable(node)
    else:
      # When the analyze_x methods in CallTracer instantiate classes in
      # preparation for analysis, often there is no frame on the stack yet, or
      # the frame is a SimpleFrame with no opcode.
      return super().instantiate(node, container)

  def __repr__(self):
    return "InterpreterClass(%s)" % self.name

  def __contains__(self, name):
    if name in self.members:
      return True
    annotations_dict = abstract_utils.get_annotations_dict(self.members)
    return annotations_dict and name in annotations_dict.annotated_locals

  def update_official_name(self, name):
    assert isinstance(name, str)
    if (self.official_name is None or
        name == self.name or
        (self.official_name != self.name and name < self.official_name)):
      # The lexical comparison is to ensure that, in the case of multiple calls
      # to this method, the official name does not depend on the call order.
      self.official_name = name


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


class Coroutine(Instance):
  """A representation of instances of coroutine."""

  def __init__(self, ctx, ret_var, node):
    super().__init__(ctx.convert.coroutine_type, ctx)
    self.merge_instance_type_parameter(node, abstract_utils.T,
                                       self.ctx.new_unsolvable(node))
    self.merge_instance_type_parameter(node, abstract_utils.T2,
                                       self.ctx.new_unsolvable(node))
    self.merge_instance_type_parameter(
        node, abstract_utils.V, ret_var.AssignToNewVariable(node))

  @classmethod
  def make(cls, ctx, func, node):
    """Get return type of coroutine function."""
    assert func.signature.has_return_annotation
    ret_val = func.signature.annotations["return"]
    if func.code.has_coroutine():
      ret_var = ret_val.instantiate(node)
    elif func.code.has_iterable_coroutine():
      ret_var = ret_val.get_formal_type_parameter(
          abstract_utils.V).instantiate(node)
    return cls(ctx, ret_var, node)


class BaseGenerator(Instance):
  """A base class of instances of generators and async generators."""

  def __init__(self, generator_type, frame, ctx, is_return_allowed):
    super().__init__(generator_type, ctx)
    self.frame = frame
    self.runs = 0
    self.is_return_allowed = is_return_allowed  # if return statement is allowed

  def run_generator(self, node):
    """Run the generator."""
    if self.runs == 0:  # Optimization: We only run it once.
      node, _ = self.ctx.vm.resume_frame(node, self.frame)
      ret_type = self.frame.allowed_returns
      if ret_type:
        # set type parameters according to annotated Generator return type
        type_params = [abstract_utils.T, abstract_utils.T2]
        if self.is_return_allowed:
          type_params.append(abstract_utils.V)
        for param_name in type_params:
          _, param_var = self.ctx.vm.init_class(
              node, ret_type.get_formal_type_parameter(param_name))
          self.merge_instance_type_parameter(node, param_name, param_var)
      else:
        # infer the type parameters based on the collected type information.
        self.merge_instance_type_parameter(
            node, abstract_utils.T, self.frame.yield_variable)
        # For T2 type, it can not be decided until the send/asend function is
        # called later on. So set T2 type as ANY so that the type check will
        # not fail when the function is called afterwards.
        self.merge_instance_type_parameter(node, abstract_utils.T2,
                                           self.ctx.new_unsolvable(node))
        if self.is_return_allowed:
          self.merge_instance_type_parameter(
              node, abstract_utils.V, self.frame.return_variable)
      self.runs += 1
    return node, self.get_instance_type_parameter(abstract_utils.T)

  def call(self, node, func, args, alias_map=None):
    """Call this generator or (more common) its "next/anext" attribute."""
    del func, args
    return self.run_generator(node)


class Generator(BaseGenerator):
  """A representation of instances of generators."""

  def __init__(self, generator_frame, ctx):
    super().__init__(ctx.convert.generator_type, generator_frame, ctx, True)

  def get_special_attribute(self, node, name, valself):
    if name == "__iter__":
      f = NativeFunction(name, self.__iter__, self.ctx)
      return f.to_variable(node)
    elif name == "__next__":
      return self.to_variable(node)
    elif name == "throw":
      # We don't model exceptions in a way that would allow us to induce one
      # inside a coroutine. So just return ourself, mapping the call of
      # throw() to a next() (which won't be executed).
      return self.to_variable(node)
    else:
      return super().get_special_attribute(node, name, valself)

  def __iter__(self, node):  # pylint: disable=non-iterator-returned,unexpected-special-method-signature
    return node, self.to_variable(node)


class AsyncGenerator(BaseGenerator):
  """A representation of instances of async generators."""

  def __init__(self, async_generator_frame, ctx):
    super().__init__(ctx.convert.async_generator_type, async_generator_frame,
                     ctx, False)


class Iterator(Instance, mixin.HasSlots):
  """A representation of instances of iterators."""

  def __init__(self, ctx, return_var):
    super().__init__(ctx.convert.iterator_type, ctx)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__next__", self.next_slot)
    self._return_var = return_var

  def next_slot(self, node):
    return node, self._return_var


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


class Module(Instance, mixin.LazyMembers):
  """Represents an (imported) module."""

  def __init__(self, ctx, name, member_map, ast):
    super().__init__(ctx.convert.module_type, ctx)
    self.name = name
    self.ast = ast
    mixin.LazyMembers.init_mixin(self, member_map)

  def _convert_member(self, member, subst=None):
    """Called to convert the items in _member_map to cfg.Variable."""
    var = self.ctx.convert.constant_to_var(member)
    for value in var.data:
      # Only do this if this is a class which isn't already part of a module, or
      # is a module itself.
      # (This happens if e.g. foo.py does "from bar import x" and we then
      #  do "from foo import x".)
      if not value.module and not isinstance(value, Module):
        value.module = self.name
    return var

  @property
  def module(self):
    return None

  @module.setter
  def module(self, m):
    assert (m is None or m == self.ast.name), (m, self.ast.name)

  @property
  def full_name(self):
    return self.ast.name

  def has_getattr(self):
    """Does this module have a module-level __getattr__?

    We allow __getattr__ on the module level to specify that this module doesn't
    have any contents. The typical syntax is
      def __getattr__(name) -> Any
    .
    See https://www.python.org/dev/peps/pep-0484/#stub-files

    Returns:
      True if we have __getattr__.
    """
    f = self._member_map.get("__getattr__")
    if f:
      if isinstance(f, pytd.Function):
        if len(f.signatures) != 1:
          log.warning("overloaded module-level __getattr__ (in %s)", self.name)
        elif f.signatures[0].return_type != pytd.AnythingType():
          log.warning("module-level __getattr__ doesn't return Any (in %s)",
                      self.name)
        return True
      else:
        log.warning("__getattr__ in %s is not a function", self.name)
    return False

  def get_submodule(self, node, name):
    full_name = self.name + "." + name
    mod = self.ctx.vm.import_module(full_name, full_name,
                                    0)  # 0: absolute import
    if mod is not None:
      return mod.to_variable(node)
    elif self.has_getattr():
      return self.ctx.new_unsolvable(node)
    else:
      log.warning("Couldn't find attribute / module %r", full_name)
      return None

  def items(self):
    for name in self._member_map:
      self.load_lazy_attribute(name)
    return list(self.members.items())

  def get_fullhash(self):
    """Hash the set of member names."""
    m = hashlib.md5()
    m.update(self.full_name.encode("utf-8"))
    for k in self._member_map:
      m.update(k.encode("utf-8"))
    return m.digest()


class BuildClass(BaseValue):
  """Representation of the Python 3 __build_class__ object."""

  CLOSURE_NAME = "__class__"

  def __init__(self, ctx):
    super().__init__("__build_class__", ctx)

  def call(self, node, _, args, alias_map=None):
    args = args.simplify(node, self.ctx)
    funcvar, name = args.posargs[0:2]
    if isinstance(args.namedargs, dict):
      kwargs = args.namedargs
    else:
      kwargs = self.ctx.convert.value_to_constant(args.namedargs, dict)
    # TODO(mdemello): Check if there are any changes between python2 and
    # python3 in the final metaclass computation.
    # TODO(b/123450483): Any remaining kwargs need to be passed to the
    # metaclass.
    metaclass = kwargs.get("metaclass", None)
    if len(funcvar.bindings) != 1:
      raise abstract_utils.ConversionError(
          "Invalid ambiguous argument to __build_class__")
    func, = funcvar.data
    if not isinstance(func, InterpreterFunction):
      raise abstract_utils.ConversionError(
          "Invalid argument to __build_class__")
    func.is_class_builder = True
    bases = args.posargs[2:]
    subst = {}
    # We need placeholder values to stick in 'subst'. These will be replaced by
    # the actual type parameter values when attribute.py looks up generic
    # attributes on instances of this class.
    any_var = self.ctx.new_unsolvable(node)
    for basevar in bases:
      for base in basevar.data:
        if isinstance(base, ParameterizedClass):
          subst.update(
              {v.name: any_var for v in base.formal_type_parameters.values()
               if isinstance(v, TypeParameter)})

    node, _ = func.call(node, funcvar.bindings[0],
                        args.replace(posargs=(), namedargs={}),
                        new_locals=True, frame_substs=(subst,))
    if func.last_frame:
      func.f_locals = func.last_frame.f_locals
      class_closure_var = func.last_frame.class_closure_var
    else:
      # We have hit 'maximum depth' before setting func.last_frame
      func.f_locals = self.ctx.convert.unsolvable
      class_closure_var = None
    for base in bases:
      # If base class is NamedTuple, we will call its own make_class method to
      # make a class.
      base = abstract_utils.get_atomic_value(
          base, default=self.ctx.convert.unsolvable)
      cls_dict = func.f_locals.to_variable(node)
      # Every subclass of an enum is itself an enum. To properly process them,
      # the class must be built by the enum overlay.
      if (isinstance(base, class_mixin.Class) and base.is_enum and
          self.ctx.options.use_enum_overlay):
        enum_base = abstract_utils.get_atomic_value(
            self.ctx.vm.loaded_overlays["enum"].members["Enum"])
        return enum_base.make_class(
            node, name, list(bases), cls_dict, metaclass,
            new_class_var=class_closure_var, is_decorated=self.is_decorated)
      if isinstance(base, PyTDClass) and base.full_name == "typing.NamedTuple":
        # The subclass of NamedTuple will ignore all its base classes. This is
        # controled by a metaclass provided to NamedTuple.
        return base.make_class(node, list(bases), cls_dict)
    return self.ctx.make_class(
        node,
        name,
        list(bases),
        func.f_locals.to_variable(node),
        metaclass,
        new_class_var=class_closure_var,
        is_decorated=self.is_decorated)


class Unsolvable(Singleton):
  """Representation of value we know nothing about.

  Unlike "Unknowns", we don't treat these as solveable. We just put them
  where values are needed, but make no effort to later try to map them
  to named types. This helps conserve memory where creating and solving
  hundreds of unknowns would yield us little to no information.

  This is typically a singleton. Since unsolvables are indistinguishable, we
  only need one.
  """
  IGNORED_ATTRIBUTES = ["__get__", "__set__", "__getattribute__"]

  # Since an unsolvable gets generated e.g. for every unresolved import, we
  # can have multiple circular Unsolvables in a class' MRO. Treat those special.
  SINGLETON = True

  def __init__(self, ctx):
    super().__init__("unsolveable", ctx)

  def get_special_attribute(self, node, name, _):
    # Overrides Singleton.get_special_attributes.
    if name in self.IGNORED_ATTRIBUTES:
      return None
    else:
      return self.to_variable(node)

  def argcount(self, _):
    return 0


class Unknown(BaseValue):
  """Representation of unknown values.

  These are e.g. the return values of certain functions (e.g. eval()). They
  "adapt": E.g. they'll respond to get_attribute requests by creating that
  attribute.

  Attributes:
    members: Attributes that were written or read so far. Mapping of str to
      cfg.Variable.
    owner: cfg.Binding that contains this instance as data.
  """

  _current_id = 0

  # For simplicity, Unknown doesn't emulate descriptors:
  IGNORED_ATTRIBUTES = ["__get__", "__set__", "__getattribute__"]

  def __init__(self, ctx):
    name = escape.unknown(Unknown._current_id)
    super().__init__(name, ctx)
    self.members = datatypes.MonitorDict()
    self.owner = None
    Unknown._current_id += 1
    self.class_name = self.name
    self._calls = []
    log.info("Creating %s", self.class_name)

  def compute_mro(self):
    return self.default_mro()

  def get_fullhash(self):
    # Unknown needs its own implementation of get_fullhash to ensure equivalent
    # Unknowns produce the same hash. "Equivalent" in this case means "has the
    # same members," so member names are used in the hash instead of id().
    m = hashlib.md5()
    for name in self.members:
      m.update(name.encode("utf-8"))
    return m.digest()

  def get_children_maps(self):
    return (self.members,)

  @classmethod
  def _to_pytd(cls, node, v):
    if isinstance(v, cfg.Variable):
      return pytd_utils.JoinTypes(cls._to_pytd(node, t) for t in v.data)
    elif isinstance(v, Unknown):
      # Do this directly, and use NamedType, in case there's a circular
      # dependency among the Unknown instances.
      return pytd.NamedType(v.class_name)
    else:
      return v.to_type(node)

  @classmethod
  def _make_params(cls, node, args):
    """Convert a list of types/variables to pytd parameters."""
    def _make_param(i, p):
      return pytd.Parameter("_%d" % (i + 1), cls._to_pytd(node, p),
                            kwonly=False, optional=False, mutated_type=None)
    return tuple(_make_param(i, p) for i, p in enumerate(args))

  def get_special_attribute(self, node, name, valself):
    del node, valself
    if name in self.IGNORED_ATTRIBUTES:
      return None
    if name in self.members:
      return self.members[name]
    new = self.ctx.convert.create_new_unknown(
        self.ctx.root_node, action="getattr_" + self.name + ":" + name)
    # We store this at the root node, even though we only just created this.
    # From the analyzing point of view, we don't know when the "real" version
    # of this attribute (the one that's not an unknown) gets created, hence
    # we assume it's there since the program start.  If something overwrites it
    # in some later CFG node, that's fine, we'll then work only with the new
    # value, which is more accurate than the "fictional" value we create here.
    self.ctx.attribute_handler.set_attribute(self.ctx.root_node, self, name,
                                             new)
    return new

  def call(self, node, _, args, alias_map=None):
    ret = self.ctx.convert.create_new_unknown(
        node, source=self.owner, action="call:" + self.name)
    self._calls.append((args.posargs, args.namedargs, ret))
    return node, ret

  def argcount(self, _):
    return 0

  def to_variable(self, node):
    v = self.ctx.program.NewVariable()
    val = v.AddBinding(self, source_set=[], where=node)
    self.owner = val
    self.ctx.vm.trace_unknown(self.class_name, val)
    return v

  def to_structural_def(self, node, class_name):
    """Convert this Unknown to a pytd.Class."""
    self_param = (pytd.Parameter("self", pytd.AnythingType(),
                                 False, False, None),)
    starargs = None
    starstarargs = None
    def _make_sig(args, ret):
      return pytd.Signature(self_param + self._make_params(node, args),
                            starargs,
                            starstarargs,
                            return_type=Unknown._to_pytd(node, ret),
                            exceptions=(),
                            template=())
    calls = tuple(pytd_utils.OrderedSet(
        _make_sig(args, ret) for args, _, ret in self._calls))
    if calls:
      methods = (pytd.Function("__call__", calls, pytd.MethodTypes.METHOD),)
    else:
      methods = ()
    return pytd.Class(
        name=class_name,
        metaclass=None,
        bases=(pytd.NamedType("builtins.object"),),
        methods=methods,
        constants=tuple(pytd.Constant(name, Unknown._to_pytd(node, c))
                        for name, c in self.members.items()),
        classes=(),
        decorators=(),
        slots=None,
        template=())

  def instantiate(self, node, container=None):
    return self.to_variable(node)


AMBIGUOUS = (Unknown, Unsolvable)
AMBIGUOUS_OR_EMPTY = AMBIGUOUS + (Empty,)
FUNCTION_TYPES = (BoundFunction, Function)
INTERPRETER_FUNCTION_TYPES = (BoundInterpreterFunction, InterpreterFunction)
PYTD_FUNCTION_TYPES = (BoundPyTDFunction, PyTDFunction)
