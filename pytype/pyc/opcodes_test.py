from pytype.pyc import opcodes
import unittest


class Python2Test(unittest.TestCase):
  """Test bytecodes.dis for Python 2 opcodes."""

  PYTHON_VERSION = (2, 7, 6)

  def dis(self, data):
    return opcodes.dis(data, self.PYTHON_VERSION)

  def test_stop_code(self):
    self.assertEquals(self.dis('\x00')[0].name, 'STOP_CODE')

  def test_pop_top(self):
    self.assertEquals(self.dis('\x01')[0].name, 'POP_TOP')

  def test_rot_two(self):
    self.assertEquals(self.dis('\x02')[0].name, 'ROT_TWO')

  def test_rot_three(self):
    self.assertEquals(self.dis('\x03')[0].name, 'ROT_THREE')

  def test_dup_top(self):
    self.assertEquals(self.dis('\x04')[0].name, 'DUP_TOP')

  def test_rot_four(self):
    self.assertEquals(self.dis('\x05')[0].name, 'ROT_FOUR')

  def test_nop(self):
    self.assertEquals(self.dis('\t')[0].name, 'NOP')

  def test_unary_positive(self):
    self.assertEquals(self.dis('\n')[0].name, 'UNARY_POSITIVE')

  def test_unary_negative(self):
    self.assertEquals(self.dis('\x0b')[0].name, 'UNARY_NEGATIVE')

  def test_unary_not(self):
    self.assertEquals(self.dis('\x0c')[0].name, 'UNARY_NOT')

  def test_unary_convert(self):
    self.assertEquals(self.dis('\r')[0].name, 'UNARY_CONVERT')

  def test_unary_invert(self):
    self.assertEquals(self.dis('\x0f')[0].name, 'UNARY_INVERT')

  def test_binary_power(self):
    self.assertEquals(self.dis('\x13')[0].name, 'BINARY_POWER')

  def test_binary_multiply(self):
    self.assertEquals(self.dis('\x14')[0].name, 'BINARY_MULTIPLY')

  def test_binary_divide(self):
    self.assertEquals(self.dis('\x15')[0].name, 'BINARY_DIVIDE')

  def test_binary_modulo(self):
    self.assertEquals(self.dis('\x16')[0].name, 'BINARY_MODULO')

  def test_binary_add(self):
    self.assertEquals(self.dis('\x17')[0].name, 'BINARY_ADD')

  def test_binary_subtract(self):
    self.assertEquals(self.dis('\x18')[0].name, 'BINARY_SUBTRACT')

  def test_binary_subscr(self):
    self.assertEquals(self.dis('\x19')[0].name, 'BINARY_SUBSCR')

  def test_binary_floor_divide(self):
    self.assertEquals(self.dis('\x1a')[0].name, 'BINARY_FLOOR_DIVIDE')

  def test_binary_true_divide(self):
    self.assertEquals(self.dis('\x1b')[0].name, 'BINARY_TRUE_DIVIDE')

  def test_inplace_floor_divide(self):
    self.assertEquals(self.dis('\x1c')[0].name, 'INPLACE_FLOOR_DIVIDE')

  def test_inplace_true_divide(self):
    self.assertEquals(self.dis('\x1d')[0].name, 'INPLACE_TRUE_DIVIDE')

  def test_slice_0(self):
    self.assertEquals(self.dis('\x1e')[0].name, 'SLICE_0')

  def test_slice_1(self):
    self.assertEquals(self.dis('\x1f')[0].name, 'SLICE_1')

  def test_slice_2(self):
    self.assertEquals(self.dis(' ')[0].name, 'SLICE_2')

  def test_slice_3(self):
    self.assertEquals(self.dis('!')[0].name, 'SLICE_3')

  def test_store_slice_0(self):
    self.assertEquals(self.dis('(')[0].name, 'STORE_SLICE_0')

  def test_store_slice_1(self):
    self.assertEquals(self.dis(')')[0].name, 'STORE_SLICE_1')

  def test_store_slice_2(self):
    self.assertEquals(self.dis('*')[0].name, 'STORE_SLICE_2')

  def test_store_slice_3(self):
    self.assertEquals(self.dis('+')[0].name, 'STORE_SLICE_3')

  def test_delete_slice_0(self):
    self.assertEquals(self.dis('2')[0].name, 'DELETE_SLICE_0')

  def test_delete_slice_1(self):
    self.assertEquals(self.dis('3')[0].name, 'DELETE_SLICE_1')

  def test_delete_slice_2(self):
    self.assertEquals(self.dis('4')[0].name, 'DELETE_SLICE_2')

  def test_delete_slice_3(self):
    self.assertEquals(self.dis('5')[0].name, 'DELETE_SLICE_3')

  def test_store_map(self):
    self.assertEquals(self.dis('6')[0].name, 'STORE_MAP')

  def test_inplace_add(self):
    self.assertEquals(self.dis('7')[0].name, 'INPLACE_ADD')

  def test_inplace_subtract(self):
    self.assertEquals(self.dis('8')[0].name, 'INPLACE_SUBTRACT')

  def test_inplace_multiply(self):
    self.assertEquals(self.dis('9')[0].name, 'INPLACE_MULTIPLY')

  def test_inplace_divide(self):
    self.assertEquals(self.dis(':')[0].name, 'INPLACE_DIVIDE')

  def test_inplace_modulo(self):
    self.assertEquals(self.dis(';')[0].name, 'INPLACE_MODULO')

  def test_store_subscr(self):
    self.assertEquals(self.dis('<')[0].name, 'STORE_SUBSCR')

  def test_delete_subscr(self):
    self.assertEquals(self.dis('=')[0].name, 'DELETE_SUBSCR')

  def test_binary_lshift(self):
    self.assertEquals(self.dis('>')[0].name, 'BINARY_LSHIFT')

  def test_binary_rshift(self):
    self.assertEquals(self.dis('?')[0].name, 'BINARY_RSHIFT')

  def test_binary_and(self):
    self.assertEquals(self.dis('@')[0].name, 'BINARY_AND')

  def test_binary_xor(self):
    self.assertEquals(self.dis('A')[0].name, 'BINARY_XOR')

  def test_binary_or(self):
    self.assertEquals(self.dis('B')[0].name, 'BINARY_OR')

  def test_inplace_power(self):
    self.assertEquals(self.dis('C')[0].name, 'INPLACE_POWER')

  def test_get_iter(self):
    self.assertEquals(self.dis('D')[0].name, 'GET_ITER')

  def test_print_expr(self):
    self.assertEquals(self.dis('F')[0].name, 'PRINT_EXPR')

  def test_print_item(self):
    self.assertEquals(self.dis('G')[0].name, 'PRINT_ITEM')

  def test_print_newline(self):
    self.assertEquals(self.dis('H')[0].name, 'PRINT_NEWLINE')

  def test_print_item_to(self):
    self.assertEquals(self.dis('I')[0].name, 'PRINT_ITEM_TO')

  def test_print_newline_to(self):
    self.assertEquals(self.dis('J')[0].name, 'PRINT_NEWLINE_TO')

  def test_inplace_lshift(self):
    self.assertEquals(self.dis('K')[0].name, 'INPLACE_LSHIFT')

  def test_inplace_rshift(self):
    self.assertEquals(self.dis('L')[0].name, 'INPLACE_RSHIFT')

  def test_inplace_and(self):
    self.assertEquals(self.dis('M')[0].name, 'INPLACE_AND')

  def test_inplace_xor(self):
    self.assertEquals(self.dis('N')[0].name, 'INPLACE_XOR')

  def test_inplace_or(self):
    self.assertEquals(self.dis('O')[0].name, 'INPLACE_OR')

  def test_break_loop(self):
    self.assertEquals(self.dis('P')[0].name, 'BREAK_LOOP')

  def test_with_cleanup(self):
    self.assertEquals(self.dis('Q')[0].name, 'WITH_CLEANUP')

  def test_load_locals(self):
    self.assertEquals(self.dis('R')[0].name, 'LOAD_LOCALS')

  def test_return_value(self):
    self.assertEquals(self.dis('S')[0].name, 'RETURN_VALUE')

  def test_import_star(self):
    self.assertEquals(self.dis('T')[0].name, 'IMPORT_STAR')

  def test_exec_stmt(self):
    self.assertEquals(self.dis('U')[0].name, 'EXEC_STMT')

  def test_yield_value(self):
    self.assertEquals(self.dis('V')[0].name, 'YIELD_VALUE')

  def test_pop_block(self):
    self.assertEquals(self.dis('W')[0].name, 'POP_BLOCK')

  def test_end_finally(self):
    self.assertEquals(self.dis('X')[0].name, 'END_FINALLY')

  def test_build_class(self):
    self.assertEquals(self.dis('Y')[0].name, 'BUILD_CLASS')

  def test_store_name(self):
    self.assertEquals(self.dis('Z\x00\x00')[0].name, 'STORE_NAME')

  def test_delete_name(self):
    self.assertEquals(self.dis('[\x00\x00')[0].name, 'DELETE_NAME')

  def test_unpack_sequence(self):
    self.assertEquals(self.dis('\\\x00\x00')[0].name, 'UNPACK_SEQUENCE')

  def test_for_iter(self):
    self.assertEquals(self.dis(']\x00\x00\t')[0].name, 'FOR_ITER')

  def test_list_append(self):
    self.assertEquals(self.dis('^\x00\x00')[0].name, 'LIST_APPEND')

  def test_store_attr(self):
    self.assertEquals(self.dis('_\x00\x00')[0].name, 'STORE_ATTR')

  def test_delete_attr(self):
    self.assertEquals(self.dis('`\x00\x00')[0].name, 'DELETE_ATTR')

  def test_store_global(self):
    self.assertEquals(self.dis('a\x00\x00')[0].name, 'STORE_GLOBAL')

  def test_delete_global(self):
    self.assertEquals(self.dis('b\x00\x00')[0].name, 'DELETE_GLOBAL')

  def test_dup_topx(self):
    self.assertEquals(self.dis('c\x00\x00')[0].name, 'DUP_TOPX')

  def test_load_const(self):
    self.assertEquals(self.dis('d\x00\x00')[0].name, 'LOAD_CONST')

  def test_load_name(self):
    self.assertEquals(self.dis('e\x00\x00')[0].name, 'LOAD_NAME')

  def test_build_tuple(self):
    self.assertEquals(self.dis('f\x00\x00')[0].name, 'BUILD_TUPLE')

  def test_build_list(self):
    self.assertEquals(self.dis('g\x00\x00')[0].name, 'BUILD_LIST')

  def test_build_set(self):
    self.assertEquals(self.dis('h\x00\x00')[0].name, 'BUILD_SET')

  def test_build_map(self):
    self.assertEquals(self.dis('i\x00\x00')[0].name, 'BUILD_MAP')

  def test_load_attr(self):
    self.assertEquals(self.dis('j\x00\x00')[0].name, 'LOAD_ATTR')

  def test_compare_op(self):
    self.assertEquals(self.dis('k\x00\x00')[0].name, 'COMPARE_OP')

  def test_import_name(self):
    self.assertEquals(self.dis('l\x00\x00')[0].name, 'IMPORT_NAME')

  def test_import_from(self):
    self.assertEquals(self.dis('m\x00\x00')[0].name, 'IMPORT_FROM')

  def test_jump_forward(self):
    self.assertEquals(self.dis('n\x00\x00\t')[0].name, 'JUMP_FORWARD')

  def test_jump_if_false_or_pop(self):
    self.assertEquals(self.dis('o\x03\x00\t')[0].name, 'JUMP_IF_FALSE_OR_POP')

  def test_jump_if_true_or_pop(self):
    self.assertEquals(self.dis('p\x03\x00\t')[0].name, 'JUMP_IF_TRUE_OR_POP')

  def test_jump_absolute(self):
    self.assertEquals(self.dis('q\x03\x00\t')[0].name, 'JUMP_ABSOLUTE')

  def test_pop_jump_if_false(self):
    self.assertEquals(self.dis('r\x03\x00\t')[0].name, 'POP_JUMP_IF_FALSE')

  def test_pop_jump_if_true(self):
    self.assertEquals(self.dis('s\x03\x00\t')[0].name, 'POP_JUMP_IF_TRUE')

  def test_load_global(self):
    self.assertEquals(self.dis('t\x00\x00')[0].name, 'LOAD_GLOBAL')

  def test_continue_loop(self):
    self.assertEquals(self.dis('w\x03\x00\t')[0].name, 'CONTINUE_LOOP')

  def test_setup_loop(self):
    self.assertEquals(self.dis('x\x00\x00\t')[0].name, 'SETUP_LOOP')

  def test_setup_except(self):
    self.assertEquals(self.dis('y\x00\x00\t')[0].name, 'SETUP_EXCEPT')

  def test_setup_finally(self):
    self.assertEquals(self.dis('z\x00\x00\t')[0].name, 'SETUP_FINALLY')

  def test_load_fast(self):
    self.assertEquals(self.dis('|\x00\x00')[0].name, 'LOAD_FAST')

  def test_store_fast(self):
    self.assertEquals(self.dis('}\x00\x00')[0].name, 'STORE_FAST')

  def test_delete_fast(self):
    self.assertEquals(self.dis('~\x00\x00')[0].name, 'DELETE_FAST')

  def test_raise_varargs(self):
    self.assertEquals(self.dis('\x82\x00\x00')[0].name, 'RAISE_VARARGS')

  def test_call_function(self):
    self.assertEquals(self.dis('\x83\x00\x00')[0].name, 'CALL_FUNCTION')

  def test_make_function(self):
    self.assertEquals(self.dis('\x84\x00\x00')[0].name, 'MAKE_FUNCTION')

  def test_build_slice(self):
    self.assertEquals(self.dis('\x85\x00\x00')[0].name, 'BUILD_SLICE')

  def test_make_closure(self):
    self.assertEquals(self.dis('\x86\x00\x00')[0].name, 'MAKE_CLOSURE')

  def test_load_closure(self):
    self.assertEquals(self.dis('\x87\x00\x00')[0].name, 'LOAD_CLOSURE')

  def test_load_deref(self):
    self.assertEquals(self.dis('\x88\x00\x00')[0].name, 'LOAD_DEREF')

  def test_store_deref(self):
    self.assertEquals(self.dis('\x89\x00\x00')[0].name, 'STORE_DEREF')

  def test_call_function_var(self):
    self.assertEquals(self.dis('\x8c\x00\x00')[0].name, 'CALL_FUNCTION_VAR')

  def test_call_function_kw(self):
    self.assertEquals(self.dis('\x8d\x00\x00')[0].name, 'CALL_FUNCTION_KW')

  def test_call_function_var_kw(self):
    self.assertEquals(self.dis('\x8e\x00\x00')[0].name, 'CALL_FUNCTION_VAR_KW')

  def test_setup_with(self):
    self.assertEquals(self.dis('\x8f\x00\x00\t')[0].name, 'SETUP_WITH')

  def test_set_add(self):
    self.assertEquals(self.dis('\x92\x00\x00')[0].name, 'SET_ADD')

  def test_map_add(self):
    self.assertEquals(self.dis('\x93\x00\x00')[0].name, 'MAP_ADD')

  def test_binary(self):
    code = ''.join(chr(c) for c in ([
        0x7c, 0, 0,  # 0 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 3 LOAD_FAST, arg=0,
        0x17,  # 6 BINARY_ADD,
        0x01,  # 7 POP_TOP,
        0x7c, 0, 0,  # 8 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 11 LOAD_FAST, arg=0,
        0x14,  # 14 BINARY_MULTIPLY,
        0x01,  # 15 POP_TOP,
        0x7c, 0, 0,  # 16 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 19 LOAD_FAST, arg=0,
        0x16,  # 22 BINARY_MODULO,
        0x01,  # 23 POP_TOP,
        0x7c, 0, 0,  # 24 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 27 LOAD_FAST, arg=0,
        0x15,  # 30 BINARY_DIVIDE,
        0x01,  # 31 POP_TOP,
        0x64, 0, 0,  # 32 LOAD_CONST, arg=0,
        0x53,  # 35 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 18)
    self.assertEquals(ops[0].name, 'LOAD_FAST')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'LOAD_FAST')
    self.assertEquals(ops[1].arg, 0)
    self.assertEquals(ops[2].name, 'BINARY_ADD')
    self.assertEquals(ops[3].name, 'POP_TOP')
    self.assertEquals(ops[4].name, 'LOAD_FAST')
    self.assertEquals(ops[4].arg, 0)
    self.assertEquals(ops[5].name, 'LOAD_FAST')
    self.assertEquals(ops[5].arg, 0)
    self.assertEquals(ops[6].name, 'BINARY_MULTIPLY')
    self.assertEquals(ops[7].name, 'POP_TOP')
    self.assertEquals(ops[8].name, 'LOAD_FAST')
    self.assertEquals(ops[8].arg, 0)
    self.assertEquals(ops[9].name, 'LOAD_FAST')
    self.assertEquals(ops[9].arg, 0)
    self.assertEquals(ops[10].name, 'BINARY_MODULO')
    self.assertEquals(ops[11].name, 'POP_TOP')
    self.assertEquals(ops[12].name, 'LOAD_FAST')
    self.assertEquals(ops[12].arg, 0)
    self.assertEquals(ops[13].name, 'LOAD_FAST')
    self.assertEquals(ops[13].arg, 0)
    self.assertEquals(ops[14].name, 'BINARY_DIVIDE')
    self.assertEquals(ops[15].name, 'POP_TOP')
    self.assertEquals(ops[16].name, 'LOAD_CONST')
    self.assertEquals(ops[16].arg, 0)
    self.assertEquals(ops[17].name, 'RETURN_VALUE')

  def test_break(self):
    code = ''.join(chr(c) for c in ([
        0x78, 4, 0,  # 0 SETUP_LOOP, dest=7,
        0x50,  # 3 BREAK_LOOP,
        0x71, 3, 0,  # 4 JUMP_ABSOLUTE, dest=3,
        0x64, 0, 0,  # 7 LOAD_CONST, arg=0,
        0x53,  # 10 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 5)
    self.assertEquals(ops[0].name, 'SETUP_LOOP')
    self.assertEquals(ops[0].arg, 3)
    self.assertEquals(ops[0].target, ops[3])
    self.assertEquals(ops[1].name, 'BREAK_LOOP')
    self.assertEquals(ops[2].name, 'JUMP_ABSOLUTE')
    self.assertEquals(ops[2].arg, 1)
    self.assertEquals(ops[2].target, ops[1])
    self.assertEquals(ops[3].name, 'LOAD_CONST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'RETURN_VALUE')

  def test_call(self):
    code = ''.join(chr(c) for c in ([
        0x74, 0, 0,  # 0 LOAD_GLOBAL, arg=0,
        0x83, 0, 0,  # 3 CALL_FUNCTION, arg=0,
        0x01,  # 6 POP_TOP,
        0x64, 0, 0,  # 7 LOAD_CONST, arg=0,
        0x53,  # 10 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 5)
    self.assertEquals(ops[0].name, 'LOAD_GLOBAL')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'CALL_FUNCTION')
    self.assertEquals(ops[1].arg, 0)
    self.assertEquals(ops[2].name, 'POP_TOP')
    self.assertEquals(ops[3].name, 'LOAD_CONST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'RETURN_VALUE')

  def test_continue(self):
    code = ''.join(chr(c) for c in ([
        0x78, 6, 0,  # 0 SETUP_LOOP, dest=9,
        0x71, 3, 0,  # 3 JUMP_ABSOLUTE, dest=3,
        0x71, 3, 0,  # 6 JUMP_ABSOLUTE, dest=3,
        0x64, 0, 0,  # 9 LOAD_CONST, arg=0,
        0x53,  # 12 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 5)
    self.assertEquals(ops[0].name, 'SETUP_LOOP')
    self.assertEquals(ops[0].arg, 3)
    self.assertEquals(ops[0].target, ops[3])
    self.assertEquals(ops[1].name, 'JUMP_ABSOLUTE')
    self.assertEquals(ops[1].arg, 1)
    self.assertEquals(ops[1].target, ops[1])
    self.assertEquals(ops[2].name, 'JUMP_ABSOLUTE')
    self.assertEquals(ops[2].arg, 1)
    self.assertEquals(ops[2].target, ops[1])
    self.assertEquals(ops[3].name, 'LOAD_CONST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'RETURN_VALUE')

  def test_except(self):
    code = ''.join(chr(c) for c in ([
        0x79, 4, 0,  # 0 SETUP_EXCEPT, dest=7,
        0x57,  # 3 POP_BLOCK,
        0x6e, 7, 0,  # 4 JUMP_FORWARD, dest=14,
        0x01,  # 7 POP_TOP,
        0x01,  # 8 POP_TOP,
        0x01,  # 9 POP_TOP,
        0x6e, 1, 0,  # 10 JUMP_FORWARD, dest=14,
        0x58,  # 13 END_FINALLY,
        0x64, 0, 0,  # 14 LOAD_CONST, arg=0,
        0x53,  # 17 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 10)
    self.assertEquals(ops[0].name, 'SETUP_EXCEPT')
    self.assertEquals(ops[0].arg, 3)
    self.assertEquals(ops[0].target, ops[3])
    self.assertEquals(ops[1].name, 'POP_BLOCK')
    self.assertEquals(ops[2].name, 'JUMP_FORWARD')
    self.assertEquals(ops[2].arg, 8)
    self.assertEquals(ops[2].target, ops[8])
    self.assertEquals(ops[3].name, 'POP_TOP')
    self.assertEquals(ops[4].name, 'POP_TOP')
    self.assertEquals(ops[5].name, 'POP_TOP')
    self.assertEquals(ops[6].name, 'JUMP_FORWARD')
    self.assertEquals(ops[6].arg, 8)
    self.assertEquals(ops[6].target, ops[8])
    self.assertEquals(ops[7].name, 'END_FINALLY')
    self.assertEquals(ops[8].name, 'LOAD_CONST')
    self.assertEquals(ops[8].arg, 0)
    self.assertEquals(ops[9].name, 'RETURN_VALUE')

  def test_finally(self):
    code = ''.join(chr(c) for c in ([
        0x7a, 4, 0,  # 0 SETUP_FINALLY, dest=7,
        0x57,  # 3 POP_BLOCK,
        0x64, 0, 0,  # 4 LOAD_CONST, arg=0,
        0x58,  # 7 END_FINALLY,
        0x64, 0, 0,  # 8 LOAD_CONST, arg=0,
        0x53,  # 11 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 6)
    self.assertEquals(ops[0].name, 'SETUP_FINALLY')
    self.assertEquals(ops[0].arg, 3)
    self.assertEquals(ops[0].target, ops[3])
    self.assertEquals(ops[1].name, 'POP_BLOCK')
    self.assertEquals(ops[2].name, 'LOAD_CONST')
    self.assertEquals(ops[2].arg, 0)
    self.assertEquals(ops[3].name, 'END_FINALLY')
    self.assertEquals(ops[4].name, 'LOAD_CONST')
    self.assertEquals(ops[4].arg, 0)
    self.assertEquals(ops[5].name, 'RETURN_VALUE')

  def test_inplace(self):
    code = ''.join(chr(c) for c in ([
        0x7c, 0, 0,  # 0 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 3 LOAD_FAST, arg=0,
        0x4b,  # 6 INPLACE_LSHIFT,
        0x7d, 0, 0,  # 7 STORE_FAST, arg=0,
        0x7c, 0, 0,  # 10 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 13 LOAD_FAST, arg=0,
        0x4c,  # 16 INPLACE_RSHIFT,
        0x7d, 0, 0,  # 17 STORE_FAST, arg=0,
        0x7c, 0, 0,  # 20 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 23 LOAD_FAST, arg=0,
        0x37,  # 26 INPLACE_ADD,
        0x7d, 0, 0,  # 27 STORE_FAST, arg=0,
        0x7c, 0, 0,  # 30 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 33 LOAD_FAST, arg=0,
        0x38,  # 36 INPLACE_SUBTRACT,
        0x7d, 0, 0,  # 37 STORE_FAST, arg=0,
        0x64, 0, 0,  # 40 LOAD_CONST, arg=0,
        0x53,  # 43 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 18)
    self.assertEquals(ops[0].name, 'LOAD_FAST')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'LOAD_FAST')
    self.assertEquals(ops[1].arg, 0)
    self.assertEquals(ops[2].name, 'INPLACE_LSHIFT')
    self.assertEquals(ops[3].name, 'STORE_FAST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'LOAD_FAST')
    self.assertEquals(ops[4].arg, 0)
    self.assertEquals(ops[5].name, 'LOAD_FAST')
    self.assertEquals(ops[5].arg, 0)
    self.assertEquals(ops[6].name, 'INPLACE_RSHIFT')
    self.assertEquals(ops[7].name, 'STORE_FAST')
    self.assertEquals(ops[7].arg, 0)
    self.assertEquals(ops[8].name, 'LOAD_FAST')
    self.assertEquals(ops[8].arg, 0)
    self.assertEquals(ops[9].name, 'LOAD_FAST')
    self.assertEquals(ops[9].arg, 0)
    self.assertEquals(ops[10].name, 'INPLACE_ADD')
    self.assertEquals(ops[11].name, 'STORE_FAST')
    self.assertEquals(ops[11].arg, 0)
    self.assertEquals(ops[12].name, 'LOAD_FAST')
    self.assertEquals(ops[12].arg, 0)
    self.assertEquals(ops[13].name, 'LOAD_FAST')
    self.assertEquals(ops[13].arg, 0)
    self.assertEquals(ops[14].name, 'INPLACE_SUBTRACT')
    self.assertEquals(ops[15].name, 'STORE_FAST')
    self.assertEquals(ops[15].arg, 0)
    self.assertEquals(ops[16].name, 'LOAD_CONST')
    self.assertEquals(ops[16].arg, 0)
    self.assertEquals(ops[17].name, 'RETURN_VALUE')

  def test_list(self):
    code = ''.join(chr(c) for c in ([
        0x67, 0, 0,  # 0 BUILD_LIST, arg=0,
        0x7c, 0, 0,  # 3 LOAD_FAST, arg=0,
        0x44,  # 6 GET_ITER,
        0x5d, 12, 0,  # 7 FOR_ITER, dest=22,
        0x7d, 1, 0,  # 10 STORE_FAST, arg=1,
        0x7c, 1, 0,  # 13 LOAD_FAST, arg=1,
        0x5e, 2, 0,  # 16 LIST_APPEND, arg=2,
        0x71, 7, 0,  # 19 JUMP_ABSOLUTE, dest=7,
        0x01,  # 22 POP_TOP,
        0x64, 0, 0,  # 23 LOAD_CONST, arg=0,
        0x53,  # 26 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 11)
    self.assertEquals(ops[0].name, 'BUILD_LIST')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'LOAD_FAST')
    self.assertEquals(ops[1].arg, 0)
    self.assertEquals(ops[2].name, 'GET_ITER')
    self.assertEquals(ops[3].name, 'FOR_ITER')
    self.assertEquals(ops[3].arg, 8)
    self.assertEquals(ops[3].target, ops[8])
    self.assertEquals(ops[4].name, 'STORE_FAST')
    self.assertEquals(ops[4].arg, 1)
    self.assertEquals(ops[5].name, 'LOAD_FAST')
    self.assertEquals(ops[5].arg, 1)
    self.assertEquals(ops[6].name, 'LIST_APPEND')
    self.assertEquals(ops[6].arg, 2)
    self.assertEquals(ops[7].name, 'JUMP_ABSOLUTE')
    self.assertEquals(ops[7].arg, 3)
    self.assertEquals(ops[7].target, ops[3])
    self.assertEquals(ops[8].name, 'POP_TOP')
    self.assertEquals(ops[9].name, 'LOAD_CONST')
    self.assertEquals(ops[9].arg, 0)
    self.assertEquals(ops[10].name, 'RETURN_VALUE')

  def test_loop(self):
    code = ''.join(chr(c) for c in ([
        0x78, 10, 0,  # 0 SETUP_LOOP, dest=13,
        0x74, 0, 0,  # 3 LOAD_GLOBAL, arg=0,
        0x72, 12, 0,  # 6 POP_JUMP_IF_FALSE, dest=12,
        0x71, 3, 0,  # 9 JUMP_ABSOLUTE, dest=3,
        0x57,  # 12 POP_BLOCK,
        0x64, 0, 0,  # 13 LOAD_CONST, arg=0,
        0x53,  # 16 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 7)
    self.assertEquals(ops[0].name, 'SETUP_LOOP')
    self.assertEquals(ops[0].arg, 5)
    self.assertEquals(ops[0].target, ops[5])
    self.assertEquals(ops[1].name, 'LOAD_GLOBAL')
    self.assertEquals(ops[1].arg, 0)
    self.assertEquals(ops[2].name, 'POP_JUMP_IF_FALSE')
    self.assertEquals(ops[2].arg, 4)
    self.assertEquals(ops[2].target, ops[4])
    self.assertEquals(ops[3].name, 'JUMP_ABSOLUTE')
    self.assertEquals(ops[3].arg, 1)
    self.assertEquals(ops[3].target, ops[1])
    self.assertEquals(ops[4].name, 'POP_BLOCK')
    self.assertEquals(ops[5].name, 'LOAD_CONST')
    self.assertEquals(ops[5].arg, 0)
    self.assertEquals(ops[6].name, 'RETURN_VALUE')

  def test_raise_one(self):
    code = ''.join(chr(c) for c in ([
        0x64, 0, 0,  # 0 LOAD_CONST, arg=0,
        0x82, 1, 0,  # 3 RAISE_VARARGS, arg=1,
        0x64, 0, 0,  # 6 LOAD_CONST, arg=0,
        0x53,  # 9 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 4)
    self.assertEquals(ops[0].name, 'LOAD_CONST')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'RAISE_VARARGS')
    self.assertEquals(ops[1].arg, 1)
    self.assertEquals(ops[2].name, 'LOAD_CONST')
    self.assertEquals(ops[2].arg, 0)
    self.assertEquals(ops[3].name, 'RETURN_VALUE')

  def test_unary(self):
    code = ''.join(chr(c) for c in ([
        0x7c, 0, 0,  # 0 LOAD_FAST, arg=0,
        0x0b,  # 3 UNARY_NEGATIVE,
        0x01,  # 4 POP_TOP,
        0x7c, 0, 0,  # 5 LOAD_FAST, arg=0,
        0x0f,  # 8 UNARY_INVERT,
        0x01,  # 9 POP_TOP,
        0x7c, 0, 0,  # 10 LOAD_FAST, arg=0,
        0x0a,  # 13 UNARY_POSITIVE,
        0x01,  # 14 POP_TOP,
        0x64, 0, 0,  # 15 LOAD_CONST, arg=0,
        0x53,  # 18 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 11)
    self.assertEquals(ops[0].name, 'LOAD_FAST')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'UNARY_NEGATIVE')
    self.assertEquals(ops[2].name, 'POP_TOP')
    self.assertEquals(ops[3].name, 'LOAD_FAST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'UNARY_INVERT')
    self.assertEquals(ops[5].name, 'POP_TOP')
    self.assertEquals(ops[6].name, 'LOAD_FAST')
    self.assertEquals(ops[6].arg, 0)
    self.assertEquals(ops[7].name, 'UNARY_POSITIVE')
    self.assertEquals(ops[8].name, 'POP_TOP')
    self.assertEquals(ops[9].name, 'LOAD_CONST')
    self.assertEquals(ops[9].arg, 0)
    self.assertEquals(ops[10].name, 'RETURN_VALUE')

  def test_with(self):
    code = ''.join(chr(c) for c in ([
        0x64, 0, 0,  # 0 LOAD_CONST, arg=0,
        0x8f, 5, 0,  # 3 SETUP_WITH, dest=11,
        0x01,  # 6 POP_TOP,
        0x57,  # 7 POP_BLOCK,
        0x64, 0, 0,  # 8 LOAD_CONST, arg=0,
        0x51,  # 11 WITH_CLEANUP,
        0x58,  # 12 END_FINALLY,
        0x64, 0, 0,  # 13 LOAD_CONST, arg=0,
        0x53,  # 16 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 9)
    self.assertEquals(ops[0].name, 'LOAD_CONST')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'SETUP_WITH')
    self.assertEquals(ops[1].arg, 5)
    self.assertEquals(ops[1].target, ops[5])
    self.assertEquals(ops[2].name, 'POP_TOP')
    self.assertEquals(ops[3].name, 'POP_BLOCK')
    self.assertEquals(ops[4].name, 'LOAD_CONST')
    self.assertEquals(ops[4].arg, 0)
    self.assertEquals(ops[5].name, 'WITH_CLEANUP')
    self.assertEquals(ops[6].name, 'END_FINALLY')
    self.assertEquals(ops[7].name, 'LOAD_CONST')
    self.assertEquals(ops[7].arg, 0)
    self.assertEquals(ops[8].name, 'RETURN_VALUE')


class Python3Test(unittest.TestCase):
  """Test bytecodes.dis for Python 3 opcodes."""

  PYTHON_VERSION = (3, 3, 0)

  def dis(self, data):
    return opcodes.dis(data, self.PYTHON_VERSION)

  def test_pop_top(self):
    self.assertEquals(self.dis('\x01')[0].name, 'POP_TOP')

  def test_rot_two(self):
    self.assertEquals(self.dis('\x02')[0].name, 'ROT_TWO')

  def test_rot_three(self):
    self.assertEquals(self.dis('\x03')[0].name, 'ROT_THREE')

  def test_dup_top(self):
    self.assertEquals(self.dis('\x04')[0].name, 'DUP_TOP')

  def test_dup_top_two(self):
    self.assertEquals(self.dis('\x05')[0].name, 'DUP_TOP_TWO')

  def test_nop(self):
    self.assertEquals(self.dis('\t')[0].name, 'NOP')

  def test_unary_positive(self):
    self.assertEquals(self.dis('\n')[0].name, 'UNARY_POSITIVE')

  def test_unary_negative(self):
    self.assertEquals(self.dis('\x0b')[0].name, 'UNARY_NEGATIVE')

  def test_unary_not(self):
    self.assertEquals(self.dis('\x0c')[0].name, 'UNARY_NOT')

  def test_unary_invert(self):
    self.assertEquals(self.dis('\x0f')[0].name, 'UNARY_INVERT')

  def test_binary_power(self):
    self.assertEquals(self.dis('\x13')[0].name, 'BINARY_POWER')

  def test_binary_multiply(self):
    self.assertEquals(self.dis('\x14')[0].name, 'BINARY_MULTIPLY')

  def test_binary_modulo(self):
    self.assertEquals(self.dis('\x16')[0].name, 'BINARY_MODULO')

  def test_binary_add(self):
    self.assertEquals(self.dis('\x17')[0].name, 'BINARY_ADD')

  def test_binary_subtract(self):
    self.assertEquals(self.dis('\x18')[0].name, 'BINARY_SUBTRACT')

  def test_binary_subscr(self):
    self.assertEquals(self.dis('\x19')[0].name, 'BINARY_SUBSCR')

  def test_binary_floor_divide(self):
    self.assertEquals(self.dis('\x1a')[0].name, 'BINARY_FLOOR_DIVIDE')

  def test_binary_true_divide(self):
    self.assertEquals(self.dis('\x1b')[0].name, 'BINARY_TRUE_DIVIDE')

  def test_inplace_floor_divide(self):
    self.assertEquals(self.dis('\x1c')[0].name, 'INPLACE_FLOOR_DIVIDE')

  def test_inplace_true_divide(self):
    self.assertEquals(self.dis('\x1d')[0].name, 'INPLACE_TRUE_DIVIDE')

  def test_store_map(self):
    self.assertEquals(self.dis('6')[0].name, 'STORE_MAP')

  def test_inplace_add(self):
    self.assertEquals(self.dis('7')[0].name, 'INPLACE_ADD')

  def test_inplace_subtract(self):
    self.assertEquals(self.dis('8')[0].name, 'INPLACE_SUBTRACT')

  def test_inplace_multiply(self):
    self.assertEquals(self.dis('9')[0].name, 'INPLACE_MULTIPLY')

  def test_inplace_modulo(self):
    self.assertEquals(self.dis(';')[0].name, 'INPLACE_MODULO')

  def test_store_subscr(self):
    self.assertEquals(self.dis('<')[0].name, 'STORE_SUBSCR')

  def test_delete_subscr(self):
    self.assertEquals(self.dis('=')[0].name, 'DELETE_SUBSCR')

  def test_binary_lshift(self):
    self.assertEquals(self.dis('>')[0].name, 'BINARY_LSHIFT')

  def test_binary_rshift(self):
    self.assertEquals(self.dis('?')[0].name, 'BINARY_RSHIFT')

  def test_binary_and(self):
    self.assertEquals(self.dis('@')[0].name, 'BINARY_AND')

  def test_binary_xor(self):
    self.assertEquals(self.dis('A')[0].name, 'BINARY_XOR')

  def test_binary_or(self):
    self.assertEquals(self.dis('B')[0].name, 'BINARY_OR')

  def test_inplace_power(self):
    self.assertEquals(self.dis('C')[0].name, 'INPLACE_POWER')

  def test_get_iter(self):
    self.assertEquals(self.dis('D')[0].name, 'GET_ITER')

  def test_print_expr(self):
    self.assertEquals(self.dis('F')[0].name, 'PRINT_EXPR')

  def test_load_build_class(self):
    self.assertEquals(self.dis('G')[0].name, 'LOAD_BUILD_CLASS')

  def test_yield_from(self):
    self.assertEquals(self.dis('H')[0].name, 'YIELD_FROM')

  def test_inplace_lshift(self):
    self.assertEquals(self.dis('K')[0].name, 'INPLACE_LSHIFT')

  def test_inplace_rshift(self):
    self.assertEquals(self.dis('L')[0].name, 'INPLACE_RSHIFT')

  def test_inplace_and(self):
    self.assertEquals(self.dis('M')[0].name, 'INPLACE_AND')

  def test_inplace_xor(self):
    self.assertEquals(self.dis('N')[0].name, 'INPLACE_XOR')

  def test_inplace_or(self):
    self.assertEquals(self.dis('O')[0].name, 'INPLACE_OR')

  def test_break_loop(self):
    self.assertEquals(self.dis('P')[0].name, 'BREAK_LOOP')

  def test_with_cleanup(self):
    self.assertEquals(self.dis('Q')[0].name, 'WITH_CLEANUP')

  def test_return_value(self):
    self.assertEquals(self.dis('S')[0].name, 'RETURN_VALUE')

  def test_import_star(self):
    self.assertEquals(self.dis('T')[0].name, 'IMPORT_STAR')

  def test_yield_value(self):
    self.assertEquals(self.dis('V')[0].name, 'YIELD_VALUE')

  def test_pop_block(self):
    self.assertEquals(self.dis('W')[0].name, 'POP_BLOCK')

  def test_end_finally(self):
    self.assertEquals(self.dis('X')[0].name, 'END_FINALLY')

  def test_pop_except(self):
    self.assertEquals(self.dis('Y')[0].name, 'POP_EXCEPT')

  def test_store_name(self):
    self.assertEquals(self.dis('Z\x00\x00')[0].name, 'STORE_NAME')

  def test_delete_name(self):
    self.assertEquals(self.dis('[\x00\x00')[0].name, 'DELETE_NAME')

  def test_unpack_sequence(self):
    self.assertEquals(self.dis('\\\x00\x00')[0].name, 'UNPACK_SEQUENCE')

  def test_for_iter(self):
    self.assertEquals(self.dis(']\x00\x00\t')[0].name, 'FOR_ITER')

  def test_unpack_ex(self):
    self.assertEquals(self.dis('^\x00\x00')[0].name, 'UNPACK_EX')

  def test_store_attr(self):
    self.assertEquals(self.dis('_\x00\x00')[0].name, 'STORE_ATTR')

  def test_delete_attr(self):
    self.assertEquals(self.dis('`\x00\x00')[0].name, 'DELETE_ATTR')

  def test_store_global(self):
    self.assertEquals(self.dis('a\x00\x00')[0].name, 'STORE_GLOBAL')

  def test_delete_global(self):
    self.assertEquals(self.dis('b\x00\x00')[0].name, 'DELETE_GLOBAL')

  def test_load_const(self):
    self.assertEquals(self.dis('d\x00\x00')[0].name, 'LOAD_CONST')

  def test_load_name(self):
    self.assertEquals(self.dis('e\x00\x00')[0].name, 'LOAD_NAME')

  def test_build_tuple(self):
    self.assertEquals(self.dis('f\x00\x00')[0].name, 'BUILD_TUPLE')

  def test_build_list(self):
    self.assertEquals(self.dis('g\x00\x00')[0].name, 'BUILD_LIST')

  def test_build_set(self):
    self.assertEquals(self.dis('h\x00\x00')[0].name, 'BUILD_SET')

  def test_build_map(self):
    self.assertEquals(self.dis('i\x00\x00')[0].name, 'BUILD_MAP')

  def test_load_attr(self):
    self.assertEquals(self.dis('j\x00\x00')[0].name, 'LOAD_ATTR')

  def test_compare_op(self):
    self.assertEquals(self.dis('k\x00\x00')[0].name, 'COMPARE_OP')

  def test_import_name(self):
    self.assertEquals(self.dis('l\x00\x00')[0].name, 'IMPORT_NAME')

  def test_import_from(self):
    self.assertEquals(self.dis('m\x00\x00')[0].name, 'IMPORT_FROM')

  def test_jump_forward(self):
    self.assertEquals(self.dis('n\x00\x00\t')[0].name, 'JUMP_FORWARD')

  def test_jump_if_false_or_pop(self):
    self.assertEquals(self.dis('o\x03\x00\t')[0].name, 'JUMP_IF_FALSE_OR_POP')

  def test_jump_if_true_or_pop(self):
    self.assertEquals(self.dis('p\x03\x00\t')[0].name, 'JUMP_IF_TRUE_OR_POP')

  def test_jump_absolute(self):
    self.assertEquals(self.dis('q\x03\x00\t')[0].name, 'JUMP_ABSOLUTE')

  def test_pop_jump_if_false(self):
    self.assertEquals(self.dis('r\x03\x00\t')[0].name, 'POP_JUMP_IF_FALSE')

  def test_pop_jump_if_true(self):
    self.assertEquals(self.dis('s\x03\x00\t')[0].name, 'POP_JUMP_IF_TRUE')

  def test_load_global(self):
    self.assertEquals(self.dis('t\x00\x00')[0].name, 'LOAD_GLOBAL')

  def test_continue_loop(self):
    self.assertEquals(self.dis('w\x03\x00\t')[0].name, 'CONTINUE_LOOP')

  def test_setup_loop(self):
    self.assertEquals(self.dis('x\x00\x00\t')[0].name, 'SETUP_LOOP')

  def test_setup_except(self):
    self.assertEquals(self.dis('y\x00\x00\t')[0].name, 'SETUP_EXCEPT')

  def test_setup_finally(self):
    self.assertEquals(self.dis('z\x00\x00\t')[0].name, 'SETUP_FINALLY')

  def test_load_fast(self):
    self.assertEquals(self.dis('|\x00\x00')[0].name, 'LOAD_FAST')

  def test_store_fast(self):
    self.assertEquals(self.dis('}\x00\x00')[0].name, 'STORE_FAST')

  def test_delete_fast(self):
    self.assertEquals(self.dis('~\x00\x00')[0].name, 'DELETE_FAST')

  def test_raise_varargs(self):
    self.assertEquals(self.dis('\x82\x00\x00')[0].name, 'RAISE_VARARGS')

  def test_call_function(self):
    self.assertEquals(self.dis('\x83\x00\x00')[0].name, 'CALL_FUNCTION')

  def test_make_function(self):
    self.assertEquals(self.dis('\x84\x00\x00')[0].name, 'MAKE_FUNCTION')

  def test_build_slice(self):
    self.assertEquals(self.dis('\x85\x00\x00')[0].name, 'BUILD_SLICE')

  def test_make_closure(self):
    self.assertEquals(self.dis('\x86\x00\x00')[0].name, 'MAKE_CLOSURE')

  def test_load_closure(self):
    self.assertEquals(self.dis('\x87\x00\x00')[0].name, 'LOAD_CLOSURE')

  def test_load_deref(self):
    self.assertEquals(self.dis('\x88\x00\x00')[0].name, 'LOAD_DEREF')

  def test_store_deref(self):
    self.assertEquals(self.dis('\x89\x00\x00')[0].name, 'STORE_DEREF')

  def test_delete_deref(self):
    self.assertEquals(self.dis('\x8a\x00\x00')[0].name, 'DELETE_DEREF')

  def test_call_function_var(self):
    self.assertEquals(self.dis('\x8c\x00\x00')[0].name, 'CALL_FUNCTION_VAR')

  def test_call_function_kw(self):
    self.assertEquals(self.dis('\x8d\x00\x00')[0].name, 'CALL_FUNCTION_KW')

  def test_call_function_var_kw(self):
    self.assertEquals(self.dis('\x8e\x00\x00')[0].name, 'CALL_FUNCTION_VAR_KW')

  def test_setup_with(self):
    self.assertEquals(self.dis('\x8f\x00\x00\t')[0].name, 'SETUP_WITH')

  def test_list_append(self):
    self.assertEquals(self.dis('\x91\x00\x00')[0].name, 'LIST_APPEND')

  def test_set_add(self):
    self.assertEquals(self.dis('\x92\x00\x00')[0].name, 'SET_ADD')

  def test_map_add(self):
    self.assertEquals(self.dis('\x93\x00\x00')[0].name, 'MAP_ADD')

  def test_load_classderef(self):
    self.assertEquals(self.dis('\x94\x00\x00')[0].name, 'LOAD_CLASSDEREF')

  def test_binary(self):
    code = ''.join(chr(c) for c in ([
        0x7c, 0, 0,  # 0 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 3 LOAD_FAST, arg=0,
        0x17,  # 6 BINARY_ADD,
        0x01,  # 7 POP_TOP,
        0x7c, 0, 0,  # 8 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 11 LOAD_FAST, arg=0,
        0x14,  # 14 BINARY_MULTIPLY,
        0x01,  # 15 POP_TOP,
        0x7c, 0, 0,  # 16 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 19 LOAD_FAST, arg=0,
        0x16,  # 22 BINARY_MODULO,
        0x01,  # 23 POP_TOP,
        0x7c, 0, 0,  # 24 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 27 LOAD_FAST, arg=0,
        0x1b,  # 30 BINARY_TRUE_DIVIDE,
        0x01,  # 31 POP_TOP,
        0x64, 0, 0,  # 32 LOAD_CONST, arg=0,
        0x53,  # 35 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 18)
    self.assertEquals(ops[0].name, 'LOAD_FAST')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'LOAD_FAST')
    self.assertEquals(ops[1].arg, 0)
    self.assertEquals(ops[2].name, 'BINARY_ADD')
    self.assertEquals(ops[3].name, 'POP_TOP')
    self.assertEquals(ops[4].name, 'LOAD_FAST')
    self.assertEquals(ops[4].arg, 0)
    self.assertEquals(ops[5].name, 'LOAD_FAST')
    self.assertEquals(ops[5].arg, 0)
    self.assertEquals(ops[6].name, 'BINARY_MULTIPLY')
    self.assertEquals(ops[7].name, 'POP_TOP')
    self.assertEquals(ops[8].name, 'LOAD_FAST')
    self.assertEquals(ops[8].arg, 0)
    self.assertEquals(ops[9].name, 'LOAD_FAST')
    self.assertEquals(ops[9].arg, 0)
    self.assertEquals(ops[10].name, 'BINARY_MODULO')
    self.assertEquals(ops[11].name, 'POP_TOP')
    self.assertEquals(ops[12].name, 'LOAD_FAST')
    self.assertEquals(ops[12].arg, 0)
    self.assertEquals(ops[13].name, 'LOAD_FAST')
    self.assertEquals(ops[13].arg, 0)
    self.assertEquals(ops[14].name, 'BINARY_TRUE_DIVIDE')
    self.assertEquals(ops[15].name, 'POP_TOP')
    self.assertEquals(ops[16].name, 'LOAD_CONST')
    self.assertEquals(ops[16].arg, 0)
    self.assertEquals(ops[17].name, 'RETURN_VALUE')

  def test_break(self):
    code = ''.join(chr(c) for c in ([
        0x78, 4, 0,  # 0 SETUP_LOOP, dest=7,
        0x50,  # 3 BREAK_LOOP,
        0x71, 3, 0,  # 4 JUMP_ABSOLUTE, dest=3,
        0x64, 0, 0,  # 7 LOAD_CONST, arg=0,
        0x53,  # 10 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 5)
    self.assertEquals(ops[0].name, 'SETUP_LOOP')
    self.assertEquals(ops[0].arg, 3)
    self.assertEquals(ops[0].target, ops[3])
    self.assertEquals(ops[1].name, 'BREAK_LOOP')
    self.assertEquals(ops[2].name, 'JUMP_ABSOLUTE')
    self.assertEquals(ops[2].arg, 1)
    self.assertEquals(ops[2].target, ops[1])
    self.assertEquals(ops[3].name, 'LOAD_CONST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'RETURN_VALUE')

  def test_call(self):
    code = ''.join(chr(c) for c in ([
        0x74, 0, 0,  # 0 LOAD_GLOBAL, arg=0,
        0x83, 0, 0,  # 3 CALL_FUNCTION, arg=0,
        0x01,  # 6 POP_TOP,
        0x64, 0, 0,  # 7 LOAD_CONST, arg=0,
        0x53,  # 10 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 5)
    self.assertEquals(ops[0].name, 'LOAD_GLOBAL')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'CALL_FUNCTION')
    self.assertEquals(ops[1].arg, 0)
    self.assertEquals(ops[2].name, 'POP_TOP')
    self.assertEquals(ops[3].name, 'LOAD_CONST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'RETURN_VALUE')

  def test_continue(self):
    code = ''.join(chr(c) for c in ([
        0x78, 6, 0,  # 0 SETUP_LOOP, dest=9,
        0x71, 3, 0,  # 3 JUMP_ABSOLUTE, dest=3,
        0x71, 3, 0,  # 6 JUMP_ABSOLUTE, dest=3,
        0x64, 0, 0,  # 9 LOAD_CONST, arg=0,
        0x53,  # 12 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 5)
    self.assertEquals(ops[0].name, 'SETUP_LOOP')
    self.assertEquals(ops[0].arg, 3)
    self.assertEquals(ops[0].target, ops[3])
    self.assertEquals(ops[1].name, 'JUMP_ABSOLUTE')
    self.assertEquals(ops[1].arg, 1)
    self.assertEquals(ops[1].target, ops[1])
    self.assertEquals(ops[2].name, 'JUMP_ABSOLUTE')
    self.assertEquals(ops[2].arg, 1)
    self.assertEquals(ops[2].target, ops[1])
    self.assertEquals(ops[3].name, 'LOAD_CONST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'RETURN_VALUE')

  def test_except(self):
    code = ''.join(chr(c) for c in ([
        0x79, 4, 0,  # 0 SETUP_EXCEPT, dest=7,
        0x57,  # 3 POP_BLOCK,
        0x6e, 8, 0,  # 4 JUMP_FORWARD, dest=15,
        0x01,  # 7 POP_TOP,
        0x01,  # 8 POP_TOP,
        0x01,  # 9 POP_TOP,
        0x59,  # 10 POP_EXCEPT,
        0x6e, 1, 0,  # 11 JUMP_FORWARD, dest=15,
        0x58,  # 14 END_FINALLY,
        0x64, 0, 0,  # 15 LOAD_CONST, arg=0,
        0x53,  # 18 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 11)
    self.assertEquals(ops[0].name, 'SETUP_EXCEPT')
    self.assertEquals(ops[0].arg, 3)
    self.assertEquals(ops[0].target, ops[3])
    self.assertEquals(ops[1].name, 'POP_BLOCK')
    self.assertEquals(ops[2].name, 'JUMP_FORWARD')
    self.assertEquals(ops[2].arg, 9)
    self.assertEquals(ops[2].target, ops[9])
    self.assertEquals(ops[3].name, 'POP_TOP')
    self.assertEquals(ops[4].name, 'POP_TOP')
    self.assertEquals(ops[5].name, 'POP_TOP')
    self.assertEquals(ops[6].name, 'POP_EXCEPT')
    self.assertEquals(ops[7].name, 'JUMP_FORWARD')
    self.assertEquals(ops[7].arg, 9)
    self.assertEquals(ops[7].target, ops[9])
    self.assertEquals(ops[8].name, 'END_FINALLY')
    self.assertEquals(ops[9].name, 'LOAD_CONST')
    self.assertEquals(ops[9].arg, 0)
    self.assertEquals(ops[10].name, 'RETURN_VALUE')

  def test_finally(self):
    code = ''.join(chr(c) for c in ([
        0x7a, 4, 0,  # 0 SETUP_FINALLY, dest=7,
        0x57,  # 3 POP_BLOCK,
        0x64, 0, 0,  # 4 LOAD_CONST, arg=0,
        0x58,  # 7 END_FINALLY,
        0x64, 0, 0,  # 8 LOAD_CONST, arg=0,
        0x53,  # 11 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 6)
    self.assertEquals(ops[0].name, 'SETUP_FINALLY')
    self.assertEquals(ops[0].arg, 3)
    self.assertEquals(ops[0].target, ops[3])
    self.assertEquals(ops[1].name, 'POP_BLOCK')
    self.assertEquals(ops[2].name, 'LOAD_CONST')
    self.assertEquals(ops[2].arg, 0)
    self.assertEquals(ops[3].name, 'END_FINALLY')
    self.assertEquals(ops[4].name, 'LOAD_CONST')
    self.assertEquals(ops[4].arg, 0)
    self.assertEquals(ops[5].name, 'RETURN_VALUE')

  def test_inplace(self):
    code = ''.join(chr(c) for c in ([
        0x7c, 0, 0,  # 0 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 3 LOAD_FAST, arg=0,
        0x4b,  # 6 INPLACE_LSHIFT,
        0x7d, 0, 0,  # 7 STORE_FAST, arg=0,
        0x7c, 0, 0,  # 10 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 13 LOAD_FAST, arg=0,
        0x4c,  # 16 INPLACE_RSHIFT,
        0x7d, 0, 0,  # 17 STORE_FAST, arg=0,
        0x7c, 0, 0,  # 20 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 23 LOAD_FAST, arg=0,
        0x37,  # 26 INPLACE_ADD,
        0x7d, 0, 0,  # 27 STORE_FAST, arg=0,
        0x7c, 0, 0,  # 30 LOAD_FAST, arg=0,
        0x7c, 0, 0,  # 33 LOAD_FAST, arg=0,
        0x38,  # 36 INPLACE_SUBTRACT,
        0x7d, 0, 0,  # 37 STORE_FAST, arg=0,
        0x64, 0, 0,  # 40 LOAD_CONST, arg=0,
        0x53,  # 43 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 18)
    self.assertEquals(ops[0].name, 'LOAD_FAST')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'LOAD_FAST')
    self.assertEquals(ops[1].arg, 0)
    self.assertEquals(ops[2].name, 'INPLACE_LSHIFT')
    self.assertEquals(ops[3].name, 'STORE_FAST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'LOAD_FAST')
    self.assertEquals(ops[4].arg, 0)
    self.assertEquals(ops[5].name, 'LOAD_FAST')
    self.assertEquals(ops[5].arg, 0)
    self.assertEquals(ops[6].name, 'INPLACE_RSHIFT')
    self.assertEquals(ops[7].name, 'STORE_FAST')
    self.assertEquals(ops[7].arg, 0)
    self.assertEquals(ops[8].name, 'LOAD_FAST')
    self.assertEquals(ops[8].arg, 0)
    self.assertEquals(ops[9].name, 'LOAD_FAST')
    self.assertEquals(ops[9].arg, 0)
    self.assertEquals(ops[10].name, 'INPLACE_ADD')
    self.assertEquals(ops[11].name, 'STORE_FAST')
    self.assertEquals(ops[11].arg, 0)
    self.assertEquals(ops[12].name, 'LOAD_FAST')
    self.assertEquals(ops[12].arg, 0)
    self.assertEquals(ops[13].name, 'LOAD_FAST')
    self.assertEquals(ops[13].arg, 0)
    self.assertEquals(ops[14].name, 'INPLACE_SUBTRACT')
    self.assertEquals(ops[15].name, 'STORE_FAST')
    self.assertEquals(ops[15].arg, 0)
    self.assertEquals(ops[16].name, 'LOAD_CONST')
    self.assertEquals(ops[16].arg, 0)
    self.assertEquals(ops[17].name, 'RETURN_VALUE')

  def test_list(self):
    code = ''.join(chr(c) for c in ([
        0x64, 1, 0,  # 0 LOAD_CONST, arg=1,
        0x64, 2, 0,  # 3 LOAD_CONST, arg=2,
        0x84, 0, 0,  # 6 MAKE_FUNCTION, arg=0,
        0x7c, 0, 0,  # 9 LOAD_FAST, arg=0,
        0x44,  # 12 GET_ITER,
        0x83, 1, 0,  # 13 CALL_FUNCTION, arg=1,
        0x01,  # 16 POP_TOP,
        0x64, 0, 0,  # 17 LOAD_CONST, arg=0,
        0x53,  # 20 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 9)
    self.assertEquals(ops[0].name, 'LOAD_CONST')
    self.assertEquals(ops[0].arg, 1)
    self.assertEquals(ops[1].name, 'LOAD_CONST')
    self.assertEquals(ops[1].arg, 2)
    self.assertEquals(ops[2].name, 'MAKE_FUNCTION')
    self.assertEquals(ops[2].arg, 0)
    self.assertEquals(ops[3].name, 'LOAD_FAST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'GET_ITER')
    self.assertEquals(ops[5].name, 'CALL_FUNCTION')
    self.assertEquals(ops[5].arg, 1)
    self.assertEquals(ops[6].name, 'POP_TOP')
    self.assertEquals(ops[7].name, 'LOAD_CONST')
    self.assertEquals(ops[7].arg, 0)
    self.assertEquals(ops[8].name, 'RETURN_VALUE')

  def test_loop(self):
    code = ''.join(chr(c) for c in ([
        0x78, 3, 0,  # 0 SETUP_LOOP, dest=6,
        0x71, 3, 0,  # 3 JUMP_ABSOLUTE, dest=3,
        0x64, 0, 0,  # 6 LOAD_CONST, arg=0,
        0x53,  # 9 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 4)
    self.assertEquals(ops[0].name, 'SETUP_LOOP')
    self.assertEquals(ops[0].arg, 2)
    self.assertEquals(ops[0].target, ops[2])
    self.assertEquals(ops[1].name, 'JUMP_ABSOLUTE')
    self.assertEquals(ops[1].arg, 1)
    self.assertEquals(ops[1].target, ops[1])
    self.assertEquals(ops[2].name, 'LOAD_CONST')
    self.assertEquals(ops[2].arg, 0)
    self.assertEquals(ops[3].name, 'RETURN_VALUE')

  def test_raise_zero(self):
    code = ''.join(chr(c) for c in ([
        0x82, 0, 0,  # 0 RAISE_VARARGS, arg=0,
        0x64, 0, 0,  # 3 LOAD_CONST, arg=0,
        0x53,  # 6 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 3)
    self.assertEquals(ops[0].name, 'RAISE_VARARGS')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'LOAD_CONST')
    self.assertEquals(ops[1].arg, 0)
    self.assertEquals(ops[2].name, 'RETURN_VALUE')

  def test_raise_one(self):
    code = ''.join(chr(c) for c in ([
        0x64, 0, 0,  # 0 LOAD_CONST, arg=0,
        0x82, 1, 0,  # 3 RAISE_VARARGS, arg=1,
        0x64, 0, 0,  # 6 LOAD_CONST, arg=0,
        0x53,  # 9 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 4)
    self.assertEquals(ops[0].name, 'LOAD_CONST')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'RAISE_VARARGS')
    self.assertEquals(ops[1].arg, 1)
    self.assertEquals(ops[2].name, 'LOAD_CONST')
    self.assertEquals(ops[2].arg, 0)
    self.assertEquals(ops[3].name, 'RETURN_VALUE')

  def test_raise_two(self):
    code = ''.join(chr(c) for c in ([
        0x74, 0, 0,  # 0 LOAD_GLOBAL, arg=0,
        0x74, 1, 0,  # 3 LOAD_GLOBAL, arg=1,
        0x82, 2, 0,  # 6 RAISE_VARARGS, arg=2,
        0x64, 0, 0,  # 9 LOAD_CONST, arg=0,
        0x53,  # 12 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 5)
    self.assertEquals(ops[0].name, 'LOAD_GLOBAL')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'LOAD_GLOBAL')
    self.assertEquals(ops[1].arg, 1)
    self.assertEquals(ops[2].name, 'RAISE_VARARGS')
    self.assertEquals(ops[2].arg, 2)
    self.assertEquals(ops[3].name, 'LOAD_CONST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'RETURN_VALUE')

  def test_raise_three(self):
    code = ''.join(chr(c) for c in ([
        0x74, 0, 0,  # 0 LOAD_GLOBAL, arg=0,
        0x74, 1, 0,  # 3 LOAD_GLOBAL, arg=1,
        0x64, 1, 0,  # 6 LOAD_CONST, arg=1,
        0x82, 3, 0,  # 9 RAISE_VARARGS, arg=3,
        0x64, 0, 0,  # 12 LOAD_CONST, arg=0,
        0x53,  # 15 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 6)
    self.assertEquals(ops[0].name, 'LOAD_GLOBAL')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'LOAD_GLOBAL')
    self.assertEquals(ops[1].arg, 1)
    self.assertEquals(ops[2].name, 'LOAD_CONST')
    self.assertEquals(ops[2].arg, 1)
    self.assertEquals(ops[3].name, 'RAISE_VARARGS')
    self.assertEquals(ops[3].arg, 3)
    self.assertEquals(ops[4].name, 'LOAD_CONST')
    self.assertEquals(ops[4].arg, 0)
    self.assertEquals(ops[5].name, 'RETURN_VALUE')

  def test_unary(self):
    code = ''.join(chr(c) for c in ([
        0x7c, 0, 0,  # 0 LOAD_FAST, arg=0,
        0x0b,  # 3 UNARY_NEGATIVE,
        0x01,  # 4 POP_TOP,
        0x7c, 0, 0,  # 5 LOAD_FAST, arg=0,
        0x0f,  # 8 UNARY_INVERT,
        0x01,  # 9 POP_TOP,
        0x7c, 0, 0,  # 10 LOAD_FAST, arg=0,
        0x0a,  # 13 UNARY_POSITIVE,
        0x01,  # 14 POP_TOP,
        0x64, 0, 0,  # 15 LOAD_CONST, arg=0,
        0x53,  # 18 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 11)
    self.assertEquals(ops[0].name, 'LOAD_FAST')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'UNARY_NEGATIVE')
    self.assertEquals(ops[2].name, 'POP_TOP')
    self.assertEquals(ops[3].name, 'LOAD_FAST')
    self.assertEquals(ops[3].arg, 0)
    self.assertEquals(ops[4].name, 'UNARY_INVERT')
    self.assertEquals(ops[5].name, 'POP_TOP')
    self.assertEquals(ops[6].name, 'LOAD_FAST')
    self.assertEquals(ops[6].arg, 0)
    self.assertEquals(ops[7].name, 'UNARY_POSITIVE')
    self.assertEquals(ops[8].name, 'POP_TOP')
    self.assertEquals(ops[9].name, 'LOAD_CONST')
    self.assertEquals(ops[9].arg, 0)
    self.assertEquals(ops[10].name, 'RETURN_VALUE')

  def test_with(self):
    code = ''.join(chr(c) for c in ([
        0x64, 0, 0,  # 0 LOAD_CONST, arg=0,
        0x8f, 5, 0,  # 3 SETUP_WITH, dest=11,
        0x01,  # 6 POP_TOP,
        0x57,  # 7 POP_BLOCK,
        0x64, 0, 0,  # 8 LOAD_CONST, arg=0,
        0x51,  # 11 WITH_CLEANUP,
        0x58,  # 12 END_FINALLY,
        0x64, 0, 0,  # 13 LOAD_CONST, arg=0,
        0x53,  # 16 RETURN_VALUE
    ]))
    ops = opcodes.dis(code, self.PYTHON_VERSION)
    self.assertEquals(len(ops), 9)
    self.assertEquals(ops[0].name, 'LOAD_CONST')
    self.assertEquals(ops[0].arg, 0)
    self.assertEquals(ops[1].name, 'SETUP_WITH')
    self.assertEquals(ops[1].arg, 5)
    self.assertEquals(ops[1].target, ops[5])
    self.assertEquals(ops[2].name, 'POP_TOP')
    self.assertEquals(ops[3].name, 'POP_BLOCK')
    self.assertEquals(ops[4].name, 'LOAD_CONST')
    self.assertEquals(ops[4].arg, 0)
    self.assertEquals(ops[5].name, 'WITH_CLEANUP')
    self.assertEquals(ops[6].name, 'END_FINALLY')
    self.assertEquals(ops[7].name, 'LOAD_CONST')
    self.assertEquals(ops[7].arg, 0)
    self.assertEquals(ops[8].name, 'RETURN_VALUE')

if __name__ == '__main__':
  unittest.main()
