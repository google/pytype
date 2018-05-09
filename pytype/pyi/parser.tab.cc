// A Bison parser, made by GNU Bison 3.0.4.

// Skeleton implementation for Bison LALR(1) parsers in C++

// Copyright (C) 2002-2015 Free Software Foundation, Inc.

// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

// As a special exception, you may create a larger work that contains
// part or all of the Bison parser skeleton and distribute that work
// under terms of your choice, so long as that work isn't itself a
// parser generator using the skeleton or a modified version thereof
// as a parser skeleton.  Alternatively, if you modify or redistribute
// the parser skeleton itself, you may (at your option) remove this
// special exception, which will cause the skeleton and the resulting
// Bison output files to be licensed under the GNU General Public
// License without this special exception.

// This special exception was added by the Free Software Foundation in
// version 2.2 of Bison.

// Take the name prefix into account.
#define yylex   pytypelex

// First part of user declarations.

#line 39 "pyi/parser.tab.cc" // lalr1.cc:404

# ifndef YY_NULLPTR
#  if defined __cplusplus && 201103L <= __cplusplus
#   define YY_NULLPTR nullptr
#  else
#   define YY_NULLPTR 0
#  endif
# endif

#include "parser.tab.hh"

// User implementation prologue.

#line 53 "pyi/parser.tab.cc" // lalr1.cc:412
// Unqualified %code blocks.
#line 31 "parser.yy" // lalr1.cc:413

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


#line 81 "pyi/parser.tab.cc" // lalr1.cc:413


#ifndef YY_
# if defined YYENABLE_NLS && YYENABLE_NLS
#  if ENABLE_NLS
#   include <libintl.h> // FIXME: INFRINGES ON USER NAME SPACE.
#   define YY_(msgid) dgettext ("bison-runtime", msgid)
#  endif
# endif
# ifndef YY_
#  define YY_(msgid) msgid
# endif
#endif

#define YYRHSLOC(Rhs, K) ((Rhs)[K].location)
/* YYLLOC_DEFAULT -- Set CURRENT to span from RHS[1] to RHS[N].
   If N is 0, then set CURRENT to the empty location which ends
   the previous symbol: RHS[0] (always defined).  */

# ifndef YYLLOC_DEFAULT
#  define YYLLOC_DEFAULT(Current, Rhs, N)                               \
    do                                                                  \
      if (N)                                                            \
        {                                                               \
          (Current).begin  = YYRHSLOC (Rhs, 1).begin;                   \
          (Current).end    = YYRHSLOC (Rhs, N).end;                     \
        }                                                               \
      else                                                              \
        {                                                               \
          (Current).begin = (Current).end = YYRHSLOC (Rhs, 0).end;      \
        }                                                               \
    while (/*CONSTCOND*/ false)
# endif


// Suppress unused-variable warnings by "using" E.
#define YYUSE(E) ((void) (E))

// Enable debugging if requested.
#if YYDEBUG

// A pseudo ostream that takes yydebug_ into account.
# define YYCDEBUG if (yydebug_) (*yycdebug_)

# define YY_SYMBOL_PRINT(Title, Symbol)         \
  do {                                          \
    if (yydebug_)                               \
    {                                           \
      *yycdebug_ << Title << ' ';               \
      yy_print_ (*yycdebug_, Symbol);           \
      *yycdebug_ << std::endl;                  \
    }                                           \
  } while (false)

# define YY_REDUCE_PRINT(Rule)          \
  do {                                  \
    if (yydebug_)                       \
      yy_reduce_print_ (Rule);          \
  } while (false)

# define YY_STACK_PRINT()               \
  do {                                  \
    if (yydebug_)                       \
      yystack_print_ ();                \
  } while (false)

#else // !YYDEBUG

# define YYCDEBUG if (false) std::cerr
# define YY_SYMBOL_PRINT(Title, Symbol)  YYUSE(Symbol)
# define YY_REDUCE_PRINT(Rule)           static_cast<void>(0)
# define YY_STACK_PRINT()                static_cast<void>(0)

#endif // !YYDEBUG

#define yyerrok         (yyerrstatus_ = 0)
#define yyclearin       (yyla.clear ())

#define YYACCEPT        goto yyacceptlab
#define YYABORT         goto yyabortlab
#define YYERROR         goto yyerrorlab
#define YYRECOVERING()  (!!yyerrstatus_)

#line 14 "parser.yy" // lalr1.cc:479
namespace pytype {
#line 167 "pyi/parser.tab.cc" // lalr1.cc:479

  /* Return YYSTR after stripping away unnecessary quotes and
     backslashes, so that it's suitable for yyerror.  The heuristic is
     that double-quoting is unnecessary unless the string contains an
     apostrophe, a comma, or backslash (other than backslash-backslash).
     YYSTR is taken from yytname.  */
  std::string
  parser::yytnamerr_ (const char *yystr)
  {
    if (*yystr == '"')
      {
        std::string yyr = "";
        char const *yyp = yystr;

        for (;;)
          switch (*++yyp)
            {
            case '\'':
            case ',':
              goto do_not_strip_quotes;

            case '\\':
              if (*++yyp != '\\')
                goto do_not_strip_quotes;
              // Fall through.
            default:
              yyr += *yyp;
              break;

            case '"':
              return yyr;
            }
      do_not_strip_quotes: ;
      }

    return yystr;
  }


  /// Build a parser object.
  parser::parser (void* scanner_yyarg, pytype::Context* ctx_yyarg)
    :
#if YYDEBUG
      yydebug_ (false),
      yycdebug_ (&std::cerr),
#endif
      scanner (scanner_yyarg),
      ctx (ctx_yyarg)
  {}

  parser::~parser ()
  {}


  /*---------------.
  | Symbol types.  |
  `---------------*/

  inline
  parser::syntax_error::syntax_error (const location_type& l, const std::string& m)
    : std::runtime_error (m)
    , location (l)
  {}

  // basic_symbol.
  template <typename Base>
  inline
  parser::basic_symbol<Base>::basic_symbol ()
    : value ()
  {}

  template <typename Base>
  inline
  parser::basic_symbol<Base>::basic_symbol (const basic_symbol& other)
    : Base (other)
    , value ()
    , location (other.location)
  {
    value = other.value;
  }


  template <typename Base>
  inline
  parser::basic_symbol<Base>::basic_symbol (typename Base::kind_type t, const semantic_type& v, const location_type& l)
    : Base (t)
    , value (v)
    , location (l)
  {}


  /// Constructor for valueless symbols.
  template <typename Base>
  inline
  parser::basic_symbol<Base>::basic_symbol (typename Base::kind_type t, const location_type& l)
    : Base (t)
    , value ()
    , location (l)
  {}

  template <typename Base>
  inline
  parser::basic_symbol<Base>::~basic_symbol ()
  {
    clear ();
  }

  template <typename Base>
  inline
  void
  parser::basic_symbol<Base>::clear ()
  {
    Base::clear ();
  }

  template <typename Base>
  inline
  bool
  parser::basic_symbol<Base>::empty () const
  {
    return Base::type_get () == empty_symbol;
  }

  template <typename Base>
  inline
  void
  parser::basic_symbol<Base>::move (basic_symbol& s)
  {
    super_type::move(s);
    value = s.value;
    location = s.location;
  }

  // by_type.
  inline
  parser::by_type::by_type ()
    : type (empty_symbol)
  {}

  inline
  parser::by_type::by_type (const by_type& other)
    : type (other.type)
  {}

  inline
  parser::by_type::by_type (token_type t)
    : type (yytranslate_ (t))
  {}

  inline
  void
  parser::by_type::clear ()
  {
    type = empty_symbol;
  }

  inline
  void
  parser::by_type::move (by_type& that)
  {
    type = that.type;
    that.clear ();
  }

  inline
  int
  parser::by_type::type_get () const
  {
    return type;
  }


  // by_state.
  inline
  parser::by_state::by_state ()
    : state (empty_state)
  {}

  inline
  parser::by_state::by_state (const by_state& other)
    : state (other.state)
  {}

  inline
  void
  parser::by_state::clear ()
  {
    state = empty_state;
  }

  inline
  void
  parser::by_state::move (by_state& that)
  {
    state = that.state;
    that.clear ();
  }

  inline
  parser::by_state::by_state (state_type s)
    : state (s)
  {}

  inline
  parser::symbol_number_type
  parser::by_state::type_get () const
  {
    if (state == empty_state)
      return empty_symbol;
    else
      return yystos_[state];
  }

  inline
  parser::stack_symbol_type::stack_symbol_type ()
  {}


  inline
  parser::stack_symbol_type::stack_symbol_type (state_type s, symbol_type& that)
    : super_type (s, that.location)
  {
    value = that.value;
    // that is emptied.
    that.type = empty_symbol;
  }

