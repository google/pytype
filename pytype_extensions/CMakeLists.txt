add_package()

py_library(
  NAME
    pytype_extensions
  SRCS
    __init__.py
)

py_test(
  NAME
    test_pytype_extensions
  SRCS
    test_pytype_extensions.py
  DEPS
    pytype.api
    pytype.pytd.api
    pytype.tests.test_base
)

py_library(
  NAME
    instrumentation_for_testing
  SRCS
    instrumentation_for_testing.py
)

py_test(
  NAME
    instrumentation_for_testing_test
  SRCS
    instrumentation_for_testing_test.py
  DEPS
    .instrumentation_for_testing
    .pytype_extensions
)
