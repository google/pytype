"""Custom implementations of builtin types."""

from pytype import abstract
from pytype import function


class TypeNew(abstract.PyTDFunction):
  """Implements type.__new__."""

  def call(self, node, func, args):
    if len(args.posargs) == 4:
      self._match_args(node, args)  # May raise FailedFunctionCall.
      cls, name_var, bases_var, class_dict_var = args.posargs
      try:
        bases = list(abstract.get_atomic_python_constant(bases_var))
        if not bases:
          bases = [self.vm.convert.object_type]
        variable = self.vm.make_class(
            node, name_var, bases, class_dict_var, cls)
      except abstract.ConversionError:
        pass
      else:
        return node, variable
    return super(TypeNew, self).call(node, func, args)


class ObjectPredicate(abstract.AtomicAbstractValue):
  """The base class for builtin predicates of the form f(obj, value).

  Subclasses need to override the following:

  _SIGNATURE: A minimal function.Signature, used for constructing exceptions.
  _call_predicate(self, node, left, right): The implementation of the predicate.
  """

  # Minimal signature, only used for constructing exceptions. Base classes
  # should set this.
  _SIGNATURE = None

  def __init__(self, name, vm):
    super(ObjectPredicate, self).__init__(name, vm)
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
        raise abstract.WrongArgCount(self._SIGNATURE, args, self.vm)
      elif args.namedargs.keys():
        raise abstract.WrongKeywordArgs(
            self._SIGNATURE, args, self.vm, args.namedargs.keys())
      else:
        result = self.vm.program.NewVariable()
        for left in args.posargs[0].bindings:
          for right in args.posargs[1].bindings:
            node, pyval = self._call_predicate(node, left.data, right.data)
            result.AddBinding(self._vm_values[pyval],
                              source_set=(left, right), where=node)
    except abstract.InvalidParameters as ex:
      self.vm.errorlog.invalid_function_call(self.vm.frames, ex)
      result = self.vm.convert.create_new_unsolvable(node)
    return node, result


class HasAttr(ObjectPredicate):
  """The hasattr() function."""

  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature(
      "hasattr", ("obj", "attr"), None, set(), None, {}, {}, {})

  def __init__(self, vm):
    super(HasAttr, self).__init__("hasattr", vm)

  def _call_predicate(self, node, left, right):
    return self._has_attr(node, left, right)

  def _has_attr(self, node, obj, attr):
    """Check if the object has attribute attr.

    Args:
      node: The given node.
      obj: An AtomicAbstractValue, generally the left hand side of a
          hasattr() call.
      attr: An AtomicAbstractValue, generally the right hand side of a
          hasattr() call.

    Returns:
      (node, result) where result = True if the object has attribute attr, False
      if it does not, and None if it is ambiguous.
    """
    if isinstance(obj, abstract.AMBIGUOUS_OR_EMPTY):
      return node, None
    # If attr is not a literal constant, don't try to resolve it.
    if (not isinstance(attr, abstract.PythonConstant) or
        not isinstance(attr.pyval, str)):
      # TODO(rechen): We should type-check the arguments
      # (using __builtin__.pytd's definition of hasattr, perhaps), so that
      # non-string things don't even get to this point.
      return node, None
    node, ret = self.vm.attribute_handler.get_attribute(node, obj, attr.pyval)
    return node, ret is not None


class IsInstance(ObjectPredicate):
  """The isinstance() function."""

  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature(
      "isinstance", ("obj", "type_or_types"), None, set(), None, {}, {}, {})

  def __init__(self, vm):
    super(IsInstance, self).__init__("isinstance", vm)

  def _call_predicate(self, node, left, right):
    return node, self._is_instance(left, right)

  def _is_instance(self, obj, class_spec):
    """Check if the object matches a class specification.

    Args:
      obj: An AtomicAbstractValue, generally the left hand side of an
          isinstance() call.
      class_spec: An AtomicAbstractValue, generally the right hand side of an
          isinstance() call.

    Returns:
      True if the object is derived from a class in the class_spec, False if
      it is not, and None if it is ambiguous whether obj matches class_spec.
    """
    if isinstance(obj, abstract.AMBIGUOUS_OR_EMPTY):
      return None
    # Assume a single binding for the object's class variable.  If this isn't
    # the case, treat the call as ambiguous.
    cls_var = obj.get_class()
    if cls_var is None:
      return None
    try:
      obj_class = abstract.get_atomic_value(cls_var)
    except abstract.ConversionError:
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
    if isinstance(value, abstract.Class):
      # A single class, no ambiguity.
      classes.append(value)
      return False
    elif isinstance(value, abstract.Tuple):
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


