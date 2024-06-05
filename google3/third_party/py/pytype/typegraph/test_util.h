// A collection of helper functions for use with typegraph unit tests.
#ifndef PYTYPE_TYPEGRAPH_TEST_UTIL_H_
#define PYTYPE_TYPEGRAPH_TEST_UTIL_H_

#include <memory>
#include <utility>
#include <vector>

#include "typegraph.h"

namespace devtools_python_typegraph {

template <typename RawDataType>
inline Binding* AddBinding(Variable* v, RawDataType* raw_data) {
  return v->AddBinding(MakeBindingData(raw_data, nullptr));
}

template <typename RawDataType>
inline Binding* AddBinding(Variable* v,
                           RawDataType* raw_data,
                           CFGNode* where,
                           const std::vector<Binding*>& source_set) {
  return v->AddBinding(MakeBindingData(raw_data, nullptr), where, source_set);
}

template <typename RawDataType>
inline DataType* AsDataType(RawDataType* raw_data) {
  return reinterpret_cast<DataType*>(raw_data);
}

}  // namespace devtools_python_typegraph

#endif  // PYTYPE_TYPEGRAPH_TEST_UTIL_H_
