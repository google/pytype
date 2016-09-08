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
from pytype import function
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


class ConversionError(ValueError):
  pass


class AsInstance(object):
  """Wrapper, used for marking things that we want to convert to an instance."""

  def __init__(self, cls):
    self.cls = cls


def variable_set_official_name(variable, name):
  """Set official_name on each value in the variable.

  Called for each entry in the top-level locals().

  Args:
    variable: A typegraph.Variable to name.
    name: The name to give.
  """
  for v in variable.bindings:
    v.data.official_name = name


def get_atomic_value(variable):
  if len(variable.bindings) == 1:
    return variable.bindings[0].data
  else:
    raise ConversionError(
        "Variable with too many options when trying to get atomic value. %s %s"
        % (variable, [a.data for a in variable.bindings]))


def get_atomic_python_constant(variable):
  """Get the concrete atomic Python value stored in this variable.

  This is used for things that are stored in typegraph.Variable, but we
  need the actual data in order to proceed. E.g. function / class defintions.

  Args:
    variable: A typegraph.Variable. It can only have one possible value.
  Returns:
    A Python constant. (Typically, a string, a tuple, or a code object.)
  Raises:
    ValueError: If the value in this Variable is purely abstract, i.e. doesn't
      store a Python value, or if it has more than one possible value.
    IndexError: If there is more than one possibility for this value.
  """
  atomic = get_atomic_value(variable)
  if isinstance(atomic, PythonConstant):
    return atomic.pyval
  raise ConversionError("Only some types are supported: %r" % type(atomic))


def match_var_against_type(var, other_type, subst, node, view):
  if hasattr(other_type, "match_var_against"):
    return other_type.match_var_against(var, subst, node, view)
  elif var.bindings:
    return _match_value_against_type(view[var], other_type, subst, node, view)
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
          subst = subst.copy()
          subst[right.name] = var.program.NewVariable("empty")
        return subst
    return None


# TODO(kramm): This needs to match values, not variables. A variable can
# consist of different types.
def _match_value_against_type(value, other_type, subst, node, view):
  """One-way unify value into pytd type given a substitution.

  Args:
    value: A typegraph.Binding
    other_type: An AtomicAbstractValue instance.
    subst: The current substitution. This dictionary is not modified.
    node: Current location (typegraph CFG node)
    view: A mapping of Variable to Value.
  Returns:
    A new (or unmodified original) substitution dict if the matching succeded,
    None otherwise.
  """
  left = value.data
  assert isinstance(left, AtomicAbstractValue), left
  assert not isinstance(left, FormalType)

  # TODO(kramm): Use view

  if isinstance(other_type, Class):
    # Accumulate substitutions in "subst", or break in case of error:
    return left.match_against_type(other_type, subst, node, view)
  elif isinstance(other_type, Union):
    for t in other_type.options:
      new_subst = _match_value_against_type(value, t, subst, node, view)
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
      new_var.AddBinding(left, [], node)
      subst[other_type.name] = new_var
    else:
      subst = subst.copy()
      subst[other_type.name] = new_var = value.AssignToNewVariable(
          other_type.name, node)
    type_key = left.get_type_key()
    # Every value with this type key produces the same result when matched
    # against other_type, so they can all be added to this substitution rather
    # than matched separately.
    for other_value in value.variable.bindings:
      if (other_value is not value and
          other_value.data.get_type_key() == type_key):
        new_var.AddBinding(other_value.data, {other_value}, node)
    return subst
  elif (isinstance(other_type, (Unknown, Unsolvable)) or
        isinstance(left, (Unknown, Unsolvable))):
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


def bad_matches(var, other_type, node, subst=None):
  """Match an Variable against a type. Return bindings that don't match.

  Args:
    var: A cfg.Variable, containing instances.
    other_type: An instance of AtomicAbstractValue.
    node: A cfg.CFGNode. The position in the CFG from which we "observe" the
      match.
    subst: Type parameter substitutions.
  Returns:
    A list of all the bindings of var that didn't match.
  """
  subst = subst or {}
  bad = []
  for combination in utils.deep_variable_product([var]):
    view = {value.variable: value for value in combination}
    if match_var_against_type(var, other_type, subst,
                              node, view) is None:
      bad.append(view[var])
  return bad


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
    assert hasattr(vm, "program"), type(self)
    self.vm = vm
    self.mro = []
    self.cls = None
    AtomicAbstractValue._value_id += 1
    self.id = AtomicAbstractValue._value_id
    self.name = name
    self.module = None
    self.official_name = None

  @property
  def full_name(self):
    return (self.module + "." if self.module else "") + self.name

  def __str__(self):
    return self.name

  def default_mro(self):
    return [self, self.vm.convert.object_type.data[0]]

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

  def get_type_parameter(self, node, name):
    return self.vm.convert.create_new_unsolvable(node, name)

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

  def get_attribute_generic(self, node, name, val):
    return self.get_attribute(node, name, valself=val)

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    """Get the named attribute from this object.

    Args:
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
    del name, valself, valcls, condition  # unused args.
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

  def call(self, node, func, args):
    """Call this abstract value with the given arguments.

    The posargs and namedargs arguments may be modified by this function.

    Args:
      node: The CFGNode calling this function
      func: The typegraph.Binding containing this function.
      args: Arguments for the call.
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

  def get_instance_type(self, node, instance=None, seen=None):
    """Return the type an instance of us would have."""
    # We don't know whether we even *are* a type, so the default is anything.
    del node, instance, seen
    return pytd.AnythingType()

  def to_type(self, node, seen=None):
    """Get a PyTD type representing this object, as seen at a node."""
    raise NotImplementedError(self.__class__.__name__)

  def get_default_type_key(self):
    """Gets a default type key. See get_type_key."""
    return type(self)

  def get_type_key(self, seen=None):  # pylint: disable=unused-argument
    """Build a key from the information used to perform type matching.

    Get a hashable object containing this value's type information. Type keys
    are only compared amongst themselves, so we don't care what the internals
    look like, only that values with different types *always* have different
    type keys and values with the same type preferably have the same type key.

    Args:
      seen: The set of values seen before while computing the type key.

    Returns:
      A hashable object built from this value's type information.
    """
    return self.get_default_type_key()

  def instantiate(self, node):
    return Instance(self.to_variable(node, self.name),
                    self.vm, node).to_variable(node, self.name)

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
    v.AddBinding(self, source_set=[], where=node)
    return v

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

  def compatible_with(self, logical_value):  # pylint: disable=unused-argument
    """Returns the conditions under which the value could be True or False.

    Args:
      logical_value: Either True or False.

    Returns:
      False: If the value could not evaluate to logical_value under any
          circumstance (i.e. value is the empty list and logical_value is True).
      True: If it is possible for the value to evaluate to the logical_value,
          and any ambiguity cannot be described by additional bindings.
      DNF: A list of lists of bindings under which the value can evaluate to
          the logical value.  For example, isinstance() could be reduced
          to the set of bindings that would satisfy th isinstance() condition.
    """
    # By default a value is ambiguous - if could potentially evaluate to
    # either True or False, thus we return True here regardless of
    # logical_value.
    return True


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


