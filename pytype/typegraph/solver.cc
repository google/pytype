#include "solver.h"

#include <algorithm>
#include <cstddef>
#include <functional>
#include <iterator>
#include <stack>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include "cfg_logging.h"
#include "map_util.h"
#include "metrics.h"
#include "typegraph.h"

namespace devtools_python_typegraph {

namespace internal {

// Helper function for checking set membership.
template <class T, class U>
static bool set_contains(const std::set<T, U>& set, const T elem) {
  return set.find(elem) != set.end();
}

static bool node_set_contains(const CFGNodeSet& set, const CFGNode* elem) {
  return set_contains<const CFGNode*>(set, elem);
}

static bool goal_set_contains(const GoalSet& set, const Binding* elem) {
  return set_contains<const Binding*>(set, elem);
}

// Stores the results of remove_finished_goals.
struct RemoveResult {
  const GoalSet removed_goals;
  const GoalSet new_goals;
  RemoveResult(const GoalSet& removed_goals, const GoalSet& new_goals):
      removed_goals(removed_goals), new_goals(new_goals) {}
};

// Remove all goals that can be fulfilled at the current CFG node.
// Generates all possible sets of new goals obtained by replacing a goal that
// originates at the current node with one of its source sets, iteratively,
// until there are no more such goals. Generating these possibilities here
// allows every _FindSolution() call to completely process its input state,
// avoiding bugs related to transmitting state information across calls.
static std::vector<RemoveResult> remove_finished_goals(const CFGNode* pos,
                                                       const GoalSet& goals) {
  GoalSet goals_to_remove;
  // We can't use set_intersection here because pos->bindings() is a vector.
  for (const auto* goal : pos->bindings()) {
    if (goal_set_contains(goals, goal)) {
      goals_to_remove.insert(goal);
    }
  }
  GoalSet seen_goals;
  GoalSet removed_goals;
  GoalSet new_goals;
  std::set_difference(goals.begin(), goals.end(),
                      goals_to_remove.begin(), goals_to_remove.end(),
                      std::inserter(new_goals, new_goals.begin()),
                      pointer_less<Binding>());
  std::vector<std::tuple<GoalSet, GoalSet, GoalSet, GoalSet>> stack;
  stack.push_back(
      std::make_tuple(goals_to_remove, seen_goals, removed_goals, new_goals));
  std::vector<RemoveResult> results;
  while (!stack.empty()) {
    std::tie(
        goals_to_remove, seen_goals, removed_goals, new_goals) = *stack.begin();
    stack.erase(stack.begin());
    if (goals_to_remove.empty()) {
      results.push_back(RemoveResult(removed_goals, new_goals));
      continue;
    }
    const auto* goal = *goals_to_remove.begin();
    goals_to_remove.erase(goals_to_remove.begin());
    if (goal_set_contains(seen_goals, goal)) {
      // Only process a goal once, to prevent infinite loops.
      stack.push_back(std::make_tuple(
          goals_to_remove, seen_goals, removed_goals, new_goals));
      continue;
    }
    seen_goals.insert(goal);
    const auto* origin = goal->FindOrigin(pos);
    if (!origin) {
      new_goals.insert(goal);
      stack.push_back(std::make_tuple(
          goals_to_remove, seen_goals, removed_goals, new_goals));
      continue;
    }
    removed_goals.insert(goal);
    for (const auto& source_set : origin->source_sets) {
      GoalSet next_goals_to_remove(goals_to_remove);
      next_goals_to_remove.insert(source_set.begin(), source_set.end());
      stack.push_back(std::make_tuple(
          next_goals_to_remove, seen_goals, removed_goals, new_goals));
    }
  }
  return results;
}

State::State(const CFGNode* pos, const GoalSet& goals)
    : pos_(pos), goals_(goals) {}

State::State(const CFGNode* pos, const std::vector<const Binding*>& goals)
    : pos_(pos), goals_(goals.begin(), goals.end()) {}

State::~State() {}

std::size_t State::Hash() const {
  std::size_t hash = std::hash<const CFGNode*>{}(pos_);
  for (auto goal : goals_)
    hash_mix<const Binding*>(hash, goal);
  return hash;
}

PathFinder::PathFinder()
    : solved_find_queries_(
          new QueryMap){}

PathFinder::~PathFinder() {}

bool PathFinder::FindAnyPathToNode(
    const CFGNode* start,
    const CFGNode* finish,
    const CFGNodeSet& blocked) const {
  std::vector<const CFGNode*> stack;
  stack.push_back(start);
  CFGNodeSet seen;
  const CFGNode* node;
  while (!stack.empty()) {
    node = stack.back();
    stack.pop_back();
    if (node == finish)
      return true;
    if (node_set_contains(seen, node) || node_set_contains(blocked, node))
      continue;
    seen.insert(node);
    stack.insert(stack.end(), node->incoming().begin(), node->incoming().end());
  }
  return false;
}

const std::deque<const CFGNode*> PathFinder::FindShortestPathToNode(
    const CFGNode* start, const CFGNode* finish,
    const CFGNodeSet& blocked) const {
  std::deque<const CFGNode*> queue;
  queue.push_front(start);
  std::unordered_map<const CFGNode*, const CFGNode*, CFGNodePtrHash> previous;
  previous[start] = nullptr;
  CFGNodeSet seen;
  const CFGNode* node;
  bool found = false;
  while (!queue.empty()) {
    node = queue.front();
    queue.pop_front();
    if (node->id() == finish->id()) {
      found = true;
      break;
    }
    if (node_set_contains(seen, node) || node_set_contains(blocked, node))
      continue;
    seen.insert(node);
    for (auto n : node->incoming())
      previous.insert({n, node});
    queue.insert(queue.end(), node->incoming().begin(), node->incoming().end());
  }
  std::deque<const CFGNode*> path;
  if (!found)
    return path;
  node = finish;
  while (node) {
    path.push_front(node);
    node = previous[node];
  }
  return path;
}

const CFGNode* PathFinder::FindHighestReachableWeight(
    const CFGNode* start, CFGNodeSet seen,
    const std::unordered_map<const CFGNode*, int, CFGNodePtrHash>& weight_map)
    const {
  std::vector<const CFGNode*> stack;
  stack.insert(stack.end(), start->incoming().begin(), start->incoming().end());
  int best_weight = -1;
  int weight;
  const CFGNode* best_node = nullptr;
  const CFGNode* node;
  while (!stack.empty()) {
    node = stack.back();
    stack.pop_back();
    if (node == start)
      // Don't allow loops back to the start.
      continue;
    weight = map_util::FindOrDefault(weight_map, node, -1);
    if (weight > best_weight) {
      best_weight = weight;
      best_node = node;
    }
    if (node_set_contains(seen, node))
      continue;
    seen.insert(node);
  stack.insert(stack.end(), node->incoming().begin(), node->incoming().end());
  }
  return best_node;
}

QueryResult PathFinder::FindNodeBackwards(
    const CFGNode* start,
    const CFGNode* finish,
    const CFGNodeSet& blocked) {
  QueryKey query(start, finish, blocked);
  const auto* res = map_util::FindOrNull(*solved_find_queries_, query);
  if (res)
    return *res;
  // Declaring result here and filling it in later lets us use RVO.
  QueryResult result;
  auto shortest_path = FindShortestPathToNode(start, finish, blocked);
  if (shortest_path.empty()) {
    result.path_exists = false;
    result.path = shortest_path;
    (*solved_find_queries_)[query] = result;
    return result;
  }
  // We now have the shortest path to finish. All articulation points are
  // guaranteed to be on that path (since they're on *all* possible paths).
  // Now "block" the path we found, and check how far we can go
  // without using any nodes on it. The furthest node we can reach (described
  // below by the "weight", which is the position on our shortest path) is our
  // first articulation point. Set that as new start and continue.
  CFGNodeSet blocked_(blocked);
  blocked_.insert(shortest_path.begin(), shortest_path.end());
  std::unordered_map<const CFGNode*, int, CFGNodePtrHash> weights;
  int w = 0;
  std::deque<const CFGNode*>::const_iterator it = shortest_path.cbegin();
  for (; it != shortest_path.cend(); w++, it++)
    weights[*it] = w;
  std::deque<const CFGNode*> path;
  const CFGNode* node = start;
  while (true) {
    if (node->condition())
      path.push_back(node);
    if (node->id() == finish->id())
      break;
    node = FindHighestReachableWeight(node, blocked_, weights);
  }
  result.path_exists = true;
  result.path = path;
  (*solved_find_queries_)[query] = result;
  return result;
}

}  // namespace internal

Solver::Solver(const Program* program)
    : solved_states_(new internal::StateMap),
      state_cache_hits_(0),
      state_cache_misses_(0),
      program_(program) {}

SolverMetrics Solver::CalculateMetrics() const {
  auto cm = CacheMetrics(solved_states_->size(), state_cache_hits_,
                         state_cache_misses_);
  return SolverMetrics(std::vector<QueryMetrics>(query_metrics_), cm);
}

bool Solver::GoalsConflict(const internal::GoalSet& goals) const {
  std::unordered_map<const Variable*, const Binding*> variables;
  for (const Binding* goal : goals) {
    const Binding* existing = map_util::FindPtrOrNull(variables,
                                                      goal->variable());
    if (existing) {
      CHECK(existing != goal) << "Internal error. Duplicate goal.";
      CHECK(existing->data() != goal->data()) <<
          "Internal error. Duplicate data across bindings.";
      return true;
    }
    variables[goal->variable()] = goal;
  }
  return false;
}

bool Solver::FindSolution(const internal::State& state,
                          internal::StateSet& seen_states, int current_depth) {
  std::string indent(current_depth, ' ');
  LOG(INFO) << indent << "I'm at <" << state.pos()->id() << "> "
            << state.pos()->name();
  query_metrics_.back().add_visited_node();
  // By setting the end node early, we ensure that end_node indicates the last
  // node visited by the query.
  query_metrics_.back().set_end_node(state.pos()->id());
  // As of now, the total number of bindings considered by a query is the sum
  // of all sets of bindings. This is because deduping the sets of bindings is
  // expensive and not currently worthwhile.
  query_metrics_.back().add_bindings(state.goals().size());
  for (const Binding* goal : state.goals()) {
    LOG(INFO) << indent << "Goal: " << goal->variable()->id() << " = "
              << goal->data();
  }

  internal::GoalSet goals(state.goals());
  if (state.pos()->condition()) {
    const auto* condition = state.pos()->condition();
    goals.insert(condition);
    LOG(INFO) << indent << "Absorbed condition: " << condition->variable()->id()
              << " = " << condition->data();
  }

  auto results = internal::remove_finished_goals(state.pos(), goals);
  for (const auto& result : results) {
    LOG(INFO) << indent << "Trying to find assignment:";
    for (const auto* goal : result.removed_goals) {
      LOG(INFO) << indent << "Removed: " << goal->variable()->id() << " = "
                << goal->data();
    }
    for (const auto* goal : result.new_goals) {
      LOG(INFO) << indent << "New: " << goal->variable()->id() << " = "
                << goal->data();
    }
    current_depth += 1;
    if (GoalsConflict(result.removed_goals)) {
      LOG(INFO) << indent << "conflicting removed goals!";
      continue;  // We bulk-removed goals that are internally conflicting.
    }
    if (result.new_goals.empty()) {
      LOG(INFO) << indent << "done!";
      return true;
    }
    CFGNodeSet blocked;
    for (const auto* goal : result.new_goals) {
      const auto vnodes = goal->variable()->nodes();
      blocked.insert(vnodes.begin(), vnodes.end());
    }
    CFGNodeSet new_positions;
    for (const Binding* goal : result.new_goals) {
      for (const auto& origin : goal->origins()) {
        internal::QueryResult origin_path = path_finder_.FindNodeBackwards(
            state.pos(), origin->where, blocked);
        if (origin_path.path_exists) {
          const CFGNode* where = origin->where;
          // Check if we found conditions on the way.
          for (const CFGNode* node : origin_path.path) {
            if (node != state.pos()) {
              where = node;
              break;
            }
          }
          new_positions.insert(where);
        }
      }
    }
    for (const auto* new_pos : new_positions) {
      LOG(INFO) << indent << "New pos: <" << new_pos->id() << "> "
                << new_pos->name();
      const internal::State new_state(new_pos, result.new_goals);
      if (internal::set_contains<const internal::State*>(
              seen_states, &new_state) && new_positions.size() > 1) {
        // Cycle detected. We ignore it unless it is the only solution.
        continue;
      }
      if (RecallOrFindSolution(new_state, seen_states, current_depth)) {
        return true;
      }
    }
    current_depth -= 1;
  }

  return false;
}

// There can only be a solution if, going backwards from the current CFG node,
// we can reach all the binding assignments for all the goals we need. This
// function does a quick check of that, ignoring the order.
bool Solver::CanHaveSolution(
    const std::vector<const Binding*>& start_attrs, const CFGNode* start_node) {
  std::vector<const Binding*> attr;
  attr.reserve(1);
  for (const Binding* goal : start_attrs) {
    attr.push_back(goal);
    if (!Solve_(attr, start_node))
      return false;
    attr.clear();
  }
  return true;
}

// Like FindSolution, but memoizes states we already solved.
bool Solver::RecallOrFindSolution(
    const internal::State& state, internal::StateSet& seen_states,
    int current_depth) {
  const bool* status = map_util::FindOrNull(*solved_states_, state);
  if (status) {
    state_cache_hits_ += 1;
    query_metrics_.back().set_from_cache(true);
    std::string indent(current_depth, ' ');
    if (*status) {
      LOG(INFO) << indent << "Known state: solvable.";
    } else {
      LOG(INFO) << indent << "Known state: not solvable.";
    }
    return *status;
  } else {
    state_cache_misses_ += 1;
  }

  // To prevent infinite loops, we insert this state into the hashmap as a
  // solvable state, even though we have not solved it yet. The reasoning is
  // that if it's possible to solve this state at this level of the tree, it can
  // also be solved in any of the children.
  (*solved_states_)[state] = true;
  // Careful! Modifying seen_states would affect other recursive calls, so we
  // need to copy it.
  internal::StateSet new_seen_states(seen_states);
  new_seen_states.insert(&state);

  bool result = FindSolution(state, new_seen_states, current_depth);
  (*solved_states_)[state] = result;
  return result;
}

// Helper for Solve to separate out query setup.
bool Solver::Solve_(const std::vector<const Binding*>& start_attrs,
                   const CFGNode* start_node) {
  // If there's multiple bindings, check that they're all possible before trying
  // to solve for all of them.
  if (start_attrs.size() > 1 && !CanHaveSolution(start_attrs, start_node)) {
    query_metrics_.back().set_shortcircuited(true);
    return false;
  }
  internal::State state(start_node, start_attrs);
  internal::StateSet seen_states;
  return RecallOrFindSolution(state, seen_states, 0);
}

// "Main method" of the solver.
bool Solver::Solve(const std::vector<const Binding*>& start_attrs,
                   const CFGNode* start_node) {
  query_metrics_.push_back(QueryMetrics(start_node->id(), start_attrs.size()));
  return Solve_(start_attrs, start_node);
}

}  // namespace devtools_python_typegraph
