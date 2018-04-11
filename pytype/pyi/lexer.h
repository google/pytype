#ifndef PYTYPE_PYI_LEXER_H_
#define PYTYPE_PYI_LEXER_H_

#include <vector>
#include <Python.h>

#include "parser.tab.hh"
#include "location.hh"
#include "refholder.h"

namespace pytype {

class Lexer {
 public:
  Lexer(const char* bytes, int length);
  ~Lexer();

  // The generated scanner associated with this lexer.
  void* scanner() const { return scanner_; }

  // Return the current indentation.
  int CurrentIndentation() const { return indents_.back(); }

  // Push and indentation to the new width.
  void PushIndentation(int width);

  // Pop indentations greater than specified width.
  bool PopIndentationTo(int width);

  // Pop one dedent, return true iff there was one to pop.
  bool PopDedent();

  // A simple counter to track open brackets.
  int bracket_count_;

  // Saved location for start of triplequoted.
  int start_line_;
  int start_column_;

  // The last error message (NULL if there hasn't been an error).
  RefHolder error_message_;

 private:
  // Keep a reference to the generated scanner.  This is an opaque type that
  // can be passed to generated functions such as pytypelex().  Note that the
  // scanner's "extra" field will also point back to the Lexer object so that
  // actions within the scanner can access the Lexer.
  void* scanner_;

  // A stack of indents.  There is always a first element of value 0.
  std::vector<int> indents_;

  // A count of dedents that have not yet been returned.
  int pending_dedents_;
};


}  // end namespace pytype

// pytypeget_extra is generated in lexer.lex.cc, and it needs to be declared
// here so the parser knows about it.
pytype::Lexer* pytypeget_extra(void* scanner);

#endif  // PYTYPE_PYI_LEXER_H_
