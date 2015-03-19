"""Tests for loadmarshal.py."""


from pytype.pyc import loadmarshal
import unittest


class TestLoadMarshal(unittest.TestCase):
  """Tests for loadmarshal.loads."""

  def load(self, s, python_version=(2, 7)):
    return loadmarshal.loads(s, python_version)

  def test_load_none(self):
    self.assertEquals(self.load('N'), None)

  def test_load_false(self):
    self.assertEquals(self.load('F'), False)

  def test_load_true(self):
    self.assertEquals(self.load('T'), True)

  def test_load_stopiter(self):
    self.assertEquals(self.load('S'), StopIteration)

  def test_load_ellipsis(self):
    self.assertEquals(self.load('.'), Ellipsis)

  def test_load_int(self):
    self.assertEquals(self.load('i\1\2\3\4'), 0x04030201)
    self.assertEquals(self.load('i\xff\xff\xff\xff'), -1)

  def test_load_int64(self):
    self.assertEquals(self.load('I\1\2\3\4\5\6\7\x08'),
                      0x0807060504030201)
    self.assertEquals(self.load('I\xff\xff\xff\xff\xff\xff\xff\xff'), -1)

  def test_load_float(self):
    self.assertEquals(self.load('f\x040.25'), 0.25)

  def test_load_long_float(self):
    self.assertEquals(self.load('f\xff0.'+('9'*253)), 1.0)

  def test_load_binary_float(self):
    self.assertEquals(self.load('g\0\0\0\0\0\0\xd0\x3f'), 0.25)

  def test_load_complex(self):
    self.assertEquals(self.load('x\3.25\3.25'), 0.25+0.25j)

  def test_load_binary_complex(self):
    c = self.load('y\0\0\0\0\0\0\xf0\x3f\0\0\0\0\0\0\xf0\x3f')
    self.assertEquals(c, 1+1j)

  def test_load_long(self):
    """Load a variable length integer."""
    self.assertEquals(self.load('l\3\0\0\0\1\0\2\0\3\0'), 1+2*2**15+3*2**30)
    self.assertEquals(self.load('l\xff\xff\xff\xff\1\0'), -1)
    self.assertEquals(self.load('l\xfe\xff\xff\xff\1\0\2\0'), -65537)

  def test_load_string(self):
    self.assertEquals(self.load(b's\4\0\0\0test'), 'test')

  def test_load_interned(self):
    self.assertEquals(self.load(b't\4\0\0\0test'), 'test')

  def test_load_stringref(self):
    st = ('(\4\0\0\0'  # tuple of 4
          't\4\0\0\0abcd'  # store "abcd" at 0
          't\4\0\0\0efgh'  # store "efgh" at 1
          'R\0\0\0\0'  # retrieve stringref 0
          'R\1\0\0\0')  # retrieve stringref 1
    self.assertEquals(self.load(st), ('abcd', 'efgh', 'abcd', 'efgh'))

  def test_load_tuple(self):
    self.assertEquals(self.load(b'(\2\0\0\0TF'), (True, False))

  def test_load_list(self):
    self.assertEquals(self.load(b'[\2\0\0\0TF'), [True, False])

  def test_load_dict(self):
    self.assertEquals(self.load(b'{TFFN0'), {True: False, False: None})

  def test_load_code(self):
    """Load a Python code object."""
    co = ('c'  # code
          '\1\0\0\0'  # args: 1
          '\2\0\0\0'  # kw args: 2
          '\3\0\0\0'  # locals: 3
          '\4\0\0\0'  # stacksize: 4
          '\5\0\0\0'  # flags: 5
          's\1\0\0\0\0'  # code '\0'
          ')\0'  # consts: ()
          ')\0'  # names: ()
          ')\0'  # varnames: ()
          ')\0'  # freevars: ()
          ')\0'  # cellvars: ()
          'z\7test.py'  # filename: 'test.py'
          'z\4test'  # name: 'test.py'
          '\6\0\0\0'  # first line no: 6
          'N')  # lnotab: None
    code = self.load(co, python_version=(3, 4))
    self.assertEquals(code.co_argcount, 1)
    self.assertEquals(code.co_kwonlyargcount, 2)
    self.assertEquals(code.co_nlocals, 3)
    self.assertEquals(code.co_stacksize, 4)
    self.assertEquals(code.co_flags, 5)
    self.assertEquals(code.co_code, '\0')
    self.assertEquals(code.co_consts, ())
    self.assertEquals(code.co_names, ())
    self.assertEquals(code.co_varnames, ())
    self.assertEquals(code.co_freevars, ())
    self.assertEquals(code.co_cellvars, ())
    self.assertEquals(code.co_filename, 'test.py')
    self.assertEquals(code.co_firstlineno, 6)
    self.assertEquals(code.co_lnotab, None)

  def test_load_unicode(self):
    self.assertEquals(self.load(b'u\4\0\0\0test'), u'test')

  def test_load_unknown(self):
    self.assertEquals(self.load(b't\4\0\0\0test'), u'test')

  def test_load_set(self):
    self.assertEquals(self.load(b'<\3\0\0\0FTN'), {True, False, None})

  def test_load_frozenset(self):
    self.assertEquals(self.load(b'>\3\0\0\0FTN'),
                      frozenset([True, False, None]))

  def test_load_ref(self):
    data = ('(\4\0\0\0'  # tuple of 4
            '\xe9\0\1\2\3'  # store 0x03020100 at 0
            '\xe9\4\5\6\7'  # store 0x07060504 at 1
            'r\0\0\0\0'  # retrieve 0
            'r\1\0\0\0')  # retrieve 1
    self.assertEquals(self.load(data),
                      (0x03020100, 0x7060504, 0x03020100, 0x7060504))

  def test_load_ascii(self):
    self.assertEquals(self.load(b'a\4\0\0\0test'), 'test')

  def test_load_ascii_interned(self):
    self.assertEquals(self.load(b'A\4\0\0\0test'), 'test')

  def test_load_small_tuple(self):
    self.assertEquals(self.load(b')\2TF'), (True, False))

  def test_load_short_ascii(self):
    self.assertEquals(self.load(b'z\4test'), 'test')

  def test_load_short_ascii_interned(self):
    self.assertEquals(self.load(b'Z\4test'), 'test')

  def test_truncated(self):
    self.assertRaises(EOFError, lambda: self.load('f\x020'))

  def test_trailing(self):
    self.assertRaises(BufferError, lambda: self.load('N\0'))

  def test_illegal(self):
    self.assertRaises(ValueError, lambda: self.load('\7'))

  def test_truncated_byte(self):
    self.assertRaises(EOFError, lambda: self.load('f'))

if __name__ == '__main__':
  unittest.main()
