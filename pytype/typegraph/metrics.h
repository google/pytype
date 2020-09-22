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

  ~QueryMetrics() {}

  size_t nodes_visited() const { return nodes_visited_; }

  NodeID start_node() const { return start_node_; }

  NodeID end_node() const { return end_node_; }

  size_t initial_binding_count() const { return initial_binding_count_; }

  size_t total_binding_count() const { return total_binding_count_; }

  bool shortcircuited() const { return shortcircuited_; }

  bool from_cache() const { return from_cache_; }

 private:
  size_t nodes_visited_;
  NodeID start_node_;
  NodeID end_node_;
  size_t initial_binding_count_;
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
                std::vector<CacheMetrics> cache_metrics)
      : query_metrics_(query_metrics), cache_metrics_(cache_metrics) {}

  ~SolverMetrics() {}

  const std::vector<QueryMetrics> query_metrics() const {
    return query_metrics_;
  }

  const std::vector<CacheMetrics> cache_metrics() const {
    return cache_metrics_;
  }

 private:
  const std::vector<QueryMetrics> query_metrics_;
  const std::vector<CacheMetrics> cache_metrics_;
};

class Metrics {
 public:
  Metrics(size_t binding_count, std::vector<NodeMetrics> cfg_node_metrics,
          std::vector<VariableMetrics> variable_metrics,
          std::vector<SolverMetrics> solver_metrics,
          CacheMetrics reachability_metrics)
      : binding_count_(binding_count),
        cfg_node_metrics_(cfg_node_metrics),
        variable_metrics_(variable_metrics),
        solver_metrics_(solver_metrics),
        reachability_metrics_(reachability_metrics) {}

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

  CacheMetrics reachability_metrics() const {
    return reachability_metrics_;
  }

 private:
  size_t binding_count_;
  const std::vector<NodeMetrics> cfg_node_metrics_;
  const std::vector<VariableMetrics> variable_metrics_;
  const std::vector<SolverMetrics> solver_metrics_;
  CacheMetrics reachability_metrics_;
};

}  // namespace devtools_python_typegraph

#endif  // THIRD_PARTY_PY_PYTYPE_TYPEGRAPH_METRICS_H_
