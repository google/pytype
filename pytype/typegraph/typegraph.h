// Data structures for the graphs we collect when doing type inference -
// In particular, these data structures model the control flow graph (CFG)
// as well as the points-to or dataflow graph.
// This package also contains some convenience routines e.g. for constructing
// a CFG.
// All allocated memory belongs to a Program instance, and will be
// deallocated whenever said Program is deleted.

#ifndef PYTYPE_TYPEGRAPH_TYPEGRAPH_H_
#define PYTYPE_TYPEGRAPH_TYPEGRAPH_H_

#include <cstddef>
#include <functional>
#include <memory>
#include <set>
#include <string>
#include <unordered_map>
#include <vector>

#include "reachable.h"
#include "map_util.h"
#include "metrics.h"

namespace devtools_python_typegraph {

class CFGNode;
struct Origin;
class Program;
class Binding;
class Variable;

// Forward declare the Solver.
class Solver;

// We declare a fictional opaque type for the raw binding data. The actual
// binding data, the ones added via the AddBinding methods, are shared pointers
// to values of this fictional type. This allows us to share the binding data
// between different Binding and Variable objects.
class DataType;
typedef std::shared_ptr<DataType> BindingData;

// A convenience function to create shareable binding data from raw binding
// data. The |cleanup| argument is called to cleanup the bound data. It can be
// nullptr to indicate that a cleanup is not required.
template <typename RawDataType>
inline BindingData MakeBindingData(RawDataType* raw_data,
                                   std::function<void(DataType*)> cleanup) {
  if (cleanup) {
    return BindingData(reinterpret_cast<DataType*>(raw_data), cleanup);
  } else {
    return BindingData(reinterpret_cast<DataType*>(raw_data), [](DataType*){});
  }
}

// Maximum number of Bindings allowed on a Variable.
// Across a sample of 19352 modules, for files which took more than 25 seconds,
// the largest variable was, on average, 157. For files below 25 seconds, it was
// 7. Additionally, for 99% of files, the largest variable was below 64, so we
// use that as the cutoff.
static const std::size_t MAX_VAR_SIZE = 64;

// Program instances tie together the CFG and the data flow graph (variables
// + bindings). We use this for memory allocation (deleting a program will
// delete everything it allocated) as well as for issuing IDs:
// We need every CFG node to have a unique ID, and this class does the
// corresponding counting.
// This class is thread compatible.
class Program {
 public:
  Program();
  ~Program();

  // Disallow copy and move semantics on Program
  Program(const Program&) = delete;
  Program& operator=(const Program&) = delete;

  CFGNode* NewCFGNode(const std::string& name);
  CFGNode* NewCFGNode(const std::string& name, Binding* condition);
  Variable* NewVariable();
  std::size_t CountCFGNodes() const { return cfg_nodes_.size(); }

  const std::vector<std::unique_ptr<CFGNode>>& cfg_nodes() const {
    return cfg_nodes_;
  }

  std::size_t next_variable_id() { return next_variable_id_; }

  const BindingData& default_data() const { return default_data_; }

  void set_default_data(const BindingData& new_default) {
    default_data_ = new_default;
  }

  std::size_t next_binding_id() const { return next_binding_id_; }

  std::size_t MakeBindingId() {
    std::size_t id = next_binding_id_++;
    return id;
  }

  CFGNode* entrypoint() { return this->entrypoint_; }
  void set_entrypoint(CFGNode* node) { this->entrypoint_ = node; }

  // For testing purposes. Client code should use GetSolver.
  Solver* solver() { return this->solver_.get(); }

  Solver* GetSolver();
  void InvalidateSolver();

  bool is_reachable(const CFGNode* src, const CFGNode* dst);

  Metrics CalculateMetrics();

 private:
  CFGNode* entrypoint_;
  std::size_t next_variable_id_;
  std::size_t next_binding_id_;
  std::unique_ptr<ReachabilityAnalyzer> backward_reachability_;
  // For deallocation, and for node counting:
  std::vector<std::unique_ptr<CFGNode>> cfg_nodes_;
  std::vector<std::unique_ptr<Variable>> variables_;
  std::unique_ptr<Solver> solver_;
  std::vector<SolverMetrics> solver_metrics_;
  BindingData default_data_;
};

// A node in the CFG. Assignments within one CFG node are treated as unordered:
// E.g. if "x = x + 1" is in a single CFG node, both bindings for x will be
// visible from inside that node.
// This class is thread compatible.
class CFGNode {
 public:
  ~CFGNode();

  // Disallow copy and move semantics on CFGNode
  CFGNode(const CFGNode&) = delete;
  CFGNode& operator=(const CFGNode&) = delete;

  // Create a new node, and connect it after this node.
  CFGNode* ConnectNew(const std::string& name);
  CFGNode* ConnectNew(const std::string& name, Binding* condition);

