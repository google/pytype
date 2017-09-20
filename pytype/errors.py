"""Code and data structures for storing and displaying errors."""

import collections
import csv
import logging
import os
import re
import StringIO
import sys

import debug

from pytype import abstract
from pytype import utils
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils

# Usually we call the logger "log" but that name is used quite often here.
_log = logging.getLogger(__name__)


# "Error level" enum for distinguishing between warnings and errors:
SEVERITY_WARNING = 1
SEVERITY_ERROR = 2

# The set of known error names.
_ERROR_NAMES = set()

# The current error name, managed by the error_name decorator.
_CURRENT_ERROR_NAME = utils.DynamicVar()

# Max number of calls in the traceback string.
MAX_TRACEBACK_LENGTH = 3

# Marker indicating the start of a traceback.
TRACEBACK_MARKER = "Traceback:"

# Symbol representing an elided portion of the stack.
_ELLIPSIS = object()


def _error_name(name):
  """Decorate a function so that it binds the current error name."""
  _ERROR_NAMES.add(name)
  def wrap(func):
    def invoke(*args, **kwargs):
      with _CURRENT_ERROR_NAME.bind(name):
        return func(*args, **kwargs)
    return invoke
  return wrap


def _maybe_truncate_traceback(traceback):
  """Truncate the traceback if it is too long.

  Args:
    traceback: A list representing an error's traceback. There should be one
      list item per entry in the traceback (in the right order); beyond that,
      this function does not care about the item types.

  Returns:
    The traceback, possibly with some items removed and an _ELLIPSIS inserted.
    Guaranteed to be no longer than MAX_TRACEBACK_LENGTH.
  """
  if len(traceback) > MAX_TRACEBACK_LENGTH:
    return traceback[:MAX_TRACEBACK_LENGTH-2] + [_ELLIPSIS, traceback[-1]]
  else:
    return traceback


def _make_traceback_str(ops):
  """Turn a stack of opcodes into a traceback string.

  Args:
    ops: A list of pyi.opcodes.Opcode objects.

  Returns:
    A traceback string representing the stack.
  """
  ops = ops[:-1]
  if ops:
    ops = _maybe_truncate_traceback(ops)
    op_to_str = lambda op: "line %d, in %s" % (op.line, op.code.co_name)
    traceback = ["..." if op is _ELLIPSIS else op_to_str(op) for op in ops]
    return TRACEBACK_MARKER + "\n  " + "\n  ".join(traceback)
  else:
    return None


def _stack_to_opcodes(stack):
  """Turn a stack of frames into a stack of opcodes, removing duplicates."""
  ops = []
  for frame in stack:
    if frame.current_opcode and (
        not ops or frame.current_opcode.line != ops[-1].line):
      # We can have consecutive opcodes with the same line number due to, e.g.,
      # a set comprehension. The first opcode we encounter is the one with the
      # real method name, whereas the second's method name is something like
      # <setcomp>, so we keep the first.
      ops.append(frame.current_opcode)
  return ops


def _compare_traceback_strings(left, right):
  """Try to compare two traceback strings.

  Two traceback strings are comparable if they are equal, or if one ends with
  the other. For example, these two tracebacks are comparable:
    Traceback:
      line 1, in <module>
      line 2, in foo
    Traceback:
      line 2, in foo
  and the first is greater than the second.

  Args:
    left: A string or None.
    right: A string or None.

  Returns:
    None if the inputs aren't comparable, else an integer.
  """
  if left == right:
    return 0
  left = left[len(TRACEBACK_MARKER):] if left else ""
  right = right[len(TRACEBACK_MARKER):] if right else ""
  if left.endswith(right):
    return 1
  elif right.endswith(left):
    return -1
  else:
    return None


class CheckPoint(object):
  """Represents a position in an error log."""

  def __init__(self, log, position):
    self.log = log
    self.position = position


