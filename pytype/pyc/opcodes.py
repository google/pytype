"""Opcode definitions."""

from typing import Dict, List, Optional

import attrs

from pycnite import bytecode


# We define all-uppercase classes, to match their opcode names:
# pylint: disable=invalid-name

HAS_CONST = 1  # references the constant table
HAS_NAME = 2  # references the name table
HAS_JREL = 4  # relative jump
HAS_JABS = 8  # absolute jump
HAS_JUNKNOWN = 16  # jumps to unknown location
HAS_LOCAL = 32  # references the varnames table
HAS_FREE = 64  # references "free variable" cells
HAS_NARGS = 128  # stores number of args + kwargs
HAS_ARGUMENT = 256  # all opcodes >= 90
NO_NEXT = 512  # doesn't execute the following opcode
STORE_JUMP = 1024  # only stores a jump, doesn't actually execute it
PUSHES_BLOCK = 2048  # starts a block (while, try, finally, with, etc.)
POPS_BLOCK = 4096  # ends a block


@attrs.define(slots=True)
class OpcodeMetadata:
  """Contextual metadata attached to opcodes."""

  # Function signature annotations in textual form
  signature_annotations: Optional[Dict[str, str]] = None
  # Code run out of line-number order, due to compiler optimisations.
  is_out_of_order: bool = False


class Opcode:
  """An opcode without arguments."""

  __slots__ = ("line", "index", "prev", "next", "target", "block_target",
               "code", "annotation", "folded", "metadata")
  _FLAGS = 0

  def __init__(self, index, line):
    self.index = index
    self.line = line
    self.target = None
    self.code = None  # If we have a CodeType or OrderedCode parent
    self.annotation = None
    self.folded = None  # elided by constant folding
    self.metadata = OpcodeMetadata()  # Filled in by the director

  def at_line(self, line):
    """Return a new opcode similar to this one but with a different line."""
    # Ignore the optional slots (prev, next, block_target).
    op = Opcode(self.index, line)
    op.target = self.target
    op.code = self.code
    return op

  def basic_str(self):
    """Helper function for the various __str__ formats."""
    folded = "<<<<" if self.folded else ""
    return "%d: %d: %s %s" % (
        self.line, self.index, self.__class__.__name__, folded)

  def __str__(self):
    if self.annotation:
      return f"{self.basic_str()}  # type: {self.annotation}"
    else:
      return self.basic_str()

  def __repr__(self):
    return self.__class__.__name__

  @property
  def name(self):
    return self.__class__.__name__

  @classmethod
  def has_const(cls):
    return bool(cls._FLAGS & HAS_CONST)

  @classmethod
  def has_name(cls):
    return bool(cls._FLAGS & HAS_NAME)

  @classmethod
  def has_jrel(cls):
    return bool(cls._FLAGS & HAS_JREL)

  @classmethod
  def has_jabs(cls):
    return bool(cls._FLAGS & HAS_JABS)

  @classmethod
  def has_known_jump(cls):
    return bool(cls._FLAGS & (HAS_JREL | HAS_JABS))

  @classmethod
  def has_junknown(cls):
    return bool(cls._FLAGS & HAS_JUNKNOWN)

  @classmethod
  def has_jump(cls):
    return bool(cls._FLAGS & (HAS_JREL | HAS_JABS | HAS_JUNKNOWN))

  @classmethod
  def has_local(cls):
    return bool(cls._FLAGS & HAS_LOCAL)

  @classmethod
  def has_free(cls):
    return bool(cls._FLAGS & HAS_FREE)

  @classmethod
  def has_nargs(cls):
    return bool(cls._FLAGS & HAS_NARGS)

  @classmethod
  def has_argument(cls):
    return bool(cls._FLAGS & HAS_ARGUMENT)

  @classmethod
  def no_next(cls):
    return bool(cls._FLAGS & NO_NEXT)

  @classmethod
  def carry_on_to_next(cls):
    return not cls._FLAGS & NO_NEXT

  @classmethod
  def store_jump(cls):
    return bool(cls._FLAGS & STORE_JUMP)

  @classmethod
  def does_jump(cls):
    return cls.has_jump() and not cls.store_jump()

  @classmethod
  def pushes_block(cls):
    return bool(cls._FLAGS & PUSHES_BLOCK)

  @classmethod
  def pops_block(cls):
    return bool(cls._FLAGS & POPS_BLOCK)


