"""LibCST-based parser."""

import collections
import dataclasses
import logging
import re

import libcst
from pytype import utils

log = logging.getLogger(__name__)

# Also supports mypy-style ignore[code, ...] syntax, treated as regular ignores.
IGNORE_RE = re.compile(r"^ignore(\[.+\])?$")

_DIRECTIVE_RE = re.compile(r"#\s*(pytype|type)\s*:\s?([^#]*)")


class SkipFileError(Exception):
  """Exception thrown if we encounter "pytype: skip-file" in the source code."""


@dataclasses.dataclass(frozen=True)
class LineRange:
  start_line: int
  end_line: int

  def __contains__(self, line):
    return self.start_line <= line <= self.end_line


@dataclasses.dataclass(frozen=True)
class Call(LineRange):
  """Tag to identify function calls."""


@dataclasses.dataclass(frozen=True)
class _StructuredComment:
  """A structured comment.

  Attributes:
    line: The line number.
    tool: The tool label, e.g., "type" for "# type: int".
    data: The data, e.g., "int" for "# type: int".
    open_ended: True if the comment appears on a line by itself (i.e., it is
     open-ended rather than attached to a line of code).
  """
  line: int
  tool: str
  data: str
  open_ended: bool


@dataclasses.dataclass(frozen=True)
class _VariableAnnotation(LineRange):
  annotation: str


class _BlockReturns:
  """Tracks return statements in with/try blocks."""

  def __init__(self):
    self._block_ranges = []
    self._returns = []
    self._block_returns = {}

  def add_return(self, pos):
    self._returns.append(pos.start.line)

  def all_returns(self):
    return set(self._returns)

  def __iter__(self):
    return iter(self._block_returns.items())

  def __repr__(self):
    return f"""
      Blocks: {self._block_ranges}
      Returns: {self._returns}
      {self._block_returns}
    """


class _Matches:
  """Tracks branches of match statements."""

  def __init__(self):
    self.start_to_end = {}
    self.end_to_starts = collections.defaultdict(list)
    self.match_cases = {}

  def add_match(self, start, end, cases):
    self.start_to_end[start] = end
    self.end_to_starts[end].append(start)
    for case_start, case_end in cases:
      for i in range(case_start, case_end + 1):
        self.match_cases[i] = start

  def __repr__(self):
    return f"""
      Matches: {sorted(self.start_to_end.items())}
      Cases: {self.match_cases}
    """