class TypeParameterInstance(AtomicAbstractValue):
  """An instance of a type parameter."""

  def __init__(self, name, instance, vm):
    super(TypeParameterInstance, self).__init__(name, vm)
    self.instance = instance

  def to_type(self, node, seen=None):
    if (self.name in self.instance.type_parameters and
        self.instance.type_parameters[self.name].bindings):
      return pytd_utils.JoinTypes(t.to_type(
          node, seen) for t in self.instance.type_parameters[self.name].data)
    else:
      # The type parameter was never initialized
      return pytd.AnythingType()


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
    self.type_parameters = utils.LazyAliasingMonitorDict()

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
    if name in self.type_parameters:
      self.type_parameters[name].PasteVariable(value, node)
    else:
      self.type_parameters[name] = value

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
    self.type_parameters = utils.LazyAliasingMonitorDict(
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

  def _maybe_load_as_instance_attribute(self, node, name):
    for cls in self.cls.data:
      var = cls.get_as_instance_attribute(node, name, self)
      if var is not None:
        if name in self.members:
          self.members[name].PasteVariable(var, node)
        else:
          self.members[name] = var

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    node, attr = self._load_special_attribute(node, name)
    if attr is not None:
      return node, attr

    if self.is_lazy:
      self._load_lazy_attribute(name)

    # If we are looking up a member that we can determine is an instance
    # rather than a class attribute, add it to the instance's members.
    if valself:
      assert isinstance(self, Instance)
      if name not in self.members or not self.members[name].Bindings(node):
        # See test_generic.testInstanceAttributeVisible for an example of an
        # attribute in self.members needing to be reloaded.
        self._maybe_load_as_instance_attribute(node, name)

    candidates = []

    # Retrieve instance attribute
    if name in self.members:
      # Allow an instance attribute to shadow a class attribute, but only
      # if there's a path through the CFG that actually assigns it.
      # TODO(kramm): It would be more precise to check whether there's NOT any
      # path that DOESN'T have it.
      if self.members[name].Bindings(node):
        candidates.append(self.members[name])

    # Retrieve class attribute
    if not candidates and self.cls:
      nodes = []
      for clsval in self.cls.bindings:
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
        for binding in candidate.Bindings(node):
          val = binding.data
          if isinstance(val, TypeParameterInstance):
            var = val.instance.type_parameters[val.name]
            if var.Bindings(node):
              # If this type parameter has visible values, we want to add those
              # to the return value. Otherwise, we add the TypeParameterInstance
              # itself as a placeholder that can be passed around and converted
              # to Any after analysis.
              candidates.append(var)
              continue
          sources = {binding}
          if condition:
            sources.add(condition.binding)
          ret.AddBinding(val, sources, node)
      if not ret.bindings:
        return node, None
      return node, ret

  def set_attribute(self, node, name, var):
    assert isinstance(var, typegraph.Variable)

    if self.is_lazy:
      self._load_lazy_attribute(name)

    if name == "__class__":
      return self.set_class(node, var)

    if isinstance(self, Instance) and name not in self.members:
      # The previous value needs to be loaded at the root node so that
      # (1) it is overwritten by the current value and (2) it is still
      # visible on branches where the current value is not
      self._maybe_load_as_instance_attribute(self.vm.root_cfg_node, name)

    variable = self.members.get(name)
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
      long_name = self.name + "." + name
      variable = var.AssignToNewVariable(long_name, node)
      self.members[name] = variable
    return node

  def call(self, node, _, args):
    node, var = self.get_attribute(node, "__call__")
    self_var = self.to_variable(node, self.name)
    if var is not None and var.bindings:
      return self.vm.call_function(
          node, var, args.replace(posargs=[self_var] + args.posargs))
    else:
      raise NotCallable(self)

  def __str__(self):
    if self.cls:
      cls = self.cls.data[0]
      return "<instance of %s>" % cls.name
    else:
      return "<instance>"

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

  def to_type(self, node, seen=None):
    """Get a PyTD type representing this object, as seen at a node.

    This uses both the instance (for type parameters) as well as the class.

    Args:
      node: The node from which we want to observe this object.
      seen: The set of values seen before while computing the type.

    Returns:
      A PyTD Type
    """
    if self.cls:
      classvalues = (v.data for v in self.cls.bindings)
      types = []
      for cls in classvalues:
        types.append(cls.get_instance_type(node, self, seen=seen))
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
    if isinstance(self, Class):
      if other_type.name in ["type", "object", "Callable"]:
        return subst
      else:
        return None
    my_type = self.get_class()
    assert my_type
    assert isinstance(self, Instance)
    for my_cls in my_type.data:
      subst = my_cls.match_instance_against_type(self, other_type,
                                                 subst, node, view)
      if subst is None:
        return None
    return subst

  def get_type_key(self, seen=None):
    if not seen:
      seen = set()
    seen.add(self)
    key = set()
    if self.cls:
      clsval, = self.cls.bindings
      key.add(clsval.data)
    for name, var in self.type_parameters.items():
      subkey = frozenset(value.data.get_default_type_key() if value.data in seen
                         else value.data.get_type_key(seen)
                         for value in var.bindings)
      key.add((name, subkey))
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
    # we don't have to recompute this information in _match_value_against_type.
    return [{value.data.get_type_key(): value
             for value in parameter.bindings}.values()
            for parameter in parameters]


class Instance(SimpleAbstractValue):
  """An instance of some object."""

  # Fully qualified names of types that are parameterized containers.
  _CONTAINER_NAMES = set([
      "__builtin__.list", "__builtin__.set", "__builtin__.frozenset"])

  def __init__(self, clsvar, vm, node):
    super(Instance, self).__init__(clsvar.data[0].name, vm)
    self.cls = clsvar
    for cls in clsvar.data:
      cls.register_instance(self)
      for base in cls.mro:
        if isinstance(base, ParameterizedClass):
          for name, param in base.type_parameters.items():
            if not isinstance(param, FormalType):
              # We inherit from a ParameterizedClass with a non-formal
              # parameter, e.g., class Foo(List[int]). Initialize the
              # corresponding instance parameter appropriately.
              assert name not in self.type_parameters
              self.type_parameters.add_lazy_item(
                  name, param.instantiate, node)
            elif name != param.name:
              # We have type parameter renaming, e.g.,
              #  class List(Generic[T]): pass
              #  class Foo(List[U]): pass
              self.type_parameters.add_alias(name, param.name)

  def compatible_with(self, logical_value):  # pylint: disable=unused-argument
    # Containers with unset parameters and NoneType instances cannot match True.
    name = self._get_full_name()
    if logical_value and name in Instance._CONTAINER_NAMES:
      return bool(self.type_parameters["T"].bindings)
    elif name == "__builtin__.NoneType":
      return not logical_value
    return True

  def _get_full_name(self):
    try:
      return get_atomic_value(self.get_class()).full_name
    except ConversionError:
      return None


class ValueWithSlots(Instance):
  """Convenience class for overriding slots with custom methods.

  This makes it easier to emulate built-in classes like dict which need special
  handling of some magic methods (__setitem__ etc.)
  """

  def __init__(self, clsvar, vm, node):
    super(ValueWithSlots, self).__init__(clsvar, vm, node)
    self._slots = {}
    self._self = {}  # TODO(kramm): Find a better place to store these.
    self._super = {}
    self._function_cache = {}

  def make_native_function(self, name, method):
    key = (name, method)
    if key not in self._function_cache:
      self._function_cache[key] = NativeFunction(name, method, self.vm,
                                                 self.vm.root_cfg_node)
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
          node, self._super[name], FunctionArgs((self._self[name],) + args))
    else:
      ret = None
      log.error(
          "Can't call bound method %s: We don't know how it was bound.", name)
    return node, ret

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    """Get an attribute.

    Will delegate to SimpleAbstractValue if we don't have a slot for it.

    Arguments:
      node: The current CFG node.
      name: name of the attribute. If this is something like "__getitem__",
        the slot mechanism might kick in.
      valself: A typegraph.Binding. See AtomicAbstractValue.get_attribute.
      valcls: A typegraph.Binding. See AtomicAbstractValue.get_attribute.
      condition: A Condition.  See AtomicAbstractValue.get_attribute.

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

  def __init__(self, name, vm, node):
    super(Dict, self).__init__(vm.convert.dict_type, vm, node)
    self.name = name
    self._entries = {}
    self.set_slot("__getitem__", self.getitem_slot)
    self.set_slot("__setitem__", self.setitem_slot)
    self.init_type_parameters(self.KEY_TYPE_PARAM, self.VALUE_TYPE_PARAM)

  def getitem_slot(self, node, name_var):
    """Implements the __getitem__ slot."""
    results = []
    for val in name_var.bindings:
      try:
        name = self.vm.convert.convert_value_to_string(val.data)
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
        node, self.KEY_TYPE_PARAM, self.vm.convert.build_string(node, name))
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
    for val in name_var.bindings:
      try:
        name = self.vm.convert.convert_value_to_string(val.data)
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

  def compatible_with(self, logical_value):
    # Always compatible with False.  Compatible with True only if type
    # parameters have been established (meaning that the dict can be
    # non-empty).
    return (not logical_value or
            bool(self.type_parameters[self.KEY_TYPE_PARAM].bindings))


class AbstractOrConcreteValue(Instance, PythonConstant):
  """Abstract value with a concrete fallback."""

  def __init__(self, pyval, clsvar, vm, node):
    super(AbstractOrConcreteValue, self).__init__(clsvar, vm, node)
    PythonConstant.init_mixin(self, pyval)

  def compatible_with(self, logical_value):
    return bool(self.pyval) == logical_value


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

  def compatible_with(self, logical_value):
    return bool(self.pyval) == logical_value


class Union(AtomicAbstractValue, FormalType):
  """A list of types. Used for parameter matching.

  Attributes:
    options: Iterable of instances of AtomicAbstractValue.
  """

  def __init__(self, options, vm):
    super(Union, self).__init__("Union", vm)
    self.name = "Union[%s]" % ", ".join(sorted([str(t) for t in options]))
    self.options = options


class FunctionArgs(collections.namedtuple("_", ["posargs", "namedargs",
                                                "starargs", "starstarargs"])):

  def __new__(cls, posargs, namedargs=None, starargs=None, starstarargs=None):
    """Create arguments for a function under analysis.

    Args:
      posargs: The positional arguments. A tuple of typegraph.Variable.
      namedargs: The keyword arguments. A dictionary, mapping strings to
        typegraph.Variable.
      starargs: The *args parameter, or None.
      starstarargs: The **kwargs parameter, or None.
    Returns:
      A FunctionArgs instance.
    """
    cls.replace = cls._replace
    return super(cls, FunctionArgs).__new__(
        cls, posargs=posargs, namedargs=namedargs or {}, starargs=starargs,
        starstarargs=starstarargs)


class FailedFunctionCall(Exception):
  """Exception for failed function calls."""


class NotCallable(FailedFunctionCall):
  """For objects that don't have __call__."""

  def __init__(self, obj):
    super(NotCallable, self).__init__()
    self.obj = obj


class InvalidParameters(FailedFunctionCall):
  """Exception for functions called with an incorrect parameter combination."""

  def __init__(self, sig):
    super(InvalidParameters, self).__init__()
    self.sig = sig


class WrongArgTypes(InvalidParameters):
  """For functions that were called with the wrong types."""

  def __init__(self, sig, passed_args):
    super(WrongArgTypes, self).__init__(sig)
    self.passed_args = passed_args


class WrongArgCount(InvalidParameters):
  """E.g. if a function expecting 4 parameters is called with 3."""

  def __init__(self, sig, call_arg_count):
    super(WrongArgCount, self).__init__(sig)
    self.call_arg_count = call_arg_count


class WrongKeywordArgs(InvalidParameters):
  """E.g. an arg "x" is passed to a function that doesn't have an "x" param."""

  def __init__(self, sig, extra_keywords):
    super(WrongKeywordArgs, self).__init__(sig)
    self.extra_keywords = tuple(extra_keywords)


