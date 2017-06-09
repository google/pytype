/* A Bison parser, made by GNU Bison 2.4.2.  */

/* Skeleton implementation for Bison's Yacc-like parsers in C
   
      Copyright (C) 1984, 1989-1990, 2000-2006, 2009-2010 Free Software
   Foundation, Inc.
   
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

/* C LALR(1) parser skeleton written by Richard Stallman, by
   simplifying the original so-called "semantic" parser.  */

/* All symbols defined below should begin with yy or YY, to avoid
   infringing on user name space.  This should be done even for local
   variables, as they might otherwise be expanded by user macros.
   There are some unavoidable exceptions within include files to
   define necessary library symbols; they are noted "INFRINGES ON
   USER NAME SPACE" below.  */

/* Identify Bison output.  */
#define YYBISON 1

/* Bison version.  */
#define YYBISON_VERSION "2.4.2"

/* Skeleton name.  */
#define YYSKELETON_NAME "yacc.c"

/* Pure parsers.  */
#define YYPURE 1

/* Push parsers.  */
#define YYPUSH 0

/* Pull parsers.  */
#define YYPULL 1

/* Using locations.  */
#define YYLSP_NEEDED 1

/* Substitute the variable and function names.  */
#define yyparse         pytypeparse
#define yylex           pytypelex
#define yyerror         pytypeerror
#define yylval          pytypelval
#define yychar          pytypechar
#define yydebug         pytypedebug
#define yynerrs         pytypenerrs
#define yylloc          pytypelloc

/* Copy the first part of user declarations.  */

/* Line 189 of yacc.c  */
#line 26 "parser.y"

#include "lexer.h"
#include "parser.h"

namespace pytype {
// Note that the pytype namespace is not closed until the trailing block of
// code after the parser skeleton is emitted.  Thus the entire parser (except
// for a few #defines) is in the pytype namespace.

namespace {
PyObject* DOT_STRING = PyString_FromString(".");

int pytypeerror(YYLTYPE* llocp, void* scanner, pytype::Context* ctx,
    const char *p);

/* Helper functions for building up lists. */
PyObject* StartList(PyObject* item);
PyObject* AppendList(PyObject* list, PyObject* item);
PyObject* ExtendList(PyObject* dst, PyObject* src);

}  // end namespace


// Check that a python value is not NULL.  The must be a macro because it
// calls YYERROR (which is a goto).
#define CHECK(x, loc) do { if (x == NULL) {\
    ctx->SetErrorLocation(&loc); \
    YYERROR; \
  }} while(0)



/* Line 189 of yacc.c  */
#line 113 "pyi/parser.tab.cc"

/* Enabling traces.  */
#ifndef YYDEBUG
# define YYDEBUG 0
#endif

/* Enabling verbose error messages.  */
#ifdef YYERROR_VERBOSE
# undef YYERROR_VERBOSE
# define YYERROR_VERBOSE 1
#else
# define YYERROR_VERBOSE 1
#endif

/* Enabling the token table.  */
#ifndef YYTOKEN_TABLE
# define YYTOKEN_TABLE 0
#endif

/* "%code requires" blocks.  */

/* Line 209 of yacc.c  */
#line 18 "parser.y"

#include <Python.h>



/* Line 209 of yacc.c  */
#line 143 "pyi/parser.tab.cc"

/* Tokens.  */
#ifndef YYTOKENTYPE
# define YYTOKENTYPE
   /* Put the tokens into the symbol table, so that GDB and other debuggers
      know about them.  */
   enum yytokentype {
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
     PASS = 267,
     IMPORT = 268,
     FROM = 269,
     AS = 270,
     RAISE = 271,
     PYTHONCODE = 272,
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
     TYPECOMMENT = 286
   };
#endif



#if ! defined YYSTYPE && ! defined YYSTYPE_IS_DECLARED
typedef union YYSTYPE
{

/* Line 214 of yacc.c  */
#line 58 "parser.y"

  PyObject* obj;
  const char* str;



/* Line 214 of yacc.c  */
#line 199 "pyi/parser.tab.cc"
} YYSTYPE;
# define YYSTYPE_IS_TRIVIAL 1
# define yystype YYSTYPE /* obsolescent; will be withdrawn */
# define YYSTYPE_IS_DECLARED 1
#endif

#if ! defined YYLTYPE && ! defined YYLTYPE_IS_DECLARED
typedef struct YYLTYPE
{
  int first_line;
  int first_column;
  int last_line;
  int last_column;
} YYLTYPE;
# define yyltype YYLTYPE /* obsolescent; will be withdrawn */
# define YYLTYPE_IS_DECLARED 1
# define YYLTYPE_IS_TRIVIAL 1
#endif


/* Copy the second part of user declarations.  */


/* Line 264 of yacc.c  */
#line 224 "pyi/parser.tab.cc"

#ifdef short
# undef short
#endif

#ifdef YYTYPE_UINT8
typedef YYTYPE_UINT8 yytype_uint8;
#else
typedef unsigned char yytype_uint8;
#endif

#ifdef YYTYPE_INT8
typedef YYTYPE_INT8 yytype_int8;
#elif (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
typedef signed char yytype_int8;
#else
typedef short int yytype_int8;
#endif

#ifdef YYTYPE_UINT16
typedef YYTYPE_UINT16 yytype_uint16;
#else
typedef unsigned short int yytype_uint16;
#endif

#ifdef YYTYPE_INT16
typedef YYTYPE_INT16 yytype_int16;
#else
typedef short int yytype_int16;
#endif

#ifndef YYSIZE_T
# ifdef __SIZE_TYPE__
#  define YYSIZE_T __SIZE_TYPE__
# elif defined size_t
#  define YYSIZE_T size_t
# elif ! defined YYSIZE_T && (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
#  include <stddef.h> /* INFRINGES ON USER NAME SPACE */
#  define YYSIZE_T size_t
# else
#  define YYSIZE_T unsigned int
# endif
#endif

#define YYSIZE_MAXIMUM ((YYSIZE_T) -1)

#ifndef YY_
# if defined YYENABLE_NLS && YYENABLE_NLS
#  if ENABLE_NLS
#   include <libintl.h> /* INFRINGES ON USER NAME SPACE */
#   define YY_(msgid) dgettext ("bison-runtime", msgid)
#  endif
# endif
# ifndef YY_
#  define YY_(msgid) msgid
# endif
#endif

/* Suppress unused-variable warnings by "using" E.  */
#if ! defined lint || defined __GNUC__
# define YYUSE(e) ((void) (e))
#else
# define YYUSE(e) /* empty */
#endif

/* Identity function, used to suppress warnings about constant conditions.  */
#ifndef lint
# define YYID(n) (n)
#else
#if (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
static int
YYID (int yyi)
#else
static int
YYID (yyi)
    int yyi;
#endif
{
  return yyi;
}
#endif

#if ! defined yyoverflow || YYERROR_VERBOSE

/* The parser invokes alloca or malloc; define the necessary symbols.  */

# ifdef YYSTACK_USE_ALLOCA
#  if YYSTACK_USE_ALLOCA
#   ifdef __GNUC__
#    define YYSTACK_ALLOC __builtin_alloca
#   elif defined __BUILTIN_VA_ARG_INCR
#    include <alloca.h> /* INFRINGES ON USER NAME SPACE */
#   elif defined _AIX
#    define YYSTACK_ALLOC __alloca
#   elif defined _MSC_VER
#    include <malloc.h> /* INFRINGES ON USER NAME SPACE */
#    define alloca _alloca
#   else
#    define YYSTACK_ALLOC alloca
#    if ! defined _ALLOCA_H && ! defined _STDLIB_H && (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
#     include <stdlib.h> /* INFRINGES ON USER NAME SPACE */
#     ifndef _STDLIB_H
#      define _STDLIB_H 1
#     endif
#    endif
#   endif
#  endif
# endif

# ifdef YYSTACK_ALLOC
   /* Pacify GCC's `empty if-body' warning.  */
#  define YYSTACK_FREE(Ptr) do { /* empty */; } while (YYID (0))
#  ifndef YYSTACK_ALLOC_MAXIMUM
    /* The OS might guarantee only one guard page at the bottom of the stack,
       and a page size can be as small as 4096 bytes.  So we cannot safely
       invoke alloca (N) if N exceeds 4096.  Use a slightly smaller number
       to allow for a few compiler-allocated temporary stack slots.  */
#   define YYSTACK_ALLOC_MAXIMUM 4032 /* reasonable circa 2006 */
#  endif
# else
#  define YYSTACK_ALLOC YYMALLOC
#  define YYSTACK_FREE YYFREE
#  ifndef YYSTACK_ALLOC_MAXIMUM
#   define YYSTACK_ALLOC_MAXIMUM YYSIZE_MAXIMUM
#  endif
#  if (defined __cplusplus && ! defined _STDLIB_H \
       && ! ((defined YYMALLOC || defined malloc) \
	     && (defined YYFREE || defined free)))
#   include <stdlib.h> /* INFRINGES ON USER NAME SPACE */
#   ifndef _STDLIB_H
#    define _STDLIB_H 1
#   endif
#  endif
#  ifndef YYMALLOC
#   define YYMALLOC malloc
#   if ! defined malloc && ! defined _STDLIB_H && (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
void *malloc (YYSIZE_T); /* INFRINGES ON USER NAME SPACE */
#   endif
#  endif
#  ifndef YYFREE
#   define YYFREE free
#   if ! defined free && ! defined _STDLIB_H && (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
void free (void *); /* INFRINGES ON USER NAME SPACE */
#   endif
#  endif
# endif
#endif /* ! defined yyoverflow || YYERROR_VERBOSE */


#if (! defined yyoverflow \
     && (! defined __cplusplus \
	 || (defined YYLTYPE_IS_TRIVIAL && YYLTYPE_IS_TRIVIAL \
	     && defined YYSTYPE_IS_TRIVIAL && YYSTYPE_IS_TRIVIAL)))

/* A type that is properly aligned for any stack member.  */
union yyalloc
{
  yytype_int16 yyss_alloc;
  YYSTYPE yyvs_alloc;
  YYLTYPE yyls_alloc;
};

/* The size of the maximum gap between one aligned stack and the next.  */
# define YYSTACK_GAP_MAXIMUM (sizeof (union yyalloc) - 1)

/* The size of an array large to enough to hold all stacks, each with
   N elements.  */
# define YYSTACK_BYTES(N) \
     ((N) * (sizeof (yytype_int16) + sizeof (YYSTYPE) + sizeof (YYLTYPE)) \
      + 2 * YYSTACK_GAP_MAXIMUM)

/* Copy COUNT objects from FROM to TO.  The source and destination do
   not overlap.  */
# ifndef YYCOPY
#  if defined __GNUC__ && 1 < __GNUC__
#   define YYCOPY(To, From, Count) \
      __builtin_memcpy (To, From, (Count) * sizeof (*(From)))
#  else
#   define YYCOPY(To, From, Count)		\
      do					\
	{					\
	  YYSIZE_T yyi;				\
	  for (yyi = 0; yyi < (Count); yyi++)	\
	    (To)[yyi] = (From)[yyi];		\
	}					\
      while (YYID (0))
#  endif
# endif

/* Relocate STACK from its old location to the new one.  The
   local variables YYSIZE and YYSTACKSIZE give the old and new number of
   elements in the stack, and YYPTR gives the new location of the
   stack.  Advance YYPTR to a properly aligned location for the next
   stack.  */
# define YYSTACK_RELOCATE(Stack_alloc, Stack)				\
    do									\
      {									\
	YYSIZE_T yynewbytes;						\
	YYCOPY (&yyptr->Stack_alloc, Stack, yysize);			\
	Stack = &yyptr->Stack_alloc;					\
	yynewbytes = yystacksize * sizeof (*Stack) + YYSTACK_GAP_MAXIMUM; \
	yyptr += yynewbytes / sizeof (*yyptr);				\
      }									\
    while (YYID (0))

#endif

/* YYFINAL -- State number of the termination state.  */
#define YYFINAL  6
/* YYLAST -- Last index in YYTABLE.  */
#define YYLAST   358

/* YYNTOKENS -- Number of terminals.  */
#define YYNTOKENS  45
/* YYNNTS -- Number of nonterminals.  */
#define YYNNTS  63
/* YYNRULES -- Number of rules.  */
#define YYNRULES  160
/* YYNRULES -- Number of states.  */
#define YYNSTATES  291

