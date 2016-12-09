"""Code and data structures for managing source directives."""

import bisect
import collections
import re
import sys

_DIRECTIVE_RE = re.compile(r"^[^#]*#\s*(pytype|type)\s*:\s([^#]*)")
_COMMENT_ONLY_RE = re.compile(r"^\s*#")
_ALL_ERRORS = "*"  # Wildcard for disabling all errors.


class _DirectiveError(Exception):
  pass


class _LineSet(object):
  """A set of line numbers.

  The data structure is optimized to represent the union of a sparse set
  of integers and ranges of non-negative integers.  This supports the two styles
  of directives: those after a statement apply only to that line and those on
  their own line apply until countered by the opposing directive.
  """

  def __init__(self):
    # Map of line->bool for specific lines, takes precedence over _transitions.
    self._lines = {}
    # A sorted list of the lines at which the range state changes
    # polarity.  It is assumed to initially be false (not in a range).
    # Even positions represent the start of a range, odd positions represent
    # the end of a range.  Thus [2, 5, 10, 12] would include lines 2, 3, 4, 10,
    # and 11.  If the length is odd, then an end of maxint is implied, thus
    # [2, 5, 10] would disable lines 2, 3, 4, 10, 11, 12, ...
    self._transitions = []

  def set_line(self, line, membership):
    """Set whether a given line is a member of the set."""
    self._lines[line] = membership

  def start_range(self, line, membership):
    """Start a range of lines that are either included/excluded from the set.

    Args:
      line: A line number.
      membership: If True, lines >= line are included in the set (starting
        a range), otherwise they are excluded (ending a range).

    Raises:
      ValueError: if line is less than that of a previous call to start_range().
    """
    last = self._transitions[-1] if self._transitions else -1
    # Assert that lines are monotonically increasing.  This simplifies the
    # logic of adding new lines and ensures that _ranges is sorted.
    if line < last:
      raise ValueError("Line number less than previous start_range() call.")
    # Determine previous membership state (True if the last range has an
    # indefinite end).
    previous = (len(self._transitions) % 2) == 1
    if membership == previous:
      # TODO(dbaum): Consider issuing a warning here.
      return  # Redundant with previous state, do nothing.
    elif line == last:
      # We have either enable/disable or disable/enable on the same line,
      # cancel them out by popping the previous transition.
      self._transitions.pop()
    else:
      # Normal case - add a transition at this line.
      self._transitions.append(line)

  def __contains__(self, line):
    """Return if a line is a member of the set."""
    # First check for an entry in _lines.
    specific = self._lines.get(line)
    if specific is not None:
      return specific
    # Find the position in _ranges for line.  The polarity of this position
    # determines whether we are inside a range (odd) or outside (even).
    pos = bisect.bisect(self._transitions, line)
    return (pos % 2) == 1


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
    self._type_comments = {}  # Map from line number to type comment text.
    # Lines that have "type: ignore".  These will disable all errors, and in
    # the future may have other impact (such as not attempting an import).
    self._ignore = _LineSet()
    # Map from error name to lines for which that error is disabled.  Note
    # that _ALL_ERRORS is essentially a wildcard name (it matches all names).
    self._disables = collections.defaultdict(_LineSet)
    # Apply global disable, from the command line arguments:
    for error_name in disable:
      self._disables[error_name].start_range(0, True)
    # Parse the source code for directives.
    self._parse_source(src)

  @property
  def type_comments(self):
    return self._type_comments

  def _parse_source(self, src):
    """Parse a source file, extracting directives from comments."""
    for lineno, line in enumerate(src.splitlines(), 1):
      m = _DIRECTIVE_RE.match(line)
      if m:
        tool, data = m.groups()
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
      if open_ended:
        self._ignore.start_range(lineno, True)
      else:
        self._ignore.set_line(lineno, True)
    else:
      self._type_comments[lineno] = data.strip()

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
      # "disable" and "enable" are supported.
      if command == "disable":
        disable = True
      elif command == "enable":
        disable = False
      else:
        raise _DirectiveError("Unknown pytype directive: '%s'" % command)
      if not values:
        raise _DirectiveError(
            "Disable/enable must specify one or more error names.")
      for error_name in values:
        if (error_name == _ALL_ERRORS or
            self._errorlog.is_valid_error_name(error_name)):
          lines = self._disables[error_name]
          if open_ended:
            lines.start_range(lineno, disable)
          else:
            lines.set_line(lineno, disable)
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
    # Treat lineno=0 as below the file, so we can filter it.
    lineno = error.lineno or sys.maxint
    # Report the error if it isn't subject to any ignore or disable.
    return (lineno not in self._ignore and
            lineno not in self._disables[_ALL_ERRORS] and
            lineno not in self._disables[error.name])
