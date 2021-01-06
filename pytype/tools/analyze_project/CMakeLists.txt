add_package()

py_library(
  NAME
    analyze_project
  DEPS
    .config
    .environment
    .parse_args
    .pytype_runner
)

py_library(
  NAME
    config
  SRCS
    config.py
  DEPS
    pytype.utils
    pytype.tools.tools
)

py_library(
  NAME
    environment
  SRCS
    environment.py
  DEPS
    pytype.utils
)

py_library(
  NAME
    parse_args
  SRCS
    parse_args.py
  DEPS
    .config
    pytype.libvm
    pytype.utils
    pytype.tools.tools
)

py_library(
  NAME
    pytype_runner
  SRCS
    pytype_runner.py
  DEPS
    .config
    pytype.utils
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
    pytype.utils
)

py_test(
  NAME
    pytype_runner_test
  SRCS
    pytype_runner_test.py
  DEPS
    .analyze_project
    pytype.libvm
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
    pytype.libvm
    pytype.tools.tools
)
