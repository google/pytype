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



#if ! defined YYSTYPE && ! defined YYSTYPE_IS_DECLARED
typedef union YYSTYPE
{

/* Line 214 of yacc.c  */
#line 58 "parser.y"

  PyObject* obj;
  const char* str;



/* Line 214 of yacc.c  */
#line 201 "pyi/parser.tab.cc"
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
#line 226 "pyi/parser.tab.cc"

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
#define YYLAST   437

/* YYNTOKENS -- Number of terminals.  */
#define YYNTOKENS  47
/* YYNNTS -- Number of nonterminals.  */
#define YYNNTS  65
/* YYNRULES -- Number of rules.  */
#define YYNRULES  169
/* YYNRULES -- Number of states.  */
#define YYNSTATES  314

/* YYTRANSLATE(YYLEX) -- Bison symbol number corresponding to YYLEX.  */
#define YYUNDEFTOK  2
#define YYMAXUTOK   288

#define YYTRANSLATE(YYX)						\
  ((unsigned int) (YYX) <= YYMAXUTOK ? yytranslate[YYX] : YYUNDEFTOK)

/* YYTRANSLATE[YYLEX] -- Bison symbol number corresponding to YYLEX.  */
static const yytype_uint8 yytranslate[] =
{
       0,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
      35,    36,    44,     2,    37,     2,    43,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,    34,     2,
      41,    38,    42,    46,    45,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,    39,     2,    40,     2,     2,     2,     2,     2,     2,
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
      25,    26,    27,    28,    29,    30,    31,    32,    33
};

#if YYDEBUG
/* YYPRHS[YYN] -- Index of the first RHS symbol of rule number YYN in
   YYRHS.  */
static const yytype_uint16 yyprhs[] =
{
       0,     0,     3,     6,    10,    12,    15,    18,    21,    24,
      27,    30,    33,    34,    36,    37,    44,    46,    50,    53,
      54,    58,    60,    62,    66,    69,    73,    78,    80,    82,
      85,    88,    91,    94,    95,   102,   104,   110,   117,   124,
     126,   132,   139,   142,   145,   147,   151,   155,   162,   169,
     173,   177,   181,   186,   192,   200,   202,   204,   206,   208,
     210,   212,   216,   220,   224,   228,   232,   238,   242,   248,
     251,   256,   261,   265,   267,   269,   273,   275,   278,   280,
     284,   289,   293,   295,   297,   299,   301,   303,   307,   311,
     319,   320,   323,   326,   331,   335,   337,   341,   350,   353,
     354,   358,   361,   362,   367,   369,   373,   375,   378,   380,
     383,   384,   387,   390,   393,   394,   397,   401,   404,   405,
     408,   414,   419,   421,   424,   428,   432,   438,   443,   448,
     449,   452,   454,   458,   461,   466,   470,   472,   474,   476,
     478,   483,   487,   494,   498,   502,   506,   508,   510,   515,
     518,   522,   524,   531,   533,   534,   536,   537,   541,   543,
     548,   551,   553,   557,   559,   563,   569,   571,   572,   574
};

/* YYRHS -- A `-1'-separated list of the rules' RHS.  */
static const yytype_int8 yyrhs[] =
{
      48,     0,    -1,    49,     0,    -1,    30,    49,     0,    -1,
      50,    -1,    50,    70,    -1,    50,    83,    -1,    50,    71,
      -1,    50,    78,    -1,    50,    52,    -1,    50,    79,    -1,
      50,    60,    -1,    -1,    93,    -1,    -1,     6,    53,    54,
      34,    51,    57,    -1,     3,    -1,    35,    55,    36,    -1,
      35,    36,    -1,    -1,    55,    37,    56,    -1,    56,    -1,
     100,    -1,     3,    38,   100,    -1,   111,    51,    -1,    28,
      58,    29,    -1,    28,    30,    58,    29,    -1,   111,    -1,
      59,    -1,    59,    70,    -1,    59,    78,    -1,    59,    83,
      -1,    59,    62,    -1,    -1,    61,    66,    34,    28,    50,
      29,    -1,    61,    -1,    64,    34,    28,    50,    29,    -1,
      61,    65,    34,    28,    50,    29,    -1,    63,    66,    34,
      28,    59,    29,    -1,    63,    -1,    64,    34,    28,    59,
      29,    -1,    63,    65,    34,    28,    59,    29,    -1,    10,
      67,    -1,     9,    67,    -1,     8,    -1,   108,    69,     3,
      -1,   108,    69,    68,    -1,   108,    39,   109,    40,    69,
       4,    -1,   108,    39,   109,    40,    69,    68,    -1,    67,
      12,    67,    -1,    67,    11,    67,    -1,    35,    67,    36,
      -1,    35,     4,    37,    36,    -1,    35,     4,    37,     4,
      36,    -1,    35,     4,    37,     4,    37,     4,    36,    -1,
      41,    -1,    42,    -1,    26,    -1,    27,    -1,    24,    -1,
      25,    -1,     3,    38,     4,    -1,     3,    38,    32,    -1,
       3,    38,    33,    -1,     3,    38,   107,    -1,     3,    38,
      23,    -1,     3,    38,    23,    31,   100,    -1,     3,    34,
     100,    -1,     3,    34,   100,    38,    23,    -1,    14,    72,
      -1,    15,    74,    14,    75,    -1,    15,    43,    14,    75,
      -1,    72,    37,    73,    -1,    73,    -1,   108,    -1,   108,
      16,     3,    -1,   108,    -1,    43,    74,    -1,    76,    -1,
      35,    76,    36,    -1,    35,    76,    37,    36,    -1,    76,
      37,    77,    -1,    77,    -1,     3,    -1,    19,    -1,    20,
      -1,    44,    -1,     3,    16,     3,    -1,     3,    38,   100,
      -1,     3,    38,    20,    35,     3,    80,    36,    -1,    -1,
      37,   106,    -1,    37,    81,    -1,    37,   106,    37,    81,
      -1,    81,    37,    82,    -1,    82,    -1,     3,    38,   100,
      -1,    84,     7,     3,    35,    86,    36,    92,    94,    -1,
      84,    85,    -1,    -1,    45,   108,    51,    -1,    87,   104,
      -1,    -1,    87,    37,    51,    88,    -1,    88,    -1,     3,
      89,    90,    -1,    44,    -1,    91,    89,    -1,    23,    -1,
      34,   100,    -1,    -1,    38,     3,    -1,    38,     4,    -1,
      38,    23,    -1,    -1,    44,     3,    -1,    44,    44,     3,
      -1,    21,   100,    -1,    -1,    31,     3,    -1,    34,    93,
      28,    96,    29,    -1,    34,    28,    96,    29,    -1,    95,
      -1,    34,   111,    -1,    34,   111,    93,    -1,    34,    93,
     111,    -1,    34,    93,    28,   111,    29,    -1,    34,    28,
     111,    29,    -1,    34,    28,    30,    29,    -1,    -1,    96,
      97,    -1,    97,    -1,     3,    22,   100,    -1,    17,   100,
      -1,    17,   100,    35,    36,    -1,    98,    37,    99,    -1,
      99,    -1,   100,    -1,    23,    -1,   108,    -1,   108,    39,
      98,    40,    -1,    39,   105,    40,    -1,    19,    35,     3,
      37,   101,    36,    -1,    35,   100,    36,    -1,   100,    12,
     100,    -1,   100,    11,   100,    -1,    46,    -1,    18,    -1,
      39,   102,   104,    40,    -1,    39,    40,    -1,   102,    37,
     103,    -1,   103,    -1,    35,     3,    37,   100,   104,    36,
      -1,    37,    -1,    -1,   106,    -1,    -1,   106,    37,   100,
      -1,   100,    -1,    35,   106,   104,    36,    -1,   100,    37,
      -1,     3,    -1,   108,    43,     3,    -1,     4,    -1,   110,
      34,   110,    -1,   110,    34,   110,    34,   110,    -1,     4,
      -1,    -1,    13,    -1,    23,    -1
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
     325,   329,   333,   337,   341,   345,   349,   353,   357,   364,
     368,   372,   381,   382,   385,   386,   391,   392,   399,   400,
     401,   405,   406,   410,   411,   412,   413,   414,   418,   422,
     429,   430,   431,   432,   436,   437,   441,   445,   463,   464,
     468,   472,   473,   485,   486,   490,   491,   492,   493,   497,
     498,   502,   503,   504,   505,   509,   510,   514,   515,   519,
     523,   524,   525,   529,   530,   531,   532,   533,   534,   535,
     539,   540,   544,   545,   546,   550,   551,   555,   556,   560,
     564,   568,   573,   577,   578,   579,   580,   581,   585,   586,
     590,   591,   595,   599,   600,   604,   605,   609,   610,   618,
     623,   627,   628,   636,   637,   642,   650,   651,   655,   656
};
#endif

#if YYDEBUG || YYERROR_VERBOSE || YYTOKEN_TABLE
/* YYTNAME[SYMBOL-NUM] -- String name of the symbol SYMBOL-NUM.
   First, the terminals, then, starting at YYNTOKENS, nonterminals.  */
static const char *const yytname[] =
{
  "\"end of file\"", "error", "$undefined", "NAME", "NUMBER", "LEXERROR",
  "CLASS", "DEF", "ELSE", "ELIF", "IF", "OR", "AND", "PASS", "IMPORT",
  "FROM", "AS", "RAISE", "NOTHING", "NAMEDTUPLE", "TYPEVAR", "ARROW",
  "COLONEQUALS", "ELLIPSIS", "EQ", "NE", "LE", "GE", "INDENT", "DEDENT",
  "TRIPLEQUOTED", "TYPECOMMENT", "BYTESTRING", "UNICODESTRING", "':'",
  "'('", "')'", "','", "'='", "'['", "']'", "'<'", "'>'", "'.'", "'*'",
  "'@'", "'?'", "$accept", "start", "unit", "alldefs", "maybe_type_ignore",
  "classdef", "class_name", "parents", "parent_list", "parent",
  "maybe_class_funcs", "class_funcs", "funcdefs", "if_stmt",
  "if_and_elifs", "class_if_stmt", "class_if_and_elifs", "if_cond",
  "elif_cond", "else_cond", "condition", "version_tuple", "condition_op",
  "constantdef", "importdef", "import_items", "import_item", "import_name",
  "from_list", "from_items", "from_item", "alias_or_constant",
  "typevardef", "typevar_args", "typevar_kwargs", "typevar_kwarg",
  "funcdef", "decorators", "decorator", "params", "param_list", "param",
  "param_type", "param_default", "param_star_name", "return", "typeignore",
  "maybe_body", "empty_body", "body", "body_stmt", "type_parameters",
  "type_parameter", "type", "named_tuple_fields", "named_tuple_field_list",
  "named_tuple_field", "maybe_comma", "maybe_type_list", "type_list",
  "type_tuple_literal", "dotted_name", "getitem_key", "maybe_number",
  "pass_or_ellipsis", 0
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
     285,   286,   287,   288,    58,    40,    41,    44,    61,    91,
      93,    60,    62,    46,    42,    64,    63
};
# endif

/* YYR1[YYN] -- Symbol number of symbol that rule YYN derives.  */
static const yytype_uint8 yyr1[] =
{
       0,    47,    48,    48,    49,    50,    50,    50,    50,    50,
      50,    50,    50,    51,    51,    52,    53,    54,    54,    54,
      55,    55,    56,    56,    57,    57,    57,    58,    58,    59,
      59,    59,    59,    59,    60,    60,    61,    61,    62,    62,
      63,    63,    64,    65,    66,    67,    67,    67,    67,    67,
      67,    67,    68,    68,    68,    69,    69,    69,    69,    69,
      69,    70,    70,    70,    70,    70,    70,    70,    70,    71,
      71,    71,    72,    72,    73,    73,    74,    74,    75,    75,
      75,    76,    76,    77,    77,    77,    77,    77,    78,    79,
      80,    80,    80,    80,    81,    81,    82,    83,    84,    84,
      85,    86,    86,    87,    87,    88,    88,    88,    88,    89,
      89,    90,    90,    90,    90,    91,    91,    92,    92,    93,
      94,    94,    94,    95,    95,    95,    95,    95,    95,    95,
      96,    96,    97,    97,    97,    98,    98,    99,    99,   100,
     100,   100,   100,   100,   100,   100,   100,   100,   101,   101,
     102,   102,   103,   104,   104,   105,   105,   106,   106,   107,
     107,   108,   108,   109,   109,   109,   110,   110,   111,   111
};

/* YYR2[YYN] -- Number of symbols composing right hand side of rule YYN.  */
static const yytype_uint8 yyr2[] =
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
       3,     1,     6,     1,     0,     1,     0,     3,     1,     4,
       2,     1,     3,     1,     3,     5,     1,     0,     1,     1
};

