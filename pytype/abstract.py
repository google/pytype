"""The abstract values used by typegraphvm.

An abstract value in effect represents a type. Groups of types are
combined using typegraph and that is what we compute over.
"""

# Because of false positives:
# pylint: disable=unpacking-non-sequence
# pylint: disable=abstract-method

import collections
import hashlib
import itertools
import logging


from pytype import exceptions
from pytype import output
from pytype import utils
from pytype.pyc import loadmarshal
from pytype.pytd import cfg as typegraph
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)
chain = itertools.chain  # pylint: disable=invalid-name
WrapsDict = pytd_utils.WrapsDict  # pylint: disable=invalid-name


def variable_set_official_name(variable, name):
  """Set official_name on each value in the variable.

  Called for each entry in the top-level locals().

  Args:
    variable: A typegraph.Variable to name.
    name: The name to give.
  """
  for v in variable.values:
    v.data.official_name = name


def match_var_against_type(var, other_type, subst, node, view):
  if var.values:
    return match_value_against_type(view[var], other_type, subst, node, view)
  else:  # Empty set of values. The "nothing" type.
    if isinstance(other_type, Union):
      right_side_options = other_type.options
    else:
      right_side_options = [other_type]
    for right in right_side_options:
      if isinstance(right, Class):
        # If this type is empty, the only thing we can match it against is
        # object (for pytd convenience).
        if right.name == "object":
          return subst
      elif isinstance(right, Nothing):
        # Matching nothing against nothing is fine.
        return subst
      elif isinstance(right, TypeParameter):
        # If we have a union like "K or V" and we match both against
        # nothing, that will fill in both K and V.
        if right.name not in subst:
          subst[right.name] = var.program.NewVariable("empty")
        return subst
    return None


# TODO(kramm): This needs to match values, not variables. A variable can
# consist of different types.
def match_value_against_type(value, other_type, subst, node, view):
  """One-way unify value into pytd type given a substitution.

  Args:
    value: A typegraph.Value
    other_type: An AtomicAbstractValue instance.
    subst: The current substitution. This dictionary is not modified.
    node: Current location (typegraph CFG node)
    view: A mapping of Variable to Value.
  Returns:
    A new (or unmodified original) substitution dict if the matching succeded,
    None otherwise.
  """
  left = value.data
  assert not isinstance(left, FormalType)

  # TODO(kramm): Use view

  if isinstance(other_type, Class):
    # Accumulate substitutions in "subst", or break in case of error:
    return left.match_against_type(other_type, subst, node, view)
  elif isinstance(other_type, Union):
    for t in other_type.options:
      new_subst = match_value_against_type(value, t, subst, node, view)
      if new_subst is not None:
        # TODO(kramm): What if more than one type matches?
        return new_subst
    return None
  elif isinstance(other_type, TypeParameter):
    if other_type.name in subst:
      # Merge the two variables.
      subst = subst.copy()
      new_var = subst[other_type.name].AssignToNewVariable(other_type.name,
                                                           node)
      new_var.AddValue(left, [], node)
      subst[other_type.name] = new_var
    else:
      subst = subst.copy()
      subst[other_type.name] = new_var = value.AssignToNewVariable(
          other_type.name, node)
    type_key = left.get_type_key()
    # Every value with this type key produces the same result when matched
    # against other_type, so they can all be added to this substitution rather
    # than matched separately.
    for other_value in value.variable.values:
      if (other_value is not value and
          other_value.data.get_type_key() == type_key):
        new_var.AddValue(other_value.data, {other_value}, node)
    return subst
  elif isinstance(other_type, Unknown) or isinstance(left, Unknown):
    # We can match anything against unknown types, and unknown types against
    # anything.
    # TODO(kramm): Do we want to record what we matched them against?
    assert not isinstance(other_type, ParameterizedClass)
    return subst
  elif isinstance(other_type, Nothing):
    return left.match_against_type(other_type, subst, node, view)
  else:
    log.error("Invalid type: %s", type(other_type))
    return None


