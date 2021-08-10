import textwrap

from pytype.tools.merge_pyi import annotate_source
import unittest


class AnnotateSourceTest(unittest.TestCase):
  """Tests for annotate_source."""

  def test_basic(self):
    py_source = textwrap.dedent('''
      class PythonToken(Token):
        def __repr__(self):
          return ('TokenInfo(type=%s, string=%r, start_pos=%r, prefix=%r)' %
                  self._replace(type=self.type.name))

      def tokenize(code, version_info, start_pos=(1, 0)):
        """Generate tokens from a the source code (string)."""
        lines = split_lines(code, keepends=True)
        return tokenize_lines(lines, version_info, start_pos=start_pos)
    ''')

    pyi_source = textwrap.dedent('''
      class PythonToken(Token):
        def __repr__(self) -> str: ...

      def tokenize(
        code: str, version_info: PythonVersionInfo, start_pos: Tuple[int, int] = (1, 0)
      ) -> Generator[PythonToken, None, None]: ...
    ''')

    merged_source = annotate_source.merge_sources(
        py_src=py_source, pyi_src=pyi_source)

    expected = textwrap.dedent('''
      class PythonToken(Token):
        def __repr__(self) -> str:
          return ('TokenInfo(type=%s, string=%r, start_pos=%r, prefix=%r)' %
                  self._replace(type=self.type.name))

      def tokenize(code: str, version_info: PythonVersionInfo, start_pos: Tuple[int, int] = (1, 0)
      ) -> Generator[PythonToken, None, None]:
        """Generate tokens from a the source code (string)."""
        lines = split_lines(code, keepends=True)
        return tokenize_lines(lines, version_info, start_pos=start_pos)
    ''')

    self.assertEqual(merged_source, expected)


if __name__ == '__main__':
  unittest.main()
