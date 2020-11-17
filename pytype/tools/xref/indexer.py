"""Generate cross references from a project."""

import collections
import re
from typing import Optional

import attr

from pytype import abstract
from pytype import analyze
from pytype import config
from pytype import errors
from pytype import io
from pytype import load_pytd
from pytype import module_utils
from pytype.ast import visitor as ast_visitor
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors
from pytype.tools.traces import source
from pytype.tools.traces import traces

from pytype.tools.xref import callgraph
from pytype.tools.xref import utils as xref_utils
from pytype.tools.xref import node_utils

from typed_ast import ast27 as ast27
from typed_ast import ast3


# A mapping of offsets between a node's start position and the symbol being
# defined. e.g. in the declaration "class X" the X is at +6 from the start.
DEF_OFFSETS = {
    "ClassDef": 6,  # class X
    "FunctionDef": 4,  # def f
}


# Marker for a link to a file rather than a node within the file.
IMPORT_FILE_MARKER = "<__FILE__>"


# Marker to capture a pending return value while traversing an AST
_RETURNING_NAME = "RETURNING NAME"


def qualified_method(data):
  """Fully qualify a method call with its class scope."""
  if isinstance(data, abstract.BoundFunction):
    return data.repr_names()
  else:
    return [data.name]


def get_location(node):
  # TODO(mdemello): The column offset for nodes like "class A" needs to be
  # adjusted to the start of the symbol.
  return source.Location(node.lineno, node.col_offset)


def match_opcodes(opcode_traces, lineno, op_match_list):
  """Get all opcodes matching op_match_list on a given line.

  Args:
    opcode_traces: traces
    lineno: line number to get ops from.
    op_match_list: [(opcode_name, symbol|None), ...]; None matches any symbol.

  Returns:
    A list of matching opcodes.
  """
  out = []
  for op, symbol, data in opcode_traces[lineno]:
    for match_op, match_symbol in op_match_list:
      if op == match_op and match_symbol in [None, symbol]:
        out.append((op, symbol, data))
  return out


def match_opcodes_multiline(opcode_traces, start, end, op_match_list):
  """Get all opcodes matching op_match_list in a range of lines."""
  out = []
  for line in range(start, end + 1):
    out.extend(match_opcodes(opcode_traces, line, op_match_list))
  return out


def _unwrap(data):
  assert len(data) == 1
  return data[0]


# Internal datatypes


class AttrError(Exception):
  pass


@attr.s
class PytypeValue:
  """Stores a value inferred by pytype."""

  module = attr.ib()
  name = attr.ib()
  typ = attr.ib()
  id = attr.ib(default=None, init=False)

  def __attrs_post_init__(self):
    self.id = self.module + "." + self.name

  def format(self):
    return "%s { %s.%s : %s }" % (
        self.id, self.module, self.typ, self.name)

  @classmethod
  def _from_data(cls, data):
    """Construct a PytypeValue from a single datum."""

    if isinstance(data, abstract.PyTDClass):
      if data.module:
        # If we have a remote reference, return Remote rather than PytypeValue.
        return Remote(data.module, data.name, resolved=True)
      else:
        # This is a namedtuple or some other special case pytype has generated a
        # local PyTDClass for. We need special cases for them too.
        return None
    elif isinstance(data, abstract.Module):
      return Remote(data.name, IMPORT_FILE_MARKER, resolved=True)
    elif isinstance(data, abstract.InterpreterClass):
      return cls("module", data.name, "Class")
    elif isinstance(data, abstract.BoundFunction):
      # TODO(mdemello): Handle multiple class bindings.
      name = data.repr_names(callself_repr=node_utils.typename)[0]
      return cls("module", name, "BoundFunction")
    else:
      # TODO(mdemello): We need to infer the module here.
      return cls("module", str(data), node_utils.typename(data))

  @classmethod
  def from_data(cls, data):
    """Construct a PytypeValue from a list of data."""

    if not data:
      return None
    else:
      return [cls._from_data(x) for x in data]

  def to_signature(self):
    return self.module + "." + self.name

  @property
  def typename(self):
    return self.to_signature()


