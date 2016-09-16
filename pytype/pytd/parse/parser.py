# -*- coding:utf-8; python-indent:2; indent-tabs-mode:nil -*-

# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Parser & Lexer for type declaration language."""

# needed for ply grammar rules:
# pylint: disable=g-bad-name, g-short-docstring-punctuation
# pylint: disable=g-bad-name, g-short-docstring-space
# pylint: disable=g-doc-args, g-no-space-after-docstring-summary
# pylint: disable=g-space-before-docstring-summary
# pylint: disable=line-too-long
# pylint: disable=g-docstring-quotes

import collections
import hashlib
import traceback
from ply import lex
from ply import yacc
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd.parse import parser_constants
from pytype.pytd.parse import visitors


DEFAULT_VERSION = (2, 7, 6)


class ParseError(Exception):
  """Exception for representing parse errors."""

  def __init__(self, msg, filename, lineno=None, column=None, line=None):
    super(ParseError, self).__init__(msg)
    assert filename is not None
    self.msg = msg
    self.filename = filename
    self.lineno = lineno
    self.column = column
    self.line = line

  def __str__(self):
    # format_exception doesn't like None for lineno
    lineno = -1 if self.lineno is None else self.lineno
    e = SyntaxError(self.msg, (self.filename, lineno,
                               self.column, self.line))
    return ("Error while parsing pyi:\n" +
            "".join(traceback.format_exception(type(e), e, None)).rstrip())


class PyLexer(object):
  """Lexer for type declaration language."""

  def __init__(self):
    # TODO(pludemann): See comments with TypeDeclParser about generating the
    #                  $GENFILESDIR/pytypedecl_lexer.py and using it by
    #                  calling lex.lex(lextab=pytypedecl_lexer)
    self.lexer = lex.lex(module=self, debug=False)
    self.default_get_token = self.lexer.token
    # TODO(kramm): Is there a better way to use a custom lexer.token() function?
    self.lexer.token = self.get_token
    self.lexer.escaping = False

  def set_parse_info(self, src, filename):
    self.src = src
    self.filename = filename
    self.indent_stack = [0]
    self.open_brackets = 0
    self.queued_dedents = 0
    self.at_eof = False

  # The ply parsing library expects class members to be named in a specific way.
  t_AT = r"@"
  t_ARROW = r"->"
  t_ASTERISK = r"[*]"
  t_COLON = r":"
  t_COLONEQUALS = r":="
  t_COMMA = r","
  t_DEDENT = r"(?!d)d"
  t_ELLIPSIS = r"\.\.\."
  t_DOT = r"\."
  t_EQ = r"=="
  t_ASSIGN = r"="
  t_INDENT = r"(?!i)i"
  t_NE = r"!="
  t_QUESTIONMARK = r"\?"

  reserved = parser_constants.RESERVED

  # Define keyword tokens, so parser knows about them.
  # We generate them in t_NAME.
  locals().update({"t_" + id.upper(): id for id in reserved})

  tokens = [
      "ARROW",
      "ASSIGN",
      "ASTERISK",
      "AT",
      "COLON",
      "COLONEQUALS",
      "COMMA",
      # "COMMENT",  # Not used in the grammar; only used to discard comments
      "DEDENT",
      "DOT",
      "ELLIPSIS",
      "LT",
      "GT",
      "LE",
      "GE",
      "EQ",
      "NE",
      "INDENT",
      "LBRACKET",
      "LPAREN",
      "NAME",
      "NUMBER",
      "QUESTIONMARK",
      "RBRACKET",
      "RPAREN",
      "TYPECOMMENT",
      "TRIPLEQUOTED",
  ] + [id.upper() for id in reserved]

  def t_LE(self, t):
    r"""<="""
    return t

  def t_GE(self, t):
    r""">="""
    return t

  def t_LBRACKET(self, t):
    r"""\["""
    self.open_brackets += 1
    return t

  def t_RBRACKET(self, t):
    r"""\]"""
    self.open_brackets -= 1
    return t

  def t_LT(self, t):
    r"""<"""
    return t

  def t_GT(self, t):
    r""">"""
    return t

  def t_LPAREN(self, t):
    r"""\("""
    self.open_brackets += 1
    return t

  def t_RPAREN(self, t):
    r"""\)"""
    self.open_brackets -= 1
    return t

  def t_TAB(self, t):
    r"""\t"""
    # Since nobody can agree anymore how wide tab characters are supposed
    # to be, disallow them altogether.
    make_syntax_error(self, "Use spaces, not tabs", t)

  def t_WHITESPACE(self, t):
    # Treat ["] and ['] as whitespace, too, since they wrap types.
    r"""([\n\r ]|(?!\"\"\"|''')["'])+"""

    if self.queued_dedents:
      self.queued_dedents -= 1
      t.type = "DEDENT"
      return t
    t.lexer.lineno += t.value.count("\n")
    if self.open_brackets:
      # inside (...) and <...>, we allow any kind of whitespace and indentation.
      return
    spaces_and_newlines = t.value.replace("\r", "")
    i = spaces_and_newlines.rfind("\n")
    if i < 0:
      # whitespace in the middle of line
      return

    eof = t.lexer.lexpos >= len(t.lexer.lexdata)
    if eof:
      # Ignore white space at end of file.
      return None

    if not eof and t.lexer.lexdata[t.lexer.lexpos] in "#":
      # empty line (ends with comment)
      return

    indent = len(spaces_and_newlines) - i - 1
    if indent < self.indent_stack[-1]:
      self.indent_stack.pop()
      while indent < self.indent_stack[-1]:
        self.indent_stack.pop()
        # Since we can't return multiple tokens at once, we instead queue them
        # and make the lexer reprocess the last whitespace.
        self.queued_dedents += 1
      if indent != self.indent_stack[-1]:
        make_syntax_error(self, "invalid dedent", t)
      if self.queued_dedents:
        t.lexer.skip(-1)  # reprocess this whitespace
      t.type = "DEDENT"
      return t
    elif indent > self.indent_stack[-1]:
      self.indent_stack.append(indent)
      t.type = "INDENT"
      return t
    else:
      # same indent as before, ignore.
      return None

  def t_NAME(self, t):
    # For handling identifiers that are reserved words in PyTD or that start
    # with '~' or contain a dash, we also allow an escape with backticks.  If
    # you change this, also change parser_constants._BACKTICK_NAME.
    (r"""([a-zA-Z_][a-zA-Z0-9_-]*)|"""
     r"""(`[a-zA-Z_~][-a-zA-Z0-9_~]*`)""")
    if t.value[0] == r"`":
      # Permit token names to be enclosed by backticks (``), to allow for names
      # that are keywords in pytd syntax.
      assert t.value[-1] == r"`"
      t.value = t.value[1:-1]
      t.type = "NAME"
    elif t.value in self.reserved:
      t.type = t.value.upper()
    return t

  def t_TRIPLEQUOTED(self, t):
    (r'"""((?!""")(.|\n))*"""|'
     r"'''((?!''')(.|\n))*'''")
    return t

  def t_NUMBER(self, t):
    r"""[-+]?[0-9]+(\.[0-9]*)*"""
    # TODO(pludemann): full Python number syntax
    # TODO(pludemann): move +/- to grammar?
    t.value = Number(t.value)
    return t

  def t_TYPECOMMENT(self, t):
    r"""\#\s*type:"""
    return t

  def t_COMMENT(self, t):
    r"""\#[^\n]*"""
    # No return value. Token discarded

  def get_token(self):
    if not self.at_eof:
      t = self.default_get_token()
      if t is not None:
        return t
    self.at_eof = True
    if len(self.indent_stack) > 1:
      self.indent_stack.pop()
      t = lex.LexToken()
      t.lexpos = self.lexer.lexpos
      t.lineno = self.lexer.lineno
      t.type = "DEDENT"
      t.value = None
      return t
    else:
      return None

  def t_error(self, t):
    make_syntax_error(self, "Illegal character '%s'" % t.value[0], t)

