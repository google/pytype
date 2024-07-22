// This file provides utility functions for creating unique_ptrs. Because we
// only support C++11, we don't have access to std::make_unique.
// This header is derived from Abseil's memory.h and is provided here to avoid a
// dependency on Abseil.
// Note that these implementations are sufficient only for the typegraph
// library's usage of unique_ptr and do not cover all possible corner cases.
#ifndef PYTYPE_TYPEGRAPH_MEMORY_UTIL_H_
#define PYTYPE_TYPEGRAPH_MEMORY_UTIL_H_

#include <memory>

namespace devtools_python_typegraph {

namespace memory_util {

// make_unique constructs a new object of type T and immediately wraps it in a
// unique_ptr.
template<typename T, typename... Args>
std::unique_ptr<T> make_unique(Args&&... args) {
  return std::unique_ptr<T>(new T(std::forward<Args>(args)...));
}

}  // namespace memory_util

}  // namespace devtools_python_typegraph

#endif  // PYTYPE_TYPEGRAPH_MEMORY_UTIL_H_
