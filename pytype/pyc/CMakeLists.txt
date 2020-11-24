add_package()

py_library(
  NAME
    pyc
  SRCS
    compile_bytecode.py
    loadmarshal.py
    magic.py
    opcodes.py
    pyc.py
  DEPS
    pytype.utils
)

py_test(
  NAME
    loadmarshal_test
  SRCS
    loadmarshal_test.py
  DEPS
    .pyc
)

py_test(
  NAME
    opcodes_test
  SRCS
    opcodes_test.py
  DEPS
    .pyc
)

py_test(
    NAME
      pyc_test
    SRCS
      pyc_test.py
    DEPS
      .pyc
      pytype.tests.test_base
)

py_test(
  NAME
    magic_test
  SRCS
    magic_test.py
  DEPS
    .pyc
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