/* YYTRANSLATE(YYLEX) -- Bison symbol number corresponding to YYLEX.  */
#define YYUNDEFTOK  2
#define YYMAXUTOK   286

#define YYTRANSLATE(YYX)						\
  ((unsigned int) (YYX) <= YYMAXUTOK ? yytranslate[YYX] : YYUNDEFTOK)

/* YYTRANSLATE[YYLEX] -- Bison symbol number corresponding to YYLEX.  */
static const yytype_uint8 yytranslate[] =
{
       0,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
      33,    34,    41,     2,    35,     2,    44,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,    32,     2,
      39,    36,    40,    43,    42,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,    37,     2,    38,     2,     2,     2,     2,     2,     2,
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
      25,    26,    27,    28,    29,    30,    31
};

#if YYDEBUG
/* YYPRHS[YYN] -- Index of the first RHS symbol of rule number YYN in
   YYRHS.  */
static const yytype_uint16 yyprhs[] =
{
       0,     0,     3,     6,    10,    12,    15,    18,    21,    24,
      27,    30,    33,    34,    36,    37,    44,    46,    50,    53,
      54,    58,    60,    62,    66,    68,    72,    77,    79,    81,
      84,    87,    90,    93,    94,   101,   103,   109,   116,   123,
     125,   131,   138,   141,   144,   146,   150,   154,   161,   168,
     172,   176,   181,   187,   195,   197,   199,   201,   203,   205,
     207,   211,   215,   221,   225,   231,   234,   239,   243,   245,
     247,   251,   253,   257,   262,   266,   268,   270,   272,   274,
     276,   280,   284,   292,   293,   296,   299,   304,   308,   310,
     314,   323,   328,   331,   332,   335,   337,   338,   342,   344,
     348,   350,   353,   355,   358,   359,   362,   365,   368,   369,
     372,   376,   379,   380,   383,   389,   394,   396,   399,   403,
     407,   413,   418,   423,   424,   427,   429,   433,   436,   441,
     445,   447,   449,   451,   453,   458,   462,   469,   473,   477,
     479,   481,   486,   489,   493,   495,   502,   504,   505,   507,
     508,   512,   514,   516,   520,   522,   526,   532,   534,   535,
     537
};

/* YYRHS -- A `-1'-separated list of the rules' RHS.  */
static const yytype_int8 yyrhs[] =
{
      46,     0,    -1,    47,     0,    -1,    30,    47,     0,    -1,
      48,    -1,    48,    68,    -1,    48,    80,    -1,    48,    69,
      -1,    48,    75,    -1,    48,    50,    -1,    48,    76,    -1,
      48,    58,    -1,    -1,    90,    -1,    -1,     6,    51,    52,
      32,    49,    55,    -1,     3,    -1,    33,    53,    34,    -1,
      33,    34,    -1,    -1,    53,    35,    54,    -1,    54,    -1,
      97,    -1,     3,    36,    97,    -1,   107,    -1,    28,    56,
      29,    -1,    28,    30,    56,    29,    -1,   107,    -1,    57,
      -1,    57,    68,    -1,    57,    75,    -1,    57,    80,    -1,
      57,    60,    -1,    -1,    59,    64,    32,    28,    48,    29,
      -1,    59,    -1,    62,    32,    28,    48,    29,    -1,    59,
      63,    32,    28,    48,    29,    -1,    61,    64,    32,    28,
      57,    29,    -1,    61,    -1,    62,    32,    28,    57,    29,
      -1,    61,    63,    32,    28,    57,    29,    -1,    10,    65,
      -1,     9,    65,    -1,     8,    -1,   104,    67,     3,    -1,
     104,    67,    66,    -1,   104,    37,   105,    38,    67,     4,
      -1,   104,    37,   105,    38,    67,    66,    -1,    65,    11,
      65,    -1,    33,    65,    34,    -1,    33,     4,    35,    34,
      -1,    33,     4,    35,     4,    34,    -1,    33,     4,    35,
       4,    35,     4,    34,    -1,    39,    -1,    40,    -1,    26,
      -1,    27,    -1,    24,    -1,    25,    -1,     3,    36,     4,
      -1,     3,    36,    23,    -1,     3,    36,    23,    31,    97,
      -1,     3,    32,    97,    -1,     3,    32,    97,    36,    23,
      -1,    13,    70,    -1,    14,   104,    13,    72,    -1,    70,
      35,    71,    -1,    71,    -1,   104,    -1,   104,    15,     3,
      -1,    73,    -1,    33,    73,    34,    -1,    33,    73,    35,
      34,    -1,    73,    35,    74,    -1,    74,    -1,     3,    -1,
      19,    -1,    20,    -1,    41,    -1,     3,    15,     3,    -1,
       3,    36,    97,    -1,     3,    36,    20,    33,     3,    77,
      34,    -1,    -1,    35,   103,    -1,    35,    78,    -1,    35,
     103,    35,    78,    -1,    78,    35,    79,    -1,    79,    -1,
       3,    36,    97,    -1,    81,     7,     3,    33,    83,    34,
      89,    91,    -1,    81,     7,     3,    17,    -1,    81,    82,
      -1,    -1,    42,   104,    -1,    84,    -1,    -1,    84,    35,
      85,    -1,    85,    -1,     3,    86,    87,    -1,    41,    -1,
      88,    86,    -1,    23,    -1,    32,    97,    -1,    -1,    36,
       3,    -1,    36,     4,    -1,    36,    23,    -1,    -1,    41,
       3,    -1,    41,    41,     3,    -1,    21,    97,    -1,    -1,
      31,     3,    -1,    32,    90,    28,    93,    29,    -1,    32,
      28,    93,    29,    -1,    92,    -1,    32,   107,    -1,    32,
     107,    90,    -1,    32,    90,   107,    -1,    32,    90,    28,
     107,    29,    -1,    32,    28,   107,    29,    -1,    32,    28,
      30,    29,    -1,    -1,    93,    94,    -1,    94,    -1,     3,
      22,    97,    -1,    16,    97,    -1,    16,    97,    33,    34,
      -1,    95,    35,    96,    -1,    96,    -1,    97,    -1,    23,
      -1,   104,    -1,   104,    37,    95,    38,    -1,    37,   102,
      38,    -1,    19,    33,     3,    35,    98,    34,    -1,    33,
      97,    34,    -1,    97,    11,    97,    -1,    43,    -1,    18,
      -1,    37,    99,   101,    38,    -1,    37,    38,    -1,    99,
      35,   100,    -1,   100,    -1,    33,     3,    35,    97,   101,
      34,    -1,    35,    -1,    -1,   103,    -1,    -1,   103,    35,
      97,    -1,    97,    -1,     3,    -1,   104,    44,     3,    -1,
       4,    -1,   106,    32,   106,    -1,   106,    32,   106,    32,
     106,    -1,     4,    -1,    -1,    12,    -1,    23,    -1
};

/* YYRLINE[YYN] -- source line where rule number YYN was defined.  */
static const yytype_uint16 yyrline[] =
{
       0,   130,   130,   131,   135,   139,   140,   141,   142,   148,
     149,   150,   155,   159,   160,   163,   170,   181,   182,   183,
     187,   188,   192,   193,   197,   198,   199,   203,   204,   208,
     209,   214,   215,   220,   225,   228,   233,   237,   256,   259,
     264,   268,   280,   284,   288,   292,   295,   298,   301,   304,
     305,   310,   311,   312,   318,   319,   320,   321,   322,   323,
     327,   331,   335,   339,   343,   350,   354,   361,   362,   365,
     366,   370,   371,   372,   376,   377,   381,   382,   383,   384,
     385,   389,   393,   400,   401,   402,   403,   407,   408,   412,
     416,   431,   442,   443,   447,   452,   453,   457,   458,   462,
     463,   464,   465,   469,   470,   474,   475,   476,   477,   481,
     482,   486,   487,   491,   495,   496,   497,   501,   502,   503,
     504,   505,   506,   507,   511,   512,   516,   517,   518,   522,
     523,   527,   528,   532,   536,   540,   545,   549,   550,   551,
     552,   556,   557,   561,   562,   566,   570,   571,   575,   576,
     580,   581,   586,   587,   595,   596,   601,   609,   610,   614,
     615
};
#endif

#if YYDEBUG || YYERROR_VERBOSE || YYTOKEN_TABLE
/* YYTNAME[SYMBOL-NUM] -- String name of the symbol SYMBOL-NUM.
   First, the terminals, then, starting at YYNTOKENS, nonterminals.  */
static const char *const yytname[] =
{
  "\"end of file\"", "error", "$undefined", "NAME", "NUMBER", "LEXERROR",
  "CLASS", "DEF", "ELSE", "ELIF", "IF", "OR", "PASS", "IMPORT", "FROM",
  "AS", "RAISE", "PYTHONCODE", "NOTHING", "NAMEDTUPLE", "TYPEVAR", "ARROW",
  "COLONEQUALS", "ELLIPSIS", "EQ", "NE", "LE", "GE", "INDENT", "DEDENT",
  "TRIPLEQUOTED", "TYPECOMMENT", "':'", "'('", "')'", "','", "'='", "'['",
  "']'", "'<'", "'>'", "'*'", "'@'", "'?'", "'.'", "$accept", "start",
  "unit", "alldefs", "maybe_type_ignore", "classdef", "class_name",
  "parents", "parent_list", "parent", "maybe_class_funcs", "class_funcs",
  "funcdefs", "if_stmt", "if_and_elifs", "class_if_stmt",
  "class_if_and_elifs", "if_cond", "elif_cond", "else_cond", "condition",
  "version_tuple", "condition_op", "constantdef", "importdef",
  "import_items", "import_item", "from_list", "from_items", "from_item",
  "alias_or_constant", "typevardef", "typevar_args", "typevar_kwargs",
  "typevar_kwarg", "funcdef", "decorators", "decorator", "params",
  "param_list", "param", "param_type", "param_default", "param_star_name",
  "return", "typeignore", "maybe_body", "empty_body", "body", "body_stmt",
  "type_parameters", "type_parameter", "type", "named_tuple_fields",
  "named_tuple_field_list", "named_tuple_field", "maybe_comma",
  "maybe_type_list", "type_list", "dotted_name", "getitem_key",
  "maybe_number", "pass_or_ellipsis", 0
};
#endif

# ifdef YYPRINT
/* YYTOKNUM[YYLEX-NUM] -- Internal token number corresponding to
   token YYLEX-NUM.  */
static const yytype_uint16 yytoknum[] =
{
       0,   256,   257,   258,   259,   260,   261,   262,   263,   264,
     265,   266,   267,   268,   269,   270,   271,   272,   273,   274,
     275,   276,   277,   278,   279,   280,   281,   282,   283,   284,
     285,   286,    58,    40,    41,    44,    61,    91,    93,    60,
      62,    42,    64,    63,    46
};
# endif

/* YYR1[YYN] -- Symbol number of symbol that rule YYN derives.  */
static const yytype_uint8 yyr1[] =
{
       0,    45,    46,    46,    47,    48,    48,    48,    48,    48,
      48,    48,    48,    49,    49,    50,    51,    52,    52,    52,
      53,    53,    54,    54,    55,    55,    55,    56,    56,    57,
      57,    57,    57,    57,    58,    58,    59,    59,    60,    60,
      61,    61,    62,    63,    64,    65,    65,    65,    65,    65,
      65,    66,    66,    66,    67,    67,    67,    67,    67,    67,
      68,    68,    68,    68,    68,    69,    69,    70,    70,    71,
      71,    72,    72,    72,    73,    73,    74,    74,    74,    74,
      74,    75,    76,    77,    77,    77,    77,    78,    78,    79,
      80,    80,    81,    81,    82,    83,    83,    84,    84,    85,
      85,    85,    85,    86,    86,    87,    87,    87,    87,    88,
      88,    89,    89,    90,    91,    91,    91,    92,    92,    92,
      92,    92,    92,    92,    93,    93,    94,    94,    94,    95,
      95,    96,    96,    97,    97,    97,    97,    97,    97,    97,
      97,    98,    98,    99,    99,   100,   101,   101,   102,   102,
     103,   103,   104,   104,   105,   105,   105,   106,   106,   107,
     107
};

