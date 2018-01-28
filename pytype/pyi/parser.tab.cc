/* A Bison parser, made by GNU Bison 3.0.4.  */

/* Bison implementation for Yacc-like parsers in C

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
#define YYBISON_VERSION "3.0.4"

/* Skeleton name.  */
#define YYSKELETON_NAME "yacc.c"

/* Pure parsers.  */
#define YYPURE 1

/* Push parsers.  */
#define YYPUSH 0

/* Pull parsers.  */
#define YYPULL 1


/* Substitute the variable and function names.  */
#define yyparse         pytypeparse
#define yylex           pytypelex
#define yyerror         pytypeerror
#define yydebug         pytypedebug
#define yynerrs         pytypenerrs


/* Copy the first part of user declarations.  */
#line 29 "parser.y" /* yacc.c:339  */

#include "lexer.h"
#include "parser.h"

namespace pytype {
// Note that the pytype namespace is not closed until the trailing block of
// code after the parser skeleton is emitted.  Thus the entire parser (except
// for a few #defines) is in the pytype namespace.

namespace {
#if PY_MAJOR_VERSION >= 3
PyObject* DOT_STRING = PyUnicode_FromString(".");
#else
PyObject* DOT_STRING = PyString_FromString(".");
#endif

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


#line 108 "parser.tab.cc" /* yacc.c:339  */

# ifndef YY_NULLPTR
#  if defined __cplusplus && 201103L <= __cplusplus
#   define YY_NULLPTR nullptr
#  else
#   define YY_NULLPTR 0
#  endif
# endif

/* Enabling verbose error messages.  */
#ifdef YYERROR_VERBOSE
# undef YYERROR_VERBOSE
# define YYERROR_VERBOSE 1
#else
# define YYERROR_VERBOSE 1
#endif

/* In a future release of Bison, this section will be replaced
   by #include "parser.tab.h".  */
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
#line 19 "parser.y" /* yacc.c:355  */

#include <Python.h>

class Context;

#line 144 "parser.tab.cc" /* yacc.c:355  */

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
#line 65 "parser.y" /* yacc.c:355  */

  PyObject* obj;
  const char* str;

#line 196 "parser.tab.cc" /* yacc.c:355  */
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

/* Copy the second part of user declarations.  */

#line 226 "parser.tab.cc" /* yacc.c:358  */

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
#else
typedef signed char yytype_int8;
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
# elif ! defined YYSIZE_T
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
#   define YY_(Msgid) dgettext ("bison-runtime", Msgid)
#  endif
# endif
# ifndef YY_
#  define YY_(Msgid) Msgid
# endif
#endif

#ifndef YY_ATTRIBUTE
# if (defined __GNUC__                                               \
      && (2 < __GNUC__ || (__GNUC__ == 2 && 96 <= __GNUC_MINOR__)))  \
     || defined __SUNPRO_C && 0x5110 <= __SUNPRO_C
#  define YY_ATTRIBUTE(Spec) __attribute__(Spec)
# else
#  define YY_ATTRIBUTE(Spec) /* empty */
# endif
#endif

#ifndef YY_ATTRIBUTE_PURE
# define YY_ATTRIBUTE_PURE   YY_ATTRIBUTE ((__pure__))
#endif

#ifndef YY_ATTRIBUTE_UNUSED
# define YY_ATTRIBUTE_UNUSED YY_ATTRIBUTE ((__unused__))
#endif

#if !defined _Noreturn \
     && (!defined __STDC_VERSION__ || __STDC_VERSION__ < 201112)
# if defined _MSC_VER && 1200 <= _MSC_VER
#  define _Noreturn __declspec (noreturn)
# else
#  define _Noreturn YY_ATTRIBUTE ((__noreturn__))
# endif
#endif

/* Suppress unused-variable warnings by "using" E.  */
#if ! defined lint || defined __GNUC__
# define YYUSE(E) ((void) (E))
#else
# define YYUSE(E) /* empty */
#endif

#if defined __GNUC__ && 407 <= __GNUC__ * 100 + __GNUC_MINOR__
/* Suppress an incorrect diagnostic about yylval being uninitialized.  */
# define YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN \
    _Pragma ("GCC diagnostic push") \
    _Pragma ("GCC diagnostic ignored \"-Wuninitialized\"")\
    _Pragma ("GCC diagnostic ignored \"-Wmaybe-uninitialized\"")
# define YY_IGNORE_MAYBE_UNINITIALIZED_END \
    _Pragma ("GCC diagnostic pop")
#else
# define YY_INITIAL_VALUE(Value) Value
#endif
#ifndef YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
# define YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
# define YY_IGNORE_MAYBE_UNINITIALIZED_END
#endif
#ifndef YY_INITIAL_VALUE
# define YY_INITIAL_VALUE(Value) /* Nothing. */
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
#    if ! defined _ALLOCA_H && ! defined EXIT_SUCCESS
#     include <stdlib.h> /* INFRINGES ON USER NAME SPACE */
      /* Use EXIT_SUCCESS as a witness for stdlib.h.  */
#     ifndef EXIT_SUCCESS
#      define EXIT_SUCCESS 0
#     endif
#    endif
#   endif
#  endif
# endif

# ifdef YYSTACK_ALLOC
   /* Pacify GCC's 'empty if-body' warning.  */
#  define YYSTACK_FREE(Ptr) do { /* empty */; } while (0)
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
#  if (defined __cplusplus && ! defined EXIT_SUCCESS \
       && ! ((defined YYMALLOC || defined malloc) \
             && (defined YYFREE || defined free)))
#   include <stdlib.h> /* INFRINGES ON USER NAME SPACE */
#   ifndef EXIT_SUCCESS
#    define EXIT_SUCCESS 0
#   endif
#  endif
#  ifndef YYMALLOC
#   define YYMALLOC malloc
#   if ! defined malloc && ! defined EXIT_SUCCESS
void *malloc (YYSIZE_T); /* INFRINGES ON USER NAME SPACE */
#   endif
#  endif
#  ifndef YYFREE
#   define YYFREE free
#   if ! defined free && ! defined EXIT_SUCCESS
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

# define YYCOPY_NEEDED 1

/* Relocate STACK from its old location to the new one.  The
   local variables YYSIZE and YYSTACKSIZE give the old and new number of
   elements in the stack, and YYPTR gives the new location of the
   stack.  Advance YYPTR to a properly aligned location for the next
   stack.  */
# define YYSTACK_RELOCATE(Stack_alloc, Stack)                           \
    do                                                                  \
      {                                                                 \
        YYSIZE_T yynewbytes;                                            \
        YYCOPY (&yyptr->Stack_alloc, Stack, yysize);                    \
        Stack = &yyptr->Stack_alloc;                                    \
        yynewbytes = yystacksize * sizeof (*Stack) + YYSTACK_GAP_MAXIMUM; \
        yyptr += yynewbytes / sizeof (*yyptr);                          \
      }                                                                 \
    while (0)

#endif

#if defined YYCOPY_NEEDED && YYCOPY_NEEDED
/* Copy COUNT objects from SRC to DST.  The source and destination do
   not overlap.  */
# ifndef YYCOPY
#  if defined __GNUC__ && 1 < __GNUC__
#   define YYCOPY(Dst, Src, Count) \
      __builtin_memcpy (Dst, Src, (Count) * sizeof (*(Src)))
#  else
#   define YYCOPY(Dst, Src, Count)              \
      do                                        \
        {                                       \
          YYSIZE_T yyi;                         \
          for (yyi = 0; yyi < (Count); yyi++)   \
            (Dst)[yyi] = (Src)[yyi];            \
        }                                       \
      while (0)
#  endif
# endif
#endif /* !YYCOPY_NEEDED */

/* YYFINAL -- State number of the termination state.  */
#define YYFINAL  6
/* YYLAST -- Last index in YYTABLE.  */
#define YYLAST   417

/* YYNTOKENS -- Number of terminals.  */
#define YYNTOKENS  47
/* YYNNTS -- Number of nonterminals.  */
#define YYNNTS  64
/* YYNRULES -- Number of rules.  */
#define YYNRULES  166
/* YYNSTATES -- Number of states.  */
#define YYNSTATES  306

/* YYTRANSLATE[YYX] -- Symbol number corresponding to YYX as returned
   by yylex, with out-of-bounds checking.  */
#define YYUNDEFTOK  2
#define YYMAXUTOK   288

#define YYTRANSLATE(YYX)                                                \
  ((unsigned int) (YYX) <= YYMAXUTOK ? yytranslate[YYX] : YYUNDEFTOK)

/* YYTRANSLATE[TOKEN-NUM] -- Symbol number corresponding to TOKEN-NUM
   as returned by yylex, without out-of-bounds checking.  */
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
  /* YYRLINE[YYN] -- Source line where rule number YYN was defined.  */
