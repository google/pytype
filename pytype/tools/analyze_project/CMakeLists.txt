add_package()

py_library(
    NAME
      analyze_project
    SRCS
      config.py
      environment.py
      parse_args.py
      pytype_runner.py
    DEPS
      pytype.config
      pytype.io
      pytype.utils
      pytype.tools.tools
)

py_test(
  NAME
    config_test
  SRCS
    config_test.py
  DEPS
    .analyze_project
    pytype.utils
)

py_test(
  NAME
    parse_args_test
  SRCS
    parse_args_test.py
  DEPS
    .analyze_project
)

py_test(
  NAME
    pytype_runner_test
  SRCS
    pytype_runner_test.py
  DEPS
    .analyze_project
    pytype.config
    pytype.utils
)

toplevel_py_binary(
  NAME
    pytype
  SRCS
    main.py
  MAIN
    main.py
  DEPS
    .analyze_project
)
