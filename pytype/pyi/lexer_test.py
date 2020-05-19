import os
import textwrap

from pytype.pyi import parser_ext
from pytype.pytd.parse import parser_constants
from pytype.tests import test_base

import unittest

# Map from token code to name.
TOKEN_NAMES = {code: name for name, code in parser_ext.TOKENS.items()}


class ExpectedToken(object):
  """An object used for token comparison.

  When checking for equality, ExpectedToken compares only as many fields as
  are provided in the ExpectedToken.  In addition, any field that has an
  expected value of None is ignores.  Thus ExpectedToken("NAME", "foo") will
  match a NAME token with value "foo" and ignore any location information,
  while ExpectedToken("NAME", "foo", 1, 2, 1, 4) will additionally require
  that the token starts on (1, 2) and ends at (1, 4).
  """

  def __init__(self, *values):
    self._values = values

  def __eq__(self, rhs):
    if len(rhs) < len(self._values):
      return False
    for left, right in zip(self._values, rhs):
      if left is not None and left != right:
        return False
    return True

  def __ne__(self, rhs):
    return not self == rhs

  def __repr__(self):
    return repr(self._values)


def convert_expected(spec):
  """Convert a token specification into an ExpectedToken.

  Args:
    spec: A token specification (see below for possible choices).

  Returns:
    An ExpectedToken object derived from spec as follows:
      string - A token of the form (spec, )
      integer - A token of the form (NUMBER, spec)
      float - A token of the form (NUMBER, spec)
      (type, value, ....) -  A token of the form (type, value, ...)
  """
  if isinstance(spec, str):
    return ExpectedToken(spec)
  elif isinstance(spec, (int, float)):
    return ExpectedToken("NUMBER", spec)
  else:
    return ExpectedToken(*spec)


def convert_token(t):
  """Convert the token type code into a more readable name."""
  pieces = list(t)
  code = pieces[0]
  if code < 256:
    pieces[0] = chr(code)
  else:
    pieces[0] = TOKEN_NAMES.get(code, code)
  return tuple(pieces)


