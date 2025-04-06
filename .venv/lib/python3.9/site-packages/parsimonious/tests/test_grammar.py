# coding=utf-8

from sys import version_info
from unittest import TestCase

import pytest

from parsimonious.exceptions import BadGrammar, LeftRecursionError, ParseError, UndefinedLabel, VisitationError
from parsimonious.expressions import Literal, Lookahead, Regex, Sequence, TokenMatcher, is_callable
from parsimonious.grammar import rule_grammar, rule_syntax, RuleVisitor, Grammar, TokenGrammar, LazyReference
from parsimonious.nodes import Node
from parsimonious.utils import Token


class BootstrappingGrammarTests(TestCase):
    """Tests for the expressions in the grammar that parses the grammar
    definition syntax"""

    def test_quantifier(self):
        text = '*'
        quantifier = rule_grammar['quantifier']
        self.assertEqual(quantifier.parse(text),
            Node(quantifier, text, 0, 1, children=[
                Node(quantifier.members[0], text, 0, 1), Node(rule_grammar['_'], text, 1, 1)]))
        text = '?'
        self.assertEqual(quantifier.parse(text),
            Node(quantifier, text, 0, 1, children=[
                Node(quantifier.members[0], text, 0, 1), Node(rule_grammar['_'], text, 1, 1)]))
        text = '+'
        self.assertEqual(quantifier.parse(text),
            Node(quantifier, text, 0, 1, children=[
                Node(quantifier.members[0], text, 0, 1), Node(rule_grammar['_'], text, 1, 1)]))

    def test_spaceless_literal(self):
        text = '"anything but quotes#$*&^"'
        spaceless_literal = rule_grammar['spaceless_literal']
        self.assertEqual(spaceless_literal.parse(text),
            Node(spaceless_literal, text, 0, len(text), children=[
                Node(spaceless_literal.members[0], text, 0, len(text))]))
        text = r'''r"\""'''
        self.assertEqual(spaceless_literal.parse(text),
            Node(spaceless_literal, text, 0, 5, children=[
                Node(spaceless_literal.members[0], text, 0, 5)]))

    def test_regex(self):
        text = '~"[a-zA-Z_][a-zA-Z_0-9]*"LI'
        regex = rule_grammar['regex']
        self.assertEqual(rule_grammar['regex'].parse(text),
            Node(regex, text, 0, len(text), children=[
                 Node(Literal('~'), text, 0, 1),
                 Node(rule_grammar['spaceless_literal'], text, 1, 25, children=[
                     Node(rule_grammar['spaceless_literal'].members[0], text, 1, 25)]),
                 Node(regex.members[2], text, 25, 27),
                 Node(rule_grammar['_'], text, 27, 27)]))

    def test_successes(self):
        """Make sure the PEG recognition grammar succeeds on various inputs."""
        self.assertTrue(rule_grammar['label'].parse('_'))
        self.assertTrue(rule_grammar['label'].parse('jeff'))
        self.assertTrue(rule_grammar['label'].parse('_THIS_THING'))

        self.assertTrue(rule_grammar['atom'].parse('some_label'))
        self.assertTrue(rule_grammar['atom'].parse('"some literal"'))
        self.assertTrue(rule_grammar['atom'].parse('~"some regex"i'))

        self.assertTrue(rule_grammar['quantified'].parse('~"some regex"i*'))
        self.assertTrue(rule_grammar['quantified'].parse('thing+'))
        self.assertTrue(rule_grammar['quantified'].parse('"hi"?'))

        self.assertTrue(rule_grammar['term'].parse('this'))
        self.assertTrue(rule_grammar['term'].parse('that+'))

        self.assertTrue(rule_grammar['sequence'].parse('this that? other'))

        self.assertTrue(rule_grammar['ored'].parse('this / that+ / "other"'))

        # + is higher precedence than &, so 'anded' should match the whole
        # thing:
        self.assertTrue(rule_grammar['lookahead_term'].parse('&this+'))

        self.assertTrue(rule_grammar['expression'].parse('this'))
        self.assertTrue(rule_grammar['expression'].parse('this? that other*'))
        self.assertTrue(rule_grammar['expression'].parse('&this / that+ / "other"'))
        self.assertTrue(rule_grammar['expression'].parse('this / that? / "other"+'))
        self.assertTrue(rule_grammar['expression'].parse('this? that other*'))

        self.assertTrue(rule_grammar['rule'].parse('this = that\r'))
        self.assertTrue(rule_grammar['rule'].parse('this = the? that other* \t\r'))
        self.assertTrue(rule_grammar['rule'].parse('the=~"hi*"\n'))

        self.assertTrue(rule_grammar.parse('''
            this = the? that other*
            that = "thing"
            the=~"hi*"
            other = "ahoy hoy"
            '''))


