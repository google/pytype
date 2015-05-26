"""Solver for type equations."""

import logging

from pytype.pytd import abc_hierarchy
from pytype.pytd import booleq
from pytype.pytd import pytd
from pytype.pytd import type_match
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import visitors

log = logging.getLogger(__name__)

# How deep to nest type parameters
# TODO(kramm): Currently, the solver only generates variables for depth 1.
MAX_DEPTH = 1

is_unknown = type_match.is_unknown
is_partial = type_match.is_partial
is_complete = type_match.is_complete


class FlawedQuery(Exception):
  """Thrown if there is a fundamental flaw in the query."""
  pass


class TypeSolver(object):
  """Class for solving ~unknowns in type inference results."""

  def __init__(self, ast):
    self.pytd = ast

  def match_unknown_against_complete(self, matcher,
                                     solver, unknown, complete):
    """Given an ~unknown, match it against a class.

    Args:
      matcher: An instance of pytd.type_match.TypeMatch.
      solver: An instance of pytd.booleq.Solver.
      unknown: The unknown class to match
      complete: A complete class to match against. (E.g. a built-in or a user
        defined class)
    Returns:
      An instance of pytd.booleq.BooleanTerm.
    """

    assert is_unknown(unknown)
    assert is_complete(complete)
    type_params = {p.type_param: matcher.type_parameter(unknown, complete, p)
                   for p in complete.template}
    subst = type_params.copy()
    implication = matcher.match_Class_against_Class(unknown, complete, subst)
    if implication is not booleq.FALSE and type_params:
      # If we're matching against a templated class (E.g. list<T>), record the
      # fact that we'll also have to solve the type parameters.
      for param in type_params.values():
        solver.register_variable(param.name)
    solver.implies(booleq.Eq(unknown.name, complete.name), implication)

  def match_partial_against_complete(self, matcher, solver, partial, complete):
    """Match a partial class (call record) against a complete class.

    Args:
      matcher: An instance of pytd.type_match.TypeMatch.
      solver: An instance of pytd.booleq.Solver.
      partial: The partial class to match. The class name needs to be prefixed
        with "~" - the rest of the name is typically the same as complete.name.
      complete: A complete class to match against. (E.g. a built-in or a user
        defined class)
    Returns:
      An instance of pytd.booleq.BooleanTerm.
    Raises:
      FlawedQuery: If this call record is incompatible with the builtin.
    """
    assert is_partial(partial)
    assert is_complete(complete)
    # Types recorded for type parameters in the partial builtin are meaningless,
    # since we don't know which instance of the builtin used them when.
    subst = {p.type_param: pytd.AnythingType() for p in complete.template}
    formula = matcher.match_Class_against_Class(partial, complete, subst)
    if formula is booleq.FALSE:
      raise FlawedQuery("%s can never be %s" % (partial.name, complete.name))
    solver.always_true(formula)

  def match_call_record(self, matcher, solver, call_record, complete):
    assert is_partial(call_record)
    assert is_complete(complete)
    formula = (
        matcher.match_FunctionWithSignatures_against_FunctionWithSignatures(
            call_record, complete, {}))
    if formula is booleq.FALSE:
      raise FlawedQuery("%s can never be %s" % (call_record.name,
                                                complete.name))
    solver.always_true(formula)

  def get_all_subclasses(self):
    """Compute a class->subclasses mapping.

    Returns:
      A dictionary, mapping instances of pytd.TYPE (types) to lists of
      pytd.Class (the derived classes).
    """
    hierarchy = self.pytd.Visit(visitors.ExtractSuperClasses())
    hierarchy = {cls: [superclass for superclass in superclasses
                       if (hasattr(superclass, "name") and
                           is_complete(superclass))]
                 for cls, superclasses in hierarchy.items()
                 if is_complete(cls)}
    # typically this is a fairly short list, e.g.:
    #  [ClassType(basestring), ClassType(int), ClassType(object)]
    return abc_hierarchy.Invert(hierarchy)

  def solve(self):
    """Solve the equations generated from the pytd.

    Returns:
      A dictionary (str->str), mapping unknown class names to known class names.
    Raises:
      AssertionError: If we detect an internal error.
    """
    unprocessed = set(self.pytd.classes)
    solver = booleq.Solver()
    factory = type_match.TypeMatch(self.get_all_subclasses())

    # TODO(kramm): We should do prefiltering of the left and right side, and
    # then only loop over the combinations we actually want to compare.
    for cls1 in self.pytd.classes:
      assert not (is_unknown(cls1) and is_complete(cls1)), cls1
      unprocessed.remove(cls1)  # Only use class once, either left or right.
      if is_unknown(cls1):
        solver.register_variable(cls1.name)
      elif is_complete(cls1):
        solver.register_value(cls1.name)
      for cls2 in unprocessed:
        if is_unknown(cls1) and is_unknown(cls2):
          pass  # Don't do identity between unknowns - pytype takes care of that
        elif is_complete(cls1) and is_complete(cls2):
          assert cls1.name != cls2.name, cls1.name
        elif not (is_complete(cls1) or is_complete(cls2)):
          assert cls1.name != cls2.name, cls1.name
        elif is_unknown(cls1) and is_complete(cls2):
          self.match_unknown_against_complete(factory, solver, cls1, cls2)
        elif is_complete(cls1) and is_unknown(cls2):
          self.match_unknown_against_complete(factory, solver, cls2, cls1)
        elif not is_complete(cls1) and is_complete(cls2):
          if type_match.unpack_name_of_partial(cls1.name) == cls2.name:
            self.match_partial_against_complete(factory, solver, cls1, cls2)
        elif is_complete(cls1) and not is_complete(cls2):
          if type_match.unpack_name_of_partial(cls2.name) == cls1.name:
            self.match_partial_against_complete(factory, solver, cls2, cls1)
        elif (is_unknown(cls1) and
              not is_complete(cls2) or
              is_unknown(cls2) and
              not is_complete(cls1)):
          pass  # We don't match unknowns against partial classes
        elif (is_partial(cls1) and not is_partial(cls2) and
              type_match.unpack_name_of_partial(cls1.name) != cls2.name):
          pass  # unrelated classes
        elif (not is_partial(cls1) and is_partial(cls2) and
              cls1.name != type_match.unpack_name_of_partial(cls2.name)):
          pass  # unrelated classes
        else:  # COV_NF_LINE
          raise AssertionError("%r %r" % (cls1.name, cls2.name))  # COV_NF_LINE

    unprocessed = set(self.pytd.functions)
    for f1 in frozenset(self.pytd.functions):
      unprocessed.remove(f1)
      for f2 in unprocessed:
        if (is_partial(f1) and
            type_match.unpack_name_of_partial(f1.name) == f2.name):
          self.match_call_record(factory, solver, f1, f2)
        elif (is_partial(f2) and
              type_match.unpack_name_of_partial(f2.name) == f1.name):
          self.match_call_record(factory, solver, f2, f1)

    log.info("=========== to solve =============\n%s", solver)
    log.info("=========== to solve (end) =============")
    return solver.solve()


