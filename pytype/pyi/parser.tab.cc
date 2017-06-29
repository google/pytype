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
     AND = 267,
     PASS = 268,
     IMPORT = 269,
     FROM = 270,
     AS = 271,
     RAISE = 272,
     PYTHONCODE = 273,
     NOTHING = 274,
     NAMEDTUPLE = 275,
     TYPEVAR = 276,
     ARROW = 277,
     COLONEQUALS = 278,
     ELLIPSIS = 279,
     EQ = 280,
     NE = 281,
     LE = 282,
     GE = 283,
     INDENT = 284,
     DEDENT = 285,
     TRIPLEQUOTED = 286,
     TYPECOMMENT = 287,
     BYTESTRING = 288,
     UNICODESTRING = 289
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
#line 202 "pyi/parser.tab.cc"
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
#line 227 "pyi/parser.tab.cc"

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
#define YYLAST   392

/* YYNTOKENS -- Number of terminals.  */
#define YYNTOKENS  48
/* YYNNTS -- Number of nonterminals.  */
#define YYNNTS  63
/* YYNRULES -- Number of rules.  */
#define YYNRULES  164
/* YYNRULES -- Number of states.  */
#define YYNSTATES  297

/* YYTRANSLATE(YYLEX) -- Bison symbol number corresponding to YYLEX.  */
#define YYUNDEFTOK  2
#define YYMAXUTOK   289

#define YYTRANSLATE(YYX)						\
  ((unsigned int) (YYX) <= YYMAXUTOK ? yytranslate[YYX] : YYUNDEFTOK)

/* YYTRANSLATE[YYLEX] -- Bison symbol number corresponding to YYLEX.  */
static const yytype_uint8 yytranslate[] =
{
       0,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
      36,    37,    44,     2,    38,     2,    47,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,    35,     2,
      42,    39,    43,    46,    45,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,    40,     2,    41,     2,     2,     2,     2,     2,     2,
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
      25,    26,    27,    28,    29,    30,    31,    32,    33,    34
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
     172,   176,   180,   185,   191,   199,   201,   203,   205,   207,
     209,   211,   215,   219,   223,   227,   233,   237,   243,   246,
     251,   255,   257,   259,   263,   265,   269,   274,   278,   280,
     282,   284,   286,   288,   292,   296,   304,   305,   308,   311,
     316,   320,   322,   326,   335,   340,   343,   344,   347,   349,
     350,   354,   356,   360,   362,   365,   367,   370,   371,   374,
     377,   380,   381,   384,   388,   391,   392,   395,   401,   406,
     408,   411,   415,   419,   425,   430,   435,   436,   439,   441,
     445,   448,   453,   457,   459,   461,   463,   465,   470,   474,
     481,   485,   489,   493,   495,   497,   502,   505,   509,   511,
     518,   520,   521,   523,   524,   528,   530,   532,   536,   538,
     542,   548,   550,   551,   553
};

/* YYRHS -- A `-1'-separated list of the rules' RHS.  */
static const yytype_int8 yyrhs[] =
{
      49,     0,    -1,    50,     0,    -1,    31,    50,     0,    -1,
      51,    -1,    51,    71,    -1,    51,    83,    -1,    51,    72,
      -1,    51,    78,    -1,    51,    53,    -1,    51,    79,    -1,
      51,    61,    -1,    -1,    93,    -1,    -1,     6,    54,    55,
      35,    52,    58,    -1,     3,    -1,    36,    56,    37,    -1,
      36,    37,    -1,    -1,    56,    38,    57,    -1,    57,    -1,
     100,    -1,     3,    39,   100,    -1,   110,    -1,    29,    59,
      30,    -1,    29,    31,    59,    30,    -1,   110,    -1,    60,
      -1,    60,    71,    -1,    60,    78,    -1,    60,    83,    -1,
      60,    63,    -1,    -1,    62,    67,    35,    29,    51,    30,
      -1,    62,    -1,    65,    35,    29,    51,    30,    -1,    62,
      66,    35,    29,    51,    30,    -1,    64,    67,    35,    29,
      60,    30,    -1,    64,    -1,    65,    35,    29,    60,    30,
      -1,    64,    66,    35,    29,    60,    30,    -1,    10,    68,
      -1,     9,    68,    -1,     8,    -1,   107,    70,     3,    -1,
     107,    70,    69,    -1,   107,    40,   108,    41,    70,     4,
      -1,   107,    40,   108,    41,    70,    69,    -1,    68,    12,
      68,    -1,    68,    11,    68,    -1,    36,    68,    37,    -1,
      36,     4,    38,    37,    -1,    36,     4,    38,     4,    37,
      -1,    36,     4,    38,     4,    38,     4,    37,    -1,    42,
      -1,    43,    -1,    27,    -1,    28,    -1,    25,    -1,    26,
      -1,     3,    39,     4,    -1,     3,    39,    33,    -1,     3,
      39,    34,    -1,     3,    39,    24,    -1,     3,    39,    24,
      32,   100,    -1,     3,    35,   100,    -1,     3,    35,   100,
      39,    24,    -1,    14,    73,    -1,    15,   107,    14,    75,
      -1,    73,    38,    74,    -1,    74,    -1,   107,    -1,   107,
      16,     3,    -1,    76,    -1,    36,    76,    37,    -1,    36,
      76,    38,    37,    -1,    76,    38,    77,    -1,    77,    -1,
       3,    -1,    20,    -1,    21,    -1,    44,    -1,     3,    16,
       3,    -1,     3,    39,   100,    -1,     3,    39,    21,    36,
       3,    80,    37,    -1,    -1,    38,   106,    -1,    38,    81,
      -1,    38,   106,    38,    81,    -1,    81,    38,    82,    -1,
      82,    -1,     3,    39,   100,    -1,    84,     7,     3,    36,
      86,    37,    92,    94,    -1,    84,     7,     3,    18,    -1,
      84,    85,    -1,    -1,    45,   107,    -1,    87,    -1,    -1,
      87,    38,    88,    -1,    88,    -1,     3,    89,    90,    -1,
      44,    -1,    91,    89,    -1,    24,    -1,    35,   100,    -1,
      -1,    39,     3,    -1,    39,     4,    -1,    39,    24,    -1,
      -1,    44,     3,    -1,    44,    44,     3,    -1,    22,   100,
      -1,    -1,    32,     3,    -1,    35,    93,    29,    96,    30,
      -1,    35,    29,    96,    30,    -1,    95,    -1,    35,   110,
      -1,    35,   110,    93,    -1,    35,    93,   110,    -1,    35,
      93,    29,   110,    30,    -1,    35,    29,   110,    30,    -1,
      35,    29,    31,    30,    -1,    -1,    96,    97,    -1,    97,
      -1,     3,    23,   100,    -1,    17,   100,    -1,    17,   100,
      36,    37,    -1,    98,    38,    99,    -1,    99,    -1,   100,
      -1,    24,    -1,   107,    -1,   107,    40,    98,    41,    -1,
      40,   105,    41,    -1,    20,    36,     3,    38,   101,    37,
      -1,    36,   100,    37,    -1,   100,    12,   100,    -1,   100,
      11,   100,    -1,    46,    -1,    19,    -1,    40,   102,   104,
      41,    -1,    40,    41,    -1,   102,    38,   103,    -1,   103,
      -1,    36,     3,    38,   100,   104,    37,    -1,    38,    -1,
      -1,   106,    -1,    -1,   106,    38,   100,    -1,   100,    -1,
       3,    -1,   107,    47,     3,    -1,     4,    -1,   109,    35,
     109,    -1,   109,    35,   109,    35,   109,    -1,     4,    -1,
      -1,    13,    -1,    24,    -1
};

