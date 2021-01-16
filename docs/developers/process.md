# Development process

<!--* freshness: { owner: 'rechen' reviewed: '2020-12-08' } *-->

<!--ts-->
   * [Development process](#development-process)
      * [GitHub](#github)
      * [Issue tracker](#issue-tracker)
      * [Running pytype locally](#running-pytype-locally)
      * [Debugging](#debugging)
      * [Profiling](#profiling)

<!-- Added by: rechen, at: 2021-01-15T16:04-08:00 -->

<!--te-->

## GitHub

1. Fork https://github.com/google/pytype and clone your fork to your machine.

1. Follow the instructions in [CONTRIBUTING.md][contributing-md] for building
   and testing pytype.

1. Make your change! Make sure the tests pass, and linting and type-checking are
   clean.

1. Push your change to your fork and open a pull request (PR) against the
   original repo. If it's your first time contributing to a Google open source
   project, please sign the Contributor License Agreement when prompted.
   Depending on what files your PR touches, it will be either merged directly or
   closed after being copied into the Google-internal codebase and re-exported
   to GitHub. You will be credited as the author either way.

## Issue tracker

Externally, pytype uses the [GitHub issue tracker][github-issues] for issue
management. You can filter by the [good first issue][good-first-issues] label to
find issues friendly to new contributors. Please comment on an issue before
starting any work, to avoid duplication of effort. When opening a PR to close an
issue, include the following in the description to
[close the issue][pr-keywords] when the PR is merged:

```
Resolves #XXX
```

(Replace `XXX` with the issue ID.) If a PR is relevant to an issue but doesn't
fix it, you can link the two by mentioning the ID without the closing keyword.

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
[contributing-md]: https://github.com/google/pytype/blob/master/CONTRIBUTING.md
[github-issues]: https://github.com/google/pytype/issues
[good-first-issues]: https://github.com/google/pytype/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22
[pdb]: https://docs.python.org/3/library/pdb.html
[pr-keywords]: https://docs.github.com/en/github/managing-your-work-on-github/linking-a-pull-request-to-an-issue#linking-a-pull-request-to-an-issue-using-a-keyword
[pylint]: http://pylint.pycqa.org/en/latest/
[pytype-quickstart]: https://github.com/google/pytype#quickstart
[pstats]: https://docs.python.org/3/library/profile.html#module-pstats
[source-install-instructions]: https://github.com/google/pytype#installing
[tests-readme-oss]: https://github.com/google/pytype/blob/master/pytype/tests/README.md