class AtomicAbstractValue(object):
  """A single abstract value such as a type or function signature.

  This is the base class of the things that appear in Variables. It represents
  an atomic object that the abstract interpreter works over just as variables
  represent sets of parallel options.

  Conceptually abstract values represent sets of possible concrete values in
  compact form. For instance, an abstract value with .__class__ = int represents
  all ints.
  """

  _value_id = 0  # for pretty-printing

  def __init__(self, name, vm):
    """Basic initializer for all AtomicAbstractValues."""
    assert hasattr(vm, "program")
    self.vm = vm
    self.mro = []
    AtomicAbstractValue._value_id += 1
    self.id = AtomicAbstractValue._value_id
    self.name = name
    self.module = None
    self.official_name = None

  def get_fullhash(self):
    """Hash this value and all of its children."""
    m = hashlib.md5()
    seen_ids = set()
    stack = [self]
    while stack:
      data = stack.pop()
      data_id = id(data)
      if data_id in seen_ids:
        continue
      seen_ids.add(data_id)
      m.update(str(data_id))
      for mapping in data.get_children_maps():
        m.update(str(mapping.changestamp))
        stack.extend(mapping.data)
    return m.digest()

  def get_children_maps(self):
    """Get this value's dictionaries of children.

    Returns:
      A sequence of dictionaries from names to child values.
    """
    return ()

  def property_get(self, callself, callcls):  # pylint: disable=unused-argument
    """Bind this value to the given self and class.

    This function is similar to __get__ except at the abstract level. This does
    not trigger any code execution inside the VM. See __get__ for more details.

    Args:
      callself: The Variable that should be passed as self when the call is
        made. None if this is class call.
      callcls: The Variable that should be used as the class when the call is
        made.

    Returns:
      Another abstract value that should be returned in place of this one. The
      default implementation returns self, so this can always be called safely.
    """
    return self

  def get_attribute_flat(self, node, name):  # pylint: disable=unused-argument
    """Get a shallow attribute from this object.

    Unlike get_attribute, this will not ascend into superclasses.

    Args:
      node: The current CFG node.
      name: The name of the attribute to retrieve.
    Returns:
      A tuple (CFGNode, typegraph.Variable). If this attribute doesn't exist,
      the Variable will be None.

    """
    return node, None

  def get_attribute(self, node, name, valself=None, valcls=None):  # pylint: disable=unused-argument
    """Get the named attribute from this object.

    Args:
      node: The current CFG node.
      name: The name of the attribute to retrieve.
      valself: A typegraph.Value, This is the self reference to use when getting
        the attribute.
      valcls: A typegraph.Value. This is the cls reference to use when getting
        the attribute. If valself is given then valcls will be ignored. Note
        that most implementations of this method ignore this value as only class
        objects need it (PyTDClass and InterpreterClass)

    Returns:
      A tuple (CFGNode, typegraph.Variable). If this attribute doesn't exist,
      the Variable will be None.
    """
    return node, None

  def set_attribute(self, node, name, value):
    """Set an attribute on this object.

    The attribute might already have a Variable in it and in that case we cannot
    overwrite it and instead need to add the elements of the new variable to the
    old variable.

    Args:
      node: The current CFG node.
      name: The name of the attribute to set.
      value: The Variable to store in it.
    Returns:
      A (possibly changed) CFG node.
    """
    raise NotImplementedError()

  def call(self, node, f, posargs, namedargs, starargs=None, starstarargs=None):
    """Call this abstract value with the given arguments.

    The posargs and namedargs arguments may be modified by this function.

    Args:
      node: The CFGNode calling this function
      f: The typegraph.Value containing this function.
      posargs: Positional arguments for the call (list of Variables).
      namedargs: Keyword arguments for the call (dict mapping str to Variable).
      starargs: *args Variable, if passed. (None otherwise).
      starstarargs: **kwargs Variable, if passed (None otherwise).
    Returns:
      A tuple (cfg.Node, typegraph.Variable). The CFGNode corresponds
      to the function's "return" statement(s).
    Raises:
      FailedFunctionCall

    Make the call as required by this specific kind of atomic value, and make
    sure to annotate the results correctly with the origins (val and also other
    values appearing in the arguments).
    """
    raise NotImplementedError

  def get_bound_arguments(self):
    """Get the arguments bound into this object.

    The default implementation returns [] since an object does not have any
    bound arguments unless specified.

    Returns:
      A list of positional arguments that will be prepended to every call to
      this value.
    """
    return []

  def is_closure(self):
    """Return whether this is a closure. Overridden by subclasses.

    This can only return True for InterpreterFunction and NativeFunction
    (i.e., at the time of this writing, never for functions e.g. from PYTD,
    which doesn't know about closures), and only if they bind variables from
    their outer scope. Inner functions not binding anything are not considered a
    closure.

    Returns:
      True if this is a closure.
    """
    return False

  def register_instance(self, instance):  # pylint: disable=unused-arg
    """Treating self as a class definition, register an instance of it.

    This is used for keeping merging call records on instances when generating
    the formal definition of a class.

    Args:
      instance: An instance of this class (as an AtomicAbstractValue)
    """
    pass  # Only InterpreterClass needs this, others can ignore it.

  def get_class(self):
    """Return the class of this object. Equivalent of x.__class__ in Python."""
    raise NotImplementedError(self.__class__.__name__)

  def get_instance_type(self, instance=None):  # pylint: disable=unused-argument
    """Return the type an instance of us would have."""
    # We don't know whether we even *are* a type, so the default is anything.
    return pytd.AnythingType()

  def to_type(self):
    """Get a PyTD type representing this object."""
    raise NotImplementedError(self.__class__.__name__)

  def get_type_key(self):
    """Build a key from the information used to perform type matching.

    Get a hashable object containing this value's type information. Type keys
    are only compared amongst themselves, so we don't care what the internals
    look like, only that values with different types *always* have different
    type keys and values with the same type preferably have the same type key.

    Returns:
      A hashable object built from this value's type information.
    """
    return type(self)

  def to_variable(self, node, name=None):
    """Build a variable out of this abstract value.

    Args:
      node: The current CFG node.
      name: The name to give the new variable.
    Returns:
      A typegraph.Variable.
    Raises:
      ValueError: If origins is an empty sequence. This is to prevent you from
        creating variables that have no origin and hence can never be used.
    """
    v = self.vm.program.NewVariable(name or self.name)
    v.AddValue(self, source_set=[], where=node)
    return v

  def match_instance_against_type(self, instance, other_type,
                                  subst, node, view):
    """Checks whether an instance of us is compatible with a (formal) type.

    Args:
      instance: The instance of this class. An abstract.Instance.
      other_type: A formal type. E.g. abstract.Class or abstract.Union.
      subst: The current type parameter assignment.
      node: The current CFG node.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    raise NotImplementedError("%s is not a class" % type(self))

  def match_against_type(self, other_type, subst, node, view):
    """Checks whether we're compatible with a (formal) type.

    Args:
      other_type: A formal type. E.g. abstract.Class or abstract.Union.
      subst: The current type parameter assignment.
      node: The current CFG node.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment if the matching succeeded, None otherwise.
    """
    raise NotImplementedError("Matching not implemented for %s", type(self))

  def has_varargs(self):
    """Return True if this is a function and has a *args parameter."""
    return False

  def has_kwargs(self):
    """Return True if this is a function and has a **kwargs parameter."""
    return False

  def unique_parameter_values(self):
    return []


class FormalType(object):
  """A mix-in for marking types that can not actually be instantiated.

  This class marks all types that will only exist to declare formal parameter
  types, but can't actually be passed around as values during abstract
  interpretation.
  """
  pass


class PythonConstant(object):
  """A mix-in for storing actual Python constants, not just their types.

  This is used for things that are stored in typegraph.Variable, but where we
  may need the actual data in order to proceed later. E.g. function / class
  definitions, tuples. Also, potentially: Small integers, strings (E.g. "w",
  "r" etc.).
  """

  def init_mixin(self, pyval):
    """Mix-in equivalent of __init__."""
    self.pyval = pyval


class TypeParameter(AtomicAbstractValue, FormalType):
  """Parameter of a type.

  Attributes:
    name: Type parameter name
  """

  def __init__(self, name, vm):
    super(TypeParameter, self).__init__(name, vm)

  def __repr__(self):
    return "TypeParameter(%r)" % self.name


class SimpleAbstractValue(AtomicAbstractValue):
  """A basic abstract value that represents instances.

  This class implements instances in the Python sense. Instances of the same
  class may vary.

  Note that the cls attribute will point to another abstract value that
  represents the class object itself, not to some special type representation.
  """
  is_lazy = False

  def __init__(self, name, vm):
    """Initialize a SimpleAbstractValue.

    Args:
      name: Name of this value. For debugging and error reporting.
      vm: The TypegraphVirtualMachine to use.
    """
    super(SimpleAbstractValue, self).__init__(name, vm)
    self.members = utils.MonitorDict()
    self.type_parameters = utils.MonitorDict()
    self.cls = None

  def get_children_maps(self):
    return (self.type_parameters, self.members)

  def get_type_parameter(self, node, name):
    """Get the typegraph.Variable representing the type parameter of self.

    This will be a typegraph.Variable made up of values that have been used in
    place of this type parameter.

    Args:
      node: The current CFG node.
      name: The name of the type parameter.
    Returns:
      A Variable which may be empty.
    """
    param = self.type_parameters.get(name)
    if not param:
      log.info("Creating new empty type param %s", name)
      param = self.vm.program.NewVariable(name, [], [], node)
      self.type_parameters[name] = param
    return param

  def merge_type_parameter(self, node, name, value):
    """Set the value of a type parameter.

    This will always add to the type_parameter unlike set_attribute which will
    replace value from the same basic block. This is because type parameters may
    be affected by a side effect so we need to collect all the information
    regardless of multiple assignments in one basic block.

    Args:
      node: The current CFG node.
      name: The name of the type parameter.
      value: The value that is being used for this type parameter as a Variable.
    """
    log.info("Modifying type param %s", name)
    self.type_parameters[name].PasteVariable(value, node)

  # TODO(kramm): remove
  def overwrite_type_parameter(self, node, name, value):
    """Overwrite the value of a type parameter.

    Unlike merge_type_parameter, this will purge the previous value and set
    the type parameter only to the new value.

    Args:
      node: The current CFG node.
      name: The name of the type parameter.
      value: The new type parameter as a Variable.
    """
    log.info("Overwriting type param %s", name)
    self.type_parameters[name] = self.vm.program.NewVariable(
        name, value.data, [], node)

  def initialize_type_parameter(self, node, name, value):
    assert isinstance(name, str)
    log.info("Initializing type param %s: %r", name, value.data)
    self.type_parameters[name] = self.vm.program.NewVariable(
        name, value.data, [], node)

  def init_type_parameters(self, *names):
    """Initialize the named type parameters to nothing (empty)."""
    self.type_parameters = utils.MonitorDict(
        (name, self.vm.program.NewVariable("empty")) for name in names)

  def _load_lazy_attribute(self, name):
    """Load the named attribute into self.members."""
    if name not in self.members and name in self._member_map:
      variable = self._convert_member(name, self._member_map[name])
      assert isinstance(variable, typegraph.Variable)
      self.members[name] = variable

  def _load_special_attribute(self, node, name):
    if name == "__class__" and self.cls is not None:
      return node, self.cls
    else:
      return node, None

  def get_attribute(self, node, name, valself=None, valcls=None):
    node, attr = self._load_special_attribute(node, name)
    if attr is not None:
      return node, attr

    if self.is_lazy:
      self._load_lazy_attribute(name)

    candidates = []
    nodes = []

    # Retrieve instance attribute
    if name in self.members:
      # Allow an instance attribute to shadow a class attribute, but only
      # if there's a path through the CFG that actually assigns it.
      # TODO(kramm): It would be more precise to check whether there's NOT any
      # path that DOESN'T have it.
      if self.members[name].Values(node):
        candidates.append(self.members[name])

    # Retrieve class attribute
    if not candidates and self.cls:
      for clsval in self.cls.values:
        cls = clsval.data
        new_node, attr = cls.get_attribute(node, name, valself, clsval)
        nodes.append(new_node)
        if attr is not None:
          candidates.append(attr)
      node = self.vm.join_cfg_nodes(nodes)

    if not candidates:
      return node, None
    else:
      ret = self.vm.program.NewVariable(name)
      for candidate in candidates:
        ret.FilterAndPasteVariable(candidate, node)
      if not ret.values:
        return node, None
      return node, ret

  def set_attribute(self, node, name, var):
    assert isinstance(var, typegraph.Variable)

    if self.is_lazy:
      self._load_lazy_attribute(name)

    if name == "__class__":
      return self.set_class(node, var)

    variable = self.members.get(name)
    if variable:
      old_len = len(variable.values)
      variable.PasteVariable(var, node)
      log.debug("Adding choice(s) to %s: %d new values", name,
                len(variable.values) - old_len)
    else:
      # TODO(kramm): Under what circumstances can we just reuse var?
      #              (variable = self.members[name] = var)?
      log.debug("Setting %s to the %d values in %r",
                name, len(var.values), var)
      long_name = self.name + "." + name
      variable = var.AssignToNewVariable(long_name, node)
      self.members[name] = variable
    return node

  def call(self, node, unused_func, posargs, namedargs,
           starargs=None, starstarargs=None):
    # End up here for:
    #   f = 1
    #   f()  # Can't call an int
    return node, self.vm.create_new_unsolvable(node, "calling " + self.name)

  def __repr__(self):
    if self.cls:
      cls = self.cls.data[0]
      return "<v%d %s [%r]>" % (self.id, self.name, cls)
    else:
      return "<v%d %s>" % (self.id, self.name)

  def to_variable(self, node, name):
    return super(SimpleAbstractValue, self).to_variable(node, name)

  def get_class(self):
    # See Py_TYPE() in Include/object.h
    return self.cls

  def set_class(self, node, var):
    """Set the __class__ of an instance, for code that does "x.__class__ = y."""
    if self.cls:
      self.cls.PasteVariable(var, node)
    else:
      self.cls = var
    for cls in var.data:
      cls.register_instance(self)
    return node

  def to_type(self):
    """Get a PyTD type representing this object.

    This uses both the instance (for type parameters) as well as the class.

    Returns:
      A PyTD Type
    """
    if self.cls:
      classvalues = (v.data for v in self.cls.values)
      types = []
      for cls in classvalues:
        types.append(cls.get_instance_type(self))
      ret = pytd_utils.JoinTypes(types)
      visitors.InPlaceFillInClasses(ret, self.vm.loader.builtins)
      return ret
    else:
      # We don't know this type's __class__, so return AnythingType to indicate
      # that we don't know anything about what this is.
      # This happens e.g. for locals / globals, which are returned from the code
      # in class declarations.
      log.info("Using ? for %s", self.name)
      return pytd.AnythingType()

  def match_against_type(self, other_type, subst, node, view):
    my_type = self.get_class()
    if not my_type:
      log.warning("Can't match %s against %s", self.__class__, other_type.name)
      return None
    for my_cls in my_type.data:
      subst = my_cls.match_instance_against_type(self, other_type,
                                                 subst, node, view)
      if subst is None:
        return None
    return subst

  def get_type_key(self):
    key = set()
    if self.cls:
      clsval, = self.cls.values
      key.add(clsval.data)
    for name, var in self.type_parameters.items():
      key.add((name, frozenset(value.data.get_type_key()
                               for value in var.values)))
    if key:
      return frozenset(key)
    else:
      return super(SimpleAbstractValue, self).get_type_key()

  def unique_parameter_values(self):
    """Get unique parameter subtypes as Values.

    This will retrieve 'children' of this value that contribute to the
    type of it. So it will retrieve type parameters, but not attributes. To
    keep the number of possible combinations reasonable, when we encounter
    multiple instances of the same type, we include only one.

    Returns:
      A list of list of Values.
    """
    parameters = self.type_parameters.values()
    clsvar = self.get_class()
    if clsvar:
      parameters.append(clsvar)
    # TODO(rechen): Remember which values were merged under which type keys so
    # we don't have to recompute this information in match_value_against_type.
    return [{value.data.get_type_key(): value
             for value in parameter.values}.values()
            for parameter in parameters]


