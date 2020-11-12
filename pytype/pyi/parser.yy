%skeleton "lalr1.cc"
// This file can work with bison 3.0.4. However, we set the minimum
// required version to 3.0.2 as that is the version of bison one can install
// with apt-get on the Travis Trusty VMs.
%require "3.0.2"
%defines

%locations

%lex-param {void* scanner}
%parse-param {void* scanner}
%parse-param {pytype::Context* ctx}

%define parse.error verbose

%define api.prefix {pytype}
%define api.namespace {pytype}

%code requires {
#include <Python.h>

#include "lexer.h"
#include "parser.h"


#if PY_MAJOR_VERSION >= 3
#  define PyString_FromString PyUnicode_FromString
#  define PyString_FromFormat PyUnicode_FromFormat
#  define PyString_AsString(ob) \
        (PyUnicode_Check(ob) ? PyUnicode_AsUTF8(ob) : PyBytes_AsString(ob))
#endif
} // %code requires

%code {
namespace {
PyObject* DOT_STRING = PyString_FromString(".");

/* Helper functions for building up lists. */
PyObject* StartList(PyObject* item);
PyObject* AppendList(PyObject* list, PyObject* item);
PyObject* ExtendList(PyObject* dst, PyObject* src);

}  // end namespace


// Check that a python value is not NULL.  This must be a macro because it
// calls YYERROR (which is a goto).
#define CHECK(x, loc) do { if (x == NULL) {\
    ctx->SetErrorLocation(loc); \
    YYERROR; \
  }} while(0)

// pytypelex is generated in lexer.lex.cc, but because it uses semantic_type and
// location, it must be declared here.
int pytypelex(pytype::parser::semantic_type* lvalp, pytype::location* llocp,
              void* scanner);

} // %code

%union{
  PyObject* obj;
  const char* str;
}

/* This token value is defined by flex, give it a nice name. */
%token END 0 "end of file"

/* Tokens with PyObject values */
%token <obj> NAME NUMBER STRING LEXERROR

/* Reserved words. */
%token ASYNC CLASS DEF ELSE ELIF IF OR AND PASS IMPORT FROM AS RAISE
%token NOTHING NAMEDTUPLE COLL_NAMEDTUPLE TYPEDDICT TYPEVAR
/* Punctuation. */
%token ARROW ELLIPSIS EQ NE LE GE
/* Other. */
%token INDENT DEDENT TRIPLEQUOTED TYPECOMMENT

/* Most nonterminals have an obj value. */
%type <obj> start unit alldefs if_stmt if_and_elifs
%type <obj> class_if_stmt class_if_and_elifs
%type <obj> if_cond elif_cond else_cond condition version_tuple
%type <obj> constantdef alias_or_constant
%type <obj> typevardef typevar_args typevar_kwargs typevar_kwarg
%type <obj> classdef class_name parents parent_list parent maybe_class_funcs
%type <obj> class_funcs funcdefs
%type <obj> importdef import_items import_item from_list from_items from_item import_name
%type <obj> funcdef funcname decorators decorator maybe_async params param_list param param_type
%type <obj> param_default param_star_name return maybe_body
%type <obj> body body_stmt
%type <obj> type type_parameters type_parameter
%type <obj> named_tuple_fields named_tuple_field_list named_tuple_field
%type <obj> coll_named_tuple_fields coll_named_tuple_field_list coll_named_tuple_field
%type <obj> typed_dict_fields typed_dict_field_dict typed_dict_field maybe_typed_dict_kwarg
%type <obj> maybe_string_list string_list
%type <obj> maybe_type_list type_list type_tuple_elements type_tuple_literal
%type <obj> dotted_name
%type <obj> getitem_key
%type <obj> maybe_number

/* Decrement ref counts of any non-null lvals. */
%destructor { Py_CLEAR($$); } <*>

/* Nonterminals that use non-object values.  Note that these also require
 * a custom %destructor.
 */
%type <str> condition_op

/* The following nonterminals do not have a value, and are not included in
 * the above %type directives.
 *
 * pass_or_ellipsis empty_body maybe_comma
 */

%left OR
%left AND

%start start


%%

