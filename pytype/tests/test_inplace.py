"""Test operators (basic tests)."""

from pytype.tests import test_inference


class InplaceTest(test_inference.InferenceTest):
  """Base class for inplace operator tests."""

  def _check_inplace(self, op, assignments, expected_return):
    assignments = "; ".join(assignments)
    src = """
      def f(x, y):
        {assignments}
        x {op}= y
        return x
      a = f(1, 2)
    """.format(assignments=assignments, op=op)
    ty = self.Infer(src, deep=False, solve_unknowns=False)
    self.assertTypeEquals(ty.Lookup("a").type, expected_return)

  def test_iadd(self):
    self._check_inplace("+", ["x=1", "y=2"], self.int)
    self._check_inplace("+", ["x=1", "y=2j"], self.complex)
    self._check_inplace("+", ["x='1'", "y='2'"], self.str)
    self._check_inplace("+", ["x=[1]", "y=[2]"], self.int_list)
    self._check_inplace("+", ["x=[]", "y=[]"], self.nothing_list)
    self._check_inplace("+", ["x=[1]", "y=['abc']"], self.intorstr_list)
    self._check_inplace("+", ["x=(1,)", "y=(2,)"], self.int_tuple)
    self._check_inplace("+", ["x=(1,)", "y=(2.0,)"], self.intorfloat_tuple)

  def test_iand(self):
    self._check_inplace("&", ["x=3", "y=5"], self.int)
    self._check_inplace("&", ["x={1}", "y={1, 2}"], self.int_set)
    self._check_inplace("&", ["x={1}", "y={1.2}"], self.intorfloat_set)
    self._check_inplace("&", ["x={1, 2}", "y=set([1])"], self.int_set)
    self._check_inplace("&", ["x=1", "y=2"], self.int)

  def test_frozenset_ops(self):
    # TODO(pludemann): when these work, put them into the appropriate
    #                  test_<op> tests
    self._check_inplace("&", ["x=frozenset()", "y=frozenset()"],
                        self.empty_frozenset)
    self._check_inplace("-", ["x=frozenset()", "y=frozenset()"],
                        self.empty_frozenset)
    self._check_inplace("|", ["x=frozenset([1.0])", "y=frozenset([2.2])"],
                        self.float_frozenset)

  def test_idiv(self):
    self._check_inplace("/", ["x=1", "y=2"], self.int)
    self._check_inplace("/", ["x=1.0", "y=2"], self.float)
    self._check_inplace("/", ["x=1", "y=2.0"], self.float)
    self._check_inplace("/", ["x=1j", "y=2j"], self.complex)
    self._check_inplace("/", ["x=2j", "y=1"], self.complex)
    self._check_inplace("/", ["x=3+2j", "y=1.0"], self.complex)

  def test_ifloordiv(self):
    self._check_inplace("//", ["x=1", "y=2"], self.int)
    self._check_inplace("//", ["x=1.0", "y=2"], self.float)
    self._check_inplace("//", ["x=1j", "y=2j"], self.complex)
    self._check_inplace("//", ["x=1.0", "y=2j"], self.complex)

  def test_ilshift(self):
    self._check_inplace("<<", ["x=1", "y=2"], self.int)

  def test_irshift(self):
    self._check_inplace(">>", ["x=1", "y=2"], self.int)

  def test_isub(self):
    self._check_inplace("-", ["x=1", "y=2"], self.int)
    self._check_inplace("-", ["x=1.0", "y=2"], self.float)
    self._check_inplace("-", ["x=1j", "y=2j"], self.complex)
    self._check_inplace("-", ["x={1}", "y={1, 2}"], self.int_set)
    self._check_inplace("-", ["x={1}", "y={1.2}"], self.int_set)

  def test_isub_frozenset(self):
    self._check_inplace("-", ["x={1, 2}", "y=frozenset([1.0])"],
                        self.int_set)

  def test_imod(self):
    self._check_inplace("%", ["x=1", "y=2"], self.int)
    self._check_inplace("%", ["x=1.5", "y=2.5"], self.float)
    self._check_inplace("%", ["x='%r'", "y=set()"], self.str)

  def test_imul(self):
    self._check_inplace("*", ["x=1", "y=2"], self.int)
    self._check_inplace("*", ["x=1", "y=2.1"], self.float)
    self._check_inplace("*", ["x=1+2j", "y=2.1+3.4j"], self.complex)
    self._check_inplace("*", ["x='x'", "y=3"], self.str)
    self._check_inplace("*", ["x=[1, 2]", "y=3"], self.int_list)
    self._check_inplace("*", ["x=99", "y=[1.0, 2]"], self.intorfloat_list)
    self._check_inplace("*", ["x=(1, 2)", "y=3"], self.int_tuple)
    self._check_inplace("*", ["x=0", "y=(1, 2.0)"], self.intorfloat_tuple)

  def test_ior(self):
    self._check_inplace("|", ["x=1", "y=2"], self.int)
    self._check_inplace("|", ["x={1}", "y={2}"], self.int_set)

  def test_ipow(self):
    self._check_inplace("**", ["x=1", "y=2"], self.intorfloat)
    self._check_inplace("**", ["x=1", "y=-2"], self.intorfloat)
    self._check_inplace("**", ["x=1.0", "y=2"], self.float)
    self._check_inplace("**", ["x=1", "y=2.0"], self.float)
    self._check_inplace("**", ["x=1.1", "y=2.1"], self.float)
    self._check_inplace("**", ["x=1j", "y=2j"], self.complex)

  def test_ixor(self):
    self._check_inplace("^", ["x=1", "y=2"], self.int)
    self._check_inplace("^", ["x={1}", "y={2}"], self.int_set)


if __name__ == "__main__":
  test_inference.main()
