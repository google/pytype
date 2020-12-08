# Configuring pytype

<!--*
freshness: { owner: 'mdemello' reviewed: '2020-12-04' }
*-->

<!--ts-->
   * [Configuring pytype](#configuring-pytype)
      * [Overview](#overview)
      * [The config.Options object](#the-configoptions-object)
      * [Setting options](#setting-options)
      * [Library-only options](#library-only-options)
      * [Config internals](#config-internals)
         * [Argument parsing](#argument-parsing)
         * [Postprocessing](#postprocessing)
      * [Adding a new option](#adding-a-new-option)
      * [Config files](#config-files)

<!-- Added by: rechen, at: 2020-12-07T20:53-08:00 -->

<!--te-->

## Overview

Pytype has a lot of knobs controlling its behaviour, and a fairly complex
configuration system to support setting and tweaking them. Fortunately, *using*
this system is relatively straightforward; the majority of developers should not
need to delve into the internals of the config implementation.

It is reasonable to wonder why the extra complexity for what is basically a
key/value dict. The main added features are (i) validating, processing and
expressing constraints between options, and (ii) allowing reuse and forwarding
of options from tools to pytype.

## The config.Options object

Pytype packs all its configuration options into a single Options object (defined
in `config.py`). This object can be constructed in one of two ways:

1. From a list of command line flags (typically `sys.argv`), e.g. in
   `single.py`:

   ```
   options = config.Options(sys.argv[1:], command_line=True)
   ```

2. By passing keyword args to `config.Options.create`:

   ```
   opts = config.Options.create(python_version=(3, 7), use_pickled_files=True)
   ```

In either case, options are validated, defaults filled in for any option not
supplied, and an `Options` object returned. The rest of the code uses this
single object, either via the vm (it's stored as `vm.options`) or by passing it
directly as a function argument. Options can be accessed as attributes, e.g.

```
if options.check_parameter_types:
  ...
```

## Setting options

The `options` object is intended to be created at the start of the pytype
invocation (either by passing command line flags to the executable, or by
creating a `config.Options` instance programmatically and passing it to one of
pytype's library entry points), and treated as an immutable singleton
thereafter. However it is useful in test code to be able to set and modify
options while testing different scenarios. The `Options` class provides an
`options.tweak(**kwargs)` method for that, allowing individual options to be
changed at "runtime".

One caveat is that unlike the `Options()` and `Options.create()` constructors,
`options.tweak()` simply sets attributes directly, bypassing the usual
postprocessing steps.


## Library-only options

The config system has some functions specifically to support tools that use
pytype as a library (i.e. they have no corresponding command-line flag defined
in the argument parser).

These are defined in two places:

1. The `_LIBRARY_ONLY_OPTIONS` hash, which currently contains a single option to
   replace the built-in `open()` function

2. Context managers (defined at the end of the file) to temporarily set an
   option and revert it when the managed block exits (again, there is currently
   a single option to temporarily override the logging verbosity).

NOTE: Libraries other than test code should not use `options.tweak()`, as this
can lead to invalid or inconsistent options; if your tool needs to temporarily
override another config setting send us a patch or a feature request to add a
setter or a context manager for it.


## Config internals

### Argument parsing

Command line arguments are parsed via `config.make_parser()`, which uses
python's `argparse` internally to define and parse options. The `argparse`
parser is wrapped in a `datatypes.ParserWrapper()` which records arguments as
they are added, but otherwise behaves entirely transparently.

Individual flags are defined via argparse's standard
`ArgumentParser.add_arguments` method; pytype divides these flags into argument
groups and provides functions to add all the arguments in a group to the option
parser. Thus pytype itself sets up its parser via

```
def make_parser():
  o = argparse.ArgumentParser(...)
  add_basic_options(o)
  add_subtools(o)
  add_pickle_options(o)
  add_infrastructure_options(o)
  add_debug_options(o)
  return o
```

but tools that wish to reuse and forward pytype flags can call any of the
`add_*` functions and populate their argument parser with a subset of pytype's
flags without needing to either define individial flags or support the entire
set of pytype options.

Look at `tools/arg_parser.py` for an example of how tools can set up their own
independent argument parser, and then add sections of pytype flags to it, using
those to create a `config.Options()` object that they use to invoke pytype
library functions.

### Postprocessing

In `config.Options.__init__`, after the Options object is populated with the
key/value pairs passed in to the constructor, it is run through a
postprocessing step. This invokes the `config.Postprocessor` class, which
copies options from the raw `input_options` to a final `output_options`. The
`Postprocessor` class does several things:

1. Define `_store_*()` methods, corresponding to some of the options. If
   `Postprocessor._store_foo()` exists, it will be called with `options.foo` as
   an argument; i.e.

   ```
   if hasattr(postprocessor, '_store_foo'):
     output_options.foo = postprocessor._store_foo(input_options.foo)
   else:
     output_options.foo = input_options.foo
   ```

2. Arrange the options into a dependency graph, so that some options can use the
   *postprocessed* values of other options in their own postprocessing step. For
   example, `options.module_name` is postprocessed via

   ```
   @uses(["input", "pythonpath"])
   def _store_module_name(self, module_name):
     if module_name is None:
       module_name = load_pytd.get_module_name(
       self.output_options.input,
       self.output_options.pythonpath)
       self.output_options.module_name = module_name
   ```

   where `self.output_options.pythonpath` is used to construct
   `self.output_options.module_name`. The postprocessor uses the
   `@uses["pythonpath"]` decorator to make sure that `_store_pythonpath()` is
   run before `_store_module_name`, so that `output_options.pythonpath` has the
   correct value when we read it.

3. Populate some options that do not correspond to inputs. For example
   `_store_python_version` sets both `output_options.python_version` and
   `output_options.python_exe`. The latter is derived from the python version
   and cached in `options.python_exe`, but it can not be set indepedently.


## Adding a new option

The simplest way to add a new option is to define a new argparse flag for it,
typically in `add_basic_options()` or `add_debug_options()` (it's rare for the
other option groups to change).

If your option needs validation or postprocessing, add a corresponding method to
the `Postprocessor` class.

Options added to `basic_options` should also be added to the
`_PYTYPE_SINGLE_ITEMS` dict in `tools/analyze_project/config.py`

For instance, look at the complete code for the `pythonpath` option:

```
def add_infrastructure_options(o):
  ...
  o.add_argument(
      "-P", "--pythonpath", type=str, action="store",
      dest="pythonpath", default="", help="...")

class Postprocessor:
  ...
  def _store_pythonpath(self, pythonpath):
    # Note that the below gives [""] for "", and ["x", ""] for "x:"
    # ("" is a valid entry to denote the current directory)
    self.output_options.pythonpath = pythonpath.split(os.pathsep)
```

## Config files

While the core `pytype-single` executable can only be configured via command
line flags, the other tools, including the `analyze_project` tool exported as
the main `pytype` binary, can be configured via a config file as well. The
config file follows the standard INI-file format parsed by python's built in
`configparser`; the supporting library to work with the config file and
ultimately convert it into pytype options is `tools/analyze_project/config.py`

NOTE: The config file mirrors the options to `pytype` (i.e. `analyze_project`),
not to `pytype-single`, and therefore does not support every option in
`config.py`.
