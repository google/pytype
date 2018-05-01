#include "reachable.h"

#include "gtest/gtest.h"

namespace devtools_python_typegraph {
namespace {

class ReachabilityTest : public ::testing::Test {
 protected:
  ReachabilityAnalyzer reach_;
};

TEST_F(ReachabilityTest, TestReachabilityRaw) {
  int i, j;
  for (i = 0; i < 201; i++) {
    reach_.add_node();
  }
  for (i = 0; i < 200; i++) {
    for (j = 0; i < 200; i++) {
      if (i != j) {
        EXPECT_FALSE(reach_.is_reachable(i, j));
      }
    }
  }
  EXPECT_TRUE(reach_.is_reachable(1, 1));
  reach_.add_connection(1, 1);
  EXPECT_TRUE(reach_.is_reachable(1, 1));
  reach_.add_connection(2, 1);
  EXPECT_TRUE(reach_.is_reachable(2, 1));
  EXPECT_FALSE(reach_.is_reachable(1, 2));
  reach_.add_connection(1, 4);
  EXPECT_TRUE(reach_.is_reachable(1, 4));
  EXPECT_TRUE(reach_.is_reachable(2, 4));
  EXPECT_FALSE(reach_.is_reachable(4, 2));
  EXPECT_FALSE(reach_.is_reachable(4, 1));
  for (i = 5; i < 200; i++) {
    for (j = 5; i < 200; i++) {
      if (i != j) {
        EXPECT_FALSE(reach_.is_reachable(i, j));
      }
    }
  }
  reach_.add_connection(1, 22);
  reach_.add_connection(22, 200);
  EXPECT_TRUE(reach_.is_reachable(2, 200));
  EXPECT_TRUE(reach_.is_reachable(1, 200));
  EXPECT_TRUE(reach_.is_reachable(22, 200));
  EXPECT_TRUE(reach_.is_reachable(1, 22));
  EXPECT_TRUE(reach_.is_reachable(2, 22));
  EXPECT_FALSE(reach_.is_reachable(1, 5));
  EXPECT_FALSE(reach_.is_reachable(5, 1));
  EXPECT_FALSE(reach_.is_reachable(22, 4));
  EXPECT_FALSE(reach_.is_reachable(4, 22));
  EXPECT_FALSE(reach_.is_reachable(4, 200));
  EXPECT_FALSE(reach_.is_reachable(200, 4));
}

}  // namespace
}  // namespace devtools_python_typegraph
