add_package()

py_library(
  NAME
    pyc
  DEPS
    ._pyc
    .compile_bytecode
    .loadmarshal
    .magic
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
    loadmarshal
  SRCS
    loadmarshal.py
  DEPS
    pytype.utils
)

py_library(
  NAME
    magic
  SRCS
    magic.py
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
    .compile_bytecode
    .loadmarshal
    .magic
    pytype.utils
)

py_test(
  NAME
    loadmarshal_test
  SRCS
    loadmarshal_test.py
  DEPS
    .loadmarshal
    pytype.utils
)

py_test(
  NAME
    opcodes_test
  SRCS
    opcodes_test.py
  DEPS
    .opcodes
    pytype.utils
)

py_test(
  NAME
    pyc_test
  SRCS
    pyc_test.py
  DEPS
    ._pyc
    .opcodes
    pytype.tests.test_base
)

py_test(
  NAME
    magic_test
  SRCS
    magic_test.py
  DEPS
    .magic
)

py_library(
  NAME
    generate_opcode_diffs
  SRCS
    generate_opcode_diffs.py
)

py_test(
  NAME
    generate_opcode_diffs_test
  SRCS
    generate_opcode_diffs_test.py
  DEPS
    .generate_opcode_diffs
)
