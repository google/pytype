#include <algorithm>
#include <memory>
#include <string>
#include <vector>

#include "solver.h"
#include "test_util.h"
#include "typegraph.h"
#include "gmock/gmock.h"  // for UnorderedElementsAre
#include "gtest/gtest.h"

namespace devtools_python_typegraph {
namespace {

TEST(SolverTest, TestOverwrite) {
  // [n0] x = 1
  // [n0] x = 2
  // [n1]
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  std::string const1("1");
  std::string const2("2");
  Variable* x = p.NewVariable();
  AddBinding(x, &const1, n0, {});
  AddBinding(x, &const2, n0, {});
  EXPECT_THAT(x->FilteredData(n1), testing::UnorderedElementsAre(
      AsDataType(&const1), AsDataType(&const2)));
}

TEST(SolverTest, TestShadow) {
  // n0->n1
  // [n0] x = 1
  // [n1] x = 2
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  std::string const1("1");
  std::string const2("2");
  Variable* x = p.NewVariable();
  AddBinding(x, &const1, n0, {});
  AddBinding(x, &const2, n1, {});
  EXPECT_THAT(x->FilteredData(n0),
              testing::UnorderedElementsAre(AsDataType(&const1)));
  EXPECT_THAT(x->FilteredData(n1),
              testing::UnorderedElementsAre(AsDataType(&const2)));
}

TEST(SolverTest, TestOriginUnreachable) {
  // n0-->n1
  //  |
  //  +-->n2
  //
  // [n1] x = 1
  // [n2] y = x
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  CFGNode* n2 = n0->ConnectNew("n2");
  std::string const1("1");
  Variable* x = p.NewVariable();
  Variable* y = p.NewVariable();
  Binding* ax = AddBinding(x, &const1, n1, {});
  Binding* ay = AddBinding(y, &const1, n2, {ax});
  EXPECT_TRUE(ax->IsVisible(n1));
  EXPECT_FALSE(ay->IsVisible(n1));
  EXPECT_FALSE(ax->IsVisible(n2));
  EXPECT_FALSE(ay->IsVisible(n2));
  EXPECT_EQ(0, y->FilteredData(n1).size());
  EXPECT_EQ(0, y->FilteredData(n2).size());
}

TEST(SolverTest, TestOriginReachable) {
  // n0->n1
  // [n0] x = 1
  // [n1] x = y
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  std::string const1("1");
  Variable* x = p.NewVariable();
  Variable* y = p.NewVariable();
  Binding* ax = AddBinding(x, &const1, n0, {});
  AddBinding(y, &const1, n1, {ax});
  EXPECT_EQ(1, x->FilteredData(n0).size());
  EXPECT_EQ(1, x->FilteredData(n1).size());
  EXPECT_EQ(0, y->FilteredData(n0).size());
  EXPECT_EQ(1, y->FilteredData(n1).size());
}

TEST(SolverTest, TestOriginMulti) {
  // n0->n1->n2
  // [n0] x = 1
  // [n1] y = x + x
  // [n2] z = x + y
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  CFGNode* n2 = n1->ConnectNew("n2");
  std::string const1("1");
  std::string const2("2");
  std::string const3("3");
  Variable* x = p.NewVariable();
  Variable* y = p.NewVariable();
  Variable* z = p.NewVariable();
  Binding* ax = AddBinding(x, &const1, n0, {});
  Binding* ay = AddBinding(y, &const2, n1, {ax});
  AddBinding(z, &const3, n2, {ax, ay});
  EXPECT_THAT(y->FilteredData(n2),
              testing::UnorderedElementsAre(AsDataType(&const2)));
  EXPECT_THAT(z->FilteredData(n2),
              testing::UnorderedElementsAre(AsDataType(&const3)));
}

TEST(SolverTest, TestDiamond) {
  // n0--------n1
  //  |        |
  //  |        v
  // n2------->n3
  // [n0] x = 1
  // [n1] y = x
  // [n2] z = x
  // [n3] yz = y + z
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  CFGNode* n2 = n0->ConnectNew("n2");
  CFGNode* n3 = n2->ConnectNew("n3");
  n1->ConnectTo(n3);
  std::string const1("1");
  Variable* x = p.NewVariable();
  Variable* y = p.NewVariable();
  Variable* z = p.NewVariable();
  Variable* yz = p.NewVariable();
  Binding* ax = AddBinding(x, &const1, n0, {});
  Binding* ay = AddBinding(y, &const1, n1, {ax});
  Binding* az = AddBinding(z, &const1, n2, {ax});
  AddBinding(yz, &const1, n3, {ay, az});
  EXPECT_EQ(0, yz->FilteredData(n3).size());
  DataType* const1_data = AsDataType(&const1);
  EXPECT_THAT(y->FilteredData(n3), testing::UnorderedElementsAre(const1_data));
  EXPECT_THAT(z->FilteredData(n3), testing::UnorderedElementsAre(const1_data));
  EXPECT_THAT(x->FilteredData(n3), testing::UnorderedElementsAre(const1_data));
}

TEST(SolverTest, TestOriginSplitPath) {
  // n0-->n1-->n3
  //  |        ^
  //  |        |
  //  +-->n2---+
  //
  // [n0] a10 = 10
  // [n1] a20 = 20
  // [n2] a1 = 1
  // [n3] a2 = 2
  // [n1] x = a10
  // [n1] y = a1
  // [n2] x = a20
  // [n2] y = a2
  // [n3] z = x + y
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  CFGNode* n2 = n0->ConnectNew("n2");
  CFGNode* n3 = n2->ConnectNew("n3");
  n1->ConnectTo(n3);
  std::string const1("1");
  std::string const2("2");
  std::string const10("10");
  std::string const20("20");
  std::string const11("11");
  std::string const21("21");
  std::string const12("12");
  std::string const22("22");
  Binding* a10 = AddBinding(p.NewVariable(), &const10, n0, {});
  Binding* a20 = AddBinding(p.NewVariable(), &const20, n0, {});
  Binding* a1 = AddBinding(p.NewVariable(), &const1, n0, {});
  Binding* a2 = AddBinding(p.NewVariable(), &const2, n0, {});
  Variable* x = p.NewVariable();
  Variable* y = p.NewVariable();
  Variable* z = p.NewVariable();

  Binding* ax10 = AddBinding(x, &const10, n1, {a10});
  Binding* ay1 = AddBinding(y, &const1, n1, {a1});
  Binding* ax20 = AddBinding(x, &const20, n2, {a20});
  Binding* ay2 = AddBinding(y, &const2, n2, {a2});

  EXPECT_TRUE(ax10->IsVisible(n3));
  EXPECT_TRUE(ay1->IsVisible(n3));
  EXPECT_TRUE(ax20->IsVisible(n3));
  EXPECT_TRUE(ay2->IsVisible(n3));

  Binding* az11 = AddBinding(z, &const11, n3, {ax10, ay1});
  Binding* az12 = AddBinding(z, &const12, n3, {ax10, ay2});
  Binding* az21 = AddBinding(z, &const21, n3, {ax20, ay1});
  Binding* az22 = AddBinding(z, &const22, n3, {ax20, ay2});

  EXPECT_TRUE(az11->IsVisible(n3));
  EXPECT_FALSE(az12->IsVisible(n3));
  EXPECT_FALSE(az21->IsVisible(n3));
  EXPECT_TRUE(az22->IsVisible(n3));

  EXPECT_EQ(2, z->FilteredData(n3).size());
  EXPECT_THAT(z->FilteredData(n3),
              testing::UnorderedElementsAre(AsDataType(&const11),
                                            AsDataType(&const22)));
}

TEST(SolverTest, TestCombination) {
  // n0->n1
  // [n0] x = 1
  // [n1] y = 1
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  std::string const1("1");
  Variable* x = p.NewVariable();
  Variable* y = p.NewVariable();
  Binding* ax = AddBinding(x, &const1, n0, {});
  Binding* ay = AddBinding(y, &const1, n1, {});
  EXPECT_FALSE(n0->HasCombination({ax, ay}));
  EXPECT_TRUE(n1->HasCombination({ax, ay}));
}

TEST(SolverTest, TestConflicting) {
  // n0
  // [n0] x = 1 or 2
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  std::string const1("1");
  std::string const2("2");
  Variable* x = p.NewVariable();
  Binding* a0 = AddBinding(x, &const1, n0, {});
  Binding* a1 = AddBinding(x, &const2, n0, {});
  EXPECT_TRUE(n0->HasCombination({a0}));
  EXPECT_TRUE(n0->HasCombination({a1}));
  EXPECT_FALSE(n0->HasCombination({a0, a1}));
}

TEST(SolverTest, TestSameBinding) {
  // n0--------n1
  //  |        |
  //  |        v
  // n2------->n3
  // [n0] x = 1 or 2
  // [n1] y = x or 1 or 2
  // [n2] y = x or 1 or 2
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  CFGNode* n2 = n0->ConnectNew("n2");
  CFGNode* n3 = n2->ConnectNew("n3");
  n1->ConnectTo(n3);
  std::string const1("1");
  std::string const2("2");
  Variable* x = p.NewVariable();
  Variable* y = p.NewVariable();
  Binding* x1 = AddBinding(x, &const1, n0, {});
  Binding* x2 = AddBinding(x, &const2, n0, {});
  AddBinding(y, &const1, n1, {});
  AddBinding(y, &const2, n1, {});
  AddBinding(y, &const1, n1, {x1});
  AddBinding(y, &const2, n1, {x2});
  AddBinding(y, &const1, n2, {});
  AddBinding(y, &const2, n2, {});
  AddBinding(y, &const1, n2, {x1});
  AddBinding(y, &const2, n2, {x2});
  EXPECT_THAT(y->Data(),
              testing::UnorderedElementsAre(AsDataType(&const1),
                                            AsDataType(&const2)));
}

TEST(SolverTest, TestEntrypoint) {
  // n0 -> n1
  // [n0] y = 1
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  std::string const1("1");
  std::string const2("2");
  Variable* x = p.NewVariable();
  Binding* v0 = AddBinding(x, &const1, n0, {});
  Binding* v1 = AddBinding(x, &const2, n1, {});
  p.set_entrypoint(n0);
  EXPECT_TRUE(n0->HasCombination({v0}));
  EXPECT_TRUE(n1->HasCombination({v1}));
}

TEST(SolverTest, TestUnordered) {
  // n0
  // [n0] x = 1
  // [n0] x = 2
  // [n0] x = 3
  // [n1] y = x
  Program p;
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  std::string const1("1");
  std::string const2("2");
  std::string const3("3");
  Variable* x = p.NewVariable();
  Variable* y = p.NewVariable();
  Binding* x1 = AddBinding(x, &const1, n0, {});
  Binding* x2 = AddBinding(x, &const2, n0, {});
  Binding* x3 = AddBinding(x, &const3, n0, {});
  Binding* y1 = AddBinding(y, &const1, n1, {x1});
  Binding* y2 = AddBinding(y, &const2, n1, {x2});
  Binding* y3 = AddBinding(y, &const3, n1, {x3});
  EXPECT_TRUE(n0->HasCombination({x1}));
  EXPECT_TRUE(n0->HasCombination({x2}));
  EXPECT_TRUE(n0->HasCombination({x3}));
  EXPECT_TRUE(n1->HasCombination({y1}));
  EXPECT_TRUE(n1->HasCombination({y2}));
  EXPECT_TRUE(n1->HasCombination({y3}));
}

TEST(SolverTest, TestMemoization) {
  // n0 -> n1 -> n1
  // [n0] x = 1;y = 1
  // [n1] x, y = x&y, x&y
  // [n2] x, y = x&y, x&y
  Program p;
  std::string const1("1");
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  CFGNode* n2 = n1->ConnectNew("n2");
  Variable* x = p.NewVariable();
  Variable* y = p.NewVariable();
  Binding* x0 = AddBinding(x, &const1, n0, {});
  Binding* y0 = AddBinding(y, &const1, n0, {});
  Binding* x1 = AddBinding(x, &const1, n1, {x0, y0});
  Binding* y1 = AddBinding(y, &const1, n1, {x0, y0});
  Binding* x2 = AddBinding(x, &const1, n2, {x1, y1});
  Binding* y2 = AddBinding(y, &const1, n2, {x1, y1});
  EXPECT_TRUE(n2->HasCombination({x2, y2}));
}

TEST(SolverTest, TestPathFinder) {
  // +-->n2--.       +--+
  // |       v       |  |
  // n1      n4 --> n5<-+
  // |       ^
  // +-->n3--'
  Program p;
  CFGNode* n1 = p.NewCFGNode("n1");
  CFGNode* n2 = n1->ConnectNew("n2");
  CFGNode* n3 = n1->ConnectNew("n3");
  CFGNode* n4 = p.NewCFGNode("n4");
  n2->ConnectTo(n4);
  n3->ConnectTo(n4);
  CFGNode* n5 = n4->ConnectNew("n5");
  n5->ConnectTo(n5);
  internal::PathFinder f;
  EXPECT_TRUE(f.FindAnyPathToNode(n1, n1, {}));
  EXPECT_TRUE(f.FindAnyPathToNode(n1, n1, {n1}));
  EXPECT_TRUE(f.FindAnyPathToNode(n4, n1, {n1}));
  EXPECT_TRUE(f.FindAnyPathToNode(n4, n1, {n2}));
  EXPECT_TRUE(f.FindAnyPathToNode(n4, n1, {n3}));
  EXPECT_FALSE(f.FindAnyPathToNode(n4, n1, {n4}));
  EXPECT_FALSE(f.FindAnyPathToNode(n4, n1, {n2, n3}));
  EXPECT_THAT(f.FindShortestPathToNode(n1, n1, {}), testing::ElementsAre(n1));
  EXPECT_THAT(f.FindShortestPathToNode(n1, n1, {n1}), testing::ElementsAre(n1));
  EXPECT_FALSE(f.FindShortestPathToNode(n4, n1, {n1}).empty());
  EXPECT_THAT(f.FindShortestPathToNode(n4, n1, {n2}),
            testing::ElementsAre(n4, n3, n1));
  EXPECT_THAT(f.FindShortestPathToNode(n4, n1, {n3}),
              testing::ElementsAre(n4, n2, n1));
  EXPECT_TRUE(f.FindShortestPathToNode(n4, n1, {n4}).empty());
  EXPECT_TRUE(f.FindShortestPathToNode(n4, n1, {n2, n3}).empty());
  std::unordered_map<const CFGNode*, int, CFGNodePtrHash> weights;
  weights[n5] = 0;
  weights[n4] = 1;
  weights[n2] = 2;
  weights[n1] = 3;
  EXPECT_EQ(n1->id(), f.FindHighestReachableWeight(n5, {}, weights)->id());
  EXPECT_EQ(n1->id(), f.FindHighestReachableWeight(n5, {n3}, weights)->id());
  EXPECT_EQ(n4->id(), f.FindHighestReachableWeight(n5, {n4}, weights)->id());
  EXPECT_EQ(n2->id(),
            f.FindHighestReachableWeight(n5, {n2, n3}, weights)->id());
  EXPECT_EQ(f.FindHighestReachableWeight(n1, {}, weights), nullptr);
  std::unordered_map<const CFGNode*, int, CFGNodePtrHash> weights2;
  weights2[n5] = 1;
  EXPECT_EQ(f.FindHighestReachableWeight(n5, {n4}, weights2), nullptr);
  std::unordered_map<const CFGNode*, int, CFGNodePtrHash> weights3;
  weights3[n4] = 1;
  weights3[n5] = 2;
  EXPECT_EQ(n4->id(),
            f.FindHighestReachableWeight(n5, {n2, n3}, weights3)->id());
}

TEST(SolverTest, TestFindNodeBackwards) {
  // +-->n2--.       +--->n6--.
  // |   c3  v       |    c3  v
  // n1      n4 --> n5<---+   n8
  // |       ^c1   c2|    |   ^
  // +-->n3--'       +--->n7--'
  Program p;
  CFGNode* n1 = p.NewCFGNode("n1");
  std::string one("1");
  std::string two("2");
  std::string thr("3");
  Variable* x = p.NewVariable();
  Variable* y = p.NewVariable();
  Variable* z = p.NewVariable();
  Binding* c1 = AddBinding(x, &one, n1, {});
  Binding* c2 = AddBinding(y, &two, n1, {});
  Binding* c3 = AddBinding(z, &thr, n1, {});
  CFGNode* n2 = n1->ConnectNew("n2", c3);
  CFGNode* n3 = n1->ConnectNew("n3");
  CFGNode* n4 = p.NewCFGNode("n4", c1);
  n2->ConnectTo(n4);
  n3->ConnectTo(n4);
  CFGNode* n5 = n4->ConnectNew("n5", c2);
  CFGNode* n6 = n5->ConnectNew("n6", c3);
  CFGNode* n7 = n5->ConnectNew("n7");
  n7->ConnectTo(n5);
  CFGNode* n8 = p.NewCFGNode("n8");
  n6->ConnectTo(n8);
  n7->ConnectTo(n8);
  internal::PathFinder f;
  EXPECT_FALSE(f.FindNodeBackwards(n8, n1, {n4}).path_exists);
  internal::QueryResult q1 = f.FindNodeBackwards(n8, n1, {});
  EXPECT_TRUE(q1.path_exists);
  EXPECT_THAT(q1.path, testing::ElementsAre(n5, n4));
  auto q2 = f.FindNodeBackwards(n8, n5, {});
  EXPECT_TRUE(q2.path_exists);
  EXPECT_THAT(q2.path, testing::ElementsAre(n5));
  auto q3 = f.FindNodeBackwards(n5, n4, {});
  EXPECT_TRUE(q3.path_exists);
  EXPECT_THAT(q3.path, testing::ElementsAre(n5, n4));
  auto q4 = f.FindNodeBackwards(n5, n2, {});
  EXPECT_TRUE(q4.path_exists);
  EXPECT_THAT(q4.path, testing::ElementsAre(n5, n4, n2));
  auto q5 = f.FindNodeBackwards(n5, n3, {});
  EXPECT_TRUE(q5.path_exists);
  EXPECT_THAT(q5.path, testing::ElementsAre(n5, n4));
}

TEST(SolverTest, TestConflict) {
  // Moved from cfg_test.py to avoid exposing GetSolver.
  Program p;
  std::string a("a");
  std::string b("b");
  CFGNode* n1 = p.NewCFGNode("n1");
  CFGNode* n2 = n1->ConnectNew("n2");
  CFGNode* n3 = n2->ConnectNew("n3");
  Variable* x = p.NewVariable();
  Binding* xa = AddBinding(x, &a, n1, {});
  AddBinding(x, &b, n2, {});
  Variable* y = p.NewVariable();
  Binding* ya = AddBinding(y, &a, n2, {});
  p.set_entrypoint(n1);
  Solver* solver = p.GetSolver();
  EXPECT_FALSE(solver->Solve({ya, xa}, n3));
  EXPECT_FALSE(solver->Solve({xa, ya}, n3));
}

TEST(SolverTest, TestStrict) {
  // Is a binding visible from the other branch?
  Program p;
  CFGNode* root = p.NewCFGNode("root");
  CFGNode* left = root->ConnectNew("left");
  CFGNode* right = root->ConnectNew("right");
  std::string a("a");
  Variable* x = p.NewVariable();
  AddBinding(x, &a, left, {});
  EXPECT_THAT(x->FilteredData(left, true),
              testing::UnorderedElementsAre(AsDataType(&a)));
  EXPECT_THAT(x->FilteredData(left, false),
              testing::UnorderedElementsAre(AsDataType(&a)));
  EXPECT_THAT(x->FilteredData(right, true), testing::IsEmpty());
  // The result should be empty, but with strict=false, the solver thinks that
  // the binding is visible.
  EXPECT_THAT(x->FilteredData(right, false),
              testing::UnorderedElementsAre(AsDataType(&a)));
}

TEST(SolverTest, TestMetricsBasic) {
  // Are metrics gathered correctly? Check with a very basic query.
  Program p;
  auto n1 = p.NewCFGNode("n1");
  std::string a("a");
  auto x = p.NewVariable();
  auto xa = AddBinding(x, &a, n1, {});

  auto solver = p.GetSolver();
  EXPECT_TRUE(solver->Solve({xa}, n1));

  auto metrics = solver->CalculateMetrics();
  // There should have been only one query.
  EXPECT_EQ(metrics.query_metrics().size(), 1);

  auto qm = metrics.query_metrics().front();
  // The query is resolved at n1, the only node in the CFG.
  EXPECT_EQ(qm.nodes_visited(), 1);
  // n1 is both the first and last node that the query visits.
  EXPECT_EQ(qm.start_node(), n1->id());
  EXPECT_EQ(qm.end_node(), n1->id());
  // Because xa has no source set, it can be solved by itself with no additional
  // bindings needed.
  EXPECT_EQ(qm.initial_binding_count(), 1);
  EXPECT_EQ(qm.total_binding_count(), 1);
  // It's the first query and has only one binding, so it by definition can't be
  // shortcircuited or solved from the cache.
  EXPECT_FALSE(qm.shortcircuited());
  EXPECT_FALSE(qm.from_cache());
}

TEST(SolverTest, TestMetricsCache) {
  Program p;
  auto n0 = p.NewCFGNode("n0");
  auto n1 = n0->ConnectNew("n1");
  auto n2 = n1->ConnectNew("n2");

  std::string a("a"), b("b");

  // At the root, x = "a"
  auto x = p.NewVariable();
  auto xa = AddBinding(x, &a, n0, {});

  auto solver = p.GetSolver();
  EXPECT_TRUE(solver->Solve({xa}, n0));
  EXPECT_TRUE(solver->Solve({xa}, n1));
  EXPECT_TRUE(solver->Solve({xa}, n2));

  auto metrics = solver->CalculateMetrics();

  auto cm = metrics.cache_metrics();
  // There are three cache entries, one from each query.
  EXPECT_EQ(cm.total_size(), 3);
  // The second and third queries hit the cache.
  EXPECT_EQ(cm.hits(), 2);
  // Since each query adds a cache entry, they all must miss the cache first.
  EXPECT_EQ(cm.misses(), 3);

  auto qm = metrics.query_metrics();
  EXPECT_FALSE(qm[0].from_cache());
  EXPECT_EQ(qm[0].end_node(), n0->id());

  EXPECT_TRUE(qm[1].from_cache());
  EXPECT_EQ(qm[1].end_node(), n1->id());

  EXPECT_TRUE(qm[2].from_cache());
  EXPECT_EQ(qm[2].end_node(), n2->id());

  // Adding a new binding will invalidate the solver and destroy the cache.
  auto y = p.NewVariable();
  auto yb = AddBinding(y, &b, n2, {});

  // Seed the cache.
  solver = p.GetSolver();
  EXPECT_TRUE(solver->Solve({xa}, n1));
  // Since xa is bound at n0, the previous query adds 2 entries to the cache.
  EXPECT_EQ(solver->CalculateMetrics().cache_metrics().total_size(), 2);

  EXPECT_TRUE(solver->Solve({xa, yb}, n2));
  auto m2 = solver->CalculateMetrics();
  auto cm2 = metrics.cache_metrics();
  EXPECT_EQ(cm2.total_size(), 3);
  // Because there are >1 initial bindings, the Solver performs a short-circuit
  // check. This hits the cache. The query isn't shortcircuited, so the cache is
  // hit a second time during regular evaluation.
  EXPECT_EQ(cm2.hits(), 2);
  EXPECT_EQ(cm2.misses(), 3);

  auto xy_qm = m2.query_metrics().back();
  // from_cache is set if any part of the query is answered by the cache.
  EXPECT_TRUE(xy_qm.from_cache());
  EXPECT_FALSE(xy_qm.shortcircuited());
  // Shortcircuiting adds 2, then evaluating adds another 2.
  EXPECT_EQ(xy_qm.total_binding_count(), 4);
  // xa is set on n0, but the cache means we can answer the query at n2.
  EXPECT_EQ(xy_qm.end_node(), n2->id());
}

TEST(SolverTest, TestMetricsShortcircuit) {
  Program p;
  auto root = p.NewCFGNode("root");
  auto left = root->ConnectNew("left");
  auto right = root->ConnectNew("right");

  std::string a("a");
  auto la = AddBinding(p.NewVariable(), &a, left, {});
  auto ra = AddBinding(p.NewVariable(), &a, right, {});

  auto solver = p.GetSolver();
  EXPECT_FALSE(solver->Solve({ra, la}, right));

  auto metrics = solver->CalculateMetrics();

  auto cm = metrics.cache_metrics();
  EXPECT_EQ(cm.total_size(), 2);
  EXPECT_EQ(cm.hits(), 0);
  EXPECT_EQ(cm.misses(), 2);

  auto qm = metrics.query_metrics().back();
  EXPECT_TRUE(qm.shortcircuited());
  // During shortcircuiting, the solver tries to solve ({la}, right).
  // But there's no path from right to la's origin, left, so the solver returns
  // false without leaving right.
  EXPECT_EQ(qm.end_node(), right->id());
  EXPECT_FALSE(qm.from_cache());
}

TEST(SolverTest, TestMetricsContradiction) {
  Program p;
  auto root = p.NewCFGNode("root");
  auto left = root->ConnectNew("left");
  auto right = root->ConnectNew("right");
  auto bottom = left->ConnectNew("bottom");
  right->ConnectTo(bottom);

  std::string a("a"), b("b");

  auto ra = AddBinding(p.NewVariable(), &a, root, {});
  auto fa = AddBinding(p.NewVariable(), &a, left, {ra});
  auto fb = AddBinding(p.NewVariable(), &b, right, {});

  auto y = p.NewVariable();
  auto ya = AddBinding(y, &a, bottom, {fa});
  AddBinding(y, &b, bottom, {fb});

  auto solver = p.GetSolver();
  // This query won't be shortcircuited, but will fail.
  EXPECT_FALSE(solver->Solve({ya, fb}, bottom));

  auto qm = solver->CalculateMetrics().query_metrics().back();
  EXPECT_EQ(qm.start_node(), bottom->id());
  EXPECT_FALSE(qm.shortcircuited());
  EXPECT_FALSE(qm.from_cache());
}

}  // namespace
}  // namespace devtools_python_typegraph
