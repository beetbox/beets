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
engine like Jinja2.
"""
import re

SYMBOL_DELIM = u'$'
FUNC_DELIM = u'%'
GROUP_OPEN = u'{'
GROUP_CLOSE = u'}'
ARG_SEP = u','

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
        return u'Call(%s, %s, %s)' % (repr(self.ident, self.args,
                                           self.original))

    def evaluate(self, env):
        """Evaluate the function call in the environment, returning a
        Unicode string.
        """
        if self.ident in env.functions:
            return u'TODO'
        else:
            return self.original

class ParseError(Exception):
    pass

class Parser(object):
    """Parses a template string.

    This is a terrible parser implementation based on a
    character-by-character, left-to-right scan with no lexing step to
    speak of; it's probably both inefficient and incorrect. Maybe this
    should eventually be replaced with a real, accepted parsing
    technique.
    """
    def __init__(self, string):
        self.string = string
        self.pos = 0
        self.parts = []

    def parse_template(self):
        """Parse a template expression starting at ``pos``. Resulting
        components (Unicode strings, Symbols, and Calls) are added to
        the ``parts`` field, a list.  The ``pos`` field is updated to be
        the next character after the expression.
        """
        text_parts = []

        while self.pos < len(self.string):
            char = self.string[self.pos]

            if char not in (SYMBOL_DELIM, FUNC_DELIM, GROUP_OPEN,
                            GROUP_CLOSE, ARG_SEP):
                # A non-special character.
                # TODO: This can be made more efficient by repeatedly asking
                # for the next special character rather than walking through
                # the non-specials one at a time.
                text_parts.append(char)
                self.pos += 1
                continue

            if self.pos == len(self.string) - 1:
                # The last character can never begin a structure, so we just
                # interpret it as a literal character.
                text_parts.append(char)
                self.pos += 1
                continue

            next_char = self.string[self.pos + 1]
            if char == next_char:
                # An escaped special character ($$, etc.).
                text_parts.append(char)
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

    def _parse_ident(self):
        """Parse an identifier and return it (possibly an empty string).
        Updates ``pos``.
        """
        remainder = self.string[self.pos:]
        ident = re.match(ur'\w*', remainder).group(0)
        self.pos += len(ident)
        return ident

def _parse(template):
    """Parse a top-level template string expression, returning a list of
    nodes. Any extraneous text is considered literal text.
    """
    parser = Parser(template)
    parser.parse_template()

    parts = parser.parts
    remainder = parser.string[parser.pos:]
    if remainder:
        parts.append(remainder)
    return parts

class Template(object):
    """A string template, including text, Symbols, and Calls.
    """
    def __init__(self, template):
        self.parts = _parse(template)
        self.original = template

    def evaluate(self, env):
        """Evaluate the entire template in the environment, returning a
        Unicode string.
        """
        out = []
        for part in self.parts:
            if isinstance(part, basestring):
                out.append(part)
            else:
                out.append(part.evaluate(env))
        return u''.join(out)

    def substitute(self, values={}, functions={}):
        """Evaluate the template given the values and functions.
        """
        return self.evaluate(Environment(values, functions))