/* YYR2[YYN] -- Number of symbols composing right hand side of rule YYN.  */
static const yytype_uint8 yyr2[] =
{
       0,     2,     2,     3,     1,     2,     2,     2,     2,     2,
       2,     2,     0,     1,     0,     6,     1,     3,     2,     0,
       3,     1,     1,     3,     1,     3,     4,     1,     1,     2,
       2,     2,     2,     0,     6,     1,     5,     6,     6,     1,
       5,     6,     2,     2,     1,     3,     3,     6,     6,     3,
       3,     4,     5,     7,     1,     1,     1,     1,     1,     1,
       3,     3,     5,     3,     5,     2,     4,     3,     1,     1,
       3,     1,     3,     4,     3,     1,     1,     1,     1,     1,
       3,     3,     7,     0,     2,     2,     4,     3,     1,     3,
       8,     4,     2,     0,     2,     1,     0,     3,     1,     3,
       1,     2,     1,     2,     0,     2,     2,     2,     0,     2,
       3,     2,     0,     2,     5,     4,     1,     2,     3,     3,
       5,     4,     4,     0,     2,     1,     3,     2,     4,     3,
       1,     1,     1,     1,     4,     3,     6,     3,     3,     1,
       1,     4,     2,     3,     1,     6,     1,     0,     1,     0,
       3,     1,     1,     3,     1,     3,     5,     1,     0,     1,
       1
};

/* YYDEFACT[STATE-NAME] -- Default rule to reduce with in state
   STATE-NUM when YYTABLE doesn't specify something else to do.  Zero
   means the default is an error.  */
static const yytype_uint8 yydefact[] =
{
      12,    12,     0,     0,    93,     0,     1,     2,     0,     0,
       0,     0,     0,     9,    11,    35,     0,     5,     7,     8,
      10,     6,     0,     3,     0,     0,    16,    19,   152,     0,
      42,     0,    65,    68,    69,     0,    44,     0,     0,     0,
       0,     0,     0,    92,   140,     0,     0,   149,   139,    63,
     133,    60,     0,    61,    81,     0,     0,     0,     0,    58,
      59,    56,    57,   158,    54,    55,     0,     0,     0,     0,
       0,    43,     0,     0,    12,     0,    94,     0,     0,   151,
       0,   148,     0,     0,     0,     0,     0,   152,    18,     0,
      21,    22,    14,    50,    49,   154,     0,     0,   153,    45,
       0,    46,    67,    70,    76,    77,    78,     0,    79,    66,
      71,    75,    12,    12,    93,    91,    96,     0,   137,   135,
       0,   138,    64,   132,     0,   130,   131,    83,    62,     0,
      17,     0,     0,     0,    13,     0,   158,     0,     0,     0,
       0,    93,    93,    36,   104,   102,   100,     0,    95,    98,
     104,     0,   150,     0,   134,     0,     0,    23,    20,   113,
     159,   160,    33,    15,    24,     0,   157,   155,     0,    80,
      72,     0,    74,    37,    34,     0,   108,   109,     0,   112,
       0,   101,     0,     0,   129,   152,    85,    88,    84,    82,
      33,     0,    93,    27,    47,    48,   158,     0,    51,    73,
     103,     0,    99,   110,     0,   123,    97,     0,   142,   147,
     144,   136,     0,     0,     0,     0,    25,     0,    32,    39,
       0,    29,    30,    31,   156,    52,     0,   105,   106,   107,
     111,     0,    90,   116,     0,   146,     0,    89,     0,    87,
      86,    26,     0,     0,     0,     0,     0,     0,     0,   117,
       0,   143,   141,     0,     0,    33,    53,     0,     0,     0,
       0,   125,     0,     0,   119,   118,   147,    33,    33,    93,
       0,   127,   122,   115,   124,   121,     0,     0,   146,     0,
      93,    93,    40,   126,     0,   114,   120,   145,    41,    38,
     128
};

/* YYDEFGOTO[NTERM-NUM].  */
static const yytype_int16 yydefgoto[] =
{
      -1,     2,     3,     4,   133,    13,    27,    56,    89,    90,
     163,   191,   192,    14,    15,   218,   219,    16,    38,    39,
      30,   101,    67,    17,    18,    32,    33,   109,   110,   111,
      19,    20,   156,   186,   187,    21,    22,    43,   147,   148,
     149,   176,   202,   150,   205,   134,   232,   233,   260,   261,
     124,   125,    54,   183,   209,   210,   236,    80,    81,    50,
      96,    97,   193
};

/* YYPACT[STATE-NUM] -- Index in YYTABLE of the portion describing
   STATE-NUM.  */
#define YYPACT_NINF -192
static const yytype_int16 yypact[] =
{
      38,  -192,     6,    76,   253,   153,  -192,  -192,   228,   159,
      32,   167,   167,  -192,  -192,   192,   140,  -192,  -192,  -192,
    -192,  -192,    21,  -192,   131,    14,  -192,   176,  -192,    32,
     220,   188,   183,  -192,    70,    29,  -192,    32,   209,   219,
     224,   259,   167,  -192,  -192,   241,   131,   131,  -192,    84,
     -23,  -192,   242,   245,   266,     7,   246,    50,    32,  -192,
    -192,  -192,  -192,   275,  -192,  -192,   277,    69,   167,   278,
      33,   220,   254,   255,  -192,   144,   240,   282,   114,   266,
     248,   252,   131,   265,   103,   286,   131,   256,  -192,   234,
    -192,   266,   260,  -192,  -192,   258,   257,   261,  -192,  -192,
     290,  -192,  -192,  -192,   281,  -192,  -192,    68,  -192,  -192,
     262,  -192,  -192,  -192,   179,  -192,    26,   263,  -192,  -192,
     131,  -192,  -192,  -192,    75,  -192,   266,   264,   266,   131,
    -192,   136,   297,   226,  -192,   218,   298,   268,   301,   236,
      68,   181,   193,  -192,   269,  -192,    13,   271,   272,  -192,
     269,   273,   266,   103,  -192,   138,   274,   266,  -192,  -192,
    -192,  -192,   207,  -192,  -192,    79,  -192,   279,    77,  -192,
    -192,    36,  -192,  -192,  -192,   131,   270,  -192,   306,   291,
      26,  -192,   -18,   280,  -192,   283,   285,  -192,   287,  -192,
     135,   284,    98,  -192,  -192,  -192,   298,   238,  -192,  -192,
     266,   213,  -192,  -192,   131,   289,  -192,   312,  -192,   288,
    -192,  -192,   131,   313,   138,   295,  -192,   229,  -192,   192,
     293,  -192,  -192,  -192,  -192,  -192,   314,  -192,  -192,  -192,
     266,    -4,  -192,  -192,   292,   296,   294,   266,   283,  -192,
     285,  -192,   100,   299,   302,   300,   303,   112,   227,   260,
     131,  -192,  -192,   305,   307,  -192,  -192,   304,   131,   309,
     149,  -192,   310,   217,  -192,  -192,    64,  -192,  -192,   157,
     131,   133,  -192,  -192,  -192,  -192,   195,   311,  -192,   308,
     173,   194,  -192,   266,   315,  -192,  -192,  -192,  -192,  -192,
    -192
};

/* YYPGOTO[NTERM-NUM].  */
static const yytype_int16 yypgoto[] =
{
    -192,  -192,   316,   -67,  -192,  -192,  -192,  -192,  -192,   199,
    -192,   146,   -20,  -192,  -192,  -192,  -192,  -191,   122,   124,
     101,   180,   211,  -189,  -192,  -192,   276,  -192,   243,   -92,
    -187,  -192,  -192,   134,   139,  -183,  -192,  -192,  -192,  -192,
     171,   197,  -192,  -192,  -192,   -86,  -192,  -192,    90,   -55,
    -192,   201,   -24,  -192,  -192,   120,    91,  -192,   203,     1,
    -192,  -132,  -131
};

/* YYTABLE[YYPACT[STATE-NUM]].  What to do in state STATE-NUM.  If
   positive, shift that token.  If negative, reduce the rule which
   number is the opposite.  If zero, do what YYDEFACT says.
   If YYTABLE_NINF, syntax error.  */
#define YYTABLE_NINF -158
static const yytype_int16 yytable[] =
{
      49,   220,   164,   221,   167,   222,     6,   114,   160,   223,
      87,    31,    34,    35,    84,   207,   177,    28,    51,   161,
     208,    66,    78,    79,   247,    44,    45,   132,    41,   144,
      31,    91,    44,    45,    52,    28,   104,    53,    31,   104,
      46,    88,    70,    76,    47,   141,   142,    46,   172,   145,
      48,    47,   105,   106,   178,   105,   106,    48,   121,    31,
     126,    58,   128,    42,   224,    29,   107,   146,     1,    34,
     199,   104,    99,    66,   108,    82,     7,   108,   220,   172,
     221,   197,   222,   194,    93,    69,   223,   105,   106,   220,
     220,   221,   221,   222,   222,    82,   152,   223,   223,   278,
     249,   217,   100,    28,    51,   157,    28,    91,    10,   108,
     153,   198,   100,   154,    66,   257,   262,   264,    44,    45,
      83,    44,    45,    53,   160,    82,   123,   -28,   258,   126,
      57,    79,   277,    46,    28,   161,    46,    47,    71,    87,
      47,   185,   259,    48,    82,   248,    48,   160,   118,    44,
      45,   200,   257,    23,    44,    45,    44,    45,   161,    94,
     217,   115,    26,   265,    46,   258,   284,    10,    47,    46,
      28,    46,    40,    47,    48,    47,   217,   116,   273,    48,
     230,    48,     8,    10,     8,     9,   282,     9,   237,    10,
     152,    10,    11,    12,    11,    12,     8,   217,   257,     9,
      36,    37,   288,    10,    10,   274,    11,    12,   143,    55,
     173,   258,    59,    60,    61,    62,   227,   228,    68,   160,
     257,   274,   174,   289,   285,    63,   266,    64,    65,   160,
     161,    58,    66,   258,   271,   269,   229,   190,   160,   160,
     161,    72,    59,    60,    61,    62,   283,   280,   281,   161,
     161,    73,    74,    -4,   162,   263,     8,    64,    65,     9,
      24,    24,    75,    10,    25,   242,    11,    12,   130,   131,
     170,   171,   225,   226,    77,    85,    86,    82,    92,    95,
      98,   103,   112,   113,    66,   117,   119,   120,   122,   127,
    -157,   132,   129,   136,   137,   135,   138,   140,   151,   155,
     159,   175,   166,   168,   169,   179,   201,   180,   189,   203,
     182,   196,   204,   216,   211,   234,   238,     5,   246,   212,
     213,   231,   214,   235,   241,   245,   270,   250,   255,   207,
     158,   253,   252,   267,   254,   268,   215,   256,   272,   275,
     286,   243,   287,   244,   102,   195,   165,   181,   240,   290,
     139,   206,   239,   276,   184,   251,     0,   279,   188
};

static const yytype_int16 yycheck[] =
{
      24,   192,   133,   192,   136,   192,     0,    74,    12,   192,
       3,    10,    11,    12,    37,    33,     3,     3,     4,    23,
      38,    44,    46,    47,    28,    18,    19,    31,     7,     3,
      29,    55,    18,    19,    20,     3,     3,    23,    37,     3,
      33,    34,    13,    42,    37,   112,   113,    33,   140,    23,
      43,    37,    19,    20,    41,    19,    20,    43,    82,    58,
      84,    11,    86,    42,   196,    33,    33,    41,    30,    68,
      34,     3,     3,    44,    41,    11,     0,    41,   269,   171,
     269,     4,   269,     4,    34,    15,   269,    19,    20,   280,
     281,   280,   281,   280,   281,    11,   120,   280,   281,    35,
     231,     3,    33,     3,     4,   129,     3,   131,    10,    41,
      35,    34,    33,    38,    44,     3,   247,   248,    18,    19,
      36,    18,    19,    23,    12,    11,    23,    29,    16,   153,
      29,   155,   263,    33,     3,    23,    33,    37,    37,     3,
      37,     3,    30,    43,    11,   231,    43,    12,    34,    18,
      19,   175,     3,     0,    18,    19,    18,    19,    23,    58,
       3,    17,     3,   249,    33,    16,    33,    10,    37,    33,
       3,    33,    32,    37,    43,    37,     3,    33,    29,    43,
     204,    43,     3,    10,     3,     6,    29,     6,   212,    10,
     214,    10,    13,    14,    13,    14,     3,     3,     3,     6,
       8,     9,    29,    10,    10,   260,    13,    14,    29,    33,
      29,    16,    24,    25,    26,    27,     3,     4,    35,    12,
       3,   276,    29,    29,    29,    37,   250,    39,    40,    12,
      23,    11,    44,    16,   258,   255,    23,    30,    12,    12,
      23,    32,    24,    25,    26,    27,   270,   267,   268,    23,
      23,    32,    28,     0,    28,    28,     3,    39,    40,     6,
      32,    32,     3,    10,    36,    36,    13,    14,    34,    35,
      34,    35,    34,    35,    33,    33,    31,    11,    32,     4,
       3,     3,    28,    28,    44,     3,    38,    35,    23,     3,
      32,    31,    36,    32,     4,    38,    15,    35,    35,    35,
       3,    32,     4,    35,     3,    34,    36,    35,    34,     3,
      37,    32,    21,    29,    34,     3,     3,     1,     4,    36,
      35,    32,    35,    35,    29,    32,    22,    35,    28,    33,
     131,    32,    38,    28,    32,    28,   190,    34,    29,    29,
      29,   219,    34,   219,    68,   165,   135,   150,   214,    34,
     107,   180,   213,   263,   153,   235,    -1,   266,   155
};