static const yytype_uint16 yyrline[] =
{
       0,   138,   138,   139,   143,   147,   148,   149,   150,   156,
     157,   158,   163,   167,   168,   171,   178,   189,   190,   191,
     195,   196,   200,   201,   205,   206,   207,   211,   212,   216,
     217,   222,   223,   228,   233,   236,   241,   245,   264,   267,
     272,   276,   288,   292,   296,   300,   303,   306,   309,   312,
     313,   314,   319,   320,   321,   327,   328,   329,   330,   331,
     332,   336,   340,   344,   348,   352,   356,   360,   367,   371,
     375,   384,   385,   388,   389,   394,   395,   406,   407,   408,
     412,   413,   417,   418,   425,   432,   439,   443,   447,   454,
     455,   456,   457,   461,   462,   466,   470,   488,   489,   493,
     497,   498,   510,   511,   515,   516,   517,   518,   522,   523,
     527,   528,   529,   530,   534,   541,   551,   552,   556,   560,
     561,   562,   566,   567,   568,   569,   570,   571,   572,   576,
     577,   581,   582,   583,   587,   588,   592,   593,   597,   601,
     605,   610,   614,   615,   616,   617,   618,   622,   623,   627,
     628,   632,   636,   637,   641,   642,   646,   647,   652,   653,
     667,   668,   673,   681,   682,   686,   687
};
#endif

#if YYDEBUG || YYERROR_VERBOSE || 1
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
  "dotted_name", "getitem_key", "maybe_number", "pass_or_ellipsis", YY_NULLPTR
};
#endif

# ifdef YYPRINT
/* YYTOKNUM[NUM] -- (External) token number corresponding to the
   (internal) symbol number NUM (which must be that of a token).  */
static const yytype_uint16 yytoknum[] =
{
       0,   256,   257,   258,   259,   260,   261,   262,   263,   264,
     265,   266,   267,   268,   269,   270,   271,   272,   273,   274,
     275,   276,   277,   278,   279,   280,   281,   282,   283,   284,
     285,   286,   287,   288,    58,    40,    41,    44,    61,    91,
      93,    60,    62,    46,    42,    64,    63
};
# endif

#define YYPACT_NINF -271

#define yypact_value_is_default(Yystate) \
  (!!((Yystate) == (-271)))

#define YYTABLE_NINF -164

#define yytable_value_is_error(Yytable_value) \
  0

  /* YYPACT[STATE-NUM] -- Index in YYTABLE of the portion describing
     STATE-NUM.  */
static const yytype_int16 yypact[] =
{
      58,  -271,    39,   126,   283,   146,  -271,  -271,   144,   109,
      16,   166,    15,  -271,  -271,    21,   141,  -271,  -271,  -271,
    -271,  -271,     9,  -271,   110,    24,  -271,   156,  -271,    16,
      11,   238,   169,  -271,    61,    12,   198,   201,  -271,    16,
     196,   204,   222,   270,   166,  -271,  -271,   261,   110,   110,
    -271,   165,   235,  -271,   274,   244,  -271,  -271,   247,    14,
     258,   148,    16,    16,  -271,  -271,  -271,  -271,   290,  -271,
    -271,   307,    17,   166,   308,    70,    31,  -271,    70,    11,
     284,   285,  -271,   279,   164,   312,   220,   247,   276,   280,
     110,   110,   295,   112,   316,   110,   282,  -271,   267,  -271,
     247,   291,  -271,   309,  -271,   289,   286,   293,  -271,  -271,
     320,  -271,  -271,  -271,   313,  -271,  -271,   145,  -271,  -271,
     288,  -271,  -271,  -271,  -271,   195,    59,   325,  -271,  -271,
     294,  -271,  -271,   110,   318,  -271,  -271,  -271,   262,  -271,
     247,   296,   247,   110,  -271,   122,    88,   243,   328,   297,
     332,   269,   145,   205,   211,  -271,   302,  -271,     4,   301,
     303,  -271,   302,  -271,   299,   247,   112,  -271,   135,   305,
     247,  -271,  -271,  -271,   223,  -271,   291,     5,  -271,   310,
      32,  -271,  -271,   152,  -271,  -271,  -271,   110,   304,  -271,
     336,   322,   240,  -271,  -271,   183,   311,  -271,   314,   317,
    -271,   319,  -271,   111,   321,    81,  -271,  -271,  -271,  -271,
     328,   271,  -271,  -271,   247,   176,  -271,  -271,   110,   315,
      59,   342,  -271,   323,  -271,  -271,   110,   343,   135,   324,
    -271,   257,  -271,    21,   327,  -271,  -271,  -271,  -271,  -271,
     344,  -271,  -271,  -271,   247,   259,  -271,  -271,  -271,   326,
     329,   330,   247,   314,  -271,   317,  -271,   104,   331,   333,
     334,   335,   170,   232,   291,   110,  -271,  -271,   338,   340,
    -271,  -271,   337,   110,   345,   103,  -271,   346,   234,  -271,
    -271,   155,  -271,  -271,   187,   110,   231,  -271,  -271,  -271,
    -271,   210,   347,  -271,   341,   219,   225,  -271,   247,   348,
    -271,  -271,  -271,  -271,  -271,  -271
};

  /* YYDEFACT[STATE-NUM] -- Default reduction number in state STATE-NUM.
     Performed when YYTABLE does not specify something else to do.  Zero
     means the default is an error.  */
static const yytype_uint8 yydefact[] =
{
      12,    12,     0,     0,    98,     0,     1,     2,     0,     0,
       0,     0,     0,     9,    11,    35,     0,     5,     7,     8,
      10,     6,     0,     3,     0,     0,    16,    19,   158,     0,
      42,     0,    68,    72,    73,     0,     0,    75,    44,     0,
       0,     0,     0,     0,     0,    97,   146,     0,     0,   155,
     145,    66,   138,    61,     0,    64,    62,    63,    87,     0,
       0,     0,     0,     0,    59,    60,    57,    58,   164,    55,
      56,     0,     0,     0,     0,     0,     0,    76,     0,    43,
       0,     0,    12,     0,    14,     0,     0,   157,     0,   154,
       0,     0,     0,     0,     0,     0,   158,    18,     0,    21,
      22,    14,    51,    50,    49,   160,     0,     0,   159,    45,
       0,    46,    71,    74,    82,    83,    84,     0,    85,    70,
      77,    81,    69,    12,    12,    98,   101,     0,    99,    13,
       0,   142,   140,     0,   144,   143,    67,   137,     0,   135,
     136,    89,    65,     0,    17,     0,     0,     0,   164,     0,
       0,     0,     0,    98,    98,    36,   109,   107,   105,     0,
     153,   103,   109,   118,     0,   156,     0,   139,     0,     0,
      23,    20,   165,   166,    33,    15,    14,     0,   163,   161,
       0,    86,    78,     0,    80,    37,    34,     0,   113,   114,
       0,   117,    14,   100,   106,     0,     0,   134,   158,    91,
      94,    90,    88,    33,     0,    98,    27,    24,    47,    48,
     164,     0,    52,    79,   108,     0,   104,   115,     0,   128,
       0,     0,   148,   153,   150,   141,     0,     0,     0,     0,
      25,     0,    32,    39,     0,    29,    30,    31,   162,    53,
       0,   110,   111,   112,   116,     0,    96,   121,   102,     0,
     152,     0,    95,     0,    93,    92,    26,     0,     0,     0,
       0,     0,     0,     0,   122,     0,   149,   147,     0,     0,
      33,    54,     0,     0,     0,     0,   130,     0,     0,   124,
     123,   153,    33,    33,    98,     0,   132,   127,   120,   129,
     126,     0,     0,   152,     0,    98,    98,    40,   131,     0,
     119,   125,   151,    41,    38,   133
};

  /* YYPGOTO[NTERM-NUM].  */
static const yytype_int16 yypgoto[] =
{
    -271,  -271,   350,   -44,   -90,  -271,  -271,  -271,  -271,   212,
    -271,   175,    18,  -271,  -271,  -271,  -271,  -203,   125,   136,
     123,   178,   226,  -201,  -271,  -271,   306,   360,   339,   263,
    -107,  -199,  -271,  -271,   153,   158,  -197,  -271,  -271,  -271,
    -271,   162,   221,  -271,  -271,  -271,   -12,  -271,  -271,   108,
    -270,  -271,   224,   -24,  -271,  -271,   137,  -220,  -271,   227,
       2,  -271,  -138,  -145
};

  /* YYDEFGOTO[NTERM-NUM].  */
static const yytype_int16 yydefgoto[] =
{
      -1,     2,     3,     4,   128,    13,    27,    60,    98,    99,
     175,   204,   205,    14,    15,   232,   233,    16,    40,    41,
      30,   111,    72,    17,    18,    32,    33,    77,   119,   120,
     121,    19,    20,   169,   199,   200,    21,    22,    45,   159,
     160,   161,   188,   216,   162,   219,   129,   246,   247,   275,
     276,   138,   139,    58,   196,   223,   224,   193,    88,    89,
      52,   106,   107,   206
};

  /* YYTABLE[YYPACT[STATE-NUM]] -- What to do in state STATE-NUM.  If
     positive, shift that token.  If negative, reduce the rule whose
     number is the opposite.  If YYTABLE_NINF, syntax error.  */
