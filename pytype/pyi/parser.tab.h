/* A Bison parser, made by GNU Bison 3.0.4.  */

/* Bison interface for Yacc-like parsers in C

   Copyright (C) 1984, 1989-1990, 2000-2015 Free Software Foundation, Inc.

   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <http://www.gnu.org/licenses/>.  */

/* As a special exception, you may create a larger work that contains
   part or all of the Bison parser skeleton and distribute that work
   under terms of your choice, so long as that work isn't itself a
   parser generator using the skeleton or a modified version thereof
   as a parser skeleton.  Alternatively, if you modify or redistribute
   the parser skeleton itself, you may (at your option) remove this
   special exception, which will cause the skeleton and the resulting
   Bison output files to be licensed under the GNU General Public
   License without this special exception.

   This special exception was added by the Free Software Foundation in
   version 2.2 of Bison.  */

#ifndef YY_PYTYPE_PARSER_TAB_H_INCLUDED
# define YY_PYTYPE_PARSER_TAB_H_INCLUDED
/* Debug traces.  */
#ifndef YYDEBUG
# define YYDEBUG 0
#endif
#if YYDEBUG
extern int pytypedebug;
#endif
/* "%code requires" blocks.  */
#line 19 "parser.y" /* yacc.c:1909  */

#include <Python.h>

class Context;

#line 50 "parser.tab.h" /* yacc.c:1909  */

/* Token type.  */
#ifndef YYTOKENTYPE
# define YYTOKENTYPE
  enum yytokentype
  {
    END = 0,
    NAME = 258,
    NUMBER = 259,
    LEXERROR = 260,
    CLASS = 261,
    DEF = 262,
    ELSE = 263,
    ELIF = 264,
    IF = 265,
    OR = 266,
    AND = 267,
    PASS = 268,
    IMPORT = 269,
    FROM = 270,
    AS = 271,
    RAISE = 272,
    NOTHING = 273,
    NAMEDTUPLE = 274,
    TYPEVAR = 275,
    ARROW = 276,
    COLONEQUALS = 277,
    ELLIPSIS = 278,
    EQ = 279,
    NE = 280,
    LE = 281,
    GE = 282,
    INDENT = 283,
    DEDENT = 284,
    TRIPLEQUOTED = 285,
    TYPECOMMENT = 286,
    BYTESTRING = 287,
    UNICODESTRING = 288
  };
#endif

/* Value type.  */
#if ! defined YYSTYPE && ! defined YYSTYPE_IS_DECLARED

union YYSTYPE
{
#line 65 "parser.y" /* yacc.c:1909  */

  PyObject* obj;
  const char* str;

#line 102 "parser.tab.h" /* yacc.c:1909  */
};

typedef union YYSTYPE YYSTYPE;
# define YYSTYPE_IS_TRIVIAL 1
# define YYSTYPE_IS_DECLARED 1
#endif

/* Location type.  */
#if ! defined YYLTYPE && ! defined YYLTYPE_IS_DECLARED
typedef struct YYLTYPE YYLTYPE;
struct YYLTYPE
{
  int first_line;
  int first_column;
  int last_line;
  int last_column;
};
# define YYLTYPE_IS_DECLARED 1
# define YYLTYPE_IS_TRIVIAL 1
#endif



int pytypeparse (void* scanner, Context* ctx);

#endif /* !YY_PYTYPE_PARSER_TAB_H_INCLUDED  */