  inline
  parser::stack_symbol_type&
  parser::stack_symbol_type::operator= (const stack_symbol_type& that)
  {
    state = that.state;
    value = that.value;
    location = that.location;
    return *this;
  }


  template <typename Base>
  inline
  void
  parser::yy_destroy_ (const char* yymsg, basic_symbol<Base>& yysym) const
  {
    if (yymsg)
      YY_SYMBOL_PRINT (yymsg, yysym);

    // User destructor.
    switch (yysym.type_get ())
    {
            case 3: // NAME

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 421 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 4: // NUMBER

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 428 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 5: // LEXERROR

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 435 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 47: // start

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 442 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 48: // unit

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 449 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 49: // alldefs

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 456 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 51: // classdef

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 463 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 52: // class_name

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 470 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 53: // parents

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 477 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 54: // parent_list

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 484 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 55: // parent

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 491 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 56: // maybe_class_funcs

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 498 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 57: // class_funcs

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 505 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 58: // funcdefs

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 512 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 59: // if_stmt

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 519 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 60: // if_and_elifs

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 526 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 61: // class_if_stmt

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 533 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 62: // class_if_and_elifs

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 540 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 63: // if_cond

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 547 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 64: // elif_cond

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 554 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 65: // else_cond

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 561 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 66: // condition

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 568 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 67: // version_tuple

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 575 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 68: // condition_op

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.str)); }
#line 582 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 69: // constantdef

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 589 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 70: // importdef

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 596 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 71: // import_items

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 603 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 72: // import_item

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 610 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 73: // import_name

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 617 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 74: // from_list

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 624 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 75: // from_items

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 631 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 76: // from_item

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 638 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 77: // alias_or_constant

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 645 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 78: // typevardef

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 652 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 79: // typevar_args

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 659 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 80: // typevar_kwargs

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 666 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 81: // typevar_kwarg

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 673 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 82: // funcdef

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 680 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 83: // decorators

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 687 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 84: // decorator

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 694 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 85: // params

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 701 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 86: // param_list

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 708 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 87: // param

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 715 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 88: // param_type

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 722 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 89: // param_default

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 729 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 90: // param_star_name

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 736 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 91: // return

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 743 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 93: // maybe_body

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 750 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 95: // body

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 757 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 96: // body_stmt

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 764 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 97: // type_parameters

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 771 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 98: // type_parameter

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 778 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 99: // type

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 785 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 100: // named_tuple_fields

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 792 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 101: // named_tuple_field_list

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 799 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 102: // named_tuple_field

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 806 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 104: // maybe_type_list

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 813 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 105: // type_list

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 820 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 106: // type_tuple_elements

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 827 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 107: // type_tuple_literal

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 834 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 108: // dotted_name

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 841 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 109: // getitem_key

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 848 "pyi/parser.tab.cc" // lalr1.cc:614
        break;

      case 110: // maybe_number

#line 96 "parser.yy" // lalr1.cc:614
        { Py_CLEAR((yysym.value.obj)); }
#line 855 "pyi/parser.tab.cc" // lalr1.cc:614
        break;


      default:
        break;
    }
  }

#if YYDEBUG
  template <typename Base>
  void
  parser::yy_print_ (std::ostream& yyo,
                                     const basic_symbol<Base>& yysym) const
  {
    std::ostream& yyoutput = yyo;
    YYUSE (yyoutput);
    symbol_number_type yytype = yysym.type_get ();
    // Avoid a (spurious) G++ 4.8 warning about "array subscript is
    // below array bounds".
    if (yysym.empty ())
      std::abort ();
    yyo << (yytype < yyntokens_ ? "token" : "nterm")
        << ' ' << yytname_[yytype] << " ("
        << yysym.location << ": ";
    YYUSE (yytype);
    yyo << ')';
  }
#endif

  inline
  void
  parser::yypush_ (const char* m, state_type s, symbol_type& sym)
  {
    stack_symbol_type t (s, sym);
    yypush_ (m, t);
  }

  inline
  void
  parser::yypush_ (const char* m, stack_symbol_type& s)
  {
    if (m)
      YY_SYMBOL_PRINT (m, s);
    yystack_.push (s);
  }

  inline
  void
  parser::yypop_ (unsigned int n)
  {
    yystack_.pop (n);
  }

#if YYDEBUG
  std::ostream&
  parser::debug_stream () const
  {
    return *yycdebug_;
  }

  void
  parser::set_debug_stream (std::ostream& o)
  {
    yycdebug_ = &o;
  }


  parser::debug_level_type
  parser::debug_level () const
  {
    return yydebug_;
  }

  void
  parser::set_debug_level (debug_level_type l)
  {
    yydebug_ = l;
  }
