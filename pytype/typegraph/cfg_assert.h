// A wrapper for asserting with a message.

#ifndef DEVTOOLS_PYTHON_TYPEGRAPH_ASSERT_H
#define DEVTOOLS_PYTHON_TYPEGRAPH_ASSERT_H

#include <iostream>
#include <exception>

namespace devtools_python_typegraph {

#define CFG_ASSERT(cond) assert(cond)
#define CFG_ASSERT_MSG(cond, msg) \
  do { \
    if (!(cond)) { \
      std::cerr << msg << std::endl; \
      std::terminate(); \
    } \
  } while(false);

}  // namespace devtools_python_typegraph

#endif  // DEVTOOLS_PYTHON_TYPEGRAPH_ASSERT_H