/* YYDEFACT[STATE-NAME] -- Default rule to reduce with in state
   STATE-NUM when YYTABLE doesn't specify something else to do.  Zero
   means the default is an error.  */
static const yytype_uint8 yydefact[] =
{
      12,    12,     0,     0,    99,     0,     1,     2,     0,     0,
       0,     0,     0,     9,    11,    35,     0,     5,     7,     8,
      10,     6,     0,     3,     0,     0,    16,    19,   161,     0,
      42,     0,    69,    73,    74,     0,     0,    76,    44,     0,
       0,     0,     0,     0,     0,    98,   147,     0,     0,   156,
     146,    67,   139,    61,     0,    65,    62,    63,     0,    88,
      64,     0,     0,     0,     0,     0,    59,    60,    57,    58,
     167,    55,    56,     0,     0,     0,     0,     0,     0,    77,
       0,    43,     0,     0,    12,     0,    14,     0,     0,   158,
       0,   155,     0,     0,     0,     0,     0,     0,   158,   154,
     160,   161,    18,     0,    21,    22,    14,    51,    50,    49,
     163,     0,     0,   162,    45,     0,    46,    72,    75,    83,
      84,    85,     0,    86,    71,    78,    82,    70,    12,    12,
      99,   102,     0,   100,    13,     0,   143,   141,     0,   145,
     144,    68,   138,     0,   136,   137,    90,    66,   153,     0,
       0,    17,     0,     0,     0,   167,     0,     0,     0,     0,
      99,    99,    36,   110,   108,   106,     0,   154,   104,   110,
     119,     0,   157,     0,   140,     0,     0,   159,    23,    20,
     168,   169,    33,    15,    14,     0,   166,   164,     0,    87,
      79,     0,    81,    37,    34,     0,   114,   115,     0,   118,
      14,   101,   107,     0,     0,   135,   161,    92,    95,    91,
      89,    33,     0,    99,    27,    24,    47,    48,   167,     0,
      52,    80,   109,     0,   105,   116,     0,   129,     0,     0,
     149,   154,   151,   142,     0,     0,     0,     0,    25,     0,
      32,    39,     0,    29,    30,    31,   165,    53,     0,   111,
     112,   113,   117,     0,    97,   122,   103,     0,   153,     0,
      96,     0,    94,    93,    26,     0,     0,     0,     0,     0,
       0,     0,   123,     0,   150,   148,     0,     0,    33,    54,
       0,     0,     0,     0,   131,     0,     0,   125,   124,   154,
      33,    33,    99,     0,   133,   128,   121,   130,   127,     0,
       0,   153,     0,    99,    99,    40,   132,     0,   120,   126,
     152,    41,    38,   134
};

