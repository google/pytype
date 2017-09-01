#include <Python.h>

#include "lexer.h"
#include "parser.h"

namespace pytype {

// From parser.tab.cc.
int pytypeparse(void* scanner, pytype::Context* ctx);

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
  {kByteString, "BYTESTRING"},
  {kUnicodeString, "UNICODESTRING"},
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
  {kNewConstant, "new_constant"},
  {kNewFunction, "new_function"},
  {kNewNamedTuple, "new_named_tuple"},
  {kRegisterClassName, "register_class_name"},
  {kAddClass, "add_class"},
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

void Context::SetErrorLocation(YYLTYPE* location) const {
  PyObject* result = Call(kSetErrorLocation, "((iiii))",
                          location->first_line, location->first_column,
                          location->last_line, location->last_column);
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
  int err = pytype::pytypeparse(lexer.scanner(), &ctx);
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
    YYSTYPE lval;
    YYLTYPE lloc;
    int t = pytypelex(&lval, &lloc, lexer.scanner());
    if (!t) break;
    PyObject* obj = lval.obj;
    if (obj == NULL) {
      Py_INCREF(Py_None);
      obj = Py_None;
    }

    PyObject* token = Py_BuildValue(
        "(iOiiii)", t, obj, lloc.first_line, lloc.first_column, lloc.last_line,
        lloc.last_column);
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
  PyObject* pyval = PyInt_FromLong(value);
  PyDict_SetItemString(dict, name, pyval);
  Py_DECREF(pyval);
}

#define ADD_TOKEN(dict, name) add_token(dict, #name, name)

// Create a TOKENS attribute that maps token names to integer values.
static void add_tokens_dict(PyObject* module) {
  PyObject* tokens = PyDict_New();
  ADD_TOKEN(tokens, NAME);
  ADD_TOKEN(tokens, NUMBER);
  ADD_TOKEN(tokens, TRIPLEQUOTED);
  ADD_TOKEN(tokens, TYPECOMMENT);
  ADD_TOKEN(tokens, ARROW);
  ADD_TOKEN(tokens, COLONEQUALS);
  ADD_TOKEN(tokens, ELLIPSIS);
  ADD_TOKEN(tokens, EQ);
  ADD_TOKEN(tokens, NE);
  ADD_TOKEN(tokens, LE);
  ADD_TOKEN(tokens, GE);
  ADD_TOKEN(tokens, INDENT);
  ADD_TOKEN(tokens, DEDENT);
  ADD_TOKEN(tokens, LEXERROR);

  // Reserved words.
  ADD_TOKEN(tokens, CLASS);
  ADD_TOKEN(tokens, DEF);
  ADD_TOKEN(tokens, ELSE);
  ADD_TOKEN(tokens, ELIF);
  ADD_TOKEN(tokens, IF);
  ADD_TOKEN(tokens, OR);
  ADD_TOKEN(tokens, PASS);
  ADD_TOKEN(tokens, IMPORT);
  ADD_TOKEN(tokens, FROM);
  ADD_TOKEN(tokens, AS);
  ADD_TOKEN(tokens, RAISE);
  ADD_TOKEN(tokens, NOTHING);
  ADD_TOKEN(tokens, NAMEDTUPLE);
  ADD_TOKEN(tokens, TYPEVAR);

  // Add dict to module.
  PyObject_SetAttrString(module, "TOKENS", tokens);
  Py_DECREF(tokens);
}


PyMODINIT_FUNC initparser_ext() {
  // TODO(dbaum): Make this Python3 compatible.
  PyObject* module = Py_InitModule("parser_ext", methods);
  add_tokens_dict(module);
}
