add_package()

py_library(
  NAME
    pyc
  DEPS
    ._pyc
    .compile_bytecode
    .compiler
    .opcodes
)

py_library(
  NAME
    compile_bytecode
  SRCS
    compile_bytecode.py
)

py_library(
  NAME
    compiler
  SRCS
    compiler.py
  DEPS
    .compile_bytecode
    pytype.utils
    pytype.platform_utils.platform_utils
)

py_library(
  NAME
    opcodes
  SRCS
    opcodes.py
)

py_library(
  NAME
    _pyc
  SRCS
    pyc.py
  DEPS
    .compiler
    pytype.utils
)

py_test(
  NAME
    compiler_test
  SRCS
    compiler_test.py
  DEPS
    .compiler
)

py_test(
  NAME
    opcodes_test
  SRCS
    opcodes_test.py
  DEPS
    .opcodes
)

py_test(
  NAME
    pyc_test
  SRCS
    pyc_test.py
  DEPS
    ._pyc
    .compiler
    .opcodes
    pytype.tests.test_base
)

py_library(
  NAME
    generate_opcode_diffs
  SRCS
    generate_opcode_diffs.py
  DEPS
    pytype.platform_utils.platform_utils
)

py_test(
  NAME
    generate_opcode_diffs_test
  SRCS
    generate_opcode_diffs_test.py
  DEPS
    .generate_opcode_diffs
)
