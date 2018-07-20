#include <Python.h>
#include <structseq.h>

#include <unordered_map>
#include <utility>

#include "cfg_logging.h"
#include "typegraph.h"

namespace typegraph = devtools_python_typegraph;

static const char* kModuleName = "cfg";

#if PY_MAJOR_VERSION >= 3
#  define PyString_Check(s) (PyBytes_Check(s) || PyUnicode_Check(s))
#  define PyString_FromString PyUnicode_FromString
#define PyString_FromFormat PyUnicode_FromFormat
#  define PyString_AsString(ob) \
        (PyUnicode_Check(ob)? PyUnicode_AsUTF8(ob): PyBytes_AS_STRING(ob))
#  define PyInt_FromLong PyLong_FromLong
#define PyInt_AsLong PyLong_AsLong
#define PyInt_FromSize_t PyLong_FromSize_t
#endif

// forward declarations of singletons
extern PyTypeObject PyProgram;
extern PyTypeObject PyCFGNode;
extern PyTypeObject PyVariable;
extern PyTypeObject PyBinding;

// String constants for tp_getattro. Initialized on module init.
static PyObject* k_entrypoint;
static PyObject* k_incoming;
static PyObject* k_outgoing;
static PyObject* k_data;
static PyObject* k_name;
static PyObject* k_variable;
static PyObject* k_origins;
static PyObject* k_where;
static PyObject* k_binding;
static PyObject* k_bindings;
static PyObject* k_choices;
static PyObject* k_cfg_nodes;
static PyObject* k_methods;
static PyObject* k_variables;
static PyObject* k_program;
static PyObject* k_id;
static PyObject* k_next_variable_id;
static PyObject* k_condition;
static PyObject* k_default_data;

typedef struct {
  PyObject_HEAD
  typegraph::Program* program;
  // To preserve object identity, we remember which C structure we wrapped and
  // the PyObject that wraps it.
  std::unordered_map<const void*, PyObject*>* cache;
} PyProgramObj;

typedef struct {
  PyObject_HEAD
  typegraph::CFGNode* cfg_node;
  PyProgramObj* program;
} PyCFGNodeObj;

typedef struct {
  PyObject_HEAD
  typegraph::Binding* attr;
  PyProgramObj* program;
} PyBindingObj;

typedef struct {
  PyObject_HEAD
  typegraph::Variable* u;
  PyProgramObj* program;
} PyVariableObj;

// We remember which C structure we wrapped and the PyObject that wraps it in
// the "cache" attribute of PyProgramObj. The entries in this cache are like
// weak references: even though they have a pointer to the PyObject, they don't
// increase the reference count of an object, but they get notified whenever
// the Python object gets destroyed.

static PyObject* FindInCache(PyProgramObj* program, const void* key) {
  auto result = program->cache->find(key);
  if (result == program->cache->end()) {
    return nullptr;
  } else {
    PyObject* obj = result->second;
    Py_INCREF(obj);  // The Wrap* functions don't do INCREF themselves.
    return obj;
  }
}

// Upon deallocation of the Python object, we remove it from our cache.
static void RemoveFromCache(PyProgramObj* program, void* key) {
  auto result = program->cache->find(key);
  CHECK(result != program->cache->end()) << "corrupted PyProgram cache";
  program->cache->erase(key);
}

static PyObject* WrapCFGNode(PyProgramObj* program,
                             typegraph::CFGNode* cfg_node) {
  PyObject* cached = FindInCache(program, cfg_node);
  if (cached)
    return cached;
  PyCFGNodeObj* py_cfg_node = PyObject_New(PyCFGNodeObj, &PyCFGNode);
  py_cfg_node->cfg_node = cfg_node;
  py_cfg_node->program = program;
  Py_INCREF(program);  // DECREF in CFGNodeDealloc
  PyObject* obj = reinterpret_cast<PyObject*>(py_cfg_node);
  (*program->cache)[cfg_node] = obj;
  return obj;
}

static PyObject* WrapBinding(PyProgramObj* program, typegraph::Binding* attr) {
  PyObject* cached = FindInCache(program, attr);
  if (cached)
    return cached;
  PyBindingObj* py_attr = PyObject_New(PyBindingObj, &PyBinding);
  py_attr->attr = attr;
  py_attr->program = program;
  Py_INCREF(program);  // DECREF in BindingDealloc
  PyObject* obj = reinterpret_cast<PyObject*>(py_attr);
  (*program->cache)[attr] = obj;
  return obj;
}

static PyObject* WrapVariable(PyProgramObj* program, typegraph::Variable* u) {
  PyObject* cached = FindInCache(program, u);
  if (cached)
    return cached;
  PyVariableObj* py_variable = PyObject_New(PyVariableObj, &PyVariable);
  py_variable->u = u;
  py_variable->program = program;
  Py_INCREF(program);  // DECREF in VariableDealloc
  PyObject* obj = reinterpret_cast<PyObject*>(py_variable);
  (*program->cache)[u] = obj;
  return obj;
}

// Helper method, for checking that an object is a list of binding instances.
static bool VerifyListOfBindings(PyObject* list, PyProgramObj* program) {
  if (!PyList_Check(list)) {
    PyErr_SetString(PyExc_TypeError, "expected a list");
    return false;
  }
  int length = PyList_Size(list);
  for (int i = 0; i < length; i++) {
    PyObject* item = PyList_GET_ITEM(list, i);
    if (Py_TYPE(item) != &PyBinding) {
      PyErr_SetString(PyExc_AttributeError,
                      "expected a list of Binding instances");
      return false;
    }
    PyBindingObj* attr = reinterpret_cast<PyBindingObj*>(item);
    if (attr->attr->program() != program->program) {
      PyErr_SetString(PyExc_AttributeError,
                      "Passing binding from different program");
      return false;
    }
  }
  return true;
}

// Checks if a PyObject is of a particular type, is Py_None, or is NULL. It then
// sets the output variable ret to that object as the given type.
// Returns true if the conversion succeeds, false otherwise.
// If obj is NULL or Py_None, *ret is set to NULL.
template <class T>
static bool IsTypeOrNone(PyObject* obj, PyTypeObject* type, T** ret) {
  if (!obj || obj == Py_None) {
    *ret = nullptr;
    return true;
  }
  if (PyObject_TypeCheck(obj, type)) {
    *ret = reinterpret_cast<T*>(obj);
    return true;
  }
  return false;
}

static bool IsCFGNodeOrNone(PyObject* obj, typegraph::CFGNode** ret) {
  PyCFGNodeObj* temp = nullptr;
  *ret = nullptr;
  if (IsTypeOrNone<PyCFGNodeObj>(obj, &PyCFGNode, &temp)) {
    if (temp)
      *ret = temp->cfg_node;
    return true;
  }
  return false;
}

// --- Program -----------------------------------------------------------------

static void ProgramDealloc(PyObject* self) {
  CHECK(self && Py_TYPE(self) == &PyProgram);
  PyProgramObj* program = reinterpret_cast<PyProgramObj*>(self);
  delete program->cache;
  delete program->program;
  PyObject_Del(self);
}

