"""Test functools overlay."""

from pytype.tests import test_base


class TestCachedProperty(test_base.BaseTest):
  """Tests for @cached.property."""

  def test_basic(self):
    self.Check("""
      import functools

      class A:
        @functools.cached_property
        def f(self):
          return 42

      a = A()

      x = a.f
      assert_type(x, int)

      a.f = 43
      x = a.f
      assert_type(x, int)

      del a.f
      x = a.f
      assert_type(x, int)
    """)

  def test_reingest(self):
    with self.DepTree([
        ("foo.py", """
            import functools

            class A:
              @functools.cached_property
              def f(self):
                return 42
         """)
    ]):
      self.Check("""
        import foo

        a = foo.A()

        x = a.f
        assert_type(x, int)

        a.f = 43
        x = a.f
        assert_type(x, int)

        del a.f
        x = a.f
        assert_type(x, int)
      """)

  @test_base.skip("Not supported yet")
  def test_pyi(self):
    with self.DepTree([
        ("foo.pyi", """
            import functools

            class A:
              @functools.cached_property
              def f(self) -> int: ...
         """)
    ]):
      self.Check("""
        import foo

        a = A()

        x = a.f
        assert_type(x, int)

        a.f = 43
        x = a.f
        assert_type(x, int)

        del a.f
        x = a.f
        assert_type(x, int)
      """)

  def test_infer(self):
    ty = self.Infer("""
      from functools import cached_property
    """)
    self.assertTypesMatchPytd(ty, """
      import functools
      cached_property: type[functools.cached_property]
    """)


if __name__ == "__main__":
  test_base.main()