/* YYRLINE[YYN] -- source line where rule number YYN was defined.  */
static const yytype_uint16 yyrline[] =
{
       0,   131,   131,   132,   136,   140,   141,   142,   143,   149,
     150,   151,   156,   160,   161,   164,   171,   182,   183,   184,
     188,   189,   193,   194,   198,   199,   200,   204,   205,   209,
     210,   215,   216,   221,   226,   229,   234,   238,   257,   260,
     265,   269,   281,   285,   289,   293,   296,   299,   302,   305,
     306,   307,   312,   313,   314,   320,   321,   322,   323,   324,
     325,   329,   333,   337,   341,   345,   349,   353,   360,   364,
     371,   372,   375,   376,   380,   381,   382,   386,   387,   391,
     392,   393,   394,   395,   399,   403,   410,   411,   412,   413,
     417,   418,   422,   426,   441,   452,   453,   457,   462,   463,
     467,   468,   472,   473,   474,   475,   479,   480,   484,   485,
     486,   487,   491,   492,   496,   497,   501,   505,   506,   507,
     511,   512,   513,   514,   515,   516,   517,   521,   522,   526,
     527,   528,   532,   533,   537,   538,   542,   546,   550,   555,
     559,   560,   561,   562,   563,   567,   568,   572,   573,   577,
     581,   582,   586,   587,   591,   592,   597,   598,   606,   607,
     612,   620,   621,   625,   626
};
#endif

#if YYDEBUG || YYERROR_VERBOSE || YYTOKEN_TABLE
/* YYTNAME[SYMBOL-NUM] -- String name of the symbol SYMBOL-NUM.
   First, the terminals, then, starting at YYNTOKENS, nonterminals.  */
static const char *const yytname[] =
{
  "\"end of file\"", "error", "$undefined", "NAME", "NUMBER", "LEXERROR",
  "CLASS", "DEF", "ELSE", "ELIF", "IF", "OR", "AND", "PASS", "IMPORT",
  "FROM", "AS", "RAISE", "PYTHONCODE", "NOTHING", "NAMEDTUPLE", "TYPEVAR",
  "ARROW", "COLONEQUALS", "ELLIPSIS", "EQ", "NE", "LE", "GE", "INDENT",
  "DEDENT", "TRIPLEQUOTED", "TYPECOMMENT", "BYTESTRING", "UNICODESTRING",
  "':'", "'('", "')'", "','", "'='", "'['", "']'", "'<'", "'>'", "'*'",
  "'@'", "'?'", "'.'", "$accept", "start", "unit", "alldefs",
  "maybe_type_ignore", "classdef", "class_name", "parents", "parent_list",
  "parent", "maybe_class_funcs", "class_funcs", "funcdefs", "if_stmt",
  "if_and_elifs", "class_if_stmt", "class_if_and_elifs", "if_cond",
  "elif_cond", "else_cond", "condition", "version_tuple", "condition_op",
  "constantdef", "importdef", "import_items", "import_item", "from_list",
  "from_items", "from_item", "alias_or_constant", "typevardef",
  "typevar_args", "typevar_kwargs", "typevar_kwarg", "funcdef",
  "decorators", "decorator", "params", "param_list", "param", "param_type",
  "param_default", "param_star_name", "return", "typeignore", "maybe_body",
  "empty_body", "body", "body_stmt", "type_parameters", "type_parameter",
  "type", "named_tuple_fields", "named_tuple_field_list",
  "named_tuple_field", "maybe_comma", "maybe_type_list", "type_list",
  "dotted_name", "getitem_key", "maybe_number", "pass_or_ellipsis", 0
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
     285,   286,   287,   288,   289,    58,    40,    41,    44,    61,
      91,    93,    60,    62,    42,    64,    63,    46
};
# endif

/* YYR1[YYN] -- Symbol number of symbol that rule YYN derives.  */
static const yytype_uint8 yyr1[] =
{
       0,    48,    49,    49,    50,    51,    51,    51,    51,    51,
      51,    51,    51,    52,    52,    53,    54,    55,    55,    55,
      56,    56,    57,    57,    58,    58,    58,    59,    59,    60,
      60,    60,    60,    60,    61,    61,    62,    62,    63,    63,
      64,    64,    65,    66,    67,    68,    68,    68,    68,    68,
      68,    68,    69,    69,    69,    70,    70,    70,    70,    70,
      70,    71,    71,    71,    71,    71,    71,    71,    72,    72,
      73,    73,    74,    74,    75,    75,    75,    76,    76,    77,
      77,    77,    77,    77,    78,    79,    80,    80,    80,    80,
      81,    81,    82,    83,    83,    84,    84,    85,    86,    86,
      87,    87,    88,    88,    88,    88,    89,    89,    90,    90,
      90,    90,    91,    91,    92,    92,    93,    94,    94,    94,
      95,    95,    95,    95,    95,    95,    95,    96,    96,    97,
      97,    97,    98,    98,    99,    99,   100,   100,   100,   100,
     100,   100,   100,   100,   100,   101,   101,   102,   102,   103,
     104,   104,   105,   105,   106,   106,   107,   107,   108,   108,
     108,   109,   109,   110,   110
};

