add_package()

py_library(
  NAME
    directors
  DEPS
    ._directors
    .annotations
    .init
    .parser
    .parser_libcst
)

py_library(
  NAME
    _directors
  SRCS
    directors.py
  DEPS
    .annotations
    .parser
    .parser_libcst
    pytype.config
    pytype.blocks.blocks
)

py_library(
  NAME
    annotations
  SRCS
    annotations.py
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
    directors_test
  SRCS
    directors_test.py
  DEPS
    .directors
    pytype.errors
    pytype.blocks.blocks
    pytype.pyc.pyc
)
