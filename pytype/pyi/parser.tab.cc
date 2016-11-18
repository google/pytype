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
#define YYLAST   278

/* YYNTOKENS -- Number of terminals.  */
#define YYNTOKENS  46
/* YYNNTS -- Number of nonterminals.  */
#define YYNNTS  58
/* YYNRULES -- Number of rules.  */
#define YYNRULES  138
/* YYNRULES -- Number of states.  */
#define YYNSTATES  249

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
      34,    35,    40,     2,    36,     2,    45,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,    33,     2,
      38,    37,    39,    44,    41,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,    42,     2,    43,     2,     2,     2,     2,     2,     2,
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
     134,   137,   139,   143,   147,   152,   158,   166,   168,   170,
     172,   174,   176,   178,   182,   186,   192,   195,   200,   204,
     206,   208,   212,   214,   218,   223,   227,   229,   231,   233,
     235,   237,   241,   245,   252,   262,   267,   270,   271,   274,
     276,   277,   281,   283,   287,   289,   292,   294,   297,   298,
     301,   304,   307,   308,   311,   315,   318,   319,   322,   323,
     327,   329,   334,   336,   339,   344,   349,   350,   353,   355,
     359,   362,   367,   371,   373,   375,   377,   379,   384,   388,
     395,   399,   403,   405,   407,   412,   415,   419,   421,   428,
     430,   431,   433,   434,   438,   440,   442,   446,   448
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
      95,    -1,   103,    -1,    29,    56,    30,    -1,    29,    31,
      56,    30,    -1,   103,    -1,    57,    -1,    57,    68,    -1,
      57,    77,    -1,    57,    60,    -1,    -1,    59,    64,    33,
      29,    49,    30,    -1,    59,    -1,    62,    33,    29,    49,
      30,    -1,    59,    63,    33,    29,    49,    30,    -1,    61,
      64,    33,    29,    57,    30,    -1,    61,    -1,    62,    33,
      29,    57,    30,    -1,    61,    63,    33,    29,    57,    30,
      -1,    10,    65,    -1,     9,    65,    -1,     8,    -1,   102,
      67,     3,    -1,   102,    67,    66,    -1,    34,     4,    36,
      35,    -1,    34,     4,    36,     4,    35,    -1,    34,     4,
      36,     4,    36,     4,    35,    -1,    38,    -1,    39,    -1,
      27,    -1,    28,    -1,    25,    -1,    26,    -1,     3,    37,
       4,    -1,     3,    37,    24,    -1,     3,    37,    24,    32,
      95,    -1,    13,    70,    -1,    14,   102,    13,    72,    -1,
      70,    36,    71,    -1,    71,    -1,   102,    -1,   102,    15,
       3,    -1,    73,    -1,    34,    73,    35,    -1,    34,    73,
      36,    35,    -1,    73,    36,    74,    -1,    74,    -1,     3,
      -1,    20,    -1,    21,    -1,    40,    -1,     3,    15,     3,
      -1,     3,    37,    95,    -1,     3,    37,    21,    34,    80,
      35,    -1,    78,     7,     3,    34,    80,    35,    86,    87,
      89,    -1,    78,     7,     3,    17,    -1,    78,    79,    -1,
      -1,    41,   102,    -1,    81,    -1,    -1,    81,    36,    82,
      -1,    82,    -1,     3,    83,    84,    -1,    40,    -1,    85,
      83,    -1,    24,    -1,    33,    95,    -1,    -1,    37,     3,
      -1,    37,     4,    -1,    37,    24,    -1,    -1,    40,     3,
      -1,    40,    40,     3,    -1,    22,    95,    -1,    -1,    19,
      88,    -1,    -1,    88,    36,    95,    -1,    95,    -1,    33,
      29,    91,    30,    -1,    90,    -1,    33,   103,    -1,    33,
      29,   103,    30,    -1,    33,    29,    31,    30,    -1,    -1,
      91,    92,    -1,    92,    -1,     3,    23,    95,    -1,    16,
       3,    -1,    16,     3,    34,    35,    -1,    93,    36,    94,
      -1,    94,    -1,    95,    -1,    24,    -1,   102,    -1,   102,
      42,    93,    43,    -1,    42,   100,    43,    -1,    20,    34,
       3,    36,    96,    35,    -1,    34,    95,    35,    -1,    95,
      11,    95,    -1,    44,    -1,    18,    -1,    42,    97,    99,
      43,    -1,    42,    43,    -1,    97,    36,    98,    -1,    98,
      -1,    34,     3,    36,    95,    99,    35,    -1,    36,    -1,
      -1,   101,    -1,    -1,   101,    36,    95,    -1,    95,    -1,
       3,    -1,   102,    45,     3,    -1,    12,    -1,    24,    -1
};

