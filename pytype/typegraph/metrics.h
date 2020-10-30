// Classes for collecting metrics from the typegraph.
// The *Metrics classes do not capture any actual typegraph objects, allowing
// them to live independently of the typegraph itself. This enables e.g. taking
// snapshots of the metrics.

#ifndef THIRD_PARTY_PY_PYTYPE_TYPEGRAPH_METRICS_H_
#define THIRD_PARTY_PY_PYTYPE_TYPEGRAPH_METRICS_H_

#include <vector>

namespace devtools_python_typegraph {

typedef size_t NodeID;

class NodeMetrics {
 public:
  NodeMetrics(size_t incoming_edge_count, size_t outgoing_edge_count,
              bool has_condition)
      : incoming_edge_count_(incoming_edge_count),
        outgoing_edge_count_(outgoing_edge_count),
        has_condition_(has_condition) {}

  ~NodeMetrics() {}

  size_t incoming_edge_count() const { return incoming_edge_count_; }

  size_t outgoing_edge_count() const { return outgoing_edge_count_; }

  bool has_condition() const { return has_condition_; }

 private:
  size_t incoming_edge_count_;
  size_t outgoing_edge_count_;
  bool has_condition_;
};

class VariableMetrics {
 public:
  VariableMetrics(size_t binding_count, std::vector<NodeID> node_ids)
      : binding_count_(binding_count), node_ids_(node_ids) {}

  ~VariableMetrics() {}

  size_t binding_count() const { return binding_count_; }

  const std::vector<NodeID> node_ids() const { return node_ids_; }

 private:
  size_t binding_count_;
  const std::vector<NodeID> node_ids_;
};

/* QueryMetrics stores metrics for a single Solver query.
 * A "query" is a call to Solver::Solve. Large queries are broken into small
 * sub-queries, and the QueryMetrics for a large query will include all the
 * metrics of the sub-queries. If a single sub-query evaluates to false, then
 * the whole query evaluates to false; this is called "shortcircuiting".
 */
class QueryMetrics {
 public:
  QueryMetrics(size_t nodes_visited, NodeID start, NodeID end,
               size_t initial_binding_count, size_t total_binding_count,
               bool shortcircuited, bool from_cache)
      : nodes_visited_(nodes_visited),
        start_node_(start),
        end_node_(end),
        initial_binding_count_(initial_binding_count),
        total_binding_count_(total_binding_count),
        shortcircuited_(shortcircuited),
        from_cache_(from_cache) {}

  // A constructor for creating QueryMetrics that will be filled in later.
  QueryMetrics(NodeID start, size_t initial_binding_count)
      : nodes_visited_(0),
        start_node_(start),
        end_node_(start),
        initial_binding_count_(initial_binding_count),
        total_binding_count_(0),
        shortcircuited_(false),
        from_cache_(false) {}

  ~QueryMetrics() {}

  size_t nodes_visited() const { return nodes_visited_; }
  void add_visited_node() { nodes_visited_ += 1; }

  NodeID start_node() const { return start_node_; }

  NodeID end_node() const { return end_node_; }
  void set_end_node(NodeID node) { end_node_ = node; }

  size_t initial_binding_count() const { return initial_binding_count_; }

  size_t total_binding_count() const { return total_binding_count_; }
  void add_bindings(size_t delta) { total_binding_count_ += delta; }

  bool shortcircuited() const { return shortcircuited_; }
  void set_shortcircuited(bool status) { shortcircuited_ = status; }

  bool from_cache() const { return from_cache_; }
  void set_from_cache(bool status) { from_cache_ = status; }

 private:
  size_t nodes_visited_;
  NodeID start_node_;
  NodeID end_node_;
  size_t initial_binding_count_;
  // Note that the total_binding_count_ is the sum of all sets of goals that
  // the solver considers when solving a query. Deduplication is expensive.
  size_t total_binding_count_;
  bool shortcircuited_;
  bool from_cache_;
};

class CacheMetrics {
 public:
  CacheMetrics(size_t total_size, size_t hits, size_t misses)
      : total_size_(total_size), hits_(hits), misses_(misses) {}

  ~CacheMetrics() {}

  size_t total_size() const { return total_size_; }

  size_t hits() const { return hits_; }

  size_t misses() const { return misses_; }

 private:
  size_t total_size_;
  size_t hits_;
  size_t misses_;
};

class SolverMetrics {
 public:
  SolverMetrics(std::vector<QueryMetrics> query_metrics,
                CacheMetrics cache_metrics)
      : query_metrics_(query_metrics), cache_metrics_(cache_metrics) {}

  ~SolverMetrics() {}

  const std::vector<QueryMetrics> query_metrics() const {
    return query_metrics_;
  }

  const CacheMetrics cache_metrics() const {
    return cache_metrics_;
  }

 private:
  const std::vector<QueryMetrics> query_metrics_;
  const CacheMetrics cache_metrics_;
};

class Metrics {
 public:
  Metrics(size_t binding_count, std::vector<NodeMetrics> cfg_node_metrics,
          std::vector<VariableMetrics> variable_metrics,
          std::vector<SolverMetrics> solver_metrics)
      : binding_count_(binding_count),
        cfg_node_metrics_(cfg_node_metrics),
        variable_metrics_(variable_metrics),
        solver_metrics_(solver_metrics) {}

  ~Metrics() {}

  size_t binding_count() { return binding_count_; }

  const std::vector<NodeMetrics> cfg_node_metrics() const {
    return cfg_node_metrics_;
  }

  const std::vector<VariableMetrics> variable_metrics() const {
    return variable_metrics_;
  }

  const std::vector<SolverMetrics> solver_metrics() const {
    return solver_metrics_;
  }

 private:
  size_t binding_count_;
  const std::vector<NodeMetrics> cfg_node_metrics_;
  const std::vector<VariableMetrics> variable_metrics_;
  const std::vector<SolverMetrics> solver_metrics_;
};

}  // namespace devtools_python_typegraph

#endif  // THIRD_PARTY_PY_PYTYPE_TYPEGRAPH_METRICS_H_