/* The value stack (i.e. $1) should be treated as new references, owned
 * by the stack up until the action is called, at which point the action
 * is responsible for properly decrementing the refcount.  The action is
 * also responsible for pushing a new reference back onto the stack ($$).
 * When an action uses ctx->Call(), these references can be properly counted
 * simply by using N instead of O in the argument format string.  In fact, N
 * is almost always going to be the right choice for values that are coming
 * from the stack or ctx->Value() since those are all new references.
 * O should be used only when working with a borrowed reference (i.e. Py_None).
 */

start
  : unit END { ctx->SetAndDelResult($1); $$ = NULL; }
  | TRIPLEQUOTED unit END { ctx->SetAndDelResult($2); $$ = NULL; }
  ;

unit
  : alldefs
  ;

alldefs
  : alldefs constantdef { $$ = AppendList($1, $2); }
  | alldefs funcdef { $$ = AppendList($1, $2); }
  | alldefs importdef { $$ = $1; Py_DECREF($2); }
  | alldefs alias_or_constant {
      $$ = $1;
      PyObject* tmp = ctx->Call(kAddAliasOrConstant, "(N)", $2);
      CHECK(tmp, @$);
      Py_DECREF(tmp);
    }
  | alldefs classdef { $$ = AppendList($1, $2); }
  | alldefs typevardef { $$ = $1; Py_DECREF($2); }
  | alldefs if_stmt {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", $2);
      CHECK(tmp, @2);
      $$ = ExtendList($1, tmp);
    }
  | { $$ = PyList_New(0); }
  ;

maybe_type_ignore
  : typeignore
  |
  ;

/* TODO(rechen): maybe_class_funcs contains all class attributes, not just
 * functions; rename it to something less confusing.
 */
classdef
  : decorators CLASS class_name parents ':' maybe_type_ignore maybe_class_funcs
    {
      $$ = ctx->Call(kNewClass, "(NNNN)", $1, $3, $4, $7);
      // Fix location tracking. See funcdef.
      @$.begin = @3.begin;
      CHECK($$, @$);
    }
  ;

class_name
  : NAME {
      // Do not borrow the $1 reference since it is also returned later
      // in $$.  Use O instead of N in the format string.
      PyObject* tmp = ctx->Call(kRegisterClassName, "(O)", $1);
      CHECK(tmp, @$);
      Py_DECREF(tmp);
      $$ = $1;
    }
  ;

parents
  : '(' parent_list ')' { $$ = $2; }
  | '(' ')' { $$ = PyList_New(0); }
  |  /* EMPTY */ { $$ = PyList_New(0); }
  ;

parent_list
  : parent_list ',' parent { $$ = AppendList($1, $3); }
  | parent { $$ = StartList($1); }
  ;

parent
  : type { $$ = $1; }
  | NAME '=' type { $$ = Py_BuildValue("(NN)", $1, $3); }
  | NAMEDTUPLE { $$ = PyString_FromString("NamedTuple"); }
  | TYPEDDICT {
      $$ = ctx->Call(kNewType, "(N)", PyString_FromString("TypedDict"));
      CHECK($$, @$);
    }
  ;

maybe_class_funcs
  : pass_or_ellipsis maybe_type_ignore { $$ = PyList_New(0); }
  | INDENT class_funcs DEDENT { $$ = $2; }
  | INDENT TRIPLEQUOTED class_funcs DEDENT { $$ = $3; }
  ;

class_funcs
  : pass_or_ellipsis { $$ = PyList_New(0); }
  | funcdefs
  ;

funcdefs
  : funcdefs constantdef { $$ = AppendList($1, $2); }
  | funcdefs alias_or_constant {
      PyObject* tmp = ctx->Call(kNewAliasOrConstant, "(N)", $2);
      CHECK(tmp, @$);
      $$ = AppendList($1, tmp);
    }
  | funcdefs funcdef { $$ = AppendList($1, $2); }
  | funcdefs class_if_stmt {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", $2);
      CHECK(tmp, @2);
      $$ = ExtendList($1, tmp);
    }
  | funcdefs classdef { $$ = AppendList($1, $2); }
  | /* EMPTY */ { $$ = PyList_New(0); }
  ;

if_stmt
  /* Optional ELSE clause after all IF/ELIF/... clauses. */
  : if_and_elifs else_cond ':' INDENT alldefs DEDENT {
      $$ = AppendList($1, Py_BuildValue("(NN)", $2, $5));
    }
  | if_and_elifs
  ;