#endif // YYDEBUG

  inline parser::state_type
  parser::yy_lr_goto_state_ (state_type yystate, int yysym)
  {
    int yyr = yypgoto_[yysym - yyntokens_] + yystate;
    if (0 <= yyr && yyr <= yylast_ && yycheck_[yyr] == yystate)
      return yytable_[yyr];
    else
      return yydefgoto_[yysym - yyntokens_];
  }

  inline bool
  parser::yy_pact_value_is_default_ (int yyvalue)
  {
    return yyvalue == yypact_ninf_;
  }

  inline bool
  parser::yy_table_value_is_error_ (int yyvalue)
  {
    return yyvalue == yytable_ninf_;
  }

  int
  parser::parse ()
  {
    // State.
    int yyn;
    /// Length of the RHS of the rule being reduced.
    int yylen = 0;

    // Error handling.
    int yynerrs_ = 0;
    int yyerrstatus_ = 0;

    /// The lookahead symbol.
    symbol_type yyla;

    /// The locations where the error started and ended.
    stack_symbol_type yyerror_range[3];

    /// The return value of parse ().
    int yyresult;

#ifdef __EXCEPTIONS
    // FIXME: This shoud be completely indented.  It is not yet to
    // avoid gratuitous conflicts when merging into the master branch.
    try
#endif // __EXCEPTIONS
      {
    YYCDEBUG << "Starting parse" << std::endl;


    /* Initialize the stack.  The initial state will be set in
       yynewstate, since the latter expects the semantical and the
       location values to have been already stored, initialize these
       stacks with a primary value.  */
    yystack_.clear ();
    yypush_ (YY_NULLPTR, 0, yyla);

    // A new symbol was pushed on the stack.
  yynewstate:
    YYCDEBUG << "Entering state " << yystack_[0].state << std::endl;

    // Accept?
    if (yystack_[0].state == yyfinal_)
      goto yyacceptlab;

    goto yybackup;

    // Backup.
  yybackup:

    // Try to take a decision without lookahead.
    yyn = yypact_[yystack_[0].state];
    if (yy_pact_value_is_default_ (yyn))
      goto yydefault;

    // Read a lookahead token.
    if (yyla.empty ())
      {
        YYCDEBUG << "Reading a token: ";
#ifdef __EXCEPTIONS
        try
#endif // __EXCEPTIONS
          {
            yyla.type = yytranslate_ (yylex (&yyla.value, &yyla.location, scanner));
          }
#ifdef __EXCEPTIONS
        catch (const syntax_error& yyexc)
          {
            error (yyexc);
            goto yyerrlab1;
          }
#endif // __EXCEPTIONS
      }
    YY_SYMBOL_PRINT ("Next token is", yyla);

    /* If the proper action on seeing token YYLA.TYPE is to reduce or
       to detect an error, take that action.  */
    yyn += yyla.type_get ();
    if (yyn < 0 || yylast_ < yyn || yycheck_[yyn] != yyla.type_get ())
      goto yydefault;

    // Reduce or error.
    yyn = yytable_[yyn];
    if (yyn <= 0)
      {
        if (yy_table_value_is_error_ (yyn))
          goto yyerrlab;
        yyn = -yyn;
        goto yyreduce;
      }

    // Count tokens shifted since error; after three, turn off error status.
    if (yyerrstatus_)
      --yyerrstatus_;

    // Shift the lookahead token.
    yypush_ ("Shifting", yyn, yyla);
    goto yynewstate;

  /*-----------------------------------------------------------.
  | yydefault -- do the default action for the current state.  |
  `-----------------------------------------------------------*/
  yydefault:
    yyn = yydefact_[yystack_[0].state];
    if (yyn == 0)
      goto yyerrlab;
    goto yyreduce;

  /*-----------------------------.
  | yyreduce -- Do a reduction.  |
  `-----------------------------*/
  yyreduce:
    yylen = yyr2_[yyn];
    {
      stack_symbol_type yylhs;
      yylhs.state = yy_lr_goto_state_(yystack_[yylen].state, yyr1_[yyn]);
      /* If YYLEN is nonzero, implement the default value of the
         action: '$$ = $1'.  Otherwise, use the top of the stack.

         Otherwise, the following line sets YYLHS.VALUE to garbage.
         This behavior is undocumented and Bison users should not rely
         upon it.  */
      if (yylen)
        yylhs.value = yystack_[yylen - 1].value;
      else
        yylhs.value = yystack_[0].value;

      // Compute the default @$.
      {
        slice<stack_symbol_type, stack_type> slice (yystack_, yylen);
        YYLLOC_DEFAULT (yylhs.location, slice, yylen);
      }

      // Perform the reduction.
      YY_REDUCE_PRINT (yyn);
#ifdef __EXCEPTIONS
      try
#endif // __EXCEPTIONS
        {
          switch (yyn)
            {
  case 2:
#line 129 "parser.yy" // lalr1.cc:867
    { ctx->SetAndDelResult((yystack_[1].value.obj)); (yylhs.value.obj) = NULL; }
#line 1102 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 3:
#line 130 "parser.yy" // lalr1.cc:867
    { ctx->SetAndDelResult((yystack_[1].value.obj)); (yylhs.value.obj) = NULL; }
#line 1108 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 5:
#line 138 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[1].value.obj), (yystack_[0].value.obj)); }
#line 1114 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 6:
#line 139 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[1].value.obj), (yystack_[0].value.obj)); }
#line 1120 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 7:
#line 140 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); Py_DECREF((yystack_[0].value.obj)); }
#line 1126 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 8:
#line 141 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = (yystack_[1].value.obj);
      PyObject* tmp = ctx->Call(kAddAliasOrConstant, "(N)", (yystack_[0].value.obj));
      CHECK(tmp, yylhs.location);
      Py_DECREF(tmp);
    }
#line 1137 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 9:
#line 147 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); Py_DECREF((yystack_[0].value.obj)); }
#line 1143 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 10:
#line 148 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); Py_DECREF((yystack_[0].value.obj)); }
#line 1149 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 11:
#line 149 "parser.yy" // lalr1.cc:867
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yystack_[0].value.obj));
      CHECK(tmp, yystack_[0].location);
      (yylhs.value.obj) = ExtendList((yystack_[1].value.obj), tmp);
    }
#line 1159 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 12:
#line 154 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyList_New(0); }
#line 1165 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 15:
#line 162 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kAddClass, "(NNN)", (yystack_[4].value.obj), (yystack_[3].value.obj), (yystack_[0].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1174 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 16:
#line 169 "parser.yy" // lalr1.cc:867
    {
      // Do not borrow the $1 reference since it is also returned later
      // in $$.  Use O instead of N in the format string.
      PyObject* tmp = ctx->Call(kRegisterClassName, "(O)", (yystack_[0].value.obj));
      CHECK(tmp, yylhs.location);
      Py_DECREF(tmp);
      (yylhs.value.obj) = (yystack_[0].value.obj);
    }
#line 1187 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 17:
#line 180 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); }
#line 1193 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 18:
#line 181 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyList_New(0); }
#line 1199 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 19:
#line 182 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyList_New(0); }
#line 1205 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 20:
#line 186 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1211 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 21:
#line 187 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = StartList((yystack_[0].value.obj)); }
#line 1217 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 22:
#line 191 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[0].value.obj); }
#line 1223 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 23:
#line 192 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1229 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 24:
#line 196 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyList_New(0); }
#line 1235 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 25:
#line 197 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); }
#line 1241 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 26:
#line 198 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); }
#line 1247 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 27:
#line 202 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyList_New(0); }
#line 1253 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 29:
#line 207 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[1].value.obj), (yystack_[0].value.obj)); }
#line 1259 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 30:
#line 208 "parser.yy" // lalr1.cc:867
    {
      PyObject* tmp = ctx->Call(kNewAliasOrConstant, "(N)", (yystack_[0].value.obj));
      CHECK(tmp, yylhs.location);
      (yylhs.value.obj) = AppendList((yystack_[1].value.obj), tmp);
    }
#line 1269 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 31:
#line 213 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[1].value.obj), (yystack_[0].value.obj)); }
#line 1275 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 32:
#line 214 "parser.yy" // lalr1.cc:867
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yystack_[0].value.obj));
      CHECK(tmp, yystack_[0].location);
      (yylhs.value.obj) = ExtendList((yystack_[1].value.obj), tmp);
    }
#line 1285 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 33:
#line 219 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyList_New(0); }
#line 1291 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 34:
#line 224 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = AppendList((yystack_[5].value.obj), Py_BuildValue("(NN)", (yystack_[4].value.obj), (yystack_[1].value.obj)));
    }
#line 1299 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 36:
#line 232 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = Py_BuildValue("[(NN)]", (yystack_[4].value.obj), (yystack_[1].value.obj));
    }
#line 1307 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 37:
#line 236 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = AppendList((yystack_[5].value.obj), Py_BuildValue("(NN)", (yystack_[4].value.obj), (yystack_[1].value.obj)));
    }
#line 1315 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 38:
#line 255 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = AppendList((yystack_[5].value.obj), Py_BuildValue("(NN)", (yystack_[4].value.obj), (yystack_[1].value.obj)));
    }
#line 1323 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 40:
#line 263 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = Py_BuildValue("[(NN)]", (yystack_[4].value.obj), (yystack_[1].value.obj));
    }
#line 1331 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 41:
#line 267 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = AppendList((yystack_[5].value.obj), Py_BuildValue("(NN)", (yystack_[4].value.obj), (yystack_[1].value.obj)));
    }
#line 1339 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 42:
#line 279 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = ctx->Call(kIfBegin, "(N)", (yystack_[0].value.obj)); CHECK((yylhs.value.obj), yylhs.location); }
#line 1345 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 43:
#line 283 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = ctx->Call(kIfElif, "(N)", (yystack_[0].value.obj)); CHECK((yylhs.value.obj), yylhs.location); }
#line 1351 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 44:
#line 287 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = ctx->Call(kIfElse, "()"); CHECK((yylhs.value.obj), yylhs.location); }
#line 1357 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 45:
#line 291 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = Py_BuildValue("((NO)sN)", (yystack_[2].value.obj), Py_None, (yystack_[1].value.str), (yystack_[0].value.obj));
    }
#line 1365 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 46:
#line 294 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = Py_BuildValue("((NO)sN)", (yystack_[2].value.obj), Py_None, (yystack_[1].value.str), (yystack_[0].value.obj));
    }
#line 1373 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 47:
#line 297 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = Py_BuildValue("((NN)sN)", (yystack_[5].value.obj), (yystack_[3].value.obj), (yystack_[1].value.str), (yystack_[0].value.obj));
    }
#line 1381 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 48:
#line 300 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = Py_BuildValue("((NN)sN)", (yystack_[5].value.obj), (yystack_[3].value.obj), (yystack_[1].value.str), (yystack_[0].value.obj));
    }
#line 1389 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 49:
#line 303 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NsN)", (yystack_[2].value.obj), "and", (yystack_[0].value.obj)); }
#line 1395 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 50:
#line 304 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NsN)", (yystack_[2].value.obj), "or", (yystack_[0].value.obj)); }
#line 1401 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 51:
#line 305 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); }
#line 1407 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 52:
#line 310 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(N)", (yystack_[2].value.obj)); }
#line 1413 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 53:
#line 311 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NN)", (yystack_[3].value.obj), (yystack_[1].value.obj)); }
#line 1419 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 54:
#line 312 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = Py_BuildValue("(NNN)", (yystack_[5].value.obj), (yystack_[3].value.obj), (yystack_[1].value.obj));
    }
#line 1427 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 55:
#line 318 "parser.yy" // lalr1.cc:867
    { (yylhs.value.str) = "<"; }
#line 1433 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 56:
#line 319 "parser.yy" // lalr1.cc:867
    { (yylhs.value.str) = ">"; }
#line 1439 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 57:
#line 320 "parser.yy" // lalr1.cc:867
    { (yylhs.value.str) = "<="; }
#line 1445 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 58:
#line 321 "parser.yy" // lalr1.cc:867
    { (yylhs.value.str) = ">="; }
#line 1451 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 59:
#line 322 "parser.yy" // lalr1.cc:867
    { (yylhs.value.str) = "=="; }
#line 1457 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 60:
#line 323 "parser.yy" // lalr1.cc:867
    { (yylhs.value.str) = "!="; }