/* YYRLINE[YYN] -- source line where rule number YYN was defined.  */
static const yytype_uint16 yyrline[] =
{
       0,   127,   127,   128,   132,   136,   137,   138,   139,   140,
     141,   142,   147,   151,   158,   169,   170,   171,   175,   176,
     180,   181,   185,   186,   187,   191,   192,   196,   197,   198,
     203,   208,   211,   216,   220,   239,   242,   247,   251,   263,
     267,   271,   275,   278,   285,   286,   287,   293,   294,   295,
     296,   297,   298,   302,   306,   310,   317,   321,   328,   329,
     332,   333,   337,   338,   339,   343,   344,   348,   349,   350,
     351,   352,   356,   363,   370,   385,   396,   397,   401,   406,
     407,   411,   412,   416,   417,   418,   419,   423,   424,   428,
     429,   430,   431,   435,   436,   440,   441,   445,   446,   450,
     451,   455,   456,   460,   461,   462,   463,   467,   468,   472,
     473,   474,   478,   479,   483,   484,   488,   492,   496,   506,
     510,   511,   512,   513,   517,   518,   522,   523,   527,   531,
     532,   536,   537,   541,   542,   547,   548,   556,   557
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
  "','", "'='", "'<'", "'>'", "'*'", "'@'", "'['", "']'", "'?'", "'.'",
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
  "dotted_name", "pass_or_ellipsis", 0
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
     285,   286,   287,    58,    40,    41,    44,    61,    60,    62,
      42,    64,    91,    93,    63,    46
};
# endif

/* YYR1[YYN] -- Symbol number of symbol that rule YYN derives.  */
static const yytype_uint8 yyr1[] =
{
       0,    46,    47,    47,    48,    49,    49,    49,    49,    49,
      49,    49,    49,    50,    51,    52,    52,    52,    53,    53,
      54,    54,    55,    55,    55,    56,    56,    57,    57,    57,
      57,    58,    58,    59,    59,    60,    60,    61,    61,    62,
      63,    64,    65,    65,    66,    66,    66,    67,    67,    67,
      67,    67,    67,    68,    68,    68,    69,    69,    70,    70,
      71,    71,    72,    72,    72,    73,    73,    74,    74,    74,
      74,    74,    75,    76,    77,    77,    78,    78,    79,    80,
      80,    81,    81,    82,    82,    82,    82,    83,    83,    84,
      84,    84,    84,    85,    85,    86,    86,    87,    87,    88,
      88,    89,    89,    90,    90,    90,    90,    91,    91,    92,
      92,    92,    93,    93,    94,    94,    95,    95,    95,    95,
      95,    95,    95,    95,    96,    96,    97,    97,    98,    99,
      99,   100,   100,   101,   101,   102,   102,   103,   103
};

/* YYR2[YYN] -- Number of symbols composing right hand side of rule YYN.  */
static const yytype_uint8 yyr2[] =
{
       0,     2,     2,     3,     1,     2,     2,     2,     2,     2,
       2,     2,     0,     5,     1,     3,     2,     0,     3,     1,
       1,     3,     1,     3,     4,     1,     1,     2,     2,     2,
       0,     6,     1,     5,     6,     6,     1,     5,     6,     2,
       2,     1,     3,     3,     4,     5,     7,     1,     1,     1,
       1,     1,     1,     3,     3,     5,     2,     4,     3,     1,
       1,     3,     1,     3,     4,     3,     1,     1,     1,     1,
       1,     3,     3,     6,     9,     4,     2,     0,     2,     1,
       0,     3,     1,     3,     1,     2,     1,     2,     0,     2,
       2,     2,     0,     2,     3,     2,     0,     2,     0,     3,
       1,     4,     1,     2,     4,     4,     0,     2,     1,     3,
       2,     4,     3,     1,     1,     1,     1,     4,     3,     6,
       3,     3,     1,     1,     4,     2,     3,     1,     6,     1,
       0,     1,     0,     3,     1,     1,     3,     1,     1
};

/* YYDEFACT[STATE-NAME] -- Default rule to reduce with in state
   STATE-NUM when YYTABLE doesn't specify something else to do.  Zero
   means the default is an error.  */
static const yytype_uint8 yydefact[] =
{
      12,    12,     0,     0,    77,     0,     1,     2,     0,     0,
       0,     0,     0,     9,    11,    32,     0,     5,     7,     8,
      10,     6,     0,     3,     0,    14,    17,   135,    39,     0,
      56,    59,    60,     0,    41,     0,     0,     0,     0,     0,
       0,    76,    53,   123,     0,     0,    54,     0,   132,   122,
      72,   116,     0,     0,    51,    52,    49,    50,    47,    48,
       0,     0,     0,     0,     0,    40,     0,     0,    12,     0,
      78,     0,    80,     0,     0,   134,     0,   131,     0,     0,
     135,    16,     0,    19,    20,     0,   136,    42,     0,    43,
      58,    61,    67,    68,    69,     0,    70,    57,    62,    66,
      12,    12,    77,    75,    80,     0,    88,    86,    84,     0,
      79,    82,    88,    55,   120,   118,     0,   121,   115,     0,
     113,   114,     0,    15,     0,   137,   138,    30,    13,    22,
       0,     0,     0,     0,    77,    77,    33,     0,     0,     0,
      92,    93,     0,    73,     0,    85,   133,     0,   117,    21,
      18,    30,     0,    77,    25,     0,    71,    63,     0,    65,
      34,    31,    96,     0,     0,    87,     0,    83,    94,    81,
     112,     0,    23,     0,    29,    36,     0,    27,    28,     0,
      44,    64,     0,    98,     0,   125,   130,   127,   119,    89,
      90,    91,    24,     0,     0,     0,     0,    45,     0,    95,
       0,   106,     0,   129,     0,     0,     0,    30,     0,    97,
     100,     0,    74,   102,     0,   126,   124,    30,    30,    77,
      46,     0,     0,   103,   130,    77,    77,    37,    99,     0,
       0,     0,     0,   108,     0,   129,     0,    38,    35,     0,
     110,   105,   101,   107,   104,   128,   109,     0,   111
};

