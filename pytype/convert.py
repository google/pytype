"""Code for translating between type systems."""

import logging
import types

from pytype import abstract
from pytype import abstract_utils
from pytype import blocks
from pytype import compat
from pytype import datatypes
from pytype import function
from pytype import mixin
from pytype import output
from pytype import special_builtins
from pytype import utils
from pytype.overlays import typing_overlay
from pytype.pyc import loadmarshal
from pytype.pytd import mro
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.typegraph import cfg


log = logging.getLogger(__name__)


MAX_IMPORT_DEPTH = 12


class Converter(utils.VirtualMachineWeakrefMixin):
  """Functions for creating the classes in abstract.py."""

  # Define this error inside Converter so that it is exposed to abstract.py
  class TypeParameterError(Exception):

    def __init__(self, type_param_name):
      super(Converter.TypeParameterError, self).__init__(type_param_name)
      self.type_param_name = type_param_name

  def __init__(self, vm):
    super(Converter, self).__init__(vm)
    self.vm.convert = self  # to make constant_to_value calls below work
    self.pytd_convert = output.Converter(vm)

    self._convert_cache = {}
    self._resolved_late_types = {}  # performance cache

    # Initialize primitive_classes to empty to allow constant_to_value to run.
    self.primitive_classes = ()

    # object_type is needed to initialize the primitive class values.
    self.object_type = self.constant_to_value(object)

    if self.vm.PY2:
      version_specific = [compat.UnicodeType]
    else:
      version_specific = [compat.BytesType]

    self.unsolvable = abstract.Unsolvable(self.vm)
    self.empty = abstract.Empty(self.vm)
    self.no_return = typing_overlay.NoReturn(self.vm)

    # Now fill primitive_classes with the real values using constant_to_value.
    primitive_classes = [
        int, float, str, object, frozenset, compat.NoneType, complex, bool,
        slice, types.CodeType, compat.EllipsisType, compat.OldStyleClassType,
        super
    ] + version_specific
    self.primitive_classes = {
        v: self.constant_to_value(v) for v in primitive_classes
    }
    self.primitive_class_names = [
        self._type_to_name(x) for x in self.primitive_classes]
    self.none = abstract.AbstractOrConcreteValue(
        None, self.primitive_classes[compat.NoneType], self.vm)
    self.true = abstract.AbstractOrConcreteValue(
        True, self.primitive_classes[bool], self.vm)
    self.false = abstract.AbstractOrConcreteValue(
        False, self.primitive_classes[bool], self.vm)
    self.ellipsis = abstract.AbstractOrConcreteValue(
        Ellipsis, self.primitive_classes[compat.EllipsisType], self.vm)

    self.primitive_class_instances = {}
    for name, cls in self.primitive_classes.items():
      if name == compat.NoneType:
        # This is possible because all None instances are the same.
        # Without it pytype could not reason that "x is None" is always true, if
        # x is indeed None.
        instance = self.none
      elif name == compat.EllipsisType:
        instance = self.ellipsis
      else:
        instance = abstract.Instance(cls, self.vm)
      self.primitive_class_instances[name] = instance
      self._convert_cache[(abstract.Instance, cls.pytd_cls)] = instance

    self.none_type = self.primitive_classes[compat.NoneType]
    self.oldstyleclass_type = self.primitive_classes[compat.OldStyleClassType]
    self.super_type = self.primitive_classes[super]
    self.str_type = self.primitive_classes[str]
    self.int_type = self.primitive_classes[int]

    self.list_type = self.constant_to_value(list)
    self.set_type = self.constant_to_value(set)
    self.frozenset_type = self.constant_to_value(frozenset)
    self.dict_type = self.constant_to_value(dict)
    self.type_type = self.constant_to_value(type)
    self.module_type = self.constant_to_value(types.ModuleType)
    self.function_type = self.constant_to_value(types.FunctionType)
    self.tuple_type = self.constant_to_value(tuple)
    self.generator_type = self.constant_to_value(types.GeneratorType)
    self.iterator_type = self.constant_to_value(compat.IteratorType)
    # TODO(ahxun): We should clean up/standardize how we initialize
    # version-specific attributes.
    if self.vm.python_version >= (3, 5):
      self.coroutine_type = self.constant_to_value(compat.CoroutineType)
      self.awaitable_type = self.constant_to_value(compat.AwaitableType)
    if self.vm.python_version >= (3, 6):
      self.async_generator_type = self.constant_to_value(
          compat.AsyncGeneratorType)
    self.bool_values = {
        True: self.true,
        False: self.false,
        None: self.primitive_class_instances[bool],
    }
    if self.vm.PY2:
      self.unicode_type = self.primitive_classes[compat.UnicodeType]
      self.bytes_type = self.str_type
      self.next_attr = "next"
    else:
      self.unicode_type = self.str_type
      self.bytes_type = self.primitive_classes[compat.BytesType]
      self.next_attr = "__next__"

  def constant_name(self, constant_type):
    if constant_type is None:
      return "constant"
    elif isinstance(constant_type, tuple):
      return "(%s)" % ", ".join(self.constant_name(c) for c in constant_type)
    else:
      return constant_type.__name__

  def _type_to_name(self, t):
    """Convert a type to its name."""
    assert t.__class__ is type
    # TODO(rechen): We should use the target version-specific name of the
    # builtins module rather than hard-coding __builtin__.
    if t is types.FunctionType:
      return "typing.Callable"
    elif t is compat.BytesType:
      return "__builtin__.bytes"
    elif t is compat.UnicodeType:
      if self.vm.PY2:
        return "__builtin__.unicode"
      else:
        return "__builtin__.str"
    elif t is compat.OldStyleClassType:
      return "__builtin__.classobj"
    elif t is compat.IteratorType:
      return "__builtin__.object"
    elif t is compat.CoroutineType:
      return "__builtin__.coroutine"
    elif t is compat.AwaitableType:
      return "typing.Awaitable"
    elif t is compat.AsyncGeneratorType:
      return "__builtin__.asyncgenerator"
    else:
      return "__builtin__." + t.__name__

  def value_to_constant(self, val, constant_type):
    if (isinstance(val, mixin.PythonConstant) and
        isinstance(val.pyval, constant_type or object) and
        not getattr(val, "could_contain_anything", False)):
      return val.pyval
    name = self.constant_name(constant_type)
    raise abstract_utils.ConversionError("%s is not of type %s" % (val, name))

  def name_to_value(self, name, subst=None, ast=None):
    if ast is None:
      pytd_cls = self.vm.lookup_builtin(name)
    else:
      pytd_cls = ast.Lookup(name)
    subst = subst or datatypes.AliasingDict()
    return self.constant_to_value(pytd_cls, subst, self.vm.root_cfg_node)

  def tuple_to_value(self, content):
    """Create a VM tuple from the given sequence."""
    content = tuple(content)  # content might be a generator
    value = abstract.Tuple(content, self.vm)
    return value

  def build_none(self, node):
    return self.none.to_variable(node)

  def build_bool(self, node, value=None):
    # pylint: disable=g-bool-id-comparison
    if value is None:
      return self.primitive_class_instances[bool].to_variable(node)
    elif value is True:
      return self.true.to_variable(node)
    elif value is False:
      return self.false.to_variable(node)
    else:
      raise ValueError("Invalid bool value: %r" % value)

  def build_int(self, node):
    i = self.primitive_class_instances[int]
    return i.to_variable(node)

  def build_string(self, node, s):
    del node
    return self.constant_to_var(s)

  def build_content(self, elements):
    if len(elements) == 1:
      return next(iter(elements))
    var = self.vm.program.NewVariable()
    for v in elements:
      var.PasteVariable(v)
    return var

  def build_slice(self, node, start, stop, step=None):
    del start
    del stop
    del step
    return self.primitive_class_instances[slice].to_variable(node)

  def build_list(self, node, content):
    """Create a VM list from the given sequence."""
    # TODO(rechen): set T to empty if there is nothing in content
    content = [var.AssignToNewVariable(node) for var in content]
    return abstract.List(content, self.vm).to_variable(node)

  def build_list_of_type(self, node, var):
    """Create a VM list with element type derived from the given variable."""
    ret = abstract.Instance(self.list_type, self.vm)
    ret.merge_instance_type_parameter(node, abstract_utils.T, var)
    return ret.to_variable(node)

  def build_set(self, node, content):
    """Create a VM set from the given sequence."""
    content = list(content)  # content might be a generator
    value = abstract.Instance(self.set_type, self.vm)
    value.merge_instance_type_parameter(
        node, abstract_utils.T, self.build_content(content))
    return value.to_variable(node)

  def build_map(self, node):
    """Create an empty VM dict."""
    return abstract.Dict(self.vm).to_variable(node)

  def build_tuple(self, node, content):
    """Create a VM tuple from the given sequence."""
    return self.tuple_to_value(content).to_variable(node)

  def get_maybe_abstract_instance(self, data):
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
    if isinstance(data, mixin.PythonConstant):
      data_type = type(data.pyval)
      if data_type in self.primitive_class_instances:
        return self.primitive_class_instances[data_type]
    return data

  def _create_new_unknown_value(self, action):
    if not action or not self.vm.frame:
      return abstract.Unknown(self.vm)
    # We allow only one Unknown at each point in the program, regardless of
    # what the call stack is.
    key = ("unknown", self.vm.frame.current_opcode, action)
    if key not in self._convert_cache:
      self._convert_cache[key] = abstract.Unknown(self.vm)
    return self._convert_cache[key]

  def create_new_unknown(self, node, source=None, action=None, force=False):
    """Create a new variable containing unknown."""
    if not force and not self.vm.generate_unknowns:
      # unsolvable instances are cheaper than unknown, so use those for --quick.
      return self.unsolvable.to_variable(node)
    unknown = self._create_new_unknown_value(action)
    v = self.vm.program.NewVariable()
    val = v.AddBinding(
        unknown, source_set=[source] if source else [], where=node)
    unknown.owner = val
    self.vm.trace_unknown(unknown.class_name, val)
    return v

  def create_new_varargs_value(self, arg_type):
    """Create a varargs argument given its element type."""
    params = {abstract_utils.T: arg_type}
    return abstract.ParameterizedClass(self.tuple_type, params, self.vm)

  def create_new_kwargs_value(self, arg_type):
    """Create a kwargs argument given its element type."""
    params = {abstract_utils.K: self.str_type, abstract_utils.V: arg_type}
    return abstract.ParameterizedClass(self.dict_type, params, self.vm)

  def get_element_type(self, arg_type):
    """Extract the element type of a vararg or kwarg."""
    if not isinstance(arg_type, abstract.ParameterizedClass):
      assert (isinstance(arg_type, mixin.Class) and
              arg_type.full_name in ("__builtin__.dict", "__builtin__.tuple"))
      return None
    elif arg_type.base_cls is self.dict_type:
      return arg_type.get_formal_type_parameter(abstract_utils.V)
    else:
      assert arg_type.base_cls is self.tuple_type
      return arg_type.get_formal_type_parameter(abstract_utils.T)

  def _copy_type_parameters(self, old_container, new_container_name):
    new_container = self.name_to_value(new_container_name)
    if isinstance(old_container, abstract.ParameterizedClass):
      return abstract.ParameterizedClass(
          new_container, old_container.formal_type_parameters, self.vm)
    else:
      assert isinstance(old_container, mixin.Class)
      return new_container

  def widen_type(self, container):
    """Widen a tuple to an iterable, or a dict to a mapping."""
    if container.full_name == "__builtin__.tuple":
      return self._copy_type_parameters(container, "typing.Iterable")
    else:
      assert container.full_name == "__builtin__.dict", container.full_name
      return self._copy_type_parameters(container, "typing.Mapping")

  def merge_classes(self, instances):
    """Merge the classes of the given instances.

    Args:
      instances: An iterable of instances.
    Returns:
      An abstract.AtomicAbstractValue created by merging the instances' classes.
    """
    classes = set()
    for v in instances:
      cls = v.get_class()
      if cls:
        classes.add(cls)
    return self.vm.merge_values(classes)

  def constant_to_var(self, pyval, subst=None, node=None, source_sets=None,
                      discard_concrete_values=False):
    """Convert a constant to a Variable.

    This converts a constant to a cfg.Variable. Unlike constant_to_value, it
    can handle things that need to be represented as a Variable with multiple
    possible values (i.e., a union type), like pytd.Function.

    Args:
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
    if isinstance(pyval, pytd.NothingType):
      return self.vm.program.NewVariable([], [], self.vm.root_cfg_node)
    elif isinstance(pyval, pytd.Alias):
      return self.constant_to_var(pyval.type, subst, node, source_sets,
                                  discard_concrete_values)
    elif isinstance(pyval, abstract_utils.AsInstance):
      cls = pyval.cls
      if isinstance(cls, pytd.AnythingType):
        return self.unsolvable.to_variable(node)
      elif (isinstance(pyval, abstract_utils.AsReturnValue) and
            isinstance(cls, pytd.NothingType)):
        return self.no_return.to_variable(node)
      var = self.vm.program.NewVariable()
      for t in pytd_utils.UnpackUnion(cls):
        if isinstance(t, pytd.TypeParameter):
          if not subst or t.full_name not in subst:
            raise self.TypeParameterError(t.full_name)
          else:
            for v in subst[t.full_name].bindings:
              for source_set in source_sets:
                var.AddBinding(self.get_maybe_abstract_instance(v.data)
                               if discard_concrete_values else v.data,
                               source_set + [v], node)
        elif isinstance(t, pytd.NothingType):
          pass
        else:
          value = self.constant_to_value(
              abstract_utils.AsInstance(t), subst, node)
          for source_set in source_sets:
            var.AddBinding(value, source_set, node)
      return var
    elif isinstance(pyval, pytd.Constant):
      return self.constant_to_var(abstract_utils.AsInstance(pyval.type), subst,
                                  node, source_sets, discard_concrete_values)
    result = self.constant_to_value(pyval, subst, node)
    if result is not None:
      return result.to_variable(node)
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
          (self.constant_to_var(v, subst, node, source_sets,
                                discard_concrete_values)
           for i, v in enumerate(pyval)))
    raise ValueError(
        "Cannot convert {} to an abstract value".format(pyval.__class__))

  def constant_to_value(self, pyval, subst=None, node=None):
    """Like constant_to_var, but convert to an abstract.AtomicAbstractValue.

    This also memoizes the results.  We don't memoize on name, as builtin types
    like str or list might be reinitialized under different names (e.g. "param
    1"), but we want the canonical name and type.  We *do* memoize on the type
    as well, to make sure that e.g. "1.0" and "1" get converted to different
    constants.  Memoization is an optimization, but an important one - mapping
    constants like "None" to the same AbstractValue greatly simplifies the
    cfg structures we're building.

    Args:
      pyval: The constant to convert.
      subst: The current type parameters.
      node: The current CFG node. (For instances)
    Returns:
      The converted constant. (Instance of AtomicAbstractValue)
    """
    node = node or self.vm.root_cfg_node
    key = ("constant", pyval, type(pyval))
    if key in self._convert_cache:
      if self._convert_cache[key] is None:
        # This error is triggered by, e.g., classes inheriting from each other.
        name = (pyval.name if hasattr(pyval, "name")
                else pyval.__class__.__name__)
        self.vm.errorlog.recursion_error(self.vm.frames, name)
        self._convert_cache[key] = self.unsolvable
      return self._convert_cache[key]
    else:
      self._convert_cache[key] = None  # for recursion detection
      need_node = [False]  # mutable value that can be modified by get_node
      def get_node():
        need_node[0] = True
        return node
      value = self._constant_to_value(pyval, subst, get_node)
      if not need_node[0] or node is self.vm.root_cfg_node:
        # Values that contain a non-root node cannot be cached. Otherwise,
        # we'd introduce bugs such as the following:
        #   if <condition>:
        #     d = {"a": 1}  # "a" is cached here
        #   else:
        #     # the cached value of "a", which contains a node that is only
        #     # visible inside the "if", is used, which will eventually lead
        #     # pytype to think that the V->complex binding isn't visible.
        #     d = {"a": 1j}
        self._convert_cache[key] = value
      return value

  def _load_late_type(self, late_type):
    """Resolve a late type, possibly by loading a module."""
    if late_type.name not in self._resolved_late_types:
      module, dot, _ = late_type.name.rpartition(".")
      assert dot
      ast = self.vm.loader.import_name(module)
      if ast is not None:
        try:
          # TODO(kramm): Should this use pytd.py:ToType?
          cls = ast.Lookup(late_type.name)
        except KeyError:
          try:
            ast.Lookup("__getattr__")
          except KeyError:
            log.warning("Couldn't resolve %s", late_type.name)
          t = pytd.AnythingType()
        else:
          t = pytd.ToType(cls, allow_constants=False)
      else:
        # A pickle file refers to a module that went away in the mean time.
        log.error("During dependency resolution, couldn't import %r", module)
        t = pytd.AnythingType()
      self._resolved_late_types[late_type.name] = t
    return self._resolved_late_types[late_type.name]

  def _create_module(self, ast):
    data = (ast.constants + ast.type_params + ast.classes +
            ast.functions + ast.aliases)
    members = {val.name.rsplit(".")[-1]: val for val in data}
    return abstract.Module(self.vm, ast.name, members, ast)

  def _get_literal_value(self, pyval):
    if pyval == self.vm.lookup_builtin("__builtin__.True"):
      return True
    elif pyval == self.vm.lookup_builtin("__builtin__.False"):
      return False
    else:
      return pyval

  def _constant_to_value(self, pyval, subst, get_node):
    """Create a AtomicAbstractValue that represents a python constant.

    This supports both constant from code constant pools and PyTD constants such
    as classes. This also supports builtin python objects such as int and float.

    Args:
      pyval: The python or PyTD value to convert.
      subst: The current type parameters.
      get_node: A getter function for the current node.
    Returns:
      A Value that represents the constant, or None if we couldn't convert.
    Raises:
      NotImplementedError: If we don't know how to convert a value.
      TypeParameterError: If we can't find a substitution for a type parameter.
    """
    if pyval.__class__ is str:
      # We use a subclass of str, compat.BytesPy3, to mark Python 3
      # bytestrings, which are converted to abstract bytes instances.
      # compat.BytesType dispatches to this when appropriate.
      return abstract.AbstractOrConcreteValue(pyval, self.str_type, self.vm)
    elif isinstance(pyval, compat.UnicodeType):
      return abstract.AbstractOrConcreteValue(pyval, self.unicode_type, self.vm)
    elif isinstance(pyval, compat.BytesType):
      return abstract.AbstractOrConcreteValue(pyval, self.bytes_type, self.vm)
    elif isinstance(pyval, bool):
      return self.true if pyval else self.false
    elif isinstance(pyval, int) and -1 <= pyval <= MAX_IMPORT_DEPTH:
      # For small integers, preserve the actual value (for things like the
      # level in IMPORT_NAME).
      return abstract.AbstractOrConcreteValue(pyval, self.int_type, self.vm)
    elif isinstance(pyval, compat.LongType):
      # long is aliased to int
      return self.primitive_class_instances[int]
    elif pyval.__class__ in self.primitive_classes:
      return self.primitive_class_instances[pyval.__class__]
    elif isinstance(pyval, (loadmarshal.CodeType, blocks.OrderedCode)):
      return abstract.AbstractOrConcreteValue(
          pyval, self.primitive_classes[types.CodeType], self.vm)
    elif pyval is super:
      return special_builtins.Super(self.vm)
    elif pyval is object:
      return special_builtins.Object(self.vm)
    elif pyval.__class__ is type:
      try:
        return self.name_to_value(self._type_to_name(pyval), subst)
      except (KeyError, AttributeError):
        log.debug("Failed to find pytd", exc_info=True)
        raise
    elif isinstance(pyval, pytd.LateType):
      actual = self._load_late_type(pyval)
      return self._constant_to_value(actual, subst, get_node)
    elif isinstance(pyval, pytd.TypeDeclUnit):
      return self._create_module(pyval)
    elif isinstance(pyval, pytd.Module):
      mod = self.vm.loader.import_name(pyval.module_name)
      return self._create_module(mod)
    elif isinstance(pyval, pytd.Class):
      if pyval.name == "__builtin__.super":
        return self.vm.special_builtins["super"]
      elif pyval.name == "__builtin__.object":
        return self.object_type
      elif pyval.name == "types.ModuleType":
        return self.module_type
      elif pyval.name == "_importlib_modulespec.ModuleType":
        # Python 3's typeshed uses a stub file indirection to define ModuleType
        # even though it is exported via types.pyi.
        return self.module_type
      elif pyval.name == "types.FunctionType":
        return self.function_type
      else:
        module, dot, base_name = pyval.name.rpartition(".")
        # typing.TypingContainer intentionally loads the underlying pytd types.
        if module != "typing" and module in self.vm.loaded_overlays:
          overlay = self.vm.loaded_overlays[module]
          if overlay.get_module(base_name) is overlay:
            overlay.load_lazy_attribute(base_name)
            return abstract_utils.get_atomic_value(overlay.members[base_name])
        try:
          cls = abstract.PyTDClass(base_name, pyval, self.vm)
        except mro.MROError as e:
          self.vm.errorlog.mro_error(self.vm.frames, base_name, e.mro_seqs)
          cls = self.unsolvable
        else:
          if dot:
            cls.module = module
        return cls
    elif isinstance(pyval, pytd.Function):
      signatures = [function.PyTDSignature(pyval.name, sig, self.vm)
                    for sig in pyval.signatures]
      type_new = self.vm.lookup_builtin("__builtin__.type").Lookup("__new__")
      if pyval is type_new:
        f_cls = special_builtins.TypeNew
      else:
        f_cls = abstract.PyTDFunction
      f = f_cls(pyval.name, signatures, pyval.kind, self.vm)
      f.is_abstract = pyval.is_abstract
      return f
    elif isinstance(pyval, pytd.ClassType):
      assert pyval.cls
      return self.constant_to_value(pyval.cls, subst, self.vm.root_cfg_node)
    elif isinstance(pyval, pytd.NothingType):
      return self.empty
    elif isinstance(pyval, pytd.AnythingType):
      return self.unsolvable
    elif (isinstance(pyval, pytd.Constant) and
          isinstance(pyval.type, pytd.AnythingType)):
      # We allow "X = ... # type: Any" to declare X as a type.
      return self.unsolvable
    elif (isinstance(pyval, pytd.Constant) and
          isinstance(pyval.type, pytd.GenericType) and
          pyval.type.base_type.name == "__builtin__.type"):
      # `X: Type[other_mod.X]` is equivalent to `X = other_mod.X`.
      param, = pyval.type.parameters
      return self.constant_to_value(param, subst, self.vm.root_cfg_node)
    elif isinstance(pyval, pytd.FunctionType):
      return self.constant_to_value(
          pyval.function, subst, self.vm.root_cfg_node)
    elif isinstance(pyval, pytd.UnionType):
      options = [self.constant_to_value(t, subst, self.vm.root_cfg_node)
                 for t in pyval.type_list]
      if len(options) > 1:
        return abstract.Union(options, self.vm)
      else:
        return options[0]
    elif isinstance(pyval, pytd.TypeParameter):
      constraints = tuple(self.constant_to_value(c, {}, self.vm.root_cfg_node)
                          for c in pyval.constraints)
      bound = (pyval.bound and
               self.constant_to_value(pyval.bound, {}, self.vm.root_cfg_node))
      return abstract.TypeParameter(
          pyval.name, self.vm, constraints=constraints,
          bound=bound, module=pyval.scope)
    elif isinstance(pyval, abstract_utils.AsInstance):
      cls = pyval.cls
      if isinstance(cls, pytd.LateType):
        actual = self._load_late_type(cls)
        if not isinstance(actual, pytd.ClassType):
          return self.unsolvable
        cls = actual.cls
      if isinstance(cls, pytd.ClassType):
        cls = cls.cls
      if (isinstance(cls, pytd.GenericType) and
          cls.base_type.name == "typing.ClassVar"):
        param, = cls.parameters
        return self.constant_to_value(
            abstract_utils.AsInstance(param), subst, self.vm.root_cfg_node)
      elif isinstance(cls, pytd.GenericType) or (isinstance(cls, pytd.Class) and
                                                 cls.template):
        # If we're converting a generic Class, need to create a new instance of
        # it. See test_classes.testGenericReinstantiated.
        if isinstance(cls, pytd.Class):
          params = tuple(t.type_param.upper_value for t in cls.template)
          cls = pytd.GenericType(base_type=pytd.ClassType(cls.name, cls),
                                 parameters=params)
        if isinstance(cls.base_type, pytd.LateType):
          actual = self._load_late_type(cls.base_type)
          if not isinstance(actual, pytd.ClassType):
            return self.unsolvable
          base_cls = actual.cls
        else:
          assert isinstance(cls.base_type, pytd.ClassType)
          base_cls = cls.base_type.cls
        assert isinstance(base_cls, pytd.Class), base_cls
        if base_cls.name == "__builtin__.type":
          c, = cls.parameters
          if isinstance(c, pytd.TypeParameter):
            if not subst or c.full_name not in subst:
              raise self.TypeParameterError(c.full_name)
            return self.merge_classes(subst[c.full_name].data)
          else:
            return self.constant_to_value(c, subst, self.vm.root_cfg_node)
        elif isinstance(cls, pytd.TupleType):
          content = tuple(self.constant_to_var(abstract_utils.AsInstance(p),
                                               subst, get_node())
                          for p in cls.parameters)
          return abstract.Tuple(content, self.vm)
        elif isinstance(cls, pytd.CallableType):
          clsval = self.constant_to_value(cls, subst, self.vm.root_cfg_node)
          return abstract.Instance(clsval, self.vm)
        else:
          clsval = self.constant_to_value(
              base_cls, subst, self.vm.root_cfg_node)
          instance = abstract.Instance(clsval, self.vm)
          num_params = len(cls.parameters)
          assert num_params <= len(base_cls.template)
          for i, formal in enumerate(base_cls.template):
            if i < num_params:
              node = get_node()
              p = self.constant_to_var(
                  abstract_utils.AsInstance(cls.parameters[i]), subst, node)
            else:
              # An omitted type parameter implies `Any`.
              node = self.vm.root_cfg_node
              p = self.unsolvable.to_variable(node)
            instance.merge_instance_type_parameter(node, formal.name, p)
          return instance
      elif isinstance(cls, pytd.Class):
        assert not cls.template
        # This key is also used in __init__
        key = (abstract.Instance, cls)
        if key not in self._convert_cache:
          if cls.name in ["__builtin__.type", "__builtin__.property"]:
            # An instance of "type" or of an anonymous property can be anything.
            instance = self._create_new_unknown_value("type")
          else:
            mycls = self.constant_to_value(cls, subst, self.vm.root_cfg_node)
            instance = abstract.Instance(mycls, self.vm)
          log.info("New pytd instance for %s: %r", cls.name, instance)
          self._convert_cache[key] = instance
        return self._convert_cache[key]
      elif isinstance(cls, pytd.Literal):
        return self.constant_to_value(
            self._get_literal_value(cls.value), subst, self.vm.root_cfg_node)
      else:
        return self.constant_to_value(cls, subst, self.vm.root_cfg_node)
    elif (isinstance(pyval, pytd.GenericType) and
          pyval.base_type.name == "typing.ClassVar"):
      param, = pyval.parameters
      return self.constant_to_value(param, subst, self.vm.root_cfg_node)
    elif isinstance(pyval, pytd.GenericType):
      if isinstance(pyval.base_type, pytd.LateType):
        actual = self._load_late_type(pyval.base_type)
        if not isinstance(actual, pytd.ClassType):
          return self.unsolvable
        base = actual.cls
      else:
        assert isinstance(pyval.base_type, pytd.ClassType), pyval
        base = pyval.base_type.cls
      assert isinstance(base, pytd.Class), base
      base_cls = self.constant_to_value(
          base, subst, self.vm.root_cfg_node)
      if not isinstance(base_cls, mixin.Class):
        # base_cls can be, e.g., an unsolvable due to an mro error.
        return self.unsolvable
      if isinstance(pyval, pytd.TupleType):
        abstract_class = abstract.TupleClass
        template = list(range(len(pyval.parameters))) + [abstract_utils.T]
        parameters = pyval.parameters + (pytd.UnionType(pyval.parameters),)
      elif isinstance(pyval, pytd.CallableType):
        abstract_class = abstract.CallableClass
        template = list(range(len(pyval.args))) + [abstract_utils.ARGS,
                                                   abstract_utils.RET]
        parameters = pyval.args + (pytd_utils.JoinTypes(pyval.args), pyval.ret)
      else:
        abstract_class = abstract.ParameterizedClass
        if pyval.base_type.name == "typing.Generic":
          pyval_template = pyval.parameters
        else:
          pyval_template = base.template
        template = tuple(t.name for t in pyval_template)
        parameters = pyval.parameters
      assert (pyval.base_type.name == "typing.Generic" or
              len(parameters) <= len(template))
      # Delay type parameter loading to handle recursive types.
      # See the ParameterizedClass.formal_type_parameters() property.
      type_parameters = abstract_utils.LazyFormalTypeParameters(
          template, parameters, subst)
      return abstract_class(base_cls, type_parameters, self.vm)
    elif isinstance(pyval, pytd.Literal):
      value = self.constant_to_value(
          self._get_literal_value(pyval.value), subst, self.vm.root_cfg_node)
      return abstract.LiteralClass(
          self.name_to_value("typing.Literal"), value, self.vm)
    elif pyval.__class__ is tuple:  # only match raw tuple, not namedtuple/Node
      return self.tuple_to_value([self.constant_to_var(item, subst,
                                                       self.vm.root_cfg_node)
                                  for i, item in enumerate(pyval)])
    else:
      raise NotImplementedError("Can't convert constant %s %r" %
                                (type(pyval), pyval))
