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
// Even with these optimizations, it's possible to construct "pathological"
// programs that would exhibit exponential running time when analyzed completely
// (and hence, will need pruning of the tree). That's normal: the underlying
// problem is NP complete; i.e., it's possible to reduce 3-SAT to a type
// inference problem.

#ifndef PYTYPE_TYPEGRAPH_SOLVER_H_
#define PYTYPE_TYPEGRAPH_SOLVER_H_

#include <cstddef>
#include <deque>
#include <functional>  // For std::hash
#include <limits>
#include <memory>
#include <optional>
#include <set>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "map_util.h"
#include "metrics.h"
#include "typegraph.h"

namespace devtools_python_typegraph {

namespace internal {

typedef std::set<const Binding*, pointer_less<Binding>> GoalSet;

// hash_mix concatenates a hash seed with the hash of the given object.
// This implementation is based on Google's hash mixing algorithm written by
// Jyrki Alakuijala.
template <typename T>
void hash_mix(std::size_t& seed, const T& val) {
  static const std::size_t kMul =
      static_cast<std::size_t>(0xdc3eb94af8ab4c93ULL);
  // Multiplicative hashing will mix bits better in the msb end ...
  seed *= kMul;
  // ... and rotating will move the better mixed msb-bits to lsb-bits.
  seed = (((seed << 19) |
           (seed >> (std::numeric_limits<std::size_t>::digits - 19))) +
          std::hash<T>{}(val));
}

// A "state" is a position in the program, together with a number of binding
// assignments (name + binding). We call a state "solved" if we found a path
// through the program that ends at said position and assigns the bindings
// to said bindings.
// This class is thread compatible.
class State {
 public:
  // Initialize a state that starts at the given cfg node. It needs to solve
  // a list of goals to succeed.
  State(const CFGNode* pos, GoalSet goals);
  State(const CFGNode* pos, const std::vector<const Binding*>& goals);
  ~State();

  // Compute hash code for this State. We use State instances as keys when
  // memoizing.
  std::size_t Hash() const;

  // Retrieve current position in the CFG. The position is used to determine
  // whether goals (bindings) are reachable.
  const CFGNode* pos() const { return pos_; }

  // Return the list of goals as a set.
  const GoalSet& goals() const { return goals_; }

  bool operator==(const State& other) const {
    // std::set does ordered comparison.
    return pos_ == other.pos_ && goals_ == other.goals_;
  }
  bool operator!=(const State& other) const {
    // std::set does ordered '!='
    return pos_ != other.pos_ || goals_ != other.goals_;
  }

  bool operator<(const State& other) const {
    return Hash() < other.Hash();
  }

 private:
  const CFGNode* pos_;
  GoalSet goals_;
};

typedef std::unordered_map<const State, bool, map_util::hash<State>> StateMap;

typedef std::set<const State*, pointer_less<State>> StateSet;

// QueryResult represents the result of a PathFinder query. It contains status
// (true = path was found) and the actual path.
struct QueryResult {
  bool path_exists = false;
  const std::deque<const CFGNode*>* path = nullptr;
};

class TrieNode {
  friend class PathCacheTrie;

 public:
  TrieNode(): path_exists(false) {}

 private:
  std::optional<std::deque<const CFGNode*>> path;
  bool path_exists;
  // There's no need to backtrack which CFGNode we represent, thus id or the
  // pointer to CFGNode is not stored.
 private:
  // Older versions of gcc don't allow self reference within the same class,
  // thus made this a unique_ptr instead to avoid incomplete type errors.
  std::unordered_map<CFGNode::IdType, std::unique_ptr<TrieNode>> children;
};

class PathCacheTrie {
 public:
  PathCacheTrie() {}
  QueryResult InsertResult(const CFGNode* start, const CFGNode* finish,
                           const CFGNodeSet& blocked, bool path_exists,
                           std::deque<const CFGNode*> result_path);
  QueryResult GetResult(const CFGNode* start, const CFGNode* finish,
                        const CFGNodeSet& blocked);

 private:
  std::unordered_map<const CFGNode*,
                     std::unordered_map<const CFGNode*, TrieNode>>
      root_;
};

// PathFinder is a helper class for finding paths within a CFG. It memoizes
// queries to improve performance.
class PathFinder {
 public:
  PathFinder() {}

  // Don't allow copy or move semantics on PathFinder.
  PathFinder(const PathFinder&) = delete;
  PathFinder& operator=(const PathFinder&) = delete;

  // Find a shortest path from start to finish, going backwards. Returns an
  // empty path if no path exists.
  std::deque<const CFGNode*> FindShortestPathToNode(
      const CFGNode* start, const CFGNode* finish,
      const CFGNodeSet& blocked) const;

  // Determine the highest weighted node we can reach, going backwards.
  const CFGNode* FindHighestReachableWeight(
      const CFGNode* start,
      std::unordered_set<const CFGNode*, CFGNodePtrHash>& seen,
      const std::unordered_map<const CFGNode*, int, CFGNodePtrHash>& weight_map)
      const;

  // Determine whether we can reach a CFG Node, going backwards.
  QueryResult FindNodeBackwards(const CFGNode* start, const CFGNode* finish,
                                const CFGNodeSet& blocked);

 private:
  PathCacheTrie path_trie_;
};

}  // namespace internal

// The solver class is instantiated for a given "problem" instance. It maintains
// a cache of solutions for subproblems to be able to recall them if they
// reoccur in the solving process.
// This class is thread compatible.
class Solver {
 public:
  // Initialize a solver that tries to prove one or more bindings starting (and
  // going backwards from) a given node, all the way to (optionally) an end
  // node.
  Solver(const Program* program);

  // Do not allow copy or move semantics on Solver.
  Solver(const Solver&) = delete;
  Solver& operator=(const Solver&) = delete;

  // Return true if there is a path through the program that would give
  // "start_attr" its binding at the "start_node" program position. For larger
  // programs, this might only look for a partial path (i.e., a path that
  // doesn't go back all the way to the entry point of the program).
  bool Solve(const std::vector<const Binding*>& start_attrs,
             const CFGNode* start_node);

  SolverMetrics CalculateMetrics () const;

 private:
  // Do a quick (one DFS run) sanity check of whether a solution might exist.
  bool CanHaveSolution(const std::vector<const Binding*>& start_attrs,
                       const CFGNode* start_node);
  // Find a sequence of assignments that would solve the given state.
  bool FindSolution(const internal::State& state,
                    internal::StateSet& seen_state, int current_depth);
  // "memoized" version of FindSolution()
  bool RecallOrFindSolution(const internal::State& state,
                            internal::StateSet& seen_state, int current_depth);

  // Are the given Bindings conflicting?
  bool GoalsConflict(const internal::GoalSet& goals) const;

  // Helper for Solve, allowing the public Solve to be purely the external API.
  // This makes gathering query metrics easier, for example.
  bool Solve_(const std::vector<const Binding*>& start_attrs,
             const CFGNode* start_node);

  internal::StateMap solved_states_;
  std::size_t state_cache_hits_;
  std::size_t state_cache_misses_;

  std::vector<QueryMetrics> query_metrics_;

  const Program* program_;
  internal::PathFinder path_finder_;
};

}  // namespace devtools_python_typegraph

#endif  // PYTYPE_TYPEGRAPH_SOLVER_H_
