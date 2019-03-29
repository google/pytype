# pylint: skip-file

#- Mod=vname(":module:", _, _, _, _).node/kind record

# The first byte in the module is tagged as defining the module.
# (Idea copied from the typescript indexer)
#- ModAnchor.node/kind anchor
#- ModAnchor./kythe/loc/start 0
#- ModAnchor./kythe/loc/end 1
#- ModAnchor defines/binding Mod

X = 42
