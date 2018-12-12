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
  size_t operator()(const Key& key) const noexcept {
    return key.Hash();
  }
};

// Same as hasher, but for pointer-type keys.
template<typename Key>
struct ptr_hash {
  size_t operator()(const Key* key) const noexcept {
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

// FindOrNull returns a pointer to the value associated with the
// given key if it exists, or nullptr otherwise.
template<typename M>
const V<M>* FindOrNull(const M& map, const K<M>& key) {
  auto it = map.find(key);
  if (it != map.end())
    return &(it->second);
  return nullptr;
}

// FindPtrOrNull returns the pointer value associated with a given key. It is
// designed to be used with maps of keys to pointers. It does not differentiate
// between keys that are not in the map and keys that are mapped to nullptr.
template<typename M>
const V<M> FindPtrOrNull(const M& map, const K<M>& key) {
  auto it = map.find(key);
  if (it != map.end())
    return it->second;
  // V<M> may not be a pointer type, but we're going to assume it is.
  return nullptr;
}

// FindOrDefault returns a const reference to the value associated with the
// given key if it exists, otherwise returns a const reference to the given
// default value.
template<typename M>
const V<M>& FindOrDefault(const M& map, const K<M>& key, const V<M>& value) {
  auto it = map.find(key);
  if (it != map.end())
    return it->second;
  return value;
}

}  // namespace map_util

}  // namespace devtools_python_typegraph

#endif  // PYTYPE_TYPEGRAPH_MAP_UTIL_H_
