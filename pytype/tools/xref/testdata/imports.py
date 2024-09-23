# pylint: skip-file

#- @#0os ref/imports ModuleOs
import os
#- @#0os ref/imports ModuleOs
#- @os_alias defines/binding OsAlias
#- OsAlias.node/kind variable
#- OsAlias.subkind import
#- OsAlias aliases ModuleOs

#- @"os.path" ref/imports ModuleOsPath
import os.path
#- @os ref ModuleOs
#- @path ref ModuleOsPath
os.path.exists

#- @path ref/imports ModuleOsPath
from os import path
#- @path ref ModuleOsPath
path.exists

#- @name ref OsName
os.name
#- @name ref/imports OsName

#- @name_alias defines/binding OsNameAlias
#- OsNameAlias.node/kind variable
#- OsNameAlias.subkind import
#- OsNameAlias aliases OsName
