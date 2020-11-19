"""Test pyc/generate_opcode_diffs.py."""
import json
import subprocess
import textwrap
import types
from unittest import mock

from pytype.pyc import generate_opcode_diffs
import unittest


class GenerateOpcodeDiffsTest(unittest.TestCase):

  def _generate_diffs(self):
    with mock.patch.object(subprocess, 'run') as mock_run:
      mapping_38 = json.dumps({
          'opmap': {'DO_THIS': 1, 'DO_EIGHT': 5},
          'HAVE_ARGUMENT': 3,
          'HAS_CONST': [],
          'HAS_NAME': [],
      })
      mapping_39 = json.dumps({
          'opmap': {'DO_THAT': 4, 'DO_THAT_TOO': 5, 'DO_NINE': 7},
          'HAVE_ARGUMENT': 6,
          'HAS_CONST': [7],
          'HAS_NAME': [5, 7],
      })
      mock_run.side_effect = [types.SimpleNamespace(stdout=mapping_38),
                              types.SimpleNamespace(stdout=mapping_39)]
      return generate_opcode_diffs.generate_diffs(['3.8', '3.9'])

  def test_classes(self):
    classes, _, _ = self._generate_diffs()
    do_that, do_that_too, do_nine = classes
    self.assertMultiLineEqual('\n'.join(do_that), textwrap.dedent("""
      class DO_THAT(Opcode):
        __slots__ = ()
    """).strip())
    self.assertMultiLineEqual('\n'.join(do_that_too), textwrap.dedent("""
      class DO_THAT_TOO(Opcode):
        FLAGS = HAS_NAME
        __slots__ = ()
    """).strip())
    self.assertMultiLineEqual('\n'.join(do_nine), textwrap.dedent("""
      class DO_NINE(OpcodeWithArg):
        FLAGS = HAS_ARGUMENT | HAS_CONST | HAS_NAME
        __slots__ = ()
    """).strip())

  def test_diff(self):
    _, diff, _ = self._generate_diffs()
    self.assertMultiLineEqual('\n'.join(diff), textwrap.dedent("""
      1: None,  # was DO_THIS in 3.8
      4: DO_THAT,
      5: DO_THAT_TOO,  # was DO_EIGHT in 3.8
      7: DO_NINE,
    """).strip())

  def test_stubs(self):
    _, _, stubs = self._generate_diffs()
    do_that, do_that_too, do_nine = stubs
    self.assertMultiLineEqual('\n'.join(do_that), textwrap.dedent("""
      def byte_DO_THAT(self, state, op):
        del op
        return state
    """).strip())
    self.assertMultiLineEqual('\n'.join(do_that_too), textwrap.dedent("""
      def byte_DO_THAT_TOO(self, state, op):
        del op
        return state
    """).strip())
    self.assertMultiLineEqual('\n'.join(do_nine), textwrap.dedent("""
      def byte_DO_NINE(self, state, op):
        del op
        return state
    """).strip())


if __name__ == '__main__':
  unittest.main()