static const yytype_int16 yytable[] =
{
      51,   176,   234,   251,   235,   289,   236,   189,   237,   208,
     179,   146,    31,    34,    37,    28,    43,    96,    28,    28,
     109,   289,    62,    63,    86,    87,    75,    28,    53,    38,
      39,    31,    46,    47,    28,   100,   211,    37,   125,     6,
     110,    31,    46,    47,    54,   184,    84,    55,   190,    48,
      97,    29,   110,    49,    44,    76,    56,    57,    35,    48,
      50,   294,   156,    49,    31,    31,   134,   135,   212,   140,
      50,   142,   238,   114,    76,    34,   184,    74,    37,   153,
     154,   234,   157,   235,   231,   236,   207,   237,     1,   115,
     116,    10,   234,   234,   235,   235,   236,   236,   237,   237,
     264,   172,   220,   158,    71,   117,   272,    28,    53,   165,
     -28,   173,    26,    28,   118,    28,   174,   277,   279,   170,
     273,   100,    46,    47,   172,    96,     7,    55,    46,    47,
      46,    47,   288,   292,   173,   137,    56,    57,   198,    48,
      46,    47,   140,    49,    87,    48,    23,    48,   114,    49,
      50,    49,    61,    46,    47,   114,    50,    48,    50,    62,
      63,    49,    79,   214,   115,   116,    90,    91,    50,    28,
      48,   115,   116,   272,    49,    42,    90,    91,    24,   241,
     242,    50,    25,   172,   102,   103,   104,   273,   213,   118,
     231,    59,   293,   173,   244,   127,   118,    10,     8,   243,
     274,     9,   252,    92,   165,    10,    73,    71,     8,    11,
      12,     9,    78,   272,     8,    10,   297,     9,   221,    11,
      12,    10,   231,   222,   155,    11,    12,   273,   231,    10,
      80,    90,    91,   263,   185,    10,   172,   272,    81,   300,
     186,   281,    90,    91,    71,   172,   173,   172,   303,   286,
      82,   273,   280,   203,   304,   173,   131,   173,    90,    91,
     278,   298,    64,    65,    66,    67,   299,    64,    65,    66,
      67,   127,   172,    83,    93,    95,  -152,    68,    71,    69,
      70,    71,   173,    -4,    69,    70,     8,   262,   284,     9,
     127,    24,   101,    10,   105,   257,    85,    11,    12,   166,
     295,   296,   167,   144,   145,   182,   183,   239,   240,    94,
     108,   113,   123,   124,   126,   130,   132,   133,   136,   141,
     143,    63,   127,  -163,   149,   152,   147,   148,   163,   150,
      91,   164,   178,   168,   180,   181,   187,   191,   195,   217,
     192,   202,   215,   218,   210,   249,   253,   225,   261,   245,
     230,     5,   226,   256,   227,   209,   228,   171,   258,   285,
     250,   260,   270,   265,   221,   268,   282,   269,   283,   259,
     267,   271,    36,   177,   287,   290,   301,   302,   229,   112,
     151,   255,   248,   194,   305,   254,   291,   266,     0,     0,
     197,     0,     0,     0,     0,   201,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,   122
};

static const yytype_int16 yycheck[] =
{
      24,   146,   205,   223,   205,   275,   205,     3,   205,     4,
     148,   101,    10,    11,    12,     3,     7,     3,     3,     3,
       3,   291,    11,    12,    48,    49,    14,     3,     4,     8,
       9,    29,    18,    19,     3,    59,     4,    35,    82,     0,
      35,    39,    18,    19,    20,   152,    44,    23,    44,    35,
      36,    35,    35,    39,    45,    43,    32,    33,    43,    35,
      46,   281,     3,    39,    62,    63,    90,    91,    36,    93,
      46,    95,   210,     3,    43,    73,   183,    16,    76,   123,
     124,   284,    23,   284,     3,   284,   176,   284,    30,    19,
      20,    10,   295,   296,   295,   296,   295,   296,   295,   296,
     245,    13,   192,    44,    43,    35,     3,     3,     4,   133,
      29,    23,     3,     3,    44,     3,    28,   262,   263,   143,
      17,   145,    18,    19,    13,     3,     0,    23,    18,    19,
      18,    19,    29,   278,    23,    23,    32,    33,     3,    35,
      18,    19,   166,    39,   168,    35,     0,    35,     3,    39,
      46,    39,    29,    18,    19,     3,    46,    35,    46,    11,
      12,    39,    39,   187,    19,    20,    11,    12,    46,     3,
      35,    19,    20,     3,    39,    34,    11,    12,    34,     3,
       4,    46,    38,    13,    36,    62,    63,    17,    36,    44,
       3,    35,    37,    23,   218,    31,    44,    10,     3,    23,
      30,     6,   226,    38,   228,    10,    37,    43,     3,    14,
      15,     6,    14,     3,     3,    10,    29,     6,    35,    14,
      15,    10,     3,    40,    29,    14,    15,    17,     3,    10,
      34,    11,    12,   245,    29,    10,    13,     3,    34,    29,
      29,   265,    11,    12,    43,    13,    23,    13,    29,   273,
      28,    17,   264,    30,    29,    23,    36,    23,    11,    12,
      28,   285,    24,    25,    26,    27,    35,    24,    25,    26,
      27,    31,    13,     3,    39,    31,    36,    39,    43,    41,
      42,    43,    23,     0,    41,    42,     3,    28,   270,     6,
      31,    34,    34,    10,     4,    38,    35,    14,    15,    37,
     282,   283,    40,    36,    37,    36,    37,    36,    37,    35,
       3,     3,    28,    28,    35,     3,    40,    37,    23,     3,
      38,    12,    31,    34,     4,    37,    40,    34,     3,    16,
      12,    37,     4,    37,    37,     3,    34,    36,    39,     3,
      37,    36,    38,    21,    34,     3,     3,    36,     4,    34,
      29,     1,    38,    29,    37,   177,    37,   145,   233,    22,
      37,    34,    28,    37,    35,    34,    28,    34,    28,   233,
      40,    36,    12,   147,    29,    29,    29,    36,   203,    73,
     117,   228,   220,   162,    36,   227,   278,   250,    -1,    -1,
     166,    -1,    -1,    -1,    -1,   168,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    78
};

  /* YYSTOS[STATE-NUM] -- The (internal number of the) accessing
     symbol of state STATE-NUM.  */
static const yytype_uint8 yystos[] =
{
       0,    30,    48,    49,    50,    49,     0,     0,     3,     6,
      10,    14,    15,    52,    60,    61,    64,    70,    71,    78,
      79,    83,    84,     0,    34,    38,     3,    53,     3,    35,
      67,   107,    72,    73,   107,    43,    74,   107,     8,     9,
      65,    66,    34,     7,    45,    85,    18,    19,    35,    39,
      46,   100,   107,     4,    20,    23,    32,    33,   100,    35,
      54,    67,    11,    12,    24,    25,    26,    27,    39,    41,
      42,    43,    69,    37,    16,    14,    43,    74,    14,    67,
      34,    34,    28,     3,   107,    35,   100,   100,   105,   106,
      11,    12,    38,    39,    35,    31,     3,    36,    55,    56,
     100,    34,    36,    67,    67,     4,   108,   109,     3,     3,
      35,    68,    73,     3,     3,    19,    20,    35,    44,    75,
      76,    77,    75,    28,    28,    50,    35,    31,    51,    93,
       3,    36,    40,    37,   100,   100,    23,    23,    98,    99,
     100,     3,   100,    38,    36,    37,    51,    40,    34,     4,
      16,    76,    37,    50,    50,    29,     3,    23,    44,    86,
      87,    88,    91,     3,    37,   100,    37,    40,    37,    80,
     100,    56,    13,    23,    28,    57,   110,    69,     4,   109,
      37,     3,    36,    37,    77,    29,    29,    34,    89,     3,
      44,    36,    37,   104,    89,    39,   101,    99,     3,    81,
      82,   106,    36,    30,    58,    59,   110,    51,     4,    68,
      34,     4,    36,    36,   100,    38,    90,     3,    21,    92,
      51,    35,    40,   102,   103,    36,    38,    37,    37,    58,
      29,     3,    62,    63,    64,    70,    78,    83,   109,    36,
      37,     3,     4,    23,   100,    34,    94,    95,    88,     3,
      37,   104,   100,     3,    82,    81,    29,    38,    65,    66,
      34,     4,    28,    93,   110,    37,   103,    40,    34,    34,
      28,    36,     3,    17,    30,    96,    97,   110,    28,   110,
      93,   100,    28,    28,    59,    22,   100,    29,    29,    97,
      29,    96,   110,    37,   104,    59,    59,    29,   100,    35,
      29,    29,    36,    29,    29,    36
};

  /* YYR1[YYN] -- Symbol number of symbol that rule YYN derives.  */
