# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import random

from astroid.context import InferenceContext
from astroid.exceptions import UseInferenceDefault
from astroid.inference_tip import inference_tip
from astroid.manager import AstroidManager
from astroid.nodes.node_classes import (
    Attribute,
    Call,
    Const,
    EvaluatedObject,
    List,
    Name,
    Set,
    Tuple,
)
from astroid.util import safe_infer

ACCEPTED_ITERABLES_FOR_SAMPLE = (List, Set, Tuple)


def _clone_node_with_lineno(node, parent, lineno):
    if isinstance(node, EvaluatedObject):
        node = node.original
    cls = node.__class__
    other_fields = node._other_fields
    _astroid_fields = node._astroid_fields
    init_params = {
        "lineno": lineno,
        "col_offset": node.col_offset,
        "parent": parent,
        "end_lineno": node.end_lineno,
        "end_col_offset": node.end_col_offset,
    }
    postinit_params = {param: getattr(node, param) for param in _astroid_fields}
    if other_fields:
        init_params.update({param: getattr(node, param) for param in other_fields})
    new_node = cls(**init_params)
    if hasattr(node, "postinit") and _astroid_fields:
        new_node.postinit(**postinit_params)
    return new_node


def infer_random_sample(node, context: InferenceContext | None = None):
    if len(node.args) != 2:
        raise UseInferenceDefault

    inferred_length = safe_infer(node.args[1], context=context)
    if not isinstance(inferred_length, Const):
        raise UseInferenceDefault
    if not isinstance(inferred_length.value, int):
        raise UseInferenceDefault

    inferred_sequence = safe_infer(node.args[0], context=context)
    if not inferred_sequence:
        raise UseInferenceDefault

    if not isinstance(inferred_sequence, ACCEPTED_ITERABLES_FOR_SAMPLE):
        raise UseInferenceDefault

    if inferred_length.value > len(inferred_sequence.elts):
        # In this case, this will raise a ValueError
        raise UseInferenceDefault

    try:
        elts = random.sample(inferred_sequence.elts, inferred_length.value)
    except ValueError as exc:
        raise UseInferenceDefault from exc

    new_node = List(
        lineno=node.lineno,
        col_offset=node.col_offset,
        parent=node.scope(),
        end_lineno=node.end_lineno,
        end_col_offset=node.end_col_offset,
    )
    new_elts = [
        _clone_node_with_lineno(elt, parent=new_node, lineno=new_node.lineno)
        for elt in elts
    ]
    new_node.postinit(new_elts)
    return iter((new_node,))


def _looks_like_random_sample(node) -> bool:
    func = node.func
    if isinstance(func, Attribute):
        return func.attrname == "sample"
    if isinstance(func, Name):
        return func.name == "sample"
    return False


def register(manager: AstroidManager) -> None:
    manager.register_transform(
        Call, inference_tip(infer_random_sample), _looks_like_random_sample
    )
