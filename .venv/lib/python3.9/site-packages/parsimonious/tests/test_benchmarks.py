"""Tests to show that the benchmarks we based our speed optimizations on are
still valid"""
import unittest
from functools import partial
from timeit import timeit

timeit = partial(timeit, number=500000)

class TestBenchmarks(unittest.TestCase):
    def test_lists_vs_dicts(self):
        """See what's faster at int key lookup: dicts or lists."""
        list_time = timeit('item = l[9000]', 'l = [0] * 10000')
        dict_time = timeit('item = d[9000]', 'd = {x: 0 for x in range(10000)}')

        # Dicts take about 1.6x as long as lists in Python 2.6 and 2.7.
        self.assertTrue(list_time < dict_time, '%s < %s' % (list_time, dict_time))


    def test_call_vs_inline(self):
        """How bad is the calling penalty?"""
        no_call = timeit('l[0] += 1', 'l = [0]')
        call = timeit('add(); l[0] += 1', 'l = [0]\n'
                                          'def add():\n'
                                          '    pass')

        # Calling a function is pretty fast; it takes just 1.2x as long as the
        # global var access and addition in l[0] += 1.
        self.assertTrue(no_call < call, '%s (no call) < %s (call)' % (no_call, call))


    def test_startswith_vs_regex(self):
        """Can I beat the speed of regexes by special-casing literals?"""
        re_time = timeit(
            'r.match(t, 19)',
            'import re\n'
            "r = re.compile('hello')\n"
            "t = 'this is the finest hello ever'")
        startswith_time = timeit("t.startswith('hello', 19)",
                                 "t = 'this is the finest hello ever'")

        # Regexes take 2.24x as long as simple string matching.
        self.assertTrue(startswith_time < re_time,
            '%s (startswith) < %s (re)' % (startswith_time, re_time))