# Development process

<!--ts-->
   * [Development process](#development-process)
      * [GitHub](#github)
      * [Running pytype locally](#running-pytype-locally)
      * [Debugging](#debugging)
      * [Profiling](#profiling)

<!-- Added by: mdemello, at: 2020-08-10T13:15-07:00 -->

<!--te-->

## GitHub

1. Fork https://github.com/google/pytype.

1. Follow the [instructions][source-install-instructions] for installing from
   source, using your fork instead of the original repository. Now the `pytype`
   and `pytype-single` command-line tools are running from your local copy of
   the pytype source code. Make sure to use `pip install -e .` so that the tools
   will automatically pick up code edits.

1. Make your change, adding [tests][tests-readme-oss] as appropriate.

1. Make sure the code still passes all [tests][tests-readme-oss] and is free of
   [lint][pylint] and [type][pytype-quickstart] errors.

1. Push your change to your fork and open a PR against the original repo. If
   it's your first time contributing to a Google open source project, please
   sign the Contributor License Agreement when prompted. Depending on what files
   your PR touches, it will be either merged directly or closed after being
   copied into the Google-internal codebase and re-exported to GitHub. You will
   be credited as the author either way.

## Running pytype locally

Run the single-file analysis tool as

```shell
pytype-single some_file.py
```

to check `some_file.py` for type errors, or

```shell
pytype-single some_file.py -o -
```

to infer a pyi (dumped to stdout via `-`). The default target Python
version is the version that pytype is running under; pass in `-V<major>.<minor>`
to select a different version.

Note that the single-file tool does not handle dependency resolution, so
you'll have to supply .pyi files for all non-stdlib imports.

If you're using the GitHub-installed tools, you can run the whole-project
analysis tool, `pytype`, over the file to generate a `.pytype` directory that
includes the necessary .pyi files. Then add

```shell
--module-name <module> --imports_info .pytype/imports/<module>.imports
```

to your `pytype-single` invocation, replacing `<module>` with the fully
qualified module name.

## Debugging

Use the `--verbosity` (or `-v`) option to print debugging output. The possible
values range from -1 ("quiet", log nothing) to 4 ("debug", log everything).

pytype can be run under [pdb][pdb], the Python debugger. Add:

```python
import pdb; pdb.set_trace()
```

at the point in the code at which you want to enter debugging.

## Profiling

For profiling a single file, pass in `--profile <path>` to turn on profiling and
write the generated profile to `<path>`. The profile can then be analyzed using
the [`pstats`][pstats] module.

Note that numbers are not directly comparable between runs; differences of 100%
for different machines on otherwise identical code have happened. The relative
rank of functions in the profile is stable between runs.

<!-- General references -->
[pdb]: https://docs.python.org/3/library/pdb.html
[pylint]: http://pylint.pycqa.org/en/latest/
[pytype-quickstart]: https://github.com/google/pytype#quickstart
[pstats]: https://docs.python.org/3/library/profile.html#module-pstats
[source-install-instructions]: https://github.com/google/pytype#installing
[tests-readme-oss]: https://github.com/google/pytype/blob/master/pytype/tests/README.md