class OpcodeWithArg(Opcode):
  """An opcode with one argument.

  Attributes:
    arg: The integer opcode argument read in from the bytecode
    argval: A decoded version of arg, performing the same steps the cpython
      interpreter does to convert arg into a python value.
  """

  __slots__ = ("arg", "argval")

  def __init__(self, index, line, arg, argval):
    super().__init__(index, line)
    self.arg = arg
    self.argval = argval

  def __str__(self):
    out = f"{self.basic_str()} {self.argval}"
    if self.annotation:
      return f"{out}  # type: {self.annotation}"
    else:
      return out


class LOAD_FOLDED_CONST(OpcodeWithArg):  # A fake opcode used internally
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()

  def __str__(self):
    return self.basic_str() + " " + str(self.arg.value)


class POP_TOP(Opcode):
  __slots__ = ()


class ROT_TWO(Opcode):
  __slots__ = ()


class ROT_THREE(Opcode):
  __slots__ = ()


class DUP_TOP(Opcode):
  __slots__ = ()


class ROT_FOUR(Opcode):
  __slots__ = ()


class DUP_TOP_TWO(Opcode):
  __slots__ = ()


class NOP(Opcode):
  __slots__ = ()


class UNARY_POSITIVE(Opcode):
  __slots__ = ()


class UNARY_NEGATIVE(Opcode):
  __slots__ = ()


class UNARY_NOT(Opcode):
  __slots__ = ()


class UNARY_INVERT(Opcode):
  __slots__ = ()


class BINARY_MATRIX_MULTIPLY(Opcode):
  __slots__ = ()


class INPLACE_MATRIX_MULTIPLY(Opcode):
  __slots__ = ()


class BINARY_POWER(Opcode):
  __slots__ = ()


class BINARY_MULTIPLY(Opcode):
  __slots__ = ()


class BINARY_MODULO(Opcode):
  __slots__ = ()


class BINARY_ADD(Opcode):
  __slots__ = ()


class BINARY_SUBTRACT(Opcode):
  __slots__ = ()


class BINARY_SUBSCR(Opcode):
  __slots__ = ()


class BINARY_FLOOR_DIVIDE(Opcode):
  __slots__ = ()


class BINARY_TRUE_DIVIDE(Opcode):
  __slots__ = ()


class INPLACE_FLOOR_DIVIDE(Opcode):
  __slots__ = ()


class INPLACE_TRUE_DIVIDE(Opcode):
  __slots__ = ()


class GET_AITER(Opcode):
  __slots__ = ()


class GET_ANEXT(Opcode):
  __slots__ = ()


class BEFORE_ASYNC_WITH(Opcode):
  __slots__ = ()


class BEGIN_FINALLY(Opcode):
  __slots__ = ()


class END_ASYNC_FOR(Opcode):
  # Even though dis documentation says that END_ASYNC_FOR may reraise an
  # exception, we do not include NO_NEXT in the flags because doing so would
  # cause the return statement for an async method to be skipped, leading to
  # an incorrect return type.
  # See tests/test_stdlib2:StdlibTestsFeatures.test_async_iter and
  # tests/test_coroutine:GeneratorFeatureTest.test_async_for_pyi for tests
  # that fail if we add NO_NEXT.
  _FLAGS = HAS_JUNKNOWN
  __slots__ = ()


class INPLACE_ADD(Opcode):
  __slots__ = ()


