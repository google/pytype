add_package()

py_library(
    NAME
      tools
    SRCS
      arg_parser.py
      config.py
      environment.py
      runner.py
      tool_utils.py
    DEPS
      pytype.config
      pytype.utils
      pytype.pytd.typeshed
)

py_test(
  NAME
    arg_parser_test
  SRCS
    arg_parser_test.py
  DEPS
    .tools
    pytype.config
)

py_test(
  NAME
    config_test
  SRCS
    config_test.py
  DEPS
    .tools
    pytype.utils
)

py_test(
  NAME
    environment_test
  SRCS
    environment_test.py
  DEPS
    .tools
    pytype.utils
)

py_test(
  NAME
    tool_utils_test
  SRCS
    tool_utils_test.py
  DEPS
    .tools
    pytype.utils
)

add_subdirectory(analyze_project)
add_subdirectory(annotate_ast)
add_subdirectory(merge_pyi)
add_subdirectory(traces)
add_subdirectory(xref)