class DuplicateKeyword(InvalidParameters):
  """E.g. an arg "x" is passed to a function that doesn't have an "x" param."""

  def __init__(self, sig, duplicate):
    super(DuplicateKeyword, self).__init__(sig)
    self.duplicate = duplicate


class MissingParameter(InvalidParameters):
  """E.g. a function requires parameter 'x' but 'x' isn't passed."""

  def __init__(self, sig, missing_parameter):
    super(MissingParameter, self).__init__(sig)
    self.missing_parameter = missing_parameter


class SuperInstance(AtomicAbstractValue):
  """The result of a super() call, i.e., a lookup proxy."""

  def __init__(self, cls, obj, vm):
    super(SuperInstance, self).__init__("super", vm)
    self.cls = self.vm.convert.super_type
    self.super_cls = cls
    self.super_obj = obj
    self.get = NativeFunction(
        "__get__", self.get, self.vm, self.vm.root_cfg_node)
    self.set = NativeFunction(
        "__set__", self.set, self.vm, self.vm.root_cfg_node)

  def get(self, node, *unused_args, **unused_kwargs):
    return node, self.to_variable(node, "get")

  def set(self, node, *unused_args, **unused_kwargs):
    return node, self.to_variable(node, "set")

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    if self.super_obj:
      valself = self.super_obj.to_variable(node, "self").bindings[0]
    if name == "__get__":
      return node, self.get.to_variable(node, name)
    elif name == "__set__":
      return node, self.set.to_variable(node, name)
    else:
      valcls = self.super_cls.to_variable(node, "cls").bindings[0]
      return node, self.super_cls.lookup_from_mro(
          node, name, valself, valcls, skip=self.super_cls)


class Super(AtomicAbstractValue):
  """The super() function. Calling it will create a SuperInstance."""

  def __init__(self, vm):
    super(Super, self).__init__("super", vm)

  def call(self, node, _, args):
    result = self.vm.program.NewVariable("super")
    if len(args.posargs) == 1:
      # TODO(kramm): Add a test for this
      for cls in args.posargs[0].bindings:
        result.AddBinding(
            SuperInstance(cls.data, None, self.vm), [cls], node)
    elif len(args.posargs) == 2:
      for cls in args.posargs[0].bindings:
        for obj in args.posargs[1].bindings:
          result.AddBinding(
              SuperInstance(cls.data, obj.data, self.vm), [cls, obj], node)
    else:
      self.vm.errorlog.super_error(
          self.vm.frame.current_opcode, len(args.posargs))
      result = self.vm.convert.create_new_unsolvable(node, "super()")
    return node, result

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    # In Python 3, you can do "super.__init__".
    raise NotImplementedError("Python 3 super not implemented yet")


class IsInstance(AtomicAbstractValue):
  """The isinstance() function."""

  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature(
      "isinstance", ("obj", "type_or_types"), None, set(), None, {},
      {"return": None})

  def __init__(self, vm):
    super(IsInstance, self).__init__("isinstance", vm)
    # Map of True/False/None (where None signals an ambiguous bool) to
    # vm values.
    self._vm_values = {
        True: vm.convert.true,
        False: vm.convert.false,
        None: vm.convert.primitive_class_instances[bool],
    }

  def call(self, node, _, args):
    try:
      if len(args.posargs) != 2:
        raise WrongArgCount(self._SIGNATURE, len(args.posargs))
      elif args.namedargs.keys():
        raise WrongKeywordArgs(self._SIGNATURE, args.namedargs.keys())
      else:
        result = self.vm.program.NewVariable("isinstance")
        for left in args.posargs[0].bindings:
          for right in args.posargs[1].bindings:
            pyval = self._is_instance(left.data, right.data)
            result.AddBinding(self._vm_values[pyval],
                              source_set=(left, right), where=node)
    except InvalidParameters as ex:
      self.vm.errorlog.invalid_function_call(self.vm.frame.current_opcode, ex)
      result = self.vm.convert.create_new_unsolvable(node, "isinstance()")

    return node, result

  def _is_instance(self, obj, class_spec):
    """Check if the object matches a class specficiation.

    Args:
      obj: An AtomicAbstractValue, generally the left hand side of an
          isinstance() call.
      class_spec: An AtomicAbstractValue, generally the right hand side of an
          isinstance() call.

    Returns:
      True if the object is derived from a class in the class_spec, False if
      it is not, and None if it is ambiguous whether obj matches class_spec.
    """
    # Unknown and Unsolvable objects are ambiguous.
    if isinstance(obj, (Unknown, Unsolvable)):
      return None
    # Assume a single binding for the object's class variable.  If this isn't
    # the case, treat the call as ambiguous.
    cls_var = obj.get_class()
    if cls_var is None:
      return None
    try:
      obj_class = get_atomic_value(cls_var)
    except ConversionError:
      return None

    # Determine the flattened list of classes to check.
    classes = []
    ambiguous = self._flatten(class_spec, classes)

    for c in classes:
      if c in obj_class.mro:
        return True  # A definite match.
    # No matches, return result depends on whether _flatten() was
    # ambiguous.
    return None if ambiguous else False

  def _flatten(self, value, classes):
    """Flatten the contents of value into classes.

    If value is a Class, it is appended to classes.
    If value is a PythonConstant of type tuple, then each element of the tuple
    that has a single binding is also flattened.
    Any other type of value, or tuple elements that have multiple bindings are
    ignored.

    Args:
      value: An abstract value.
      classes: A list to be modified.

    Returns:
      True iff a value was ignored during flattening.
    """
    if isinstance(value, Class):
      # A single class, no ambiguity.
      classes.append(value)
      return False
    elif (isinstance(value, PythonConstant) and
          value.get_class() is self.vm.convert.tuple_type and
          isinstance(value.pyval, tuple)):
      # A tuple, need to process each element.
      ambiguous = False
      for var in value.pyval:
        if (len(var.bindings) != 1 or
            self._flatten(var.bindings[0].data, classes)):
          # There were either multiple bindings or ambiguity deeper in the
          # recursion.
          ambiguous = True
      return ambiguous
    else:
      return True


class Function(Instance):
  """Base class for function objects (NativeFunction, InterpreterFunction).

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    vm: TypegraphVirtualMachine instance.
  """

  def __init__(self, name, vm, node):
    super(Function, self).__init__(vm.convert.function_type, vm, node)
    self.name = name
    self.is_attribute_of_class = False
    self._bound_functions_cache = {}
    self.members["func_name"] = self.vm.convert.build_string(
        self.vm.root_cfg_node, name)

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    if name == "__get__":
      # The pytd for "function" has a __get__ attribute, but if we already
      # have a function we don't want to be treated as a descriptor.
      return node, None
    return super(Function, self).get_attribute(node, name, valself, valcls,
                                               condition)

  def property_get(self, callself, callcls):
    if self.name == "__new__" or not callself or not callcls:
      return self
    self.is_attribute_of_class = True
    key = tuple(sorted(callself.data))
    if key not in self._bound_functions_cache:
      self._bound_functions_cache[key] = (self.bound_class)(
          callself, callcls, self)
    return self._bound_functions_cache[key]

  def get_class(self):
    return self.vm.convert.function_type

  def to_type(self, node, seen=None):
    return pytd.NamedType("__builtin__.function")

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name in ["function", "object", "Callable"]:
      return subst

  def __repr__(self):
    return self.name + "(...)"

  # We want to use __repr__ above rather than SimpleAbstractValue.__str__
  __str__ = __repr__


class Mutation(collections.namedtuple("_", ["instance", "name", "value"])):
  pass


