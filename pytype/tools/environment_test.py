"""Tests for environment.py."""

import os

from pytype import file_utils
from pytype.tools import environment
import unittest


class TestComputePythonPath(unittest.TestCase):
  """Tests for environment.compute_pythonpath."""

  def test_script_path(self):
    with file_utils.Tempdir() as d:
      f = d.create_file('foo.py')
      self.assertSequenceEqual(environment.compute_pythonpath([f]), [d.path])

  def test_module_path(self):
    with file_utils.Tempdir() as d:
      d.create_file('__init__.py')
      f = d.create_file('foo.py')
      self.assertSequenceEqual(environment.compute_pythonpath([f]),
                               [os.path.dirname(d.path)])

  def test_subpackage(self):
    with file_utils.Tempdir() as d:
      d.create_file('__init__.py')
      d.create_file('d/__init__.py')
      f = d.create_file('d/foo.py')
      self.assertSequenceEqual(environment.compute_pythonpath([f]),
                               [os.path.dirname(d.path)])

  def test_multiple_paths(self):
    with file_utils.Tempdir() as d:
      f1 = d.create_file('d1/foo.py')
      f2 = d.create_file('d2/foo.py')
      self.assertSequenceEqual(
          environment.compute_pythonpath([f1, f2]),
          [os.path.join(d.path, 'd2'), os.path.join(d.path, 'd1')])

  def test_sort(self):
    with file_utils.Tempdir() as d:
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


class TestDoXOrDie(unittest.TestCase):
  """Tests for {do_x}_or_die() methods.

  Since whether these functions complete successfully depends on one's
  particular environment, these tests allow either succeeding or raising
  SystemExit. Any other exception will cause a test failure.
  """

  def _test(self, method, *args):
    try:
      method(*args)
    except SystemExit:
      pass

  def test_pytype(self):
    self._test(environment.check_pytype_or_die)

  def test_python_exe(self):
    self._test(environment.check_python_exe_or_die, 3.0)

  def test_typeshed(self):
    self._test(environment.initialize_typeshed_or_die)


if __name__ == '__main__':
  unittest.main()