if_and_elifs
  /* Always start with IF */
  : if_cond ':' INDENT alldefs DEDENT {
      $$ = Py_BuildValue("[(NN)]", $1, $4);
    }
  /* Then zero or more ELIF clauses */
  | if_and_elifs elif_cond ':' INDENT alldefs DEDENT {
      $$ = AppendList($1, Py_BuildValue("(NN)", $2, $5));
    }
  ;

/* Classes accept a smaller set of definitions (funcdefs instead of
 * alldefs).  The corresponding "if" statement thus requires its own
 * set of productions which are similar to the top level if, except they
 * recurse to funcdefs instead of alldefs.
 */

class_if_stmt
  /* Optional ELSE clause after all IF/ELIF/... clauses. */
  : class_if_and_elifs else_cond ':' INDENT funcdefs DEDENT {
      $$ = AppendList($1, Py_BuildValue("(NN)", $2, $5));
    }
  | class_if_and_elifs
  ;

class_if_and_elifs
  /* Always start with IF */
  : if_cond ':' INDENT funcdefs DEDENT {
      $$ = Py_BuildValue("[(NN)]", $1, $4);
    }
  /* Then zero or more ELIF clauses */
  | class_if_and_elifs elif_cond ':' INDENT funcdefs DEDENT {
      $$ = AppendList($1, Py_BuildValue("(NN)", $2, $5));
    }
  ;

/* if_cond, elif_cond, and else_cond appear in their own rules in order
 * to trigger an action before processing the body of the corresponding
 * clause.  Although Bison does support mid-rule actions, they don't
 * work well with %type declarations and destructors.
 */

if_cond
  : IF condition { $$ = ctx->Call(kIfBegin, "(N)", $2); CHECK($$, @$); }
  ;

elif_cond
  : ELIF condition { $$ = ctx->Call(kIfElif, "(N)", $2); CHECK($$, @$); }
  ;

else_cond
  : ELSE { $$ = ctx->Call(kIfElse, "()"); CHECK($$, @$); }
  ;

condition
  : dotted_name condition_op STRING {
      $$ = Py_BuildValue("((NO)sN)", $1, Py_None, $2, $3);
    }
  | dotted_name condition_op version_tuple {
      $$ = Py_BuildValue("((NO)sN)", $1, Py_None, $2, $3);
    }
  | dotted_name '[' getitem_key ']' condition_op NUMBER {
      $$ = Py_BuildValue("((NN)sN)", $1, $3, $5, $6);
    }
  | dotted_name '[' getitem_key ']' condition_op version_tuple {
      $$ = Py_BuildValue("((NN)sN)", $1, $3, $5, $6);
    }
  | condition AND condition { $$ = Py_BuildValue("(NsN)", $1, "and", $3); }
  | condition OR condition { $$ = Py_BuildValue("(NsN)", $1, "or", $3); }
  | '(' condition ')' { $$ = $2; }
  ;

version_tuple
  : '(' NUMBER ',' ')' { $$ = Py_BuildValue("(N)", $2); }
  | '(' NUMBER ',' NUMBER ')' { $$ = Py_BuildValue("(NN)", $2, $4); }
  | '(' NUMBER ',' NUMBER ',' NUMBER ')' {
      $$ = Py_BuildValue("(NNN)", $2, $4, $6);
    }
  ;

condition_op
  : '<' { $$ = "<"; }
  | '>' { $$ = ">"; }
  | LE  { $$ = "<="; }
  | GE  { $$ = ">="; }
  | EQ  { $$ = "=="; }
  | NE  { $$ = "!="; }
  ;

