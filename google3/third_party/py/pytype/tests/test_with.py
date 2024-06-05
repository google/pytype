"""Test the with statement."""

from pytype.tests import test_base


class TestWithStatement(test_base.BaseTest):
  """Tests for the with statement."""

  def test_simple_context_manager(self):
    self.Check("""
      class NullContext:
        def __enter__(self):
          l.append('i')
          # __enter__ usually returns self, but doesn't have to.
          return 17

        def __exit__(self, exc_type, exc_val, exc_tb):
          l.append('o')
          return False

      l = []
      for i in range(3):
        with NullContext() as val:
          assert val == 17
          l.append('w')
        l.append('e')
      l.append('r')
      s = ''.join(l)
      print("Look: %r" % s)
      assert s == "iwoeiwoeiwoer"
      """)

  def test_raise_in_context_manager(self):
    self.Check("""
      class NullContext:
        def __enter__(self):
          l.append('i')
          return self

        def __exit__(self, exc_type, exc_val, exc_tb):
          assert exc_type is ValueError, \\
            "Expected ValueError: %r" % exc_type
          l.append('o')
          return False

      l = []
      try:
        with NullContext():
          l.append('w')
          raise ValueError("Boo!")
        l.append('e')
      except ValueError:
        l.append('x')
      l.append('r')
      s = ''.join(l)
      print("Look: %r" % s)
      assert s == "iwoxr"
      """)

  def test_suppressed_raise_in_context_manager(self):
    self.Check("""
      class SuppressingContext:
        def __enter__(self):
          l.append('i')
          return self

        def __exit__(self, exc_type, exc_val, exc_tb):
          assert exc_type is ValueError, \\
            "Expected ValueError: %r" % exc_type
          l.append('o')
          return True

      l = []
      try:
        with SuppressingContext():
          l.append('w')
          raise ValueError("Boo!")
        l.append('e')
      except ValueError:
        l.append('x')
      l.append('r')
      s = ''.join(l)
      print("Look: %r" % s)
      assert s == "iwoer"
      """)

  def test_return_in_with(self):
    self.Check("""
      class NullContext:
        def __enter__(self):
          l.append('i')
          return self

        def __exit__(self, exc_type, exc_val, exc_tb):
          l.append('o')
          return False

      l = []
      def use_with(val):
        with NullContext():
          l.append('w')
          return val
        l.append('e')

      assert use_with(23) == 23
      l.append('r')
      s = ''.join(l)
      print("Look: %r" % s)
      assert s == "iwor"
      """)

  def test_continue_in_with(self):
    self.Check("""
      class NullContext:
        def __enter__(self):
          l.append('i')
          return self

        def __exit__(self, exc_type, exc_val, exc_tb):
          l.append('o')
          return False

      l = []
      for i in range(3):
        with NullContext():
          l.append('w')
          if i % 2:
             continue
          l.append('z')
        l.append('e')

      l.append('r')
      s = ''.join(l)
      print("Look: %r" % s)
      assert s == "iwzoeiwoiwzoer"
      """)

  def test_break_in_with(self):
    self.Check("""
      class NullContext:
        def __enter__(self):
          l.append('i')
          return self

        def __exit__(self, exc_type, exc_val, exc_tb):
          l.append('o')
          return False

      l = []
      for i in range(3):
        with NullContext():
          l.append('w')
          if i % 2:
             break
          l.append('z')
        l.append('e')

      l.append('r')
      s = ''.join(l)
      print("Look: %r" % s)
      assert s == "iwzoeiwor"
      """)

  def test_raise_in_with(self):
    self.Check("""
      class NullContext:
        def __enter__(self):
          l.append('i')
          return self

        def __exit__(self, exc_type, exc_val, exc_tb):
          l.append('o')
          return False

      l = []
      try:
        with NullContext():
          l.append('w')
          raise ValueError("oops")
          l.append('z')
        l.append('e')
      except ValueError as e:
        assert str(e) == "oops"
        l.append('x')
      l.append('r')
      s = ''.join(l)
      print("Look: %r" % s)
      assert s == "iwoxr", "What!?"
      """)

  def test_at_context_manager_simplified(self):
    self.Check("""
      import sys
      class GeneratorContextManager:
        def __init__(self, gen):
          self.gen = gen

        def __enter__(self):
          try:
            return next(self.gen)
          except StopIteration:
            raise RuntimeError("generator didn't yield")

        def __exit__(self, type, value, traceback):
          if type is None:
            try:
              next(self.gen)
            except StopIteration:
              return
            else:
              raise RuntimeError("generator didn't stop")
          else:
            if value is None:
              value = type()  # pytype: disable=not-callable # (needs if-split)
            try:
              self.gen.throw(type, value, traceback)
              raise RuntimeError(
                "generator didn't stop after throw()"
              )
            except StopIteration as exc:
              return exc is not value
            except:
              if sys.exc_info()[1] is not value:
                raise

      def contextmanager(func):
        def helper(*args, **kwds):
          return GeneratorContextManager(func(*args, **kwds))
        return helper

      @contextmanager
      def my_context_manager(val):
        yield val

      with my_context_manager(17) as x:
        assert x == 17
      """)

  def test_at_context_manager_complete(self):
    # The complete code for an @contextmanager example, lifted from
    # the stdlib.
    self.Check("""
      from functools import partial
      import sys

      WRAPPER_ASSIGNMENTS = ('__module__', '__name__', '__doc__')
      WRAPPER_UPDATES = ('__dict__',)

      def update_wrapper(wrapper,
              wrapped,
              assigned = WRAPPER_ASSIGNMENTS,
              updated = WRAPPER_UPDATES):
        for attr in assigned:
          setattr(wrapper, attr, getattr(wrapped, attr))
        for attr in updated:
          getattr(wrapper, attr).update(getattr(wrapped, attr, {}))
        # Return the wrapper so this can be used as a decorator
        # via partial().
        return wrapper

      def wraps(wrapped,
          assigned = WRAPPER_ASSIGNMENTS,
          updated = WRAPPER_UPDATES):
        return partial(update_wrapper, wrapped=wrapped,
              assigned=assigned, updated=updated)

      class GeneratorContextManager:
        def __init__(self, gen):
          self.gen = gen

        def __enter__(self):
          try:
            return next(self.gen)
          except StopIteration:
            raise RuntimeError("generator didn't yield")

        def __exit__(self, type, value, traceback):
          if type is None:
            try:
              next(self.gen)
            except StopIteration:
              return
            else:
              raise RuntimeError("generator didn't stop")
          else:
            if value is None:
              value = type()
            try:
              self.gen.throw(type, value, traceback)
              raise RuntimeError(
                "generator didn't stop after throw()"
              )
            except StopIteration as exc:
              return exc is not value
            except:
              if sys.exc_info()[1] is not value:
                raise

      def contextmanager(func):
        @wraps(func)
        def helper(*args, **kwds):
          return GeneratorContextManager(func(*args, **kwds))
        return helper

      @contextmanager
      def my_context_manager(val):
        yield val

      with my_context_manager(17) as x:
        assert x == 17
      """)

  def test_tempfile(self):
    self.Infer("""
      import tempfile
      def f():
        with tempfile.NamedTemporaryFile(dir="bla", delete=False) as fi:
          pass
      """)


if __name__ == "__main__":
  test_base.main()
