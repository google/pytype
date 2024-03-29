add_package()

py_library(
  NAME
    indexer
  DEPS
    ._indexer
    .debug
    .utils
    .kythe
    .output
    .parse_args
)

toplevel_py_binary(
  NAME
    xref
  SRCS
    main.py
  MAIN
    main.py
  DEPS
    ._indexer
    .debug
    .kythe
    .output
    .parse_args
    pytype.utils
)

py_library(
  NAME
    callgraph
  SRCS
    callgraph.py
  DEPS
    pytype.pytd.pytd
)

py_library(
  NAME
    debug
  SRCS
    debug.py
  DEPS
    pytype.ast.ast
)

py_library(
  NAME
    utils
  SRCS
    utils.py
  DEPS
    pytype.utils
)

py_library(
  NAME
    _indexer
  SRCS
    __init__.py
    indexer.py
  DEPS
    .callgraph
    .utils
    .node_utils
    pytype.libvm
    pytype.utils
    pytype.abstract.abstract
    pytype.ast.ast
    pytype.pytd.pytd
    pytype.tools.traces.traces
)

py_library(
  NAME
    kythe
  SRCS
    kythe.py
  DEPS
    ._indexer
    .utils
)

py_library(
  NAME
    node_utils
  SRCS
    node_utils.py
)

py_library(
  NAME
    output
  SRCS
    output.py
)

py_library(
  NAME
    parse_args
  SRCS
    parse_args.py
  DEPS
    .kythe
    pytype.config
    pytype.utils
    pytype.tools.tools
)

py_test(
  NAME
    callgraph_test
  SRCS
    callgraph_test.py
  DEPS
    ._indexer
    pytype.config
    pytype.tests.test_base
)

py_test(
  NAME
    indexer_test
  SRCS
    indexer_test.py
  DEPS
    ._indexer
    .kythe
    .output
    pytype.config
    pytype.utils
    pytype.abstract.abstract
    pytype.tests.test_base
)

py_test(
  NAME
    parse_args_test
  SRCS
    parse_args_test.py
  DEPS
    .parse_args
    pytype.tests.test_base
)

add_subdirectory(testdata)
