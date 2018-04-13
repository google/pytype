from pytype import compat
from pytype.pyc import opcodes
import unittest


class _TestBase(unittest.TestCase):
  """Base class for all opcodes.dis testing."""

  def dis(self, code):
    """Return the opcodes from disassbling a code sequence."""
    return opcodes.dis(compat.int_array_to_bytes(code), self.PYTHON_VERSION)

  def assertSimple(self, opcode, name):
    """Assert that a single opcode byte diassembles to the given name."""
    self.assertName([opcode], name)

  def assertName(self, code, name):
    """Assert that the first diassembled opcode has the given name."""
    self.assertEqual(self.dis(code)[0].name, name)


class CommonTest(_TestBase):
  """Test bytecodes that are common to Python 2 and 3 using python 2."""

  PYTHON_VERSION = (2, 7, 6)

  def test_pop_top(self):
    self.assertSimple(1, 'POP_TOP')

  def test_rot_two(self):
    self.assertSimple(2, 'ROT_TWO')

  def test_rot_three(self):
    self.assertSimple(3, 'ROT_THREE')

  def test_dup_top(self):
    self.assertSimple(4, 'DUP_TOP')

  def test_nop(self):
    self.assertSimple(9, 'NOP')

  def test_unary_positive(self):
    self.assertSimple(10, 'UNARY_POSITIVE')

  def test_unary_negative(self):
    self.assertSimple(11, 'UNARY_NEGATIVE')

  def test_unary_not(self):
    self.assertSimple(12, 'UNARY_NOT')

  def test_unary_invert(self):
    self.assertSimple(15, 'UNARY_INVERT')

  def test_binary_power(self):
    self.assertSimple(19, 'BINARY_POWER')

  def test_binary_multiply(self):
    self.assertSimple(20, 'BINARY_MULTIPLY')

  def test_binary_modulo(self):
    self.assertSimple(22, 'BINARY_MODULO')

  def test_binary_add(self):
    self.assertSimple(23, 'BINARY_ADD')

  def test_binary_subtract(self):
    self.assertSimple(24, 'BINARY_SUBTRACT')

  def test_binary_subscr(self):
    self.assertSimple(25, 'BINARY_SUBSCR')

  def test_binary_floor_divide(self):
    self.assertSimple(26, 'BINARY_FLOOR_DIVIDE')

  def test_binary_true_divide(self):
    self.assertSimple(27, 'BINARY_TRUE_DIVIDE')

  def test_inplace_floor_divide(self):
    self.assertSimple(28, 'INPLACE_FLOOR_DIVIDE')

  def test_inplace_true_divide(self):
    self.assertSimple(29, 'INPLACE_TRUE_DIVIDE')

  def test_store_map(self):
    self.assertSimple(54, 'STORE_MAP')

  def test_inplace_add(self):
    self.assertSimple(55, 'INPLACE_ADD')

  def test_inplace_subtract(self):
    self.assertSimple(56, 'INPLACE_SUBTRACT')

  def test_inplace_multiply(self):
    self.assertSimple(57, 'INPLACE_MULTIPLY')

  def test_inplace_modulo(self):
    self.assertSimple(59, 'INPLACE_MODULO')

  def test_store_subscr(self):
    self.assertSimple(60, 'STORE_SUBSCR')

  def test_delete_subscr(self):
    self.assertSimple(61, 'DELETE_SUBSCR')

  def test_binary_lshift(self):
    self.assertSimple(62, 'BINARY_LSHIFT')

  def test_binary_rshift(self):
    self.assertSimple(63, 'BINARY_RSHIFT')

  def test_binary_and(self):
    self.assertSimple(64, 'BINARY_AND')

  def test_binary_xor(self):
    self.assertSimple(65, 'BINARY_XOR')

  def test_binary_or(self):
    self.assertSimple(66, 'BINARY_OR')

  def test_inplace_power(self):
    self.assertSimple(67, 'INPLACE_POWER')

  def test_get_iter(self):
    self.assertSimple(68, 'GET_ITER')

  def test_print_expr(self):
    self.assertSimple(70, 'PRINT_EXPR')

  def test_inplace_lshift(self):
    self.assertSimple(75, 'INPLACE_LSHIFT')

  def test_inplace_rshift(self):
    self.assertSimple(76, 'INPLACE_RSHIFT')

  def test_inplace_and(self):
    self.assertSimple(77, 'INPLACE_AND')

  def test_inplace_xor(self):
    self.assertSimple(78, 'INPLACE_XOR')

  def test_inplace_or(self):
    self.assertSimple(79, 'INPLACE_OR')

  def test_break_loop(self):
    self.assertSimple(80, 'BREAK_LOOP')

  def test_with_cleanup(self):
    self.assertSimple(81, 'WITH_CLEANUP')

  def test_return_value(self):
    self.assertSimple(83, 'RETURN_VALUE')

  def test_import_star(self):
    self.assertSimple(84, 'IMPORT_STAR')

  def test_yield_value(self):
    self.assertSimple(86, 'YIELD_VALUE')

  def test_pop_block(self):
    self.assertSimple(87, 'POP_BLOCK')

  def test_end_finally(self):
    self.assertSimple(88, 'END_FINALLY')

  def test_store_name(self):
    self.assertName([90, 0, 0], 'STORE_NAME')

  def test_delete_name(self):
    self.assertName([91, 0, 0], 'DELETE_NAME')

  def test_unpack_sequence(self):
    self.assertName([92, 0, 0], 'UNPACK_SEQUENCE')

  def test_for_iter(self):
    self.assertName([93, 0, 0, 9], 'FOR_ITER')

  def test_store_attr(self):
    self.assertName([95, 0, 0], 'STORE_ATTR')

  def test_delete_attr(self):
    self.assertName([96, 0, 0], 'DELETE_ATTR')

  def test_store_global(self):
    self.assertName([97, 0, 0], 'STORE_GLOBAL')

  def test_delete_global(self):
    self.assertName([98, 0, 0], 'DELETE_GLOBAL')

  def test_load_const(self):
    self.assertName([100, 0, 0], 'LOAD_CONST')

  def test_load_name(self):
    self.assertName([101, 0, 0], 'LOAD_NAME')

  def test_build_tuple(self):
    self.assertName([102, 0, 0], 'BUILD_TUPLE')

  def test_build_list(self):
    self.assertName([103, 0, 0], 'BUILD_LIST')

  def test_build_set(self):
    self.assertName([104, 0, 0], 'BUILD_SET')

  def test_build_map(self):
    self.assertName([105, 0, 0], 'BUILD_MAP')

  def test_load_attr(self):
    self.assertName([106, 0, 0], 'LOAD_ATTR')

  def test_compare_op(self):
    self.assertName([107, 0, 0], 'COMPARE_OP')

  def test_import_name(self):
    self.assertName([108, 0, 0], 'IMPORT_NAME')

  def test_import_from(self):
    self.assertName([109, 0, 0], 'IMPORT_FROM')

  def test_jump_forward(self):
    self.assertName([110, 0, 0, 9], 'JUMP_FORWARD')

  def test_jump_if_false_or_pop(self):
    self.assertName([111, 3, 0, 9], 'JUMP_IF_FALSE_OR_POP')

  def test_jump_if_true_or_pop(self):
    self.assertName([112, 3, 0, 9], 'JUMP_IF_TRUE_OR_POP')

  def test_jump_absolute(self):
    self.assertName([113, 3, 0, 9], 'JUMP_ABSOLUTE')

  def test_pop_jump_if_false(self):
    self.assertName([114, 3, 0, 9], 'POP_JUMP_IF_FALSE')

  def test_pop_jump_if_true(self):
    self.assertName([115, 3, 0, 9], 'POP_JUMP_IF_TRUE')

  def test_load_global(self):
    self.assertName([116, 0, 0], 'LOAD_GLOBAL')

  def test_continue_loop(self):
    self.assertName([119, 3, 0, 9], 'CONTINUE_LOOP')

  def test_setup_loop(self):
    self.assertName([120, 0, 0, 9], 'SETUP_LOOP')

  def test_setup_except(self):
    self.assertName([121, 0, 0, 9], 'SETUP_EXCEPT')

  def test_setup_finally(self):
    self.assertName([122, 0, 0, 9], 'SETUP_FINALLY')

  def test_load_fast(self):
    self.assertName([124, 0, 0], 'LOAD_FAST')

  def test_store_fast(self):
    self.assertName([125, 0, 0], 'STORE_FAST')

  def test_delete_fast(self):
    self.assertName([126, 0, 0], 'DELETE_FAST')

  def test_raise_varargs(self):
    self.assertName([130, 0, 0], 'RAISE_VARARGS')

  def test_call_function(self):
    self.assertName([131, 0, 0], 'CALL_FUNCTION')

  def test_make_function(self):
    self.assertName([132, 0, 0], 'MAKE_FUNCTION')

  def test_build_slice(self):
    self.assertName([133, 0, 0], 'BUILD_SLICE')

  def test_make_closure(self):
    self.assertName([134, 0, 0], 'MAKE_CLOSURE')

  def test_load_closure(self):
    self.assertName([135, 0, 0], 'LOAD_CLOSURE')

  def test_load_deref(self):
    self.assertName([136, 0, 0], 'LOAD_DEREF')

  def test_store_deref(self):
    self.assertName([137, 0, 0], 'STORE_DEREF')

  def test_call_function_var(self):
    self.assertName([140, 0, 0], 'CALL_FUNCTION_VAR')

  def test_call_function_kw(self):
    self.assertName([141, 0, 0], 'CALL_FUNCTION_KW')

  def test_call_function_var_kw(self):
    self.assertName([142, 0, 0], 'CALL_FUNCTION_VAR_KW')

  def test_setup_with(self):
    self.assertName([143, 0, 0, 9], 'SETUP_WITH')

  def test_set_add(self):
    self.assertName([146, 0, 0], 'SET_ADD')

  def test_map_add(self):
    self.assertName([147, 0, 0], 'MAP_ADD')

  def test_binary(self):
    ops = self.dis([
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
    ])
    self.assertEqual(len(ops), 18)
    self.assertEqual(ops[0].name, 'LOAD_FAST')
    self.assertEqual(ops[0].arg, 0)
    self.assertEqual(ops[1].name, 'LOAD_FAST')
    self.assertEqual(ops[1].arg, 0)
    self.assertEqual(ops[2].name, 'BINARY_ADD')
    self.assertEqual(ops[3].name, 'POP_TOP')
    self.assertEqual(ops[4].name, 'LOAD_FAST')
    self.assertEqual(ops[4].arg, 0)
    self.assertEqual(ops[5].name, 'LOAD_FAST')
    self.assertEqual(ops[5].arg, 0)
    self.assertEqual(ops[6].name, 'BINARY_MULTIPLY')
    self.assertEqual(ops[7].name, 'POP_TOP')
    self.assertEqual(ops[8].name, 'LOAD_FAST')
    self.assertEqual(ops[8].arg, 0)
    self.assertEqual(ops[9].name, 'LOAD_FAST')
    self.assertEqual(ops[9].arg, 0)
    self.assertEqual(ops[10].name, 'BINARY_MODULO')
    self.assertEqual(ops[11].name, 'POP_TOP')
    self.assertEqual(ops[12].name, 'LOAD_FAST')
    self.assertEqual(ops[12].arg, 0)
    self.assertEqual(ops[13].name, 'LOAD_FAST')
    self.assertEqual(ops[13].arg, 0)
    self.assertEqual(ops[14].name, 'BINARY_TRUE_DIVIDE')
    self.assertEqual(ops[15].name, 'POP_TOP')
    self.assertEqual(ops[16].name, 'LOAD_CONST')
    self.assertEqual(ops[16].arg, 0)
    self.assertEqual(ops[17].name, 'RETURN_VALUE')

  def test_break(self):
    ops = self.dis([
        0x78, 4, 0,  # 0 SETUP_LOOP, dest=7,
        0x50,  # 3 BREAK_LOOP,
        0x71, 3, 0,  # 4 JUMP_ABSOLUTE, dest=3,
        0x64, 0, 0,  # 7 LOAD_CONST, arg=0,
        0x53,  # 10 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 5)
    self.assertEqual(ops[0].name, 'SETUP_LOOP')
    self.assertEqual(ops[0].arg, 3)
    self.assertEqual(ops[0].target, ops[3])
    self.assertEqual(ops[1].name, 'BREAK_LOOP')
    self.assertEqual(ops[2].name, 'JUMP_ABSOLUTE')
    self.assertEqual(ops[2].arg, 1)
    self.assertEqual(ops[2].target, ops[1])
    self.assertEqual(ops[3].name, 'LOAD_CONST')
    self.assertEqual(ops[3].arg, 0)
    self.assertEqual(ops[4].name, 'RETURN_VALUE')

  def test_call(self):
    ops = self.dis([
        0x74, 0, 0,  # 0 LOAD_GLOBAL, arg=0,
        0x83, 0, 0,  # 3 CALL_FUNCTION, arg=0,
        0x01,  # 6 POP_TOP,
        0x64, 0, 0,  # 7 LOAD_CONST, arg=0,
        0x53,  # 10 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 5)
    self.assertEqual(ops[0].name, 'LOAD_GLOBAL')
    self.assertEqual(ops[0].arg, 0)
    self.assertEqual(ops[1].name, 'CALL_FUNCTION')
    self.assertEqual(ops[1].arg, 0)
    self.assertEqual(ops[2].name, 'POP_TOP')
    self.assertEqual(ops[3].name, 'LOAD_CONST')
    self.assertEqual(ops[3].arg, 0)
    self.assertEqual(ops[4].name, 'RETURN_VALUE')

  def test_continue(self):
    ops = self.dis([
        0x78, 6, 0,  # 0 SETUP_LOOP, dest=9,
        0x71, 3, 0,  # 3 JUMP_ABSOLUTE, dest=3,
        0x71, 3, 0,  # 6 JUMP_ABSOLUTE, dest=3,
        0x64, 0, 0,  # 9 LOAD_CONST, arg=0,
        0x53,  # 12 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 5)
    self.assertEqual(ops[0].name, 'SETUP_LOOP')
    self.assertEqual(ops[0].arg, 3)
    self.assertEqual(ops[0].target, ops[3])
    self.assertEqual(ops[1].name, 'JUMP_ABSOLUTE')
    self.assertEqual(ops[1].arg, 1)
    self.assertEqual(ops[1].target, ops[1])
    self.assertEqual(ops[2].name, 'JUMP_ABSOLUTE')
    self.assertEqual(ops[2].arg, 1)
    self.assertEqual(ops[2].target, ops[1])
    self.assertEqual(ops[3].name, 'LOAD_CONST')
    self.assertEqual(ops[3].arg, 0)
    self.assertEqual(ops[4].name, 'RETURN_VALUE')

  def test_finally(self):
    ops = self.dis([
        0x7a, 4, 0,  # 0 SETUP_FINALLY, dest=7,
        0x57,  # 3 POP_BLOCK,
        0x64, 0, 0,  # 4 LOAD_CONST, arg=0,
        0x58,  # 7 END_FINALLY,
        0x64, 0, 0,  # 8 LOAD_CONST, arg=0,
        0x53,  # 11 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 6)
    self.assertEqual(ops[0].name, 'SETUP_FINALLY')
    self.assertEqual(ops[0].arg, 3)
    self.assertEqual(ops[0].target, ops[3])
    self.assertEqual(ops[1].name, 'POP_BLOCK')
    self.assertEqual(ops[2].name, 'LOAD_CONST')
    self.assertEqual(ops[2].arg, 0)
    self.assertEqual(ops[3].name, 'END_FINALLY')
    self.assertEqual(ops[4].name, 'LOAD_CONST')
    self.assertEqual(ops[4].arg, 0)
    self.assertEqual(ops[5].name, 'RETURN_VALUE')

  def test_inplace(self):
    ops = self.dis([
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
    ])
    self.assertEqual(len(ops), 18)
    self.assertEqual(ops[0].name, 'LOAD_FAST')
    self.assertEqual(ops[0].arg, 0)
    self.assertEqual(ops[1].name, 'LOAD_FAST')
    self.assertEqual(ops[1].arg, 0)
    self.assertEqual(ops[2].name, 'INPLACE_LSHIFT')
    self.assertEqual(ops[3].name, 'STORE_FAST')
    self.assertEqual(ops[3].arg, 0)
    self.assertEqual(ops[4].name, 'LOAD_FAST')
    self.assertEqual(ops[4].arg, 0)
    self.assertEqual(ops[5].name, 'LOAD_FAST')
    self.assertEqual(ops[5].arg, 0)
    self.assertEqual(ops[6].name, 'INPLACE_RSHIFT')
    self.assertEqual(ops[7].name, 'STORE_FAST')
    self.assertEqual(ops[7].arg, 0)
    self.assertEqual(ops[8].name, 'LOAD_FAST')
    self.assertEqual(ops[8].arg, 0)
    self.assertEqual(ops[9].name, 'LOAD_FAST')
    self.assertEqual(ops[9].arg, 0)
    self.assertEqual(ops[10].name, 'INPLACE_ADD')
    self.assertEqual(ops[11].name, 'STORE_FAST')
    self.assertEqual(ops[11].arg, 0)
    self.assertEqual(ops[12].name, 'LOAD_FAST')
    self.assertEqual(ops[12].arg, 0)
    self.assertEqual(ops[13].name, 'LOAD_FAST')
    self.assertEqual(ops[13].arg, 0)
    self.assertEqual(ops[14].name, 'INPLACE_SUBTRACT')
    self.assertEqual(ops[15].name, 'STORE_FAST')
    self.assertEqual(ops[15].arg, 0)
    self.assertEqual(ops[16].name, 'LOAD_CONST')
    self.assertEqual(ops[16].arg, 0)
    self.assertEqual(ops[17].name, 'RETURN_VALUE')

  def test_raise_one(self):
    ops = self.dis([
        0x64, 0, 0,  # 0 LOAD_CONST, arg=0,
        0x82, 1, 0,  # 3 RAISE_VARARGS, arg=1,
        0x64, 0, 0,  # 6 LOAD_CONST, arg=0,
        0x53,  # 9 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 4)
    self.assertEqual(ops[0].name, 'LOAD_CONST')
    self.assertEqual(ops[0].arg, 0)
    self.assertEqual(ops[1].name, 'RAISE_VARARGS')
    self.assertEqual(ops[1].arg, 1)
    self.assertEqual(ops[2].name, 'LOAD_CONST')
    self.assertEqual(ops[2].arg, 0)
    self.assertEqual(ops[3].name, 'RETURN_VALUE')

  def test_unary(self):
    ops = self.dis([
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
    ])
    self.assertEqual(len(ops), 11)
    self.assertEqual(ops[0].name, 'LOAD_FAST')
    self.assertEqual(ops[0].arg, 0)
    self.assertEqual(ops[1].name, 'UNARY_NEGATIVE')
    self.assertEqual(ops[2].name, 'POP_TOP')
    self.assertEqual(ops[3].name, 'LOAD_FAST')
    self.assertEqual(ops[3].arg, 0)
    self.assertEqual(ops[4].name, 'UNARY_INVERT')
    self.assertEqual(ops[5].name, 'POP_TOP')
    self.assertEqual(ops[6].name, 'LOAD_FAST')
    self.assertEqual(ops[6].arg, 0)
    self.assertEqual(ops[7].name, 'UNARY_POSITIVE')
    self.assertEqual(ops[8].name, 'POP_TOP')
    self.assertEqual(ops[9].name, 'LOAD_CONST')
    self.assertEqual(ops[9].arg, 0)
    self.assertEqual(ops[10].name, 'RETURN_VALUE')

  def test_with(self):
    ops = self.dis([
        0x64, 0, 0,  # 0 LOAD_CONST, arg=0,
        0x8f, 5, 0,  # 3 SETUP_WITH, dest=11,
        0x01,  # 6 POP_TOP,
        0x57,  # 7 POP_BLOCK,
        0x64, 0, 0,  # 8 LOAD_CONST, arg=0,
        0x51,  # 11 WITH_CLEANUP,
        0x58,  # 12 END_FINALLY,
        0x64, 0, 0,  # 13 LOAD_CONST, arg=0,
        0x53,  # 16 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 9)
    self.assertEqual(ops[0].name, 'LOAD_CONST')
    self.assertEqual(ops[0].arg, 0)
    self.assertEqual(ops[1].name, 'SETUP_WITH')
    self.assertEqual(ops[1].arg, 5)
    self.assertEqual(ops[1].target, ops[5])
    self.assertEqual(ops[2].name, 'POP_TOP')
    self.assertEqual(ops[3].name, 'POP_BLOCK')
    self.assertEqual(ops[4].name, 'LOAD_CONST')
    self.assertEqual(ops[4].arg, 0)
    self.assertEqual(ops[5].name, 'WITH_CLEANUP')
    self.assertEqual(ops[6].name, 'END_FINALLY')
    self.assertEqual(ops[7].name, 'LOAD_CONST')
    self.assertEqual(ops[7].arg, 0)
    self.assertEqual(ops[8].name, 'RETURN_VALUE')


class CommonUnder3Test(CommonTest):
  """Test the common bytecodes using Python 3.4."""

  PYTHON_VERSION = (3, 4, 0)


class Python2Test(_TestBase):
  """Test bytecodes specific to Python 2."""

  PYTHON_VERSION = (2, 7, 6)

  def test_stop_code(self):
    self.assertSimple(0, 'STOP_CODE')

  def test_rot_four(self):
    self.assertSimple(5, 'ROT_FOUR')

  def test_unary_convert(self):
    self.assertSimple(13, 'UNARY_CONVERT')

  def test_binary_divide(self):
    self.assertSimple(21, 'BINARY_DIVIDE')

  def test_slice_0(self):
    self.assertSimple(30, 'SLICE_0')

  def test_slice_1(self):
    self.assertSimple(31, 'SLICE_1')

  def test_slice_2(self):
    self.assertSimple(32, 'SLICE_2')

  def test_slice_3(self):
    self.assertSimple(33, 'SLICE_3')

  def test_store_slice_0(self):
    self.assertSimple(40, 'STORE_SLICE_0')

  def test_store_slice_1(self):
    self.assertSimple(41, 'STORE_SLICE_1')

  def test_store_slice_2(self):
    self.assertSimple(42, 'STORE_SLICE_2')

  def test_store_slice_3(self):
    self.assertSimple(43, 'STORE_SLICE_3')

  def test_delete_slice_0(self):
    self.assertSimple(50, 'DELETE_SLICE_0')

  def test_delete_slice_1(self):
    self.assertSimple(51, 'DELETE_SLICE_1')

  def test_delete_slice_2(self):
    self.assertSimple(52, 'DELETE_SLICE_2')

  def test_delete_slice_3(self):
    self.assertSimple(53, 'DELETE_SLICE_3')

  def test_inplace_divide(self):
    self.assertSimple(58, 'INPLACE_DIVIDE')

  def test_print_item(self):
    self.assertSimple(71, 'PRINT_ITEM')

  def test_print_newline(self):
    self.assertSimple(72, 'PRINT_NEWLINE')

  def test_print_item_to(self):
    self.assertSimple(73, 'PRINT_ITEM_TO')

  def test_print_newline_to(self):
    self.assertSimple(74, 'PRINT_NEWLINE_TO')

  def test_load_locals(self):
    self.assertSimple(82, 'LOAD_LOCALS')

  def test_exec_stmt(self):
    self.assertSimple(85, 'EXEC_STMT')

  def test_build_class(self):
    self.assertSimple(89, 'BUILD_CLASS')

  def test_list_append(self):
    self.assertName([94, 0, 0], 'LIST_APPEND')

  def test_dup_topx(self):
    self.assertName([99, 0, 0], 'DUP_TOPX')

  def test_except(self):
    ops = self.dis([
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
    ])
    self.assertEqual(len(ops), 10)
    self.assertEqual(ops[0].name, 'SETUP_EXCEPT')
    self.assertEqual(ops[0].arg, 3)
    self.assertEqual(ops[0].target, ops[3])
    self.assertEqual(ops[1].name, 'POP_BLOCK')
    self.assertEqual(ops[2].name, 'JUMP_FORWARD')
    self.assertEqual(ops[2].arg, 8)
    self.assertEqual(ops[2].target, ops[8])
    self.assertEqual(ops[3].name, 'POP_TOP')
    self.assertEqual(ops[4].name, 'POP_TOP')
    self.assertEqual(ops[5].name, 'POP_TOP')
    self.assertEqual(ops[6].name, 'JUMP_FORWARD')
    self.assertEqual(ops[6].arg, 8)
    self.assertEqual(ops[6].target, ops[8])
    self.assertEqual(ops[7].name, 'END_FINALLY')
    self.assertEqual(ops[8].name, 'LOAD_CONST')
    self.assertEqual(ops[8].arg, 0)
    self.assertEqual(ops[9].name, 'RETURN_VALUE')

  def test_list(self):
    ops = self.dis([
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
    ])
    self.assertEqual(len(ops), 11)
    self.assertEqual(ops[0].name, 'BUILD_LIST')
    self.assertEqual(ops[0].arg, 0)
    self.assertEqual(ops[1].name, 'LOAD_FAST')
    self.assertEqual(ops[1].arg, 0)
    self.assertEqual(ops[2].name, 'GET_ITER')
    self.assertEqual(ops[3].name, 'FOR_ITER')
    self.assertEqual(ops[3].arg, 8)
    self.assertEqual(ops[3].target, ops[8])
    self.assertEqual(ops[4].name, 'STORE_FAST')
    self.assertEqual(ops[4].arg, 1)
    self.assertEqual(ops[5].name, 'LOAD_FAST')
    self.assertEqual(ops[5].arg, 1)
    self.assertEqual(ops[6].name, 'LIST_APPEND')
    self.assertEqual(ops[6].arg, 2)
    self.assertEqual(ops[7].name, 'JUMP_ABSOLUTE')
    self.assertEqual(ops[7].arg, 3)
    self.assertEqual(ops[7].target, ops[3])
    self.assertEqual(ops[8].name, 'POP_TOP')
    self.assertEqual(ops[9].name, 'LOAD_CONST')
    self.assertEqual(ops[9].arg, 0)
    self.assertEqual(ops[10].name, 'RETURN_VALUE')

  def test_loop(self):
    ops = self.dis([
        0x78, 10, 0,  # 0 SETUP_LOOP, dest=13,
        0x74, 0, 0,  # 3 LOAD_GLOBAL, arg=0,
        0x72, 12, 0,  # 6 POP_JUMP_IF_FALSE, dest=12,
        0x71, 3, 0,  # 9 JUMP_ABSOLUTE, dest=3,
        0x57,  # 12 POP_BLOCK,
        0x64, 0, 0,  # 13 LOAD_CONST, arg=0,
        0x53,  # 16 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 7)
    self.assertEqual(ops[0].name, 'SETUP_LOOP')
    self.assertEqual(ops[0].arg, 5)
    self.assertEqual(ops[0].target, ops[5])
    self.assertEqual(ops[1].name, 'LOAD_GLOBAL')
    self.assertEqual(ops[1].arg, 0)
    self.assertEqual(ops[2].name, 'POP_JUMP_IF_FALSE')
    self.assertEqual(ops[2].arg, 4)
    self.assertEqual(ops[2].target, ops[4])
    self.assertEqual(ops[3].name, 'JUMP_ABSOLUTE')
    self.assertEqual(ops[3].arg, 1)
    self.assertEqual(ops[3].target, ops[1])
    self.assertEqual(ops[4].name, 'POP_BLOCK')
    self.assertEqual(ops[5].name, 'LOAD_CONST')
    self.assertEqual(ops[5].arg, 0)
    self.assertEqual(ops[6].name, 'RETURN_VALUE')

  def test_extended_arg(self):
    ops = self.dis([
        0x91, 1, 0,  # 0 EXTENDED_ARG, arg=1,
        0x64, 2, 0,  # 3 LOAD_CONST, arg=2
        0x53,  # 6 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 2)
    self.assertEqual(ops[0].name, 'LOAD_CONST')
    self.assertEqual(ops[0].arg, 0x10002)
    self.assertEqual(ops[1].name, 'RETURN_VALUE')


class Python34Test(_TestBase):
  """Test bytecodes specific to Python 3.4."""

  PYTHON_VERSION = (3, 4, 0)

  def test_dup_top_two(self):
    self.assertSimple(5, 'DUP_TOP_TWO')

  def test_load_build_class(self):
    self.assertSimple(71, 'LOAD_BUILD_CLASS')

  def test_yield_from(self):
    self.assertSimple(72, 'YIELD_FROM')

  def test_pop_except(self):
    self.assertSimple(89, 'POP_EXCEPT')

  def test_unpack_ex(self):
    self.assertName([94, 0, 0], 'UNPACK_EX')

  def test_delete_deref(self):
    self.assertName([138, 0, 0], 'DELETE_DEREF')

  def test_list_append(self):
    self.assertName([145, 0, 0], 'LIST_APPEND')

  def test_load_classderef(self):
    self.assertName([148, 0, 0], 'LOAD_CLASSDEREF')

  def test_except(self):
    ops = self.dis([
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
    ])
    self.assertEqual(len(ops), 11)
    self.assertEqual(ops[0].name, 'SETUP_EXCEPT')
    self.assertEqual(ops[0].arg, 3)
    self.assertEqual(ops[0].target, ops[3])
    self.assertEqual(ops[1].name, 'POP_BLOCK')
    self.assertEqual(ops[2].name, 'JUMP_FORWARD')
    self.assertEqual(ops[2].arg, 9)
    self.assertEqual(ops[2].target, ops[9])
    self.assertEqual(ops[3].name, 'POP_TOP')
    self.assertEqual(ops[4].name, 'POP_TOP')
    self.assertEqual(ops[5].name, 'POP_TOP')
    self.assertEqual(ops[6].name, 'POP_EXCEPT')
    self.assertEqual(ops[7].name, 'JUMP_FORWARD')
    self.assertEqual(ops[7].arg, 9)
    self.assertEqual(ops[7].target, ops[9])
    self.assertEqual(ops[8].name, 'END_FINALLY')
    self.assertEqual(ops[9].name, 'LOAD_CONST')
    self.assertEqual(ops[9].arg, 0)
    self.assertEqual(ops[10].name, 'RETURN_VALUE')

  def test_list(self):
    ops = self.dis([
        0x64, 1, 0,  # 0 LOAD_CONST, arg=1,
        0x64, 2, 0,  # 3 LOAD_CONST, arg=2,
        0x84, 0, 0,  # 6 MAKE_FUNCTION, arg=0,
        0x7c, 0, 0,  # 9 LOAD_FAST, arg=0,
        0x44,  # 12 GET_ITER,
        0x83, 1, 0,  # 13 CALL_FUNCTION, arg=1,
        0x01,  # 16 POP_TOP,
        0x64, 0, 0,  # 17 LOAD_CONST, arg=0,
        0x53,  # 20 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 9)
    self.assertEqual(ops[0].name, 'LOAD_CONST')
    self.assertEqual(ops[0].arg, 1)
    self.assertEqual(ops[1].name, 'LOAD_CONST')
    self.assertEqual(ops[1].arg, 2)
    self.assertEqual(ops[2].name, 'MAKE_FUNCTION')
    self.assertEqual(ops[2].arg, 0)
    self.assertEqual(ops[3].name, 'LOAD_FAST')
    self.assertEqual(ops[3].arg, 0)
    self.assertEqual(ops[4].name, 'GET_ITER')
    self.assertEqual(ops[5].name, 'CALL_FUNCTION')
    self.assertEqual(ops[5].arg, 1)
    self.assertEqual(ops[6].name, 'POP_TOP')
    self.assertEqual(ops[7].name, 'LOAD_CONST')
    self.assertEqual(ops[7].arg, 0)
    self.assertEqual(ops[8].name, 'RETURN_VALUE')

  def test_loop(self):
    ops = self.dis([
        0x78, 3, 0,  # 0 SETUP_LOOP, dest=6,
        0x71, 3, 0,  # 3 JUMP_ABSOLUTE, dest=3,
        0x64, 0, 0,  # 6 LOAD_CONST, arg=0,
        0x53,  # 9 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 4)
    self.assertEqual(ops[0].name, 'SETUP_LOOP')
    self.assertEqual(ops[0].arg, 2)
    self.assertEqual(ops[0].target, ops[2])
    self.assertEqual(ops[1].name, 'JUMP_ABSOLUTE')
    self.assertEqual(ops[1].arg, 1)
    self.assertEqual(ops[1].target, ops[1])
    self.assertEqual(ops[2].name, 'LOAD_CONST')
    self.assertEqual(ops[2].arg, 0)
    self.assertEqual(ops[3].name, 'RETURN_VALUE')

  def test_raise_zero(self):
    ops = self.dis([
        0x82, 0, 0,  # 0 RAISE_VARARGS, arg=0,
        0x64, 0, 0,  # 3 LOAD_CONST, arg=0,
        0x53,  # 6 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 3)
    self.assertEqual(ops[0].name, 'RAISE_VARARGS')
    self.assertEqual(ops[0].arg, 0)
    self.assertEqual(ops[1].name, 'LOAD_CONST')
    self.assertEqual(ops[1].arg, 0)
    self.assertEqual(ops[2].name, 'RETURN_VALUE')

  def test_raise_two(self):
    ops = self.dis([
        0x74, 0, 0,  # 0 LOAD_GLOBAL, arg=0,
        0x74, 1, 0,  # 3 LOAD_GLOBAL, arg=1,
        0x82, 2, 0,  # 6 RAISE_VARARGS, arg=2,
        0x64, 0, 0,  # 9 LOAD_CONST, arg=0,
        0x53,  # 12 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 5)
    self.assertEqual(ops[0].name, 'LOAD_GLOBAL')
    self.assertEqual(ops[0].arg, 0)
    self.assertEqual(ops[1].name, 'LOAD_GLOBAL')
    self.assertEqual(ops[1].arg, 1)
    self.assertEqual(ops[2].name, 'RAISE_VARARGS')
    self.assertEqual(ops[2].arg, 2)
    self.assertEqual(ops[3].name, 'LOAD_CONST')
    self.assertEqual(ops[3].arg, 0)
    self.assertEqual(ops[4].name, 'RETURN_VALUE')

  def test_raise_three(self):
    ops = self.dis([
        0x74, 0, 0,  # 0 LOAD_GLOBAL, arg=0,
        0x74, 1, 0,  # 3 LOAD_GLOBAL, arg=1,
        0x64, 1, 0,  # 6 LOAD_CONST, arg=1,
        0x82, 3, 0,  # 9 RAISE_VARARGS, arg=3,
        0x64, 0, 0,  # 12 LOAD_CONST, arg=0,
        0x53,  # 15 RETURN_VALUE
    ])
    self.assertEqual(len(ops), 6)
    self.assertEqual(ops[0].name, 'LOAD_GLOBAL')
    self.assertEqual(ops[0].arg, 0)
    self.assertEqual(ops[1].name, 'LOAD_GLOBAL')
    self.assertEqual(ops[1].arg, 1)
    self.assertEqual(ops[2].name, 'LOAD_CONST')
    self.assertEqual(ops[2].arg, 1)
    self.assertEqual(ops[3].name, 'RAISE_VARARGS')
    self.assertEqual(ops[3].arg, 3)
    self.assertEqual(ops[4].name, 'LOAD_CONST')
    self.assertEqual(ops[4].arg, 0)
    self.assertEqual(ops[5].name, 'RETURN_VALUE')

  def test_extended_arg(self):
    # LOAD_CONST should be stored in the jump table with an address of 0, due to
    # the extended arg; if we don't do this we would throw an exception.
    ops = self.dis([
        0x90, 1, 0,  # 0 EXTENDED_ARG, arg=1,
        0x64, 2, 0,  # 3 LOAD_CONST, arg=2
        0x71, 0, 0  # 6 JUMP_ABSOLUTE, arg=0
    ])
    self.assertEqual(len(ops), 2)
    self.assertEqual(ops[0].name, 'LOAD_CONST')
    self.assertEqual(ops[0].arg, 0x10002)
    self.assertEqual(ops[1].name, 'JUMP_ABSOLUTE')


class Python35Test(_TestBase):
  """Test bytecodes specific to Python 3.5."""

  PYTHON_VERSION = (3, 5, 2)

  def test_binary_matrix_multiply(self):
    self.assertSimple(16, 'BINARY_MATRIX_MULTIPLY')

  def test_inplace_matrix_multiply(self):
    self.assertSimple(17, 'INPLACE_MATRIX_MULTIPLY')

  def test_get_yield_from_iter(self):
    self.assertSimple(69, 'GET_YIELD_FROM_ITER')

  def test_with_cleanup_start(self):
    self.assertSimple(81, 'WITH_CLEANUP_START')

  def test_with_cleanup_finish(self):
    self.assertSimple(82, 'WITH_CLEANUP_FINISH')

  def test_build_list_unpack(self):
    self.assertName([149, 0, 0], 'BUILD_LIST_UNPACK')

  def test_build_map_unpack(self):
    self.assertName([150, 0, 0], 'BUILD_MAP_UNPACK')

  def test_build_map_unpack_with_call(self):
    self.assertName([151, 0, 0], 'BUILD_MAP_UNPACK_WITH_CALL')

  def test_build_tuple_unpack(self):
    self.assertName([152, 0, 0], 'BUILD_TUPLE_UNPACK')

  def test_build_set_unpack(self):
    self.assertName([153, 0, 0], 'BUILD_SET_UNPACK')


class Python36Test(_TestBase):
  """Test bytecodes specific to Python 3.6."""

  PYTHON_VERSION = (3, 6, 0)

  def test_setup_annotations(self):
    self.assertSimple(85, 'SETUP_ANNOTATIONS')

  def test_store_annotation(self):
    self.assertName([127, 0], 'STORE_ANNOTATION')

  def test_call_function_ex(self):
    self.assertName([142, 0], 'CALL_FUNCTION_EX')

  def test_format_value(self):
    self.assertName([155, 0], 'FORMAT_VALUE')

  def test_build_const_key_map(self):
    self.assertName([156, 0], 'BUILD_CONST_KEY_MAP')

  def test_build_string(self):
    self.assertName([157, 0], 'BUILD_STRING')

  def test_build_tuple_unpack_with_call(self):
    self.assertName([158, 0], 'BUILD_TUPLE_UNPACK_WITH_CALL')

  def test_extended_arg(self):
    """Same as the previous extended arg test, but using the wordcode format."""
    # LOAD_CONST should be stored in the jump table with an address of 0, due to
    # the extended arg; if we don't do this we would throw an exception.
    ops = self.dis([
        0x90, 1,  # 0 EXTENDED_ARG, arg=1,
        0x64, 2,  # 3 LOAD_CONST, arg=2
        0x71, 0,  # 6 JUMP_ABSOLUTE, arg=0
    ])
    self.assertEqual(len(ops), 2)
    self.assertEqual(ops[0].name, 'LOAD_CONST')
    self.assertEqual(ops[0].arg, 0x102)
    self.assertEqual(ops[1].name, 'JUMP_ABSOLUTE')

if __name__ == '__main__':
  unittest.main()
