"""
 Copyright (C) 2020, 2021 biqqles.
 This Source Code Form is subject to the terms of the Mozilla Public
 License, v. 2.0. If a copy of the MPL was not distributed with this
 file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
from .decorator import dataclass, make_dataclass
from .dataclass import DataClass, Hashed, Internal, factory
from .functions import fields, values, as_dict, as_tuple, replace

# aliases intended for migration from dataclasses
asdict, astuple = as_dict, as_tuple

# for the benefit of mypy --strict
__all__ = (
    'dataclass', 'make_dataclass',
    'DataClass', 'Hashed', 'Internal', 'factory',
    'fields', 'values', 'as_dict', 'as_tuple', 'replace',
    'asdict', 'astuple',
)
