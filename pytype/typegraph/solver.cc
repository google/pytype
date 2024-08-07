#include "solver.h"

#include <algorithm>
#include <cstddef>
#include <deque>
#include <functional>
#include <iterator>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include "cfg_logging.h"
#include "map_util.h"
#include "metrics.h"
#include "typegraph.h"

namespace devtools_python_typegraph {

namespace internal {

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
    if (goals.count(goal)) {
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
  stack.emplace_back(goals_to_remove, seen_goals, removed_goals, new_goals);
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
    if (seen_goals.count(goal)) {
      // Only process a goal once, to prevent infinite loops.
      stack.emplace_back(goals_to_remove, seen_goals, removed_goals, new_goals);
      continue;
    }
    seen_goals.insert(goal);
    const auto* origin = goal->FindOrigin(pos);
    if (!origin) {
      new_goals.insert(goal);
      stack.emplace_back(goals_to_remove, seen_goals, removed_goals, new_goals);
      continue;
    }
    removed_goals.insert(goal);
    for (const auto& source_set : origin->source_sets) {
      GoalSet next_goals_to_remove(goals_to_remove);
      next_goals_to_remove.insert(source_set.begin(), source_set.end());
      stack.emplace_back(std::move(next_goals_to_remove), seen_goals,
                         removed_goals, new_goals);
    }
  }
  return results;
}

State::State(const CFGNode* pos, GoalSet goals)
    : pos_(pos), goals_(std::move(goals)) {}

State::State(const CFGNode* pos, const std::vector<const Binding*>& goals)
    : pos_(pos), goals_(goals.begin(), goals.end()) {}

State::~State() {}

std::size_t State::Hash() const {
  std::size_t hash = std::hash<const CFGNode*>{}(pos_);
  for (auto goal : goals_)
    hash_mix<const Binding*>(hash, goal);
  return hash;
}

QueryResult PathCacheTrie::InsertResult(
    const CFGNode* start, const CFGNode* finish, const CFGNodeSet& blocked,
    bool path_exists, std::deque<const CFGNode*> result_path) {
  TrieNode* current_trie_node = &root_[start][finish];
  std::unordered_map<CFGNode::IdType, std::unique_ptr<TrieNode>>*
      current_children = &current_trie_node->children;

  for (const CFGNode* node : blocked) {
    auto it = current_children->find(node->id());
    if (it == current_children->end()) {
      auto inserted =
          current_children->insert({node->id(), std::make_unique<TrieNode>()});
      current_trie_node = inserted.first->second.get();
      current_children = &current_trie_node->children;
      continue;
    }
    current_trie_node = it->second.get();
    current_children = &it->second->children;
  }
  current_trie_node->path = std::move(result_path);
  current_trie_node->path_exists = path_exists;
  return {path_exists, &current_trie_node->path.value()};
}

QueryResult PathCacheTrie::GetResult(const CFGNode* start,
                                     const CFGNode* finish,
                                     const CFGNodeSet& blocked) {
  TrieNode* current_trie_node = &root_[start][finish];
  std::unordered_map<CFGNode::IdType, std::unique_ptr<TrieNode>>*
      current_children = &current_trie_node->children;

  for (const CFGNode* node : blocked) {
    auto it = current_children->find(node->id());
    if (it == current_children->end()) {
      return {false, nullptr};
    }
    current_trie_node = it->second.get();
    current_children = &it->second->children;
  }

  if (current_trie_node->path.has_value()) {
    return {current_trie_node->path_exists, &current_trie_node->path.value()};
  }
  return {false, nullptr};
}

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
    if (seen.count(node) || blocked.count(node))
      continue;
    seen.insert(node);
    stack.insert(stack.end(), node->incoming().begin(), node->incoming().end());
  }
  return false;
}

std::deque<const CFGNode*> PathFinder::FindShortestPathToNode(
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
    if (seen.count(node) || blocked.count(node))
      continue;
    seen.insert(node);
    for (auto n : node->incoming()) {
      previous.emplace(n, node);
    }
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
    const CFGNode* start,
    std::unordered_set<const CFGNode*, CFGNodePtrHash>& seen,
    const std::unordered_map<const CFGNode*, int, CFGNodePtrHash>& weight_map)
    const {
  std::vector<const CFGNode*> stack;
  stack.insert(stack.end(), start->incoming().begin(), start->incoming().end());
  int best_weight = -1;
  const CFGNode* best_node = nullptr;
  const CFGNode* node;
  while (!stack.empty()) {
    node = stack.back();
    stack.pop_back();
    if (node == start)
      // Don't allow loops back to the start.
      continue;
    const auto weight = weight_map.find(node);
    if (weight != weight_map.end() && weight->second > best_weight) {
      best_weight = weight->second;
      best_node = node;
    }
    if (!seen.insert(node).second) continue;
    stack.insert(stack.end(), node->incoming().begin(), node->incoming().end());
  }
  return best_node;
}

