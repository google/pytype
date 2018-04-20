// Algorithm for solving the data flow graphs in typegraph.h.  This uses DFS and
// memoized backtracking to find use-def chains that explain one or multiple
// variable<->type assignments at a given point in the program.  The performance
// depends on the program being analyzed.  Right now, we explore the whole state
// space, i.e. analyze every possible order of variable assignments, but we
// reserve the right to prune "uninteresting" parts of the use-def tree, to keep
// complexity at bay.
// We also use memoization to remember solutions to specific variable
// assignments, and we do a "sanity" pass over the program to quickly rule out
// assignments that are impossible because the bindings they use have fallen
// out of scope.
//
