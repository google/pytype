// A cache to store the reachability set of nodes.

#ifndef PYTYPE_TYPEGRAPH_REACHABLE_H_
#define PYTYPE_TYPEGRAPH_REACHABLE_H_

#include <vector>
#include <cstdint>

namespace devtools_python_typegraph {

class ReachabilityAnalyzer {
 public:
  ReachabilityAnalyzer();

  int add_node();
  void add_connection(const int src, const int dst);
  const bool is_reachable(const int src, const int dst);

 private:
  std::vector<std::vector<int64_t>> adj_;
  int num_nodes_;  // == adj_.size() == adj_[0].size()
  int size_;
};

}  // namespace devtools_python_typegraph

#endif  // PYTYPE_TYPEGRAPH_REACHABLE_H_
