#include <algorithm>

#include "test_util.h"
#include "typegraph.h"

#include "gmock/gmock.h"  // for UnorderedElementsAre
#include "gtest/gtest.h"

namespace devtools_python_typegraph {
namespace {

class TypeGraphTest : public ::testing::Test {
 protected:
  virtual void SetUp() {
    // Construct a simple circular CFG
    //
    //         +-------+
    //         |       |+----->n5
    //         |       ||      |
    //         v       ||      v
    // n0----->n1----->n2----->n3---->n4

    n_[0] = p_.NewCFGNode("n0");
    n_[1] = n_[0]->ConnectNew("n1");
    n_[2] = n_[1]->ConnectNew("n2");
    n_[3] = n_[2]->ConnectNew("n3");
    n_[4] = n_[3]->ConnectNew("n4");
    n_[2]->ConnectTo(n_[1]);
    n_[5] = n_[2]->ConnectNew("n5");
    n_[5]->ConnectTo(n_[3]);

    // This variable assignment corresponds to the following program:
    // x = classA()  # n0
    // y = classB()
    // z = classC()
    // do {
    //   x = 1  # n1
    //   x = z  # n2
    // } while(...);
    // if ... {
    //   x = classD() # n5
    // }
    // a = 2 # n3
    // b = 3 # n4
    // c = z # n4
    std::string classA("classA");
    std::string classB("classB");
    std::string classC("classC");
    std::string classD("classD");
    std::string const1("1");
    std::string const2("2");
    std::string const3("3");

    a_ = p_.NewVariable();
    b_ = p_.NewVariable();
    c_ = p_.NewVariable();
    x_ = p_.NewVariable();
    y_ = p_.NewVariable();
    z_ = p_.NewVariable();

    xval_ = AddBinding(x_, &classA, n_[0], {});
    yval_ = AddBinding(y_, &classB, n_[0], {});
    zval_ = AddBinding(z_, &classC, n_[0], {});
    AddBinding(x_, &const1, n_[1], {});
    for (const auto& binding : z_->bindings()) {
      x_->AddBinding(binding->data(), n_[2], {});
    }
    AddBinding(x_, &classD, n_[5], {});
    AddBinding(a_, &const2, n_[3], {});
    AddBinding(b_, &const3, n_[4], {});
    for (const auto& binding : z_->bindings()) {
      c_->AddBinding(binding->data(), n_[4], {});
    }
  }

  Program p_;

