%option prefix="pytype"
%option 8bit
%option noyywrap
%option reentrant
%option never-interactive
%option warn
%option nodefault
%option yylineno
%option nounistd

%option bison-bridge
%option bison-locations

 /* Exclusive start states. */
%x NEWLINE PENDING TRIPLE1 TRIPLE2 COMMENT

%{
#include "lexer.h"
#include "parser.tab.hh"
#include "location.hh"

#define YY_EXTRA_TYPE pytype::Lexer*

#define YY_USER_INIT BEGIN(NEWLINE);

#define YYSTYPE pytype::parser::semantic_type
#define YYLTYPE pytype::location

#define YY_USER_ACTION \
  yylval->obj=NULL; \
  yylloc->begin.line = yylineno; \
  yylloc->begin.column = yycolumn; \
  yylloc->end.line = yylineno; \
  yylloc->end.column = yycolumn + yyleng - 1; \
  yycolumn += yyleng;

#if PY_MAJOR_VERSION >= 3
#  define PyInt_FromString PyLong_FromString
#  define PyString_FromFormat PyUnicode_FromFormat
#  define PyString_FromString PyUnicode_FromString
#  define PyString_FromStringAndSize PyUnicode_FromStringAndSize
#endif

typedef pytype::parser::token t;
%}

%%

\n { BEGIN(NEWLINE); yycolumn=1; }  /* Determine indentation. */
[ ]+ { }  /* Ignore whitespace */

 /* Punctuation */
[@*:,.=?<>.] { return yytext[0]; }
\[ { ++yyextra->bracket_count_; return yytext[0]; }
\] { --yyextra->bracket_count_; return yytext[0]; }
\( { ++yyextra->bracket_count_; return yytext[0]; }
\) { --yyextra->bracket_count_; return yytext[0]; }
\{ { ++yyextra->bracket_count_; return yytext[0]; }
\} { --yyextra->bracket_count_; return yytext[0]; }

 /* STRING */
 /* TODO(rechen): the string parsing below doesn't handle escaped quotes. */

 /* Omit \x27, the single quote character. */
[bu]?'[\x20-\x26 \x28-\x7E]*' {
  yylval->obj=PyString_FromString(yytext);
  return t::STRING;
}

 /* Omit \x22, the double quote character. */
[bu]?\"[\x20-\x21 \x23-\x7E]*\" {
  yylval->obj=PyString_FromString(yytext);
  return t::STRING;
}

 /* Multi-character punctuation. */
"->" { return t::ARROW; }
"..." { return t::ELLIPSIS; }
"==" { return t::EQ; }
"!=" { return t::NE; }
"<=" { return t::LE; }
">=" { return t::GE; }

 /* Reserved words (must also be added to parse_ext.cc and match
  * parser_constant.py).
  */

"async" { return t::ASYNC; }
"class" { return t::CLASS; }
"def" { return t::DEF; }
"else" { return t::ELSE; }
"elif" { return t::ELIF; }
"if" { return t::IF; }
"or" { return t::OR; }
"and" { return t::AND; }
"pass" { return t::PASS; }
"import" { return t::IMPORT; }
"from" { return t::FROM; }
"as" { return t::AS; }
"raise" { return t::RAISE; }
"nothing" { return t::NOTHING; }
"NamedTuple" { return t::NAMEDTUPLE; }
"typing.NamedTuple" { return t::NAMEDTUPLE; }
"namedtuple" { return t::COLL_NAMEDTUPLE; }
"collections.namedtuple" { return t::COLL_NAMEDTUPLE; }
"TypedDict" { return t::TYPEDDICT; }
"typing.TypedDict" { return t::TYPEDDICT; }
"typing_extensions.TypedDict" { return t::TYPEDDICT; }
"TypeVar" { return t::TYPEVAR; }
"typing.TypeVar" { return t::TYPEVAR; }

 /* NAME */
[_[:alpha:]][-_[:alnum:]]* {
  yylval->obj=PyString_FromString(yytext);
  return t::NAME;
}
`[_~[:alpha:]][-_~[:alnum:]]*` {
  yylval->obj=PyString_FromStringAndSize(yytext+1, yyleng-2);
  return t::NAME;
}

 /* NUMBER */
[-+]?[0-9]+  {
  yylval->obj=PyInt_FromString(yytext, NULL, 10);
  return t::NUMBER;
}
[-+]?0b[01]+  {
  yylval->obj=PyInt_FromString(yytext, NULL, 2);
  return t::NUMBER;
}
[-+]?0o[0-7]+  {
  yylval->obj=PyInt_FromString(yytext, NULL, 8);
  return t::NUMBER;
}
[-+]?0x[0-9a-fA-F]+  {
  yylval->obj=PyInt_FromString(yytext, NULL, 16);
  return t::NUMBER;
}
[-+]?[0-9]*\.[0-9]+  {
  yylval->obj=PyFloat_FromDouble(atof(yytext));
  return t::NUMBER;
}
[-+]?[0-9]+\.[0-9]*  {
  yylval->obj=PyFloat_FromDouble(atof(yytext));
  return t::NUMBER;
}

 /* TRIPLEQUOTED */
