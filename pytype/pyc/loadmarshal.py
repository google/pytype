"""Parser for the "marshal" file format.

This file is adapted from pypy/lib_pypy/_marshal.py.

This module contains functions that can read and write Python values in a binary
format. The format is specific to Python, but independent of machine
architecture issues (e.g., you can write a Python value to a file on a PC,
           transport the file to a Sun, and read it back there).
Details of the format may change between Python versions.
"""

import struct
import sys
from typing import List, Sequence, Tuple, Union

from pytype import utils


TYPE_NULL = 0x30  # '0'
TYPE_NONE = 0x4e  # 'N'
TYPE_FALSE = 0x46  # 'F'
TYPE_TRUE = 0x54  # 'T'
TYPE_STOPITER = 0x53  # 'S'
TYPE_ELLIPSIS = 0x2e  # '.'
TYPE_INT = 0x69  # 'i'
TYPE_INT64 = 0x49  # 'I'
TYPE_FLOAT = 0x66  # 'f'
TYPE_BINARY_FLOAT = 0x67  # 'g'
TYPE_COMPLEX = 0x78  # 'x'
TYPE_BINARY_COMPLEX = 0x79  # 'y'
TYPE_LONG = 0x6c  # 'l'
TYPE_STRING = 0x73  # 's'
TYPE_INTERNED = 0x74  # 't'
TYPE_STRINGREF = 0x52  # 'R'
TYPE_TUPLE = 0x28  # '('
TYPE_LIST = 0x5b  # '['
TYPE_DICT = 0x7b  # '{'
TYPE_CODE = 0x63  # 'c'
TYPE_UNICODE = 0x75  # 'u'
TYPE_UNKNOWN = 0x3f  # '?', CPython uses this for error reporting
TYPE_SET = 0x3c  # '<'
TYPE_FROZENSET = 0x3e  # '>'
TYPE_REF = 0x72  # 'r'
TYPE_ASCII = 0x61  # 'a'
TYPE_ASCII_INTERNED = 0x41  # 'A'
TYPE_SMALL_TUPLE = 0x29  # ')'
TYPE_SHORT_ASCII = 0x7a  # 'z'
TYPE_SHORT_ASCII_INTERNED = 0x5a  # 'Z'

# Masks and values used by FORMAT_VALUE opcode.
FVC_MASK = 0x3
FVC_NONE = 0x0
FVC_STR = 0x1
FVC_REPR = 0x2
FVC_ASCII = 0x3
FVS_MASK = 0x4
FVS_HAVE_SPEC = 0x4

# Flag used by CALL_FUNCTION_EX
CALL_FUNCTION_EX_HAS_KWARGS = 0x1

# Flags used by MAKE_FUNCTION
MAKE_FUNCTION_HAS_POS_DEFAULTS = 0x1
MAKE_FUNCTION_HAS_KW_DEFAULTS = 0x2
MAKE_FUNCTION_HAS_ANNOTATIONS = 0x4
MAKE_FUNCTION_HAS_FREE_VARS = 0x8

# Or-ing this flag to one of the codes above will cause the decoded value to
# be stored in a reference table for later lookup. This feature was added in
# Python 3.4.
REF = 0x80


class _NULL:
  """Used internally, e.g. as a sentinel in dictionary entry lists."""


class CodeType:
  """Version-agnostic types.CodeType."""

  # for co_flags:
  CO_OPTIMIZED = 0x0001
  CO_NEWLOCALS = 0x0002
  CO_VARARGS = 0x0004
  CO_VARKEYWORDS = 0x0008
  CO_NESTED = 0x0010
  CO_GENERATOR = 0x0020
  CO_NOFREE = 0x0040
  CO_COROUTINE = 0x0080
  CO_ITERABLE_COROUTINE = 0x0100
  CO_ASYNC_GENERATOR = 0x0200
  CO_FUTURE_DIVISION = 0x2000
  CO_FUTURE_ABSOLUTE_IMPORT = 0x4000
  CO_FUTURE_WITH_STATEMENT = 0x8000
  CO_FUTURE_PRINT_FUNCTION = 0x10000
  CO_FUTURE_UNICODE_LITERALS = 0x20000

  def __init__(self, argcount: int, posonlyargcount: int, kwonlyargcount: int,
               nlocals: int, stacksize: int, flags: int, code: bytes,
               consts: List[object], names: List[str], varnames: List[str],
               filename: Union[bytes, str], name: str, firstlineno: int,
               lnotab: Sequence[int], freevars: List[str], cellvars: List[str],
               python_version: Tuple[int, int]):
    self.co_argcount = argcount
    self.co_posonlyargcount = posonlyargcount
    self.co_kwonlyargcount = kwonlyargcount
    self.co_nlocals = nlocals
    self.co_stacksize = stacksize
    self.co_flags = flags
    self.co_code = code
    self.co_consts = consts
    self.co_names = names
    self.co_varnames = varnames
    self.co_filename = filename
    self.co_name = name
    self.co_firstlineno = firstlineno
    self.co_lnotab = lnotab
    self.co_freevars = freevars
    self.co_cellvars = cellvars
    self.python_version = python_version  # This field is not in types.CodeType.

  def __repr__(self):
    return f'<code: {self.co_name}>'


