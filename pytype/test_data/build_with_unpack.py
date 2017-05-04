# Tests python 3.5 opcodes
#   BUILD_LIST_UNPACK
#   BUILD_MAP_UNPACK
#   BUILD_MAP_UNPACK_WITH_CALL
#   BUILD_SET_UNPACK
#   BUILD_TUPLE_UNPACK

a = [1,2,3,4]
b = [1,2,3,4]
c = {'1':2, '3':4}
d = {'5':6, '7':8}
e = {'9':10, 'B':12}

def f(**kwargs):
  print(kwargs)

p = [*a, *b]  # BUILD_LIST_UNPACK
q = {*a, *b}  # BUILD_SET_UNPACK
r = (*a, *b)  # BUILD_TUPLE_UNPACK
s = {**c, **d}  # BUILD_MAP_UNPACK
f(**c, **d, **e)  # BUILD_MAP_UNPACK_WITH_CALL

