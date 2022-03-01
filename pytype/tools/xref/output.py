"""Output utilities for xref."""

import dataclasses
import json


def json_kythe_graph(kythe_graph):
  """Generate kythe entries."""

  for x in kythe_graph.entries:
    yield json.dumps(dataclasses.asdict(x))


def output_kythe_graph(kythe_graph):
  for x in json_kythe_graph(kythe_graph):
    print(x)
