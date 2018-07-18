#include <iostream>

#include "cfg_logging.h"

namespace pytype {
namespace typegraph {

namespace internal {

pytype::pylogging::LogObject CFGLogger::log;

void CFGLogger::Init() {
  CFGLogger::log.Init("pytype.typegraph.cfg");
}

int CFGLogger::Shutdown(PyObject* unused) {
  CFGLogger::log.Detach();
  return 0;
}

FatalStreamer::~FatalStreamer() {
  std::cerr << stream_.str();
  std::exit(1);
}

}  // namespace internal

}  // namespace typegraph
}  // namespace pytype
