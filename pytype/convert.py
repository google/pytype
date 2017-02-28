"""Code for translating between type systems."""

import logging
import types


from pytype import abstract
from pytype import blocks
from pytype import output
from pytype import typing
from pytype import utils
from pytype.pyc import loadmarshal
from pytype.pytd import cfg
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils


log = logging.getLogger(__name__)


MAX_IMPORT_DEPTH = 12


class Converter(object):
  """Functions for creating the classes in abstract.py."""

  # Define this error inside Converter so that it is exposed to abstract.py
  class TypeParameterError(Exception):

    def __init__(self, type_param_name):
      super(Converter.TypeParameterError, self).__init__()
      self.type_param_name = type_param_name

  def __init__(self, vm):
    self.vm = vm
    self.vm.convert = self  # to make constant_to_var calls below work
    self.pytd_convert = output.Converter()

    self._convert_cache = {}

    # Initialize primitive_classes to empty to allow constant_to_var to run
    self.primitive_classes = ()
    # Now fill primitive_classes with the real values using constant_to_var
    self.primitive_classes = {v: self.constant_to_var(v.__name__, v)
                              for v in [int, float, str, unicode, object,
                                        types.NoneType, complex, bool, slice,
                                        types.CodeType, types.EllipsisType,
                                        types.ClassType, super]}

    self.none = abstract.AbstractOrConcreteValue(
        None, self.primitive_classes[types.NoneType], self.vm,
        self.vm.root_cfg_node)
    self.true = abstract.AbstractOrConcreteValue(
        True, self.primitive_classes[bool], self.vm, self.vm.root_cfg_node)
    self.false = abstract.AbstractOrConcreteValue(
        False, self.primitive_classes[bool], self.vm, self.vm.root_cfg_node)
    self.ellipsis = abstract.AbstractOrConcreteValue(
        Ellipsis, self.primitive_classes[types.EllipsisType], self.vm,
        self.vm.root_cfg_node)

    self.primitive_class_instances = {}
    for name, clsvar in self.primitive_classes.items():
      if name == types.NoneType:
        # This is possible because all None instances are the same.
        # Without it pytype could not reason that "x is None" is always true, if
        # x is indeed None.
        instance = self.none
      elif name == types.EllipsisType:
        instance = self.ellipsis
      else:
        instance = abstract.Instance(clsvar, self.vm, self.vm.root_cfg_node)
      self.primitive_class_instances[name] = instance
      clsval, = clsvar.bindings
      self._convert_cache[(abstract.Instance, clsval.data.pytd_cls)] = instance

    self.none_type = self.primitive_classes[types.NoneType]
    self.object_type = self.primitive_classes[object]
    self.oldstyleclass_type = self.primitive_classes[types.ClassType]
    self.super_type = self.primitive_classes[super]
    self.str_type = self.primitive_classes[str]
    self.int_type = self.primitive_classes[int]

    self.nothing = abstract.Nothing(self.vm)
    self.unsolvable = abstract.Unsolvable(self.vm)
    self.empty = abstract.Empty(self.vm)

    self.tuple_type = self.constant_to_var("tuple", tuple)
    self.list_type = self.constant_to_var("list", list)
    self.set_type = self.constant_to_var("set", set)
    self.frozenset_type = self.constant_to_var("frozenset", frozenset)
    self.dict_type = self.constant_to_var("dict", dict)
    self.type_type = self.constant_to_var("type", type)
    self.module_type = self.constant_to_var("module", types.ModuleType)
    self.function_type = self.constant_to_var("function", types.FunctionType)
    self.generator_type = self.constant_to_var("generator", types.GeneratorType)
    # TODO(dbaum): There isn't a types.IteratorType.  This can probably be
    # based on typing.Iterator, but that will also require changes to
    # convert.py since that assumes all types can be looked up in
    # __builtin__.
    self.iterator_type = self.constant_to_var("iterator", types.ObjectType)
    self.bool_values = {
        True: self.true,
        False: self.false,
        None: self.primitive_class_instances[bool],
    }
    self.empty_type = self.empty.to_variable(self.vm.root_cfg_node)
    object_val, = self.object_type.data
    object_val.load_lazy_attribute("__new__")
    self.object_new, = object_val.members["__new__"].data
    self.typing_overlay = typing.TypingOverlay(self.vm, self.vm.root_cfg_node)

  def value_to_constant(self, val, constant_type):
    if (isinstance(val, abstract.PythonConstant) and
        isinstance(val.pyval, constant_type or object)):
      return val.pyval
    name = "constant" if constant_type is None else constant_type.__name__
    raise abstract.ConversionError("%s is not a(n) %s" % (val, name))

  def name_to_value(self, name, subst=None, node=None):
    pytd_cls = self.vm.lookup_builtin(name)
    subst = subst or {}
    node = node or self.vm.root_cfg_node
    return self.constant_to_value(pytd_cls.name, pytd_cls, subst, node)

  def tuple_to_value(self, node, content):
    """Create a VM tuple from the given sequence."""
    content = tuple(content)  # content might be a generator
    value = abstract.Tuple(content, self.vm, node)
    return value

  def build_none(self, node):
    none = self.none.to_variable(node)
    assert self.vm.is_none(none)
    return none

  def build_bool(self, node, value=None):
    if value is None:
      return self.primitive_class_instances[bool].to_variable(node)
    elif value is True:
      return self.true.to_variable(node)
    elif value is False:
      return self.false.to_variable(node)
    else:
      raise ValueError("Invalid bool value: %r", value)

  def build_int(self, node):
    i = self.primitive_class_instances[int]
    return i.to_variable(node)

  def build_string(self, node, s):
    del node
    return self.constant_to_var(repr(s), s)

  def build_content(self, node, elements):
    if len(elements) == 1:
      return next(iter(elements))
    var = self.vm.program.NewVariable()
    for v in elements:
      var.PasteVariable(v, node)
    return var

  def build_slice(self, node, start, stop, step=None):
    del start
    del stop
    del step
    return self.primitive_class_instances[slice].to_variable(node)

  def build_list(self, node, content):
    """Create a VM list from the given sequence."""
    # TODO(rechen): set T to empty if there is nothing in content
    content = list(content)  # content might be a generator
    value = abstract.Instance(self.list_type, self.vm, node)
    value.initialize_type_parameter(node, abstract.T,
                                    self.build_content(node, content))
    return value.to_variable(node)

  def build_set(self, node, content):
    """Create a VM set from the given sequence."""
    content = list(content)  # content might be a generator
    value = abstract.Instance(self.set_type, self.vm, node)
    value.initialize_type_parameter(node, abstract.T,
                                    self.build_content(node, content))
    return value.to_variable(node)

  def build_map(self, node):
    """Create an empty VM dict."""
    return abstract.Dict(self.vm, node).to_variable(node)

  def build_tuple(self, node, content):
    """Create a VM tuple from the given sequence."""
    return self.tuple_to_value(node, content).to_variable(node)

  def _get_maybe_abstract_instance(self, data):
    """Get an instance of the same type as the given data, abstract if possible.

    Get an abstract instance of primitive data stored as an
    AbstractOrConcreteValue. Return any other data as-is. This is used by
    constant_to_var to discard concrete values that have been kept
    around for InterpreterFunction.

    Arguments:
      data: The data.

    Returns:
      An instance of the same type as the data, abstract if possible.
    """
    if isinstance(data, abstract.PythonConstant):
      data_type = type(data.pyval)
      if data_type in self.primitive_class_instances:
        return self.primitive_class_instances[data_type]
    return data

  def _create_new_unknown_value(self, action):
    if not self.vm.cache_unknowns or not action or not self.vm.frame:
      return abstract.Unknown(self.vm)
    # We allow only one Unknown at each point in the program, regardless of
    # what the call stack is.
    key = ("unknown", self.vm.frame.current_opcode, action)
    if key not in self._convert_cache:
      self._convert_cache[key] = abstract.Unknown(self.vm)
    return self._convert_cache[key]

  def create_new_unknown(self, node, source=None, action=None):
    """Create a new variable containing unknown."""
    if not self.vm.generate_unknowns:
      # unsolvable instances are cheaper than unknown, so use those for --quick.
      return self.unsolvable.to_variable(node)
    unknown = self._create_new_unknown_value(action)
    v = self.vm.program.NewVariable()
    val = v.AddBinding(
        unknown, source_set=[source] if source else [], where=node)
    unknown.owner = val
    self.vm.trace_unknown(unknown.class_name, v)
    return v

  def create_new_unsolvable(self, node):
    """Create a new variable containing an unsolvable."""
    return self.unsolvable.to_variable(node)

  def create_new_varargs_value(self, arg_type):
    """Create a varargs argument given its element type."""
    params = {abstract.T: arg_type}
    return abstract.ParameterizedClass(
        abstract.get_atomic_value(self.tuple_type), params, self.vm)

  def create_new_kwargs_value(self, arg_type):
    """Create a kwargs argument given its element type."""
    params = {abstract.K: abstract.get_atomic_value(self.str_type),
              abstract.V: arg_type}
    return abstract.ParameterizedClass(
        abstract.get_atomic_value(self.dict_type), params, self.vm)

  def optionalize(self, value):
    """Optionalize the value, if necessary."""
    assert isinstance(value, abstract.AtomicAbstractValue)
    none_type = self.vm.convert.none_type.bindings[0].data
    if isinstance(value, abstract.Union) and none_type in value.options:
      return value
    return abstract.Union((value, none_type), self.vm)

  def merge_classes(self, node, instances):
    """Merge the classes of the given instances.

    Args:
      node: The current node.
      instances: An iterable of instances.
    Returns:
      An abstract.AtomicAbstractValue created by merging the instances' classes.
    """
    classes = set()
    for v in instances:
      cls = v.get_class()
      if cls:
        classes.update(cls.Data(node))
    return abstract.merge_values(classes, self.vm)

  def constant_to_var(self, name, pyval, subst=None, node=None,
                      source_sets=None, discard_concrete_values=False):
    """Convert a constant to a Variable.

    This converts a constant to a cfg.Variable. Unlike constant_to_value, it
    can handle things that need to be represented as a Variable with multiple
    possible values (i.e., a union type), like pytd.Function.

    Args:
      name: The name to give the new variable.
      pyval: The Python constant to convert. Can be a PyTD definition or a
        builtin constant.
      subst: The current type parameters.
      node: The current CFG node. (For instances)
      source_sets: An iterator over instances of SourceSet (or just tuples).
      discard_concrete_values: Whether concrete values should be discarded from
        type parameters.
    Returns:
      A cfg.Variable.
    Raises:
      TypeParameterError: if conversion is attempted on a type parameter without
        a substitution.
      ValueError: if pytype is not of a known type.
    """
    source_sets = source_sets or [[]]
    node = node or self.vm.root_cfg_node
    if isinstance(pyval, pytd.UnionType):
      options = [self.constant_to_value(pytd.Print(t), t, subst, node)
                 for t in pyval.type_list]
      return self.vm.program.NewVariable(options, [], self.vm.root_cfg_node)
    elif isinstance(pyval, pytd.NothingType):
      return self.vm.program.NewVariable([], [], self.vm.root_cfg_node)
    elif isinstance(pyval, pytd.Alias):
      return self.constant_to_var(pytd.Print(pyval), pyval.type, subst,
                                  node, source_sets, discard_concrete_values)
    elif isinstance(pyval, abstract.AsInstance):
      cls = pyval.cls
      if isinstance(cls, pytd.AnythingType):
        return self.create_new_unsolvable(node)
      if hasattr(cls, "name"):
        name = cls.name
      else:
        name = cls.__class__.__name__
      var = self.vm.program.NewVariable()
      for t in pytd_utils.UnpackUnion(cls):
        if isinstance(t, pytd.TypeParameter):
          if not subst or t.name not in subst:
            raise self.TypeParameterError(t.name)
          else:
            for v in subst[t.name].bindings:
              for source_set in source_sets:
                var.AddBinding(self._get_maybe_abstract_instance(v.data)
                               if discard_concrete_values else v.data,
                               source_set + [v], node)
        elif isinstance(t, pytd.NothingType):
          pass
        else:
          value = self.constant_to_value(
              name, abstract.AsInstance(t), subst, node)
          for source_set in source_sets:
            var.AddBinding(value, source_set, node)
      return var
    elif isinstance(pyval, pytd.Constant):
      return self.constant_to_var(name, abstract.AsInstance(pyval.type), subst,
                                  node, source_sets, discard_concrete_values)
    result = self.constant_to_value(name, pyval, subst, node)
    if result is not None:
      return result.to_variable(self.vm.root_cfg_node)
    # There might still be bugs on the abstract intepreter when it returns,
    # e.g. a list of values instead of a list of types:
    assert pyval.__class__ != cfg.Variable, pyval
    if pyval.__class__ == tuple:
      # TODO(ampere): This does not allow subclasses. Handle namedtuple
      # correctly.
      # This case needs to go at the end because many things are actually also
      # tuples.
      return self.build_tuple(
          self.vm.root_cfg_node,
          (self.constant_to_var("tuple[%d]" % i, v, subst, node, source_sets,
                                discard_concrete_values)
           for i, v in enumerate(pyval)))
    raise ValueError(
        "Cannot convert {} to an abstract value".format(pyval.__class__))

  def constant_to_value(self, name, pyval, subst, node):
    """Like constant_to_var, but convert to an abstract.AtomicAbstractValue.

    This also memoizes the results.  We don't memoize on name, as builtin types
    like str or list might be reinitialized under different names (e.g. "param
    1"), but we want the canonical name and type.  We *do* memoize on the type
    as well, to make sure that e.g. "1.0" and "1" get converted to different
    constants.  Memoization is an optimization, but an important one - mapping
    constants like "None" to the same AbstractValue greatly simplifies the
    cfg structures we're building.

    Args:
      name: The name to give to the AtomicAbstractValue.
      pyval: The constant to convert.
      subst: The current type parameters.
      node: The current CFG node. (For instances)
    Returns:
      The converted constant. (Instance of AtomicAbstractValue)
    """
    key = ("constant", pyval, type(pyval))
    if key not in self._convert_cache:
      self._convert_cache[key] = None  # for recursion detection
      self._convert_cache[key] = self._constant_to_value(
          name, pyval, subst, node)
    elif self._convert_cache[key] is None:
      # This error is triggered by, e.g., classes inheriting from each other
      self.vm.errorlog.recursion_error(self.vm.frame.current_opcode, name)
      self._convert_cache[key] = self.unsolvable
    return self._convert_cache[key]

  def _constant_to_value(self, name, pyval, subst, node):
    """Create a AtomicAbstractValue that represents a python constant.

    This supports both constant from code constant pools and PyTD constants such
    as classes. This also supports builtin python objects such as int and float.

    Args:
      name: The name of this constant. Used for naming its attribute variables.
      pyval: The python or PyTD value to convert.
      subst: The current type parameters.
      node: The current CFG node.
    Returns:
      A Value that represents the constant, or None if we couldn't convert.
    Raises:
      NotImplementedError: If we don't know how to convert a value.
      TypeParameterError: If we can't find a substitution for a type parameter.
    """
    if isinstance(pyval, str):
      return abstract.AbstractOrConcreteValue(
          pyval, self.str_type, self.vm, node)
    elif isinstance(pyval, int) and -1 <= pyval <= MAX_IMPORT_DEPTH:
      # For small integers, preserve the actual value (for things like the
      # level in IMPORT_NAME).
      return abstract.AbstractOrConcreteValue(
          pyval, self.int_type, self.vm, node)
    elif isinstance(pyval, long):
      # long is aliased to int
      return self.primitive_class_instances[int]
    elif pyval.__class__ in self.primitive_classes:
      return self.primitive_class_instances[pyval.__class__]
    elif isinstance(pyval, (loadmarshal.CodeType, blocks.OrderedCode)):
      return abstract.AbstractOrConcreteValue(
          pyval, self.primitive_classes[types.CodeType], self.vm, node)
    elif (pyval.__class__ in [types.FunctionType,
                              types.ModuleType,
                              types.GeneratorType,
                              type] or pyval is type):
      if pyval is types.FunctionType:
        classname = "typing.Callable"
      else:
        classname = "__builtin__." + pyval.__name__
      try:
        return self.name_to_value(classname, subst, node)
      except (KeyError, AttributeError):
        log.debug("Failed to find pytd", exc_info=True)
        raise
    elif isinstance(pyval, pytd.TypeDeclUnit):
      data = (pyval.constants + pyval.type_params + pyval.classes +
              pyval.functions + pyval.aliases)
      members = {val.name.rsplit(".")[-1]: val
                 for val in data}
      return abstract.Module(self.vm, node, pyval.name, members)
    elif isinstance(pyval, pytd.Class):
      module, dot, base_name = pyval.name.rpartition(".")
      try:
        cls = abstract.PyTDClass(base_name, pyval, self.vm)
      except pytd_utils.MROError as e:
        self.vm.errorlog.mro_error(
            self.vm.frame.current_opcode, base_name, e.mro_seqs)
        cls = self.unsolvable
      else:
        if dot:
          cls.module = module
      return cls
    elif isinstance(pyval, pytd.Function):
      signatures = [abstract.PyTDSignature(pyval.name, sig, self.vm)
                    for sig in pyval.signatures]
      type_new = self.vm.lookup_builtin("__builtin__.type").Lookup("__new__")
      if pyval is type_new:
        f_cls = abstract.TypeNew
      else:
        f_cls = abstract.PyTDFunction
      f = f_cls(pyval.name, signatures, pyval.kind, self.vm)
      return f
    elif isinstance(pyval, pytd.ClassType):
      assert pyval.cls
      return self.constant_to_value(pyval.name, pyval.cls, subst, node)
    elif isinstance(pyval, pytd.NothingType):
      return self.nothing
    elif isinstance(pyval, pytd.AnythingType):
      return self.unsolvable
    elif isinstance(pyval, pytd.FunctionType):
      return self._constant_to_value(name, pyval.function, subst, node)
    elif isinstance(pyval, pytd.UnionType):
      options = [self.constant_to_value(pytd.Print(t), t, subst, node)
                 for t in pyval.type_list]
      if len(options) > 1:
        return abstract.Union(options, self.vm)
      else:
        return options[0]
    elif isinstance(pyval, pytd.TypeParameter):
      return abstract.TypeParameter(pyval.name, self.vm)
    elif isinstance(pyval, abstract.AsInstance):
      cls = pyval.cls
      if isinstance(cls, pytd.ClassType):
        cls = cls.cls
      if isinstance(cls, pytd.Class):
        # This key is also used in __init__
        key = (abstract.Instance, cls)
        if key not in self._convert_cache:
          if cls.name in ["__builtin__.type", "__builtin__.property"]:
            # An instance of "type" or of an anonymous property can be anything.
            instance = self._create_new_unknown_value("type")
          else:
            mycls = self.constant_to_var(cls.name, cls, subst, node)
            instance = abstract.Instance(mycls, self.vm, node)
            instance.make_template_unsolvable(cls.template, node)
          log.info("New pytd instance for %s: %r", cls.name, instance)
          self._convert_cache[key] = instance
        return self._convert_cache[key]
      elif isinstance(cls, pytd.GenericType):
        assert isinstance(cls.base_type, pytd.ClassType)
        base_cls = cls.base_type.cls
        if base_cls.name == "__builtin__.type":
          c, = cls.parameters
          if isinstance(c, pytd.TypeParameter):
            if not subst or c.name not in subst:
              raise self.TypeParameterError(c.name)
            return self.merge_classes(node, subst[c.name].data)
          else:
            return self.constant_to_value(pytd.Print(c), c, subst, node)
        elif isinstance(cls, pytd.TupleType):
          content = tuple(self.constant_to_var(pytd.Print(p),
                                               abstract.AsInstance(p),
                                               subst, node)
                          for p in cls.parameters)
          return abstract.Tuple(content, self.vm, node)
        else:
          instance = abstract.Instance(
              self.constant_to_var(base_cls.name, base_cls, subst, node),
              self.vm, node)
          assert len(cls.parameters) <= len(base_cls.template)
          for formal, actual in zip(base_cls.template, cls.parameters):
            p = self.constant_to_var(
                repr(formal), abstract.AsInstance(actual), subst, node)
            instance.initialize_type_parameter(node, formal.name, p)
          return instance
      else:
        return self.constant_to_value(name, cls, subst, node)
    elif isinstance(pyval, pytd.GenericType):
      assert isinstance(pyval.base_type, pytd.ClassType)
      if isinstance(pyval, pytd.TupleType):
        abstract_class = abstract.TupleClass
        template = range(len(pyval.parameters)) + [abstract.T]
        parameters = pyval.parameters + (pytd.UnionType(pyval.parameters),)
      else:
        abstract_class = abstract.ParameterizedClass
        template = tuple(t.name for t in pyval.base_type.cls.template)
        parameters = pyval.parameters
      assert (pyval.base_type.name == "typing.Generic" or
              len(parameters) <= len(template))
      type_parameters = utils.LazyDict()
      for i, name in enumerate(template):
        if i < len(parameters):
          type_parameters.add_lazy_item(name, self.constant_to_value, name,
                                        parameters[i], subst, node)
        else:
          type_parameters[name] = self.unsolvable
      base_cls = self.constant_to_value(
          pytd.Print(pyval.base_type), pyval.base_type.cls, subst, node)
      cls = abstract_class(base_cls, type_parameters, self.vm)
      return cls
    elif pyval.__class__ is tuple:  # only match raw tuple, not namedtuple/Node
      return self.tuple_to_value(self.vm.root_cfg_node,
                                 [self.constant_to_var("tuple[%d]" % i, item,
                                                       subst, node)
                                  for i, item in enumerate(pyval)])
    else:
      raise NotImplementedError("Can't convert constant %s %r" %
                                (type(pyval), pyval))