static PyObject* ProgramGetAttro(PyObject* self, PyObject* attr) {
  CHECK(self && Py_TYPE(self) == &PyProgram);
  PyProgramObj* program = reinterpret_cast<PyProgramObj*>(self);
  if (PyObject_RichCompareBool(attr, k_cfg_nodes, Py_EQ) > 0) {
    PyObject* list = PyList_New(0);
    for (const auto& method : program->program->cfg_nodes()) {
      PyObject* cfg_node = WrapCFGNode(program, method.get());
      PyList_Append(list, cfg_node);
      Py_DECREF(cfg_node);
    }
    return list;
  } else if (PyObject_RichCompareBool(attr, k_variables, Py_EQ) > 0) {
    PyObject* set = PySet_New(0);
    for (const auto& n : program->program->cfg_nodes()) {
      for (auto b : n->bindings()) {
        PyObject* variable = WrapVariable(program, b->variable());
        PySet_Add(set, variable);
        Py_DECREF(variable);
      }
    }
    return set;
  } else if (PyObject_RichCompareBool(attr, k_entrypoint, Py_EQ) > 0) {
    typegraph::CFGNode* entrypoint = program->program->entrypoint();
    if (entrypoint) {
      return WrapCFGNode(program, entrypoint);
    } else {
      Py_RETURN_NONE;
    }
  } else if (PyObject_RichCompareBool(attr, k_next_variable_id, Py_EQ) > 0) {
    return PyInt_FromSize_t(program->program->next_variable_id());
  } else if (PyObject_RichCompareBool(attr, k_default_data, Py_EQ) > 0) {
    auto data = reinterpret_cast<PyObject*>(program->program->default_data());
    if (!data) {
      Py_RETURN_NONE;
    }
    Py_INCREF(data);
    return data;
  }
  return PyObject_GenericGetAttr(self, attr);
}

static int ProgramSetAttro(PyObject* self, PyObject* attr, PyObject* val) {
  CHECK(self != nullptr);
  CHECK(Py_TYPE(self) == &PyProgram);
  PyProgramObj* program = reinterpret_cast<PyProgramObj*>(self);

  if (PyObject_RichCompareBool(attr, k_entrypoint, Py_EQ) > 0) {
    if (Py_TYPE(val) == &PyCFGNode) {
      PyCFGNodeObj* cfg_node = reinterpret_cast<PyCFGNodeObj*>(val);
      program->program->set_entrypoint(cfg_node->cfg_node);
    } else if (val == Py_None) {
      program->program->set_entrypoint(nullptr);
    } else {
      PyErr_SetString(PyExc_ValueError, "entrypoint must be a CFGNode or None");
      return -1;
    }
    return 0;
  } else if (PyObject_RichCompareBool(attr, k_default_data, Py_EQ) > 0) {
    Py_XDECREF(program->program->default_data());
    Py_INCREF(val);
    program->program->set_default_data(val);
    return 0;
  }
  return PyObject_GenericSetAttr(self, attr, val);
}

static PyObject* ProgramNew(PyTypeObject* type,
                            PyObject* args, PyObject* kwargs) {
  if (!PyArg_ParseTuple(args, ""))
    return nullptr;
  PyProgramObj* program = PyObject_New(PyProgramObj, &PyProgram);
  program->cache = new std::unordered_map<const void*, PyObject*>;
  program->program = new typegraph::Program;
  return reinterpret_cast<PyObject*>(program);
}

PyDoc_STRVAR(new_cfg_node_doc,
    "Start a new CFG node.");

static PyObject* NewCFGNode(PyProgramObj* self,
                            PyObject* args, PyObject* kwargs) {
  static char *kwlist[] = {"name", "condition", nullptr};
  PyObject* name_obj = nullptr;
  const char* name = nullptr;
  PyObject* condition_obj = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|OO!", kwlist, &name_obj,
                                   &PyBinding, &condition_obj))
    return nullptr;
  if (name_obj) {
    name_obj = PyObject_Str(name_obj);
    name = PyString_AsString(name_obj);
    Py_DECREF(name_obj);
  } else {
    name = "None";
  }
  if (condition_obj) {
    auto bind_obj = reinterpret_cast<PyBindingObj*>(condition_obj);
    return WrapCFGNode(self, self->program->NewCFGNode(name, bind_obj->attr));
  }
  return WrapCFGNode(self, self->program->NewCFGNode(name));
}

static std::vector<typegraph::Binding*> ParseBindingList(PyObject* list) {
  int length = PyList_Size(list);
  std::vector<typegraph::Binding*> origins;
  for (int i = 0; i < length; i++) {
    PyObject* item = PyList_GetItem(list, i);
    PyBindingObj* attr = reinterpret_cast<PyBindingObj*>(item);
    origins.push_back(attr->attr);
  }
  return origins;  // copy elided
}

// Checks that a PyObject* is a PyList of typegraph::Bindings, converting the
// given PyObject* to a PyList if necessary. (e.g. from a PySet).
// The given PyObject* will be set to a new reference.
// Returns true if conversion succeeds.
// Returns false and sets an error if otherwise.
// If the given PyObject* is NULL or Py_None, returns true but sets the
// PyObject* to NULL, so check that!
static bool ContainerToSourceSet(PyObject** container,
                                 PyProgramObj* program) {
  if (!container || *container == nullptr || *container == Py_None) {
    *container = nullptr;
    return true;
  }
  *container = PySequence_List(*container);
  if (!(*container)) {
    PyErr_SetString(PyExc_TypeError,
                    "SourceSet can only be generated from an iterable");
    return false;
  }
  if (!VerifyListOfBindings(*container, program)) {
    Py_DECREF(*container);
    return false;  // pass error through
  }
  return true;
}

PyDoc_STRVAR(
    new_variable_doc,
    "Create a new Variable.\n\n"
    "A Variable typically models a \"union type\", i.e., a disjunction of "
    "different possible types."
    "This constructor assumes that all the bindings in this Variable have the "
    "same origin(s). If that's not the case, construct a variable with "
    "bindings=[] and origins=[] and then call AddBinding() to add the different"
    " bindings.");

static PyObject* NewVariable(PyProgramObj* self,
                             PyObject* args, PyObject* kwargs) {
  static char* kwlist[] = {"bindings", "source_set", "where", nullptr};
  PyObject* bindings = nullptr;
  PyObject* source_set = nullptr;
  PyObject* where_obj = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|OOO", kwlist,
                                   &bindings, &source_set, &where_obj))
    return nullptr;

  if (bindings == Py_None)
    bindings = nullptr;

  if (bindings && !PyObject_GetIter(bindings))
    return nullptr;  // propagate error raised by PyObject_GetIter

  typegraph::CFGNode* where;
  if (!IsCFGNodeOrNone(where_obj, &where)) {
    PyErr_SetString(PyExc_TypeError, "where must be a CFGNode or None.");
    return nullptr;
  }

  if (!ContainerToSourceSet(&source_set, self))
    return nullptr;

  typegraph::Variable* u = self->program->NewVariable();

  if (bindings) {
    // TODO(kramm): Is assert the right thing to use, inside a Python extension?
    CHECK(bindings && source_set && where);
    PyObject* item;
    PyObject* bind_iter = PyObject_GetIter(bindings);
    while ((item = PyIter_Next(bind_iter))) {
      // PyIter_Next returns a new reference, which will be owned by AddBinding.
      // That means we don't need to INCREF or DECREF item.
      typegraph::Binding* attr = u->AddBinding(item);
      typegraph::Origin* origin = attr->AddOrigin(where);
      origin->AddSourceSet(ParseBindingList(source_set));
    }
    Py_DECREF(bind_iter);
    if (PyErr_Occurred()) {
      // PyIter_Next raised an error, so clean up and propagate.
      Py_DECREF(source_set);
      return nullptr;
    }
  }
  Py_XDECREF(source_set);
  return WrapVariable(self, u);
}

