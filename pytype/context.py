"""Container of things that should be accessible to all abstract values."""

import contextlib
from typing import Dict, List, Tuple

from pytype import annotation_utils
from pytype import attribute
from pytype import config
from pytype import convert
from pytype import errors
from pytype import load_pytd
from pytype import matcher
from pytype import output
from pytype import special_builtins
from pytype import tracer_vm
from pytype.abstract import abstract
from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils


class Context:
  """An abstract context."""

  def __init__(
      self,
      errorlog: errors.ErrorLog,
      options: config.Options,
      loader: load_pytd.Loader,
      generate_unknowns=False,
      store_all_calls=False,
  ):
    # Inputs
    self.errorlog = errorlog
    self.options = options
    self.python_version: Tuple[int, int] = self.options.python_version
    self.loader = loader
    self.generate_unknowns = generate_unknowns
    self.store_all_calls = store_all_calls

    # Typegraph
    self.program = cfg.Program()
    self.root_node: cfg.CFGNode = self.program.NewCFGNode("root")
    self.program.entrypoint = self.root_node
    # Represents the program exit. Needs to be set before analyze_types.
    self.exitpoint: cfg.CFGNode = None

    # Helper classes/modules
    self.vm = tracer_vm.CallTracer(self)
    self.annotation_utils = annotation_utils.AnnotationUtils(self)
    self.attribute_handler = attribute.AbstractAttributeHandler(self)
    self.converter_minimally_initialized = False
    self.convert = convert.Converter(self)
    self.pytd_convert = output.Converter(self)
    self.program.default_data = self.convert.unsolvable

    # Other context
    self.callself_stack: List[cfg.Variable] = []
    # Map from builtin names to canonical objects.
    self.special_builtins: Dict[str, abstract.BaseValue] = {
        # The super() function.
        "super": self.convert.super_type,
        # The object type.
        "object": self.convert.object_type,
        # for more pretty branching tests.
        "__random__": self.convert.primitive_class_instances[bool],
        # for debugging
        "reveal_type": special_builtins.RevealType(self),
        # boolean values.
        "True": self.convert.true,
        "False": self.convert.false,
        # builtin classes
        "property": special_builtins.Property(self),
        "staticmethod": special_builtins.StaticMethod(self),
        "classmethod": special_builtins.ClassMethod(self),
        "dict": special_builtins.Dict(self),
    }
    # builtin functions
    for cls in (
        special_builtins.Abs,
        special_builtins.AssertType,
        special_builtins.HasAttr,
        special_builtins.IsCallable,
        special_builtins.IsInstance,
        special_builtins.IsSubclass,
        special_builtins.Next,
    ):
      self.special_builtins[cls.name] = cls.make(self)
    # If set, allow construction of recursive values, setting the
    # self-referential field to Any
    self.recursion_allowed = False

  def matcher(self, node):
    return matcher.AbstractMatcher(node, self)

  @contextlib.contextmanager
  def allow_recursive_convert(self):
    old = self.recursion_allowed
    self.recursion_allowed = True
    try:
      yield
    finally:
      self.recursion_allowed = old

  def new_unsolvable(self, node):
    """Create a new unsolvable variable at node."""
    return self.convert.unsolvable.to_variable(node)

  def join_cfg_nodes(self, nodes):
    """Get a new node to which the given nodes have been joined."""
    assert nodes
    if len(nodes) == 1:
      return nodes[0]
    else:
      ret = self.program.NewCFGNode(self.vm.frame and
                                    self.vm.frame.current_opcode and
                                    self.vm.frame.current_opcode.line)
      for node in nodes:
        node.ConnectTo(ret)
      return ret

  def join_variables(self, node, variables):
    return cfg_utils.merge_variables(self.program, node, variables)

  def join_bindings(self, node, bindings):
    return cfg_utils.merge_bindings(self.program, node, bindings)
