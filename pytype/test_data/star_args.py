stuff = {('a', 'b'): 666}


def foo(*key):
  p = stuff.get(key)
  if p is not None:
    return p
  return -123


def bar():
  return foo('a', 'b')


print bar()