def solve(ast, builtins_pytd):
  """Solve the unknowns in a pytd AST using the standard Python builtins.

  Args:
    ast: A pytd.TypeDeclUnit, containing classes named ~unknownXX.
    builtins_pytd: A pytd for builtins.

  Returns:
    A dictionary (str->str), mapping unknown class names to known class names.
  """
  builtins_pytd = pytd_utils.RemoveMutableParameters(builtins_pytd)
  combined = pytd_utils.Concat(builtins_pytd, ast)
  combined = visitors.LookupClasses(combined, overwrite=True)
  return TypeSolver(combined).solve()


def extract_local(ast):
  """Extract all classes that are not unknowns of call records of builtins."""
  return pytd.TypeDeclUnit(
      name=ast.name,
      classes=tuple(cls for cls in ast.classes
                    if is_complete(cls)),
      functions=tuple(f for f in ast.functions
                      if is_complete(f)),
      constants=tuple(c for c in ast.constants
                      if is_complete(c)),
      modules=())


def convert_string_type(string_type, unknown, mapping, global_lookup, depth=0):
  """Convert a string representing a type back to a pytd type."""
  try:
    # Check whether this is a type declared in a pytd.
    cls = global_lookup.Lookup(string_type)
    base_type = pytd.ClassType(cls.name, cls)
  except KeyError:
    # If we don't have a pytd for this type, it can't be a template.
    cls = None
    base_type = pytd.NamedType(string_type)

  if cls and cls.template:
    parameters = []
    for t in cls.template:
      type_param_name = unknown + "." + string_type + "." + t.name
      if type_param_name in mapping and depth < MAX_DEPTH:
        string_type_params = mapping[type_param_name]
        parameters.append(convert_string_type_list(
            string_type_params, unknown, mapping, global_lookup, depth + 1))
      else:
        parameters.append(pytd.AnythingType())
    if len(parameters) == 1:
      return pytd.HomogeneousContainerType(base_type, tuple(parameters))
    else:
      return pytd.GenericType(base_type, tuple(parameters))
  else:
    return base_type


def convert_string_type_list(types_as_string, unknown, mapping,
                             global_lookup, depth=0):
  """Like convert_string_type, but operate on a list."""
  return pytd_utils.JoinTypes(convert_string_type(type_as_string, unknown,
                                                  mapping, global_lookup, depth)
                              for type_as_string in types_as_string)


def insert_solution(result, mapping, global_lookup):
  """Replace ~unknown types in a pytd with the actual (solved) types."""
  subst = {
      unknown: convert_string_type_list(types_as_strings, unknown,
                                        mapping, global_lookup)
      for unknown, types_as_strings in mapping.items()}
  # TODO(kramm): The below takes over 11s for pytree.py
  return result.Visit(visitors.ReplaceTypes(subst))


def convert_pytd(ast, builtins_pytd):
  """Convert pytd with unknowns (structural types) to one with nominal types."""
  # builtins_pytd = pytd_utils.RemoveMutableParameters(builtins_pytd)
  builtins_pytd = builtins_pytd.Visit(visitors.ClassTypeToNamedType())
  mapping = solve(ast, builtins_pytd)
  log_info_mapping(mapping)
  result = extract_local(ast)
  if log.isEnabledFor(logging.INFO):
    log.info("=========== solve result =============\n%s", pytd.Print(result))
    log.info("=========== solve result (end) =============")
  lookup = pytd_utils.Concat(builtins_pytd, result)
  result = insert_solution(result, mapping, lookup)
  return result


def log_info_mapping(mapping):
  """Print a raw type mapping. For debugging."""
  if log.isEnabledFor(logging.INFO):
    cutoff = 12
    log.info("=========== (possible types) ===========")
    for unknown, possible_types in sorted(mapping.items()):
      assert isinstance(possible_types, (set, frozenset))
      if len(possible_types) > cutoff:
        log.info("%s can be   %s, ... (total: %d)", unknown,
                 ", ".join(sorted(possible_types)[0:cutoff]),
                 len(possible_types))
      else:
        log.info("%s can be %s", unknown,
                 ", ".join(sorted(possible_types)))
    log.info("=========== (end of possible types) ===========")