class Error(object):
  """Representation of an error in the error log."""

  def __init__(self, severity, message, filename=None, lineno=0,
               methodname=None, details=None, traceback=None):
    name = _CURRENT_ERROR_NAME.get()
    assert name, ("Errors must be created from a caller annotated "
                  "with @error_name.")
    # Required for every Error.
    self._severity = severity
    self._message = message
    self._name = name
    # Optional information about the error.
    self._details = details
    # Optional information about error position.
    # TODO(dbaum): Do not allow filename (and maybe lineno) of None.
    self._filename = filename
    self._lineno = lineno or 0
    self._methodname = methodname
    self._traceback = traceback

  @classmethod
  def with_stack(cls, stack, severity, message, details=None):
    """Return an error using a stack for position information.

    Args:
      stack: A list of state.Frame or state.SimpleFrame objects.
      severity: The error level (error or warning), an integer.
      message: The error message string.
      details: Optionally, a string of message details.

    Returns:
      An Error object.
    """
    opcodes = _stack_to_opcodes(stack) if stack else None
    opcode = opcodes[-1] if opcodes else None
    if opcode is None:
      return cls(severity, message, details=details)
    else:
      return cls(severity, message, filename=opcode.code.co_filename,
                 lineno=opcode.line, methodname=opcode.code.co_name,
                 details=details, traceback=_make_traceback_str(opcodes))

  @classmethod
  def for_test(cls, severity, message, name, **kwargs):
    """Create an _Error with the specified name, for use in tests."""
    with _CURRENT_ERROR_NAME.bind(name):
      return cls(severity, message, **kwargs)

  @property
  def name(self):
    return self._name

  @property
  def lineno(self):
    return self._lineno

  @property
  def filename(self):
    return self._filename

  @property
  def message(self):
    message = self._message
    if self._details:
      message += "\n" + self._details
    if self._traceback:
      message += "\n" + self._traceback
    return message

  @property
  def traceback(self):
    return self._traceback

  @property
  def methodname(self):
    return self._methodname

  def _position(self):
    """Return human-readable filename + line number."""
    method = ", in %s" % self._methodname if self._methodname else ""

    if self._filename:
      filename = os.path.basename(self._filename)
      return "File \"%s\", line %d%s" % (filename,
                                         self._lineno,
                                         method)
    elif self._lineno:
      return "Line %d%s" % (self._lineno, method)
    else:
      return ""

  def __str__(self):
    pos = self._position()
    if pos:
      pos += ": "
    text = "%s%s [%s]" % (pos, self._message.replace("\n", "\n  "), self._name)
    if self._details:
      text += "\n  " + self._details.replace("\n", "\n  ")
    if self._traceback:
      text += "\n" + self._traceback
    return text

  def drop_traceback(self):
    with _CURRENT_ERROR_NAME.bind(self._name):
      return self.__class__(
          severity=self._severity,
          message=self._message,
          filename=self._filename,
          lineno=self._lineno,
          methodname=self._methodname,
          details=self._details,
          traceback=None)


