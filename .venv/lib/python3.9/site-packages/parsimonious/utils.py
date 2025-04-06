"""General tools which don't depend on other parts of Parsimonious"""

import ast


class StrAndRepr(object):
    """Mix-in which gives the class the same __repr__ and __str__."""

    def __repr__(self):
        return self.__str__()


def evaluate_string(string):
    """Piggyback on Python's string support so we can have backslash escaping
    and niceties like \n, \t, etc.

    This also supports:
    1. b"strings", allowing grammars to parse bytestrings, in addition to str.
    2. r"strings" to simplify regexes.
    """
    return ast.literal_eval(string)


class Token(StrAndRepr):
    """A class to represent tokens, for use with TokenGrammars

    You will likely want to subclass this to hold additional information, like
    the characters that you lexed to create this token. Alternately, feel free
    to create your own class from scratch. The only contract is that tokens
    must have a ``type`` attr.

    """
    __slots__ = ['type']

    def __init__(self, type):
        self.type = type

    def __str__(self):
        return '<Token "%s">' % (self.type,)

    def __eq__(self, other):
        return self.type == other.type
