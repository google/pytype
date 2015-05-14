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

# pylint: disable=g-bad-name, g-short-docstring-punctuation
# pylint: disable=g-doc-args, g-no-space-after-docstring-summary
# pylint: disable=g-space-before-docstring-summary
# pylint: disable=g-backslash-continuation
# pylint: disable=line-too-long

import collections
import hashlib
import sys
import traceback
from ply import lex
from ply import yacc
from pytype.pytd import pytd
from pytype.pytd.parse import parser_constants
from pytype.pytd.parse import visitors


DEFAULT_VERSION = (2, 7, 6)


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
  t_ARROW = r'->'
  t_AT = r'@'
  t_COLON = r':'
  t_COLONEQUALS = r':='
  t_COMMA = r','
  t_DEDENT = r'(?!d)d'
  t_DOT = r'\.'
  t_EQ = r'=='
  t_INDENT = r'(?!i)i'
  t_NE = r'!='
  t_QUESTIONMARK = r'\?'

  reserved = parser_constants.RESERVED

  # Define keyword tokens, so parser knows about them.
  # We generate them in t_NAME.
  locals().update({'t_' + id.upper(): id for id in reserved})

  tokens = [
      'ARROW',
      'AT',
      'COLON',
      'COLONEQUALS',
      'COMMA',
      # 'COMMENT',  # Not used in the grammar; only used to discard comments
      'DEDENT',
      'DOT',
      'LE',
      'GE',
      'EQ',
      'NE',
      'INDENT',
      'LBRACKET',
      'LPAREN',
      'NAME',
      'NUMBER',
      'QUESTIONMARK',
      'RBRACKET',
      'RPAREN',
      'STRING',
  ] + [id.upper() for id in reserved]

  def CancelLBracket(self):
    self.open_brackets -= 1

  def CancelRBracket(self):
    self.open_brackets += 1

  # LE and GE need to be functions (not constants) because ply prioritizes
  # functions, and we need them before LBRACKET / RBRACKET.
  def t_LE(self, t):
    r"""<="""
    return t

  def t_GE(self, t):
    r""">="""
    return t

  def t_LBRACKET(self, t):
    r"""<"""
    self.open_brackets += 1
    return t

  def t_RBRACKET(self, t):
    r""">"""
    self.open_brackets -= 1
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
    make_syntax_error(self, 'Use spaces, not tabs', t)

  def t_WHITESPACE(self, t):
    r"""[\n\r ]+"""  # explicit [...] instead of \s, to omit tab

    if self.queued_dedents:
      self.queued_dedents -= 1
      t.type = 'DEDENT'
      return t
    t.lexer.lineno += t.value.count('\n')
    if self.open_brackets:
      # inside (...) and <...>, we allow any kind of whitespace and indentation.
      return
    spaces_and_newlines = t.value.replace('\r', '')
    i = spaces_and_newlines.rfind('\n')
    if i < 0:
      # whitespace in the middle of line
      return

    eof = t.lexer.lexpos >= len(t.lexer.lexdata)
    if eof:
      # Ignore white space at end of file.
      return None

    if not eof and t.lexer.lexdata[t.lexer.lexpos] in '#':
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
        make_syntax_error(self, 'invalid dedent', t)
      if self.queued_dedents:
        t.lexer.skip(-1)  # reprocess this whitespace
      t.type = 'DEDENT'
      return t
    elif indent > self.indent_stack[-1]:
      self.indent_stack.append(indent)
      t.type = 'INDENT'
      return t
    else:
      # same indent as before, ignore.
      return None

  def t_NAME(self, t):
    # For handling identifiers that are reserved words in PyTD or that start
    # with '~' or contain a dash, we also allow an escape with backticks.  If
    # you change this, also change parser_constants._BACKTICK_NAME.
    (r"""([a-zA-Z_][a-zA-Z0-9_-]*)|"""
     r"""(`[a-zA-Z_~][-a-zA-Z0-9_]*`)""")
    if t.value[0] == r'`':
      # Permit token names to be enclosed by backticks (``), to allow for names
      # that are keywords in pytd syntax.
      assert t.value[-1] == r'`'
      t.value = t.value[1:-1]
      t.type = 'NAME'
    elif t.value in self.reserved:
      t.type = t.value.upper()
    return t

  def t_STRING(self, t):
    (r"""'([^']|\\')*'|"""
     r'"([^"]|\\")*"')
    # TODO(pludemann): full Python string syntax (e.g., """...""", r"...")
    # TODO(pludemann): use something like devtools/python/library_types/ast.py
    #                  _ParseLiteral
    t.value = eval(t.value)  # pylint: disable=eval-used
    return t

  def t_NUMBER(self, t):
    r"""[-+]?[0-9]+(\.[0-9]*)*"""
    # TODO(pludemann): full Python number syntax
    # TODO(pludemann): move +/- to grammar?
    t.value = Number(t.value)
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
      t.type = 'DEDENT'
      t.value = None
      return t
    else:
      return None

  def t_error(self, t):
    make_syntax_error(self, "Illegal character '%s'" % t.value[0], t)