  // Connect to an existing node. O(n), with n current number of outgoing edges.
  void ConnectTo(CFGNode* node);

  // Determines whether a combination of bindings is possible (visible) from
  // the current CFG node.
  bool HasCombination(const std::vector<const Binding*>& bindings);

  bool CanHaveCombination(const std::vector<const Binding*>& bindings);

  // Called whenever a Binding uses a (new) CFG node.
  void RegisterBinding(Binding* a) { bindings_.push_back(a); }

  // Program this node belongs to, for alloc.
  const Program* program() const { return program_; }

  // Node ID. Node IDs are dense (they don't have any gaps).
  std::size_t id() const { return id_; }

  // Node name. E.g. filename plus line number, for generating backtraces.
  const std::string& name() const { return name_; }

  // Node condition. The binding representing condition for node's branch.
  Binding* condition() const { return condition_; }
  void set_condition(Binding* condition) { this->condition_ = condition; }

  // Incoming nodes, i.e. program paths that converge at this point.
  const std::vector<CFGNode*>& incoming() const { return incoming_; }

  // Outgoing nodes, i.e. program branches that start here.
  const std::vector<CFGNode*>& outgoing() const { return outgoing_; }

  // All bindings that variables are assigned at this cfg node. They point back
  // at us through their origin data structures.
  const std::vector<Binding*>& bindings() const { return bindings_; }

  // Ordering CFGNodes is useful for ordered data structures like std::set.
  bool operator<(const CFGNode& other) const { return id() < other.id(); }

  std::size_t Hash() const {
    return id_;
  }

 private:
  CFGNode(Program* program, const std::string& name, std::size_t id,
          Binding* condition, ReachabilityAnalyzer* backward_reachability);

  const std::string name_;
  std::vector<CFGNode*> incoming_;
  std::vector<CFGNode*> outgoing_;
  std::size_t id_;
  std::vector<Binding*> bindings_;
  Program* program_;  // for alloc
  Binding* condition_;
  ReachabilityAnalyzer* backward_reachability_;
  friend Program;  // to allow Program to construct CFGNodes
};

typedef map_util::ptr_hash<CFGNode> CFGNodePtrHash;

// std::set uses less-than comparisons to order elements. Provide a custom
// comparator that compares the underlying elements instead of pointers.
template<typename T>
struct pointer_less {
  bool operator()(const T* a, const T* b) const {
    return *a < *b;
  }
};

typedef std::set<const CFGNode*, pointer_less<CFGNode>> CFGNodeSet;

// A SourceSet is a combination of Bindings that was used to form a Binding.
// E.g., for a statement like "z = a.x + y", a, a.x and y would be the
// SourceSet to create z.
typedef std::set<Binding*, pointer_less<Binding>> SourceSet;

// An "origin" is an explanation of how a binding was constructed. It consists
// of a CFG node and a set of sourcesets.
struct Origin {
  CFGNode* where = nullptr;

  std::set<SourceSet> source_sets;

  explicit Origin(CFGNode* where) { this->where = where; }

  void AddSourceSet(const std::vector<Binding*>& source_set);
  void AddSourceSet(const SourceSet& source_set);
};

// A binding assigns a binding to a (specific) variable. Bindings will hence be
// stored in a dictionary in the Variable class, mapping strings to Binding
// instances.
// This class is thread compatible.
class Binding {
 public:
  ~Binding();

  // Disallow copy and move semantics on Binding
  Binding(const Binding&) = delete;
  Binding& operator=(const Binding&) = delete;

  // Can we "see" this binding from the current cfg node? This will only
  // return true if there is at least one path through the program in which
  // the binding was assigned (and not overwritten afterwards), and all the
  // bindings it depends on were assigned (and not overwritten) before that,
  // etc.
  bool IsVisible(const CFGNode* viewpoint) const;

  // Add an origin - this describes where and how this Binding was formed.
  // Every Binding should have at least one origin, unless it's a constant.
  Origin* AddOrigin(CFGNode* node);
  Origin* AddOrigin(CFGNode* node, const std::vector<Binding*>& source_set);
  Origin* AddOrigin(CFGNode* node, const SourceSet& source_set);

  // Copy the origins from another Binding.
  void CopyOrigins(Binding* other, CFGNode* where);
  void CopyOrigins(Binding* other, CFGNode* where,
                   const SourceSet& additional_sources);

  // Does this Binding depend on a given source?
  bool HasSource(const Binding* binding) const;

  // What Program this Binding belongs to, for alloc.
  Program* program() const { return program_; }

  // The ID of this Binding, used for ordering Bindings.
  std::size_t id() const { return id_; }

  // "<" is used to order Bindings by id.
  bool operator<(const Binding& other) const { return id() < other.id(); }

