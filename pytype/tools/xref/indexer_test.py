from pytype import config
from pytype import file_utils

from pytype.tests import test_base

from pytype.tools.xref import indexer


def index_code(code):
  """Generate references from a code string."""
  with file_utils.Tempdir() as d:
    d.create_file("t.py", code)
    options = config.Options([d["t.py"]])
    return indexer.process_file(options)


class IndexerTest(test_base.TargetIndependentTest):
  """Tests for the indexer."""

  def assertDef(self, index, fqname, name, typ):
    self.assertTrue(fqname in index.defs)
    d = index.defs[fqname]
    self.assertEqual(d.name, name)
    self.assertEqual(d.typ, typ)

  def assertDefLocs(self, index, fqname, locs):
    self.assertTrue(fqname in index.locs)
    deflocs = index.locs[fqname]
    self.assertCountEqual([x.location for x in deflocs], locs)

  def test_class_def(self):
    ix = index_code("""\
        class A(object):
          pass
        b = A()
    """)
    self.assertDef(ix, "module::A", "A", "ClassDef")
    self.assertDef(ix, "module::b", "b", "Store")
    self.assertDefLocs(ix, "module::A", [(1, 0)])
    self.assertDefLocs(ix, "module::b", [(3, 0)])


test_base.main(globals(), __name__ == "__main__")