static const yytype_uint8 yyr1[] =
{
       0,    47,    48,    48,    49,    50,    50,    50,    50,    50,
      50,    50,    50,    51,    51,    52,    53,    54,    54,    54,
      55,    55,    56,    56,    57,    57,    57,    58,    58,    59,
      59,    59,    59,    59,    60,    60,    61,    61,    62,    62,
      63,    63,    64,    65,    66,    67,    67,    67,    67,    67,
      67,    67,    68,    68,    68,    69,    69,    69,    69,    69,
      69,    70,    70,    70,    70,    70,    70,    70,    71,    71,
      71,    72,    72,    73,    73,    74,    74,    75,    75,    75,
      76,    76,    77,    77,    77,    77,    77,    78,    79,    80,
      80,    80,    80,    81,    81,    82,    83,    84,    84,    85,
      86,    86,    87,    87,    88,    88,    88,    88,    89,    89,
      90,    90,    90,    90,    91,    91,    92,    92,    93,    94,
      94,    94,    95,    95,    95,    95,    95,    95,    95,    96,
      96,    97,    97,    97,    98,    98,    99,    99,   100,   100,
     100,   100,   100,   100,   100,   100,   100,   101,   101,   102,
     102,   103,   104,   104,   105,   105,   106,   106,   107,   107,
     108,   108,   108,   109,   109,   110,   110
};

  /* YYR2[YYN] -- Number of symbols on the right hand side of rule YYN.  */
static const yytype_uint8 yyr2[] =
{
       0,     2,     2,     3,     1,     2,     2,     2,     2,     2,
       2,     2,     0,     1,     0,     6,     1,     3,     2,     0,
       3,     1,     1,     3,     2,     3,     4,     1,     1,     2,
       2,     2,     2,     0,     6,     1,     5,     6,     6,     1,
       5,     6,     2,     2,     1,     3,     3,     6,     6,     3,
       3,     3,     4,     5,     7,     1,     1,     1,     1,     1,
       1,     3,     3,     3,     3,     5,     3,     5,     2,     4,
       4,     3,     1,     1,     3,     1,     2,     1,     3,     4,
       3,     1,     1,     1,     1,     1,     3,     3,     7,     0,
       2,     2,     4,     3,     1,     3,     8,     2,     0,     3,
       2,     0,     4,     1,     3,     1,     2,     1,     2,     0,
       2,     2,     2,     0,     2,     3,     2,     0,     2,     5,
       4,     1,     2,     3,     3,     5,     4,     4,     0,     2,
       1,     3,     2,     4,     3,     1,     1,     1,     1,     4,
       3,     6,     3,     3,     3,     1,     1,     4,     2,     3,
       1,     6,     1,     0,     1,     0,     3,     1,     1,     3,
       1,     3,     5,     1,     0,     1,     1
};


#define yyerrok         (yyerrstatus = 0)
#define yyclearin       (yychar = YYEMPTY)
#define YYEMPTY         (-2)
#define YYEOF           0

#define YYACCEPT        goto yyacceptlab
#define YYABORT         goto yyabortlab
#define YYERROR         goto yyerrorlab


#define YYRECOVERING()  (!!yyerrstatus)

#define YYBACKUP(Token, Value)                                  \
do                                                              \
  if (yychar == YYEMPTY)                                        \
    {                                                           \
      yychar = (Token);                                         \
      yylval = (Value);                                         \
      YYPOPSTACK (yylen);                                       \
      yystate = *yyssp;                                         \
      goto yybackup;                                            \
    }                                                           \
  else                                                          \
    {                                                           \
      yyerror (&yylloc, scanner, ctx, YY_("syntax error: cannot back up")); \
      YYERROR;                                                  \
    }                                                           \
while (0)

/* Error token number */
#define YYTERROR        1
#define YYERRCODE       256


/* YYLLOC_DEFAULT -- Set CURRENT to span from RHS[1] to RHS[N].
   If N is 0, then set CURRENT to the empty location which ends
   the previous symbol: RHS[0] (always defined).  */

#ifndef YYLLOC_DEFAULT
# define YYLLOC_DEFAULT(Current, Rhs, N)                                \
    do                                                                  \
      if (N)                                                            \
        {                                                               \
          (Current).first_line   = YYRHSLOC (Rhs, 1).first_line;        \
          (Current).first_column = YYRHSLOC (Rhs, 1).first_column;      \
          (Current).last_line    = YYRHSLOC (Rhs, N).last_line;         \
          (Current).last_column  = YYRHSLOC (Rhs, N).last_column;       \
        }                                                               \
      else                                                              \
        {                                                               \
          (Current).first_line   = (Current).last_line   =              \
            YYRHSLOC (Rhs, 0).last_line;                                \
          (Current).first_column = (Current).last_column =              \
            YYRHSLOC (Rhs, 0).last_column;                              \
        }                                                               \
    while (0)
#endif

#define YYRHSLOC(Rhs, K) ((Rhs)[K])


/* Enable debugging if requested.  */
#if YYDEBUG

# ifndef YYFPRINTF
#  include <stdio.h> /* INFRINGES ON USER NAME SPACE */
#  define YYFPRINTF fprintf
# endif

# define YYDPRINTF(Args)                        \
do {                                            \
  if (yydebug)                                  \
    YYFPRINTF Args;                             \
} while (0)


/* YY_LOCATION_PRINT -- Print the location on the stream.
   This macro was not mandated originally: define only if we know
   we won't break user code: when these are the locations we know.  */

#ifndef YY_LOCATION_PRINT
# if defined YYLTYPE_IS_TRIVIAL && YYLTYPE_IS_TRIVIAL

/* Print *YYLOCP on YYO.  Private, do not rely on its existence. */

YY_ATTRIBUTE_UNUSED
static unsigned
yy_location_print_ (FILE *yyo, YYLTYPE const * const yylocp)
{
  unsigned res = 0;
  int end_col = 0 != yylocp->last_column ? yylocp->last_column - 1 : 0;
  if (0 <= yylocp->first_line)
    {
      res += YYFPRINTF (yyo, "%d", yylocp->first_line);
      if (0 <= yylocp->first_column)
        res += YYFPRINTF (yyo, ".%d", yylocp->first_column);
    }
  if (0 <= yylocp->last_line)
    {
      if (yylocp->first_line < yylocp->last_line)
        {
          res += YYFPRINTF (yyo, "-%d", yylocp->last_line);
          if (0 <= end_col)
            res += YYFPRINTF (yyo, ".%d", end_col);
        }
      else if (0 <= end_col && yylocp->first_column < end_col)
        res += YYFPRINTF (yyo, "-%d", end_col);
    }
  return res;
 }

#  define YY_LOCATION_PRINT(File, Loc)          \
  yy_location_print_ (File, &(Loc))

# else
#  define YY_LOCATION_PRINT(File, Loc) ((void) 0)
# endif
#endif


# define YY_SYMBOL_PRINT(Title, Type, Value, Location)                    \
do {                                                                      \
  if (yydebug)                                                            \
    {                                                                     \
      YYFPRINTF (stderr, "%s ", Title);                                   \
      yy_symbol_print (stderr,                                            \
                  Type, Value, Location, scanner, ctx); \
      YYFPRINTF (stderr, "\n");                                           \
    }                                                                     \
} while (0)


/*----------------------------------------.
| Print this symbol's value on YYOUTPUT.  |
`----------------------------------------*/

static void
yy_symbol_value_print (FILE *yyoutput, int yytype, YYSTYPE const * const yyvaluep, YYLTYPE const * const yylocationp, void* scanner, Context* ctx)
{
  FILE *yyo = yyoutput;
  YYUSE (yyo);
  YYUSE (yylocationp);
  YYUSE (scanner);
  YYUSE (ctx);
  if (!yyvaluep)
    return;
# ifdef YYPRINT
  if (yytype < YYNTOKENS)
    YYPRINT (yyoutput, yytoknum[yytype], *yyvaluep);
# endif
  YYUSE (yytype);
}


/*--------------------------------.
| Print this symbol on YYOUTPUT.  |
`--------------------------------*/

static void
yy_symbol_print (FILE *yyoutput, int yytype, YYSTYPE const * const yyvaluep, YYLTYPE const * const yylocationp, void* scanner, Context* ctx)
{
  YYFPRINTF (yyoutput, "%s %s (",
             yytype < YYNTOKENS ? "token" : "nterm", yytname[yytype]);

  YY_LOCATION_PRINT (yyoutput, *yylocationp);
  YYFPRINTF (yyoutput, ": ");
  yy_symbol_value_print (yyoutput, yytype, yyvaluep, yylocationp, scanner, ctx);
  YYFPRINTF (yyoutput, ")");
}

/*------------------------------------------------------------------.
| yy_stack_print -- Print the state stack from its BOTTOM up to its |
| TOP (included).                                                   |
`------------------------------------------------------------------*/

static void
yy_stack_print (yytype_int16 *yybottom, yytype_int16 *yytop)
{
  YYFPRINTF (stderr, "Stack now");
  for (; yybottom <= yytop; yybottom++)
    {
      int yybot = *yybottom;
      YYFPRINTF (stderr, " %d", yybot);
    }
  YYFPRINTF (stderr, "\n");
}

# define YY_STACK_PRINT(Bottom, Top)                            \
do {                                                            \
  if (yydebug)                                                  \
    yy_stack_print ((Bottom), (Top));                           \
} while (0)


/*------------------------------------------------.
| Report that the YYRULE is going to be reduced.  |
`------------------------------------------------*/