@attr.s
class Module:
  """Module representation."""
  name = attr.ib()

  def attr(self, attr_name):
    return Remote(self.name, attr_name, resolved=True)

  def submodule(self, attr_name):
    name = self.name + "." + attr_name
    return Remote(name, IMPORT_FILE_MARKER, resolved=True)


@attr.s
class DocString:
  """Store the text and location of a docstring."""

  text = attr.ib()
  location = attr.ib()
  length = attr.ib()

  @classmethod
  def from_node(cls, ast, node):
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


@attr.s
class Definition:
  """A symbol definition.

  Attributes:
    name: The symbol name
    typ: The definition type (e.g. ClassDef)
    data: Pytype data from the opcode traces
    scope: The namespace id (e.g. module:class A:function f:x)
    target: The LHS of an attribute (e.g. for x.foo, target = typeof(x))
    doc: The docstring, if any, for function and class defs
    id: The id
  """

  name = attr.ib()
  typ = attr.ib()
  data = attr.ib()
  scope = attr.ib()
  target = attr.ib()
  doc = attr.ib()
  id = attr.ib(default=None, init=False)

  def __attrs_post_init__(self):
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

  def subkind(self) -> Optional[str]:
    if self.typ == "Import" or self.typ == "ImportFrom":
      return "import"
    return None

  @property
  def typename(self):
    """The fully qualified type of the object the definition is bound to."""
    if self.data and self.data[0]:
      d = self.data[0][0]
      if d.cls:
        return d.cls.full_name
      else:
        return "typing.Any"
    else:
      return "typing.Any"


@attr.s
class Remote:
  """A symbol from another module."""

  module = attr.ib()
  name = attr.ib()
  resolved = attr.ib()
  id = attr.ib(default=None, init=False)
  typ = attr.ib(default=None, init=False)

  def __attrs_post_init__(self):
    self.id = self.module + "/module." + self.name

  def attr(self, attr_name):
    return Remote(self.module, self.name + "." + attr_name, self.resolved)

  def format(self):
    return self.id

  @property
  def typename(self):
    name = self.name.split(".")[0]
    return self.module + "." + name


@attr.s
class DefLocation:
  """A location of a symbol definition.

  Attributes:
    def_id: The definition id (scope + name)
    location: The location of the definition in the source code.

  Note that a single definition can have multiple locations, for symbols that
  are redefined in the code.
  """

  def_id = attr.ib()
  location = attr.ib()


@attr.s
class FunctionParam:
  """A link between a function def and the defs of its params."""

  def_id = attr.ib(type=str)
  param_id = attr.ib(type=str)
  position = attr.ib(type=int)


@attr.s
class Reference:
  """A symbol holding a reference to a definition.

  Attributes:
    name: The symbol name
    typ: The symbol type (e.g. Attribute)
    data: The pytype data attached to the symbol
    scope: The namespace id (e.g. module.A.f)
    ref_scope: The namespace id of the referred symbol (if we can determine it)
    target: The LHS of an attribute (e.g. for x.foo, target = typeof(x))
    location: The line and column of the symbol in the source code
    id: The id
  """

  name = attr.ib()
  typ = attr.ib()
  data = attr.ib()
  scope = attr.ib()
  ref_scope = attr.ib()
  target = attr.ib()
  location = attr.ib()
  id = attr.ib(default=None, init=False)

  def __attrs_post_init__(self):
    self.id = self.scope + "." + self.name

  def format(self):
    return self.id


@attr.s
class NameArg:
  """Representation of a single-variable function call argument."""

  name = attr.ib()
  type = attr.ib()


@attr.s
class ExprArg:
  """Representation of an expression function call argument."""

  names = attr.ib()
  type = attr.ib()


@attr.s
class Funcall:
  """Representation of a function call."""

  name = attr.ib()
  scope = attr.ib()
  func = attr.ib()
  location = attr.ib()
  args = attr.ib()
  return_type = attr.ib()