Params = collections.namedtuple('_', ['required', 'has_optional'])
NameAndSig = collections.namedtuple('_', ['name', 'signature', 'external_code'])


class Number(collections.namedtuple('Number', ['string'])):
  """Store a number token (float or int, or a version number)."""

  def AsFloatOrInt(self):
    return float(self.string) if '.' in self.string else int(self.string)

  def AsVersion(self, parser, p):
    components = self.string.split('.')
    if (len(components) not in (1, 2, 3) or
        any(not digit.isdigit() for digit in components) or
        not all(0 <= int(digit) <= 9 for digit in components)):
      make_syntax_error(parser,
                        'Illegal version \"%s\"' % self.string, p)
    prefix = tuple(int(digit) for digit in components)
    return (prefix + (0, 0, 0))[0:3]


class Mutator(object):
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
    self.name = name
    self.new_type = new_type
    self.successful = False

  def VisitParameter(self, p):
    if p.name == self.name:
      self.successful = True
      return pytd.MutableParameter(p.name, p.type, self.new_type)
    else:
      return p


class InsertTypeParameters(object):
  """Visitor for inserting TypeParameter instances."""

  def VisitClass(self, node):
    return node.Visit(visitors.ReplaceTypes({p.name: p.type_param
                                             for p in node.template}))

  def VisitSignature(self, node):
    return node.Visit(visitors.ReplaceTypes({p.name: p.type_param
                                             for p in node.template}))


def CheckStringIsPython(parser, string, p):
  if string == 'python':
    return
  make_syntax_error(
      parser, 'If conditions can only depend on the \'python\' variable', p)