class _LoadMarshal:
  """Stateful loader for marshalled files."""

  def __init__(self, data, python_version):
    self.bufstr = data
    self.bufpos = 0
    self.python_version = python_version
    self.refs = []
    self._stringtable = []

  def eof(self):
    """Return True if we reached the end of the stream."""
    return self.bufpos == len(self.bufstr)

  def load(self):
    """Load an encoded Python data structure."""
    c = ord('?')  # make pylint happy
    try:
      c = self._read_byte()
      if c & REF:
        # This element might recursively contain other elements, which
        # themselves store things in the refs table. So we need to determine the
        # index position *before* reading the contents of this element.
        idx = self._reserve_ref()
        result = _LoadMarshal.dispatch[c & ~REF](self)
        self.refs[idx] = result
      else:
        result = _LoadMarshal.dispatch[c](self)
      return result
    except KeyError as e:
      raise ValueError(f'bad marshal code: {chr(c)!r} ({c:02x})') from e
    except IndexError as e:
      raise EOFError() from e

  def _read(self, n):
    """Read n bytes as a string."""
    pos = self.bufpos
    self.bufpos += n
    if self.bufpos > len(self.bufstr):
      raise EOFError()
    return self.bufstr[pos : self.bufpos]

  def _read_byte(self):
    """Read an unsigned byte."""
    pos = self.bufpos
    self.bufpos += 1
    return self.bufstr[pos]

  def _read_short(self):
    """Read a signed 16 bit word."""
    lo = self._read_byte()
    hi = self._read_byte()
    x = lo | (hi<<8)
    if x & 0x8000:
      # sign extension
      x -= 0x10000
    return x

  def _read_long(self):
    """Read a signed 32 bit word."""
    s = self._read(4)
    b = lambda i: s[i]
    x = b(0) | b(1)<<8 | b(2)<<16 | b(3)<<24
    if b(3) & 0x80 and x > 0:
      # sign extension
      x = -((1<<32) - x)
      return int(x)
    else:
      return x

  def _read_long64(self):
    """Read a signed 64 bit integer."""
    s = self._read(8)
    b = lambda i: s[i]
    x = (b(0) | b(1)<<8 | b(2)<<16 | b(3)<<24 |
         b(4)<<32 | b(5)<<40 | b(6)<<48 | b(7)<<56)
    if b(7) & 0x80 and x > 0:
      # sign extension
      x = -((1<<64) - x)
    return x

  def _reserve_ref(self):
    """Reserve one entry in the reference table.

    This is done before reading an element, because reading an element and
    all its subelements might change the size of the reference table.

    Returns:
      Reserved index position in the reference table.
    """
    # See r_ref_reserve in Python-3.4/Python/marshal.c
    idx = len(self.refs)
    self.refs.append(None)
    return idx

  # pylint: disable=missing-docstring
  # This is a bunch of small methods with self-explanatory names.

  def load_null(self):
    return _NULL

  def load_none(self):
    return None

  def load_true(self):
    return True

  def load_false(self):
    return False

  def load_stopiter(self):
    return StopIteration

  def load_ellipsis(self):
    return Ellipsis

  def load_int(self):
    return self._read_long()

  def load_int64(self):
    return self._read_long64()

  def load_long(self):
    """Load a variable length integer."""
    size = self._read_long()
    x = 0
    for i in range(abs(size)):
      d = self._read_short()
      x |= d<<(i*15)
    return x if size >= 0 else -x

  def load_float(self):
    n = self._read_byte()
    s = self._read(n)
    return float(s)

  def load_binary_float(self):
    binary = self._read(8)
    return struct.unpack('<d', binary)[0]

  def load_complex(self):
    n = self._read_byte()
    s = self._read(n)
    real = float(s)
    n = self._read_byte()
    s = self._read(n)
    imag = float(s)
    return complex(real, imag)

  def load_binary_complex(self):
    binary = self._read(16)
    return complex(*struct.unpack('dd', binary))

  def load_string(self):
    n = self._read_long()
    s = bytes(self._read(n))
    return s

  def load_interned(self):
    n = self._read_long()
    s = self._read(n)
    ret = sys.intern(utils.native_str(s))
    self._stringtable.append(ret)
    return ret

  def load_stringref(self):
    n = self._read_long()
    return self._stringtable[n]

  def load_unicode(self):
    n = self._read_long()
    s = self._read(n)
    # We need to convert bytes to a unicode string.
    # We use the 'backslashreplace' error mode in order to handle non-utf8
    # backslash-escaped string literals correctly.
    s = s.decode('utf8', 'backslashreplace')
    return s

  def load_ascii(self):
    n = self._read_long()
    return utils.native_str(self._read(n))

  def load_short_ascii(self):
    n = self._read_byte()
    return utils.native_str(self._read(n))

  def load_tuple(self):
    return tuple(self.load_list())

  def load_small_tuple(self):
    n = self._read_byte()
    l = []
    for _ in range(n):
      l.append(self.load())
    return tuple(l)

  def load_list(self):
    n = self._read_long()
    l = []
    for _ in range(n):
      l.append(self.load())
    return l

  def load_dict(self):
    d = {}
    while True:
      key = self.load()
      if key is _NULL:
        break
      value = self.load()
      d[key] = value
    return d

  def load_code(self):
    """Load a Python code object."""
    argcount = self._read_long()
    # Python 3.8+ has positional only arguments.
    if self.python_version >= (3, 8):
      posonlyargcount = self._read_long()
    else:
      posonlyargcount = -1
    if self.python_version[0] >= 3:
      kwonlyargcount = self._read_long()
    else:
      kwonlyargcount = -1
    nlocals = self._read_long()
    stacksize = self._read_long()
    flags = self._read_long()
    # The code field is a 'string of raw compiled bytecode'
    # (https://docs.python.org/3/library/inspect.html#types-and-members).
    code = self.load()
    consts = self.load()
    names = self.load()
    varnames = self.load()
    freevars = self.load()
    cellvars = self.load()
    filename = self.load()
    name = self.load()
    firstlineno = self._read_long()
    # lnotab, from
    # https://github.com/python/cpython/blob/master/Objects/lnotab_notes.txt:
    # 'an array of unsigned bytes disguised as a Python bytes object'.
    lnotab = self.load()
    return CodeType(argcount, posonlyargcount, kwonlyargcount, nlocals,
                    stacksize, flags, code, consts, names, varnames, filename,
                    name, firstlineno, lnotab, freevars, cellvars,
                    self.python_version)

  def load_set(self):
    n = self._read_long()
    args = [self.load() for _ in range(n)]
    return set(args)

  def load_frozenset(self):
    n = self._read_long()
    args = [self.load() for _ in range(n)]
    return frozenset(args)

  def load_ref(self):
    n = self._read_long()
    return self.refs[n]

  # pylint: enable=missing-docstring

  dispatch = {
      TYPE_ASCII: load_ascii,
      TYPE_ASCII_INTERNED: load_ascii,
      TYPE_BINARY_COMPLEX: load_binary_complex,
      TYPE_BINARY_FLOAT: load_binary_float,
      TYPE_CODE: load_code,
      TYPE_COMPLEX: load_complex,
      TYPE_DICT: load_dict,
      TYPE_ELLIPSIS: load_ellipsis,
      TYPE_FALSE: load_false,
      TYPE_FLOAT: load_float,
      TYPE_FROZENSET: load_frozenset,
      TYPE_INT64: load_int64,
      TYPE_INT: load_int,
      TYPE_INTERNED: load_interned,
      TYPE_LIST: load_list,
      TYPE_LONG: load_long,
      TYPE_NONE: load_none,
      TYPE_NULL: load_null,
      TYPE_REF: load_ref,
      TYPE_SET: load_set,
      TYPE_SHORT_ASCII: load_short_ascii,
      TYPE_SHORT_ASCII_INTERNED: load_short_ascii,
      TYPE_SMALL_TUPLE: load_small_tuple,
      TYPE_STOPITER: load_stopiter,
      TYPE_STRING: load_string,
      TYPE_STRINGREF: load_stringref,
      TYPE_TRUE: load_true,
      TYPE_TUPLE: load_tuple,
      TYPE_UNICODE: load_unicode,
  }


def loads(s, python_version):
  um = _LoadMarshal(s, python_version)
  result = um.load()
  if not um.eof():
    raise BufferError('trailing bytes in marshal data')
  return result
