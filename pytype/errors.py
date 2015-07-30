"""Code and data structures for storing and displaying errors."""

import os
import sys


from pytype import abstract
from pytype.pytd import pytd


# "Error level" enum for distinguishing between warnings and errors:
SEVERITY_WARNING = 1
SEVERITY_ERROR = 2


class CheckPoint(object):
  """Represents a position in an error log."""

  def __init__(self, log, position):
    self.log = log
    self.position = position


class Error(object):
  """Representation of an error in the error log."""

  def __init__(self, severity, opcode, message):
    self.severity = severity
    self.opcode = opcode
    self.message = message

  def position(self):
    """Return human-readable filename + line number."""
    if self.opcode.code.co_filename:
      filename = os.path.basename(self.opcode.code.co_filename)
      return "File \"%s\", line %d, in %s" % (filename,
                                              self.opcode.line,
                                              self.opcode.code.co_name)
    else:
      return "Line %d, in %s" % (self.opcode.line, self.opcode.code.co_name)

  def __str__(self):
    return self.position() + ":\n  " + self.message.replace("\n", "\n  ")


class ErrorLogBase(object):
  """A stream of errors."""

  def __init__(self):
    self.errors = []

  def warn(self, opcode, message, *args):
    self.errors.append(Error(SEVERITY_WARNING, opcode, message % args))

  def error(self, opcode, message, *args):
    self.errors.append(Error(SEVERITY_ERROR, opcode, message % args))

  def save(self):
    """Returns a checkpoint that represents the log messages up to now."""
    return CheckPoint(self, len(self.errors))

  def revert_to(self, checkpoint):
    assert checkpoint.log is self
    self.errors = self.errors[:checkpoint.position]

  def print_to_file(self, fi):
    for error in self.errors:
      print >>fi, error

  def print_to_stderr(self):
    self.print_to_file(sys.stderr)


class ErrorLog(ErrorLogBase):
  """ErrorLog with convenience functions."""

  def attribute_error(self, opcode, obj, attr_name):
    on = " on %s" % obj.data[0].name if obj.values else ""
    self.error(opcode, "No attribute %r%s" % (attr_name, on))

  def import_error(self, opcode, module_name):
    self.error(opcode, "Can't find module %r" % module_name)

  def wrong_arg_count(self, opcode, sig, call_arg_count):
    self.error(
        opcode,
        "Function %s was called with %d args instead of expected %d" % (
            (sig.name, call_arg_count, len(sig.get_parameter_names())))
        )

  def wrong_arg_types(self, opcode, sig, passed_args):
    """A function was called with the wrong parameter types."""
    message = "".join([
        "Function %s was called with the wrong arguments\n" % sig.name,
        "Expected: (",
        ", ".join("%s: %s" % (p.name, pytd.Print(p.type))
                  for p in sig.pytd_sig.params),
        ")\n",
        "Actually passed: (",
        ", ".join("%s: %s" % (name, arg.name)
                  for name, arg in zip(sig.get_parameter_names(), passed_args)),
        ")"])
    self.error(opcode, message)

  def invalid_function_call(self, opcode, error):
    if isinstance(error, abstract.WrongArgCount):
      self.wrong_arg_count(opcode, error.sig, error.call_arg_count)
    elif isinstance(error, abstract.WrongArgTypes):
      self.wrong_arg_types(opcode, error.sig, error.passed_args)
    else:
      raise AssertionError(error)

  def index_error(self, opcode, container, unused_index):
    if container.data:
      out_of = " out of %s" % container.data[0].name
    else:
      out_of = ""
    self.error(opcode, "Can't retrieve item%s. Empty?",
               out_of)