static void
yy_reduce_print (yytype_int16 *yyssp, YYSTYPE *yyvsp, YYLTYPE *yylsp, int yyrule, void* scanner, Context* ctx)
{
  unsigned long int yylno = yyrline[yyrule];
  int yynrhs = yyr2[yyrule];
  int yyi;
  YYFPRINTF (stderr, "Reducing stack by rule %d (line %lu):\n",
             yyrule - 1, yylno);
  /* The symbols being reduced.  */
  for (yyi = 0; yyi < yynrhs; yyi++)
    {
      YYFPRINTF (stderr, "   $%d = ", yyi + 1);
      yy_symbol_print (stderr,
                       yystos[yyssp[yyi + 1 - yynrhs]],
                       &(yyvsp[(yyi + 1) - (yynrhs)])
                       , &(yylsp[(yyi + 1) - (yynrhs)])                       , scanner, ctx);
      YYFPRINTF (stderr, "\n");
    }
}

# define YY_REDUCE_PRINT(Rule)          \
do {                                    \
  if (yydebug)                          \
    yy_reduce_print (yyssp, yyvsp, yylsp, Rule, scanner, ctx); \
} while (0)

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
#ifndef YYINITDEPTH
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
static YYSIZE_T
yystrlen (const char *yystr)
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
static char *
yystpcpy (char *yydest, const char *yysrc)
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

/* Copy into *YYMSG, which is of size *YYMSG_ALLOC, an error message
   about the unexpected token YYTOKEN for the state stack whose top is
   YYSSP.

   Return 0 if *YYMSG was successfully written.  Return 1 if *YYMSG is
   not large enough to hold the message.  In that case, also set
   *YYMSG_ALLOC to the required number of bytes.  Return 2 if the
   required number of bytes is too large to store.  */
static int
yysyntax_error (YYSIZE_T *yymsg_alloc, char **yymsg,
                yytype_int16 *yyssp, int yytoken)
{
  YYSIZE_T yysize0 = yytnamerr (YY_NULLPTR, yytname[yytoken]);
  YYSIZE_T yysize = yysize0;
  enum { YYERROR_VERBOSE_ARGS_MAXIMUM = 5 };
  /* Internationalized format string. */
  const char *yyformat = YY_NULLPTR;
  /* Arguments of yyformat. */
  char const *yyarg[YYERROR_VERBOSE_ARGS_MAXIMUM];
  /* Number of reported tokens (one for the "unexpected", one per
     "expected"). */
  int yycount = 0;

  /* There are many possibilities here to consider:
     - If this state is a consistent state with a default action, then
       the only way this function was invoked is if the default action
       is an error action.  In that case, don't check for expected
       tokens because there are none.
     - The only way there can be no lookahead present (in yychar) is if
       this state is a consistent state with a default action.  Thus,
       detecting the absence of a lookahead is sufficient to determine
       that there is no unexpected or expected token to report.  In that
       case, just report a simple "syntax error".
     - Don't assume there isn't a lookahead just because this state is a
       consistent state with a default action.  There might have been a
       previous inconsistent state, consistent state with a non-default
       action, or user semantic action that manipulated yychar.
     - Of course, the expected token list depends on states to have
       correct lookahead information, and it depends on the parser not
       to perform extra reductions after fetching a lookahead from the
       scanner and before detecting a syntax error.  Thus, state merging
       (from LALR or IELR) and default reductions corrupt the expected
       token list.  However, the list is correct for canonical LR with
       one exception: it will still contain any token that will not be
       accepted due to an error action in a later state.
  */
  if (yytoken != YYEMPTY)
    {
      int yyn = yypact[*yyssp];
      yyarg[yycount++] = yytname[yytoken];
      if (!yypact_value_is_default (yyn))
        {
          /* Start YYX at -YYN if negative to avoid negative indexes in
             YYCHECK.  In other words, skip the first -YYN actions for
             this state because they are default actions.  */
          int yyxbegin = yyn < 0 ? -yyn : 0;
          /* Stay within bounds of both yycheck and yytname.  */
          int yychecklim = YYLAST - yyn + 1;
          int yyxend = yychecklim < YYNTOKENS ? yychecklim : YYNTOKENS;
          int yyx;

          for (yyx = yyxbegin; yyx < yyxend; ++yyx)
            if (yycheck[yyx + yyn] == yyx && yyx != YYTERROR
                && !yytable_value_is_error (yytable[yyx + yyn]))
              {
                if (yycount == YYERROR_VERBOSE_ARGS_MAXIMUM)
                  {
                    yycount = 1;
                    yysize = yysize0;
                    break;
                  }
                yyarg[yycount++] = yytname[yyx];
                {
                  YYSIZE_T yysize1 = yysize + yytnamerr (YY_NULLPTR, yytname[yyx]);
                  if (! (yysize <= yysize1
                         && yysize1 <= YYSTACK_ALLOC_MAXIMUM))
                    return 2;
                  yysize = yysize1;
                }
              }
        }
    }

  switch (yycount)
    {
# define YYCASE_(N, S)                      \
      case N:                               \
        yyformat = S;                       \
      break
      YYCASE_(0, YY_("syntax error"));
      YYCASE_(1, YY_("syntax error, unexpected %s"));
      YYCASE_(2, YY_("syntax error, unexpected %s, expecting %s"));
      YYCASE_(3, YY_("syntax error, unexpected %s, expecting %s or %s"));
      YYCASE_(4, YY_("syntax error, unexpected %s, expecting %s or %s or %s"));
      YYCASE_(5, YY_("syntax error, unexpected %s, expecting %s or %s or %s or %s"));
# undef YYCASE_
    }

  {
    YYSIZE_T yysize1 = yysize + yystrlen (yyformat);
    if (! (yysize <= yysize1 && yysize1 <= YYSTACK_ALLOC_MAXIMUM))
      return 2;
    yysize = yysize1;
  }

  if (*yymsg_alloc < yysize)
    {
      *yymsg_alloc = 2 * yysize;
      if (! (yysize <= *yymsg_alloc
             && *yymsg_alloc <= YYSTACK_ALLOC_MAXIMUM))
        *yymsg_alloc = YYSTACK_ALLOC_MAXIMUM;
      return 1;
    }

  /* Avoid sprintf, as that infringes on the user's name space.
     Don't have undefined behavior even if the translation
     produced a string with the wrong number of "%s"s.  */
  {
    char *yyp = *yymsg;
    int yyi = 0;
    while ((*yyp = *yyformat) != '\0')
      if (*yyp == '%' && yyformat[1] == 's' && yyi < yycount)
        {
          yyp += yytnamerr (yyp, yyarg[yyi++]);
          yyformat += 2;
        }
      else
        {
          yyp++;
          yyformat++;
        }
  }
  return 0;
}
#endif /* YYERROR_VERBOSE */

/*-----------------------------------------------.
| Release the memory associated to this symbol.  |
`-----------------------------------------------*/

static void
yydestruct (const char *yymsg, int yytype, YYSTYPE *yyvaluep, YYLTYPE *yylocationp, void* scanner, Context* ctx)
{
  YYUSE (yyvaluep);
  YYUSE (yylocationp);
  YYUSE (scanner);
  YYUSE (ctx);
  if (!yymsg)
    yymsg = "Deleting";
  YY_SYMBOL_PRINT (yymsg, yytype, yyvaluep, yylocationp);

  YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
  switch (yytype)
    {
          case 3: /* NAME  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1370 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 4: /* NUMBER  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1376 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 5: /* LEXERROR  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1382 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 48: /* start  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1388 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 49: /* unit  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1394 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 50: /* alldefs  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1400 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 52: /* classdef  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1406 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 53: /* class_name  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1412 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 54: /* parents  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1418 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 55: /* parent_list  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1424 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 56: /* parent  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1430 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 57: /* maybe_class_funcs  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1436 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 58: /* class_funcs  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1442 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 59: /* funcdefs  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1448 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 60: /* if_stmt  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1454 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 61: /* if_and_elifs  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1460 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 62: /* class_if_stmt  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1466 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 63: /* class_if_and_elifs  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1472 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 64: /* if_cond  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1478 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 65: /* elif_cond  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1484 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 66: /* else_cond  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1490 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 67: /* condition  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1496 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 68: /* version_tuple  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1502 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 69: /* condition_op  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).str)); }
#line 1508 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 70: /* constantdef  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1514 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 71: /* importdef  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1520 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 72: /* import_items  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1526 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 73: /* import_item  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1532 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 74: /* import_name  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1538 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 75: /* from_list  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1544 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 76: /* from_items  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1550 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 77: /* from_item  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1556 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 78: /* alias_or_constant  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1562 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 79: /* typevardef  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1568 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 80: /* typevar_args  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1574 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 81: /* typevar_kwargs  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1580 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 82: /* typevar_kwarg  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1586 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 83: /* funcdef  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1592 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 84: /* decorators  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1598 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 85: /* decorator  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1604 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 86: /* params  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1610 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 87: /* param_list  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1616 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 88: /* param  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1622 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 89: /* param_type  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1628 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 90: /* param_default  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1634 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 91: /* param_star_name  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1640 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 92: /* return  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1646 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 94: /* maybe_body  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1652 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 96: /* body  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1658 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 97: /* body_stmt  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1664 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 98: /* type_parameters  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1670 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 99: /* type_parameter  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1676 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 100: /* type  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1682 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 101: /* named_tuple_fields  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1688 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 102: /* named_tuple_field_list  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1694 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 103: /* named_tuple_field  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1700 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 105: /* maybe_type_list  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1706 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 106: /* type_list  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1712 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 107: /* dotted_name  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1718 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 108: /* getitem_key  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1724 "parser.tab.cc" /* yacc.c:1257  */
        break;

    case 109: /* maybe_number  */
#line 104 "parser.y" /* yacc.c:1257  */
      { Py_CLEAR(((*yyvaluep).obj)); }
#line 1730 "parser.tab.cc" /* yacc.c:1257  */
        break;


      default:
        break;
    }
  YY_IGNORE_MAYBE_UNINITIALIZED_END
}




