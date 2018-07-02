#include "typegraph.h"

#include <algorithm>
#include <iterator>
#include <stack>
#include <unordered_set>
#include <vector>

#include <cassert>
#include "map_util.h"
#include "memory_util.h"
#include "solver.h"

namespace devtools_python_typegraph {

CFGNode* Program::NewCFGNode(const std::string& name) {
  return NewCFGNode(name, nullptr);
}

CFGNode* Program::NewCFGNode(const std::string& name, Binding* condition) {
  // Count the number of nodes so far and use that as ID
  InvalidateSolver();
  size_t node_nr = CountCFGNodes();
  int n = backward_reachability_->add_node();
  assert((n == node_nr) &&
      "internal error: wrong reachability cache node count.");
  auto node = memory_util::WrapUnique(
      new CFGNode(this, name, node_nr, condition,
                  backward_reachability_.get()));
  CFGNode* np = node.get();
  cfg_nodes_.push_back(std::move(node));
  return np;
}

Variable* Program::NewVariable() {
  auto u = memory_util::WrapUnique(new Variable(this, next_variable_id_));
  next_variable_id_ += 1;
  Variable* up = u.get();
  variables_.push_back(std::move(u));
  return up;
}

size_t Program::CountCFGNodes() const { return cfg_nodes_.size(); }

Program::Program()
    : entrypoint_(nullptr),
      next_variable_id_(0),
      backward_reachability_(memory_util::make_unique<ReachabilityAnalyzer>()),
      default_data_(nullptr) {}

Program::~Program() {}

Solver* Program::GetSolver() {
  if (solver_ == nullptr) solver_ = memory_util::make_unique<Solver>(this);
  return solver_.get();
}

void Program::InvalidateSolver() { solver_.reset(); }

bool Program::is_reachable(const CFGNode* src, const CFGNode* dst) {
  return backward_reachability_->is_reachable(dst->id(), src->id());
}

CFGNode::CFGNode(Program* program, const std::string& name, size_t id,
                 Binding* condition,
                 ReachabilityAnalyzer* backward_reachability)
    : name_(name),
      id_(id),
      program_(program),
      condition_(condition),
      backward_reachability_(backward_reachability) {}

CFGNode::~CFGNode() {}

CFGNode* CFGNode::ConnectNew(const std::string& name) {
  return ConnectNew(name, nullptr);
}

CFGNode* CFGNode::ConnectNew(const std::string& name, Binding* condition) {
  CFGNode* node = program_->NewCFGNode(name, condition);

  this->ConnectTo(node);
  return node;
}

void CFGNode::ConnectTo(CFGNode* node) {
  // Another option for avoiding duplication would be to store outgoing edges in
  // a set. But sets are more expensive to iterate over, and we later iterate
  // over the outgoing edges many times, but we only store them once.
  for (CFGNode* n : outgoing_) {
    if (n == node) {
      return;  // already connected
    }
  }
  program_->InvalidateSolver();
  node->incoming_.push_back(this);
  this->outgoing_.push_back(node);
  this->backward_reachability_->add_connection(node->id(), this->id());
}

bool CFGNode::HasCombination(const std::vector<const Binding*>& bindings) {
  return program_->GetSolver()->Solve(bindings, this);
}

bool CFGNode::CanHaveCombination(const std::vector<const Binding*>& bindings) {
  for (const Binding* goal : bindings) {
    bool origin_reachable = false;
    for (const auto& origin : goal->origins()) {
      if (this->backward_reachability_->is_reachable(this->id(),
                                                     origin->where->id())) {
        origin_reachable = true;
        break;
      }
    }
    if (!origin_reachable) {
      return false;
    }
  }
  return true;
}

void Origin::AddSourceSet(const std::vector<Binding*>& source_set) {
  source_sets.emplace(source_set.begin(), source_set.end());
}

void Origin::AddSourceSet(const SourceSet& source_set) {
  source_sets.emplace(source_set.begin(), source_set.end());
}

// Create a Binding, and also registers it with its CFG node.
Binding::Binding(Program* program, Variable* variable, void* data)
    : variable_(variable), data_(data), program_(program) {}

Binding::~Binding() {}

bool Binding::IsVisible(const CFGNode* viewpoint) const {
  Solver* s = program_->GetSolver();
  return s->Solve({this}, viewpoint);
}

Origin* Binding::FindOrigin(const CFGNode* node) const {
  return map_util::FindPtrOrNull(node_to_origin_, node);
}

Origin* Binding::FindOrAddOrigin(CFGNode* node) {
  auto it = node_to_origin_.find(node);
  if (it == node_to_origin_.end()) {
    auto o = memory_util::make_unique<Origin>(node);
    Origin* op = o.get();
    origins_.push_back(std::move(o));
    node_to_origin_[node] = op;
    variable_->RegisterBindingAtNode(this, node);
    node->RegisterBinding(this);
    return op;
  }
  return it->second;
}

Origin* Binding::AddOrigin(CFGNode* node) {
  program_->InvalidateSolver();
  return FindOrAddOrigin(node);
}

Origin* Binding::AddOrigin(CFGNode* node,
                           const std::vector<Binding*>& source_set) {
  program_->InvalidateSolver();
  Origin* origin = FindOrAddOrigin(node);
  origin->AddSourceSet(source_set);
  return origin;
}

Origin* Binding::AddOrigin(CFGNode* node, const SourceSet& source_set) {
  Origin* origin = FindOrAddOrigin(node);
  origin->AddSourceSet(source_set);
  return origin;
}

void Binding::CopyOrigins(Binding* other, CFGNode* where) {
  CopyOrigins(other, where, SourceSet());
}

void Binding::CopyOrigins(Binding* other, CFGNode* where,
                          const SourceSet& additional_sources) {
  if (where) {
    SourceSet sources =
        SourceSet(additional_sources.begin(), additional_sources.end());
    sources.insert(other);
    AddOrigin(where, sources);
  } else {
    for (const auto& o : other->origins()) {
      for (const SourceSet& source_set : o->source_sets) {
        SourceSet sources = SourceSet(additional_sources);
        sources.insert(source_set.begin(), source_set.end());
        AddOrigin(o->where, sources);
      }
    }
  }
}

bool Binding::HasSource(const Binding* binding) const {
  if (this == binding) return true;
  for (const auto& o : origins()) {
    for (const SourceSet& source_set : o->source_sets) {
      for (const Binding* source : source_set) {
        if (source->HasSource(binding)) {
          return true;
        }
      }
    }
  }
  return false;
}

Variable::Variable(Program* program, size_t id) : id_(id), program_(program) {}

Binding* Variable::FindOrAddBinding(void* data) {
  if (bindings_.size() >= MAX_VAR_SIZE - 1 &&
      !map_util::ContainsKey(data_to_binding_, data))
    data = this->program_->default_data();
  auto it = data_to_binding_.find(data);
  if (it == data_to_binding_.end()) {
    program_->InvalidateSolver();
    auto binding =
        std::unique_ptr<Binding>(new Binding(this->program_, this, data));
    Binding* bp = binding.get();
    bindings_.push_back(std::move(binding));
    data_to_binding_[data] = bp;
    return bp;
  }
  return it->second;
}

void Variable::RegisterBindingAtNode(Binding* binding, const CFGNode* node) {
  if (!map_util::ContainsKey(cfg_node_to_bindings_, node)) {
    cfg_node_to_bindings_[node] = SourceSet();
  }
  cfg_node_to_bindings_[node].insert(binding);
}

Binding* Variable::AddBinding(void* data) { return FindOrAddBinding(data); }

Binding* Variable::AddBinding(void* data, CFGNode* where,
                              const std::vector<Binding*>& source_set) {
  Binding* binding = FindOrAddBinding(data);
  Origin* origin = binding->AddOrigin(where);
  origin->AddSourceSet(source_set);
  return binding;
}

void Variable::PasteVariable(Variable* variable, CFGNode* where,
                             const SourceSet& additional_sources) {
  for (const auto& b : variable->bindings()) {
    PasteBinding(b.get(), where, additional_sources);
  }
}

void Variable::PasteBinding(Binding* binding, CFGNode* where,
                            const SourceSet& additional_sources) {
  Binding* new_binding = AddBinding(binding->data());
  if (!where) {
    new_binding->CopyOrigins(binding, nullptr, additional_sources);
    return;
  }
  for (const auto& o : binding->origins()) {
    if (o->where->id() != where->id()) {
      // Optimization: If all the bindings of the old variable happen at the
      // same CFG node as the one we're assigning now, we can copy the old
      // source_set instead of linking to it. That way, the solver has to
      // consider fewer levels.
      new_binding->CopyOrigins(binding, where, additional_sources);
      return;
    }
  }
  new_binding->CopyOrigins(binding, nullptr, additional_sources);
}

const std::set<const CFGNode*> Variable::nodes() const {
  std::set<const CFGNode*> nodes;
  for (auto kvpair : cfg_node_to_bindings_) {
    nodes.insert(kvpair.first);
  }
  return nodes;
}

const std::vector<void*> Variable::Data() const {
  std::vector<void*> data;
  data.reserve(bindings_.size());
  for (const auto& a : bindings_) {
    data.push_back(a->data());
  }
  return data;
}

const std::vector<void*> Variable::FilteredData(
    const CFGNode* viewpoint) const {
  std::vector<Binding*> filtered = Filter(viewpoint);
  std::vector<void*> data;
  data.reserve(filtered.size());
  for (const auto& a : filtered) {
    data.push_back(a->data());
  }
  return data;
}

std::vector<Binding*> Variable::Filter(const CFGNode* viewpoint) const {
  std::vector<Binding*> filtered;
  filtered.reserve(bindings_.size());
  for (const auto& binding : bindings_) {
    if (binding->IsVisible(viewpoint)) {
      filtered.push_back(binding.get());
    }
  }
  return filtered;
}

std::set<Binding*> Variable::Prune(const CFGNode* viewpoint) {
  std::stack<const CFGNode*> stack;
  std::set<Binding*> result;
  if (!viewpoint) {
    for (const auto& r : bindings_) {
      result.insert(r.get());
    }
    return result;
  }
  if (!viewpoint) {
    for (const auto& binding : bindings_) {
      result.insert(binding.get());
    }
    return result;
  }
  std::unordered_set<const CFGNode*> seen;
  stack.push(viewpoint);
  do {
    const CFGNode* node = stack.top();
    stack.pop();
    seen.insert(node);
    if (map_util::ContainsKey(cfg_node_to_bindings_, node)) {
      assert((cfg_node_to_bindings_[node].size()) && "empty binding list");
      for (auto v : cfg_node_to_bindings_[node]) {
        result.insert(v);
      }
      // Don't expand this node - previous assignments to this variable will
      // be invisible, since they're overwritten here.
      continue;
    } else {
      for (CFGNode* next : node->incoming()) {
        if (!map_util::ContainsKey(seen, next)) {
          stack.push(next);
        }
      }
    }
  } while (!stack.empty());
  return result;
}

Variable::~Variable() {}

}  // namespace devtools_python_typegraph
