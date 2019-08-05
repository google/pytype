import ast
import itertools
import textwrap

from pytype import config
from pytype.tests import test_base
from pytype.tools.annotate_ast import annotate_ast
import six


class AnnotaterTest(test_base.TargetIndependentTest):

  def annotate(self, source):
    source = textwrap.dedent(source.lstrip('\n'))
    ast_factory = lambda unused_options: ast
    pytype_options = config.Options.create(python_version=self.python_version)

    module = annotate_ast.annotate_source(source, ast_factory, pytype_options)
    return module

  def assert_annotations_equal(self, expected, module):
    nodes = [
        node for node in ast.walk(module)
        if getattr(node, 'resolved_type', None)
    ]
    actual = {}
    for node in nodes:
      key = self._get_node_key(node)
      actual[key] = '{} :: {!r}'.format(node.resolved_annotation,
                                        node.resolved_type)

    for key in sorted(set(itertools.chain(expected, actual))):
      expected_pattern = expected.get(key)
      if not expected_pattern:
        self.fail('Unexpected annotation: {} -> {}'.format(key, actual[key]))
      actual_text = actual.get(key)
      if not actual_text:
        self.fail(
            'Expected to find node {} annotated, but it was not.'.format(key))
      msg = ('Resolved annotation value does not match {!r}: Node {} annotated '
             'with {}').format(expected_pattern, key, actual_text)
      six.assertRegex(self, actual_text, expected_pattern, msg=msg)

  def _get_node_key(self, node):
    base = (node.lineno, node.__class__.__name__)

    if isinstance(node, ast.Name):
      return base + (node.id,)
    else:
      return base

  def test_annotating_name(self):
    source = """
    a = 1
    b = {}
    c = []
    d = 3, 4
    """
    module = self.annotate(source)

    expected = {
        (1, 'Name', 'a'): 'int',
        (2, 'Name', 'b'): 'dict',
        (3, 'Name', 'c'): 'list',
        (4, 'Name', 'd'): 'tuple',
    }
    self.assert_annotations_equal(expected, module)


test_base.main(globals(), __name__ == '__main__')
