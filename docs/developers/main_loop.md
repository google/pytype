# The main loop

<!--ts-->
   * [The main loop](#the-main-loop)
      * [Processing a file](#processing-a-file)
      * [Processing a single opcode](#processing-a-single-opcode)
      * [Two-pass Analysis](#two-pass-analysis)

<!-- Added by: tsudol, at: 2020-11-20T16:19-08:00 -->

<!--te-->

## Processing a file

Pytype's high-level workflow to analyse a single file[^process-one-file] is:

*   Instantiate a CallTracer VM[^calltracer]
*   Call `run_program`[^run-program]
*   Compile the source into bytecode[^compile-src]
*   Run the bytecode[^run-bytecode]

    *   For each frame[^frame]

        *   Loop over opcodes, updating state[^run-instruction]

            ```python
            state = run_instruction(op, state)
            ```

*   Call `analyze`[^analyze]

*   Optionally, run type inference[^compute-types] on the code, using the final
    state computed by `run_program` and `analyze` to infer type signatures for
    all classes, methods and functions.

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

## Two-pass Analysis

Pytype performs two passes when analyzing a file, as mentioned in the workflow
above.

The first pass starts with `run_program()`, which executes the bytecode of the
Python program using pytype's virtual machine. This first step compiles the
source code, executes the bytecode and builds the typegraph for the program.
Besides regular type errors, this step also checks for errors such as:

-   incorrect and ignored type comments
-   abstract methods on non-abstract classes
-   incorrect type parameters on functions

However, this step will only find errors in functions and classes that are part
of the control flow graph, starting with the main function of the file. If a
function or class is not reachable from `main()`, this pass will miss errors in
that member. If the file doesn't have a `main()` -- i.e. it is a library -- then
no class or function bodies will be type checked.

Because of that, pytype uses the typegraph to run a second analysis pass by
calling `analyze()`. This pass recursively type checks all members of the
program, starting at the top level definitions. These are mostly classes, though
some libraries define top-level functions.

Both passes will be performed, no matter if pytype is run in "inference" (`-o`)
or "check" (`-C`) mode. The second pass can be disabled using the `--main` (or
`-m`) debug option, in which case only the code that is reachable from `main()`
will be analyzed.

[^process-one-file]: io.py : `process_one_file()`
[^run-program]: vm.py: `run_program()`
[^calltracer]: analyze.py : `class CallTracer`
[^compile-src]: vm.py: `compile_src()`
[^run-bytecode]: vm.py: `run_bytecode()`
[^analyze]: analyze.py: `analyze()`
[^frame]: A frame is a segment of code, typically one method or function. See
    state.py
[^run-instruction]: vm.py: `run_instruction()`
[^compute-types]: analyze.py: `compute_types()`
