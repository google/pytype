"""Tests for abstract_utils.py."""

from pytype import abstract_utils
from pytype import config
from pytype import errors
from pytype import load_pytd
from pytype import vm
from pytype.tests import test_base

import six

import unittest


class GetViewsTest(test_base.UnitTest):

  def setUp(self):
    super().setUp()
    self._vm = vm.VirtualMachine(
        errors.ErrorLog(), config.Options.create(
            python_version=self.python_version),
        load_pytd.Loader(None, self.python_version))

  def test_basic(self):
    v1 = self._vm.program.NewVariable(
        [self._vm.convert.unsolvable], [], self._vm.root_cfg_node)
    v2 = self._vm.program.NewVariable(
        [self._vm.convert.int_type, self._vm.convert.str_type], [],
        self._vm.root_cfg_node)
    views = list(abstract_utils.get_views([v1, v2], self._vm.root_cfg_node))
    six.assertCountEqual(self,
                         [{v1: views[0][v1], v2: views[0][v2]},
                          {v1: views[1][v1], v2: views[1][v2]}],
                         [{v1: v1.bindings[0], v2: v2.bindings[0]},
                          {v1: v1.bindings[0], v2: v2.bindings[1]}])

  def _test_optimized(self, skip_future_value, expected_num_views):
    v1 = self._vm.program.NewVariable(
        [self._vm.convert.unsolvable], [], self._vm.root_cfg_node)
    v2 = self._vm.program.NewVariable(
        [self._vm.convert.int_type, self._vm.convert.str_type], [],
        self._vm.root_cfg_node)
    views = abstract_utils.get_views([v1, v2], self._vm.root_cfg_node)
    skip_future = None
    # To count the number of views. Doesn't matter what we put in here, as long
    # as it's one per view.
    view_markers = []
    while True:
      try:
        view = views.send(skip_future)
      except StopIteration:
        break
      # Accesses v1 only, so the v2 bindings should be deduplicated when
      # `skip_future` is True.
      view_markers.append(view[v1])
      skip_future = skip_future_value
    self.assertEqual(len(view_markers), expected_num_views)

  def test_skip(self):
    self._test_optimized(skip_future_value=True, expected_num_views=1)

  def test_no_skip(self):
    self._test_optimized(skip_future_value=False, expected_num_views=2)


if __name__ == "__main__":
  unittest.main()
