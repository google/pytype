#!/usr/bin/env python

"""Generate cross references from a project."""

from __future__ import print_function

import collections
import logging

from pytype import abstract
from pytype import analyze
from pytype import errors
from pytype import io
from pytype import load_pytd
from pytype import module_utils
from pytype import utils

from typed_ast import ast27
from typed_ast import ast3


# A global "ast" variable that we set to ast27 or ast3 depending on the target
# python version.
#
# TODO(mdemello): Use typed_ast.convert to coerce everything into ast3
ast = None


def children(node):
  """Children to recurse over."""

  # Children to recurse into for each node type.
  node_children = {
      ast.Module: ["body"],
      ast.ClassDef: ["body"],
      ast.FunctionDef: ["body"],
      ast.Assign: ["targets", "value"],
  }

  ks = node_children.get(node.__class__, None)
  if ks:
    return [(k, getattr(node, k)) for k in ks]
  else:
    return ast.iter_fields(node)


def typename(node):
  return node.__class__.__name__


def get_id(node):
  """Construct an id based on node type."""

  c = node.__class__
  if c == ast.FunctionDef:
    return "function %s" % node.name
  elif c == ast.ClassDef:
    return "class %s" % node.name
  elif c == ast.Module:
    return "module"
  else:
    raise Exception("Unexpected scope: %r" % node)


def get_name(node):
  """Nodes have different name attributes."""

  if isinstance(node, ast.Attribute):
    return get_name(node.value) + "." + node.attr
  elif isinstance(node, str):
    return node
  elif hasattr(node, "name"):
    return node.name
  elif hasattr(node, "id"):
    return node.id
  else:
    return "[" + typename(node) + "]"


def get_location(node):
  # TODO(mdemello): The column offset for nodes like "class A" needs to be
  # adjusted to the start of the symbol.
  return (node.lineno, node.col_offset)


def has_decorator(f, decorator):
  for d in f.decorator_list:
    if isinstance(d, ast.Name) and d.id == decorator:
      return True
  return False


def get_opcodes(traces, lineno, op_list):
  """Get all opcodes in op_list on a given line."""
  return [x for x in traces[lineno] if x[0] in op_list]


class AttrError(Exception):
  pass


class PytypeValue(object):
  """Stores a value inferred by pytype."""

  def __init__(self, module, name, typ):
    self.module = module
    self.name = name
    self.typ = typ

  def format(self):
    return "{ %s::%s : %s }" % (self.module, self.typ, self.name)

  @classmethod
  def from_data(cls, data):
    """Construct a PytypeValue from a list of data."""

    if not data:
      return None
    else:
      # TODO(mdemello): We need to use all the data
      data = data[0]
    if isinstance(data, abstract.PyTDClass):
      return cls(data.module, data.name, "Class")
    elif isinstance(data, abstract.InterpreterClass):
      return cls("module", data.name, "Class")
    elif isinstance(data, abstract.BoundFunction):
      # TODO(mdemello): Handle multiple callcls values.
      data_cls = typename(data._callcls.data[0])  # pylint: disable=protected-access
      return cls("module", data_cls + "." + data.name, "BoundFunction")
    else:
      # TODO(mdemello): We need to infer the module here.
      return cls("module", str(data), typename(data))


class Dummy(object):
  """Work around a python3 issue with calling super with kwargs."""

  def __init__(self, *args, **kwargs):
    pass


class Definition(collections.namedtuple(
    "defn", ["name", "typ", "scope", "target"]), Dummy):
  """A symbol definition.

  Attributes:
    name: The symbol name
    typ: The definition type (e.g. ClassDef)
    scope: The namespace id (e.g. module:class A:function f:x)
    target: The LHS of an attribute (e.g. for x.foo, target = typeof(x))
  """

  def __init__(self, name, typ, scope, target):
    super(Definition, self).__init__(name, typ, scope, target)
    self.id = self.scope + "::" + self.name

  def format(self):
    return self.id


class DefLocation(collections.namedtuple("defloc", ["def_id", "location"])):
  """A location of a symbol definition.

  Attributes:
    def_id: The definition id (scope + name)
    location: The location of the definition in the source code.

  Note that a single definition can have multiple locations, for symbols that
  are redefined in the code.
  """

  pass


