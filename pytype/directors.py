"""Code and data structures for managing source directives."""

import bisect
import collections
import re
import sys
import tokenize

from pytype import utils
from six import moves

_DIRECTIVE_RE = re.compile(r"#\s*(pytype|type)\s*:\s([^#]*)")
_CLOSING_BRACKETS_RE = re.compile(r"^(\s*[]})]\s*)+(#.*)?$")
_WHITESPACE_RE = re.compile(r"^\s*(#.*)?$")
_CLASS_OR_FUNC_RE = re.compile(r"^(def|class)\s")
_ALL_ERRORS = "*"  # Wildcard for disabling all errors.


class _DirectiveError(Exception):
  pass


class SkipFile(Exception):
  """Exception thrown if we encounter "pytype: skip-file" in the source code."""


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

  def get_disable_after(self, lineno):
    """Get an unclosed disable, if any, that starts after lineno."""
    if len(self._transitions) % 2 == 1 and self._transitions[-1] >= lineno:
      return self._transitions[-1]
    return None


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
    self._type_comments = {}  # Map from line number to (code, comment).
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

  @property
  def ignore(self):
    return self._ignore

  def _adjust_type_comments(self, closing_bracket_lines, whitespace_lines):
    """Adjust any type comments affected by closing bracket lines.

    Lines that contain nothing but closing brackets don't appear in the
    bytecode, so for, e.g.,
      v = [
        "hello",
        "world",
      ]  # line 4
    line 4 is where any type comment for 'v' should be put, but the
    STORE_NAME opcode for 'v' is at line 3. If we find a type comment put
    (wrongly) on line 3, we'll report an error, and if we find a type comment
    on line 4, we'll move it to line 3.

    Args:
      closing_bracket_lines: A set of lines containing only closing brackets,
        to be used for adjusting affected type comments.
      whitespace_lines: A set of lines containing only whitespace. Its union
        with closing_bracket_lines is a set of consecutive lines.
    """
    target = min(closing_bracket_lines | whitespace_lines) - 1
    if target in self._type_comments:
      self._errorlog.ignored_type_comment(
          self._filename, target, self._type_comments[target][1])
      del self._type_comments[target]
    end = max(closing_bracket_lines)
    if end in self._type_comments:
      self._type_comments[target] = self._type_comments[end]
      del self._type_comments[end]

  def _parse_source(self, src):
    """Parse a source file, extracting directives from comments."""
    f = moves.cStringIO(src)
    defs_start = None
    closing_bracket_lines = set()
    whitespace_lines = set()
    for tok, _, start, _, line in tokenize.generate_tokens(f.readline):
      lineno, col = start
      if defs_start is None and _CLASS_OR_FUNC_RE.match(line):
        defs_start = lineno
      if _CLOSING_BRACKETS_RE.match(line):
        closing_bracket_lines.add(lineno)
      elif _WHITESPACE_RE.match(line):
        whitespace_lines.add(lineno)
      else:
        if closing_bracket_lines:
          self._adjust_type_comments(closing_bracket_lines, whitespace_lines)
        closing_bracket_lines.clear()
        whitespace_lines.clear()
      if tok == tokenize.COMMENT:
        matches = list(_DIRECTIVE_RE.finditer(line[col:]))
        is_nested = bool(matches) and matches[0].start(0) > 0
        for m in matches:
          code = line[:col].strip()
          tool, data = m.groups()
          open_ended = not code
          data = data.strip()
          if tool == "type":
            self._process_type(lineno, code, data, is_nested)
          elif tool == "pytype":
            try:
              self._process_pytype(lineno, data, open_ended)
            except _DirectiveError as e:
              self._errorlog.invalid_directive(
                  self._filename, lineno, utils.message(e))
          else:
            pass  # ignore comments for other tools
    if closing_bracket_lines:
      self._adjust_type_comments(closing_bracket_lines, whitespace_lines)
    if defs_start is not None:
      disables = list(self._disables.items())
      # Add "# type: ignore" to the list of disables that we check.
      disables.append(("Type checking", self._ignore))
      for name, lineset in disables:
        lineno = lineset.get_disable_after(defs_start)
        if lineno is not None:
          self._errorlog.late_directive(self._filename, lineno, name)

  def _process_type(self, lineno, code, data, is_nested):
    """Process a type: comment."""
    # Discard type comments embedded in larger whole-line comments.
    if not code and is_nested:
      return
    if lineno in self._type_comments:
      # If we have multiple type comments on the same line, take the last one,
      # but add an error to the log.
      self._errorlog.invalid_directive(
          self._filename, lineno,
          "Multiple type comments on the same line.")
    if data == "ignore":
      if not code:
        self._ignore.start_range(lineno, True)
      else:
        self._ignore.set_line(lineno, True)
    else:
      self._type_comments[lineno] = (code, data)

  def _process_pytype(self, lineno, data, open_ended):
    """Process a pytype: comment."""
    if not data:
      raise _DirectiveError("Invalid directive syntax.")
    for option in data.split():
      # Parse the command.
      if option == "skip-file":
        raise SkipFile()
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
    lineno = error.lineno or sys.maxsize
    # Report the error if it isn't subject to any ignore or disable.
    return (lineno not in self._ignore and
            lineno not in self._disables[_ALL_ERRORS] and
            lineno not in self._disables[error.name])