/* YYDEFGOTO[NTERM-NUM].  */
static const yytype_int16 yydefgoto[] =
{
      -1,     2,     3,     4,   133,    13,    27,    62,   103,   104,
     183,   212,   213,    14,    15,   240,   241,    16,    40,    41,
      30,   116,    74,    17,    18,    32,    33,    79,   124,   125,
     126,    19,    20,   176,   207,   208,    21,    22,    45,   166,
     167,   168,   196,   224,   169,   227,   134,   254,   255,   283,
     284,   143,   144,   172,   204,   231,   232,   149,    90,    91,
      60,    52,   111,   112,   214
};

/* YYPACT[STATE-NUM] -- Index in YYTABLE of the portion describing
   STATE-NUM.  */
#define YYPACT_NINF -231
static const yytype_int16 yypact[] =
{
      85,  -231,    27,   140,   290,   155,  -231,  -231,   241,    41,
      17,   173,    44,  -231,  -231,   293,   124,  -231,  -231,  -231,
    -231,  -231,     9,  -231,   126,   104,  -231,   149,  -231,    17,
     297,   239,   169,  -231,   117,    74,   205,   202,  -231,    17,
     243,   249,   257,   229,   173,  -231,  -231,   212,   126,   126,
    -231,     7,   255,  -231,   216,   236,  -231,  -231,   126,    79,
    -231,    95,   272,   219,    17,    17,  -231,  -231,  -231,  -231,
     291,  -231,  -231,   314,    18,   173,   315,    11,    75,  -231,
      11,   297,   292,   294,  -231,   286,   217,   316,   223,   299,
     283,   287,   126,   126,   302,   129,   323,   126,   223,   295,
    -231,   289,  -231,   189,  -231,   299,   298,  -231,   318,  -231,
     300,   288,   301,  -231,  -231,   327,  -231,  -231,  -231,   317,
    -231,  -231,    19,  -231,  -231,   303,  -231,  -231,  -231,  -231,
     185,   143,   333,  -231,  -231,   304,  -231,  -231,   126,   325,
    -231,  -231,  -231,    72,  -231,   299,   305,   299,   126,   307,
     126,  -231,   135,   263,   246,   334,   308,   336,   277,    19,
     198,   214,  -231,   310,  -231,    14,   311,   309,  -231,   310,
    -231,   312,   299,   129,  -231,   159,   313,  -231,   299,  -231,
    -231,  -231,   231,  -231,   298,    29,  -231,   319,    45,  -231,
    -231,    40,  -231,  -231,  -231,   126,   320,  -231,   345,   329,
       4,  -231,  -231,   145,   321,  -231,   322,   324,  -231,   326,
    -231,   245,   330,   153,  -231,  -231,  -231,  -231,   334,   279,
    -231,  -231,   299,    25,  -231,  -231,   126,   328,   143,   349,
    -231,   331,  -231,  -231,   126,   351,   159,   335,  -231,   265,
    -231,   293,   332,  -231,  -231,  -231,  -231,  -231,   352,  -231,
    -231,  -231,   299,   261,  -231,  -231,  -231,   337,   338,   339,
     299,   322,  -231,   324,  -231,    47,   341,   342,   343,   344,
     156,   284,   298,   126,  -231,  -231,   350,   353,  -231,  -231,
     347,   126,   348,   180,  -231,   354,   233,  -231,  -231,   178,
    -231,  -231,   193,   126,   227,  -231,  -231,  -231,  -231,   204,
     355,  -231,   346,   208,   213,  -231,   299,   356,  -231,  -231,
    -231,  -231,  -231,  -231
};

