add_package()

py_library(
  NAME
    parse
  DEPS
    .node
    .parser_constants
    .preconditions
)

py_library(
  NAME
    parser_test_base
  SRCS
    parser_test_base.py
  DEPS
    pytype.libvm
    pytype.pyi.parser
    pytype.pytd.pytd
    pytype.tests.test_base
)

py_library(
  NAME
    preconditions
  SRCS
    preconditions.py
  DEPS
    pytype.utils
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
    .preconditions
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
    preconditions_test
  SRCS
    preconditions_test.py
  DEPS
    .preconditions
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