/* YYDEFGOTO[NTERM-NUM].  */
static const yytype_int16 yydefgoto[] =
{
      -1,     2,     3,     4,    13,    26,    53,    82,    83,   128,
     152,   153,    14,    15,   174,   175,    16,    36,    37,    28,
      89,    61,    17,    18,    30,    31,    97,    98,    99,    19,
      20,    21,    22,    41,   109,   110,   111,   140,   167,   112,
     183,   201,   209,   212,   213,   232,   233,   119,   120,    84,
     164,   186,   187,   204,    76,    77,    51,   154
};

/* YYPACT[STATE-NUM] -- Index in YYTABLE of the portion describing
   STATE-NUM.  */
#define YYPACT_NINF -152
static const yytype_int16 yypact[] =
{
      -9,  -152,    61,    90,   195,    93,  -152,  -152,    72,    25,
     108,   108,   108,  -152,  -152,    87,   107,  -152,  -152,  -152,
    -152,  -152,    -2,  -152,     9,  -152,    83,  -152,  -152,   147,
     120,  -152,    67,    28,  -152,   108,   129,   131,   124,   180,
     108,  -152,  -152,  -152,   154,   159,   162,    18,    18,  -152,
     191,   -26,     0,   170,  -152,  -152,  -152,  -152,  -152,  -152,
     207,    11,   108,   211,    82,  -152,   187,   188,  -152,   144,
     173,   216,     7,    18,    45,   191,   178,   184,    18,    47,
     185,  -152,   132,  -152,   191,   158,  -152,  -152,   219,  -152,
    -152,  -152,   209,  -152,  -152,    43,  -152,  -152,   189,  -152,
    -152,  -152,   122,  -152,     7,   190,   194,  -152,     8,   193,
     196,  -152,   194,   191,  -152,  -152,    18,  -152,  -152,   168,
    -152,   191,    18,  -152,    66,  -152,  -152,   153,  -152,  -152,
     197,   226,   171,    43,   136,   141,  -152,   199,   198,    18,
     200,  -152,   227,  -152,     7,  -152,   191,    47,  -152,   191,
    -152,   157,   201,    91,  -152,    62,  -152,  -152,    84,  -152,
    -152,  -152,   213,   -17,   203,   191,   156,  -152,  -152,  -152,
    -152,   206,  -152,   202,  -152,    87,   208,  -152,  -152,   177,
    -152,  -152,    18,   223,   240,  -152,   210,  -152,  -152,  -152,
    -152,  -152,  -152,   139,   212,   214,   215,  -152,   244,   191,
      18,   217,   218,   221,   220,   222,   224,  -152,   225,   228,
     191,   167,  -152,  -152,    18,  -152,  -152,  -152,  -152,    96,
    -152,    18,   117,  -152,     4,   104,   127,  -152,   191,   229,
     246,   231,   115,  -152,   232,  -152,   230,  -152,  -152,    18,
     233,  -152,  -152,  -152,  -152,  -152,   191,   234,  -152
};

/* YYPGOTO[NTERM-NUM].  */
static const yytype_int16 yypgoto[] =
{
    -152,  -152,   255,   -43,  -152,  -152,  -152,  -152,   133,  -152,
     119,   -18,  -152,  -152,  -152,  -152,  -151,    97,    98,   236,
    -152,  -152,  -149,  -152,  -152,   204,  -152,   163,   -45,  -152,
    -152,  -147,  -152,  -152,   155,  -152,   130,   164,  -152,  -152,
    -152,  -152,  -152,  -152,  -152,  -152,    36,  -152,   128,   -24,
    -152,  -152,    74,    54,  -152,  -152,    -3,   -84
};

/* YYTABLE[YYPACT[STATE-NUM]].  What to do in state STATE-NUM.  If
   positive, shift that token.  If negative, reduce the rule which
   number is the opposite.  If zero, do what YYDEFACT says.
   If YYTABLE_NINF, syntax error.  */