class Instance(SimpleAbstractValue):

  def __init__(self, clsvar, vm):
    super(Instance, self).__init__(clsvar.name, vm)
    self.cls = clsvar
    for cls in clsvar.data:
      cls.register_instance(self)


class ValueWithSlots(Instance):
  """Convenience class for overriding slots with custom methods.

  This makes it easier to emulate built-in classes like dict which need special
  handling of some magic methods (__setitem__ etc.)
  """

  def __init__(self, clsvar, vm):
    super(ValueWithSlots, self).__init__(clsvar, vm)
    self._slots = {}
    self._self = {}  # TODO(kramm): Find a better place to store these.
    self._super = {}
    self._function_cache = {}

  def make_native_function(self, name, method):
    key = (name, method)
    if key not in self._function_cache:
      self._function_cache[key] = NativeFunction(name, method, self.vm)
    return self._function_cache[key]

  def set_slot(self, name, method):
    """Add a new slot to this value."""
    assert name not in self._slots, "slot %s already occupied" % name
    f = self.make_native_function(name, method)
    self._slots[name] = f.to_variable(self.vm.root_cfg_node, name)
    _, attr = super(ValueWithSlots, self).get_attribute(
        self.vm.root_cfg_node, name)
    self._super[name] = attr

  def call_pytd(self, node, name, *args):
    """Call the (original) pytd version of a method we overwrote."""
    if name in self._self:
      node, ret = self.vm.call_function(
          node, self._super[name], (self._self[name],) + args)
    else:
      ret = None
      log.error(
          "Can't call bound method %s: We don't know how it was bound.", name)
    return node, ret

  def get_attribute(self, node, name, valself=None, valcls=None):
    """Get an attribute.

    Will delegate to SimpleAbstractValue if we don't have a slot for it.

    Arguments:
      node: The current CFG node.
      name: name of the attribute. If this is something like "__getitem__",
        the slot mechanism might kick in.
      valself: A typegraph.Value. See AtomicAbstractValue.get_attribute.
      valcls: A typegraph.Value. See AtomicAbstractValue.get_attribute.

    Returns:
      A tuple (CFGNode, Variable). The Variable will be None if the attribute
      doesn't exist.
    """
    if name in self._slots:
      self._self[name] = valself.AssignToNewVariable(valself.variable.name,
                                                     node)
      return node, self._slots[name]
    else:
      return super(ValueWithSlots, self).get_attribute(
          node, name, valself, valcls)


class Dict(ValueWithSlots, WrapsDict("_entries")):
  """Representation of Python 'dict' objects.

  It works like __builtins__.dict, except that, for string keys, it keeps track
  of what got stored.
  """

  # These match __builtins__.pytd:
  KEY_TYPE_PARAM = "K"
  VALUE_TYPE_PARAM = "V"

  def __init__(self, name, vm):
    super(Dict, self).__init__(vm.dict_type, vm)
    self.name = name
    self._entries = {}
    self.set_slot("__getitem__", self.getitem_slot)
    self.set_slot("__setitem__", self.setitem_slot)
    self.init_type_parameters(self.KEY_TYPE_PARAM, self.VALUE_TYPE_PARAM)

  def getitem_slot(self, node, name_var):
    """Implements the __getitem__ slot."""
    results = []
    for val in name_var.values:
      try:
        name = self.vm.convert_value_to_string(val.data)
      except ValueError:  # ConversionError
        # We *do* know the overall type of the values through the "V" type
        # parameter, even if we don't know the exact type of self[name]:
        results.append(self.get_type_parameter(node, "V"))
      else:
        try:
          results.append(self._entries[name])
        except KeyError:
          raise exceptions.ByteCodeKeyError("KeyError: %r" % name)
    # For call tracing only, we don't actually use the return value:
    node, _ = self.call_pytd(node, "__getitem__", name_var)
    return node, self.vm.join_variables(
        node, "getitem[var%s]" % name_var.id, results)

  def set_str_item(self, node, name, value_var):
    self.merge_type_parameter(
        node, self.KEY_TYPE_PARAM, self.vm.build_string(node, name))
    self.merge_type_parameter(
        node, self.VALUE_TYPE_PARAM, value_var)
    if name in self._entries:
      self._entries[name].PasteVariable(value_var, node)
    else:
      self._entries[name] = value_var
    return node

  def setitem(self, node, name_var, value_var):
    assert isinstance(name_var, typegraph.Variable)
    assert isinstance(value_var, typegraph.Variable)
    for val in name_var.values:
      try:
        name = self.vm.convert_value_to_string(val.data)
      except ValueError:  # ConversionError
        continue
      if name in self._entries:
        self._entries[name].PasteVariable(value_var, node)
      else:
        self._entries[name] = value_var

  def setitem_slot(self, node, name_var, value_var):
    """Implements the __setitem__ slot."""
    self.setitem(node, name_var, value_var)
    return self.call_pytd(node, "__setitem__", name_var, value_var)

  def update(self, node, other_dict, omit=()):
    if isinstance(other_dict, (Dict, dict)):
      for key, value in other_dict.items():
        # TODO(kramm): sources
        if key not in omit:
          self.set_str_item(node, key, value)
      if isinstance(other_dict, Dict):
        k = other_dict.get_type_parameter(node, self.KEY_TYPE_PARAM)
        v = other_dict.get_type_parameter(node, self.VALUE_TYPE_PARAM)
        self.merge_type_parameter(node, self.KEY_TYPE_PARAM, k)
        self.merge_type_parameter(node, self.VALUE_TYPE_PARAM, v)
      return True
    else:
      assert isinstance(other_dict, AtomicAbstractValue)
      return False


class AbstractOrConcreteValue(Instance, PythonConstant):
  """Abstract value with a concrete fallback."""

  def __init__(self, pyval, clsvar, vm):
    super(AbstractOrConcreteValue, self).__init__(clsvar, vm)
    PythonConstant.init_mixin(self, pyval)


class LazyAbstractOrConcreteValue(SimpleAbstractValue, PythonConstant):
  """Lazy abstract value with a concrete fallback."""

  is_lazy = True  # uses _convert_member

  def __init__(self, name, pyval, member_map, resolver, vm):
    SimpleAbstractValue.__init__(self, name, vm)
    self._member_map = member_map
    self._resolver = resolver
    PythonConstant.init_mixin(self, pyval)

  def _convert_member(self, name, pyval):
    return self._resolver(name, pyval)


class Union(AtomicAbstractValue, FormalType):
  """A list of types. Used for parameter matching.

  Attributes:
    options: Iterable of instances of AtomicAbstractValue.
  """

  def __init__(self, options, vm):
    super(Union, self).__init__("union", vm)
    self.options = options


# return value from PyTDSignature._call_with_values:
FunctionCallResult = collections.namedtuple(
    "_", ["return_type", "subst", "mutations"])


class FailedFunctionCall(Exception):
  """Exception for failed function calls."""

  def __init__(self, sig):
    super(FailedFunctionCall, self).__init__()
    self.sig = sig


class WrongArgTypes(FailedFunctionCall):
  """For functions that were called with the wrong types."""

  def __init__(self, sig, passed_args):
    super(WrongArgTypes, self).__init__(sig)
    self.passed_args = passed_args


class WrongArgCount(FailedFunctionCall):
  """E.g. if a function expecting 4 parameters is called with 3."""

  def __init__(self, sig, call_arg_count):
    super(WrongArgCount, self).__init__(sig)
    self.call_arg_count = call_arg_count


class SuperInstance(AtomicAbstractValue):
  """The result of a super() call, i.e., a lookup proxy."""

  def __init__(self, cls, obj, vm):
    super(SuperInstance, self).__init__("super", vm)
    self.super_cls = cls
    self.super_obj = obj

  def get_attribute(self, node, name, valself=None, valcls=None):
    if self.super_obj:
      valself = self.super_obj.to_variable(node, "self").values[0]
    valcls = self.super_cls.to_variable(node, "cls").values[0]
    return node, self.super_cls.lookup_from_mro(
        node, name, valself, valcls, skip=self.super_cls)


class Super(AtomicAbstractValue):
  """The super() function. Calling it will create a SuperInstance."""

  def __init__(self, vm):
    super(Super, self).__init__("super", vm)

  def call(self, node, _, posargs, namedargs, starargs=None, starstarargs=None):
    result = self.vm.program.NewVariable("super")
    if len(posargs) == 1:
      # TODO(kramm): Add a test for this
      for cls in posargs[0].values:
        result.AddValue(
            SuperInstance(cls.data, None, self.vm), [cls], node)
    elif len(posargs) == 2:
      for cls in posargs[0].values:
        for obj in posargs[1].values:
          result.AddValue(
              SuperInstance(cls.data, obj.data, self.vm), [cls, obj], node)
    else:
      self.errorlog.super_error(self.vm.frame.current_opcode, len(posargs))
      result = self.vm.create_new_unsolvable(node, "super()")
    return node, result

  def get_attribute(self, node, name, valself=None, valcls=None):
    # In Python 3, you can do "super.__init__".
    raise NotImplementedError("Python 3 super not implemented yet")


