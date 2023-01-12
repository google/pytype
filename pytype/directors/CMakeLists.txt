add_package()

py_library(
  NAME
    directors
  DEPS
    ._directors
    .blocks
    .init
    .parser
    .parser_libcst
)

py_library(
  NAME
    blocks
  SRCS
    blocks.py
  DEPS
    pytype.pyc.pyc
    pytype.typegraph.cfg_utils
)

py_library(
  NAME
    _directors
  SRCS
    directors.py
  DEPS
    .blocks
    .parser
    .parser_libcst
    pytype.config
)

py_library(
  NAME
    init
  SRCS
    __init__.py
)

py_library(
  NAME
    parser
  SRCS
    parser.py
  DEPS
    pytype.ast.ast
)

py_library(
  NAME
    parser_libcst
  SRCS
    parser_libcst.py
  DEPS
    pytype.utils
)

py_test(
  NAME
    blocks_test
  SRCS
    blocks_test.py
  DEPS
    .blocks
    pytype.pyc.pyc
    pytype.tests.test_base
)

py_test(
  NAME
    directors_test
  SRCS
    directors_test.py
  DEPS
    .blocks
    .directors
    pytype.errors
    pytype.pyc.pyc
)