constantdef
  : NAME '=' NUMBER {
      $$ = ctx->Call(kNewConstant, "(NN)", $1, $3);
      CHECK($$, @$);
    }
  | NAME '=' STRING {
      $$ = ctx->Call(kNewConstant, "(NN)", $1, $3);
      CHECK($$, @$);
    }
  | NAME '=' type_tuple_literal {
      $$ = ctx->Call(kNewConstant, "(NN)", $1, $3);
      CHECK($$, @$);
    }
  | NAME '=' ELLIPSIS {
      $$ = ctx->Call(kNewConstant, "(NN)", $1, ctx->Value(kAnything));
      CHECK($$, @$);
    }
  | NAME '=' ELLIPSIS TYPECOMMENT type maybe_type_ignore {
      $$ = ctx->Call(kNewConstant, "(NN)", $1, $5);
      CHECK($$, @$);
    }
  | NAME ':' type maybe_type_ignore {
      $$ = ctx->Call(kNewConstant, "(NN)", $1, $3);
      CHECK($$, @$);
    }
  | NAME ':' type '=' ELLIPSIS maybe_type_ignore {
      $$ = ctx->Call(kNewConstant, "(NN)", $1, $3);
      CHECK($$, @$);
    }
  | TYPEDDICT ':' type maybe_type_ignore {
      $$ = ctx->Call(kNewConstant, "(NN)", PyString_FromString("TypedDict"), $3);
      CHECK($$, @$);
    }
  | TYPEDDICT ':' type '=' ELLIPSIS maybe_type_ignore {
      $$ = ctx->Call(kNewConstant, "(NN)", PyString_FromString("TypedDict"), $3);
      CHECK($$, @$);
    }
  ;

importdef
  : IMPORT import_items maybe_type_ignore {
      $$ = ctx->Call(kAddImport, "(ON)", Py_None, $2);
      CHECK($$, @$);
    }
  | FROM import_name IMPORT from_list maybe_type_ignore {
      $$ = ctx->Call(kAddImport, "(NN)", $2, $4);
      CHECK($$, @$);
    }
  | FROM '.' IMPORT from_list maybe_type_ignore {
      // Special-case "from . import" and pass in a __PACKAGE__ token that
      // the Python parser code will rewrite to the current package name.
      $$ = ctx->Call(kAddImport, "(sN)", "__PACKAGE__", $4);
      CHECK($$, @$);
    }
  | FROM '.' '.' IMPORT from_list maybe_type_ignore {
      // Special-case "from .. import" and pass in a __PARENT__ token that
      // the Python parser code will rewrite to the parent package name.
      $$ = ctx->Call(kAddImport, "(sN)", "__PARENT__", $5);
      CHECK($$, @$);
    }
  ;

import_items
  : import_items ',' import_item { $$ = AppendList($1, $3); }
  | import_item { $$ = StartList($1); }
  ;

import_item
  : dotted_name
  | dotted_name AS NAME { $$ = Py_BuildValue("(NN)", $1, $3); }
  ;


import_name
  : dotted_name
  | '.' import_name {
      $$ = PyString_FromFormat(".%s", PyString_AsString($2));
      Py_DECREF($2);
    }
  ;

from_list
  : from_items
  | '(' from_items ')' { $$ = $2; }
  | '(' from_items ',' ')' { $$ = $2; }
  ;

from_items
  : from_items ',' from_item { $$ = AppendList($1, $3); }
  | from_item { $$ = StartList($1); }
  ;

from_item
  : NAME
  | NAMEDTUPLE {
      $$ = PyString_FromString("NamedTuple");
    }
  | COLL_NAMEDTUPLE {
      $$ = PyString_FromString("namedtuple");
    }
  | TYPEDDICT {
      $$ = PyString_FromString("TypedDict");
    }
  | TYPEVAR {
      $$ = PyString_FromString("TypeVar");
    }
  | '*' {
      $$ = PyString_FromString("*");
    }
  | NAME AS NAME { $$ = Py_BuildValue("(NN)", $1, $3); }
  ;

alias_or_constant
  : NAME '=' type maybe_type_ignore { $$ = Py_BuildValue("(NN)", $1, $3); }
  | NAME '=' '[' maybe_string_list ']' maybe_type_ignore { $$ = Py_BuildValue("(NN)", $1, $4); }
  ;

maybe_string_list
  : string_list maybe_comma { $$ = $1; }
  | /* EMPTY */ { $$ = PyList_New(0); }
  ;

string_list
  : string_list ',' STRING { $$ = AppendList($1, $3); }
  | STRING { $$ = StartList($1); }
  ;

typevardef
  : NAME '=' TYPEVAR '(' STRING typevar_args ')' {
      $$ = ctx->Call(kAddTypeVar, "(NNN)", $1, $5, $6);
      CHECK($$, @$);
    }
  ;

