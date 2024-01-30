add_package()

py_library(
  NAME
    rewrite
  DEPS
    .analyze
    .variables
)

py_library(
  NAME
    analyze
  SRCS
    analyze.py
  DEPS
    pytype.config
    pytype.errors
    pytype.load_pytd
    pytype.pytd.pytd
)

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