class Reference(collections.namedtuple(
    "refr", ["name", "typ", "data", "scope", "target", "location"]), Dummy):
  """A symbol holding a reference to a definition.

  Attributes:
    name: The symbol name
    typ: The symbol type (e.g. Attribute)
    data: The pytype data attached to the symbol
    scope: The namespace id (e.g. module:class A:function f:x)
    target: The LHS of an attribute (e.g. for x.foo, target = typeof(x))
    location: The line and column of the symbol in the source code.
  """

  def __init__(self, name, typ, data, scope, target, location):
    super(Reference, self).__init__(name, typ, data, scope, target, location)
    self.id = self.scope + "::" + self.name

  def format(self):
    return self.id


class Env(object):
  """A collection of namespaced symbols."""

  def __init__(self, scope, parent, cls):
    """Initialize an environment.

    Arguments:
      scope: The namespace key (e.g. module:class A:function f)
      parent: The env of the directly enclosing namespace
      cls: The class currently being defined
           (None if we are not in a class definition)

    Other attributes defined:
      env: The dictionary holding the symbol table for this environment
      attrs: Attributes defined on the current class
      self_var: The `self` variable in method definitions
    """

    self.scope = scope
    self.parent = parent
    self.cls = cls
    self.env = {}
    self.attrs = None
    self.self_var = parent and parent.self_var

  def lookup(self, symbol):
    if symbol in self.env:
      return (self, self.env[symbol])
    elif self.parent:
      return self.parent.lookup(symbol)
    else:
      return (None, None)

  def __getitem__(self, symbol):
    return self.lookup(symbol)[1]

  def __setitem__(self, symbol, value):
    self.env[symbol] = value

  def is_self_attr(self, node):
    return (
        self.self_var and
        isinstance(node, ast.Attribute) and
        isinstance(node.value, ast.Name) and
        node.value.id == self.self_var.name)

  def getattr(self, attr):
    if self.attrs:
      return self.attrs[attr]
    elif self.cls:
      return self.cls.getattr(attr)
    else:
      raise AttrError("called getattr in non-class context")

  def setattr(self, attr, value):
    if self.attrs is not None:
      self.attrs[attr] = value
    elif self.cls is not None:
      return self.cls.setattr(attr, value)
    else:
      print("setattr: ", attr, value)
      raise AttrError("called setattr in non-class context")


# pylint: disable=invalid-name
# pylint: disable=missing-docstring
#
# Visitors use generated method names that don't follow the pylint spec.
# Also names like visit_Name are self-documenting and do not need docstrings.


class ScopedVisitor(object):
  """An AST node visitor that keeps track of scopes and environments.

  A "scope" is the abstract namespace (represented by a string key that tracks
  the nested path of namespaces from the module root, e.g. module:class A:f).
  An "environment" holds data for the current scope. self.envs is not
  hierarchical, it's just a flat mapping of scope keys to environments.
  """

  # TODO(mdemello): Is the two-level visitor hierarchy really buying us
  # anything by way of maintainability or readability?

  def __init__(self):
    self.stack = []
    self.class_ids = []
    self.envs = {}

  def get_suppressed_nodes(self):
    """Nodes whose subtrees will be pruned during generic_visit."""
    return []

  def iprint(self, x):
    """Print messages indented by scope level, for debugging."""
    print("  " * len(self.stack), x)

  def scope_id(self):
    return ":".join(get_id(x) for x in self.stack)

  def visit(self, node):
    """Visit a node."""

    if isinstance(node, ast.AST):
      self.enter(node)
      for k, v in children(node):
        ret = self.visit(v)
        if ret:
          setattr(node, k, ret)
      out = self.call_visitor(node)
      self.leave(node)
      if out:
        return out
    elif isinstance(node, list):
      for v in node:
        self.visit(v)

  @property
  def current_class(self):
    if self.class_ids:
      return self.envs[self.class_ids[-1]]
    return None

  @property
  def current_env(self):
    current_scope = self.scope_id()
    return self.envs.get(current_scope, None)

  def add_scope(self, node, is_class=False):
    parent = self.current_env
    self.stack.append(node)
    new_scope = self.scope_id()
    new_env = Env(scope=new_scope, parent=parent,
                  cls=self.current_class)
    if is_class:
      new_env.attrs = {}
    self.envs[new_scope] = new_env
    return new_env

  def enter(self, node):
    method = "enter_" + node.__class__.__name__
    visitor = getattr(self, method, None)
    if visitor:
      return visitor(node)

  def enter_ClassDef(self, node):
    new_env = self.add_scope(node, is_class=True)
    self.class_ids.append(self.scope_id())
    # We need to set the env's cls to the new class, not the enclosing one.
    new_env.cls = self.current_class

  def enter_FunctionDef(self, node):
    self.add_scope(node)

  def enter_Module(self, node):
    self.add_scope(node)

  def generic_visit(self, node):
    if node.__class__ in self.get_suppressed_nodes():
      return "<node>"

  def call_visitor(self, node):
    method = "visit_" + node.__class__.__name__
    visitor = getattr(self, method, self.generic_visit)
    return visitor(node)

  def leave(self, node):
    """If the node has introduced a new scope, we need to pop it off."""
    if node == self.stack[-1]:
      self.stack.pop()
    if isinstance(node, ast.ClassDef):
      self.class_ids.pop()


