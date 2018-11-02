add_package()

py_test(
  NAME
    config_test
  SRCS
    config_test.py
  DEPS
    pytype.tools
    pytype.utils
)

py_test(
  NAME
    environment_test
  SRCS
    environment_test.py
  DEPS
    pytype.pytd
    pytype.tools
    pytype.utils
)

py_test(
  NAME
    tool_utils_test
  SRCS
    tool_utils_test.py
  DEPS
    pytype.tools
    pytype.utils
)

add_subdirectory(analyze_project)
add_subdirectory(merge_pyi)
add_subdirectory(pyi_checker)