class RuleVisitorTests(TestCase):
    """Tests for ``RuleVisitor``

    As I write these, Grammar is not yet fully implemented. Normally, there'd
    be no reason to use ``RuleVisitor`` directly.

    """
    def test_round_trip(self):
        """Test a simple round trip.

        Parse a simple grammar, turn the parse tree into a map of expressions,
        and use that to parse another piece of text.

        Not everything was implemented yet, but it was a big milestone and a
        proof of concept.

        """
        tree = rule_grammar.parse('''number = ~"[0-9]+"\n''')
        rules, default_rule = RuleVisitor().visit(tree)

        text = '98'
        self.assertEqual(default_rule.parse(text), Node(default_rule, text, 0, 2))

    def test_undefined_rule(self):
        """Make sure we throw the right exception on undefined rules."""
        tree = rule_grammar.parse('boy = howdy\n')
        self.assertRaises(UndefinedLabel, RuleVisitor().visit, tree)

    def test_optional(self):
        tree = rule_grammar.parse('boy = "howdy"?\n')
        rules, default_rule = RuleVisitor().visit(tree)

        howdy = 'howdy'

        # It should turn into a Node from the Optional and another from the
        # Literal within.
        self.assertEqual(default_rule.parse(howdy), Node(default_rule, howdy, 0, 5, children=[
                                           Node(Literal("howdy"), howdy, 0, 5)]))


def function_rule(text, pos):
    """This is an example of a grammar rule implemented as a function, and is
    provided as a test fixture."""
    token = 'function'
    return pos + len(token) if text[pos:].startswith(token) else None