PyDoc_STRVAR(
    is_reachable_doc,
    "Whether a path exists (going forward) from src to dst.");

static PyObject* is_reachable(PyProgramObj* self,
                              PyObject* args, PyObject* kwargs) {
  static char* kwlist[] = {"src", "dst", nullptr};
  PyCFGNodeObj* src;
  PyCFGNodeObj* dst;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O!O!", kwlist, &PyCFGNode,
                                   &src, &PyCFGNode, &dst))
    return nullptr;
  if (self->program->is_reachable(src->cfg_node, dst->cfg_node)) {
    Py_RETURN_TRUE;
  } else {
    Py_RETURN_FALSE;
  }
}

static PyMethodDef program_methods[] = {
  {"NewCFGNode", reinterpret_cast<PyCFunction>(NewCFGNode),
    METH_VARARGS|METH_KEYWORDS, new_cfg_node_doc},
  {"NewVariable", reinterpret_cast<PyCFunction>(NewVariable),
    METH_VARARGS|METH_KEYWORDS, new_variable_doc},
  {"is_reachable", reinterpret_cast<PyCFunction>(is_reachable),
   METH_VARARGS|METH_KEYWORDS, is_reachable_doc},
  {0, 0, 0, nullptr}  // sentinel
};

PyDoc_STRVAR(
    program_doc,
    "Program instances describe program entities.\n\n"
    "This class ties together the CFG, the data flow graph (variables + "
    "bindings) as well as methods for creating CFGNodes and Variables."
    "We use this for issuing IDs: We need every CFGNode and Variable to have a "
    "unique ID, and this class does the necessary counting.\n\n"
    "A program is the owner of all the structures it contains, so as long as "
    "you hold a reference of a program or any (!) of its structures, it will "
    "stay in memory.");

PyTypeObject PyProgram = {
  PyVarObject_HEAD_INIT(&PyType_Type, 0) tp_name : "Program",
  tp_basicsize : sizeof(PyProgramObj),
  tp_itemsize : 0,
  tp_dealloc : ProgramDealloc,
  tp_print : nullptr,
  tp_getattr : nullptr,
  tp_setattr : nullptr,
#if PY_VERSION_HEX >= 0x03050000  // 3.5
  tp_as_async : nullptr,
#else
  tp_compare : nullptr,
#endif
  tp_repr : nullptr,
  tp_as_number : nullptr,
  tp_as_sequence : nullptr,
  tp_as_mapping : nullptr,
  tp_hash : nullptr,
  tp_call : nullptr,
  tp_str : nullptr,
  tp_getattro : ProgramGetAttro,
  tp_setattro : ProgramSetAttro,
  tp_as_buffer : nullptr,
  tp_flags : 0,
  tp_doc : program_doc,
  tp_traverse : nullptr,
  tp_clear : nullptr,
  tp_richcompare : nullptr,
  tp_weaklistoffset : 0,
  tp_iter : nullptr,
  tp_iternext : nullptr,
  tp_methods : program_methods,
  tp_members : nullptr,
  tp_getset : nullptr,
  tp_base : nullptr,
  tp_dict : nullptr,
  tp_descr_get : nullptr,
  tp_descr_set : nullptr,
  tp_dictoffset : 0,
  tp_init : nullptr,
  tp_alloc : nullptr,
  tp_new : ProgramNew,
};

// --- CFGNode -----------------------------------------------------------------

static PyObject* CFGNodeGetAttro(PyObject* self, PyObject* attr) {
  CHECK(self && Py_TYPE(self) == &PyCFGNode);
  PyCFGNodeObj* cfg_node = reinterpret_cast<PyCFGNodeObj*>(self);
  PyProgramObj* program = cfg_node->program;

  if (PyObject_RichCompareBool(attr, k_incoming, Py_EQ) > 0) {
    PyObject* list = PyList_New(0);
    for (typegraph::CFGNode* node : cfg_node->cfg_node->incoming()) {
      PyObject* cfg_node = WrapCFGNode(program, node);
      PyList_Append(list, cfg_node);
      Py_DECREF(cfg_node);
    }
    return list;
  } else if (PyObject_RichCompareBool(attr, k_outgoing, Py_EQ) > 0) {
    PyObject* list = PyList_New(0);
    for (typegraph::CFGNode* node : cfg_node->cfg_node->outgoing()) {
      PyObject* cfg_node = WrapCFGNode(program, node);
      PyList_Append(list, cfg_node);
      Py_DECREF(cfg_node);
    }
    return list;
  } else if (PyObject_RichCompareBool(attr, k_bindings, Py_EQ) > 0) {
    PyObject* list = PyList_New(0);
    for (typegraph::Binding* v : cfg_node->cfg_node->bindings()) {
      PyObject* binding = WrapBinding(program, v);
      PyList_Append(list, binding);
      Py_DECREF(binding);
    }
    return list;
  } else if (PyObject_RichCompareBool(attr, k_name, Py_EQ) > 0) {
    return PyString_FromString(cfg_node->cfg_node->name().c_str());
  } else if (PyObject_RichCompareBool(attr, k_program, Py_EQ) > 0) {
    Py_INCREF(program);
    return reinterpret_cast<PyObject*>(program);
  } else if (PyObject_RichCompareBool(attr, k_id, Py_EQ) > 0) {
    return PyInt_FromLong(cfg_node->cfg_node->id());
  } else if (PyObject_RichCompareBool(attr, k_condition, Py_EQ) > 0) {
    typegraph::Binding* cond = cfg_node->cfg_node->condition();
    if (cond) {
      return WrapBinding(program, cond);
    }
    Py_RETURN_NONE;
  }
  return PyObject_GenericGetAttr(self, attr);
}

static int CFGNodeSetAttro(PyObject* self, PyObject* attr, PyObject* val) {
  CHECK(self != nullptr);
  CHECK(Py_TYPE(self) == &PyCFGNode);
  PyCFGNodeObj* cfg_node = reinterpret_cast<PyCFGNodeObj*>(self);

  if (PyObject_RichCompareBool(attr, k_condition, Py_EQ) > 0) {
    if (Py_TYPE(val) == &PyBinding) {
      PyBindingObj* condition = reinterpret_cast<PyBindingObj*>(val);
      cfg_node->cfg_node->set_condition(condition->attr);
    } else if (val == Py_None) {
      cfg_node->cfg_node->set_condition(nullptr);
    } else {
      PyErr_SetString(PyExc_ValueError, "condition must be a Binding or None");
      return -1;
    }
    return 0;
  }
  return PyObject_GenericSetAttr(self, attr, val);
}

static void CFGNodeDealloc(PyObject* self) {
  CHECK(self && Py_TYPE(self) == &PyCFGNode);
  PyCFGNodeObj* cfg_node = reinterpret_cast<PyCFGNodeObj*>(self);
  RemoveFromCache(cfg_node->program, cfg_node->cfg_node);
  Py_DECREF(cfg_node->program);
  PyObject_Del(self);
}

