#include "map_util.h"

#include <string>
#include <unordered_map>

#include "gtest/gtest.h"

namespace devtools_python_typegraph {
namespace map_util {
namespace {

TEST(MapUtilTest, ContainsKeyTest) {
  std::unordered_map<int, int> m;
  m[1] = 2;
  EXPECT_TRUE(ContainsKey(m, 1));
  EXPECT_FALSE(ContainsKey(m, 2));
}
}  // namespace

}  // namespace map_util

}  // namespace devtools_python_typegraph
