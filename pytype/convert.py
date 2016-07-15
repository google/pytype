"""Code for translating between type systems."""

import logging
import types


from pytype import abstract
from pytype import blocks
from pytype.pyc import loadmarshal
from pytype.pytd import cfg as typegraph
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils


log = logging.getLogger(__name__)


MAX_IMPORT_DEPTH = 12


class ConversionError(Exception):
  """For when a type conversion failed."""
  pass


class Converter(object):
  """Functions for creating the classes in abstract.py."""

  def __init__(self, vm):
    self.vm = vm
    self.vm.convert = self  # to make convert_constant calls below work

    self._convert_cache = {}

    # Initialize primitive_classes to empty to allow convert_constant to run
    self.primitive_classes = {}
    # Now fill primitive_classes with the real values using convert_constant
    self.primitive_classes = {v: self.convert_constant(v.__name__, v)
                              for v in [int, long, float, str, unicode, object,
                                        types.NoneType, complex, bool, slice,
                                        types.CodeType, types.EllipsisType,
                                        types.ClassType]}

    self.none = abstract.AbstractOrConcreteValue(
        None, self.primitive_classes[types.NoneType], self.vm)
    self.true = abstract.AbstractOrConcreteValue(
        True, self.primitive_classes[bool], self.vm)
    self.false = abstract.AbstractOrConcreteValue(
        False, self.primitive_classes[bool], self.vm)
    self.ellipsis = abstract.AbstractOrConcreteValue(
        Ellipsis, self.primitive_classes[types.EllipsisType], self.vm)

    self.nothing = abstract.Nothing(self.vm)
    self.unsolvable = abstract.Unsolvable(self.vm)

    self.primitive_class_instances = {}
    for name, clsvar in self.primitive_classes.items():
      instance = abstract.Instance(clsvar, self.vm)
      self.primitive_class_instances[name] = instance
      clsval, = clsvar.bindings
      self._convert_cache[(abstract.Instance, clsval.data.pytd_cls)] = instance
    self.primitive_class_instances[types.NoneType] = self.none

    self.object_type = self.primitive_classes[object]
    self.oldstyleclass_type = self.primitive_classes[types.ClassType]
    self.str_type = self.primitive_classes[str]
    self.int_type = self.primitive_classes[int]
    self.tuple_type = self.convert_constant("tuple", tuple)
    self.list_type = self.convert_constant("list", list)
    self.set_type = self.convert_constant("set", set)
    self.dict_type = self.convert_constant("dict", dict)
    self.type_type = self.convert_constant("type", type)
    self.module_type = self.convert_constant("module", types.ModuleType)
    self.function_type = self.convert_constant(
        "function", types.FunctionType)
    self.generator_type = self.convert_constant(
        "generator", types.GeneratorType)

    self.undefined = self.vm.program.NewVariable("undefined")

  def convert_value_to_string(self, val):
    if isinstance(val, abstract.PythonConstant) and isinstance(val.pyval, str):
      return val.pyval
    raise abstract.ConversionError("%s is not a string" % val)

  def tuple_to_value(self, node, content):
    """Create a VM tuple from the given sequence."""
    content = tuple(content)  # content might be a generator
    value = abstract.AbstractOrConcreteValue(
        content, self.tuple_type, self.vm)
    value.initialize_type_parameter(node, "T",
                                    self.build_content(node, content))
    return value

  def make_none(self, node):
    none = self.none.to_variable(node, "None")
    assert self.vm.is_none(none)
    return none

  def build_bool(self, node, value=None):
    if value is None:
      name, val = "bool", self.primitive_class_instances[bool]
    elif value is True:
      name, val = "True", self.true_value
    elif value is False:
      name, val = "False", self.false_value
    else:
      raise ValueError("Invalid bool value: %r", value)
    return val.to_variable(node, name)

  def build_string(self, node, s):
    del node
    return self.convert_constant(repr(s), s)

  def build_content(self, node, elements):
    var = self.vm.program.NewVariable("<elements>")
    for v in elements:
      var.PasteVariable(v, node)
    return var

  def build_slice(self, node, start, stop, step=None):
    del start
    del stop
    del step
    return self.primitive_class_instances[slice].to_variable(node, "slice")

  def build_list(self, node, content):
    """Create a VM list from the given sequence."""
    content = list(content)  # content might be a generator
    value = abstract.Instance(self.list_type, self.vm)
    value.initialize_type_parameter(node, "T",
                                    self.build_content(node, content))
    return value.to_variable(node, name="list(...)")

  def build_set(self, node, content):
    """Create a VM set from the given sequence."""
    content = list(content)  # content might be a generator
    value = abstract.Instance(self.set_type, self.vm)
    value.initialize_type_parameter(node, "T",
                                    self.build_content(node, content))
    return value.to_variable(node, name="set(...)")

  def build_map(self, node):
    """Create an empty VM dict."""
    return abstract.Dict("dict()", self.vm).to_variable(node, "dict()")

  def build_tuple(self, node, content):
    """Create a VM tuple from the given sequence."""
    return self.tuple_to_value(node, content).to_variable(node, name="tuple")

  def _get_maybe_abstract_instance(self, data):
    """Get an instance of the same type as the given data, abstract if possible.

    Get an abstract instance of primitive data stored as an
    AbstractOrConcreteValue. Return any other data as-is. This is used by
    create_pytd_instance to discard concrete values that have been kept
    around for InterpreterFunction.

    Arguments:
      data: The data.

    Returns:
      An instance of the same type as the data, abstract if possible.
    """
    if isinstance(data, abstract.AbstractOrConcreteValue):
      data_type = type(data.pyval)
      if data_type in self.primitive_class_instances:
        return self.primitive_class_instances[data_type]
    return data

  def create_pytd_instance(self, name, pytype, subst, node, source_sets=None,
                           discard_concrete_values=False):
    """Create an instance of a PyTD type as a typegraph.Variable.

    Because this (unlike create_pytd_instance_value) creates variables, it can
    also handle union types.

    Args:
      name: What to call the resulting variable.
      pytype: A PyTD type to construct an instance of.
      subst: The current type parameters.
      node: The current CFG node.
      source_sets: An iterator over instances of SourceSet (or just tuples).
        Each SourceSet describes a combination of values that were used to
        build the new value (e.g., for a function call, parameter types).
      discard_concrete_values: Whether concrete values should be discarded from
        type parameters.
    Returns:
      A typegraph.Variable.
    Raises:
      ValueError: If we can't resolve a type parameter.
    """
    if not source_sets:
      source_sets = [[]]
    if isinstance(pytype, pytd.AnythingType):
      return self.create_new_unsolvable(node, "?")
    name = pytype.name if hasattr(pytype, "name") else pytype.__class__.__name__
    var = self.vm.program.NewVariable(name)
    for t in pytd_utils.UnpackUnion(pytype):
      if isinstance(t, pytd.TypeParameter):
        if not subst or t.name not in subst:
          raise ValueError("Can't resolve type parameter %s using %r" % (
              t.name, subst))
        for v in subst[t.name].bindings:
          for source_set in source_sets:
            var.AddBinding(self._get_maybe_abstract_instance(v.data)
                           if discard_concrete_values else v.data,
                           source_set + [v], node)
      elif isinstance(t, pytd.NothingType):
        pass
      else:
        value = self._create_pytd_instance_value(name, t, subst, node)
        for source_set in source_sets:
          var.AddBinding(value, source_set, node)
    return var

  def _create_pytd_instance_value(self, name, pytype, subst, node):
    """Create an instance of PyTD type.

    This can handle any PyTD type and is used for generating both methods of
    classes (when given a Signature) and instance of classes (when given a
    ClassType).

    Args:
      name: What to call the value.
      pytype: A PyTD type to construct an instance of.
      subst: The current type parameters.
      node: The current CFG node.
    Returns:
      An instance of AtomicAbstractType.
    Raises:
      ValueError: if pytype is not of a known type.
    """
    if isinstance(pytype, pytd.ClassType):
      # This key is also used in __init__
      key = (abstract.Instance, pytype.cls)
      if key not in self._convert_cache:
        if pytype.name in ["__builtin__.type", "__builtin__.property"]:
          # An instance of "type" or of an anonymous property can be anything.
          instance = self._create_new_unknown_value("type")
        else:
          cls = self.convert_constant(str(pytype), pytype)
          instance = abstract.Instance(cls, self.vm)
        log.info("New pytd instance for %s: %r", pytype.cls.name, instance)
        self._convert_cache[key] = instance
      return self._convert_cache[key]
    elif isinstance(pytype, pytd.GenericType):
      assert isinstance(pytype.base_type, pytd.ClassType)
      cls = pytype.base_type.cls
      instance = abstract.Instance(
          self.convert_constant(cls.name, cls), self.vm)
      for formal, actual in zip(cls.template, pytype.parameters):
        p = self.create_pytd_instance(repr(formal), actual, subst, node)
        instance.initialize_type_parameter(node, formal.name, p)
      return instance
    else:
      return self.convert_constant_to_value(name, pytype)

  def _create_new_unknown_value(self, action):
    if not self.vm.cache_unknowns or not action or not self.vm.frame:
      return abstract.Unknown(self.vm)
    # We allow only one Unknown at each point in the program, regardless of
    # what the call stack is.
    key = ("unknown", self.vm.frame.current_opcode, action)
    if key not in self._convert_cache:
      self._convert_cache[key] = abstract.Unknown(self.vm)
    return self._convert_cache[key]

  def create_new_unknown(self, node, name, source=None, action=None):
    """Create a new variable containing unknown, originating from this one."""
    if self.vm.options.quick:
      # unsolvable instances are cheaper than unknown, so use those for --quick.
      return abstract.Unsolvable(self.vm).to_variable(node, name)
    unknown = self._create_new_unknown_value(action)
    v = self.vm.program.NewVariable(name)
    val = v.AddBinding(
        unknown, source_set=[source] if source else [], where=node)
    unknown.owner = val
    self.vm.trace_unknown(unknown.class_name, v)
    return v

  def create_new_unsolvable(self, node, name):
    """Create a new variable containing an unsolvable."""
    return self.unsolvable.to_variable(node, name)

  def convert_constant(self, name, pyval):
    """Convert a constant to a Variable.

    This converts a constant to a typegraph.Variable. Unlike
    convert_constant_to_value, it can handle things that need to be represented
    as a Variable with multiple possible values (i.e., a union type), like
    pytd.Function.

    Args:
      name: The name to give the new variable.
      pyval: The Python constant to convert. Can be a PyTD definition or a
      builtin constant.
    Returns:
      A typegraph.Variable.
    Raises:
      ValueError: if pytype is not of a known type.
    """
    if isinstance(pyval, pytd.UnionType):
      options = [self.convert_constant_to_value(pytd.Print(t), t)
                 for t in pyval.type_list]
      return self.vm.program.NewVariable(name, options, [],
                                         self.vm.root_cfg_node)
    elif isinstance(pyval, pytd.NothingType):
      return self.vm.program.NewVariable(name, [], [], self.vm.root_cfg_node)
    elif isinstance(pyval, pytd.Alias):
      return self.convert_constant(pytd.Print(pyval), pyval.type)
    elif isinstance(pyval, pytd.Constant):
      return self.create_pytd_instance(name, pyval.type, {},
                                       self.vm.root_cfg_node)
    result = self.convert_constant_to_value(name, pyval)
    if result is not None:
      return result.to_variable(self.vm.root_cfg_node, name)
    # There might still be bugs on the abstract intepreter when it returns,
    # e.g. a list of values instead of a list of types:
    assert pyval.__class__ != typegraph.Variable, pyval
    if pyval.__class__ == tuple:
      # TODO(ampere): This does not allow subclasses. Handle namedtuple
      # correctly.
      # This case needs to go at the end because many things are actually also
      # tuples.
      return self.build_tuple(
          self.vm.root_cfg_node,
          (self.maybe_convert_constant("tuple[%d]" % i, v)
           for i, v in enumerate(pyval)))
    raise ValueError(
        "Cannot convert {} to an abstract value".format(pyval.__class__))

  def convert_constant_to_value(self, name, pyval):
    # We don't memoize on name, as builtin types like str or list might be
    # reinitialized under different names (e.g. "param 1"), but we want the
    # canonical name and type.
    # We *do* memoize on the type as well, to make sure that e.g. "1.0" and
    # "1" get converted to different constants.
    # Memoization is an optimization, but an important one- mapping constants
    # like "None" to the same AbstractValue greatly simplifies the typegraph
    # structures we're building.
    key = ("constant", pyval, type(pyval))
    if key not in self._convert_cache:
      self._convert_cache[key] = None  # for recursion detection
      self._convert_cache[key] = self.construct_constant_from_value(name, pyval)
    elif self._convert_cache[key] is None:
      # This error is triggered by, e.g., classes inheriting from each other
      raise ConversionError(
          "Detected recursion while converting %s to value" % name)
    return self._convert_cache[key]

  def construct_constant_from_value(self, name, pyval):
    """Create a AtomicAbstractValue that represents a python constant.

    This supports both constant from code constant pools and PyTD constants such
    as classes. This also supports built-in python objects such as int and
    float.

    Args:
      name: The name of this constant. Used for naming its attribute variables.
      pyval: The python or PyTD value to convert.
    Returns:
      A Value that represents the constant, or None if we couldn't convert.
    Raises:
      NotImplementedError: If we don't know how to convert a value.
    """
    if pyval is type:
      return abstract.SimpleAbstractValue(name, self.vm)
    elif isinstance(pyval, str):
      return abstract.AbstractOrConcreteValue(pyval, self.str_type, self.vm)
    elif isinstance(pyval, int) and -1 <= pyval <= MAX_IMPORT_DEPTH:
      # For small integers, preserve the actual value (for things like the
      # level in IMPORT_NAME).
      return abstract.AbstractOrConcreteValue(pyval, self.int_type, self.vm)
    elif pyval.__class__ in self.primitive_classes:
      return self.primitive_class_instances[pyval.__class__]
    elif isinstance(pyval, (loadmarshal.CodeType, blocks.OrderedCode)):
      return abstract.AbstractOrConcreteValue(
          pyval, self.primitive_classes[types.CodeType], self.vm)
    elif pyval.__class__ in [types.FunctionType,
                             types.ModuleType,
                             types.GeneratorType,
                             type]:
      try:
        pyclass = self.vm.vmbuiltins.Lookup("__builtin__." + pyval.__name__)
        return self.convert_constant_to_value(name, pyclass)
      except (KeyError, AttributeError):
        log.debug("Failed to find pytd", exc_info=True)
        raise
    elif isinstance(pyval, pytd.TypeDeclUnit):
      data = pyval.constants + pyval.classes + pyval.functions + pyval.aliases
      members = {val.name.rsplit(".")[-1]: val
                 for val in data}
      return abstract.Module(self.vm, pyval.name, members)
    elif isinstance(pyval, pytd.Class):
      if "." in pyval.name:
        module, base_name = pyval.name.rsplit(".", 1)
        cls = abstract.PyTDClass(base_name, pyval, self.vm)
        cls.module = module
      else:
        cls = abstract.PyTDClass(name, pyval, self.vm)
      return cls
    elif isinstance(pyval, pytd.Function):
      signatures = [abstract.PyTDSignature(pyval.name, sig, self.vm)
                    for sig in pyval.signatures]
      f = abstract.PyTDFunction(pyval.name, signatures, pyval.kind, self.vm)
      return f
    elif isinstance(pyval, pytd.ClassType):
      assert pyval.cls
      return self.convert_constant_to_value(pyval.name, pyval.cls)
    elif isinstance(pyval, pytd.NothingType):
      return self.nothing
    elif isinstance(pyval, pytd.AnythingType):
      # TODO(kramm): This should be an Unsolveable. We don't need to solve this.
      return self._create_new_unknown_value("AnythingType")
    elif isinstance(pyval, pytd.FunctionType):
      return self.construct_constant_from_value(name, pyval.function)
    elif isinstance(pyval, pytd.UnionType):
      return abstract.Union([self.convert_constant_to_value(pytd.Print(t), t)
                             for t in pyval.type_list], self.vm)
    elif isinstance(pyval, pytd.TypeParameter):
      return abstract.TypeParameter(pyval.name, self.vm)
    elif isinstance(pyval, pytd.GenericType):
      # TODO(kramm): Remove ParameterizedClass. This should just create a
      # SimpleAbstractValue with type parameters.
      assert isinstance(pyval.base_type, pytd.ClassType)
      type_parameters = {
          param.name: self.convert_constant_to_value(param.name, value)
          for param, value in zip(pyval.base_type.cls.template,
                                  pyval.parameters)
      }
      cls = self.convert_constant_to_value(pytd.Print(pyval.base_type),
                                           pyval.base_type.cls)
      return abstract.ParameterizedClass(cls, type_parameters, self.vm)
    elif pyval.__class__ is tuple:  # only match raw tuple, not namedtuple/Node
      return self.tuple_to_value(self.vm.root_cfg_node,
                                 [self.convert_constant("tuple[%d]" % i, item)
                                  for i, item in enumerate(pyval)])
    else:
      raise NotImplementedError("Can't convert constant %s %r" %
                                (type(pyval), pyval))

  def maybe_convert_constant(self, name, pyval):
    """Create a variable that represents a python constant if needed.

    Call self.convert_constant if pyval is not an AtomicAbstractValue, otherwise
    store said value in a variable. This also handles dict values by
    constructing a new abstract value representing it. Dict values are not
    cached.

    Args:
      name: The name to give to the variable.
      pyval: The python value or PyTD value to convert or pass
        through.
    Returns:
      A Variable.
    """
    assert not isinstance(pyval, typegraph.Variable)
    if isinstance(pyval, abstract.AtomicAbstractValue):
      return pyval.to_variable(self.vm.root_cfg_node, name)
    else:
      return self.convert_constant(name, pyval)