class SuperInstance(abstract.AtomicAbstractValue):
  """The result of a super() call, i.e., a lookup proxy."""

  def __init__(self, cls, obj, vm):
    super(SuperInstance, self).__init__("super", vm)
    self.cls = self.vm.convert.super_type
    self.super_cls = cls
    self.super_obj = obj
    self.get = abstract.NativeFunction("__get__", self.get, self.vm)
    self.set = abstract.NativeFunction("__set__", self.set, self.vm)

  def get(self, node, *unused_args, **unused_kwargs):
    return node, self.to_variable(node)

  def set(self, node, *unused_args, **unused_kwargs):
    return node, self.to_variable(node)

  def get_special_attribute(self, node, name, valself):
    if name == "__get__":
      return self.get.to_variable(node)
    elif name == "__set__":
      return self.set.to_variable(node)
    else:
      return super(SuperInstance, self).get_special_attribute(
          node, name, valself)

  def get_class(self):
    return self.cls

  def call(self, node, _, args):
    self.vm.errorlog.not_callable(self.vm.frames, self)
    return node, abstract.Unsolvable(self.vm).to_variable(node)


class Super(abstract.PyTDClass):
  """The super() function. Calling it will create a SuperInstance."""

  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature(
      "super", ("cls", "self"), None, set(), None, {}, {}, {})

  def __init__(self, vm):
    super(Super, self).__init__(
        "super", vm.lookup_builtin("__builtin__.super"), vm)
    self.module = "__builtin__"

  def call(self, node, _, args):
    result = self.vm.program.NewVariable()
    num_args = len(args.posargs)
    if 1 <= num_args and num_args <= 2:
      super_objects = args.posargs[1].bindings if num_args == 2 else [None]
      for cls in args.posargs[0].bindings:
        if not isinstance(cls.data, (abstract.Class,
                                     abstract.AMBIGUOUS_OR_EMPTY)):
          bad = abstract.BadParam(
              name="cls", expected=self.vm.convert.type_type.data[0])
          raise abstract.WrongArgTypes(
              self._SIGNATURE, args, self.vm, bad_param=bad)
        for obj in super_objects:
          if obj:
            result.AddBinding(
                SuperInstance(cls.data, obj.data, self.vm), [cls, obj], node)
          else:
            result.AddBinding(
                SuperInstance(cls.data, None, self.vm), [cls], node)
    else:
      raise abstract.WrongArgCount(self._SIGNATURE, args, self.vm)
    return node, result


class Object(abstract.PyTDClass):
  """Implementation of __builtin__.object."""

  def __init__(self, vm):
    super(Object, self).__init__(
        "object", vm.lookup_builtin("__builtin__.object"), vm)
    self.module = "__builtin__"

  def is_object_new(self, func):
    """Whether the given function is object.__new__.

    Args:
      func: A function.

    Returns:
      True if func equals either of the pytd definitions for object.__new__,
      False otherwise.
    """
    self.load_lazy_attribute("__new__")
    self.load_lazy_attribute("__new__extra_args")
    return ([func] == self.members["__new__"].data or
            [func] == self.members["__new__extra_args"].data)

  def _has_own(self, node, cls, method):
    """Whether a class has its own implementation of a particular method.

    Args:
      node: The current node.
      cls: An abstract.Class.
      method: The method name. So that we don't have to handle the cases when
        the method doesn't exist, we only support "__new__" and "__init__".

    Returns:
      True if the class's definition of the method is different from the
      definition in __builtin__.object, False otherwise.
    """
    assert method in ("__new__", "__init__")
    self.load_lazy_attribute(method)
    obj_method = self.members[method]
    _, cls_method = self.vm.attribute_handler.get_class_attribute(
        node, cls, method)
    return obj_method.data != cls_method.data

  def get_special_attribute(self, node, name, valself):
    # Based on the definitions of object_init and object_new in
    # cpython/Objects/typeobject.c (https://goo.gl/bTEBRt). It is legal to pass
    # extra arguments to object.__new__ if the calling class overrides
    # object.__init__, and vice versa.
    if valself:
      val = valself.data
      if (name == "__new__" and isinstance(val, abstract.Class) and
          self._has_own(node, val, "__init__")):
        self.load_lazy_attribute("__new__extra_args")
        return self.members["__new__extra_args"]
      elif (name == "__init__" and isinstance(val, abstract.Instance) and
            any(self._has_own(node, cls, "__new__") for cls in val.cls.data)):
        self.load_lazy_attribute("__init__extra_args")
        return self.members["__init__extra_args"]
    return super(Object, self).get_special_attribute(node, name, valself)


class RevealType(abstract.AtomicAbstractValue):
  """For debugging. reveal_type(x) prints the type of "x"."""

  def __init__(self, vm):
    super(RevealType, self).__init__("reveal_type", vm)

  def call(self, node, _, args):
    for a in args.posargs:
      self.vm.errorlog.reveal_type(self.vm.frames, node, a)
    return node, self.vm.convert.build_none(node)
