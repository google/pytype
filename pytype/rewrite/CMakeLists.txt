add_package()

py_library(
  NAME
    rewrite
  DEPS
    .analyze
    .vm
)

py_library(
  NAME
    analyze
  SRCS
    analyze.py
  DEPS
    .vm
    pytype.config
    pytype.errors
    pytype.load_pytd
    pytype.blocks.blocks
    pytype.pyc.pyc
    pytype.pytd.pytd
)

py_test(
  NAME
    analyze_test
  SRCS
    analyze_test.py
  DEPS
    .analyze
    pytype.config
    pytype.load_pytd
    pytype.pytd.pytd
)

py_library(
  NAME
    vm
  SRCS
    vm.py
  DEPS
    pytype.blocks.blocks
    pytype.rewrite.flow.flow
)

add_subdirectory(flow)
