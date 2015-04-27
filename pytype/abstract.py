"""The abstract values used by typegraphvm.

An abstract value in effect represents a type. Groups of types are
combined using typegraph and that is what we compute over.
"""

# Because of false positives:
# pylint: disable=unpacking-non-sequence
# pylint: disable=abstract-method

import collections
import logging


from pytype import exceptions
from pytype import path
from pytype import utils
from pytype.pyc import loadmarshal
from pytype.pytd import cfg as typegraph
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)


def variable_set_official_name(variable, name):
  """Set official_name on each value in the variable.

  Called when a variable is stored in locals().

  Args:
    variable: A typegraph.Variable to name.
    name: The name to give.
  """
  for v in variable.values:
    v.data.official_name = name


def match_var_against_type(var, other_type, subst, loc):
  """One-way unify value into pytd type given a substitution.

  Args:
    var: A typegraph.Variable
    other_type: An AtomicAbstractValue instance.
    subst: The current substitution. This dictionary is not modified.
    loc: Current location (typegraph CFG node)
  Returns:
    A new (or unmodified original) substitution dict if the matching succeded,
    None otherwise.
  """
  # TODO(ampere): Add support for functions and other things.
  if isinstance(other_type, Class):
    # Accumulate substitutions in "subst", or break in case of error:
    for val in var.values:
      subst = val.data.match_against_type(other_type, subst)
      if subst is None:
        break
  elif isinstance(other_type, Union):
    for t in other_type.options:
      new_subst = match_var_against_type(var, t, subst, loc)
      if new_subst is not None:
        # TODO(kramm): What if more than one type matches?
        subst = new_subst
        break
    else:
      subst = None
  elif isinstance(other_type, TypeParameter):
    if other_type.name in subst:
      # Merge the two variables.
      subst = subst.copy()
      new_var = subst[other_type.name].AssignToNewVariable(other_type.name, loc)
      new_var.AddValues(var, loc)
      subst[other_type.name] = new_var
    else:
      subst = subst.copy()
      subst[other_type.name] = var
  elif (isinstance(other_type, Unknown) or
        any(isinstance(val.data, Unknown) for val in var.values)):
    # We can match anything against unknown types, and unknown types against
    # anything.
    # TODO(kramm): Do we want to record what we matched them against?
    assert not isinstance(other_type, ParameterizedClass)
  else:
    log.error("Invalid type: %s", type(other_type))
    subst = None
  return subst


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

  def __init__(self, vm):
    """Basic initializer for all AtomicAbstractValues."""
    assert hasattr(vm, "program")
    self.vm = vm
    self.mro = []
    AtomicAbstractValue._value_id += 1
    self.id = AtomicAbstractValue._value_id
    self.name = "v%d" % self.id
    self.parent = None
    self.official_name = None

  def get_name(self):
    """Return the name of this value.

    The proper name of the value is taken to be the name given to the object by
    Python (such as by the func_name attribute or the __name__ attribute) if the
    value was also stored into locals with that name at some point.  This
    differs from self.name because the latter is *always* set, whereas
    official_name only gets set if the value was stored into locals.

    Returns:
      The proper name of this value or None.
    """
    return self.official_name

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

  def get_attribute(self, name, valself=None, valcls=None):  # pylint: disable=unused-argument
    """Get the named attribute from this object.

    Args:
      name: The name of the attribute to retrieve.
      valself: A typegraph.Value, This is the self reference to use when getting
        the attribute.
      valcls: A typegraph.Value. This is the cls reference to use when getting
        the attribute. If valself is given then valcls will be ignored. Note
        that most implementations of this method ignore this value as only class
        objects need it (PyTDClass and InterpreterClass)

    Returns:
      A typegraph.Variable, or None if this attribute doesn't exist.
    """
    return None

  def has_attribute(self, name, valself=None, valcls=None):
    # TODO(pludemann): make varself, varcls required args (no default)
    """Trie of self has the named attribute.

    Args:
      name: The name of the attribute to retrieve.
      valself: A typegraph.Value. See get_attribute.
      valcls: A typegraph.Value. See get_attribute.

    Returns:
      A boolean.
    """
    attr = self.get_attribute(name, valself, valcls)
    return bool(attr and len(attr.values))

  def set_attribute(self, name, value):
    """Set an attribute on this object.

    Args:
      name: The name of the attribute to set.
      value: The Variable to store in it.

    The attribute might already have a Variable in it and in that case we cannot
    overwrite it and instead need to add the elements of the new variable to the
    old variable.
    """
    raise NotImplementedError()

  def call(self, node, f, args, kws):
    """Call this abstract value with the given arguments.

    The args and kws arguments may be modified by this function.

    Args:
      node: The CFGNode calling this function
      f: The typegraph.Value containing this function.
      args: Positional arguments for the call (Variables).
      kws: Keyword arguments for the call (Variables).
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

  def get_type(self):
    """Return the type of this object. Equivalent of type(x) in Python."""
    raise NotImplementedError(self.__class__.__name__)

  def to_type(self):
    """Get a PyTD type representing this object."""
    raise NotImplementedError(self.__class__.__name__)

  def to_variable(self, name=None):
    """Build a variable out of this abstract value.

    Args:
      name: The name to give the new variable.
    Returns:
      A typegraph.Variable.
    Raises:
      ValueError: If origins is an empty sequence. This is to prevent you from
        creating variables that have no origin and hence can never be used.
    """
    v = self.vm.program.NewVariable(name or self.get_name())
    v.AddValue(self, source_set=[], where=self.vm.current_location)
    return v

  def get_static_path(self):
    """Return the static value path of this object.

    Returns:
      An instance of path.Path, or None if this object does not have a
      proper name. See get_name for a discussion of proper names.
    """
    raise NotImplementedError

  def match_instance_against_type(self, instance, other_type, subst):
    raise NotImplementedError("%s is not a class" % type(self))

  def match_against_type(self, other_type, subst):
    raise NotImplementedError("Matching not implemented for %s", type(self))

  def full_name(self):
    return str(self.get_static_path())

  def _raise_failed_function_call(self, explanation_lines):
    """Convenience function to log & raise, used by subclasses."""
    log.debug("Raise FailedFunctionCall for %s", self)
    for msg in explanation_lines:
      log.debug("  %s", msg)
    log.debug("End FailedFunctionCall explanation")
    raise FailedFunctionCall(self, explanation_lines)


class PythonConstant(object):
  """A mix-in for storing actual Python constants, not just their types.

  This is used for things that are stored in typegraph.Variable, but where we
  may need the actual data in order to proceed later. E.g. function / class
  definitions, tuples. Also, potentially: Small integers, strings (E.g. "w",
  "r" etc.).
  """

  def __init__(self, pyval):
    self.pyval = pyval


class TypeParameter(AtomicAbstractValue):
  """Parameter of a type.

  Attributes:
    name: Type parameter name
    pytd_instance: The PYTD instance used to mark of this type parameter, for
      matching.
  """

  def __init__(self, name, pytd_instance, vm):
    super(TypeParameter, self).__init__(vm)
    self.name = name
    self.pytd_instance = pytd_instance

  def __repr__(self):
    return "TypeParameter(%r)" % self.name


class SimpleAbstractValue(AtomicAbstractValue):
  """A basic abstract value that represents instances.

  This class implements instances in the python sense. Instances of the same
  type may vary however the type of an object represented by this type will be
  in it's __class__ attribute (get_attribute("__class__")). This class
  implements attribute resolution in the class.

  Note that the __class__ attribute will point to another abstract value that
  represents the class object itself, not to some special type representation.
  """

  def __init__(self, name, vm):
    """Initialize a SimpleAbstractValue.

    Args:
      name: Name of this value. For debugging and error reporting.
      vm: The TypegraphVirtualMachine to use.
    """
    super(SimpleAbstractValue, self).__init__(vm)
    self.name = name
    self.members = {}
    self.type_parameters = {}

  def get_type_parameter(self, name):
    """Get the typegraph.Variable representing the type parameter of self.

    This will be a typegraph.Variable made up of values that have been used in
    place of this type parameter.

    Args:
      name: The name of the type parameter.
    Returns:
      A Variable which may be empty.
    """
    param = self.type_parameters.get(name)
    if not param:
      param = self.vm.new_variable(name, [], [], self.vm.current_location)
      self.type_parameters[name] = param
    return param

  def merge_type_parameter(self, name, value):
    """Set the value of a type parameter.

    This will always add to the type_parameter unlike set_attribute which will
    replace value from the same basic block. This is because type parameters may
    be affected by a side effect so we need to collect all the information
    regardless of multiple assignments in one basic block.

    Args:
      name: The name of the type parameter.
      value: The value that is being used for this type parameter as a Variable.
    """
    param = self.get_type_parameter(name)
    self.type_parameters[name] = self.vm.join_variables(name, [param, value])

  def overwrite_type_parameter(self, name, value):
    """Overwrite the value of a type parameter.

    Unlike merge_type_parameter, this will purge the previous value and set
    the type parameter only to the new value.

    Args:
      name: The name of the type parameter.
      value: The new type parameter as a Variable.
    """
    self.type_parameters[name] = self.vm.new_variable(
        name, value.data, [], self.vm.current_location)

  def get_attribute(self, name, valself=None, valcls=None):
    candidates = []
    if "__class__" in self.members:
      # TODO(kramm): superclasses
      for clsval in self.members["__class__"].values:
        cls = clsval.data
        attr = cls.get_attribute(name, valself, clsval)
        if attr is not None:
          candidates.append(attr)
    if name in self.members:
      candidates.append(self.members[name])

    if not candidates:
      return None
    elif len(candidates) == 1:
      return candidates[0]
    else:
      ret = self.vm.program.NewVariable(name)
      for candidate in candidates:
        ret.AddValues(candidate, self.vm.current_location)
      return ret

  def set_attribute(self, name, var):
    assert isinstance(var, typegraph.Variable)

    if name == "__class__":
      assert all(hasattr(v.data, "name") for v in var.values), [
          v.data for v in var.values]

    variable = self.members.get(name)
    if variable:
      old_len = len(variable.values)
      variable.AddValues(var, self.vm.current_location)
      log.debug("Adding choice(s) to %s: %d new values", name,
                len(variable.values) - old_len)
    else:
      # TODO(kramm): Under what circumstances can we just reuse var?
      #              (variable = self.members[name] = var)?
      if name != "__class__":
        log.debug("Setting %s to the %d values in %r",
                  name, len(var.values), var)
      long_name = self.name + "." + name
      variable = var.AssignToNewVariable(long_name, self.vm.current_location)
      self.members[name] = variable

  def call(self, node, unused_func, args, kws):
    # End up here for:
    #   f = 1
    #   f()  # Can't call an int
    # TODO(kramm): What if we have a __call__ attribute?
    self._raise_failed_function_call(
        ["__call__ on SimpleAbstractValue not implemented"])

  def __repr__(self):
    if "__class__" in self.members:
      cls = self.members["__class__"].data[0]
      return "<v%d %s [%r]>" % (self.id, self.name, cls)
    else:
      return "<v%d %s>" % (self.id, self.name)

  def to_variable(self, name=None):
    assert name
    return super(SimpleAbstractValue, self).to_variable(name)

  def get_type(self):
    # See Py_TYPE() in Include/object.h
    return self.members.get("__class__")

  def to_type(self):
    """Get a PyTD type representing this object.

    This uses the values __class__ attribute to determine the type that it has.

    Returns:
      A PyTD Type
    """
    if "__class__" in self.members:
      classvalues = (v.data for v in self.members["__class__"].values)
      types = []
      for cls in classvalues:
        types.append(cls.get_instance_type(self))
      ret = pytd_utils.JoinTypes(types)
      visitors.FillInClasses(ret, self.vm.builtins_pytd)
      return ret
    else:
      # We don't know this type's __class__, so return AnythingType to indicate
      # that we don't know anything about what this is.
      # This happens e.g. for locals / globals, which are returned from the code
      # in class declarations.
      return pytd.AnythingType()

  def get_static_path(self):
    if "__class__" in self.members:
      classes = self.members["__class__"].values
      if len(classes) == 1:
        return classes[0].data.get_static_path()
      else:
        raise ValueError("Value has no path")

  def match_against_type(self, other_type, subst):
    my_type = self.get_type()
    if not my_type:
      log.warning("Can't match %s against %s", self.__class__, other_type.name)
      return None
    for my_cls in my_type.data:
      subst = my_cls.match_instance_against_type(self, other_type, subst)
      if subst is None:
        return None
    return subst


class Instance(SimpleAbstractValue):

  def __init__(self, clsvar, vm):
    super(Instance, self).__init__(clsvar.name, vm)
    self.members["__class__"] = clsvar


class ValueWithSlots(SimpleAbstractValue):
  """Convenience class for overriding slots with custom methods.

  This makes it easier to emulate built-in classes like dict which need special
  handling of some magic methods (__setitem__ etc.)
  """

  def __init__(self, name, vm):
    super(ValueWithSlots, self).__init__(name, vm)
    self.name = name
    self._slots = {}
    self._self = {}  # TODO(kramm): Find a better place to store these.
    self._super = {}

  def set_slot(self, name, method):
    """Add a new slot to this value."""
    assert name not in self._slots, "slot %s already occupied" % name
    self._slots[name] = NativeFunction(
        name, method, self.vm).to_variable(name)
    self._super[name] = super(ValueWithSlots, self).get_attribute(name)

  def call_pytd(self, name, *args):
    """Call the (original) pytd version of a method we overwrote."""
    if name in self._self:
      return self.vm.call_function(self._super[name],
                                   (self._self[name],) + args)
    else:
      log.error(
          "Can't call bound method %s: We don't know how it was bound.", name)
      return None

  def get_attribute(self, name, valself=None, valcls=None):
    """Get an attribute.

    Will delegate to SimpleAbstractValue if we don't have a slot for it.

    Arguments:
      name: name of the attribute. If this is something like "__getitem__",
        the slot mechanism might kick in.
      valself: A typegraph.Value. See AtomicAbstractValue.get_attribute.
      valcls: A typegraph.Value. See AtomicAbstractValue.get_attribute.

    Returns:
      The attribute, as a typegraph.Variable.
    """
    if name in self._slots:
      self._self[name] = valself.variable
      return self._slots[name]
    else:
      return super(ValueWithSlots, self).get_attribute(name, valself, valcls)


class Dict(ValueWithSlots):
  """Representation of Python 'dict' objects.

  It works like __builtins__.dict, except that, for string keys, it keeps track
  of what got stored.
  """

  # These match __builtins__.pytd:
  KEY_TYPE_PARAM = "K"
  VALUE_TYPE_PARAM = "V"

  def __init__(self, name, vm):
    super(Dict, self).__init__(name, vm)
    self.name = name
    self._entries = {}
    self.set_attribute("__class__", vm.dict_type)
    self.set_slot("__getitem__", self.getitem_slot)
    self.set_slot("__setitem__", self.setitem_slot)

  def getitem_slot(self, name_var):
    """Implements the __getitem__ slot."""
    results = []
    for val in name_var.values:
      try:
        name = self.vm.convert_value_to_string(val.data)
      except ValueError:  # ConversionError
        # We *do* know the overall type of the values through the "V" type
        # parameter, even if we don't know the exact type of self[name]:
        results.append(self.get_type_parameter("V"))
      else:
        try:
          results.append(self._entries[name])
        except KeyError:
          raise exceptions.ByteCodeKeyError("KeyError: %r" % name)
    # For call tracing only, we don't actually use the return value:
    _ = self.call_pytd("__getitem__", name_var)
    return self.vm.join_variables("getitem[var%s]" % name_var.id, results)

  def set_str_item(self, name, value_var):
    self.merge_type_parameter(self.KEY_TYPE_PARAM, self.vm.build_string(name))
    self.merge_type_parameter(self.VALUE_TYPE_PARAM, value_var)
    if name in self._entries:
      self._entries[name].AddValues(value_var, self.vm.current_location)
    else:
      self._entries[name] = value_var

  def setitem(self, name_var, value_var):
    assert isinstance(name_var, typegraph.Variable)
    assert isinstance(value_var, typegraph.Variable)
    for val in name_var.values:
      try:
        name = self.vm.convert_value_to_string(val.data)
      except ValueError:  # ConversionError
        continue
      if name in self._entries:
        self._entries[name].AddValues(value_var, self.vm.current_location)
      else:
        self._entries[name] = value_var

  def setitem_slot(self, name_var, value_var):
    """Implements the __setitem__ slot."""
    self.setitem(name_var, value_var)
    return self.call_pytd("__setitem__", name_var, value_var)

  def values(self):
    return self._entries.values()

  def items(self):
    return self._entries.items()

  def update(self, other_dict):
    assert isinstance(other_dict, typegraph.Variable)
    for v in other_dict.data:
      if isinstance(v, Dict):
        for key, value in v.items():
          # TODO(kramm): sources
          self.set_str_item(key, value)


class AbstractOrConcreteValue(Instance, PythonConstant):
  """Abstract value with a concrete fallback."""

  def __init__(self, pyval, clsvar, vm):
    Instance.__init__(self, clsvar, vm)
    PythonConstant.__init__(self, pyval)


class LazyAbstractValue(SimpleAbstractValue):
  """Extend SimpleAbstractValue with support for lazy resolution of its members.

  This is mostly useful for large context dictionaries or classes (the actual
  class object), since it avoids loading members that are not needed in the
  program.
  """

  def __init__(self, name, member_map, resolver, vm):
    """Initialize a LazyAbstractValue.

    Args:
      name: Name of this value. For debugging and error reporting.
      member_map: A dict from names to arbitrary python values.
      resolver: A function that takes an arbitrary value from member_map and
        returns typegraph.Variables.
      vm: The TypegraphVirtualMachine to use.
    """
    super(LazyAbstractValue, self).__init__(name, vm)
    assert callable(resolver)
    self._member_map = member_map
    self._resolver = resolver

  def _load_attribute(self, name):
    """Load the named attribute into self.members."""
    if name not in self.members and name in self._member_map:
      variable = self._resolver(name, self._member_map[name])
      assert isinstance(variable, typegraph.Variable)
      self.members[name] = variable

  def get_attribute(self, name, valself=None, valcls=None):
    self._load_attribute(name)
    return super(LazyAbstractValue, self).get_attribute(name, valself, valcls)

  def has_attribute(self, name, valself=None, valcls=None):
    self._load_attribute(name)
    return super(LazyAbstractValue, self).has_attribute(name, valself, valcls)

  def set_attribute(self, name, value):
    self._load_attribute(name)
    return super(LazyAbstractValue, self).set_attribute(name, value)

  def __repr__(self):
    return utils.maybe_truncate(self.name)


class LazyAbstractOrConcreteValue(LazyAbstractValue, PythonConstant):
  """Lazy abstract value with a concrete fallback."""

  def __init__(self, name, pyval, member_map, resolver, vm):
    LazyAbstractValue.__init__(self, name, member_map, resolver, vm)
    PythonConstant.__init__(self, pyval)


class Union(AtomicAbstractValue):
  """A list of types. Used for parameter matching.

  Attributes:
    options: Iterable of instances of AtomicAbstractValue.
  """

  def __init__(self, options, vm):
    super(Union, self).__init__(vm)
    self.options = options


# return value from PyTDSignature._call_with_values:
FunctionCallResult = collections.namedtuple("_", "return_type, subst, sources")


class FailedFunctionCall(Exception):
  """Exception for when there's no possible value from a call.

  This is caught wherever there is the possibility of multiple call signatures
  matching, and it's OK to have individual failures as long as there's at least
  one that matches. If nothing matches, a new exception is thrown and will
  eventually bubble up to typegraphvm.call_function().
  """

  def __init__(self, obj, explanation_lines):
    super(FailedFunctionCall, self).__init__()
    self.obj = obj
    self.explanation_lines = explanation_lines

  def __repr__(self):
    return "FailedFunctionCall(%s, %s)" % (self.obj, self.explanation_lines)


class PyTDSignature(AtomicAbstractValue):
  """A PyTD function type (signature).

  This represents instances of functions with specific arguments and return
  type.
  """

  def __init__(self, function, pytd_sig, vm):
    super(PyTDSignature, self).__init__(vm)
    self.function = function
    self.name = function.name
    self.pytd_sig = pytd_sig
    self.param_types = [
        self.vm.convert_constant_to_value(pytd.Print(p), p.type)
        for p in self.pytd_sig.params]

  def property_get(self, callself, callcls):
    assert callself
    return BoundPyTDSignature(self.function, callself,
                              self.pytd_sig, self.vm)

  def get_attribute(self, name, valself=None, valcls=None):
    return None

  def has_attribute(self, name, valself=None, valcls=None):
    return False

  def set_attribute(self, name, value):
    raise AttributeError()

  def call(self, node, func, args, kws):
    if self.pytd_sig.has_optional:
      # Truncate extraneous params. E.g. when calling f(a, b, ...) as f(1, 2, 3)
      args = args[0:len(self.pytd_sig.params)]
    if len(args) != len(self.pytd_sig.params):
      # Number of parameters mismatch is possible when matching against an
      # overloaded function (e.g., a __builtins__ entry that has optional
      # parameters that are specified by multiple def's).
      msg_lines = [
          "Function %s was called with %d args instead of expected %d" %
          (self.function.full_name(), len(args),
           len(self.pytd_sig.params)),
          "  Expected: %r" % [p.name for p in self.pytd_sig.params],
          "  Actually passed: %r" % (args,)]
      self._raise_failed_function_call(msg_lines)
    results = collections.defaultdict(list)
    msg_lines = []
    for args_selected in utils.variable_product(args):
      for kws_selected in utils.variable_product_dict(kws):
        try:
          r = self._call_with_values(args_selected, kws_selected)
        except FailedFunctionCall as e:
          msg_lines.extend(e.explanation_lines)
        else:
          results[(r.return_type, r.subst)].append(r.sources)
    if not results:
      self._raise_failed_function_call(msg_lines)
    retvar = self.vm.program.NewVariable("<return:" + self.name + "()>")
    for (return_type, subst), source_sets in results.items():
      for t in pytd_utils.UnpackUnion(return_type):
        if isinstance(t, pytd.TypeParameter) and t.name in subst:
          # For functions that directly return a type parameter.
          retvar.AddValues(subst[t.name], self.vm.current_location)
        else:
          v = self.vm.create_pytd_instance_value(t, subst)
          for source_set in source_sets:
            retvar.AddValue(v, source_set + [func], self.vm.current_location)
    return node, retvar

  def _call_with_values(self, arg_values, kw_values):
    """Try to execute this signature with the given arguments.

    This uses specific typegraph.Value instances (not: Variables) to try to
    match this signature. This is used by call(), which dissects
    typegraph.Variable instances into Value lists.

    Args:
      arg_values: A list of pytd.Value instances.
      kw_values: A map of strings to pytd.Values instances.
    Returns:
      A FunctionCallResult instance
    Raises:
      FailedFunctionCall
    """
    return_type = self.pytd_sig.return_type
    subst = self._compute_subst(arg_values, kw_values)
    # FailedFunctionCall is thrown by _compute_subst if no signature could be
    # matched (subst might be []).
    log.debug("Matched arguments against sig%s", pytd.Print(self.pytd_sig))
    for nr, (actual, formal) in enumerate(zip(arg_values,
                                              self.pytd_sig.params)):
      log.info("param %d) %s: %s <=> %s %r", nr, formal.name, formal.type,
               actual.data, actual.variable)
    for name, value in sorted(subst.items()):
      log.debug("Using %s=%r", name, value)
    self._execute_mutable(arg_values, kw_values, subst)
    # Use a plain list (NOT: itertools.chain etc.) to facilitate memoization.
    sources = list(arg_values) + kw_values.values()
    return FunctionCallResult(return_type, subst, sources)

  def _compute_subst(self, arg_values, kw_values):
    """Compute information about type parameters using one-way unification.

    Given the arguments of a function call, try to find a substitution that
    matches them against the formal parameter of this PyTDSignature.

    Args:
      arg_values: A list of pytd.Value instances.
      kw_values: A map of strings to pytd.Values instances.
    Returns:
      utils.HashableDict if we found a working substition, None otherwise.
    Raises:
      FailedFunctionCall
    """
    if not arg_values:
      return utils.HashableDict()
    if kw_values:
      log.warning("Ignoring keyword parameters %r", kw_values)
    subst = {}
    for actual, formal in zip(arg_values, self.param_types):
      actual_var = actual.AssignToNewVariable(formal.name,
                                              self.vm.current_location)
      subst = match_var_against_type(actual_var, formal,
                                     subst, self.vm.current_location)
      if subst is None:
        # This parameter combination didn't work.
        # This is typically a real error: The user program is calling a
        # builtin type with incorrect arguments. However, for multiple
        # signatures, it's not an error (unless nothing matches).
        msg_lines = ["Function %s was called with the wrong arguments" %
                     self.function.full_name(),
                     "  Expected: %r" % ["%s: %s" % (p.name, p.type)
                                         for p in self.pytd_sig.params],
                     "  Actually passed: %r" % [a.data.name
                                                for a in arg_values]]
        self._raise_failed_function_call(msg_lines)
    return utils.HashableDict(subst)

  def _execute_mutable(self, arg_values, kw_values, subst):
    """Change the type parameters of mutable arguments.

    This will adjust the type parameters as needed for pytd functions like:
      def append_float(x: list<int>):
        x := list<int or float>
    This is called after all the signature matching has succeeded, and we
    know we're actually calling this function. We'll therefore modify the input
    parameters according to the rules specified in pytd.MutableParameter.

    Args:
      arg_values: A list of pytd.Value instances.
      kw_values: A map of strings to pytd.Values instances.
      subst: Current type parameters.
    Returns:
      None
    Raises:
      ValueError: If the pytd contains invalid MutableParameter information.
    """
    # Handle mutable parameters using the information type parameters
    if kw_values:
      log.warning("Ignoring keyword parameters %r", kw_values)
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
                type_actual, subst=subst, sources=[])
            arg.overwrite_type_parameter(tparam.name, type_actual_val)
        else:
          log.error("Old: %s", pytd.Print(formal.type))
          log.error("New: %s", pytd.Print(formal.new_type))
          log.error("Actual: %r", actual)
          raise ValueError("Mutable parameters setting a type to a "
                           "different base type is not allowed.")

  def get_parameter_names(self):
    return [p.name for p in self.pytd_sig.params]

  def to_type(self):
    return pytd.NamedType("function")

  def get_static_path(self):
    return self.function.get_static_path()

  def __repr__(self):
    return pytd.Print(self.pytd_sig)


class PyTDFunction(AtomicAbstractValue):
  """A PyTD function (name + list of signatures).

  This represents (potentially overloaded) functions.
  """

  def __init__(self, name, signatures, vm):
    super(PyTDFunction, self).__init__(vm)
    self.name = name
    self.signatures = signatures

  def property_get(self, callself, callcls):
    return PyTDFunction("bound " + self.name,
                        [s.property_get(callself, callcls)
                         for s in self.signatures], self.vm)

  def call(self, node, func, args, kws):
    log.debug("Calling function %r: %d signature(s)",
              self.name, len(self.signatures))
    # If we're calling an overloaded pytd function with an unknown as a
    # parameter, we can't tell whether it matched or not. Hence, we don't know
    # which signature got called. Check if this is the case and if yes, return
    # an unknown.
    # TODO(kramm): We should only do this if the return values of the possible
    #              signatures (taking into account unknowns) actually differ.
    if (len(self.signatures) > 1 and
        any(isinstance(value, Unknown)
            for arg in (args + kws.values())
            for value in arg.data)):
      log.debug("Creating unknown return")
      # TODO(kramm): Add proper sources.
      # TODO(kramm): What about mutable parameters?
      return node, self.vm.create_new_unknown(
          "<unknown return of " + self.name + ">")

    # We only take the first signature that matches, and ignore all after it.
    # This is because in the pytds for the standard library, the last
    # signature(s) is/are fallback(s) - e.g. list is defined by
    # def __init__(self: x: list)
    # def __init__(self, x: iterable)
    # def __init__(self, x: generator)
    # def __init__(self, x: object)
    # with the last signature only being used if none of the others match.
    msg_lines = []
    for sig in self.signatures:
      try:
        new_node, result = sig.call(node, func, args, kws)
      except FailedFunctionCall as e:
        msg_lines.extend(e.explanation_lines)
      else:
        return new_node, result
    self._raise_failed_function_call(
        ["Failed call function %r: signature: %r" %
         (self.name, self.signatures)] +
        msg_lines)

  def to_type(self):
    return pytd.NamedType("function")

  def get_static_path(self):
    if self.parent:
      return path.Path(path.Class(self.parent.name),
                       path.Function(self.name))
    else:
      return path.Path(path.Function(self.name))

  def __repr__(self):
    return self.name + "(...)"

  def match_against_type(self, other_type, subst):
    if other_type.name in ["function", "object"]:
      return subst


class BoundPyTDSignature(PyTDSignature):
  """A PyTD function type which has had an argument bound into it.
  """

  def __init__(self, function, callself, pytd_sig, vm):
    super(BoundPyTDSignature, self).__init__(function, pytd_sig, vm)
    self._callself = callself
    self.name = "bound " + function.name

  def call(self, node, func, args, kws):
    return super(BoundPyTDSignature, self).call(
        node, func, [self._callself] + args, kws)

  def get_bound_arguments(self):
    return [self._callself]


class Class(object):
  """Mixin to mark all class-like values."""

  def __new__(cls, *args, **kwds):
    """Prevent direct instantiation."""
    assert cls is not Class, "Cannot instantiate Class"
    return object.__new__(cls, *args, **kwds)

  def get_attribute(self, name, valself=None, valcls=None):
    """Retrieve an attribute by looking at the MRO of this class."""
    ret = self.vm.program.NewVariable(name)
    add_origins = []
    if valself and valcls:
      assert isinstance(valself, typegraph.Value)
      assert isinstance(valcls, typegraph.Value)
      variableself = valself.AssignToNewVariable(valself.variable.name,
                                                 self.vm.current_location)
      variablecls = valcls.AssignToNewVariable(valcls.variable.name,
                                               self.vm.current_location)
      add_origins.append(valself)
      add_origins.append(valcls)
    else:
      variableself = variablecls = None

    # Trace down the MRO if there is one.
    # TODO(ampere): Handle case where class has variables INSIDE it?
    for base in self.mro:
      var = base.get_attribute_flat(name)
      if var is None:
        continue
      for varval in var.values:
        value = varval.data
        if variableself and variablecls:
          value = value.property_get(variableself, variablecls)
        ret.AddValue(value, [varval] + add_origins, self.vm.current_location)
      break  # we found a class which has this attribute
    return ret


class ParameterizedClass(AtomicAbstractValue, Class):
  """A class that contains additional parameters. E.g. a container."""

  def __init__(self, cls, type_parameters, vm):
    super(ParameterizedClass, self).__init__(vm)
    self.cls = cls
    self.type_parameters = type_parameters

  def __repr__(self):
    return "ParameterizedClass(cls=%r params=%s)" % (self.cls,
                                                     self.type_parameters)

  def to_type(self):
    return pytd.NamedType("type")

  def get_instance_type(self, _):
    type_arguments = []
    for type_param in self.cls.cls.template:
      values = (self.type_parameters[type_param.name],)
      type_arguments.append(pytd_utils.JoinTypes([e.get_instance_type(None)
                                                  for e in values]))
    return pytd_utils.MakeClassOrContainerType(
        pytd.NamedType(self.cls.cls.name), type_arguments)


class PyTDClass(LazyAbstractValue, Class):
  """An abstract wrapper for PyTD class objects.

  These are the abstract values for class objects that are described in PyTD.
  """

  def __init__(self, cls, vm):
    mm = {}
    for val in cls.constants + cls.methods:
      mm[val.name] = val
    super(PyTDClass, self).__init__(cls.name, mm, self._retrieve_member, vm)
    self.cls = cls
    self.mro = utils.compute_mro(self)
    self.formal_type_parameters = {}

  def get_attribute(self, name, valself=None, valcls=None):
    return Class.get_attribute(self, name, valself, valcls)

  def bases(self):
    return [self.vm.convert_constant_to_value(parent.name, parent)
            for parent in self.cls.parents]

  def _retrieve_member(self, name, pyval):
    """Convert a member as a variable. For lazy lookup."""
    c = self.vm.convert_constant_to_value(repr(pyval), pyval)
    c.parent = self
    return c.to_variable(name)

  def get_attribute_flat(self, name):
    # delegate to LazyAbstractValue
    return super(PyTDClass, self).get_attribute(name)

  def call(self, node, func, args, kws):
    value = SimpleAbstractValue("instance of " + self.name, self.vm)
    value.set_attribute(
        "__class__",
        self.vm.convert_constant(self.name + ".__class__", self.cls))

    fill_in_type_params = True
    if fill_in_type_params:
      for type_param in self.cls.template:
        unknown = self.vm.create_new_unknown(type_param.name)
        value.overwrite_type_parameter(type_param.name, unknown)

    origins = [func] + sum((u.values for u in args + kws.values()), [])
    results = self.vm.program.NewVariable(self.name)
    retval = results.AddValue(value, origins, self.vm.current_location)

    init = value.get_attribute("__init__",
                               retval,
                               value.get_attribute("__class__").values[0])
    # TODO(pludemann): Verify that this follows MRO:
    if init:
      log.debug("calling %s.__init__(...)", self.name)
      ret = self.vm.call_function(init, args, kws)
      log.debug("%s.__init__(...) returned %r", self.name, ret)

    return node, results

  def to_type(self):
    return pytd.NamedType("type")

  def get_instance_type(self, instance):
    """Convert instances of this class to their PYTD type."""
    type_arguments = []
    for type_param in self.cls.template:
      values = (v.data
                for v in instance.get_type_parameter(type_param.name).values)
      type_arguments.append(pytd_utils.JoinTypes([e.to_type() for e in values]))
    return pytd_utils.MakeClassOrContainerType(
        pytd.NamedType(self.cls.name), type_arguments)

  def __repr__(self):
    return self.cls.name

  def match_instance_against_type(self, instance, other_type, subst):
    """Match an instance of this class against an other type."""
    if other_type is self:
      return subst
    elif isinstance(other_type, ParameterizedClass) and other_type.cls is self:
      extra_params = (set(instance.type_parameters.keys()) -
                      set(other_type.type_parameters.keys()))
      assert not extra_params
      for name, class_param in other_type.type_parameters.items():
        instance_param = instance.get_type_parameter(name)
        subst = match_var_against_type(instance_param, class_param, subst,
                                       self.vm.current_location)
        if subst is None:
          return None
      return subst
    elif other_type.name == "object":
      return subst
    return None

  def match_against_type(self, other_type, subst):
    if other_type.name == "type":
      return subst


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
    self._bases = bases
    self.mro = utils.compute_mro(self)
    self.members = members
    self.formal_type_parameters = {}  # builtin types don't have type params
    log.info("Created class: %r", self)

  def bases(self):
    return self._bases

  def get_attribute_flat(self, name):
    return super(InterpreterClass, self).get_attribute(name)

  def get_attribute(self, name, valself=None, valcls=None):
    return Class.get_attribute(self, name, valself, valcls)

  def set_attribute(self, name, value):
    # Note that even if we have a superclass that already has an attribute
    # with this name, Python will still set the (possibly new) attribute
    # on this class, thus shadowing the one on the superclass. Hence MRO doesn't
    # come into play.
    return super(InterpreterClass, self).set_attribute(name, value)

  def call(self, node, func, args, kws):
    value = SimpleAbstractValue("instance of " + self.name, self.vm)
    value.set_attribute("__class__", func.variable)
    variable = self.vm.program.NewVariable(self.name + " instance")
    val = variable.AddValue(value, [func], self.vm.current_location)

    init = value.get_attribute("__init__", val)
    # TODO(pludemann): Verify that this follows MRO:
    if init:
      log.debug("calling %s.__init__(...)", self.name)
      # TODO(kramm): This needs to pass through the CFG node.
      ret = self.vm.call_function(init, args, kws)
      log.debug("%s.__init__(...) returned %r", self.name, ret)
    return node, variable

  def get_static_path(self):
    if self.get_name():
      return path.Path(path.Class(self.get_name()))
    else:
      return None

  def match_instance_against_type(self, instance, other_type, subst):
    if isinstance(other_type, Class):
      for base in self.mro:
        assert isinstance(base, Class)
        if base is self:
          return subst
      return None
    else:
      raise NotImplementedError(
          "Can't match instance %r against %r", self, other_type)

  def to_type(self):
    return pytd.NamedType("type")

  def get_instance_type(self, _):
    return pytd.NamedType(self.official_name)

  def __repr__(self):
    return "InterpreterClass(%s)" % self.name


class Function(AtomicAbstractValue):
  """Base class for function objects (NativeFunction, InterpreterFunction).

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    vm: TypegraphVirtualMachine instance.
  """

  def __init__(self, name, vm):
    super(Function, self).__init__(vm)
    self.name = name
    self.func_name = self.vm.build_string(name)
    self.cls = None

  def get_attribute(self, name, valself=None, valcls=None):
    if name == "func_name":
      return self.func_name
    else:
      return None

  def set_attribute(self, name, value):
    if name == "func_name":
      self.func_name = value
    else:
      raise AttributeError("Can't set attributes on function")

  def property_get(self, callself, callcls):
    self.cls = callcls.values[0].data
    if callself:
      return BoundFunction(callself, self)
    else:
      raise NotImplementedError()

  def get_static_path(self):
    if not self.get_name():
      return None
    if self.cls:
      return self.cls.get_static_path().add(
          path.Function(self.get_name()))
    else:
      return path.Path(path.Function(self.get_name()))

  def get_type(self):
    return self.vm.function_type

  def to_type(self):
    return pytd.NamedType("function")

  def match_against_type(self, other_type, subst):
    if other_type.name in ["function", "object"]:
      return subst


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
    self.cls = None

  def argcount(self):
    return self.func.func_code.co_argcount

  def call(self, node, unused_func, args, kws):
    # Originate a new variable for each argument and call.
    return node, self.func(
        *[u.AssignToNewVariable(u.name, self.vm.current_location)
          for u in args],
        **{k: u.AssignToNewVariable(u.name, self.vm.current_location)
           for k, u in kws.items()})

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

  def __init__(self, name, code, f_locals, f_globals, defaults, closure, vm):
    super(InterpreterFunction, self).__init__(name, vm)
    log.debug("Creating InterpreterFunction %r for %r", name, code.co_name)
    self.doc = code.co_consts[0] if code.co_consts else None
    self.name = name
    self.code = code
    self.f_globals = f_globals
    self.f_locals = f_locals
    self.defaults = tuple(defaults)
    self.closure = closure
    self.cls = None

  # TODO(kramm): support retrieving the following attributes:
  # 'func_{code, name, defaults, globals, locals, dict, closure},
  # '__name__', '__dict__', '__doc__', '_vm', '_func'

  def is_closure(self):
    return self.closure is not None

  def argcount(self):
    return self.code.co_argcount

  def _map_args(self, args, kwargs):
    """Map call args to function args.

    This emulates how Python would map arguments of function calls. It takes
    care of keyword parameters, default parameters, and *args and **kwargs.

    Args:
      args: The positional arguments. A tuple of typegraph.Variable.
      kwargs: The keyword arguments. A dictionary, mapping strings to
      typegraph.Variable.

    Returns:
      A dictionary, mapping strings (parameter names) to typegraph.Variable.
    """
    # Originate a new variable for each argument and call.
    args = [u.AssignToNewVariable(u.name, self.vm.current_location)
            for u in args]
    kwargs = {k: u.AssignToNewVariable(u.name, self.vm.current_location)
              for k, u in kwargs.items()}
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
      if key in kwargs:
        raise exceptions.ByteCodeTypeError(
            "function got multiple values for keyword argument %r" % key)
    callargs.update(positional)
    callargs.update(kwargs)
    for key in param_names:
      if key not in callargs:
        raise exceptions.ByteCodeTypeError(
            "No value for parameter %r" % key)
    arg_pos = self.code.co_argcount
    if self.code.co_flags & loadmarshal.CodeType.CO_VARARGS:
      vararg_name = self.code.co_varnames[arg_pos]
      # Build a *args tuple out of the extraneous parameters
      callargs[vararg_name] = self.vm.build_tuple(args[self.code.co_argcount:])
      arg_pos += 1
    elif len(args) > self.code.co_argcount:
      raise exceptions.ByteCodeTypeError(
          "Function takes %d positional arguments (%d given)" % (
          arg_pos, len(args)))
    if self.code.co_flags & loadmarshal.CodeType.CO_VARKEYWORDS:
      kwvararg_name = self.code.co_varnames[arg_pos]
      k = Dict("kwargs", self.vm)
      # Build a **kwargs dictionary out of the extraneous parameters
      for name, value_var in kwargs.items():
        if name not in param_names:
          k.set_str_item(name, value_var)
      callargs[kwvararg_name] = k.to_variable(kwvararg_name)
      arg_pos += 1
    return callargs

  def call(self, node, unused_func, args, kws):
    callargs = self._map_args(args, kws)
    # Might throw vm.RecursionException:
    frame = self.vm.make_frame(self.code, callargs,
                               self.f_globals, self.f_locals, self.closure)
    if self.code.co_flags & loadmarshal.CodeType.CO_GENERATOR:
      return node, Generator(frame, self.vm).to_variable(self.name)
    else:
      return self.vm.run_frame(frame, node)

  def get_parameter_names(self):
    return list(self.code.co_varnames[:self.code.co_argcount])


class BoundFunction(AtomicAbstractValue):
  """An function type which has had an argument bound into it.
  """

  def __init__(self, callself, underlying):
    super(BoundFunction, self).__init__(underlying.vm)
    self._callself = callself
    self.underlying = underlying

  def get_attribute(self, name, valself=None, valcls=None):
    return None

  def has_attribute(self, name, valself=None, valcls=None):
    return False

  def set_attribute(self, name, value):
    raise AttributeError()

  def argcount(self):
    return self.underlying.argcount() - 1  # account for self

  def call(self, node, func, args, kws):
    return self.underlying.call(node, func, [self._callself] + args, kws)

  def get_bound_arguments(self):
    return [self._callself]

  def get_parameter_names(self):
    return self.underlying.get_parameter_names()

  def get_static_path(self):
    return self.underlying.get_static_path()

  def to_type(self):
    return pytd.NamedType("function")


class Generator(AtomicAbstractValue):
  """A representation of instances of generators.

  (I.e., the return type of coroutines).
  """

  TYPE_PARAM = "T"  # See class generator in pytd/builtins/__builtin__.pytd

  def __init__(self, generator_frame, vm):
    super(Generator, self).__init__(vm)
    self.generator_frame = generator_frame
    self.retvar = None

  def _next(self, unused_value=None):
    # TODO(kramm): "send" value to generator:
    # self.generator_frame.push(value or self.vm.make_none())
    # Run the generator, by pushing its frame and running it:
    return self.vm.resume_frame(self.generator_frame)

  def get_attribute(self, name, valself=None, valcls=None):
    if name == "__iter__":
      f = NativeFunction(name, self.__iter__, self.vm)
      return f.to_variable(name)
    elif name in ["next", "__next__"]:
      return self.to_variable(name)

  def __iter__(self):
    return self.to_variable("__iter__")

  def get_yielded_type(self):
    if not self.retvar:
      try:
        self.retvar = self._next()
      except StopIteration:
        # Happens for iterators that return zero entries.
        log.info("Iterator raised StopIteration before first entry")
        self.retvar = Nothing(self.vm).to_variable("next()")
    return self.retvar

  def call(self, node, unused_func, args, kws):
    """Call this generator or (more common) its "next" attribute."""
    return node, self.get_yielded_type()

  def match_against_type(self, other_type, subst):
    if (isinstance(other_type, ParameterizedClass) and
        other_type.cls.name == "generator"):
      return match_var_against_type(self.get_yielded_type(),
                                    other_type.type_parameters[self.TYPE_PARAM],
                                    subst, self.vm.current_location)
    else:
      log.warn("Matching generator against wrong type (%r)", other_type)
      return None

  def to_type(self):
    return pytd.ClassType("generator")


class Nothing(AtomicAbstractValue):
  """The VM representation of Nothing values.

  These are fake values that never exist at runtime, but they appear if you, for
  example, extract a value from an empty list.
  """

  def get_attribute(self, name, valself=None, valcls=None):
    return None

  def has_attribute(self, name, valself=None, valcls=None):
    return False

  def set_attribute(self, name, value):
    raise AttributeError("Object %r has no attribute %s" % (self, name))

  def call(self, node, unused_func, args, kws):
    raise ValueError("Object %r is not callable", self)

  def to_type(self):
    return pytd.NothingType()

  def match_against_type(self, other_type, subst):
    raise NotImplementedError("Matching nothing against %r", other_type)


def to_type(v):
  if isinstance(v, typegraph.Variable):
    return pytd_utils.JoinTypes(to_type(t) for t in v.data)
  elif isinstance(v, Unknown):
    # Do this directly, and use NamedType, in case there's a circular dependency
    # among the Unknown instances.
    return pytd.NamedType(v.class_name)
  else:
    return v.to_type()


def make_params(args):
  """Convert a list of types/variables to pytd parameters."""
  return tuple(pytd.Parameter("_%d" % (i + 1), to_type(p))
               for i, p in enumerate(args))


class Module(LazyAbstractValue):
  """Represents an (imported) module."""

  def __init__(self, vm, name, member_map):
    super(Module, self).__init__(name, member_map, vm.convert_constant, vm=vm)

  def set_attribute(self, name, value):
    # Assigning attributes on modules is pretty common. E.g.
    # sys.path, sys.excepthook.
    log.warning("Ignoring overwrite of %s.%s", self.name, name)

  def items(self):
    # TODO(kramm): Test.
    return self._member_map.keys()

  def to_type(self):
    return pytd.NamedType("module")

  def match_against_type(self, other_type, subst):
    if other_type.name in ["module", "object"]:
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
    super(Unknown, self).__init__(vm)
    self.members = {}
    self.owner = None
    Unknown._current_id += 1
    self.class_name = "~unknown%d" % Unknown._current_id
    self.name = self.class_name
    self._calls = []
    # Remember the pytd class we created in to_pytd_class, to keep them unique:
    self._pytd_class = None
    log.info("Creating %s", self.class_name)

  def get_attribute(self, name, valself=None, valcls=None):
    if name in self.members:
      return self.members[name]
    new = self.vm.create_new_unknown(self.name + "." + name, source=self.owner)
    self.set_attribute(name, new)
    return new

  def get_attribute_flat(self, name):
    # Unknown objects don't have an MRO, so this is the same as get_attribute.
    return self.get_attribute(name)

  def has_attribute(self, name, valself=None, valcls=None):
    return name not in self.IGNORED_ATTRIBUTES

  def set_attribute(self, name, v):
    if name in self.members:
      variable = self.members[name]
      variable.AddValues(v, self.vm.current_location)
    else:
      self.members[name] = v.AssignToNewVariable(self.name + "." + name,
                                                 self.vm.current_location)

  def call(self, node, unused_func, args, kws):
    ret = self.vm.create_new_unknown(self.name + "()", source=self.owner)
    self._calls.append((args, kws, ret))
    return node, ret

  def to_variable(self, name=None):
    v = self.vm.program.NewVariable(self.name or name)
    val = v.AddValue(self, source_set=[], where=self.vm.current_location)
    self.owner = val
    self.vm.trace_unknown(v)
    return v

  def to_pytd_class(self):
    """Convert this Unknown to a pytd.Class."""
    if not self._pytd_class:
      self_param = (pytd.Parameter("self", pytd.NamedType("object")),)
      calls = tuple(pytd.Signature(params=self_param + make_params(args),
                                   return_type=to_type(ret),
                                   exceptions=(),
                                   template=(),
                                   has_optional=False)
                    for args, _, ret in self._calls)
      if calls:
        methods = (pytd.FunctionWithSignatures("__call__", calls),)
      else:
        methods = ()
      self._pytd_class = pytd.Class(
          name=self.class_name,
          parents=(),
          methods=methods,
          constants=tuple(pytd.Constant(name, to_type(c))
                          for name, c in self.members.items()),
          template=())
    return self._pytd_class

  def get_type(self):
    # We treat instances of an Unknown as the same as the class.
    return self.to_variable("class of " + self.name)

  def to_type(self):
    cls = self.to_pytd_class()
    t = pytd.ClassType(cls.name)  # pylint: disable=no-member
    t.cls = cls
    return t

  def match_against_type(self, other_type, subst):
    # TODO(kramm): Do we want to match the instance or the class?
    if isinstance(other_type, ParameterizedClass):
      return None
    return subst
