# Stack Frames

<!-- freshness: { owner: 'mdemello' reviewed: '2020-08-14' } -->

<!--ts-->
   * [Stack Frames](#stack-frames)
      * [Overview](#overview)
      * [The frame stack](#the-frame-stack)
      * [Frame state](#frame-state)
      * [The data stack](#the-data-stack)
         * [Values and variables](#values-and-variables)
         * [LOAD and STORE operations](#load-and-store-operations)
      * [The block stack](#the-block-stack)

<!-- Added by: mdemello, at: 2020-09-14T16:26-07:00 -->

<!--te-->

## Overview

A stack frame (also "interpreter frame" or just "frame") is a key component of
interpreter implementations in general, and specifically of both CPython and
pytype. At a conceptual level, an interpreter executes a series of instructions
within some "execution context", roughly the environment within which variables
are looked up. A function call creates a new context, which is used to
execute the function's code, and then cleaned up when it returns.

Concretely, this execution model is implemented as stack of "frame" objects,
containing data like the local and global variable tables and any metadata
specific to the current function. Calling a function pushes a new frame onto the
stack, and returning pops it back off, leaving the calling code's frame on top
of the stack again.

The python stack frame is described
[in this article](https://realpython.com/cpython-source-code-guide/#execution);
since a lot of the pytype code is based on the details of the CPython
interpreter it is worth being familiar with the latter.

## The frame stack

The vm maintains a stack of frames in `vm.frames`, and methods `push_frame()`
and `pop_frame()` to add and remove frames from the stack. Analogously to
python, the frame stack is also used when reporting errors, so that pytype can
display positional information and tracebacks if desired.

## Frame state

The main entry point is the `vm.run_frame()` method, which adds a frame to the
stack, runs it, retrieves the return value and pops it back off. Pytype also
threads a **state** through the execution of the individual instructions. The
state, an object of type `state.FrameState`, is an immutable snapshot of the
state of the frame when running the opcode, including the data stack, the block
stack and the current cfg node. (These will be detailed in a separate section on
opcode execution).

At a high level, a frame's code consists of an ordered series of blocks, each of
which consists of several opcodes. The overall execution loop is (simplified):

```python
def run_bytecode(code):
  frame = make_frame(code)
  push_frame(frame)
  for block in frame.f_code.order:
    state = initial state for block
    for op in block:
      state = self.run_instruction(op, state)
  pop_frame(frame)  # does cleanup as well as removing the frame from the stack
  return frame.return_variable, frame.f_locals, frame.f_globals
```

Note that unlike the frame state the frame itself is mutable; attributes like
`frame.return_variable` are populated or modified in the course of the execution
loop, and then returned from `run_bytecode()` (the frame object goes out of
scope and is discarded).

## The data stack

The python VM is a "stack machine", meaning that its opcodes operate on a stack
of inputs. This stack (not to be confused with the frame stack) is how
values are passed between instructions - cpython calls it the "value
stack", and pytype the "data stack".

NOTE: The values themselves are python objects allocated and stored in the heap
(explicitly by the cpython VM, and implicitly by pytype since we create abstract
representations of values as python objects). The data stack contains references
to these values, and does not actually create or destroy them. We refer to
pushing and popping values for simplicity, but we are really pushing and popping
references.

Opcodes perform a variety of operations with respect to the data stack:

- Create a new value, and push a reference to it onto the stack
- Retrieve a value from the heap and push a reference onto the stack
- Pop one or more value references off the stack, and perform some operation on
  the underlying values
- Push a reference to an operation's result onto the stack
- Pop a value reference off the stack and copy it to some other part of the
  heap

The current frame state (passed as `state` to all opcode implementations) stores
a reference to the data stack; pushing and popping values is done through the
accessors `state.push` and `state.pop` rather than access the stack directly.

### Values and variables

One reason pytype does not follow cpython in naming the data stack the "value
stack" is that we do not store values directly on the stack; we store Variables
with bindings to those values. This detail becomes important when we factor in
control flow analysis; while the cpython VM will execute an opcode and store
a single python object on the stack, pytype pushes a Variable with multiple
bindings, each one representing a different potential value that the opcode
might be pushing. As a quick example, given the code

```python
if a:
  y = 10
else:
  y = None
x = y
```

When we hit the opcode `LOAD_FAST y` for the final line, we would push a
variable with bindings `<y = 10>` and `<y = None>` onto the stack, whereas
python would push either `10` or `None` depending on what `a` actually was.

### LOAD and STORE operations

The `LOAD_*` family of opcodes typically retrieve a value from one of the
frame's other data stores (e.g. the locals dictionary) and push them onto the
stack. Similarly, the `STORE_*` family pops a value off the stack and writes it
to a heap location. So the following code:

```python
x = a + b
```

would compile to

```
LOAD_FAST   0 (a)
LOAD_FAST   1 (b)
BINARY_ADD
STORE_FAST  2 (x)
```

The pytype implementations of these opcodes can be seen in
`vm.py/byte_LOAD_FAST` etc. Let us do a quick code tour of the execution of
`byte_LOAD_FAST` when running the first opcode, `LOAD_FAST 0`

```python
  def byte_LOAD_FAST(self, state, op):
    """Load a local. Unlike LOAD_NAME, it doesn't fall back to globals."""
    # op.arg is an index into the current frame's table of local variable names.
    # Use the index to look up the name of the variable to load.
    name = self.frame.f_code.co_varnames[op.arg] # returns 'a'
    # Load the variable 'a' in the current frame's `locals` dict.
    try:
      # load_local gets the current value of a in `val`. Note the common pattern
      # of threading an immutable state object through functions in vm.py by
      # having them take in a state and return an updated state.
      state, val = self.load_local(state, name)
    except KeyError:
      # Raise an error if we have referred to an undefined local variable
      val = self._name_error_or_late_annotation(name).to_variable(state.node)
    # Raise an error if we have referred to a deleted local variable. (We need
    # to do this because pytype stores deleted variables as a `Deleted` object
    # rather than removing them from the symbol table.
    self.check_for_deleted(state, name, val)
    # trace_opcode simply logs opcode execution.
    self.trace_opcode(op, name, val)
    # Push the value of a onto the data stack
    return state.push(val)
```

The overall stack effect is to have the data stack go from `[]` to `[a]`.
Tracing the state of the stack through each opcode:

```
LOAD_FAST   0 (a)  | (a)       | a has been loaded from locals[a] and pushed
LOAD_FAST   1 (b)  | (b), (a)  | b has been loaded from locals[b] and pushed
BINARY_ADD         | (a+b)     | a and b have been popped and a+b pushed
STORE_FAST  2 (x)  |           | a+b has been popped and stored in locals[x]
```

## The block stack

The block stack is the third of the stacks that python, and hence pytype,
maintain when running bytecode. [This blog
post](https://tech.blog.aknin.name/2010/07/22/pythons-innards-interpreter-stacks/)
is a good introduction to it from a cpython perspective.

The block stack tracks [*compound
statements*](https://docs.python.org/3/reference/compound_stmts.html),
statements like `if` and `for` which have an associated block of code. In python
source code, compound statements contain an indented block of code:
```
for x in xs:
  code block
  ...
```

The corresponding bytecode has paired `SETUP_*` and `POP_BLOCK` statements to
delimit the code block, for instance the bytecode for the `for` statement above
would compile to

```
SETUP_LOOP
LOAD_FAST xs
GET_ITER
FOR_ITER
STORE_FAST x
...
code block
...
POP_BLOCK
```

NOTE: Some of the `SETUP_*` opcodes changed in python 3.8, however the basic
principle remains the same. See `vm.py/byte_SETUP_FINALLY()` for a quick look at
how pytype handles version-specific opcode differences.

Internally, pytype represents a block as an object with four fields:

```
Block = collections.namedtuple("Block", [
  "type",     # string representing the block type ("loop", "except", etc)
  "level"     # the size of the data stack when entering the block
])
```

Pytype's primary use for the block stack is to ensure the data stack is cleaned
up when exiting a block (see `vm.py/_revert_state_to()`).
