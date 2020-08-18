#include <Python.h>

#include "lexer.h"
#include "parser.h"

// The parser defines a token struct. Give it a shorter alias.
typedef pytype::parser::token t;

// pytypelex is generated in lexer.lex.cc, but because it uses semantic_type and
// location, it must be declared here.
int pytypelex(pytype::parser::semantic_type* lvalp, pytype::location* llocp,
              void* scanner);

namespace pytype {

// From parser.tab.cc.
/* int pytypeparse(void* scanner, pytype::Context* ctx); */

// A pair of enum value and attribute name, parameterized by enum type.
template <typename T> class SelectorEntry {
 public:
  const T selector;
  const char* attribute_name;
};

// Mapping from ValueSelector to attribute name.
static const SelectorEntry<ValueSelector> value_attributes[] = {
  {kEllipsis, "ELLIPSIS"},
  {kParseError, "PARSE_ERROR"},
  {kNothing, "NOTHING"},
  {kAnything, "ANYTHING"},
  {kTuple, "TUPLE"},
};

// Mapping from CallSelector to method name.
static const SelectorEntry<CallSelector> call_attributes[] = {
  {kSetErrorLocation, "set_error_location"},
  {kNewType, "new_type"},
  {kNewUnionType, "new_union_type"},
  {kNewIntersectionType, "new_intersection_type"},
  {kAddImport, "add_import"},
  {kAddAliasOrConstant, "add_alias_or_constant"},
  {kNewAliasOrConstant, "new_alias_or_constant"},
  {kNewClass, "new_class"},
  {kNewConstant, "new_constant"},
  {kNewFunction, "new_function"},
  {kNewNamedTuple, "new_named_tuple"},
  {kNewTypedDict, "new_typed_dict"},
  {kRegisterClassName, "register_class_name"},
  {kAddTypeVar, "add_type_var"},

  {kIfBegin, "if_begin"},
  {kIfElif, "if_elif"},
  {kIfElse, "if_else"},
  {kIfEnd, "if_end"},
};

// Initialize a selector's dispatch table.
//
// refs: Array of RefHolders to be filled in (should contain NULLs on entry).
// selector_count: The number of selectors (i.e. kValueSelectorCount).  refs
//   must be at least this size.
// entries: Array of SelectorEntry<T> pairs.
// entry_count: The number of elements in entries.
// peer: The Python peer object to inspect for attributes.
// callable: true iff the atttributes must be callable.
// enum_name: The name of type T, used in error messages.
//
// Returns: true if there was exactly one entry for every selector and all
//   of the attributes could be found.
template <typename T> bool InitSelectorTable(
    RefHolder* refs,
    int selector_count,
    const SelectorEntry<T>* entries,
    int entry_count,
    PyObject* peer,
    bool callable,
    const char* enum_name) {

  if (selector_count != entry_count) {
    PyErr_Format(PyExc_AssertionError,
                 "Not enough selector entries for %s.", enum_name);
    return false;
  }

  for (int i = 0; i < entry_count; i++) {
    const SelectorEntry<T>& entry = entries[i];
    if (refs[entry.selector] != NULL) {
      // Duplicate entry (or Init called twice).
      PyErr_Format(
          PyExc_AssertionError,
          "Duplicate %s entry {%d, \"%s\"}.", enum_name, entry.selector,
          entry.attribute_name);
      return false;
    }
    RefHolder object = PyObject_GetAttrString(peer, entry.attribute_name);
    if (object == NULL || (callable && !PyCallable_Check(object))) {
      return false;
    }
    refs[entry.selector] = object;
  }

  return true;
}

bool Context::Init(PyObject* peer) {
  if (initialized_) {
    return false;
  }
  if (!InitSelectorTable(
      values_, kValueSelectorCount,
      value_attributes, sizeof(value_attributes) / sizeof(value_attributes[0]),
      peer, false, "ValueSelector")) {
    return false;
  }

  if (!InitSelectorTable(
      callables_, kCallSelectorCount,
      call_attributes, sizeof(call_attributes) / sizeof(call_attributes[0]),
      peer, true, "CallSelector")) {
    return false;
  }

  initialized_ = true;
  return true;
}

PyObject* Context::Value(ValueSelector selector) const {
  if (!initialized_ || selector < 0 || selector >= kValueSelectorCount) {
    return NULL;
  }

  PyObject* obj = values_[selector];
  Py_INCREF(obj);
  return obj;
}

PyObject* Context::Call(CallSelector selector, const char* fmt, ...) const {
  if (!initialized_ || selector < 0 || selector >= kCallSelectorCount) {
    return NULL;
  }

  // Build args.
  va_list va;
  va_start(va, fmt);
  PyObject* args = Py_VaBuildValue(fmt, va);
  va_end(va);
  if (!args) {
    return NULL;
  }

  // Call and return result.
  PyObject* result = PyObject_CallObject(callables_[selector], args);
  Py_DECREF(args);
  return result;
}

void Context::SetErrorLocation(const pytype::location& loc) const {
  // Call clobbers any existing error, so we need to save it.
  PyObject *ptype, *pvalue, *ptraceback;
  PyErr_Fetch(&ptype, &pvalue, &ptraceback);
  PyObject* result = Call(kSetErrorLocation, "((iiii))",
                          loc.begin.line, loc.begin.column,
                          loc.end.line, loc.end.column);
  PyErr_Restore(ptype, pvalue, ptraceback);
  Py_XDECREF(result);
}

}  // end namespace pytype