class GrammarTests(TestCase):
    """Integration-test ``Grammar``: feed it a PEG and see if it works."""

    def method_rule(self, text, pos):
        """This is an example of a grammar rule implemented as a method, and is
        provided as a test fixture."""
        token = 'method'
        return pos + len(token) if text[pos:].startswith(token) else None

    @staticmethod
    def descriptor_rule(text, pos):
        """This is an example of a grammar rule implemented as a descriptor,
        and is provided as a test fixture."""
        token = 'descriptor'
        return pos + len(token) if text[pos:].startswith(token) else None

    rules = {"descriptor_rule": descriptor_rule}

    def test_expressions_from_rules(self):
        """Test the ``Grammar`` base class's ability to compile an expression
        tree from rules.

        That the correct ``Expression`` tree is built is already tested in
        ``RuleGrammarTests``. This tests only that the ``Grammar`` base class's
        ``_expressions_from_rules`` works.

        """
        greeting_grammar = Grammar('greeting = "hi" / "howdy"')
        tree = greeting_grammar.parse('hi')
        self.assertEqual(tree, Node(greeting_grammar['greeting'], 'hi', 0, 2, children=[
                       Node(Literal('hi'), 'hi', 0, 2)]))

    def test_unicode(self):
        """Assert that a ``Grammar`` can convert into a string-formatted series
        of rules."""
        grammar = Grammar(r"""
                          bold_text  = bold_open text bold_close
                          text       = ~"[A-Z 0-9]*"i
                          bold_open  = "(("
                          bold_close = "))"
                          """)
        lines = str(grammar).splitlines()
        self.assertEqual(lines[0], 'bold_text = bold_open text bold_close')
        self.assertTrue("text = ~'[A-Z 0-9]*'i%s" % ('u' if version_info >= (3,) else '')
            in lines)
        self.assertTrue("bold_open = '(('" in lines)
        self.assertTrue("bold_close = '))'" in lines)
        self.assertEqual(len(lines), 4)

    def test_match(self):
        """Make sure partial-matching (with pos) works."""
        grammar = Grammar(r"""
                          bold_text  = bold_open text bold_close
                          text       = ~"[A-Z 0-9]*"i
                          bold_open  = "(("
                          bold_close = "))"
                          """)
        s = ' ((boo))yah'
        self.assertEqual(grammar.match(s, pos=1), Node(grammar['bold_text'], s, 1, 8, children=[
                                         Node(grammar['bold_open'], s, 1, 3),
                                         Node(grammar['text'], s, 3, 6),
                                         Node(grammar['bold_close'], s, 6, 8)]))

    def test_bad_grammar(self):
        """Constructing a Grammar with bad rules should raise ParseError."""
        self.assertRaises(ParseError, Grammar, 'just a bunch of junk')

    def test_comments(self):
        """Test tolerance of comments and blank lines in and around rules."""
        grammar = Grammar(r"""# This is a grammar.

                          # It sure is.
                          bold_text  = stars text stars  # nice
                          text       = ~"[A-Z 0-9]*"i #dude


                          stars      = "**"
                          # Pretty good
                          #Oh yeah.#""")  # Make sure a comment doesn't need a
                                          # \n or \r to end.
        self.assertEqual(list(sorted(str(grammar).splitlines())),
            ['''bold_text = stars text stars''',
             # TODO: Unicode flag is on by default in Python 3. I wonder if we
             # should turn it on all the time in Parsimonious.
             """stars = '**'""",
             '''text = ~'[A-Z 0-9]*'i%s''' % ('u' if version_info >= (3,)
                                              else '')])

    def test_multi_line(self):
        """Make sure we tolerate all sorts of crazy line breaks and comments in
        the middle of rules."""
        grammar = Grammar("""
            bold_text  = bold_open  # commenty comment
                         text  # more comment
                         bold_close
            text       = ~"[A-Z 0-9]*"i
            bold_open  = "((" bold_close =  "))"
            """)
        self.assertTrue(grammar.parse('((booyah))') is not None)

    def test_not(self):
        """Make sure "not" predicates get parsed and work properly."""
        grammar = Grammar(r'''not_arp = !"arp" ~"[a-z]+"''')
        self.assertRaises(ParseError, grammar.parse, 'arp')
        self.assertTrue(grammar.parse('argle') is not None)

    def test_lookahead(self):
        grammar = Grammar(r'''starts_with_a = &"a" ~"[a-z]+"''')
        self.assertRaises(ParseError, grammar.parse, 'burp')

        s = 'arp'
        self.assertEqual(grammar.parse('arp'), Node(grammar['starts_with_a'], s, 0, 3, children=[
                                      Node(Lookahead(Literal('a')), s, 0, 0),
                                      Node(Regex(r'[a-z]+'), s, 0, 3)]))

    def test_parens(self):
        grammar = Grammar(r'''sequence = "chitty" (" " "bang")+''')
        # Make sure it's not as if the parens aren't there:
        self.assertRaises(ParseError, grammar.parse, 'chitty bangbang')

        s = 'chitty bang bang'
        self.assertEqual(str(grammar.parse(s)),
            """<Node called "sequence" matching "chitty bang bang">
    <Node matching "chitty">
    <Node matching " bang bang">
        <Node matching " bang">
            <Node matching " ">
            <Node matching "bang">
        <Node matching " bang">
            <Node matching " ">
            <Node matching "bang">""")

    def test_resolve_refs_order(self):
        """Smoke-test a circumstance where lazy references don't get resolved."""
        grammar = Grammar("""
            expression = "(" terms ")"
            terms = term+
            term = number
            number = ~r"[0-9]+"
            """)
        grammar.parse('(34)')

    def test_resolve_refs_completeness(self):
        """Smoke-test another circumstance where lazy references don't get resolved."""
        grammar = Grammar(r"""
            block = "{" _ item* "}" _

            # An item is an element of a block.
            item = number / word / block / paren

            # Parens are for delimiting subexpressions.
            paren = "(" _ item* ")" _

            # Words are barewords, unquoted things, other than literals, that can live
            # in lists. We may renege on some of these chars later, especially ".". We
            # may add Unicode.
            word = spaceless_word _
            spaceless_word = ~r"[-a-z`~!@#$%^&*_+=|\\;<>,.?][-a-z0-9`~!@#$%^&*_+=|\\;<>,.?]*"i

            number = ~r"[0-9]+" _ # There are decimals and strings and other stuff back on the "parsing" branch, once you get this working.

            _ = meaninglessness*
            meaninglessness = whitespace
            whitespace = ~r"\s+"
            """)
        grammar.parse('{log (add 3 to 5)}')

    def test_infinite_loop(self):
        """Smoke-test a grammar that was causing infinite loops while building.

        This was going awry because the "int" rule was never getting marked as
        resolved, so it would just keep trying to resolve it over and over.

        """
        Grammar("""
            digits = digit+
            int = digits
            digit = ~"[0-9]"
            number = int
            main = number
            """)

    def test_circular_toplevel_reference(self):
        with pytest.raises(VisitationError):
            Grammar("""
                foo = bar
                bar = foo
            """)
        with pytest.raises(VisitationError):
            Grammar("""
                foo = foo
                bar = foo
            """)
        with pytest.raises(VisitationError):
            Grammar("""
                foo = bar
                bar = baz
                baz = foo
            """)

    def test_right_recursive(self):
        """Right-recursive refs should resolve."""
        grammar = Grammar("""
            digits = digit digits?
            digit = ~r"[0-9]"
            """)
        self.assertTrue(grammar.parse('12') is not None)

    def test_badly_circular(self):
        """Uselessly circular references should be detected by the grammar
        compiler."""
        self.skipTest('We have yet to make the grammar compiler detect these.')
        Grammar("""
             foo = bar
             bar = foo
             """)

    def test_parens_with_leading_whitespace(self):
        """Make sure a parenthesized expression is allowed to have leading
        whitespace when nested directly inside another."""
        Grammar("""foo = ( ("c") )""").parse('c')

    def test_single_quoted_literals(self):
        Grammar("""foo = 'a' '"'""").parse('a"')

    def test_simple_custom_rules(self):
        """Run 2-arg custom-coded rules through their paces."""
        grammar = Grammar("""
            bracketed_digit = start digit end
            start = '['
            end = ']'""",
            digit=lambda text, pos:
                    (pos + 1) if text[pos].isdigit() else None)
        s = '[6]'
        self.assertEqual(grammar.parse(s),
            Node(grammar['bracketed_digit'], s, 0, 3, children=[
                Node(grammar['start'], s, 0, 1),
                Node(grammar['digit'], s, 1, 2),
                Node(grammar['end'], s, 2, 3)]))

    def test_complex_custom_rules(self):
        """Run 5-arg custom rules through their paces.

        Incidentally tests returning an actual Node from the custom rule.

        """
        grammar = Grammar("""
            bracketed_digit = start digit end
            start = '['
            end = ']'
            real_digit = '6'""",
            # In this particular implementation of the digit rule, no node is
            # generated for `digit`; it falls right through to `real_digit`.
            # I'm not sure if this could lead to problems; I can't think of
            # any, but it's probably not a great idea.
            digit=lambda text, pos, cache, error, grammar:
                    grammar['real_digit'].match_core(text, pos, cache, error))
        s = '[6]'
        self.assertEqual(grammar.parse(s),
            Node(grammar['bracketed_digit'], s, 0, 3, children=[
                Node(grammar['start'], s, 0, 1),
                Node(grammar['real_digit'], s, 1, 2),
                Node(grammar['end'], s, 2, 3)]))

    def test_lazy_custom_rules(self):
        """Make sure LazyReferences manually shoved into custom rules are
        resolved.

        Incidentally test passing full-on Expressions as custom rules and
        having a custom rule as the default one.

        """
        grammar = Grammar("""
            four = '4'
            five = '5'""",
            forty_five=Sequence(LazyReference('four'),
                                LazyReference('five'),
                                name='forty_five')).default('forty_five')
        s = '45'
        self.assertEqual(grammar.parse(s),
            Node(grammar['forty_five'], s, 0, 2, children=[
                Node(grammar['four'], s, 0, 1),
                Node(grammar['five'], s, 1, 2)]))

    def test_unconnected_custom_rules(self):
        """Make sure custom rules that aren't hooked to any other rules still
        get included in the grammar and that lone ones get set as the
        default.

        Incidentally test Grammar's `rules` default arg.

        """
        grammar = Grammar(one_char=lambda text, pos: pos + 1).default('one_char')
        s = '4'
        self.assertEqual(grammar.parse(s),
            Node(grammar['one_char'], s, 0, 1))

    def test_callability_of_routines(self):
        self.assertTrue(is_callable(function_rule))
        self.assertTrue(is_callable(self.method_rule))
        self.assertTrue(is_callable(self.rules['descriptor_rule']))

    def test_callability_custom_rules(self):
        """Confirms that functions, methods and method descriptors can all be
        used to supply custom grammar rules.
        """
        grammar = Grammar("""
            default = function method descriptor
            """,
            function=function_rule,
            method=self.method_rule,
            descriptor=self.rules['descriptor_rule'],
        )
        result = grammar.parse('functionmethoddescriptor')
        rule_names = [node.expr.name for node in result.children]
        self.assertEqual(rule_names, ['function', 'method', 'descriptor'])

    def test_lazy_default_rule(self):
        """Make sure we get an actual rule set as our default rule, even when
        the first rule has forward references and is thus a LazyReference at
        some point during grammar compilation.

        """
        grammar = Grammar(r"""
            styled_text = text
            text        = "hi"
            """)
        self.assertEqual(grammar.parse('hi'), Node(grammar['text'], 'hi', 0, 2))

    def test_immutable_grammar(self):
        """Make sure that a Grammar is immutable after being created."""
        grammar = Grammar(r"""
            foo = 'bar'
        """)

        def mod_grammar(grammar):
            grammar['foo'] = 1
        self.assertRaises(TypeError, mod_grammar, [grammar])

        def mod_grammar(grammar):
            new_grammar = Grammar(r"""
                baz = 'biff'
            """)
            grammar.update(new_grammar)
        self.assertRaises(AttributeError, mod_grammar, [grammar])

    def test_repr(self):
        self.assertTrue(repr(Grammar(r'foo = "a"')))

    def test_rule_ordering_is_preserved(self):
        grammar = Grammar('\n'.join('r%s = "something"' % i for i in range(100)))
        self.assertEqual(
            list(grammar.keys()),
            ['r%s' % i for i in range(100)])

    def test_rule_ordering_is_preserved_on_shallow_copies(self):
        grammar = Grammar('\n'.join('r%s = "something"' % i for i in range(100)))._copy()
        self.assertEqual(
            list(grammar.keys()),
            ['r%s' % i for i in range(100)])

    def test_repetitions(self):
        grammar = Grammar(r'''
            left_missing = "a"{,5}
            right_missing = "a"{5,}
            exact = "a"{5}
            range = "a"{2,5}
            optional = "a"?
            plus = "a"+
            star = "a"*
        ''')
        should_parse = [
            ("left_missing", ["a" * i for i in range(6)]),
            ("right_missing", ["a" * i for i in range(5, 8)]),
            ("exact", ["a" * 5]),
            ("range", ["a" * i for i in range(2, 6)]),
            ("optional", ["", "a"]),
            ("plus", ["a", "aa"]),
            ("star", ["", "a", "aa"]),
        ]
        for rule, examples in should_parse:
            for example in examples:
                assert grammar[rule].parse(example)

        should_not_parse = [
            ("left_missing", ["a" * 6]),
            ("right_missing", ["a" * i for i in range(5)]),
            ("exact", ["a" * i for i in list(range(5)) + list(range(6, 10))]),
            ("range", ["a" * i for i in list(range(2)) + list(range(6, 10))]),
            ("optional", ["aa"]),
            ("plus", [""]),
            ("star", ["b"]),
        ]
        for rule, examples in should_not_parse:
            for example in examples:
                with pytest.raises(ParseError):
                    grammar[rule].parse(example)

    def test_equal(self):
        grammar_def = (r"""
            x = y / z / ""
            y = "y" x
            z = "z" x
        """)
        assert Grammar(grammar_def) == Grammar(grammar_def)

        self.assertEqual(Grammar(rule_syntax), Grammar(rule_syntax))
        self.assertNotEqual(Grammar('expr = ~"[a-z]{1,3}"'), Grammar('expr = ~"[a-z]{2,3}"'))
        self.assertNotEqual(Grammar('expr = ~"[a-z]{1,3}"'), Grammar('expr = ~"[a-z]{1,4}"'))
        self.assertNotEqual(Grammar('expr = &"a"'), Grammar('expr = !"a"'))