class ErrorLogBase(object):
  """A stream of errors."""

  def __init__(self):
    self._errors = []
    # An error filter (initially None)
    self._filter = None

  def __len__(self):
    return len(self._errors)

  def __iter__(self):
    return iter(self._errors)

  def __getitem__(self, index):
    return self._errors[index]

  def is_valid_error_name(self, name):
    """Return True iff name was defined in an @error_name() decorator."""
    return name in _ERROR_NAMES

  def set_error_filter(self, filt):
    """Set the error filter.

    Args:
      filt: A function or callable object that accepts a single argument of
          type Error and returns True if that error should be included in the
          log.  A filter of None will add all errors.
    """
    self._filter = filt

  def has_error(self):
    """Return true iff an Error with SEVERITY_ERROR is present."""
    # pylint: disable=protected-access
    return any(e._severity == SEVERITY_ERROR for e in self._errors)

  def _add(self, error):
    if self._filter is None or self._filter(error):
      _log.info("Added error to log: %s\n%s", error.name, error)
      if _log.isEnabledFor(logging.DEBUG):
        _log.debug(debug.stack_trace(limit=1).rstrip())
      self._errors.append(error)

  def warn(self, stack, message, *args):
    self._add(Error.with_stack(stack, SEVERITY_WARNING, message % args))

  def error(self, stack, message, details=None):
    self._add(Error.with_stack(stack, SEVERITY_ERROR, message, details=details))

  def save(self):
    """Returns a checkpoint that represents the log messages up to now."""
    return CheckPoint(self, len(self._errors))

  def revert_to(self, checkpoint):
    assert checkpoint.log is self
    self._errors = self._errors[:checkpoint.position]

  def print_to_csv_file(self, filename):
    with open(filename, "wb") as f:
      csv_file = csv.writer(f, delimiter=",")
      for error in self.unique_sorted_errors():
        # pylint: disable=protected-access
        # TODO(kramm): Add _methodname
        if error._details and error._traceback:
          details = error._details + "\n\n" + error._traceback
        elif error._traceback:
          details = error._traceback
        else:
          details = error._details
        csv_file.writerow(
            [error._filename,
             error._lineno,
             error._name,
             error._message,
             details])

  def print_to_file(self, fi):
    for error in self.unique_sorted_errors():
      print >> fi, error

  def unique_sorted_errors(self):
    """Gets the unique errors in this log, sorted on filename and lineno."""
    unique_errors = collections.OrderedDict()
    for error in self._sorted_errors():
      error_without_traceback = str(error.drop_traceback())
      if error_without_traceback not in unique_errors:
        unique_errors[error_without_traceback] = [error]
        continue
      errors = unique_errors[error_without_traceback]
      for previous_error in list(errors):  # make a copy, since we modify errors
        traceback_cmp = _compare_traceback_strings(error.traceback,
                                                   previous_error.traceback)
        if traceback_cmp is None:
          # We have multiple bad call sites, e.g.,
          #   def f(x):  x + 42
          #   f("hello")  # error
          #   f("world")  # same error, different backtrace
          # so we'll report this error multiple times with different backtraces.
          continue
        elif traceback_cmp < 0:
          # If the current traceback is shorter, use the current error instead
          # of the previous one.
          errors.remove(previous_error)
        else:
          # One of the previous errors has a shorter traceback than the current
          # one, so the latter can be discarded.
          break
      else:
        errors.append(error)
    return sum(unique_errors.values(), [])

  def _sorted_errors(self):
    return sorted(self._errors, key=lambda x: (x.filename, x.lineno))

  def print_to_stderr(self):
    self.print_to_file(sys.stderr)

  def __str__(self):
    io = StringIO.StringIO()
    self.print_to_file(io)
    return io.getvalue()


