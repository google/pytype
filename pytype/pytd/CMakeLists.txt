add_package()

# CMake does not do dependency tracking if files are listed by a GLOB operation.
# So, we have to list the files individually as we want them to be tracked as
# build inputs.
filegroup(
  NAME
    builtins_pytd
  SRCS
    builtins/2/__builtin__.pytd
    builtins/2/array.pytd
    builtins/2/attr/__init__.pytd
    builtins/2/attr/_compat.pytd
    builtins/2/attr/_config.pytd
    builtins/2/attr/_funcs.pytd
    builtins/2/attr/_make.pytd
    builtins/2/attr/converters.pytd
    builtins/2/attr/exceptions.pytd
    builtins/2/attr/filters.pytd
    builtins/2/attr/setters.pytd
    builtins/2/attr/validators.pytd
    builtins/2/mypy_extensions.pytd
    builtins/2/numpy/__init__.pytd
    builtins/2/protocols.pytd
    builtins/2/typing.pytd

    builtins/2and3/array.pytd
    builtins/2and3/attr/__init__.pytd
    builtins/2and3/attr/_compat.pytd
    builtins/2and3/attr/_config.pytd
    builtins/2and3/attr/_funcs.pytd
    builtins/2and3/attr/_make.pytd
    builtins/2and3/attr/converters.pytd
    builtins/2and3/attr/exceptions.pytd
    builtins/2and3/attr/filters.pytd
    builtins/2and3/attr/setters.pytd
    builtins/2and3/attr/validators.pytd
    builtins/2and3/mypy_extensions.pytd
    builtins/2and3/numpy/__init__.pytd
    builtins/2and3/protocols.pytd
    builtins/2and3/typing.pytd

    builtins/3/__builtin__.pytd
    builtins/3/array.pytd
    builtins/3/attr/__init__.pytd
    builtins/3/attr/_compat.pytd
    builtins/3/attr/_config.pytd
    builtins/3/attr/_funcs.pytd
    builtins/3/attr/_make.pytd
    builtins/3/attr/converters.pytd
    builtins/3/attr/exceptions.pytd
    builtins/3/attr/filters.pytd
    builtins/3/attr/setters.pytd
    builtins/3/attr/validators.pytd
    builtins/3/builtins.pytd
    builtins/3/mypy_extensions.pytd
    builtins/3/numpy/__init__.pytd
    builtins/3/protocols.pytd
    builtins/3/typing.pytd

    stdlib/2/_ctypes.pytd
    stdlib/2/collections.pytd
    stdlib/2/dummy_thread.pytd
    stdlib/2/encodings.pytd

    stdlib/2and3/_ctypes.pytd
    stdlib/2and3/collections.pytd
    stdlib/2and3/dummy_thread.pytd
    stdlib/2and3/encodings.pytd

    stdlib/3/_ctypes.pytd
    stdlib/3/collections.pytd
    stdlib/3/dummy_thread.pytd
    stdlib/3/encodings.pytd
    stdlib/3/enum.pytd
)

toplevel_py_binary(
  NAME
    pytd
  SRCS
    main.py
  MAIN
    main.py
  DEPS
    .pytd_for_parser
    .pytd_utils
    pytype.utils
    pytype.pyi.parser
    pytype.pytd.parse.builtins
)

py_library(
  NAME
    pytd_for_parser
  SRCS
    abc_hierarchy.py
    booleq.py
    escape.py
    mro.py
    optimize.py
    pep484.py
    slots.py
    transforms.py
    type_match.py
    visitors.py
  DEPS
    .builtins_pytd  # TODO(b/159043305): Move this into a data dependency
    .pytd_defs
    .pytd_utils
    .pytd_visitors
    pytype.debug
    pytype.metrics
    pytype.utils
    pytype.pytd.parse.node
    pytype.pytd.parse.parser_constants
    pytype.typegraph.cfg
)

py_library(
  NAME
    pytd_defs
  SRCS
    pytd.py
  DEPS
    pytype.pytd.parse.node
    pytype.pytd.parse.preconditions
)

py_library(
  NAME
    pytd_utils
  SRCS
    pytd_utils.py
  DEPS
    .pytd_defs
    .pytd_visitors
    pytype.utils
)

py_library(
  NAME
    pytd_visitors
  SRCS
    pytd_visitors.py
  DEPS
    .pytd_defs
    pytype.cfg_utils
    pytype.pytd.parse.parser_constants
)

py_library(
  NAME
    serialize_ast
  SRCS
    serialize_ast.py
  DEPS
    .pytd_for_parser
    pytype.utils
    pytype.pyi.parser
)

py_library(
  NAME
    typeshed
  SRCS
    typeshed.py
  DEPS
    pytype.utils
    pytype.pyi.parser
    pytype.pytd.parse.builtins
)

py_test(
  NAME
    abc_hierarchy_test
  SRCS
    abc_hierarchy_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    booleq_test
  SRCS
    booleq_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    mro_test
  SRCS
    mro_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    optimize_test
  SRCS
    optimize_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    pep484_test
  SRCS
    pep484_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    slots_test
  SRCS
    slots_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    transforms_test
  SRCS
    transforms_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    type_match_test
  SRCS
    type_match_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    visitors_test
  SRCS
    visitors_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    pytd_test
  SRCS
    pytd_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    pytd_utils_test
  SRCS
    pytd_utils_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    pytd_visitors_test
  SRCS
    pytd_visitors_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
)

py_test(
  NAME
    serialize_ast_test
  SRCS
    serialize_ast_test.py
  DEPS
    pytype.libvm
    pytype.pytd.parse.parser_test_base
    pytype.tests.test_base
)

py_test(
  NAME
    typeshed_test
  SRCS
    typeshed_test.py
  DEPS
    pytype.pytd.parse.parser_test_base
    pytype.tests.test_base
)

add_subdirectory(parse)
