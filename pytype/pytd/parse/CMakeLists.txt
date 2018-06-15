add_package()

py_test(
  NAME
    builtins_test
  SRCS
    builtins_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    preconditions_test
  SRCS
    preconditions_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    node_test
  SRCS
    node_test.py
  DEPS
    pytype.pytdtest
)

