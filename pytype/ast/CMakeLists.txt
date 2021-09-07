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
    visitor_c
  SRCS
    visitor.py
)

py_library(
  NAME
    init
  SRCS
    __init__.py
)

py_library(
  NAME
    visitor
  DEPS
    .init
    .visitor_c
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