static PyObject* parse(PyObject* self, PyObject* args) {
  const char* bytes;
  Py_ssize_t length;
  PyObject* peer;
  pytype::Context ctx;

  if (!PyArg_ParseTuple(args, "Os#", &peer, &bytes, &length)) {
    return NULL;
  }

  if (!ctx.Init(peer)) {
    return NULL;
  }

  pytype::Lexer lexer(bytes, length);
  pytype::parser parser(lexer.scanner(), &ctx);
  int err = parser.parse();
  if (err) {
    if (err != 1) {
      // This wasn't a syntax error (which has already constructed an error
      // message).  In theory the only other error code is #2 for memory
      // exhaustion, but just in case there are other codes, build a generic
      // error messsage.
      PyErr_Format(PyExc_RuntimeError, "Parse error #%d.", err);
    }
    return NULL;
  } else {
    PyObject* result = ctx.GetResult();
    Py_INCREF(result);
    return result;
  }
}

static char parse_doc[] =
    "parse(peer, text)\n\n"
    "Parse text (a string) and return a pyi parse tree.  The peer is called\n"
    "during parsing and must contain the methods and attributes described\n"
    "in the selector tables defined in C++.";


static PyObject* tokenize(PyObject* self, PyObject* args) {
  const char* bytes;
  Py_ssize_t length;

  if (!PyArg_ParseTuple(args, "s#", &bytes, &length))
    return NULL;

  pytype::Lexer lexer(bytes, length);
  PyObject* tokens = PyList_New(0);
  while (1) {
    pytype::parser::semantic_type lval;
    pytype::location lloc;
    int t = pytypelex(&lval, &lloc, lexer.scanner());
    if (!t) break;
    PyObject* obj = lval.obj;
    if (obj == NULL) {
      Py_INCREF(Py_None);
      obj = Py_None;
    }

    PyObject* token = Py_BuildValue(
        "(iOiiii)", t, obj, lloc.begin.line, lloc.begin.column, lloc.end.line,
        lloc.end.column);
    PyList_Append(tokens, token);
    Py_DECREF(token);
    Py_DECREF(obj);
  }

  return tokens;
}

static char tokenize_doc[] = "Convert a string into a list of token tuples.";


static PyMethodDef methods[] = {
  {"parse", (PyCFunction)parse, METH_VARARGS, parse_doc},
  {"tokenize", (PyCFunction)tokenize, METH_VARARGS, tokenize_doc},
  {NULL}
};


static void add_token(PyObject* dict, const char* name, int value) {
#if PY_MAJOR_VERSION >= 3
  PyObject* pyval = PyLong_FromLong(value);
#else
  PyObject* pyval = PyInt_FromLong(value);
#endif
  PyDict_SetItemString(dict, name, pyval);
  Py_DECREF(pyval);
}

// Create a TOKENS attribute that maps token names to integer values.
static void add_tokens_dict(PyObject* module) {
  PyObject* tokens = PyDict_New();
  add_token(tokens, "NAME",            t::NAME);
  add_token(tokens, "NUMBER",          t::NUMBER);
  add_token(tokens, "STRING",          t::STRING);
  add_token(tokens, "TRIPLEQUOTED",    t::TRIPLEQUOTED);
  add_token(tokens, "TYPECOMMENT",     t::TYPECOMMENT);
  add_token(tokens, "ARROW",           t::ARROW);
  add_token(tokens, "ELLIPSIS",        t::ELLIPSIS);
  add_token(tokens, "EQ",              t::EQ);
  add_token(tokens, "NE",              t::NE);
  add_token(tokens, "LE",              t::LE);
  add_token(tokens, "GE",              t::GE);
  add_token(tokens, "INDENT",          t::INDENT);
  add_token(tokens, "DEDENT",          t::DEDENT);
  add_token(tokens, "LEXERROR",        t::LEXERROR);

  // reserved words.
  add_token(tokens, "ASYNC",           t::ASYNC);
  add_token(tokens, "CLASS",           t::CLASS);
  add_token(tokens, "DEF",             t::DEF);
  add_token(tokens, "ELSE",            t::ELSE);
  add_token(tokens, "ELIF",            t::ELIF);
  add_token(tokens, "IF",              t::IF);
  add_token(tokens, "OR",              t::OR);
  add_token(tokens, "PASS",            t::PASS);
  add_token(tokens, "IMPORT",          t::IMPORT);
  add_token(tokens, "FROM",            t::FROM);
  add_token(tokens, "AS",              t::AS);
  add_token(tokens, "RAISE",           t::RAISE);
  add_token(tokens, "NOTHING",         t::NOTHING);
  add_token(tokens, "NAMEDTUPLE",      t::NAMEDTUPLE);
  add_token(tokens, "COLL_NAMEDTUPLE", t::COLL_NAMEDTUPLE);
  add_token(tokens, "TYPEDDICT",       t::TYPEDDICT);
  add_token(tokens, "TYPEVAR",         t::TYPEVAR);

  // Add dict to module.
  PyObject_SetAttrString(module, "TOKENS", tokens);
  Py_DECREF(tokens);
}

#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT, "parser_ext", NULL, -1, methods,
};

PyMODINIT_FUNC PyInit_parser_ext() {
  PyObject* module = PyModule_Create(&moduledef);
  add_tokens_dict(module);
  return module;
}

#else

PyMODINIT_FUNC initparser_ext() {
  PyObject* module = Py_InitModule("parser_ext", methods);
  add_tokens_dict(module);
}
#endif
