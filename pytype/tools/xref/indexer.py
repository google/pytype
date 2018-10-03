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

from pytype.tools.xref import kythe

from typed_ast import ast27t as ast27
from typed_ast import ast3


# A global "ast" variable that we set to ast27 or ast3 depending on the target
# python version.
#
# TODO(mdemello): Use typed_ast.convert to coerce everything into ast3
ast = None


# A mapping of offsets between a node's start position and the symbol being
# defined. e.g. in the declaration "class X" the X is at +6 from the start.
DEF_OFFSETS = {
    "ClassDef": 6,  # class X
    "FunctionDef": 4,  # def f
}


def children(node):
  """Children to recurse over."""

  # Children to recurse into for each node type.
  node_children = {
      ast.Module: ["body"],
      ast.ClassDef: ["bases", "body"],
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
    raise ValueError("Unexpected scope: %r" % node)


def qualified_method(data):
  """Fully qualify a method call with its class scope."""
  if isinstance(data, abstract.BoundFunction):
    return data.repr_names()
  else:
    return [data.name]


def get_name(node):
  """Nodes have different name attributes."""

  if isinstance(node, ast.Attribute):
    return get_name(node.value) + "." + node.attr
  elif isinstance(node, ast.arg):
    return node.arg
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


# Internal datatypes


class AttrError(Exception):
  pass


class SourceFile(object):
  """Line-based source code access."""

  def __init__(self, src, raw_traces, filename):
    self.text = src
    self.traces = self.collect_traces(raw_traces)
    self.filename = filename
    self.lines = src.split("\n")
    self.offsets = []
    self._init_byte_offsets()

  def _init_byte_offsets(self):
    offset = 0
    for line in self.lines:
      self.offsets.append(offset)
      offset += len(line) + 1  # account for the \n

  def get_offset(self, line, column):
    return self.offsets[line - 1] + column

  def collect_traces(self, raw_traces):
    """Postprocess pytype's opcode traces."""

    out = collections.defaultdict(list)
    for op, symbol, data in raw_traces:
      out[op.line].append((op.name, symbol, data))
    return out

  def line(self, n):
    """Index source lines from 1."""
    return self.lines[n - 1]

  def find_text(self, start_line, end_line, text):
    for l in range(start_line, end_line):
      col = self.line(l).find(text)
      if col > -1:
        return (l, col)
    return None, None

  def display_traces(self):
    """Debug printing of source + traces per line."""
    for line in sorted(self.traces.keys()):
      print("%d %s" % (line, self.line(line)))
      for name, symbol, data in self.traces[line]:
        print("  %s : %s <- %s %s" % (
            name, symbol, data, data and [typename(x) for x in data]))
      print("-------------------")


class PytypeValue(object):
  """Stores a value inferred by pytype."""

  def __init__(self, module, name, typ):
    self.module = module
    self.name = name
    self.typ = typ
    self.id = self.module + "." + self.name

  def format(self):
    return "%s { %s.%s : %s }" % (
        self.id, self.module, self.typ, self.name)

  @classmethod
  def _from_data(cls, data):
    """Construct a PytypeValue from a single datum."""

    if not data:
      return None

    if isinstance(data, abstract.PyTDClass):
      if data.module:
        # If we have a remote reference, return Remote rather than PytypeValue.
        return Remote(data.module, data.name, resolved=True)
      else:
        # This is a namedtuple or some other special case pytype has generated a
        # local PyTDClass for. We need special cases for them too.
        return None
    elif isinstance(data, abstract.InterpreterClass):
      return cls("module", data.name, "Class")
    elif isinstance(data, abstract.BoundFunction):
      # TODO(mdemello): Handle multiple class bindings.
      name = data.repr_names(callself_repr=typename)[0]
      return cls("module", name, "BoundFunction")
    else:
      # TODO(mdemello): We need to infer the module here.
      return cls("module", str(data), typename(data))

  @classmethod
  def from_data(cls, data):
    """Construct a PytypeValue from a list of data."""

    if not data:
      return None
    else:
      return [cls._from_data(x) for x in data]

  def to_signature(self):
    return self.module + "." + self.name


class Module(object):

  def __init__(self, name):
    self.name = name

  def attr(self, attr_name):
    return Remote(self.name, attr_name, resolved=True)


class Dummy(object):
  """Work around a python3 issue with calling super with kwargs."""

  def __init__(self, *args, **kwargs):
    pass


class DocString(collections.namedtuple(
    "docstring", ["text", "location", "length"])):
  """Store the text and location of a docstring."""

  @classmethod
  def from_node(cls, node):
    """If the first element in node.body is a string, create a docstring."""

    # This should only be called on ClassDef and FunctionDef
    assert isinstance(node, (ast.ClassDef, ast.FunctionDef))
    if (node.body and
        isinstance(node.body[0], ast.Expr) and
        isinstance(node.body[0].value, ast.Str)):
      doc_node = node.body[0]
      doc = doc_node.value.s
      length = len(doc)  # we want to preserve the byte length
      if isinstance(doc, bytes):
        # In target 2.7 mode we get docstrings as bytes.
        doc = doc.decode("utf-8")
      return cls(doc, get_location(doc_node), length)
    return None


class Definition(collections.namedtuple(
    "defn", ["name", "typ", "scope", "target", "doc"]), Dummy):
  """A symbol definition.

  Attributes:
    name: The symbol name
    typ: The definition type (e.g. ClassDef)
    scope: The namespace id (e.g. module:class A:function f:x)
    target: The LHS of an attribute (e.g. for x.foo, target = typeof(x))
    doc: The docstring, if any, for function and class defs
  """

  def __init__(self, name, typ, scope, target, doc):
    super(Definition, self).__init__(name, typ, scope, target, doc)
    self.id = self.scope + "." + self.name

  def format(self):
    return self.id

  def to_signature(self):
    return self.id

  def doc_signature(self):
    """Signature for the definition's docstring."""
    return self.to_signature() + ".__doc__"

  def node_kind(self):
    # TODO(mdemello): Add more node types.
    if self.typ == "ClassDef":
      return "class"
    elif self.typ == "FunctionDef":
      return "function"
    else:
      return "variable"


class Remote(collections.namedtuple(
    "remote", ["module", "name", "resolved"]), Dummy):
  """A symbol from another module."""

  def __init__(self, module, name, resolved):
    super(Remote, self).__init__(module, name, resolved)
    self.id = self.module + "/module." + self.name

  def attr(self, attr_name):
    return Remote(self.module, self.name + "." + attr_name, self.resolved)

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
    "refr", [
        "name", "typ", "data", "scope", "ref_scope", "target", "location"])
                , Dummy):
  """A symbol holding a reference to a definition.

  Attributes:
    name: The symbol name
    typ: The symbol type (e.g. Attribute)
    data: The pytype data attached to the symbol
    scope: The namespace id (e.g. module.A.f)
    ref_scope: The namespace id of the referred symbol (if we can determine it)
    target: The LHS of an attribute (e.g. for x.foo, target = typeof(x))
    location: The line and column of the symbol in the source code.
  """

  def __init__(self, name, typ, data, scope, ref_scope, target, location):
    super(Reference, self).__init__(
        name, typ, data, scope, ref_scope, target, location)
    self.id = self.scope + "." + self.name

  def format(self):
    return self.id