#line 1463 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 61:
#line 327 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewConstant, "(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1472 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 62:
#line 331 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewConstant, "(NN)", (yystack_[2].value.obj), ctx->Value(kByteString));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1481 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 63:
#line 335 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewConstant, "(NN)", (yystack_[2].value.obj), ctx->Value(kUnicodeString));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1490 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 64:
#line 339 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewConstant, "(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1499 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 65:
#line 343 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewConstant, "(NN)", (yystack_[2].value.obj), ctx->Value(kAnything));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1508 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 66:
#line 347 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewConstant, "(NN)", (yystack_[4].value.obj), (yystack_[0].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1517 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 67:
#line 351 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewConstant, "(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1526 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 68:
#line 355 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewConstant, "(NN)", (yystack_[4].value.obj), (yystack_[2].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1535 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 69:
#line 362 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kAddImport, "(ON)", Py_None, (yystack_[0].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1544 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 70:
#line 366 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kAddImport, "(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1553 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 71:
#line 370 "parser.yy" // lalr1.cc:867
    {
      // Special-case "from . import" and pass in a __PACKAGE__ token that
      // the Python parser code will rewrite to the current package name.
      (yylhs.value.obj) = ctx->Call(kAddImport, "(sN)", "__PACKAGE__", (yystack_[0].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1564 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 72:
#line 379 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1570 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 73:
#line 380 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = StartList((yystack_[0].value.obj)); }
#line 1576 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 75:
#line 384 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1582 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 77:
#line 390 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = PyString_FromFormat(".%s", PyString_AsString((yystack_[0].value.obj)));
      Py_DECREF((yystack_[0].value.obj));
    }
#line 1591 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 79:
#line 398 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); }
#line 1597 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 80:
#line 399 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[2].value.obj); }
#line 1603 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 81:
#line 403 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1609 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 82:
#line 404 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = StartList((yystack_[0].value.obj)); }
#line 1615 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 84:
#line 409 "parser.yy" // lalr1.cc:867
    {
 (yylhs.value.obj) = PyString_FromString("NamedTuple");
 }
#line 1623 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 85:
#line 412 "parser.yy" // lalr1.cc:867
    {
 (yylhs.value.obj) = PyString_FromString("TypeVar");
 }
#line 1631 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 86:
#line 415 "parser.yy" // lalr1.cc:867
    {
 (yylhs.value.obj) = PyString_FromString("*");
 }
#line 1639 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 87:
#line 418 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1645 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 88:
#line 422 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1651 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 89:
#line 426 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kAddTypeVar, "(NNN)", (yystack_[6].value.obj), (yystack_[2].value.obj), (yystack_[1].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1660 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 90:
#line 433 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(OO)", Py_None, Py_None); }
#line 1666 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 91:
#line 434 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NO)", (yystack_[0].value.obj), Py_None); }
#line 1672 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 92:
#line 435 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(ON)", Py_None, (yystack_[0].value.obj)); }
#line 1678 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 93:
#line 436 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1684 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 94:
#line 440 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1690 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 95:
#line 441 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = StartList((yystack_[0].value.obj)); }
#line 1696 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 96:
#line 445 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1702 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 97:
#line 449 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewFunction, "(NNNNN)", (yystack_[7].value.obj), (yystack_[5].value.obj), (yystack_[3].value.obj), (yystack_[1].value.obj), (yystack_[0].value.obj));
      // Decorators is nullable and messes up the location tracking by
      // using the previous symbol as the start location for this production,
      // which is very misleading.  It is better to ignore decorators and
      // pretend the production started with DEF.  Even when decorators are
      // present the error line will be close enough to be helpful.
      //
      // TODO(dbaum): Consider making this smarter and only ignoring decorators
      // when they are empty.  Making decorators non-nullable and having two
      // productions for funcdef would be a reasonable solution.
      yylhs.location.begin = yystack_[6].location.begin;
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1721 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 98:
#line 466 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[1].value.obj), (yystack_[0].value.obj)); }
#line 1727 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 99:
#line 467 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyList_New(0); }
#line 1733 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 100:
#line 471 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); }
#line 1739 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 101:
#line 475 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); }
#line 1745 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 102:
#line 476 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyList_New(0); }
#line 1751 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 103:
#line 488 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[3].value.obj), (yystack_[0].value.obj)); }
#line 1757 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 104:
#line 489 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = StartList((yystack_[0].value.obj)); }
#line 1763 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 105:
#line 493 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NNN)", (yystack_[2].value.obj), (yystack_[1].value.obj), (yystack_[0].value.obj)); }
#line 1769 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 106:
#line 494 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(sOO)", "*", Py_None, Py_None); }
#line 1775 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 107:
#line 495 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NNO)", (yystack_[1].value.obj), (yystack_[0].value.obj), Py_None); }
#line 1781 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 108:
#line 496 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = ctx->Value(kEllipsis); }
#line 1787 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 109:
#line 500 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[0].value.obj); }
#line 1793 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 110:
#line 501 "parser.yy" // lalr1.cc:867
    { Py_INCREF(Py_None); (yylhs.value.obj) = Py_None; }
#line 1799 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 111:
#line 505 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[0].value.obj); }
#line 1805 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 112:
#line 506 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[0].value.obj); }
#line 1811 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 113:
#line 507 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = ctx->Value(kEllipsis); }
#line 1817 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 114:
#line 508 "parser.yy" // lalr1.cc:867
    { Py_INCREF(Py_None); (yylhs.value.obj) = Py_None; }
#line 1823 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 115:
#line 512 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyString_FromFormat("*%s", PyString_AsString((yystack_[0].value.obj))); }
#line 1829 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 116:
#line 513 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyString_FromFormat("**%s", PyString_AsString((yystack_[0].value.obj))); }
#line 1835 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 117:
#line 517 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[0].value.obj); }
#line 1841 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 118:
#line 518 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = ctx->Value(kAnything); }
#line 1847 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 119:
#line 522 "parser.yy" // lalr1.cc:867
    { Py_DecRef((yystack_[0].value.obj)); }
#line 1853 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 120:
#line 526 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); }
#line 1859 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 121:
#line 527 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); }
#line 1865 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 122:
#line 528 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyList_New(0); }
#line 1871 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 130:
#line 542 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[1].value.obj), (yystack_[0].value.obj)); }
#line 1877 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 131:
#line 543 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = StartList((yystack_[0].value.obj)); }
#line 1883 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 132:
#line 547 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1889 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 133:
#line 548 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[0].value.obj); }
#line 1895 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 134:
#line 549 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[2].value.obj); }
#line 1901 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 135:
#line 553 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1907 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 136:
#line 554 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = StartList((yystack_[0].value.obj)); }
#line 1913 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 137:
#line 558 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[0].value.obj); }
#line 1919 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 138:
#line 559 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = ctx->Value(kEllipsis); }
#line 1925 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 139:
#line 563 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewType, "(N)", (yystack_[0].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1934 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 140:
#line 567 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewType, "(NN)", (yystack_[3].value.obj), (yystack_[1].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1943 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 141:
#line 571 "parser.yy" // lalr1.cc:867
    {
      // This rule is needed for Callable[[...], ...]
      (yylhs.value.obj) = ctx->Call(kNewType, "(sN)", "tuple", (yystack_[1].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1953 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 142:
#line 576 "parser.yy" // lalr1.cc:867
    {
      (yylhs.value.obj) = ctx->Call(kNewNamedTuple, "(NN)", (yystack_[3].value.obj), (yystack_[1].value.obj));
      CHECK((yylhs.value.obj), yylhs.location);
    }
#line 1962 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 143:
#line 580 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[1].value.obj); }
#line 1968 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 144:
#line 581 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = ctx->Call(kNewIntersectionType, "([NN])", (yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1974 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 145:
#line 582 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = ctx->Call(kNewUnionType, "([NN])", (yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 1980 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 146:
#line 583 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = ctx->Value(kAnything); }
#line 1986 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 147:
#line 584 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = ctx->Value(kNothing); }
#line 1992 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 148:
#line 588 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[2].value.obj); }
#line 1998 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 149:
#line 589 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyList_New(0); }
#line 2004 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 150:
#line 593 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 2010 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 151:
#line 594 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = StartList((yystack_[0].value.obj)); }
#line 2016 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 152:
#line 598 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NN)", (yystack_[4].value.obj), (yystack_[2].value.obj)); }
#line 2022 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 155:
#line 607 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[0].value.obj); }
#line 2028 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 156:
#line 608 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = PyList_New(0); }
#line 2034 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 157:
#line 612 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 2040 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 158:
#line 613 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = StartList((yystack_[0].value.obj)); }
#line 2046 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 159:
#line 620 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = AppendList((yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 2052 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 160:
#line 621 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = Py_BuildValue("(NN)", (yystack_[2].value.obj), (yystack_[0].value.obj)); }
#line 2058 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 161:
#line 630 "parser.yy" // lalr1.cc:867
    {
      Py_DECREF((yystack_[2].value.obj));
      (yylhs.value.obj) = ctx->Value(kTuple);
    }
#line 2067 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 162:
#line 635 "parser.yy" // lalr1.cc:867
    {
      Py_DECREF((yystack_[2].value.obj));
      (yylhs.value.obj) = ctx->Value(kTuple);
    }
#line 2076 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 163:
#line 641 "parser.yy" // lalr1.cc:867
    {
      Py_DECREF((yystack_[1].value.obj));
      (yylhs.value.obj) = ctx->Value(kTuple);
    }
#line 2085 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 164:
#line 648 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[0].value.obj); }
#line 2091 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 165:
#line 649 "parser.yy" // lalr1.cc:867
    {
#if PY_MAJOR_VERSION >= 3
      (yystack_[2].value.obj) = PyUnicode_Concat((yystack_[2].value.obj), DOT_STRING);
      (yystack_[2].value.obj) = PyUnicode_Concat((yystack_[2].value.obj), (yystack_[0].value.obj));
      Py_DECREF((yystack_[0].value.obj));
#else
      PyString_Concat(&(yystack_[2].value.obj), DOT_STRING);
      PyString_ConcatAndDel(&(yystack_[2].value.obj), (yystack_[0].value.obj));
#endif
      (yylhs.value.obj) = (yystack_[2].value.obj);
    }
#line 2107 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 166:
#line 663 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[0].value.obj); }
#line 2113 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 167:
#line 664 "parser.yy" // lalr1.cc:867
    {
      PyObject* slice = PySlice_New((yystack_[2].value.obj), (yystack_[0].value.obj), NULL);
      CHECK(slice, yylhs.location);
      (yylhs.value.obj) = slice;
    }
#line 2123 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 168:
#line 669 "parser.yy" // lalr1.cc:867
    {
      PyObject* slice = PySlice_New((yystack_[4].value.obj), (yystack_[2].value.obj), (yystack_[0].value.obj));
      CHECK(slice, yylhs.location);
      (yylhs.value.obj) = slice;
    }
#line 2133 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 169:
#line 677 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = (yystack_[0].value.obj); }
#line 2139 "pyi/parser.tab.cc" // lalr1.cc:867
    break;

  case 170:
#line 678 "parser.yy" // lalr1.cc:867
    { (yylhs.value.obj) = NULL; }
#line 2145 "pyi/parser.tab.cc" // lalr1.cc:867
    break;


#line 2149 "pyi/parser.tab.cc" // lalr1.cc:867
            default:
              break;
            }
        }
#ifdef __EXCEPTIONS
      catch (const syntax_error& yyexc)
        {
          error (yyexc);
          YYERROR;
        }
#endif // __EXCEPTIONS
      YY_SYMBOL_PRINT ("-> $$ =", yylhs);
      yypop_ (yylen);
      yylen = 0;
      YY_STACK_PRINT ();

      // Shift the result of the reduction.
      yypush_ (YY_NULLPTR, yylhs);
    }
    goto yynewstate;

  /*--------------------------------------.
  | yyerrlab -- here on detecting error.  |
  `--------------------------------------*/
  yyerrlab:
    // If not already recovering from an error, report this error.
    if (!yyerrstatus_)
      {
        ++yynerrs_;
        error (yyla.location, yysyntax_error_ (yystack_[0].state, yyla));
      }


    yyerror_range[1].location = yyla.location;
    if (yyerrstatus_ == 3)
      {
        /* If just tried and failed to reuse lookahead token after an
           error, discard it.  */

        // Return failure if at end of input.
        if (yyla.type_get () == yyeof_)
          YYABORT;
        else if (!yyla.empty ())
          {
            yy_destroy_ ("Error: discarding", yyla);
            yyla.clear ();
          }
      }

    // Else will try to reuse lookahead token after shifting the error token.
    goto yyerrlab1;


  /*---------------------------------------------------.
  | yyerrorlab -- error raised explicitly by YYERROR.  |
  `---------------------------------------------------*/
  yyerrorlab:

    /* Pacify compilers like GCC when the user code never invokes
       YYERROR and the label yyerrorlab therefore never appears in user
       code.  */
    if (false)
      goto yyerrorlab;
    yyerror_range[1].location = yystack_[yylen - 1].location;
    /* Do not reclaim the symbols of the rule whose action triggered
       this YYERROR.  */
    yypop_ (yylen);
    yylen = 0;
    goto yyerrlab1;

  /*-------------------------------------------------------------.
  | yyerrlab1 -- common code for both syntax error and YYERROR.  |
  `-------------------------------------------------------------*/
  yyerrlab1:
    yyerrstatus_ = 3;   // Each real token shifted decrements this.
    {
      stack_symbol_type error_token;
      for (;;)
        {
          yyn = yypact_[yystack_[0].state];
          if (!yy_pact_value_is_default_ (yyn))
            {
              yyn += yyterror_;
              if (0 <= yyn && yyn <= yylast_ && yycheck_[yyn] == yyterror_)
                {
                  yyn = yytable_[yyn];
                  if (0 < yyn)
                    break;
                }
            }

          // Pop the current state because it cannot handle the error token.
          if (yystack_.size () == 1)
            YYABORT;

          yyerror_range[1].location = yystack_[0].location;
          yy_destroy_ ("Error: popping", yystack_[0]);
          yypop_ ();
          YY_STACK_PRINT ();
        }

      yyerror_range[2].location = yyla.location;
      YYLLOC_DEFAULT (error_token.location, yyerror_range, 2);

      // Shift the error token.
      error_token.state = yyn;
      yypush_ ("Shifting", error_token);
    }
    goto yynewstate;

    // Accept.
  yyacceptlab:
    yyresult = 0;
    goto yyreturn;

    // Abort.
  yyabortlab:
    yyresult = 1;
    goto yyreturn;

  yyreturn:
    if (!yyla.empty ())
      yy_destroy_ ("Cleanup: discarding lookahead", yyla);

    /* Do not reclaim the symbols of the rule whose action triggered
       this YYABORT or YYACCEPT.  */
    yypop_ (yylen);
    while (1 < yystack_.size ())
      {
        yy_destroy_ ("Cleanup: popping", yystack_[0]);
        yypop_ ();
      }

    return yyresult;
  }
#ifdef __EXCEPTIONS
    catch (...)
      {
        YYCDEBUG << "Exception caught: cleaning lookahead and stack"
                 << std::endl;
        // Do not try to display the values of the reclaimed symbols,
        // as their printer might throw an exception.
        if (!yyla.empty ())
          yy_destroy_ (YY_NULLPTR, yyla);

        while (1 < yystack_.size ())
          {
            yy_destroy_ (YY_NULLPTR, yystack_[0]);
            yypop_ ();
          }
        throw;
      }
#endif // __EXCEPTIONS
  }

  void
  parser::error (const syntax_error& yyexc)
  {
    error (yyexc.location, yyexc.what());
  }

  // Generate an error message.
  std::string
  parser::yysyntax_error_ (state_type yystate, const symbol_type& yyla) const
  {
    // Number of reported tokens (one for the "unexpected", one per
    // "expected").
    size_t yycount = 0;
    // Its maximum.
    enum { YYERROR_VERBOSE_ARGS_MAXIMUM = 5 };
    // Arguments of yyformat.
    char const *yyarg[YYERROR_VERBOSE_ARGS_MAXIMUM];

    /* There are many possibilities here to consider:
       - If this state is a consistent state with a default action, then
         the only way this function was invoked is if the default action
         is an error action.  In that case, don't check for expected
         tokens because there are none.
       - The only way there can be no lookahead present (in yyla) is
         if this state is a consistent state with a default action.
         Thus, detecting the absence of a lookahead is sufficient to
         determine that there is no unexpected or expected token to
         report.  In that case, just report a simple "syntax error".
       - Don't assume there isn't a lookahead just because this state is
         a consistent state with a default action.  There might have
         been a previous inconsistent state, consistent state with a
         non-default action, or user semantic action that manipulated
         yyla.  (However, yyla is currently not documented for users.)
       - Of course, the expected token list depends on states to have
         correct lookahead information, and it depends on the parser not
         to perform extra reductions after fetching a lookahead from the
         scanner and before detecting a syntax error.  Thus, state
         merging (from LALR or IELR) and default reductions corrupt the
         expected token list.  However, the list is correct for
         canonical LR with one exception: it will still contain any
         token that will not be accepted due to an error action in a
         later state.
    */
    if (!yyla.empty ())
      {
        int yytoken = yyla.type_get ();
        yyarg[yycount++] = yytname_[yytoken];
        int yyn = yypact_[yystate];
        if (!yy_pact_value_is_default_ (yyn))
          {
            /* Start YYX at -YYN if negative to avoid negative indexes in
               YYCHECK.  In other words, skip the first -YYN actions for
               this state because they are default actions.  */
            int yyxbegin = yyn < 0 ? -yyn : 0;
            // Stay within bounds of both yycheck and yytname.
            int yychecklim = yylast_ - yyn + 1;
            int yyxend = yychecklim < yyntokens_ ? yychecklim : yyntokens_;
            for (int yyx = yyxbegin; yyx < yyxend; ++yyx)
              if (yycheck_[yyx + yyn] == yyx && yyx != yyterror_
                  && !yy_table_value_is_error_ (yytable_[yyx + yyn]))
                {
                  if (yycount == YYERROR_VERBOSE_ARGS_MAXIMUM)
                    {
                      yycount = 1;
                      break;
                    }
                  else
                    yyarg[yycount++] = yytname_[yyx];
                }
          }
      }

    char const* yyformat = YY_NULLPTR;
    switch (yycount)
      {
#define YYCASE_(N, S)                         \
        case N:                               \
          yyformat = S;                       \
        break
        YYCASE_(0, YY_("syntax error"));
        YYCASE_(1, YY_("syntax error, unexpected %s"));
        YYCASE_(2, YY_("syntax error, unexpected %s, expecting %s"));
        YYCASE_(3, YY_("syntax error, unexpected %s, expecting %s or %s"));
        YYCASE_(4, YY_("syntax error, unexpected %s, expecting %s or %s or %s"));
        YYCASE_(5, YY_("syntax error, unexpected %s, expecting %s or %s or %s or %s"));
#undef YYCASE_
      }

    std::string yyres;
    // Argument number.
    size_t yyi = 0;
    for (char const* yyp = yyformat; *yyp; ++yyp)
      if (yyp[0] == '%' && yyp[1] == 's' && yyi < yycount)
        {
          yyres += yytnamerr_ (yyarg[yyi++]);
          ++yyp;
        }
      else
        yyres += *yyp;
    return yyres;
  }


  const short int parser::yypact_ninf_ = -244;

  const short int parser::yytable_ninf_ = -170;

  const short int
  parser::yypact_[] =
  {
     -13,  -244,    18,    65,   302,    82,  -244,  -244,   166,   108,
       7,   117,    12,  -244,  -244,    30,    93,  -244,  -244,  -244,
    -244,  -244,    13,  -244,   145,   113,  -244,   100,  -244,     7,
     292,   253,   119,  -244,    94,   175,   160,   107,  -244,     7,
     169,   176,   149,   236,   117,  -244,  -244,   221,   145,   145,
    -244,    69,   243,  -244,   256,   211,  -244,  -244,   145,   148,
    -244,    29,   235,   184,     7,     7,  -244,  -244,  -244,  -244,
     296,  -244,  -244,   304,    57,   117,   312,    10,    14,  -244,
      10,   292,   305,   306,  -244,   284,   241,   320,   252,   310,
     299,   300,   145,   145,   313,   143,   331,   145,   224,   301,
    -244,   303,  -244,   291,  -244,   310,   309,  -244,   329,  -244,
     311,   307,   314,  -244,  -244,   338,  -244,  -244,  -244,   327,
    -244,  -244,    16,  -244,  -244,   315,  -244,  -244,  -244,  -244,
     212,     6,   342,  -244,  -244,   316,  -244,  -244,   145,   336,
    -244,  -244,  -244,   213,  -244,   310,   317,   310,    74,   145,
     319,   145,  -244,   153,   297,   273,   345,   321,   347,   293,
      16,   218,   228,  -244,   322,  -244,     2,   323,   324,  -244,
     322,  -244,   318,   310,   143,  -244,   167,   326,  -244,   310,
     310,  -244,   310,  -244,  -244,  -244,   245,  -244,   309,    27,
    -244,   330,    68,  -244,  -244,    23,  -244,  -244,  -244,   145,
     325,  -244,   356,   343,    83,  -244,  -244,   158,   332,  -244,
     328,   333,  -244,   334,  -244,    66,   340,   197,  -244,  -244,
    -244,  -244,   345,   295,  -244,  -244,   310,   207,  -244,  -244,
     145,   339,     6,   363,  -244,   335,  -244,  -244,   145,   370,
     167,   346,  -244,   249,  -244,    30,   344,  -244,  -244,  -244,
    -244,  -244,   371,  -244,  -244,  -244,   310,   279,  -244,  -244,
    -244,   348,   349,   337,   310,   328,  -244,   333,  -244,   135,
     352,   353,   351,   354,   191,   298,   309,   145,  -244,  -244,
     355,   360,  -244,  -244,   357,   145,   362,   165,  -244,   364,
     267,  -244,  -244,   233,  -244,  -244,   220,   145,   254,  -244,
    -244,  -244,  -244,   234,   365,  -244,   361,   244,   247,  -244,
     310,   366,  -244,  -244,  -244,  -244,  -244,  -244
  };

  const unsigned char
  parser::yydefact_[] =
  {
      12,    12,     0,     0,    99,     0,     1,     2,     0,     0,
       0,     0,     0,     9,    11,    35,     0,     5,     7,     8,
      10,     6,     0,     3,     0,     0,    16,    19,   164,     0,
      42,     0,    69,    73,    74,     0,     0,    76,    44,     0,
       0,     0,     0,     0,     0,    98,   147,     0,     0,   156,
     146,    67,   139,    61,     0,    65,    62,    63,     0,    88,
      64,     0,     0,     0,     0,     0,    59,    60,    57,    58,
     170,    55,    56,     0,     0,     0,     0,     0,     0,    77,
       0,    43,     0,     0,    12,     0,    14,     0,     0,   158,
       0,   155,     0,     0,     0,     0,     0,     0,     0,   154,
     163,   164,    18,     0,    21,    22,    14,    51,    50,    49,
     166,     0,     0,   165,    45,     0,    46,    72,    75,    83,
      84,    85,     0,    86,    71,    78,    82,    70,    12,    12,
      99,   102,     0,   100,    13,     0,   143,   141,     0,   145,
     144,    68,   138,     0,   136,   137,    90,    66,     0,   153,
       0,     0,    17,     0,     0,     0,   170,     0,     0,     0,
       0,    99,    99,    36,   110,   108,   106,     0,   154,   104,
     110,   119,     0,   157,     0,   140,     0,     0,   162,   160,
     159,   161,    23,    20,   171,   172,    33,    15,    14,     0,
     169,   167,     0,    87,    79,     0,    81,    37,    34,     0,
     114,   115,     0,   118,    14,   101,   107,     0,     0,   135,
     164,    92,    95,    91,    89,    33,     0,    99,    27,    24,
      47,    48,   170,     0,    52,    80,   109,     0,   105,   116,
       0,   129,     0,     0,   149,   154,   151,   142,     0,     0,
       0,     0,    25,     0,    32,    39,     0,    29,    30,    31,
     168,    53,     0,   111,   112,   113,   117,     0,    97,   122,
     103,     0,   153,     0,    96,     0,    94,    93,    26,     0,
       0,     0,     0,     0,     0,     0,   123,     0,   150,   148,
       0,     0,    33,    54,     0,     0,     0,     0,   131,     0,
       0,   125,   124,   154,    33,    33,    99,     0,   133,   128,
     121,   130,   127,     0,     0,   153,     0,    99,    99,    40,
     132,     0,   120,   126,   152,    41,    38,   134
  };

  const short int
  parser::yypgoto_[] =
  {
    -244,  -244,   378,   -77,  -104,  -244,  -244,  -244,  -244,   227,
    -244,   173,  -152,  -244,  -244,  -244,  -244,  -213,   136,   146,
      76,   206,   242,  -211,  -244,  -244,   341,   386,   350,   277,
    -133,  -209,  -244,  -244,   162,   161,  -206,  -244,  -244,  -244,
    -244,   171,   237,  -244,  -244,  -244,  -243,  -244,  -244,   114,
    -180,  -244,   231,   -24,  -244,  -244,   144,  -165,  -244,   232,
    -244,  -244,    11,  -244,  -144,  -153
  };

  const short int
  parser::yydefgoto_[] =
  {
      -1,     2,     3,     4,   133,    13,    27,    62,   103,   104,
     187,   216,   217,    14,    15,   244,   245,    16,    40,    41,
      30,   116,    74,    17,    18,    32,    33,    79,   124,   125,
     126,    19,    20,   177,   211,   212,    21,    22,    45,   167,
     168,   169,   200,   228,   170,   231,   134,   258,   259,   287,
     288,   143,   144,    59,   208,   235,   236,   150,    90,    91,
      99,    60,    52,   111,   112,   218
  };

  const short int
  parser::yytable_[] =
  {
      51,   188,   154,   205,   246,   201,   247,   130,   248,   164,
      28,   249,   191,   119,   275,    28,     1,    28,     6,   119,
      43,    31,    34,    37,    88,    89,   119,   196,   165,   120,
     121,   220,   101,   292,    98,   120,   121,   105,    38,    39,
      31,    29,   120,   121,   122,   202,    37,    46,    47,   166,
      31,   161,   162,   123,    35,    86,    78,    44,   225,   123,
     114,   115,   196,    48,   102,     7,   123,    49,   139,   140,
     263,   145,   223,   147,    50,    31,    31,    28,   250,   184,
      92,    93,    23,   246,   219,   247,    34,   248,   185,    37,
     249,   115,    46,    47,   246,   246,   247,   247,   248,   248,
     232,   249,   249,   224,   276,    63,    94,   301,    48,   178,
      76,    26,    49,   132,   173,    81,    28,    53,  -153,    50,
      28,   289,   291,   301,   179,   180,    42,   182,   306,   105,
     296,    46,    47,    54,    61,    55,    73,   304,    28,    53,
     108,   109,   307,   308,    56,    57,    28,    58,    28,    73,
     145,    49,    89,    46,    47,    75,   101,    55,    50,    92,
      93,    46,    47,    46,    47,   142,    56,    57,   284,    58,
     210,    46,    47,    49,    80,   226,    84,    48,    28,    48,
      50,    49,   285,    49,   100,    46,    47,    48,    50,    77,
      50,    49,   233,   300,   284,    64,    65,   234,    50,    24,
     243,    48,    82,    25,   184,    49,   256,    10,   285,    83,
     253,   254,    50,   185,   264,     8,   173,    78,     9,   107,
     286,     8,    10,   243,     9,   -28,    11,    12,    10,   255,
      10,     8,    11,    12,     9,    92,    93,   284,    10,    85,
     163,    97,    11,    12,    92,    93,   197,   243,   309,   174,
     243,   285,   175,   293,    10,    87,   198,    10,   184,   136,
     148,   298,   312,    92,    93,    92,    93,   185,   106,   305,
     284,   132,   315,   310,   215,   316,    66,    67,    68,    69,
     184,    95,    24,    73,   285,    73,   269,   136,   311,   185,
      96,    70,   184,    71,    72,    73,    66,    67,    68,    69,
     110,   185,    -4,    64,    65,     8,   274,   113,     9,   132,
     184,   184,    10,    71,    72,   118,    11,    12,   131,   185,
     185,    92,    93,   135,   186,   290,   152,   153,   194,   195,
     251,   252,   128,   129,   146,   141,   138,   149,   137,   132,
     151,    65,   157,   158,  -169,   171,   155,   156,    93,   190,
     193,   160,   172,   176,   181,   199,   207,   192,   203,   229,
     204,   214,   227,   222,   230,   238,   261,   237,   242,   239,
     240,   262,   257,   265,   268,   273,   279,   272,   282,     5,
     183,   270,   294,   233,   277,   280,   281,   295,   241,   283,
     299,   271,   302,   313,   297,   221,   314,   189,    36,   159,
     266,   317,   267,   260,   303,   209,   278,   206,   213,     0,
       0,     0,     0,     0,     0,     0,   117,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     127
  };

  const short int
  parser::yycheck_[] =
  {
      24,   154,   106,   168,   217,     3,   217,    84,   217,     3,
       3,   217,   156,     3,   257,     3,    29,     3,     0,     3,
       7,    10,    11,    12,    48,    49,     3,   160,    22,    19,
      20,     4,     3,   276,    58,    19,    20,    61,     8,     9,
      29,    34,    19,    20,    34,    43,    35,    18,    19,    43,
      39,   128,   129,    43,    42,    44,    42,    44,    35,    43,
       3,    34,   195,    34,    35,     0,    43,    38,    92,    93,
     235,    95,     4,    97,    45,    64,    65,     3,   222,    13,
      11,    12,     0,   296,   188,   296,    75,   296,    22,    78,
     296,    34,    18,    19,   307,   308,   307,   308,   307,   308,
     204,   307,   308,    35,   257,    29,    37,   287,    34,    35,
      16,     3,    38,    30,   138,    39,     3,     4,    35,    45,
       3,   274,   275,   303,   148,   149,    33,   151,   293,   153,
     282,    18,    19,    20,    34,    22,    42,   290,     3,     4,
      64,    65,   294,   295,    31,    32,     3,    34,     3,    42,
     174,    38,   176,    18,    19,    36,     3,    22,    45,    11,
      12,    18,    19,    18,    19,    22,    31,    32,     3,    34,
       3,    18,    19,    38,    14,   199,    27,    34,     3,    34,
      45,    38,    17,    38,    36,    18,    19,    34,    45,    14,
      45,    38,    34,    28,     3,    11,    12,    39,    45,    33,
       3,    34,    33,    37,    13,    38,   230,    10,    17,    33,
       3,     4,    45,    22,   238,     3,   240,    42,     6,    35,
      29,     3,    10,     3,     6,    28,    14,    15,    10,    22,
      10,     3,    14,    15,     6,    11,    12,     3,    10,     3,
      28,    30,    14,    15,    11,    12,    28,     3,    28,    36,
       3,    17,    39,   277,    10,    34,    28,    10,    13,    35,
      36,   285,    28,    11,    12,    11,    12,    22,    33,    36,
       3,    30,    28,   297,    29,    28,    23,    24,    25,    26,
      13,    38,    33,    42,    17,    42,    37,    35,    34,    22,
      34,    38,    13,    40,    41,    42,    23,    24,    25,    26,
       4,    22,     0,    11,    12,     3,    27,     3,     6,    30,
      13,    13,    10,    40,    41,     3,    14,    15,    34,    22,
      22,    11,    12,     3,    27,    27,    35,    36,    35,    36,
      35,    36,    27,    27,     3,    22,    36,    36,    39,    30,
      37,    12,     4,    16,    33,     3,    39,    33,    12,     4,
       3,    36,    36,    36,    35,    33,    38,    36,    35,     3,
      36,    35,    37,    33,    21,    37,     3,    35,    28,    36,
      36,    36,    33,     3,    28,     4,    39,    33,    27,     1,
     153,   245,    27,    34,    36,    33,    33,    27,   215,    35,
      28,   245,    28,    28,    37,   189,    35,   155,    12,   122,
     239,    35,   240,   232,   290,   174,   262,   170,   176,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    75,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      80
  };

  const unsigned char
  parser::yystos_[] =
  {
       0,    29,    47,    48,    49,    48,     0,     0,     3,     6,
      10,    14,    15,    51,    59,    60,    63,    69,    70,    77,
      78,    82,    83,     0,    33,    37,     3,    52,     3,    34,
      66,   108,    71,    72,   108,    42,    73,   108,     8,     9,
      64,    65,    33,     7,    44,    84,    18,    19,    34,    38,
      45,    99,   108,     4,    20,    22,    31,    32,    34,    99,
     107,    34,    53,    66,    11,    12,    23,    24,    25,    26,
      38,    40,    41,    42,    68,    36,    16,    14,    42,    73,
      14,    66,    33,    33,    27,     3,   108,    34,    99,    99,
     104,   105,    11,    12,    37,    38,    34,    30,    99,   106,
      36,     3,    35,    54,    55,    99,    33,    35,    66,    66,
       4,   109,   110,     3,     3,    34,    67,    72,     3,     3,
      19,    20,    34,    43,    74,    75,    76,    74,    27,    27,
      49,    34,    30,    50,    92,     3,    35,    39,    36,    99,
      99,    22,    22,    97,    98,    99,     3,    99,    36,    36,
     103,    37,    35,    36,    50,    39,    33,     4,    16,    75,
      36,    49,    49,    28,     3,    22,    43,    85,    86,    87,
      90,     3,    36,    99,    36,    39,    36,    79,    35,    99,
      99,    35,    99,    55,    13,    22,    27,    56,   111,    68,
       4,   110,    36,     3,    35,    36,    76,    28,    28,    33,
      88,     3,    43,    35,    36,   103,    88,    38,   100,    98,
       3,    80,    81,   105,    35,    29,    57,    58,   111,    50,
       4,    67,    33,     4,    35,    35,    99,    37,    89,     3,
      21,    91,    50,    34,    39,   101,   102,    35,    37,    36,
      36,    57,    28,     3,    61,    62,    63,    69,    77,    82,
     110,    35,    36,     3,     4,    22,    99,    33,    93,    94,
      87,     3,    36,   103,    99,     3,    81,    80,    28,    37,
      64,    65,    33,     4,    27,    92,   111,    36,   102,    39,
      33,    33,    27,    35,     3,    17,    29,    95,    96,   111,
      27,   111,    92,    99,    27,    27,    58,    37,    99,    28,
      28,    96,    28,    95,   111,    36,   103,    58,    58,    28,
      99,    34,    28,    28,    35,    28,    28,    35
  };

  const unsigned char
  parser::yyr1_[] =
  {
       0,    46,    47,    47,    48,    49,    49,    49,    49,    49,
      49,    49,    49,    50,    50,    51,    52,    53,    53,    53,
      54,    54,    55,    55,    56,    56,    56,    57,    57,    58,
      58,    58,    58,    58,    59,    59,    60,    60,    61,    61,
      62,    62,    63,    64,    65,    66,    66,    66,    66,    66,
      66,    66,    67,    67,    67,    68,    68,    68,    68,    68,
      68,    69,    69,    69,    69,    69,    69,    69,    69,    70,
      70,    70,    71,    71,    72,    72,    73,    73,    74,    74,
      74,    75,    75,    76,    76,    76,    76,    76,    77,    78,
      79,    79,    79,    79,    80,    80,    81,    82,    83,    83,
      84,    85,    85,    86,    86,    87,    87,    87,    87,    88,
      88,    89,    89,    89,    89,    90,    90,    91,    91,    92,
      93,    93,    93,    94,    94,    94,    94,    94,    94,    94,
      95,    95,    96,    96,    96,    97,    97,    98,    98,    99,
      99,    99,    99,    99,    99,    99,    99,    99,   100,   100,
     101,   101,   102,   103,   103,   104,   104,   105,   105,   106,
     106,   107,   107,   107,   108,   108,   109,   109,   109,   110,
     110,   111,   111
  };

  const unsigned char
  parser::yyr2_[] =
  {
       0,     2,     2,     3,     1,     2,     2,     2,     2,     2,
       2,     2,     0,     1,     0,     6,     1,     3,     2,     0,
       3,     1,     1,     3,     2,     3,     4,     1,     1,     2,
       2,     2,     2,     0,     6,     1,     5,     6,     6,     1,
       5,     6,     2,     2,     1,     3,     3,     6,     6,     3,
       3,     3,     4,     5,     7,     1,     1,     1,     1,     1,
       1,     3,     3,     3,     3,     3,     5,     3,     5,     2,
       4,     4,     3,     1,     1,     3,     1,     2,     1,     3,
       4,     3,     1,     1,     1,     1,     1,     3,     3,     7,
       0,     2,     2,     4,     3,     1,     3,     8,     2,     0,
       3,     2,     0,     4,     1,     3,     1,     2,     1,     2,
       0,     2,     2,     2,     0,     2,     3,     2,     0,     2,
       5,     4,     1,     2,     3,     3,     5,     4,     4,     0,
       2,     1,     3,     2,     4,     3,     1,     1,     1,     1,
       4,     3,     6,     3,     3,     3,     1,     1,     4,     2,
       3,     1,     6,     1,     0,     1,     0,     3,     1,     3,
       3,     4,     4,     2,     1,     3,     1,     3,     5,     1,
       0,     1,     1
  };



  // YYTNAME[SYMBOL-NUM] -- String name of the symbol SYMBOL-NUM.
  // First, the terminals, then, starting at \a yyntokens_, nonterminals.
  const char*
  const parser::yytname_[] =
  {
  "\"end of file\"", "error", "$undefined", "NAME", "NUMBER", "LEXERROR",
  "CLASS", "DEF", "ELSE", "ELIF", "IF", "OR", "AND", "PASS", "IMPORT",
  "FROM", "AS", "RAISE", "NOTHING", "NAMEDTUPLE", "TYPEVAR", "ARROW",
  "ELLIPSIS", "EQ", "NE", "LE", "GE", "INDENT", "DEDENT", "TRIPLEQUOTED",
  "TYPECOMMENT", "BYTESTRING", "UNICODESTRING", "':'", "'('", "')'", "','",
  "'='", "'['", "']'", "'<'", "'>'", "'.'", "'*'", "'@'", "'?'", "$accept",
  "start", "unit", "alldefs", "maybe_type_ignore", "classdef",
  "class_name", "parents", "parent_list", "parent", "maybe_class_funcs",
  "class_funcs", "funcdefs", "if_stmt", "if_and_elifs", "class_if_stmt",
  "class_if_and_elifs", "if_cond", "elif_cond", "else_cond", "condition",
  "version_tuple", "condition_op", "constantdef", "importdef",
  "import_items", "import_item", "import_name", "from_list", "from_items",
  "from_item", "alias_or_constant", "typevardef", "typevar_args",
  "typevar_kwargs", "typevar_kwarg", "funcdef", "decorators", "decorator",
  "params", "param_list", "param", "param_type", "param_default",
  "param_star_name", "return", "typeignore", "maybe_body", "empty_body",
  "body", "body_stmt", "type_parameters", "type_parameter", "type",
  "named_tuple_fields", "named_tuple_field_list", "named_tuple_field",
  "maybe_comma", "maybe_type_list", "type_list", "type_tuple_elements",
  "type_tuple_literal", "dotted_name", "getitem_key", "maybe_number",
  "pass_or_ellipsis", YY_NULLPTR
  };

