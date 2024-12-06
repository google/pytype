// This file provides a few utility functions for working with
// std::unordered_map and other containers with similar interfaces. (e.g. any
// containers whose find() method returns an iterator pointing to the key and
// the associated value.)
// The functions are self-explanatory based on their names.

#ifndef PYTYPE_TYPEGRAPH_MAP_UTIL_H_
#define PYTYPE_TYPEGRAPH_MAP_UTIL_H_

#include <cstddef>

namespace devtools_python_typegraph {

namespace map_util {

// Functor for calculating the hash of an object using its Hash() method.
template<typename Key>
struct hash {
  std::size_t operator()(const Key& key) const noexcept {
    return key.Hash();
  }
};

// Same as hasher, but for pointer-type keys.
template<typename Key>
struct ptr_hash {
  std::size_t operator()(const Key* key) const noexcept {
    return key->Hash();
  }
};

// Typename aliases for map's key and value types.
// e.g. for unordered_map<string, int>, M = unordered_map, K = string, V = int.
template<typename M>
using K = typename M::key_type;
template<typename M>
using V = typename M::mapped_type;

template<typename M>
bool ContainsKey(const M& map, const K<M>& key) {
  return map.find(key) != map.end();
}

}  // namespace map_util

}  // namespace devtools_python_typegraph

#endif  // PYTYPE_TYPEGRAPH_MAP_UTIL_H_
