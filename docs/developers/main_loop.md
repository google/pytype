# The main loop

<!--ts-->
   * [The main loop](#the-main-loop)
      * [Processing a file](#processing-a-file)
      * [Processing a single opcode](#processing-a-single-opcode)

<!-- Added by: mdemello, at: 2020-05-21T16:31-07:00 -->

<!--te-->

## Processing a file

Pytype's high-level workflow to analyse a single file[^process-one-file] is:

* Instantiate a CallTracer VM[^calltracer]
* Call `run_program`[^run-program]
* Compile the source into bytecode[^compile-src]
* Run the bytecode[^run-bytecode]
    * For each frame[^frame]
        * Loop over opcodes, updating state[^run-instruction]

          ```python
          state = run_instruction(op, state)
          ```
* Optionally, run type inference[^infer-types] on the code, using the final
  state computed by `run_program` to infer type signatures for all classes,
  methods and functions.

## Processing a single opcode

`run_instruction` is the central dispatch point for opcode analysis. For every
opcode, `OP`, we have a corresponding `byte_OP()` method; `run_instruction`
looks this method up, calls it with the current state and the opcode, and uses
the return value as the new state.

TIP: If you want to get a feel for how pytype works, an excellent
starting point is to look at some of the `byte_*` methods and see how they
mirror the workings of the python interpreter at a type level, popping arguments
off the stack, manipulating `locals` and `globals` dictionaries, and creating
objects for classes, methods and functions.

[^process-one-file]: io.py : `process_one_file()`
[^run-program]: vm.py: `run_program()`
[^calltracer]: analyze.py : `class CallTracer`
[^compile-src]: vm.py: `compile_src()`
[^run-bytecode]: vm.py: `run_bytecode()`
[^frame]: A frame is a segment of code, typically one method or function. See
  state.py
[^run-instruction]: vm.py: `run_instruction()`
[^infer-types]: analyze.py: `infer_types()`