class INPLACE_SUBTRACT(Opcode):
  __slots__ = ()


class INPLACE_MULTIPLY(Opcode):
  __slots__ = ()


class INPLACE_MODULO(Opcode):
  __slots__ = ()


class STORE_SUBSCR(Opcode):
  __slots__ = ()


class DELETE_SUBSCR(Opcode):
  __slots__ = ()


class BINARY_LSHIFT(Opcode):
  __slots__ = ()


class BINARY_RSHIFT(Opcode):
  __slots__ = ()


class BINARY_AND(Opcode):
  __slots__ = ()


class BINARY_XOR(Opcode):
  __slots__ = ()


class BINARY_OR(Opcode):
  __slots__ = ()


class INPLACE_POWER(Opcode):
  __slots__ = ()


class GET_ITER(Opcode):
  __slots__ = ()


class GET_YIELD_FROM_ITER(Opcode):
  __slots__ = ()


class PRINT_EXPR(Opcode):
  __slots__ = ()


class LOAD_BUILD_CLASS(Opcode):
  __slots__ = ()


class YIELD_FROM(Opcode):
  _FLAGS = HAS_JUNKNOWN
  __slots__ = ()


# TODO(b/265374890): GET_AWAITABLE gains an argument in Python 3.11, but
# unconditionally adding the argument causes tests in earlier versions to fail.
class GET_AWAITABLE(Opcode):
  __slots__ = ()


class INPLACE_LSHIFT(Opcode):
  __slots__ = ()


class INPLACE_RSHIFT(Opcode):
  __slots__ = ()


class INPLACE_AND(Opcode):
  __slots__ = ()


class INPLACE_XOR(Opcode):
  __slots__ = ()


class INPLACE_OR(Opcode):
  __slots__ = ()


class BREAK_LOOP(Opcode):
  _FLAGS = HAS_JUNKNOWN | NO_NEXT
  __slots__ = ()


class WITH_CLEANUP_START(Opcode):
  _FLAGS = HAS_JUNKNOWN  # might call __exit__
  __slots__ = ()


class WITH_CLEANUP_FINISH(Opcode):
  __slots__ = ()


class RETURN_VALUE(Opcode):
  _FLAGS = HAS_JUNKNOWN | NO_NEXT
  __slots__ = ()


class IMPORT_STAR(Opcode):
  __slots__ = ()


class SETUP_ANNOTATIONS(Opcode):
  __slots__ = ()


class YIELD_VALUE(Opcode):
  _FLAGS = HAS_JUNKNOWN
  __slots__ = ()


class POP_BLOCK(Opcode):
  _FLAGS = POPS_BLOCK
  __slots__ = ()


class END_FINALLY(Opcode):
  _FLAGS = HAS_JUNKNOWN  # might re-raise an exception
  __slots__ = ()


class POP_EXCEPT(Opcode):
  __slots__ = ()


class STORE_NAME(OpcodeWithArg):  # Indexes into name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class DELETE_NAME(OpcodeWithArg):  # Indexes into name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class UNPACK_SEQUENCE(OpcodeWithArg):  # Arg: Number of tuple items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class FOR_ITER(OpcodeWithArg):
  _FLAGS = HAS_JREL|HAS_ARGUMENT
  __slots__ = ()


