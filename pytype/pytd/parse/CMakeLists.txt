add_package()

py_library(
  NAME
    builtins
  SRCS
    builtins.py
  DEPS
    pytype.utils
    pytype.pyi.parser
    pytype.pytd.pytd_for_parser
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
    pytype.metrics
)

py_library(
  NAME
    parser_constants
  SRCS
    parser_constants.py
)

py_library(
  NAME
    parser_test_base
  SRCS
    parser_test_base.py
  DEPS
    pytype.load_pytd
    pytype.pyi.parser
    pytype.pytd.pytd_for_parser
    pytype.tests.test_base
)

py_test(
  NAME
    builtins_test
  SRCS
    builtins_test.py
  DEPS
    .parser_test_base
    pytype.tests.test_base
)

py_test(
  NAME
    preconditions_test
  SRCS
    preconditions_test.py
  DEPS
    .parser_test_base
)

py_test(
  NAME
    node_test
  SRCS
    node_test.py
  DEPS
    .parser_test_base
)