class PyTDSignature(object):
  """A PyTD function type (signature).

  This represents instances of functions with specific arguments and return
  type.
  """

  def __init__(self, name, pytd_sig, vm):
    self.vm = vm
    self.name = name
    self.pytd_sig = pytd_sig
    self.param_types = [
        self.vm.convert.convert_constant_to_value(
            pytd.Print(p), p.type, subst={}, node=self.vm.root_cfg_node)
        for p in self.pytd_sig.params]
    self._bound_sig_cache = {}
    self.signature = function.Signature.from_pytd(vm, name, pytd_sig)

  def match_args(self, node, args, view):
    """Match arguments against this signature. Used by PyTDFunction."""
    arg_dict = {name: view[arg]
                for name, arg in zip(self.signature.param_names, args.posargs)}
    arg_dict.update({name: view[arg]
                     for name, arg in args.namedargs.items()})

    for p in self.pytd_sig.params:
      if p.name not in arg_dict:
        if (not p.optional and args.starargs is None and
            args.starstarargs is None):
          raise MissingParameter(self.signature, p.name)
        # Assume the missing parameter is filled in by *args or **kwargs.
        # TODO(kramm): Can we use the contents of [star]starargs to fill in a
        # more precise type than just "unsolvable"?
        var = self.vm.convert.create_new_unsolvable(node, p.name)
        arg_dict[p.name] = var.bindings[0]

    for p in self.pytd_sig.params:
      if not (p.optional or p.name in arg_dict):
        raise MissingParameter(self.signature, p.name)
    if not self.pytd_sig.has_optional:
      if len(args.posargs) > len(self.pytd_sig.params):
        raise WrongArgCount(self.signature, len(args.posargs))
      invalid_names = set(args.namedargs) - {p.name
                                             for p in self.pytd_sig.params}
      if invalid_names:
        raise WrongKeywordArgs(self.signature, sorted(invalid_names))

    subst = self._compute_subst(node, arg_dict, view)
    assert subst is not None
    # FailedFunctionCall is thrown by _compute_subst if no signature could be
    # matched (subst might be []).
    log.debug("Matched arguments against sig%s", pytd.Print(self.pytd_sig))
    for nr, p in enumerate(self.pytd_sig.params):
      log.info("param %d) %s: %s <=> %s", nr, p.name, p.type, arg_dict[p.name])
    for name, var in sorted(subst.items()):
      log.debug("Using %s=%r %r", name, var, var.data)

    return arg_dict, subst

  def call_with_args(self, node, func, arg_dict, subst, ret_map):
    """Call this signature. Used by PyTDFunction."""
    return_type = self.pytd_sig.return_type
    t = (return_type, subst)
    sources = [func] + arg_dict.values()
    if t not in ret_map:
      try:
        ret_map[t] = self.vm.convert.convert_constant(
            "ret", AsInstance(return_type), subst, node, source_sets=[sources])
      except self.vm.convert.TypeParameterError:
        # The return type contains a type parameter without a substitution. See
        # test_functions.test_type_parameter_in_return for an example of a
        # return type being set to Unknown here and solved later.
        ret_map[t] = Unknown(self.vm).to_variable(node, "ret")
    else:
      # add the new sources
      for data in ret_map[t].data:
        ret_map[t].AddBinding(data, sources, node)
    mutations = self._get_mutation(node, arg_dict, subst)
    self.vm.trace_call(node, func,
                       tuple(arg_dict[p.name] for p in self.pytd_sig.params),
                       {},
                       ret_map[t])
    return node, ret_map[t], mutations

  def _compute_subst(self, node, arg_dict, view):
    """Compute information about type parameters using one-way unification.

    Given the arguments of a function call, try to find a substitution that
    matches them against the formal parameter of this PyTDSignature.

    Args:
      node: The current CFG node.
      arg_dict: A map of strings to pytd.Bindings instances.
      view: A mapping of Variable to Value.
    Returns:
      utils.HashableDict if we found a working substition, None otherwise.
    Raises:
      FailedFunctionCall: For incorrect parameter types.
    """
    if not arg_dict:
      return utils.HashableDict()
    subst = {}
    for p in self.pytd_sig.params:
      actual = arg_dict[p.name]
      formal = self.signature.annotations[p.name]
      subst = _match_value_against_type(actual, formal, subst, node, view)
      if subst is None:
        # These parameters didn't match this signature. There might be other
        # signatures that work, but figuring that out is up to the caller.
        passed = [arg_dict[name].data
                  for name in self.signature.param_names]
        raise WrongArgTypes(self.signature, passed)
    return utils.HashableDict(subst)

  def _get_mutation(self, node, arg_dict, subst):
    """Mutation for changing the type parameters of mutable arguments.

    This will adjust the type parameters as needed for pytd functions like:
      def append_float(x: list[int]):
        x := list[int or float]
    This is called after all the signature matching has succeeded, and we
    know we're actually calling this function.

    Args:
      node: The current CFG node.
      arg_dict: A map of strings to pytd.Bindings instances.
      subst: Current type parameters.
    Returns:
      A list of Mutation instances.
    Raises:
      ValueError: If the pytd contains invalid information for mutated params.
    """
    # Handle mutable parameters using the information type parameters
    mutations = []
    for formal in self.pytd_sig.params:
      actual = arg_dict[formal.name]
      if formal.mutated_type is not None:
        if (isinstance(formal.type, pytd.GenericType) and
            isinstance(formal.mutated_type, pytd.GenericType) and
            formal.type.base_type == formal.mutated_type.base_type and
            isinstance(formal.type.base_type, pytd.ClassType) and
            formal.type.base_type.cls):
          arg = actual.data
          names_actuals = zip(formal.mutated_type.base_type.cls.template,
                              formal.mutated_type.parameters)
          for tparam, type_actual in names_actuals:
            log.info("Mutating %s to %s",
                     tparam.name,
                     pytd.Print(type_actual))
            type_actual_val = self.vm.convert.convert_constant(
                tparam.name, AsInstance(type_actual), subst, node,
                discard_concrete_values=True)
            mutations.append(Mutation(arg, tparam.name, type_actual_val))
        else:
          log.error("Old: %s", pytd.Print(formal.type))
          log.error("New: %s", pytd.Print(formal.mutated_type))
          log.error("Actual: %r", actual)
          raise ValueError("Mutable parameters setting a type to a "
                           "different base type is not allowed.")
    return mutations

  def get_bound_arguments(self):
    return []

  def get_positional_names(self):
    return [p.name for p in self.pytd_sig.params
            if not p.kwonly]

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

  def call(self, node, func, args):
    # Since this only used in pyi, we don't need to verify the type of the "cls"
    # arg a second time. So just pass an unsolveable. (All we care about is the
    # return type, anyway.)
    cls = self.vm.convert.create_new_unsolvable(node, "cls")
    return self.method.call(
        node, func, args.replace(posargs=[cls] + args.posargs))

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name in ["classmethod", "object"]:
      return subst


class StaticMethod(AtomicAbstractValue):
  """Implements @staticmethod methods in pyi."""

  def __init__(self, name, method, callself, callcls, vm):
    super(StaticMethod, self).__init__(name, vm)
    self.method = method
    self.callself = callself  # unused
    self.callcls = callcls  # unused
    self.signatures = self.method.signatures

  def call(self, *args, **kwargs):
    return self.method.call(*args, **kwargs)

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name in ["staticmethod", "object"]:
      return subst
    else:
      return None


class PyTDFunction(Function):
  """A PyTD function (name + list of signatures).

  This represents (potentially overloaded) functions.
  """

  def __init__(self, name, signatures, kind, vm, node):
    super(PyTDFunction, self).__init__(name, vm, node)
    assert signatures
    self.kind = kind
    self.bound_class = BoundPyTDFunction
    self.signatures = signatures
    self._signature_cache = {}
    self._return_types = {sig.pytd_sig.return_type for sig in signatures}
    self._has_mutable = any(param.mutated_type is not None
                            for sig in signatures
                            for param in sig.pytd_sig.params)
    for sig in signatures:
      sig.function = self
      sig.name = self.name

  def property_get(self, callself, callcls):
    if self.kind == pytd.STATICMETHOD:
      return StaticMethod(self.name, self, callself, callcls, self.vm)
    elif self.kind == pytd.CLASSMETHOD:
      return ClassMethod(self.name, self, callself, callcls, self.vm)
    else:
      return Function.property_get(self, callself, callcls)

  def _log_args(self, arg_values_list, level=0, logged=None):
    if log.isEnabledFor(logging.DEBUG):
      if logged is None:
        logged = set()
      for i, arg_values in enumerate(arg_values_list):
        if level:
          if arg_values and any(v.data not in logged for v in arg_values):
            log.debug("%s%s:", "  " * level, arg_values[0].variable.name)
        else:
          log.debug("Arg %d", i)
        for value in arg_values:
          if value.data not in logged:
            log.debug("%s%s", "  " * (level + 1), value.data)
            self._log_args(value.data.unique_parameter_values(), level + 2,
                           logged | {value.data})

  def call(self, node, func, args):
    self._log_args(arg.bindings for arg in args.posargs)
    ret_map = {}
    retvar = self.vm.program.NewVariable("%s ret" % self.name)
    error = None
    variables = tuple(args.posargs) + tuple(args.namedargs.values())
    all_calls_failed = True
    all_mutations = []
    for combination in utils.deep_variable_product(variables):
      view = {value.variable: value for value in combination}
      try:
        node, result, mutations = self._call_with_view(
            node, func, args, view, ret_map)
      except FailedFunctionCall as e:
        # TODO(kramm): Does this ever happen?
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
    return [Mutation(v, name, self.vm.convert.create_new_unknown(
        node, name, action="type_param_" + name))
            for v in values if isinstance(v, SimpleAbstractValue)
            for name in v.type_parameters]

  def _call_with_view(self, node, func, args, view, ret_map):
    """Call function using a specific Variable->Value view."""
    log.debug("call_with_view function %r: %d signature(s)",
              self.name, len(self.signatures))
    log.debug("args in view: %r", [(a.bindings and view[a].data)
                                   for a in args.posargs])

    if not all(a.bindings for a in args.posargs):
      raise exceptions.ByteCodeTypeError(
          "Can't call function with <nothing> parameter")

    # If we're calling an overloaded pytd function with an unknown as a
    # parameter, we can't tell whether it matched or not. Hence, if multiple
    # signatures are possible matches, we don't know which got called. Check
    # if this is the case.
    if (len(self.signatures) > 1 and
        any(isinstance(view[arg].data, (Unknown, Unsolvable))
            for arg in chain(args.posargs, args.namedargs.values()))):
      signatures = tuple(self._yield_matching_signatures(node, args, view))
      if len(signatures) > 1:
        return self._call_with_signatures(node, func, args, view, signatures)
      else:
        (sig, arg_dict, subst), = signatures
    else:
      # We only take the first signature that matches, and ignore all after it.
      # This is because in the pytds for the standard library, the last
      # signature(s) is/are fallback(s) - e.g. list is defined by
      # def __init__(self: x: list)
      # def __init__(self, x: iterable)
      # def __init__(self, x: generator)
      # def __init__(self, x: object)
      # with the last signature only being used if none of the others match.
      sig, arg_dict, subst = next(self._yield_matching_signatures(
          node, args, view))
    return sig.call_with_args(node, func, arg_dict, subst, ret_map)

  def _call_with_signatures(self, node, func, args, view, signatures):
    """Perform a function call that involves multiple signatures."""
    if len(self._return_types) == 1:
      ret_type, = self._return_types
      try:
        # Even though we don't know which signature got picked, if the return
        # type is unique and does not contain any type parameter, we can use it.
        result = self.vm.convert.convert_constant(
            "ret", AsInstance(ret_type), {}, node)
      except self.vm.convert.TypeParameterError:
        # The return type contains a type parameter
        result = None
      else:
        log.debug("Unknown args. But return is always %s", pytd.Print(ret_type))
    else:
      result = None
    if result is None:
      log.debug("Creating unknown return")
      result = self.vm.convert.create_new_unknown(
          node, "<unknown return of " + self.name + ">", action="pytd_call")
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
            view[arg] = arg.AddBinding(self.vm.convert.unsolvable, [], node)
            break
    if self._has_mutable:
      # TODO(kramm): We only need to whack the type params that appear in
      # a mutable parameter.
      mutations = self._get_mutation_to_unknown(
          node, (view[p].data for p in chain(args.posargs,
                                             args.namedargs.values())))
    else:
      mutations = []
    self.vm.trace_call(node, func,
                       [view[arg] for arg in args.posargs],
                       {name: view[arg]
                        for name, arg in args.namedargs.items()},
                       result)
    return node, result, mutations

  def _yield_matching_signatures(self, node, args, view):
    """Try, in order, all pytd signatures, yielding matches."""
    error = None
    matched = False
    for sig in self.signatures:
      try:
        arg_dict, subst = sig.match_args(node, args, view)
      except FailedFunctionCall as e:
        error = e
      else:
        matched = True
        yield sig, arg_dict, subst
    if not matched:
      raise error  # pylint: disable=raising-bad-type

  def to_pytd_def(self, node, name):
    del node
    return pytd.Function(
        name, tuple(sig.pytd_sig for sig in self.signatures), pytd.METHOD)