class TokenGrammarTests(TestCase):
    """Tests for the TokenGrammar class and associated machinery"""

    def test_parse_success(self):
        """Token literals should work."""
        s = [Token('token1'), Token('token2')]
        grammar = TokenGrammar("""
            foo = token1 "token2"
            token1 = "token1"
            """)
        self.assertEqual(grammar.parse(s),
            Node(grammar['foo'], s, 0, 2, children=[
                Node(grammar['token1'], s, 0, 1),
                Node(TokenMatcher('token2'), s, 1, 2)]))

    def test_parse_failure(self):
        """Parse failures should work normally with token literals."""
        grammar = TokenGrammar("""
            foo = "token1" "token2"
            """)
        with pytest.raises(ParseError) as e:
            grammar.parse([Token('tokenBOO'), Token('token2')])
        assert "Rule 'foo' didn't match at" in str(e.value)

    def test_token_repr(self):
        t = Token('💣')
        self.assertTrue(isinstance(t.__repr__(), str))
        self.assertEqual('<Token "💣">', t.__repr__())

    def test_token_star_plus_expressions(self):
        a = Token("a")
        b = Token("b")
        grammar = TokenGrammar("""
            foo = "a"*
            bar = "a"+
        """)
        assert grammar["foo"].parse([]) is not None
        assert grammar["foo"].parse([a]) is not None
        assert grammar["foo"].parse([a, a]) is not None

        with pytest.raises(ParseError):
            grammar["foo"].parse([a, b])
        with pytest.raises(ParseError):
            grammar["foo"].parse([b])

        assert grammar["bar"].parse([a]) is not None
        with pytest.raises(ParseError):
            grammar["bar"].parse([a, b])
        with pytest.raises(ParseError):
            grammar["bar"].parse([b])


