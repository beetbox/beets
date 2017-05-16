# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

from __future__ import division, absolute_import, print_function

import re
import ast
import dis
import types
import sys
import six

SYMBOL_DELIM = u'$'
FUNC_DELIM = u'%'
GROUP_OPEN = u'{'
GROUP_CLOSE = u'}'
ARG_SEP = u','
ESCAPE_CHAR = u'$'

VARIABLE_PREFIX = '__var_'
FUNCTION_PREFIX = '__func_'


class Environment(object):
    """Contains the values and functions to be substituted into a
    template.
    """
    def __init__(self, values, functions):
        self.values = values
        self.functions = functions


# Code generation helpers.

def ex_lvalue(name):
    """A variable load expression."""
    return ast.Name(name, ast.Store())


def ex_rvalue(name):
    """A variable store expression."""
    return ast.Name(name, ast.Load())


def ex_literal(val):
    """An int, float, long, bool, string, or None literal with the given
    value.
    """
    if val is None:
        return ast.Name('None', ast.Load())
    elif isinstance(val, six.integer_types):
        return ast.Num(val)
    elif isinstance(val, bool):
        return ast.Name(bytes(val), ast.Load())
    elif isinstance(val, six.string_types):
        return ast.Str(val)
    raise TypeError(u'no literal for {0}'.format(type(val)))


def ex_varassign(name, expr):
    """Assign an expression into a single variable. The expression may
    either be an `ast.expr` object or a value to be used as a literal.
    """
    if not isinstance(expr, ast.expr):
        expr = ex_literal(expr)
    return ast.Assign([ex_lvalue(name)], expr)


def ex_call(func, args):
    """A function-call expression with only positional parameters. The
    function may be an expression or the name of a function. Each
    argument may be an expression or a value to be used as a literal.
    """
    if isinstance(func, six.string_types):
        func = ex_rvalue(func)

    args = list(args)
    for i in range(len(args)):
        if not isinstance(args[i], ast.expr):
            args[i] = ex_literal(args[i])

    if sys.version_info[:2] < (3, 5):
        return ast.Call(func, args, [], None, None)
    else:
        return ast.Call(func, args, [])


def compile_func(arg_names, statements, name='_the_func', debug=False):
    """Compile a list of statements as the body of a function and return
    the resulting Python function. If `debug`, then print out the
    bytecode of the compiled function.
    """
    if six.PY2:
        func_def = ast.FunctionDef(
            name=name.encode('utf-8'),
            args=ast.arguments(
                args=[ast.Name(n, ast.Param()) for n in arg_names],
                vararg=None,
                kwarg=None,
                defaults=[ex_literal(None) for _ in arg_names],
            ),
            body=statements,
            decorator_list=[],
        )
    else:
        func_def = ast.FunctionDef(
            name=name,
            args=ast.arguments(
                args=[ast.arg(arg=n, annotation=None) for n in arg_names],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[ex_literal(None) for _ in arg_names],
            ),
            body=statements,
            decorator_list=[],
        )

    mod = ast.Module([func_def])
    ast.fix_missing_locations(mod)

    prog = compile(mod, '<generated>', 'exec')

    # Debug: show bytecode.
    if debug:
        dis.dis(prog)
        for const in prog.co_consts:
            if isinstance(const, types.CodeType):
                dis.dis(const)

    the_locals = {}
    exec(prog, {}, the_locals)
    return the_locals[name]


# AST nodes for the template language.

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

    def translate(self):
        """Compile the variable lookup."""
        if six.PY2:
            ident = self.ident.encode('utf-8')
        else:
            ident = self.ident
        expr = ex_rvalue(VARIABLE_PREFIX + ident)
        return [expr], set([ident]), set()


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
            except Exception as exc:
                # Function raised exception! Maybe inlining the name of
                # the exception will help debug.
                return u'<%s>' % six.text_type(exc)
            return six.text_type(out)
        else:
            return self.original

    def translate(self):
        """Compile the function call."""
        varnames = set()
        if six.PY2:
            ident = self.ident.encode('utf-8')
        else:
            ident = self.ident
        funcnames = set([ident])

        arg_exprs = []
        for arg in self.args:
            subexprs, subvars, subfuncs = arg.translate()
            varnames.update(subvars)
            funcnames.update(subfuncs)

            # Create a subexpression that joins the result components of
            # the arguments.
            arg_exprs.append(ex_call(
                ast.Attribute(ex_literal(u''), 'join', ast.Load()),
                [ex_call(
                    'map',
                    [
                        ex_rvalue(six.text_type.__name__),
                        ast.List(subexprs, ast.Load()),
                    ]
                )],
            ))

        subexpr_call = ex_call(
            FUNCTION_PREFIX + ident,
            arg_exprs
        )
        return [subexpr_call], varnames, funcnames


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
            if isinstance(part, six.string_types):
                out.append(part)
            else:
                out.append(part.evaluate(env))
        return u''.join(map(six.text_type, out))

    def translate(self):
        """Compile the expression to a list of Python AST expressions, a
        set of variable names used, and a set of function names.
        """
        expressions = []
        varnames = set()
        funcnames = set()
        for part in self.parts:
            if isinstance(part, six.string_types):
                expressions.append(ex_literal(part))
            else:
                e, v, f = part.translate()
                expressions.extend(e)
                varnames.update(v)
                funcnames.update(f)
        return expressions, varnames, funcnames