static PyObject* CFGNodeRepr(PyObject* self) {
  PyCFGNodeObj* py_node = reinterpret_cast<PyCFGNodeObj*>(self);
  auto node = py_node->cfg_node;
  PyObject* str = PyString_FromFormat(
      "<cfgnode %zu %s", node->id(), node->name().c_str());
  if (node->condition()) {
    PyObject* cond_str = PyString_FromFormat(
        " condition:%zu",
        node->condition()->variable()->id());
#if PY_MAJOR_VERSION >= 3
    PyObject* str_cond_str = PyUnicode_Concat(str, cond_str);
    // Drop references to the old |str| and |cond_str| as we do not need them
    // anymore.
    Py_DECREF(str);
    Py_DECREF(cond_str);
    str = str_cond_str;
#else
    PyString_ConcatAndDel(&str, cond_str);
#endif
  }
#if PY_MAJOR_VERSION >= 3
  PyObject* final_str = PyUnicode_Concat(str, PyString_FromString(">"));
  // Drop reference to |str| as we do not need it anymore.
  Py_DECREF(str);
  str = final_str;
#else
  PyString_ConcatAndDel(&str, PyString_FromString(">"));
#endif
  return str;
}

PyDoc_STRVAR(connect_new_doc,
    "Add a new node connected to this node.");

static PyObject* ConnectNew(PyCFGNodeObj* self,
                            PyObject* args, PyObject* kwargs) {
  PyProgramObj* program = self->program;
  static char *kwlist[] = {"name", "condition", nullptr};
  PyObject* name_obj = nullptr;
  const char* name = "None";
  PyObject* condition_obj = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|OO", kwlist, &name_obj,
                                   &condition_obj))
    return nullptr;
  if (name_obj) {
    name_obj = PyObject_Str(name_obj);
    name = PyString_AsString(name_obj);
    Py_DECREF(name_obj);
  }

  if (!condition_obj || condition_obj == Py_None) {
    return WrapCFGNode(program, self->cfg_node->ConnectNew(name, nullptr));
  } else if (PyObject_TypeCheck(condition_obj, &PyBinding)) {
    auto cond = reinterpret_cast<PyBindingObj*>(condition_obj);
    return WrapCFGNode(program, self->cfg_node->ConnectNew(name, cond->attr));
  } else {
    PyErr_SetString(PyExc_TypeError, "condition must be a Binding or None.");
    return nullptr;
  }
}

PyDoc_STRVAR(connect_to_doc,
    "Connect this node to an existing node.");

static PyObject* ConnectTo(PyCFGNodeObj* self,
                           PyObject* args, PyObject* kwargs) {
  PyCFGNodeObj* node;
  if (!PyArg_ParseTuple(args, "O!", &PyCFGNode, &node))
    return nullptr;
  self->cfg_node->ConnectTo(node->cfg_node);
  Py_RETURN_NONE;
}

PyDoc_STRVAR(
    has_combination_doc,
    "Query whether a combination is possible.\n\n"
    "Query whether it's possible to have the given combination of Bindings at "
    "this CFG node. (i.e. whether they can all be assigned at the same time.) "
    "This is used, for example, to tell us if a return binding is possible "
    "given a specific combination of argument bindings.");

static PyObject* HasCombination(PyCFGNodeObj* self,
                                PyObject* args, PyObject* kwargs) {
  PyProgramObj* program = self->program;
  static char *kwlist[] = {"attrs", nullptr};
  PyObject* list = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O!", kwlist,
                                   &PyList_Type, &list))
    return nullptr;
  if (!VerifyListOfBindings(list, program)) return nullptr;
  int length = PyList_Size(list);
  std::vector<const typegraph::Binding*> attrs(length);
  for (int i = 0; i < length; i++) {
    auto item = reinterpret_cast<PyBindingObj*>(PyList_GET_ITEM(list, i));
    attrs[i] = item->attr;
  }
  if (self->cfg_node->HasCombination(attrs)) {
    Py_RETURN_TRUE;
  } else {
    Py_RETURN_FALSE;
  }
}

PyDoc_STRVAR(
    can_have_combo_doc,
    "CanHaveCombination([attr, att2, ...]) -> bool\n\n"
    "Faster but less correct version of HasCombination.");

static PyObject* CanHaveCombination(PyCFGNodeObj* self,
                                    PyObject* args, PyObject* kwargs) {
  PyProgramObj* program = self->program;
  static char *kwlist[] = {"attrs", nullptr};
  PyObject* list = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O!", kwlist,
                                   &PyList_Type, &list))
    return nullptr;
  if (!VerifyListOfBindings(list, program)) return nullptr;
  int length = PyList_Size(list);
  std::vector<const typegraph::Binding*> attrs(length);
  for (int i = 0; i < length; i++) {
    auto item = reinterpret_cast<PyBindingObj*>(PyList_GET_ITEM(list, i));
    attrs[i] = item->attr;
  }
  if (self->cfg_node->CanHaveCombination(attrs)) {
    Py_RETURN_TRUE;
  } else {
    Py_RETURN_FALSE;
  }
}

static PyMethodDef cfg_node_methods[] = {
  {"ConnectNew", reinterpret_cast<PyCFunction>(ConnectNew),
    METH_VARARGS|METH_KEYWORDS, connect_new_doc},
  {"ConnectTo", reinterpret_cast<PyCFunction>(ConnectTo),
    METH_VARARGS|METH_KEYWORDS, connect_to_doc},
  {"HasCombination", reinterpret_cast<PyCFunction>(HasCombination),
    METH_VARARGS|METH_KEYWORDS, has_combination_doc},
  {"CanHaveCombination", reinterpret_cast<PyCFunction>(CanHaveCombination),
    METH_VARARGS|METH_KEYWORDS, can_have_combo_doc},
  {0, 0, 0, nullptr}  // sentinel
};

PyDoc_STRVAR(cfg_node_doc,
    "A node in the CFG.\n\n"
    "Assignments within one CFGNode are treated as unordered: e.g. if "
    "\"x = x + 1\" is in a single CFGNode, both bindings for x will be visible "
    "inside that node.");

PyTypeObject PyCFGNode = {
  PyVarObject_HEAD_INIT(&PyType_Type, 0) tp_name : "CFGNode",
  tp_basicsize : sizeof(PyCFGNodeObj),
  tp_itemsize : 0,
  tp_dealloc : CFGNodeDealloc,
  tp_print : nullptr,
  tp_getattr : nullptr,
  tp_setattr : nullptr,
#if PY_VERSION_HEX >= 0x03050000  // 3.5
  tp_as_async : nullptr,
#else
  tp_compare : nullptr,
#endif
  tp_repr : CFGNodeRepr,
  tp_as_number : nullptr,
  tp_as_sequence : nullptr,
  tp_as_mapping : nullptr,
  tp_hash : nullptr,
  tp_call : nullptr,
  tp_str : CFGNodeRepr,
  tp_getattro : CFGNodeGetAttro,
  tp_setattro : CFGNodeSetAttro,
  tp_as_buffer : nullptr,
  tp_flags : 0,
  tp_doc : cfg_node_doc,
  tp_traverse : nullptr,
  tp_clear : nullptr,
  tp_richcompare : nullptr,
  tp_weaklistoffset : 0,
  tp_iter : nullptr,
  tp_iternext : nullptr,
  tp_methods : cfg_node_methods,
};