QueryResult PathFinder::FindNodeBackwards(const CFGNode* start,
                                          const CFGNode* finish,
                                          const CFGNodeSet& blocked) {
  QueryResult result = path_trie_.GetResult(start, finish, blocked);
  if (result.path) {
    return result;
  }
  auto shortest_path = FindShortestPathToNode(start, finish, blocked);
  if (shortest_path.empty()) {
    return path_trie_.InsertResult(start, finish, blocked,
                                   /*path_exists=*/false,
                                   std::move(shortest_path));
  }
  // We now have the shortest path to finish. All articulation points are
  // guaranteed to be on that path (since they're on *all* possible paths).
  // Now "block" the path we found, and check how far we can go
  // without using any nodes on it. The furthest node we can reach (described
  // below by the "weight", which is the position on our shortest path) is our
  // first articulation point. Set that as new start and continue.
  std::unordered_set<const CFGNode*, CFGNodePtrHash> blocked_;
  blocked_.insert(blocked.begin(), blocked.end());
  blocked_.insert(shortest_path.begin(), shortest_path.end());
  std::unordered_map<const CFGNode*, int, CFGNodePtrHash> weights;
  int w = 0;
  for (const auto& x : shortest_path) {
    weights[x] = w++;
  }
  std::deque<const CFGNode*> path;
  const CFGNode* node = start;
  while (true) {
    if (node->condition())
      path.push_back(node);
    if (node->id() == finish->id())
      break;
    node = FindHighestReachableWeight(node, blocked_, weights);
  }
  return path_trie_.InsertResult(start, finish, blocked, true, std::move(path));
}

}  // namespace internal

Solver::Solver(const Program* program)
    : state_cache_hits_(0), state_cache_misses_(0), program_(program) {}

SolverMetrics Solver::CalculateMetrics() const {
  auto cm = CacheMetrics(solved_states_.size(), state_cache_hits_,
                         state_cache_misses_);
  return SolverMetrics(query_metrics_, std::move(cm));
}

bool Solver::GoalsConflict(const internal::GoalSet& goals) const {
  std::unordered_map<const Variable*, const Binding*> variables;
  for (const Binding* goal : goals) {
    const auto& [it, inserted] = variables.emplace(goal->variable(), goal);
    if (!inserted) {
      CHECK(it->second != goal) << "Internal error. Duplicate goal.";
      CHECK(it->second->data() != goal->data())
          << "Internal error. Duplicate data across bindings.";
      return true;
    }
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

  std::vector<std::size_t> goal_ids;
  goal_ids.reserve(state.goals().size());
  for (const Binding* goal : state.goals()) goal_ids.push_back(goal->id());

  query_metrics_.back().add_step(
      QueryStep(state.pos()->id(), std::move(goal_ids), current_depth));
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
    // calling FindNodeBackwards is expensive, even with the trie cache going on
    // there, because trie queries can happen tons of time if the CFG gets
    // complicated. thus gather unique sets of nodes that want to visit first to
    // avoid querying for the same path multiple times.
    std::unordered_set<const CFGNode*> unique_finish_nodes;
    for (const Binding* goal : result.new_goals) {
      for (const auto& origin : goal->origins()) {
        unique_finish_nodes.insert(origin->where);
      }
    }
    for (const CFGNode* finish_node : unique_finish_nodes) {
      internal::QueryResult origin_path =
          path_finder_.FindNodeBackwards(state.pos(), finish_node, blocked);
      if (origin_path.path_exists) {
        const CFGNode* where = finish_node;
        // Check if we found conditions on the way.
        for (const CFGNode* node : *origin_path.path) {
          if (node != state.pos()) {
            where = node;
            break;
          }
        }
        new_positions.insert(where);
      }
    }
    for (const auto* new_pos : new_positions) {
      LOG(INFO) << indent << "New pos: <" << new_pos->id() << "> "
                << new_pos->name();
      const internal::State new_state(new_pos, result.new_goals);
      if (seen_states.count(&new_state) > 0 && new_positions.size() > 1) {
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
  const bool* status = map_util::FindOrNull(solved_states_, state);
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
  solved_states_[state] = true;
  // Careful! Modifying seen_states would affect other recursive calls, so we
  // need to copy it.
  auto inserted = seen_states.insert(&state);
  bool result = FindSolution(state, seen_states, current_depth);
  solved_states_[state] = result;
  if (inserted.second) {
    seen_states.erase(inserted.first);
  }
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
