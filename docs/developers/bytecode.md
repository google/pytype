# Bytecode Compilation

<!--*
freshness: { owner: 'mdemello' reviewed: '2020-08-07' }
*-->

<!--ts-->
   * [Bytecode Compilation](#bytecode-compilation)
      * [Overview](#overview)
      * [Host and Target Versions](#host-and-target-versions)
      * [Opcodes](#opcodes)

<!-- Added by: rechen, at: 2020-08-29T02:25-07:00 -->

<!--te-->

## Overview

Python code is first compiled to bytecode, and then interpreted by the python
virtual machine. Pytype follows this strategy, "interpreting" the bytecode with
a virtual machine (`vm.py/VirtualMachine`) which manipulates types rather than
values. This means that when analysing a file, pytype's first step is to run the
python interpreter over it and compile it to bytecode. The bytecode is then
disassembled into `Opcode`s, pytype's internal representation of a python
opcode, and this list of `Opcode`s is used as the canonical representation of
the program by the rest of the code.

## Host and Target Versions

One caveat for any sort of python code tool is that the python language, and
hence its bytecode, are evolving over time. For pytype specifically, one of the
consequences of this is that we accept a `--version` argument specifying the
python version of the code being analysed, and make sure that our internal model
of the language matches the exact state of the code's version.

Since pytype itself is written in python, we have to make a clear distinction
between the **host** and the **target** python version:

* The **host** version is the version of the python interpreter that is used to
  run pytype
* The **target** version is the version of python that the code we are analysing
  (as specified by `--version`). If no version is specified, we assume it is the
  same as the host version.

If the host and target versions differ, we need to compile python source files
to bytecode using a *target-version* interpreter, e.g. if we are running under
python 3.6 and are passed `--version=2.7` we cannot use python 3.6's internal
libraries to compile the code; we have to launch a python 2.7 interpreter,
compile the target code to bytecode, and then retrieve that bytecode to run
through our VirtualMachine.

The relevant compilation code can be found at `pyc/pyc.py`. The process is:

```python
if host_version == target_version:
  bytecode = compile_source(src)
else:
  write source to tmpfile src.py
  subprocess.call(target_python_exe, tmpfile) # generates src.pyc
  bytecode = read(src.pyc)
```

To support `host != target`, we have a check in
`config.py/_store_python_version()` to make sure there is a target-version
python interpreter available, and a standalone executable,
`pyc/compile_bytecode.py` that can be called as a subprocess.

## Opcodes

As the name suggests, "bytecode" is a binary representation consisting of a
series of bytes, each with a meaning defined by the interpreter (e.g. `10` =
`UNARY_POSITIVE`).  Pytype reads in the bytecode version of a `.py` file and
disassembles it into `Opcodes`, our internal representation of a bytecode VM
instruction.

NOTE: If you are not already familiar with python bytecode and disassembly,
playing with the [dis module](https://docs.python.org/3/library/dis.html) will
be helpful. [This article](http://www.goldsborough.me/python/low-level/2016/10/04/00-31-30-disassembling_python_bytecode)
is a good introduction to the topic.

The relevant code is in `opcodes.py`, which defines two classes, `Opcode` and
`OpcodeWithArg`, and then creates a subclass corresponding to every python
opcode. Opcodes have a set of properties like `HAS_LOCAL` and `PUSHES_BLOCK`
(stored as a bitvector, see the top of `opcodes.py` for explanations of each
bit), and optionally a single argument. The semantic value of the argument
depends on the opcode. For example,

```python
class STORE_ATTR(OpcodeWithArg):  # Indexes into name list
  FLAGS = HAS_NAME|HAS_ARGUMENT
    __slots__ = ()
```

means that the opcode `STORE_ATTR` references the name table, has a single
associated argument, and that that argument is an index into the list of names.

> TIP: The meaning of the argument is not part of the opcode definition (hence the
> need to document it as a comment). Looking at `vm.py`, every opcode has a
> corresponding `byte_<Opcode>` method in the `VirtualMachine` class, which deals
> with actually interpreting that opcode. The `byte_STORE_ATTR` method starts off
> with the code
>
> ```python
> name = self.frame.f_code.co_names[op.arg]
> ```
>
> which essentially says "use the opcode's argument to index into the list of
> names and retrieve the name of the attr that we are storing". The comments on
> the Opcode class document these semantic meanings.

After defining a class for every python opcode, `opcodes.py` defines a series of
tables mapping between bytecodes and opcodes for each python version we support
(currently `2.7` and `3.5`-`3.8`). The `opcodes.py/dis()` function gets the
right mapping table for the target python version, and then passes it to a
bytecode reader which iterates over the block of bytes, converting each one into
an opcode or into the argument for the preceding opcode.

NOTE: One subtlety is that from python 3.6 the bytecode format changed;
therefore we need two separate bytecode scanners, `_bytecode_reader` for python
<= 3.5 and `_wordcode_reader` for 3.6 onwards.
