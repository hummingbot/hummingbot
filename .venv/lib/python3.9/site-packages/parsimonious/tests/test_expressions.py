# coding=utf-8
from unittest import TestCase

from parsimonious.exceptions import ParseError, IncompleteParseError
from parsimonious.expressions import (Literal, Regex, Sequence, OneOf, Not,
                                      Quantifier, Optional, ZeroOrMore, OneOrMore, Expression)
from parsimonious.grammar import Grammar, rule_grammar
from parsimonious.nodes import Node


class LengthTests(TestCase):
    """Tests for returning the right lengths

    I wrote these before parse tree generation was implemented. They're
    partially redundant with TreeTests.

    """

    def len_eq(self, node, length):
        """Return whether the match lengths of 2 nodes are equal.

        Makes tests shorter and lets them omit positional stuff they don't care
        about.

        """
        node_length = None if node is None else node.end - node.start
        assert node_length == length

    def test_regex(self):
        self.len_eq(Literal('hello').match('ehello', 1), 5)  # simple
        self.len_eq(Regex('hello*').match('hellooo'), 7)  # *
        self.assertRaises(ParseError, Regex('hello*').match, 'goodbye')  # no match
        self.len_eq(Regex('hello', ignore_case=True).match('HELLO'), 5)

    def test_sequence(self):
        self.len_eq(Sequence(Regex('hi*'), Literal('lo'), Regex('.ingo')).match('hiiiilobingo1234'), 12)  # succeed
        self.assertRaises(ParseError, Sequence(Regex('hi*'), Literal('lo'),
                                               Regex('.ingo')).match, 'hiiiilobing')  # don't
        self.len_eq(Sequence(Regex('hi*')).match('>hiiii', 1), 5)  # non-0 pos

    def test_one_of(self):
        self.len_eq(OneOf(Literal('aaa'), Literal('bb')).match('aaa'), 3)  # first alternative
        self.len_eq(OneOf(Literal('aaa'), Literal('bb')).match('bbaaa'), 2)  # second
        self.assertRaises(ParseError, OneOf(Literal('aaa'), Literal('bb')).match, 'aa')  # no match

    def test_not(self):
        self.len_eq(Not(Regex('.')).match(''), 0)  # match
        self.assertRaises(ParseError, Not(Regex('.')).match, 'Hi')  # don't

    def test_optional(self):
        self.len_eq(Sequence(Optional(Literal('a')), Literal('b')).match('b'), 1)  # contained expr fails
        self.len_eq(Sequence(Optional(Literal('a')), Literal('b')).match('ab'), 2)  # contained expr succeeds
        self.len_eq(Optional(Literal('a')).match('aa'), 1)
        self.len_eq(Optional(Literal('a')).match('bb'), 0)

    def test_zero_or_more(self):
        self.len_eq(ZeroOrMore(Literal('b')).match(''), 0)  # zero
        self.len_eq(ZeroOrMore(Literal('b')).match('bbb'), 3)  # more

        self.len_eq(Regex('^').match(''), 0)  # Validate the next test.

        # Try to make it loop infinitely using a zero-length contained expression:
        self.len_eq(ZeroOrMore(Regex('^')).match(''), 0)

    def test_one_or_more(self):
        self.len_eq(OneOrMore(Literal('b')).match('b'), 1)  # one
        self.len_eq(OneOrMore(Literal('b')).match('bbb'), 3)  # more
        self.len_eq(OneOrMore(Literal('b'), min=3).match('bbb'), 3)  # with custom min; success
        self.len_eq(Quantifier(Literal('b'), min=3, max=5).match('bbbb'), 4)  # with custom min and max; success
        self.len_eq(Quantifier(Literal('b'), min=3, max=5).match('bbbbbb'), 5)  # with custom min and max; success
        self.assertRaises(ParseError, OneOrMore(Literal('b'), min=3).match, 'bb')  # with custom min; failure
        self.assertRaises(ParseError, Quantifier(Literal('b'), min=3, max=5).match, 'bb')  # with custom min and max; failure
        self.len_eq(OneOrMore(Regex('^')).match('bb'), 0)  # attempt infinite loop