class LIST_APPEND(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class UNPACK_EX(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class STORE_ATTR(OpcodeWithArg):  # Indexes into name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class DELETE_ATTR(OpcodeWithArg):  # Indexes into name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class STORE_GLOBAL(OpcodeWithArg):  # Indexes into name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class DELETE_GLOBAL(OpcodeWithArg):  # Indexes into name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class LOAD_CONST(OpcodeWithArg):  # Arg: Index in const list
  _FLAGS = HAS_ARGUMENT|HAS_CONST
  __slots__ = ()


class LOAD_NAME(OpcodeWithArg):  # Arg: Index in name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class BUILD_TUPLE(OpcodeWithArg):  # Arg: Number of tuple items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BUILD_LIST(OpcodeWithArg):  # Arg: Number of list items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BUILD_SET(OpcodeWithArg):  # Arg: Number of set items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BUILD_MAP(OpcodeWithArg):  # Arg: Number of dict entries (up to 255)
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class LOAD_ATTR(OpcodeWithArg):  # Arg: Index in name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class COMPARE_OP(OpcodeWithArg):  # Arg: Comparison operator
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class IMPORT_NAME(OpcodeWithArg):  # Arg: Index in name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT|HAS_JUNKNOWN
  __slots__ = ()


class IMPORT_FROM(OpcodeWithArg):  # Arg: Index in name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class JUMP_FORWARD(OpcodeWithArg):
  _FLAGS = HAS_JREL|HAS_ARGUMENT|NO_NEXT
  __slots__ = ()


class JUMP_IF_FALSE_OR_POP(OpcodeWithArg):
  _FLAGS = HAS_JABS|HAS_ARGUMENT
  __slots__ = ()


class JUMP_IF_TRUE_OR_POP(OpcodeWithArg):
  _FLAGS = HAS_JABS|HAS_ARGUMENT
  __slots__ = ()


class JUMP_ABSOLUTE(OpcodeWithArg):
  _FLAGS = HAS_JABS|HAS_ARGUMENT|NO_NEXT
  __slots__ = ()


class POP_JUMP_IF_FALSE(OpcodeWithArg):
  _FLAGS = HAS_JABS|HAS_ARGUMENT
  __slots__ = ()


class POP_JUMP_IF_TRUE(OpcodeWithArg):
  _FLAGS = HAS_JABS|HAS_ARGUMENT
  __slots__ = ()


class LOAD_GLOBAL(OpcodeWithArg):  # Indexes into name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class CONTINUE_LOOP(OpcodeWithArg):  # Acts as jump
  _FLAGS = HAS_JABS|HAS_ARGUMENT|NO_NEXT
  __slots__ = ()


class SETUP_LOOP(OpcodeWithArg):
  _FLAGS = HAS_JREL|HAS_ARGUMENT|STORE_JUMP|PUSHES_BLOCK
  __slots__ = ()


class SETUP_EXCEPT(OpcodeWithArg):
  _FLAGS = HAS_JREL|HAS_ARGUMENT|STORE_JUMP|PUSHES_BLOCK
  __slots__ = ()


class SETUP_FINALLY(OpcodeWithArg):
  _FLAGS = HAS_JREL|HAS_ARGUMENT|STORE_JUMP|PUSHES_BLOCK
  __slots__ = ()


class LOAD_FAST(OpcodeWithArg):  # Loads local variable number
  _FLAGS = HAS_LOCAL|HAS_ARGUMENT
  __slots__ = ()


class STORE_FAST(OpcodeWithArg):  # Stores local variable number
  _FLAGS = HAS_LOCAL|HAS_ARGUMENT
  __slots__ = ()


class DELETE_FAST(OpcodeWithArg):  # Deletes local variable number
  _FLAGS = HAS_LOCAL|HAS_ARGUMENT
  __slots__ = ()


class STORE_ANNOTATION(OpcodeWithArg):
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class RAISE_VARARGS(OpcodeWithArg):  # Arg: Number of raise args (1, 2, or 3)
  _FLAGS = HAS_ARGUMENT|HAS_JUNKNOWN|NO_NEXT
  __slots__ = ()


class CALL_FUNCTION(OpcodeWithArg):  # Arg: #args + (#kwargs << 8)
  _FLAGS = HAS_NARGS|HAS_ARGUMENT|HAS_JUNKNOWN
  __slots__ = ()


class MAKE_FUNCTION(OpcodeWithArg):  # Arg: Number of args with default values
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BUILD_SLICE(OpcodeWithArg):  # Arg: Number of items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class MAKE_CLOSURE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class LOAD_CLOSURE(OpcodeWithArg):
  _FLAGS = HAS_FREE|HAS_ARGUMENT
  __slots__ = ()


class LOAD_DEREF(OpcodeWithArg):
  _FLAGS = HAS_FREE|HAS_ARGUMENT
  __slots__ = ()


class STORE_DEREF(OpcodeWithArg):
  _FLAGS = HAS_FREE|HAS_ARGUMENT
  __slots__ = ()


class DELETE_DEREF(OpcodeWithArg):
  _FLAGS = HAS_FREE|HAS_ARGUMENT
  __slots__ = ()


class CALL_FUNCTION_VAR(OpcodeWithArg):  # Arg: #args + (#kwargs << 8)
  _FLAGS = HAS_NARGS|HAS_ARGUMENT|HAS_JUNKNOWN
  __slots__ = ()


class CALL_FUNCTION_KW(OpcodeWithArg):  # Arg: #args + (#kwargs << 8)
  _FLAGS = HAS_NARGS|HAS_ARGUMENT|HAS_JUNKNOWN
  __slots__ = ()


class CALL_FUNCTION_VAR_KW(OpcodeWithArg):  # Arg: #args + (#kwargs << 8)
  _FLAGS = HAS_NARGS|HAS_ARGUMENT|HAS_JUNKNOWN
  __slots__ = ()


class CALL_FUNCTION_EX(OpcodeWithArg):  # Arg: flags
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class SETUP_WITH(OpcodeWithArg):
  _FLAGS = HAS_JREL|HAS_ARGUMENT|STORE_JUMP|PUSHES_BLOCK
  __slots__ = ()


class EXTENDED_ARG(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class SET_ADD(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class MAP_ADD(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class LOAD_CLASSDEREF(OpcodeWithArg):
  _FLAGS = HAS_FREE|HAS_ARGUMENT
  __slots__ = ()


class BUILD_LIST_UNPACK(OpcodeWithArg):  # Arg: Number of items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BUILD_MAP_UNPACK(OpcodeWithArg):  # Arg: Number of items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BUILD_MAP_UNPACK_WITH_CALL(OpcodeWithArg):  # Arg: Number of items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BUILD_TUPLE_UNPACK(OpcodeWithArg):  # Arg: Number of items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BUILD_SET_UNPACK(OpcodeWithArg):  # Arg: Number of items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class SETUP_ASYNC_WITH(OpcodeWithArg):
  _FLAGS = HAS_JREL|HAS_ARGUMENT|STORE_JUMP|PUSHES_BLOCK
  __slots__ = ()


class FORMAT_VALUE(OpcodeWithArg):  # Arg: Flags
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BUILD_CONST_KEY_MAP(OpcodeWithArg):  # Arg: Number of items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BUILD_STRING(OpcodeWithArg):  # Arg: Number of items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BUILD_TUPLE_UNPACK_WITH_CALL(OpcodeWithArg):  # Arg: Number of items
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class LOAD_METHOD(OpcodeWithArg):  # Arg: Index in name list
  _FLAGS = HAS_NAME|HAS_ARGUMENT
  __slots__ = ()


class CALL_METHOD(OpcodeWithArg):  # Arg: #args
  _FLAGS = HAS_NARGS|HAS_ARGUMENT|HAS_JUNKNOWN
  __slots__ = ()


class CALL_FINALLY(OpcodeWithArg):  # Arg: Jump offset to finally block
  _FLAGS = HAS_JREL | HAS_ARGUMENT
  __slots__ = ()


class POP_FINALLY(OpcodeWithArg):
  # might re-raise an exception or jump to a finally
  _FLAGS = HAS_ARGUMENT | HAS_JUNKNOWN
  __slots__ = ()


class WITH_EXCEPT_START(Opcode):
  __slots__ = ()


class LOAD_ASSERTION_ERROR(Opcode):
  __slots__ = ()


class LIST_TO_TUPLE(Opcode):
  __slots__ = ()


class IS_OP(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class CONTAINS_OP(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class JUMP_IF_NOT_EXC_MATCH(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JABS
  __slots__ = ()


class LIST_EXTEND(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class SET_UPDATE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class DICT_MERGE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class DICT_UPDATE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class GET_LEN(Opcode):
  __slots__ = ()


class MATCH_MAPPING(Opcode):
  __slots__ = ()


class MATCH_SEQUENCE(Opcode):
  __slots__ = ()


class MATCH_KEYS(Opcode):
  __slots__ = ()


class COPY_DICT_WITHOUT_KEYS(Opcode):
  __slots__ = ()


class ROT_N(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class RERAISE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | NO_NEXT
  __slots__ = ()


class GEN_START(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class MATCH_CLASS(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class CACHE(Opcode):
  __slots__ = ()


class PUSH_NULL(Opcode):
  __slots__ = ()


class PUSH_EXC_INFO(Opcode):
  __slots__ = ()


class CHECK_EXC_MATCH(Opcode):
  __slots__ = ()


class CHECK_EG_MATCH(Opcode):
  __slots__ = ()


class BEFORE_WITH(Opcode):
  __slots__ = ()


class RETURN_GENERATOR(Opcode):
  __slots__ = ()


class ASYNC_GEN_WRAP(Opcode):
  __slots__ = ()


class PREP_RERAISE_STAR(Opcode):
  __slots__ = ()


class SWAP(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class POP_JUMP_FORWARD_IF_FALSE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JREL
  __slots__ = ()


class POP_JUMP_FORWARD_IF_TRUE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JREL
  __slots__ = ()


class COPY(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class BINARY_OP(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class SEND(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JREL
  __slots__ = ()


class POP_JUMP_FORWARD_IF_NOT_NONE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JREL
  __slots__ = ()


class POP_JUMP_FORWARD_IF_NONE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JREL
  __slots__ = ()


class JUMP_BACKWARD_NO_INTERRUPT(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JREL | NO_NEXT
  __slots__ = ()


class MAKE_CELL(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_FREE
  __slots__ = ()


class JUMP_BACKWARD(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JREL | NO_NEXT
  __slots__ = ()


class COPY_FREE_VARS(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class RESUME(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class PRECALL(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class CALL(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT
  __slots__ = ()


class KW_NAMES(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_CONST
  __slots__ = ()


class POP_JUMP_BACKWARD_IF_NOT_NONE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JREL
  __slots__ = ()


class POP_JUMP_BACKWARD_IF_NONE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JREL
  __slots__ = ()


class POP_JUMP_BACKWARD_IF_FALSE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JREL
  __slots__ = ()


class POP_JUMP_BACKWARD_IF_TRUE(OpcodeWithArg):
  _FLAGS = HAS_ARGUMENT | HAS_JREL
  __slots__ = ()


def dis(code) -> List[Opcode]:
  """Disassemble a string into a list of Opcode instances."""
  ret = []
  offset_to_index = {}
  g = globals()
  for index, op in enumerate(bytecode.dis(code)):
    cls = g[op.name]
    offset_to_index[op.offset] = index
    if cls.has_argument():
      ret.append(cls(index, op.line, op.arg, op.argval))
    else:
      ret.append(cls(index, op.line))
  # Map the target of jump instructions to the opcode they jump to, and fill
  # in "next" and "prev" pointers
  for i, op in enumerate(ret):
    if op.has_known_jump():
      # op.argval is the postprocessed version of op.arg
      op.arg = op.argval = offset_to_index[op.argval]
      op.target = ret[op.arg]
    get_code = lambda j: ret[j] if 0 <= j < len(ret) else None
    op.prev = get_code(i - 1)
    op.next = get_code(i + 1)
  return ret
