"""Constant folding optimisation for bytecode.

This optimisation adds a new pseudo-opcode, LOAD_FOLDED_CONST, which encodes the
type of a complex literal constant in its `arg` field, in a "typestruct" format
described below. There is a corresponding function, build_folded_type, which
constructs a vm type from the encoded typestruct.

The type structure stored in LOAD_FOLDED_CONST is an immutable (for easy
hashing) tree with the following elements:

('prim', <python type>) : a primitive type, e.g. ('prim', str)
(tag, types) : a collection type; 'types' represent the type params
frozenset(types): a union of types

tag   = prim | tuple | list | map | set
            the types python supports for a literal constant
types = a tuple of type | frozenset(types)
            where the size of the tuple depends on the tag, e.g ('map', (k, v))

For ease of testing and debugging there is also a simplified literal syntax to
construct and examine these typestructs, see constant_folding_test for examples.
This is less uniform, and therefore not recommended to use other than for
input/output.
"""

from pytype.pyc import loadmarshal
from pytype.pyc import opcodes
from pytype.pyc import pyc


class _Stack:
  """A simple opcode stack."""

  def __init__(self):
    self.stack = []

  def __iter__(self):
    return self.stack.__iter__()

  def push(self, val):
    self.stack.append(val)

  def pop(self):
    return self.stack.pop()

  def clear(self):
    self.stack = []

  def fold_args(self, n):
    """Collect the arguments to a build call."""
    types = set()
    if len(self.stack) < n:
      # We have something other than constants in the op list
      return None
    else:
      for _ in range(n):
        elt, op = self.stack.pop()
        types.add(elt)
        op.folded = True
    return frozenset(types)

  def fold_map_args(self, n):
    """Collect the arguments to a BUILD_MAP call."""
    k_types = set()
    v_types = set()
    if len(self.stack) < 2 * n:
      # We have something other than constants in the op list
      return None, None
    else:
      for _ in range(n):
        v_elt, v_op = self.stack.pop()
        k_elt, k_op = self.stack.pop()
        k_types.add(k_elt)
        v_types.add(v_elt)
        k_op.folded = True
        v_op.folded = True
    return frozenset(k_types), frozenset(v_types)

  def build(self, typename, op):
    const = self.fold_args(op.arg)
    if const:
      self.stack.append([(typename, const), op])


class _FoldConstants:
  """Fold constant literals in pyc code."""

  def visit_code(self, code):
    """Visit code, folding literals."""

    def build_tuple(tup):
      out = []
      for e in tup:
        if isinstance(e, tuple):
          out.append(build_tuple(e))
        else:
          out.append(('prim', type(e)))
      return ('tuple', tuple(out))

    for block in code.order:
      stack = _Stack()
      consts = {}
      for op in block:
        if isinstance(op, opcodes.LOAD_CONST):
          elt = code.co_consts[op.arg]
          if isinstance(elt, tuple):
            stack.push([build_tuple(elt), op])
          else:
            stack.push([('prim', type(elt)), op])
        elif isinstance(op, opcodes.BUILD_LIST):
          stack.build('list', op)
        elif isinstance(op, opcodes.BUILD_SET):
          stack.build('set', op)
        elif isinstance(op, opcodes.FORMAT_VALUE):
          if op.arg & loadmarshal.FVS_MASK:
            stack.pop()
          _ = stack.fold_args(1)
          stack.push([('prim', str), op])
        elif isinstance(op, opcodes.BUILD_STRING):
          _ = stack.fold_args(op.arg)
          stack.push([('prim', str), op])
        elif isinstance(op, opcodes.BUILD_MAP):
          key_types, val_types = stack.fold_map_args(op.arg)
          if key_types:
            key_types = frozenset(key_types)
            stack.push([('map', (key_types, val_types)), op])
        elif isinstance(op, opcodes.BUILD_CONST_KEY_MAP):
          (_, key_types), key_op = stack.pop()
          key_types = frozenset(key_types)
          val_types = stack.fold_args(op.arg)
          if val_types:
            key_op.folded = True
            stack.push([('map', (key_types, val_types)), op])
        else:
          # If we hit any other bytecode, we are no longer building a literal
          # constant. Clear the stack, but save any substructures that have
          # already been folded from primitives.
          for t, o in stack:
            if t[0] != 'prim' or isinstance(o, opcodes.BUILD_STRING):
              consts[id(o)] = t
          stack.clear()
      out = []
      for op in block:
        if id(op) in consts:
          t = consts[id(op)]
          arg = t
          pretty_arg = t
          o = opcodes.LOAD_FOLDED_CONST(op.index, op.line, arg, pretty_arg)
          out.append(o)
        elif not op.folded:
          out.append(op)
        else:
          pass
      block.code = out
    return code