Params = collections.namedtuple("_", ["required",
                                      "starargs", "starstarargs",
                                      "has_bare_star"])
NameAndSig = collections.namedtuple("_", ["name", "signature",
                                          "decorators", "external_code"])


class Number(collections.namedtuple("Number", ["string"])):
  """Store a number token (float or int, or a version number)."""

  def AsFloatOrInt(self):
    return float(self.string) if "." in self.string else int(self.string)

  def AsVersion(self, parser, p):
    components = self.string.split(".")
    if (len(components) not in (1, 2, 3) or
        any(not digit.isdigit() for digit in components) or
        not all(0 <= int(digit) <= 9 for digit in components)):
      make_syntax_error(parser,
                        "Illegal version \"%s\"" % self.string, p)
    prefix = tuple(int(digit) for digit in components)
    return (prefix + (0, 0, 0))[0:3]

  def __int__(self):
    return int(self.string)


class Mutator(visitors.Visitor):
  """Visitor for changing parameters to BeforeAfterType instances.

  We model
    def f(x: old_type):
      x := new_type
  as
    def f(x: BeforeAfterType(old_type, new_type))
  .
  This visitor applies the body "x := new_type" to the function signature.
  """

  def __init__(self, name, new_type):
    super(Mutator, self).__init__()
    self.name = name
    self.new_type = new_type
    self.successful = False

  def VisitParameter(self, p):
    if p.name == self.name:
      self.successful = True
      if p.optional:
        raise NotImplementedError(
            "Argument %s can not be both mutable and optional" % p.name)
      return p.Replace(mutated_type=self.new_type)
    else:
      return p


class InsertTypeParameters(visitors.Visitor):
  """Visitor for inserting TypeParameter instances."""

  def EnterTypeDeclUnit(self, node):
    self.type_params = {p.name: p for p in node.type_params}

  def LeaveTypeDeclUnit(self, node):
    self.type_params = None

  def VisitNamedType(self, node):
    if node.name in self.type_params:
      return self.type_params[node.name]
    else:
      return node


def CheckIsSysPythonInfo(parser, string, p):
  if string == "sys.version_info":
    return
  make_syntax_error(
      parser, "Only \"sys.version_info\" can be compared with a tuple: %s" % (
          string), p)


def CheckIsSysPlatform(parser, string, p):
  if string == "sys.platform":
    return
  make_syntax_error(
      parser, "Only \"sys.platform\" can be compared with a string: %s" % (
          string), p)


def EvaluateIfElse(if_expr, if_body, elif_list, else_body):
  for condition, body in [(if_expr, if_body)] + elif_list:
    if condition:
      return body
  return else_body


