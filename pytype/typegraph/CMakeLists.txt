add_package()

py_test(
  NAME
    cfg_test
  SRCS
    cfg_test.py
  DEPS
    pytype.cfg_py
)

py_test(
  NAME
    cfg_utils_test
  SRCS
    cfg_utils_test.py
  DEPS
    pytype.cfg_py
    pytype.cfg_utils
)
