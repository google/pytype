add_package()

py_library(
  NAME
    flow
  DEPS
    .conditions
    .state
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
    state
  SRCS
    state.py
  DEPS
    .conditions
    .variables
)

py_test(
  NAME
    state_test
  SRCS
    state_test.py
  DEPS
    .conditions
    .state
    .variables
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
    .conditions
    .variables
)

py_library(
  NAME
    vm_base
  SRCS
    vm_base.py
  DEPS
    .state
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
    .state
    .vm_base
    pytype.pyc.pyc
    pytype.rewrite.tests.test_utils
)
