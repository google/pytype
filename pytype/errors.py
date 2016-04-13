"""Code and data structures for storing and displaying errors."""

import os
import StringIO
import sys


from pytype import abstract
from pytype import utils
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils


# "Error level" enum for distinguishing between warnings and errors:
SEVERITY_WARNING = 1
SEVERITY_ERROR = 2

# The set of known error names.
_ERROR_NAMES = set()

# The current error name, managed by the error_name decorator.
_CURRENT_ERROR_NAME = utils.DynamicVar()


def _error_name(name):
  """Decorate a function so that it binds the current error name."""
  _ERROR_NAMES.add(name)
  def wrap(func):
    def invoke(*args, **kwargs):
      with _CURRENT_ERROR_NAME.bind(name):
        return func(*args, **kwargs)
    return invoke
  return wrap


class CheckPoint(object):
  """Represents a position in an error log."""

  def __init__(self, log, position):
    self.log = log
    self.position = position


class Error(object):
  """Representation of an error in the error log."""

  def __init__(self, severity, filename, lineno, column,
               methodname, linetext, message):
    self.severity = severity
    self.filename = filename
    self.lineno = lineno
    self.column = column
    self.methodname = methodname
    self.linetext = linetext
    self.message = message

  @property
  def lineno(self):
    return self._lineno

  @property
  def filename(self):
    return self._filename

  def _position(self):
    """Return human-readable filename + line number."""
    method = ", in %s" % self.methodname if self.methodname else ""

    if self.filename:
      filename = os.path.basename(self.filename)
      return "File \"%s\", line %d%s" % (filename,
                                         self.lineno,
                                         method)
    elif self.lineno:
      return "Line %d%s" % (self.lineno, method)
    else:
      return ""

  def __str__(self):
    pos = self.position()
    return (pos + ": " if pos else "") + self.message.replace("\n", "\n  ")


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
      self._errors.append(error)

  def _add(self, severity, opcode, message, args):
    self.errors.append(Error(
        severity=severity,
        filename=opcode.code.co_filename if opcode else None,
        lineno=opcode.line if opcode else None,
        column=None,
        methodname=opcode.code.co_name if opcode else None,
        linetext=None,
        message=message % args))

  def warn(self, opcode, message, *args):
    self._add(SEVERITY_WARNING, opcode, message, args)

  def error(self, opcode, message, *args):
    self._add(SEVERITY_ERROR, opcode, message, args)

  def save(self):
    """Returns a checkpoint that represents the log messages up to now."""
    return CheckPoint(self, len(self._errors))

  def revert_to(self, checkpoint):
    assert checkpoint.log is self
    self._errors = self._errors[:checkpoint.position]

  def print_to_file(self, fi):
    seen = set()
    for error in self.sorted_errors():
      text = str(error)
      if text not in seen:
        print >>fi, error
        seen.add(text)

  def sorted_errors(self):
    # pylint: disable=protected-access
    return sorted(self._errors,
                  key=lambda x: (x._filename, x._lineno))

  def print_to_stderr(self):
    self.print_to_file(sys.stderr)

  def __str__(self):
    io = StringIO.StringIO()
    self.print_to_file(io)
    return io.getvalue()


