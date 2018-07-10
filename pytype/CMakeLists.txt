add_package()

# CMake does not do dependency tracking if files are listed by a GLOB operation.
# So, we have to list the files individually as we want them to be tracked as
# build inputs.
filegroup(
  NAME
    builtins_pytd
  SRCS
    pytd/builtins/2/__builtin__.pytd
    pytd/builtins/2/array.pytd
    pytd/builtins/2/mypy_extensions.pytd
    pytd/builtins/2/protocols.pytd
    pytd/builtins/2/typing.pytd

    pytd/builtins/2and3/array.pytd
    pytd/builtins/2and3/mypy_extensions.pytd
    pytd/builtins/2and3/protocols.pytd
    pytd/builtins/2and3/typing.pytd

    pytd/builtins/3/__builtin__.pytd
    pytd/builtins/3/array.pytd
    pytd/builtins/3/builtins.pytd
    pytd/builtins/3/mypy_extensions.pytd
    pytd/builtins/3/protocols.pytd
    pytd/builtins/3/typing.pytd

    pytd/stdlib/2/_ctypes.pytd
    pytd/stdlib/2/collections.pytd
    pytd/stdlib/2/ctypes.pytd
    pytd/stdlib/2/dummy_thread.pytd
    pytd/stdlib/2/encodings.pytd
    pytd/stdlib/2/xmlrpclib.pytd

    pytd/stdlib/2and3/_ctypes.pytd
    pytd/stdlib/2and3/collections.pytd
    pytd/stdlib/2and3/ctypes.pytd
    pytd/stdlib/2and3/dummy_thread.pytd
    pytd/stdlib/2and3/encodings.pytd
    pytd/stdlib/2and3/xmlrpclib.pytd

    pytd/stdlib/3/_ctypes.pytd
    pytd/stdlib/3/collections.pytd
    pytd/stdlib/3/ctypes.pytd
    pytd/stdlib/3/dummy_thread.pytd
    pytd/stdlib/3/encodings.pytd
    pytd/stdlib/3/re.pytd
    pytd/stdlib/3/signal.pytd
    pytd/stdlib/3/xmlrpclib.pytd

    pytd/stdlib/3/asyncio/tasks.pytd

    pytd/stdlib/3/importlib/__init__.pytd

    pytd/stdlib/3/multiprocessing/pool.pytd
)

py_library(
  NAME
    metrics
  SRCS
    metrics.py
)

py_library(
  NAME
    utils
  SRCS
    compat.py
    datatypes.py
    file_utils.py
    module_utils.py
    pytype_source_utils.py
    utils.py
)

py_library(
  NAME
    debug
  SRCS
    debug.py
  DEPS
    .utils
)

py_library(
  NAME
    libvm
  SRCS
    __version__.py
    abc_overlay.py
    abstract.py
    analyze.py
    annotations_util.py
    attribute.py
    blocks.py
    collections_overlay.py
    compare.py
    config.py
    convert.py
    convert_structural.py
    directors.py
    errors.py
    function.py
    imports_map_loader.py
    io.py
    matcher.py
    output.py
    overlay.py
    overlay_dict.py
    six_overlay.py
    special_builtins.py
    state.py
    sys_overlay.py
    typing.py
    vm.py
  DEPS
    .debug
    .metrics
    .pyc
    .pytd
    .utils
)

py_library(
  NAME
    cfg_py
  SRCS
    typegraph/cfg.py
  DEPS
    .debug
    .metrics
)

py_library(
  NAME
    cfg_utils
  SRCS
    typegraph/cfg_utils.py
  DEPS
    pytype.typegraph.cfg
)

py_library(
  NAME
    preconditions
  SRCS
    pytd/parse/preconditions.py
  DEPS
    .utils
)

py_library(
  NAME
    pyc
  SRCS
    pyc/compile_bytecode.py
    pyc/loadmarshal.py
    pyc/magic.py
    pyc/opcodes.py
    pyc/pyc.py
  DEPS
    .utils
)

