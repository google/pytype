add_package()

py_library(
  NAME
    parse
  DEPS
    .node
    .parser_constants
)

py_library(
  NAME
    parser_test_base
  SRCS
    parser_test_base.py
  DEPS
    pytype.api
    pytype.pyi.parser
    pytype.pytd.pytd
    pytype.tests.test_base
)

py_library(
  NAME
    node_c
  SRCS
    node.py
)

py_library(
  NAME
    node
  DEPS
    .node_c
    pytype.utils
)

py_library(
  NAME
    parser_constants
  SRCS
    parser_constants.py
)

py_test(
  NAME
    node_test
  SRCS
    node_test.py
  DEPS
    .node
    pytype.pytd.pytd
)
