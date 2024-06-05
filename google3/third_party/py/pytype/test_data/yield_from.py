# Tests python 3.5 opcodes
#   GET_YIELD_FROM_ITER
#   YIELD_FROM
def chain(*iters):
  for it in iters:
    yield from it
