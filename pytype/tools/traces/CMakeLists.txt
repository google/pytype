add_package()

py_library(
  NAME
    source
  SRCS
    source.py
)

py_test(
  NAME
    source_test
  SRCS
    source_test.py
  DEPS
    .source
)

py_library(
  NAME
    visitor
  SRCS
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
