// A cache to store the reachability set of nodes.

#ifndef PYTYPE_TYPEGRAPH_REACHABLE_H_
#define PYTYPE_TYPEGRAPH_REACHABLE_H_

#include <cstddef>
#include <cstdint>
#include <vector>

namespace devtools_python_typegraph {

class ReachabilityAnalyzer {
 public:
  ReachabilityAnalyzer();

  int add_node();
  void add_connection(int src, int dst);
  bool is_reachable(int src, int dst) const;

  std::size_t size() const { return size_; }

 private:
  std::vector<std::vector<std::int64_t>> adj_;
  std::size_t num_nodes_;  // == adj_.size() == adj_[0].size()
  std::size_t size_;
};

}  // namespace devtools_python_typegraph

#endif  // PYTYPE_TYPEGRAPH_REACHABLE_H_