class Function(Instance):
  """Base class for function objects (NativeFunction, InterpreterFunction).

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    vm: TypegraphVirtualMachine instance.
  """

  def __init__(self, name, vm):
    super(Function, self).__init__(vm.function_type, vm)
    self.name = name
    self.parent_class = None
    self._bound_functions_cache = {}
    self.members["func_name"] = self.vm.build_string(
        self.vm.root_cfg_node, name)

  def get_attribute(self, node, name, valself=None, valcls=None):
    if name == "__get__":
      # The pytd for "function" has a __get__ attribute, but if we already
      # have a function we don't want to be treated as a descriptor.
      return node, None
    return super(Function, self).get_attribute(node, name, valself, valcls)

  def property_get(self, callself, callcls):
    if not callself or not callcls:
      return self
    self.parent_class = callcls.values[0].data
    key = tuple(sorted(callself.data))
    if key not in self._bound_functions_cache:
      self._bound_functions_cache[key] = (self.bound_class)(callself, self)
    return self._bound_functions_cache[key]

  def get_class(self):
    return self.vm.function_type

  def to_type(self):
    return pytd.NamedType("function")

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name in ["function", "object"]:
      return subst


class Mutation(collections.namedtuple("_", ["instance", "name", "value"])):
  pass


class PyTDSignature(object):
  """A PyTD function type (signature).

  This represents instances of functions with specific arguments and return
  type.
  """

  def __init__(self, pytd_sig, vm):
    self.vm = vm
    self.pytd_sig = pytd_sig
    self.param_types = [
        self.vm.convert_constant_to_value(pytd.Print(p), p.type)
        for p in self.pytd_sig.params]
    self._bound_sig_cache = {}

  # pylint: disable=unused-argument
  def call_with_view(self, node, func, view, posargs, namedargs, ret_map,
                     starargs=None, starstarargs=None,
                     record_call=False):
    """Call this signature. Used by PyTDFunction."""
    args_selected = [view[arg] for arg in posargs]
    kws_selected = {name: view[arg] for name, arg in namedargs.items()}

    if self.pytd_sig.has_optional:
      # Truncate extraneous params. E.g. when calling f(a, b, ...) as f(1, 2, 3)
      posargs = posargs[0:len(self.pytd_sig.params)]
    if len(posargs) < len(self.pytd_sig.params):
      for p in self.pytd_sig.params[len(posargs):]:
        if p.name in namedargs:
          posargs.append(namedargs[p.name])
        elif starargs is not None or starstarargs is not None:
          # Assume the missing parameter is filled in by *args or **kwargs.
          # TODO(kramm): Can we use the contents of [star]starargs to fill in a
          # more precise type than just "unsolvable"?
          posargs.append(self.vm.create_new_unsolvable(node, p.name))
        else:
          break  # We just found a missing parameter. Raise error below.
    if len(posargs) != len(self.pytd_sig.params):
      # Either too many or too few parameters.
      # Number of parameters mismatch is allowed when matching against an
      # overloaded function (e.g., a __builtins__ entry that has optional
      # parameters that are specified by multiple def's).
      raise WrongArgCount(self, len(posargs))
    r = self._call_with_values(node, args_selected, kws_selected, view)
    assert r.subst is not None
    t = (r.return_type, r.subst)
    sources = [func] + args_selected + kws_selected.values()
    if t not in ret_map:
      ret_map[t] = self.vm.create_pytd_instance(
          "ret", r.return_type, r.subst, node,
          source_sets=[sources])
    else:
      # add the new sources
      for data in ret_map[t].data:
        ret_map[t].AddValue(data, sources, node)
    if record_call:
      self.vm.trace_call(func, args_selected, kws_selected, ret_map[t])
    return node, ret_map[t], r.mutations

  def _call_with_values(self, node, arg_values, kw_values, view):
    """Try to execute this signature with the given arguments.

    This uses specific typegraph.Value instances (not: Variables) to try to
    match this signature. This is used by call(), which dissects
    typegraph.Variable instances into Value lists.

    Args:
      node: The current CFG node.
      arg_values: A list of pytd.Value instances.
      kw_values: A map of strings to pytd.Values instances.
      view: A mapping of Variable to Value.
    Returns:
      A FunctionCallResult instance
    Raises:
      FailedFunctionCall
    """
    return_type = self.pytd_sig.return_type
    subst = self._compute_subst(node, arg_values, kw_values, view)
    # FailedFunctionCall is thrown by _compute_subst if no signature could be
    # matched (subst might be []).
    log.debug("Matched arguments against sig%s", pytd.Print(self.pytd_sig))
    for nr, (actual, formal) in enumerate(zip(arg_values,
                                              self.pytd_sig.params)):
      log.info("param %d) %s: %s <=> %s", nr, formal.name, formal.type,
               actual.data)
    for name, var in sorted(subst.items()):
      log.debug("Using %s=%r %r", name, var, var.data)
    mutations = self._get_mutation(node, arg_values, kw_values, subst)
    return FunctionCallResult(return_type, subst, mutations)

  def _compute_subst(self, node, arg_values, kw_values, view):
    """Compute information about type parameters using one-way unification.

    Given the arguments of a function call, try to find a substitution that
    matches them against the formal parameter of this PyTDSignature.

    Args:
      node: The current CFG node.
      arg_values: A list of pytd.Value instances.
      kw_values: A map of strings to pytd.Values instances.
      view: A mapping of Variable to Value.
    Returns:
      utils.HashableDict if we found a working substition, None otherwise.
    Raises:
      FailedFunctionCall: For incorrect parameter types.
    """
    if not arg_values:
      return utils.HashableDict()
    if kw_values:
      log.warning("Ignoring keyword parameters %r", kw_values)
    subst = {}
    for actual, formal in zip(arg_values, self.param_types):
      subst = match_value_against_type(actual, formal, subst, node, view)
      if subst is None:
        # These parameters didn't match this signature. There might be other
        # signatures that work, but figuring that out is up to the caller.
        raise WrongArgTypes(self, [a.data for a in arg_values])
    return utils.HashableDict(subst)

  def _get_mutation(self, node, arg_values, kw_values, subst):
    """Mutation for changing the type parameters of mutable arguments.

    This will adjust the type parameters as needed for pytd functions like:
      def append_float(x: list[int]):
        x := list[int or float]
    This is called after all the signature matching has succeeded, and we
    know we're actually calling this function.

    Args:
      node: The current CFG node.
      arg_values: A list of pytd.Value instances.
      kw_values: A map of strings to pytd.Values instances.
      subst: Current type parameters.
    Returns:
      A list of Mutation instances.
    Raises:
      ValueError: If the pytd contains invalid MutableParameter information.
    """
    # Handle mutable parameters using the information type parameters
    if kw_values:
      log.warning("Ignoring keyword parameters %r", kw_values)
    mutations = []
    for actual, formal in zip(arg_values, self.pytd_sig.params):
      if isinstance(formal, pytd.MutableParameter):
        if (isinstance(formal.type, pytd.GenericType) and
            isinstance(formal.new_type, pytd.GenericType) and
            formal.type.base_type == formal.new_type.base_type and
            isinstance(formal.type.base_type, pytd.ClassType) and
            formal.type.base_type.cls):
          arg = actual.data
          names_actuals = zip(formal.new_type.base_type.cls.template,
                              formal.new_type.parameters)
          for tparam, type_actual in names_actuals:
            log.info("Mutating %s to %s",
                     tparam.name,
                     pytd.Print(type_actual))
            type_actual_val = self.vm.create_pytd_instance(
                tparam.name, type_actual, subst, node,
                discard_concrete_values=True)
            mutations.append(Mutation(arg, tparam.name, type_actual_val))
        else:
          log.error("Old: %s", pytd.Print(formal.type))
          log.error("New: %s", pytd.Print(formal.new_type))
          log.error("Actual: %r", actual)
          raise ValueError("Mutable parameters setting a type to a "
                           "different base type is not allowed.")
    return mutations

  def get_bound_arguments(self):
    return []

  def get_parameter_names(self):
    return [p.name for p in self.pytd_sig.params]

  def __repr__(self):
    return pytd.Print(self.pytd_sig)


class ClassMethod(AtomicAbstractValue):
  """Implements @classmethod methods in pyi."""

  def __init__(self, name, method, callself, callcls, vm):
    super(ClassMethod, self).__init__(name, vm)
    self.method = method
    self.callself = callself  # unused
    self.callcls = callcls  # unused
    self.signatures = self.method.signatures

  def call(self, node, func, posargs, namedargs,
           starargs=None, starstarargs=None):
    # Since this only used in pyi, we don't need to verify the type of the "cls"
    # arg a second time. So just pass an unsolveable. (All we care about is the
    # return type, anyway.)
    cls = self.vm.create_new_unsolvable(node, "cls")
    return self.method.call(node, func,
                            [cls] + posargs,
                            namedargs, starargs, starstarargs)

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name in ["classmethod", "object"]:
      return subst


