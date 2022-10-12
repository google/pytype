"""Serialize typegraphs into JSON.

Usage:
  from pytype.typegraph import typegraph_serializer
  s = typegraph_serializer.encode_program(ctx.program)
  p = typegraph_serializer.decode_program(s)

You can also call `json` methods directly, using `TypegraphEncoder` and
`object_hook`:
  import json
  from pytype.typegraph import typegraph_serializer
  s = json.dumps(ctx.program, cls=typegraph_serializer.TypegraphEncoder)
  p = json.loads(s, object_hook=typegraph_serializer.object_hook)

We are not interesting in deserialization into a usable cfg.Program. If you
want to use the Program for your own needs later, use pytype as a library.
"""

import dataclasses
import json
from typing import Any, Dict, List, Optional

from pytype.typegraph import cfg


@dataclasses.dataclass
class SerializedCFGNode:
  id: int
  name: str
  incoming: List[int]
  outgoing: List[int]
  bindings: List[int]
  condition: Optional[int]


@dataclasses.dataclass
class SerializedVariable:
  id: int
  bindings: List[int]


@dataclasses.dataclass
class SerializedOrigin:
  where: int
  source_sets: List[List[int]]


@dataclasses.dataclass
class SerializedBinding:
  id: int
  variable: int
  data: Any
  origins: List[SerializedOrigin]


@dataclasses.dataclass
class SerializedProgram:
  cfg_nodes: List[SerializedCFGNode]
  variables: List[SerializedVariable]
  bindings: List[SerializedBinding]
  entrypoint: int


class TypegraphEncoder(json.JSONEncoder):
  """Implements the JSONEncoder behavior for typegraph objects."""

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._bindings: Dict[int, cfg.Binding] = {}

  def _encode_program(self, program: cfg.Program) -> Dict[str, Any]:
    variables = [self._encode_variable(v) for v in program.variables]
    # After visiting every Variable, self._bindings contains every Binding.
    # cfg_nodes and variables are sorted by ID number, so bindings will be too.
    bindings = sorted(self._bindings.values(), key=lambda b: b.id)
    return {
        "_type": "Program",
        "cfg_nodes": [self._encode_cfgnode(n) for n in program.cfg_nodes],
        "variables": variables,
        "entrypoint": program.entrypoint.id,
        "bindings": [self._encode_binding(b) for b in bindings],
    }

  def _encode_cfgnode(self, node: cfg.CFGNode) -> Dict[str, Any]:
    return {
        "_type": "CFGNode",
        "id": node.id,
        "name": node.name,
        "incoming": [n.id for n in node.incoming],
        "outgoing": [n.id for n in node.outgoing],
        "bindings": [b.id for b in node.bindings],
        "condition": node.condition.id if node.condition else None,
    }

  def _encode_variable(self, variable: cfg.Variable) -> Dict[str, Any]:
    self._bindings.update(((b.id, b) for b in variable.bindings))
    return {
        "_type": "Variable",
        "id": variable.id,
        "bindings": [b.id for b in variable.bindings],
    }

  def _encode_binding(self, binding: cfg.Binding) -> Dict[str, Any]:
    return {
        "_type": "Binding",
        "id": binding.id,
        "variable": binding.variable.id,
        "data": repr(binding.data),
        "origins": [self._encode_origin(o) for o in binding.origins],
    }

  def _encode_origin(self, origin: cfg.Origin) -> Dict[str, Any]:
    return {
        "_type": "Origin",
        "where": origin.where.id,
        "source_sets": [[b.id for b in s] for s in origin.source_sets],
    }

  def default(self, o):
    if isinstance(o, cfg.Program):
      return self._encode_program(o)
    elif isinstance(o, cfg.CFGNode):
      return self._encode_cfgnode(o)
    elif isinstance(o, cfg.Variable):
      return self._encode_variable(o)
    elif isinstance(o, cfg.Binding):
      return self._encode_binding(o)
    elif isinstance(o, cfg.Origin):
      return self._encode_origin(o)
    else:
      return super().default(o)


_TYP_MAP = {
    "Program": SerializedProgram,
    "CFGNode": SerializedCFGNode,
    "Variable": SerializedVariable,
    "Binding": SerializedBinding,
    "Origin": SerializedOrigin,
}


def _decode(obj):
  typ = obj.pop("_type")
  return _TYP_MAP[typ](**obj)


def object_hook(obj: Dict[str, Any]) -> Any:
  """An object hook for json.load that produces serialized CFG objects."""
  if "_type" in obj:
    return _decode(obj)
  return obj


def encode_program(program: cfg.Program) -> str:
  return json.dumps(program, cls=TypegraphEncoder)


def decode_program(json_str: str) -> SerializedProgram:
  prog = json.loads(json_str, object_hook=object_hook)
  assert isinstance(prog, SerializedProgram)
  return prog