class IndexVisitor(ScopedVisitor):
  """Visitor that generates indexes."""

  def __init__(self, traces):
    super(IndexVisitor, self).__init__()
    self.defs = {}
    self.locs = collections.defaultdict(list)
    self.refs = []
    self.modules = {}
    self.traces = traces

    self.traces = traces

  def get_suppressed_nodes(self):
    return [ast.Module, ast.BinOp, ast.Return, ast.Assign,
            ast.Num, ast.Add, ast.Str]

  def make_def(self, node, **kwargs):
    """Make a definition from a node."""

    if isinstance(node, ast.Name):
      t = typename(node.ctx)
    else:
      t = typename(node)
    args = {
        "name": get_name(node),
        "scope": self.scope_id(),
        "typ": t,
        "target": None,
    }
    args.update(kwargs)
    defn = Definition(**args)
    defloc = DefLocation(defn.id, get_location(node))
    return (defn, defloc)

  def make_ref(self, node, **kwargs):
    """Make a reference from a node."""

    args = {
        "name": get_name(node),
        "scope": self.scope_id(),
        "typ": typename(node),
        "location": get_location(node),
        "target": None,
        "data": None
    }
    args.update(kwargs)
    return Reference(**args)

  def add_local_def(self, node, **kwargs):
    defn, defloc = self.make_def(node, **kwargs)
    if defn.id not in self.defs:
      self.defs[defn.id] = defn
    self.locs[defn.id].append(defloc)
    self.envs[defn.scope][defn.name] = defn
    return defn

  def add_global_def(self, node, **kwargs):
    kwargs.update({"scope": "module"})
    return self.add_local_def(node, **kwargs)

  def add_local_ref(self, node, **kwargs):
    ref = self.make_ref(node, **kwargs)
    self.refs.append(ref)

  def add_global_ref(self, node, **kwargs):
    kwargs.update({"scope": "module"})
    return self.add_local_ref(node, **kwargs)

  def add_attr(self, node):
    defn, _ = self.make_def(node)
    self.defs[defn.id] = defn
    env = self.envs[self.scope_id()]
    if env.is_self_attr(node):
      self.envs[self.scope_id()].setattr(node.attr, defn)

  def enter_ClassDef(self, node):
    self.add_local_def(node)
    super(IndexVisitor, self).enter_ClassDef(node)

  def enter_FunctionDef(self, node):
    self.add_local_def(node)
    env = self.add_scope(node)
    params = [self.add_local_def(v) for v in node.args.args]
    if env.cls:
      if (not has_decorator(node, "classmethod") and
          not has_decorator(node, "staticmethod")):
        env.self_var = params[0]

  def visit_Name(self, node):
    # We use pytype trace data to distinguish between local and global
    # variables.
    if isinstance(node.ctx, ast.Load):
      ops = self.traces[node.lineno]
      for op, symbol, data in ops:
        if symbol == node.id:
          if op == "LOAD_GLOBAL":
            self.add_global_ref(node, name=symbol, data=data)
            break
          elif op in ["LOAD_FAST", "LOAD_NAME"]:
            self.add_local_ref(node, name=symbol, data=data)
            break
    elif isinstance(node.ctx, ast.Store):
      ops = self.traces[node.lineno]
      for op, symbol, data in ops:
        if symbol == node.id:
          if op == "STORE_GLOBAL":
            self.add_global_def(node, name=symbol)
            break
          elif op in ["STORE_FAST", "STORE_NAME"]:
            self.add_local_def(node, name=symbol)
            break
    return node.id

  def visit_Call(self, node):
    if isinstance(node.func, str):
      name = node.func
    else:
      name = node.func.id
    return name

  def visit_Assign(self, node):
    for v in node.targets:
      if isinstance(v, ast.Attribute):
        self.add_attr(v)

  def visit_Attribute(self, node):
    ops = self.traces[node.lineno]
    for op, symbol, data in ops:
      if symbol == node.attr and op in ["LOAD_ATTR"]:
        self.add_local_ref(
            node,
            target=node.value,
            name=node.value + "." + symbol,
            data=data)
        break
      elif symbol == node.attr and op in ["STORE_ATTR"]:
        self.add_local_def(node)
    return node.value + "." + node.attr

  def visit_Subscript(self, node):
    return node.value

  def visit_DictComp(self, _node):
    return "<expr>"

  def visit_ListComp(self, _node):
    return "<expr>"

  def visit_Import(self, node):
    store_ops = get_opcodes(self.traces, node.lineno, "STORE_NAME")
    import_ops = get_opcodes(self.traces, node.lineno, "IMPORT_NAME")
    for alias in node.names:
      name = alias.asname if alias.asname else alias.name
      d = self.add_local_def(node, name=name)
      # Only record modules that pytype has resolved in self.modules
      if alias.asname:
        # for |import x.y as z| we want {z: x.y}
        for _, symbol, data in store_ops:
          if (symbol == d.name and data and
              isinstance(data[0], abstract.Module)):
            self.modules[d.id] = data[0].full_name
      else:
        for _, symbol, data in import_ops:
          if (symbol == d.name and data and
              isinstance(data[0], abstract.Module)):
            # |import x.y| puts both {x: x} and {x.y: x.y} in modules
            for mod in module_utils.get_all_prefixes(name):
              self.modules[d.scope + "::" + mod] = mod

  def visit_ImportFrom(self, node):
    store_ops = get_opcodes(self.traces, node.lineno, "STORE_NAME")
    for alias in node.names:
      name = alias.asname if alias.asname else alias.name
      d = self.add_local_def(node, name=name)
      for _, symbol, data in store_ops:
        if (symbol == d.name and data and
            isinstance(data[0], abstract.Module)):
          # Only record modules that pytype has resolved in self.modules
          self.modules[d.id] = data[0].full_name


