add_package()

py_test(
  NAME
    collections_overlay_test
  SRCS
    collections_overlay_test.py
  DEPS
    pytype.libvm
    pytype.tests.test_base
)