#define YYTABLE_NINF -27
static const yytype_int16 yytable[] =
{
      50,   129,   176,    80,   177,    39,   178,    29,    32,    33,
     106,   141,    27,    42,    87,    78,    79,   184,    43,    60,
      44,    27,     1,    74,    75,   102,   185,    43,    25,    44,
      45,   107,    29,    46,    47,    81,    43,    70,    44,    40,
     235,    64,    48,    47,    49,    88,    92,   108,   142,   113,
      27,    48,    47,    49,   117,   121,    78,   134,   135,    32,
      48,     6,    49,    93,    94,    43,   179,    44,   176,    80,
     177,   118,   178,    60,   176,   176,   177,   177,   178,   178,
     114,    47,    63,    96,    43,    92,    44,    92,   159,    48,
       7,    49,   146,    23,   173,    34,    35,   180,   149,   173,
      47,    10,    93,    94,    93,    94,    10,   173,    48,    24,
      49,    27,    60,   159,    10,   165,    95,    52,   229,   181,
     229,   -26,    96,   121,    96,     8,   227,   223,     9,   125,
     173,   230,    10,   230,   237,    11,    12,    10,   234,     8,
      38,   126,     9,    42,     8,   242,    10,     9,   231,    11,
      12,    10,   136,    68,    11,    12,    62,   238,   199,   189,
     190,   103,    66,    46,    67,   125,   160,   123,   124,   125,
     125,   161,    54,    55,    56,    57,   210,   126,   104,   125,
     191,   126,   126,    69,   151,    58,    59,   127,    71,   219,
     224,   126,    60,    72,    73,    -4,   222,   228,     8,   225,
     226,     9,    78,    85,   147,    10,   157,   158,    11,    12,
      86,   148,   197,   198,    91,   246,   100,   101,    60,   105,
     116,   115,   122,   130,   131,   133,   138,   139,   143,   156,
     168,   172,   144,   155,   162,   182,   192,   166,   188,   193,
     163,   196,   200,   202,   207,   205,   203,   206,   208,   240,
     211,   217,   239,   218,   214,   184,     5,   150,   132,   137,
     220,   241,   244,   216,   221,   245,    90,   247,   243,   248,
     171,    65,   194,   195,   169,   170,   145,   215,   236
};

static const yytype_uint8 yycheck[] =
{
      24,    85,   153,     3,   153,     7,   153,    10,    11,    12,
       3,     3,     3,     4,     3,    11,    42,    34,    18,    45,
      20,     3,    31,    47,    48,    68,    43,    18,     3,    20,
      21,    24,    35,    24,    34,    35,    18,    40,    20,    41,
      36,    13,    42,    34,    44,    34,     3,    40,    40,    73,
       3,    42,    34,    44,    78,    79,    11,   100,   101,    62,
      42,     0,    44,    20,    21,    18,     4,    20,   219,     3,
     219,    24,   219,    45,   225,   226,   225,   226,   225,   226,
      35,    34,    15,    40,    18,     3,    20,     3,   133,    42,
       0,    44,   116,     0,     3,     8,     9,    35,   122,     3,
      34,    10,    20,    21,    20,    21,    10,     3,    42,    37,
      44,     3,    45,   158,    10,   139,    34,    34,     3,    35,
       3,    30,    40,   147,    40,     3,    30,   211,     6,    12,
       3,    16,    10,    16,    30,    13,    14,    10,   222,     3,
      33,    24,     6,     4,     3,    30,    10,     6,    31,    13,
      14,    10,    30,    29,    13,    14,    36,    30,   182,     3,
       4,    17,    33,    24,    33,    12,    30,    35,    36,    12,
      12,    30,    25,    26,    27,    28,   200,    24,    34,    12,
      24,    24,    24,     3,    31,    38,    39,    29,    34,   207,
     214,    24,    45,    34,    32,     0,    29,   221,     3,   217,
     218,     6,    11,    33,    36,    10,    35,    36,    13,    14,
       3,    43,    35,    36,     3,   239,    29,    29,    45,     3,
      36,    43,    37,     4,    15,    36,    36,    33,    35,     3,
       3,    30,    36,    36,    35,    22,    30,    37,    35,    37,
      42,    33,    19,     3,    29,    33,    36,    33,     4,     3,
      33,    29,    23,    29,    36,    34,     1,   124,    95,   104,
      35,    30,    30,    43,    36,    35,    62,    34,   232,    35,
     151,    35,   175,   175,   144,   147,   112,   203,   224
};

/* YYSTOS[STATE-NUM] -- The (internal number of the) accessing
   symbol of state STATE-NUM.  */