/*----------.
| yyparse.  |
`----------*/

int
yyparse (void* scanner, Context* ctx)
{
/* The lookahead symbol.  */
int yychar;


/* The semantic value of the lookahead symbol.  */
/* Default value used for initialization, for pacifying older GCCs
   or non-GCC compilers.  */
YY_INITIAL_VALUE (static YYSTYPE yyval_default;)
YYSTYPE yylval YY_INITIAL_VALUE (= yyval_default);

/* Location data for the lookahead symbol.  */
static YYLTYPE yyloc_default
# if defined YYLTYPE_IS_TRIVIAL && YYLTYPE_IS_TRIVIAL
  = { 1, 1, 1, 1 }
# endif
;
YYLTYPE yylloc = yyloc_default;

    /* Number of syntax errors so far.  */
    int yynerrs;

    int yystate;
    /* Number of tokens to shift before error messages enabled.  */
    int yyerrstatus;

    /* The stacks and their tools:
       'yyss': related to states.
       'yyvs': related to semantic values.
       'yyls': related to locations.

       Refer to the stacks through separate pointers, to allow yyoverflow
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
    YYLTYPE yyerror_range[3];

    YYSIZE_T yystacksize;

  int yyn;
  int yyresult;
  /* Lookahead token as an internal (translated) token number.  */
  int yytoken = 0;
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

  yyssp = yyss = yyssa;
  yyvsp = yyvs = yyvsa;
  yylsp = yyls = yylsa;
  yystacksize = YYINITDEPTH;

  YYDPRINTF ((stderr, "Starting parse\n"));

  yystate = 0;
  yyerrstatus = 0;
  yynerrs = 0;
  yychar = YYEMPTY; /* Cause a token to be read.  */
  yylsp[0] = yylloc;
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
  if (yypact_value_is_default (yyn))
    goto yydefault;

  /* Not known => get a lookahead token if don't already have one.  */

  /* YYCHAR is either YYEMPTY or YYEOF or a valid lookahead symbol.  */
  if (yychar == YYEMPTY)
    {
      YYDPRINTF ((stderr, "Reading a token: "));
      yychar = yylex (&yylval, &yylloc, scanner);
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
      if (yytable_value_is_error (yyn))
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
  YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
  *++yyvsp = yylval;
  YY_IGNORE_MAYBE_UNINITIALIZED_END
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
     '$$ = $1'.

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
#line 138 "parser.y" /* yacc.c:1646  */
    { ctx->SetAndDelResult((yyvsp[-1].obj)); (yyval.obj) = NULL; }
#line 2024 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 3:
#line 139 "parser.y" /* yacc.c:1646  */
    { ctx->SetAndDelResult((yyvsp[-1].obj)); (yyval.obj) = NULL; }
#line 2030 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 5:
#line 147 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-1].obj), (yyvsp[0].obj)); }
#line 2036 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 6:
#line 148 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-1].obj), (yyvsp[0].obj)); }
#line 2042 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 7:
#line 149 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); Py_DECREF((yyvsp[0].obj)); }
#line 2048 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 8:
#line 150 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = (yyvsp[-1].obj);
      PyObject* tmp = ctx->Call(kAddAliasOrConstant, "(N)", (yyvsp[0].obj));
      CHECK(tmp, (yyloc));
      Py_DECREF(tmp);
    }
#line 2059 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 9:
#line 156 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); Py_DECREF((yyvsp[0].obj)); }
#line 2065 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 10:
#line 157 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); Py_DECREF((yyvsp[0].obj)); }
#line 2071 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 11:
#line 158 "parser.y" /* yacc.c:1646  */
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yyvsp[0].obj));
      CHECK(tmp, (yylsp[0]));
      (yyval.obj) = ExtendList((yyvsp[-1].obj), tmp);
    }
#line 2081 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 12:
#line 163 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = PyList_New(0); }
#line 2087 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 15:
#line 171 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kAddClass, "(NNN)", (yyvsp[-4].obj), (yyvsp[-3].obj), (yyvsp[0].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2096 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 16:
#line 178 "parser.y" /* yacc.c:1646  */
    {
      // Do not borrow the $1 reference since it is also returned later
      // in $$.  Use O instead of N in the format string.
      PyObject* tmp = ctx->Call(kRegisterClassName, "(O)", (yyvsp[0].obj));
      CHECK(tmp, (yyloc));
      Py_DECREF(tmp);
      (yyval.obj) = (yyvsp[0].obj);
    }
#line 2109 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 17:
#line 189 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); }
#line 2115 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 18:
#line 190 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = PyList_New(0); }
#line 2121 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 19:
#line 191 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = PyList_New(0); }
#line 2127 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 20:
#line 195 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2133 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 21:
#line 196 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = StartList((yyvsp[0].obj)); }
#line 2139 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 22:
#line 200 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[0].obj); }
#line 2145 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 23:
#line 201 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2151 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 24:
#line 205 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = PyList_New(0); }
#line 2157 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 25:
#line 206 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); }
#line 2163 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 26:
#line 207 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); }
#line 2169 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 27:
#line 211 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = PyList_New(0); }
#line 2175 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 29:
#line 216 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-1].obj), (yyvsp[0].obj)); }
#line 2181 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 30:
#line 217 "parser.y" /* yacc.c:1646  */
    {
      PyObject* tmp = ctx->Call(kNewAliasOrConstant, "(N)", (yyvsp[0].obj));
      CHECK(tmp, (yyloc));
      (yyval.obj) = AppendList((yyvsp[-1].obj), tmp);
    }
#line 2191 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 31:
#line 222 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-1].obj), (yyvsp[0].obj)); }
#line 2197 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 32:
#line 223 "parser.y" /* yacc.c:1646  */
    {
      PyObject* tmp = ctx->Call(kIfEnd, "(N)", (yyvsp[0].obj));
      CHECK(tmp, (yylsp[0]));
      (yyval.obj) = ExtendList((yyvsp[-1].obj), tmp);
    }
#line 2207 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 33:
#line 228 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = PyList_New(0); }
#line 2213 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 34:
#line 233 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = AppendList((yyvsp[-5].obj), Py_BuildValue("(NN)", (yyvsp[-4].obj), (yyvsp[-1].obj)));
    }
#line 2221 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 36:
#line 241 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = Py_BuildValue("[(NN)]", (yyvsp[-4].obj), (yyvsp[-1].obj));
    }
#line 2229 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 37:
#line 245 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = AppendList((yyvsp[-5].obj), Py_BuildValue("(NN)", (yyvsp[-4].obj), (yyvsp[-1].obj)));
    }
#line 2237 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 38:
#line 264 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = AppendList((yyvsp[-5].obj), Py_BuildValue("(NN)", (yyvsp[-4].obj), (yyvsp[-1].obj)));
    }
#line 2245 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 40:
#line 272 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = Py_BuildValue("[(NN)]", (yyvsp[-4].obj), (yyvsp[-1].obj));
    }
#line 2253 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 41:
#line 276 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = AppendList((yyvsp[-5].obj), Py_BuildValue("(NN)", (yyvsp[-4].obj), (yyvsp[-1].obj)));
    }
#line 2261 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 42:
#line 288 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = ctx->Call(kIfBegin, "(N)", (yyvsp[0].obj)); CHECK((yyval.obj), (yyloc)); }
#line 2267 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 43:
#line 292 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = ctx->Call(kIfElif, "(N)", (yyvsp[0].obj)); CHECK((yyval.obj), (yyloc)); }
#line 2273 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 44:
#line 296 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = ctx->Call(kIfElse, "()"); CHECK((yyval.obj), (yyloc)); }
#line 2279 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 45:
#line 300 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = Py_BuildValue("((NO)sN)", (yyvsp[-2].obj), Py_None, (yyvsp[-1].str), (yyvsp[0].obj));
    }
#line 2287 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 46:
#line 303 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = Py_BuildValue("((NO)sN)", (yyvsp[-2].obj), Py_None, (yyvsp[-1].str), (yyvsp[0].obj));
    }
#line 2295 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 47:
#line 306 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = Py_BuildValue("((NN)sN)", (yyvsp[-5].obj), (yyvsp[-3].obj), (yyvsp[-1].str), (yyvsp[0].obj));
    }
