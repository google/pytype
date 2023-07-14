"""Tests for loadmarshal.py."""

from pytype.pyc import loadmarshal
import unittest


class TestLoadMarshal(unittest.TestCase):
  """Tests for loadmarshal.loads."""

  def assertStrictEqual(self, s1, s2):
    self.assertEqual(s1, s2)
    self.assertEqual(type(s1), type(s2))

  def load(self, s, python_version=None):
    python_version = python_version or (3, 9)
    return loadmarshal.loads(s, python_version)

  def test_load_none(self):
    self.assertIsNone(self.load(b'N'))

  def test_load_false(self):
    self.assertEqual(self.load(b'F'), False)

  def test_load_true(self):
    self.assertEqual(self.load(b'T'), True)

  def test_load_stopiter(self):
    self.assertEqual(self.load(b'S'), StopIteration)

  def test_load_ellipsis(self):
    self.assertEqual(self.load(b'.'), Ellipsis)

  def test_load_int(self):
    self.assertEqual(self.load(b'i\1\2\3\4'), 0x04030201)
    self.assertEqual(self.load(b'i\xff\xff\xff\xff'), -1)

  def test_load_int64(self):
    self.assertEqual(self.load(b'I\1\2\3\4\5\6\7\x08'),
                     0x0807060504030201)
    self.assertEqual(self.load(b'I\xff\xff\xff\xff\xff\xff\xff\xff'), -1)

  def test_load_float(self):
    self.assertEqual(self.load(b'f\x040.25'), 0.25)

  def test_load_long_float(self):
    self.assertEqual(self.load(b'f\xff0.'+(b'9'*253)), 1.0)

  def test_load_binary_float(self):
    self.assertEqual(self.load(b'g\0\0\0\0\0\0\xd0\x3f'), 0.25)

  def test_load_complex(self):
    self.assertEqual(self.load(b'x\3.25\3.25'), 0.25+0.25j)

  def test_load_binary_complex(self):
    c = self.load(b'y\0\0\0\0\0\0\xf0\x3f\0\0\0\0\0\0\xf0\x3f')
    self.assertEqual(c, 1+1j)

  def test_load_long(self):
    """Load a variable length integer."""
    self.assertEqual(self.load(b'l\3\0\0\0\1\0\2\0\3\0'), 1+2*2**15+3*2**30)
    self.assertEqual(self.load(b'l\xff\xff\xff\xff\1\0'), -1)
    self.assertEqual(self.load(b'l\xfe\xff\xff\xff\1\0\2\0'), -65537)

  def test_load_string(self):
    self.assertStrictEqual(self.load(b's\4\0\0\0test', (3, 9)), bytes(b'test'))

  def test_load_interned(self):
    self.assertStrictEqual(self.load(b't\4\0\0\0test'), 'test')

  def test_load_stringref(self):
    st = (b'(\4\0\0\0'  # tuple of 4
          b't\4\0\0\0abcd'  # store "abcd" at 0
          b't\4\0\0\0efgh'  # store "efgh" at 1
          b'R\0\0\0\0'  # retrieve stringref 0
          b'R\1\0\0\0')  # retrieve stringref 1
    self.assertEqual(self.load(st), ('abcd', 'efgh', 'abcd', 'efgh'))

  def test_load_tuple(self):
    self.assertEqual(self.load(b'(\2\0\0\0TF'), (True, False))

  def test_load_list(self):
    self.assertEqual(self.load(b'[\2\0\0\0TF'), [True, False])

  def test_load_dict(self):
    self.assertEqual(self.load(b'{TFFN0'), {True: False, False: None})

  def test_load_code(self):
    """Load a Python code object."""
    co = (b'c'  # code
          b'\1\0\0\0'  # args: 1
          b'\2\0\0\0'  # kw args: 2
          b'\3\0\0\0'  # locals: 3
          b'\4\0\0\0'  # stacksize: 4
          b'\5\0\0\0'  # flags: 5
          b's\1\0\0\0\0'  # code '\0'
          b')\0'  # consts: ()
          b')\0'  # names: ()
          b')\0'  # varnames: ()
          b')\0'  # freevars: ()
          b')\0'  # cellvars: ()
          b'z\7test.py'  # filename: 'test.py'
          b'z\4test'  # name: 'test.py'
          b'\6\0\0\0'  # first line no: 6
          b'N')  # lnotab: None
    code = self.load(co, python_version=(3, 5))
    self.assertEqual(code.co_argcount, 1)
    self.assertEqual(code.co_kwonlyargcount, 2)
    self.assertEqual(code.co_nlocals, 3)
    self.assertEqual(code.co_stacksize, 4)
    self.assertEqual(code.co_flags, 5)
    self.assertEqual(code.co_code, b'\0')
    self.assertEqual(code.co_consts, ())
    self.assertEqual(code.co_names, ())
    self.assertEqual(code.co_varnames, ())
    self.assertEqual(code.co_freevars, ())
    self.assertEqual(code.co_cellvars, ())
    self.assertEqual(code.co_filename, 'test.py')
    self.assertEqual(code.co_firstlineno, 6)
    self.assertIsNone(code.co_lnotab)

  def test_load_unicode(self):
    self.assertStrictEqual(self.load(b'u\4\0\0\0test', (3, 9)), 'test')
    # This character is \u00e4 (umlaut a).
    s = b'u\2\0\0\0\xc3\xa4'
    self.assertStrictEqual(self.load(s, (3, 9)), '\xe4')

  def test_load_set(self):
    self.assertEqual(self.load(b'<\3\0\0\0FTN'), {True, False, None})

  def test_load_frozenset(self):
    self.assertEqual(self.load(b'>\3\0\0\0FTN'),
                     frozenset([True, False, None]))

  def test_load_ref(self):
    data = (b'(\4\0\0\0'  # tuple of 4
            b'\xe9\0\1\2\3'  # store 0x03020100 at 0
            b'\xe9\4\5\6\7'  # store 0x07060504 at 1
            b'r\0\0\0\0'  # retrieve 0
            b'r\1\0\0\0')  # retrieve 1
    self.assertEqual(self.load(data),
                     (0x03020100, 0x7060504, 0x03020100, 0x7060504))

  def test_load_ascii(self):
    self.assertStrictEqual(self.load(b'a\4\0\0\0test'), 'test')

  def test_load_ascii_interned(self):
    self.assertStrictEqual(self.load(b'A\4\0\0\0test'), 'test')

  def test_load_small_tuple(self):
    self.assertEqual(self.load(b')\2TF'), (True, False))

  def test_load_short_ascii(self):
    self.assertStrictEqual(self.load(b'z\4test'), 'test')

  def test_load_short_ascii_interned(self):
    self.assertStrictEqual(self.load(b'Z\4test'), 'test')

  def test_truncated(self):
    self.assertRaises(EOFError, lambda: self.load(b'f\x020'))

  def test_trailing(self):
    self.assertRaises(BufferError, lambda: self.load(b'N\0'))

  def test_illegal(self):
    self.assertRaises(ValueError, lambda: self.load(b'\7'))

  def test_truncated_byte(self):
    self.assertRaises(EOFError, lambda: self.load(b'f'))

  def test_load_code_311(self):
    # Code from marshal.dumps of the following in a 3.11.4 interpreter:
    #   def f():
    #     x = 10
    #     def g():
    #       return x
    #     return g
    s = (b'\xe3\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00'
         b'\x00\x03\x00\x00\x00\xf3\x16\x00\x00\x00\x87\x01\x97\x00d\x01\x8a'
         b'\x01\x88\x01f\x01d\x02\x84\x08}\x00|\x00S\x00)\x03N\xe9\n\x00\x00'
         b'\x00c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00'
         b'\x00\x13\x00\x00\x00\xf3\x08\x00\x00\x00\x95\x01\x97\x00\x89\x00'
         b'S\x00)\x01N\xa9\x00)\x01\xda\x01xs\x01\x00\x00\x00\x80\xfa\x1e'
         b'<ipython-input-1-229f6fd9be57>\xda\x01gz\x0cf.<locals>.g\x03\x00'
         b'\x00\x00s\x08\x00\x00\x00\xf8\x80\x00\xd8\x0f\x10\x88\x08\xf3\x00'
         b'\x00\x00\x00r\x04\x00\x00\x00)\x02r\x07\x00\x00\x00r\x05\x00\x00'
         b'\x00s\x02\x00\x00\x00 @r\x06\x00\x00\x00\xda\x01fr\t\x00\x00\x00'
         b'\x01\x00\x00\x00s&\x00\x00\x00\xf8\x80\x00\xd8\x08\n\x80A\xf0\x02'
         b'\x01\x05\x11\xf0\x00\x01\x05\x11\xf0\x00\x01\x05\x11\xf0\x00\x01'
         b'\x05\x11\xf0\x00\x01\x05\x11\xe0\x0b\x0c\x80Hr\x08\x00\x00\x00')
    code = loadmarshal.loads(s, (3, 11))
    self.assertEqual(code.co_argcount, 0)
    self.assertEqual(code.co_kwonlyargcount, 0)
    self.assertEqual(code.co_nlocals, 1)
    self.assertEqual(code.co_stacksize, 2)
    self.assertEqual(code.co_flags, 3)
    self.assertEqual(code.co_names, ())
    self.assertEqual(code.co_varnames, ('g',))
    self.assertEqual(code.co_freevars, ())
    self.assertEqual(code.co_cellvars, ('x',))
    self.assertEqual(code.co_firstlineno, 1)
    self.assertEqual(code.co_consts[:-1], [None, 10])
    g = code.co_consts[-1]
    self.assertIsInstance(g, loadmarshal.CodeType)
    self.assertEqual(g.co_name, 'g')
    self.assertEqual(g.co_freevars, ('x',))


if __name__ == '__main__':
  unittest.main()
