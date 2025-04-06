"""Subexpressions that make up a parsed grammar

These do the parsing.

"""
# TODO: Make sure all symbol refs are local--not class lookups or
# anything--for speed. And kill all the dots.

from collections import defaultdict
from inspect import getfullargspec, isfunction, ismethod, ismethoddescriptor
import regex as re

from parsimonious.exceptions import ParseError, IncompleteParseError, LeftRecursionError
from parsimonious.nodes import Node, RegexNode
from parsimonious.utils import StrAndRepr


def is_callable(value):
    criteria = [isfunction, ismethod, ismethoddescriptor]
    return any([criterion(value) for criterion in criteria])


def expression(callable, rule_name, grammar):
    """Turn a plain callable into an Expression.

    The callable can be of this simple form::

        def foo(text, pos):
            '''If this custom expression matches starting at text[pos], return
            the index where it stops matching. Otherwise, return None.'''
            if the expression matched:
                return end_pos

    If there child nodes to return, return a tuple::

        return end_pos, children

    If the expression doesn't match at the given ``pos`` at all... ::

        return None

    If your callable needs to make sub-calls to other rules in the grammar or
    do error reporting, it can take this form, gaining additional arguments::

        def foo(text, pos, cache, error, grammar):
            # Call out to other rules:
            node = grammar['another_rule'].match_core(text, pos, cache, error)
            ...
            # Return values as above.

    The return value of the callable, if an int or a tuple, will be
    automatically transmuted into a :class:`~parsimonious.Node`. If it returns
    a Node-like class directly, it will be passed through unchanged.

    :arg rule_name: The rule name to attach to the resulting
        :class:`~parsimonious.Expression`
    :arg grammar: The :class:`~parsimonious.Grammar` this expression will be a
        part of, to make delegating to other rules possible

    """

    # Resolve unbound methods; allows grammars to use @staticmethod custom rules
    # https://stackoverflow.com/questions/41921255/staticmethod-object-is-not-callable
    if ismethoddescriptor(callable) and hasattr(callable, '__func__'):
        callable = callable.__func__

    num_args = len(getfullargspec(callable).args)
    if ismethod(callable):
        # do not count the first argument (typically 'self') for methods
        num_args -= 1
    if num_args == 2:
        is_simple = True
    elif num_args == 5:
        is_simple = False
    else:
        raise RuntimeError("Custom rule functions must take either 2 or 5 "
                           "arguments, not %s." % num_args)

    class AdHocExpression(Expression):
        def _uncached_match(self, text, pos, cache, error):
            result = (callable(text, pos) if is_simple else
                      callable(text, pos, cache, error, grammar))

            if isinstance(result, int):
                end, children = result, None
            elif isinstance(result, tuple):
                end, children = result
            else:
                # Node or None
                return result
            return Node(self, text, pos, end, children=children)

        def _as_rhs(self):
            return '{custom function "%s"}' % callable.__name__

    return AdHocExpression(name=rule_name)


IN_PROGRESS = object()