class ErrorLog(ErrorLogBase):
  """ErrorLog with convenience functions."""

  def pyi_error(self, e):
    self.errors.append(Error(
        severity=SEVERITY_ERROR,
        filename=e.filename,
        lineno=e.lineno,
        column=e.column,
        methodname=None,
        linetext=e.line,
        message=e.msg))

  def attribute_error(self, opcode, obj, attr_name):
    on = " on %s" % obj.data[0].name if obj.bindings else ""
    self.error(opcode, "No attribute %r%s" % (attr_name, on))

  @_error_name("name-error")
  def name_error(self, opcode, name):
    self.error(opcode, "Name %r is not defined" % name)

  @_error_name("import-error")
  def import_error(self, opcode, module_name):
    self.error(opcode, "Can't find module %r." % module_name)

  @_error_name("import-error")
  def import_from_error(self, opcode, module, name):
    module_name = module.data[0].name
    self.error(opcode, "Can't find %s.%s" % (module_name, name))

  @_error_name("wrong-arg-count")
  def wrong_arg_count(self, opcode, sig, call_arg_count):
    self.error(
        opcode,
        "Function %s was called with %d args instead of expected %d" % (
            sig.name, call_arg_count, sig.mandatory_param_count())
        )

  def _prettyprint_arg(self, arg):
    return re.sub(r"~unknown\d*", "?", arg.name)

  @_error_name("wrong-arg-types")
  def wrong_arg_types(self, opcode, sig, passed_args):
    """A function was called with the wrong parameter types."""
    message = "".join([
        "Function %s was called with the wrong arguments\n" % sig.name,
        "Expected: (", str(sig), ")\n",
        "Actually passed: (",
        ", ".join("%s: %s" % (name, arg.name)
                  for name, arg in zip(sig.param_names, passed_args)),
        ")"])
    self.error_with_details(opcode, message, details)

  @_error_name("wrong-keyword-args")
  def wrong_keyword_args(self, opcode, sig, extra_keywords):
    """A function was called with extra keywords."""
    if len(extra_keywords) == 1:
      message = "Invalid keyword argument %s to function %s" % (
          extra_keywords[0], sig.name)
    else:
      message = "Invalid keyword arguments %s to function %s" % (
          "(" + ", ".join(extra_keywords) + ")", sig.name)
    self.error(opcode, message)

  @_error_name("missing-parameter")
  def missing_parameter(self, opcode, sig, missing_parameter):
    """A function call is missing parameters."""
    message = "Missing parameter %r in call to function %s" % (
        missing_parameter, sig.name)
    self.error(opcode, message)

  @_error_name("not-callable")
  def not_callable(self, opcode, function):
    """Calling an object that isn't callable."""
    message = "%r object is not callable" % (function.name)
    self.error(opcode, message)

  def wrong_keyword_args(self, opcode, sig, extra_keywords):
    """A function was called with extra keywords."""
    if len(extra_keywords) == 1:
      message = "Invalid keyword argument %s to function %s\n" % (
          extra_keywords[0], sig.name)
    else:
      message = "Invalid keyword arguments %s to function %s\n" % (
          "(" + ", ".join(extra_keywords) + ")", sig.name)
    self.error(opcode, message)

  def missing_parameter(self, opcode, sig, missing_parameter):
    """A function call is missing parameters."""
    message = "Missing parameter %r in call to function %s\n" % (
        missing_parameter, sig.name)
    self.error(opcode, message)

  def invalid_function_call(self, opcode, error):
    if isinstance(error, abstract.WrongArgCount):
      self.wrong_arg_count(opcode, error.sig, error.call_arg_count)
    elif isinstance(error, abstract.WrongArgTypes):
      self.wrong_arg_types(opcode, error.sig, error.passed_args)
    elif isinstance(error, abstract.WrongKeywordArgs):
      self.wrong_keyword_args(opcode, error.sig, error.extra_keywords)
    elif isinstance(error, abstract.MissingParameter):
      self.missing_parameter(opcode, error.sig, error.missing_parameter)
    else:
      raise AssertionError(error)

  @_error_name("index-error")
  def index_error(self, opcode, container, unused_index):
    if container.data:
      out_of = " out of %s" % container.data[0].name
    else:
      out_of = ""
    self.error(opcode, "Can't retrieve item%s. Empty?",
               out_of)

  @_error_name("super-error")
  def super_error(self, opcode, arg_count):
    self.error(opcode, "super() takes one or two arguments. %d given.",
               arg_count)

  @_error_name("base-class-error")
  def base_class_error(self, opcode, base_var):
    pytd_type = pytd_utils.JoinTypes(t.get_instance_type()
                                     for t in base_var.data)
    self.error(opcode, "Invalid base class: %s", pytd.Print(pytd_type))

  @_error_name("missing-definition")
  def missing_definition(self, item, pytd_filename, py_filename):
    self.error(None, "%s %s declared in pytd %s, but not defined in %s",
               type(item).__name__, item.name, pytd_filename, py_filename)

  @_error_name("bad-return-type")
  def bad_return_type(self, opcode, unused_function, actual, expected):
    self.error(opcode, "return type is %s, should be %s",
               pytd.Print(actual.to_type()),
               pytd.Print(expected))

  @_error_name("unsupported-operands")
  def unsupported_operands(self, opcode, operation, var1, var2):
    left = pytd_utils.JoinTypes(t.to_type() for t in var1.data)
    right = pytd_utils.JoinTypes(t.to_type() for t in var2.data)
    # TODO(kramm): Display things like '__add__' as '+'
    self.error(opcode, "unsupported operand type(s) for %s: %r and %r" % (
        operation, pytd.Print(left), pytd.Print(right)))

  def invalid_annotation(self, opcode, name):
    self.error(opcode, "Invalid type annotation for %s. Must be constant" %
               name)