/* YYR2[YYN] -- Number of symbols composing right hand side of rule YYN.  */
static const yytype_uint8 yyr2[] =
{
       0,     2,     2,     3,     1,     2,     2,     2,     2,     2,
       2,     2,     0,     1,     0,     6,     1,     3,     2,     0,
       3,     1,     1,     3,     1,     3,     4,     1,     1,     2,
       2,     2,     2,     0,     6,     1,     5,     6,     6,     1,
       5,     6,     2,     2,     1,     3,     3,     6,     6,     3,
       3,     3,     4,     5,     7,     1,     1,     1,     1,     1,
       1,     3,     3,     3,     3,     5,     3,     5,     2,     4,
       3,     1,     1,     3,     1,     3,     4,     3,     1,     1,
       1,     1,     1,     3,     3,     7,     0,     2,     2,     4,
       3,     1,     3,     8,     4,     2,     0,     2,     1,     0,
       3,     1,     3,     1,     2,     1,     2,     0,     2,     2,
       2,     0,     2,     3,     2,     0,     2,     5,     4,     1,
       2,     3,     3,     5,     4,     4,     0,     2,     1,     3,
       2,     4,     3,     1,     1,     1,     1,     4,     3,     6,
       3,     3,     3,     1,     1,     4,     2,     3,     1,     6,
       1,     0,     1,     0,     3,     1,     1,     3,     1,     3,
       5,     1,     0,     1,     1
};

/* YYDEFACT[STATE-NAME] -- Default rule to reduce with in state
   STATE-NUM when YYTABLE doesn't specify something else to do.  Zero
   means the default is an error.  */
static const yytype_uint8 yydefact[] =
{
      12,    12,     0,     0,    96,     0,     1,     2,     0,     0,
       0,     0,     0,     9,    11,    35,     0,     5,     7,     8,
      10,     6,     0,     3,     0,     0,    16,    19,   156,     0,
      42,     0,    68,    71,    72,     0,    44,     0,     0,     0,
       0,     0,     0,    95,   144,     0,     0,   153,   143,    66,
     136,    61,     0,    64,    62,    63,    84,     0,     0,     0,
       0,     0,    59,    60,    57,    58,   162,    55,    56,     0,
       0,     0,     0,     0,    43,     0,     0,    12,     0,    97,
       0,     0,   155,     0,   152,     0,     0,     0,     0,     0,
       0,   156,    18,     0,    21,    22,    14,    51,    50,    49,
     158,     0,     0,   157,    45,     0,    46,    70,    73,    79,
      80,    81,     0,    82,    69,    74,    78,    12,    12,    96,
      94,    99,     0,   140,   138,     0,   142,   141,    67,   135,
       0,   133,   134,    86,    65,     0,    17,     0,     0,     0,
      13,     0,   162,     0,     0,     0,     0,    96,    96,    36,
     107,   105,   103,     0,    98,   101,   107,     0,   154,     0,
     137,     0,     0,    23,    20,   116,   163,   164,    33,    15,
      24,     0,   161,   159,     0,    83,    75,     0,    77,    37,
      34,     0,   111,   112,     0,   115,     0,   104,     0,     0,
     132,   156,    88,    91,    87,    85,    33,     0,    96,    27,
      47,    48,   162,     0,    52,    76,   106,     0,   102,   113,
       0,   126,   100,     0,   146,   151,   148,   139,     0,     0,
       0,     0,    25,     0,    32,    39,     0,    29,    30,    31,
     160,    53,     0,   108,   109,   110,   114,     0,    93,   119,
       0,   150,     0,    92,     0,    90,    89,    26,     0,     0,
       0,     0,     0,     0,     0,   120,     0,   147,   145,     0,
       0,    33,    54,     0,     0,     0,     0,   128,     0,     0,
     122,   121,   151,    33,    33,    96,     0,   130,   125,   118,
     127,   124,     0,     0,   150,     0,    96,    96,    40,   129,
       0,   117,   123,   149,    41,    38,   131
};

/* YYDEFGOTO[NTERM-NUM].  */
static const yytype_int16 yydefgoto[] =
{
      -1,     2,     3,     4,   139,    13,    27,    58,    93,    94,
     169,   197,   198,    14,    15,   224,   225,    16,    38,    39,
      30,   106,    70,    17,    18,    32,    33,   114,   115,   116,
      19,    20,   162,   192,   193,    21,    22,    43,   153,   154,
     155,   182,   208,   156,   211,   140,   238,   239,   266,   267,
     130,   131,    56,   189,   215,   216,   242,    83,    84,    50,
     101,   102,   199
};

/* YYPACT[STATE-NUM] -- Index in YYTABLE of the portion describing
   STATE-NUM.  */
#define YYPACT_NINF -212
static const yytype_int16 yypact[] =
{
     -11,  -212,   119,   146,   273,   170,  -212,  -212,    99,    29,
      13,    83,    83,  -212,  -212,   220,   212,  -212,  -212,  -212,
    -212,  -212,    20,  -212,   109,    10,  -212,   173,  -212,    13,
     257,   199,   184,  -212,    26,     7,  -212,    13,   227,   236,
     249,   235,    83,  -212,  -212,   250,   109,   109,  -212,   142,
      74,  -212,   255,   260,  -212,  -212,   269,    32,   258,   171,
      13,    13,  -212,  -212,  -212,  -212,   278,  -212,  -212,   291,
      44,    83,   292,     4,   257,   267,   268,  -212,    66,   251,
     296,   200,   269,   259,   263,   109,   109,   279,    86,   299,
     109,   265,  -212,   193,  -212,   269,   274,  -212,   293,  -212,
     272,   270,   275,  -212,  -212,   304,  -212,  -212,  -212,   297,
    -212,  -212,    54,  -212,  -212,   271,  -212,  -212,  -212,   185,
    -212,    14,   276,  -212,  -212,   109,   300,  -212,  -212,  -212,
     123,  -212,   269,   277,   269,   109,  -212,   120,   313,   246,
    -212,   223,   314,   281,   317,   247,    54,   187,   204,  -212,
     282,  -212,     9,   284,   285,  -212,   282,   286,   269,    86,
    -212,   122,   287,   269,  -212,  -212,  -212,  -212,   243,  -212,
    -212,     1,  -212,   290,    63,  -212,  -212,   130,  -212,  -212,
    -212,   109,   283,  -212,   324,   306,    14,  -212,    41,   294,
    -212,   295,   298,  -212,   301,  -212,     2,   302,   133,  -212,
    -212,  -212,   314,   252,  -212,  -212,   269,    15,  -212,  -212,
     109,   303,  -212,   326,  -212,   305,  -212,  -212,   109,   327,
     122,   307,  -212,   219,  -212,   220,   309,  -212,  -212,  -212,
    -212,  -212,   329,  -212,  -212,  -212,   269,   231,  -212,  -212,
     308,   311,   310,   269,   295,  -212,   298,  -212,    84,   315,
     318,   312,   319,   156,   248,   274,   109,  -212,  -212,   316,
     320,  -212,  -212,   325,   109,   322,   162,  -212,   328,   240,
    -212,  -212,   160,  -212,  -212,   174,   109,   209,  -212,  -212,
    -212,  -212,   186,   330,  -212,   331,   175,   203,  -212,   269,
     332,  -212,  -212,  -212,  -212,  -212,  -212
};

