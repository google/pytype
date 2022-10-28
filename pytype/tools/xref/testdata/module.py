# pylint: skip-file
#- File.node/kind file
#- File childof Mod
#- Mod=vname(":module:", _, _, _, _).node/kind package

# The first byte in the module is tagged as defining the module.
# (Idea copied from the typescript indexer)
#- ModAnchor.node/kind anchor
#- ModAnchor./kythe/loc/start 0
#- ModAnchor./kythe/loc/end 0
#- ModAnchor defines/implicit Mod

X = 42
