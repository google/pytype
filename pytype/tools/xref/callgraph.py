"""Trace function arguments, return values and calls to other functions."""

import collections

from pytype.pytd import pytd_utils
from pytype.tools.xref import node_utils


Attr = collections.namedtuple(
    'Attr',
    ['name', 'node_type', 'type', 'attr', 'location'])


Arg = collections.namedtuple('Arg', ['name', 'node_type', 'type'])


Call = collections.namedtuple('Call', ['function_id', 'args', 'location'])


Function = collections.namedtuple(
    'Function',
    ['id', 'params', 'param_attrs', 'local_attrs', 'calls', 'ret', 'location'])


def unknown_to_any(typename):
  if '~unknown' in typename:
    return 'typing.Any'
  return typename


def get_function_params(pytd_fn):
  # The pytd def of an InterpreterFunction should have a single signature.
  assert len(pytd_fn.signatures) == 1
  sig = pytd_fn.signatures[0]
  return [(x.name, unknown_to_any(pytd_utils.Print(x.type)))
          for x in sig.params]


def collect_function_map(index):
  """Track types and outgoing calls within a function."""

  def pytd_of_fn(f):
    d = f.data[0][0]
    return index.get_pytd_def(d, f.name)

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
      typename = unknown_to_any(defn.typename)
      fns[ref.ref_scope].append(
          Attr(d.name, d.typ, typename, attr, ref.location))

  # Collect function calls
  for call in index.calls:
    env = index.envs[call.scope]
    args = []
    for name in call.args:
      if name in env.env:
        defn = env.env[name]
        node_type = defn.typ
        typename = unknown_to_any(defn.typename)
      else:
        node_type = None
        typename = 'typing.Any'
      args.append(Arg(name, node_type, typename))
    fns[call.scope].append(Call(call.func, args, call.location))

  # Build up the map of function -> outgoing calls
  out = {}
  fn_defs = [(k, v) for k, v in index.defs.items() if v.typ == 'FunctionDef']
  for fn_id, fn in fn_defs:
    params = get_function_params(pytd_of_fn(fn))
    calls, param_attrs, local_attrs = [], set(), set()
    for x in fns[fn_id]:
      if isinstance(x, Call):
        calls.append(x)
      elif getattr(x, 'node_type', None) == 'Param':
        param_attrs.add(x)
      else:
        local_attrs.add(x)
    ret = index.envs[fn_id].ret
    if fn_id in index.locs:
      location = index.locs[fn_id][-1].location
    else:
      location = None

    out[fn_id] = Function(id=fn_id,
                          params=params,
                          param_attrs=param_attrs,
                          local_attrs=local_attrs,
                          ret=ret,
                          calls=calls,
                          location=location)
  return out