def to_literal(typ, always_tuple=False):
  """Convert a typestruct item to a simplified form for ease of use."""

  def expand(params):
    return (to_literal(x) for x in params)

  def union(params):
    ret = tuple(sorted(expand(params), key=str))
    if len(ret) == 1 and not always_tuple:
      ret, = ret  # pylint: disable=self-assigning-variable
    return ret

  tag, params = typ
  if tag == 'prim':
    return params
  elif tag == 'tuple':
    vals = tuple(expand(params))
    return (tag, *vals)
  elif tag == 'map':
    k, v = params
    return (tag, union(k), union(v))
  else:
    return (tag, union(params))


def from_literal(tup):
  """Convert from simple literal form to the more uniform typestruct."""

  def expand(vals):
    return [from_literal(x) for x in vals]

  def union(vals):
    if not isinstance(vals, tuple):
      vals = (vals,)
    v = expand(vals)
    return frozenset(v)

  if not isinstance(tup, tuple):
    return ('prim', tup)
  elif isinstance(tup[0], str):
    tag, *vals = tup
    if tag == 'prim':
      return tup
    elif tag == 'tuple':
      params = tuple(expand(vals))
      return (tag, params)
    elif tag == 'map':
      k, v = vals
      return (tag, (union(k), union(v)))
    else:
      vals, = vals  # pylint: disable=self-assigning-variable
      return (tag, union(vals))
  else:
    return tuple(expand(tup))


def optimize(code):
  """Fold all constant literals in the bytecode into LOAD_FOLDED_CONST ops."""
  return pyc.visit(code, _FoldConstants())


def build_folded_type(vm, state, typ):
  """Convert a typestruct to a vm type."""

  def join(state, xs):
    vs = []
    for x in xs:
      state, v = build_folded_type(vm, state, x)
      vs.append(v)
    val = vm.convert.build_content(vs)
    return state, val

  def collect(state, convert_type, params):
    state, t = join(state, params)
    ret = vm.convert.build_collection_of_type(state.node, convert_type, t)
    return state, ret

  def collect_tuple(state, params):
    vs = []
    for t in params:
      state, v = build_folded_type(vm, state, t)
      vs.append(v)
    ret = vm.convert.build_tuple(state.node, vs)
    return state, ret

  def collect_map(state, params):
    k_types, v_types = params
    state, v = join(state, v_types)
    m = vm.convert.build_map(state.node)
    for t in k_types:
      state, kt = build_folded_type(vm, state, t)
      state = vm.store_subscr(state, m, kt, v)
    return state, m

  tag, params = typ
  if tag == 'prim':
    val = vm.convert.primitive_class_instances[params]
    return state, val.to_variable(state.node)
  elif tag == 'list':
    return collect(state, vm.convert.list_type, params)
  elif tag == 'set':
    return collect(state, vm.convert.set_type, params)
  elif tag == 'tuple':
    return collect_tuple(state, params)
  elif tag == 'map':
    return collect_map(state, params)
  else:
    assert False, ('Unexpected type tag:', typ)