class Expression(StrAndRepr):
    """A thing that can be matched against a piece of text"""

    # Slots are about twice as fast as __dict__-based attributes:
    # http://stackoverflow.com/questions/1336791/dictionary-vs-object-which-is-more-efficient-and-why

    # Top-level expressions--rules--have names. Subexpressions are named ''.
    __slots__ = ['name', 'identity_tuple']

    def __init__(self, name=''):
        self.name = name
        self.identity_tuple = (self.name, )

    def __hash__(self):
        return hash(self.identity_tuple)

    def __eq__(self, other):
        return self._eq_check_cycles(other, set())

    def __ne__(self, other):
        return not (self == other)

    def _eq_check_cycles(self, other, checked):
        # keep a set of all pairs that are already checked, so we won't fall into infinite recursions.
        checked.add((id(self), id(other)))
        return other.__class__ is self.__class__ and self.identity_tuple == other.identity_tuple

    def resolve_refs(self, rule_map):
        # Nothing to do on the base expression.
        return self

    def parse(self, text, pos=0):
        """Return a parse tree of ``text``.

        Raise ``ParseError`` if the expression wasn't satisfied. Raise
        ``IncompleteParseError`` if the expression was satisfied but didn't
        consume the full string.

        """
        node = self.match(text, pos=pos)
        if node.end < len(text):
            raise IncompleteParseError(text, node.end, self)
        return node

    def match(self, text, pos=0):
        """Return the parse tree matching this expression at the given
        position, not necessarily extending all the way to the end of ``text``.

        Raise ``ParseError`` if there is no match there.

        :arg pos: The index at which to start matching

        """
        error = ParseError(text)
        node = self.match_core(text, pos, defaultdict(dict), error)
        if node is None:
            raise error
        return node

    def match_core(self, text, pos, cache, error):
        """Internal guts of ``match()``

        This is appropriate to call only from custom rules or Expression
        subclasses.

        :arg cache: The packrat cache::

            {(oid, pos): Node tree matched by object `oid` at index `pos` ...}

        :arg error: A ParseError instance with ``text`` already filled in but
            otherwise blank. We update the error reporting info on this object
            as we go. (Sticking references on an existing instance is faster
            than allocating a new one for each expression that fails.) We
            return None rather than raising and catching ParseErrors because
            catching is slow.

        """
        # TODO: Optimize. Probably a hot spot.
        #
        # Is there a faster way of looking up cached stuff?
        #
        # If this is slow, think about the array module. It might (or might
        # not!) use more RAM, but it'll likely be faster than hashing things
        # all the time. Also, can we move all the allocs up front?
        #
        # To save space, we have lots of choices: (0) Quit caching whole Node
        # objects. Cache just what you need to reconstitute them. (1) Cache
        # only the results of entire rules, not subexpressions (probably a
        # horrible idea for rules that need to backtrack internally a lot). (2)
        # Age stuff out of the cache somehow. LRU? (3) Cuts.
        expr_cache = cache[id(self)]
        if pos in expr_cache:
            node = expr_cache[pos]
        else:
            # TODO: Set default value to prevent infinite recursion in left-recursive rules.
            expr_cache[pos] = IN_PROGRESS  # Mark as in progress
            node = expr_cache[pos] = self._uncached_match(text, pos, cache, error)
        if node is IN_PROGRESS:
            raise LeftRecursionError(text, pos=-1, expr=self)

        # Record progress for error reporting:
        if node is None and pos >= error.pos and (
                self.name or getattr(error.expr, 'name', None) is None):
            # Don't bother reporting on unnamed expressions (unless that's all
            # we've seen so far), as they're hard to track down for a human.
            # Perhaps we could include the unnamed subexpressions later as
            # auxiliary info.
            error.expr = self
            error.pos = pos

        return node

    def __str__(self):
        return '<%s %s>' % (
            self.__class__.__name__,
            self.as_rule())

    def as_rule(self):
        """Return the left- and right-hand sides of a rule that represents me.

        Return unicode. If I have no ``name``, omit the left-hand side.

        """
        rhs = self._as_rhs().strip()
        if rhs.startswith('(') and rhs.endswith(')'):
            rhs = rhs[1:-1]

        return ('%s = %s' % (self.name, rhs)) if self.name else rhs

    def _unicode_members(self):
        """Return an iterable of my unicode-represented children, stopping
        descent when we hit a named node so the returned value resembles the
        input rule."""
        return [(m.name or m._as_rhs()) for m in self.members]

    def _as_rhs(self):
        """Return the right-hand side of a rule that represents me.

        Implemented by subclasses.

        """
        raise NotImplementedError


class Literal(Expression):
    """A string literal

    Use these if you can; they're the fastest.

    """
    __slots__ = ['literal']

    def __init__(self, literal, name=''):
        super().__init__(name)
        self.literal = literal
        self.identity_tuple = (name, literal)

    def _uncached_match(self, text, pos, cache, error):
        if text.startswith(self.literal, pos):
            return Node(self, text, pos, pos + len(self.literal))

    def _as_rhs(self):
        return repr(self.literal)


class TokenMatcher(Literal):
    """An expression matching a single token of a given type

    This is for use only with TokenGrammars.

    """
    def _uncached_match(self, token_list, pos, cache, error):
        if token_list[pos].type == self.literal:
            return Node(self, token_list, pos, pos + 1)


class Regex(Expression):
    """An expression that matches what a regex does.

    Use these as much as you can and jam as much into each one as you can;
    they're fast.

    """
    __slots__ = ['re']

    def __init__(self, pattern, name='', ignore_case=False, locale=False,
                 multiline=False, dot_all=False, unicode=False, verbose=False, ascii=False):
        super().__init__(name)
        self.re = re.compile(pattern, (ignore_case and re.I) |
                                      (locale and re.L) |
                                      (multiline and re.M) |
                                      (dot_all and re.S) |
                                      (unicode and re.U) |
                                      (verbose and re.X) |
                                      (ascii and re.A))
        self.identity_tuple = (self.name, self.re)

    def _uncached_match(self, text, pos, cache, error):
        """Return length of match, ``None`` if no match."""
        m = self.re.match(text, pos)
        if m is not None:
            span = m.span()
            node = RegexNode(self, text, pos, pos + span[1] - span[0])
            node.match = m  # TODO: A terrible idea for cache size?
            return node

    def _regex_flags_from_bits(self, bits):
        """Return the textual equivalent of numerically encoded regex flags."""
        flags = 'ilmsuxa'
        return ''.join(flags[i - 1] if (1 << i) & bits else '' for i in range(1, len(flags) + 1))

    def _as_rhs(self):
        return '~{!r}{}'.format(self.re.pattern,
                                self._regex_flags_from_bits(self.re.flags))