/* YYPGOTO[NTERM-NUM].  */
static const yytype_int16 yypgoto[] =
{
    -231,  -231,   364,   -72,  -101,  -231,  -231,  -231,  -231,   203,
    -231,   161,   -38,  -231,  -231,  -231,  -231,  -207,   144,   146,
     128,   182,   232,  -203,  -231,  -231,   340,   358,   357,   266,
     -49,  -200,  -231,  -231,   154,   158,  -198,  -231,  -231,  -231,
    -231,   163,   220,  -231,  -231,  -231,  -230,  -231,  -231,   108,
    -188,  -231,   222,   -24,  -231,  -231,   138,  -164,  -231,   -54,
    -231,    -3,  -231,  -144,  -151
};

/* YYTABLE[YYPACT[STATE-NUM]].  What to do in state STATE-NUM.  If
   positive, shift that token.  If negative, reduce the rule which
   number is the opposite.  If zero, do what YYDEFACT says.
   If YYTABLE_NINF, syntax error.  */
#define YYTABLE_NINF -167
static const yytype_int16 yytable[] =
{
      51,    59,   184,   201,    99,   153,   242,    31,    34,    37,
     243,   187,   130,   244,   119,   245,    43,   197,    92,    93,
      28,   114,   119,   271,    88,    89,    31,     6,   249,   250,
     120,   121,    37,   216,    98,   132,    31,   105,   120,   121,
    -153,    86,   288,   119,    26,    94,   122,    28,   251,   219,
      28,    53,    29,   115,    44,   123,   160,   161,   198,   120,
     121,    31,    31,   123,   115,    46,    47,   259,   139,   140,
      55,   145,    34,   147,   246,    37,   221,    28,    28,    56,
      57,   220,    58,   215,   123,   242,    49,    35,    77,   243,
      92,    93,   244,    50,   245,   297,   242,   242,   101,   228,
     243,   243,   272,   244,   244,   245,   245,    28,    53,   173,
     192,   297,   174,    46,    47,     1,   100,    78,    78,   285,
     287,   209,    46,    47,    54,   302,   178,    55,   105,    28,
      48,   102,    28,    76,    49,   300,    56,    57,   101,    58,
       7,    50,   192,    49,    46,    47,   163,    46,    47,   145,
      50,    89,   142,    46,    47,    23,   239,    63,    42,   280,
      73,    48,   206,    10,    48,    49,   164,    81,    49,   180,
      48,   222,    50,   281,    49,    50,    28,    46,    47,   181,
     229,    50,   -28,   280,    61,   230,   282,   165,     8,    92,
      93,     9,   108,   109,    48,    10,   239,   281,    49,    11,
      12,     8,   252,    10,     9,    50,    75,   280,    10,   296,
     260,   239,    11,    12,   162,   301,   239,     8,    10,    80,
       9,   281,   305,    10,    10,   151,   152,   193,    11,    12,
      64,    65,    85,   308,    92,    93,   280,   311,    92,    93,
     292,    59,   312,   194,   180,    73,   180,    87,   132,   289,
     281,    96,   303,   304,   181,   107,   181,   294,   180,   136,
      73,   211,   307,    66,    67,    68,    69,    97,   181,   306,
      66,    67,    68,    69,   180,    24,   180,    82,    70,    25,
      71,    72,    73,    83,   181,    84,   181,    71,    72,   270,
      -4,   182,   132,     8,    95,   110,     9,   180,    73,    24,
      10,    38,    39,   265,    11,    12,   106,   181,    64,    65,
      92,    93,   286,   190,   191,   247,   248,   113,   118,   135,
     128,   131,   129,   137,   138,   141,   146,   150,   154,   132,
      65,   156,   148,   157,  -166,   155,   170,    93,   186,   189,
     159,   171,   175,   177,   195,   188,   200,   199,   225,   210,
     226,   203,   257,   218,   261,   179,   269,   233,   223,   238,
     234,   235,   253,   236,   264,     5,   268,   217,   258,   293,
      36,   278,   237,   229,   273,   276,   277,   295,   290,   275,
     279,   291,   310,   298,   309,   266,   185,   267,   158,   202,
     263,   256,   313,   262,   299,   205,   274,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,   117,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,   127
};

