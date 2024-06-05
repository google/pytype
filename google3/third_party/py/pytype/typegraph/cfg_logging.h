#ifndef PYTYPE_TYPEGRAPH_CFG_LOGGING_H_
#define PYTYPE_TYPEGRAPH_CFG_LOGGING_H_

#include <sstream>

#include "pylogging.h"

namespace pytype {
namespace typegraph {

namespace internal {

class CFGLogger {
 public:
  static void Init();
  static int Shutdown(PyObject *);
  static pytype::pylogging::LogObject log;
};

class FatalStreamer {
 public:
  FatalStreamer(const char* filename, int line) {
    stream_ << filename << ":" << line << ": ";
  }

  ~FatalStreamer();

  template <typename ValType>
  FatalStreamer& operator<<(ValType val) {
    stream_ << val;
    return *this;
  }

 public:
  std::stringstream stream_;
};

}  // namespace internal

}  // namespace typegraph
}  // namespace pytype

#define LOG(TYPE) pytype::typegraph::internal::CFGLogger::log.TYPE##_Streamer( \
    __FILE__, __LINE__)

#define CHECK(COND) if (!(COND)) pytype::typegraph::internal::FatalStreamer( \
    __FILE__, __LINE__)

#endif  // PYTYPE_TYPEGRAPH_CFG_LOGGING_H_
