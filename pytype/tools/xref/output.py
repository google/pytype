"""Output utilities for xref."""

from __future__ import print_function

import json


def unpack(obj):
  """Recursively expand namedtuples into dicts."""

  if hasattr(obj, "_asdict"):
    return {k: unpack(v) for k, v in obj._asdict().items()}
  elif isinstance(obj, dict):
    return {k: unpack(v) for k, v in obj.items()}
  elif isinstance(obj, list):
    return [unpack(v) for v in obj]
  elif isinstance(obj, tuple):
    return tuple(unpack(v) for v in obj)
  else:
    return obj


def json_kythe_graph(index):
  """Generate kythe entries."""

  for x in index.kythe.entries:
    yield json.dumps(unpack(x))


def output_kythe_graph(index):
  for x in json_kythe_graph(index):
    print(x)
