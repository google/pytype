add_package()

py_test(
  NAME
    config_test
  SRCS
    config_test.py
  DEPS
    pytype.analyze_project
    pytype.utils
)

py_test(
  NAME
    parse_args_test
  SRCS
    parse_args_test.py
  DEPS
    pytype.analyze_project
)

py_test(
  NAME
    pytype_runner_test
  SRCS
    pytype_runner_test.py
  DEPS
    pytype.analyze_project
    pytype.libvm
)
