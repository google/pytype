add_package()

py_library(
  NAME
    visitor
  SRCS
    debug.py
    visitor.py
)

py_test(
  NAME
    visitor_test
  SRCS
    visitor_test.py
  DEPS
    .visitor
)
