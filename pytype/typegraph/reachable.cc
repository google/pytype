#include "reachable.h"

#include <cstddef>

namespace devtools_python_typegraph {

static inline int64_t _node_bit(int node_id) {
  return 1l << (node_id & 63);
}

ReachabilityAnalyzer::ReachabilityAnalyzer() : num_nodes_(0) {
}

int ReachabilityAnalyzer::add_node() {
  /* Add a single node, and grow the matrix by one row and one column. */
  int node = num_nodes_++;
  size_ = (num_nodes_ + 63) / 64;
  adj_.resize(num_nodes_);
  for (int i = 0; i < num_nodes_; i++) {
    adj_[i].resize(size_, 0);
  }
  adj_[node][node / 64] = _node_bit(node);  // New row, so we don't need "|="
  return node;
}

void ReachabilityAnalyzer::add_connection(const int src, const int dst) {
  /* Update the bit matrix to account for the fact that src and dst are now
   * connected. We consider every pair (i, j) of nodes, and check whether we
   * can now connect them using the new src->dst edge. */
  int64_t src_bit = _node_bit(src);
  int src_pos = src / 64;
  int64_t* row_dst = adj_[dst].data();
  for (int i = 0; i < num_nodes_; i++) {
    if (adj_[i][src_pos] & src_bit) {
      // i is connected to src
      int64_t* row_i = adj_[i].data();
      for (int j = 0; j < size_; j++) {
        row_i[j] |= row_dst[j];  // if dst is connected to j, connect i and j
      }
    }
  }
}

const bool ReachabilityAnalyzer::is_reachable(const int src, const int dst) {
  return adj_[src][dst / 64] & _node_bit(dst) ? true : false;
}

}  // namespace devtools_python_typegraph
