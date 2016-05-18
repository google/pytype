"""Code and data structures for managing source directives."""

import collections
import re
import sys

_DIRECTIVE_RE = re.compile(r"#\s*(pytype|type)\s*:\s([^#]*)")
_COMMENT_ONLY_RE = re.compile(r"^\s*#")
_ALL_ERRORS = "*"  # Wildcard for disabling all errors.


class _DirectiveError(Exception):
  pass


class _LineSet(object):
  """A set of line numbers.

  The data structure is optimized to represent the union of a sparse set
  of integers and all integers greater than X.  This supports the two
  styles of directives: those after a statement apply only to that line
  and those on their own line apply until the end of the file.
  """

  def __init__(self):
    self._lines = set()  # Specific lines that belong to this set.
    # All lines strictly greater than limit are in the set.
    self._limit = sys.maxint

  def add(self, line, open_ended=False):
    """Add a line to the set.

    Args:
      line: A line number.
      open_ended: If False, then only line is added.  If True, then all lines
          greater than or equal to line are added.
    """
    if open_ended:
      self._limit = min(line - 1, self._limit)
    else:
      self._lines.add(line)

  def __contains__(self, line):
    """Return if a line is a memeber of the set."""
    return line > self._limit or line in self._lines


class Director(object):
  """Holds all of the directive information for a source file."""

  def __init__(self, src, errorlog, filename, disable):
    """Create a Director for a source file.

    Args:
      src:  The source text as a string.
      errorlog: An ErrorLog object.  Directive errors will be logged to the
          errorlog.
      filename: The name of the source file.
      disable: List of error messages to always ignore.
    """
    self._filename = filename
    self._errorlog = errorlog
    # Lines that have "type: ignore".  These will disable all errors, and in
    # the future may have other impact (such as not attempting an import).
    self._ignore = _LineSet()
    # Map from error name to lines for which that error is disabled.  Note
    # that _ALL_ERRORS is essentially a wildcard name (it matches all names).
    self._disables = collections.defaultdict(_LineSet)
    # Apply global disable, from the command line arguments:
    for error_name in disable:
      self._disables[error_name].add(0, open_ended=True)
    # Parse the source code for directives.
    self._parse_source(src)

  def _parse_source(self, src):
    """Parse a source file, extracting directives from comments."""
    for lineno, line in enumerate(src.splitlines(), 1):
      for tool, data in _DIRECTIVE_RE.findall(line):
        open_ended = bool(_COMMENT_ONLY_RE.match(line))
        data = data.strip()
        if tool == "type":
          self._process_type(lineno, data, open_ended)
        elif tool == "pytype":
          try:
            self._process_pytype(lineno, data, open_ended)
          except _DirectiveError as e:
            self._errorlog.invalid_directive(self._filename, lineno, e.message)
        else:
          pass  # ignore comments for other tools

  def _process_type(self, lineno, data, open_ended):
    """Process a type: comment."""
    if data == "ignore":
      self._ignore.add(lineno, open_ended=open_ended)

  def _process_pytype(self, lineno, data, open_ended):
    """Process a pytype: comment."""
    if not data:
      raise _DirectiveError("Invalid directive syntax.")
    for option in data.split():
      # Parse the command.
      try:
        command, values = option.split("=", 1)
        values = values.split(",")
      except ValueError:
        raise _DirectiveError("Invalid directive syntax.")
      # Additional commands may be added in the future.  For now, only
      # "disable" is supported.
      if command != "disable":
        raise _DirectiveError("Unknown pytype directive: '%s'" % command)
      if not values:
        raise _DirectiveError("Disable must specify one or more error names.")
      for error_name in values:
        if (error_name == _ALL_ERRORS or
            self._errorlog.is_valid_error_name(error_name)):
          self._disables[error_name].add(lineno, open_ended=open_ended)
        else:
          self._errorlog.invalid_directive(
              self._filename, lineno, "Invalid error name: '%s'" % error_name)

  def should_report_error(self, error):
    """Return whether the error should be logged.

    This method is suitable for use as an error filter.

    Args:
      error: An error._Error object.

    Returns:
      True iff the error should be included in the log.
    """
    # Always report errors that aren't for this file or do not have a line
    # number.
    if error.filename != self._filename or error.lineno is None:
      return True
    # Report the error if it isn't subject to any ignore or disable.
    lineno = error.lineno
    return (lineno not in self._ignore and
            lineno not in self._disables[_ALL_ERRORS] and
            lineno not in self._disables[error.name])