typevar_args
  : /* EMPTY */ { $$ = Py_BuildValue("(OO)", Py_None, Py_None); }
  | ',' type_list { $$ = Py_BuildValue("(NO)", $2, Py_None); }
  | ',' typevar_kwargs { $$ = Py_BuildValue("(ON)", Py_None, $2); }
  | ',' type_list ',' typevar_kwargs { $$ = Py_BuildValue("(NN)", $2, $4); }
  ;

typevar_kwargs
  : typevar_kwargs ',' typevar_kwarg { $$ = AppendList($1, $3); }
  | typevar_kwarg { $$ = StartList($1); }
  ;

typevar_kwarg
  : NAME '=' type { $$ = Py_BuildValue("(NN)", $1, $3); }
  // for typeshed
  | NAME '=' STRING { $$ = Py_BuildValue("(NN)", $1, $3); }
  ;

funcdef
  : decorators maybe_async DEF funcname '(' maybe_type_ignore params ')' return
    maybe_body {
      $$ = ctx->Call(kNewFunction, "(NONNNN)", $1, $2, $4, $7, $9, $10);
      // Decorators is nullable and messes up the location tracking by
      // using the previous symbol as the start location for this production,
      // which is very misleading.  It is better to ignore decorators and
      // pretend the production started with DEF.  Even when decorators are
      // present the error line will be close enough to be helpful.
      @$.begin = @3.begin;
      CHECK($$, @$);
    }
  ;

funcname
  : NAME { $$ = $1; }
  | COLL_NAMEDTUPLE { $$ = PyString_FromString("namedtuple"); }
  | TYPEDDICT { $$ = PyString_FromString("TypedDict"); }
  ;

decorators
  : decorators decorator { $$ = AppendList($1, $2); }
  | /* EMPTY */ { $$ = PyList_New(0); }
  ;

decorator
  : '@' dotted_name maybe_type_ignore { $$ = $2; }
  ;

maybe_async
  : ASYNC { $$ = Py_True; }
  | /* EMPTY */ { $$ = Py_False; }
  ;

params
  : param_list maybe_comma { $$ = $1; }
  | /* EMPTY */ { $$ = PyList_New(0); }
  ;

param_list
  // The maybe_type_ignore is a hack to support multiline function definitions
  // with a type: ignore directive on the first line, e.g.
  //    def foo(self,  # type: ignore
  //            x: int, ...)
  // The pattern is found in typeshed, and keeps the pyi files more readable and
  // maintainable, so it's worth supporting, but it's messier to try to support
  // just this exact case, so allowing a type: ignore after the comma of any
  // param is a reasonable workaround.
  : param_list ',' maybe_type_ignore param { $$ = AppendList($1, $4); }
  | param { $$ = StartList($1); }
  ;

param
  : NAME param_type param_default { $$ = Py_BuildValue("(NNN)", $1, $2, $3); }
  | '*' { $$ = Py_BuildValue("(sOO)", "*", Py_None, Py_None); }
  | param_star_name param_type { $$ = Py_BuildValue("(NNO)", $1, $2, Py_None); }
  | ELLIPSIS { $$ = ctx->Value(kEllipsis); }
  ;

param_type
  : ':' type { $$ = $2; }
  | /* EMPTY */ { Py_INCREF(Py_None); $$ = Py_None; }
  ;

param_default
  : '=' NAME { $$ = $2; }
  | '=' NUMBER { $$ = $2; }
  | '=' ELLIPSIS { $$ = ctx->Value(kEllipsis); }
  | { Py_INCREF(Py_None); $$ = Py_None; }
  ;

param_star_name
  : '*' NAME { $$ = PyString_FromFormat("*%s", PyString_AsString($2)); }
  | '*' '*' NAME { $$ = PyString_FromFormat("**%s", PyString_AsString($3)); }
  ;

return
  : ARROW type { $$ = $2; }
  | /* EMPTY */ { $$ = ctx->Value(kAnything); }
  ;

typeignore
  : TYPECOMMENT NAME { Py_DecRef($2); }
  | TYPECOMMENT NAME '[' maybe_type_list ']' {
      Py_DecRef($2);
      Py_DecRef($4);
    }
  ;