/* YYSTOS[STATE-NUM] -- The (internal number of the) accessing
   symbol of state STATE-NUM.  */
static const yytype_uint8 yystos[] =
{
       0,    30,    46,    47,    48,    47,     0,     0,     3,     6,
      10,    13,    14,    50,    58,    59,    62,    68,    69,    75,
      76,    80,    81,     0,    32,    36,     3,    51,     3,    33,
      65,   104,    70,    71,   104,   104,     8,     9,    63,    64,
      32,     7,    42,    82,    18,    19,    33,    37,    43,    97,
     104,     4,    20,    23,    97,    33,    52,    65,    11,    24,
      25,    26,    27,    37,    39,    40,    44,    67,    35,    15,
      13,    65,    32,    32,    28,     3,   104,    33,    97,    97,
     102,   103,    11,    36,    37,    33,    31,     3,    34,    53,
      54,    97,    32,    34,    65,     4,   105,   106,     3,     3,
      33,    66,    71,     3,     3,    19,    20,    33,    41,    72,
      73,    74,    28,    28,    48,    17,    33,     3,    34,    38,
      35,    97,    23,    23,    95,    96,    97,     3,    97,    36,
      34,    35,    31,    49,    90,    38,    32,     4,    15,    73,
      35,    48,    48,    29,     3,    23,    41,    83,    84,    85,
      88,    35,    97,    35,    38,    35,    77,    97,    54,     3,
      12,    23,    28,    55,   107,    67,     4,   106,    35,     3,
      34,    35,    74,    29,    29,    32,    86,     3,    41,    34,
      35,    86,    37,    98,    96,     3,    78,    79,   103,    34,
      30,    56,    57,   107,     4,    66,    32,     4,    34,    34,
      97,    36,    87,     3,    21,    89,    85,    33,    38,    99,
     100,    34,    36,    35,    35,    56,    29,     3,    60,    61,
      62,    68,    75,    80,   106,    34,    35,     3,     4,    23,
      97,    32,    91,    92,     3,    35,   101,    97,     3,    79,
      78,    29,    36,    63,    64,    32,     4,    28,    90,   107,
      35,   100,    38,    32,    32,    28,    34,     3,    16,    30,
      93,    94,   107,    28,   107,    90,    97,    28,    28,    57,
      22,    97,    29,    29,    94,    29,    93,   107,    35,   101,
      57,    57,    29,    97,    33,    29,    29,    34,    29,    29,
      34
};

#define yyerrok		(yyerrstatus = 0)
#define yyclearin	(yychar = YYEMPTY)
#define YYEMPTY		(-2)
#define YYEOF		0

#define YYACCEPT	goto yyacceptlab
#define YYABORT		goto yyabortlab
#define YYERROR		goto yyerrorlab


/* Like YYERROR except do call yyerror.  This remains here temporarily
   to ease the transition to the new meaning of YYERROR, for GCC.
   Once GCC version 2 has supplanted version 1, this can go.  However,
   YYFAIL appears to be in use.  Nevertheless, it is formally deprecated
   in Bison 2.4.2's NEWS entry, where a plan to phase it out is
   discussed.  */

#define YYFAIL		goto yyerrlab
#if defined YYFAIL
  /* This is here to suppress warnings from the GCC cpp's
     -Wunused-macros.  Normally we don't worry about that warning, but
     some users do, and we want to make it easy for users to remove
     YYFAIL uses, which will produce warnings from Bison 2.5.  */
#endif

#define YYRECOVERING()  (!!yyerrstatus)

#define YYBACKUP(Token, Value)					\
do								\
  if (yychar == YYEMPTY && yylen == 1)				\
    {								\
      yychar = (Token);						\
      yylval = (Value);						\
      yytoken = YYTRANSLATE (yychar);				\
      YYPOPSTACK (1);						\
      goto yybackup;						\
    }								\
  else								\
    {								\
      yyerror (&yylloc, scanner, ctx, YY_("syntax error: cannot back up")); \
      YYERROR;							\
    }								\
while (YYID (0))


#define YYTERROR	1
#define YYERRCODE	256


/* YYLLOC_DEFAULT -- Set CURRENT to span from RHS[1] to RHS[N].
   If N is 0, then set CURRENT to the empty location which ends
   the previous symbol: RHS[0] (always defined).  */

#define YYRHSLOC(Rhs, K) ((Rhs)[K])
#ifndef YYLLOC_DEFAULT
# define YYLLOC_DEFAULT(Current, Rhs, N)				\
    do									\
      if (YYID (N))                                                    \
	{								\
	  (Current).first_line   = YYRHSLOC (Rhs, 1).first_line;	\
	  (Current).first_column = YYRHSLOC (Rhs, 1).first_column;	\
	  (Current).last_line    = YYRHSLOC (Rhs, N).last_line;		\
	  (Current).last_column  = YYRHSLOC (Rhs, N).last_column;	\
	}								\
      else								\
	{								\
	  (Current).first_line   = (Current).last_line   =		\
	    YYRHSLOC (Rhs, 0).last_line;				\
	  (Current).first_column = (Current).last_column =		\
	    YYRHSLOC (Rhs, 0).last_column;				\
	}								\
    while (YYID (0))
#endif


/* YY_LOCATION_PRINT -- Print the location on the stream.
   This macro was not mandated originally: define only if we know
   we won't break user code: when these are the locations we know.  */

#ifndef YY_LOCATION_PRINT
# if defined YYLTYPE_IS_TRIVIAL && YYLTYPE_IS_TRIVIAL
#  define YY_LOCATION_PRINT(File, Loc)			\
     fprintf (File, "%d.%d-%d.%d",			\
	      (Loc).first_line, (Loc).first_column,	\
	      (Loc).last_line,  (Loc).last_column)
# else
#  define YY_LOCATION_PRINT(File, Loc) ((void) 0)
# endif
#endif


/* YYLEX -- calling `yylex' with the right arguments.  */

#ifdef YYLEX_PARAM
# define YYLEX yylex (&yylval, &yylloc, YYLEX_PARAM)
#else
# define YYLEX yylex (&yylval, &yylloc, scanner)
#endif

/* Enable debugging if requested.  */
#if YYDEBUG

# ifndef YYFPRINTF
#  include <stdio.h> /* INFRINGES ON USER NAME SPACE */
#  define YYFPRINTF fprintf
# endif

# define YYDPRINTF(Args)			\
do {						\
  if (yydebug)					\
    YYFPRINTF Args;				\
} while (YYID (0))

# define YY_SYMBOL_PRINT(Title, Type, Value, Location)			  \
do {									  \
  if (yydebug)								  \
    {									  \
      YYFPRINTF (stderr, "%s ", Title);					  \
      yy_symbol_print (stderr,						  \
		  Type, Value, Location, scanner, ctx); \
      YYFPRINTF (stderr, "\n");						  \
    }									  \
} while (YYID (0))


/*--------------------------------.
| Print this symbol on YYOUTPUT.  |
`--------------------------------*/

/*ARGSUSED*/
#if (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
static void
yy_symbol_value_print (FILE *yyoutput, int yytype, YYSTYPE const * const yyvaluep, YYLTYPE const * const yylocationp, void* scanner, pytype::Context* ctx)
#else
static void
yy_symbol_value_print (yyoutput, yytype, yyvaluep, yylocationp, scanner, ctx)
    FILE *yyoutput;
    int yytype;
    YYSTYPE const * const yyvaluep;
    YYLTYPE const * const yylocationp;
    void* scanner;
    pytype::Context* ctx;
#endif
{
  if (!yyvaluep)
    return;
  YYUSE (yylocationp);
  YYUSE (scanner);
  YYUSE (ctx);
# ifdef YYPRINT
  if (yytype < YYNTOKENS)
    YYPRINT (yyoutput, yytoknum[yytype], *yyvaluep);
# else
  YYUSE (yyoutput);
# endif
  switch (yytype)
    {
      default:
	break;
    }
}


/*--------------------------------.
| Print this symbol on YYOUTPUT.  |
`--------------------------------*/

#if (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
static void
yy_symbol_print (FILE *yyoutput, int yytype, YYSTYPE const * const yyvaluep, YYLTYPE const * const yylocationp, void* scanner, pytype::Context* ctx)
#else
static void
yy_symbol_print (yyoutput, yytype, yyvaluep, yylocationp, scanner, ctx)
    FILE *yyoutput;
    int yytype;
    YYSTYPE const * const yyvaluep;
    YYLTYPE const * const yylocationp;
    void* scanner;
    pytype::Context* ctx;
#endif
{
  if (yytype < YYNTOKENS)
    YYFPRINTF (yyoutput, "token %s (", yytname[yytype]);
  else
    YYFPRINTF (yyoutput, "nterm %s (", yytname[yytype]);

  YY_LOCATION_PRINT (yyoutput, *yylocationp);
  YYFPRINTF (yyoutput, ": ");
  yy_symbol_value_print (yyoutput, yytype, yyvaluep, yylocationp, scanner, ctx);
  YYFPRINTF (yyoutput, ")");
}

/*------------------------------------------------------------------.
| yy_stack_print -- Print the state stack from its BOTTOM up to its |
| TOP (included).                                                   |
`------------------------------------------------------------------*/

#if (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
static void
yy_stack_print (yytype_int16 *yybottom, yytype_int16 *yytop)
#else
static void
yy_stack_print (yybottom, yytop)
    yytype_int16 *yybottom;
    yytype_int16 *yytop;
#endif
{
  YYFPRINTF (stderr, "Stack now");
  for (; yybottom <= yytop; yybottom++)
    {
      int yybot = *yybottom;
      YYFPRINTF (stderr, " %d", yybot);
    }
  YYFPRINTF (stderr, "\n");
}

# define YY_STACK_PRINT(Bottom, Top)				\
do {								\
  if (yydebug)							\
    yy_stack_print ((Bottom), (Top));				\
} while (YYID (0))


/*------------------------------------------------.
| Report that the YYRULE is going to be reduced.  |
`------------------------------------------------*/

#if (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
static void
yy_reduce_print (YYSTYPE *yyvsp, YYLTYPE *yylsp, int yyrule, void* scanner, pytype::Context* ctx)
#else
static void
yy_reduce_print (yyvsp, yylsp, yyrule, scanner, ctx)
    YYSTYPE *yyvsp;
    YYLTYPE *yylsp;
    int yyrule;
    void* scanner;
    pytype::Context* ctx;
#endif
{
  int yynrhs = yyr2[yyrule];
  int yyi;
  unsigned long int yylno = yyrline[yyrule];
  YYFPRINTF (stderr, "Reducing stack by rule %d (line %lu):\n",
	     yyrule - 1, yylno);
  /* The symbols being reduced.  */
  for (yyi = 0; yyi < yynrhs; yyi++)
    {
      YYFPRINTF (stderr, "   $%d = ", yyi + 1);
      yy_symbol_print (stderr, yyrhs[yyprhs[yyrule] + yyi],
		       &(yyvsp[(yyi + 1) - (yynrhs)])
		       , &(yylsp[(yyi + 1) - (yynrhs)])		       , scanner, ctx);
      YYFPRINTF (stderr, "\n");
    }
}

