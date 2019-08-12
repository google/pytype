"""Trace function arguments, return values and calls to other functions."""

import collections

from pytype.tools.xref import indexer


Attr = collections.namedtuple(
    'Attr',
    ['name', 'node_type', 'type', 'attr', 'location'])


Arg = collections.namedtuple('Arg', ['name', 'node_type', 'type'])


Call = collections.namedtuple('Call', ['function_id', 'args', 'location'])


Function = collections.namedtuple(
    'Function',
    ['id', 'param_attrs', 'local_attrs', 'calls', 'ret', 'location'])


def get_type_fqname(defn):
  typename = defn.typename
  if '~unknown' in typename:
    return 'typing.Any'
  return typename


def collect_functions(index):
  """Track types and outgoing calls within a function."""
  fns = collections.defaultdict(list)

  # Collect methods and attribute accesses
  for ref, defn in index.links:
    if ref.typ == 'Attribute':
      attr = ref.name
      env = index.envs[ref.ref_scope]
      try:
        d = index.envs[ref.ref_scope].env[ref.target]
      except KeyError:
        continue
      typename = get_type_fqname(defn)
      fns[ref.ref_scope].append(
          Attr(d.name, d.typ, typename, attr, ref.location))

  # Collect function calls
  for call in index.calls:
    env = index.envs[call.scope]
    args = []
    for node in call.args:
      name = indexer.get_name(node)
      if indexer.typename(node) == 'Name':
        defn = env.env[node.id]
        node_type = defn.typ
        typename = get_type_fqname(defn)
      else:
        node_type = None
        typename = 'typing.Any'
      args.append(Arg(name, node_type, typename))
    fns[call.scope].append(Call(call.func, args, call.location))

  # Build up the map of function -> outgoing calls
  out = {}
  for k, v in fns.items():
    calls, param_attrs, local_attrs = [], set(), set()
    for x in v:
      if isinstance(x, Call):
        calls.append(x)
      elif getattr(x, 'node_type', None) == 'Param':
        param_attrs.add(x)
      else:
        local_attrs.add(x)
    ret = index.envs[k].ret
    if k in index.locs:
      location = index.locs[k][-1].location
    else:
      location = None
    out[k] = Function(id=k, param_attrs=param_attrs, local_attrs=local_attrs,
                      ret=ret, calls=calls, location=location)
  return out