maybe_body
  : ':' typeignore INDENT body DEDENT { $$ = $4; }
  | ':' INDENT body DEDENT { $$ = $3; }
  | empty_body { $$ = PyList_New(0); }
  ;

empty_body
  : ':' pass_or_ellipsis
  | ':' pass_or_ellipsis typeignore
  | ':' typeignore pass_or_ellipsis
  | ':' typeignore INDENT pass_or_ellipsis DEDENT
  | ':' INDENT pass_or_ellipsis DEDENT
  | ':' INDENT TRIPLEQUOTED DEDENT
  | /* EMPTY */
  ;

body
  : body body_stmt { $$ = AppendList($1, $2); }
  | body_stmt { $$ = StartList($1); }
  ;

body_stmt
  : NAME '=' type { $$ = Py_BuildValue("(NN)", $1, $3); }
  | RAISE type { $$ = $2; }
  | RAISE type '(' ')' { $$ = $2; }
  ;

type_parameters
  : type_parameters ',' type_parameter { $$ = AppendList($1, $3); }
  | type_parameter { $$ = StartList($1); }
  ;

type_parameter
  : type { $$ = $1; }
  | ELLIPSIS { $$ = ctx->Value(kEllipsis); }
  // These rules are needed for typing.Literal
  | NUMBER { $$ = $1; }
  | STRING { $$ = $1; }
  // This rule is needed for Callable[[...], ...]
  | '[' maybe_type_list ']' {
      $$ = ctx->Call(kNewType, "(sN)", "tuple", $2);
      CHECK($$, @$);
    }
  ;

maybe_type_list
  : type_list maybe_comma { $$ = $1; }
  | /* EMPTY */ { $$ = PyList_New(0); }
  ;

type_list
  : type_list ',' type { $$ = AppendList($1, $3); }
  | type { $$ = StartList($1); }
  ;

type
  : dotted_name {
      $$ = ctx->Call(kNewType, "(N)", $1);
      CHECK($$, @$);
    }
  | dotted_name '[' '(' ')' ']' {
      $$ = ctx->Call(kNewType, "(NN)", $1, PyList_New(0));
      CHECK($$, @$);
    }
  | dotted_name '[' type_parameters maybe_comma ']' {
      $$ = ctx->Call(kNewType, "(NN)", $1, $3);
      CHECK($$, @$);
    }
  | NAMEDTUPLE '(' STRING ',' named_tuple_fields maybe_comma ')' {
      $$ = ctx->Call(kNewNamedTuple, "(NN)", $3, $5);
      CHECK($$, @$);
    }
  | COLL_NAMEDTUPLE '(' STRING ',' coll_named_tuple_fields maybe_comma ')' {
      $$ = ctx->Call(kNewNamedTuple, "(NN)", $3, $5);
      CHECK($$, @$);
    }
  | TYPEDDICT '(' STRING ',' typed_dict_fields maybe_typed_dict_kwarg ')' {
      $$ = ctx->Call(kNewTypedDict, "(NNN)", $3, $5, $6);
      CHECK($$, @$);
    }
  | '(' type ')' { $$ = $2; }
  | type AND type { $$ = ctx->Call(kNewIntersectionType, "([NN])", $1, $3); }
  | type OR type { $$ = ctx->Call(kNewUnionType, "([NN])", $1, $3); }
  | '?' { $$ = ctx->Value(kAnything); }
  | NOTHING { $$ = ctx->Value(kNothing); }
  ;

named_tuple_fields
  : '[' named_tuple_field_list maybe_comma ']' { $$ = $2; }
  | '[' ']' { $$ = PyList_New(0); }
  ;

named_tuple_field_list
  : named_tuple_field_list ',' named_tuple_field { $$ = AppendList($1, $3); }
  | named_tuple_field { $$ = StartList($1); }
  ;

named_tuple_field
  : '(' STRING ',' type maybe_comma ')'  { $$ = Py_BuildValue("(NN)", $2, $4); }
  ;

maybe_comma
  : ','
  | /* EMPTY */
  ;

coll_named_tuple_fields
  : '[' coll_named_tuple_field_list maybe_comma ']' { $$ = $2; }
  | '[' ']' { $$ = PyList_New(0); }
  ;