  // All these are owned by p_:
  CFGNode* n_[6];
  Variable *x_, *y_, *z_, *a_, *b_, *c_;
  Binding *xval_, *yval_, *zval_;
};

TEST_F(TypeGraphTest, TestProgram) {
  for (int i = 0; i < p_.CountCFGNodes(); ++i) {
    EXPECT_EQ(p_.cfg_nodes()[i].get(), n_[i]);
  }
  EXPECT_EQ(6, p_.next_variable_id());
}

TEST_F(TypeGraphTest, TestCFG) {
  EXPECT_EQ("n0", n_[0]->name());
  EXPECT_EQ("n1", n_[1]->name());
  EXPECT_EQ("n2", n_[2]->name());
  EXPECT_EQ("n3", n_[3]->name());
  EXPECT_EQ("n4", n_[4]->name());
  EXPECT_EQ("n5", n_[5]->name());

  EXPECT_EQ(1, n_[0]->outgoing().size());
  EXPECT_EQ(1, n_[1]->outgoing().size());
  EXPECT_EQ(3, n_[2]->outgoing().size());
  EXPECT_EQ(1, n_[3]->outgoing().size());
  EXPECT_EQ(0, n_[4]->outgoing().size());
  EXPECT_EQ(1, n_[5]->outgoing().size());

  EXPECT_EQ(0, n_[0]->incoming().size());
  EXPECT_EQ(2, n_[1]->incoming().size());
  EXPECT_EQ(1, n_[2]->incoming().size());
  EXPECT_EQ(2, n_[3]->incoming().size());
  EXPECT_EQ(1, n_[4]->incoming().size());
  EXPECT_EQ(1, n_[5]->incoming().size());
}

TEST_F(TypeGraphTest, TestVariable) {
  // count different bindings encountered for x, y, z at any point in the
  // program
  EXPECT_EQ(4, x_->size());
  EXPECT_EQ(1, y_->size());
  EXPECT_EQ(1, z_->size());
  EXPECT_EQ(1, a_->size());
  EXPECT_EQ(1, b_->size());
  EXPECT_EQ(1, c_->size());

  EXPECT_EQ(1, x_->Filter(n_[1]).size());
  EXPECT_EQ(1, x_->Filter(n_[2]).size());
  EXPECT_EQ(2, x_->Filter(n_[3]).size());
  EXPECT_EQ(2, x_->Filter(n_[4]).size());
  EXPECT_EQ(1, x_->Filter(n_[5]).size());
}

TEST_F(TypeGraphTest, TestBinding) {
  EXPECT_EQ(3, n_[0]->bindings().size());
  EXPECT_EQ(1, n_[1]->bindings().size());
  EXPECT_EQ(1, n_[2]->bindings().size());
  EXPECT_EQ(1, n_[3]->bindings().size());
  EXPECT_EQ(2, n_[4]->bindings().size());
  EXPECT_EQ(1, n_[5]->bindings().size());
}

TEST_F(TypeGraphTest, TestDuplicateEdges) {
  EXPECT_EQ(n_[0]->outgoing().size(), 1);
  n_[0]->ConnectTo(n_[1]);  // identical to existing edge
  EXPECT_EQ(n_[0]->outgoing().size(), 1);
}

TEST_F(TypeGraphTest, TestId) { EXPECT_LT(x_->id(), y_->id()); }

TEST_F(TypeGraphTest, TestPrune) {
  EXPECT_EQ(1, x_->Prune(n_[0]).size());
  EXPECT_EQ(0, a_->Prune(n_[0]).size());
  EXPECT_EQ(1, x_->Prune(n_[1]).size());
  EXPECT_EQ(1, a_->Prune(n_[3]).size());
}

TEST_F(TypeGraphTest, TestVariableProperties) {
  auto xx_ = p_.NewVariable();
  std::string A("A");
  std::string B("B");
  std::string C("C");
  AddBinding(xx_, &A, n_[1], {});
  AddBinding(xx_, &B, n_[2], {});
  AddBinding(xx_, &C, n_[3], {});
  EXPECT_THAT(xx_->nodes(), testing::UnorderedElementsAre(n_[1], n_[2], n_[3]));
  EXPECT_THAT(xx_->Data(), testing::UnorderedElementsAre(
      AsDataType(&A), AsDataType(&B), AsDataType(&C)));
}

TEST_F(TypeGraphTest, testConditionOnStartNode2) {
  // Test that a condition on the initial node blocks the node.
  // At the time of writing this can not happen in pytype. The test guards
  // against future additions.
  // Moved from cfg_test.py to avoid exposing InvalidateSolver.
  Program p;
  CFGNode* n1 = p.NewCFGNode("n1");
  Variable* x = p.NewVariable();
  std::string a("a");
  std::string b("b");
  Binding* x_a = AddBinding(x, &a, n1, {});
  Binding* x_b = AddBinding(x, &b, n1, {});
  EXPECT_TRUE(n1->HasCombination({x_a}));
  n1->set_condition(x_b);
  p.InvalidateSolver();
  EXPECT_FALSE(n1->HasCombination({x_a}));
}

TEST_F(TypeGraphTest, testInvalidateSolver) {
  // Test that the program's Solver is created and destroyed as expected.
  Program p;
  // Adding a Variable or CFGNode doesn't create a solver.
  p.NewVariable();
  CFGNode* n1 = p.NewCFGNode("n1");
  EXPECT_EQ(p.solver(), nullptr);
  n1->HasCombination({});
  EXPECT_NE(p.solver(), nullptr);
  // Adding a new CFGNode invalidates the current solver.
  CFGNode* n2 = p.NewCFGNode("n2");
  EXPECT_EQ(p.solver(), nullptr);
  n2->HasCombination({});
  EXPECT_NE(p.solver(), nullptr);
  // a new Variable by itself doesn't change the CFG, so the solver is valid.
  Variable* x = p.NewVariable();
  EXPECT_NE(p.solver(), nullptr);
  // Adding a binding invalidates the solver.
  std::string a("a");
  Binding* ax = AddBinding(x, &a);
  ax->AddOrigin(n1);
  EXPECT_EQ(p.solver(), nullptr);
  n2->HasCombination({ax});
  EXPECT_NE(p.solver(), nullptr);
}

TEST_F(TypeGraphTest, testMaxVarSize) {
  Program p;
  int def_data(MAX_VAR_SIZE + 3);
  p.set_default_data(MakeBindingData(&def_data, nullptr));
  Variable* x = p.NewVariable();
  int data[MAX_VAR_SIZE];
  for (int i = 0; i < MAX_VAR_SIZE; i++) {
    data[i] = i;
    AddBinding(x, &data[i]);
  }
  EXPECT_EQ(MAX_VAR_SIZE, x->bindings().size());
  EXPECT_EQ(x->bindings()[1].get(), AddBinding(x, &data[1]));
  EXPECT_EQ(x->bindings().back().get(), AddBinding(x, &def_data));
  EXPECT_EQ(MAX_VAR_SIZE, x->bindings().size());
}

TEST_F(TypeGraphTest, TestBindingIDs) {
  // Small sanity check to make sure Binding IDs are created correctly.
  Program p;
  Variable* x = p.NewVariable();
  int one = 1;
  int two = 2;
  Binding* ax1 = AddBinding(x, &one);
  Binding* ax2 = AddBinding(x, &two);
  EXPECT_EQ(0, ax1->id());
  EXPECT_EQ(1, ax2->id());
  EXPECT_EQ(2, p.next_binding_id());
}


TEST_F(TypeGraphTest, TestMetrics) {
  // Small test for making sure Metrics are collected.

  Program p;
  Variable* x = p.NewVariable();
  CFGNode* n0 = p.NewCFGNode("n0");
  CFGNode* n1 = n0->ConnectNew("n1");
  int one = 1;
  Binding* ax1 = AddBinding(x, &one, n1, {});
  ax1->AddOrigin(n0);

  auto metrics = p.CalculateMetrics();
  EXPECT_EQ(metrics.binding_count(), 1);

  auto cfgm = metrics.cfg_node_metrics();
  EXPECT_EQ(cfgm[0].incoming_edge_count(), 0);
  EXPECT_EQ(cfgm[0].outgoing_edge_count(), 1);
  EXPECT_FALSE(cfgm[0].has_condition());

  auto varm = metrics.variable_metrics();
  EXPECT_EQ(varm.size(), 1);
  EXPECT_EQ(varm[0].binding_count(), 1);
  EXPECT_THAT(varm[0].node_ids(), testing::UnorderedElementsAre(0, 1));
}
}  // namespace
}  // namespace devtools_python_typegraph