class Env:
  """A collection of namespaced symbols."""

  def __init__(self, ast, scope, parent, cls):
    """Initialize an environment.

    Arguments:
      ast: An ast module
      scope: The namespace key (e.g. module:class A:function f)
      parent: The env of the directly enclosing namespace
      cls: The class currently being defined
           (None if we are not in a class definition)

    Other attributes defined:
      env: The dictionary holding the symbol table for this environment
      attrs: Attributes defined on the current class
      self_var: The `self` variable in method definitions
      ret: The `return` variable for functions
    """

    self.ast = ast
    self.scope = scope
    self.parent = parent
    self.cls = cls
    self.env = {}
    self.attrs = None
    self.self_var = parent and parent.self_var
    self.ret = None

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
        isinstance(node, self.ast.Attribute) and
        isinstance(node.value, self.ast.Name) and
        node.value.id == self.self_var.name)

  def getattr(self, attrib):
    if self.attrs is not None and attrib in self.attrs:
      return self.attrs[attrib]
    elif self.cls and self.cls.scope != self.scope:
      return self.cls.getattr(attrib)
    else:
      raise AttrError("called getattr in non-class context")

  def setattr(self, attrib, value):
    if self.attrs is not None:
      self.attrs[attrib] = value
    elif self.cls is not None:
      return self.cls.setattr(attrib, value)
    else:
      raise AttrError("called setattr in non-class context")


# pylint: disable=invalid-name
# pylint: disable=missing-docstring
#
# Visitors use generated method names that don't follow the pylint spec.
# Also names like visit_Name are self-documenting and do not need docstrings.


class ScopedVisitor(ast_visitor.BaseVisitor):
  """An AST node visitor that keeps track of scopes and environments.

  A "scope" is the abstract namespace (represented by a string key that tracks
  the nested path of namespaces from the module root, e.g. module:class A:f).
  An "environment" holds data for the current scope. self.envs is not
  hierarchical, it's just a flat mapping of scope keys to environments.
  """

  # TODO(mdemello): Is the two-level visitor hierarchy really buying us
  # anything by way of maintainability or readability?

  def __init__(self, ast, module_name, **kwargs):
    super().__init__(ast=ast, **kwargs)  # pytype: disable=wrong-keyword-args
    self.stack = []
    self.class_ids = []
    self.envs = {}
    self.module_name = module_name

  def get_id(self, node):
    """Construct an id based on node type."""

    c = node.__class__
    if c == self._ast.FunctionDef:
      return node.name
    elif c == self._ast.ClassDef:
      return node.name
    elif c == self._ast.Module:
      return self.module_name
    else:
      raise Exception("Unexpected scope: %r" % node)

  def iprint(self, x):
    """Print messages indented by scope level, for debugging."""
    print("  " * len(self.stack), x)

  def scope_id(self):
    return ".".join(self.get_id(x) for x in self.stack)

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
    new_env = Env(ast=self._ast,
                  scope=new_scope,
                  parent=parent,
                  cls=self.current_class)
    if is_class:
      new_env.attrs = {}
    self.envs[new_scope] = new_env
    return new_env

  def enter_ClassDef(self, node):
    new_env = self.add_scope(node, is_class=True)
    self.class_ids.append(self.scope_id())
    # We need to set the env's cls to the new class, not the enclosing one.
    new_env.cls = self.current_class

  def leave_ClassDef(self, _):
    self.class_ids.pop()

  def enter_FunctionDef(self, node):
    self.add_scope(node)

  def enter_Module(self, node):
    super().enter_Module(node)  # pytype: disable=attribute-error
    self.add_scope(node)

  def leave(self, node):
    """If the node has introduced a new scope, we need to pop it off."""
    super().leave(node)
    if node == self.stack[-1]:
      self.stack.pop()


