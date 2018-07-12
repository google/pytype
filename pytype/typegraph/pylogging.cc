
#include <cstdlib>
#include <iostream>

#include "pylogging.h"

namespace pytype {
namespace pylogging {

namespace internal {

void ExitWithMsg(const std::string& msg) {
  std::cerr << "UNEXPECTED ERROR: " << msg;
  std::exit(1);
}

}  // namespace internal

}  // namespace pylogging
}  // namespace pytype
