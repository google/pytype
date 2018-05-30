add_package()

py_library(
  NAME
    test_base
  SRCS
    test_base.py
  DEPS
    pytype.libvm
)

py_test(
  NAME
    test_abc
  SRCS
    test_abc.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_basic
  SRCS
    test_basic.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_anystr
  SRCS
    test_anystr.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_match
  SRCS
    test_match.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_decorators
  SRCS
    test_decorators.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_exceptions
  SRCS
    test_exceptions.py
  DEPS
    .test_base
)

py_test(
  NAME
    test_functions
  SRCS
    test_functions.py
  DEPS
    .test_base
)
