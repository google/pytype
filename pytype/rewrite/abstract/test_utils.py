"""Abstract test utilities."""
from typing import Any
from pytype.rewrite.abstract import base
import unittest


class FakeContext:
  """Fake context."""

  # TODO(b/241479600): We have to duplicate the instance attributes here to work
  # around a weird bug in current pytype. Once rewrite/ is rolled out, this bug
  # will hopefully be gone and we can delete these duplicate declarations.
  ANY: base.Singleton
  BUILD_CLASS: base.Singleton
  NULL: base.Singleton

  errorlog: Any
  pytd_converter: Any

  def __init__(self):
    # pylint: disable=invalid-name
    self.ANY = base.Singleton(self, 'ANY')
    self.BUILD_CLASS = base.Singleton(self, 'BUILD_CLASS')
    self.NULL = base.Singleton(self, 'NULL')
    # pylint: enable=invalid-name
    self.errorlog = None
    self.pytd_converter = None


class AbstractTestBase(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.ctx = FakeContext()
