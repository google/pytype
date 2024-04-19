from typing import Dict, List, Set, Tuple

from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import containers
from pytype.rewrite.abstract import internal
from pytype.rewrite.flow import variables
from pytype.rewrite.tests import test_utils
from typing_extensions import assert_type

import unittest

# Type aliases
_AbstractVariable = base.AbstractVariableType


class BaseTest(test_utils.ContextfulTestBase):
  """Base class for constant tests."""

  def const_var(self, const, name=None):
    return self.ctx.consts[const].to_variable(name)


class ListTest(BaseTest):

  def test_constant_type(self):
    a = self.const_var("a")
    c = containers.List(self.ctx, [a])
    assert_type(c.constant, List[_AbstractVariable])

  def test_append(self):
    l1 = containers.List(self.ctx, [self.const_var("a")])
    l2 = l1.append(self.const_var("b"))
    self.assertEqual(l2.constant, [self.const_var("a"), self.const_var("b")])

  def test_extend(self):
    l1 = containers.List(self.ctx, [self.const_var("a")])
    l2 = containers.List(self.ctx, [self.const_var("b")])
    l3 = l1.extend(l2.to_variable())
    self.assertIsInstance(l3, containers.List)
    self.assertEqual(l3.constant, [self.const_var("a"), self.const_var("b")])

  def test_extend_splat(self):
    l1 = containers.List(self.ctx, [self.const_var("a")])
    l2 = self.ctx.types[list].instantiate()
    l3 = l1.extend(l2.to_variable())
    self.assertIsInstance(l3, containers.List)
    self.assertEqual(
        l3.constant,
        [self.const_var("a"), internal.Splat(self.ctx, l2).to_variable()])

  def test_extend_multiple_bindings(self):
    l1 = containers.List(self.ctx, [self.const_var("a")])
    l2 = containers.List(self.ctx, [self.const_var("b")])
    l3 = containers.List(self.ctx, [self.const_var("c")])
    var = variables.Variable((variables.Binding(l2), variables.Binding(l3)))
    l4 = l1.extend(var)
    self.assertEqual(l4, self.ctx.types[list].instantiate())


class DictTest(BaseTest):

  def test_constant_type(self):
    a = self.const_var("a")
    b = self.const_var("b")
    c = containers.Dict(self.ctx, {a: b})
    assert_type(c.constant, Dict[_AbstractVariable, _AbstractVariable])

  def test_setitem(self):
    d1 = containers.Dict(self.ctx, {})
    d2 = d1.setitem(self.const_var("a"), self.const_var("b"))
    self.assertEqual(d2.constant, {self.const_var("a"): self.const_var("b")})

  def test_update(self):
    d1 = containers.Dict(self.ctx, {})
    d2 = containers.Dict(self.ctx, {self.const_var("a"): self.const_var("b")})
    d3 = d1.update(d2.to_variable())
    self.assertIsInstance(d3, containers.Dict)
    self.assertEqual(d3.constant, {self.const_var("a"): self.const_var("b")})

  def test_update_indefinite(self):
    d1 = containers.Dict(self.ctx, {})
    indef = self.ctx.types[dict].instantiate()
    d2 = d1.update(indef.to_variable())
    self.assertIsInstance(d2, containers.Dict)
    self.assertEqual(d2.constant, {})
    self.assertTrue(d2.indefinite)

  def test_update_multiple_bindings(self):
    d1 = containers.Dict(self.ctx, {})
    d2 = containers.Dict(self.ctx, {self.const_var("a"): self.const_var("b")})
    d3 = containers.Dict(self.ctx, {self.const_var("c"): self.const_var("d")})
    var = variables.Variable((variables.Binding(d2), variables.Binding(d3)))
    d4 = d1.update(var)
    self.assertIsInstance(d4, containers.Dict)
    self.assertEqual(d4.constant, {})
    self.assertTrue(d4.indefinite)

  def test_update_from_arg_dict(self):
    d1 = containers.Dict(self.ctx, {})
    d2 = internal.FunctionArgDict(self.ctx, {"a": self.const_var("b")})
    d3 = d1.update(d2.to_variable())
    self.assertIsInstance(d3, containers.Dict)
    self.assertEqual(d3.constant, {self.const_var("a"): self.const_var("b")})


class SetTest(BaseTest):

  def test_constant_type(self):
    a = self.const_var("a")
    c = containers.Set(self.ctx, {a})
    assert_type(c.constant, Set[_AbstractVariable])

  def test_add(self):
    c1 = containers.Set(self.ctx, set())
    c2 = c1.add(self.const_var("a"))
    self.assertEqual(c2.constant, {self.const_var("a")})


class TupleTest(BaseTest):

  def test_constant_type(self):
    a = self.const_var("a")
    b = self.const_var("b")
    c = containers.Tuple(self.ctx, (a, b))
    assert_type(c.constant, Tuple[_AbstractVariable, ...])


if __name__ == "__main__":
  unittest.main()
