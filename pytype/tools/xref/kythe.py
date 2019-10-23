"""Kythe graph structure."""

import base64
import collections

from pytype.tools.xref import utils as xref_utils
from pytype.tools.xref import indexer


FILE_ANCHOR_SIGNATURE = ":module:"

Args = collections.namedtuple("Args", ["root", "corpus"])


# Kythe nodes

VName = collections.namedtuple(
    "VName", ["signature", "path", "language", "root", "corpus"])

Entry = collections.namedtuple(
    "Entry", ["source", "kind", "target", "fact_label", "value"])

Fact = collections.namedtuple(
    "Fact", ["source", "fact_name", "fact_value"])

Edge = collections.namedtuple(
    "Edge", ["source", "edge_kind", "target", "fact_name"])


class Kythe(object):
  """Store a list of kythe graph entries."""

  def __init__(self, source, args=None):
    self.path = source.filename
    if args:
      self.root = args.root
      self.corpus = args.corpus
    else:
      self.root = ""
      self.corpus = ""
    self.entries = []
    self._seen_entries = set()
    self.file_vname = self._add_file(source.text)
    self._add_file_anchor()

  def _encode(self, value):
    """Encode fact values as base64."""
    value_bytes = bytes(value, "utf-8")
    encoded_bytes = base64.b64encode(value_bytes)
    return encoded_bytes.decode("utf-8")

  def _add_file(self, file_contents):
    # File vnames are special-cased to have an empty signature and lang.
    vname = VName(
        signature="", language="", path=self.path, root=self.root,
        corpus=self.corpus)
    self.add_fact(vname, "node/kind", "file")
    self.add_fact(vname, "text", file_contents)
    return vname

  def _add_file_anchor(self):
    # Add a special anchor for the first byte of a file, so we can link to it.
    anchor_vname = self.add_anchor(0, 1)
    mod_vname = self.vname(FILE_ANCHOR_SIGNATURE)
    self.add_fact(mod_vname, "node/kind", "record")
    self.add_edge(anchor_vname, "defines/binding", mod_vname)

  def _add_entry(self, entry):
    """Make sure we don't have duplicate entries."""
    if entry in self._seen_entries:
      return
    self._seen_entries.add(entry)
    self.entries.append(entry)

  def vname(self, signature, filepath=None):
    return VName(
        signature=signature,
        path=filepath or self.path,
        language="python",
        root=self.root,
        corpus=self.corpus)

  def stdlib_vname(self, signature, filepath=None):
    return VName(
        signature=signature,
        path=filepath or self.path,
        language="python",
        root=self.root,
        corpus="pystdlib")

  def anchor_vname(self, start, end):
    signature = "@%d:%d" % (start, end)
    return self.vname(signature)

  def fact(self, source, fact_name, fact_value):
    fact_name = "/kythe/" + fact_name
    fact_value = self._encode(fact_value)
    return Fact(source, fact_name, fact_value)

  def edge(self, source, edge_name, target):
    edge_kind = "/kythe/edge/" + edge_name
    return Edge(source, edge_kind, target, "/")

  def add_fact(self, source, fact_name, fact_value):
    fact = self.fact(source, fact_name, fact_value)
    self._add_entry(fact)
    return fact

  def add_edge(self, source, edge_name, target):
    edge = self.edge(source, edge_name, target)
    self._add_entry(edge)
    return edge

  def add_anchor(self, start, end):
    vname = self.anchor_vname(start, end)
    self.add_fact(vname, "node/kind", "anchor")
    self.add_fact(vname, "loc/start", str(start))
    self.add_fact(vname, "loc/end", str(end))
    self.add_edge(vname, "childof", self.file_vname)
    return vname


# ----------------------------------------------------------------
# Generate kythe facts from an indexer.Indexer


