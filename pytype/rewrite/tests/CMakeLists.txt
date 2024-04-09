add_package()

py_library(
  NAME
    test_utils
  SRCS
    test_utils.py
  DEPS
    pytype.blocks.blocks
    pytype.pyc.pyc
    pytype.pytd.parse.parser_test_base
    pytype.rewrite.context
    pytype_extensions.instrumentation_for_testing
)

py_test(
  NAME
    test_basic
  SRCS
    test_basic.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    test_utils_test
  SRCS
    test_utils_test.py
  DEPS
    .test_utils
    pytype.pyc.pyc
)