def test_precedence_of_string_modifiers():
    # r"strings", etc. should be parsed as a single literal, not r followed
    # by a string literal.
    g = Grammar(r"""
        escaped_bell = r"\b"
        r = "irrelevant"
    """)
    assert isinstance(g["escaped_bell"], Literal)
    assert g["escaped_bell"].literal == "\\b"
    with pytest.raises(ParseError):
        g.parse("irrelevant\b")

    g2 = Grammar(r"""
        escaped_bell = r"\b"
    """)
    assert g2.parse("\\b")


def test_binary_grammar():
    g = Grammar(r"""
        file = header body terminator
        header = b"\xFF" length b"~"
        length = ~rb"\d+"
        body = ~b"[^\xFF]*"
        terminator = b"\xFF"
    """)
    length = 22
    assert g.parse(b"\xff22~" + (b"a" * 22) + b"\xff") is not None


def test_inconsistent_string_types_in_grammar():
    with pytest.raises(VisitationError) as e:
        Grammar(r"""
            foo = b"foo"
            bar = "bar"
        """)
    assert e.value.original_class is BadGrammar
    with pytest.raises(VisitationError) as e:
        Grammar(r"""
            foo = ~b"foo"
            bar = "bar"
        """)
    assert e.value.original_class is BadGrammar

    # The following should parse without errors because they use the same
    # string types:
    Grammar(r"""
        foo = b"foo"
        bar = b"bar"
    """)
    Grammar(r"""
        foo = "foo"
        bar = "bar"
    """)


def test_left_associative():
    # Regression test for https://github.com/erikrose/parsimonious/issues/209
    language_grammar = r"""
    expression = operator_expression / non_operator_expression
    non_operator_expression = number_expression

    operator_expression = expression "+" non_operator_expression

    number_expression = ~"[0-9]+"
    """

    grammar = Grammar(language_grammar)
    with pytest.raises(LeftRecursionError) as e:
        grammar["operator_expression"].parse("1+2")
    assert "Parsimonious is a packrat parser, so it can't handle left recursion." in str(e.value)