class TreeTests(TestCase):
    """Tests for building the right trees

    We have only to test successes here; failures (None-returning cases) are
    covered above.

    """

    def test_simple_node(self):
        """Test that leaf expressions like ``Literal`` make the right nodes."""
        h = Literal('hello', name='greeting')
        self.assertEqual(h.match('hello'), Node(h, 'hello', 0, 5))

    def test_sequence_nodes(self):
        """Assert that ``Sequence`` produces nodes with the right children."""
        s = Sequence(Literal('heigh', name='greeting1'),
                     Literal('ho',    name='greeting2'), name='dwarf')
        text = 'heighho'
        self.assertEqual(s.match(text), Node(s, text, 0, 7, children=[Node(s.members[0], text, 0, 5),
                                                                      Node(s.members[1], text, 5, 7)]))

    def test_one_of(self):
        """``OneOf`` should return its own node, wrapping the child that succeeds."""
        o = OneOf(Literal('a', name='lit'), name='one_of')
        text = 'aa'
        self.assertEqual(o.match(text), Node(o, text, 0, 1, children=[
            Node(o.members[0], text, 0, 1)]))

    def test_optional(self):
        """``Optional`` should return its own node wrapping the succeeded child."""
        expr = Optional(Literal('a', name='lit'), name='opt')

        text = 'a'
        self.assertEqual(expr.match(text), Node(expr, text, 0, 1, children=[
            Node(expr.members[0], text, 0, 1)]))

        # Test failure of the Literal inside the Optional; the
        # LengthTests.test_optional is ambiguous for that.
        text = ''
        self.assertEqual(expr.match(text), Node(expr, text, 0, 0))

    def test_zero_or_more_zero(self):
        """Test the 0 case of ``ZeroOrMore``; it should still return a node."""
        expr = ZeroOrMore(Literal('a'), name='zero')
        text = ''
        self.assertEqual(expr.match(text), Node(expr, text, 0, 0))

    def test_one_or_more_one(self):
        """Test the 1 case of ``OneOrMore``; it should return a node with a child."""
        expr = OneOrMore(Literal('a', name='lit'), name='one')
        text = 'a'
        self.assertEqual(expr.match(text), Node(expr, text, 0, 1, children=[
            Node(expr.members[0], text, 0, 1)]))

    # Things added since Grammar got implemented are covered in integration
    # tests in test_grammar.


class ParseTests(TestCase):
    """Tests for the ``parse()`` method"""

    def test_parse_success(self):
        """Make sure ``parse()`` returns the tree on success.

        There's not much more than that to test that we haven't already vetted
        above.

        """
        expr = OneOrMore(Literal('a', name='lit'), name='more')
        text = 'aa'
        self.assertEqual(expr.parse(text), Node(expr, text, 0, 2, children=[
            Node(expr.members[0], text, 0, 1),
            Node(expr.members[0], text, 1, 2)]))


class ErrorReportingTests(TestCase):
    """Tests for reporting parse errors"""

    def test_inner_rule_succeeding(self):
        """Make sure ``parse()`` fails and blames the
        rightward-progressing-most named Expression when an Expression isn't
        satisfied.

        Make sure ParseErrors have nice Unicode representations.

        """
        grammar = Grammar("""
            bold_text = open_parens text close_parens
            open_parens = "(("
            text = ~"[a-zA-Z]+"
            close_parens = "))"
            """)
        text = '((fred!!'
        try:
            grammar.parse(text)
        except ParseError as error:
            self.assertEqual(error.pos, 6)
            self.assertEqual(error.expr, grammar['close_parens'])
            self.assertEqual(error.text, text)
            self.assertEqual(str(error), "Rule 'close_parens' didn't match at '!!' (line 1, column 7).")

    def test_rewinding(self):
        """Make sure rewinding the stack and trying an alternative (which
        progresses farther) from a higher-level rule can blame an expression
        within the alternative on failure.

        There's no particular reason I suspect this wouldn't work, but it's a
        more real-world example than the no-alternative cases already tested.

        """
        grammar = Grammar("""
            formatted_text = bold_text / weird_text
            bold_text = open_parens text close_parens
            weird_text = open_parens text "!!" bork
            bork = "bork"
            open_parens = "(("
            text = ~"[a-zA-Z]+"
            close_parens = "))"
            """)
        text = '((fred!!'
        try:
            grammar.parse(text)
        except ParseError as error:
            self.assertEqual(error.pos, 8)
            self.assertEqual(error.expr, grammar['bork'])
            self.assertEqual(error.text, text)

    def test_no_named_rule_succeeding(self):
        """Make sure ParseErrors have sane printable representations even if we
        never succeeded in matching any named expressions."""
        grammar = Grammar('''bork = "bork"''')
        try:
            grammar.parse('snork')
        except ParseError as error:
            self.assertEqual(error.pos, 0)
            self.assertEqual(error.expr, grammar['bork'])
            self.assertEqual(error.text, 'snork')

    def test_parse_with_leftovers(self):
        """Make sure ``parse()`` reports where we started failing to match,
        even if a partial match was successful."""
        grammar = Grammar(r'''sequence = "chitty" (" " "bang")+''')
        try:
            grammar.parse('chitty bangbang')
        except IncompleteParseError as error:
            self.assertEqual(str(
                error), "Rule 'sequence' matched in its entirety, but it didn't consume all the text. The non-matching portion of the text begins with 'bang' (line 1, column 12).")

    def test_favoring_named_rules(self):
        """Named rules should be used in error messages in favor of anonymous
        ones, even if those are rightward-progressing-more, and even if the
        failure starts at position 0."""
        grammar = Grammar(r'''starts_with_a = &"a" ~"[a-z]+"''')
        try:
            grammar.parse('burp')
        except ParseError as error:
            self.assertEqual(str(error), "Rule 'starts_with_a' didn't match at 'burp' (line 1, column 1).")

    def test_line_and_column(self):
        """Make sure we got the line and column computation right."""
        grammar = Grammar(r"""
            whee_lah = whee "\n" lah "\n"
            whee = "whee"
            lah = "lah"
            """)
        try:
            grammar.parse('whee\nlahGOO')
        except ParseError as error:
            # TODO: Right now, this says "Rule <Literal "\n" at 0x4368250432>
            # didn't match". That's not the greatest. Fix that, then fix this.
            self.assertTrue(str(error).endswith(r"""didn't match at 'GOO' (line 2, column 4)."""))


