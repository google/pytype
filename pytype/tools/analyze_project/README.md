## pytype-all

pytype-all is a tool that runs [pytype](https://github.com/google/pytype) over an entire project.

(This is not an official Google product.)

## License
Apache 2.0

## Installation

`pytype-all` is part of pytype; installing pytype should also provide the
`pytype-all` executable.

## Usage

### Prerequisites
`pytype-all` depends on [importlab](https://github.com/google/importlab) for
dependency analysis. It also requires `pytype` itself to be installed and
available in $PATH. Pytype comes with its own copy of
[typeshed](https://github.com/python/typeshed), but there is also an option
to use an external local installation.

* `importlab`: Needs to be installed
* `pytype`: Needs to be installed and in $PATH
* `typeshed`: (Optional) Can be checked out from git, and pointed to via
  the `TYPESHED_HOME` environment variable

Running `pip install pytype` should automatically satisfy these requirements.

If the target python version (the version of the code being analyzed) does not
match the version of python being used to run `pytype-all` it will require (at
runtime) a python executable for the version of code that is being analyzed.
(e.g. if we run with python 3.6 but target version=2.7, pytype-all will look for
a `python2.7` executable).

### Usage

`pytype-all` takes one or more python files as arguments, and runs pytype over
them. Typechecking errors and `.pyi` files are generated in an output directory
specified in the config file.

```
usage: pytype-all [-h] [--tree] [--unresolved] [--verbosity]
                  [--config CONFIG] [--generate-config CONFIG]
                  [filename [filename ...]]

positional arguments:
  filename              input file(s)

optional arguments:
  -h, --help            show this help message and exit
  --tree                Display import tree.
  --unresolved          Display unresolved dependencies.
  -v, --verbosity       Set logging level: 0=ERROR, 1=WARNING (default), 2=INFO.
  --config CONFIG       Configuration file.
  --generate-config CONFIG
                        Write out a dummy configuration file.
```

### Config File

`pytype-all` uses a config file to set up per-project input, dependency and
output directories. The config file is an INI-style file with a `[pytype]`
section; if an explicit config file is not supplied pytype-all will look for a
`[pytype]` section in your `setup.cfg` (the first `setup.cfg` file found by
walking upwards from the current working directory).

Start off by generating a sample config file:
```
$ pytype-all --generate-config my-project.cfg
```

Now customise each section based on your local setup. Directories may be
relative to the location of the config file, which is useful if you want to
check in the config file as part of your project.

Here is an example of a filled-in config file for a project with files split
across two directories, `~/code/foo` and `~/code/bar`, and the config file at
`~/code/foo/foo.cfg`

```
# NOTE: All relative paths are relative to the location of this file.

[pytype]
# Python version ("major.minor") of the target code.
python_version = 3.6

# All pytype output goes here.
output_dir = pytype_output

# Dependencies within these directories will be checked for type errors.
projects =
  .,
  ~/code/bar

# Dependencies within these directories will have type inference run on them,
# but will not be checked for errors.
deps =
  ~/code/some_dependency,
  /usr/local/lib/python3.6/dist-packages/project.egg/
```

### Example

A complete set of steps to check out the `requests` project and run `pytype` over it. We will assume a ~/github toplevel directory in which everything gets checked out:

```
# Install typeshed (optional)
$ git clone https://github.com/python/typeshed
$ export TYPESHED_HOME=`pwd`/typeshed

# Install pytype
$ pip install pytype

# Check out and analyze requests
$ git clone https://github.com/requests/requests
$ cd requests
# Generate a config file
$ pytype-all --generate-config requests.conf
# and edit it to point to your toplevel directory
$ cat requests.conf
  [pytype]

  # Python version (major.minor)
  python_version = 2.7

  # Dependencies within these directories will be checked for type errors.
  projects = .

  # All output goes here.
  output_dir = pytype_output

$ pytype-all --config=requests.conf requests/*.py
```

This will generate the following tree:

```
pytype_output/
├── pyi
│   └── requests
│       ├── auth.pyi
│       ├── certs.pyi
│       ├── compat.py.errors
│       ├── compat.pyi
│       ├── cookies.py.errors
│       ├── cookies.pyi
│       ├── ...
└── pytype.log
```

So for example to see the pytype errors generated for `requests/compat.py`, run

```
$ cat pytype_output/pyi/requests/compat.py.errors
```

or to see all the errors at once,

```
less pytype_output/pytype.log
```

You will notice a set of import errors for urllib3; this can be fixed by
checking out the urllib3 source as well, and adding it to your config file.

Note that you could also have discovered this by running pytype-all's broken
dependency checker:
```
$ pytype-all --config=requests.conf requests/*.py --unresolved
```

Since we are analysing `requests`, and not `urllib3`, we add it to `deps` rather
than `projects`:

```
$ cd ..
$ git clone https://github.com/shazow/urllib3
$ cd requests

# edit file
$ cat requests.conf
  # Dependencies within these directories will be checked for type errors.
  projects = .

  # Dependencies within these directories will have type inference
  # run on them, but will not be checked for errors.
  deps = ~/github/urllib3

# run pytype-all again
$ pytype-all --config=requests.conf requests/*.py
```

## Roadmap

* `Makefile` generation, to take advantage of `make`'s incremental update and
  parallel execution features
