add_package()

py_library(
    NAME
      definitions
    SRCS
      definitions.py
      definitions.pyi
)

py_test(
    NAME
      definitions_test
    SRCS
      definitions_test.py
    DEPS
      .definitions
)