# define YY_REDUCE_PRINT(Rule)		\
do {					\
  if (yydebug)				\
    yy_reduce_print (yyvsp, yylsp, Rule, scanner, ctx); \
} while (YYID (0))

/* Nonzero means print parse trace.  It is left uninitialized so that
   multiple parsers can coexist.  */
int yydebug;
#else /* !YYDEBUG */
# define YYDPRINTF(Args)
# define YY_SYMBOL_PRINT(Title, Type, Value, Location)
# define YY_STACK_PRINT(Bottom, Top)
# define YY_REDUCE_PRINT(Rule)
#endif /* !YYDEBUG */


/* YYINITDEPTH -- initial size of the parser's stacks.  */
#ifndef	YYINITDEPTH
# define YYINITDEPTH 200
#endif

/* YYMAXDEPTH -- maximum size the stacks can grow to (effective only
   if the built-in stack extension method is used).

   Do not make this value too large; the results are undefined if
   YYSTACK_ALLOC_MAXIMUM < YYSTACK_BYTES (YYMAXDEPTH)
   evaluated with infinite-precision integer arithmetic.  */

#ifndef YYMAXDEPTH
# define YYMAXDEPTH 10000
#endif



#if YYERROR_VERBOSE

# ifndef yystrlen
#  if defined __GLIBC__ && defined _STRING_H
#   define yystrlen strlen
#  else
/* Return the length of YYSTR.  */
#if (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
static YYSIZE_T
yystrlen (const char *yystr)
#else
static YYSIZE_T
yystrlen (yystr)
    const char *yystr;
#endif
{
  YYSIZE_T yylen;
  for (yylen = 0; yystr[yylen]; yylen++)
    continue;
  return yylen;
}
#  endif
# endif

# ifndef yystpcpy
#  if defined __GLIBC__ && defined _STRING_H && defined _GNU_SOURCE
#   define yystpcpy stpcpy
#  else
/* Copy YYSRC to YYDEST, returning the address of the terminating '\0' in
   YYDEST.  */
#if (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
static char *
yystpcpy (char *yydest, const char *yysrc)
#else
static char *
yystpcpy (yydest, yysrc)
    char *yydest;
    const char *yysrc;
#endif
{
  char *yyd = yydest;
  const char *yys = yysrc;

  while ((*yyd++ = *yys++) != '\0')
    continue;

  return yyd - 1;
}
#  endif
# endif

# ifndef yytnamerr
/* Copy to YYRES the contents of YYSTR after stripping away unnecessary
   quotes and backslashes, so that it's suitable for yyerror.  The
   heuristic is that double-quoting is unnecessary unless the string
   contains an apostrophe, a comma, or backslash (other than
   backslash-backslash).  YYSTR is taken from yytname.  If YYRES is
   null, do not copy; instead, return the length of what the result
   would have been.  */
static YYSIZE_T
yytnamerr (char *yyres, const char *yystr)
{
  if (*yystr == '"')
    {
      YYSIZE_T yyn = 0;
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
	    /* Fall through.  */
	  default:
	    if (yyres)
	      yyres[yyn] = *yyp;
	    yyn++;
	    break;

	  case '"':
	    if (yyres)
	      yyres[yyn] = '\0';
	    return yyn;
	  }
    do_not_strip_quotes: ;
    }

  if (! yyres)
    return yystrlen (yystr);

  return yystpcpy (yyres, yystr) - yyres;
}
# endif

/* Copy into YYRESULT an error message about the unexpected token
   YYCHAR while in state YYSTATE.  Return the number of bytes copied,
   including the terminating null byte.  If YYRESULT is null, do not
   copy anything; just return the number of bytes that would be
   copied.  As a special case, return 0 if an ordinary "syntax error"
   message will do.  Return YYSIZE_MAXIMUM if overflow occurs during
   size calculation.  */
static YYSIZE_T
yysyntax_error (char *yyresult, int yystate, int yychar)
{
  int yyn = yypact[yystate];

  if (! (YYPACT_NINF < yyn && yyn <= YYLAST))
    return 0;
  else
    {
      int yytype = YYTRANSLATE (yychar);
      YYSIZE_T yysize0 = yytnamerr (0, yytname[yytype]);
      YYSIZE_T yysize = yysize0;
      YYSIZE_T yysize1;
      int yysize_overflow = 0;
      enum { YYERROR_VERBOSE_ARGS_MAXIMUM = 5 };
      char const *yyarg[YYERROR_VERBOSE_ARGS_MAXIMUM];
      int yyx;

# if 0
      /* This is so xgettext sees the translatable formats that are
	 constructed on the fly.  */
      YY_("syntax error, unexpected %s");
      YY_("syntax error, unexpected %s, expecting %s");
      YY_("syntax error, unexpected %s, expecting %s or %s");
      YY_("syntax error, unexpected %s, expecting %s or %s or %s");
      YY_("syntax error, unexpected %s, expecting %s or %s or %s or %s");
# endif
      char *yyfmt;
      char const *yyf;
      static char const yyunexpected[] = "syntax error, unexpected %s";
      static char const yyexpecting[] = ", expecting %s";
      static char const yyor[] = " or %s";
      char yyformat[sizeof yyunexpected
		    + sizeof yyexpecting - 1
		    + ((YYERROR_VERBOSE_ARGS_MAXIMUM - 2)
		       * (sizeof yyor - 1))];
      char const *yyprefix = yyexpecting;

      /* Start YYX at -YYN if negative to avoid negative indexes in
	 YYCHECK.  */
      int yyxbegin = yyn < 0 ? -yyn : 0;

      /* Stay within bounds of both yycheck and yytname.  */
      int yychecklim = YYLAST - yyn + 1;
      int yyxend = yychecklim < YYNTOKENS ? yychecklim : YYNTOKENS;
      int yycount = 1;

      yyarg[0] = yytname[yytype];
      yyfmt = yystpcpy (yyformat, yyunexpected);

      for (yyx = yyxbegin; yyx < yyxend; ++yyx)
	if (yycheck[yyx + yyn] == yyx && yyx != YYTERROR)
	  {
	    if (yycount == YYERROR_VERBOSE_ARGS_MAXIMUM)
	      {
		yycount = 1;
		yysize = yysize0;
		yyformat[sizeof yyunexpected - 1] = '\0';
		break;
	      }
	    yyarg[yycount++] = yytname[yyx];
	    yysize1 = yysize + yytnamerr (0, yytname[yyx]);
	    yysize_overflow |= (yysize1 < yysize);
	    yysize = yysize1;
	    yyfmt = yystpcpy (yyfmt, yyprefix);
	    yyprefix = yyor;
	  }

      yyf = YY_(yyformat);
      yysize1 = yysize + yystrlen (yyf);
      yysize_overflow |= (yysize1 < yysize);
      yysize = yysize1;

      if (yysize_overflow)
	return YYSIZE_MAXIMUM;

      if (yyresult)
	{
	  /* Avoid sprintf, as that infringes on the user's name space.
	     Don't have undefined behavior even if the translation
	     produced a string with the wrong number of "%s"s.  */
	  char *yyp = yyresult;
	  int yyi = 0;
	  while ((*yyp = *yyf) != '\0')
	    {
	      if (*yyp == '%' && yyf[1] == 's' && yyi < yycount)
		{
		  yyp += yytnamerr (yyp, yyarg[yyi++]);
		  yyf += 2;
		}
	      else
		{
		  yyp++;
		  yyf++;
		}
	    }
	}
      return yysize;
    }
}
#endif /* YYERROR_VERBOSE */


/*-----------------------------------------------.
| Release the memory associated to this symbol.  |
`-----------------------------------------------*/

/*ARGSUSED*/
#if (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
static void
yydestruct (const char *yymsg, int yytype, YYSTYPE *yyvaluep, YYLTYPE *yylocationp, void* scanner, pytype::Context* ctx)
#else
static void
yydestruct (yymsg, yytype, yyvaluep, yylocationp, scanner, ctx)
    const char *yymsg;
    int yytype;
    YYSTYPE *yyvaluep;
    YYLTYPE *yylocationp;
    void* scanner;
    pytype::Context* ctx;
