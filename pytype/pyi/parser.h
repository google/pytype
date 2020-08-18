#ifndef PYTYPE_PYI_PARSER_H_
#define PYTYPE_PYI_PARSER_H_

#include <vector>
#include <Python.h>

#include "location.hh"
#include "refholder.h"

namespace pytype {

// Selector codes for retrieving values from the Context.
enum ValueSelector {
  kEllipsis = 0,  // First value must be 0.
  kParseError,
  kNothing,
  kAnything,
  kTuple,

  // This must be last, it isn't an actual selector.
  kValueSelectorCount
};

// Selector codes for calling a peer's methods via the Context.
enum CallSelector {
  kSetErrorLocation = 0,  // First value must be 0.
  kNewType,
  kNewUnionType,
  kNewIntersectionType,
  kAddImport,
  kAddAliasOrConstant,
  kNewAliasOrConstant,
  kNewClass,
  kNewConstant,
  kNewFunction,
  kNewNamedTuple,
  kNewTypedDict,
  kRegisterClassName,
  kAddTypeVar,

  kIfBegin,
  kIfElif,
  kIfElse,
  kIfEnd,

  // This must be last, it isn't an actual selector.
  kCallSelectorCount,
};


// A context manages interaction with the python side of the parser (referred
// to as the "peer").
class Context {
 public:
  Context() : initialized_(false), result_(Py_None) {}

  // Returns true iff initialization was successful.
  bool Init(PyObject* peer);

  // Returns a new reference to the selected value.
  PyObject* Value(ValueSelector selector) const;

  // Call the corresponding method in the peer building the arguments from
  // the specified format and additional args.
  PyObject* Call(CallSelector selector, const char* fmt, ...) const;

  // Call the peer's kSetErrorLocation method.
  void SetErrorLocation(const location& loc) const;

  // Get the result object (a borrowed reference).
  PyObject* GetResult() const { return result_; }

  // Set the result object, consuming the reference.
  void SetAndDelResult(PyObject* result) {
    result_ = result;
    Py_XDECREF(result);
  }

 private:
  bool initialized_;
  RefHolder values_[kValueSelectorCount];
  RefHolder callables_[kCallSelectorCount];
  RefHolder result_;
};

}  // end namespace pytype

#endif  // PYTYPE_PYI_PARSER_H_