py_library(
  NAME
    node_c
  SRCS
    pytd/parse/node.py
)

py_library(
  NAME
    node
  DEPS
    .metrics
    .node_c
    .preconditions
)

py_library(
  NAME
    pytd_for_parser
  SRCS
    pytd/abc_hierarchy.py
    pytd/booleq.py
    pytd/mro.py
    pytd/optimize.py
    pytd/parse/parser_constants.py
    pytd/pep484.py
    pytd/pytd.py
    pytd/pytd_utils.py
    pytd/slots.py
    pytd/transforms.py
    pytd/type_match.py
    pytd/visitors.py
  DEPS
    .builtins_pytd  # TODO(sivachandra): Move this into a data dependency
    .cfg_utils
    .debug
    .metrics
    .node
    .utils
    pytype.typegraph.cfg
)

py_library(
  NAME
    parser
  SRCS
    pyi/parser.py
  DEPS
    .pytd_for_parser
    .utils
    pytype.pyi.parser_ext
)

py_library(
  NAME
    pytd
  SRCS
    load_pytd.py
    pytd/parse/builtins.py
    pytd/serialize_ast.py
    pytd/typeshed.py
  DEPS
    .parser
    .pytd_for_parser
    .utils
)

py_library(
  NAME
    pytdtest
  SRCS
    pytd/parse/parser_test_base.py
  DEPS
    .pytd
)

py_library(
    NAME
      tools
    SRCS
      tools/config.py
      tools/environment.py
      tools/runner.py
      tools/tool_utils.py
    DEPS
      .utils
)

py_library(
    NAME
      analyze_project
    SRCS
      tools/analyze_project/config.py
      tools/analyze_project/parse_args.py
      tools/analyze_project/pytype_runner.py
    DEPS
      .libvm
      .tools
      .utils
)

py_test(
  NAME
    config_test
  SRCS
    config_test.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    datatypes_test
  SRCS
    datatypes_test.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    file_utils_test
  SRCS
    file_utils_test.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    module_utils_test
  SRCS
    module_utils_test.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    utils_test
  SRCS
    utils_test.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    abstract_test
  SRCS
    abstract_test.py
  DEPS
    .libvm
)

py_test(
  NAME
    matcher_test
  SRCS
    matcher_test.py
  DEPS
    .libvm
)

py_test(
  NAME
    convert_test
  SRCS
    convert_test.py
  DEPS
    .libvm
)

py_test(
  NAME
    attribute_test
  SRCS
    attribute_test.py
  DEPS
    .libvm
)

py_test(
  NAME
    convert_structural_test
  SRCS
    convert_structural_test.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    blocks_test
  SRCS
    blocks_test.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    vm_test
  SRCS
    vm_test.py
  DEPS
    pytype.tests.test_base
)

py_test(
  NAME
    directors_test
  SRCS
    directors_test.py
  DEPS
    .libvm
)

py_test(
  NAME
    load_pytd_test
  SRCS
    load_pytd_test.py
  DEPS
    .builtins_pytd
    .libvm
)

py_test(
  NAME
    imports_map_loader_test
  SRCS
    imports_map_loader_test.py
  DEPS
    .builtins_pytd
    .libvm
)

py_test(
  NAME
    metrics_test
  SRCS
    metrics_test.py
  DEPS
    .metrics
)

py_test(
  NAME
    state_test
  SRCS
    state_test.py
  DEPS
    .libvm
)

py_test(
  NAME
    collections_overlay_test
  SRCS
    collections_overlay_test.py
  DEPS
    .libvm
)

py_test(
  NAME
    debug_test
  SRCS
    debug_test.py
  DEPS
    .debug
    .pytd
)

add_subdirectory(pyc)
add_subdirectory(pyi)
add_subdirectory(pytd)
add_subdirectory(tests)
add_subdirectory(tools)
add_subdirectory(typegraph)
