The `out` directory is to be used as CMake's binary directory. That is, one
should invoke CMake from this directory as follows:

```
cd out
cmake ../ [-G Ninja]
```

Having an explicit `out` directory prevents polluting the main source tree
with build artifacts.
