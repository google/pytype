add_package()

py_library(
  NAME
    tools
  DEPS
    .arg_parser
    .config
    .environment
    .runner
    .tool_utils
)

py_library(
  NAME
    arg_parser
  SRCS
    arg_parser.py
  DEPS
    pytype.config
    pytype.utils
)

py_library(
  NAME
    config
  SRCS
    config.py
  DEPS
    pytype.platform_utils.platform_utils
)

py_library(
  NAME
    environment
  SRCS
    environment.py
  DEPS
    .runner
    pytype.imports.imports
    pytype.platform_utils.platform_utils
)

py_library(
  NAME
    runner
  SRCS
    runner.py
)

py_library(
  NAME
    tool_utils
  SRCS
    tool_utils.py
  DEPS
    pytype.utils
)

py_test(
  NAME
    arg_parser_test
  SRCS
    arg_parser_test.py
  DEPS
    .tools
    pytype.config
    pytype.utils
)

py_test(
  NAME
    config_test
  SRCS
    config_test.py
  DEPS
    .tools
    pytype.tests.test_base
)

py_test(
  NAME
    environment_test
  SRCS
    environment_test.py
  DEPS
    .tools
    pytype.utils
    pytype.platform_utils.platform_utils
    pytype.tests.test_base
)

py_test(
  NAME
    tool_utils_test
  SRCS
    tool_utils_test.py
  DEPS
    .tools
    pytype.platform_utils.platform_utils
    pytype.tests.test_base
)

add_subdirectory(analyze_project)
add_subdirectory(annotate_ast)
add_subdirectory(debugger)
add_subdirectory(merge_pyi)
add_subdirectory(traces)
add_subdirectory(xref)