# Parser.

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
    def __init__(self, string, in_argument=False):
        """ Create a new parser.
        :param in_arguments: boolean that indicates the parser is to be
        used for parsing function arguments, ie. considering commas
        (`ARG_SEP`) a special character
        """
        self.string = string
        self.in_argument = in_argument
        self.pos = 0
        self.parts = []

    # Common parsing resources.
    special_chars = (SYMBOL_DELIM, FUNC_DELIM, GROUP_OPEN, GROUP_CLOSE,
                     ESCAPE_CHAR)
    special_char_re = re.compile(r'[%s]|\Z' %
                                 u''.join(re.escape(c) for c in special_chars))
    escapable_chars = (SYMBOL_DELIM, FUNC_DELIM, GROUP_CLOSE, ARG_SEP)
    terminator_chars = (GROUP_CLOSE,)

    def parse_expression(self):
        """Parse a template expression starting at ``pos``. Resulting
        components (Unicode strings, Symbols, and Calls) are added to
        the ``parts`` field, a list.  The ``pos`` field is updated to be
        the next character after the expression.
        """
        # Append comma (ARG_SEP) to the list of special characters only when
        # parsing function arguments.
        extra_special_chars = ()
        special_char_re = self.special_char_re
        if self.in_argument:
            extra_special_chars = (ARG_SEP,)
            special_char_re = re.compile(
                r'[%s]|\Z' % u''.join(
                    re.escape(c) for c in
                    self.special_chars + extra_special_chars
                )
            )

        text_parts = []

        while self.pos < len(self.string):
            char = self.string[self.pos]

            if char not in self.special_chars + extra_special_chars:
                # A non-special character. Skip to the next special
                # character, treating the interstice as literal text.
                next_pos = (
                    special_char_re.search(
                        self.string[self.pos:]).start() + self.pos
                )
                text_parts.append(self.string[self.pos:next_pos])
                self.pos = next_pos
                continue

            if self.pos == len(self.string) - 1:
                # The last character can never begin a structure, so we
                # just interpret it as a literal character (unless it
                # terminates the expression, as with , and }).
                if char not in self.terminator_chars + extra_special_chars:
                    text_parts.append(char)
                    self.pos += 1
                break

            next_char = self.string[self.pos + 1]
            if char == ESCAPE_CHAR and next_char in (self.escapable_chars +
                                                     extra_special_chars):
                # An escaped special character ($$, $}, etc.). Note that
                # ${ is not an escape sequence: this is ambiguous with
                # the start of a symbol and it's not necessary (just
                # using { suffices in all cases).
                text_parts.append(next_char)
                self.pos += 2  # Skip the next character.
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
            elif char in self.terminator_chars + extra_special_chars:
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
            self.pos += 1  # Skip opening.
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

        self.pos += 1  # Move past closing brace.
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
            subparser = Parser(self.string[self.pos:], in_argument=True)
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
        ident = re.match(r'\w*', remainder).group(0)
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


# External interface.

class Template(object):
    """A string template, including text, Symbols, and Calls.
    """
    def __init__(self, template):
        self.expr = _parse(template)
        self.original = template
        self.compiled = self.translate()

    def __eq__(self, other):
        return self.original == other.original

    def interpret(self, values={}, functions={}):
        """Like `substitute`, but forces the interpreter (rather than
        the compiled version) to be used. The interpreter includes
        exception-handling code for missing variables and buggy template
        functions but is much slower.
        """
        return self.expr.evaluate(Environment(values, functions))

    def substitute(self, values={}, functions={}):
        """Evaluate the template given the values and functions.
        """
        try:
            res = self.compiled(values, functions)
        except Exception:  # Handle any exceptions thrown by compiled version.
            res = self.interpret(values, functions)

        return res

    def translate(self):
        """Compile the template to a Python function."""
        expressions, varnames, funcnames = self.expr.translate()

        argnames = []
        for varname in varnames:
            argnames.append(VARIABLE_PREFIX + varname)
        for funcname in funcnames:
            argnames.append(FUNCTION_PREFIX + funcname)

        func = compile_func(
            argnames,
            [ast.Return(ast.List(expressions, ast.Load()))],
        )

        def wrapper_func(values={}, functions={}):
            args = {}
            for varname in varnames:
                args[VARIABLE_PREFIX + varname] = values[varname]
            for funcname in funcnames:
                args[FUNCTION_PREFIX + funcname] = functions[funcname]
            parts = func(**args)
            return u''.join(parts)

        return wrapper_func


# Performance tests.

if __name__ == '__main__':
    import timeit
    _tmpl = Template(u'foo $bar %baz{foozle $bar barzle} $bar')
    _vars = {'bar': 'qux'}
    _funcs = {'baz': six.text_type.upper}
    interp_time = timeit.timeit('_tmpl.interpret(_vars, _funcs)',
                                'from __main__ import _tmpl, _vars, _funcs',
                                number=10000)
    print(interp_time)
    comp_time = timeit.timeit('_tmpl.substitute(_vars, _funcs)',
                              'from __main__ import _tmpl, _vars, _funcs',
                              number=10000)
    print(comp_time)
    print(u'Speedup:', interp_time / comp_time)
