# Lint as: python2, python3
"""Source and trace information."""

from __future__ import print_function
import collections

Location = collections.namedtuple("Location", ("line", "column"))


class Code(object):
  """Line-based source code access."""

  def __init__(self, src, raw_traces, filename):
    self.text = src
    self.traces = _collect_traces(raw_traces)
    self.filename = filename
    self._lines = src.split("\n")
    self._offsets = []
    self._init_byte_offsets()

  def _init_byte_offsets(self):
    offset = 0
    for line in self._lines:
      self._offsets.append(offset)
      offset += len(line) + 1  # account for the \n

  def get_offset(self, location):
    return self._offsets[location.line - 1] + location.column

  def line(self, n):
    """Index source lines from 1."""
    return self._lines[n - 1]

  def get_closest_line_range(self, start, end):
    """Get as close as we can to the given range without going out of bounds."""
    return range(start, min(end, len(self._lines)))

  def find_text(self, start_line, end_line, text):
    """Find text within a range of lines."""

    for l in self.get_closest_line_range(start_line, end_line):
      col = self.line(l).find(text)
      if col > -1:
        # TODO(mdemello): Temporary hack, replace with a token stream!
        # This will break if we have a # in a string before our desired text.
        comment_marker = self.line(l).find("#")
        if -1 < comment_marker < col:
          continue
        return Location(l, col)
    return None

  def next_non_comment_line(self, line):
    for l in range(line + 1, len(self._lines)):
      if self.line(l).lstrip().startswith("#"):
        continue
      return l
    return None

  def display_traces(self):
    """Debug printing of source + traces per line."""
    for line in sorted(self.traces):
      print("%d %s" % (line, self.line(line)))
      for name, symbol, data in self.traces[line]:
        data_types = tuple(d and [x.__class__.__name__ for x in d]
                           for d in data)
        print("  %s : %s <- %s %s" % (name, symbol, data, data_types))
      print("-------------------")

  def get_attr_location(self, name, location):
    """Calculate ((line, col), len(attr)) for an attr access."""
    # TODO(mdemello): This is pretty crude, and does not for example take into
    # account multiple calls of the same attribute in a line. It is just to get
    # our tests passing until we incorporate asttokens.
    line, _ = location
    src_line = self.line(line)
    attr = name.split(".")[-1]
    dot_attr = "." + attr
    if dot_attr in src_line:
      col = src_line.index(dot_attr)
      return (Location(line, col + 1), len(attr))
    else:
      # We have something like
      #   (foo
      #      .bar)
      # or
      #   (foo.
      #     bar)
      # Lookahead up to 5 lines to find '.attr' (the ast node always starts from
      # the beginning of the chain, so foo.\nbar.\nbaz etc could span several
      # lines).
      attr_loc = self._get_multiline_location(location, 5, dot_attr)
      if attr_loc:
        return (Location(attr_loc.line, attr_loc.column + 1), len(attr))
      else:
        # Find consecutive lines ending with '.' and starting with 'attr'.
        for l in self.get_closest_line_range(line, line + 5):
          if self.line(l).endswith("."):
            next_line = self.next_non_comment_line(l)
            text = self.line(next_line)
            if text.lstrip().startswith(attr):
              c = text.index(attr)
              return (Location(next_line, c), len(attr))
      # if all else fails, fall back to just spanning the name
      return (location, len(name))

  def _get_multiline_location(self, location, n_lines, text):
    """Get the start location of text anywhere within n_lines of location."""
    line, _ = location
    text_loc = self.find_text(line, line + n_lines, text)
    if text_loc:
      return text_loc
    else:
      return None


def _collect_traces(raw_traces):
  """Postprocess pytype's opcode traces."""
  out = collections.defaultdict(list)
  for op, symbol, data in raw_traces:
    out[op.line].append((op.name, symbol, data))
  return out