class ErrorLog(ErrorLogBase):
  """ErrorLog with convenience functions."""

  def _pytd_print(self, pytd_type):
    name = pytd.Print(
        pytd_utils.CanonicalOrdering(optimize.Optimize(pytd_type)))
    # Clean up autogenerated namedtuple names, e.g. "namedtuple-X-a-_0-c"
    # becomes just "X", by extracting out just the type name.
    if "namedtuple-" in name:
      return re.sub(r"\bnamedtuple-([^-]+)-[-_\w]*", r"\1", name)
    return name

  def _print_as_expected_type(self, t):
    if isinstance(t, (abstract.Unknown, abstract.Unsolvable, abstract.Class,
                      abstract.Union)):
      with t.vm.convert.pytd_convert.produce_detailed_output():
        return self._pytd_print(t.get_instance_type())
    elif isinstance(t, abstract.PythonConstant):
      return re.sub(r"(\\n|\s)+", " ",
                    t.str_of_constant(self._print_as_expected_type))
    elif isinstance(t, abstract.AnnotationClass) or not t.cls:
      return t.name
    else:
      return "<instance of %s>" % self._print_as_expected_type(t.cls.data[0])

  def _print_as_actual_type(self, t):
    with t.vm.convert.pytd_convert.produce_detailed_output():
      return self._pytd_print(t.to_type())

  def _join_printed_types(self, types):
    types = sorted(types)
    if len(types) == 1:
      return next(iter(types))
    elif types:
      return "Union[%s]" % ", ".join(types)
    else:
      return "nothing"

  def _iter_sig(self, sig):
    """Iterate through a function.Signature object. Focus on a bad parameter."""
    for name in sig.param_names:
      yield "", name
    if sig.varargs_name is not None:
      yield "*", sig.varargs_name
    elif sig.kwonly_params:
      yield ("*", "")
    for name in sorted(sig.kwonly_params):
      yield "", name
    if sig.kwargs_name is not None:
      yield "**", sig.kwargs_name

  def _iter_expected(self, sig, bad_param):
    """Yield the prefix, name and type information for expected parameters."""
    for prefix, name in self._iter_sig(sig):
      suffix = " = ..." if name in sig.defaults else ""
      if bad_param and name == bad_param.name:
        type_str = self._print_as_expected_type(bad_param.expected)
        suffix = ": " + type_str + suffix
      else:
        suffix = suffix
      yield prefix, name, suffix

  def _iter_actual(self, sig, passed_args, bad_param):
    """Yield the prefix, name and type information for actual parameters."""
    # We want to display the passed_args in the order they're defined in the
    # signature, unless there are starargs or starstarargs.
    # Map param names to their position in the list, then sort the list of
    # passed args so it's in the same order as the params.
    keys = {param: n for n, (_, param) in enumerate(self._iter_sig(sig))}
    def key_f(arg):
      arg_name = arg[0]
      # starargs are given anonymous names, which won't be found in the sig.
      # Instead, use the same name as the varags param itself, if present.
      if arg_name not in keys and pytd_utils.ANON_PARAM.match(arg_name):
        return keys.get(sig.varargs_name, len(keys)+1)
      return keys.get(arg_name, len(keys)+1)
    for name, arg in sorted(passed_args, key=key_f):
      if bad_param and name == bad_param.name:
        suffix = ": " + self._print_as_actual_type(arg)
      else:
        suffix = ""
      yield "", name, suffix

  def _print_args(self, arg_iter, bad_param):
    """Pretty-print a list of arguments. Focus on a bad parameter."""
    # (foo, bar, broken : type, ...)
    printed_params = []
    found = False
    for prefix, name, suffix in arg_iter:
      if bad_param and name == bad_param.name:
        printed_params.append(prefix + name + suffix)
        found = True
      elif found:
        printed_params.append("...")
        break
      elif pytd_utils.ANON_PARAM.match(name):
        printed_params.append(prefix + "_")
      else:
        printed_params.append(prefix + name)
    return ", ".join(printed_params)

  @_error_name("pyi-error")
  def pyi_error(self, stack, name, error):
    self.error(stack, "Couldn't import pyi for %r" % name, str(error))

  @_error_name("attribute-error")
  def attribute_error(self, stack, obj, attr_name):
    assert obj.bindings
    obj_values = abstract.merge_values(obj.data, obj.data[0].vm)
    obj_repr = self._print_as_actual_type(obj_values)
    self.error(stack, "No attribute %r on %s" % (attr_name, obj_repr))

  @_error_name("not-writable")
  def not_writable(self, stack, obj, attr_name):
    obj_values = abstract.merge_values([obj], obj.vm)
    obj_repr = self._print_as_actual_type(obj_values)
    self.error(stack, "Can't assign attribute %r on %s" % (attr_name, obj_repr))

  @_error_name("module-attr")
  def module_attr(self, stack, obj, attr_name):
    module_names = {m.name for m in obj.data if isinstance(m, abstract.Module)}
    assert module_names
    self.error(stack, "No attribute %r on module %r" % (
        attr_name, min(module_names)))

  def attribute_or_module_error(self, stack, obj, attr_name):
    if any(isinstance(x, abstract.Module) for x in obj.data):
      return self.module_attr(stack, obj, attr_name)
    else:
      return self.attribute_error(stack, obj, attr_name)

  @_error_name("none-attr")
  def none_attr(self, stack, attr_name):
    self.error(
        stack,
        "Access of attribute %r on a type that might be None" % attr_name,
        details="Do you need a type comment?")

  @_error_name("unbound-type-param")
  def unbound_type_param(self, stack, obj, attr_name, type_param_name):
    self.error(
        stack, "Can't access attribute %r on %s" % (attr_name, obj.name),
        "No binding for type parameter %s" % type_param_name)

  @_error_name("name-error")
  def name_error(self, stack, name):
    self.error(stack, "Name %r is not defined" % name)

  @_error_name("import-error")
  def import_error(self, stack, module_name):
    self.error(stack, "Can't find module %r." % module_name)

  @_error_name("missing-typing-dependency")
  def missing_typing_dependency(self):
    self.error(None, "Can't find module `typing`.")

  def _explain_protocol_mismatch(self, protocol_param, passed_params):
    """Return possibly extra protocol details about an argument mismatch."""
    if not protocol_param:
      return []
    vm = protocol_param.expected.vm
    if not vm.matcher.is_protocol(protocol_param.expected):
      return []
    p = None  # make pylint happy
    for name, p in passed_params:
      if name == protocol_param.name:
        break
    else:
      return []
    methods = vm.matcher.unimplemented_protocol_methods(
        p, protocol_param.expected)
    if not methods:
      # Happens if all the protocol methods are implemented, but with the wrong
      # types. We don't yet provide more detail about that.
      return []
    return [
        "\nYou may need to implement the following methods on %s:\n" %
        self._print_as_actual_type(p)] + [", ".join(sorted(methods))]

  def _invalid_parameters(self, stack, message, bad_call):
    """Log an invalid parameters error."""
    sig, passed_args, bad_param = bad_call
    expected = self._print_args(self._iter_expected(sig, bad_param), bad_param)
    actual = self._print_args(
        self._iter_actual(sig, passed_args, bad_param), bad_param)
    details = [
        "Expected: (", expected, ")\n",
        "Actually passed: (", actual,
        ")"]
    details += self._explain_protocol_mismatch(bad_param, passed_args)
    self.error(stack, message, "".join(details))

  @_error_name("wrong-arg-count")
  def wrong_arg_count(self, stack, name, bad_call):
    message = "Function %s expects %d arg(s), got %d" % (
        name, bad_call.sig.mandatory_param_count(), len(bad_call.passed_args))
    self._invalid_parameters(stack, message, bad_call)

  @_error_name("wrong-arg-types")
  def wrong_arg_types(self, stack, name, bad_call):
    """A function was called with the wrong parameter types."""
    message = "Function %s was called with the wrong arguments" % name
    self._invalid_parameters(stack, message, bad_call)

  @_error_name("wrong-keyword-args")
  def wrong_keyword_args(self, stack, name, bad_call, extra_keywords):
    """A function was called with extra keywords."""
    if len(extra_keywords) == 1:
      message = "Invalid keyword argument %s to function %s" % (
          extra_keywords[0], name)
    else:
      message = "Invalid keyword arguments %s to function %s" % (
          "(" + ", ".join(sorted(extra_keywords)) + ")", name)
    self._invalid_parameters(stack, message, bad_call)

  @_error_name("missing-parameter")
  def missing_parameter(self, stack, name, bad_call, missing_parameter):
    """A function call is missing parameters."""
    message = "Missing parameter %r in call to function %s" % (
        missing_parameter, name)
    self._invalid_parameters(stack, message, bad_call)

  @_error_name("not-callable")
  def not_callable(self, stack, function):
    """Calling an object that isn't callable."""
    message = "%r object is not callable" % (function.name)
    self.error(stack, message)

  @_error_name("not-indexable")
  def not_indexable(self, stack, name, generic_warning=False):
    message = "class %s is not indexable" % name
    if generic_warning:
      self.error(stack, message, "(%r does not subclass Generic)" % name)
    else:
      self.error(stack, message)

  @_error_name("not-instantiable")
  def not_instantiable(self, stack, cls):
    """Instantiating an abstract class."""
    message = "Can't instantiate %s with abstract methods %s" % (
        cls.full_name, ", ".join(sorted(cls.abstract_methods)))
    self.error(stack, message)

  @_error_name("ignored-abstractmethod")
  def ignored_abstractmethod(self, stack, cls_name, method_name):
    message = "Stray abc.abstractmethod decorator on method %s" % method_name
    self.error(stack, message,
               details="(%s does not have metaclass abc.ABCMeta)" % cls_name)

  @_error_name("none-attr")  # None doesn't have attribute '__call__'
  def none_not_callable(self, stack):
    """Calling None."""
    self.error(stack, "Calling a type that might be None",
               details="Do you need a type comment?")

  @_error_name("duplicate-keyword-argument")
  def duplicate_keyword(self, stack, name, bad_call, duplicate):
    message = ("function %s got multiple values for keyword argument %r" %
               (name, duplicate))
    self._invalid_parameters(stack, message, bad_call)

  def invalid_function_call(self, stack, error):
    if isinstance(error, abstract.WrongArgCount):
      self.wrong_arg_count(stack, error.name, error.bad_call)
    elif isinstance(error, abstract.WrongArgTypes):
      self.wrong_arg_types(stack, error.name, error.bad_call)
    elif isinstance(error, abstract.WrongKeywordArgs):
      self.wrong_keyword_args(
          stack, error.name, error.bad_call, error.extra_keywords)
    elif isinstance(error, abstract.MissingParameter):
      self.missing_parameter(
          stack, error.name, error.bad_call, error.missing_parameter)
    elif isinstance(error, abstract.NoneNotCallable):
      self.none_not_callable(stack)
    elif isinstance(error, abstract.NotCallable):
      self.not_callable(stack, error.obj)
    elif isinstance(error, abstract.DuplicateKeyword):
      self.duplicate_keyword(
          stack, error.name, error.bad_call, error.duplicate)
    else:
      raise AssertionError(error)

  @_error_name("base-class-error")
  def base_class_error(self, stack, base_var):
    base_cls = self._join_printed_types(
        self._print_as_expected_type(t) for t in base_var.data)
    self.error(stack, "Invalid base class: %s" % base_cls)

  @_error_name("bad-return-type")
  def bad_return_type(self, stack, actual_pytd, expected_pytd):
    details = "".join([
        "Expected: ", self._pytd_print(expected_pytd), "\n",
        "Actually returned: ", self._pytd_print(actual_pytd),
    ])
    self.error(stack, "bad option in return type", details)

  @_error_name("unsupported-operands")
  def unsupported_operands(self, stack, operation, var1, var2):
    left = self._join_printed_types(
        self._print_as_actual_type(t) for t in var1.data)
    right = self._join_printed_types(
        self._print_as_actual_type(t) for t in var2.data)
    # TODO(kramm): Display things like '__add__' as '+'
    self.error(stack, "unsupported operand type(s) for %s: %r and %r" % (
        operation, left, right))

  def invalid_annotation(self, stack, annot, details=None, name=None):
    self._invalid_annotation(stack, self._print_as_expected_type(annot),
                             details, name)

  def ambiguous_annotation(self, stack, options, name=None):
    desc = " or ".join(sorted(self._print_as_expected_type(o) for o in options))
    self._invalid_annotation(stack, desc, "Must be constant", name)

  @_error_name("invalid-annotation")
  def _invalid_annotation(self, stack, annot_string, details, name):
    if name is None:
      suffix = ""
    else:
      suffix = " for " + name
    self.error(stack, "Invalid type annotation %r%s" % (annot_string, suffix),
               details=details)

  @_error_name("mro-error")
  def mro_error(self, stack, name, mro_seqs):
    seqs = []
    for seq in mro_seqs:
      seqs.append("[%s]" % ", ".join(cls.name for cls in seq))
    self.error(stack, "Class %s has invalid (cyclic?) inheritance: %s." % (
        name, ", ".join(seqs)))

  @_error_name("invalid-directive")
  def invalid_directive(self, filename, lineno, message):
    self._add(Error(
        SEVERITY_WARNING, message, filename=filename, lineno=lineno))

  @_error_name("late-directive")
  def late_directive(self, filename, lineno, name):
    message = "%s disabled from here to the end of the file" % name
    details = ("Consider limiting this directive's scope or moving it to the "
               "top of the file.")
    self._add(Error(SEVERITY_WARNING, message, details=details,
                    filename=filename, lineno=lineno))

  @_error_name("not-supported-yet")
  def not_supported_yet(self, stack, feature):
    self.error(stack, "%s not supported yet" % feature)

  @_error_name("key-error")
  def key_error(self, stack, key):
    self.error(stack, "Key %r possibly not in dictionary (yet)" % key)

  @_error_name("python-compiler-error")
  def python_compiler_error(self, filename, lineno, message):
    self._add(Error(
        SEVERITY_ERROR, message, filename=filename, lineno=lineno))

  @_error_name("recursion-error")
  def recursion_error(self, stack, name):
    self.error(stack, "Detected recursion in %s" % name)

  @_error_name("redundant-function-type-comment")
  def redundant_function_type_comment(self, filename, lineno):
    self._add(Error(
        SEVERITY_ERROR,
        "Function type comments cannot be used with annotations",
        filename=filename, lineno=lineno))

  @_error_name("invalid-function-type-comment")
  def invalid_function_type_comment(self, stack, comment, details=None):
    self.error(stack, "Invalid function type comment: %s" % comment,
               details=details)

  @_error_name("invalid-type-comment")
  def invalid_type_comment(self, stack, comment, details=None):
    self.error(stack, "Invalid type comment: %s" % comment,
               details=details)

  @_error_name("ignored-type-comment")
  def ignored_type_comment(self, filename, lineno, comment):
    self._add(Error(
        SEVERITY_WARNING, "Stray type comment: %s" % comment,
        filename=filename, lineno=lineno))

  @_error_name("invalid-typevar")
  def invalid_typevar(self, stack, comment, bad_call=None):
    if bad_call:
      self._invalid_parameters(stack, comment, bad_call)
    else:
      self.error(stack, "Invalid TypeVar: %s" % comment)

  @_error_name("invalid-namedtuple-arg")
  def invalid_namedtuple_arg(self, stack, badname):
    msg = ("collections.namedtuple argument %r is not a valid typename or "
           "field name.")
    self.warn(stack, msg % badname)

  @_error_name("bad-function-defaults")
  def bad_function_defaults(self, stack, func_name):
    msg = "Attempt to set %s.__defaults__ to a non-tuple value."
    self.warn(stack, msg % func_name)

  @_error_name("bad-slots")
  def bad_slots(self, stack, msg):
    self.error(stack, msg)

  @_error_name("bad-unpacking")
  def bad_unpacking(self, stack, num_vals, num_vars):
    prettify = lambda v, label: "%d %s%s" % (v, label, "" if v == 1 else "s")
    vals_str = prettify(num_vals, "value")
    vars_str = prettify(num_vars, "variable")
    msg = "Cannot unpack %s into %s" % (vals_str, vars_str)
    self.error(stack, msg)

  @_error_name("reveal-type")
  def reveal_type(self, stack, node, var):
    types = [self._print_as_actual_type(b.data)
             for b in var.bindings
             if node.HasCombination([b])]
    self.error(stack, self._join_printed_types(types))