class _TypeDeclParser(object):
  """Parser for type declaration language."""

  def __init__(self):
    """Initialize.

    Parameters:
      version: A tuple of three numbers: (major, minor, micro).
               E.g. (3,4,0).
      kwargs: Additional parameters to pass to yacc.yacc().
    """
    # TODO(pludemann): Don't generate the lex/yacc tables each time. This should
    #                  be done by a separate program that imports this module
    #                  and calls yacc.yacc(write_tables=True,
    #                  outputdir=$GENFILESDIR, tabmodule='pytypedecl_parser')
    #                  and similar params for lex.lex(...).  Then:
    #                    import pytypdecl_parser
    #                    self.parser = yacc.yacc(tabmodule=pytypedecl_parser)
    #                  [might also need optimize=True]
    self.lexer = PyLexer()
    self.tokens = self.lexer.tokens

    self.parser = yacc.yacc(
        start="start",  # warning: ply ignores this
        module=self,
        debug=False,
        write_tables=False)
        # debuglog=yacc.PlyLogger(sys.stderr),
        # errorlog=yacc.NullLogger())  # If you really want to suppress messages)

  def Parse(self, src, name=None, filename="<string>", version=None,
            platform="linux"):
    """Run tokenizer, parser, and postprocess the AST."""
    self.src = src  # Keep a copy of what's being parsed
    self.filename = filename if filename else "<string>"
    self.python_version = version or DEFAULT_VERSION
    self.platform = platform
    self.generated_classes = collections.defaultdict(list)
    # For the time being, also allow shortcuts, i.e., using "List" for
    # "typing.List", even without having imported typing:
    if name != "typing":
      self.aliases = {name: pytd.NamedType("typing." + name)
                      for name in pep484.PEP484_NAMES}
    else:
      self.aliases = {}
    # If a translation overwrites a shortcut, the definition in the typing
    # module is ignored. We disallow this confusing behavior.
    intersection = set(self.aliases) & set(pep484.PEP484_TRANSLATIONS)
    assert not intersection, "Multiple definitions: " + str(intersection)
    self.aliases.update(pep484.PEP484_TRANSLATIONS)
    self.lexer.set_parse_info(self.src, self.filename)
    ast = self.parser.parse(src, lexer=self.lexer.lexer)
    # If there's no unique name, hash the sourcecode.
    name = name or hashlib.md5(src).hexdigest()
    ast = ast.Visit(InsertTypeParameters())
    ast = ast.Visit(pep484.ConvertTypingToNative(name))
    return ast.Replace(name=name)

  precedence = (
      ("left", "OR"),
      ("left", "AND"),
      ("left", "COMMA"),
  )

  def p_start(self, p):
    """start : unit"""
    p[0] = p[1]

  def p_start_with_docstring(self, p):
    """start : TRIPLEQUOTED unit"""
    p[0] = p[2]

  def p_unit(self, p):
    """unit : alldefs"""
    generated_classes = [x for class_list in self.generated_classes.values()
                         for x in class_list]

    funcdefs = [x for x in p[1] if isinstance(x, NameAndSig)]
    constants = [x for x in p[1] if isinstance(x, pytd.Constant)]
    type_params = [x for x in p[1] if isinstance(x, pytd.TypeParameter)]
    classes = (generated_classes +
               [x for x in p[1] if isinstance(x, pytd.Class)])
    aliases = [x for x in p[1] if isinstance(x, pytd.Alias)]
    all_names = (list(set(f.name for f in funcdefs)) +
                 [c.name for c in constants] +
                 [c.name for c in type_params] +
                 [c.name for c in classes] +
                 [c.name for c in aliases])
    duplicates = [name
                  for name, count in collections.Counter(all_names).items()
                  if count >= 2]
    if duplicates:
      make_syntax_error(
          self, "Duplicate top-level identifier(s): " + ", ".join(duplicates),
          p)

    functions, properties = self.MergeSignatures(funcdefs)
    if properties:
      prop_names = ", ".join(p.name for p in properties)
      make_syntax_error(
          self,
          "Module-level functions with property decorators: " + prop_names,
          p)

    p[0] = pytd.TypeDeclUnit(name=None,  # replaced later, in Parse
                             constants=tuple(constants),
                             type_params=tuple(type_params),
                             functions=tuple(functions),
                             classes=tuple(classes),
                             aliases=tuple(aliases))

  def p_alldefs_constant(self, p):
    """alldefs : alldefs constantdef"""
    p[0] = p[1] + [p[2]]

  def p_alldefs_class(self, p):
    """alldefs : alldefs classdef"""
    p[0] = p[1] + [p[2]]

  def p_alldefs_func(self, p):
    """alldefs : alldefs funcdef"""
    p[0] = p[1] + [p[2]]

  def p_alldefs_typevar(self, p):
    """alldefs : alldefs typevardef"""
    p[0] = p[1] + [p[2]]

  def p_alldefs_if(self, p):
    """alldefs : alldefs toplevel_if"""
    p[0] = p[1] + p[2]

  def p_alldefs_import(self, p):
    """alldefs : alldefs import"""
    p[0] = p[1] + p[2]

  def p_alldefs_alias(self, p):
    """alldefs : alldefs alias_or_constant"""
    p[0] = p[1] + [p[2]]

  def p_alldefs_null(self, p):
    """alldefs :"""
    p[0] = []

  def p_import_simple(self, p):
    """import : IMPORT import_list"""
    aliases = []
    for module, new_name in p[2]:
      if module != new_name:
        make_syntax_error(
            self, "Renaming of modules not supported. Use 'from' syntax.", p)
      # TODO(kramm): Put modules into aliases, too.
    p[0] = aliases

  def p_import_from(self, p):
    """import : FROM dotted_name IMPORT import_from_list"""
    _, _, dotted_name, _, import_from_list = p
    aliases = []
    for name, new_name in import_from_list:
      if name != "*":
        t = pytd.NamedType(dotted_name + "." + name)
        self.aliases[new_name] = t
        if dotted_name != "typing":
          aliases.append(pytd.Alias(new_name, t))
      else:
        pass  # TODO(kramm): Handle '*' imports in pyi
    p[0] = aliases

  def p_quoted_from_list(self, p):
    """
    import_from_list : LPAREN import_from_items       RPAREN
    import_from_list : LPAREN import_from_items COMMA RPAREN
    """
    p[0] = p[2]

  def p_nonquoted_from_list(self, p):
    """import_from_list : import_from_items"""
    p[0] = p[1]

  def p_import_list_1(self, p):
    """import_list : import_item"""
    p[0] = [p[1]]

  def p_import_list(self, p):
    """import_list : import_list COMMA import_item"""
    p[0] = p[1] + [p[3]]

  def p_import_item(self, p):
    """import_item : dotted_name"""
    p[0] = (p[1], p[1])

  def p_import_item_as(self, p):
    """import_item : dotted_name AS NAME"""
    p[0] = (p[1], p[3])

  def p_import_from_items_1(self, p):
    """import_from_items : from_item"""
    p[0] = [p[1]]

  def p_import_from_items(self, p):
    """import_from_items : import_from_items COMMA from_item"""
    p[0] = p[1] + [p[3]]

  def p_from_item(self, p):
    """from_item : NAME"""
    p[0] = (p[1], p[1])

  def p_from_item_namedtuple(self, p):
    """from_item : NAMEDTUPLE"""
    # So NamedTuple can be imported from typing
    p[0] = ("NamedTuple", "NamedTuple")

  def p_from_item_typevar(self, p):
    """from_item : TYPEVAR"""
    # So TypeVar can be imported from typing
    p[0] = ("TypeVar", "TypeVar")

  def p_from_item_as(self, p):
    """from_item : NAME AS NAME"""
    p[0] = (p[1], p[3])

  def p_from_item_asterisk(self, p):
    """from_item : ASTERISK"""
    p[0] = ("*", "*")

  def p_dotted_name_1(self, p):
    """dotted_name : NAME"""
    p[0] = p[1]

  def p_dotted_name(self, p):
    """dotted_name : dotted_name DOT NAME"""
    p[0] = p[1] + "." + p[3]

  def p_alias_or_constant(self, p):
    """alias_or_constant : NAME ASSIGN type"""
    # Other special cases of constant definitions are handled in constantdef,
    # e.g.  p_constantdef_int (for "name = 0")
    if p[3] in [pytd.NamedType("True"), pytd.NamedType("False")]:
      # See https://github.com/google/pytype/issues/14
      p[0] = pytd.Constant(p[1], pytd.NamedType("bool"))
    else:
      self.aliases[p[1]] = p[3]
      p[0] = pytd.Alias(p[1], p[3])

  def p_if(self, p):
    """if : IF version_expr COLON INDENT"""
    _, _, version_expr, _, _ = p
    p[0] = version_expr

  def p_toplevel_else(self, p):
    """toplevel_else : ELSE COLON INDENT alldefs DEDENT"""
    p[0] = p[4]

  def p_funcdefs_else(self, p):
    """funcdefs_else : ELSE COLON INDENT funcdefs DEDENT"""
    p[0] = p[4]

  def p_toplevel_else_0(self, p):
    """toplevel_else : """
    p[0] = []

  def p_funcdefs_else_0(self, p):
    """funcdefs_else : """
    p[0] = []

  def p_toplevel_elifs(self, p):
    """alldefs_elifs : ELIF version_expr COLON INDENT alldefs DEDENT alldefs_elifs"""
    p[0] = [(p[2], p[5])] + p[7]

  def p_funcdefs_elifs(self, p):
    """funcdefs_elifs : ELIF version_expr COLON INDENT funcdefs DEDENT funcdefs_elifs"""
    p[0] = [(p[2], p[5])] + p[7]

  def p_toplevel_elifs_0(self, p):
    """alldefs_elifs : """
    p[0] = []

  def p_funcdefs_elifs_0(self, p):
    """funcdefs_elifs : """
    p[0] = []

  def p_toplevel_if(self, p):
    """toplevel_if : if alldefs DEDENT alldefs_elifs toplevel_else"""
    _, version_expr, alldefs, _, elifs, else_defs = p
    p[0] = EvaluateIfElse(version_expr, alldefs, elifs, else_defs)

  def p_funcdefs_if(self, p):
    """funcdefs_if : if funcdefs DEDENT funcdefs_elifs funcdefs_else"""
    _, version_expr, funcdefs, _, elifs, else_defs = p
    p[0] = EvaluateIfElse(version_expr, funcdefs, elifs, else_defs)

  def p_version_tuple_1(self, p):
    """number_tuple : LPAREN NUMBER COMMA RPAREN"""
    p[0] = p[2]

  def p_version_tuple_2(self, p):
    """number_tuple : LPAREN NUMBER COMMA NUMBER RPAREN"""
    _, _, major, _, minor, _ = p
    p[0] = Number(major.string + "." + minor.string)

  def p_version_tuple_3(self, p):
    """number_tuple : LPAREN NUMBER COMMA NUMBER COMMA NUMBER RPAREN"""
    _, _, major, _, minor, _, micro, _ = p
    p[0] = Number(major.string + "." + minor.string + "." + micro.string)

  def p_version_expr_lt(self, p):
    """version_expr : dotted_name LT number_tuple"""
    _, sys_version, _, number = p
    CheckIsSysPythonInfo(self, sys_version, p)
    p[0] = self.python_version < number.AsVersion(self, p)

  def p_version_expr_gt(self, p):
    """version_expr : dotted_name GT number_tuple"""
    _, sys_version, _, number = p
    CheckIsSysPythonInfo(self, sys_version, p)
    p[0] = self.python_version > number.AsVersion(self, p)

  def p_version_expr_ge(self, p):
    """version_expr : dotted_name GE number_tuple"""
    _, sys_version, _, number = p
    CheckIsSysPythonInfo(self, sys_version, p)
    p[0] = self.python_version >= number.AsVersion(self, p)

  def p_version_expr_le(self, p):
    """version_expr : dotted_name LE number_tuple"""
    _, sys_version, _, number = p
    CheckIsSysPythonInfo(self, sys_version, p)
    p[0] = self.python_version <= number.AsVersion(self, p)

  def p_version_expr_eq(self, p):
    """version_expr : dotted_name EQ number_tuple"""
    _, sys_version, _, number = p
    CheckIsSysPythonInfo(self, sys_version, p)
    p[0] = self.python_version == number.AsVersion(self, p)

  def p_version_expr_ne(self, p):
    """version_expr : dotted_name NE number_tuple"""
    _, sys_version, _, number = p
    CheckIsSysPythonInfo(self, sys_version, p)
    p[0] = self.python_version != number.AsVersion(self, p)

  def p_platform_eq(self, p):
    """version_expr : dotted_name EQ NAME"""
    _, sys_platform, _, name = p
    CheckIsSysPlatform(self, sys_platform, p)
    p[0] = self.platform == name

  def p_platform_ne(self, p):
    """version_expr : dotted_name NE NAME"""
    _, sys_platform, _, name = p
    CheckIsSysPlatform(self, sys_platform, p)
    p[0] = self.platform != name

  def p_class_parents(self, p):
    """class_parents : parents"""
    p[0] = tuple(parent for parent in p[1]
                 if not isinstance(parent, pytd.NothingType))

  def p_end_class(self, p):
    """end_class : """
    p[0] = None

  def p_class_name(self, p):
    """class_name : NAME """
    self.aliases[p[1]] = pytd.NamedType(p[1])
    p[0] = p[1]

  # TODO(raoulDoc): doesn't support nested classes
  def p_classdef(self, p):
    """classdef : CLASS class_name class_parents COLON maybe_class_funcs end_class"""
    _, _, class_name, parents, _, class_funcs, _ = p
    methoddefs = [x for x in class_funcs  if isinstance(x, NameAndSig)]
    constants = [x for x in class_funcs if isinstance(x, pytd.Constant)]

    all_names = (list(set(f.name for f in methoddefs)) +
                 [c.name for c in constants])
    duplicates = [name
                  for name, count in collections.Counter(all_names).items()
                  if count >= 2]
    if duplicates:
      # TODO(kramm): raise a syntax error right when the identifier is defined.
      raise make_syntax_error(
          self, "Duplicate identifier(s): " + ", ".join(duplicates), p)

    methods, properties = self.MergeSignatures(methoddefs)
    # Ensure that old style classes inherit from classobj.
    if not parents and class_name not in ["classobj", "object"]:
      parents = (pytd.NamedType("classobj"),)
    p[0] = pytd.Class(name=class_name, parents=parents,
                      methods=tuple(methods),
                      constants=tuple(constants + properties),
                      template=())

  def p_maybe_class_funcs(self, p):
    """maybe_class_funcs : INDENT class_funcs DEDENT"""
    p[0] = p[2]

  def p_maybe_class_funcs_docstring(self, p):
    """maybe_class_funcs : INDENT TRIPLEQUOTED class_funcs DEDENT"""
    p[0] = p[3]

  def p_maybe_class_funcs_ellipsis(self, p):
    """maybe_class_funcs : ELLIPSIS"""
    p[0] = []

  def p_maybe_class_funcs_pass(self, p):
    """maybe_class_funcs : PASS"""
    p[0] = []

  def p_class_funcs(self, p):
    """class_funcs : funcdefs"""  # funcdefs can be empty
    p[0] = p[1]

  def p_class_funcs_pass(self, p):
    """class_funcs : PASS"""
    p[0] = []

  def p_class_funcs_ellipsis(self, p):
    """class_funcs : ELLIPSIS"""
    p[0] = []

  def p_parents(self, p):
    """parents : LPAREN parent_list RPAREN"""
    _, _, parent_list, _ = p
    p[0] = parent_list

  def p_parents_kwarg(self, p):
    """parents : LPAREN parent_list COMMA NAME ASSIGN NAME RPAREN"""
    parent_list, kwarg = p[2], p[4]
    if kwarg != "metaclass":
      make_syntax_error(self, "Only 'metaclass' allowed as classdef kwarg", p)
    p[0] = parent_list

  def p_parents_empty_kwarg(self, p):
    """parents : LPAREN NAME ASSIGN NAME RPAREN"""
    kwarg = p[2]
    if kwarg != "metaclass":
      make_syntax_error(self, "Only 'metaclass' allowed as classdef kwarg", p)
    p[0] = []

  def p_parents_empty(self, p):
    """parents : LPAREN RPAREN"""
    p[0] = []

  def p_parents_null(self, p):
    """parents :"""
    p[0] = []

  def p_parent_list_multi(self, p):
    """parent_list : parent_list COMMA type"""
    _, parent_list, _, parent = p
    p[0] = parent_list + [parent]

  def p_parent_list_1(self, p):
    """parent_list : type"""
    p[0] = [p[1]]

  def p_funcdefs_func(self, p):
    """funcdefs : funcdefs funcdef"""
    p[0] = p[1] + [p[2]]

  def p_funcdefs_constant(self, p):
    """funcdefs : funcdefs constantdef"""
    p[0] = p[1] + [p[2]]

  def p_funcdefs_conditional(self, p):
    """funcdefs : funcdefs funcdefs_if"""
    p[0] = p[1] + p[2]

  # TODO(raoulDoc): doesn't support nested functions
  def p_funcdefs_null(self, p):
    """funcdefs :"""
    p[0] = []

  def p_constantdef_ellipsis(self, p):
    """constantdef : NAME ASSIGN ELLIPSIS"""
    p[0] = pytd.Constant(p[1], pytd.AnythingType())

  def p_constantdef_ellipsis_comment(self, p):
    """constantdef : NAME ASSIGN ELLIPSIS TYPECOMMENT type"""
    p[0] = pytd.Constant(p[1], p[5])

  def p_constantdef_int(self, p):
    """constantdef : NAME ASSIGN NUMBER"""
    if int(p[3]) != 0:
      make_syntax_error(self, "Only '0' allowed as int literal", p)
    p[0] = pytd.Constant(p[1], pytd.NamedType("int"))

  def p_typevardef(self, p):
    """typevardef : NAME ASSIGN TYPEVAR LPAREN params RPAREN"""
    name, params = p[1], p[5]

    if (not params.required or
        not isinstance(params.required[0], pytd.Parameter)):
      make_syntax_error(self, "TypeVar's first arg should be a string", p)

    # Allow and ignore any other arguments (types, covariant=..., etc)
    name_param = params.required[0].name
    if name != name_param:
      make_syntax_error(self, "TypeVar name needs to be %r (not %r)" % (
          name_param, name), p)
    p[0] = pytd.TypeParameter(name, scope=None)

  def p_namedtuple_field(self, p):
    """
    namedtuple_field : LPAREN NAME COMMA type       RPAREN
    namedtuple_field : LPAREN NAME COMMA type COMMA RPAREN
    """
    p[0] = (p[2], p[4])

  def p_namedtuple_field_list(self, p):
    """namedtuple_field_list : namedtuple_field_list COMMA namedtuple_field"""
    p[0] = p[1] + [p[3]]

  def p_namedtuple_field_list_1(self, p):
    """namedtuple_field_list : namedtuple_field"""
    p[0] = [p[1]]

  def p_namedtuple_fields(self, p):
    """
    namedtuple_fields : LBRACKET                             RBRACKET
    namedtuple_fields : LBRACKET namedtuple_field_list       RBRACKET
    namedtuple_fields : LBRACKET namedtuple_field_list COMMA RBRACKET
    """
    p[0] = tuple() if len(p) == 3 else tuple(p[2])

  def p_type_namedtupledef(self, p):
    """type : NAMEDTUPLE LPAREN NAME COMMA namedtuple_fields RPAREN"""
    base_name, fields = p[3], p[5]

    # Handle previously defined NamedTuples with the same name
    prev_list = self.generated_classes[base_name]
    name_dedup = "~%d" % len(prev_list) if prev_list else ""
    class_name = "`%s%s`" % (base_name, name_dedup)

    # Like for typing.Tuple, heterogeneous NamedTuples get converted to
    # homogeneous ones:
    # NamedTuple[("x", X), ("y", Y)] -> Tuple[X, Y] -> Tuple[Union[X, Y], ...]
    types = tuple(t for _, t in fields)
    container_param = (pytd.UnionType(type_list=types) if types
                       else pytd.AnythingType())

    class_parent = pytd.HomogeneousContainerType(
        base_type=pytd.NamedType("tuple"),
        parameters=(container_param,))

    class_constants = tuple(pytd.Constant(n, t) for n, t in fields)
    nt_class = pytd.Class(name=class_name,
                          parents=(class_parent,),
                          methods=(),
                          constants=class_constants,
                          template=())

    self.generated_classes[base_name].append(nt_class)
    p[0] = pytd.NamedType(nt_class.name)

  def p_decorator(self, p):
    """decorator : AT dotted_name"""
    name = p[2]
    if name == "overload":
      # used for multiple signatures for the same function, discard
      p[0] = []
    elif name == "abstractmethod":
      # discard
      p[0] = []
    elif (name in ("staticmethod", "classmethod", "property") or
          "." in name):
      # dotted_name decorators need more context to be validated, done in
      # TryParseSignatureAsProperty
      p[0] = [name]
    else:
      make_syntax_error(self, "Decorator %r not supported" % name, p)

  def p_decorators_0(self, p):
    """decorators : """
    p[0] = []

  def p_decorators_many(self, p):
    """decorators : decorators decorator"""
    p[0] = p[1] + p[2]

  def p_funcdef(self, p):
    """funcdef : decorators DEF NAME LPAREN params RPAREN return raises signature maybe_body"""
    _, decorators, _, name, _, params, _, return_type, raises, _, body = p
    # TODO(kramm): Output a warning if we already encountered a signature
    #              with these types (but potentially different argument names)
    if name == "__init__" and isinstance(return_type, pytd.AnythingType):
      ret = pytd.NamedType("NoneType")
    else:
      ret = return_type
    signature = pytd.Signature(params=tuple(params.required), return_type=ret,
                               starargs=params.starargs,
                               starstarargs=params.starstarargs,
                               exceptions=tuple(raises), template=())

    for mutator in body:
      try:
        signature = signature.Visit(mutator)
      except NotImplementedError as e:
        make_syntax_error(self, e.message, p)
      if not mutator.successful:
        make_syntax_error(self, "No parameter named %s" % mutator.name, p)

    # TODO(acaceres): if not inside a class, any decorator should be an error
    if len(decorators) > 1:
      make_syntax_error(self, "Too many decorators for %s" % name, p)

    p[0] = NameAndSig(name=name, signature=signature,
                      decorators=tuple(sorted(decorators)),
                      external_code=False)

  def p_funcdef_code(self, p):
    """funcdef : decorators DEF NAME PYTHONCODE"""
    # NAME (not: module_name) because PYTHONCODE is always local.
    _, _, _, name, _ = p
    p[0] = NameAndSig(
        name=name,
        # signature is for completeness - it's ignored
        signature=pytd.Signature(params=(),
                                 starargs=None, starstarargs=None,
                                 return_type=pytd.NothingType(),
                                 exceptions=(),
                                 template=()),
        decorators=(),
        external_code=True)

  def p_empty_body(self, p):
    """maybe_body :"""
    p[0] = []

  def p_sameline_body(self, p):
    """maybe_body : COLON ELLIPSIS"""
    p[0] = []

  def p_sameline_body_pass(self, p):
    """maybe_body : COLON PASS"""
    p[0] = []

  def p_ellipsis_body(self, p):
    """maybe_body : COLON INDENT ELLIPSIS DEDENT"""
    p[0] = []

  def p_pass_body(self, p):
    """maybe_body : COLON INDENT PASS DEDENT"""
    p[0] = []

  def p_docstring_body(self, p):
    """maybe_body : COLON INDENT TRIPLEQUOTED DEDENT"""
    p[0] = []

  def p_has_body(self, p):
    """maybe_body : COLON INDENT body DEDENT"""
    _, _, _, body, _ = p
    p[0] = body

  def p_body_1(self, p):
    """body : body_stmt"""
    p[0] = p[1]

  def p_body_multiple(self, p):
    """body : body_stmt body"""
    p[0] = p[1] + p[2]

  def p_body_stmt_mutator(self, p):
    """body_stmt : mutator"""
    p[0] = p[1]

  def p_body_stmt_raise(self, p):
    """body_stmt : raise"""
    p[0] = p[1]

  def p_mutator(self, p):
    """mutator : NAME COLONEQUALS type"""
    p[0] = [Mutator(p[1], p[3])]

  def p_raise(self, p):
    """raise : RAISE NAME"""
    p[0] = []  # TODO(kramm): process

  def p_raise_parens(self, p):
    """raise : RAISE NAME LPAREN RPAREN"""
    p[0] = []  # TODO(kramm): process

  def p_return(self, p):
    """return : ARROW type"""
    p[0] = p[2]

  def p_no_return(self, p):
    """return : """
    p[0] = pytd.AnythingType()

  # TODO(pludemann): add
  # def p_return_2(self, p):
  #   """return : ARROW STRICT type"""
  #   p[0] = p[3]
  #   p[0].strict = True

  # TODO(pludemann): allow the return type to be missing from *only* __init__
  #                  in which case it defaults to "-> NoneType"
  # Design decision: Require a return type. An earlier design defaulted
  #                  the return type to pytd.AnythingType but that led to
  #                  confusion.
  # This rule is commented out until we can add the logic for restricting
  # NoneType to only definitions of __init__
  # # We interpret a missing "-> type" as: "Type not specified"
  # def p_return_null(self, p):
  #   """return :"""
  #   p[0] = pytd.NamedType("NoneType")

  def p_param_list_single(self, p):
    """param_list : param"""
    # we don't let param_list be empty because params rules append to it
    p[0] = [p[1]]

  def p_param_list(self, p):
    """param_list : param_list COMMA param"""
    p[0] = p[1] + [p[3]]

  def p_params_empty(self, p):
    """params : """
    p[0] = Params([], None, None, has_bare_star=False)

  def p_params_empty_ellipsis(self, p):
    """params : ELLIPSIS"""
    starargs, starstarargs = visitors.InventStarArgParams([])
    p[0] = Params([], starargs, starstarargs, has_bare_star=False)

  def p_params_from_list(self, p):
    """params : param_list"""
    p[0] = self.ValidateParamList(p, p[1])

  def p_params_ellipsis(self, p):
    """params : param_list COMMA ELLIPSIS"""
    params = self.ValidateParamList(p, p[1])
    if params.has_bare_star:
      make_syntax_error(self, "ellipsis (...) not compatible with bare *", p)
    starargs, starstarargs = visitors.InventStarArgParams([])
    p[0] = Params(params.required, starargs, starstarargs, has_bare_star=False)

  def p_param(self, p):
    """param : NAME"""
    # type is optional and defaults to "object"
    # TODO(kramm): We should use __builtin__.object. (And other places)
    p[0] = pytd.Parameter(p[1], pytd.NamedType("object"),
                          False, False, None)

  def p_optional_ellipsis(self, p):
    """optional : ELLIPSIS"""
    # TODO(kramm): We should use __builtin__.object. (And other places)
    p[0] = pytd.NamedType("object")

  def p_optional_id(self, p):
    """optional : NAME"""
    if p[1] == "None":
      # TODO(kramm): We should use __builtin__.NoneType here. (And other places)
      p[0] = pytd.NamedType("NoneType")
    else:
      p[0] = pytd.NamedType("object")

  def p_optional_number(self, p):
    """optional : NUMBER"""
    if "." in p[1].string:
      # TODO(kramm): We should use __builtin__.float here. (And other places)
      p[0] = pytd.NamedType("float")
    else:
      p[0] = pytd.NamedType("int")

  def p_param_optional(self, p):
    """param : NAME ASSIGN optional"""
    p[0] = pytd.Parameter(p[1], p[3],
                          kwonly=False,  # adjusted later
                          optional=True, mutated_type=None)

  def p_param_and_type(self, p):
    """param : NAME COLON type"""
    p[0] = pytd.Parameter(p[1], p[3],
                          kwonly=False,  # adjusted later
                          optional=False, mutated_type=None)

  def p_param_and_type_optional(self, p):
    """param : NAME COLON type ASSIGN optional"""
    _, name, _, t, _, opt = p
    if opt == pytd.NamedType("NoneType"):
      p[0] = pytd.Parameter(name, pytd.UnionType((t, opt)),
                            kwonly=False,  # adjusted later
                            optional=True, mutated_type=None)
    else:
      p[0] = pytd.Parameter(name, t,
                            kwonly=False,  # adjusted later
                            optional=True, mutated_type=None)

  def p_param_only_star(self, p):
    """param : ASTERISK"""
    # Empty *args, for keyword-only args, see PEP3102
    p[0] = pytd.Parameter("*", pytd.NothingType(),
                          False, True, None)

  def p_param_star(self, p):
    """param : ASTERISK NAME"""
    p[0] = pytd.Parameter("*" + p[2], pytd.NamedType("tuple"),
                          False, True, None)

  def p_param_star_type(self, p):
    """param : ASTERISK NAME COLON type"""
    _, _, name, _, t = p
    p[0] = pytd.Parameter(
        "*" + name,
        pytd.HomogeneousContainerType(pytd.NamedType("tuple"), (t,)),
        False, True, None)

  def p_param_kw(self, p):
    """param : ASTERISK ASTERISK NAME"""
    p[0] = pytd.Parameter(
        "**" + p[3],
        pytd.NamedType("dict"),
        False, True, None)

  def p_param_kw_type(self, p):
    """param : ASTERISK ASTERISK NAME COLON type"""
    _, _, _, name, _, t = p
    p[0] = pytd.Parameter(
        "**" + name,
        pytd.GenericType(pytd.NamedType("dict"), (pytd.NamedType("str"), t)),
        False, True, None)

  def p_raises(self, p):
    """raises : RAISES exceptions"""
    p[0] = p[2]

  def p_raises_null(self, p):
    """raises :"""
    p[0] = []

  def p_exceptions_1(self, p):
    """exceptions : exception"""
    p[0] = [p[1]]

  def p_exceptions_multi(self, p):
    """exceptions : exceptions COMMA exception"""
    p[0] = p[1] + [p[3]]

  def p_exception(self, p):
    """exception : type"""
    p[0] = p[1]

  def p_parameters_1(self, p):
    """parameters : parameter"""
    p[0] = (p[1],)

  def p_parameters_multi(self, p):
    """parameters : parameters COMMA parameter"""
    p[0] = p[1] + (p[3],)

  def p_parameter(self, p):
    """parameter : type"""
    p[0] = p[1]

  def p_parameter_dotdotdot(self, p):
    """parameter : ELLIPSIS"""
    p[0] = Ellipsis

  def p_signature_none(self, p):
    """signature :"""
    p[0] = None

  def p_type_tuple(self, p):
    # Used for function types, e.g.  # Callable[[args...], return]
    """type : LBRACKET maybe_type_list RBRACKET"""
    p[0] = pytd.GenericType(pytd.NamedType("tuple"), tuple(p[2]))

  def p_type_list_1(self, p):
    """type_list : type """
    p[0] = [p[1]]

  def p_type_list(self, p):
    """type_list : type_list COMMA type """
    p[0] = p[1] + [p[3]]

  def p_maybe_type_list(self, p):
    """maybe_type_list : type_list"""
    p[0] = p[1]

  def p_maybe_type_list_0(self, p):
    """maybe_type_list : """
    p[0] = []

  def p_type_and(self, p):
    """type : type AND type"""
    # TODO(kramm): Unless we bring interfaces back, it's not clear when
    #              "type1 and type2" would be useful for anything. We
    #              should remove it.
    # This rule depends on precedence specification
    # IntersectionType flattens any contained IntersectinType's
    p[0] = pytd.IntersectionType((p[1], p[3]))

  def p_type_or(self, p):
    """type : type OR type"""
    # This rule depends on precedence specification
    # UnionType flattens any contained UnionType's
    p[0] = pytd.UnionType((p[1], p[3]))

  # This is parameterized type
  # TODO(raoulDoc): support data types in future?
  # data  Tree a  =  Leaf a | Branch (Tree a) (Tree a)
  # TODO(raoulDoc): should we consider nested generics?

  def p_type_homogeneous(self, p):
    """type : named_or_external_type LBRACKET parameters RBRACKET"""
    _, base_type, _, parameters, _ = p
    if p[1] == pytd.NamedType("typing.Callable"):
      # TODO(kramm): Support Callable[[params], ret].
      p[0] = p[1]
    elif len(parameters) == 2 and parameters[-1] is Ellipsis:
      element_type, _ = parameters
      if element_type is Ellipsis:
        make_syntax_error(self, "[..., ...] not supported", p)
      p[0] = pytd.HomogeneousContainerType(base_type=base_type,
                                           parameters=(element_type,))
    else:
      parameters = tuple(pytd.AnythingType() if p is Ellipsis else p
                         for p in parameters)
      if p[1] == pytd.NamedType("typing.Tuple"):
        # Since we only support homogeneous tuples, convert heterogeneous
        # tuples to tuples of a union.
        if len(parameters) > 1:
          element_type = pytd.UnionType(parameters)
        else:
          element_type, = parameters
        p[0] = pytd.HomogeneousContainerType(base_type=base_type,
                                             parameters=(element_type,))
      else:
        p[0] = pytd.GenericType(base_type=base_type, parameters=parameters)

  def p_type_paren(self, p):
    """type : LPAREN type RPAREN"""
    p[0] = p[2]

  def p_type_name(self, p):
    """type : named_or_external_type"""
    p[0] = p[1]

  def p_named_or_external_type(self, p):
    """named_or_external_type : NAME"""
    _, name = p
    if name in self.aliases:
      p[0] = self.aliases[name]
    else:
      p[0] = pytd.NamedType(name)

  def p_named_or_external_type_multi(self, p):
    """named_or_external_type : module_name DOT NAME"""
    _, module_name, _, name = p
    p[0] = pytd.NamedType(module_name + "." + name)

  def p_type_unknown(self, p):
    """type : QUESTIONMARK"""
    p[0] = pytd.AnythingType()

  def p_type_nothing(self, p):
    """type : NOTHING"""
    p[0] = pytd.NothingType()

  def p_module_name_1(self, p):
    """module_name : NAME"""
    p[0] = p[1]

  def p_module_name_multi(self, p):
    """module_name : module_name DOT NAME"""
    p[0] = p[1] + "." + p[3]

  def p_error(self, t):
    if t is None:
      make_syntax_error(self, "Unexpected EOF", self.lexer.lexer)
    else:
      make_syntax_error(self, "Unexpected %r" % t.type, t)

  def ValidateParamList(self, p, param_list):
    """Validate and sanitize a param_list.

    Does checks that are harder to do with grammar.

    Args:
      p: YaccProduction from a rule containing param_list.
      param_list: param_list element of p.

    Returns:
      A Params instance.

    Raises:
      ParseError: param_list didn't follow our syntax.
    """
    # TODO(kramm): Disallow "self" and "cls" as names for param (if it's not
    # the first parameter).

    params = []
    seen_star = False
    seen_starstar = False
    has_bare_star = False
    stararg = None
    starstararg = None

    for i, param in enumerate(param_list):
      if param.name.startswith("*") and not param.name.startswith("**"):
        # *args
        if seen_star:
          make_syntax_error(self, "Unexpected second *", p)
        if seen_starstar:
          make_syntax_error(self, "* after **", p)
        if param.name == "*" and i == len(param_list) - 1:
          make_syntax_error(self, "Named arguments must follow bare *", p)
        seen_star = True
        has_bare_star = param.name == "*"
        if param.name != "*":
          stararg = param.Replace(name=param.name[1:])
      elif param.name.startswith("**"):
        # **kwargs
        if seen_starstar:
          make_syntax_error(self, "Unexpected second **", p)
        if i != len(param_list) - 1:
          make_syntax_error(self, "**%s must be last parameter" % param.name, p)
        seen_starstar = True
        starstararg = param.Replace(name=param.name[2:])
      else:
        params.append(param.Replace(kwonly=seen_star))

    return Params(params,
                  stararg,
                  starstararg,
                  has_bare_star=has_bare_star)

  def TryParseSignatureAsProperty(self, full_signature):
    """Given a signature, see if it corresponds to a @property.

    Return whether it's compatible with a @property, and the properties' type
    if specified in the signature's return value (for @property methods) or
    argument (for @foo.setter methods).

    Arguments:
      full_signature: NameAndSig

    Returns:
      (is_property: bool, property_type: Union[None, NamedType, ...?)].
    """
    name, signature, decorators, _ = full_signature
    # TODO(acaceres): validate full_signature.external_code?

    def MaybePropertyDecorator(dec_string):
      return "." in dec_string or "property" == dec_string

    if all(not MaybePropertyDecorator(d) for d in decorators):
      return False, None

    if 1 != len(decorators):
      make_syntax_error(
          self, "Can't handle more than one decorator for %s" % name, None)

    decorator = decorators[0]
    num_params = len(signature.params)
    property_type = None
    is_valid = False

    if "property" == decorator:
      is_valid = (1 == num_params)
      property_type = signature.return_type
    elif 1 == decorator.count("."):
      dec_name, dec_type = decorator.split(".")
      if "setter" == dec_type and 2 == num_params:
        is_valid = True
        property_type = signature.params[1].type
        if property_type == pytd.NamedType("object"):
          # default, different from signature.return_type
          property_type = None
      elif "deleter" == dec_type:
        is_valid = (1 == num_params)

      is_valid &= (dec_name == name)

    # Property decorators are the only decorators where we accept dotted-names,
    # so any other dotted-name uses will throw an error here.
    if not is_valid:
      make_syntax_error(
          self, "Unhandled decorator: %s" % decorator, None)

    return True, property_type

  def MergeSignatures(self, signatures):
    """Given a list of pytd function signature declarations, group them by name.

    Converts a list of NameAndSig items to a list of Functions and a list of
    Constants (grouping signatures by name). Constants are derived from
    functions with @property decorators.

    Arguments:
      signatures: List[NameAndSig].

    Returns:
      Tuple[List[pytd.Function], List[pytd.Constant]].
    """
    name_to_property_type = collections.OrderedDict()
    method_signatures = []
    for signature in signatures:
      is_property, property_type = self.TryParseSignatureAsProperty(signature)
      if is_property:
        # Any methods with a decorator that looks like one of {@property,
        # @foo.setter, @foo.deleter) will get merged into a Constant.
        name = signature.name
        if property_type or name not in name_to_property_type:
          name_to_property_type[name] = property_type
          # TODO(acaceres): warn if incompatible types? Or only take type
          # from @property, not @foo.setter? Take last non-None for now.
      else:
        method_signatures.append(signature)

    name_to_signatures = collections.OrderedDict()
    # map name to (# external_code is {False,True}):
    name_external = collections.defaultdict(lambda: {False: 0, True: 0})

    name_to_decorators = {}
    for name, signature, decorators, external_code in method_signatures:
      if name in name_to_property_type:
        make_syntax_error(
            self, "Incompatible signatures for %s" % name,
            None)

      if name not in name_to_signatures:
        name_to_signatures[name] = []
        name_to_decorators[name] = decorators

      if name_to_decorators[name] != decorators:
        make_syntax_error(
            self, "Overloaded signatures for %s disagree on decorators" % name,
            None)

      name_to_signatures[name].append(signature)
      name_external[name][external_code] += 1

    self.VerifyPythonCode(name_external)
    methods = []
    for name, signatures in name_to_signatures.items():
      kind = pytd.METHOD
      decorators = name_to_decorators[name]
      if "classmethod" in decorators:
        kind = pytd.CLASSMETHOD
      if name == "__new__" or "staticmethod" in decorators:
        kind = pytd.STATICMETHOD
      if name_external[name][True]:
        methods.append(pytd.ExternalFunction(name, (), kind))
      else:
        methods.append(pytd.Function(name, tuple(signatures), kind))

    constants = []
    for name, property_type in name_to_property_type.items():
      if not property_type:
        property_type = pytd.AnythingType()
      constants.append(pytd.Constant(name, property_type))

    return methods, constants

  def VerifyPythonCode(self, name_external):
    for name in name_external:
      if name_external[name][True] > 1:
        raise make_syntax_error(self, "Multiple PYTHONCODEs for %s" %
                                name, None)
      if name_external[name][True] and name_external[name][False]:
        raise make_syntax_error(self, "Mixed pytd and PYTHONCODEs for %s" %
                                name, None)