// --- Origin --------------------------------------------------------------

static PyTypeObject PyOrigin = {
  // initialized in inittypegraph
  PyVarObject_HEAD_INIT(nullptr, 0)
  tp_name: nullptr
};

PyDoc_STRVAR(origin_doc,
             "An \"origin\" is an explanation of how a binding was "
             "constructed. It consists "
             "of a CFG node and a set of sourcesets.");

static PyStructSequence_Field origin_fields[] = {
    {"where", "CFG Node where this assignment happened."},
    {"source_sets", "Possible sets of source bindings used to construct this."},
    {nullptr}};

static PyStructSequence_Desc origin_desc = {
  name: "Origin",
  doc: origin_doc,
  fields: origin_fields,
  n_in_sequence: 2,
};

// --- Binding ---------------------------------------------------------------

static void BindingDealloc(PyObject* self) {
  CHECK(self && Py_TYPE(self) == &PyBinding);
  PyBindingObj* attr = reinterpret_cast<PyBindingObj*>(self);
  RemoveFromCache(attr->program, attr->attr);
  Py_DECREF(attr->program);
  PyObject_Del(self);
}

static PyObject* BindingRepr(PyObject* self) {
  PyBindingObj* attr = reinterpret_cast<PyBindingObj*>(self);
  PyObject* py_id = PyObject_GetAttrString(self, "id");
  size_t id;
  if (!py_id) {
    PyErr_Clear();
    id = reinterpret_cast<size_t>(attr->attr->data());
  } else {
    id = PyInt_AsLong(py_id);
    if (id == -1 && PyErr_Occurred())
      return nullptr;
  }
  return PyString_FromFormat(
      "<binding of variable %zu to data %zu>",
      attr->attr->variable()->id(), id);
}

static PyObject* BindingGetAttro(PyObject* self, PyObject* attr) {
  CHECK(self && Py_TYPE(self) == &PyBinding);
  PyBindingObj* a = reinterpret_cast<PyBindingObj*>(self);
  PyProgramObj* program = a->program;

  if (PyObject_RichCompareBool(attr, k_variable, Py_EQ) > 0) {
    return WrapVariable(program, a->attr->variable());
  } else if (PyObject_RichCompareBool(attr, k_origins, Py_EQ) > 0) {
    PyObject* py_origins = PyList_New(0);
    for (const auto& origin : a->attr->origins()) {
      PyObject* py_origin = PyStructSequence_New(&PyOrigin);
      PyStructSequence_SET_ITEM(py_origin, 0, WrapCFGNode(program,
          origin->where));
      PyObject* py_source_sets = PyList_New(0);
      for (const typegraph::SourceSet& source_set : origin->source_sets) {
        PyObject* py_source_set = PySet_New(0);
        for (typegraph::Binding* source : source_set) {
          PyObject* binding = WrapBinding(program, source);
          PySet_Add(py_source_set, binding);
          Py_DECREF(binding);
        }
        PyList_Append(py_source_sets, py_source_set);
        Py_DECREF(py_source_set);
      }
      // Do not DECREF on |py_source_sets| as PyStructSequence_SET_ITEM
      // steals the reference.
      PyStructSequence_SET_ITEM(py_origin, 1, py_source_sets);
      PyList_Append(py_origins, py_origin);
      Py_DECREF(py_origin);
    }
    return py_origins;
  } else if (PyObject_RichCompareBool(attr, k_data, Py_EQ) > 0) {
    PyObject* data = static_cast<PyObject*>(a->attr->data());
    Py_INCREF(data);
    return data;
  }
  return PyObject_GenericGetAttr(self, attr);
}

PyDoc_STRVAR(
    is_visible_doc,
    "Can we \"see\" this binding from the given CFGNode?\n\n"
    "This will run a solver to determine if there's a path through the program "
    "that makes a variable have this binding at the given CFGNode.");

static PyObject* IsVisible(PyBindingObj* self, PyObject* args,
                           PyObject* kwargs) {
  static char *kwlist[] = {"where", nullptr};
  PyCFGNodeObj* node;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O!", kwlist,
                                   &PyCFGNode, &node))
    return nullptr;
  if (self->attr->IsVisible(node->cfg_node)) {
    Py_RETURN_TRUE;
  } else {
    Py_RETURN_FALSE;
  }
}

PyDoc_STRVAR(add_origin_doc, "Add another possible origin to this binding.");

static PyObject* AddOrigin(PyBindingObj* self, PyObject* args,
                           PyObject* kwargs) {
  static char *kwlist[] = {"where", "source_set", nullptr};
  PyCFGNodeObj* where;
  PyObject* source_set;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O!O", kwlist,
                                   &PyCFGNode, &where, &source_set))
    return nullptr;
  if (!ContainerToSourceSet(&source_set, self->program))
    return nullptr;
  if (!source_set) {
    PyErr_SetString(PyExc_TypeError,
                    "source_set must be a sequence of cfg.Binding objects");
    return nullptr;
  }
  self->attr->AddOrigin(where->cfg_node, ParseBindingList(source_set));
  Py_RETURN_NONE;
}

PyDoc_STRVAR(assign_to_new_variable_doc,
             "Assign this binding to a new variable.");

static PyObject* AssignToNewVariable(PyBindingObj* self, PyObject* args,
                                     PyObject* kwargs) {
  static char* kwlist[] = {"where", nullptr};
  PyObject* where_obj = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|O", kwlist, &where_obj))
    return nullptr;
  typegraph::CFGNode* where;
  if (!IsCFGNodeOrNone(where_obj, &where)) {
    PyErr_SetString(PyExc_TypeError, "where must be a CFGNode or None.");
    return nullptr;
  }
  typegraph::Variable* v = self->program->program->NewVariable();
  PyObject* data = reinterpret_cast<PyObject*>(self->attr->data());
  Py_XINCREF(data);
  typegraph::Binding* binding = v->AddBinding(data);
  binding->CopyOrigins(self->attr, where);
  return WrapVariable(self->program, v);
}

PyDoc_STRVAR(has_source_doc, "Does this binding depend on a given source?");

static PyObject* HasSource(PyBindingObj* self, PyObject* args,
                           PyObject* kwargs) {
  static char* kwlist[] = {"binding", nullptr};
  PyBindingObj* binding;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O!", kwlist, &PyBinding,
                                   &binding))
    return nullptr;
  if (self->attr->HasSource(binding->attr)) {
    Py_RETURN_TRUE;
  } else {
    Py_RETURN_FALSE;
  }
}

static PyMethodDef binding_methods[] = {
    {"IsVisible", reinterpret_cast<PyCFunction>(IsVisible),
     METH_VARARGS | METH_KEYWORDS, is_visible_doc},
    {"AddOrigin", reinterpret_cast<PyCFunction>(AddOrigin),
     METH_VARARGS | METH_KEYWORDS, add_origin_doc},
    {"AssignToNewVariable", reinterpret_cast<PyCFunction>(AssignToNewVariable),
     METH_VARARGS | METH_KEYWORDS, assign_to_new_variable_doc},
    {"HasSource", reinterpret_cast<PyCFunction>(HasSource),
     METH_VARARGS | METH_KEYWORDS, has_source_doc},
    {0, 0, 0, nullptr},  // sentinel
};

