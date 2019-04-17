# pylint: skip-file

#- @import defines/binding ImportXY
#- ImportXY.node/kind variable
import x.y
#- @import defines/binding ImportPQ
#- ImportPQ.node/kind variable
import p.q

#- @import defines/binding ImportBar
#- ImportBar.node/kind variable
from foo import bar
#- @import defines/binding ImportQuux
#- ImportQuux.node/kind variable
from foo import baz as quux