class PyTDFunction(Function):
  """A PyTD function (name + list of signatures).

  This represents (potentially overloaded) functions.
  """

  def __init__(self, name, signatures, kind, vm):
    super(PyTDFunction, self).__init__(name, vm)
    assert signatures
    self.kind = kind
    self.bound_class = BoundPyTDFunction
    self.signatures = signatures
    self._signature_cache = {}
    self._return_types = {sig.pytd_sig.return_type for sig in signatures}
    self._has_mutable = any(isinstance(param, pytd.MutableParameter)
                            for sig in signatures
                            for param in sig.pytd_sig.params)
    for sig in signatures:
      sig.function = self
      sig.name = self.name

  def property_get(self, callself, callcls):
    if self.kind == pytd.STATICMETHOD:
      return self
    elif self.kind == pytd.CLASSMETHOD:
      return ClassMethod(self.name, self, callself, callcls, self.vm)
    else:
      return Function.property_get(self, callself, callcls)

  def _log_args(self, arg_values_list, level=0):
    if log.isEnabledFor(logging.DEBUG):
      for i, arg_values in enumerate(arg_values_list):
        if level:
          if arg_values:
            log.debug("%s%s:", "  " * level, arg_values[0].variable.name)
        else:
          log.debug("Arg %d", i)
        for value in arg_values:
          log.debug("%s%s", "  " * (level + 1), value.data)
          self._log_args(value.data.unique_parameter_values(), level + 2)

  def call(self, node, func, posargs, namedargs,
           starargs=None, starstarargs=None):
    self._log_args(arg.values for arg in posargs)
    ret_map = {}
    retvar = self.vm.program.NewVariable("%s ret" % self.name)
    error = None
    variables = tuple(posargs) + tuple(namedargs.values())
    all_calls_failed = True
    all_mutations = []
    for combination in utils.deep_variable_product(variables):
      view = {value.variable: value for value in combination}
      try:
        node, result, mutations = self._call_with_view(
            node, func, view, posargs, namedargs, ret_map,
            starargs, starstarargs)
      except FailedFunctionCall as e:
        error = error or e
      else:
        retvar.PasteVariable(result, node)
        all_mutations += mutations
        all_calls_failed = False
    if all_calls_failed and error:
      raise error  # pylint: disable=raising-bad-type

    log.info("Applying %d mutations", len(all_mutations))
    for obj, name, value in all_mutations:
      obj.merge_type_parameter(node, name, value)

    return node, retvar

  def _get_mutation_to_unknown(self, node, values):
    """Mutation for making all type parameters in a list of instances "unknown".

    This is used if we call a function that has mutable parameters and
    multiple signatures with unknown parameters.

    Args:
      node: The current CFG node.
      values: A list of instances of AtomicAbstractValue.

    Returns:
      A list of Mutation instances.
    """
    return [Mutation(v, name,
                     self.vm.create_new_unknown(node, name,
                                                action="type_param_" + name))
            for v in values if isinstance(v, SimpleAbstractValue)
            for name in v.type_parameters]

  def _call_with_view(self, node, func, view, posargs, namedargs,
                      ret_map, starargs=None, starstarargs=None):
    """Call function using a specific Variable->Value view."""
    log.debug("call_with_view function %r: %d signature(s)",
              self.name, len(self.signatures))
    log.debug("args in view: %r", [(a.values and view[a].data)
                                   for a in posargs])

    if not all(a.values for a in posargs):
      raise exceptions.ByteCodeTypeError(
          "Can't call function with <nothing> parameter")

    # If we're calling an overloaded pytd function with an unknown as a
    # parameter, we can't tell whether it matched or not. Hence, we don't know
    # which signature got called. Check if this is the case.
    if (len(self.signatures) > 1 and
        any(isinstance(view[arg].data, Unknown)
            for arg in chain(posargs, namedargs.values()))):
      return self.call_with_unknowns(node, func, view, posargs, namedargs,
                                     ret_map, starargs, starstarargs)
    else:
      return self.find_matching_signature(
          node, func, view, posargs, namedargs, ret_map,
          starargs, starstarargs, record_call=True)

  def call_with_unknowns(self, node, func, view, posargs, namedargs, ret_map,
                         starargs, starstarargs):
    """Perform a function call that involves unknowns."""

    # Make sure that at least one signature is possible:
    self.find_matching_signature(node, func, view, posargs, namedargs, ret_map,
                                 starargs, starstarargs)

    unique_type = None
    if len(self._return_types) == 1:
      ret_type, = self._return_types
      # TODO(kramm): This needs to do a deep scan
      if not isinstance(ret_type, pytd.TypeParameter):
        unique_type = ret_type
    # Even though we don't know which signature got picked, if the return
    # type is unique, we can use it.
    if unique_type:
      log.debug("Unknown args. But return is always %s",
                pytd.Print(unique_type))
      result = self.vm.create_pytd_instance(
          "ret", ret_type, {}, node)
    else:
      log.debug("Creating unknown return")
      result = self.vm.create_new_unknown(
          node, "<unknown return of " + self.name + ">", action="pytd_call")
    if self._has_mutable:
      # TODO(kramm): We only need to whack the type params that appear in
      # a MutableParameter.
      mutations = self._get_mutation_to_unknown(
          node, (view[p].data for p in chain(posargs, namedargs.values())))
    else:
      mutations = []
    self.vm.trace_call(func,
                       [view[arg] for arg in posargs],
                       {name: view[arg] for name, arg in namedargs.items()},
                       result)
    return node, result, mutations

  def find_matching_signature(self, node, func, view, posargs, namedargs,
                              ret_map, starargs, starstarargs,
                              record_call=False):
    """Try, in order, all pytd signatures until we find one that matches."""

    # We only take the first signature that matches, and ignore all after it.
    # This is because in the pytds for the standard library, the last
    # signature(s) is/are fallback(s) - e.g. list is defined by
    # def __init__(self: x: list)
    # def __init__(self, x: iterable)
    # def __init__(self, x: generator)
    # def __init__(self, x: object)
    # with the last signature only being used if none of the others match.

    error = None
    for sig in self.signatures:
      try:
        new_node, result, mutations = sig.call_with_view(
            node, func, view, posargs, namedargs, ret_map,
            starargs, starstarargs, record_call)
      except FailedFunctionCall as e:
        error = error or e
      else:
        return new_node, result, mutations
    raise error  # pylint: disable=raising-bad-type

  def to_pytd_def(self, _):
    return pytd.NamedType("function")

  def __repr__(self):
    return self.name + "(...)"


class Class(object):
  """Mix-in to mark all class-like values."""

  def __new__(cls, *args, **kwds):
    """Prevent direct instantiation."""
    assert cls is not Class, "Cannot instantiate Class"
    return object.__new__(cls, *args, **kwds)

  def init_mixin(self):
    """Mix-in equivalent of __init__."""
    pass

  def lookup_from_mro(self, node, name, valself, valcls, skip=None):
    """Find an identifier in the MRO of the class."""
    ret = self.vm.program.NewVariable(name)
    add_origins = []
    variableself = variablecls = None
    if valself:
      assert isinstance(valself, typegraph.Value)
      variableself = valself.AssignToNewVariable(valself.variable.name, node)
      add_origins.append(valself)
    if valcls:
      assert isinstance(valcls, typegraph.Value)
      variablecls = valcls.AssignToNewVariable(valcls.variable.name, node)
      add_origins.append(valcls)

    for base in self.mro:
      # Potentially skip start of MRO, for super()
      if base is skip:
        continue
      node, var = base.get_attribute_flat(node, name)
      if var is None:
        continue
      for varval in var.values:
        value = varval.data
        if variableself or variablecls:
          value = value.property_get(variableself, variablecls)
        ret.AddValue(value, [varval] + add_origins, node)
      break  # we found a class which has this attribute
    return ret

  def get_attribute(self, node, name, valself=None, valcls=None):
    """Retrieve an attribute by looking at the MRO of this class."""
    var = self.lookup_from_mro(node, name, valself, valcls)
    return node, var

  def to_pytd_def(self, name):
    # Default method. Generate an empty pytd. Subclasses override this.
    return pytd.Class(name, (), (), (), ())


class ParameterizedClass(AtomicAbstractValue, Class, FormalType):
  """A class that contains additional parameters. E.g. a container.

  Attributes:
    cls: A PyTDClass representing the base type.
    type_parameters: An iterable of AtomicAbstractValue, one for each type
        parameter.
  """

  def __init__(self, base_cls, type_parameters, vm):
    super(ParameterizedClass, self).__init__(base_cls.name, vm)
    Class.init_mixin(self)
    self.base_cls = base_cls
    self.type_parameters = type_parameters

  def __repr__(self):
    return "ParameterizedClass(cls=%r params=%s)" % (self.base_cls,
                                                     self.type_parameters)

  def to_type(self):
    return pytd.NamedType("type")

  def get_instance_type(self, _):
    type_arguments = []
    for type_param in self.base_cls.pytd_cls.template:
      type_arguments.append(
          self.type_parameters[type_param.name].get_instance_type())
    return pytd_utils.MakeClassOrContainerType(
        pytd_utils.NamedOrExternalType(self.base_cls.pytd_cls.name,
                                       self.base_cls.module),
        type_arguments)