coll_named_tuple_field_list
  : coll_named_tuple_field_list ',' coll_named_tuple_field {
      $$ = AppendList($1, $3);
    }
  | coll_named_tuple_field { $$ = StartList($1); }
  ;

coll_named_tuple_field
  : STRING { $$ = Py_BuildValue("(NN)", $1, ctx->Value(kAnything)); }
  ;

typed_dict_fields
  : '{' typed_dict_field_dict maybe_comma '}' { $$ = $2; }
  | '{' '}' { $$ = PyDict_New(); }
  ;

typed_dict_field_dict
  : typed_dict_field_dict ',' typed_dict_field {
      PyDict_Update($1, $3);
      $$ = $1;
      Py_DECREF($3);
    }
  | typed_dict_field { $$ = $1; }
  ;

typed_dict_field
  : STRING ':' NAME { $$ = Py_BuildValue("{N: N}", $1, $3); }
  ;

maybe_typed_dict_kwarg
  : ',' NAME '=' type maybe_comma { $$ = Py_BuildValue("(NN)", $2, $4); }
  | maybe_comma { $$ = Py_None; }
  ;

/* Handle the case of a "regular" tuple of at least two elements, separated by
 * commas. Optional trailing commas, and the one-element case with a required
 * trailing comma, are handled in type_tuple_literal */
type_tuple_elements
  : type_tuple_elements ',' type { $$ = AppendList($1, $3); }
  | type ',' type { $$ = Py_BuildValue("(NN)", $1, $3); }
  ;

/* Allow types to be specified in the following forms:
 *   string_types = (str, bytes)
 *   string_types = (str,)
 *   string_types = str,
 */
type_tuple_literal
  : '(' type_tuple_elements maybe_comma ')' {
      Py_DECREF($2);
      $$ = ctx->Value(kTuple);
    }

  | '(' type ',' ')' {
      Py_DECREF($2);
      $$ = ctx->Value(kTuple);
    }
  ;
    /* typeshed does this in a few places */
  | type ',' {
      Py_DECREF($1);
      $$ = ctx->Value(kTuple);
    }
  ;

dotted_name
  : NAME { $$ = $1; }
  | dotted_name '.' NAME {
#if PY_MAJOR_VERSION >= 3
      $1 = PyUnicode_Concat($1, DOT_STRING);
      $1 = PyUnicode_Concat($1, $3);
      Py_DECREF($3);
#else
      PyString_Concat(&$1, DOT_STRING);
      PyString_ConcatAndDel(&$1, $3);
#endif
      $$ = $1;
    }
  ;

getitem_key
  : NUMBER { $$ = $1; }
  | maybe_number ':' maybe_number {
      PyObject* slice = PySlice_New($1, $3, NULL);
      CHECK(slice, @$);
      $$ = slice;
    }
  | maybe_number ':' maybe_number ':' maybe_number {
      PyObject* slice = PySlice_New($1, $3, $5);
      CHECK(slice, @$);
      $$ = slice;
    }
  ;

maybe_number
  : NUMBER { $$ = $1; }
  | /* EMPTY */ { $$ = NULL; }
  ;

pass_or_ellipsis
  : PASS
  | ELLIPSIS
  ;

%%

void pytype::parser::error(const location& loc, const std::string& msg) {
  ctx->SetErrorLocation(loc);
  pytype::Lexer* lexer = pytypeget_extra(scanner);
  if (lexer->error_message_) {
    PyErr_SetObject(ctx->Value(pytype::kParseError), lexer->error_message_);
  } else {
    PyErr_SetString(ctx->Value(pytype::kParseError), msg.c_str());
  }
}

namespace {

PyObject* StartList(PyObject* item) {
  return Py_BuildValue("[N]", item);
}

PyObject* AppendList(PyObject* list, PyObject* item) {
  PyList_Append(list, item);
  Py_DECREF(item);
  return list;
}

PyObject* ExtendList(PyObject* dst, PyObject* src) {
  // Add items from src to dst (both of which must be lists) and return src.
  // Borrows the reference to src.
  Py_ssize_t count = PyList_Size(src);
  for (Py_ssize_t i=0; i < count; ++i) {
    PyList_Append(dst, PyList_GetItem(src, i));
  }
  Py_DECREF(src);
  return dst;
}

}  // end namespace