static const yytype_uint8 yystos[] =
{
       0,    31,    47,    48,    49,    48,     0,     0,     3,     6,
      10,    13,    14,    50,    58,    59,    62,    68,    69,    75,
      76,    77,    78,     0,    37,     3,    51,     3,    65,   102,
      70,    71,   102,   102,     8,     9,    63,    64,    33,     7,
      41,    79,     4,    18,    20,    21,    24,    34,    42,    44,
      95,   102,    34,    52,    25,    26,    27,    28,    38,    39,
      45,    67,    36,    15,    13,    65,    33,    33,    29,     3,
     102,    34,    34,    32,    95,    95,   100,   101,    11,    42,
       3,    35,    53,    54,    95,    33,     3,     3,    34,    66,
      71,     3,     3,    20,    21,    34,    40,    72,    73,    74,
      29,    29,    49,    17,    34,     3,     3,    24,    40,    80,
      81,    82,    85,    95,    35,    43,    36,    95,    24,    93,
      94,    95,    37,    35,    36,    12,    24,    29,    55,   103,
       4,    15,    73,    36,    49,    49,    30,    80,    36,    33,
      83,     3,    40,    35,    36,    83,    95,    36,    43,    95,
      54,    31,    56,    57,   103,    36,     3,    35,    36,    74,
      30,    30,    35,    42,    96,    95,    37,    84,     3,    82,
      94,    56,    30,     3,    60,    61,    62,    68,    77,     4,
      35,    35,    22,    86,    34,    43,    97,    98,    35,     3,
       4,    24,    30,    37,    63,    64,    33,    35,    36,    95,
      19,    87,     3,    36,    99,    33,    33,    29,     4,    88,
      95,    33,    89,    90,    36,    98,    43,    29,    29,    57,
      35,    36,    29,   103,    95,    57,    57,    30,    95,     3,
      16,    31,    91,    92,   103,    36,    99,    30,    30,    23,
       3,    30,    30,    92,    30,    35,    95,    34,    35
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
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1393 "pyi/parser.tab.cc"
	break;
      case 4: /* "NUMBER" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1402 "pyi/parser.tab.cc"
	break;
      case 5: /* "LEXERROR" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1411 "pyi/parser.tab.cc"
	break;
      case 47: /* "start" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1420 "pyi/parser.tab.cc"
	break;
      case 48: /* "unit" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1429 "pyi/parser.tab.cc"
	break;
      case 49: /* "alldefs" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1438 "pyi/parser.tab.cc"
	break;
      case 50: /* "classdef" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1447 "pyi/parser.tab.cc"
	break;
      case 51: /* "class_name" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1456 "pyi/parser.tab.cc"
	break;
      case 52: /* "parents" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1465 "pyi/parser.tab.cc"
	break;
      case 53: /* "parent_list" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1474 "pyi/parser.tab.cc"
	break;
      case 54: /* "parent" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1483 "pyi/parser.tab.cc"
	break;
      case 55: /* "maybe_class_funcs" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1492 "pyi/parser.tab.cc"
	break;
      case 56: /* "class_funcs" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1501 "pyi/parser.tab.cc"
	break;
      case 57: /* "funcdefs" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1510 "pyi/parser.tab.cc"
	break;
      case 58: /* "if_stmt" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1519 "pyi/parser.tab.cc"
	break;
      case 59: /* "if_and_elifs" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1528 "pyi/parser.tab.cc"
	break;
      case 60: /* "class_if_stmt" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1537 "pyi/parser.tab.cc"
	break;
      case 61: /* "class_if_and_elifs" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1546 "pyi/parser.tab.cc"
	break;
      case 62: /* "if_cond" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1555 "pyi/parser.tab.cc"
	break;
      case 63: /* "elif_cond" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1564 "pyi/parser.tab.cc"
	break;
      case 64: /* "else_cond" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1573 "pyi/parser.tab.cc"
	break;
      case 65: /* "condition" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1582 "pyi/parser.tab.cc"
	break;
      case 66: /* "version_tuple" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1591 "pyi/parser.tab.cc"
	break;
      case 67: /* "condition_op" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->str)); };

/* Line 1009 of yacc.c  */
#line 1600 "pyi/parser.tab.cc"
	break;
      case 68: /* "constantdef" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1609 "pyi/parser.tab.cc"
	break;
      case 69: /* "importdef" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1618 "pyi/parser.tab.cc"
	break;
      case 70: /* "import_items" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1627 "pyi/parser.tab.cc"
	break;
      case 71: /* "import_item" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1636 "pyi/parser.tab.cc"
	break;
      case 72: /* "from_list" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1645 "pyi/parser.tab.cc"
	break;
      case 73: /* "from_items" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1654 "pyi/parser.tab.cc"
	break;
      case 74: /* "from_item" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1663 "pyi/parser.tab.cc"
	break;
      case 75: /* "alias_or_constant" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1672 "pyi/parser.tab.cc"
	break;
      case 76: /* "typevardef" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1681 "pyi/parser.tab.cc"
	break;
      case 77: /* "funcdef" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1690 "pyi/parser.tab.cc"
	break;
      case 78: /* "decorators" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1699 "pyi/parser.tab.cc"
	break;
      case 79: /* "decorator" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1708 "pyi/parser.tab.cc"
	break;
      case 80: /* "params" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1717 "pyi/parser.tab.cc"
	break;
      case 81: /* "param_list" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1726 "pyi/parser.tab.cc"
	break;
      case 82: /* "param" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1735 "pyi/parser.tab.cc"
	break;
      case 83: /* "param_type" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1744 "pyi/parser.tab.cc"
	break;
      case 84: /* "param_default" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1753 "pyi/parser.tab.cc"
	break;
      case 85: /* "param_star_name" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1762 "pyi/parser.tab.cc"
	break;
      case 86: /* "return" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1771 "pyi/parser.tab.cc"
	break;
      case 87: /* "raises" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1780 "pyi/parser.tab.cc"
	break;
      case 88: /* "exceptions" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1789 "pyi/parser.tab.cc"
	break;
      case 89: /* "maybe_body" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1798 "pyi/parser.tab.cc"
	break;
      case 91: /* "body" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1807 "pyi/parser.tab.cc"
	break;
      case 92: /* "body_stmt" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1816 "pyi/parser.tab.cc"
	break;
      case 93: /* "type_parameters" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1825 "pyi/parser.tab.cc"
	break;
      case 94: /* "type_parameter" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1834 "pyi/parser.tab.cc"
	break;
      case 95: /* "type" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1843 "pyi/parser.tab.cc"
	break;
      case 96: /* "named_tuple_fields" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1852 "pyi/parser.tab.cc"
	break;
      case 97: /* "named_tuple_field_list" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1861 "pyi/parser.tab.cc"
	break;
      case 98: /* "named_tuple_field" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1870 "pyi/parser.tab.cc"
	break;
      case 100: /* "maybe_type_list" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1879 "pyi/parser.tab.cc"
	break;
      case 101: /* "type_list" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1888 "pyi/parser.tab.cc"
	break;
      case 102: /* "dotted_name" */

/* Line 1009 of yacc.c  */
#line 94 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1897 "pyi/parser.tab.cc"
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
#line 127 "parser.y"
    { ctx->SetAndDelResult((yyvsp[(1) - (2)].obj)); (yyval.obj) = NULL; ;}
    break;

  case 3:

/* Line 1464 of yacc.c  */
#line 128 "parser.y"
    { ctx->SetAndDelResult((yyvsp[(2) - (3)].obj)); (yyval.obj) = NULL; ;}
    break;

  case 5:

/* Line 1464 of yacc.c  */
#line 136 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 6:

/* Line 1464 of yacc.c  */
#line 137 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 7:

/* Line 1464 of yacc.c  */
#line 138 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 8:

/* Line 1464 of yacc.c  */
#line 139 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 9:

/* Line 1464 of yacc.c  */
#line 140 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 10:

/* Line 1464 of yacc.c  */
#line 141 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); Py_DECREF((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 11:

/* Line 1464 of yacc.c  */
#line 142 "parser.y"
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yylsp[(2) - (2)]));
      (yyval.obj) = ExtendList((yyvsp[(1) - (2)].obj), tmp);
    ;}
    break;

  case 12:

