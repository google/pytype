#ifndef PYTYPE_TYPEGRAPH_PYLOGGING_H_
#define PYTYPE_TYPEGRAPH_PYLOGGING_H_

#include <Python.h>

#include <sstream>
#include <string>

namespace pytype {
namespace pylogging{

namespace internal {

void ExitWithMsg(const std::string& msg);

class LogStreamer {
 public:
  // |method_name| is the logging method to call on |log_object|. This streamer
  // class merely holds a borrowed reference to |log_object|. A streamer
  // instance will become invalid once the parent LogObject goes away.
  LogStreamer(const char* filename,
              int line,
              const char* method_name,
              PyObject* log_object)
      : method_name_(method_name), log_object_(log_object) {
#ifdef PYTYPE_ENABLE_CPP_LOGGING
    stream_ = new std::stringstream;
    if (log_object == nullptr) {
      ExitWithMsg("Cannot log with a NULL log object.\n");
    }
    *stream_ << filename << ":" << line << ": ";
#endif
  }

  ~LogStreamer() {
#ifdef PYTYPE_ENABLE_CPP_LOGGING
    PyObject* result = PyObject_CallMethod(log_object_,
                                           const_cast<char*>(method_name_),
                                           const_cast<char*>("s"),
                                           stream_->str().c_str());
    delete stream_;
    if (result == nullptr) {
      PyErr_Print();
      ExitWithMsg(
          std::string("Unable to log to '") + method_name_ + "' stream.\n");
    }
    Py_DECREF(result);
#endif
  }

  template <typename T>
  LogStreamer& operator<<(T val) {
#ifdef PYTYPE_ENABLE_CPP_LOGGING
    *stream_ << val;
#endif
    return *this;
  }

 private:
  // We want to keep this class copyable. Hence, we want the stream field to be
  // a pointer as std::stringstream is not a copyable class. An alternate is to
  // use std::shared_ptr, but that is an overkill for the usecase here as we do
  // not need to share this stream object with any other entity.
  std::stringstream* stream_;

  const char* method_name_;
  PyObject* log_object_;
};

}  // namespace internal

// It is assumed that all methods of this class will be called while holding
// the Python GIL.
class LogObject {
 public:
  LogObject() : log_obj_(nullptr) {}

  // This method imports the Python "logging" module and
  // creates a log object with |name| by calling logging.getLogger.
  void Init(const std::string& name) {
#ifdef PYTYPE_ENABLE_CPP_LOGGING
    PyObject* logging_module = PyImport_ImportModule("logging");
    if (logging_module == nullptr) {
      PyErr_Print();
      internal::ExitWithMsg("Error importing the Python 'logging' library.\n");
    }
    log_obj_ = PyObject_CallMethod(
        logging_module,
        const_cast<char*>("getLogger"),
        const_cast<char*>("s"),
        name.c_str());
    Py_DECREF(logging_module);
    if (log_obj_ == nullptr) {
      PyErr_Print();
      internal::ExitWithMsg(
          std::string("Error while creating a logger for '") + name + "'.\n");
    }
#endif
  }


  void Detach() {
#ifdef PYTYPE_ENABLE_CPP_LOGGING
    Py_XDECREF(log_obj_);
#endif
  }

#define STREAMER_METHOD(TYPE, method_name)                                   \
 public:                                                                     \
  internal::LogStreamer TYPE##_Streamer(                                     \
      const char* filename, int line) const {                                \
    return internal::LogStreamer(filename, line, method_name, log_obj_);     \
  }

  STREAMER_METHOD(DEBUG, "debug")
  STREAMER_METHOD(INFO, "info")
  STREAMER_METHOD(WARN, "warn")
  STREAMER_METHOD(ERROR, "error")
  STREAMER_METHOD(CRITICAL, "critical")

 private:
  PyObject* log_obj_;

  // Disallow copy and assign.
  LogObject(const LogObject&) = delete;
  LogObject& operator=(const LogObject&) = delete;
};

}  // namespace pylogging
}  // namespace pytype

#endif  // PYTYPE_TYPEGRAPH_PYLOGGING_H_