#endif
{
  YYUSE (yyvaluep);
  YYUSE (yylocationp);
  YYUSE (scanner);
  YYUSE (ctx);

  if (!yymsg)
    yymsg = "Deleting";
  YY_SYMBOL_PRINT (yymsg, yytype, yyvaluep, yylocationp);

  switch (yytype)
    {
      case 3: /* "NAME" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1447 "pyi/parser.tab.cc"
	break;
      case 4: /* "NUMBER" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1456 "pyi/parser.tab.cc"
	break;
      case 5: /* "LEXERROR" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1465 "pyi/parser.tab.cc"
	break;
      case 46: /* "start" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1474 "pyi/parser.tab.cc"
	break;
      case 47: /* "unit" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1483 "pyi/parser.tab.cc"
	break;
      case 48: /* "alldefs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1492 "pyi/parser.tab.cc"
	break;
      case 50: /* "classdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1501 "pyi/parser.tab.cc"
	break;
      case 51: /* "class_name" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1510 "pyi/parser.tab.cc"
	break;
      case 52: /* "parents" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1519 "pyi/parser.tab.cc"
	break;
      case 53: /* "parent_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1528 "pyi/parser.tab.cc"
	break;
      case 54: /* "parent" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1537 "pyi/parser.tab.cc"
	break;
      case 55: /* "maybe_class_funcs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1546 "pyi/parser.tab.cc"
	break;
      case 56: /* "class_funcs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1555 "pyi/parser.tab.cc"
	break;
      case 57: /* "funcdefs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1564 "pyi/parser.tab.cc"
	break;
      case 58: /* "if_stmt" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1573 "pyi/parser.tab.cc"
	break;
      case 59: /* "if_and_elifs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1582 "pyi/parser.tab.cc"
	break;
      case 60: /* "class_if_stmt" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1591 "pyi/parser.tab.cc"
	break;
      case 61: /* "class_if_and_elifs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1600 "pyi/parser.tab.cc"
	break;
      case 62: /* "if_cond" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1609 "pyi/parser.tab.cc"
	break;
      case 63: /* "elif_cond" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1618 "pyi/parser.tab.cc"
	break;
      case 64: /* "else_cond" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1627 "pyi/parser.tab.cc"
	break;
      case 65: /* "condition" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1636 "pyi/parser.tab.cc"
	break;
      case 66: /* "version_tuple" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1645 "pyi/parser.tab.cc"
	break;
      case 67: /* "condition_op" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->str)); };

/* Line 1009 of yacc.c  */
#line 1654 "pyi/parser.tab.cc"
	break;
      case 68: /* "constantdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1663 "pyi/parser.tab.cc"
	break;
      case 69: /* "importdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1672 "pyi/parser.tab.cc"
	break;
      case 70: /* "import_items" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1681 "pyi/parser.tab.cc"
	break;
      case 71: /* "import_item" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1690 "pyi/parser.tab.cc"
	break;
      case 72: /* "from_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1699 "pyi/parser.tab.cc"
	break;
      case 73: /* "from_items" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1708 "pyi/parser.tab.cc"
	break;
      case 74: /* "from_item" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1717 "pyi/parser.tab.cc"
	break;
      case 75: /* "alias_or_constant" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1726 "pyi/parser.tab.cc"
	break;
      case 76: /* "typevardef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1735 "pyi/parser.tab.cc"
	break;
      case 77: /* "typevar_args" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1744 "pyi/parser.tab.cc"
	break;
      case 78: /* "typevar_kwargs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1753 "pyi/parser.tab.cc"
	break;
      case 79: /* "typevar_kwarg" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1762 "pyi/parser.tab.cc"
	break;
      case 80: /* "funcdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1771 "pyi/parser.tab.cc"
	break;
      case 81: /* "decorators" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1780 "pyi/parser.tab.cc"
	break;
      case 82: /* "decorator" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1789 "pyi/parser.tab.cc"
	break;
      case 83: /* "params" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1798 "pyi/parser.tab.cc"
	break;
      case 84: /* "param_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1807 "pyi/parser.tab.cc"
	break;
      case 85: /* "param" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1816 "pyi/parser.tab.cc"
	break;
      case 86: /* "param_type" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1825 "pyi/parser.tab.cc"
	break;
      case 87: /* "param_default" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1834 "pyi/parser.tab.cc"
	break;
      case 88: /* "param_star_name" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1843 "pyi/parser.tab.cc"
	break;
      case 89: /* "return" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1852 "pyi/parser.tab.cc"
	break;
      case 91: /* "maybe_body" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1861 "pyi/parser.tab.cc"
	break;
      case 93: /* "body" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1870 "pyi/parser.tab.cc"
	break;
      case 94: /* "body_stmt" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1879 "pyi/parser.tab.cc"
	break;
      case 95: /* "type_parameters" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1888 "pyi/parser.tab.cc"
	break;
      case 96: /* "type_parameter" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1897 "pyi/parser.tab.cc"
	break;
      case 97: /* "type" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1906 "pyi/parser.tab.cc"
	break;
      case 98: /* "named_tuple_fields" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1915 "pyi/parser.tab.cc"
	break;
      case 99: /* "named_tuple_field_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1924 "pyi/parser.tab.cc"
	break;
      case 100: /* "named_tuple_field" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1933 "pyi/parser.tab.cc"
	break;
      case 102: /* "maybe_type_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1942 "pyi/parser.tab.cc"
	break;
      case 103: /* "type_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1951 "pyi/parser.tab.cc"
	break;
      case 104: /* "dotted_name" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1960 "pyi/parser.tab.cc"
	break;
      case 105: /* "getitem_key" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1969 "pyi/parser.tab.cc"
	break;
      case 106: /* "maybe_number" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1978 "pyi/parser.tab.cc"
	break;

      default:
	break;
    }
}

/* Prevent warnings from -Wmissing-prototypes.  */
#ifdef YYPARSE_PARAM
#if defined __STDC__ || defined __cplusplus
int yyparse (void *YYPARSE_PARAM);
#else
int yyparse ();
#endif
#else /* ! YYPARSE_PARAM */
#if defined __STDC__ || defined __cplusplus
int yyparse (void* scanner, pytype::Context* ctx);
#else
int yyparse ();
#endif
#endif /* ! YYPARSE_PARAM */





/*-------------------------.
| yyparse or yypush_parse.  |
`-------------------------*/

#ifdef YYPARSE_PARAM
#if (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
int
yyparse (void *YYPARSE_PARAM)
#else
int
yyparse (YYPARSE_PARAM)
    void *YYPARSE_PARAM;
#endif
#else /* ! YYPARSE_PARAM */
#if (defined __STDC__ || defined __C99__FUNC__ \
     || defined __cplusplus || defined _MSC_VER)
int
yyparse (void* scanner, pytype::Context* ctx)
#else
int
yyparse (scanner, ctx)
    void* scanner;
    pytype::Context* ctx;
#endif
#endif
{
/* The lookahead symbol.  */
int yychar;

/* The semantic value of the lookahead symbol.  */
YYSTYPE yylval;

/* Location data for the lookahead symbol.  */
YYLTYPE yylloc;

    /* Number of syntax errors so far.  */
    int yynerrs;

    int yystate;
    /* Number of tokens to shift before error messages enabled.  */
    int yyerrstatus;

    /* The stacks and their tools:
       `yyss': related to states.
       `yyvs': related to semantic values.
       `yyls': related to locations.

       Refer to the stacks thru separate pointers, to allow yyoverflow
       to reallocate them elsewhere.  */

    /* The state stack.  */
    yytype_int16 yyssa[YYINITDEPTH];
    yytype_int16 *yyss;
    yytype_int16 *yyssp;

    /* The semantic value stack.  */
    YYSTYPE yyvsa[YYINITDEPTH];
    YYSTYPE *yyvs;
    YYSTYPE *yyvsp;

    /* The location stack.  */
    YYLTYPE yylsa[YYINITDEPTH];
    YYLTYPE *yyls;
    YYLTYPE *yylsp;

    /* The locations where the error started and ended.  */
    YYLTYPE yyerror_range[2];

    YYSIZE_T yystacksize;

  int yyn;
  int yyresult;
  /* Lookahead token as an internal (translated) token number.  */
  int yytoken;
  /* The variables used to return semantic value and location from the
     action routines.  */
  YYSTYPE yyval;
  YYLTYPE yyloc;

#if YYERROR_VERBOSE
  /* Buffer for error messages, and its allocated size.  */
  char yymsgbuf[128];
  char *yymsg = yymsgbuf;
  YYSIZE_T yymsg_alloc = sizeof yymsgbuf;
#endif

#define YYPOPSTACK(N)   (yyvsp -= (N), yyssp -= (N), yylsp -= (N))

  /* The number of symbols on the RHS of the reduced rule.
     Keep to zero when no symbol should be popped.  */
  int yylen = 0;

  yytoken = 0;
  yyss = yyssa;
  yyvs = yyvsa;
  yyls = yylsa;
  yystacksize = YYINITDEPTH;

  YYDPRINTF ((stderr, "Starting parse\n"));

  yystate = 0;
  yyerrstatus = 0;
  yynerrs = 0;
  yychar = YYEMPTY; /* Cause a token to be read.  */

  /* Initialize stack pointers.
     Waste one element of value and location stack
     so that they stay on the same level as the state stack.
     The wasted elements are never initialized.  */
  yyssp = yyss;
  yyvsp = yyvs;
  yylsp = yyls;

#if defined YYLTYPE_IS_TRIVIAL && YYLTYPE_IS_TRIVIAL
  /* Initialize the default location before parsing starts.  */
  yylloc.first_line   = yylloc.last_line   = 1;
  yylloc.first_column = yylloc.last_column = 1;
#endif

  goto yysetstate;

/*------------------------------------------------------------.
| yynewstate -- Push a new state, which is found in yystate.  |
`------------------------------------------------------------*/
 yynewstate:
  /* In all cases, when you get here, the value and location stacks
     have just been pushed.  So pushing a state here evens the stacks.  */
  yyssp++;

 yysetstate:
  *yyssp = yystate;

  if (yyss + yystacksize - 1 <= yyssp)
    {
      /* Get the current used size of the three stacks, in elements.  */
      YYSIZE_T yysize = yyssp - yyss + 1;

#ifdef yyoverflow
      {
	/* Give user a chance to reallocate the stack.  Use copies of
	   these so that the &'s don't force the real ones into
	   memory.  */
	YYSTYPE *yyvs1 = yyvs;
	yytype_int16 *yyss1 = yyss;
	YYLTYPE *yyls1 = yyls;

	/* Each stack pointer address is followed by the size of the
	   data in use in that stack, in bytes.  This used to be a
	   conditional around just the two extra args, but that might
	   be undefined if yyoverflow is a macro.  */
	yyoverflow (YY_("memory exhausted"),
		    &yyss1, yysize * sizeof (*yyssp),
		    &yyvs1, yysize * sizeof (*yyvsp),
		    &yyls1, yysize * sizeof (*yylsp),
		    &yystacksize);

	yyls = yyls1;
	yyss = yyss1;
	yyvs = yyvs1;
      }
#else /* no yyoverflow */
# ifndef YYSTACK_RELOCATE
      goto yyexhaustedlab;
# else
      /* Extend the stack our own way.  */
      if (YYMAXDEPTH <= yystacksize)
	goto yyexhaustedlab;
      yystacksize *= 2;
      if (YYMAXDEPTH < yystacksize)
	yystacksize = YYMAXDEPTH;

      {
	yytype_int16 *yyss1 = yyss;
	union yyalloc *yyptr =
	  (union yyalloc *) YYSTACK_ALLOC (YYSTACK_BYTES (yystacksize));
	if (! yyptr)
	  goto yyexhaustedlab;
	YYSTACK_RELOCATE (yyss_alloc, yyss);
	YYSTACK_RELOCATE (yyvs_alloc, yyvs);
	YYSTACK_RELOCATE (yyls_alloc, yyls);
#  undef YYSTACK_RELOCATE
	if (yyss1 != yyssa)
	  YYSTACK_FREE (yyss1);
      }
# endif
#endif /* no yyoverflow */

      yyssp = yyss + yysize - 1;
      yyvsp = yyvs + yysize - 1;
      yylsp = yyls + yysize - 1;

      YYDPRINTF ((stderr, "Stack size increased to %lu\n",
		  (unsigned long int) yystacksize));

      if (yyss + yystacksize - 1 <= yyssp)
	YYABORT;
    }

  YYDPRINTF ((stderr, "Entering state %d\n", yystate));

  if (yystate == YYFINAL)
    YYACCEPT;

  goto yybackup;

/*-----------.
| yybackup.  |
`-----------*/
yybackup:

  /* Do appropriate processing given the current state.  Read a
     lookahead token if we need one and don't already have one.  */

  /* First try to decide what to do without reference to lookahead token.  */
  yyn = yypact[yystate];
  if (yyn == YYPACT_NINF)
    goto yydefault;

  /* Not known => get a lookahead token if don't already have one.  */

  /* YYCHAR is either YYEMPTY or YYEOF or a valid lookahead symbol.  */
  if (yychar == YYEMPTY)
    {
      YYDPRINTF ((stderr, "Reading a token: "));
      yychar = YYLEX;
    }

  if (yychar <= YYEOF)
    {
      yychar = yytoken = YYEOF;
      YYDPRINTF ((stderr, "Now at end of input.\n"));
    }
  else
    {
      yytoken = YYTRANSLATE (yychar);
      YY_SYMBOL_PRINT ("Next token is", yytoken, &yylval, &yylloc);
    }

  /* If the proper action on seeing token YYTOKEN is to reduce or to
     detect an error, take that action.  */
  yyn += yytoken;
  if (yyn < 0 || YYLAST < yyn || yycheck[yyn] != yytoken)
    goto yydefault;
  yyn = yytable[yyn];
  if (yyn <= 0)
    {
      if (yyn == 0 || yyn == YYTABLE_NINF)
	goto yyerrlab;
      yyn = -yyn;
      goto yyreduce;
    }

  /* Count tokens shifted since error; after three, turn off error
     status.  */
  if (yyerrstatus)
    yyerrstatus--;

  /* Shift the lookahead token.  */
  YY_SYMBOL_PRINT ("Shifting", yytoken, &yylval, &yylloc);

  /* Discard the shifted token.  */
  yychar = YYEMPTY;

  yystate = yyn;
  *++yyvsp = yylval;
  *++yylsp = yylloc;
  goto yynewstate;


/*-----------------------------------------------------------.
| yydefault -- do the default action for the current state.  |
`-----------------------------------------------------------*/
yydefault:
  yyn = yydefact[yystate];
  if (yyn == 0)
    goto yyerrlab;
  goto yyreduce;


/*-----------------------------.
| yyreduce -- Do a reduction.  |
`-----------------------------*/
yyreduce:
  /* yyn is the number of a rule to reduce with.  */
  yylen = yyr2[yyn];

  /* If YYLEN is nonzero, implement the default value of the action:
     `$$ = $1'.

     Otherwise, the following line sets YYVAL to garbage.
     This behavior is undocumented and Bison
     users should not rely upon it.  Assigning to YYVAL
     unconditionally makes the parser a bit smaller, and it avoids a
     GCC warning that YYVAL may be used uninitialized.  */
  yyval = yyvsp[1-yylen];

  /* Default location.  */
  YYLLOC_DEFAULT (yyloc, (yylsp - yylen), yylen);
  YY_REDUCE_PRINT (yyn);
  switch (yyn)
    {
        case 2:

/* Line 1464 of yacc.c  */
#line 130 "parser.y"
    { ctx->SetAndDelResult((yyvsp[(1) - (2)].obj)); (yyval.obj) = NULL; ;}
    break;

  case 3:

/* Line 1464 of yacc.c  */
#line 131 "parser.y"
    { ctx->SetAndDelResult((yyvsp[(2) - (3)].obj)); (yyval.obj) = NULL; ;}
    break;

  case 5:

/* Line 1464 of yacc.c  */
#line 139 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 6:

/* Line 1464 of yacc.c  */
#line 140 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 7:

/* Line 1464 of yacc.c  */
#line 141 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 8:

/* Line 1464 of yacc.c  */
#line 142 "parser.y"
    {
      (yyval.obj) = (yyvsp[(1) - (2)].obj);
      PyObject* tmp = ctx->Call(kAddAliasOrConstant, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yyloc));
      Py_DECREF(tmp);
    ;}
    break;

  case 9:

/* Line 1464 of yacc.c  */
#line 148 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 10:

/* Line 1464 of yacc.c  */
#line 149 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 11:

/* Line 1464 of yacc.c  */
#line 150 "parser.y"
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yylsp[(2) - (2)]));
      (yyval.obj) = ExtendList((yyvsp[(1) - (2)].obj), tmp);
    ;}
    break;

  case 12:

/* Line 1464 of yacc.c  */
#line 155 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 15:

/* Line 1464 of yacc.c  */
#line 163 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddClass, "(NNN)", (yyvsp[(2) - (6)].obj), (yyvsp[(3) - (6)].obj), (yyvsp[(6) - (6)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 16:

/* Line 1464 of yacc.c  */
#line 170 "parser.y"
    {
      // Do not borrow the $1 reference since it is also returned later
      // in $$.  Use O instead of N in the format string.
      PyObject* tmp = ctx->Call(kRegisterClassName, "(O)", (yyvsp[(1) - (1)].obj));
      CHECK(tmp, (yyloc));
      Py_DECREF(tmp);
      (yyval.obj) = (yyvsp[(1) - (1)].obj);
    ;}
    break;

  case 17:

/* Line 1464 of yacc.c  */
#line 181 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 18:

/* Line 1464 of yacc.c  */
#line 182 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 19:

/* Line 1464 of yacc.c  */
#line 183 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 20:

/* Line 1464 of yacc.c  */
#line 187 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 21:

/* Line 1464 of yacc.c  */
#line 188 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 22:

/* Line 1464 of yacc.c  */
#line 192 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 23:

/* Line 1464 of yacc.c  */
#line 193 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 24:

/* Line 1464 of yacc.c  */
#line 197 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 25:

/* Line 1464 of yacc.c  */
#line 198 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 26:

/* Line 1464 of yacc.c  */
#line 199 "parser.y"
    { (yyval.obj) = (yyvsp[(3) - (4)].obj); ;}
    break;

  case 27:

/* Line 1464 of yacc.c  */
#line 203 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 29:

/* Line 1464 of yacc.c  */
#line 208 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 30:

/* Line 1464 of yacc.c  */
#line 209 "parser.y"
    {
      PyObject* tmp = ctx->Call(kNewAliasOrConstant, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yyloc));
      (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), tmp);
    ;}
    break;

  case 31:

/* Line 1464 of yacc.c  */
#line 214 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 32:

/* Line 1464 of yacc.c  */
#line 215 "parser.y"
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yylsp[(2) - (2)]));
      (yyval.obj) = ExtendList((yyvsp[(1) - (2)].obj), tmp);
    ;}
    break;

  case 33:

/* Line 1464 of yacc.c  */
#line 220 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 34:

/* Line 1464 of yacc.c  */
#line 225 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 36:

/* Line 1464 of yacc.c  */
#line 233 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("[(NN)]", (yyvsp[(1) - (5)].obj), (yyvsp[(4) - (5)].obj));
    ;}
    break;

  case 37:

/* Line 1464 of yacc.c  */
#line 237 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 38:

/* Line 1464 of yacc.c  */
#line 256 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 40:

/* Line 1464 of yacc.c  */
#line 264 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("[(NN)]", (yyvsp[(1) - (5)].obj), (yyvsp[(4) - (5)].obj));
    ;}
    break;

  case 41:

/* Line 1464 of yacc.c  */
#line 268 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 42:

/* Line 1464 of yacc.c  */
#line 280 "parser.y"
    { (yyval.obj) = ctx->Call(kIfBegin, "(N)", (yyvsp[(2) - (2)].obj)); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 43:

/* Line 1464 of yacc.c  */
#line 284 "parser.y"
    { (yyval.obj) = ctx->Call(kIfElif, "(N)", (yyvsp[(2) - (2)].obj)); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 44:

/* Line 1464 of yacc.c  */
#line 288 "parser.y"
    { (yyval.obj) = ctx->Call(kIfElse, "()"); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 45:

/* Line 1464 of yacc.c  */
#line 292 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NO)sN)", (yyvsp[(1) - (3)].obj), Py_None, (yyvsp[(2) - (3)].str), (yyvsp[(3) - (3)].obj));
    ;}
    break;

  case 46:

/* Line 1464 of yacc.c  */
#line 295 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NO)sN)", (yyvsp[(1) - (3)].obj), Py_None, (yyvsp[(2) - (3)].str), (yyvsp[(3) - (3)].obj));
    ;}
    break;

  case 47:

/* Line 1464 of yacc.c  */
#line 298 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NN)sN)", (yyvsp[(1) - (6)].obj), (yyvsp[(3) - (6)].obj), (yyvsp[(5) - (6)].str), (yyvsp[(6) - (6)].obj));
    ;}
    break;

  case 48:

/* Line 1464 of yacc.c  */
#line 301 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NN)sN)", (yyvsp[(1) - (6)].obj), (yyvsp[(3) - (6)].obj), (yyvsp[(5) - (6)].str), (yyvsp[(6) - (6)].obj));
    ;}
    break;

  case 49:

/* Line 1464 of yacc.c  */
#line 304 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NsN)", (yyvsp[(1) - (3)].obj), "or", (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 50:

/* Line 1464 of yacc.c  */
#line 305 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 51:

/* Line 1464 of yacc.c  */
#line 310 "parser.y"
    { (yyval.obj) = Py_BuildValue("(N)", (yyvsp[(2) - (4)].obj)); ;}
    break;

  case 52:

/* Line 1464 of yacc.c  */
#line 311 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (5)].obj), (yyvsp[(4) - (5)].obj)); ;}
    break;

  case 53:

/* Line 1464 of yacc.c  */
#line 312 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("(NNN)", (yyvsp[(2) - (7)].obj), (yyvsp[(4) - (7)].obj), (yyvsp[(6) - (7)].obj));
    ;}
    break;

  case 54:

/* Line 1464 of yacc.c  */
#line 318 "parser.y"
    { (yyval.str) = "<"; ;}
    break;

  case 55:

/* Line 1464 of yacc.c  */
#line 319 "parser.y"
    { (yyval.str) = ">"; ;}
    break;

  case 56:

/* Line 1464 of yacc.c  */
#line 320 "parser.y"
    { (yyval.str) = "<="; ;}
    break;

  case 57:

/* Line 1464 of yacc.c  */
#line 321 "parser.y"
    { (yyval.str) = ">="; ;}
    break;

  case 58:

/* Line 1464 of yacc.c  */
#line 322 "parser.y"
    { (yyval.str) = "=="; ;}
    break;

  case 59:

/* Line 1464 of yacc.c  */
#line 323 "parser.y"
    { (yyval.str) = "!="; ;}
    break;

  case 60:

/* Line 1464 of yacc.c  */
#line 327 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 61:

/* Line 1464 of yacc.c  */
#line 331 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), ctx->Value(kAnything));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 62:

/* Line 1464 of yacc.c  */
#line 335 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (5)].obj), (yyvsp[(5) - (5)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 63:

/* Line 1464 of yacc.c  */
#line 339 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 64:

/* Line 1464 of yacc.c  */
#line 343 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (5)].obj), (yyvsp[(3) - (5)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 65:

/* Line 1464 of yacc.c  */
#line 350 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddImport, "(ON)", Py_None, (yyvsp[(2) - (2)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 66:

/* Line 1464 of yacc.c  */
#line 354 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddImport, "(NN)", (yyvsp[(2) - (4)].obj), (yyvsp[(4) - (4)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 67:

/* Line 1464 of yacc.c  */
#line 361 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 68:

/* Line 1464 of yacc.c  */
#line 362 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 70:

/* Line 1464 of yacc.c  */
#line 366 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 72:

/* Line 1464 of yacc.c  */
#line 371 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 73:

/* Line 1464 of yacc.c  */
#line 372 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 74:

/* Line 1464 of yacc.c  */
#line 376 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 75:

/* Line 1464 of yacc.c  */
#line 377 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 77:

/* Line 1464 of yacc.c  */
#line 382 "parser.y"
    { (yyval.obj) = PyString_FromString("NamedTuple"); ;}
    break;

  case 78:

/* Line 1464 of yacc.c  */
#line 383 "parser.y"
    { (yyval.obj) = PyString_FromString("TypeVar"); ;}
    break;

  case 79:

/* Line 1464 of yacc.c  */
#line 384 "parser.y"
    { (yyval.obj) = PyString_FromString("*"); ;}
    break;

  case 80:

/* Line 1464 of yacc.c  */
#line 385 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 81:

/* Line 1464 of yacc.c  */
#line 389 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 82:

/* Line 1464 of yacc.c  */
#line 393 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddTypeVar, "(NNN)", (yyvsp[(1) - (7)].obj), (yyvsp[(5) - (7)].obj), (yyvsp[(6) - (7)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 83:

/* Line 1464 of yacc.c  */
#line 400 "parser.y"
    { (yyval.obj) = Py_BuildValue("(OO)", Py_None, Py_None); ;}
    break;

  case 84:

/* Line 1464 of yacc.c  */
#line 401 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NO)", (yyvsp[(2) - (2)].obj), Py_None); ;}
    break;

  case 85:

