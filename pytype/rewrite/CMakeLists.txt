add_package()

py_library(
  NAME
    rewrite
  DEPS
    .abstract
    .analyze
    .frame
    .vm
)

py_library(
  NAME
    abstract
  SRCS
    abstract.py
)

py_test(
  NAME
    abstract_test
  SRCS
    abstract_test.py
  DEPS
    .abstract
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
    frame
  SRCS
    frame.py
  DEPS
    .abstract
    pytype.blocks.blocks
    pytype.rewrite.flow.flow
)

py_test(
  NAME
    frame_test
  SRCS
    frame_test.py
  DEPS
    .abstract
    .frame
    pytype.blocks.blocks
    pytype.pyc.pyc
    pytype.rewrite.flow.flow
    pytype.rewrite.tests.test_utils
)

py_library(
  NAME
    vm
  SRCS
    vm.py
  DEPS
    .abstract
    .frame
    pytype.blocks.blocks
    pytype.rewrite.flow.flow
)

py_test(
  NAME
    vm_test
  SRCS
    vm_test.py
  DEPS
    .vm
    pytype.pyc.pyc
    pytype.rewrite.tests.test_utils
)

add_subdirectory(flow)
add_subdirectory(tests)
