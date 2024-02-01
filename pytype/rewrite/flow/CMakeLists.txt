add_package()

py_library(
  NAME
    flow
  DEPS
    .conditions
    .variables
    .vm_base
)

py_library(
  NAME
    conditions
  SRCS
    conditions.py
)

py_test(
  NAME
    conditions_test
  SRCS
    conditions_test.py
  DEPS
    .conditions
)

py_library(
  NAME
    variables
  SRCS
    variables.py
  DEPS
    .conditions
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
    .conditions
    .variables
    pytype.blocks.blocks
)

py_test(
  NAME
    vm_base_test
  SRCS
    vm_base_test.py
  DEPS
    .conditions
    .vm_base
    pytype.pyc.pyc
    pytype.rewrite.tests.test_utils
)