/* Line 1464 of yacc.c  */
#line 402 "parser.y"
    { (yyval.obj) = Py_BuildValue("(ON)", Py_None, (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 86:

/* Line 1464 of yacc.c  */
#line 403 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (4)].obj), (yyvsp[(4) - (4)].obj)); ;}
    break;

  case 87:

/* Line 1464 of yacc.c  */
#line 407 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 88:

/* Line 1464 of yacc.c  */
#line 408 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 89:

/* Line 1464 of yacc.c  */
#line 412 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 90:

/* Line 1464 of yacc.c  */
#line 416 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewFunction, "(NNNNN)", (yyvsp[(1) - (8)].obj), (yyvsp[(3) - (8)].obj), (yyvsp[(5) - (8)].obj), (yyvsp[(7) - (8)].obj), (yyvsp[(8) - (8)].obj));
      // Decorators is nullable and messes up the location tracking by
      // using the previous symbol as the start location for this production,
      // which is very misleading.  It is better to ignore decorators and
      // pretend the production started with DEF.  Even when decorators are
      // present the error line will be close enough to be helpful.
      //
      // TODO(dbaum): Consider making this smarter and only ignoring decorators
      // when they are empty.  Making decorators non-nullable and having two
      // productions for funcdef would be a reasonable solution.
      (yyloc).first_line = (yylsp[(2) - (8)]).first_line;
      (yyloc).first_column = (yylsp[(2) - (8)]).first_column;
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 91:

/* Line 1464 of yacc.c  */
#line 431 "parser.y"
    {
      // TODO(dbaum): Is PYTHONCODE necessary?
      (yyval.obj) = ctx->Call(kNewExternalFunction, "(NN)", (yyvsp[(1) - (4)].obj), (yyvsp[(3) - (4)].obj));
      // See comment above about why @2 is used as the start.
      (yyloc).first_line = (yylsp[(2) - (4)]).first_line;
      (yyloc).first_column = (yylsp[(2) - (4)]).first_column;
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 92:

/* Line 1464 of yacc.c  */
#line 442 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 93:

/* Line 1464 of yacc.c  */
#line 443 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 94:

/* Line 1464 of yacc.c  */
#line 447 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 95:

/* Line 1464 of yacc.c  */
#line 452 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 96:

/* Line 1464 of yacc.c  */
#line 453 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 97:

/* Line 1464 of yacc.c  */
#line 457 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 98:

/* Line 1464 of yacc.c  */
#line 458 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 99:

/* Line 1464 of yacc.c  */
#line 462 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NNN)", (yyvsp[(1) - (3)].obj), (yyvsp[(2) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 100:

/* Line 1464 of yacc.c  */
#line 463 "parser.y"
    { (yyval.obj) = Py_BuildValue("(sOO)", "*", Py_None, Py_None); ;}
    break;

  case 101:

/* Line 1464 of yacc.c  */
#line 464 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NNO)", (yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj), Py_None); ;}
    break;

  case 102:

/* Line 1464 of yacc.c  */
#line 465 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis) ;}
    break;

  case 103:

/* Line 1464 of yacc.c  */
#line 469 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 104:

/* Line 1464 of yacc.c  */
#line 470 "parser.y"
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 105:

/* Line 1464 of yacc.c  */
#line 474 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 106:

/* Line 1464 of yacc.c  */
#line 475 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 107:

/* Line 1464 of yacc.c  */
#line 476 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis); ;}
    break;

  case 108:

/* Line 1464 of yacc.c  */
#line 477 "parser.y"
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 109:

/* Line 1464 of yacc.c  */
#line 481 "parser.y"
    { (yyval.obj) = PyString_FromFormat("*%s", PyString_AsString((yyvsp[(2) - (2)].obj))); ;}
    break;

  case 110:

/* Line 1464 of yacc.c  */
#line 482 "parser.y"
    { (yyval.obj) = PyString_FromFormat("**%s", PyString_AsString((yyvsp[(3) - (3)].obj))); ;}
    break;

  case 111:

/* Line 1464 of yacc.c  */
#line 486 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 112:

/* Line 1464 of yacc.c  */
#line 487 "parser.y"
    { (yyval.obj) = ctx->Value(kAnything); ;}
    break;

  case 113:

/* Line 1464 of yacc.c  */
#line 491 "parser.y"
    { Py_DecRef((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 114:

/* Line 1464 of yacc.c  */
#line 495 "parser.y"
    { (yyval.obj) = (yyvsp[(4) - (5)].obj); ;}
    break;

  case 115:

/* Line 1464 of yacc.c  */
#line 496 "parser.y"
    { (yyval.obj) = (yyvsp[(3) - (4)].obj); ;}
    break;

  case 116:

/* Line 1464 of yacc.c  */
#line 497 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 124:

/* Line 1464 of yacc.c  */
#line 511 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 125:

/* Line 1464 of yacc.c  */
#line 512 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 126:

/* Line 1464 of yacc.c  */
#line 516 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 127:

/* Line 1464 of yacc.c  */
#line 517 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 128:

/* Line 1464 of yacc.c  */
#line 518 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 129:

/* Line 1464 of yacc.c  */
#line 522 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 130:

/* Line 1464 of yacc.c  */
#line 523 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 131:

/* Line 1464 of yacc.c  */
#line 527 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 132:

/* Line 1464 of yacc.c  */
#line 528 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis); ;}
    break;

  case 133:

/* Line 1464 of yacc.c  */
#line 532 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewType, "(N)", (yyvsp[(1) - (1)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 134:

/* Line 1464 of yacc.c  */
#line 536 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewType, "(NN)", (yyvsp[(1) - (4)].obj), (yyvsp[(3) - (4)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 135:

/* Line 1464 of yacc.c  */
#line 540 "parser.y"
    {
      // This rule is needed for Callable[[...], ...]
      (yyval.obj) = ctx->Call(kNewType, "(sN)", "tuple", (yyvsp[(2) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 136:

/* Line 1464 of yacc.c  */
#line 545 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewNamedTuple, "(NN)", (yyvsp[(3) - (6)].obj), (yyvsp[(5) - (6)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 137:

/* Line 1464 of yacc.c  */
#line 549 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 138:

/* Line 1464 of yacc.c  */
#line 550 "parser.y"
    { (yyval.obj) = ctx->Call(kNewUnionType, "([NN])", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 139:

/* Line 1464 of yacc.c  */
#line 551 "parser.y"
    { (yyval.obj) = ctx->Value(kAnything); ;}
    break;

  case 140:

/* Line 1464 of yacc.c  */
#line 552 "parser.y"
    { (yyval.obj) = ctx->Value(kNothing); ;}
    break;

  case 141:

/* Line 1464 of yacc.c  */
#line 556 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 142:

/* Line 1464 of yacc.c  */
#line 557 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 143:

/* Line 1464 of yacc.c  */
#line 561 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 144:

/* Line 1464 of yacc.c  */
#line 562 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 145:

/* Line 1464 of yacc.c  */
#line 566 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(4) - (6)].obj)); ;}
    break;

  case 148:

/* Line 1464 of yacc.c  */
#line 575 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 149:

/* Line 1464 of yacc.c  */
#line 576 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 150:

/* Line 1464 of yacc.c  */
#line 580 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 151:

/* Line 1464 of yacc.c  */
#line 581 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 152:

/* Line 1464 of yacc.c  */
#line 586 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 153:

/* Line 1464 of yacc.c  */
#line 587 "parser.y"
    {
      PyString_Concat(&(yyvsp[(1) - (3)].obj), DOT_STRING);
      PyString_ConcatAndDel(&(yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      (yyval.obj) = (yyvsp[(1) - (3)].obj);
    ;}
    break;

  case 154:

/* Line 1464 of yacc.c  */
#line 595 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 155:

/* Line 1464 of yacc.c  */
#line 596 "parser.y"
    {
      PyObject* slice = PySlice_New((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj), NULL);
      CHECK(slice, (yyloc));
      (yyval.obj) = slice;
    ;}
    break;

  case 156:

/* Line 1464 of yacc.c  */
#line 601 "parser.y"
    {
      PyObject* slice = PySlice_New((yyvsp[(1) - (5)].obj), (yyvsp[(3) - (5)].obj), (yyvsp[(5) - (5)].obj));
      CHECK(slice, (yyloc));
      (yyval.obj) = slice;
    ;}
    break;

  case 157:

/* Line 1464 of yacc.c  */
#line 609 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 158:

/* Line 1464 of yacc.c  */
#line 610 "parser.y"
    { (yyval.obj) = NULL; ;}
    break;



/* Line 1464 of yacc.c  */
#line 3402 "pyi/parser.tab.cc"
      default: break;
    }
  YY_SYMBOL_PRINT ("-> $$ =", yyr1[yyn], &yyval, &yyloc);

  YYPOPSTACK (yylen);
  yylen = 0;
  YY_STACK_PRINT (yyss, yyssp);

  *++yyvsp = yyval;
  *++yylsp = yyloc;

  /* Now `shift' the result of the reduction.  Determine what state
     that goes to, based on the state we popped back to and the rule
     number reduced by.  */

  yyn = yyr1[yyn];

  yystate = yypgoto[yyn - YYNTOKENS] + *yyssp;
  if (0 <= yystate && yystate <= YYLAST && yycheck[yystate] == *yyssp)
    yystate = yytable[yystate];
  else
    yystate = yydefgoto[yyn - YYNTOKENS];

  goto yynewstate;


/*------------------------------------.
| yyerrlab -- here on detecting error |
`------------------------------------*/
yyerrlab:
  /* If not already recovering from an error, report this error.  */
  if (!yyerrstatus)
    {
      ++yynerrs;
#if ! YYERROR_VERBOSE
      yyerror (&yylloc, scanner, ctx, YY_("syntax error"));
#else
      {
	YYSIZE_T yysize = yysyntax_error (0, yystate, yychar);
	if (yymsg_alloc < yysize && yymsg_alloc < YYSTACK_ALLOC_MAXIMUM)
	  {
	    YYSIZE_T yyalloc = 2 * yysize;
	    if (! (yysize <= yyalloc && yyalloc <= YYSTACK_ALLOC_MAXIMUM))
	      yyalloc = YYSTACK_ALLOC_MAXIMUM;
	    if (yymsg != yymsgbuf)
	      YYSTACK_FREE (yymsg);
	    yymsg = (char *) YYSTACK_ALLOC (yyalloc);
	    if (yymsg)
	      yymsg_alloc = yyalloc;
	    else
	      {
		yymsg = yymsgbuf;
		yymsg_alloc = sizeof yymsgbuf;
	      }
	  }

	if (0 < yysize && yysize <= yymsg_alloc)
	  {
	    (void) yysyntax_error (yymsg, yystate, yychar);
	    yyerror (&yylloc, scanner, ctx, yymsg);
	  }
	else
	  {
	    yyerror (&yylloc, scanner, ctx, YY_("syntax error"));
	    if (yysize != 0)
	      goto yyexhaustedlab;
	  }
      }
#endif
    }

  yyerror_range[0] = yylloc;

  if (yyerrstatus == 3)
    {
      /* If just tried and failed to reuse lookahead token after an
	 error, discard it.  */

      if (yychar <= YYEOF)
	{
	  /* Return failure if at end of input.  */
	  if (yychar == YYEOF)
	    YYABORT;
	}
      else
	{
	  yydestruct ("Error: discarding",
		      yytoken, &yylval, &yylloc, scanner, ctx);
	  yychar = YYEMPTY;
	}
    }

  /* Else will try to reuse lookahead token after shifting the error
     token.  */
  goto yyerrlab1;


/*---------------------------------------------------.
| yyerrorlab -- error raised explicitly by YYERROR.  |
`---------------------------------------------------*/
yyerrorlab:

  /* Pacify compilers like GCC when the user code never invokes
     YYERROR and the label yyerrorlab therefore never appears in user
     code.  */
  if (/*CONSTCOND*/ 0)
     goto yyerrorlab;

  yyerror_range[0] = yylsp[1-yylen];
  /* Do not reclaim the symbols of the rule which action triggered
     this YYERROR.  */
  YYPOPSTACK (yylen);
  yylen = 0;
  YY_STACK_PRINT (yyss, yyssp);
  yystate = *yyssp;
  goto yyerrlab1;


/*-------------------------------------------------------------.
| yyerrlab1 -- common code for both syntax error and YYERROR.  |
`-------------------------------------------------------------*/
yyerrlab1:
  yyerrstatus = 3;	/* Each real token shifted decrements this.  */

  for (;;)
    {
      yyn = yypact[yystate];
      if (yyn != YYPACT_NINF)
	{
	  yyn += YYTERROR;
	  if (0 <= yyn && yyn <= YYLAST && yycheck[yyn] == YYTERROR)
	    {
	      yyn = yytable[yyn];
	      if (0 < yyn)
		break;
	    }
	}

      /* Pop the current state because it cannot handle the error token.  */
      if (yyssp == yyss)
	YYABORT;

      yyerror_range[0] = *yylsp;
      yydestruct ("Error: popping",
		  yystos[yystate], yyvsp, yylsp, scanner, ctx);
      YYPOPSTACK (1);
      yystate = *yyssp;
      YY_STACK_PRINT (yyss, yyssp);
    }

  *++yyvsp = yylval;

  yyerror_range[1] = yylloc;
  /* Using YYLLOC is tempting, but would change the location of
     the lookahead.  YYLOC is available though.  */
  YYLLOC_DEFAULT (yyloc, (yyerror_range - 1), 2);
  *++yylsp = yyloc;

  /* Shift the error token.  */
  YY_SYMBOL_PRINT ("Shifting", yystos[yyn], yyvsp, yylsp);

  yystate = yyn;
  goto yynewstate;


/*-------------------------------------.
| yyacceptlab -- YYACCEPT comes here.  |
`-------------------------------------*/
yyacceptlab:
  yyresult = 0;
  goto yyreturn;

/*-----------------------------------.
| yyabortlab -- YYABORT comes here.  |
`-----------------------------------*/
yyabortlab:
  yyresult = 1;
  goto yyreturn;

#if !defined(yyoverflow) || YYERROR_VERBOSE
/*-------------------------------------------------.
| yyexhaustedlab -- memory exhaustion comes here.  |
`-------------------------------------------------*/
yyexhaustedlab:
  yyerror (&yylloc, scanner, ctx, YY_("memory exhausted"));
  yyresult = 2;
  /* Fall through.  */
#endif

yyreturn:
  if (yychar != YYEMPTY)
     yydestruct ("Cleanup: discarding lookahead",
		 yytoken, &yylval, &yylloc, scanner, ctx);
  /* Do not reclaim the symbols of the rule which action triggered
     this YYABORT or YYACCEPT.  */
  YYPOPSTACK (yylen);
  YY_STACK_PRINT (yyss, yyssp);
  while (yyssp != yyss)
    {
      yydestruct ("Cleanup: popping",
		  yystos[*yyssp], yyvsp, yylsp, scanner, ctx);
      YYPOPSTACK (1);
    }
#ifndef yyoverflow
  if (yyss != yyssa)
    YYSTACK_FREE (yyss);
#endif
#if YYERROR_VERBOSE
  if (yymsg != yymsgbuf)
    YYSTACK_FREE (yymsg);
#endif
  /* Make sure YYID is used.  */
  return YYID (yyresult);
}



/* Line 1684 of yacc.c  */
#line 618 "parser.y"


namespace {

int pytypeerror(
    YYLTYPE* llocp, void* scanner, pytype::Context* ctx, const char *p) {
  ctx->SetErrorLocation(llocp);
  Lexer* lexer = pytypeget_extra(scanner);
  if (lexer->error_message_) {
    PyErr_SetObject(ctx->Value(kParseError), lexer->error_message_);
  } else {
    PyErr_SetString(ctx->Value(kParseError), p);
  }
  return 0;
}

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
}  // end namespace pytype

