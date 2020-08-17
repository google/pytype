# Stack Frames

freshness: { owner: 'mdemello' reviewed: '2020-08-14' }

<!--ts-->
   * [Stack Frames](#stack-frames)
      * [Overview](#overview)
      * [The frame stack](#the-frame-stack)
      * [Frame state](#frame-state)

<!-- Added by: mdemello, at: 2020-08-14T21:36-07:00 -->

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

```
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