class RepresentationTests(TestCase):
    """Tests for str(), unicode(), and repr() of expressions"""

    def test_unicode_crash(self):
        """Make sure matched unicode strings don't crash ``__str__``."""
        grammar = Grammar(r'string = ~r"\S+"u')
        str(grammar.parse('中文'))

    def test_unicode(self):
        """Smoke-test the conversion of expressions to bits of rules.

        A slightly more comprehensive test of the actual values is in
        ``GrammarTests.test_unicode``.

        """
        str(rule_grammar)

    def test_unicode_keep_parens(self):
        """Make sure converting an expression to unicode doesn't strip
        parenthesis.

        """
        # ZeroOrMore
        self.assertEqual(str(Grammar('foo = "bar" ("baz" "eggs")* "spam"')),
                         "foo = 'bar' ('baz' 'eggs')* 'spam'")

        # Quantifiers
        self.assertEqual(str(Grammar('foo = "bar" ("baz" "eggs"){2,4} "spam"')),
                         "foo = 'bar' ('baz' 'eggs'){2,4} 'spam'")
        self.assertEqual(str(Grammar('foo = "bar" ("baz" "eggs"){2,} "spam"')),
                         "foo = 'bar' ('baz' 'eggs'){2,} 'spam'")
        self.assertEqual(str(Grammar('foo = "bar" ("baz" "eggs"){1,} "spam"')),
                         "foo = 'bar' ('baz' 'eggs')+ 'spam'")
        self.assertEqual(str(Grammar('foo = "bar" ("baz" "eggs"){,4} "spam"')),
                         "foo = 'bar' ('baz' 'eggs'){,4} 'spam'")
        self.assertEqual(str(Grammar('foo = "bar" ("baz" "eggs"){0,1} "spam"')),
                         "foo = 'bar' ('baz' 'eggs')? 'spam'")
        self.assertEqual(str(Grammar('foo = "bar" ("baz" "eggs"){0,} "spam"')),
                         "foo = 'bar' ('baz' 'eggs')* 'spam'")

        # OneOf
        self.assertEqual(str(Grammar('foo = "bar" ("baz" / "eggs") "spam"')),
                         "foo = 'bar' ('baz' / 'eggs') 'spam'")

        # Lookahead
        self.assertEqual(str(Grammar('foo = "bar" &("baz" "eggs") "spam"')),
                         "foo = 'bar' &('baz' 'eggs') 'spam'")

        # Multiple sequences
        self.assertEqual(str(Grammar('foo = ("bar" "baz") / ("baff" "bam")')),
                         "foo = ('bar' 'baz') / ('baff' 'bam')")

    def test_unicode_surrounding_parens(self):
        """
        Make sure there are no surrounding parens around the entire
        right-hand side of an expression (as they're unnecessary).

        """
        self.assertEqual(str(Grammar('foo = ("foo" ("bar" "baz"))')),
                         "foo = 'foo' ('bar' 'baz')")


class SlotsTests(TestCase):
    """Tests to do with __slots__"""

    def test_subclassing(self):
        """Make sure a subclass of a __slots__-less class can introduce new
        slots itself.

        This isn't supposed to work, according to the language docs:

            When inheriting from a class without __slots__, the __dict__
            attribute of that class will always be accessible, so a __slots__
            definition in the subclass is meaningless.

        But it does.

        """
        class Smoo(Quantifier):
            __slots__ = ['smoo']

            def __init__(self):
                self.smoo = 'smoo'

        smoo = Smoo()
        self.assertEqual(smoo.__dict__, {})  # has a __dict__ but with no smoo in it
        self.assertEqual(smoo.smoo, 'smoo')  # The smoo attr ended up in a slot.
