add_package()

py_library(
  NAME
    variables
  SRCS
    variables.py
)

py_test(
  NAME
    variables_test
  SRCS
    variables_test.py
  DEPS
    .variables
)

py_library(
  NAME
    rewrite
)
