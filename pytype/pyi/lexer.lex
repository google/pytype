%option prefix="pytype"
%option outfile="lexer.lex.cc"
%option 8bit
%option noyywrap
%option reentrant
%option never-interactive
%option warn
%option nodefault
%option yylineno

%option bison-bridge
%option bison-locations

 /* Exclusive start states. */
%x NEWLINE PENDING TRIPLE1 TRIPLE2 COMMENT

%{
#include "lexer.h"

#define YY_EXTRA_TYPE pytype::Lexer*

#define YY_USER_INIT BEGIN(NEWLINE);

#define YY_USER_ACTION \
  yylval->obj=NULL; \
  yylloc->first_line = yylineno; \
  yylloc->first_column = yycolumn; \
  yylloc->last_line = yylineno; \
  yylloc->last_column = yycolumn + yyleng - 1; \
  yycolumn += yyleng;
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

b'' { return BYTESTRING; }
b\"\" { return BYTESTRING; }
u'' { return UNICODESTRING; }
u\"\" { return UNICODESTRING; }

 /* Ignore all other quotes, to simplify processing of forward references. */
['"] { }

 /* Multi-character punctuation. */
"->" { return ARROW; }
":=" { return COLONEQUALS; }
"..." { return ELLIPSIS; }
"==" { return EQ; }
"!=" { return NE; }
"<=" { return LE; }
">=" { return GE; }

 /* Reserved words (must also be added to parse_ext.cc and match
  * parser_constant.py).
  */

"class" { return CLASS; }
"def" { return DEF; }
"else" { return ELSE; }
"elif" { return ELIF; }
"if" { return IF; }
"or" { return OR; }
"and" { return AND; }
"pass" { return PASS; }
"import" { return IMPORT; }
"from" { return FROM; }
"as" { return AS; }
"raise" { return RAISE; }
"nothing" { return NOTHING; }
"NamedTuple" { return NAMEDTUPLE; }
"typing.NamedTuple" { return NAMEDTUPLE; }
"TypeVar" { return TYPEVAR; }
"typing.TypeVar" { return TYPEVAR; }

 /* NAME */
[_[:alpha:]][-_[:alnum:]]* {
#if PY_MAJOR_VERSION >= 3
  yylval->obj=PyUnicode_FromString(yytext);
#else
  yylval->obj=PyString_FromString(yytext);
#endif
  return NAME;
}
`[_~[:alpha:]][-_~[:alnum:]]*` {
#if PY_MAJOR_VERSION >= 3
  yylval->obj=PyUnicode_FromStringAndSize(yytext+1, yyleng-2);
#else
  yylval->obj=PyString_FromStringAndSize(yytext+1, yyleng-2);
#endif
  return NAME;
}

 /* NUMBER */
[-+]?[0-9]+  {
#if PY_MAJOR_VERSION >= 3
  yylval->obj=PyLong_FromString(yytext, NULL, 10);
#else
  yylval->obj=PyInt_FromString(yytext, NULL, 10);
#endif
  return NUMBER;
}
[-+]?[0-9]*\.[0-9]+  {
  yylval->obj=PyFloat_FromDouble(atof(yytext));
  return NUMBER;
}
[-+]?[0-9]+\.[0-9]*  {
  yylval->obj=PyFloat_FromDouble(atof(yytext));
  return NUMBER;
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
  yylloc->first_line = yyextra->start_line_;
  yylloc->first_column = yyextra->start_column_;
  return TRIPLEQUOTED;
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
  yylloc->first_line = yyextra->start_line_;
  yylloc->first_column = yyextra->start_column_;
  return TRIPLEQUOTED;
}

\#[ ]*"type:" { return TYPECOMMENT; }
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
#if PY_MAJOR_VERSION >= 3
      yylval->obj=PyUnicode_FromString("Invalid indentation");
#else
      yylval->obj=PyString_FromString("Invalid indentation");
#endif
      yyextra->error_message_ = yylval->obj;
      return LEXERROR;
    }
    BEGIN(PENDING);
  } else if (yyleng == yyextra->CurrentIndentation()) {
    // No change.
    BEGIN(INITIAL);
  } else {
    // Indent
    yyextra->PushIndentation(yyleng);
    BEGIN(INITIAL);
    return INDENT;
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
    return DEDENT;
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
    return DEDENT;
  } else {
    yyterminate();
  }
}

 /* Anything we don't understand is an error. */
<*>.|\n {
#if PY_MAJOR_VERSION >= 3
  yylval->obj=PyUnicode_FromFormat("Illegal character '%c'", yytext[0]);
#else
  yylval->obj=PyString_FromFormat("Illegal character '%c'", yytext[0]);
#endif
  yyextra->error_message_ = yylval->obj;
  return LEXERROR;
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