/* YYPGOTO[NTERM-NUM].  */
static const yytype_int16 yypgoto[] =
{
    -212,  -212,   334,    30,  -212,  -212,  -212,  -212,  -212,   205,
    -212,   144,   -38,  -212,  -212,  -212,  -212,  -196,   129,   132,
     115,   188,   214,  -194,  -212,  -212,   321,  -212,   253,  -101,
    -192,  -212,  -212,   141,   143,  -190,  -212,  -212,  -212,  -212,
     177,   208,  -212,  -212,  -212,  -128,  -212,  -212,    97,  -211,
    -212,   211,   -24,  -212,  -212,   126,   100,  -212,   210,    -1,
    -212,  -139,  -138
};

/* YYTABLE[YYPACT[STATE-NUM]].  What to do in state STATE-NUM.  If
   positive, shift that token.  If negative, reduce the rule which
   number is the opposite.  If zero, do what YYDEFACT says.
   If YYTABLE_NINF, syntax error.  */
#define YYTABLE_NINF -162
static const yytype_int16 yytable[] =
{
      49,   170,   226,   173,   227,   200,   228,   109,   229,    31,
      34,    35,   183,    28,    51,   166,    28,   150,   233,   234,
       1,    73,    81,    82,   110,   111,   167,    41,    31,    44,
      45,    52,    26,    95,    53,    91,    31,   105,   151,   235,
     112,    79,    72,    54,    55,   178,    46,   104,   113,    29,
      47,    44,    45,   184,    69,   280,    48,   109,   152,    31,
      31,   126,   127,   230,   132,    42,   134,   203,    46,    92,
      34,   280,    47,    69,   110,   111,   178,   213,    48,   226,
     105,   227,   214,   228,   120,   229,    28,    28,    51,    28,
     226,   226,   227,   227,   228,   228,   229,   229,   113,   255,
     204,   158,   121,    44,    45,    44,    45,   119,    53,   254,
     129,   163,    28,    95,    88,   268,   270,    54,    55,     6,
      46,    69,    46,    91,    47,   191,    47,   271,    44,    45,
      48,   283,    48,   109,    24,   132,   223,    82,    25,    44,
      45,    44,    45,    10,    59,    46,     7,   147,   148,    47,
     110,   111,    74,    85,    86,    48,    46,   206,    46,   263,
      47,   159,    47,   -28,   160,   263,    48,   205,    48,   166,
      23,    85,    86,   264,   113,    98,    99,   223,   223,   264,
     167,    87,    60,    61,    10,    10,   236,   265,     8,   263,
       8,     9,   279,     9,   243,    10,   158,    10,   284,    11,
      12,    11,    12,   264,   288,   294,   223,     8,    97,    57,
       9,    85,    86,    10,    10,   149,   291,   179,    11,    12,
      85,    86,    71,   275,    62,    63,    64,    65,    36,    37,
     136,   137,   272,   295,   180,   286,   287,   123,    78,    66,
     277,    67,    68,   263,   166,   290,    69,    40,    62,    63,
      64,    65,   289,   166,    24,   167,   166,   264,   248,   166,
     253,   166,    75,   138,   167,    67,    68,   167,    60,    61,
     167,    76,   167,    -4,   196,   168,     8,   269,    77,     9,
      85,    86,   100,    10,   176,   177,    80,    11,    12,   231,
     232,    89,    90,    96,   103,   108,   117,   118,    69,   122,
     124,   125,   133,   128,   135,    61,   138,  -161,   143,   146,
     142,   141,    86,   144,   157,   161,   165,   181,   172,   174,
     175,   185,   207,   186,   195,   202,   188,   209,   210,   240,
     244,   217,   222,   252,   218,     5,   219,   247,   237,   220,
     221,   261,   164,   241,   251,   273,   256,   213,   276,   274,
     259,   258,   278,   260,   249,   171,   262,   250,   281,   201,
     292,   246,   245,   212,   187,   145,   282,   257,   293,   296,
     190,   194,   285,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,   107
};

static const yytype_int16 yycheck[] =
{
      24,   139,   198,   142,   198,     4,   198,     3,   198,    10,
      11,    12,     3,     3,     4,    13,     3,     3,     3,     4,
      31,    14,    46,    47,    20,    21,    24,     7,    29,    19,
      20,    21,     3,    57,    24,     3,    37,    36,    24,    24,
      36,    42,    16,    33,    34,   146,    36,     3,    44,    36,
      40,    19,    20,    44,    47,   266,    46,     3,    44,    60,
      61,    85,    86,   202,    88,    45,    90,     4,    36,    37,
      71,   282,    40,    47,    20,    21,   177,    36,    46,   275,
      36,   275,    41,   275,    18,   275,     3,     3,     4,     3,
     286,   287,   286,   287,   286,   287,   286,   287,    44,   237,
      37,   125,    36,    19,    20,    19,    20,    77,    24,   237,
      24,   135,     3,   137,    40,   253,   254,    33,    34,     0,
      36,    47,    36,     3,    40,     3,    40,   255,    19,    20,
      46,   269,    46,     3,    35,   159,     3,   161,    39,    19,
      20,    19,    20,    10,    29,    36,     0,   117,   118,    40,
      20,    21,    37,    11,    12,    46,    36,   181,    36,     3,
      40,    38,    40,    30,    41,     3,    46,    37,    46,    13,
       0,    11,    12,    17,    44,    60,    61,     3,     3,    17,
      24,    39,    11,    12,    10,    10,   210,    31,     3,     3,
       3,     6,    30,     6,   218,    10,   220,    10,    38,    14,
      15,    14,    15,    17,    30,    30,     3,     3,    37,    36,
       6,    11,    12,    10,    10,    30,    30,    30,    14,    15,
      11,    12,    38,   261,    25,    26,    27,    28,     8,     9,
      37,    38,   256,    30,    30,   273,   274,    37,     3,    40,
     264,    42,    43,     3,    13,    36,    47,    35,    25,    26,
      27,    28,   276,    13,    35,    24,    13,    17,    39,    13,
      29,    13,    35,    32,    24,    42,    43,    24,    11,    12,
      24,    35,    24,     0,    31,    29,     3,    29,    29,     6,
      11,    12,     4,    10,    37,    38,    36,    14,    15,    37,
      38,    36,    32,    35,     3,     3,    29,    29,    47,     3,
      41,    38,     3,    24,    39,    12,    32,    35,     4,    38,
      35,    41,    12,    16,    38,    38,     3,    35,     4,    38,
       3,    37,    39,    38,    37,    35,    40,     3,    22,     3,
       3,    37,    30,     4,    39,     1,    38,    30,    35,    38,
     196,    29,   137,    38,    35,    29,    38,    36,    23,    29,
      35,    41,    30,    35,   225,   141,    37,   225,    30,   171,
      30,   220,   219,   186,   156,   112,   269,   241,    37,    37,
     159,   161,   272,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    71
};