class TypeDeclParser(object):
  """Parser for type declaration language."""

  def __init__(self, version=None, **kwargs):
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
    self.python_version = version or DEFAULT_VERSION

    self.parser = yacc.yacc(
        start='start',  # warning: ply ignores this
        module=self,
        debug=False,
        write_tables=False,
        # debuglog=yacc.PlyLogger(sys.stderr),
        # errorlog=yacc.NullLogger(),  # If you really want to suppress messages
        **kwargs)

  def Parse(self, src, name=None, filename='<string>', **kwargs):
    self.src = src  # Keep a copy of what's being parsed
    self.filename = filename if filename else '<string>'
    self.lexer.set_parse_info(self.src, self.filename)
    ast = self.parser.parse(src, **kwargs)
    # If there's no name, compute an MD5 to make something unique but comparable
    # from the src. (The original code had object.__repr__(src) which meant that
    # in effect object identity was forced.)
    name = name or hashlib.md5(src).hexdigest()
    return ast.Visit(InsertTypeParameters()).Replace(name=name)

  precedence = (
      ('left', 'OR'),
      ('left', 'AND'),
      ('left', 'COMMA'),
  )

  def p_start(self, p):
    """start : unit"""
    p[0] = p[1]

  def p_unit(self, p):
    """unit : alldefs"""
    funcdefs = [x for x in p[1] if isinstance(x, NameAndSig)]
    constants = [x for x in p[1] if isinstance(x, pytd.Constant)]
    classes = [x for x in p[1] if isinstance(x, pytd.Class)]
    all_names = (list(set(f.name for f in funcdefs)) +
                 [c.name for c in constants] +
                 [c.name for c in classes])
    duplicates = [name
                  for name, count in collections.Counter(all_names).items()
                  if count >= 2]
    if duplicates:
      make_syntax_error(
          self, 'Duplicate top-level identifier(s):' + ', '.join(duplicates), p)
    p[0] = pytd.TypeDeclUnit(name=None,  # replaced later, in Parse
                             constants=tuple(constants),
                             functions=tuple(self.MergeSignatures(funcdefs)),
                             classes=tuple(classes),
                             modules=())

  def p_alldefs_constant(self, p):
    """alldefs : alldefs constantdef"""
    p[0] = p[1] + [p[2]]

  def p_alldefs_class(self, p):
    """alldefs : alldefs classdef"""
    p[0] = p[1] + [p[2]]

  def p_alldefs_func(self, p):
    """alldefs : alldefs funcdef"""
    p[0] = p[1] + [p[2]]

  def p_alldefs_if(self, p):
    """alldefs : alldefs toplevel_if"""
    p[0] = p[1] + p[2]

  def p_alldefs_null(self, p):
    """alldefs :"""
    p[0] = []

  def p_toplevel_if(self, p):
    """toplevel_if : IF version_expr COLON INDENT alldefs DEDENT"""
    p[0] = p[5] if p[2] else []

  def p_toplevel_if_else(self, p):
    """toplevel_if : IF version_expr COLON INDENT alldefs DEDENT ELSE COLON INDENT alldefs DEDENT"""
    p[0] = p[5] if p[2] else p[10]

  def p_funcdefs_if(self, p):
    """funcdefs_if : IF version_expr COLON INDENT funcdefs DEDENT"""
    p[0] = p[5] if p[2] else []

  def p_funcdefs_if_else(self, p):
    """funcdefs_if : IF version_expr COLON INDENT funcdefs DEDENT ELSE COLON INDENT funcdefs DEDENT"""
    p[0] = p[5] if p[2] else p[10]

  def p_version_expr_lt(self, p):
    """version_expr : NAME RBRACKET NUMBER"""
    self.lexer.CancelRBracket()
    CheckStringIsPython(self, p[1], p)
    p[0] = self.python_version > p[3].AsVersion(self, p)

  def p_version_expr_gt(self, p):
    """version_expr : NAME LBRACKET NUMBER"""
    self.lexer.CancelLBracket()
    CheckStringIsPython(self, p[1], p)
    p[0] = self.python_version < p[3].AsVersion(self, p)

  def p_version_expr_ge(self, p):
    """version_expr : NAME GE NUMBER"""
    CheckStringIsPython(self, p[1], p)
    p[0] = self.python_version >= p[3].AsVersion(self, p)

  def p_version_expr_le(self, p):
    """version_expr : NAME LE NUMBER"""
    CheckStringIsPython(self, p[1], p)
    p[0] = self.python_version <= p[3].AsVersion(self, p)

  def p_version_expr_eq(self, p):
    """version_expr : NAME EQ NUMBER"""
    CheckStringIsPython(self, p[1], p)
    p[0] = self.python_version == p[3].AsVersion(self, p)

  def p_version_expr_ne(self, p):
    """version_expr : NAME NE NUMBER"""
    CheckStringIsPython(self, p[1], p)
    p[0] = self.python_version != p[3].AsVersion(self, p)

  # TODO(raoulDoc): doesn't support nested classes
  def p_classdef(self, p):
    """classdef : CLASS qname template parents COLON INDENT class_funcs DEDENT"""
    #             1     2     3        4       5     6      7           8
    methoddefs = [x for x in p[7] if isinstance(x, NameAndSig)]
    constants = [x for x in p[7] if isinstance(x, pytd.Constant)]
    if (set(f.name for f in methoddefs) | set(c.name for c in constants) !=
        set(d.name for d in p[7])):
      # TODO(kramm): raise a syntax error right when the identifier is defined.
      raise make_syntax_error(self, 'Duplicate identifier(s)', p)
    # Check that template parameter names are unique:
    template_names = {t.name for t in p[3]}
    for _, sig, _ in methoddefs:
      for t in sig.template:
        if t.name in template_names:
          raise make_syntax_error(self, 'Duplicate template parameter %s' %
                                  t.name, p)
    if p[4] == [pytd.NothingType()]:
      bases = ()
    else:
      # Everything implicitly subclasses "object"
      bases = tuple(p[4]) or (pytd.NamedType('object'),)
    cls = pytd.Class(name=p[2], parents=bases,
                     methods=tuple(self.MergeSignatures(methoddefs)),
                     constants=tuple(constants), template=tuple(p[3]))
    p[0] = cls.Visit(visitors.AdjustSelf())

  def p_class_funcs(self, p):
    """class_funcs : funcdefs"""
    p[0] = p[1]

  def p_class_funcs_pass(self, p):
    """class_funcs : PASS"""
    p[0] = []

  def p_parents(self, p):
    """parents : LPAREN parent_list RPAREN"""
    p[0] = p[2]

  def p_parents_null(self, p):
    """parents :"""
    p[0] = []

  def p_parent_list_multi(self, p):
    """parent_list : parent_list COMMA type"""
    p[0] = p[1] + [p[3]]

  def p_parent_list_1(self, p):
    """parent_list : type"""
    p[0] = [p[1]]

  def p_template(self, p):
    """template : LBRACKET template_items RBRACKET"""
    p[0] = p[2]
    # Verify we don't have duplicate identifiers.
    names = [template.name for template in p[2]]
    for name in names:
      if names.count(name) > 1:
        make_syntax_error(self, 'Duplicate name %s' % name, p)

  def p_template_null(self, p):
    """template : """  # pylint: disable=g-short-docstring-space
    # TODO(pludemann): test cases
    p[0] = []

  def p_template_items_multi(self, p):
    """template_items : template_items COMMA template_item"""
    p[0] = p[1] + [p[3]]

  def p_template_items_1(self, p):
    """template_items : template_item"""
    p[0] = [p[1]]

  def p_template_item(self, p):
    """template_item : NAME"""
    p[0] = pytd.TemplateItem(pytd.TypeParameter(p[1]))

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

  def p_constantdef(self, p):
    """constantdef : NAME COLON type"""
    p[0] = pytd.Constant(p[1], p[3])

  def p_funcdef(self, p):
    """funcdef : DEF NAME template LPAREN params RPAREN return raises signature maybe_body"""
    #            1   2    3        4      5      6      7      8      9         10
    # TODO(kramm): Output a warning if we already encountered a signature
    #              with these types (but potentially different argument names)
    if p[2] == '__init__' and isinstance(p[7], pytd.AnythingType):
      # TODO(pludemann): see TODO for p_return_null.
      # for __init__, the default return value is None -> NoneType
      ret = pytd.NamedType('NoneType')
    else:
      ret = p[7]
    signature = pytd.Signature(params=tuple(p[5].required), return_type=ret,
                               exceptions=tuple(p[8]), template=tuple(p[3]),
                               has_optional=p[5].has_optional)
    for mutator in p[10]:
      signature = signature.Visit(mutator)
      if not mutator.successful:
        make_syntax_error(self, 'No parameter named %s' % mutator.name, p)
    p[0] = NameAndSig(name=p[2], signature=signature, external_code=False)

  def p_funcdef_code(self, p):
    """funcdef : DEF NAME PYTHONCODE"""
    # TODO(pludemann): DEF qname PYTHONCODE function_name
    p[0] = NameAndSig(
        name=p[2],
        # signature is for completeness - it's ignored
        signature=pytd.Signature(params=(),
                                 return_type=pytd.NothingType(),
                                 exceptions=(),
                                 template=(),
                                 has_optional=False),
        external_code=True)

  def p_empty_body(self, p):
    """maybe_body :"""
    p[0] = []

  def p_has_body(self, p):
    """maybe_body : COLON INDENT body DEDENT"""
    p[0] = p[3]

  def p_body_1(self, p):
    """body : mutator"""
    p[0] = [p[1]]

  def p_body_multiple(self, p):
    """body : mutator body"""
    p[0] = p[1] + [p[2]]

  def p_mutator(self, p):
    """mutator : NAME COLONEQUALS type"""
    p[0] = Mutator(p[1], p[3])

  def p_return(self, p):
    """return : ARROW type"""
    p[0] = p[2]

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

  def p_params_multi(self, p):
    """params : params COMMA param"""
    # TODO(kramm): Disallow "self" and "cls" as names for param (since it's not
    # the first parameter).
    p[0] = Params(p[1].required + [p[3]], has_optional=False)

  def p_params_ellipsis(self, p):
    """params : params COMMA DOT DOT DOT"""
    p[0] = Params(p[1].required, has_optional=True)

  def p_params_1(self, p):
    """params : param"""
    p[0] = Params([p[1]], has_optional=False)

  def p_params_only_ellipsis(self, p):
    """params : DOT DOT DOT"""
    p[0] = Params([], has_optional=True)

  def p_params_null(self, p):
    """params :"""
    p[0] = Params([], has_optional=False)

  def p_param(self, p):
    """param : NAME"""
    # type is optional and defaults to "object"
    p[0] = pytd.Parameter(p[1], pytd.NamedType('object'))

  def p_param_and_type(self, p):
    """param : NAME COLON type"""
    p[0] = pytd.Parameter(p[1], p[3])

  def p_raise(self, p):
    """raises : RAISES exceptions"""
    p[0] = p[2]

  def p_raise_null(self, p):
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

  def p_signature_(self, p):
    """signature : AT STRING"""
    p[0] = p[2]

  def p_signature_none(self, p):
    """signature :"""
    p[0] = None

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

  # TODO(pludemann): for generic types, we explicitly don't allow
  #                  type<...> but insist on identifier<...> ... this
  #                  is because the grammar would be ambiguous, but for some
  #                  reason PLY didn't come up with a shift/reduce conflict but
  #                  just quietly promoted OR and AND above LBRACKET
  #                  (or, at least, that's what I think happened). Probably best
  #                  to not use precedence and write everything out fully, even
  #                  if it's a more verbose grammar.

  def p_type_homogeneous(self, p):
    """type : qname LBRACKET parameters RBRACKET"""
    if len(p[3]) == 1:
      element_type, = p[3]
      p[0] = pytd.HomogeneousContainerType(base_type=pytd.NamedType(p[1]),
                                           parameters=(element_type,))
    else:
      p[0] = pytd.GenericType(base_type=pytd.NamedType(p[1]), parameters=p[3])

  def p_type_generic_1(self, p):
    """type : qname LBRACKET parameters COMMA RBRACKET"""
    p[0] = pytd.GenericType(base_type=pytd.NamedType(p[1]), parameters=p[3])

  def p_type_paren(self, p):
    """type : LPAREN type RPAREN"""
    p[0] = p[2]

  def p_type_name(self, p):
    """type : qname"""
    p[0] = pytd.NamedType(p[1])

  def p_type_unknown(self, p):
    """type : QUESTIONMARK"""
    p[0] = pytd.AnythingType()

  def p_type_nothing(self, p):
    """type : NOTHING"""
    p[0] = pytd.NothingType()

  def p_type_constant(self, p):
    """type : scalar"""
    p[0] = p[1]

  def p_qname_1(self, p):
    """qname : NAME"""
    p[0] = p[1]

  def p_qname_multi(self, p):
    """qname : qname DOT NAME"""
    p[0] = p[1] + '.' + p[3]

  def p_scalar_string(self, p):
    """scalar : STRING"""
    p[0] = pytd.Scalar(p[1])

  def p_scalar_number(self, p):
    """scalar : NUMBER"""
    p[0] = pytd.Scalar(p[1].AsFloatOrInt())

  def p_error(self, t):
    if t is None:
      make_syntax_error(self, 'Parse error: unexpected EOF', t)
    else:
      raise make_syntax_error(self, 'Parse error: unexpected %r' % t.type, t)

  def MergeSignatures(self, signatures):
    """Given a list of pytd function signature declarations, group them by name.

    Converts a list of NameAndSignature items to a list of Functions (grouping
    signatures by name).

    Arguments:
      signatures: A list of tuples (name, signature).

    Returns:
      A list of instances of pytd.FunctionWithSignatures.
    """

    name_to_signatures = collections.OrderedDict()
    # map name to (# external_code is {False,True}):
    name_external = collections.defaultdict(lambda: {False: 0, True: 0})

    for name, signature, external_code in signatures:
      if name not in name_to_signatures:
        name_to_signatures[name] = []
      name_to_signatures[name].append(signature)
      name_external[name][external_code] += 1
    self.VerifyPythonCode(name_external)
    ret = []
    for name, signatures in name_to_signatures.items():
      if name_external[name][True]:
        ret.append(pytd.FunctionWithCode(name, None))
      else:
        ret.append(pytd.FunctionWithSignatures(name, tuple(signatures)))
    return ret

  def VerifyPythonCode(self, name_external):
    for name in name_external:
      if name_external[name][True] > 1:
        raise make_syntax_error(self, 'Multiple PYTHONCODEs for %s' %
                                name, None)
      if name_external[name][True] and name_external[name][False]:
        raise make_syntax_error(self, 'Mixed pytd and PYTHONCODEs for %s' %
                                name, None)


