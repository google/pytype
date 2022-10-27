# pylint: skip-file

#- @A defines/binding ClassA
#- ClassA.node/kind record
#- ClassA.subkind class
class A:
  pass

#- @B defines/binding BTAlias
#- BTAlias.node/kind talias
B = A

#- @C defines/binding CTAlias
#- CTAlias.node/kind talias
C = int

#- @D defines/binding DTAlias
#- DTAlias.node/kind talias
D = C

#- @Y defines/binding YTAlias
#- YTAlias.node/kind talias
Y = list[int]

#- @U defines/binding UTAlias
#- UTAlias.node/kind talias
U = list[B]

#- @x defines/binding XVar
#- XVar.node/kind variable
#- !{ XVar.node/kind talias}
x = A()

#- @q defines/binding QVar
#- QVar.node/kind variable
#- !{ QVar.node/kind talias}
q = x