  // A binding has history ("origins"): It knows where the binding was
  // originally retrieved from, before being assigned to something else here.
  // This also applies if we combined two different bindings (e.g. "a + b") to
  // create the binding referenced here. This is a disjunction of conjunctions -
  // i.e., any of the origins is possible, but all sources in a source_set must
  // appear together.
  const std::vector<std::unique_ptr<Origin>>& origins() const {
    return origins_;
  }

  // An Variable can be assigned in multiple different places in the program.
  // The variable() function gives us the variable that belongs to this binding,
  // to facilitate "reaching definition" analysis: A binding is only still
  // visible if none of the other assignments has overwritten the variable since
  // then.
  Variable* variable() const { return variable_; }

  // User data, for specifying what this binding is set to.
  const BindingData& data() const { return data_; }

  // Used by solver.cc:
  Origin* FindOrigin(const CFGNode* node) const;

 private:
  Binding(Program* program, Variable* variable, const BindingData& data,
          std::size_t id);
  Origin* FindOrAddOrigin(CFGNode* node);

  std::vector<std::unique_ptr<Origin>> origins_;
  std::unordered_map<const CFGNode*, Origin*, CFGNodePtrHash> node_to_origin_;
  Variable* variable_;
  BindingData data_;
  Program* program_;  // for alloc
  std::size_t id_;
  friend Variable;    // to allow Variables to construct Bindings
};

// Since a variable (or attribute, local, global, etc.) can have multiple
// possible bindings during the course of a program, we store it as a union:
// This stores all the bindings that have potentially been assigned to this
// variable so far and can still be visible.
// This class is thread compatible.
class Variable {
 public:
  ~Variable();

  // Disallow copy and move semantics on Variable
  Variable(const Variable&) = delete;
  Variable& operator=(const Variable&) = delete;

  // Filters down the possibilities of this variable, by analyzing the
  // control flow graph. Any definition for this variable that is impossible
  // at the current point in the CFG is filtered out. When the strict flag is
  // not set, may make performance-improving approximations.
  std::vector<Binding*> Filter(const CFGNode* viewpoint,
                               const bool strict = true) const;

  // Prunes all bindings of this variable that are invisible at the CFG node.
  // This only takes the CFG into account, and ignores source sets. It's faster
  // than Filter().
  std::vector<Binding*> Prune(const CFGNode* viewpoint,
                              const bool strict = true);

  // Add another choice to this variable. This will not overwrite this variable
  // in the current CFG node - do that explicitly with RemoveChoicesFromCFGNode.
  // (It's legitimate to have multiple bindings for a variable on the same CFG
  //  node, e.g. if a union type is introduced at that node)
  Binding* AddBinding(const BindingData& data);
  Binding* AddBinding(const BindingData& data, CFGNode* where,
                      const std::vector<Binding*>& source_set);

  // Adds all bindings from another variable to this one.
  void PasteVariable(Variable* variable, CFGNode* where,
                     const SourceSet& additional_sources);
  // Adds a binding from another variable to this one.
  void PasteBinding(Binding* binding, CFGNode* where,
                    const SourceSet& additional_sources);

  // Number of choices we have for this binding.
  std::size_t size() const { return bindings_.size(); }

  // ID of this Variable.
  std::size_t id() const { return id_; }

  // What program this Variable belongs to.
  Program* program() const { return program_; }

  // Array of possibilities for the binding of this variable.
  const std::vector<std::unique_ptr<Binding>>& bindings() const {
    return bindings_;
  }
  // All nodes in the bindings of this variable.
  const CFGNodeSet nodes() const;

  // Get the (unfiltered) data of all bindings.
  const std::vector<DataType*> Data() const;

  // Convenience function for retrieving the filtered data of all bindings.
  const std::vector<DataType*> FilteredData(const CFGNode* viewpoint,
                                            const bool strict = true) const;

 private:
  // Initialize an empty variable
  explicit Variable(Program* program, std::size_t id);
  Binding* FindOrAddBindingHelper(const BindingData& data);
  Binding* FindOrAddBinding(const BindingData& data);
  void RegisterBindingAtNode(Binding* binding, const CFGNode* node);

  std::size_t id_;
  std::vector<std::unique_ptr<Binding>> bindings_;
  std::unordered_map<DataType*, Binding*> data_to_binding_;
  std::unordered_map<const CFGNode*, SourceSet, CFGNodePtrHash>
      cfg_node_to_bindings_;

  Program* program_;  // for alloc
  friend Program;     // to allow Program to construct Variables
  friend Binding;     // to allow Bindings to call RegisterBinding()
};

}  // namespace devtools_python_typegraph

#endif  // PYTYPE_TYPEGRAPH_TYPEGRAPH_H_