class _ParseVisitor(libcst.CSTVisitor):
  """Visitor for parsing a source tree.

  Attributes:
    structured_comment_groups: Ordered map from a line range to the "type:" and
      "pytype:" comments within the range. Line ranges come in several flavors:
      * Instances of the base LineRange class represent single logical
        statements. These ranges are ascending and non-overlapping and record
        all structured comments found.
      * Instances of the Call subclass represent function calls. These ranges
        are ascending by start_line but may overlap and only record "pytype:"
        comments.
    variable_annotations: Sequence of PEP 526-style variable annotations with
      line numbers.
    decorators: Sequence of lines at which decorated functions are defined.
    defs_start: The line number at which the first class or function definition
      appears, if any.
  """

  METADATA_DEPENDENCIES = (libcst.metadata.PositionProvider,
                           libcst.metadata.ParentNodeProvider,)

  def __init__(self):
    self.structured_comment_groups = collections.OrderedDict()
    self.variable_annotations = []
    self.decorators = []
    self.defs_start = None
    self.function_ranges = {}
    self.block_returns = _BlockReturns()
    self.matches = _Matches()

  def _get_containing_groups(self, start_line, end_line=None):
    """Get _StructuredComment groups that fully contain the given line range."""
    end_line = end_line or start_line
    # Since the visitor processes the source file roughly from top to bottom,
    # the given line range should be within a recently added comment group. We
    # also keep the groups ordered. So we do a reverse search and stop as soon
    # as we hit a statement that does not overlap with our given range.
    for line_range, group in reversed(self.structured_comment_groups.items()):
      if (line_range.start_line <= start_line and
          end_line <= line_range.end_line):
        yield (line_range, group)
      elif (not isinstance(line_range, Call) and
            line_range.end_line < start_line):
        return

  def _has_containing_group(self, start_line, end_line=None):
    for line_range, _ in self._get_containing_groups(start_line, end_line):
      if not isinstance(line_range, Call):
        return True
    return False

  def _add_structured_comment_group(self, start_line, end_line, cls=LineRange):
    """Adds an empty _StructuredComment group with the given line range."""
    if cls is LineRange and self._has_containing_group(start_line, end_line):
      return
    # We keep structured_comment_groups ordered by inserting the new line range
    # at the end, then absorbing line ranges that the new range contains and
    # calling move_to_end() on ones that should come after it. We encounter line
    # ranges in roughly ascending order, so this reordering is not expensive.
    keys_to_absorb = []
    keys_to_move = []
    for line_range in reversed(self.structured_comment_groups):
      if (cls is LineRange and
          start_line <= line_range.start_line and
          line_range.end_line <= end_line):
        if type(line_range) is LineRange:  # pylint: disable=unidiomatic-typecheck
          keys_to_absorb.append(line_range)
        else:
          keys_to_move.append(line_range)
      elif line_range.start_line > start_line:
        keys_to_move.append(line_range)
      else:
        break
    self.structured_comment_groups[cls(start_line, end_line)] = new_group = []
    for k in reversed(keys_to_absorb):
      new_group.extend(self.structured_comment_groups[k])
      del self.structured_comment_groups[k]
    for k in reversed(keys_to_move):
      self.structured_comment_groups.move_to_end(k)

  def _process_comment(self, line, comment, open_ended):
    """Process a single comment."""
    matches = list(_DIRECTIVE_RE.finditer(comment))
    if not matches:
      return
    is_nested = matches[0].start(0) > 0
    for m in matches:
      tool, data = m.groups()
      assert data is not None
      data = data.strip()
      if tool == "pytype" and data == "skip-file":
        # Abort immediately to avoid unnecessary processing.
        raise SkipFileError()
      if tool == "type" and open_ended and is_nested:
        # Discard type comments embedded in larger whole-line comments.
        continue
      structured_comment = _StructuredComment(line, tool, data, open_ended)
      for line_range, group in self._get_containing_groups(line):
        if not isinstance(line_range, Call):
          # A structured comment belongs to exactly one logical statement.
          group.append(structured_comment)
          break
        elif not open_ended and (
            tool == "pytype" or (tool == "type" and IGNORE_RE.match(data))):
          # A "type: ignore" or "pytype:" comment can additionally belong to any
          # number of overlapping function calls.
          group.append(structured_comment)
      else:
        raise AssertionError("Could not find a line range for comment "
                             f"{structured_comment} on line {line}")

  def _get_position(self, node):
    return self.get_metadata(libcst.metadata.PositionProvider, node)

  # Comments are found inside TrailingWhitespace and EmptyLine nodes. We visit
  # all the nodes that can contain a TrailingWhitespace node and add a comment
  # group for each of them, then populate the groups with TrailingWhitespace
  # comments. EmptyLine comments form their own single-line groups. Note that
  # comment.start should be used to get the line at which a comment is located;
  # comment.end is at column 0 of the following line.

  def _visit_comment_owner(self, node, cls=LineRange):
    pos = self._get_position(node)
    self._add_structured_comment_group(pos.start.line, pos.end.line, cls)

  def visit_Decorator(self, node):
    self._visit_comment_owner(node)

  def visit_SimpleStatementLine(self, node):
    self._visit_comment_owner(node)

  def visit_SimpleStatementSuite(self, node):
    self._visit_comment_owner(node)

  def visit_IndentedBlock(self, node):
    # An indented block has a "header" child that holds any trailing comment
    # from the block's header, e.g.:
    #   if __random__:  # header comment
    #     indented_block
    # The comment's line range goes from the first line of the header to the
    # comment line.
    parent = self.get_metadata(libcst.metadata.ParentNodeProvider, node)
    # visit_FunctionDef takes care of adding line ranges for FunctionDef.
    if not isinstance(parent, libcst.FunctionDef):
      start = self._get_position(parent).start
      end = self._get_position(node.header).start
      self._add_structured_comment_group(start.line, end.line)

  def visit_ParenthesizedWhitespace(self, node):
    self._visit_comment_owner(node)

  def visit_Call(self, node):
    self._visit_comment_owner(node, cls=Call)

  def visit_Comparison(self, node):
    self._visit_comment_owner(node, cls=Call)

  def visit_Subscript(self, node):
    self._visit_comment_owner(node, cls=Call)

  def visit_TrailingWhitespace(self, node):
    if node.comment:
      line = self._get_position(node).start.line
      self._process_comment(line, node.comment.value, open_ended=False)

  def visit_EmptyLine(self, node):
    if node.comment:
      line = self._get_position(node).start.line
      self._add_structured_comment_group(line, line)
      self._process_comment(line, node.comment.value, open_ended=True)

  def visit_AnnAssign(self, node):
    if not node.value:
      # vm.py preprocesses the source code so that all annotations in function
      # bodies have values. So the only annotations without values are module-
      # and class-level ones, which generate STORE opcodes and therefore
      # don't need to be handled here.
      return
    pos = self._get_position(node)
    # Gets a string representation of the annotation.
    annotation = re.sub(
        r"\s*(#.*)?\n\s*", "",
        libcst.Module([node.annotation.annotation]).code)
    self.variable_annotations.append(
        _VariableAnnotation(pos.start.line, pos.end.line, annotation))

  def visit_Return(self, node):
    self.block_returns.add_return(self._get_position(node))

  def _visit_decorators(self, node):
    if not node.decorators:
      return
    # The line range for this definition starts at the beginning of the last
    # decorator and ends at the definition's name.
    decorator = node.decorators[-1]
    start = self._get_position(decorator).start
    end = self._get_position(node.name).start
    self.decorators.append(LineRange(start.line, end.line))

  def _visit_def(self, node):
    line = self._get_position(node).start.line
    if not self.defs_start or line < self.defs_start:
      self.defs_start = line

  def visit_ClassDef(self, node):
    self._visit_decorators(node)
    self._visit_def(node)

  def visit_FunctionDef(self, node):
    # A function signature's line range starts at the beginning of the signature
    # and ends at the final colon.
    pos = self._get_position(node)
    self._add_structured_comment_group(
        pos.start.line,
        self._get_position(node.whitespace_before_colon).end.line)
    self._visit_decorators(node)
    self._visit_def(node)
    self.function_ranges[pos.start.line] = pos.end.line


def parse_src(src, python_version):
  """Parses a string of source code into a LibCST tree."""
  assert python_version < (3, 9)
  version_str = utils.format_version(python_version)
  config = libcst.PartialParserConfig(python_version=version_str)
  src_tree = libcst.parse_module(src, config)
  # The docstring for unsafe_skip_copy says:
  #
  # When true, this skips the deep cloning of the module.
  # This can provide a small performance benefit, but you should only use this
  # if you know that there are no duplicate nodes in your tree (e.g. this
  # module came from the parser).
  #
  # We only pass in trees constructed by libcst.parse_module, so we disable
  # copying for the performance benefit.
  return libcst.metadata.MetadataWrapper(src_tree, unsafe_skip_copy=True)


def visit_src_tree(src_tree):
  visitor = _ParseVisitor()
  try:
    src_tree.visit(visitor)
  except RecursionError:
    log.warning("File parsing failed. Comment directives and some variable "
                "annotations will be ignored.")
    return None
  return visitor