#line 2303 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 48:
#line 309 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = Py_BuildValue("((NN)sN)", (yyvsp[-5].obj), (yyvsp[-3].obj), (yyvsp[-1].str), (yyvsp[0].obj));
    }
#line 2311 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 49:
#line 312 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NsN)", (yyvsp[-2].obj), "and", (yyvsp[0].obj)); }
#line 2317 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 50:
#line 313 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NsN)", (yyvsp[-2].obj), "or", (yyvsp[0].obj)); }
#line 2323 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 51:
#line 314 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); }
#line 2329 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 52:
#line 319 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(N)", (yyvsp[-2].obj)); }
#line 2335 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 53:
#line 320 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[-3].obj), (yyvsp[-1].obj)); }
#line 2341 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 54:
#line 321 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = Py_BuildValue("(NNN)", (yyvsp[-5].obj), (yyvsp[-3].obj), (yyvsp[-1].obj));
    }
#line 2349 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 55:
#line 327 "parser.y" /* yacc.c:1646  */
    { (yyval.str) = "<"; }
#line 2355 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 56:
#line 328 "parser.y" /* yacc.c:1646  */
    { (yyval.str) = ">"; }
#line 2361 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 57:
#line 329 "parser.y" /* yacc.c:1646  */
    { (yyval.str) = "<="; }
#line 2367 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 58:
#line 330 "parser.y" /* yacc.c:1646  */
    { (yyval.str) = ">="; }
#line 2373 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 59:
#line 331 "parser.y" /* yacc.c:1646  */
    { (yyval.str) = "=="; }
#line 2379 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 60:
#line 332 "parser.y" /* yacc.c:1646  */
    { (yyval.str) = "!="; }
#line 2385 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 61:
#line 336 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[-2].obj), (yyvsp[0].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2394 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 62:
#line 340 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[-2].obj), ctx->Value(kByteString));
      CHECK((yyval.obj), (yyloc));
    }
#line 2403 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 63:
#line 344 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[-2].obj), ctx->Value(kUnicodeString));
      CHECK((yyval.obj), (yyloc));
    }
#line 2412 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 64:
#line 348 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[-2].obj), ctx->Value(kAnything));
      CHECK((yyval.obj), (yyloc));
    }