_shared_parser = None


def TypeDeclParser():
  """Return a shared parser for TypeDeclUnits.

  This instance is shared by all callers to TypeDeclParser, thus is not
  appropriate for multi-threadeded or reentrant usage.

  Returns:
    A _TypeDeclParser instance.
  """
  global _shared_parser
  if _shared_parser is None:
    _shared_parser = _TypeDeclParser()
  return _shared_parser


def _find_line_and_column(lexpos, src):
  """Determine column and line contents, for pretty-printing."""
  # TODO(pludemann): use regexp to split on r'[\r\n]' (for Windows, old MacOS):
  if lexpos is not None and src is not None:
    last_line_offset = src.rfind("\n", 0, lexpos) + 1
    line, _, _ = src[last_line_offset:].partition("\n")
    column = lexpos - last_line_offset + 1
    if not line:
      line = None  # don't allow empty lines
    return column, line
  else:
    return None, None


def make_syntax_error(parser_or_tokenizer, msg, p):
  """Convert a parser error into a SyntaxError and throw it."""
  # TODO(pludemann): add test cases for this (including beginning/end of file,
  #                  lexer error, parser error)
  # TODO(kramm): Add test cases for all the various places where this function
  #              is used (duplicate detection etc.)

  if isinstance(p, yacc.YaccProduction):
    lineno = p.lineno(1)
    column, line = _find_line_and_column(p.lexpos(1), parser_or_tokenizer.src)
  elif isinstance(p, (lex.LexToken, lex.Lexer)):
    lineno = p.lineno
    column, line = _find_line_and_column(p.lexpos, parser_or_tokenizer.src)
  elif p is None:
    lineno = None
    column, line = None, None
  else:
    assert False, "Invalid error data %r" % p
  raise ParseError(msg, parser_or_tokenizer.filename, lineno, column, line)


def parse_string(string, name=None, filename=None,
                 python_version=DEFAULT_VERSION):
  return TypeDeclParser().Parse(string, name, filename, version=python_version)
