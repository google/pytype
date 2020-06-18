# pylint: skip-file

#- @os ref/imports ModuleOs
import os
#- @os ref/imports ModuleOs
#- @alias defines/binding OsAlias
#- OsAlias.node/kind variable
#- OsAlias.subkind import
#- OsAlias aliases ModuleOs
import os as alias

#- @"os.path" ref/imports ModuleOsPath
import os.path
#- @os ref ModuleOs
#- @path ref ModuleOsPath
os.path.exists

#- @path ref/imports ModuleOsPath
from os import path
#- @path ref ModuleOsPath
path.exists
