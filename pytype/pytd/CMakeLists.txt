add_package()

py_test(
  NAME
    serialize_ast_test
  SRCS
    serialize_ast_test.py
  DEPS
    pytype.libvm
    pytype.pytdtest
    pytype.tests.test_base
)

py_test(
  NAME
    booleq_test
  SRCS
    booleq_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    pep484_test
  SRCS
    pep484_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    type_match_test
  SRCS
    type_match_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    typeshed_test
  SRCS
    typeshed_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    transforms_test
  SRCS
    transforms_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    optimize_test
  SRCS
    optimize_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    pytd_test
  SRCS
    pytd_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    visitors_test
  SRCS
    visitors_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    slots_test
  SRCS
    slots_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    pytd_utils_test
  SRCS
    pytd_utils_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    mro_test
  SRCS
    mro_test.py
  DEPS
    pytype.pytdtest
)

py_test(
  NAME
    abc_hierarchy_test
  SRCS
    abc_hierarchy_test.py
  DEPS
    pytype.pytdtest
)

add_subdirectory(parse)
