add_package()

py_library(
  NAME
    blocks
  DEPS
    .blocks_impl
    .process_blocks
)

py_library(
  NAME
    blocks_impl
  SRCS
    blocks.py
  DEPS
    pytype.pyc.pyc
    pytype.typegraph.cfg_utils
)

py_library(
  NAME
    process_blocks
  SRCS
    process_blocks.py
  DEPS
    .blocks_impl
    pytype.pyc.pyc
)

py_library(
  NAME
    block_serializer
  SRCS
    block_serializer.py
  DEPS
    .blocks_impl
)

py_library(
  NAME
    init
  SRCS
    __init__.py
)

py_test(
  NAME
    blocks_test
  SRCS
    blocks_test.py
  DEPS
    .blocks_impl
    .process_blocks
    pytype.directors.annotations
    pytype.pyc.pyc
    pytype.tests.test_base
)