class LexerTest(test_base.UnitTest):

  def check(self, expected, text):
    text = textwrap.dedent(text)
    actual = map(convert_token, parser_ext.tokenize(text))
    if expected is not None:
      self.assertListEqual(list(map(convert_expected, expected)), list(actual))

  def test_punctuation(self):
    punctuation = "@*:,.=?<>().[]"
    self.check(list(punctuation), punctuation)

  def test_quotes(self):
    self.check([("NUMBER", 1), ("STRING", "'2'"), ("STRING", '"3"')],
               "1 '2' \"3\"")

  def test_multi_char(self):
    self.check(["ARROW"], "->")
    self.check(["ELLIPSIS"], "...")
    self.check(["EQ"], "==")
    self.check(["NE"], "!=")
    self.check(["LE"], "<=")
    self.check(["GE"], ">=")

  def test_reserved(self):
    for word in parser_constants.RESERVED:
      self.check([word.upper()], word)

  def test_name(self):
    def check_name(expected, text):
      self.check([("NAME", expected)], text)
    # Regular names (hyphen is allowed).
    check_name("abc", "abc")
    check_name("_foo123", "_foo123")
    check_name("Foo-bar-BAZ", "Foo-bar-BAZ")
    # Names can be enclosed in backticks.
    check_name("abc", "`abc`")
    check_name("_foo123", "`_foo123`")
    check_name("Foo-bar-BAZ", "`Foo-bar-BAZ`")
    # Reserved words and ~ are allowed in backticks.
    check_name("~foo~", "`~foo~`")
    check_name("class", "`class`")

  def test_number(self):
    self.check([123], "123")
    self.check([123], "+123")
    self.check([-123], "-123")
    self.check([1.75], "1.75")
    self.check([1.75], "+1.75")
    self.check([-1.75], "-1.75")
    self.check([42.0], "42.")
    self.check([42.0], "+42.")
    self.check([-42.0], "-42.")
    self.check([0.5], ".5")
    self.check([0.5], "+.5")
    self.check([-0.5], "-.5")

  def test_number_base(self):
    self.check([0], "0b0")
    self.check([1], "0b1")
    self.check([42], "0b101010")
    self.check([-8], "-0b1000")

    self.check([1], "0o1")
    self.check([8], "0o10")
    self.check([42], "0o52")
    self.check([-7], "-0o7")

    self.check([1], "0x1")
    self.check([240], "0xF0")
    self.check([-240], "-0xF0")
    self.check([15], "0x0f")
    self.check([-15], "-0x0f")

  def test_line_numbers(self):
    self.check([("NAME", "a", 1), ("NAME", "b", 2)], "a\nb")

  def test_triplequoted(self):
    # Single quotes.
    self.check([
        ("NUMBER", 1, 1),
        ("TRIPLEQUOTED", None, 1, 3, 3, 5),
        ("NUMBER", 2, 4),
        ("TRIPLEQUOTED", None, 4, 3, 4, 58),
        ("NUMBER", 3, 5)], """
      1 ''' one quote is allowed '
            newlines and two quotes are allowed '', end on next line
        '''
      2 '''this shoulnd't be swallowed by the previous string'''
      3""".lstrip("\n"))
    # Double quotes.
    # pylint: disable=g-inconsistent-quotes
    self.check([
        ("NUMBER", 1, 1),
        ("TRIPLEQUOTED", None, 1, 3, 3, 5),
        ("NUMBER", 2, 4),
        ("TRIPLEQUOTED", None, 4, 3, 4, 58),
        ("NUMBER", 3, 5)], '''
      1 """ one quote is allowed "
            newlines and two quotes are allowed "", end on next line
        """
      2 """this shoulnd't be swallowed by the previous string"""
      3'''.lstrip("\n"))

  def test_typecomment(self):
    self.check([1, "TYPECOMMENT", 2, "TYPECOMMENT", 3, "TYPECOMMENT", 4], """
      1 # type: 2
      #type: 3
      #    type: 4""")

  def test_comments_are_ignored(self):
    self.check([("NUMBER", 1, 1), ("NUMBER", 2, 5)], """
      1 # comment until end of line
      # type not quite a type comment, no colon!
      #
      # The preceding line had a # followed immediately by newline.
      2""".lstrip("\n"))

  def test_indent(self):
    self.check(
        [1, "INDENT", 2, "INDENT", 3, "INDENT", 4, "DEDENT", "DEDENT", 5,
         "DEDENT", 6], """
      1
        2
          3
            4
        5
      6""")

  def test_indent_ignore_blank_line2(self):
    self.check(
        [1, "INDENT", 2, 3, "DEDENT"], """
      1
        2


        3""")

  def test_indent_dedents_at_eof(self):
    self.check(
        [1, "INDENT", 2, "INDENT", 3, "DEDENT", "DEDENT"], """
      1
        2
          3""")

  def test_indent_not_inside_brackets(self):
    self.check(
        [1, "[", 2, "[", "]", 3, "]", 4, "INDENT", 5, "DEDENT"], """
      1 [2 [ ]
         3]
      4
        5""")

  def test_indent_not_inside_parens(self):
    self.check(
        [1, "(", 2, "(", ")", 3, ")", 4, "INDENT", 5, "DEDENT"], """
      1 (2 ( )
         3)
      4
        5""")

  def test_indent_legacy_bug(self):
    # The legacy lexer was not properly handling 3 dedents in a row.
    self.check([1, "INDENT", 2, "INDENT", 3, "INDENT", 4, "DEDENT", "DEDENT",
                "DEDENT", 99], """
      1
        2
          3
            4
      99
      """)

  def test_indent_mismatch(self):
    self.check([1, "INDENT", 2, ("LEXERROR", "Invalid indentation"), 3,
                "DEDENT"], """
      1
        2
       3""")

  def test_lex_error(self):
    self.check([1, ("LEXERROR", "Illegal character '%'"), 2],
               "1 % 2")

  def test_column(self):
    # A blank line is part of the test because that is a special case
    # in the lex specification.
    self.check([
        ("NAME", "foo", 1, 1, 1, 3),
        ("NAME", "bar", 1, 5, 1, 7),
        "INDENT",
        ("NAME", "hello", 2, 3, 2, 7),
        ("NAME", "goodbye", 4, 3, 4, 9),
        "DEDENT"], """
      foo bar
        hello

        goodbye
      """.lstrip("\n"))

  def test_ignore_comment_indentation(self):
    self.check([1, "TYPECOMMENT", 2, 3], """
      1
        # comment 0
        # type: 2
      3""")

  def test_builtins(self):
    filename = "builtins/%d/__builtin__.pytd" % self.python_version[0]
    pytd_dir = os.path.dirname(os.path.dirname(parser_constants.__file__))
    with open(os.path.join(pytd_dir, filename)) as f:
      text = f.read()
    self.check(None, text)

  def test_typevar(self):
    self.check(["TYPEVAR"], "TypeVar")
    self.check(["TYPEVAR"], "typing.TypeVar")

  def test_namedtuple(self):
    self.check(["NAMEDTUPLE"], "NamedTuple")
    self.check(["NAMEDTUPLE"], "typing.NamedTuple")

  def test_collections_namedtuple(self):
    self.check(["COLL_NAMEDTUPLE"], "namedtuple")
    self.check(["COLL_NAMEDTUPLE"], "collections.namedtuple")


if __name__ == "__main__":
  unittest.main()
