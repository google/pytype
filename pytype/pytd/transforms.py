"""Functions and visitors for transforming pytd."""

import collections
import logging

from pytype.pytd import booleq
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import slots
from pytype.pytd import type_match
from pytype.pytd import visitors


class ExtractOperators(visitors.Visitor):
  """Visitor for retrieving all reversible operators."""

  def __init__(self, matcher):
    """Initialize this visitor.

    Args:
      matcher: A class with a "Match" method, used for matching function
        argument types.
    """
    super(ExtractOperators, self).__init__()
    # class name -> op name -> list of signatures
    self.operators = collections.defaultdict(
        lambda: collections.defaultdict(list))
    self._slots = slots.ReverseSlotMapping()
    self.matcher = matcher

  def EnterFunction(self, f):
    self.function_name = f.name
    self.unreversed_name = self._slots.get(self.function_name)

  def LeaveFunction(self, _):
    del self.function_name
    del self.unreversed_name

  def VisitTypeDeclUnit(self, _):
    return self.operators

  def _IsSubClass(self, x, y):
    """Transistively determine whether x is a proper subclass of y."""
    # "Proper subclass" so that if we have e.g. an __add__(self, Foo) and an
    # __radd__(self, Foo) on the same class Foo, the __add__ should still take
    # precedence.
    for parent in x.parents:
      if isinstance(parent, pytd.ClassType):
        if parent.cls is y or self._IsSubClass(parent.cls, y):
          return True
    return False

  def _HasOperator(self, left, op, right):
    """Determine whether the operator left <op> right is defined on left.

    Args:
      left: A pytd.Class.
      op: A string. Operator name. E.g. "__add__".
      right: A pytd.Class.

    Returns:
      True if this operator is defined on left. Reverse operators on right are
      ignored.
    """
    try:
      f = left.Lookup(op)
    except KeyError:
      return False
    # Now we know that the left side has e.g. an __add__(self, ...) method,
    # but we yet have to check whether it can do __add__(self, right)
    for sig in f.signatures:
      if (len(sig.params) >= 2 and
          self.matcher.Match(sig.params[1].type,
                             pytd.ClassType(right.name, right))):
        return True
    return False

  def _ShouldReplace(self, left, right, ltr, rtl):
    """Determine whether the reverse operator replaces the normal operator.

    Args:
      left: The left side of an operation. The x in x + y (A.k.a. __add__(x, y))
      right: The right side of an operation. The y in x + y (__radd__(x, y))
      ltr: A string. The normal ("left to right") operator. "__add__" etc.
      rtl: A string. The reverse ("right to left") operator. "__radd__" etc.

    Returns:
      True if the reverse operator takes precedence over the normal operator.
    """
    left_has_operator = self._HasOperator(left, ltr, right)
    right_has_operator = self._HasOperator(right, rtl, left)
    # Also see binary_op1 in Python/Objects/abstract.c:
    return (not left_has_operator or
            (right_has_operator and self._IsSubClass(right, left)))

  def EnterSignature(self, signature):
    """Parse a signature, and update self.operators.

    This will add the reverse of operators like __radd__ to self.operators for
    later processing by PreprocessReverseOperatorsVisitor.

    Args:
      signature: A pytd.Signature

    Returns:
      False, to indicate that we don't want this visitor to descend into the
      subtree of the signature.
    """
    if self.unreversed_name:
      assert len(signature.params) == 2
      left, right = signature.params[0], signature.params[1]
      if (isinstance(left.type, pytd.ClassType) and
          isinstance(right.type, pytd.ClassType)):
        if self._ShouldReplace(right.type.cls, left.type.cls,
                               self.unreversed_name, self.function_name):
          self.operators[right.type.cls][self.unreversed_name].append(
              signature.Replace(params=(right.Replace(name="self"),
                                        left.Replace(name="other"))))
        else:
          logging.warn("Ignoring %s on %s: %s has %s",
                       self.function_name, left.type.name,
                       right.type.name, self.unreversed_name)
      else:
        logging.warn("Unsupported %s operator on %s", self.function_name,
                     type(right).__name__)
    return False  # don't bother descending into this signature


class PreprocessReverseOperatorsVisitor(visitors.Visitor):
  """Visitor for turning __radd__ into __add__, etc.

  This will change
    class A:
      pass
    class B:
      def __radd__(self, A) -> C
  to
    class A:
      def __add__(self, B) -> C
    class B:
      pass
  .
  """

  def __init__(self):
    super(PreprocessReverseOperatorsVisitor, self).__init__()
    self._reversible_operator_names = slots.ReversibleOperatorNames()
    self._reverse_operator_names = slots.ReverseOperatorNames()

  def EnterTypeDeclUnit(self, unit):
    self.type_matcher = type_match.TypeMatch(pytd_utils.GetAllSubClasses(unit))
    self.methods_to_add = unit.Visit(ExtractOperators(self))

  def LeaveTypeDeclUnit(self, _):
    del self.type_matcher

  def _IsReverse(self, name):
    """Return True if name is a name like __radd__, __rmul__ etc."""
    return name in self._reverse_operator_names

  def Match(self, x, y):
    """True if it is legal to pass x as argument to a function accepting y."""
    return self.type_matcher.match_type_against_type(x, y, {}) == booleq.TRUE

  def _MatchSignature(self, sig1, sig2):
    return (len(sig1.params) == len(sig2.params) and
            all(self.Match(p1.type, p2.type)
                for p1, p2 in list(zip(sig1.params, sig2.params))[1:]))

  def VisitClass(self, cls):
    """Modify the methods of a class.

    This
      (a) removes all reverse operators from the class
      (b) adds the unreversed version of reverse operators from other classes.

    Args:
      cls: An instance of pytd.Class.
    Returns:
      A new class, with modified operators.
    """
    methods_to_add = self.methods_to_add[cls]
    new_methods = []
    method_names = (set(method.name for method in cls.methods) |
                    set(methods_to_add.keys()))
    for method_name in sorted(method_names):
      if method_name in self._reverse_operator_names:
        # This is a reverse operator (__radd__ etc.). We're going to add
        # the counterpiece (__add__), so we can throw away the original.
        continue
      try:
        method = cls.Lookup(method_name)
      except KeyError:
        method = pytd.Function(method_name, (), pytd.METHOD)
      # wrap the extra signatures into a method, for easier matching
      extra_signatures = methods_to_add.get(method_name, [])
      new_signatures = []
      if method_name in self._reversible_operator_names:
        # If this is a normal "unreversed" operator (__add__ etc.), see whether
        # one of signatures we got from the reversed operators takes precedence.
        for sig1 in method.signatures:
          if not any(self._MatchSignature(sig1, sig2)
                     for sig2 in extra_signatures):
            new_signatures.append(sig1)
      else:
        new_signatures.extend(method.signatures)
      new_methods.append(
          method.Replace(signatures=(
              tuple(new_signatures + extra_signatures))))
    return cls.Replace(methods=tuple(new_methods))


def RemoveMutableParameters(ast):
  """Change all mutable parameters in a pytd AST to a non-mutable form."""
  ast = ast.Visit(optimize.AbsorbMutableParameters())
  ast = ast.Visit(optimize.CombineContainers())
  ast = ast.Visit(optimize.MergeTypeParameters())
  ast = ast.Visit(visitors.AdjustSelf(force=True))
  return ast