class Compound(Expression):
    """An abstract expression which contains other expressions"""

    __slots__ = ['members']

    def __init__(self, *members, **kwargs):
        """``members`` is a sequence of expressions."""
        super().__init__(kwargs.get('name', ''))
        self.members = members

    def resolve_refs(self, rule_map):
        self.members = tuple(m.resolve_refs(rule_map) for m in self.members)
        return self

    def _eq_check_cycles(self, other, checked):
        return (
            super()._eq_check_cycles(other, checked) and
            len(self.members) == len(other.members) and
            all(m._eq_check_cycles(mo, checked) for m, mo in zip(self.members, other.members) if (id(m), id(mo)) not in checked)
        )

    def __hash__(self):
        # Note we leave members out of the hash computation, since compounds can get added to
        # sets, then have their members mutated. See RuleVisitor._resolve_refs.
        # Equality should still work, but we want the rules to go into the correct hash bucket.
        return hash((self.__class__, self.name))


class Sequence(Compound):
    """A series of expressions that must match contiguous, ordered pieces of
    the text

    In other words, it's a concatenation operator: each piece has to match, one
    after another.

    """
    def _uncached_match(self, text, pos, cache, error):
        new_pos = pos
        children = []
        for m in self.members:
            node = m.match_core(text, new_pos, cache, error)
            if node is None:
                return None
            children.append(node)
            length = node.end - node.start
            new_pos += length
        # Hooray! We got through all the members!
        return Node(self, text, pos, new_pos, children)

    def _as_rhs(self):
        return '({0})'.format(' '.join(self._unicode_members()))


class OneOf(Compound):
    """A series of expressions, one of which must match

    Expressions are tested in order from first to last. The first to succeed
    wins.

    """
    def _uncached_match(self, text, pos, cache, error):
        for m in self.members:
            node = m.match_core(text, pos, cache, error)
            if node is not None:
                # Wrap the succeeding child in a node representing the OneOf:
                return Node(self, text, pos, node.end, children=[node])

    def _as_rhs(self):
        return '({0})'.format(' / '.join(self._unicode_members()))


class Lookahead(Compound):
    """An expression which consumes nothing, even if its contained expression
    succeeds"""

    __slots__ = ['negativity']

    def __init__(self, member, *, negative=False, **kwargs):
        super().__init__(member, **kwargs)
        self.negativity = bool(negative)

    def _uncached_match(self, text, pos, cache, error):
        node = self.members[0].match_core(text, pos, cache, error)
        if (node is None) == self.negativity: # negative lookahead == match only if not found
            return Node(self, text, pos, pos)

    def _as_rhs(self):
        return '%s%s' % ('!' if self.negativity else '&', self._unicode_members()[0])

    def _eq_check_cycles(self, other, checked):
        return (
            super()._eq_check_cycles(other, checked) and
            self.negativity == other.negativity
        )

def Not(term):
    return Lookahead(term, negative=True)

# Quantifiers. None of these is strictly necessary, but they're darn handy.

class Quantifier(Compound):
    """An expression wrapper like the */+/?/{n,m} quantifier in regexes."""

    __slots__ = ['min', 'max']

    def __init__(self, member, *, min=0, max=float('inf'), name='', **kwargs):
        super().__init__(member, name=name, **kwargs)
        self.min = min
        self.max = max

    def _uncached_match(self, text, pos, cache, error):
        new_pos = pos
        children = []
        size = len(text)
        while new_pos < size and len(children) < self.max:
            node = self.members[0].match_core(text, new_pos, cache, error)
            if node is None:
                break # no more matches
            children.append(node)
            length = node.end - node.start
            if len(children) >= self.min and length == 0:  # Don't loop infinitely
                break
            new_pos += length
        if len(children) >= self.min:
            return Node(self, text, pos, new_pos, children)

    def _as_rhs(self):
        if self.min == 0 and self.max == 1:
            qualifier = '?'
        elif self.min == 0 and self.max == float('inf'):
            qualifier = '*'
        elif self.min == 1 and self.max == float('inf'):
            qualifier = '+'
        elif self.max == float('inf'):
            qualifier = '{%d,}' % self.min
        elif self.min == 0:
            qualifier = '{,%d}' % self.max
        else:
            qualifier = '{%d,%d}' % (self.min, self.max)
        return '%s%s' % (self._unicode_members()[0], qualifier)

    def _eq_check_cycles(self, other, checked):
        return (
            super()._eq_check_cycles(other, checked) and
            self.min == other.min and
            self.max == other.max
        )

def ZeroOrMore(member, name=''):
    return Quantifier(member, name=name, min=0, max=float('inf'))

def OneOrMore(member, name='', min=1):
    return Quantifier(member, name=name, min=min, max=float('inf'))

def Optional(member, name=''):
    return Quantifier(member, name=name, min=0, max=1)