def make_syntax_error(parser_or_tokenizer, msg, p):
  """Convert a parser error into a SyntaxError and throw it."""
  # SyntaxError(msg, (filename, lineno, offset, line))
  # is output in a nice format by traceback.print_exception
  # TODO(pludemann): add test cases for this (including beginning/end of file,
  #                  lexer error, parser error)
  # TODO(kramm): Add test cases for all the various places where this function
  #              is used (duplicate detection etc.)

  if isinstance(p, yacc.YaccProduction):
    # TODO(kramm): pretty-print lexpos / lineno
    lexpos = p.lexpos(1)
    lineno = p.lineno(1)
    # TODO(kramm): The code below only works in the tokenizer, not in the
    # parser. Additionally, ply's yacc catches SyntaxError, but has broken
    # error handling (so we throw a SystemError for the time being).
    raise SystemError(msg, parser_or_tokenizer.filename, (lexpos, lineno))
  elif p is None:
    raise SystemError(msg, parser_or_tokenizer.filename)

  # Convert the lexer's offset to an offset within the line with the error
  # TODO(pludemann): use regexp to split on r'[\r\n]' (for Windows, old MacOS):
  last_line_offset = parser_or_tokenizer.src.rfind('\n', 0, p.lexpos) + 1
  line, _, _ = parser_or_tokenizer.src[last_line_offset:].partition('\n')

  raise SyntaxError(msg,
                    (parser_or_tokenizer.filename,
                     p.lineno, p.lexpos - last_line_offset + 1, line))


def parse_string(string, name=None, filename=None,
                 python_version=DEFAULT_VERSION):
  try:
    return TypeDeclParser(python_version).Parse(string, name, filename)
  except SyntaxError as unused_exception:
    # without all the tedious traceback stuff from PLY:
    # TODO(pludemann): What happens if we don't catch SyntaxError?
    traceback.print_exception(sys.exc_type, sys.exc_value, None)
    sys.exit(1)


def parse_file(filename, name=None, python_version=DEFAULT_VERSION):
  with open(filename) as f:
    return parse_string(f.read(), name, filename, python_version)