#if YYDEBUG
  const unsigned short int
  parser::yyrline_[] =
  {
       0,   129,   129,   130,   134,   138,   139,   140,   141,   147,
     148,   149,   154,   158,   159,   162,   169,   180,   181,   182,
     186,   187,   191,   192,   196,   197,   198,   202,   203,   207,
     208,   213,   214,   219,   224,   227,   232,   236,   255,   258,
     263,   267,   279,   283,   287,   291,   294,   297,   300,   303,
     304,   305,   310,   311,   312,   318,   319,   320,   321,   322,
     323,   327,   331,   335,   339,   343,   347,   351,   355,   362,
     366,   370,   379,   380,   383,   384,   389,   390,   397,   398,
     399,   403,   404,   408,   409,   412,   415,   418,   422,   426,
     433,   434,   435,   436,   440,   441,   445,   449,   466,   467,
     471,   475,   476,   488,   489,   493,   494,   495,   496,   500,
     501,   505,   506,   507,   508,   512,   513,   517,   518,   522,
     526,   527,   528,   532,   533,   534,   535,   536,   537,   538,
     542,   543,   547,   548,   549,   553,   554,   558,   559,   563,
     567,   571,   576,   580,   581,   582,   583,   584,   588,   589,
     593,   594,   598,   602,   603,   607,   608,   612,   613,   620,
     621,   630,   635,   641,   648,   649,   663,   664,   669,   677,
     678,   682,   683
  };

  // Print the state stack on the debug stream.
  void
  parser::yystack_print_ ()
  {
    *yycdebug_ << "Stack now";
    for (stack_type::const_iterator
           i = yystack_.begin (),
           i_end = yystack_.end ();
         i != i_end; ++i)
      *yycdebug_ << ' ' << i->state;
    *yycdebug_ << std::endl;
  }

  // Report on the debug stream that the rule \a yyrule is going to be reduced.
  void
  parser::yy_reduce_print_ (int yyrule)
  {
    unsigned int yylno = yyrline_[yyrule];
    int yynrhs = yyr2_[yyrule];
    // Print the symbols being reduced, and their result.
    *yycdebug_ << "Reducing stack by rule " << yyrule - 1
               << " (line " << yylno << "):" << std::endl;
    // The symbols being reduced.
    for (int yyi = 0; yyi < yynrhs; yyi++)
      YY_SYMBOL_PRINT ("   $" << yyi + 1 << " =",
                       yystack_[(yynrhs) - (yyi + 1)]);
  }
#endif // YYDEBUG

  // Symbol number corresponding to token number t.
  inline
  parser::token_number_type
  parser::yytranslate_ (int t)
  {
    static
    const token_number_type
    translate_table[] =
    {
     0,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
      34,    35,    43,     2,    36,     2,    42,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,    33,     2,
      40,    37,    41,    45,    44,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,    38,     2,    39,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     1,     2,     3,     4,
       5,     6,     7,     8,     9,    10,    11,    12,    13,    14,
      15,    16,    17,    18,    19,    20,    21,    22,    23,    24,
      25,    26,    27,    28,    29,    30,    31,    32
    };
    const unsigned int user_token_number_max_ = 287;
    const token_number_type undef_token_ = 2;

    if (static_cast<int>(t) <= yyeof_)
      return yyeof_;
    else if (static_cast<unsigned int> (t) <= user_token_number_max_)
      return translate_table[t];
    else
      return undef_token_;
  }

#line 14 "parser.yy" // lalr1.cc:1179
} // pytype
#line 2826 "pyi/parser.tab.cc" // lalr1.cc:1179
#line 686 "parser.yy" // lalr1.cc:1180


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