/* Line 1464 of yacc.c  */
#line 147 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 13:

/* Line 1464 of yacc.c  */
#line 151 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddClass, "(NNN)", (yyvsp[(2) - (5)].obj), (yyvsp[(3) - (5)].obj), (yyvsp[(5) - (5)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 14:

/* Line 1464 of yacc.c  */
#line 158 "parser.y"
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
#line 169 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 16:

/* Line 1464 of yacc.c  */
#line 170 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 17:

/* Line 1464 of yacc.c  */
#line 171 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 18:

/* Line 1464 of yacc.c  */
#line 175 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 19:

/* Line 1464 of yacc.c  */
#line 176 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 20:

/* Line 1464 of yacc.c  */
#line 180 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 21:

/* Line 1464 of yacc.c  */
#line 181 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 22:

/* Line 1464 of yacc.c  */
#line 185 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 23:

/* Line 1464 of yacc.c  */
#line 186 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 24:

/* Line 1464 of yacc.c  */
#line 187 "parser.y"
    { (yyval.obj) = (yyvsp[(3) - (4)].obj); ;}
    break;

  case 25:

/* Line 1464 of yacc.c  */
#line 191 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 27:

/* Line 1464 of yacc.c  */
#line 196 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 28:

/* Line 1464 of yacc.c  */
#line 197 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 29:

/* Line 1464 of yacc.c  */
#line 198 "parser.y"
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yyvsp[(2) - (2)].obj));
      CHECK(tmp, (yylsp[(2) - (2)]));
      (yyval.obj) = ExtendList((yyvsp[(1) - (2)].obj), tmp);
    ;}
    break;

  case 30:

/* Line 1464 of yacc.c  */
#line 203 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 31:

/* Line 1464 of yacc.c  */
#line 208 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 33:

/* Line 1464 of yacc.c  */
#line 216 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("[(NN)]", (yyvsp[(1) - (5)].obj), (yyvsp[(4) - (5)].obj));
    ;}
    break;

  case 34:

/* Line 1464 of yacc.c  */
#line 220 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 35:

/* Line 1464 of yacc.c  */
#line 239 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 37:

/* Line 1464 of yacc.c  */
#line 247 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("[(NN)]", (yyvsp[(1) - (5)].obj), (yyvsp[(4) - (5)].obj));
    ;}
    break;

  case 38:

/* Line 1464 of yacc.c  */
#line 251 "parser.y"
    {
      (yyval.obj) = AppendList((yyvsp[(1) - (6)].obj), Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(5) - (6)].obj)));
    ;}
    break;

  case 39:

/* Line 1464 of yacc.c  */
#line 263 "parser.y"
    { (yyval.obj) = ctx->Call(kIfBegin, "(N)", (yyvsp[(2) - (2)].obj)); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 40:

/* Line 1464 of yacc.c  */
#line 267 "parser.y"
    { (yyval.obj) = ctx->Call(kIfElif, "(N)", (yyvsp[(2) - (2)].obj)); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 41:

/* Line 1464 of yacc.c  */
#line 271 "parser.y"
    { (yyval.obj) = ctx->Call(kIfElse, "()"); CHECK((yyval.obj), (yyloc)); ;}
    break;

  case 42:

/* Line 1464 of yacc.c  */
#line 275 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("(NsN)", (yyvsp[(1) - (3)].obj), (yyvsp[(2) - (3)].str), (yyvsp[(3) - (3)].obj));
    ;}
    break;

  case 43:

/* Line 1464 of yacc.c  */
#line 278 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("(NsN)", (yyvsp[(1) - (3)].obj), (yyvsp[(2) - (3)].str), (yyvsp[(3) - (3)].obj));
    ;}
    break;

  case 44:

/* Line 1464 of yacc.c  */
#line 285 "parser.y"
    { (yyval.obj) = Py_BuildValue("(N)", (yyvsp[(2) - (4)].obj)); ;}
    break;

  case 45:

/* Line 1464 of yacc.c  */
#line 286 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (5)].obj), (yyvsp[(4) - (5)].obj)); ;}
    break;

  case 46:

/* Line 1464 of yacc.c  */
#line 287 "parser.y"
    {
      (yyval.obj) = Py_BuildValue("(NNN)", (yyvsp[(2) - (7)].obj), (yyvsp[(4) - (7)].obj), (yyvsp[(6) - (7)].obj));
    ;}
    break;

  case 47:

/* Line 1464 of yacc.c  */
#line 293 "parser.y"
    { (yyval.str) = "<"; ;}
    break;

  case 48:

/* Line 1464 of yacc.c  */
#line 294 "parser.y"
    { (yyval.str) = ">"; ;}
    break;

  case 49:

/* Line 1464 of yacc.c  */
#line 295 "parser.y"
    { (yyval.str) = "<="; ;}
    break;

  case 50:

/* Line 1464 of yacc.c  */
#line 296 "parser.y"
    { (yyval.str) = ">="; ;}
    break;

  case 51:

/* Line 1464 of yacc.c  */
#line 297 "parser.y"
    { (yyval.str) = "=="; ;}
    break;

  case 52:

/* Line 1464 of yacc.c  */
#line 298 "parser.y"
    { (yyval.str) = "!="; ;}
    break;

  case 53:

/* Line 1464 of yacc.c  */
#line 302 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 54:

/* Line 1464 of yacc.c  */
#line 306 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), ctx->Value(kAnything));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 55:

/* Line 1464 of yacc.c  */
#line 310 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (5)].obj), (yyvsp[(5) - (5)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 56:

/* Line 1464 of yacc.c  */
#line 317 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddImport, "(ON)", Py_None, (yyvsp[(2) - (2)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 57:

/* Line 1464 of yacc.c  */
#line 321 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddImport, "(NN)", (yyvsp[(2) - (4)].obj), (yyvsp[(4) - (4)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 58:

/* Line 1464 of yacc.c  */
#line 328 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 59:

/* Line 1464 of yacc.c  */
#line 329 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 61:

/* Line 1464 of yacc.c  */
#line 333 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 63:

/* Line 1464 of yacc.c  */
#line 338 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 64:

/* Line 1464 of yacc.c  */
#line 339 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 65:

/* Line 1464 of yacc.c  */
#line 343 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 66:

/* Line 1464 of yacc.c  */
#line 344 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 68:

/* Line 1464 of yacc.c  */
#line 349 "parser.y"
    { (yyval.obj) = PyString_FromString("NamedTuple"); ;}
    break;

  case 69:

/* Line 1464 of yacc.c  */
#line 350 "parser.y"
    { (yyval.obj) = PyString_FromString("TypeVar"); ;}
    break;

  case 70:

/* Line 1464 of yacc.c  */
#line 351 "parser.y"
    { (yyval.obj) = PyString_FromString("*"); ;}
    break;

  case 71:

/* Line 1464 of yacc.c  */
#line 352 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 72:

/* Line 1464 of yacc.c  */
#line 356 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddAliasOrConstant, "(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 73:

/* Line 1464 of yacc.c  */
#line 363 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddTypeVar, "(NN)", (yyvsp[(1) - (6)].obj), (yyvsp[(5) - (6)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 74:

/* Line 1464 of yacc.c  */
#line 370 "parser.y"
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

  case 75:

/* Line 1464 of yacc.c  */
#line 385 "parser.y"
    {
      // TODO(dbaum): Is PYTHONCODE necessary?
      (yyval.obj) = ctx->Call(kNewExternalFunction, "(NN)", (yyvsp[(1) - (4)].obj), (yyvsp[(3) - (4)].obj));
      // See comment above about why @2 is used as the start.
      (yyloc).first_line = (yylsp[(2) - (4)]).first_line;
      (yyloc).first_column = (yylsp[(2) - (4)]).first_column;
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 76:

/* Line 1464 of yacc.c  */
#line 396 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 77:

/* Line 1464 of yacc.c  */
#line 397 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 78:

/* Line 1464 of yacc.c  */
#line 401 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 79:

/* Line 1464 of yacc.c  */
#line 406 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 80:

/* Line 1464 of yacc.c  */
#line 407 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 81:

/* Line 1464 of yacc.c  */
#line 411 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 82:

/* Line 1464 of yacc.c  */
#line 412 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 83:

/* Line 1464 of yacc.c  */
#line 416 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NNN)", (yyvsp[(1) - (3)].obj), (yyvsp[(2) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 84:

/* Line 1464 of yacc.c  */
#line 417 "parser.y"
    { (yyval.obj) = Py_BuildValue("(sOO)", "*", Py_None, Py_None); ;}
    break;

  case 85:

/* Line 1464 of yacc.c  */
#line 418 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NNO)", (yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj), Py_None); ;}
    break;

  case 86:

/* Line 1464 of yacc.c  */
#line 419 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis) ;}
    break;

  case 87:

/* Line 1464 of yacc.c  */
#line 423 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 88:

/* Line 1464 of yacc.c  */
#line 424 "parser.y"
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 89:

/* Line 1464 of yacc.c  */
#line 428 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 90:

/* Line 1464 of yacc.c  */
#line 429 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 91:

/* Line 1464 of yacc.c  */
#line 430 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis); ;}
    break;

  case 92:

/* Line 1464 of yacc.c  */
#line 431 "parser.y"
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 93:

/* Line 1464 of yacc.c  */
#line 435 "parser.y"
    { (yyval.obj) = PyString_FromFormat("*%s", PyString_AsString((yyvsp[(2) - (2)].obj))); ;}
    break;

  case 94:

/* Line 1464 of yacc.c  */
#line 436 "parser.y"
    { (yyval.obj) = PyString_FromFormat("**%s", PyString_AsString((yyvsp[(3) - (3)].obj))); ;}
    break;

  case 95:

/* Line 1464 of yacc.c  */
#line 440 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 96:

/* Line 1464 of yacc.c  */
#line 441 "parser.y"
    { (yyval.obj) = ctx->Value(kAnything); ;}
    break;

  case 97:

/* Line 1464 of yacc.c  */
#line 445 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 98:

/* Line 1464 of yacc.c  */
#line 446 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 99:

/* Line 1464 of yacc.c  */
#line 450 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 100:

/* Line 1464 of yacc.c  */
#line 451 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 101:

/* Line 1464 of yacc.c  */
#line 455 "parser.y"
    { (yyval.obj) = (yyvsp[(3) - (4)].obj); ;}
    break;

  case 102:

/* Line 1464 of yacc.c  */
#line 456 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 107:

/* Line 1464 of yacc.c  */
#line 467 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 108:

/* Line 1464 of yacc.c  */
#line 468 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 109:

/* Line 1464 of yacc.c  */
#line 472 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 110:

/* Line 1464 of yacc.c  */
#line 473 "parser.y"
    { Py_DECREF((yyvsp[(2) - (2)].obj)); Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 111:

/* Line 1464 of yacc.c  */
#line 474 "parser.y"
    { Py_DECREF((yyvsp[(2) - (4)].obj)); Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 112:

/* Line 1464 of yacc.c  */
#line 478 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 113:

/* Line 1464 of yacc.c  */
#line 479 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 114:

/* Line 1464 of yacc.c  */
#line 483 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 115:

/* Line 1464 of yacc.c  */
#line 484 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis); ;}
    break;

  case 116:

/* Line 1464 of yacc.c  */
#line 488 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewType, "(N)", (yyvsp[(1) - (1)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 117:

/* Line 1464 of yacc.c  */
#line 492 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewType, "(NN)", (yyvsp[(1) - (4)].obj), (yyvsp[(3) - (4)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 118:

/* Line 1464 of yacc.c  */
#line 496 "parser.y"
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

  case 119:

/* Line 1464 of yacc.c  */
#line 506 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewNamedTuple, "(NN)", (yyvsp[(3) - (6)].obj), (yyvsp[(5) - (6)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 120:

/* Line 1464 of yacc.c  */
#line 510 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 121:

/* Line 1464 of yacc.c  */
#line 511 "parser.y"
    { (yyval.obj) = ctx->Call(kNewUnionType, "([NN])", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 122:

/* Line 1464 of yacc.c  */
#line 512 "parser.y"
    { (yyval.obj) = ctx->Value(kAnything); ;}
    break;

  case 123:

/* Line 1464 of yacc.c  */
#line 513 "parser.y"
    { (yyval.obj) = ctx->Value(kNothing); ;}
    break;

  case 124:

/* Line 1464 of yacc.c  */
#line 517 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 125:

/* Line 1464 of yacc.c  */
#line 518 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 126:

/* Line 1464 of yacc.c  */
#line 522 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 127:

/* Line 1464 of yacc.c  */
#line 523 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 128:

/* Line 1464 of yacc.c  */
#line 527 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(4) - (6)].obj)); ;}
    break;

  case 131:

/* Line 1464 of yacc.c  */
#line 536 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 132:

/* Line 1464 of yacc.c  */
#line 537 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 133:

/* Line 1464 of yacc.c  */
#line 541 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 134:

/* Line 1464 of yacc.c  */
#line 542 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 135:

/* Line 1464 of yacc.c  */
#line 547 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 136:

/* Line 1464 of yacc.c  */
#line 548 "parser.y"
    {
      PyString_Concat(&(yyvsp[(1) - (3)].obj), DOT_STRING);
      PyString_ConcatAndDel(&(yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      (yyval.obj) = (yyvsp[(1) - (3)].obj);
    ;}
    break;



/* Line 1464 of yacc.c  */
#line 3183 "pyi/parser.tab.cc"
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
#line 560 "parser.y"


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