def _process_deflocs(kythe, index):
  """Generate kythe edges for definitions."""

  for def_id in index.locs:
    defn = index.defs[def_id]
    for defloc in index.locs[def_id]:
      defn = index.defs[defloc.def_id]
      defn_vname = kythe.vname(defn.to_signature())
      start, end = index.get_def_offsets(defloc)
      anchor_vname = kythe.add_anchor(start, end)
      kythe.add_fact(
          source=defn_vname,
          fact_name="node/kind",
          fact_value=defn.node_kind())
      kythe.add_edge(
          source=anchor_vname,
          target=defn_vname,
          edge_name="defines/binding")

      # Emit a docstring if we have one.
      doc = defn.doc
      if doc:
        doc_vname = kythe.vname(defn.doc_signature())
        start, end = index.get_doc_offsets(defn.doc)
        anchor_vname = kythe.add_anchor(start, end)
        kythe.add_fact(
            source=doc_vname,
            fact_name="node/kind",
            fact_value="doc")
        kythe.add_fact(
            source=doc_vname,
            fact_name="text",
            fact_value=doc.text)
        kythe.add_edge(
            source=anchor_vname,
            target=doc_vname,
            edge_name="defines")
        kythe.add_edge(
            source=doc_vname,
            target=defn_vname,
            edge_name="documents")


def _process_params(kythe, index):
  """Generate kythe edges for function parameters."""

  for fp in index.function_params:
    fn_def = index.defs[fp.def_id]
    param = index.defs[fp.param_id]
    kythe.add_edge(
        source=kythe.vname(fn_def.to_signature()),
        edge_name="param.%d" % fp.position,
        target=kythe.vname(param.to_signature()))


def _make_defn_vname(kythe, index, defn):
  """Convert a definition into a kythe vname."""

  if isinstance(defn, indexer.Remote):
    remote = defn.module
    if remote in index.resolved_modules:
      if remote in index.imports:
        # The canonical path from the imports_map is the best bet for
        # module->filepath translation.
        path = index.imports[remote]
      else:
        # Fallback to the filepath of the stub file, though this is not always
        # accurate due to overrides.
        path = index.resolved_modules[remote].filename
      path = xref_utils.get_module_filepath(path)
      if defn.name == indexer.IMPORT_FILE_MARKER:
        sig = FILE_ANCHOR_SIGNATURE
      else:
        sig = "module." + defn.name
      if path.startswith("pytd:"):
        return kythe.stdlib_vname(
            sig, "pytd:" + index.resolved_modules[remote].module_name)
      else:
        return kythe.vname(sig, path)
    else:
      # Don't generate vnames for unresolved modules.
      return None
  else:
    return kythe.vname(defn.to_signature())


def _process_links(kythe, index):
  """Generate kythe edges for references."""

  for ref, defn in index.links:
    supported_types = (indexer.Definition, indexer.Remote, indexer.Module)
    if not isinstance(defn, supported_types):
      # TODO(mdemello): Fixes needed for chained method calls.
      continue
    start, end = index.get_ref_bounds(ref)
    vname = kythe.add_anchor(start, end)
    target = _make_defn_vname(kythe, index, defn)
    if target:
      kythe.add_edge(
          source=vname,
          target=target,
          edge_name="ref")


def _process_calls(kythe, index):
  """Generate kythe edges for function calls."""

  # Checks if a function call corresponds to a resolved reference, and generates
  # a ref/call to that reference's source definition if so.

  link_map = collections.defaultdict(list)
  for ref, defn in index.links:
    link_map[ref.location].append((ref, defn))

  for call in index.calls:
    call_links = link_map[call.location]
    call_ref = None
    call_defn = None
    for ref, d in call_links:
      if ref.name == call.name:
        call_ref = ref
        call_defn = d
        break
    if call_defn:
      target = _make_defn_vname(kythe, index, call_defn)
      if target:
        start, end = index.get_ref_bounds(call_ref)
        anchor_vname = kythe.anchor_vname(start, end)
        kythe.add_edge(
            source=anchor_vname,
            target=target,
            edge_name="ref/call")
        # The call is a child of the enclosing function/class (this lets us
        # generate call graphs).
        if ref.scope != "module":
          parent_defn = index.defs.get(call_ref.scope)
          if parent_defn:
            # TODO(mdemello): log the 'else' case; it should never happen.
            kythe.add_edge(
                source=anchor_vname,
                target=kythe.vname(parent_defn.to_signature()),
                edge_name="childof")
          else:
            assert False, ref


def generate_graph(index, kythe_args):
  kythe = Kythe(index.source, kythe_args)
  _process_deflocs(kythe, index)
  _process_params(kythe, index)
  _process_links(kythe, index)
  _process_calls(kythe, index)
  return kythe