/* YYSTOS[STATE-NUM] -- The (internal number of the) accessing
   symbol of state STATE-NUM.  */
static const yytype_uint8 yystos[] =
{
       0,    31,    49,    50,    51,    50,     0,     0,     3,     6,
      10,    14,    15,    53,    61,    62,    65,    71,    72,    78,
      79,    83,    84,     0,    35,    39,     3,    54,     3,    36,
      68,   107,    73,    74,   107,   107,     8,     9,    66,    67,
      35,     7,    45,    85,    19,    20,    36,    40,    46,   100,
     107,     4,    21,    24,    33,    34,   100,    36,    55,    68,
      11,    12,    25,    26,    27,    28,    40,    42,    43,    47,
      70,    38,    16,    14,    68,    35,    35,    29,     3,   107,
      36,   100,   100,   105,   106,    11,    12,    39,    40,    36,
      32,     3,    37,    56,    57,   100,    35,    37,    68,    68,
       4,   108,   109,     3,     3,    36,    69,    74,     3,     3,
      20,    21,    36,    44,    75,    76,    77,    29,    29,    51,
      18,    36,     3,    37,    41,    38,   100,   100,    24,    24,
      98,    99,   100,     3,   100,    39,    37,    38,    32,    52,
      93,    41,    35,     4,    16,    76,    38,    51,    51,    30,
       3,    24,    44,    86,    87,    88,    91,    38,   100,    38,
      41,    38,    80,   100,    57,     3,    13,    24,    29,    58,
     110,    70,     4,   109,    38,     3,    37,    38,    77,    30,
      30,    35,    89,     3,    44,    37,    38,    89,    40,   101,
      99,     3,    81,    82,   106,    37,    31,    59,    60,   110,
       4,    69,    35,     4,    37,    37,   100,    39,    90,     3,
      22,    92,    88,    36,    41,   102,   103,    37,    39,    38,
      38,    59,    30,     3,    63,    64,    65,    71,    78,    83,
     109,    37,    38,     3,     4,    24,   100,    35,    94,    95,
       3,    38,   104,   100,     3,    82,    81,    30,    39,    66,
      67,    35,     4,    29,    93,   110,    38,   103,    41,    35,
      35,    29,    37,     3,    17,    31,    96,    97,   110,    29,
     110,    93,   100,    29,    29,    60,    23,   100,    30,    30,
      97,    30,    96,   110,    38,   104,    60,    60,    30,   100,
      36,    30,    30,    37,    30,    30,    37
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
#line 1460 "pyi/parser.tab.cc"
	break;
      case 4: /* "NUMBER" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1469 "pyi/parser.tab.cc"
	break;
      case 5: /* "LEXERROR" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1478 "pyi/parser.tab.cc"
	break;
      case 49: /* "start" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1487 "pyi/parser.tab.cc"
	break;
      case 50: /* "unit" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1496 "pyi/parser.tab.cc"
	break;
      case 51: /* "alldefs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1505 "pyi/parser.tab.cc"
	break;
      case 53: /* "classdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1514 "pyi/parser.tab.cc"
	break;
      case 54: /* "class_name" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1523 "pyi/parser.tab.cc"
	break;
      case 55: /* "parents" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1532 "pyi/parser.tab.cc"
	break;
      case 56: /* "parent_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1541 "pyi/parser.tab.cc"
	break;
      case 57: /* "parent" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1550 "pyi/parser.tab.cc"
	break;
      case 58: /* "maybe_class_funcs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1559 "pyi/parser.tab.cc"
	break;
      case 59: /* "class_funcs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1568 "pyi/parser.tab.cc"
	break;
      case 60: /* "funcdefs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1577 "pyi/parser.tab.cc"
	break;
      case 61: /* "if_stmt" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1586 "pyi/parser.tab.cc"
	break;
      case 62: /* "if_and_elifs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1595 "pyi/parser.tab.cc"
	break;
      case 63: /* "class_if_stmt" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1604 "pyi/parser.tab.cc"
	break;
      case 64: /* "class_if_and_elifs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1613 "pyi/parser.tab.cc"
	break;
      case 65: /* "if_cond" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1622 "pyi/parser.tab.cc"
	break;
      case 66: /* "elif_cond" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1631 "pyi/parser.tab.cc"
	break;
      case 67: /* "else_cond" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1640 "pyi/parser.tab.cc"
	break;
      case 68: /* "condition" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1649 "pyi/parser.tab.cc"
	break;
      case 69: /* "version_tuple" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1658 "pyi/parser.tab.cc"
	break;
      case 70: /* "condition_op" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->str)); };

/* Line 1009 of yacc.c  */
#line 1667 "pyi/parser.tab.cc"
	break;
      case 71: /* "constantdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1676 "pyi/parser.tab.cc"
	break;
      case 72: /* "importdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1685 "pyi/parser.tab.cc"
	break;
      case 73: /* "import_items" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1694 "pyi/parser.tab.cc"
	break;
      case 74: /* "import_item" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1703 "pyi/parser.tab.cc"
	break;
      case 75: /* "from_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1712 "pyi/parser.tab.cc"
	break;
      case 76: /* "from_items" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1721 "pyi/parser.tab.cc"
	break;
      case 77: /* "from_item" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1730 "pyi/parser.tab.cc"
	break;
      case 78: /* "alias_or_constant" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1739 "pyi/parser.tab.cc"
	break;
      case 79: /* "typevardef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1748 "pyi/parser.tab.cc"
	break;
      case 80: /* "typevar_args" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1757 "pyi/parser.tab.cc"
	break;
      case 81: /* "typevar_kwargs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1766 "pyi/parser.tab.cc"
	break;
      case 82: /* "typevar_kwarg" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1775 "pyi/parser.tab.cc"
	break;
      case 83: /* "funcdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1784 "pyi/parser.tab.cc"
	break;
      case 84: /* "decorators" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1793 "pyi/parser.tab.cc"
	break;
      case 85: /* "decorator" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1802 "pyi/parser.tab.cc"
	break;
      case 86: /* "params" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1811 "pyi/parser.tab.cc"
	break;
      case 87: /* "param_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1820 "pyi/parser.tab.cc"
	break;
      case 88: /* "param" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1829 "pyi/parser.tab.cc"
	break;
      case 89: /* "param_type" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1838 "pyi/parser.tab.cc"
	break;
      case 90: /* "param_default" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1847 "pyi/parser.tab.cc"
	break;
      case 91: /* "param_star_name" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1856 "pyi/parser.tab.cc"
	break;
      case 92: /* "return" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1865 "pyi/parser.tab.cc"
	break;
      case 94: /* "maybe_body" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1874 "pyi/parser.tab.cc"
	break;
      case 96: /* "body" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1883 "pyi/parser.tab.cc"
	break;
      case 97: /* "body_stmt" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1892 "pyi/parser.tab.cc"
	break;
      case 98: /* "type_parameters" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1901 "pyi/parser.tab.cc"
	break;
      case 99: /* "type_parameter" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1910 "pyi/parser.tab.cc"
	break;
      case 100: /* "type" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1919 "pyi/parser.tab.cc"
	break;
      case 101: /* "named_tuple_fields" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1928 "pyi/parser.tab.cc"
	break;
      case 102: /* "named_tuple_field_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1937 "pyi/parser.tab.cc"
	break;
      case 103: /* "named_tuple_field" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1946 "pyi/parser.tab.cc"
	break;
      case 105: /* "maybe_type_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1955 "pyi/parser.tab.cc"
	break;
      case 106: /* "type_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1964 "pyi/parser.tab.cc"
	break;
      case 107: /* "dotted_name" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1973 "pyi/parser.tab.cc"
	break;
      case 108: /* "getitem_key" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1982 "pyi/parser.tab.cc"
	break;
      case 109: /* "maybe_number" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1991 "pyi/parser.tab.cc"
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
#line 131 "parser.y"
    { ctx->SetAndDelResult((yyvsp[(1) - (2)].obj)); (yyval.obj) = NULL; ;}
    break;

  case 3:

/* Line 1464 of yacc.c  */
#line 132 "parser.y"
    { ctx->SetAndDelResult((yyvsp[(2) - (3)].obj)); (yyval.obj) = NULL; ;}
    break;

  case 5:

/* Line 1464 of yacc.c  */
#line 140 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 6:

/* Line 1464 of yacc.c  */
#line 141 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 7:

/* Line 1464 of yacc.c  */
#line 142 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 8:

/* Line 1464 of yacc.c  */
#line 143 "parser.y"
    {
      (yyval.obj) = (yyvsp[(1) - (2)].obj);
      PyObject* tmp = ctx->Call(kAddAliasOrConstant, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yyloc));
      Py_DECREF(tmp);
    ;}
    break;

  case 9:

/* Line 1464 of yacc.c  */
#line 149 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 10:

/* Line 1464 of yacc.c  */
#line 150 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 11:

/* Line 1464 of yacc.c  */
#line 151 "parser.y"
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yylsp[(2) - (2)]));
      (yyval.obj) = ExtendList((yyvsp[(1) - (2)].obj), tmp);
    ;}
    break;

  case 12:

/* Line 1464 of yacc.c  */
#line 156 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 15:

/* Line 1464 of yacc.c  */
#line 164 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddClass, "(NNN)", (yyvsp[(2) - (6)].obj), (yyvsp[(3) - (6)].obj), (yyvsp[(6) - (6)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 16:

/* Line 1464 of yacc.c  */
#line 171 "parser.y"
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
#line 182 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 18:

/* Line 1464 of yacc.c  */
#line 183 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 19:

/* Line 1464 of yacc.c  */
#line 184 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 20:

/* Line 1464 of yacc.c  */
#line 188 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 21:

/* Line 1464 of yacc.c  */
#line 189 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 22:

/* Line 1464 of yacc.c  */
#line 193 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 23:

/* Line 1464 of yacc.c  */
#line 194 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 24:

/* Line 1464 of yacc.c  */
#line 198 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 25:

/* Line 1464 of yacc.c  */
#line 199 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 26:

/* Line 1464 of yacc.c  */
#line 200 "parser.y"
    { (yyval.obj) = (yyvsp[(3) - (4)].obj); ;}
    break;

  case 27:

/* Line 1464 of yacc.c  */
#line 204 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 29:

/* Line 1464 of yacc.c  */
#line 209 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 30:

/* Line 1464 of yacc.c  */
#line 210 "parser.y"
    {
      PyObject* tmp = ctx->Call(kNewAliasOrConstant, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yyloc));
      (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), tmp);
    ;}
    break;

  case 31:

/* Line 1464 of yacc.c  */
#line 215 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 32:

/* Line 1464 of yacc.c  */
#line 216 "parser.y"
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yylsp[(2) - (2)]));
      (yyval.obj) = ExtendList((yyvsp[(1) - (2)].obj), tmp);
    ;}
    break;

  case 33:

/* Line 1464 of yacc.c  */
#line 221 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 34:

/* Line 1464 of yacc.c  */
#line 226 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 36:

/* Line 1464 of yacc.c  */
#line 234 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("[(NN)]", (yyvsp[(1) - (5)].obj), (yyvsp[(4) - (5)].obj));
    ;}
    break;

  case 37:

/* Line 1464 of yacc.c  */
#line 238 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 38:

/* Line 1464 of yacc.c  */
#line 257 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 40:

/* Line 1464 of yacc.c  */
#line 265 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("[(NN)]", (yyvsp[(1) - (5)].obj), (yyvsp[(4) - (5)].obj));
    ;}
    break;

  case 41:

/* Line 1464 of yacc.c  */
#line 269 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 42:

/* Line 1464 of yacc.c  */
#line 281 "parser.y"
    { (yyval.obj) = ctx->Call(kIfBegin, "(N)", (yyvsp[(2) - (2)].obj)); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 43:

/* Line 1464 of yacc.c  */
#line 285 "parser.y"
    { (yyval.obj) = ctx->Call(kIfElif, "(N)", (yyvsp[(2) - (2)].obj)); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 44:

/* Line 1464 of yacc.c  */
#line 289 "parser.y"
    { (yyval.obj) = ctx->Call(kIfElse, "()"); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 45:

/* Line 1464 of yacc.c  */
#line 293 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NO)sN)", (yyvsp[(1) - (3)].obj), Py_None, (yyvsp[(2) - (3)].str), (yyvsp[(3) - (3)].obj));
    ;}
    break;

  case 46:

/* Line 1464 of yacc.c  */
#line 296 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NO)sN)", (yyvsp[(1) - (3)].obj), Py_None, (yyvsp[(2) - (3)].str), (yyvsp[(3) - (3)].obj));
    ;}
    break;

  case 47:

/* Line 1464 of yacc.c  */
#line 299 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NN)sN)", (yyvsp[(1) - (6)].obj), (yyvsp[(3) - (6)].obj), (yyvsp[(5) - (6)].str), (yyvsp[(6) - (6)].obj));
    ;}
    break;

  case 48:

/* Line 1464 of yacc.c  */
#line 302 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NN)sN)", (yyvsp[(1) - (6)].obj), (yyvsp[(3) - (6)].obj), (yyvsp[(5) - (6)].str), (yyvsp[(6) - (6)].obj));
    ;}
    break;

  case 49:

/* Line 1464 of yacc.c  */
#line 305 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NsN)", (yyvsp[(1) - (3)].obj), "and", (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 50:

/* Line 1464 of yacc.c  */
#line 306 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NsN)", (yyvsp[(1) - (3)].obj), "or", (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 51:

/* Line 1464 of yacc.c  */
#line 307 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 52:

/* Line 1464 of yacc.c  */
#line 312 "parser.y"
    { (yyval.obj) = Py_BuildValue("(N)", (yyvsp[(2) - (4)].obj)); ;}
    break;

  case 53:

/* Line 1464 of yacc.c  */
#line 313 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (5)].obj), (yyvsp[(4) - (5)].obj)); ;}
    break;

  case 54:

/* Line 1464 of yacc.c  */
#line 314 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("(NNN)", (yyvsp[(2) - (7)].obj), (yyvsp[(4) - (7)].obj), (yyvsp[(6) - (7)].obj));
    ;}
    break;

  case 55:

/* Line 1464 of yacc.c  */
#line 320 "parser.y"
    { (yyval.str) = "<"; ;}
    break;

  case 56:

/* Line 1464 of yacc.c  */
#line 321 "parser.y"
    { (yyval.str) = ">"; ;}
    break;

  case 57:

/* Line 1464 of yacc.c  */
#line 322 "parser.y"
    { (yyval.str) = "<="; ;}
    break;

  case 58:

/* Line 1464 of yacc.c  */
#line 323 "parser.y"
    { (yyval.str) = ">="; ;}
    break;

  case 59:

/* Line 1464 of yacc.c  */
#line 324 "parser.y"
    { (yyval.str) = "=="; ;}
    break;

  case 60:

/* Line 1464 of yacc.c  */
#line 325 "parser.y"
    { (yyval.str) = "!="; ;}
    break;

  case 61:

/* Line 1464 of yacc.c  */
#line 329 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 62:

/* Line 1464 of yacc.c  */
#line 333 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), ctx->Value(kByteString));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 63:

/* Line 1464 of yacc.c  */
#line 337 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), ctx->Value(kUnicodeString));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 64:

/* Line 1464 of yacc.c  */
#line 341 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), ctx->Value(kAnything));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 65:

/* Line 1464 of yacc.c  */
#line 345 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (5)].obj), (yyvsp[(5) - (5)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 66:

/* Line 1464 of yacc.c  */
#line 349 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 67:

/* Line 1464 of yacc.c  */
#line 353 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (5)].obj), (yyvsp[(3) - (5)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 68:

/* Line 1464 of yacc.c  */
#line 360 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddImport, "(ON)", Py_None, (yyvsp[(2) - (2)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 69:

/* Line 1464 of yacc.c  */
#line 364 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddImport, "(NN)", (yyvsp[(2) - (4)].obj), (yyvsp[(4) - (4)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 70:

/* Line 1464 of yacc.c  */
#line 371 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 71:

/* Line 1464 of yacc.c  */
#line 372 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 73:

/* Line 1464 of yacc.c  */
#line 376 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 75:

/* Line 1464 of yacc.c  */
#line 381 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 76:

/* Line 1464 of yacc.c  */
#line 382 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 77:

/* Line 1464 of yacc.c  */
#line 386 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 78:

/* Line 1464 of yacc.c  */
#line 387 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 80:

/* Line 1464 of yacc.c  */
#line 392 "parser.y"
    { (yyval.obj) = PyString_FromString("NamedTuple"); ;}
    break;

  case 81:

/* Line 1464 of yacc.c  */
#line 393 "parser.y"
    { (yyval.obj) = PyString_FromString("TypeVar"); ;}
    break;

  case 82:

/* Line 1464 of yacc.c  */
#line 394 "parser.y"
    { (yyval.obj) = PyString_FromString("*"); ;}
    break;

  case 83:

/* Line 1464 of yacc.c  */
#line 395 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 84:

/* Line 1464 of yacc.c  */
#line 399 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 85:

/* Line 1464 of yacc.c  */
#line 403 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddTypeVar, "(NNN)", (yyvsp[(1) - (7)].obj), (yyvsp[(5) - (7)].obj), (yyvsp[(6) - (7)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 86:

/* Line 1464 of yacc.c  */
#line 410 "parser.y"
    { (yyval.obj) = Py_BuildValue("(OO)", Py_None, Py_None); ;}
    break;

  case 87:

/* Line 1464 of yacc.c  */
#line 411 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NO)", (yyvsp[(2) - (2)].obj), Py_None); ;}
    break;

  case 88:

/* Line 1464 of yacc.c  */
#line 412 "parser.y"
    { (yyval.obj) = Py_BuildValue("(ON)", Py_None, (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 89:

/* Line 1464 of yacc.c  */
#line 413 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (4)].obj), (yyvsp[(4) - (4)].obj)); ;}
    break;

  case 90:

/* Line 1464 of yacc.c  */
#line 417 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 91:

/* Line 1464 of yacc.c  */
#line 418 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 92:

/* Line 1464 of yacc.c  */
#line 422 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 93:

/* Line 1464 of yacc.c  */
#line 426 "parser.y"
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

  case 94:

/* Line 1464 of yacc.c  */
#line 441 "parser.y"
    {
      // TODO(dbaum): Is PYTHONCODE necessary?
      (yyval.obj) = ctx->Call(kNewExternalFunction, "(NN)", (yyvsp[(1) - (4)].obj), (yyvsp[(3) - (4)].obj));
      // See comment above about why @2 is used as the start.
      (yyloc).first_line = (yylsp[(2) - (4)]).first_line;
      (yyloc).first_column = (yylsp[(2) - (4)]).first_column;
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 95:

/* Line 1464 of yacc.c  */
#line 452 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 96:

/* Line 1464 of yacc.c  */
#line 453 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 97:

/* Line 1464 of yacc.c  */
#line 457 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 98:

/* Line 1464 of yacc.c  */
#line 462 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 99:

/* Line 1464 of yacc.c  */
#line 463 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 100:

/* Line 1464 of yacc.c  */
#line 467 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 101:

/* Line 1464 of yacc.c  */
#line 468 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 102:

/* Line 1464 of yacc.c  */
#line 472 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NNN)", (yyvsp[(1) - (3)].obj), (yyvsp[(2) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 103:

/* Line 1464 of yacc.c  */
#line 473 "parser.y"
    { (yyval.obj) = Py_BuildValue("(sOO)", "*", Py_None, Py_None); ;}
    break;

  case 104:

/* Line 1464 of yacc.c  */
#line 474 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NNO)", (yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj), Py_None); ;}
    break;

  case 105:

/* Line 1464 of yacc.c  */
#line 475 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis) ;}
    break;

  case 106:

/* Line 1464 of yacc.c  */
#line 479 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 107:

/* Line 1464 of yacc.c  */
#line 480 "parser.y"
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 108:

/* Line 1464 of yacc.c  */
#line 484 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 109:

/* Line 1464 of yacc.c  */
#line 485 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 110:

/* Line 1464 of yacc.c  */
#line 486 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis); ;}
    break;

  case 111:

/* Line 1464 of yacc.c  */
#line 487 "parser.y"
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 112:

/* Line 1464 of yacc.c  */
#line 491 "parser.y"
    { (yyval.obj) = PyString_FromFormat("*%s", PyString_AsString((yyvsp[(2) - (2)].obj))); ;}
    break;

  case 113:

/* Line 1464 of yacc.c  */
#line 492 "parser.y"
    { (yyval.obj) = PyString_FromFormat("**%s", PyString_AsString((yyvsp[(3) - (3)].obj))); ;}
    break;

  case 114:

/* Line 1464 of yacc.c  */
#line 496 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 115:

/* Line 1464 of yacc.c  */
#line 497 "parser.y"
    { (yyval.obj) = ctx->Value(kAnything); ;}
    break;

  case 116:

/* Line 1464 of yacc.c  */
#line 501 "parser.y"
    { Py_DecRef((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 117:

/* Line 1464 of yacc.c  */
#line 505 "parser.y"
    { (yyval.obj) = (yyvsp[(4) - (5)].obj); ;}
    break;

  case 118:

/* Line 1464 of yacc.c  */
#line 506 "parser.y"
    { (yyval.obj) = (yyvsp[(3) - (4)].obj); ;}
    break;

  case 119:

/* Line 1464 of yacc.c  */
#line 507 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 127:

/* Line 1464 of yacc.c  */
#line 521 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 128:

/* Line 1464 of yacc.c  */
#line 522 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 129:

/* Line 1464 of yacc.c  */
#line 526 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 130:

/* Line 1464 of yacc.c  */
#line 527 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 131:

/* Line 1464 of yacc.c  */
#line 528 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 132:

/* Line 1464 of yacc.c  */
#line 532 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 133:

/* Line 1464 of yacc.c  */
#line 533 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 134:

/* Line 1464 of yacc.c  */
#line 537 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 135:

/* Line 1464 of yacc.c  */
#line 538 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis); ;}
    break;

  case 136:

/* Line 1464 of yacc.c  */
#line 542 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewType, "(N)", (yyvsp[(1) - (1)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 137:

/* Line 1464 of yacc.c  */
#line 546 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewType, "(NN)", (yyvsp[(1) - (4)].obj), (yyvsp[(3) - (4)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 138:

/* Line 1464 of yacc.c  */
#line 550 "parser.y"
    {
      // This rule is needed for Callable[[...], ...]
      (yyval.obj) = ctx->Call(kNewType, "(sN)", "tuple", (yyvsp[(2) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 139:

/* Line 1464 of yacc.c  */
#line 555 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewNamedTuple, "(NN)", (yyvsp[(3) - (6)].obj), (yyvsp[(5) - (6)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 140:

/* Line 1464 of yacc.c  */
#line 559 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 141:

/* Line 1464 of yacc.c  */
#line 560 "parser.y"
    { (yyval.obj) = ctx->Call(kNewIntersectionType, "([NN])", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 142:

/* Line 1464 of yacc.c  */
#line 561 "parser.y"
    { (yyval.obj) = ctx->Call(kNewUnionType, "([NN])", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 143:

/* Line 1464 of yacc.c  */
#line 562 "parser.y"
    { (yyval.obj) = ctx->Value(kAnything); ;}
    break;

  case 144:

/* Line 1464 of yacc.c  */
#line 563 "parser.y"
    { (yyval.obj) = ctx->Value(kNothing); ;}
    break;

  case 145:

/* Line 1464 of yacc.c  */
#line 567 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 146:

/* Line 1464 of yacc.c  */
#line 568 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 147:

/* Line 1464 of yacc.c  */
#line 572 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 148:

/* Line 1464 of yacc.c  */
#line 573 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 149:

/* Line 1464 of yacc.c  */
#line 577 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(4) - (6)].obj)); ;}
    break;

  case 152:

/* Line 1464 of yacc.c  */
#line 586 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 153:

/* Line 1464 of yacc.c  */
#line 587 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 154:

/* Line 1464 of yacc.c  */
#line 591 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 155:

/* Line 1464 of yacc.c  */
#line 592 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 156:

/* Line 1464 of yacc.c  */
#line 597 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 157:

/* Line 1464 of yacc.c  */
#line 598 "parser.y"
    {
      PyString_Concat(&(yyvsp[(1) - (3)].obj), DOT_STRING);
      PyString_ConcatAndDel(&(yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      (yyval.obj) = (yyvsp[(1) - (3)].obj);
    ;}
    break;

  case 158:

/* Line 1464 of yacc.c  */
#line 606 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 159:

/* Line 1464 of yacc.c  */
#line 607 "parser.y"
    {
      PyObject* slice = PySlice_New((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj), NULL);
      CHECK(slice, (yyloc));
      (yyval.obj) = slice;
    ;}
    break;

  case 160:

/* Line 1464 of yacc.c  */
#line 612 "parser.y"
    {
      PyObject* slice = PySlice_New((yyvsp[(1) - (5)].obj), (yyvsp[(3) - (5)].obj), (yyvsp[(5) - (5)].obj));
      CHECK(slice, (yyloc));
      (yyval.obj) = slice;
    ;}
    break;

  case 161:

/* Line 1464 of yacc.c  */
#line 620 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 162:

/* Line 1464 of yacc.c  */
#line 621 "parser.y"
    { (yyval.obj) = NULL; ;}
    break;



/* Line 1464 of yacc.c  */
#line 3449 "pyi/parser.tab.cc"
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
#line 629 "parser.y"


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

