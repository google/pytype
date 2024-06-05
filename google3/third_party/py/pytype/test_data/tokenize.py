"""Test case for functions with complex cfg."""
# pylint: skip-file
#
# Modified copy of lib2to3/pgen2/tokenize.py
#
# See tests/test_complex_function.py for the corresponding test case.

import re
import string


ASYNC = '...'
COMMENT = '...'
DEDENT = '...'
ENDMARKER = '...'
ERRORTOKEN = '...'
INDENT = '...'
NAME = '...'
NEWLINE = '...'
NL = '...'
NUMBER = '...'
OP = '...'
endprogs = [re.compile('.*')]
pseudoprog = re.compile('.*')
single_quoted = '...'
STRING = '...'
tabsize = 8
triple_quoted = '...'


def generate_tokens(readline):
    lnum = parenlev = continued = 0
    contstr, needcont = '', 0
    contline = None
    indents = [0]

    # 'stashed' and 'async_*' are used for async/await parsing
    stashed = None
    async_def = False
    async_def_indent = 0
    async_def_nl = False

    while 1:                                   # loop over lines in stream
        try:
            line = readline()
        except StopIteration:
            line = ''
        lnum = lnum + 1
        pos, max = 0, len(line)

        if contstr:                            # continued string
            if not line:
                raise TokenError("EOF in multi-line string", strstart)
            endmatch = endprog.match(line)
            if endmatch:
                pos = end = endmatch.end(0)
                yield (STRING, contstr + line[:end],
                       strstart, (lnum, end), contline + line)
                contstr, needcont = '', 0
                contline = None
            elif needcont and line[-2:] != '\\\n' and line[-3:] != '\\rn':
                yield (ERRORTOKEN, contstr + line,
                           strstart, (lnum, len(line)), contline)
                contstr = ''
                contline = None
                continue
            else:
                contstr = contstr + line
                contline = contline + line
                continue

        elif parenlev == 0 and not continued:  # new statement
            if not line: break
            column = 0
            while pos < max:                   # measure leading whitespace
                if line[pos] == ' ': column = column + 1
                elif line[pos] == '\t': column = (column//tabsize + 1)*tabsize
                elif line[pos] == '\f': column = 0
                else: break
                pos = pos + 1
            if pos == max: break

            if stashed:
                yield stashed
                stashed = None

            if line[pos] in '#rn':           # skip comments or blank lines
                if line[pos] == '#':
                    comment_token = line[pos:].rstrip('rn')
                    nl_pos = pos + len(comment_token)
                    yield (COMMENT, comment_token,
                           (lnum, pos), (lnum, pos + len(comment_token)), line)
                    yield (NL, line[nl_pos:],
                           (lnum, nl_pos), (lnum, len(line)), line)
                else:
                    yield ((NL, COMMENT)[line[pos] == '#'], line[pos:],
                           (lnum, pos), (lnum, len(line)), line)
                continue
            if column > indents[-1]:           # count indents or dedents
                indents.append(column)
                yield (INDENT, line[:pos], (lnum, 0), (lnum, pos), line)
            while column < indents[-1]:
                if column not in indents:
                    raise IndentationError(
                        "unindent does not match any outer indentation level",
                        ("<tokenize>", lnum, pos, line))
                indents = indents[:-1]

                if async_def and async_def_indent >= indents[-1]:
                    async_def = False
                    async_def_nl = False
                    async_def_indent = 0

                yield (DEDENT, '', (lnum, pos), (lnum, pos), line)

            if async_def and async_def_nl and async_def_indent >= indents[-1]:
                async_def = False
                async_def_nl = False
                async_def_indent = 0

        else:                                  # continued statement
            if not line:
                raise TokenError("EOF in multi-line statement", (lnum, 0))
            continued = 0

        while pos < max:
            pseudomatch = pseudoprog.match(line, pos)
            if pseudomatch:                                # scan for tokens
                start, end = pseudomatch.span(1)
                spos, epos, pos = (lnum, start), (lnum, end), end
                token, initial = line[start:end], line[start]

                if initial in string.digits or \
                   (initial == '.' and token != '.'):      # ordinary number
                    yield (NUMBER, token, spos, epos, line)
                elif initial in 'rn':
                    newline = NEWLINE
                    if parenlev > 0:
                        newline = NL
                    elif async_def:
                        async_def_nl = True
                    if stashed:
                        yield stashed
                        stashed = None
                    yield (newline, token, spos, epos, line)

                elif initial == '#':
                    assert not token.endswith("n")
                    if stashed:
                        yield stashed
                        stashed = None
                    yield (COMMENT, token, spos, epos, line)
                elif token in triple_quoted:
                    endprog = endprogs[token]
                    endmatch = endprog.match(line, pos)
                    if endmatch:                           # all on one line
                        pos = endmatch.end(0)
                        token = line[start:pos]
                        if stashed:
                            yield stashed
                            stashed = None
                        yield (STRING, token, spos, (lnum, pos), line)
                    else:
                        strstart = (lnum, start)           # multiple lines
                        contstr = line[start:]
                        contline = line
                        break
                elif initial in single_quoted or \
                    token[:2] in single_quoted or \
                    token[:3] in single_quoted:
                    if token[-1] == 'n':                  # continued string
                        strstart = (lnum, start)
                        endprog = (endprogs[initial] or endprogs[token[1]] or
                                   endprogs[token[2]])
                        contstr, needcont = line[start:], 1
                        contline = line
                        break
                    else:                                  # ordinary string
                        if stashed:
                            yield stashed
                            stashed = None
                        yield (STRING, token, spos, epos, line)
                elif initial.isidentifier():               # ordinary name
                    if token in ('async', 'await'):
                        if async_def:
                            yield (ASYNC if token == 'async' else AWAIT,
                                   token, spos, epos, line)
                            continue

                    tok = (NAME, token, spos, epos, line)
                    if token == 'async' and not stashed:
                        stashed = tok
                        continue

                    if token in ('def', 'for'):
                        if (stashed
                                and stashed[0] == NAME
                                and stashed[1] == 'async'):

                            if token == 'def':
                                async_def = True
                                async_def_indent = indents[-1]

                            yield (ASYNC, stashed[1],
                                   stashed[2], stashed[3],
                                   stashed[4])
                            stashed = None

                    if stashed:
                        yield stashed
                        stashed = None

                    yield tok
                elif initial == '':                      # continued stmt
                    # This yield is new; needed for better idempotency:
                    if stashed:
                        yield stashed
                        stashed = None
                    yield (NL, token, spos, (lnum, pos), line)
                    continued = 1
                else:
                    if initial in '([{': parenlev = parenlev + 1
                    elif initial in ')]}': parenlev = parenlev - 1
                    if stashed:
                        yield stashed
                        stashed = None
                    yield (OP, token, spos, epos, line)
            else:
                yield (ERRORTOKEN, line[pos],
                           (lnum, pos), (lnum, pos+1), line)
                pos = pos + 1

    if stashed:
        yield stashed
        stashed = None

    for indent in indents[1:]:                 # pop remaining indent levels
        yield (DEDENT, '', (lnum, 0), (lnum, 0), '')
    yield (ENDMARKER, '', (lnum, 0), (lnum, 0), '')
