#ifndef PYTYPE_PYI_REFHOLDER_H_
#define PYTYPE_PYI_REFHOLDER_H_

#include <Python.h>

namespace pytype {

// Holder for a reference to a PyObject that automatically increments the
// refcount upon assignment and decrements it at reassignment and destruction.
class RefHolder {
 public:
  RefHolder() : object_(NULL) {}

  // Initialize with an object, increment the refcount.
  RefHolder(PyObject* object) {
    Py_XINCREF(object);
    object_ = object;
  }

  ~RefHolder() { Py_XDECREF(object_); }

  RefHolder& operator=(PyObject* object) {
    // Must increment before decrement just in case object==object_.
    Py_XINCREF(object);
    Py_XDECREF(object_);
    object_ = object;
    return *this;
  }

  // Allow RefHolder to be used in place of a PyObject*.
  operator PyObject* () const {
    return object_;
  }

 private:
  PyObject* object_;
};

}  // end namespace pytype

#endif  // PYTYPE_PYI_REFHOLDER_H_
