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
     RAISES = 274,
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
     TYPECOMMENT = 287
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
#line 200 "pyi/parser.tab.cc"
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
#line 225 "pyi/parser.tab.cc"

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
#define YYLAST   313

/* YYNTOKENS -- Number of terminals.  */
#define YYNTOKENS  46
/* YYNNTS -- Number of nonterminals.  */
#define YYNNTS  60
/* YYNRULES -- Number of rules.  */
#define YYNRULES  149
/* YYNRULES -- Number of states.  */
#define YYNSTATES  271

/* YYTRANSLATE(YYLEX) -- Bison symbol number corresponding to YYLEX.  */
#define YYUNDEFTOK  2
#define YYMAXUTOK   287

#define YYTRANSLATE(YYX)						\
  ((unsigned int) (YYX) <= YYMAXUTOK ? yytranslate[YYX] : YYUNDEFTOK)

/* YYTRANSLATE[YYLEX] -- Bison symbol number corresponding to YYLEX.  */
static const yytype_uint8 yytranslate[] =
{
       0,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
      34,    35,    42,     2,    36,     2,    45,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,    33,     2,
      40,    37,    41,    44,    43,     2,     2,     2,     2,     2,
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

#if YYDEBUG
/* YYPRHS[YYN] -- Index of the first RHS symbol of rule number YYN in
   YYRHS.  */
static const yytype_uint16 yyprhs[] =
{
       0,     0,     3,     6,    10,    12,    15,    18,    21,    24,
      27,    30,    33,    34,    40,    42,    46,    49,    50,    54,
      56,    58,    62,    64,    68,    73,    75,    77,    80,    83,
      86,    87,    94,    96,   102,   109,   116,   118,   124,   131,
     134,   137,   139,   143,   147,   154,   161,   165,   169,   174,
     180,   188,   190,   192,   194,   196,   198,   200,   204,   208,
     214,   218,   224,   227,   232,   236,   238,   240,   244,   246,
     250,   255,   259,   261,   263,   265,   267,   269,   273,   277,
     284,   294,   299,   302,   303,   306,   308,   309,   313,   315,
     319,   321,   324,   326,   329,   330,   333,   336,   339,   340,
     343,   347,   350,   351,   354,   355,   359,   361,   366,   368,
     371,   376,   381,   382,   385,   387,   391,   394,   399,   403,
     405,   407,   409,   411,   416,   420,   427,   431,   435,   437,
     439,   444,   447,   451,   453,   460,   462,   463,   465,   466,
     470,   472,   474,   478,   480,   484,   490,   492,   493,   495
};

/* YYRHS -- A `-1'-separated list of the rules' RHS.  */
static const yytype_int8 yyrhs[] =
{
      47,     0,    -1,    48,     0,    -1,    31,    48,     0,    -1,
      49,    -1,    49,    68,    -1,    49,    77,    -1,    49,    69,
      -1,    49,    75,    -1,    49,    50,    -1,    49,    76,    -1,
      49,    58,    -1,    -1,     6,    51,    52,    33,    55,    -1,
       3,    -1,    34,    53,    35,    -1,    34,    35,    -1,    -1,
      53,    36,    54,    -1,    54,    -1,    95,    -1,     3,    37,
      95,    -1,   105,    -1,    29,    56,    30,    -1,    29,    31,
      56,    30,    -1,   105,    -1,    57,    -1,    57,    68,    -1,
      57,    77,    -1,    57,    60,    -1,    -1,    59,    64,    33,
      29,    49,    30,    -1,    59,    -1,    62,    33,    29,    49,
      30,    -1,    59,    63,    33,    29,    49,    30,    -1,    61,
      64,    33,    29,    57,    30,    -1,    61,    -1,    62,    33,
      29,    57,    30,    -1,    61,    63,    33,    29,    57,    30,
      -1,    10,    65,    -1,     9,    65,    -1,     8,    -1,   102,
      67,     3,    -1,   102,    67,    66,    -1,   102,    38,   103,
      39,    67,     4,    -1,   102,    38,   103,    39,    67,    66,
      -1,    65,    11,    65,    -1,    34,    65,    35,    -1,    34,
       4,    36,    35,    -1,    34,     4,    36,     4,    35,    -1,
      34,     4,    36,     4,    36,     4,    35,    -1,    40,    -1,
      41,    -1,    27,    -1,    28,    -1,    25,    -1,    26,    -1,
       3,    37,     4,    -1,     3,    37,    24,    -1,     3,    37,
      24,    32,    95,    -1,     3,    33,    95,    -1,     3,    33,
      95,    37,    24,    -1,    13,    70,    -1,    14,   102,    13,
      72,    -1,    70,    36,    71,    -1,    71,    -1,   102,    -1,
     102,    15,     3,    -1,    73,    -1,    34,    73,    35,    -1,
      34,    73,    36,    35,    -1,    73,    36,    74,    -1,    74,
      -1,     3,    -1,    20,    -1,    21,    -1,    42,    -1,     3,
      15,     3,    -1,     3,    37,    95,    -1,     3,    37,    21,
      34,    80,    35,    -1,    78,     7,     3,    34,    80,    35,
      86,    87,    89,    -1,    78,     7,     3,    17,    -1,    78,
      79,    -1,    -1,    43,   102,    -1,    81,    -1,    -1,    81,
      36,    82,    -1,    82,    -1,     3,    83,    84,    -1,    42,
      -1,    85,    83,    -1,    24,    -1,    33,    95,    -1,    -1,
      37,     3,    -1,    37,     4,    -1,    37,    24,    -1,    -1,
      42,     3,    -1,    42,    42,     3,    -1,    22,    95,    -1,
      -1,    19,    88,    -1,    -1,    88,    36,    95,    -1,    95,
      -1,    33,    29,    91,    30,    -1,    90,    -1,    33,   105,
      -1,    33,    29,   105,    30,    -1,    33,    29,    31,    30,
      -1,    -1,    91,    92,    -1,    92,    -1,     3,    23,    95,
      -1,    16,     3,    -1,    16,     3,    34,    35,    -1,    93,
      36,    94,    -1,    94,    -1,    95,    -1,    24,    -1,   102,
      -1,   102,    38,    93,    39,    -1,    38,   100,    39,    -1,
      20,    34,     3,    36,    96,    35,    -1,    34,    95,    35,
      -1,    95,    11,    95,    -1,    44,    -1,    18,    -1,    38,
      97,    99,    39,    -1,    38,    39,    -1,    97,    36,    98,
      -1,    98,    -1,    34,     3,    36,    95,    99,    35,    -1,
      36,    -1,    -1,   101,    -1,    -1,   101,    36,    95,    -1,
      95,    -1,     3,    -1,   102,    45,     3,    -1,     4,    -1,
     104,    33,   104,    -1,   104,    33,   104,    33,   104,    -1,
       4,    -1,    -1,    12,    -1,    24,    -1
};

/* YYRLINE[YYN] -- source line where rule number YYN was defined.  */
static const yytype_uint16 yyrline[] =
{
       0,   129,   129,   130,   134,   138,   139,   140,   141,   142,
     143,   144,   149,   153,   160,   171,   172,   173,   177,   178,
     182,   183,   187,   188,   189,   193,   194,   198,   199,   200,
     205,   210,   213,   218,   222,   241,   244,   249,   253,   265,
     269,   273,   277,   280,   283,   286,   289,   290,   295,   296,
     297,   303,   304,   305,   306,   307,   308,   312,   316,   320,
     324,   328,   335,   339,   346,   347,   350,   351,   355,   356,
     357,   361,   362,   366,   367,   368,   369,   370,   374,   381,
     388,   403,   414,   415,   419,   424,   425,   429,   430,   434,
     435,   436,   437,   441,   442,   446,   447,   448,   449,   453,
     454,   458,   459,   463,   464,   468,   469,   473,   474,   478,
     479,   480,   481,   485,   486,   490,   491,   492,   496,   497,
     501,   502,   506,   510,   514,   524,   528,   529,   530,   531,
     535,   536,   540,   541,   545,   549,   550,   554,   555,   559,
     560,   565,   566,   574,   575,   580,   588,   589,   593,   594
};
#endif

#if YYDEBUG || YYERROR_VERBOSE || YYTOKEN_TABLE
/* YYTNAME[SYMBOL-NUM] -- String name of the symbol SYMBOL-NUM.
   First, the terminals, then, starting at YYNTOKENS, nonterminals.  */
static const char *const yytname[] =
{
  "\"end of file\"", "error", "$undefined", "NAME", "NUMBER", "LEXERROR",
  "CLASS", "DEF", "ELSE", "ELIF", "IF", "OR", "PASS", "IMPORT", "FROM",
  "AS", "RAISE", "PYTHONCODE", "NOTHING", "RAISES", "NAMEDTUPLE",
  "TYPEVAR", "ARROW", "COLONEQUALS", "ELLIPSIS", "EQ", "NE", "LE", "GE",
  "INDENT", "DEDENT", "TRIPLEQUOTED", "TYPECOMMENT", "':'", "'('", "')'",
  "','", "'='", "'['", "']'", "'<'", "'>'", "'*'", "'@'", "'?'", "'.'",
  "$accept", "start", "unit", "alldefs", "classdef", "class_name",
  "parents", "parent_list", "parent", "maybe_class_funcs", "class_funcs",
  "funcdefs", "if_stmt", "if_and_elifs", "class_if_stmt",
  "class_if_and_elifs", "if_cond", "elif_cond", "else_cond", "condition",
  "version_tuple", "condition_op", "constantdef", "importdef",
  "import_items", "import_item", "from_list", "from_items", "from_item",
  "alias_or_constant", "typevardef", "funcdef", "decorators", "decorator",
  "params", "param_list", "param", "param_type", "param_default",
  "param_star_name", "return", "raises", "exceptions", "maybe_body",
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
     285,   286,   287,    58,    40,    41,    44,    61,    91,    93,
      60,    62,    42,    64,    63,    46
};
# endif

/* YYR1[YYN] -- Symbol number of symbol that rule YYN derives.  */
static const yytype_uint8 yyr1[] =
{
       0,    46,    47,    47,    48,    49,    49,    49,    49,    49,
      49,    49,    49,    50,    51,    52,    52,    52,    53,    53,
      54,    54,    55,    55,    55,    56,    56,    57,    57,    57,
      57,    58,    58,    59,    59,    60,    60,    61,    61,    62,
      63,    64,    65,    65,    65,    65,    65,    65,    66,    66,
      66,    67,    67,    67,    67,    67,    67,    68,    68,    68,
      68,    68,    69,    69,    70,    70,    71,    71,    72,    72,
      72,    73,    73,    74,    74,    74,    74,    74,    75,    76,
      77,    77,    78,    78,    79,    80,    80,    81,    81,    82,
      82,    82,    82,    83,    83,    84,    84,    84,    84,    85,
      85,    86,    86,    87,    87,    88,    88,    89,    89,    90,
      90,    90,    90,    91,    91,    92,    92,    92,    93,    93,
      94,    94,    95,    95,    95,    95,    95,    95,    95,    95,
      96,    96,    97,    97,    98,    99,    99,   100,   100,   101,
     101,   102,   102,   103,   103,   103,   104,   104,   105,   105
};

/* YYR2[YYN] -- Number of symbols composing right hand side of rule YYN.  */
static const yytype_uint8 yyr2[] =
{
       0,     2,     2,     3,     1,     2,     2,     2,     2,     2,
       2,     2,     0,     5,     1,     3,     2,     0,     3,     1,
       1,     3,     1,     3,     4,     1,     1,     2,     2,     2,
       0,     6,     1,     5,     6,     6,     1,     5,     6,     2,
       2,     1,     3,     3,     6,     6,     3,     3,     4,     5,
       7,     1,     1,     1,     1,     1,     1,     3,     3,     5,
       3,     5,     2,     4,     3,     1,     1,     3,     1,     3,
       4,     3,     1,     1,     1,     1,     1,     3,     3,     6,
       9,     4,     2,     0,     2,     1,     0,     3,     1,     3,
       1,     2,     1,     2,     0,     2,     2,     2,     0,     2,
       3,     2,     0,     2,     0,     3,     1,     4,     1,     2,
       4,     4,     0,     2,     1,     3,     2,     4,     3,     1,
       1,     1,     1,     4,     3,     6,     3,     3,     1,     1,
       4,     2,     3,     1,     6,     1,     0,     1,     0,     3,
       1,     1,     3,     1,     3,     5,     1,     0,     1,     1
};

/* YYDEFACT[STATE-NAME] -- Default rule to reduce with in state
   STATE-NUM when YYTABLE doesn't specify something else to do.  Zero
   means the default is an error.  */
static const yytype_uint8 yydefact[] =
{
      12,    12,     0,     0,    83,     0,     1,     2,     0,     0,
       0,     0,     0,     9,    11,    32,     0,     5,     7,     8,
      10,     6,     0,     3,     0,     0,    14,    17,   141,     0,
      39,     0,    62,    65,    66,     0,    41,     0,     0,     0,
       0,     0,     0,    82,   129,     0,     0,   138,   128,    60,
     122,    57,     0,    58,    78,     0,     0,     0,     0,    55,
      56,    53,    54,   147,    51,    52,     0,     0,     0,     0,
       0,    40,     0,     0,    12,     0,    84,     0,     0,   140,
       0,   137,     0,     0,     0,    86,     0,   141,    16,     0,
      19,    20,     0,    47,    46,   143,     0,     0,   142,    42,
       0,    43,    64,    67,    73,    74,    75,     0,    76,    63,
      68,    72,    12,    12,    83,    81,    86,     0,   126,   124,
       0,   127,    61,   121,     0,   119,   120,    94,    92,    90,
       0,    85,    88,    94,    59,     0,    15,     0,   148,   149,
      30,    13,    22,     0,   147,     0,     0,     0,     0,    83,
      83,    33,     0,     0,   139,     0,   123,     0,    98,    99,
       0,    79,     0,    91,    21,    18,    30,     0,    83,    25,
       0,   146,   144,     0,    77,    69,     0,    71,    34,    31,
     102,     0,     0,   118,    93,     0,    89,   100,    87,     0,
      23,     0,    29,    36,     0,    27,    28,    44,    45,   147,
       0,    48,    70,     0,   104,     0,   131,   136,   133,   125,
      95,    96,    97,    24,     0,     0,     0,     0,   145,    49,
       0,   101,     0,   112,     0,   135,     0,     0,     0,    30,
       0,   103,   106,     0,    80,   108,     0,   132,   130,    30,
      30,    83,    50,     0,     0,   109,   136,    83,    83,    37,
     105,     0,     0,     0,     0,   114,     0,   135,     0,    38,
      35,     0,   116,   111,   107,   113,   110,   134,   115,     0,
     117
};

/* YYDEFGOTO[NTERM-NUM].  */
static const yytype_int16 yydefgoto[] =
{
      -1,     2,     3,     4,    13,    27,    56,    89,    90,   141,
     167,   168,    14,    15,   192,   193,    16,    38,    39,    30,
     101,    67,    17,    18,    32,    33,   109,   110,   111,    19,
      20,    21,    22,    43,   130,   131,   132,   158,   186,   133,
     204,   223,   231,   234,   235,   254,   255,   124,   125,    91,
     182,   207,   208,   226,    80,    81,    50,    96,    97,   169
};

/* YYPACT[STATE-NUM] -- Index in YYTABLE of the portion describing
   STATE-NUM.  */
#define YYPACT_NINF -166
static const yytype_int16 yypact[] =
{
      24,  -166,   115,   126,   217,   134,  -166,  -166,   -16,    58,
       3,   144,   144,  -166,  -166,   199,   140,  -166,  -166,  -166,
    -166,  -166,     6,  -166,    61,     8,  -166,   125,  -166,     3,
     157,   159,   154,  -166,    -1,     5,  -166,     3,   170,   185,
     163,   219,   144,  -166,  -166,   192,    61,    61,  -166,    60,
      83,  -166,   204,   207,   221,    13,   208,   116,     3,  -166,
    -166,  -166,  -166,   236,  -166,  -166,   239,    31,   144,   240,
      33,   157,   215,   216,  -166,    90,   201,   244,   135,   221,
     209,   213,    61,   226,    70,    21,    61,   214,  -166,   189,
    -166,   221,   181,  -166,  -166,   220,   218,   222,  -166,  -166,
     248,  -166,  -166,  -166,   241,  -166,  -166,    99,  -166,  -166,
     223,  -166,  -166,  -166,   147,  -166,    21,   224,  -166,  -166,
      61,  -166,  -166,  -166,   101,  -166,   221,   225,  -166,    35,
     227,   228,  -166,   225,   221,    61,  -166,    98,  -166,  -166,
     171,  -166,  -166,   188,   250,   229,   258,   198,    99,   152,
     161,  -166,   231,   230,   221,    70,  -166,    61,   232,  -166,
     260,  -166,    21,  -166,   221,  -166,   197,   237,   100,  -166,
      66,  -166,   238,    37,  -166,  -166,    71,  -166,  -166,  -166,
     251,   -14,   235,  -166,   221,   177,  -166,  -166,  -166,   242,
    -166,    56,  -166,   199,   243,  -166,  -166,  -166,  -166,   250,
     200,  -166,  -166,    61,   255,   272,  -166,   245,  -166,  -166,
    -166,  -166,  -166,  -166,    15,   246,   247,   249,  -166,  -166,
     273,   221,    61,   252,   253,   254,   256,   257,   261,  -166,
     259,   262,   221,   182,  -166,  -166,    61,  -166,  -166,  -166,
    -166,   119,  -166,    61,   132,  -166,    87,   142,   166,  -166,
     221,   264,   279,   263,   109,  -166,   266,  -166,   265,  -166,
    -166,    61,   267,  -166,  -166,  -166,  -166,  -166,   221,   268,
    -166
};

/* YYPGOTO[NTERM-NUM].  */
static const yytype_int16 yypgoto[] =
{
    -166,  -166,   282,   -44,  -166,  -166,  -166,  -166,   155,  -166,
     118,   -51,  -166,  -166,  -166,  -166,  -165,   104,   106,    80,
     121,   162,  -163,  -166,  -166,   234,  -166,   202,  -133,  -166,
    -166,  -161,  -166,  -166,   190,  -166,   145,   175,  -166,  -166,
    -166,  -166,  -166,  -166,  -166,  -166,    50,  -166,   156,   -24,
    -166,  -166,    85,    67,  -166,  -166,    -2,  -166,  -140,   -90
};

/* YYTABLE[YYPACT[STATE-NUM]].  What to do in state STATE-NUM.  If
   positive, shift that token.  If negative, reduce the rule which
   number is the opposite.  If zero, do what YYDEFACT says.
   If YYTABLE_NINF, syntax error.  */
#define YYTABLE_NINF -147
static const yytype_int16 yytable[] =
{
      49,    54,   142,   194,   172,   195,    28,   196,    31,    34,
      35,    28,    51,    41,    69,   177,    87,    24,    70,    51,
     205,    25,    78,    79,   127,   206,    44,    31,    45,    52,
     114,    44,    53,    45,    99,    31,   104,    29,   159,    53,
      76,   200,    46,   177,    66,   128,    47,    46,    88,    42,
      66,    47,    48,   105,   106,     1,    31,    48,   121,   218,
     126,    26,   134,   129,    28,   100,    34,   107,   149,   150,
     197,    82,   201,    28,   104,   108,   194,   160,   195,    44,
     196,    45,   194,   194,   195,   195,   196,   196,    44,    24,
      45,   105,   106,   214,   123,    46,   154,    83,    82,    47,
     100,    87,   104,   191,    46,    48,   202,   115,    47,    57,
      10,   164,   251,   108,    48,     6,    44,    71,    45,   105,
     106,    84,   191,   257,   116,   252,     7,    58,    66,    10,
     -26,   126,    46,   184,    23,   251,    47,   155,    94,   264,
     156,   108,    48,   245,   138,   191,    82,    28,   252,   249,
       8,    93,    10,     9,   256,     8,   139,    10,     9,    55,
      11,    12,    10,   253,     8,    11,    12,     9,    58,   191,
     118,    10,   259,    40,    11,    12,    10,   151,   241,   221,
     210,   211,   178,   138,    59,    60,    61,    62,   247,   248,
      68,   179,    74,   138,   138,   139,   260,    63,   232,    64,
      65,   212,   166,    72,    66,   139,   139,    36,    37,   138,
     140,   244,   246,    59,    60,    61,    62,    -4,    73,   250,
       8,   139,    75,     9,   136,   137,    77,    10,    64,    65,
      11,    12,    82,   175,   176,   219,   220,   268,    85,    86,
      95,    92,    98,   103,   112,   113,    66,   117,   119,   120,
     122,   135,   145,  -146,   171,   144,   146,   143,   157,   148,
     153,   174,   161,   187,   162,   173,   180,   190,   181,   185,
     209,   199,   213,   203,   222,   224,   217,   230,   229,   227,
     228,   225,   262,     5,   189,   233,   239,   261,   205,   236,
     240,   198,   165,   263,   242,   238,   266,   215,   243,   216,
     267,   269,   102,   270,   265,   170,   152,   188,   163,   147,
     237,   183,     0,   258
};

static const yytype_int16 yycheck[] =
{
      24,    25,    92,   168,   144,   168,     3,   168,    10,    11,
      12,     3,     4,     7,    15,   148,     3,    33,    13,     4,
      34,    37,    46,    47,     3,    39,    18,    29,    20,    21,
      74,    18,    24,    20,     3,    37,     3,    34,     3,    24,
      42,     4,    34,   176,    45,    24,    38,    34,    35,    43,
      45,    38,    44,    20,    21,    31,    58,    44,    82,   199,
      84,     3,    86,    42,     3,    34,    68,    34,   112,   113,
       4,    11,    35,     3,     3,    42,   241,    42,   241,    18,
     241,    20,   247,   248,   247,   248,   247,   248,    18,    33,
      20,    20,    21,    37,    24,    34,   120,    37,    11,    38,
      34,     3,     3,     3,    34,    44,    35,    17,    38,    29,
      10,   135,     3,    42,    44,     0,    18,    37,    20,    20,
      21,    38,     3,    36,    34,    16,     0,    11,    45,    10,
      30,   155,    34,   157,     0,     3,    38,    36,    58,    30,
      39,    42,    44,   233,    12,     3,    11,     3,    16,    30,
       3,    35,    10,     6,   244,     3,    24,    10,     6,    34,
      13,    14,    10,    31,     3,    13,    14,     6,    11,     3,
      35,    10,    30,    33,    13,    14,    10,    30,   229,   203,
       3,     4,    30,    12,    25,    26,    27,    28,   239,   240,
      36,    30,    29,    12,    12,    24,    30,    38,   222,    40,
      41,    24,    31,    33,    45,    24,    24,     8,     9,    12,
      29,    29,   236,    25,    26,    27,    28,     0,    33,   243,
       3,    24,     3,     6,    35,    36,    34,    10,    40,    41,
      13,    14,    11,    35,    36,    35,    36,   261,    34,    32,
       4,    33,     3,     3,    29,    29,    45,     3,    39,    36,
      24,    37,     4,    33,     4,    33,    15,    39,    33,    36,
      36,     3,    35,     3,    36,    36,    35,    30,    38,    37,
      35,    33,    30,    22,    19,     3,    33,     4,    29,    33,
      33,    36,     3,     1,   166,    33,    29,    23,    34,    36,
      29,   170,   137,    30,    35,    39,    30,   193,    36,   193,
      35,    34,    68,    35,   254,   143,   116,   162,   133,   107,
     225,   155,    -1,   246
};

/* YYSTOS[STATE-NUM] -- The (internal number of the) accessing
   symbol of state STATE-NUM.  */
static const yytype_uint8 yystos[] =
{
       0,    31,    47,    48,    49,    48,     0,     0,     3,     6,
      10,    13,    14,    50,    58,    59,    62,    68,    69,    75,
      76,    77,    78,     0,    33,    37,     3,    51,     3,    34,
      65,   102,    70,    71,   102,   102,     8,     9,    63,    64,
      33,     7,    43,    79,    18,    20,    34,    38,    44,    95,
     102,     4,    21,    24,    95,    34,    52,    65,    11,    25,
      26,    27,    28,    38,    40,    41,    45,    67,    36,    15,
      13,    65,    33,    33,    29,     3,   102,    34,    95,    95,
     100,   101,    11,    37,    38,    34,    32,     3,    35,    53,
      54,    95,    33,    35,    65,     4,   103,   104,     3,     3,
      34,    66,    71,     3,     3,    20,    21,    34,    42,    72,
      73,    74,    29,    29,    49,    17,    34,     3,    35,    39,
      36,    95,    24,    24,    93,    94,    95,     3,    24,    42,
      80,    81,    82,    85,    95,    37,    35,    36,    12,    24,
      29,    55,   105,    39,    33,     4,    15,    73,    36,    49,
      49,    30,    80,    36,    95,    36,    39,    33,    83,     3,
      42,    35,    36,    83,    95,    54,    31,    56,    57,   105,
      67,     4,   104,    36,     3,    35,    36,    74,    30,    30,
      35,    38,    96,    94,    95,    37,    84,     3,    82,    56,
      30,     3,    60,    61,    62,    68,    77,     4,    66,    33,
       4,    35,    35,    22,    86,    34,    39,    97,    98,    35,
       3,     4,    24,    30,    37,    63,    64,    33,   104,    35,
      36,    95,    19,    87,     3,    36,    99,    33,    33,    29,
       4,    88,    95,    33,    89,    90,    36,    98,    39,    29,
      29,    57,    35,    36,    29,   105,    95,    57,    57,    30,
      95,     3,    16,    31,    91,    92,   105,    36,    99,    30,
      30,    23,     3,    30,    30,    92,    30,    35,    95,    34,
      35
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
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1419 "pyi/parser.tab.cc"
	break;
      case 4: /* "NUMBER" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1428 "pyi/parser.tab.cc"
	break;
      case 5: /* "LEXERROR" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1437 "pyi/parser.tab.cc"
	break;
      case 47: /* "start" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1446 "pyi/parser.tab.cc"
	break;
      case 48: /* "unit" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1455 "pyi/parser.tab.cc"
	break;
      case 49: /* "alldefs" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1464 "pyi/parser.tab.cc"
	break;
      case 50: /* "classdef" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1473 "pyi/parser.tab.cc"
	break;
      case 51: /* "class_name" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1482 "pyi/parser.tab.cc"
	break;
      case 52: /* "parents" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1491 "pyi/parser.tab.cc"
	break;
      case 53: /* "parent_list" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1500 "pyi/parser.tab.cc"
	break;
      case 54: /* "parent" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1509 "pyi/parser.tab.cc"
	break;
      case 55: /* "maybe_class_funcs" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1518 "pyi/parser.tab.cc"
	break;
      case 56: /* "class_funcs" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1527 "pyi/parser.tab.cc"
	break;
      case 57: /* "funcdefs" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1536 "pyi/parser.tab.cc"
	break;
      case 58: /* "if_stmt" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1545 "pyi/parser.tab.cc"
	break;
      case 59: /* "if_and_elifs" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1554 "pyi/parser.tab.cc"
	break;
      case 60: /* "class_if_stmt" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1563 "pyi/parser.tab.cc"
	break;
      case 61: /* "class_if_and_elifs" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1572 "pyi/parser.tab.cc"
	break;
      case 62: /* "if_cond" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1581 "pyi/parser.tab.cc"
	break;
      case 63: /* "elif_cond" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1590 "pyi/parser.tab.cc"
	break;
      case 64: /* "else_cond" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1599 "pyi/parser.tab.cc"
	break;
      case 65: /* "condition" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1608 "pyi/parser.tab.cc"
	break;
      case 66: /* "version_tuple" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1617 "pyi/parser.tab.cc"
	break;
      case 67: /* "condition_op" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->str)); };

/* Line 1009 of yacc.c  */
#line 1626 "pyi/parser.tab.cc"
	break;
      case 68: /* "constantdef" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1635 "pyi/parser.tab.cc"
	break;
      case 69: /* "importdef" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1644 "pyi/parser.tab.cc"
	break;
      case 70: /* "import_items" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1653 "pyi/parser.tab.cc"
	break;
      case 71: /* "import_item" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1662 "pyi/parser.tab.cc"
	break;
      case 72: /* "from_list" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1671 "pyi/parser.tab.cc"
	break;
      case 73: /* "from_items" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1680 "pyi/parser.tab.cc"
	break;
      case 74: /* "from_item" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1689 "pyi/parser.tab.cc"
	break;
      case 75: /* "alias_or_constant" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1698 "pyi/parser.tab.cc"
	break;
      case 76: /* "typevardef" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1707 "pyi/parser.tab.cc"
	break;
      case 77: /* "funcdef" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1716 "pyi/parser.tab.cc"
	break;
      case 78: /* "decorators" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1725 "pyi/parser.tab.cc"
	break;
      case 79: /* "decorator" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1734 "pyi/parser.tab.cc"
	break;
      case 80: /* "params" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1743 "pyi/parser.tab.cc"
	break;
      case 81: /* "param_list" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1752 "pyi/parser.tab.cc"
	break;
      case 82: /* "param" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1761 "pyi/parser.tab.cc"
	break;
      case 83: /* "param_type" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1770 "pyi/parser.tab.cc"
	break;
      case 84: /* "param_default" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1779 "pyi/parser.tab.cc"
	break;
      case 85: /* "param_star_name" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1788 "pyi/parser.tab.cc"
	break;
      case 86: /* "return" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1797 "pyi/parser.tab.cc"
	break;
      case 87: /* "raises" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1806 "pyi/parser.tab.cc"
	break;
      case 88: /* "exceptions" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1815 "pyi/parser.tab.cc"
	break;
      case 89: /* "maybe_body" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1824 "pyi/parser.tab.cc"
	break;
      case 91: /* "body" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1833 "pyi/parser.tab.cc"
	break;
      case 92: /* "body_stmt" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1842 "pyi/parser.tab.cc"
	break;
      case 93: /* "type_parameters" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1851 "pyi/parser.tab.cc"
	break;
      case 94: /* "type_parameter" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1860 "pyi/parser.tab.cc"
	break;
      case 95: /* "type" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1869 "pyi/parser.tab.cc"
	break;
      case 96: /* "named_tuple_fields" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1878 "pyi/parser.tab.cc"
	break;
      case 97: /* "named_tuple_field_list" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1887 "pyi/parser.tab.cc"
	break;
      case 98: /* "named_tuple_field" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1896 "pyi/parser.tab.cc"
	break;
      case 100: /* "maybe_type_list" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1905 "pyi/parser.tab.cc"
	break;
      case 101: /* "type_list" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1914 "pyi/parser.tab.cc"
	break;
      case 102: /* "dotted_name" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1923 "pyi/parser.tab.cc"
	break;
      case 103: /* "getitem_key" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1932 "pyi/parser.tab.cc"
	break;
      case 104: /* "maybe_number" */

/* Line 1009 of yacc.c  */
#line 96 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1941 "pyi/parser.tab.cc"
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
#line 129 "parser.y"
    { ctx->SetAndDelResult((yyvsp[(1) - (2)].obj)); (yyval.obj) = NULL; ;}
    break;

  case 3:

/* Line 1464 of yacc.c  */
#line 130 "parser.y"
    { ctx->SetAndDelResult((yyvsp[(2) - (3)].obj)); (yyval.obj) = NULL; ;}
    break;

  case 5:

/* Line 1464 of yacc.c  */
#line 138 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 6:

/* Line 1464 of yacc.c  */
#line 139 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 7:

/* Line 1464 of yacc.c  */
#line 140 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 8:

/* Line 1464 of yacc.c  */
#line 141 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 9:

/* Line 1464 of yacc.c  */
#line 142 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 10:

/* Line 1464 of yacc.c  */
#line 143 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 11:

/* Line 1464 of yacc.c  */
#line 144 "parser.y"
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yylsp[(2) - (2)]));
      (yyval.obj) = ExtendList((yyvsp[(1) - (2)].obj), tmp);
    ;}
    break;

  case 12:

/* Line 1464 of yacc.c  */
#line 149 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 13:

/* Line 1464 of yacc.c  */
#line 153 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddClass, "(NNN)", (yyvsp[(2) - (5)].obj), (yyvsp[(3) - (5)].obj), (yyvsp[(5) - (5)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 14:

/* Line 1464 of yacc.c  */
#line 160 "parser.y"
    {
      // Do not borrow the $1 reference since it is also returned later
      // in $$.  Use O instead of N in the format string.
      PyObject* tmp = ctx->Call(kRegisterClassName, "(O)", (yyvsp[(1) - (1)].obj));
      CHECK(tmp, (yyloc));
      Py_DECREF(tmp);
      (yyval.obj) = (yyvsp[(1) - (1)].obj);
    ;}
    break;

  case 15:

/* Line 1464 of yacc.c  */
#line 171 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 16:

/* Line 1464 of yacc.c  */
#line 172 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 17:

/* Line 1464 of yacc.c  */
#line 173 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 18:

/* Line 1464 of yacc.c  */
#line 177 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 19:

/* Line 1464 of yacc.c  */
#line 178 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 20:

/* Line 1464 of yacc.c  */
#line 182 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 21:

/* Line 1464 of yacc.c  */
#line 183 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 22:

/* Line 1464 of yacc.c  */
#line 187 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 23:

/* Line 1464 of yacc.c  */
#line 188 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 24:

/* Line 1464 of yacc.c  */
#line 189 "parser.y"
    { (yyval.obj) = (yyvsp[(3) - (4)].obj); ;}
    break;

  case 25:

/* Line 1464 of yacc.c  */
#line 193 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 27:

/* Line 1464 of yacc.c  */
#line 198 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 28:

/* Line 1464 of yacc.c  */
#line 199 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 29:

/* Line 1464 of yacc.c  */
#line 200 "parser.y"
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yylsp[(2) - (2)]));
      (yyval.obj) = ExtendList((yyvsp[(1) - (2)].obj), tmp);
    ;}
    break;

  case 30:

/* Line 1464 of yacc.c  */
#line 205 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 31:

/* Line 1464 of yacc.c  */
#line 210 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 33:

/* Line 1464 of yacc.c  */
#line 218 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("[(NN)]", (yyvsp[(1) - (5)].obj), (yyvsp[(4) - (5)].obj));
    ;}
    break;

  case 34:

/* Line 1464 of yacc.c  */
#line 222 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 35:

/* Line 1464 of yacc.c  */
#line 241 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 37:

/* Line 1464 of yacc.c  */
#line 249 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("[(NN)]", (yyvsp[(1) - (5)].obj), (yyvsp[(4) - (5)].obj));
    ;}
    break;

  case 38:

/* Line 1464 of yacc.c  */
#line 253 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 39:

/* Line 1464 of yacc.c  */
#line 265 "parser.y"
    { (yyval.obj) = ctx->Call(kIfBegin, "(N)", (yyvsp[(2) - (2)].obj)); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 40:

/* Line 1464 of yacc.c  */
#line 269 "parser.y"
    { (yyval.obj) = ctx->Call(kIfElif, "(N)", (yyvsp[(2) - (2)].obj)); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 41:

/* Line 1464 of yacc.c  */
#line 273 "parser.y"
    { (yyval.obj) = ctx->Call(kIfElse, "()"); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 42:

/* Line 1464 of yacc.c  */
#line 277 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NO)sN)", (yyvsp[(1) - (3)].obj), Py_None, (yyvsp[(2) - (3)].str), (yyvsp[(3) - (3)].obj));
    ;}
    break;

  case 43:

/* Line 1464 of yacc.c  */
#line 280 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NO)sN)", (yyvsp[(1) - (3)].obj), Py_None, (yyvsp[(2) - (3)].str), (yyvsp[(3) - (3)].obj));
    ;}
    break;

  case 44:

/* Line 1464 of yacc.c  */
#line 283 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NN)sN)", (yyvsp[(1) - (6)].obj), (yyvsp[(3) - (6)].obj), (yyvsp[(5) - (6)].str), (yyvsp[(6) - (6)].obj));
    ;}
    break;

  case 45:

/* Line 1464 of yacc.c  */
#line 286 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("((NN)sN)", (yyvsp[(1) - (6)].obj), (yyvsp[(3) - (6)].obj), (yyvsp[(5) - (6)].str), (yyvsp[(6) - (6)].obj));
    ;}
    break;

  case 46:

/* Line 1464 of yacc.c  */
#line 289 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NsN)", (yyvsp[(1) - (3)].obj), "or", (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 47:

/* Line 1464 of yacc.c  */
#line 290 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 48:

/* Line 1464 of yacc.c  */
#line 295 "parser.y"
    { (yyval.obj) = Py_BuildValue("(N)", (yyvsp[(2) - (4)].obj)); ;}
    break;

  case 49:

/* Line 1464 of yacc.c  */
#line 296 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (5)].obj), (yyvsp[(4) - (5)].obj)); ;}
    break;

  case 50:

/* Line 1464 of yacc.c  */
#line 297 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("(NNN)", (yyvsp[(2) - (7)].obj), (yyvsp[(4) - (7)].obj), (yyvsp[(6) - (7)].obj));
    ;}
    break;

  case 51:

/* Line 1464 of yacc.c  */
#line 303 "parser.y"
    { (yyval.str) = "<"; ;}
    break;

  case 52:

/* Line 1464 of yacc.c  */
#line 304 "parser.y"
    { (yyval.str) = ">"; ;}
    break;

  case 53:

/* Line 1464 of yacc.c  */
#line 305 "parser.y"
    { (yyval.str) = "<="; ;}
    break;

  case 54:

/* Line 1464 of yacc.c  */
#line 306 "parser.y"
    { (yyval.str) = ">="; ;}
    break;

  case 55:

/* Line 1464 of yacc.c  */
#line 307 "parser.y"
    { (yyval.str) = "=="; ;}
    break;

  case 56:

/* Line 1464 of yacc.c  */
#line 308 "parser.y"
    { (yyval.str) = "!="; ;}
    break;

  case 57:

/* Line 1464 of yacc.c  */
#line 312 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 58:

/* Line 1464 of yacc.c  */
#line 316 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), ctx->Value(kAnything));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 59:

/* Line 1464 of yacc.c  */
#line 320 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (5)].obj), (yyvsp[(5) - (5)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 60:

/* Line 1464 of yacc.c  */
#line 324 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 61:

/* Line 1464 of yacc.c  */
#line 328 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (5)].obj), (yyvsp[(3) - (5)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 62:

/* Line 1464 of yacc.c  */
#line 335 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddImport, "(ON)", Py_None, (yyvsp[(2) - (2)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 63:

/* Line 1464 of yacc.c  */
#line 339 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddImport, "(NN)", (yyvsp[(2) - (4)].obj), (yyvsp[(4) - (4)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 64:

/* Line 1464 of yacc.c  */
#line 346 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 65:

/* Line 1464 of yacc.c  */
#line 347 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 67:

/* Line 1464 of yacc.c  */
#line 351 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 69:

/* Line 1464 of yacc.c  */
#line 356 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 70:

/* Line 1464 of yacc.c  */
#line 357 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 71:

/* Line 1464 of yacc.c  */
#line 361 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 72:

/* Line 1464 of yacc.c  */
#line 362 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 74:

/* Line 1464 of yacc.c  */
#line 367 "parser.y"
    { (yyval.obj) = PyString_FromString("NamedTuple"); ;}
    break;

  case 75:

/* Line 1464 of yacc.c  */
#line 368 "parser.y"
    { (yyval.obj) = PyString_FromString("TypeVar"); ;}
    break;

  case 76:

/* Line 1464 of yacc.c  */
#line 369 "parser.y"
    { (yyval.obj) = PyString_FromString("*"); ;}
    break;

  case 77:

/* Line 1464 of yacc.c  */
#line 370 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 78:

/* Line 1464 of yacc.c  */
#line 374 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddAliasOrConstant, "(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 79:

/* Line 1464 of yacc.c  */
#line 381 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddTypeVar, "(NN)", (yyvsp[(1) - (6)].obj), (yyvsp[(5) - (6)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 80:

/* Line 1464 of yacc.c  */
#line 388 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewFunction, "(NNNNNN)", (yyvsp[(1) - (9)].obj), (yyvsp[(3) - (9)].obj), (yyvsp[(5) - (9)].obj), (yyvsp[(7) - (9)].obj), (yyvsp[(8) - (9)].obj), (yyvsp[(9) - (9)].obj));
      // Decorators is nullable and messes up the location tracking by
      // using the previous symbol as the start location for this production,
      // which is very misleading.  It is better to ignore decorators and
      // pretend the production started with DEF.  Even when decorators are
      // present the error line will be close enough to be helpful.
      //
      // TODO(dbaum): Consider making this smarter and only ignoring decorators
      // when they are empty.  Making decorators non-nullable and having two
      // productions for funcdef would be a reasonable solution.
      (yyloc).first_line = (yylsp[(2) - (9)]).first_line;
      (yyloc).first_column = (yylsp[(2) - (9)]).first_column;
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 81:

/* Line 1464 of yacc.c  */
#line 403 "parser.y"
    {
      // TODO(dbaum): Is PYTHONCODE necessary?
      (yyval.obj) = ctx->Call(kNewExternalFunction, "(NN)", (yyvsp[(1) - (4)].obj), (yyvsp[(3) - (4)].obj));
      // See comment above about why @2 is used as the start.
      (yyloc).first_line = (yylsp[(2) - (4)]).first_line;
      (yyloc).first_column = (yylsp[(2) - (4)]).first_column;
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 82:

/* Line 1464 of yacc.c  */
#line 414 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 83:

/* Line 1464 of yacc.c  */
#line 415 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 84:

/* Line 1464 of yacc.c  */
#line 419 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 85:

/* Line 1464 of yacc.c  */
#line 424 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 86:

/* Line 1464 of yacc.c  */
#line 425 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 87:

/* Line 1464 of yacc.c  */
#line 429 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 88:

/* Line 1464 of yacc.c  */
#line 430 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 89:

/* Line 1464 of yacc.c  */
#line 434 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NNN)", (yyvsp[(1) - (3)].obj), (yyvsp[(2) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 90:

/* Line 1464 of yacc.c  */
#line 435 "parser.y"
    { (yyval.obj) = Py_BuildValue("(sOO)", "*", Py_None, Py_None); ;}
    break;

  case 91:

/* Line 1464 of yacc.c  */
#line 436 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NNO)", (yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj), Py_None); ;}
    break;

  case 92:

/* Line 1464 of yacc.c  */
#line 437 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis) ;}
    break;

  case 93:

/* Line 1464 of yacc.c  */
#line 441 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 94:

/* Line 1464 of yacc.c  */
#line 442 "parser.y"
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 95:

/* Line 1464 of yacc.c  */
#line 446 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 96:

/* Line 1464 of yacc.c  */
#line 447 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 97:

/* Line 1464 of yacc.c  */
#line 448 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis); ;}
    break;

  case 98:

/* Line 1464 of yacc.c  */
#line 449 "parser.y"
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 99:

/* Line 1464 of yacc.c  */
#line 453 "parser.y"
    { (yyval.obj) = PyString_FromFormat("*%s", PyString_AsString((yyvsp[(2) - (2)].obj))); ;}
    break;

  case 100:

/* Line 1464 of yacc.c  */
#line 454 "parser.y"
    { (yyval.obj) = PyString_FromFormat("**%s", PyString_AsString((yyvsp[(3) - (3)].obj))); ;}
    break;

  case 101:

/* Line 1464 of yacc.c  */
#line 458 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 102:

/* Line 1464 of yacc.c  */
#line 459 "parser.y"
    { (yyval.obj) = ctx->Value(kAnything); ;}
    break;

  case 103:

/* Line 1464 of yacc.c  */
#line 463 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 104:

/* Line 1464 of yacc.c  */
#line 464 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 105:

/* Line 1464 of yacc.c  */
#line 468 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 106:

/* Line 1464 of yacc.c  */
#line 469 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 107:

/* Line 1464 of yacc.c  */
#line 473 "parser.y"
    { (yyval.obj) = (yyvsp[(3) - (4)].obj); ;}
    break;

  case 108:

/* Line 1464 of yacc.c  */
#line 474 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 113:

/* Line 1464 of yacc.c  */
#line 485 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 114:

/* Line 1464 of yacc.c  */
#line 486 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 115:

/* Line 1464 of yacc.c  */
#line 490 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 116:

/* Line 1464 of yacc.c  */
#line 491 "parser.y"
    { Py_DECREF((yyvsp[(2) - (2)].obj)); Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 117:

/* Line 1464 of yacc.c  */
#line 492 "parser.y"
    { Py_DECREF((yyvsp[(2) - (4)].obj)); Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 118:

/* Line 1464 of yacc.c  */
#line 496 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 119:

/* Line 1464 of yacc.c  */
#line 497 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 120:

/* Line 1464 of yacc.c  */
#line 501 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 121:

/* Line 1464 of yacc.c  */
#line 502 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis); ;}
    break;

  case 122:

/* Line 1464 of yacc.c  */
#line 506 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewType, "(N)", (yyvsp[(1) - (1)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 123:

/* Line 1464 of yacc.c  */
#line 510 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewType, "(NN)", (yyvsp[(1) - (4)].obj), (yyvsp[(3) - (4)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 124:

/* Line 1464 of yacc.c  */
#line 514 "parser.y"
    {
      // TODO(dbaum): Is this rule necessary?  Seems like it may be old cruft.
      //
      // TODO(dbaum): This assumes kNewType will make this a GenericType and
      // not try to convert it to HomogeneousContainerType (like it does with
      // typing.Tuple).  This feels inconsistent and should be revisited once
      // the parser is complete.
      (yyval.obj) = ctx->Call(kNewType, "(sN)", "tuple", (yyvsp[(2) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 125:

/* Line 1464 of yacc.c  */
#line 524 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewNamedTuple, "(NN)", (yyvsp[(3) - (6)].obj), (yyvsp[(5) - (6)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 126:

/* Line 1464 of yacc.c  */
#line 528 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 127:

/* Line 1464 of yacc.c  */
#line 529 "parser.y"
    { (yyval.obj) = ctx->Call(kNewUnionType, "([NN])", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 128:

/* Line 1464 of yacc.c  */
#line 530 "parser.y"
    { (yyval.obj) = ctx->Value(kAnything); ;}
    break;

  case 129:

/* Line 1464 of yacc.c  */
#line 531 "parser.y"
    { (yyval.obj) = ctx->Value(kNothing); ;}
    break;

  case 130:

/* Line 1464 of yacc.c  */
#line 535 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 131:

/* Line 1464 of yacc.c  */
#line 536 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 132:

/* Line 1464 of yacc.c  */
#line 540 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 133:

/* Line 1464 of yacc.c  */
#line 541 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 134:

/* Line 1464 of yacc.c  */
#line 545 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(4) - (6)].obj)); ;}
    break;

  case 137:

/* Line 1464 of yacc.c  */
#line 554 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 138:

/* Line 1464 of yacc.c  */
#line 555 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 139:

/* Line 1464 of yacc.c  */
#line 559 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 140:

/* Line 1464 of yacc.c  */
#line 560 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 141:

/* Line 1464 of yacc.c  */
#line 565 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 142:

/* Line 1464 of yacc.c  */
#line 566 "parser.y"
    {
      PyString_Concat(&(yyvsp[(1) - (3)].obj), DOT_STRING);
      PyString_ConcatAndDel(&(yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      (yyval.obj) = (yyvsp[(1) - (3)].obj);
    ;}
    break;

  case 143:

/* Line 1464 of yacc.c  */
#line 574 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 144:

/* Line 1464 of yacc.c  */
#line 575 "parser.y"
    {
      PyObject* slice = PySlice_New((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj), NULL);
      CHECK(slice, (yyloc));
      (yyval.obj) = slice;
    ;}
    break;

  case 145:

/* Line 1464 of yacc.c  */
#line 580 "parser.y"
    {
      PyObject* slice = PySlice_New((yyvsp[(1) - (5)].obj), (yyvsp[(3) - (5)].obj), (yyvsp[(5) - (5)].obj));
      CHECK(slice, (yyloc));
      (yyval.obj) = slice;
    ;}
    break;

  case 146:

/* Line 1464 of yacc.c  */
#line 588 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 147:

/* Line 1464 of yacc.c  */
#line 589 "parser.y"
    { (yyval.obj) = NULL; ;}
    break;



/* Line 1464 of yacc.c  */
#line 3322 "pyi/parser.tab.cc"
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
#line 597 "parser.y"


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