static const yytype_int16 yycheck[] =
{
      24,    25,   153,   167,    58,   106,   213,    10,    11,    12,
     213,   155,    84,   213,     3,   213,     7,     3,    11,    12,
       3,     3,     3,   253,    48,    49,    29,     0,     3,     4,
      19,    20,    35,     4,    58,    31,    39,    61,    19,    20,
      36,    44,   272,     3,     3,    38,    35,     3,    23,     4,
       3,     4,    35,    35,    45,    44,   128,   129,    44,    19,
      20,    64,    65,    44,    35,    18,    19,   231,    92,    93,
      23,    95,    75,    97,   218,    78,    36,     3,     3,    32,
      33,    36,    35,   184,    44,   292,    39,    43,    14,   292,
      11,    12,   292,    46,   292,   283,   303,   304,     3,   200,
     303,   304,   253,   303,   304,   303,   304,     3,     4,    37,
     159,   299,    40,    18,    19,    30,    37,    43,    43,   270,
     271,   175,    18,    19,    20,   289,   150,    23,   152,     3,
      35,    36,     3,    16,    39,   286,    32,    33,     3,    35,
       0,    46,   191,    39,    18,    19,     3,    18,    19,   173,
      46,   175,    23,    18,    19,     0,     3,    29,    34,     3,
      43,    35,     3,    10,    35,    39,    23,    39,    39,    13,
      35,   195,    46,    17,    39,    46,     3,    18,    19,    23,
      35,    46,    29,     3,    35,    40,    30,    44,     3,    11,
      12,     6,    64,    65,    35,    10,     3,    17,    39,    14,
      15,     3,   226,    10,     6,    46,    37,     3,    10,    29,
     234,     3,    14,    15,    29,    37,     3,     3,    10,    14,
       6,    17,    29,    10,    10,    36,    37,    29,    14,    15,
      11,    12,     3,    29,    11,    12,     3,    29,    11,    12,
     278,   265,    29,    29,    13,    43,    13,    35,    31,   273,
      17,    35,   290,   291,    23,    36,    23,   281,    13,    36,
      43,    30,    35,    24,    25,    26,    27,    31,    23,   293,
      24,    25,    26,    27,    13,    34,    13,    34,    39,    38,
      41,    42,    43,    34,    23,    28,    23,    41,    42,    28,
       0,    28,    31,     3,    39,     4,     6,    13,    43,    34,
      10,     8,     9,    38,    14,    15,    34,    23,    11,    12,
      11,    12,    28,    36,    37,    36,    37,     3,     3,     3,
      28,    35,    28,    40,    37,    23,     3,    38,    40,    31,
      12,     4,    37,    16,    34,    34,     3,    12,     4,     3,
      37,    37,    37,    36,    34,    37,    37,    36,     3,    36,
      21,    39,     3,    34,     3,   152,     4,    36,    38,    29,
      38,    37,    34,    37,    29,     1,    34,   185,    37,    22,
      12,    28,   211,    35,    37,    34,    34,    29,    28,    40,
      36,    28,    36,    29,    29,   241,   154,   241,   122,   169,
     236,   228,    36,   235,   286,   173,   258,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    75,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    80
};

/* YYSTOS[STATE-NUM] -- The (internal number of the) accessing
   symbol of state STATE-NUM.  */
