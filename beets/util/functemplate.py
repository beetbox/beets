# This file is part of beets.
# Copyright 2011, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""This module implements a string formatter based on the standard PEP
292 string.Template class extended with function calls. Variables, as
with string.Template, are indicated with $ and functions are delimited
with %.

This module assumes that everything is Unicode: the template and the
substitution values. Bytestrings are not supported. Also, the templates
always behave like the ``safe_substitute`` method in the standard
library: unknown symbols are left intact.

This is sort of like a tiny, horrible degeneration of a real templating
engine like Jinja2 or Mustache.
"""
import re

SYMBOL_DELIM = u'$'
FUNC_DELIM = u'%'
GROUP_OPEN = u'{'
GROUP_CLOSE = u'}'
ARG_SEP = u','
ESCAPE_CHAR = u'$'

class Environment(object):
    """Contains the values and functions to be substituted into a
    template.
    """
    def __init__(self, values, functions):
        self.values = values
        self.functions = functions

class Symbol(object):
    """A variable-substitution symbol in a template."""
    def __init__(self, ident, original):
        self.ident = ident
        self.original = original

    def __repr__(self):
        return u'Symbol(%s)' % repr(self.ident)

    def evaluate(self, env):
        """Evaluate the symbol in the environment, returning a Unicode
        string.
        """
        if self.ident in env.values:
            # Substitute for a value.
            return env.values[self.ident]
        else:
            # Keep original text.
            return self.original

class Call(object):
    """A function call in a template."""
    def __init__(self, ident, args, original):
        self.ident = ident
        self.args = args
        self.original = original

    def __repr__(self):
        return u'Call(%s, %s, %s)' % (repr(self.ident), repr(self.args),
                                      repr(self.original))

    def evaluate(self, env):
        """Evaluate the function call in the environment, returning a
        Unicode string.
        """
        if self.ident in env.functions:
            arg_vals = [expr.evaluate(env) for expr in self.args]
            try:
                out = env.functions[self.ident](*arg_vals)
            except Exception, exc:
                # Function raised exception! Maybe inlining the name of
                # the exception will help debug.
                return u'<%s>' % unicode(exc)
            return unicode(out)
        else:
            return self.original

class Expression(object):
    """Top-level template construct: contains a list of text blobs,
    Symbols, and Calls.
    """
    def __init__(self, parts):
        self.parts = parts

    def __repr__(self):
        return u'Expression(%s)' % (repr(self.parts))

    def evaluate(self, env):
        """Evaluate the entire expression in the environment, returning
        a Unicode string.
        """
        out = []
        for part in self.parts:
            if isinstance(part, basestring):
                out.append(part)
            else:
                out.append(part.evaluate(env))
        return u''.join(out)

class ParseError(Exception):
    pass

class Parser(object):
    """Parses a template expression string. Instantiate the class with
    the template source and call ``parse_expression``. The ``pos`` field
    will indicate the character after the expression finished and
    ``parts`` will contain a list of Unicode strings, Symbols, and Calls
    reflecting the concatenated portions of the expression.

    This is a terrible, ad-hoc parser implementation based on a
    left-to-right scan with no lexing step to speak of; it's probably
    both inefficient and incorrect. Maybe this should eventually be
    replaced with a real, accepted parsing technique (PEG, parser
    generator, etc.).
    """
    def __init__(self, string):
        self.string = string
        self.pos = 0
        self.parts = []

    # Common parsing resources.
    special_chars = (SYMBOL_DELIM, FUNC_DELIM, GROUP_OPEN, GROUP_CLOSE,
                     ARG_SEP, ESCAPE_CHAR)
    special_char_re = re.compile(ur'[%s]|$' %
                                 u''.join(re.escape(c) for c in special_chars))

    def parse_expression(self):
        """Parse a template expression starting at ``pos``. Resulting
        components (Unicode strings, Symbols, and Calls) are added to
        the ``parts`` field, a list.  The ``pos`` field is updated to be
        the next character after the expression.
        """
        text_parts = []

        while self.pos < len(self.string):
            char = self.string[self.pos]

            if char not in self.special_chars:
                # A non-special character. Skip to the next special
                # character, treating the interstice as literal text.
                next_pos = (
                    self.special_char_re.search(self.string[self.pos:]).start()
                    + self.pos
                )
                text_parts.append(self.string[self.pos:next_pos])
                self.pos = next_pos
                continue

            if self.pos == len(self.string) - 1:
                # The last character can never begin a structure, so we
                # just interpret it as a literal character (unless it
                # terminates the expression, as with , and }).
                if char not in (GROUP_CLOSE, ARG_SEP):
                    text_parts.append(char)
                    self.pos += 1
                break

            next_char = self.string[self.pos + 1]
            if char == ESCAPE_CHAR and next_char in \
                  (SYMBOL_DELIM, FUNC_DELIM, GROUP_CLOSE, ARG_SEP):
                # An escaped special character ($$, $}, etc.). Note that
                # ${ is not an escape sequence: this is ambiguous with
                # the start of a symbol and it's not necessary (just
                # using { suffices in all cases).
                text_parts.append(next_char)
                self.pos += 2 # Skip the next character.
                continue

            # Shift all characters collected so far into a single string.
            if text_parts:
                self.parts.append(u''.join(text_parts))
                text_parts = []

            if char == SYMBOL_DELIM:
                # Parse a symbol.
                self.parse_symbol()
            elif char == FUNC_DELIM:
                # Parse a function call.
                self.parse_call()
            elif char in (GROUP_CLOSE, ARG_SEP):
                # Template terminated.
                break
            elif char == GROUP_OPEN:
                # Start of a group has no meaning hear; just pass
                # through the character.
                text_parts.append(char)
                self.pos += 1
            else:
                assert False

        # If any parsed characters remain, shift them into a string.
        if text_parts:
            self.parts.append(u''.join(text_parts))

    def parse_symbol(self):
        """Parse a variable reference (like ``$foo`` or ``${foo}``)
        starting at ``pos``. Possibly appends a Symbol object (or,
        failing that, text) to the ``parts`` field and updates ``pos``.
        The character at ``pos`` must, as a precondition, be ``$``.
        """
        assert self.pos < len(self.string)
        assert self.string[self.pos] == SYMBOL_DELIM

        if self.pos == len(self.string) - 1:
            # Last character.
            self.parts.append(SYMBOL_DELIM)
            self.pos += 1
            return

        next_char = self.string[self.pos + 1]
        start_pos = self.pos
        self.pos += 1

        if next_char == GROUP_OPEN:
            # A symbol like ${this}.
            self.pos += 1 # Skip opening.
            closer = self.string.find(GROUP_CLOSE, self.pos)
            if closer == -1 or closer == self.pos:
                # No closing brace found or identifier is empty.
                self.parts.append(self.string[start_pos:self.pos])
            else:
                # Closer found.
                ident = self.string[self.pos:closer]
                self.pos = closer + 1
                self.parts.append(Symbol(ident,
                                         self.string[start_pos:self.pos]))

        else:
            # A bare-word symbol.
            ident = self._parse_ident()
            if ident:
                # Found a real symbol.
                self.parts.append(Symbol(ident,
                                         self.string[start_pos:self.pos]))
            else:
                # A standalone $.
                self.parts.append(SYMBOL_DELIM)

    def parse_call(self):
        """Parse a function call (like ``%foo{bar,baz}``) starting at
        ``pos``.  Possibly appends a Call object to ``parts`` and update
        ``pos``. The character at ``pos`` must be ``%``.
        """
        assert self.pos < len(self.string)
        assert self.string[self.pos] == FUNC_DELIM

        start_pos = self.pos
        self.pos += 1

        ident = self._parse_ident()
        if not ident:
            # No function name.
            self.parts.append(FUNC_DELIM)
            return
        
        if self.pos >= len(self.string):
            # Identifier terminates string.
            self.parts.append(self.string[start_pos:self.pos])
            return

        if self.string[self.pos] != GROUP_OPEN:
            # Argument list not opened.
            self.parts.append(self.string[start_pos:self.pos])
            return

        # Skip past opening brace and try to parse an argument list.
        self.pos += 1
        args = self.parse_argument_list()
        if self.pos >= len(self.string) or \
           self.string[self.pos] != GROUP_CLOSE:
            # Arguments unclosed.
            self.parts.append(self.string[start_pos:self.pos])
            return

        self.pos += 1 # Move past closing brace.
        self.parts.append(Call(ident, args, self.string[start_pos:self.pos]))

    def parse_argument_list(self):
        """Parse a list of arguments starting at ``pos``, returning a
        list of Expression objects. Does not modify ``parts``. Should
        leave ``pos`` pointing to a } character or the end of the
        string.
        """
        # Try to parse a subexpression in a subparser.
        expressions = []

        while self.pos < len(self.string):
            subparser = Parser(self.string[self.pos:])
            subparser.parse_expression()

            # Extract and advance past the parsed expression.
            expressions.append(Expression(subparser.parts))
            self.pos += subparser.pos 

            if self.pos >= len(self.string) or \
               self.string[self.pos] == GROUP_CLOSE:
                # Argument list terminated by EOF or closing brace.
                break

            # Only other way to terminate an expression is with ,.
            # Continue to the next argument.
            assert self.string[self.pos] == ARG_SEP
            self.pos += 1

        return expressions

    def _parse_ident(self):
        """Parse an identifier and return it (possibly an empty string).
        Updates ``pos``.
        """
        remainder = self.string[self.pos:]
        ident = re.match(ur'\w*', remainder).group(0)
        self.pos += len(ident)
        return ident

def _parse(template):
    """Parse a top-level template string Expression. Any extraneous text
    is considered literal text.
    """
    parser = Parser(template)
    parser.parse_expression()

    parts = parser.parts
    remainder = parser.string[parser.pos:]
    if remainder:
        parts.append(remainder)
    return Expression(parts)

class Template(object):
    """A string template, including text, Symbols, and Calls.
    """
    def __init__(self, template):
        self.expr = _parse(template)
        self.original = template

    def substitute(self, values={}, functions={}):
        """Evaluate the template given the values and functions.
        """
        return self.expr.evaluate(Environment(values, functions))