class Funcall(object):
  """Representation of a function call."""

  def __init__(self, name, func, location):
    self.name = name
    self.func = func
    self.location = location


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
    if self.attrs is not None and attr in self.attrs:
      return self.attrs[attr]
    elif self.cls and self.cls.scope != self.scope:
      return self.cls.getattr(attr)
    else:
      raise AttrError("called getattr in non-class context")

  def setattr(self, attr, value):
    if self.attrs is not None:
      self.attrs[attr] = value
    elif self.cls is not None:
      return self.cls.setattr(attr, value)
    else:
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

  def __init__(self, module_name):
    self.stack = []
    self.class_ids = []
    self.envs = {}
    self.module_name = module_name

  def get_id(self, node):
    """Construct an id based on node type."""

    c = node.__class__
    if c == ast.FunctionDef:
      return node.name
    elif c == ast.ClassDef:
      return node.name
    elif c == ast.Module:
      return self.module_name
    else:
      raise Exception("Unexpected scope: %r" % node)

  def get_suppressed_nodes(self):
    """Nodes whose subtrees will be pruned during generic_visit."""
    return []

  def iprint(self, x):
    """Print messages indented by scope level, for debugging."""
    print("  " * len(self.stack), x)

  def scope_id(self):
    return ".".join(self.get_id(x) for x in self.stack)

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
    return self.envs[current_scope]

  def add_scope(self, node, is_class=False):
    if self.stack:
      parent = self.current_env
    else:
      parent = None
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

  def __init__(self, source, module_name):
    super(IndexVisitor, self).__init__(module_name)
    self.defs = {}
    self.locs = collections.defaultdict(list)
    self.refs = []
    self.modules = {}
    self.source = source
    self.traces = source.traces
    self.typemap = {}
    self.classmap = {}
    self.calls = []
    self.kythe = kythe.Kythe(source)

  def _get_location(self, node, args):
    """Get a more accurate node location."""

    line, col = None, None

    if isinstance(node, ast.ClassDef):
      # For class and function definitions, search for the string
      #   (class|def) <name>
      # between the start of the AST node and the start of the body. Handles the
      # offset for decorated functions/classes.
      body_start = node.body[0].lineno
      text = "class %s" % args["name"]
      line, col = self.source.find_text(node.lineno, body_start, text)
    elif isinstance(node, ast.FunctionDef):
      body_start = node.body[0].lineno
      text = "def %s" % args["name"]
      line, col = self.source.find_text(node.lineno, body_start, text)
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
      # Search for imported module names
      text = self.source.line(node.lineno)
      name = args["name"]
      c = text.index(" " + name)
      if c == -1:
        c = text.index("," + name)
      if c != -1:
        line, col = node.lineno, c + 1

    if line is None:
      line, col = get_location(node)

    return (line, col)

  def get_suppressed_nodes(self):
    return [ast.Module, ast.BinOp, ast.BoolOp, ast.Return, ast.Assign, ast.Num,
            ast.Add, ast.Str]

  def make_def(self, node, **kwargs):
    """Make a definition from a node."""

    if isinstance(node, ast.Name):
      t = typename(node.ctx)
    elif isinstance(node, ast.arg):
      t = "Param"
    else:
      t = typename(node)
    args = {
        "name": get_name(node),
        "scope": self.scope_id(),
        "typ": t,
        "target": None,
        "doc": None,
    }
    args.update(kwargs)
    defn = Definition(**args)
    line, col = self._get_location(node, args)
    assert line is not None
    defloc = DefLocation(defn.id, (line, col))
    return (defn, defloc)

  def make_ref(self, node, **kwargs):
    """Make a reference from a node."""

    args = {
        "name": get_name(node),
        "scope": self.scope_id(),
        "ref_scope": None,
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
    kwargs.update({"ref_scope": self.scope_id()})
    ref = self.make_ref(node, **kwargs)
    self.refs.append(ref)
    return ref

  def add_closure_ref(self, node, **kwargs):
    """Look for node.name up the chain of scopes."""
    name = get_name(node)
    env, _ = self.current_env.lookup(name)
    if env:
      kwargs.update({"ref_scope": env.scope})
    else:
      # This should never happen! If python has generated a LOAD_DEREF bytecode
      # then we do have the name defined in a parent scope. However, in the
      # interests of not crashing the indexer, fall back to the current scope.
      # TODO(mdemello): We need error logs.
      pass
    ref = self.make_ref(node, **kwargs)
    self.refs.append(ref)
    return ref

  def add_global_ref(self, node, **kwargs):
    kwargs.update({"ref_scope": "module"})
    return self.add_local_ref(node, **kwargs)

  def add_call(self, node, name, func):
    self.calls.append(Funcall(name, func, get_location(node)))

  def add_attr(self, node):
    defn, _ = self.make_def(node)
    self.defs[defn.id] = defn
    env = self.envs[self.scope_id()]
    if env.is_self_attr(node):
      self.envs[self.scope_id()].setattr(node.attr, defn)

  def enter_ClassDef(self, node):
    defn = self.add_local_def(node, doc=DocString.from_node(node))
    # TODO(mdemello): For decorated classes, the node's lineno starts at the
    # first decorator, and therefore does not match the opcode's lineno.
    # Likewise, when a class definition spans multiple lines, the AST node
    # starts on the first line but the BUILD_CLASS opcode starts on the last
    # one. Fix when we incorporate asttokens.
    ops = get_opcodes(self.traces, node.lineno, ["BUILD_CLASS"])
    class_name = get_name(node)
    for _, symbol, data in ops:
      if symbol == class_name:
        self.classmap[data[0]] = defn
    super(IndexVisitor, self).enter_ClassDef(node)

  def enter_FunctionDef(self, node):
    fn_def = self.add_local_def(node, doc=DocString.from_node(node))
    env = self.add_scope(node)
    params = [self.add_local_def(v) for v in node.args.args]
    for i, param in enumerate(params):
      self.kythe.add_edge(
          source=self.kythe.vname(fn_def.to_signature()),
          edge_name="param.%d" % i,
          target=self.kythe.vname(param.to_signature()))
    if env.cls:
      if (not has_decorator(node, "classmethod") and
          not has_decorator(node, "staticmethod")):
        # Don't crash if we have buggy code like
        # class A(): def f(): ...
        if params:
          env.self_var = params[0]

  def visit_Name(self, node):
    # We use pytype trace data to distinguish between local and global
    # variables.
    if isinstance(node.ctx, ast.Load):
      ops = self.traces[node.lineno]
      for op, symbol, data in ops:
        if symbol == node.id:
          if op == "LOAD_GLOBAL":
            ref = self.add_global_ref(node, name=symbol, data=data)
            self.typemap[ref.id] = data
            break
          elif op in ["LOAD_FAST", "LOAD_NAME"]:
            ref = self.add_local_ref(node, name=symbol, data=data)
            self.typemap[ref.id] = data
            break
          elif op in ["LOAD_DEREF"]:
            ref = self.add_closure_ref(node, name=symbol, data=data)
            self.typemap[ref.id] = data
            break

    elif isinstance(node.ctx, ast.Store):
      ops = self.traces[node.lineno]
      for op, symbol, data in ops:
        if symbol == node.id:
          if op == "STORE_GLOBAL":
            defn = self.add_global_def(node, name=symbol)
            self.typemap[defn.id] = data
            break
          elif op in ["STORE_FAST", "STORE_NAME", "STORE_DEREF"]:
            defn = self.add_local_def(node, name=symbol)
            self.typemap[defn.id] = data
            break
    return node.id

  def visit_Call(self, node):
    if isinstance(node.func, str):
      name = node.func
    else:
      name = node.func.id
    if "." in name:
      basename = name.split(".")[-1]
    else:
      basename = name
    ops = [x for x in self.traces[node.lineno]
           if x[0].startswith("CALL_FUNCTION")]
    seen = set()
    for _, symbol, data in ops:
      if symbol == basename:
        for d in data:
          if not isinstance(d, list):
            d = [d]
          for d1 in d:
            for f in qualified_method(d1):
              if f not in seen:
                self.add_call(node, name, f)
                seen.add(f)
    return name

  def visit_Assign(self, node):
    for v in node.targets:
      if isinstance(v, ast.Attribute):
        self.add_attr(v)

  def visit_Attribute(self, node):
    ops = self.traces[node.lineno]
    for op, symbol, data in ops:
      if symbol == node.attr and op in ["LOAD_ATTR"]:
        ref = self.add_local_ref(
            node,
            target=node.value,
            name=node.value + "." + symbol,
            data=data)
        if data and len(data) == 2:
          _, rhs = data
          self.typemap[ref.id] = rhs
        break
      elif symbol == node.attr and op in ["STORE_ATTR"]:
        defn = self.add_local_def(node)
        if self.current_class:
          # We only support attr definitions within a class definition.
          self.current_env.setattr(node.attr, defn)
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
              self.modules[d.scope + "." + mod] = mod

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

  def __init__(self, source, resolved_modules, module_name):
    self.source = source
    self.resolved_modules = resolved_modules
    self.module_name = module_name
    self.traces = source.traces
    self.defs = None
    self.locs = None
    self.refs = None
    self.envs = None
    self.modules = None
    self.typemap = None
    self.classmap = None
    self.calls = None
    self.kythe = None
    self._links = []  # for debugging purposes

  def index(self, code_ast):
    """Index an AST corresponding to self.source."""

    v = IndexVisitor(self.source, self.module_name)
    v.visit(code_ast)
    self.defs = v.defs
    self.locs = v.locs
    self.refs = v.refs
    self.envs = v.envs
    self.modules = v.modules
    self.typemap = v.typemap
    self.classmap = v.classmap
    self.calls = v.calls
    self.kythe = v.kythe

  def get_def_offsets(self, defloc):
    """Get the byte offsets for a definition."""

    defn = self.defs[defloc.def_id]
    typ = defn.typ
    if typ == "Attribute":
      start, end = self._get_attr_bounds(defn.name, defloc.location)
    else:
      line, col = defloc.location
      start = self.source.get_offset(line, col)
      if typ in DEF_OFFSETS:
        start += DEF_OFFSETS[typ]
      end = start + len(defn.name)
    return (start, end)

  def get_doc_offsets(self, doc):
    """Get the byte offsets for a docstring."""

    line, col = doc.location
    start = self.source.get_offset(line, col)
    end = start + doc.length
    return (start, end)

  def finalize(self):
    """Postprocess the information gathered by the tree visitor.

    Note that these functions need to be run in order; some of them depend on
    information generated by previous ones.
    """

    links = self._lookup_refs()
    self._links = links
    self._process_deflocs()
    self._process_links(links)
    self._process_calls(links)

  def _process_deflocs(self):
    """Generate kythe edges for definitions."""

    for def_id in self.locs:
      defn = self.defs[def_id]
      for defloc in self.locs[def_id]:
        defn = self.defs[defloc.def_id]
        defn_vname = self.kythe.vname(defn.to_signature())
        start, end = self.get_def_offsets(defloc)
        anchor_vname = self.kythe.add_anchor(start, end)
        self.kythe.add_fact(
            source=defn_vname,
            fact_name="node/kind",
            fact_value=defn.node_kind())
        self.kythe.add_edge(
            source=anchor_vname,
            target=defn_vname,
            edge_name="defines/binding")

        # Emit a docstring if we have one.
        doc = defn.doc
        if doc:
          doc_vname = self.kythe.vname(defn.doc_signature())
          start, end = self.get_doc_offsets(defn.doc)
          anchor_vname = self.kythe.add_anchor(start, end)
          self.kythe.add_fact(
              source=doc_vname,
              fact_name="node/kind",
              fact_value="doc")
          self.kythe.add_fact(
              source=doc_vname,
              fact_name="text",
              fact_value=doc.text)
          self.kythe.add_edge(
              source=anchor_vname,
              target=doc_vname,
              edge_name="defines")
          self.kythe.add_edge(
              source=doc_vname,
              target=defn_vname,
              edge_name="documents")

  def _get_attr_bounds(self, name, location):
    """Calculate the anchor bounds for an attr access."""
    # TODO(mdemello): This is pretty crude, and does not for example take into
    # account multiple calls of the same attribute in a line. It is just to get
    # our tests passing till we incorporate asttokens.
    lineno, col = location
    line = self.source.line(lineno)
    attr = name.split(".")[-1]
    offset = line.index("." + attr) - col + 1
    start, end = self.get_anchor_bounds(location, len(attr))
    return (start + offset, end + offset)

  def get_anchor_bounds(self, location, length):
    """Generate byte offsets from a location and length."""

    line, col = location
    start = self.source.get_offset(line, col)
    end = start + length
    return (start, end)

  def get_ref_bounds(self, ref):
    if ref.typ == "Attribute":
      return self._get_attr_bounds(ref.name, ref.location)
    else:
      return self.get_anchor_bounds(ref.location, len(ref.name))

  def _make_defn_vname(self, defn):
    """Convert a definition into a kythe vname."""
    if isinstance(defn, Remote):
      remote = defn.module
      if remote in self.resolved_modules:
        path = self.resolved_modules[remote].filename
        if path.endswith(".pyi"):
          path = path[:-1]
        sig = "module." + defn.name
        return self.kythe.vname(sig, path)
      else:
        # Don't generate vnames for unresolved modules
        return None
    else:
      return self.kythe.vname(defn.to_signature())

  def _process_links(self, links):
    """Generate kythe edges for references."""

    for ref, defn in links:
      if not isinstance(defn, (Definition, Remote, Module)):
        # TODO(mdemello): Fixes needed for chained method calls.
        continue
      start, end = self.get_ref_bounds(ref)
      vname = self.kythe.add_anchor(start, end)
      target = self._make_defn_vname(defn)
      if target:
        self.kythe.add_edge(
            source=vname,
            target=target,
            edge_name="ref")

  def _process_calls(self, links):
    """Generate kythe edges for function calls.

    Checks if a function call corresponds to a resolved reference, and generates
    a ref/call to that references's source definition if so.

    Args:
      links: A list of (reference, definition) tuples.
    """

    link_map = collections.defaultdict(list)
    for ref, defn in links:
      link_map[ref.location].append((ref, defn))

    for call in self.calls:
      call_links = link_map[call.location]
      call_ref = None
      call_defn = None
      for ref, d in call_links:
        if ref.name == call.name:
          call_ref = ref
          call_defn = d
          break
      if call_defn:
        target = self._make_defn_vname(call_defn)
        if target:
          start, end = self.get_ref_bounds(call_ref)
          anchor_vname = self.kythe.anchor_vname(start, end)
          self.kythe.add_edge(
              source=anchor_vname,
              target=target,
              edge_name="ref/call")
          # The call is a child of the enclosing function/class (this lets us
          # generate call graphs).
          if ref.scope != "module":
            parent_defn = self.defs.get(call_ref.scope)
            if parent_defn:
              # TODO(mdemello): log the 'else' case; it should never happen.
              self.kythe.add_edge(
                  source=anchor_vname,
                  target=self.kythe.vname(parent_defn.to_signature()),
                  edge_name="childof")
            else:
              assert False, ref

  def _lookup_remote_symbol(self, ref, defn):
    """Try to look up a definition in an imported module."""

    if defn.id in self.modules:
      remote = self.modules[defn.id]
      resolved = True
    elif defn.typ in ["Import", "ImportFrom"]:
      # Allow unresolved modules too.
      remote = defn.name
      resolved = False
    else:
      return None
    name = ref.name
    if name.startswith(remote):
      name = name[(len(remote) + 1):]
    return Remote(module=remote, name=name, resolved=resolved)

  def _lookup_class_attr(self, name, attr):
    """Look up a class attribute in the environment."""

    env = self.envs["module"]
    if name not in env.env:
      return None
    d = env.env[name]
    class_env = self.envs[d.id]
    _, defn = class_env.lookup(attr)
    return defn

  def _get_attribute_class(self, obj):
    """Look up the class of an attribute target."""

    if isinstance(obj, abstract.Module):
      return Module(obj.name)
    elif isinstance(obj, abstract.InterpreterClass):
      return self.classmap.get(obj)
    elif isinstance(obj, abstract.PyTDClass):
      if obj.module:
        return Remote(obj.module, obj.name, resolved=True)
      else:
        # Corner case: a namedtuple in the MRO of a class will generate a
        # PyTDClass even though it's in the current module.
        # TODO(mdemello): We need special handling for namedtuples to generate
        # and populate a class.
        return None
    else:
      return None

  def _get_mro(self, obj):
    if isinstance(obj, abstract.InterpreterClass):
      return obj.mro
    elif isinstance(obj, abstract.Instance):
      return obj.cls.mro
    else:
      return []

  def _is_pytype_module(self, obj):
    return isinstance(obj, abstract.Module)

  def _lookup_attribute_by_type(self, r, attr_name):
    """Look up an attribute using pytype annotations."""

    lhs, _ = r.data
    links = []
    for l in lhs:
      if self._is_pytype_module(l):
        lookup = [l]
      else:
        lookup = self._get_mro(l)
      for pytype_cls in lookup:
        cls = self._get_attribute_class(pytype_cls)
        if cls:
          if isinstance(cls, Definition):
            env = self.envs[cls.id]
            _, attr_value = env.lookup(attr_name)
            if not attr_value and isinstance(l, abstract.Instance):
              try:
                attr_value = env.getattr(attr_name)
              except AttrError:
                # We will walk up the MRO if we can't find anything.
                continue
            if attr_value:
              links.append((r, attr_value))
              break
          elif isinstance(cls, (Module, Remote)):
            links.append((r, cls.attr(attr_name)))
            break
    return links

  def _lookup_refs(self):
    """Look up references to generate links."""

    links = []

    for r in self.refs:
      if r.typ == "Attribute":
        attr_name = r.name.split(".")[-1]
        defs = self._lookup_attribute_by_type(r, attr_name)
        if defs:
          links.extend(defs)
          continue
        else:
          env = self.envs[r.scope]
          env, defn = env.lookup(r.target)
          if defn:
            # See if this is a definition from an imported module first.
            remote = self._lookup_remote_symbol(r, defn)
            if remote:
              links.append((r, remote))
            else:
              # See if we can figure out the class of a bound attribute from the
              # typemap.
              typ = self.typemap.get(defn.id)
              if typ:
                for x in PytypeValue.from_data(typ):
                  if isinstance(x, Remote):
                    links.append((r, x.attr(attr_name)))
                  elif x.typ == "Class":
                    d = self._lookup_class_attr(x.name, attr_name)
                    if d:
                      links.append((r, d))
                    else:
                      # Fall back to <module>.<name>
                      links.append((r, x))
                  else:
                    links.append((r, x))
              else:
                links.append((r, defn))
      else:
        try:
          env, defn = self.envs[r.scope].lookup(r.name)
        except KeyError:
          env, defn = None, None

        if defn:
          links.append((r, defn))
        else:
          data = PytypeValue.from_data(r.data)
          if data:
            for x in data:
              links.append((r, x))

    return links


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

  major, minor = options.python_version
  if major == 2:
    # python2.7 is the only supported py2 version.
    a = ast27.parse(src, options.input)
    ast = ast27
  else:
    a = ast3.parse(src, options.input, feature_version=minor)
    ast = ast3

  # TODO(mdemello): Get from args
  module_name = "module"
  source = SourceFile(src, vm.opcode_traces, filename=options.input)
  ix = Indexer(source, vm.loader.get_resolved_modules(), module_name)
  ix.index(a)
  ix.finalize()
  return ix