class PyTDClass(SimpleAbstractValue, Class):
  """An abstract wrapper for PyTD class objects.

  These are the abstract values for class objects that are described in PyTD.

  Attributes:
    cls: A pytd.Class
    mro: Method resolution order. An iterable of AtomicAbstractValue.
  """
  is_lazy = True  # uses _convert_member

  def __init__(self, name, pytd_cls, vm):
    super(PyTDClass, self).__init__(name, vm)
    mm = {}
    for val in pytd_cls.constants + pytd_cls.methods:
      mm[val.name] = val
    self._member_map = mm
    Class.init_mixin(self)
    self.pytd_cls = pytd_cls
    self.mro = utils.compute_mro(self)

  def get_attribute(self, node, name, valself=None, valcls=None):
    return Class.get_attribute(self, node, name, valself, valcls)

  def get_attribute_flat(self, node, name):
    # get_attribute_flat ?
    return SimpleAbstractValue.get_attribute(self, node, name)

  def bases(self):
    return [self.vm.convert_constant_to_value(pytd.Print(parent), parent)
            for parent in self.pytd_cls.parents]

  def _convert_member(self, name, pyval):
    """Convert a member as a variable. For lazy lookup."""
    if isinstance(pyval, pytd.Constant):
      return self.vm.create_pytd_instance(name, pyval.type, {},
                                          self.vm.root_cfg_node)
    elif isinstance(pyval, pytd.Function):
      c = self.vm.convert_constant_to_value(repr(pyval), pyval)
      c.parent = self
      return c.to_variable(self.vm.root_cfg_node, name)
    else:
      raise AssertionError("Invalid class member %s", pytd.Print(pyval))

  def call(self, node, func, posargs, namedargs,
           starargs=None, starstarargs=None):
    value = Instance(self.vm.convert_constant(
        self.name, self.pytd_cls), self.vm)

    for type_param in self.pytd_cls.template:
      value.type_parameters[type_param.name] = self.vm.program.NewVariable(
          type_param.name)

    results = self.vm.program.NewVariable(self.name)
    retval = results.AddValue(value, [func], node)

    node, init = value.get_attribute(node, "__init__", retval,
                                     value.cls.values[0])
    # TODO(pludemann): Verify that this follows MRO:
    if init:
      log.debug("calling %s.__init__(...)", self.name)
      node, ret = self.vm.call_function(node, init, posargs, namedargs,
                                        starargs=starargs,
                                        starstarargs=starstarargs)
      log.debug("%s.__init__(...) returned %r", self.name, ret)

    return node, results

  def to_type(self):
    return pytd.NamedType("type")

  def get_instance_type(self, instance=None):
    """Convert instances of this class to their PYTD type."""
    type_arguments = []
    for type_param in self.pytd_cls.template:
      if instance is not None and type_param.name in instance.type_parameters:
        param = instance.type_parameters[type_param.name]
        type_arguments.append(pytd_utils.JoinTypes(
            v.data.to_type() for v in param.values))
      else:
        type_arguments.append(pytd.AnythingType())
    return pytd_utils.MakeClassOrContainerType(
        pytd_utils.NamedOrExternalType(self.name, self.module),
        type_arguments)

  def __repr__(self):
    return self.name

  def _match_instance(self, instance, other_type, subst, node, view):
    """Used by match_instance_against_type. Matches each MRO entry."""
    if other_type is self:
      return subst
    elif (isinstance(other_type, ParameterizedClass) and
          other_type.base_cls is self):
      extra_params = (set(instance.type_parameters) -
                      set(other_type.type_parameters))
      assert not extra_params
      for name, class_param in other_type.type_parameters.items():
        instance_param = instance.get_type_parameter(node, name)
        subst = match_var_against_type(instance_param, class_param, subst,
                                       node, view)
        if subst is None:
          return None
      return subst
    return None

  def match_instance_against_type(self, instance, other_type,
                                  subst, node, view):
    """Match an instance of this class against an other type."""
    for cls in self.mro:
      # pylint: disable=protected-access
      new_subst = cls._match_instance(instance, other_type, subst, node, view)
      if new_subst is not None:
        return new_subst

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name in ["type", "object"]:
      return subst

  def to_pytd_def(self, name):
    # This happens if a module does e.g. "from x import y as z", i.e., copies
    # something from another module to the local namespace. We *could*
    # reproduce the entire class, but we choose a more dense representation.
    return pytd.NamedType("type")


class InterpreterClass(SimpleAbstractValue, Class):
  """An abstract wrapper for user-defined class objects.

  These are the abstract value for class objects that are implemented in the
  program.
  """

  def __init__(self, name, bases, members, vm):
    assert isinstance(name, str)
    assert isinstance(bases, list)
    assert isinstance(members, dict)
    super(InterpreterClass, self).__init__(name, vm)
    Class.init_mixin(self)
    self._bases = bases
    self.mro = utils.compute_mro(self)
    self.members = utils.MonitorDict(members)
    self.instances = set()  # filled through register_instance
    self._instance_cache = {}
    log.info("Created class: %r", self)

  def register_instance(self, instance):
    self.instances.add(instance)

  def bases(self):
    return utils.concat_lists(b.data for b in self._bases)

  def get_attribute_flat(self, node, name):
    return SimpleAbstractValue.get_attribute(self, node, name)

  def get_attribute(self, node, name, valself=None, valcls=None):
    node, attr_var = Class.get_attribute(self, node, name, valself, valcls)
    result = self.vm.program.NewVariable(name)
    nodes = []
    # Deal with descriptors as a potential additional level of indirection.
    for v in attr_var.Values(node):
      value = v.data
      node2, getter = value.get_attribute(node, "__get__", v)
      if getter is not None:
        node2, get_result = self.vm.call_function(
            node2, getter, [getter, value.get_class()])
        for getter in get_result.values:
          result.AddValue(getter.data, [getter], node2)
      else:
        result.AddValue(value, [v], node2)
      nodes.append(node2)
    if nodes:
      return self.vm.join_cfg_nodes(nodes), result
    else:
      return node, None

  def set_attribute(self, node, name, value):
    # Note that even if we have a superclass that already has an attribute
    # with this name, Python will still set the (possibly new) attribute
    # on this class, thus shadowing the one on the superclass. Hence MRO doesn't
    # come into play.
    return super(InterpreterClass, self).set_attribute(node, name, value)

  def _new_instance(self, node, value):
    # We allow only one "instance" per code location, regardless of call stack.
    key = self.vm.frame.current_opcode
    if key not in self._instance_cache:
      cls = self.vm.program.NewVariable(self.name)
      cls.AddValue(self, [value], node)
      self._instance_cache[key] = Instance(cls, self.vm)
    return self._instance_cache[key]

  def call(self, node, value, posargs, namedargs,
           starargs=None, starstarargs=None):
    value = self._new_instance(node, value)
    variable = self.vm.program.NewVariable(self.name + " instance")
    val = variable.AddValue(value, [], node)
    node, init = value.get_attribute(node, "__init__", val)
    if init:
      log.debug("calling %s.__init__(...)", self.name)
      node, ret = self.vm.call_function(node, init, posargs, namedargs,
                                        starargs, starstarargs)
      log.debug("%s.__init__(...) returned %r", self.name, ret)
    return node, variable

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name in ["type", "object"]:
      return subst

  def match_instance_against_type(self, instance, other_type,
                                  subst, node, view):
    if other_type.name == "object":
      return subst
    if isinstance(other_type, Class):
      for base in self.mro:
        if isinstance(base, Class):
          if base is other_type:
            return subst
        elif isinstance(base, (Unknown, Unsolvable)):
          # See match_Function_against_Class in type_match.py. Even though it's
          # possible that this Unknown is of type other_type, our class would
          # then be a match for *everything*. Hence, return False, to keep
          # the list of possible types from exploding.
          return None
        else:
          raise AssertionError("Bad base class %r", base)
      return None
    elif isinstance(other_type, Nothing):
      return None
    else:
      raise NotImplementedError(
          "Can't match instance %r against %r", self, other_type)

  def to_type(self):
    return pytd.NamedType("type")

  def to_pytd_def(self, class_name):
    methods = []
    constants = collections.defaultdict(pytd_utils.TypeBuilder)

    # class-level attributes
    for name, member in self.members.items():
      if name not in output.CLASS_LEVEL_IGNORE:
        for value in member.FilteredData(self.vm.exitpoint):
          if isinstance(value, Function):
            v = value.to_pytd_def(name)
            if isinstance(v, pytd.Function):
              methods.append(v)
            elif isinstance(v, pytd.TYPE):
              constants[name].add_type(v)
            else:
              raise AssertionError(str(type(v)))
          else:
            constants[name].add_type(value.to_type())

    # instance-level attributes
    for instance in self.instances:
      for name, member in instance.members.items():
        if name not in output.CLASS_LEVEL_IGNORE:
          for value in member.FilteredData(self.vm.exitpoint):
            constants[name].add_type(value.to_type())

    bases = [pytd_utils.JoinTypes(b.get_instance_type()
                                  for b in basevar.data)
             for basevar in self._bases]
    constants = [pytd.Constant(name, builder.build())
                 for name, builder in constants.items()
                 if builder]
    return pytd.Class(name=class_name,
                      parents=tuple(bases),
                      methods=tuple(methods),
                      constants=tuple(constants),
                      template=())

  def get_instance_type(self, unused_instance=None):
    if self.official_name:
      return pytd_utils.NamedOrExternalType(self.official_name, self.module)
    else:
      return pytd.AnythingType()

  def __repr__(self):
    return "InterpreterClass(%s)" % self.name


class NativeFunction(Function):
  """An abstract value representing a native function.

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    func: An object with a __call__ method.
    vm: TypegraphVirtualMachine instance.
  """

  def __init__(self, name, func, vm):
    super(NativeFunction, self).__init__(name, vm)
    self.name = name
    self.func = func
    self.cls = self.vm.function_type

  def argcount(self):
    return self.func.func_code.co_argcount

  def call(self, node, unused_func, posargs, namedargs,
           starargs=None, starstarargs=None):
    # Originate a new variable for each argument and call.
    return self.func(
        node,
        *[u.AssignToNewVariable(u.name, node)
          for u in posargs],
        **{k: u.AssignToNewVariable(u.name, node)
           for k, u in namedargs.items()})

  def get_parameter_names(self):
    code = self.func.func_code
    return list(code.co_varnames[:code.co_argcount])


