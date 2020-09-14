"""Code related to sequence merging and MRO."""

from pytype.pytd import pytd


def MergeSequences(seqs):
  """Merge a sequence of sequences into a single sequence.

  This code is copied from https://www.python.org/download/releases/2.3/mro/
  with print statements removed and modified to take a sequence of sequences.
  We use it to merge both MROs and class templates.

  Args:
    seqs: A sequence of sequences.

  Returns:
    A single sequence in which every element of the input sequences appears
    exactly once and local precedence order is preserved.

  Raises:
    ValueError: If the merge is impossible.
  """
  res = []
  while True:
    if not any(seqs):  # any empty subsequence left?
      return res
    for seq in seqs:  # find merge candidates among seq heads
      if not seq:
        continue
      cand = seq[0]
      if getattr(cand, "SINGLETON", False):
        # Special class. Cycles are allowed. Emit and remove duplicates.
        seqs = [[s for s in seq if s != cand] for seq in seqs]  # pylint: disable=g-complex-comprehension
        break
      if any(s for s in seqs if cand in s[1:] and s is not seq):
        cand = None  # reject candidate
      else:
        # Remove and emit. The candidate can be head of more than one list.
        for other_seq in seqs:
          if other_seq and other_seq[0] == cand:
            del other_seq[0]
        break
    if cand is None:
      raise ValueError
    res.append(cand)


def Dedup(seq):
  """Return a sequence in the same order, but with duplicates removed."""
  seen = set()
  result = []
  for s in seq:
    if s not in seen:
      result.append(s)
    seen.add(s)
  return result


class MROError(Exception):  # pylint: disable=g-bad-exception-name

  def __init__(self, seqs):
    super().__init__()
    self.mro_seqs = seqs


def MROMerge(input_seqs):
  """Merge a sequence of MROs into a single resulting MRO.

  Args:
    input_seqs: A sequence of MRO sequences.

  Returns:
    A single resulting MRO.

  Raises:
    MROError: If we discovered an illegal inheritance.
  """
  seqs = [Dedup(s) for s in input_seqs]
  try:
    return MergeSequences(seqs)
  except ValueError as e:
    raise MROError(input_seqs) from e


def _GetClass(t, lookup_ast):
  if t.cls:
    return t.cls
  if lookup_ast:
    return lookup_ast.Lookup(t.name)
  raise AttributeError("Class not found: %s" % t.name)


def _Degenerify(types):
  return [t.base_type if isinstance(t, pytd.GenericType) else t for t in types]


def _ComputeMRO(t, mros, lookup_ast):
  """Compute the MRO."""
  if isinstance(t, pytd.ClassType):
    if t not in mros:
      mros[t] = None
      parent_mros = []
      for parent in _GetClass(t, lookup_ast).parents:
        if parent in mros:
          if mros[parent] is None:
            raise MROError([[t]])
          else:
            parent_mro = mros[parent]
        else:
          parent_mro = _ComputeMRO(parent, mros, lookup_ast)
        parent_mros.append(parent_mro)
      mros[t] = tuple(
          MROMerge([[t]] + parent_mros + [_Degenerify(
              _GetClass(t, lookup_ast).parents)]))
    return mros[t]
  elif isinstance(t, pytd.GenericType):
    return _ComputeMRO(t.base_type, mros, lookup_ast)
  else:
    return [t]


def GetBasesInMRO(cls, lookup_ast=None):
  """Get the given class's bases in Python's method resolution order."""
  mros = {}
  parent_mros = []
  for p in cls.parents:
    parent_mros.append(_ComputeMRO(p, mros, lookup_ast))
  return tuple(MROMerge(parent_mros + [_Degenerify(cls.parents)]))
