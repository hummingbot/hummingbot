# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for numpy.core.numeric module."""

import functools

from astroid.brain.brain_numpy_utils import (
    attribute_looks_like_numpy_member,
    infer_numpy_member,
)
from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.inference_tip import inference_tip
from astroid.manager import AstroidManager
from astroid.nodes.node_classes import Attribute


def numpy_core_numeric_transform():
    return parse(
        """
    # different functions defined in numeric.py
    import numpy
    def zeros_like(a, dtype=None, order='K', subok=True, shape=None): return numpy.ndarray((0, 0))
    def ones_like(a, dtype=None, order='K', subok=True, shape=None): return numpy.ndarray((0, 0))
    def full_like(a, fill_value, dtype=None, order='K', subok=True, shape=None): return numpy.ndarray((0, 0))
        """
    )


METHODS_TO_BE_INFERRED = {
    "ones": """def ones(shape, dtype=None, order='C'):
            return numpy.ndarray([0, 0])"""
}


def register(manager: AstroidManager) -> None:
    register_module_extender(
        manager, "numpy.core.numeric", numpy_core_numeric_transform
    )

    for method_name, function_src in METHODS_TO_BE_INFERRED.items():
        inference_function = functools.partial(infer_numpy_member, function_src)
        manager.register_transform(
            Attribute,
            inference_tip(inference_function),
            functools.partial(attribute_looks_like_numpy_member, method_name),
        )
