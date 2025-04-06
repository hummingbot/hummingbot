# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for numpy ma module."""

from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.manager import AstroidManager


def numpy_ma_transform():
    """
    Infer the call of various numpy.ma functions.

    :param node: node to infer
    :param context: inference context
    """
    return parse(
        """
    import numpy.ma
    def masked_where(condition, a, copy=True):
        return numpy.ma.masked_array(a, mask=[])

    def masked_invalid(a, copy=True):
        return numpy.ma.masked_array(a, mask=[])
    """
    )


def register(manager: AstroidManager) -> None:
    register_module_extender(manager, "numpy.ma", numpy_ma_transform)