class Class(object):
  """Mix-in to mark all class-like values."""

  def __new__(cls, *args, **kwds):
    """Prevent direct instantiation."""
    assert cls is not Class, "Cannot instantiate Class"
    return object.__new__(cls, *args, **kwds)

  def init_mixin(self):
    """Mix-in equivalent of __init__."""
    pass

  def get_attribute_computed(self, node, name, valself, valcls, condition):
    """Call __getattr__ (if defined) to compute an attribute."""
    node, attr_var = Class.get_attribute(self, node, "__getattr__", valself,
                                         valcls, condition)
    if attr_var and attr_var.bindings:
      name_var = AbstractOrConcreteValue(name, self.vm.convert.str_type,
                                         self.vm, node).to_variable(node, name)
      return self.vm.call_function(node, attr_var, FunctionArgs([name_var]))
    else:
      return node, None

  def lookup_from_mro(self, node, name, valself, valcls, skip=None):
    """Find an identifier in the MRO of the class."""
    ret = self.vm.program.NewVariable(name)
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

    for base in self.mro:
      # Potentially skip start of MRO, for super()
      if base is skip:
        continue
      node, var = base.get_attribute_flat(node, name)
      if var is None or not var.bindings:
        continue
      for varval in var.bindings:
        value = varval.data
        if variableself or variablecls:
          value = value.property_get(variableself, variablecls)
        ret.AddBinding(value, [varval] + add_origins, node)
      break  # we found a class which has this attribute
    return ret

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    """Retrieve an attribute by looking at the MRO of this class."""
    del condition  # unused arg.
    var = self.lookup_from_mro(node, name, valself, valcls)
    return node, var

  def get_as_instance_attribute(self, node, name, instance):
    for base in self.mro:
      if isinstance(base, ParameterizedClass):
        base = base.base_cls
      if isinstance(base, PyTDClass):
        var = base.get_as_instance_attribute_flat(node, name, instance)
        if var is not None:
          return var

  def to_pytd_def(self, node, name):
    # Default method. Generate an empty pytd. Subclasses override this.
    del node
    return pytd.Class(name, (), (), (), ())

  def match_instance(self, instance, subst, node, view):
    """Used by match_instance_against_type. Matches a single MRO entry.

    Called after the instance has been successfully matched against a
    formal type to do any remaining matching special to the type; e.g.,
    ParameterizedClass overrides this method to match instance type
    parameters against formal type parameters. By default this match
    succeeds without doing anything.

    Args:
      instance: The instance of this class.
      subst: The current type parameter assignment.
      node: The current CFG node.
      view: The current mapping of Variable to Value.
    Returns:
      A new type parameter assignment of the matching succeeded, None otherwise.
    """
    del instance, node, view
    return subst

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
    if other_type.full_name == "__builtin__.object":
      return subst

    # LINT.IfChange
    # Should keep in sync with visitors.ExpandCompatibleBuiltins
    compatible_builtins = {
        # See https://github.com/python/typeshed/issues/270
        "__builtin__.NoneType": "__builtin__.bool",
        "__builtin__.str": "__builtin__.unicode",
        "__builtin__.bytes": "__builtin__.unicode",
        "__builtin__.int": "__builtin__.float"
    }

    if compatible_builtins.get(self.full_name) == other_type.full_name:
      return subst

    if isinstance(other_type, Class):
      for base in self.mro:
        if isinstance(base, ParameterizedClass):
          base = base.base_cls
        if isinstance(base, Class):
          if other_type is base or (
              isinstance(other_type, ParameterizedClass) and
              other_type.base_cls is base):
            new_subst = other_type.match_instance(instance, subst, node, view)
            if new_subst is not None:
              return new_subst
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
    self.mro = (self,) + self.base_cls.mro[1:]

  def __repr__(self):
    return "ParameterizedClass(cls=%r params=%s)" % (self.base_cls,
                                                     self.type_parameters)

  def __str__(self):
    params = [self.type_parameters[type_param.name]
              for type_param in self.base_cls.pytd_cls.template]
    return "%s[%s]" % (self.base_cls, ", ".join(str(p) for p in params))

  def get_attribute_generic(self, node, name, val):
    return self.base_cls.get_attribute_generic(node, name, val)

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    return self.base_cls.get_attribute(node, name, valself, valcls, condition)

  def get_attribute_flat(self, node, name):
    return self.base_cls.get_attribute_flat(node, name)

  def to_type(self, node, seen=None):
    return pytd.NamedType("__builtin__.type")

  def get_instance_type(self, node, instance, seen=None):
    type_arguments = []
    for type_param in self.base_cls.pytd_cls.template:
      type_arguments.append(
          self.type_parameters[type_param.name].get_instance_type(
              node, None, seen))
    return pytd_utils.MakeClassOrContainerType(
        pytd_utils.NamedTypeWithModule(self.base_cls.pytd_cls.name,
                                       self.base_cls.module),
        type_arguments)

  def match_instance(self, instance, subst, node, view):
    for name, class_param in self.type_parameters.items():
      instance_param = instance.get_type_parameter(node, name)
      if instance_param.bindings and instance_param not in view:
        binding, = instance_param.bindings
        assert isinstance(binding.data, Unsolvable)
        view = view.copy()
        view[instance_param] = binding
      subst = match_var_against_type(instance_param, class_param,
                                     subst, node, view)
      if subst is None:
        return None
    return subst


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

  def get_attribute_generic(self, node, name, val):
    return self.get_attribute(node, name, valcls=val)

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    node, var = Class.get_attribute(
        self, node, name, valself, valcls, condition)
    if var.bindings or not valself:
      return node, var
    elif isinstance(valself.data, Module):
      # Modules do their own __getattr__ handling.
      return node, None
    else:
      return self.get_attribute_computed(node, name, valself, valcls, condition)

  def get_attribute_flat(self, node, name):
    # get_attribute_flat ?
    return SimpleAbstractValue.get_attribute(self, node, name)

  def bases(self):
    convert = self.vm.convert
    return [convert.convert_constant_to_value(
        pytd.Print(parent), parent, subst={}, node=self.vm.root_cfg_node)
            for parent in self.pytd_cls.parents]

  def _convert_member(self, name, pyval, subst=None, node=None):
    """Convert a member as a variable. For lazy lookup."""
    subst = subst or {}
    node = node or self.vm.root_cfg_node
    if isinstance(pyval, pytd.Constant):
      return self.vm.convert.convert_constant(
          name, AsInstance(pyval.type), subst, node)
    elif isinstance(pyval, pytd.Function):
      c = self.vm.convert.convert_constant_to_value(
          repr(pyval), pyval, subst=subst, node=node)
      c.parent = self
      return c.to_variable(self.vm.root_cfg_node, name)
    else:
      raise AssertionError("Invalid class member %s", pytd.Print(pyval))

  def call(self, node, func, args):
    value = Instance(self.vm.convert.convert_constant(
        self.name, self.pytd_cls), self.vm, node)

    for type_param in self.pytd_cls.template:
      if type_param.name not in value.type_parameters:
        value.type_parameters[type_param.name] = self.vm.program.NewVariable(
            type_param.name)

    results = self.vm.program.NewVariable(self.name)
    retval = results.AddBinding(value, [func], node)

    node, init = value.get_attribute(node, "__init__", retval,
                                     value.cls.bindings[0])
    # TODO(pludemann): Verify that this follows MRO:
    if init:
      log.debug("calling %s.__init__(...)", self.name)
      node, ret = self.vm.call_function(node, init, args)
      log.debug("%s.__init__(...) returned %r", self.name, ret)

    return node, results

  def instantiate(self, node):
    return self.vm.convert.convert_constant(
        self.name, AsInstance(self.pytd_cls), {}, node)

  def to_type(self, node, seen=None):
    return pytd.NamedType("__builtin__.type")

  def get_instance_type(self, node, instance=None, seen=None):
    """Convert instances of this class to their PYTD type."""
    if seen is None:
      seen = set()
    type_params = self.pytd_cls.template
    if instance in seen:
      # We have a circular dependency in our types (e.g., lst[0] == lst). Stop
      # descending into the type parameters.
      type_params = ()
    if instance is not None:
      seen.add(instance)
    type_arguments = []
    for type_param in type_params:
      if instance is not None and type_param.name in instance.type_parameters:
        param = instance.type_parameters[type_param.name]
        type_arguments.append(pytd_utils.JoinTypes(
            data.to_type(node, seen=seen) for data in param.Data(node)))
      else:
        type_arguments.append(pytd.AnythingType())
    return pytd_utils.MakeClassOrContainerType(
        pytd_utils.NamedTypeWithModule(self.name, self.module),
        type_arguments)

  def __repr__(self):
    return self.name

  def __str__(self):
    return self.name

  def to_pytd_def(self, node, name):
    # This happens if a module does e.g. "from x import y as z", i.e., copies
    # something from another module to the local namespace. We *could*
    # reproduce the entire class, but we choose a more dense representation.
    return pytd.NamedType("__builtin__.type")

  def get_as_instance_attribute_flat(self, node, name, instance):
    try:
      c = self.pytd_cls.Lookup(name)
    except KeyError:
      return None
    if isinstance(c, pytd.Constant):
      try:
        self._convert_member(name, c)
      except self.vm.convert.TypeParameterError:
        # Constant c cannot be converted without type parameter substitutions,
        # so it must be an instance attribute.
        subst = {itm.name: TypeParameterInstance(
            itm.name, instance, self.vm).to_variable(node, name)
                 for itm in self.pytd_cls.template}
        return self._convert_member(name, c, subst, node)


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

  def get_attribute_generic(self, node, name, val):
    return self.get_attribute(node, name, valcls=val)

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    node, attr_var = Class.get_attribute(self, node, name, valself, valcls,
                                         condition)
    result = self.vm.program.NewVariable(name)
    nodes = []
    # Deal with descriptors as a potential additional level of indirection.
    for v in attr_var.Bindings(node):
      value = v.data
      node2, getter = value.get_attribute(node, "__get__", v)
      if getter is not None:
        posargs = []
        if valself:
          posargs.append(valself.variable)
        if valcls:
          if not valself:
            posargs.append(self.vm.convert.none.to_variable(node, "None"))
          posargs.append(valcls.variable)
        node2, get_result = self.vm.call_function(
            node2, getter, FunctionArgs(posargs))
        for getter in get_result.bindings:
          result.AddBinding(getter.data, [getter], node2)
      else:
        result.AddBinding(value, [v], node2)
      nodes.append(node2)
    if nodes:
      return self.vm.join_cfg_nodes(nodes), result
    elif valself:
      return self.get_attribute_computed(node, name, valself, valcls, condition)
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
      cls.AddBinding(self, [value], node)
      self._instance_cache[key] = Instance(cls, self.vm, node)
    return self._instance_cache[key]

  def call(self, node, value, args):
    value = self._new_instance(node, value)
    variable = self.vm.program.NewVariable(self.name + " instance")
    val = variable.AddBinding(value, [], node)
    node, init = value.get_attribute(node, "__init__", val)
    if init:
      log.debug("calling %s.__init__(...)", self.name)
      node, ret = self.vm.call_function(node, init, args)
      log.debug("%s.__init__(...) returned %r", self.name, ret)
    return node, variable

  def to_type(self, node, seen=None):
    return pytd.NamedType("__builtin__.type")

  def to_pytd_def(self, node, class_name):
    methods = []
    constants = collections.defaultdict(pytd_utils.TypeBuilder)

    # class-level attributes
    for name, member in self.members.items():
      if name not in output.CLASS_LEVEL_IGNORE:
        for value in member.FilteredData(self.vm.exitpoint):
          if isinstance(value, Function):
            v = value.to_pytd_def(node, name)
            if isinstance(v, pytd.Function):
              methods.append(v)
            elif isinstance(v, pytd.TYPE):
              constants[name].add_type(v)
            else:
              raise AssertionError(str(type(v)))
          else:
            constants[name].add_type(value.to_type(node))

    # instance-level attributes
    for instance in self.instances:
      for name, member in instance.members.items():
        if name not in output.CLASS_LEVEL_IGNORE:
          for value in member.FilteredData(self.vm.exitpoint):
            constants[name].add_type(value.to_type(node))

    bases = [pytd_utils.JoinTypes(b.get_instance_type(node)
                                  for b in basevar.data)
             for basevar in self._bases
             if basevar is not self.vm.convert.oldstyleclass_type]
    constants = [pytd.Constant(name, builder.build())
                 for name, builder in constants.items()
                 if builder]
    return pytd.Class(name=class_name,
                      parents=tuple(bases),
                      methods=tuple(methods),
                      constants=tuple(constants),
                      template=())

  def get_instance_type(self, node, instance=None, seen=None):
    del node, instance
    if self.official_name:
      return pytd_utils.NamedTypeWithModule(self.official_name, self.module)
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

  def __init__(self, name, func, vm, node):
    super(NativeFunction, self).__init__(name, vm, node)
    self.name = name
    self.func = func
    self.cls = self.vm.convert.function_type

  def argcount(self):
    return self.func.func_code.co_argcount

  def call(self, node, _, args):
    # Originate a new variable for each argument and call.
    return self.func(
        node,
        *[u.AssignToNewVariable(u.name, node)
          for u in args.posargs],
        **{k: u.AssignToNewVariable(u.name, node)
           for k, u in args.namedargs.items()})

  def get_positional_names(self):
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
  def make_function(name, code, f_locals, f_globals, defaults, kw_defaults,
                    closure, annotations, vm):
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
      annotations: Function annotations. Dict of name -> AtomicAbstractValue.
      vm: VirtualMachine instance.

    Returns:
      An InterpreterFunction.
    """
    annotations = annotations or {}
    key = (name, code,
           InterpreterFunction._hash_all(
               (f_globals.members, set(code.co_names)),
               (f_locals.members, set(code.co_varnames)),
               ({key: vm.program.NewVariable(key, [value], [],
                                             vm.root_cfg_node)
                 for key, value in annotations.items()}, None),
               (dict(enumerate(defaults)), None),
               (dict(enumerate(closure or ())), None)))
    if key not in InterpreterFunction._function_cache:
      InterpreterFunction._function_cache[key] = InterpreterFunction(
          name, code, f_locals, f_globals, defaults, kw_defaults,
          closure, annotations, vm, vm.root_cfg_node)
    return InterpreterFunction._function_cache[key]

  def __init__(self, name, code, f_locals, f_globals, defaults, kw_defaults,
               closure, annotations, vm, node):
    super(InterpreterFunction, self).__init__(name, vm, node)
    log.debug("Creating InterpreterFunction %r for %r", name, code.co_name)
    self.bound_class = BoundInterpreterFunction
    self.doc = code.co_consts[0] if code.co_consts else None
    self.name = name
    self.code = code
    self.f_globals = f_globals
    self.f_locals = f_locals
    self.defaults = tuple(defaults)
    self.kw_defaults = kw_defaults
    self.closure = closure
    self.annotations = annotations
    self.cls = self.vm.convert.function_type
    self._call_records = {}
    self.nonstararg_count = self.code.co_argcount
    if self.code.co_kwonlyargcount >= 0:  # This is usually -1 or 0 (fast call)
      self.nonstararg_count += self.code.co_kwonlyargcount
    self.signature = self._build_signature()
    self.last_frame = None  # for BuildClass

  def _build_signature(self):
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
        self.name,
        list(self.code.co_varnames[:self.nonstararg_count]),
        vararg_name,
        kwonly,
        kwarg_name,
        defaults,
        self.annotations)

  # TODO(kramm): support retrieving the following attributes:
  # 'func_{code, name, defaults, globals, locals, dict, closure},
  # '__name__', '__dict__', '__doc__', '_vm', '_func'

  def get_first_opcode(self):
    return self.code.co_code[0]

  def is_closure(self):
    return self.closure is not None

  def argcount(self):
    return self.code.co_argcount

  def _map_args(self, node, args):
    """Map call args to function args.

    This emulates how Python would map arguments of function calls. It takes
    care of keyword parameters, default parameters, and *args and **kwargs.

    Args:
      node: The current CFG node.
      args: The arguments.

    Returns:
      A dictionary, mapping strings (parameter names) to typegraph.Variable.

    Raises:
      FailedFunctionCall: If the caller supplied incorrect arguments.
    """
    # Originate a new variable for each argument and call.
    posargs = [u.AssignToNewVariable(u.name, node)
               for u in args.posargs]
    kws = {k: u.AssignToNewVariable(u.name, node)
           for k, u in args.namedargs.items()}
    if (self.vm.python_version[0] == 2 and
        self.code.co_name in ["<setcomp>", "<dictcomp>", "<genexpr>"]):
      # This code is from github.com/nedbat/byterun. Apparently, Py2 doesn't
      # know how to inspect set comprehensions, dict comprehensions, or
      # generator expressions properly. See http://bugs.python.org/issue19611.
      # Byterun says: "They are always functions of one argument, so just do the
      # right thing."
      assert len(posargs) == 1, "Surprising comprehension!"
      return {".0": posargs[0]}
    param_names = self.get_positional_names()
    num_defaults = len(self.defaults)
    callargs = dict(zip(param_names[-num_defaults:], self.defaults))
    callargs.update(self.kw_defaults)
    positional = dict(zip(param_names, posargs))
    for key in positional:
      if key in kws:
        raise DuplicateKeyword(self.signature, key)
    callargs.update(positional)
    callargs.update(kws)
    for key, kwonly in self.get_nondefault_params():
      if key not in callargs:
        if args.starstarargs or (args.starargs and not kwonly):
          # We assume that because we have *args or **kwargs, we can use these
          # to fill in any parameters we might be missing.
          callargs[key] = self.vm.convert.create_new_unsolvable(node, key)
        else:
          raise MissingParameter(self.signature, key)
    arg_pos = self.nonstararg_count
    if self.has_varargs():
      vararg_name = self.code.co_varnames[arg_pos]
      extraneous = posargs[self.code.co_argcount:]
      if args.starargs:
        if extraneous:
          log.warning("Not adding extra params to *%s", vararg_name)
        callargs[vararg_name] = args.starargs.AssignToNewVariable(
            "*args", node)
      else:
        callargs[vararg_name] = self.vm.convert.build_tuple(node, extraneous)
      arg_pos += 1
    elif len(posargs) > self.code.co_argcount:
      raise WrongArgCount(self.signature, len(posargs))
    if self.has_kwargs():
      kwvararg_name = self.code.co_varnames[arg_pos]
      # Build a **kwargs dictionary out of the extraneous parameters
      if args.starstarargs:
        # TODO(kramm): modify type parameters to account for namedargs
        callargs[kwvararg_name] = args.starstarargs.AssignToNewVariable(
            "**kwargs", node)
      else:
        k = Dict("kwargs", self.vm, node)
        k.update(node, args.namedargs, omit=param_names)
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
      for value in var.bindings:
        m.update(value.data.get_fullhash())
    return m.digest()

  @staticmethod
  def _hash_all(*hash_args):
    """Convenience method for hashing a sequence of dicts."""
    return hashlib.md5("".join(InterpreterFunction._hash(*args)
                               for args in hash_args)).digest()

  def _check_call(self, node, args):
    if not self.signature.has_param_annotations:
      return
    args = list(self.signature.iter_args(
        args.posargs, args.namedargs, args.starargs, args.starstarargs))
    for i, (_, param_var, formal) in enumerate(args):
      if formal is not None:
        bad = bad_matches(param_var, formal, node)
        if bad:
          passed = [p.data[0] for _, p, _ in args]
          if len(bad) == 1:
            passed[i] = bad[0].data
          else:
            passed[i] = Union([b.data for b in bad], self.vm)
          raise WrongArgTypes(self.signature, passed)

  def call(self, node, _, args, new_locals=None):
    if self.vm.is_at_maximum_depth():
      log.info("Maximum depth reached. Not analyzing %r", self.name)
      return (node,
              self.vm.convert.create_new_unsolvable(node, self.name + ":ret"))
    self._check_call(node, args)
    callargs = self._map_args(node, args)
    # Might throw vm.RecursionException:
    frame = self.vm.make_frame(node, self.code, callargs,
                               self.f_globals, self.f_locals, self.closure,
                               new_locals=new_locals)
    if self.signature.has_return_annotation:
      frame.allowed_returns = self.signature.annotations["return"]
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
      _, old_ret, _, old_remaining_depth = self._call_records[callkey]
      # Optimization: This function has already been called, with the same
      # environment and arguments, so recycle the old return value and don't
      # record this call. We pretend that this return value originated at the
      # current node to make sure we don't miss any possible types.
      # We would want to skip this optimization and reanalyze the call
      # if the all the possible types of the return value was unsolvable
      # and we can transverse the function deeper.
      if (all(x == self.vm.convert.unsolvable for x in old_ret.data) and
          self.vm.remaining_depth() > old_remaining_depth):
        log.info("Renalyzing %r because all of its call record's bindings are "
                 "Unsolvable; remaining_depth = %d,"
                 "record remaining_depth = %d",
                 self.name, self.vm.remaining_depth(), old_remaining_depth)
      else:
        ret = self.vm.program.NewVariable(old_ret.name, old_ret.data, [], node)
        return node, ret

    if self.code.co_flags & loadmarshal.CodeType.CO_GENERATOR:
      generator = Generator(frame, self.vm, node)
      # Run the generator right now, even though the program didn't call it,
      # because we need to know the contained type for futher matching.
      node2, _ = generator.run_until_yield(node)
      node_after_call, ret = node2, generator.to_variable(node2, self.name)
    else:
      node_after_call, ret = self.vm.run_frame(frame, node)
    self._call_records[callkey] = (callargs,
                                   ret,
                                   node_after_call,
                                   self.vm.remaining_depth())
    self.last_frame = frame
    return node_after_call, ret

  def _get_call_combinations(self):
    signature_data = set()
    for callargs, ret, node_after_call, _ in self._call_records.values():
      for combination in utils.variable_product_dict(callargs):
        for return_value in ret.bindings:
          values = combination.values() + [return_value]
          data = tuple(v.data for v in values)
          if data in signature_data:
            # This combination yields a signature we already know is possible
            continue
          if node_after_call.HasCombination(values):
            signature_data.add(data)
            yield node_after_call, combination, return_value

  def _fix_param_name(self, name):
    """Sanitize a parameter name; remove Python intrinstics."""
    # Python uses ".0" etc. for parameters that are tuples, like e.g. in:
    # "def f((x, y), z)".
    return name.replace(".", "_")

  def _with_replaced_annotations(self, node, params):
    """Insert type annotations into parameter list."""
    params = list(params)
    varnames = self.code.co_varnames[0:self.nonstararg_count]
    for name, formal_type in self.annotations.items():
      try:
        i = varnames.index(name)
      except ValueError:
        pass
      else:
        params[i] = params[i].Replace(type=formal_type.get_instance_type(node))
    return tuple(params)

  def _get_annotation_return(self, node, default):
    if "return" in self.annotations:
      return self.annotations["return"].get_instance_type(node)
    else:
      return default

  def _get_star_params(self):
    """Returns pytd nodes for *args, **kwargs."""
    if self.has_varargs():
      starargs = pytd.Parameter(self.signature.varargs_name,
                                pytd.NamedType("__builtin__.tuple"),
                                False, True, None)
    else:
      starargs = None
    if self.has_kwargs():
      starstarargs = pytd.Parameter(self.signature.kwargs_name,
                                    pytd.NamedType("__builtin__.dict"),
                                    False, True, None)
    else:
      starstarargs = None
    return starargs, starstarargs

  def to_pytd_def(self, node, function_name):
    """Generate a pytd.Function definition."""
    signatures = []
    for node_after, combination, return_value in self._get_call_combinations():
      params = tuple(pytd.Parameter(self._fix_param_name(name),
                                    combination[name].data.to_type(node),
                                    kwonly, optional, None)
                     for name, kwonly, optional in self.get_parameters())
      params = self._with_replaced_annotations(node_after, params)
      ret = self._get_annotation_return(
          node, default=return_value.data.to_type(node_after))
      starargs, starstarargs = self._get_star_params()
      signatures.append(pytd.Signature(
          params=params,
          starargs=starargs,
          starstarargs=starstarargs,
          return_type=ret,
          exceptions=(),  # TODO(kramm): record exceptions
          template=()))
    if signatures:
      return pytd.Function(function_name, tuple(signatures), pytd.METHOD)
    else:
      # Fallback: Generate a pytd signature only from the definition of the
      # method, not the way it's being used.
      return pytd.Function(function_name, (self._simple_pytd_signature(node),),
                           pytd.METHOD)

  def _simple_pytd_signature(self, node):
    params = self._with_replaced_annotations(
        node, [pytd.Parameter(name, pytd.NamedType("__builtin__.object"),
                              kwonly, optional, None)
               for name, kwonly, optional in self.get_parameters()])
    starargs, starstarargs = self._get_star_params()
    ret = self._get_annotation_return(node, default=pytd.AnythingType())
    return pytd.Signature(
        params=params,
        starargs=starargs,
        starstarargs=starstarargs,
        return_type=ret,
        exceptions=(), template=())

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
    return bool(self.code.co_flags & loadmarshal.CodeType.CO_VARARGS)

  def has_kwargs(self):
    return bool(self.code.co_flags & loadmarshal.CodeType.CO_VARKEYWORDS)


class BoundFunction(AtomicAbstractValue):
  """An function type which has had an argument bound into it."""

  def __init__(self, callself, callcls, underlying):
    super(BoundFunction, self).__init__(underlying.name, underlying.vm)
    self._callself = callself
    self._callcls = callcls
    self.underlying = underlying
    self.is_attribute_of_class = False

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    return self.underlying.get_attribute(node, name, valself, valcls, condition)

  def set_attribute(self, node, name, value):
    return self.underlying.set_attribute(node, name, value)

  def argcount(self):
    return self.underlying.argcount() - 1  # account for self

  @property
  def signature(self):
    return self.underlying.signature.drop_first_parameter()

  def call(self, node, func, args):
    return self.underlying.call(
        node, func, args.replace(posargs=[self._callself] + args.posargs))

  def get_bound_arguments(self):
    return [self._callself]

  def get_positional_names(self):
    return self.underlying.get_positional_names()

  def has_varargs(self):
    return self.underlying.has_varargs()

  def has_kwargs(self):
    return self.underlying.has_kwargs()

  def to_type(self, node, seen=None):
    return pytd.NamedType("__builtin__.function")

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name in ["function", "object", "Callable"]:
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

  def __init__(self, generator_frame, vm, node):
    super(Generator, self).__init__(vm.convert.generator_type, vm, node)
    self.generator_frame = generator_frame
    self.runs = 0

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    if name == "__iter__":
      f = NativeFunction(name, self.__iter__, self.vm, node)
      return node, f.to_variable(node, name)
    elif name in ["next", "__next__"]:
      return node, self.to_variable(node, name)
    elif name == "throw":
      # We don't model exceptions in a way that would allow us to induce one
      # inside a coroutine. So just return ourself, mapping the call of
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

  def call(self, node, func, args):
    """Call this generator or (more common) its "next" attribute."""
    del func, args
    return self.run_until_yield(node)


class Iterator(ValueWithSlots):
  """A representation of instances of iterators."""

  TYPE_PARAM = "T"

  def __init__(self, vm, return_var, node):
    super(Iterator, self).__init__(vm.convert.iterator_type, vm, node)
    self.set_slot("next", self.next_slot)
    self.init_type_parameters(self.TYPE_PARAM)
    # TODO(dbaum): Should we set type_parameters[self.TYPE_PARAM] to something
    # based on return_var?
    self._return_var = return_var

  def next_slot(self, node):
    return node, self._return_var


class Nothing(AtomicAbstractValue, FormalType):
  """The VM representation of Nothing values.

  These are fake values that never exist at runtime, but they appear if you, for
  example, extract a value from an empty list.
  """

  def __init__(self, vm):
    super(Nothing, self).__init__("nothing", vm)

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    return node, None

  def set_attribute(self, node, name, value):
    raise AttributeError("Object %r has no attribute %s" % (self, name))

  def call(self, node, func, args):
    raise AssertionError("Can't call empty object ('nothing')")

  def to_type(self, node, seen=None):
    return pytd.NothingType()

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name == "nothing":
      return subst
    else:
      return None


class Module(Instance):
  """Represents an (imported) module."""

  is_lazy = True  # uses _convert_member

  def __init__(self, vm, node, name, member_map):
    super(Module, self).__init__(vm.convert.module_type, vm=vm, node=node)
    self.name = name
    self._member_map = member_map

  def _convert_member(self, name, ty):
    """Called to convert the items in _member_map to cfg.Variable."""
    var = self.vm.convert.convert_constant(name, ty)
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

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    # Local variables in __init__.py take precedence over submodules.
    node, var = super(Module, self).get_attribute(node, name, valself, valcls,
                                                  condition)
    if var is None:
      full_name = self.name + "." + name
      # The line below can raise load_pytd.DependencyNotFoundError. This is OK
      # since we'll always be called from vm.byte_IMPORT_FROM which catches it.
      mod = self.vm.import_module(full_name, 0)  # 0: absolute import
      if mod is not None:
        var = mod.to_variable(node, name)
      elif self.has_getattr():
        var = self.vm.convert.create_new_unsolvable(node, full_name)
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

  def to_type(self, node, seen=None):
    return pytd.NamedType("__builtin__.module")

  def match_against_type(self, other_type, subst, node, view):
    if other_type.name in ["module", "object"]:
      return subst


class BuildClass(AtomicAbstractValue):
  """Representation of the Python 3 __build_class__ object."""

  def __init__(self, vm):
    super(BuildClass, self).__init__("__build_class__", vm)

  def call(self, node, _, args):
    funcvar, name = args.posargs[0:2]
    if len(funcvar.bindings) != 1:
      raise ConversionError("Invalid ambiguous argument to __build_class__")
    func, = funcvar.data
    if not isinstance(func, InterpreterFunction):
      raise ConversionError("Invalid argument to __build_class__")
    bases = args.posargs[2:]
    node, _ = func.call(node, funcvar.bindings[0],
                        args.replace(posargs=[], namedargs={}),
                        new_locals=True)
    return node, self.vm.make_class(
        node, name, bases,
        func.last_frame.f_locals.to_variable(node, "locals()"))


class Unsolvable(AtomicAbstractValue):
  """Representation of value we know nothing about.

  Unlike "Unknowns", we don't treat these as solveable. We just put them
  where values are needed, but make no effort to later try to map them
  to named types. This helps conserve memory where creating and solving
  hundreds of unknowns would yield us little to no information.

  This is typically a singleton. Since unsolvables are indistinguishable, we
  only need one.
  """
  IGNORED_ATTRIBUTES = ["__get__", "__set__"]

  # Since an unsolvable gets generated e.g. for every unresolved import, we
  # can have multiple circular Unsolvables in a class' MRO. Treat those special.
  SINGLETON = True

  def __init__(self, vm):
    super(Unsolvable, self).__init__("unsolveable", vm)
    self.mro = self.default_mro()

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    if name in self.IGNORED_ATTRIBUTES:
      return node, None
    return node, self.to_variable(node, self.name)

  def get_attribute_flat(self, node, name):
    return self.get_attribute(node, name)

  def set_attribute(self, node, name, _):
    return node

  def call(self, node, func, args):
    del func, args
    # return ourself.
    return node, self.to_variable(node, self.name)

  def to_variable(self, node, name=None):
    return self.vm.program.NewVariable(name, [self], source_set=[], where=node)

  def get_class(self):
    # return ourself.
    return self.to_variable(self.vm.root_cfg_node, self.name)

  def to_pytd_def(self, node, name):
    """Convert this Unknown to a pytd.Class."""
    return pytd.Constant(name, self.to_type(node))

  def to_type(self, node, seen=None):
    return pytd.AnythingType()

  def get_instance_type(self, node, instance=None, seen=None):
    del node
    return pytd.AnythingType()

  def match_against_type(self, other_type, subst, node, view):
    return other_type.match_instance(self, subst, node, view)

  def instantiate(self, node):
    # return ourself.
    return self.to_variable(node, self.name)


class Unknown(AtomicAbstractValue):
  """Representation of unknown values.

  These are e.g. the return values of certain functions (e.g. eval()). They
  "adapt": E.g. they'll respond to get_attribute requests by creating that
  attribute.

  Attributes:
    members: Attributes that were written or read so far. Mapping of str to
      typegraph.Variable.
    owner: typegraph.Binding that contains this instance as data.
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
    self.mro = self.default_mro()
    log.info("Creating %s", self.class_name)

  def get_children_maps(self):
    return (self.members,)

  @staticmethod
  def _to_pytd(node, v):
    if isinstance(v, typegraph.Variable):
      return pytd_utils.JoinTypes(Unknown._to_pytd(node, t) for t in v.data)
    elif isinstance(v, Unknown):
      # Do this directly, and use NamedType, in case there's a circular
      # dependency among the Unknown instances.
      return pytd.NamedType(v.class_name)
    else:
      return v.to_type(node)

  @staticmethod
  def _make_params(node, args):
    """Convert a list of types/variables to pytd parameters."""
    return tuple(pytd.Parameter("_%d" % (i + 1), Unknown._to_pytd(node, p),
                                kwonly=False, optional=False,
                                mutated_type=None)
                 for i, p in enumerate(args))

  def get_attribute(self, node, name, valself=None, valcls=None,
                    condition=None):
    if name in self.IGNORED_ATTRIBUTES:
      return node, None
    if name in self.members:
      return node, self.members[name]
    new = self.vm.convert.create_new_unknown(self.vm.root_cfg_node,
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

  def call(self, node, _, args):
    ret = self.vm.convert.create_new_unknown(
        node, self.name + "()", source=self.owner, action="call:" + self.name)
    self._calls.append((args.posargs, args.namedargs, ret))
    return node, ret

  def to_variable(self, node, name=None):
    v = self.vm.program.NewVariable(self.name or name)
    val = v.AddBinding(self, source_set=[], where=node)
    self.owner = val
    self.vm.trace_unknown(self.class_name, v)
    return v

  def to_structural_def(self, node, class_name):
    """Convert this Unknown to a pytd.Class."""
    self_param = (pytd.Parameter("self", pytd.NamedType("__builtin__.object"),
                                 False, False, None),)
    # TODO(kramm): Record these.
    starargs = None
    starstarargs = None
    calls = tuple(pytd_utils.OrderedSet(
        pytd.Signature(self_param + self._make_params(node, args),
                       starargs,
                       starstarargs,
                       return_type=Unknown._to_pytd(node, ret),
                       exceptions=(),
                       template=())
        for args, _, ret in self._calls))
    if calls:
      methods = (pytd.Function("__call__", calls, pytd.METHOD),)
    else:
      methods = ()
    return pytd.Class(
        name=class_name,
        parents=(pytd.NamedType("__builtin__.object"),),
        methods=methods,
        constants=tuple(pytd.Constant(name, Unknown._to_pytd(node, c))
                        for name, c in self.members.items()),
        template=())

  def get_class(self):
    # We treat instances of an Unknown as the same as the class.
    return self.to_variable(self.vm.root_cfg_node, "class of " + self.name)

  def to_type(self, node, seen=None):
    return pytd.NamedType(self.class_name)

  def get_instance_type(self, node, instance=None, seen=None):
    log.info("Using ? for instance of %s", self.name)
    return pytd.AnythingType()

  def match_against_type(self, other_type, subst, node, view):
    # TODO(kramm): Do we want to match the instance or the class?
    return other_type.match_instance(self, subst, node, view)