class InterpreterFunction(Function):
  """An abstract value representing a user-defined function.

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    code: A code object.
    closure: Tuple of cells (typegraph.Variable) containing the free variables
      this closure binds to.
    vm: TypegraphVirtualMachine instance.
  """

  _function_cache = {}

  @staticmethod
  def make_function(name, code, f_locals, f_globals, defaults, closure, vm):
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
      closure: The free variables this closure binds to.
      vm: VirtualMachine instance.

    Returns:
      An InterpreterFunction.
    """
    key = (name, code,
           InterpreterFunction._hash_all(
               (f_globals.members, set(code.co_names)),
               (f_locals.members, set(code.co_varnames)),
               (dict(enumerate(defaults)), None),
               (dict(enumerate(closure or ())), None)))
    if key not in InterpreterFunction._function_cache:
      InterpreterFunction._function_cache[key] = InterpreterFunction(
          name, code, f_locals, f_globals, defaults, closure, vm)
    return InterpreterFunction._function_cache[key]

  def __init__(self, name, code, f_locals, f_globals, defaults, closure, vm):
    super(InterpreterFunction, self).__init__(name, vm)
    log.debug("Creating InterpreterFunction %r for %r", name, code.co_name)
    self.bound_class = BoundInterpreterFunction
    self.doc = code.co_consts[0] if code.co_consts else None
    self.name = name
    self.code = code
    self.f_globals = f_globals
    self.f_locals = f_locals
    self.defaults = tuple(defaults)
    self.closure = closure
    self.cls = self.vm.function_type
    self._call_records = {}

  # TODO(kramm): support retrieving the following attributes:
  # 'func_{code, name, defaults, globals, locals, dict, closure},
  # '__name__', '__dict__', '__doc__', '_vm', '_func'

  def get_first_opcode(self):
    return self.code.co_code[0]

  def is_closure(self):
    return self.closure is not None

  def argcount(self):
    return self.code.co_argcount

  def _map_args(self, node, posargs, namedargs, starargs, starstarargs):
    """Map call args to function args.

    This emulates how Python would map arguments of function calls. It takes
    care of keyword parameters, default parameters, and *args and **kwargs.

    Args:
      node: The current CFG node.
      posargs: The positional arguments. A tuple of typegraph.Variable.
      namedargs: The keyword arguments. A dictionary, mapping strings to
        typegraph.Variable.
      starargs: The *args parameter, or None.
      starstarargs: The **kwargs parameter, or None.

    Returns:
      A dictionary, mapping strings (parameter names) to typegraph.Variable.

    Raises:
      ByteCodeTypeError
    """
    # Originate a new variable for each argument and call.
    args = [u.AssignToNewVariable(u.name, node)
            for u in posargs]
    kws = {k: u.AssignToNewVariable(u.name, node)
           for k, u in namedargs.items()}
    if (self.vm.python_version[0] == 2 and
        self.code.co_name in ["<setcomp>", "<dictcomp>", "<genexpr>"]):
      # This code is from github.com/nedbat/byterun. Apparently, Py2 doesn't
      # know how to inspect set comprehensions, dict comprehensions, or
      # generator expressions properly. See http://bugs.python.org/issue19611.
      # Byterun says: "They are always functions of one argument, so just do the
      # right thing."
      assert len(args) == 1, "Surprising comprehension!"
      return {".0": args[0]}
    param_names = self.get_parameter_names()
    num_defaults = len(self.defaults)
    callargs = dict(zip(param_names[-num_defaults:], self.defaults))
    positional = dict(zip(param_names, args))
    for key in positional.keys():
      if key in kws:
        raise exceptions.ByteCodeTypeError(
            "function got multiple values for keyword argument %r" % key)
    callargs.update(positional)
    callargs.update(kws)
    for key in param_names:
      if key not in callargs:
        raise exceptions.ByteCodeTypeError(
            "No value for parameter %r" % key)
    arg_pos = self.code.co_argcount
    if self.has_varargs():
      vararg_name = self.code.co_varnames[arg_pos]
      extraneous = args[self.code.co_argcount:]
      if starargs:
        if extraneous:
          log.warning("Not adding extra params to *%s", vararg_name)
        callargs[vararg_name] = starargs.AssignToNewVariable(
            "*args", node)
      else:
        callargs[vararg_name] = self.vm.build_tuple(node, extraneous)
      arg_pos += 1
    elif len(args) > self.code.co_argcount:
      raise exceptions.ByteCodeTypeError(
          "Function takes %d positional arguments (%d given)" % (
              arg_pos, len(args)))
    if self.has_kwargs():
      kwvararg_name = self.code.co_varnames[arg_pos]
      # Build a **kwargs dictionary out of the extraneous parameters
      if starstarargs:
        # TODO(kramm): modify type parameters to account for namedargs
        callargs[kwvararg_name] = starstarargs.AssignToNewVariable(
            "**kwargs", node)
      else:
        k = Dict("kwargs", self.vm)
        k.update(node, namedargs, omit=param_names)
        callargs[kwvararg_name] = k.to_variable(node, kwvararg_name)
      arg_pos += 1
    return callargs

  @staticmethod
  def _hash(vardict, names):
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
      m.update(str(name))
      for value in var.values:
        m.update(value.data.get_fullhash())
    return m.digest()

  @staticmethod
  def _hash_all(*hash_args):
    """Convenience method for hashing a sequence of dicts."""
    return hashlib.md5("".join(InterpreterFunction._hash(*args)
                               for args in hash_args)).digest()

  def call(self, node, unused_func, posargs, namedargs,
           starargs=None, starstarargs=None):
    if self.vm.is_at_maximum_depth():
      log.info("Maximum depth reached. Not analyzing %r", self.name)
      return node, self.vm.program.NewVariable(self.name + ":ret", [], [], node)
    callargs = self._map_args(node, posargs, namedargs, starargs, starstarargs)
    # Might throw vm.RecursionException:
    frame = self.vm.make_frame(node, self.code, callargs,
                               self.f_globals, self.f_locals, self.closure)
    if self.vm.options.skip_repeat_calls:
      callkey = self._hash_all(
          (callargs, None),
          (frame.f_globals.members, set(self.code.co_names)),
          (frame.f_locals.members, set(self.code.co_varnames)))
    else:
      # Make the callkey the number of times this function has been called so
      # that no call has the same key as a previous one.
      callkey = len(self._call_records)
    if callkey in self._call_records:
      _, old_ret, _ = self._call_records[callkey]
      # Optimization: This function has already been called, with the same
      # environment and arguments, so recycle the old return value and don't
      # record this call. We pretend that this return value originated at the
      # current node to make sure we don't miss any possible types.
      ret = self.vm.program.NewVariable(old_ret.name, old_ret.data, [], node)
      return node, ret
    if self.code.co_flags & loadmarshal.CodeType.CO_GENERATOR:
      generator = Generator(frame, self.vm)
      # Run the generator right now, even though the program didn't call it,
      # because we need to know the contained type for futher matching.
      node2, _ = generator.run_until_yield(node)
      node_after_call, ret = node2, generator.to_variable(node2, self.name)
    else:
      node_after_call, ret = self.vm.run_frame(frame, node)
    self._call_records[callkey] = (callargs, ret, node_after_call)
    return node_after_call, ret

  def _get_call_combinations(self):
    signature_data = set()
    for callargs, ret, node_after_call in self._call_records.values():
      for combination in utils.variable_product_dict(callargs):
        for return_value in ret.values:
          values = combination.values() + [return_value]
          data = tuple(v.data for v in values)
          if data in signature_data:
            # This combination yields a signature we already know is possible
            continue
          if node_after_call.HasCombination(values):
            signature_data.add(data)
            yield combination, return_value

  def _fix_param_name(self, name):
    """Sanitize a parameter name; remove Python intrinstics."""
    # Python uses ".0" etc. for parameters that are tuples, like e.g. in:
    # "def f((x, y), z)".
    return name.replace(".", "_")

  def to_pytd_def(self, function_name):
    """Generate a pytd.Function definition."""
    num_defaults = len(self.defaults)
    signatures = []
    has_optional = num_defaults > 0 or self.has_varargs() or self.has_kwargs()
    for combination, return_value in self._get_call_combinations():
      params = tuple(pytd.Parameter(self._fix_param_name(name),
                                    combination[name].data.to_type())
                     for name in self.get_parameter_names())
      if num_defaults:
        params = params[:-num_defaults]
      signatures.append(pytd.Signature(
          params=params, return_type=return_value.data.to_type(),
          exceptions=(),  # TODO(kramm): record exceptions
          template=(), has_optional=has_optional))
    if signatures:
      return pytd.Function(function_name, tuple(signatures), pytd.METHOD)
    else:
      # Fallback: Generate a pytd signature only from the definition of the
      # method, not the way it's being used.
      return pytd.Function(function_name, (self.simple_pytd_signature(),),
                           pytd.METHOD)

  def simple_pytd_signature(self):
    return pytd.Signature(
        params=tuple(pytd.Parameter(name, pytd.NamedType("object"))
                     for name in self.get_parameter_names()),
        return_type=pytd.AnythingType(),
        exceptions=(), template=(), has_optional=bool(self.defaults))

  def get_parameter_names(self):
    return list(self.code.co_varnames[:self.code.co_argcount])

  def has_varargs(self):
    return bool(self.code.co_flags & loadmarshal.CodeType.CO_VARARGS)

  def has_kwargs(self):
    return bool(self.code.co_flags & loadmarshal.CodeType.CO_VARKEYWORDS)


class BoundFunction(AtomicAbstractValue):
  """An function type which has had an argument bound into it."""

  def __init__(self, callself, underlying):
    super(BoundFunction, self).__init__(underlying.name, underlying.vm)
    self._callself = callself
    self.underlying = underlying

  def get_attribute(self, node, name, valself=None, valcls=None):
    return self.underlying.get_attribute(node, name, valself, valcls)

  def set_attribute(self, node, name, value):
    return self.underlying.set_attribute(node, name, value)

  def argcount(self):
    return self.underlying.argcount() - 1  # account for self

  def call(self, node, func, posargs, namedargs,
           starargs=None, starstarargs=None):
    return self.underlying.call(node, func, [self._callself] + posargs,
                                namedargs, starargs, starstarargs)

  def get_bound_arguments(self):
    return [self._callself]

  def get_parameter_names(self):
    return self.underlying.get_parameter_names()

  def has_varargs(self):
    return self.underlying.has_varargs()

  def has_kwargs(self):
    return self.underlying.has_kwargs()

  def to_type(self):
    return pytd.NamedType("function")

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name in ["function", "object"]:
      return subst


class BoundInterpreterFunction(BoundFunction):
  """The method flavor of InterpreterFunction."""

  def get_first_opcode(self):
    return self.underlying.code.co_code[0]


class BoundPyTDFunction(BoundFunction):
  pass


class Generator(Instance):
  """A representation of instances of generators.

  (I.e., the return type of coroutines).
  """

  TYPE_PARAM = "T"  # See class generator in pytd/builtins/__builtin__.pytd

  def __init__(self, generator_frame, vm):
    super(Generator, self).__init__(vm.generator_type, vm)
    self.generator_frame = generator_frame
    self.runs = 0

  def get_attribute(self, node, name, valself=None, valcls=None):
    if name == "__iter__":
      f = NativeFunction(name, self.__iter__, self.vm)
      return node, f.to_variable(node, name)
    elif name in ["next", "__next__"]:
      return node, self.to_variable(node, name)
    elif name == "throw":
      # We don't model exceptions in a way that would allow us to induce one
      # inside a coroutine. So just return ourselves, mapping the call of
      # throw() to a next() (which won't be executed).
      return node, self.to_variable(node, name)
    else:
      return node, None

  def __iter__(self, node):  # pylint: disable=non-iterator-returned,unexpected-special-method-signature
    return node, self.to_variable(node, "__iter__")

  def run_until_yield(self, node):
    if self.runs == 0:  # Optimization: We only run the coroutine once.
      node, _ = self.vm.resume_frame(node, self.generator_frame)
      contained_type = self.generator_frame.yield_variable
      self.type_parameters[self.TYPE_PARAM] = contained_type
      self.runs += 1
    return node, self.type_parameters[self.TYPE_PARAM]

  def call(self, node, unused_func, posargs, namedargs,
           starargs=None, starstarargs=None):
    """Call this generator or (more common) its "next" attribute."""
    return self.run_until_yield(node)


class Nothing(AtomicAbstractValue, FormalType):
  """The VM representation of Nothing values.

  These are fake values that never exist at runtime, but they appear if you, for
  example, extract a value from an empty list.
  """

  def __init__(self, vm):
    super(Nothing, self).__init__("nothing", vm)

  def get_attribute(self, node, name, valself=None, valcls=None):
    return node, None

  def set_attribute(self, node, name, value):
    raise AttributeError("Object %r has no attribute %s" % (self, name))

  def call(self, node, unused_func, posargs, namedargs,
           starargs=None, starstarargs=None):
    raise AssertionError("Can't call empty object ('nothing')")

  def to_type(self):
    return pytd.NothingType()

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name == "nothing":
      return subst
    else:
      return None


class Module(Instance):
  """Represents an (imported) module."""

  is_lazy = True  # uses _convert_member

  def __init__(self, vm, name, member_map):
    super(Module, self).__init__(vm.module_type, vm=vm)
    self.name = name
    self._member_map = member_map

  def _convert_member(self, name, ty):
    """Called to convert the items in _member_map to cfg.Variable."""
    var = self.vm.convert_constant(name, ty)
    for value in var.data:
      # Only do this if this class isn't already part of a module.
      # (This happens if e.g. foo.py does "from bar import x" and we then
      #  do "from foo import x".)
      if not value.module:
        value.module = self.name
    return var

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

  def get_attribute(self, node, name, valself=None, valcls=None):
    # Local variables in __init__.py take precedence over submodules.
    node, var = super(Module, self).get_attribute(node, name, valself, valcls)
    if var is None:
      full_name = self.name + "." + name
      mod = self.vm.import_module(full_name, 0)  # 0: absolute import
      if mod is not None:
        var = mod.to_variable(node, name)
      elif self.has_getattr():
        var = self.vm.create_new_unsolvable(node, full_name)
      else:
        log.warning("Couldn't find attribute / module %r", full_name)
    return node, var

  def set_attribute(self, node, name, value):  # pylint: disable=unused-argument
    # Assigning attributes on modules is pretty common. E.g.
    # sys.path, sys.excepthook.
    log.warning("Ignoring overwrite of %s.%s using", self.name, name)
    return node

  def items(self):
    return [(name, self._convert_member(name, ty))
            for name, ty in self._member_map.items()]

  def to_type(self):
    return pytd.NamedType("module")

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name in ["module", "object"]:
      return subst


class Unsolvable(AtomicAbstractValue):
  """Representation of value we know nothing about.

  Unlike "Unknowns", we don't treat these as solveable. We just put them
  where values are needed, but make no effort to later try to map them
  to named types. This helps conserve memory where creating and solving
  hundreds of unknowns would yield us little to no information.
  """
  IGNORED_ATTRIBUTES = ["__get__", "__set__"]

  def __init__(self, vm):
    super(Unsolvable, self).__init__("unsolveable", vm)

  def get_attribute(self, node, name, valself=None, valcls=None):
    if name in self.IGNORED_ATTRIBUTES:
      return node, None
    return node, self.to_variable(node, self.name)

  def get_attribute_flat(self, node, name):
    return self.get_attribute(node, name)

  def set_attribute(self, node, name, _):
    return node

  def call(self, node, unused_func, posargs, namedargs,
           starargs=None, starstarargs=None):
    return node, self.to_variable(node, self.name)

  def to_variable(self, node, name=None):
    return self.vm.program.NewVariable(name, [self], source_set=[], where=node)

  def get_class(self):
    return self.to_variable(self.vm.root_cfg_node, self.name)

  def to_pytd_def(self, name):
    """Convert this Unknown to a pytd.Class."""
    return pytd.Constant(name, self.to_type())

  def to_type(self):
    return pytd.AnythingType()

  def get_instance_type(self, unused_instance=None):
    return pytd.AnythingType()

  def match_against_type(self, other_type, subst, node, view):
    if isinstance(other_type, ParameterizedClass):
      return None
    else:
      return subst


class Unknown(AtomicAbstractValue):
  """Representation of unknown values.

  These are e.g. the return values of certain functions (e.g. eval()). They
  "adapt": E.g. they'll respond to get_attribute requests by creating that
  attribute.

  Attributes:
    members: Attributes that were written or read so far. Mapping of str to
      typegraph.Variable.
    owner: typegraph.Value that contains this instance as data.
  """

  _current_id = 0

  # For simplicity, Unknown doesn't emulate descriptors:
  IGNORED_ATTRIBUTES = ["__get__", "__set__"]

  def __init__(self, vm):
    name = "~unknown%d" % Unknown._current_id
    super(Unknown, self).__init__(name, vm)
    self.members = utils.MonitorDict()
    self.owner = None
    Unknown._current_id += 1
    self.class_name = self.name
    self._calls = []
    log.info("Creating %s", self.class_name)

  def get_children_maps(self):
    return (self.members,)

  @staticmethod
  def _to_pytd(v):
    if isinstance(v, typegraph.Variable):
      return pytd_utils.JoinTypes(Unknown._to_pytd(t) for t in v.data)
    elif isinstance(v, Unknown):
      # Do this directly, and use NamedType, in case there's a circular
      # dependency among the Unknown instances.
      return pytd.NamedType(v.class_name)
    else:
      return v.to_type()

  @staticmethod
  def _make_params(args):
    """Convert a list of types/variables to pytd parameters."""
    return tuple(pytd.Parameter("_%d" % (i + 1), Unknown._to_pytd(p))
                 for i, p in enumerate(args))

  def get_attribute(self, node, name, valself=None, valcls=None):
    if name in self.IGNORED_ATTRIBUTES:
      return node, None
    if name in self.members:
      return node, self.members[name]
    new = self.vm.create_new_unknown(self.vm.root_cfg_node,
                                     self.name + "." + name,
                                     action="getattr:" + name)
    # We store this at the root node, even though we only just created this.
    # From the analyzing point of view, we don't know when the "real" version
    # of this attribute (the one that's not an unknown) gets created, hence
    # we assume it's there since the program start.  If something overwrites it
    # in some later CFG node, that's fine, we'll then work only with the new
    # value, which is more accurate than the "fictional" value we create here.
    self.set_attribute(self.vm.root_cfg_node, name, new)
    return node, new

  def get_attribute_flat(self, node, name):
    # Unknown objects don't have an MRO, so this is the same as get_attribute.
    return self.get_attribute(node, name)

  def set_attribute(self, node, name, v):
    if name in self.members:
      self.members[name].PasteVariable(v, node)
    else:
      self.members[name] = v.AssignToNewVariable(self.name + "." + name, node)
    return node

  def call(self, node, unused_func, posargs, namedargs,
           starargs=None, starstarargs=None):
    ret = self.vm.create_new_unknown(node, self.name + "()", source=self.owner,
                                     action="call:" + self.name)
    self._calls.append((posargs, namedargs, ret))
    return node, ret

  def to_variable(self, node, name=None):
    v = self.vm.program.NewVariable(self.name or name)
    val = v.AddValue(self, source_set=[], where=node)
    self.owner = val
    self.vm.trace_unknown(self.class_name, v)
    return v

  def to_structural_def(self, class_name):
    """Convert this Unknown to a pytd.Class."""
    self_param = (pytd.Parameter("self", pytd.NamedType("object")),)
    calls = tuple(pytd_utils.OrderedSet(
        pytd.Signature(params=self_param + self._make_params(args),
                       return_type=Unknown._to_pytd(ret),
                       exceptions=(),
                       template=(),
                       has_optional=False)
        for args, _, ret in self._calls))
    if calls:
      methods = (pytd.Function("__call__", calls, pytd.METHOD),)
    else:
      methods = ()
    return pytd.Class(
        name=class_name,
        parents=(pytd.NamedType("object"),),
        methods=methods,
        constants=tuple(pytd.Constant(name, Unknown._to_pytd(c))
                        for name, c in self.members.items()),
        template=())

  def get_class(self):
    # We treat instances of an Unknown as the same as the class.
    return self.to_variable(self.vm.root_cfg_node, "class of " + self.name)

  def to_type(self):
    return pytd.NamedType(self.class_name)

  def get_instance_type(self, unused_instance=None):
    log.info("Using ? for instance of %s", self.name)
    return pytd.AnythingType()

  def match_against_type(self, other_type, subst, node, view):
    # TODO(kramm): Do we want to match the instance or the class?
    if isinstance(other_type, ParameterizedClass):
      return None
    return subst
