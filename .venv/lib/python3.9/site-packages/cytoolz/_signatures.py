from toolz._signatures import *
from toolz._signatures import (_is_arity, _has_varargs, _has_keywords,
                               _num_required_args, _is_partial_args, _is_valid_args)

cytoolz_info = {}

cytoolz_info['cytoolz.dicttoolz'] = dict(
    assoc=[
        lambda d, key, value, factory=dict: None],
    assoc_in=[
        lambda d, keys, value, factory=dict: None],
    dissoc=[
        lambda d, *keys, **kwargs: None],
    get_in=[
        lambda keys, coll, default=None, no_default=False: None],
    itemfilter=[
        lambda predicate, d, factory=dict: None],
    itemmap=[
        lambda func, d, factory=dict: None],
    keyfilter=[
        lambda predicate, d, factory=dict: None],
    keymap=[
        lambda func, d, factory=dict: None],
    merge=[
        lambda *dicts, **kwargs: None],
    merge_with=[
        lambda func, *dicts, **kwargs: None],
    update_in=[
        lambda d, keys, func, default=None, factory=dict: None],
    valfilter=[
        lambda predicate, d, factory=dict: None],
    valmap=[
        lambda func, d, factory=dict: None],
)

cytoolz_info['cytoolz.functoolz'] = dict(
    apply=[
        lambda *func_and_args, **kwargs: None],
    Compose=[
        lambda *funcs: None],
    complement=[
        lambda func: None],
    compose=[
        lambda *funcs: None],
    compose_left=[
        lambda *funcs: None],
    curry=[
        lambda *args, **kwargs: None],
    do=[
        lambda func, x: None],
    excepts=[
        lambda exc, func, handler=None: None],
    flip=[
        lambda: None,
        lambda func: None,
        lambda func, a: None,
        lambda func, a, b: None],
    _flip=[
        lambda func, a, b: None],
    identity=[
        lambda x: None],
    juxt=[
        lambda *funcs: None],
    memoize=[
        lambda cache=None, key=None: None,
        lambda func, cache=None, key=None: None],
    _memoize=[
        lambda func, cache=None, key=None: None],
    pipe=[
        lambda data, *funcs: None],
    return_none=[
        lambda exc: None],
    thread_first=[
        lambda val, *forms: None],
    thread_last=[
        lambda val, *forms: None],
)

cytoolz_info['cytoolz.itertoolz'] = dict(
    accumulate=[
        lambda binop, seq, initial='__no__default__': None],
    concat=[
        lambda seqs: None],
    concatv=[
        lambda *seqs: None],
    cons=[
        lambda el, seq: None],
    count=[
        lambda seq: None],
    diff=[
        lambda *seqs, **kwargs: None],
    drop=[
        lambda n, seq: None],
    first=[
        lambda seq: None],
    frequencies=[
        lambda seq: None],
    get=[
        lambda ind, seq, default=None: None],
    getter=[
        lambda index: None],
    groupby=[
        lambda key, seq: None],
    identity=[
        lambda x: None],
    interleave=[
        lambda seqs: None],
    interpose=[
        lambda el, seq: None],
    isdistinct=[
        lambda seq: None],
    isiterable=[
        lambda x: None],
    iterate=[
        lambda func, x: None],
    join=[
        lambda leftkey, leftseq, rightkey, rightseq, left_default=None, right_default=None: None],
    last=[
        lambda seq: None],
    mapcat=[
        lambda func, seqs: None],
    merge_sorted=[
        lambda *seqs, **kwargs: None],
    nth=[
        lambda n, seq: None],
    partition=[
        lambda n, seq, pad=None: None],
    partition_all=[
        lambda n, seq: None],
    peek=[
        lambda seq: None],
    peekn=[
        lambda n, seq: None],
    pluck=[
        lambda ind, seqs, default=None: None],
    random_sample=[
        lambda prob, seq, random_state=None: None],
    reduceby=[
        lambda key, binop, seq, init=None: None],
    remove=[
        lambda predicate, seq: None],
    rest=[
        lambda seq: None],
    second=[
        lambda seq: None],
    sliding_window=[
        lambda n, seq: None],
    tail=[
        lambda n, seq: None],
    take=[
        lambda n, seq: None],
    take_nth=[
        lambda n, seq: None],
    topk=[
        lambda k, seq, key=None: None],
    unique=[
        lambda seq, key=None: None],
)

cytoolz_info['cytoolz.recipes'] = dict(
    countby=[
        lambda key, seq: None],
    partitionby=[
        lambda func, seq: None],
)

def update_signature_registry():
    create_signature_registry(cytoolz_info)
    module_info.update(cytoolz_info)
