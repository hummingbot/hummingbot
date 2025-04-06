"""
Alternate namespace for cytoolz such that all functions are curried

Currying provides implicit partial evaluation of all functions

Example:

    Get usually requires two arguments, an index and a collection
    >>> from cytoolz.curried import get
    >>> get(0, ('a', 'b'))
    'a'

    When we use it in higher order functions we often want to pass a partially
    evaluated form
    >>> data = [(1, 2), (11, 22), (111, 222)]
    >>> list(map(lambda seq: get(0, seq), data))
    [1, 11, 111]

    The curried version allows simple expression of partial evaluation
    >>> list(map(get(0), data))
    [1, 11, 111]

See Also:
    cytoolz.functoolz.curry
"""
import cytoolz
from . import operator
from cytoolz import (
    apply,
    comp,
    complement,
    compose,
    compose_left,
    concat,
    concatv,
    count,
    curry,
    diff,
    first,
    flip,
    frequencies,
    identity,
    interleave,
    isdistinct,
    isiterable,
    juxt,
    last,
    memoize,
    merge_sorted,
    peek,
    pipe,
    second,
    thread_first,
    thread_last,
)
from .exceptions import merge, merge_with

accumulate = cytoolz.curry(cytoolz.accumulate)
assoc = cytoolz.curry(cytoolz.assoc)
assoc_in = cytoolz.curry(cytoolz.assoc_in)
cons = cytoolz.curry(cytoolz.cons)
countby = cytoolz.curry(cytoolz.countby)
dissoc = cytoolz.curry(cytoolz.dissoc)
do = cytoolz.curry(cytoolz.do)
drop = cytoolz.curry(cytoolz.drop)
excepts = cytoolz.curry(cytoolz.excepts)
filter = cytoolz.curry(cytoolz.filter)
get = cytoolz.curry(cytoolz.get)
get_in = cytoolz.curry(cytoolz.get_in)
groupby = cytoolz.curry(cytoolz.groupby)
interpose = cytoolz.curry(cytoolz.interpose)
itemfilter = cytoolz.curry(cytoolz.itemfilter)
itemmap = cytoolz.curry(cytoolz.itemmap)
iterate = cytoolz.curry(cytoolz.iterate)
join = cytoolz.curry(cytoolz.join)
keyfilter = cytoolz.curry(cytoolz.keyfilter)
keymap = cytoolz.curry(cytoolz.keymap)
map = cytoolz.curry(cytoolz.map)
mapcat = cytoolz.curry(cytoolz.mapcat)
nth = cytoolz.curry(cytoolz.nth)
partial = cytoolz.curry(cytoolz.partial)
partition = cytoolz.curry(cytoolz.partition)
partition_all = cytoolz.curry(cytoolz.partition_all)
partitionby = cytoolz.curry(cytoolz.partitionby)
peekn = cytoolz.curry(cytoolz.peekn)
pluck = cytoolz.curry(cytoolz.pluck)
random_sample = cytoolz.curry(cytoolz.random_sample)
reduce = cytoolz.curry(cytoolz.reduce)
reduceby = cytoolz.curry(cytoolz.reduceby)
remove = cytoolz.curry(cytoolz.remove)
sliding_window = cytoolz.curry(cytoolz.sliding_window)
sorted = cytoolz.curry(cytoolz.sorted)
tail = cytoolz.curry(cytoolz.tail)
take = cytoolz.curry(cytoolz.take)
take_nth = cytoolz.curry(cytoolz.take_nth)
topk = cytoolz.curry(cytoolz.topk)
unique = cytoolz.curry(cytoolz.unique)
update_in = cytoolz.curry(cytoolz.update_in)
valfilter = cytoolz.curry(cytoolz.valfilter)
valmap = cytoolz.curry(cytoolz.valmap)

del exceptions
del cytoolz
