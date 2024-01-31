add_package()

py_library(
  NAME
    flow
  DEPS
    .variables
    .vm_base
)

py_library(
  NAME
    variables
  SRCS
    variables.py
)

py_test(
  NAME
    variables_test
  SRCS
    variables_test.py
  DEPS
    .variables
)

py_library(
  NAME
    vm_base
  SRCS
    vm_base.py
  DEPS
    .variables
    pytype.blocks.blocks
)

py_test(
  NAME
    vm_base_test
  SRCS
    vm_base_test.py
  DEPS
    .vm_base
    pytype.blocks.blocks
    pytype.pyc.pyc
    pytype_extensions.instrumentation_for_testing
)
