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

TEST(MapUtilTest, FindOrNullTest) {
  std::unordered_map<int, bool> m;
  EXPECT_EQ(FindOrNull(m, 1), nullptr);
  m[1] = true;
  const bool* res = FindOrNull(m, 1);
  EXPECT_NE(res, nullptr);
  EXPECT_EQ(*res, true);
}

TEST(MapUtilTest, FindPtrOrNullTest) {
  std::unordered_map<int, std::string*> m;
  EXPECT_EQ(FindPtrOrNull(m, 1), nullptr);
  std::string val = "hello";
  m[1] = &val;
  std::string* res = FindPtrOrNull(m, 1);
  EXPECT_NE(res, nullptr);
  EXPECT_EQ(*res, val);
}

TEST(MapUtilTest, FindOrDefaultTest) {
  std::unordered_map<int, int> m;
  EXPECT_EQ(FindOrDefault(m, 1, 2), 2);
  m[1] = 3;
  EXPECT_EQ(FindOrDefault(m, 1, 2), 3);
}

}  // namespace

}  // namespace map_util

}  // namespace devtools_python_typegraph
