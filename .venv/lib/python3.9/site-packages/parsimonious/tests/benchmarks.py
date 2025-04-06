"""Benchmarks for Parsimonious

Run these with ``python parsimonious/tests/benchmarks.py``. They don't run during
normal test runs because they're not tests--they don't assert anything. Also,
they're a bit slow.

These differ from the ones in test_benchmarks in that these are meant to be
compared from revision to revision of Parsimonious to make sure we're not
getting slower. test_benchmarks simply makes sure our choices among
implementation alternatives remain valid.

"""
from __future__ import print_function
import gc
from timeit import repeat

from parsimonious.grammar import Grammar


def test_not_really_json_parsing():
    """As a baseline for speed, parse some JSON.

    I have no reason to believe that JSON is a particularly representative or
    revealing grammar to test with. Also, this is a naive, unoptimized,
    incorrect grammar, so don't use it as a basis for comparison with other
    parsers. It's just meant to compare across versions of Parsimonious.

    """
    father = """{
        "id" : 1,
        "married" : true,
        "name" : "Larry Lopez",
        "sons" : null,
        "daughters" : [
          {
            "age" : 26,
            "name" : "Sandra"
            },
          {
            "age" : 25,
            "name" : "Margaret"
            },
          {
            "age" : 6,
            "name" : "Mary"
            }
          ]
        }"""
    more_fathers = ','.join([father] * 60)
    json = '{"fathers" : [' + more_fathers + ']}'
    grammar = Grammar(r"""
        value = space (string / number / object / array / true_false_null)
                space

        object = "{" members "}"
        members = (pair ("," pair)*)?
        pair = string ":" value
        array = "[" elements "]"
        elements = (value ("," value)*)?
        true_false_null = "true" / "false" / "null"

        string = space "\"" chars "\"" space
        chars = ~"[^\"]*"  # TODO implement the real thing
        number = (int frac exp) / (int exp) / (int frac) / int
        int = "-"? ((digit1to9 digits) / digit)
        frac = "." digits
        exp = e digits
        digits = digit+
        e = "e+" / "e-" / "e" / "E+" / "E-" / "E"

        digit1to9 = ~"[1-9]"
        digit = ~"[0-9]"
        space = ~"\s*"
        """)

    # These number and repetition values seem to keep results within 5% of the
    # difference between min and max. We get more consistent results running a
    # bunch of single-parse tests and taking the min rather than upping the
    # NUMBER and trying to stomp out the outliers with averaging.
    NUMBER = 1
    REPEAT = 5
    total_seconds = min(repeat(lambda: grammar.parse(json),
                               lambda: gc.enable(),  # so we take into account how we treat the GC
                               repeat=REPEAT,
                               number=NUMBER))
    seconds_each = total_seconds / NUMBER

    kb = len(json) / 1024.0
    print('Took %.3fs to parse %.1fKB: %.0fKB/s.' % (seconds_each,
                                                     kb,
                                                     kb / seconds_each))


if __name__ == "__main__":
    test_not_really_json_parsing()