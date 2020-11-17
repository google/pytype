py_library(
  NAME
    visitor
  SRCS
    visitor.py
    debug.py
)

py_test(
  NAME
    visitor_test
  SRCS
    visitor_test.py
  DEPS
    .visitor
    pytype.tests.test_base
)

