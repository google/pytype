"""Kythe graph structure."""

import base64
import collections


FILE_ANCHOR_SIGNATURE = ":module:"

Args = collections.namedtuple("Args", ["root", "corpus"])


# Kythe nodes

VName = collections.namedtuple(
    "VName", ["signature", "path", "lang", "root", "corpus"])

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
        signature="", lang="", path=self.path, root=self.root,
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
        lang="python",
        root=self.root,
        corpus=self.corpus)

  def builtin_vname(self, signature, filepath=None):
    return VName(
        signature=signature,
        path=filepath or self.path,
        lang="python",
        root=self.root,
        corpus="builtins")

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
