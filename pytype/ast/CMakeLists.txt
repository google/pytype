add_package()

py_library(
  NAME
    ast
  DEPS
    .debug
    .visitor
)

py_library(
  NAME
    visitor
  SRCS
    visitor.py
)

py_library(
  NAME
    debug
  SRCS
    debug.py
)

py_test(
  NAME
    visitor_test
  SRCS
    visitor_test.py
  DEPS
    .visitor
)