\'\'\' {
  BEGIN(TRIPLE1);
  yyextra->start_line_ = yylineno;
  yyextra->start_column_ = yycolumn - yyleng;
}
<TRIPLE1>[^'\n]* { }
<TRIPLE1>\n { yycolumn = 1; }
<TRIPLE1>\'\'? { }
<TRIPLE1>\'\'\' {
  BEGIN(INITIAL);
  yylloc->begin.line = yyextra->start_line_;
  yylloc->begin.column = yyextra->start_column_;
  return t::TRIPLEQUOTED;
}

\"\"\" {
  BEGIN(TRIPLE2);
  yyextra->start_line_ = yylineno;
  yyextra->start_column_ = yycolumn - yyleng;
}
<TRIPLE2>[^"\n]* { }
<TRIPLE2>\n { yycolumn = 1; }
<TRIPLE2>\"\"? { }
<TRIPLE2>\"\"\" {
  BEGIN(INITIAL);
  yylloc->begin.line = yyextra->start_line_;
  yylloc->begin.column = yyextra->start_column_;
  return t::TRIPLEQUOTED;
}

\#[ ]*"type:" { return t::TYPECOMMENT; }
\# { BEGIN(COMMENT); }
 /* Due to a quirk of the flex state machine, matching an empty string
  * does not trigger an action, thus <COMMENT>[^\n]* would not by itself
  * trigger a switch to the INITIAL state if the comment were empty.  In
  * order to deal with this, we have two rules for the COMMENT state: the
  * first consumes any non-empty comment and switchtes to INITIAL.  The second
  * consumes a lone newline and moves to the NEWLINE state.
  */
<COMMENT>[^\n]+ { BEGIN(INITIAL); }
<COMMENT>\n { BEGIN(NEWLINE); yycolumn=1; }


 /* NEWLINE state is responsible for processing the whitespace at the start
  * of a line.  It can generate INDENT tokens, queue DEDENT tokens, and
  * eventually exits to either INITIAL or PENDING
  */

 /* Ignore empty lines. */
<NEWLINE>[ ]*\n { yycolumn = 1; }

 /* Ignore comment indentation. */
<NEWLINE>[ ]+/# { BEGIN(INITIAL); }

 /* White space at start of line. */
<NEWLINE>[ ]+ {
  if (yyextra->bracket_count_) {
    // Ignore indentation within brackets.
    BEGIN(INITIAL);
  } else if (yyleng < yyextra->CurrentIndentation()) {
    // Dedent.
    if (!yyextra->PopIndentationTo(yyleng)) {
      yylval->obj=PyString_FromString("Invalid indentation");
      yyextra->error_message_ = yylval->obj;
      return t::LEXERROR;
    }
    BEGIN(PENDING);
  } else if (yyleng == yyextra->CurrentIndentation()) {
    // No change.
    BEGIN(INITIAL);
  } else {
    // Indent
    yyextra->PushIndentation(yyleng);
    BEGIN(INITIAL);
    return t::INDENT;
  }
}

 /* Anything else - put it back and transition to PENDING or INITIAL. */
<NEWLINE>. {
  yyless(0); yycolumn--;
  if (yyextra->CurrentIndentation()) {
    yyextra->PopIndentationTo(0);
    BEGIN(PENDING);
  } else {
    BEGIN(INITIAL);
  }
}

 /* Remain in the PENDING state not consuming anything until all queued
  * DEDENTS have been returned, then transition to INITIAL.
  */
<PENDING>. {
  yyless(0);
  if (yyextra->PopDedent()) {
    return t::DEDENT;
  } else {
    BEGIN(INITIAL);
  }
}

<<EOF>> {
  if (yyextra->CurrentIndentation()) {
    yyextra->PopIndentationTo(0);
  }
  // Ensure a yylval of NULL, even when returning EOF.
  yylval->obj=NULL;
  if (yyextra->PopDedent()) {
    return t::DEDENT;
  } else {
    yyterminate();
  }
}

 /* Anything we don't understand is an error. */
<*>.|\n {
  yylval->obj=PyString_FromFormat("Illegal character '%c'", yytext[0]);
  yyextra->error_message_ = yylval->obj;
  return t::LEXERROR;
}

%%

namespace pytype {

Lexer::Lexer(const char* data, int len)
    : bracket_count_(0), pending_dedents_(0) {
  yylex_init(&scanner_);
  yyset_extra(this, scanner_);
  yy_scan_bytes(data, len, scanner_);
  // When using scan_bytes() a new buffer is installed without intializing
  // yylineno, thus it must be explicitly initialized.
  yyset_lineno(1, scanner_);
  yyset_column(1, scanner_);

  indents_.push_back(0);
}

Lexer::~Lexer() {
  yylex_destroy(scanner_);
}

void Lexer::PushIndentation(int width) {
  indents_.push_back(width);
}

bool Lexer::PopIndentationTo(int width) {
  if (width < 0) {
    width = 0;
  }
  pending_dedents_ = 0;
  while (indents_.back() > width) {
    indents_.pop_back();
    pending_dedents_++;
  }
  return indents_.back() == width;
}

bool Lexer::PopDedent() {
  if (pending_dedents_) {
    pending_dedents_--;
    return true;
  } else {
    return false;
  }
}

}  // end namespace pytype