PyDoc_STRVAR(
    binding_doc,
    "A Binding assigns data to a (specific) variable.\n\n"
    "Bindings will therefore be stored in a dictionary in the Variable class, "
    "mapping strings to Binding instances.\n"
    "Depending on context, a Binding might also be called a \"Source\" (if "
    "it's used for creating another Binding) or a \"goal\" (if we want to find "
    "a solution for a path through the program that assigns it).\n\n"
    "A Binding has history (\"origins\"): It knows where the Binding was "
    "originally retrieved from, before being assigned to something else here."
    "Origins contain, through source sets, \"sources\", which are other "
    "Bindings.");

PyTypeObject PyBinding = {
  PyVarObject_HEAD_INIT(&PyType_Type, 0) tp_name : "Binding",
  tp_basicsize : sizeof(PyBindingObj),
  tp_itemsize : 0,
  tp_dealloc : BindingDealloc,
  tp_print : nullptr,
  tp_getattr : nullptr,
  tp_setattr : nullptr,
#if PY_VERSION_HEX >= 0x03050000  // 3.5
  tp_as_async : nullptr,
#else
  tp_compare : nullptr,
#endif
  tp_repr : BindingRepr,
  tp_as_number : nullptr,
  tp_as_sequence : nullptr,
  tp_as_mapping : nullptr,
  tp_hash : nullptr,
  tp_call : nullptr,
  tp_str : BindingRepr,
  tp_getattro : BindingGetAttro,
  tp_setattro : nullptr,
  tp_as_buffer : nullptr,
  tp_flags : 0,
  tp_doc : binding_doc,
  tp_traverse : nullptr,
  tp_clear : nullptr,
  tp_richcompare : nullptr,
  tp_weaklistoffset : 0,
  tp_iter : nullptr,
  tp_iternext : nullptr,
  tp_methods : binding_methods,
};

// --- Variable ----------------------------------------------------------------

static void VariableDealloc(PyObject* self) {
  CHECK(self && Py_TYPE(self) == &PyVariable);
  PyVariableObj* u = reinterpret_cast<PyVariableObj*>(self);
  RemoveFromCache(u->program, u->u);
  Py_DECREF(u->program);
  PyObject_Del(self);
}

static PyObject* VariableRepr(PyObject* self) {
  PyVariableObj* u = reinterpret_cast<PyVariableObj*>(self);
  return PyString_FromFormat("<Variable v%zu: %zu choices>", u->u->id(),
                             u->u->size());
}

static PyObject* VariableGetAttro(PyObject* self, PyObject* attr) {
  CHECK(self && Py_TYPE(self) == &PyVariable);
  PyVariableObj* u = reinterpret_cast<PyVariableObj*>(self);
  PyProgramObj* program = u->program;

  if (PyObject_RichCompareBool(attr, k_bindings, Py_EQ) > 0) {
    PyObject* list = PyList_New(0);
    for (const auto& attr : u->u->bindings()) {
      PyObject* binding = WrapBinding(program, attr.get());
      PyList_Append(list, binding);
      Py_DECREF(binding);
    }
    return list;
  } else if (PyObject_RichCompareBool(attr, k_data, Py_EQ) > 0) {
    PyObject* list = PyList_New(0);
    for (const auto& attr : u->u->bindings()) {
      PyObject* data = reinterpret_cast<PyObject*>(attr->data());
      // Do not INCREF on |data| as PyList_Append does it internally.
      PyList_Append(list, data);
    }
    return list;
  } else if (PyObject_RichCompareBool(attr, k_id, Py_EQ) > 0) {
    return PyInt_FromLong(u->u->id());
  } else if (PyObject_RichCompareBool(attr, k_program, Py_EQ) > 0) {
    Py_INCREF(program);
    return reinterpret_cast<PyObject*>(program);
  }
  return PyObject_GenericGetAttr(self, attr);
}

static int VariableSetAttro(PyObject* self, PyObject* attr, PyObject* val) {
  CHECK(self != nullptr);
  CHECK(Py_TYPE(self) == &PyVariable);
  return PyObject_GenericSetAttr(self, attr, val);
}

PyDoc_STRVAR(
    variable_prune_doc,
    "Bindings(cfg_node)\n\n"
    "Filters down the possibilities of bindings for this variable, by "
    "analyzing "
    "the control flow graph. Any definition for this variable that is "
    "invisible from the current point in the CFG is filtered out. This "
    "function differs from Filter() in that it only honors the CFG, not the "
    "source sets. As such, it's much faster.");

static PyObject* VariablePrune(PyVariableObj* self,
                               PyObject* args, PyObject* kwargs) {
  static char *kwlist[] = {"cfg_node", nullptr};
  PyObject* cfg_node_obj;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", kwlist, &cfg_node_obj))
    return nullptr;
  typegraph::CFGNode* cfg_node = nullptr;
  if (!IsCFGNodeOrNone(cfg_node_obj, &cfg_node)) {
    PyErr_SetString(PyExc_TypeError, "where must be a CFGNode or None.");
    return nullptr;
  }
  auto bindings = self->u->Prune(cfg_node);
  PyObject* list = PyList_New(0);
  for (typegraph::Binding* attr : bindings) {
    PyObject* binding = WrapBinding(self->program, attr);
    PyList_Append(list, binding);
    Py_DECREF(binding);
  }
  return list;
}

PyDoc_STRVAR(variable_prune_data_doc,
             "Data(cfg_node)\n\n"
             "Like Bindings(cfg_node), but only return the data.\n\n");

static PyObject* VariablePruneData(PyVariableObj* self,
                                         PyObject* args, PyObject* kwargs) {
  static char *kwlist[] = {"cfg_node", nullptr};
  PyObject* cfg_node_obj = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", kwlist, &cfg_node_obj))
    return nullptr;

  typegraph::CFGNode* cfg_node = nullptr;
  if (!IsCFGNodeOrNone(cfg_node_obj, &cfg_node)) {
    PyErr_SetString(PyExc_TypeError, "where must be a CFGNode or None.");
    return nullptr;
  }
  auto bindings = self->u->Prune(cfg_node);
  PyObject* list = PyList_New(0);
  for (typegraph::Binding* attr : bindings) {
    PyObject* data = reinterpret_cast<PyObject*>(attr->data());
    // Do not INCREF on |data| as PyList_Append does that internally.
    PyList_Append(list, data);
  }
  return list;
}

PyDoc_STRVAR(
    variable_filter_doc,
    "Filter(cfg_node)\n\n"
    "Filters down the possibilities of bindings for this variable, by "
    "analyzing the control flow graph and the source sets. Any definition for "
    "this impossible at the current point in the CFG is filtered out.");

static PyObject* VariableFilter(PyVariableObj* self,
                                PyObject* args, PyObject* kwargs) {
  PyProgramObj* program = self->program;
  static char *kwlist[] = {"cfg_node", nullptr};
  PyCFGNodeObj* cfg_node;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", kwlist, &cfg_node))
    return nullptr;
  auto bindings = self->u->Filter(cfg_node->cfg_node);
  PyObject* list = PyList_New(0);
  for (typegraph::Binding* attr : bindings) {
    PyObject* binding = WrapBinding(program, attr);
    PyList_Append(list, binding);
    Py_DECREF(binding);
  }
  return list;
}

