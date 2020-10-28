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
#include <set>
#include <unordered_map>
#include <vector>

#include "typegraph.h"
#include "map_util.h"
#include "metrics.h"

namespace devtools_python_typegraph {

namespace internal {

typedef std::set<const Binding*, pointer_less<Binding>> GoalSet;

// hash_mix concatenates a hash seed with the hash of the given object.
// This implementation is based on Google's hash mixing algorithm written by
// Jyrki Alakuijala.
template <typename T>
void hash_mix(size_t& seed, const T& val) {
  static const size_t kMul = static_cast<size_t>(0xdc3eb94af8ab4c93ULL);
  // Multiplicative hashing will mix bits better in the msb end ...
  seed *= kMul;
  // ... and rotating will move the better mixed msb-bits to lsb-bits.
  seed = (((seed << 19) |
           (seed >> (std::numeric_limits<size_t>::digits - 19))) +
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
  State(const CFGNode* pos, const GoalSet& goals);
  State(const CFGNode* pos, const std::vector<const Binding*>& goals);
  ~State();

  // Compute hash code for this State. We use State instances as keys when
  // memoizing.
  size_t Hash() const;

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

 private:
  const CFGNode* pos_;
  GoalSet goals_;
};

typedef std::unordered_map<const State, bool, map_util::hash<State>> StateMap;

// The PathFinder uses QueryKeys to cache queries. Each query is characterized
// by the start and end nodes and the set of blocked nodes.
// This class implements functions necessary for use in a hash map, namely Hash,
// operator== and operator!=.
class QueryKey {
 public:
  QueryKey(): start_(nullptr), finish_(nullptr) {}
  QueryKey(const CFGNode* s, const CFGNode* f,
           const CFGNodeSet& b):
    start_(s), finish_(f), blocked_(b) {}

  size_t Hash() const {
    size_t hash = std::hash<const CFGNode*>{}(start_);
    hash_mix<const CFGNode*>(hash, finish_);
    for (auto n : blocked_)
      hash_mix<const CFGNode*>(hash, n);
    return hash;
  }

  bool operator==(const QueryKey& other) const {
    return (start_ == other.start_ &&
            finish_ == other.finish_ &&
            blocked_ == other.blocked_);
  }

  bool operator!=(const QueryKey& other) const {
    return !(start_ == other.start_ &&
             finish_ == other.finish_ &&
             blocked_ == other.blocked_);
  }

 private:
  const CFGNode* start_;
  const CFGNode* finish_;
  CFGNodeSet blocked_;
};

// QueryResult represents the result of a PathFinder query. It contains status
// (true = path was found) and the actual path.
// The copy constructor is implemented so that QueryResult can be easily used as
// a value in a hash map.
struct QueryResult {
  bool path_exists = false;
  std::deque<const CFGNode*> path;
  QueryResult() {}
  QueryResult(bool path_exists, const std::deque<const CFGNode*>& path):
    path_exists(path_exists), path(path) {}
  QueryResult(const QueryResult& other):
    path_exists(other.path_exists), path(other.path) {}
};

typedef std::unordered_map<QueryKey, QueryResult, map_util::hash<QueryKey>>
    QueryMap;

// PathFinder is a helper class for finding paths within a CFG. It memoizes
// queries to improve performance.
class PathFinder {
 public:
  PathFinder();
  ~PathFinder();

  // Don't allow copy or move semantics on PathFinder.
  PathFinder(const PathFinder&) = delete;
  PathFinder& operator=(const PathFinder&) = delete;

  // Determine whether we can reach a node at all.
  bool FindAnyPathToNode(const CFGNode* start, const CFGNode* finish,
                         const CFGNodeSet& blocked) const;

  // Find a shortest path from start to finish, going backwards. Returns an
  // empty path if no path exists.
  const std::deque<const CFGNode*> FindShortestPathToNode(
      const CFGNode* start, const CFGNode* finish,
      const CFGNodeSet& blocked) const;

  // Determine the highest weighted node we can reach, going backwards.
  const CFGNode* FindHighestReachableWeight(
      const CFGNode* start, CFGNodeSet seen,
      const std::unordered_map<const CFGNode*, int, CFGNodePtrHash>& weight_map)
      const;

  // Determine whether we can reach a CFG Node, going backwards.
  QueryResult FindNodeBackwards(const CFGNode* start, const CFGNode* finish,
                                const CFGNodeSet& blocked);

 private:
  const std::unique_ptr<QueryMap> solved_find_queries_;
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
  bool FindSolution(const internal::State& state, int current_depth);
  // "memoized" version of FindSolution()
  bool RecallOrFindSolution(const internal::State& state, int current_depth);

  // Are the given Bindings conflicting?
  bool GoalsConflict(const internal::GoalSet& goals) const;

  // Helper for Solve, allowing the public Solve to be purely the external API.
  // This makes gathering query metrics easier, for example.
  bool Solve_(const std::vector<const Binding*>& start_attrs,
             const CFGNode* start_node);

  const std::unique_ptr<internal::StateMap> solved_states_;
  size_t state_cache_hits_;
  size_t state_cache_misses_;

  std::vector<QueryMetrics> query_metrics_;

  const Program* program_;
  internal::PathFinder path_finder_;
};

}  // namespace devtools_python_typegraph

#endif  // PYTYPE_TYPEGRAPH_SOLVER_H_
