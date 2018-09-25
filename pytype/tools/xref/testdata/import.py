# pylint: skip-file

#- @"x.y" defines/binding ImportXY
#- @"p.q" defines/binding ImportPQ
#- ImportXY.node/kind variable
#- ImportPQ.node/kind variable
import x.y, p.q

#- @bar defines/binding ImportBar
#- @quux defines/binding ImportQuux
#- ImportBar.node/kind variable
#- ImportQuux.node/kind variable
from foo import bar, baz as quux