class IndexVisitor(ScopedVisitor, traces.MatchAstVisitor):
  """Visitor that generates indexes."""

  def __init__(self, ast, src, module_name):
    super().__init__(ast=ast, src_code=src, module_name=module_name)
    self.defs = {}
    self.locs = collections.defaultdict(list)
    self.refs = []
    self.modules = {}
    self.aliases = {}
    self.source = src
    self.traces = src.traces
    self.typemap = {}
    self.classmap = {}
    self.calls = []
    self.function_params = []

  def _get_location(self, node, args):
    """Get a more accurate node location."""

    loc = None

    if isinstance(node, self._ast.ClassDef):
      # For class and function definitions, search for the string
      #   (class|def) <name>
      # between the start of the AST node and the start of the body. Handles the
      # offset for decorated functions/classes.
      body_start = node.body[0].lineno
      text = "class %s" % args["name"]
      loc = self.source.find_first_text(node.lineno, body_start, text)
    elif isinstance(node, self._ast.FunctionDef):
      body_start = node.body[0].lineno
      text = "def %s" % args["name"]
      loc = self.source.find_first_text(node.lineno, body_start, text)

    if loc is None:
      loc = get_location(node)

    return loc

  def _get_node_name(self, node):
    if isinstance(node, str):
      # We replace nodes with their names after visiting them.
      return node
    return super()._get_node_name(node)

  def make_def(self, node, **kwargs):
    """Make a definition from a node."""

    if isinstance(node, self._ast.Name):
      t = node_utils.typename(node.ctx)
    elif isinstance(node, self._ast.arg):
      t = "Param"
    else:
      t = node_utils.typename(node)
    args = {
        "name": node_utils.get_name(node, self._ast),
        "scope": self.scope_id(),
        "typ": t,
        "data": None,
        "target": None,
        "doc": None,
    }
    args.update(kwargs)
    defn = Definition(**args)
    line, col = self._get_location(node, args)
    assert line is not None
    defloc = DefLocation(defn.id, source.Location(line, col))
    return (defn, defloc)

  def make_ref(self, node, **kwargs):
    """Make a reference from a node."""

    assert "data" in kwargs  # required kwarg
    args = {
        "name": node_utils.get_name(node, self._ast),
        "scope": self.scope_id(),
        "ref_scope": None,
        "typ": node_utils.typename(node),
        "location": get_location(node),
        "target": None,
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
    name = node_utils.get_name(node, self._ast)
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

  def add_call(self, node, name, func, arg_varnames, return_type):
    self.calls.append(
        Funcall(name, self.scope_id(), func, get_location(node), arg_varnames,
                return_type))

  def add_attr(self, node):
    defn, _ = self.make_def(node)
    self.defs[defn.id] = defn
    env = self.envs[self.scope_id()]
    if env.is_self_attr(node):
      self.envs[self.scope_id()].setattr(node.attr, defn)

  def _has_decorator(self, f, decorator):
    for d in f.decorator_list:
      if isinstance(d, self._ast.Name) and d.id == decorator:
        return True
    return False

  def enter_ClassDef(self, node):
    class_name = node_utils.get_name(node, self._ast)
    last_line = max(node.lineno, node.body[0].lineno - 1)

    # Python2
    ops = match_opcodes_multiline(self.traces, node.lineno, last_line, [
        ("BUILD_CLASS", class_name)
    ])
    d = None
    if ops:
      _, _, data = ops[0]
      d = _unwrap(data)
    else:
      # Python3
      ops = match_opcodes_multiline(self.traces, node.lineno, last_line, [
          ("LOAD_BUILD_CLASS", None),
          ("STORE_NAME", class_name),
          # Classes defined within a function generate a STORE_FAST op.
          ("STORE_FAST", class_name),
          # A class being declared global anywhere generates a STORE_GLOBAL op.
          ("STORE_GLOBAL", class_name),
      ])
      # pytype sometimes analyses this twice, leading to duplicate opcode
      # traces. We only want the first two in the list.
      if (len(ops) >= 2 and
          ops[0][0] == "LOAD_BUILD_CLASS" and
          ops[1][0] in ("STORE_NAME", "STORE_FAST", "STORE_GLOBAL")):
        _, _, data = ops[1]
        d = _unwrap(data)

    assert d, "Did not get pytype data for class %s" % class_name
    defn = self.add_local_def(node, data=data,
                              doc=DocString.from_node(self._ast, node))
    self.classmap[d[0]] = defn
    super().enter_ClassDef(node)

  def enter_FunctionDef(self, node):
    last_line = max(node.lineno, node.body[0].lineno - 1)
    ops = match_opcodes_multiline(self.traces, node.lineno, last_line, [
        ("MAKE_FUNCTION", None),  # py2 has no symbol, py3 has node.name
        ("LOAD_CLOSURE", None)  # Nested functions
    ])
    if ops:
      _, _, data = ops[0]
    else:
      # TODO(mdemello): Add an assert; this should not happen but I would rather
      # not break grok indexing if it does.
      data = None
    fn_def = self.add_local_def(node, data=data,
                                doc=DocString.from_node(self._ast, node))
    env = self.add_scope(node)
    # TODO(mdemello): Get pytype data for params
    params = [self.add_local_def(v) for v in node.args.args]
    for i, param in enumerate(params):
      self.function_params.append(FunctionParam(
          def_id=fn_def.id, param_id=param.id, position=i))
    if env.cls:
      if (not self._has_decorator(node, "classmethod") and
          not self._has_decorator(node, "staticmethod")):
        # Don't crash if we have buggy code like
        # class A(): def f(): ...
        if params:
          env.self_var = params[0]

  def visit_Name(self, node):
    # We ignore the location returned by match() because we'll recompute the
    # same location anyways.
    # We use pytype trace data to distinguish between local and global
    # variables.
    for unused_loc, (op, symbol, data) in self.match(node):
      d = _unwrap(data)
      ref = None
      if op == "LOAD_GLOBAL":
        ref = self.add_global_ref(node, name=symbol, data=data)
        self.typemap[ref.id] = d
      elif op in ["LOAD_FAST", "LOAD_NAME"]:
        ref = self.add_local_ref(node, name=symbol, data=data)
        self.typemap[ref.id] = d
      elif op in ["LOAD_DEREF"]:
        ref = self.add_closure_ref(node, name=symbol, data=data)
        self.typemap[ref.id] = d
      elif op == "STORE_GLOBAL":
        defn = self.add_global_def(node, name=symbol, data=data)
        self.typemap[defn.id] = d
      elif op in ["STORE_FAST", "STORE_NAME", "STORE_DEREF"]:
        defn = self.add_local_def(node, name=symbol, data=data)
        self.typemap[defn.id] = d
      if ref and self.current_env.ret == _RETURNING_NAME:
        self.current_env.ret = ref

    return node.id

  def visit_Call(self, node):
    name = self._get_node_name(node)
    # We have replaced Name() in args with the corresponding string
    arg_varnames = [x for x in node.args if isinstance(x, str)]
    seen = set()
    for _, (_, _, data) in self.match(node):
      call, return_type = data
      if call is None:
        continue
      for d in call:
        for f in qualified_method(d):
          if f not in seen:
            self.add_call(node, name, f, arg_varnames, return_type)
            seen.add(f)
    return name

  def visit_Assign(self, node):
    for v in node.targets:
      if isinstance(v, self._ast.Attribute):
        self.add_attr(v)

  def visit_Attribute(self, node):
    node_str = self._get_node_name(node)
    # match() returns the location of the attribute, whereas the indexer needs
    # the location of the value on which the attribute is accessed, in order to
    # link function calls. We'll manually adjust the location later.
    for unused_loc, (op, unused_symbol, data) in self.match(node):
      if op in ("LOAD_ATTR", "LOAD_METHOD"):
        ref = self.add_local_ref(
            node,
            target=node.value,
            name=node_str,
            data=data)
        if len(data) == 2:
          _, rhs = data
          self.typemap[ref.id] = rhs
      elif op == "STORE_ATTR":
        defn = self.add_local_def(node)
        if self.current_class:
          # We only support attr definitions within a class definition.
          self.current_env.setattr(node.attr, defn)
    return node_str

  def visit_Subscript(self, node):
    return node.value

  def visit_DictComp(self, _node):
    return "<expr>"

  def visit_ListComp(self, _node):
    return "<expr>"

  def process_import(self, node):
    """Common code for Import and ImportFrom."""

    for alias, (loc, (op, symbol, data)) in zip(node.names, self.match(node)):
      # If an import is aliased, match() returns only the symbol/loc of
      # the alias, whereas the indexer also needs access to the unaliased
      # name in order to reference the imported module.
      defn = None  # type: Optional[Definition]
      if alias.asname:
        defn = self.add_local_def(
            node, name=symbol, target=alias.name, data=data)
        defloc = self.locs[defn.id].pop()
        self.locs[defn.id].append(DefLocation(defloc.def_id, loc))

        # Shift symbol/loc back to the unaliased name.
        symbol = alias.name
        m = re.search("[ ,]" + symbol + r"\b", self.source.line(loc.line))
        if m is None:
          # TODO(slebedev): Support multi-line from-imports.
          continue
        c, _ = m.span()
        loc = source.Location(loc.line, c + 1)

      try:
        [imported] = _unwrap(data)
      except (TypeError, ValueError):
        resolved = False
      else:
        resolved = not isinstance(imported, abstract.Unsolvable)

      if not resolved:
        continue

      if op == "STORE_NAME":
        # for |import x.y as z| or |from x import y as z| we want {z: x.y}
        self.add_local_ref(node, name=symbol, data=data, location=loc)
        if not isinstance(imported, abstract.Module):
          # Make the from-imported symbol available in the current namespace.
          remote = Remote(imported.module, name=symbol, resolved=True)
          if defn:
            self.aliases[defn.id] = remote
          self.current_env[symbol] = remote
          self.typemap[remote.id] = [imported]
          continue

        if defn:
          remote = Remote(imported.full_name, IMPORT_FILE_MARKER, resolved=True)
          self.aliases[defn.id] = remote
          self.modules[defn.id] = imported.full_name
        else:
          self.modules[self.scope_id() + "." + symbol] = imported.full_name
      elif op == "IMPORT_NAME":
        # |import x.y| puts both {x: x} and {x.y: x.y} in modules
        self.add_local_ref(node, name=symbol, data=data, location=loc)
        # TODO(slebedev): Reference every import path component.
        # For example here
        #
        #   from foo.bar import boo
        #   import foo.bar.boo
        #
        # we should reference both foo and foo.bar (in addition to foo.bar.boo).
        for mod in module_utils.get_all_prefixes(symbol):
          self.modules[self.scope_id() + "." + mod] = mod

  def visit_Import(self, node):
    self.process_import(node)

  def visit_ImportFrom(self, node):
    self.process_import(node)

  def enter_Return(self, node):
    if isinstance(node.value, self._ast.Name):
      self.current_env.ret = _RETURNING_NAME

  def leave_Return(self, node):
    if self.current_env.ret == _RETURNING_NAME:
      self.current_env.ret = None


# pylint: enable=invalid-name
# pylint: enable=missing-docstring


class Indexer:
  """Runs the indexer visitor and collects its results."""

  def __init__(self,
               *,
               ast,
               src,
               loader,
               pytd_module,
               module_name):
    self.ast = ast
    self.source = src
    self.loader = loader
    self.pytd_module = pytd_module
    self.resolved_modules = loader.get_resolved_modules()
    self.imports = xref_utils.process_imports_map(loader.imports_map)
    self.module_name = module_name
    self.traces = src.traces
    self.defs = None
    self.locs = None
    self.refs = None
    self.envs = None
    self.modules = None
    self.aliases = None
    self.typemap = None
    self.classmap = None
    self.calls = None
    self.links = []
    self.function_params = None
    self.function_map = None

    # Optionally preserve the pytype vm so we can access the types later
    self.vm = None

  def index(self, code_ast):
    """Index an AST corresponding to self.source."""

    v = IndexVisitor(self.ast, self.source, self.module_name)
    v.visit(code_ast)
    self.defs = v.defs
    self.locs = v.locs
    self.refs = v.refs
    self.envs = v.envs
    self.modules = v.modules
    self.aliases = v.aliases
    self.typemap = v.typemap
    self.classmap = v.classmap
    self.calls = v.calls
    self.function_params = v.function_params

  def get_def_offsets(self, defloc):
    """Get the byte offsets for a definition."""

    defn = self.defs[defloc.def_id]
    typ = defn.typ
    if typ == "Attribute":
      start, end = self._get_attr_bounds(defn.name, defloc.location)
    else:
      start = self.source.get_offset(defloc.location)
      if typ in DEF_OFFSETS:
        start += DEF_OFFSETS[typ]
      end = start + len(defn.name)
    return (start, end)

  def get_doc_offsets(self, doc):
    """Get the byte offsets for a docstring."""

    start = self.source.get_offset(doc.location)
    end = start + doc.length
    return (start, end)

  def finalize(self):
    """Postprocess the information gathered by the tree visitor."""
    self.links = self._lookup_refs()

  def _get_attr_bounds(self, name, location):
    """Calculate the anchor bounds for an attr access."""
    return self.get_anchor_bounds(
        *self.source.get_attr_location(name, location))

  def get_anchor_bounds(self, location, length):
    """Generate byte offsets from a location and length."""

    start = self.source.get_offset(location)
    end = start + length
    return (start, end)

  def get_ref_bounds(self, ref):
    if ref.typ == "Attribute":
      return self._get_attr_bounds(ref.name, ref.location)
    else:
      return self.get_anchor_bounds(ref.location, len(ref.name))

  def _lookup_remote_symbol(self, defn, attr_name):
    """Try to look up a definition in an imported module."""
    if defn.id in self.modules:
      return Remote(self.modules[defn.id], name=attr_name, resolved=True)

    if not (defn.typ == "Import" or defn.typ == "ImportFrom"):
      return None

    try:
      [imported] = _unwrap(defn.data)
    except (TypeError, ValueError):
      resolved = False
    else:
      resolved = not isinstance(imported, abstract.Unsolvable)

    if not resolved:
      return Remote(defn.name, name=attr_name, resolved=False)

    assert not isinstance(imported, abstract.Module)
    assert defn.target
    remote = Remote(imported.module, name=defn.target, resolved=True)
    return remote.attr(attr_name)

  def _lookup_class_attr(self, name, attrib):
    """Look up a class attribute in the environment."""

    env = self.envs["module"]
    if name not in env.env:
      return None
    d = env.env[name]
    class_env = self.envs[d.id]
    _, defn = class_env.lookup(attrib)
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

    lhs, rhs = r.data
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
          elif isinstance(cls, Module):
            # Probably extra-cautious about rhs not being a single binding, but
            # better to check than crash here.
            if len(rhs) == 1 and self._is_pytype_module(rhs[0]):
              # e.g. import x.y; a = x.y
              links.append((r, cls.submodule(attr_name)))
            else:
              links.append((r, cls.attr(attr_name)))
            break
          elif isinstance(cls, Remote):
            links.append((r, cls.attr(attr_name)))
            break
    return links

  def _lookup_refs(self):
    """Look up references to generate links."""

    links = []

    for r in self.refs:
      if r.typ == "Attribute":
        attr_name = r.name.rsplit(".", 1)[-1]
        defs = self._lookup_attribute_by_type(r, attr_name)
        if defs:
          links.extend(defs)
          continue
        else:
          env = self.envs[r.scope]
          env, defn = env.lookup(r.target)
          if defn:
            # See if this is a definition from an imported module first.
            remote = self._lookup_remote_symbol(defn, attr_name)
            if remote:
              links.append((r, remote))
            else:
              # See if we can figure out the class of a bound attribute from the
              # typemap.
              typ = self.typemap.get(defn.id)
              if typ:
                for x in PytypeValue.from_data(typ):
                  if x is None:
                    continue  # Not-yet-special-cased type, e.g. namedtuple.
                  elif isinstance(x, Remote):
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
      elif r.typ == "Import" or r.typ == "ImportFrom":
        [imported] = _unwrap(r.data)
        if isinstance(imported, abstract.Module):
          name = IMPORT_FILE_MARKER
          if r.name in self.resolved_modules:
            module = r.name
          else:
            module = imported.full_name
        else:
          assert imported.module
          name = r.name
          module = imported.module

        links.append((r, Remote(module, name=name, resolved=True)))
      else:
        try:
          env, defn = self.envs[r.scope].lookup(r.name)
        except KeyError:
          env, defn = None, None

        if defn:
          links.append((r, defn))
        else:
          data = PytypeValue.from_data(_unwrap(r.data))
          if data:
            for x in data:
              links.append((r, x))

    return links

  def get_pytd_def(self, data, name):
    assert self.vm, "Indexer vm has not been preserved."
    node = self.vm.root_cfg_node
    return self.vm.convert.pytd_convert.value_to_pytd_def(node, data, name)

  def get_pytd(self, datum):
    if not datum:
      return pytd.AnythingType()
    t = pytd_utils.JoinTypes(v.to_type() for v in datum).Visit(
        visitors.RemoveUnknownClasses())
    return self.loader.resolve_type(t, self.pytd_module)

  def make_serializable(self):
    """Delete all data that cannot be pickled."""
    for r in self.refs:
      r.target = None
      r.data = None

    for d in self.defs.values():
      d.data = None

    for call in self.calls:
      call.return_type = None

    for a in self.aliases.values():
      a.data = None

    for r, d in self.links:
      r.data = None
      d.data = None

    # This is all internal data used when building up the final index; if any of
    # it proves to be needed we can look at just stripping out the non-picklable
    # bits, or converting it to a final form in finalize()
    self.ast = None
    self.pytd_module = None
    self.source = None
    self.loader = None
    self.resolved_modules = None
    self.imports = None
    self.traces = None
    self.modules = None
    self.typemap = None
    self.classmap = None
    self.envs = None
    self.function_params = None
    self.calls = None


class PytypeError(Exception):
  """Wrap exceptions raised by the indexer."""


class VmTrace(source.AbstractTrace):

  def __repr__(self):
    types_repr = tuple(
        t and [node_utils.typename(x) for x in t]
        for t in self.types)
    return "%s %s" % (super().__repr__(), types_repr)


def process_file(options, source_text=None, generate_callgraphs=False,
                 preserve_pytype_vm=False):
  """Process a single file and return cross references.

  Args:
    options: A dictionary of pytype options.
    source_text: Optional text of the file; will be read from the file pointed
      to by options.input if not supplied.
    generate_callgraphs: Collect call graph information
    preserve_pytype_vm: Preserve the pytype vm in the indexer

  Returns:
    The Indexer object used for indexing.

  Raises:
    PytypeError if pytype fails.
  """
  with config.verbosity_from(options):
    errorlog = errors.ErrorLog()
    loader = load_pytd.create_loader(options)
    src = source_text or io.read_source_file(options.input)
    vm = analyze.CallTracer(
        errorlog=errorlog,
        options=options,
        generate_unknowns=options.protocols,
        store_all_calls=True,
        loader=loader)
    with io.wrap_pytype_exceptions(PytypeError, filename=options.input):
      pytd_module, _ = analyze.infer_types(
          src=src,
          filename=options.input,
          errorlog=errorlog,
          options=options,
          loader=loader,
          tracer_vm=vm)

  major, minor = options.python_version
  if major == 2:
    # python2.7 is the only supported py2 version.
    ast_root_node = ast27.parse(src, options.input)
    ast = ast27
  else:
    ast_root_node = ast3.parse(src, options.input, feature_version=minor)
    ast = ast3

  # TODO(mdemello): Get from args
  module_name = "module"
  src_code = source.Code(src, vm.opcode_traces, VmTrace, filename=options.input)
  ix = Indexer(ast=ast,
               src=src_code,
               loader=vm.loader,
               module_name=module_name,
               pytd_module=pytd_module)
  ix.index(ast_root_node)
  ix.finalize()

  # Make the vm available via indexer.vm for post-finalize() functions.
  ix.vm = vm

  # Use the indexer as a single object to hold data for calling processes.
  if generate_callgraphs:
    ix.function_map = callgraph.collect_function_map(ix)

  # Release the vm before returning
  if not preserve_pytype_vm:
    ix.vm = None

  return ix