static const yytype_uint8 yystos[] =
{
       0,    30,    48,    49,    50,    49,     0,     0,     3,     6,
      10,    14,    15,    52,    60,    61,    64,    70,    71,    78,
      79,    83,    84,     0,    34,    38,     3,    53,     3,    35,
      67,   108,    72,    73,   108,    43,    74,   108,     8,     9,
      65,    66,    34,     7,    45,    85,    18,    19,    35,    39,
      46,   100,   108,     4,    20,    23,    32,    33,    35,   100,
     107,    35,    54,    67,    11,    12,    24,    25,    26,    27,
      39,    41,    42,    43,    69,    37,    16,    14,    43,    74,
      14,    67,    34,    34,    28,     3,   108,    35,   100,   100,
     105,   106,    11,    12,    38,    39,    35,    31,   100,   106,
      37,     3,    36,    55,    56,   100,    34,    36,    67,    67,
       4,   109,   110,     3,     3,    35,    68,    73,     3,     3,
      19,    20,    35,    44,    75,    76,    77,    75,    28,    28,
      50,    35,    31,    51,    93,     3,    36,    40,    37,   100,
     100,    23,    23,    98,    99,   100,     3,   100,    37,   104,
      38,    36,    37,    51,    40,    34,     4,    16,    76,    37,
      50,    50,    29,     3,    23,    44,    86,    87,    88,    91,
       3,    37,   100,    37,    40,    37,    80,    36,   100,    56,
      13,    23,    28,    57,   111,    69,     4,   110,    37,     3,
      36,    37,    77,    29,    29,    34,    89,     3,    44,    36,
      37,   104,    89,    39,   101,    99,     3,    81,    82,   106,
      36,    30,    58,    59,   111,    51,     4,    68,    34,     4,
      36,    36,   100,    38,    90,     3,    21,    92,    51,    35,
      40,   102,   103,    36,    38,    37,    37,    58,    29,     3,
      62,    63,    64,    70,    78,    83,   110,    36,    37,     3,
       4,    23,   100,    34,    94,    95,    88,     3,    37,   104,
     100,     3,    82,    81,    29,    38,    65,    66,    34,     4,
      28,    93,   111,    37,   103,    40,    34,    34,    28,    36,
       3,    17,    30,    96,    97,   111,    28,   111,    93,   100,
      28,    28,    59,    22,   100,    29,    29,    97,    29,    96,
     111,    37,   104,    59,    59,    29,   100,    35,    29,    29,
      36,    29,    29,    36
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
#line 1476 "pyi/parser.tab.cc"
	break;
      case 4: /* "NUMBER" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1485 "pyi/parser.tab.cc"
	break;
      case 5: /* "LEXERROR" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1494 "pyi/parser.tab.cc"
	break;
      case 48: /* "start" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1503 "pyi/parser.tab.cc"
	break;
      case 49: /* "unit" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1512 "pyi/parser.tab.cc"
	break;
      case 50: /* "alldefs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1521 "pyi/parser.tab.cc"
	break;
      case 52: /* "classdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1530 "pyi/parser.tab.cc"
	break;
      case 53: /* "class_name" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1539 "pyi/parser.tab.cc"
	break;
      case 54: /* "parents" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1548 "pyi/parser.tab.cc"
	break;
      case 55: /* "parent_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1557 "pyi/parser.tab.cc"
	break;
      case 56: /* "parent" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1566 "pyi/parser.tab.cc"
	break;
      case 57: /* "maybe_class_funcs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1575 "pyi/parser.tab.cc"
	break;
      case 58: /* "class_funcs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1584 "pyi/parser.tab.cc"
	break;
      case 59: /* "funcdefs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1593 "pyi/parser.tab.cc"
	break;
      case 60: /* "if_stmt" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1602 "pyi/parser.tab.cc"
	break;
      case 61: /* "if_and_elifs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1611 "pyi/parser.tab.cc"
	break;
      case 62: /* "class_if_stmt" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1620 "pyi/parser.tab.cc"
	break;
      case 63: /* "class_if_and_elifs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1629 "pyi/parser.tab.cc"
	break;
      case 64: /* "if_cond" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1638 "pyi/parser.tab.cc"
	break;
      case 65: /* "elif_cond" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1647 "pyi/parser.tab.cc"
	break;
      case 66: /* "else_cond" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1656 "pyi/parser.tab.cc"
	break;
      case 67: /* "condition" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1665 "pyi/parser.tab.cc"
	break;
      case 68: /* "version_tuple" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1674 "pyi/parser.tab.cc"
	break;
      case 69: /* "condition_op" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->str)); };

/* Line 1009 of yacc.c  */
#line 1683 "pyi/parser.tab.cc"
	break;
      case 70: /* "constantdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1692 "pyi/parser.tab.cc"
	break;
      case 71: /* "importdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1701 "pyi/parser.tab.cc"
	break;
      case 72: /* "import_items" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1710 "pyi/parser.tab.cc"
	break;
      case 73: /* "import_item" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1719 "pyi/parser.tab.cc"
	break;
      case 74: /* "import_name" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1728 "pyi/parser.tab.cc"
	break;
      case 75: /* "from_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1737 "pyi/parser.tab.cc"
	break;
      case 76: /* "from_items" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1746 "pyi/parser.tab.cc"
	break;
      case 77: /* "from_item" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1755 "pyi/parser.tab.cc"
	break;
      case 78: /* "alias_or_constant" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1764 "pyi/parser.tab.cc"
	break;
      case 79: /* "typevardef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1773 "pyi/parser.tab.cc"
	break;
      case 80: /* "typevar_args" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1782 "pyi/parser.tab.cc"
	break;
      case 81: /* "typevar_kwargs" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1791 "pyi/parser.tab.cc"
	break;
      case 82: /* "typevar_kwarg" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1800 "pyi/parser.tab.cc"
	break;
      case 83: /* "funcdef" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1809 "pyi/parser.tab.cc"
	break;
      case 84: /* "decorators" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1818 "pyi/parser.tab.cc"
	break;
      case 85: /* "decorator" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1827 "pyi/parser.tab.cc"
	break;
      case 86: /* "params" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1836 "pyi/parser.tab.cc"
	break;
      case 87: /* "param_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1845 "pyi/parser.tab.cc"
	break;
      case 88: /* "param" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1854 "pyi/parser.tab.cc"
	break;
      case 89: /* "param_type" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1863 "pyi/parser.tab.cc"
	break;
      case 90: /* "param_default" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1872 "pyi/parser.tab.cc"
	break;
      case 91: /* "param_star_name" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1881 "pyi/parser.tab.cc"
	break;
      case 92: /* "return" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1890 "pyi/parser.tab.cc"
	break;
      case 94: /* "maybe_body" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1899 "pyi/parser.tab.cc"
	break;
      case 96: /* "body" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1908 "pyi/parser.tab.cc"
	break;
      case 97: /* "body_stmt" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1917 "pyi/parser.tab.cc"
	break;
      case 98: /* "type_parameters" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1926 "pyi/parser.tab.cc"
	break;
      case 99: /* "type_parameter" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1935 "pyi/parser.tab.cc"
	break;
      case 100: /* "type" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1944 "pyi/parser.tab.cc"
	break;
      case 101: /* "named_tuple_fields" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1953 "pyi/parser.tab.cc"
	break;
      case 102: /* "named_tuple_field_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1962 "pyi/parser.tab.cc"
	break;
      case 103: /* "named_tuple_field" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1971 "pyi/parser.tab.cc"
	break;
      case 105: /* "maybe_type_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1980 "pyi/parser.tab.cc"
	break;
      case 106: /* "type_list" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1989 "pyi/parser.tab.cc"
	break;
      case 107: /* "type_tuple_literal" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 1998 "pyi/parser.tab.cc"
	break;
      case 108: /* "dotted_name" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 2007 "pyi/parser.tab.cc"
	break;
      case 109: /* "getitem_key" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 2016 "pyi/parser.tab.cc"
	break;
      case 110: /* "maybe_number" */

/* Line 1009 of yacc.c  */
#line 97 "parser.y"
	{ Py_CLEAR((yyvaluep->obj)); };

/* Line 1009 of yacc.c  */
#line 2025 "pyi/parser.tab.cc"
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
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 65:

/* Line 1464 of yacc.c  */
#line 345 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), ctx->Value(kAnything));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 66:

/* Line 1464 of yacc.c  */
#line 349 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (5)].obj), (yyvsp[(5) - (5)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 67:

/* Line 1464 of yacc.c  */
#line 353 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 68:

/* Line 1464 of yacc.c  */
#line 357 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[(1) - (5)].obj), (yyvsp[(3) - (5)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 69:

/* Line 1464 of yacc.c  */
#line 364 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddImport, "(ON)", Py_None, (yyvsp[(2) - (2)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 70:

/* Line 1464 of yacc.c  */
#line 368 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddImport, "(NN)", (yyvsp[(2) - (4)].obj), (yyvsp[(4) - (4)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 71:

/* Line 1464 of yacc.c  */
#line 372 "parser.y"
    {
      // Special-case "from . import" and pass in a __PACKAGE__ token that
      // the Python parser code will rewrite to the current package name.
      (yyval.obj) = ctx->Call(kAddImport, "(sN)", "__PACKAGE__", (yyvsp[(4) - (4)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 72:

/* Line 1464 of yacc.c  */
#line 381 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 73:

/* Line 1464 of yacc.c  */
#line 382 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 75:

/* Line 1464 of yacc.c  */
#line 386 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 77:

/* Line 1464 of yacc.c  */
#line 392 "parser.y"
    {
      (yyval.obj) = PyString_FromFormat(".%s", PyString_AsString((yyvsp[(2) - (2)].obj)));
      Py_DECREF((yyvsp[(2) - (2)].obj));
    ;}
    break;

  case 79:

/* Line 1464 of yacc.c  */
#line 400 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 80:

/* Line 1464 of yacc.c  */
#line 401 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 81:

/* Line 1464 of yacc.c  */
#line 405 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 82:

/* Line 1464 of yacc.c  */
#line 406 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 84:

/* Line 1464 of yacc.c  */
#line 411 "parser.y"
    { (yyval.obj) = PyString_FromString("NamedTuple"); ;}
    break;

  case 85:

/* Line 1464 of yacc.c  */
#line 412 "parser.y"
    { (yyval.obj) = PyString_FromString("TypeVar"); ;}
    break;

  case 86:

/* Line 1464 of yacc.c  */
#line 413 "parser.y"
    { (yyval.obj) = PyString_FromString("*"); ;}
    break;

  case 87:

/* Line 1464 of yacc.c  */
#line 414 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 88:

/* Line 1464 of yacc.c  */
#line 418 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 89:

/* Line 1464 of yacc.c  */
#line 422 "parser.y"
    {
      (yyval.obj) = ctx->Call(kAddTypeVar, "(NNN)", (yyvsp[(1) - (7)].obj), (yyvsp[(5) - (7)].obj), (yyvsp[(6) - (7)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 90:

/* Line 1464 of yacc.c  */
#line 429 "parser.y"
    { (yyval.obj) = Py_BuildValue("(OO)", Py_None, Py_None); ;}
    break;

  case 91:

/* Line 1464 of yacc.c  */
#line 430 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NO)", (yyvsp[(2) - (2)].obj), Py_None); ;}
    break;

  case 92:

/* Line 1464 of yacc.c  */
#line 431 "parser.y"
    { (yyval.obj) = Py_BuildValue("(ON)", Py_None, (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 93:

/* Line 1464 of yacc.c  */
#line 432 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (4)].obj), (yyvsp[(4) - (4)].obj)); ;}
    break;

  case 94:

/* Line 1464 of yacc.c  */
#line 436 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 95:

/* Line 1464 of yacc.c  */
#line 437 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 96:

/* Line 1464 of yacc.c  */
#line 441 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 97:

/* Line 1464 of yacc.c  */
#line 445 "parser.y"
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

  case 98:

/* Line 1464 of yacc.c  */
#line 463 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 99:

/* Line 1464 of yacc.c  */
#line 464 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 100:

/* Line 1464 of yacc.c  */
#line 468 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 101:

/* Line 1464 of yacc.c  */
#line 472 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (2)].obj); ;}
    break;

  case 102:

/* Line 1464 of yacc.c  */
#line 473 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 103:

/* Line 1464 of yacc.c  */
#line 485 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (4)].obj), (yyvsp[(4) - (4)].obj)); ;}
    break;

  case 104:

/* Line 1464 of yacc.c  */
#line 486 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 105:

/* Line 1464 of yacc.c  */
#line 490 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NNN)", (yyvsp[(1) - (3)].obj), (yyvsp[(2) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 106:

/* Line 1464 of yacc.c  */
#line 491 "parser.y"
    { (yyval.obj) = Py_BuildValue("(sOO)", "*", Py_None, Py_None); ;}
    break;

  case 107:

/* Line 1464 of yacc.c  */
#line 492 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NNO)", (yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj), Py_None); ;}
    break;

  case 108:

/* Line 1464 of yacc.c  */
#line 493 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis) ;}
    break;

  case 109:

/* Line 1464 of yacc.c  */
#line 497 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 110:

/* Line 1464 of yacc.c  */
#line 498 "parser.y"
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 111:

/* Line 1464 of yacc.c  */
#line 502 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 112:

/* Line 1464 of yacc.c  */
#line 503 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 113:

/* Line 1464 of yacc.c  */
#line 504 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis); ;}
    break;

  case 114:

/* Line 1464 of yacc.c  */
#line 505 "parser.y"
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; ;}
    break;

  case 115:

/* Line 1464 of yacc.c  */
#line 509 "parser.y"
    { (yyval.obj) = PyString_FromFormat("*%s", PyString_AsString((yyvsp[(2) - (2)].obj))); ;}
    break;

  case 116:

/* Line 1464 of yacc.c  */
#line 510 "parser.y"
    { (yyval.obj) = PyString_FromFormat("**%s", PyString_AsString((yyvsp[(3) - (3)].obj))); ;}
    break;

  case 117:

/* Line 1464 of yacc.c  */
#line 514 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 118:

/* Line 1464 of yacc.c  */
#line 515 "parser.y"
    { (yyval.obj) = ctx->Value(kAnything); ;}
    break;

  case 119:

/* Line 1464 of yacc.c  */
#line 519 "parser.y"
    { Py_DecRef((yyvsp[(2) - (2)].obj)); ;}
    break;

  case 120:

/* Line 1464 of yacc.c  */
#line 523 "parser.y"
    { (yyval.obj) = (yyvsp[(4) - (5)].obj); ;}
    break;

  case 121:

/* Line 1464 of yacc.c  */
#line 524 "parser.y"
    { (yyval.obj) = (yyvsp[(3) - (4)].obj); ;}
    break;

  case 122:

/* Line 1464 of yacc.c  */
#line 525 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 130:

/* Line 1464 of yacc.c  */
#line 539 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (2)].obj), (yyvsp[(2) - (2)].obj)); ;}
    break;

  case 131:

/* Line 1464 of yacc.c  */
#line 540 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 132:

/* Line 1464 of yacc.c  */
#line 544 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 133:

/* Line 1464 of yacc.c  */
#line 545 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (2)].obj); ;}
    break;

  case 134:

/* Line 1464 of yacc.c  */
#line 546 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 135:

/* Line 1464 of yacc.c  */
#line 550 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 136:

/* Line 1464 of yacc.c  */
#line 551 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 137:

/* Line 1464 of yacc.c  */
#line 555 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 138:

/* Line 1464 of yacc.c  */
#line 556 "parser.y"
    { (yyval.obj) = ctx->Value(kEllipsis); ;}
    break;

  case 139:

/* Line 1464 of yacc.c  */
#line 560 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewType, "(N)", (yyvsp[(1) - (1)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 140:

/* Line 1464 of yacc.c  */
#line 564 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewType, "(NN)", (yyvsp[(1) - (4)].obj), (yyvsp[(3) - (4)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 141:

/* Line 1464 of yacc.c  */
#line 568 "parser.y"
    {
      // This rule is needed for Callable[[...], ...]
      (yyval.obj) = ctx->Call(kNewType, "(sN)", "tuple", (yyvsp[(2) - (3)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 142:

/* Line 1464 of yacc.c  */
#line 573 "parser.y"
    {
      (yyval.obj) = ctx->Call(kNewNamedTuple, "(NN)", (yyvsp[(3) - (6)].obj), (yyvsp[(5) - (6)].obj));
      CHECK((yyval.obj), (yyloc));
    ;}
    break;

  case 143:

/* Line 1464 of yacc.c  */
#line 577 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (3)].obj); ;}
    break;

  case 144:

/* Line 1464 of yacc.c  */
#line 578 "parser.y"
    { (yyval.obj) = ctx->Call(kNewIntersectionType, "([NN])", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 145:

/* Line 1464 of yacc.c  */
#line 579 "parser.y"
    { (yyval.obj) = ctx->Call(kNewUnionType, "([NN])", (yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 146:

/* Line 1464 of yacc.c  */
#line 580 "parser.y"
    { (yyval.obj) = ctx->Value(kAnything); ;}
    break;

  case 147:

/* Line 1464 of yacc.c  */
#line 581 "parser.y"
    { (yyval.obj) = ctx->Value(kNothing); ;}
    break;

  case 148:

/* Line 1464 of yacc.c  */
#line 585 "parser.y"
    { (yyval.obj) = (yyvsp[(2) - (4)].obj); ;}
    break;

  case 149:

/* Line 1464 of yacc.c  */
#line 586 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 150:

/* Line 1464 of yacc.c  */
#line 590 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 151:

/* Line 1464 of yacc.c  */
#line 591 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 152:

/* Line 1464 of yacc.c  */
#line 595 "parser.y"
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[(2) - (6)].obj), (yyvsp[(4) - (6)].obj)); ;}
    break;

  case 155:

/* Line 1464 of yacc.c  */
#line 604 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 156:

/* Line 1464 of yacc.c  */
#line 605 "parser.y"
    { (yyval.obj) = PyList_New(0); ;}
    break;

  case 157:

/* Line 1464 of yacc.c  */
#line 609 "parser.y"
    { (yyval.obj) = AppendList((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj)); ;}
    break;

  case 158:

/* Line 1464 of yacc.c  */
#line 610 "parser.y"
    { (yyval.obj) = StartList((yyvsp[(1) - (1)].obj)); ;}
    break;

  case 159:

/* Line 1464 of yacc.c  */
#line 618 "parser.y"
    {
      Py_DECREF((yyvsp[(2) - (4)].obj));
      (yyval.obj) = ctx->Value(kTuple);
    ;}
    break;

  case 160:

/* Line 1464 of yacc.c  */
#line 623 "parser.y"
    { (yyval.obj) = ctx->Value(kTuple); ;}
    break;

  case 161:

/* Line 1464 of yacc.c  */
#line 627 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 162:

/* Line 1464 of yacc.c  */
#line 628 "parser.y"
    {
      PyString_Concat(&(yyvsp[(1) - (3)].obj), DOT_STRING);
      PyString_ConcatAndDel(&(yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj));
      (yyval.obj) = (yyvsp[(1) - (3)].obj);
    ;}
    break;

  case 163:

/* Line 1464 of yacc.c  */
#line 636 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 164:

/* Line 1464 of yacc.c  */
#line 637 "parser.y"
    {
      PyObject* slice = PySlice_New((yyvsp[(1) - (3)].obj), (yyvsp[(3) - (3)].obj), NULL);
      CHECK(slice, (yyloc));
      (yyval.obj) = slice;
    ;}
    break;

  case 165:

/* Line 1464 of yacc.c  */
#line 642 "parser.y"
    {
      PyObject* slice = PySlice_New((yyvsp[(1) - (5)].obj), (yyvsp[(3) - (5)].obj), (yyvsp[(5) - (5)].obj));
      CHECK(slice, (yyloc));
      (yyval.obj) = slice;
    ;}
    break;

  case 166:

/* Line 1464 of yacc.c  */
#line 650 "parser.y"
    { (yyval.obj) = (yyvsp[(1) - (1)].obj); ;}
    break;

  case 167:

/* Line 1464 of yacc.c  */
#line 651 "parser.y"
    { (yyval.obj) = NULL; ;}
    break;



/* Line 1464 of yacc.c  */
#line 3518 "pyi/parser.tab.cc"
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
#line 659 "parser.y"


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