PyDoc_STRVAR(variable_filtered_data_doc,
    "FilteredData(cfg_node)\n\n"
    "Like Filter(cfg_node), but only return the data.\n\n");

static PyObject* VariableFilteredData(PyVariableObj* self,
                                      PyObject* args, PyObject* kwargs) {
  static char *kwlist[] = {"cfg_node", nullptr};
  PyCFGNodeObj* cfg_node;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O!", kwlist,
                                   &PyCFGNode, &cfg_node))
    return nullptr;
  auto bindings = self->u->FilteredData(cfg_node->cfg_node);
  PyObject* list = PyList_New(0);
  for (void* attr_data : bindings) {
    PyObject* data = reinterpret_cast<PyObject*>(attr_data);
    // Do not INCREF on |data| as PyList_Append does that internally.
    PyList_Append(list, data);
  }
  return list;
}

PyDoc_STRVAR(variable_add_choice_doc,
             "AddBinding(data, source_set, where)\n\n"
             "Adds another option to this variable.\n\n"
             "This will not overwrite this variable in the current CFGNode. "
             "(It's legitimate to have multiple bindings for a variable on the "
             "same CFGNode, e.g. if a union type is introduced at that node.)");

static PyObject* VariableAddBinding(PyVariableObj* self, PyObject* args,
                                    PyObject* kwargs) {
  PyProgramObj* program = self->program;
  static char* kwlist[] = {"data", "source_set", "where", nullptr};
  PyObject* data = nullptr;
  PyObject* source_set = nullptr;
  PyObject* where_obj = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|OO", kwlist, &data,
                                   &source_set, &where_obj))
    return nullptr;
  if (!where_obj != !source_set) {
    PyErr_SetString(PyExc_ValueError,
                    "Either specify both where and source_set, or neither.");
    return nullptr;
  }

  typegraph::CFGNode* where = nullptr;
  if (!IsCFGNodeOrNone(where_obj, &where)) {
    PyErr_SetString(PyExc_TypeError, "where must be a CFGNode or None.");
    return nullptr;
  }
  if (where && where->program() != program->program) {
    PyErr_SetString(PyExc_AttributeError,
                    "Passing Binding from different program");
    return nullptr;
  }

  if (!ContainerToSourceSet(&source_set, program))
    return nullptr;

  Py_INCREF(data);
  typegraph::Binding* attr = self->u->AddBinding(data);
  if (where && source_set) {
    typegraph::Origin* origin = attr->AddOrigin(where);
    origin->AddSourceSet(ParseBindingList(source_set));
  }
  Py_XDECREF(source_set);
  return WrapBinding(program, attr);
}

PyDoc_STRVAR(variable_add_bindings_doc,
             "AddBindings(variable)\n\n"
             "Adds all the Bindings from another variable to this one.");

static PyObject* VariableAddBindings(PyVariableObj* self, PyObject* args,
                                     PyObject* kwargs) {
  static char *kwlist[] = {"variable", "where", nullptr};
  PyVariableObj* variable = nullptr;
  PyCFGNodeObj* where = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O!O!", kwlist,
                                   &PyVariable, &variable,
                                   &PyCFGNode, &where)) {
    return nullptr;
  }
  for (const auto& binding : variable->u->bindings()) {
    PyObject* data = reinterpret_cast<PyObject*>(binding->data());
    Py_XINCREF(data);
    typegraph::Binding* copy = self->u->AddBinding(data);
    copy->CopyOrigins(binding.get(), where->cfg_node);
  }
  Py_RETURN_NONE;
}

PyDoc_STRVAR(
    var_assign_to_new_variable_doc,
    "Assign this variable to a new variable.\n\n"
    "This is essentially a copy: All entries in the Union will be copied to "
    "the new variable, but with the corresponding current variable binding "
    "as an origin.");

static PyObject* VarAssignToNewVariable(PyVariableObj* self,
                                        PyObject* args, PyObject* kwargs) {
  static char* kwlist[] = {"where", nullptr};
  PyObject* where_obj = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|O", kwlist, &where_obj))
    return nullptr;
  typegraph::CFGNode* where;
  if (!IsCFGNodeOrNone(where_obj, &where)) {
    PyErr_SetString(PyExc_TypeError, "where must be a CFGNode or None.");
    return nullptr;
  }
  typegraph::Variable* v = self->program->program->NewVariable();
  for (const auto& binding : self->u->bindings()) {
    PyObject* data = reinterpret_cast<PyObject*>(binding->data());
    Py_XINCREF(data);
    typegraph::Binding* copy = v->AddBinding(data);
    copy->CopyOrigins(binding.get(), where);
  }
  return WrapVariable(self->program, v);
}

PyDoc_STRVAR(
    variable_paste_variable_doc,
    "Adds all the bindings from another variable to this one.");

static PyObject* VariablePasteVariable(PyVariableObj* self, PyObject* args,
                                       PyObject* kwargs) {
  static char *kwlist[] = {"variable", "where", "additional_sources", nullptr};
  PyVariableObj* variable;
  PyObject* where_obj = nullptr;
  PyObject* additional = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O!|OO", kwlist,
                                   &PyVariable, &variable,
                                   &where_obj, &additional)) {
    return nullptr;
  }

  typegraph::CFGNode* where;
  if (!IsCFGNodeOrNone(where_obj, &where)) {
    PyErr_SetString(PyExc_TypeError, "where should be a CFGNode or None.");
    return nullptr;
  }
  // PasteVariable expects a SourceSet for additional sources, so convert the
  // given sequence to a SourceSet after verifying its contents.
  typegraph::SourceSet additional_sources;
  if (!ContainerToSourceSet(&additional, self->program)) {
    return nullptr;
  }
  if (additional) {
    auto additional_list = ParseBindingList(additional);
    additional_sources = typegraph::SourceSet(
        additional_list.begin(), additional_list.end());
  }
  Py_XDECREF(additional);
  self->u->PasteVariable(variable->u, where, additional_sources);
  Py_RETURN_NONE;
}

PyDoc_STRVAR(
    variable_paste_binding_doc,
    "Adds a Binding from another variable to this one.");

static PyObject* VariablePasteBinding(PyVariableObj* self, PyObject* args,
                                      PyObject* kwargs) {
  static char *kwlist[] = {"binding", "where", "additional_sources", nullptr};
  PyBindingObj* binding;
  PyObject* where_obj = nullptr;
  PyObject* additional = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O!|OO", kwlist,
                                   &PyBinding, &binding,
                                    &where_obj, &additional)) {
    return nullptr;
  }
  typegraph::CFGNode* where;
  if (!IsCFGNodeOrNone(where_obj, &where)) {
    PyErr_SetString(PyExc_TypeError, "where must be a CFGNode or None.");
    return nullptr;
  }

  // PasteBinding expects a SourceSet for additional sources.
  typegraph::SourceSet additional_sources;
  if (!ContainerToSourceSet(&additional, self->program)) {
    return nullptr;
  }
  if (additional) {
    auto additional_list = ParseBindingList(additional);
    additional_sources = typegraph::SourceSet(
        additional_list.begin(), additional_list.end());
  }
  Py_XDECREF(additional);
  self->u->PasteBinding(binding->attr, where, additional_sources);
  Py_RETURN_NONE;
}

