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
          'opmap': {'DO_THIS': 1, 'I_MOVE': 2, 'DO_EIGHT': 5},
          'opname': ['<0>', 'DO_THIS', 'I_MOVE', '<3>', '<4>', 'DO_EIGHT',
                     '<6>', '<7>'],
          'HAVE_ARGUMENT': 3,
          'HAS_CONST': [],
          'HAS_NAME': [],
      })
      mapping_39 = json.dumps({
          'opmap': {'I_MOVE': 3, 'DO_THAT': 4, 'DO_THAT_TOO': 5, 'DO_NINE': 7},
          'opname': ['<0>', '<1>', '<2>', 'I_MOVE', 'DO_THAT', 'DO_THAT_TOO',
                     '<6>', 'DO_NINE'],
          'HAVE_ARGUMENT': 6,
          'HAS_CONST': [7],
          'HAS_NAME': [5, 7],
      })
      mock_run.side_effect = [types.SimpleNamespace(stdout=mapping_38),
                              types.SimpleNamespace(stdout=mapping_39)]
      return generate_opcode_diffs.generate_diffs(['3.8', '3.9'])

  def test_classes(self):
    classes, _, _, _ = self._generate_diffs()
    i_move, do_that, do_that_too, do_nine = classes
    self.assertMultiLineEqual('\n'.join(i_move), textwrap.dedent("""
      class I_MOVE(Opcode):
        __slots__ = ()
    """).strip())
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
    _, diff, _, _ = self._generate_diffs()
    self.assertMultiLineEqual('\n'.join(diff), textwrap.dedent("""
      1: None,  # was DO_THIS in 3.8
      2: None,  # was I_MOVE in 3.8
      3: I_MOVE,
      4: DO_THAT,
      5: DO_THAT_TOO,  # was DO_EIGHT in 3.8
      7: DO_NINE,
    """).strip())

  def test_stubs(self):
    _, _, stubs, _ = self._generate_diffs()
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

  def test_moved(self):
    _, _, _, moved = self._generate_diffs()
    self.assertEqual(moved, ['I_MOVE'])


if __name__ == '__main__':
  unittest.main()
