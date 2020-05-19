add_package()

py_test(
  NAME
    loadmarshal_test
  SRCS
    loadmarshal_test.py
  DEPS
    pytype.pyc
)

py_test(
  NAME
    opcodes_test
  SRCS
    opcodes_test.py
  DEPS
    pytype.pyc
)

py_test(
    NAME
      pyc_test
    SRCS
      pyc_test.py
    DEPS
      pytype.pyc
      pytype.tests.test_base
)

py_test(
  NAME
    magic_test
  SRCS
    magic_test.py
  DEPS
    pytype.pyc
)
