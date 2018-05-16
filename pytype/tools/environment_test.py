"""Tests for environment.py."""

import os
import unittest

from pytype import utils
from pytype.tools import environment


class TestComputePythonPath(unittest.TestCase):
  """Tests for environment.compute_pythonpath."""

  def test_script_path(self):
    with utils.Tempdir() as d:
      f = d.create_file('foo.py')
      self.assertSequenceEqual(environment.compute_pythonpath([f]), [d.path])

  def test_module_path(self):
    with utils.Tempdir() as d:
      d.create_file('__init__.py')
      f = d.create_file('foo.py')
      self.assertSequenceEqual(environment.compute_pythonpath([f]),
                               [os.path.dirname(d.path)])

  def test_subpackage(self):
    with utils.Tempdir() as d:
      d.create_file('__init__.py')
      d.create_file('d/__init__.py')
      f = d.create_file('d/foo.py')
      self.assertSequenceEqual(environment.compute_pythonpath([f]),
                               [os.path.dirname(d.path)])

  def test_multiple_paths(self):
    with utils.Tempdir() as d:
      f1 = d.create_file('d1/foo.py')
      f2 = d.create_file('d2/foo.py')
      self.assertSequenceEqual(
          environment.compute_pythonpath([f1, f2]),
          [os.path.join(d.path, 'd2'), os.path.join(d.path, 'd1')])

  def test_sort(self):
    with utils.Tempdir() as d:
      f1 = d.create_file('d1/foo.py')
      f2 = d.create_file('d1/d2/foo.py')
      f3 = d.create_file('d1/d2/d3/foo.py')
      path = [os.path.join(d.path, 'd1', 'd2', 'd3'),
              os.path.join(d.path, 'd1', 'd2'),
              os.path.join(d.path, 'd1')]
      self.assertSequenceEqual(
          environment.compute_pythonpath([f1, f2, f3]), path)
      self.assertSequenceEqual(
          environment.compute_pythonpath([f3, f2, f1]), path)


if __name__ == '__main__':
  unittest.main()