static PyMethodDef variable_methods[] = {
    {"Bindings", reinterpret_cast<PyCFunction>(VariablePrune),
     METH_VARARGS | METH_KEYWORDS, variable_prune_doc},
    {"Data", reinterpret_cast<PyCFunction>(VariablePruneData),
     METH_VARARGS | METH_KEYWORDS, variable_prune_data_doc},
    {"Filter", reinterpret_cast<PyCFunction>(VariableFilter),
     METH_VARARGS | METH_KEYWORDS, variable_filter_doc},
    {"FilteredData", reinterpret_cast<PyCFunction>(VariableFilteredData),
     METH_VARARGS | METH_KEYWORDS, variable_filtered_data_doc},
    {"AddBinding", reinterpret_cast<PyCFunction>(VariableAddBinding),
     METH_VARARGS | METH_KEYWORDS, variable_add_choice_doc},
    {"AddBindings", reinterpret_cast<PyCFunction>(VariableAddBindings),
     METH_VARARGS | METH_KEYWORDS, variable_add_bindings_doc},
    {"AssignToNewVariable",
     reinterpret_cast<PyCFunction>(VarAssignToNewVariable),
     METH_VARARGS | METH_KEYWORDS, var_assign_to_new_variable_doc},
    {"PasteVariable", reinterpret_cast<PyCFunction>(VariablePasteVariable),
      METH_VARARGS | METH_KEYWORDS, variable_paste_variable_doc},
    {"PasteBinding", reinterpret_cast<PyCFunction>(VariablePasteBinding),
      METH_VARARGS | METH_KEYWORDS, variable_paste_binding_doc},
    {0, 0, 0, nullptr},  // sentinel
};

PyDoc_STRVAR(
    variable_doc,
    "A collection of possible bindings for a variable, along with their "
    "origins.\n\n"
    "A Variable stores the Bindings it can have as well as the CFGNodes at "
    "which the bindings occur. New bindings are added via AddBinding or "
    "PasteVariable.");

PyTypeObject PyVariable = {
  PyVarObject_HEAD_INIT(&PyType_Type, 0) tp_name : "Variable",
  tp_basicsize : sizeof(PyVariableObj),
  tp_itemsize : 0,
  tp_dealloc : VariableDealloc,
  tp_print : nullptr,
  tp_getattr : nullptr,
  tp_setattr : nullptr,
#if PY_VERSION_HEX >= 0x03050000  // 3.5
  tp_as_async : nullptr,
#else
  tp_compare : nullptr,
#endif
  tp_repr : VariableRepr,
  tp_as_number : nullptr,
  tp_as_sequence : nullptr,
  tp_as_mapping : nullptr,
  tp_hash : nullptr,
  tp_call : nullptr,
  tp_str : VariableRepr,
  tp_getattro : VariableGetAttro,
  tp_setattro : VariableSetAttro,
  tp_as_buffer : nullptr,
  tp_flags : 0,
  tp_doc : variable_doc,
  tp_traverse : nullptr,
  tp_clear : nullptr,
  tp_richcompare : nullptr,
  tp_weaklistoffset : 0,
  tp_iter : nullptr,
  tp_iternext : nullptr,
  tp_methods : variable_methods,
};

// --- typegraph ---------------------------------------------------------------

PyDoc_STRVAR(typegraph_doc,
    "Typegraph is a points-to / dataflow / cfg graph engine.\n"
    "It can be used to run reaching-definition queries on a nested CFG graph "
    "and to model path-specific visibility of nested data structures.");

static PyMethodDef typegraph_methods[] = {
  {0, 0, 0, nullptr},  // sentinel
};

#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef typegraph_moduledef = {
  PyModuleDef_HEAD_INIT,
  m_name : kModuleName,
  m_doc : typegraph_doc,
  m_size : -1,
  m_methods : typegraph_methods,
#if PY_VERSION_HEX >= 0x03050000  // 3.5
  m_slots : nullptr,
#else
  m_reload : nullptr,
#endif
  m_traverse : nullptr,
  m_clear : &pytype::typegraph::internal::CFGLogger::Shutdown,
  m_free : nullptr,
};
#endif

static PyObject* InitModule(PyObject* module) {
  PyObject* module_dict = PyModule_GetDict(module);
  if (PyOrigin.tp_name == 0)
    PyStructSequence_InitType(&PyOrigin, &origin_desc);
  PyDict_SetItemString(module_dict, "Program",
                       reinterpret_cast<PyObject*>(&PyProgram));
  PyDict_SetItemString(module_dict, "CFGNode",
                       reinterpret_cast<PyObject*>(&PyCFGNode));
  PyDict_SetItemString(module_dict, "Origin",
                       reinterpret_cast<PyObject*>(&PyOrigin));
  PyDict_SetItemString(module_dict, "Binding",
                       reinterpret_cast<PyObject*>(&PyBinding));
  PyDict_SetItemString(module_dict, "Variable",
                       reinterpret_cast<PyObject*>(&PyVariable));

  Py_XDECREF(k_entrypoint);
  k_entrypoint = PyString_FromString("entrypoint");
  Py_XDECREF(k_incoming);
  k_incoming = PyString_FromString("incoming");
  Py_XDECREF(k_outgoing);
  k_outgoing = PyString_FromString("outgoing");
  Py_XDECREF(k_data);
  k_data = PyString_FromString("data");
  Py_XDECREF(k_name);
  k_name = PyString_FromString("name");
  Py_XDECREF(k_variable);
  k_variable = PyString_FromString("variable");
  Py_XDECREF(k_origins);
  k_origins = PyString_FromString("origins");
  Py_XDECREF(k_where);
  k_where = PyString_FromString("where");
  Py_XDECREF(k_binding);
  k_binding = PyString_FromString("binding");
  Py_XDECREF(k_choices);
  k_choices = PyString_FromString("choices");
  Py_XDECREF(k_bindings);
  k_bindings = PyString_FromString("bindings");
  Py_XDECREF(k_cfg_nodes);
  k_cfg_nodes = PyString_FromString("cfg_nodes");
  Py_XDECREF(k_methods);
  k_methods = PyString_FromString("methods");
  Py_XDECREF(k_variables);
  k_variables = PyString_FromString("variables");
  Py_XDECREF(k_program);
  k_program = PyString_FromString("program");
  Py_XDECREF(k_id);
  k_id = PyString_FromString("id");
  Py_XDECREF(k_next_variable_id);
  k_next_variable_id = PyString_FromString("next_variable_id");
  Py_XDECREF(k_condition);
  k_condition = PyString_FromString("condition");
  Py_XDECREF(k_default_data);
  k_default_data = PyString_FromString("default_data");
  return module;
}

#if PY_MAJOR_VERSION >= 3
PyMODINIT_FUNC PyInit_cfg(void) {
  PyObject* module = PyModule_Create(&typegraph_moduledef);
  pytype::typegraph::internal::CFGLogger::Init();
  return InitModule(module);
}
#else
PyMODINIT_FUNC initcfg(void) {
  PyObject* module = Py_InitModule3(
      kModuleName, typegraph_methods, typegraph_doc);
  PyType_Ready(&PyProgram);
  PyType_Ready(&PyCFGNode);
  PyType_Ready(&PyVariable);
  PyType_Ready(&PyBinding);
  InitModule(module);
  pytype::typegraph::internal::CFGLogger::Init();
}
#endif