#line 2421 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 65:
#line 352 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[-4].obj), (yyvsp[0].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2430 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 66:
#line 356 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[-2].obj), (yyvsp[0].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2439 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 67:
#line 360 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kNewConstant, "(NN)", (yyvsp[-4].obj), (yyvsp[-2].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2448 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 68:
#line 367 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kAddImport, "(ON)", Py_None, (yyvsp[0].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2457 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 69:
#line 371 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kAddImport, "(NN)", (yyvsp[-2].obj), (yyvsp[0].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2466 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 70:
#line 375 "parser.y" /* yacc.c:1646  */
    {
      // Special-case "from . import" and pass in a __PACKAGE__ token that
      // the Python parser code will rewrite to the current package name.
      (yyval.obj) = ctx->Call(kAddImport, "(sN)", "__PACKAGE__", (yyvsp[0].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2477 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 71:
#line 384 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2483 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 72:
#line 385 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = StartList((yyvsp[0].obj)); }
#line 2489 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 74:
#line 389 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2495 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 76:
#line 395 "parser.y" /* yacc.c:1646  */
    {
#if PY_MAJOR_VERSION >= 3
      (yyval.obj) = PyUnicode_FromFormat(".%s", PyBytes_AsString((yyvsp[0].obj)));
#else
      (yyval.obj) = PyString_FromFormat(".%s", PyString_AsString((yyvsp[0].obj)));
#endif
      Py_DECREF((yyvsp[0].obj));
    }
#line 2508 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 78:
#line 407 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); }
#line 2514 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 79:
#line 408 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-2].obj); }
#line 2520 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 80:
#line 412 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2526 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 81:
#line 413 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = StartList((yyvsp[0].obj)); }
#line 2532 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 83:
#line 418 "parser.y" /* yacc.c:1646  */
    {
#if PY_MAJOR_VERSION >= 3
  (yyval.obj) = PyUnicode_FromString("NamedTuple");
#else
  (yyval.obj) = PyString_FromString("NamedTuple");
#endif
  }
#line 2544 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 84:
#line 425 "parser.y" /* yacc.c:1646  */
    {
#if PY_MAJOR_VERSION >= 3
  (yyval.obj) = PyUnicode_FromString("TypeVar");
#else
  (yyval.obj) = PyString_FromString("TypeVar");
#endif
  }
#line 2556 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 85:
#line 432 "parser.y" /* yacc.c:1646  */
    {
#if PY_MAJOR_VERSION >= 3
  (yyval.obj) = PyUnicode_FromString("*");
#else
  (yyval.obj) = PyString_FromString("*");
#endif
  }
#line 2568 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 86:
#line 439 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2574 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 87:
#line 443 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2580 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 88:
#line 447 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kAddTypeVar, "(NNN)", (yyvsp[-6].obj), (yyvsp[-2].obj), (yyvsp[-1].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2589 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 89:
#line 454 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(OO)", Py_None, Py_None); }
#line 2595 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 90:
#line 455 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NO)", (yyvsp[0].obj), Py_None); }
#line 2601 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 91:
#line 456 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(ON)", Py_None, (yyvsp[0].obj)); }
#line 2607 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 92:
#line 457 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2613 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 93:
#line 461 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2619 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 94:
#line 462 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = StartList((yyvsp[0].obj)); }
#line 2625 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 95:
#line 466 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2631 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 96:
#line 470 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kNewFunction, "(NNNNN)", (yyvsp[-7].obj), (yyvsp[-5].obj), (yyvsp[-3].obj), (yyvsp[-1].obj), (yyvsp[0].obj));
      // Decorators is nullable and messes up the location tracking by
      // using the previous symbol as the start location for this production,
      // which is very misleading.  It is better to ignore decorators and
      // pretend the production started with DEF.  Even when decorators are
      // present the error line will be close enough to be helpful.
      //
      // TODO(dbaum): Consider making this smarter and only ignoring decorators
      // when they are empty.  Making decorators non-nullable and having two
      // productions for funcdef would be a reasonable solution.
      (yyloc).first_line = (yylsp[-6]).first_line;
      (yyloc).first_column = (yylsp[-6]).first_column;
      CHECK((yyval.obj), (yyloc));
    }
#line 2651 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 97:
#line 488 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-1].obj), (yyvsp[0].obj)); }
#line 2657 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 98:
#line 489 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = PyList_New(0); }
#line 2663 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 99:
#line 493 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); }
#line 2669 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 100:
#line 497 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); }
#line 2675 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 101:
#line 498 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = PyList_New(0); }
#line 2681 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 102:
#line 510 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-3].obj), (yyvsp[0].obj)); }
#line 2687 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 103:
#line 511 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = StartList((yyvsp[0].obj)); }
#line 2693 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 104:
#line 515 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NNN)", (yyvsp[-2].obj), (yyvsp[-1].obj), (yyvsp[0].obj)); }
#line 2699 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 105:
#line 516 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(sOO)", "*", Py_None, Py_None); }
#line 2705 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 106:
#line 517 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NNO)", (yyvsp[-1].obj), (yyvsp[0].obj), Py_None); }
#line 2711 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 107:
#line 518 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = ctx->Value(kEllipsis); }
#line 2717 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 108:
#line 522 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[0].obj); }
#line 2723 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 109:
#line 523 "parser.y" /* yacc.c:1646  */
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; }
#line 2729 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 110:
#line 527 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[0].obj); }
#line 2735 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 111:
#line 528 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[0].obj); }
#line 2741 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 112:
#line 529 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = ctx->Value(kEllipsis); }
#line 2747 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 113:
#line 530 "parser.y" /* yacc.c:1646  */
    { Py_INCREF(Py_None); (yyval.obj) = Py_None; }
#line 2753 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 114:
#line 534 "parser.y" /* yacc.c:1646  */
    {
#if PY_MAJOR_VERSION >= 3
  (yyval.obj) = PyUnicode_FromFormat("*%s", PyBytes_AsString((yyvsp[0].obj)));
#else
  (yyval.obj) = PyString_FromFormat("*%s", PyString_AsString((yyvsp[0].obj)));
#endif
  }
#line 2765 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 115:
#line 541 "parser.y" /* yacc.c:1646  */
    {
#if PY_MAJOR_VERSION >= 3
  (yyval.obj) = PyUnicode_FromFormat("**%s", PyBytes_AsString((yyvsp[0].obj)));
#else
  (yyval.obj) = PyString_FromFormat("**%s", PyString_AsString((yyvsp[0].obj)));
#endif
  }
#line 2777 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 116:
#line 551 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[0].obj); }
#line 2783 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 117:
#line 552 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = ctx->Value(kAnything); }
#line 2789 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 118:
#line 556 "parser.y" /* yacc.c:1646  */
    { Py_DecRef((yyvsp[0].obj)); }
#line 2795 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 119:
#line 560 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); }
#line 2801 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 120:
#line 561 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); }
#line 2807 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 121:
#line 562 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = PyList_New(0); }
#line 2813 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 129:
#line 576 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-1].obj), (yyvsp[0].obj)); }
#line 2819 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 130:
#line 577 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = StartList((yyvsp[0].obj)); }
#line 2825 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 131:
#line 581 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2831 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 132:
#line 582 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[0].obj); }
#line 2837 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 133:
#line 583 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-2].obj); }
#line 2843 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 134:
#line 587 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2849 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 135:
#line 588 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = StartList((yyvsp[0].obj)); }
#line 2855 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 136:
#line 592 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[0].obj); }
#line 2861 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 137:
#line 593 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = ctx->Value(kEllipsis); }
#line 2867 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 138:
#line 597 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kNewType, "(N)", (yyvsp[0].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2876 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 139:
#line 601 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kNewType, "(NN)", (yyvsp[-3].obj), (yyvsp[-1].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2885 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 140:
#line 605 "parser.y" /* yacc.c:1646  */
    {
      // This rule is needed for Callable[[...], ...]
      (yyval.obj) = ctx->Call(kNewType, "(sN)", "tuple", (yyvsp[-1].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2895 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 141:
#line 610 "parser.y" /* yacc.c:1646  */
    {
      (yyval.obj) = ctx->Call(kNewNamedTuple, "(NN)", (yyvsp[-3].obj), (yyvsp[-1].obj));
      CHECK((yyval.obj), (yyloc));
    }
#line 2904 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 142:
#line 614 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-1].obj); }
#line 2910 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 143:
#line 615 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = ctx->Call(kNewIntersectionType, "([NN])", (yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2916 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 144:
#line 616 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = ctx->Call(kNewUnionType, "([NN])", (yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2922 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 145:
#line 617 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = ctx->Value(kAnything); }
#line 2928 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 146:
#line 618 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = ctx->Value(kNothing); }
#line 2934 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 147:
#line 622 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[-2].obj); }
#line 2940 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 148:
#line 623 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = PyList_New(0); }
#line 2946 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 149:
#line 627 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2952 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 150:
#line 628 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = StartList((yyvsp[0].obj)); }
#line 2958 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 151:
#line 632 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = Py_BuildValue("(NN)", (yyvsp[-4].obj), (yyvsp[-2].obj)); }
#line 2964 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 154:
#line 641 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[0].obj); }
#line 2970 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 155:
#line 642 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = PyList_New(0); }
#line 2976 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 156:
#line 646 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = AppendList((yyvsp[-2].obj), (yyvsp[0].obj)); }
#line 2982 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 157:
#line 647 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = StartList((yyvsp[0].obj)); }
#line 2988 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 158:
#line 652 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[0].obj); }
#line 2994 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 159:
#line 653 "parser.y" /* yacc.c:1646  */
    {
#if PY_MAJOR_VERSION >= 3
      (yyvsp[-2].obj) = PyUnicode_Concat((yyvsp[-2].obj), DOT_STRING);
      (yyvsp[-2].obj) = PyUnicode_Concat((yyvsp[-2].obj), (yyvsp[0].obj));
      Py_DECREF((yyvsp[0].obj));
#else
      PyString_Concat(&(yyvsp[-2].obj), DOT_STRING);
      PyString_ConcatAndDel(&(yyvsp[-2].obj), (yyvsp[0].obj));
#endif
      (yyval.obj) = (yyvsp[-2].obj);
    }
#line 3010 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 160:
#line 667 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[0].obj); }
#line 3016 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 161:
#line 668 "parser.y" /* yacc.c:1646  */
    {
      PyObject* slice = PySlice_New((yyvsp[-2].obj), (yyvsp[0].obj), NULL);
      CHECK(slice, (yyloc));
      (yyval.obj) = slice;
    }
#line 3026 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 162:
#line 673 "parser.y" /* yacc.c:1646  */
    {
      PyObject* slice = PySlice_New((yyvsp[-4].obj), (yyvsp[-2].obj), (yyvsp[0].obj));
      CHECK(slice, (yyloc));
      (yyval.obj) = slice;
    }
#line 3036 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 163:
#line 681 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = (yyvsp[0].obj); }
#line 3042 "parser.tab.cc" /* yacc.c:1646  */
    break;

  case 164:
#line 682 "parser.y" /* yacc.c:1646  */
    { (yyval.obj) = NULL; }
#line 3048 "parser.tab.cc" /* yacc.c:1646  */
    break;


#line 3052 "parser.tab.cc" /* yacc.c:1646  */
      default: break;
    }
  /* User semantic actions sometimes alter yychar, and that requires
     that yytoken be updated with the new translation.  We take the
     approach of translating immediately before every use of yytoken.
     One alternative is translating here after every semantic action,
     but that translation would be missed if the semantic action invokes
     YYABORT, YYACCEPT, or YYERROR immediately after altering yychar or
     if it invokes YYBACKUP.  In the case of YYABORT or YYACCEPT, an
     incorrect destructor might then be invoked immediately.  In the
     case of YYERROR or YYBACKUP, subsequent parser actions might lead
     to an incorrect destructor call or verbose syntax error message
     before the lookahead is translated.  */
  YY_SYMBOL_PRINT ("-> $$ =", yyr1[yyn], &yyval, &yyloc);

  YYPOPSTACK (yylen);
  yylen = 0;
  YY_STACK_PRINT (yyss, yyssp);

  *++yyvsp = yyval;
  *++yylsp = yyloc;

  /* Now 'shift' the result of the reduction.  Determine what state
     that goes to, based on the state we popped back to and the rule
     number reduced by.  */

  yyn = yyr1[yyn];

  yystate = yypgoto[yyn - YYNTOKENS] + *yyssp;
  if (0 <= yystate && yystate <= YYLAST && yycheck[yystate] == *yyssp)
    yystate = yytable[yystate];
  else
    yystate = yydefgoto[yyn - YYNTOKENS];

  goto yynewstate;


/*--------------------------------------.
| yyerrlab -- here on detecting error.  |
`--------------------------------------*/
yyerrlab:
  /* Make sure we have latest lookahead translation.  See comments at
     user semantic actions for why this is necessary.  */
  yytoken = yychar == YYEMPTY ? YYEMPTY : YYTRANSLATE (yychar);

  /* If not already recovering from an error, report this error.  */
  if (!yyerrstatus)
    {
      ++yynerrs;
#if ! YYERROR_VERBOSE
      yyerror (&yylloc, scanner, ctx, YY_("syntax error"));
#else
# define YYSYNTAX_ERROR yysyntax_error (&yymsg_alloc, &yymsg, \
                                        yyssp, yytoken)
      {
        char const *yymsgp = YY_("syntax error");
        int yysyntax_error_status;
        yysyntax_error_status = YYSYNTAX_ERROR;
        if (yysyntax_error_status == 0)
          yymsgp = yymsg;
        else if (yysyntax_error_status == 1)
          {
            if (yymsg != yymsgbuf)
              YYSTACK_FREE (yymsg);
            yymsg = (char *) YYSTACK_ALLOC (yymsg_alloc);
            if (!yymsg)
              {
                yymsg = yymsgbuf;
                yymsg_alloc = sizeof yymsgbuf;
                yysyntax_error_status = 2;
              }
            else
              {
                yysyntax_error_status = YYSYNTAX_ERROR;
                yymsgp = yymsg;
              }
          }
        yyerror (&yylloc, scanner, ctx, yymsgp);
        if (yysyntax_error_status == 2)
          goto yyexhaustedlab;
      }
# undef YYSYNTAX_ERROR
#endif
    }

  yyerror_range[1] = yylloc;

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

  yyerror_range[1] = yylsp[1-yylen];
  /* Do not reclaim the symbols of the rule whose action triggered
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
  yyerrstatus = 3;      /* Each real token shifted decrements this.  */

  for (;;)
    {
      yyn = yypact[yystate];
      if (!yypact_value_is_default (yyn))
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

      yyerror_range[1] = *yylsp;
      yydestruct ("Error: popping",
                  yystos[yystate], yyvsp, yylsp, scanner, ctx);
      YYPOPSTACK (1);
      yystate = *yyssp;
      YY_STACK_PRINT (yyss, yyssp);
    }

  YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
  *++yyvsp = yylval;
  YY_IGNORE_MAYBE_UNINITIALIZED_END

  yyerror_range[2] = yylloc;
  /* Using YYLLOC is tempting, but would change the location of
     the lookahead.  YYLOC is available though.  */
  YYLLOC_DEFAULT (yyloc, yyerror_range, 2);
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

#if !defined yyoverflow || YYERROR_VERBOSE
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
    {
      /* Make sure we have latest lookahead translation.  See comments at
         user semantic actions for why this is necessary.  */
      yytoken = YYTRANSLATE (yychar);
      yydestruct ("Cleanup: discarding lookahead",
                  yytoken, &yylval, &yylloc, scanner, ctx);
    }
  /* Do not reclaim the symbols of the rule whose action triggered
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
  return yyresult;
}
#line 690 "parser.y" /* yacc.c:1906  */


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