# pylint: enable=invalid-name
# pylint: enable=missing-docstring


class Indexer(object):
  """Runs the indexer visitor and collects its results."""

  def __init__(self, traces):
    self.traces = traces
    self.defs = None
    self.locs = None
    self.refs = None
    self.envs = None
    self.modules = None
    self.links = []

  def index(self, code_ast):
    v = IndexVisitor(self.traces)
    v.visit(code_ast)
    self.defs = v.defs
    self.locs = v.locs
    self.refs = v.refs
    self.envs = v.envs
    self.modules = v.modules

  def lookup_refs(self):
    """Look up references to generate links."""

    for r in self.refs:
      if r.typ == "Attribute":
        env = self.envs[r.scope]
        env, defn = env.lookup(r.target)
        if defn:
          if defn.id in self.modules:
            remote = self.modules[defn.id]
            kw = defn._asdict()
            del kw["scope"]
            del kw["name"]
            scope = "%s/%s" % (remote, defn.scope)
            name = r.name
            if name.startswith(remote):
              name = name[(len(remote) + 1):]
            # pytype: disable=missing-parameter
            new = Definition(scope=scope, name=name, **kw)
            # pytype: enable=missing-parameter
            self.links.append((r, new))
          else:
            self.links.append((r, defn))
        else:
          self.links.append((r, r.target))
      else:
        try:
          env, defn = self.envs[r.scope].lookup(r.name)
        except KeyError:
          env, defn = None, None

        if defn:
          self.links.append((r, defn))
        else:
          self.links.append((r, PytypeValue.from_data(r.data)))


def collect_traces(opcode_traces):
  """Postprocess pytype"s opcode traces."""

  out = collections.defaultdict(list)
  for op, symbol, data in opcode_traces:
    out[op.line].append((op.name, symbol, data))
  return out


def process_file(options):
  """Process a single file and return cross references."""

  # We bind the global ast variable in this function.
  global ast

  errorlog = errors.ErrorLog()
  loader = load_pytd.create_loader(options)
  src = io.read_source_file(options.input)
  vm = analyze.CallTracer(
      errorlog=errorlog,
      options=options,
      generate_unknowns=options.protocols,
      store_all_calls=False,
      loader=loader)
  try:
    analyze.infer_types(
        src=src,
        filename=options.input,
        errorlog=errorlog,
        options=options,
        loader=loader,
        tracer_vm=vm)
  except utils.UsageError as e:
    logging.error("Usage error: %s\n", utils.message(e))
    return 1

  traces = collect_traces(vm.opcode_traces)

  major, minor = options.python_version
  if major == 2:
    # python2.7 is the only supported py2 version.
    a = ast27.parse(src, options.input)
    ast = ast27
  else:
    a = ast3.parse(src, options.input, feature_version=minor)
    ast = ast3

  ix = Indexer(traces)
  ix.index(a)
  ix.lookup_refs()
  return ix
