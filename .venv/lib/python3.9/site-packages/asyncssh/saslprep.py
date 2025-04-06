# Copyright (c) 2013-2024 by Ron Frederick <ronf@timeheart.net> and others.
#
# This program and the accompanying materials are made available under
# the terms of the Eclipse Public License v2.0 which accompanies this
# distribution and is available at:
#
#     http://www.eclipse.org/legal/epl-2.0/
#
# This program may also be made available under the following secondary
# licenses when the conditions for such availability set forth in the
# Eclipse Public License v2.0 are satisfied:
#
#    GNU General Public License, Version 2.0, or any later versions of
#    that license
#
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later
#
# Contributors:
#     Ron Frederick - initial implementation, API, and documentation

"""SASLprep implementation

   This module implements the stringprep algorithm defined in RFC 3454
   and the SASLprep profile of stringprep defined in RFC 4013. This
   profile is used to normalize usernames and passwords sent in the
   SSH protocol.

"""

# The stringprep module should not be flagged as deprecated
# pylint: disable=deprecated-module
import stringprep
# pylint: enable=deprecated-module
import unicodedata

from typing import Callable, Optional, Sequence
from typing_extensions import Literal


class SASLPrepError(ValueError):
    """Invalid data provided to saslprep"""


def _check_bidi(s: str) -> None:
    """Enforce bidirectional character check from RFC 3454 (stringprep)"""

    r_and_al_cat = False
    l_cat = False

    for c in s:
        if not r_and_al_cat and stringprep.in_table_d1(c):
            r_and_al_cat = True

        if not l_cat and stringprep.in_table_d2(c):
            l_cat = True

    if r_and_al_cat and l_cat:
        raise SASLPrepError('Both RandALCat and LCat characters present')

    if r_and_al_cat and not (stringprep.in_table_d1(s[0]) and
                             stringprep.in_table_d1(s[-1])):
        raise SASLPrepError('RandALCat character not at both start and end')


def _stringprep(s: str, check_unassigned: bool,
                mapping: Optional[Callable[[str], str]],
                normalization: Literal['NFC', 'NFD', 'NFKC', 'NFKD'],
                prohibited: Sequence[Callable[[str], bool]],
                bidi: bool) -> str:
    """Implement a stringprep profile as defined in RFC 3454"""

    if check_unassigned: # pragma: no branch
        for c in s:
            if stringprep.in_table_a1(c):
                raise SASLPrepError(f'Unassigned character: {c!r}')

    if mapping: # pragma: no branch
        s = mapping(s)

    if normalization: # pragma: no branch
        s = unicodedata.normalize(normalization, s)

    if prohibited: # pragma: no branch
        for c in s:
            for lookup in prohibited:
                if lookup(c):
                    raise SASLPrepError(f'Prohibited character: {c!r}')

    if bidi: # pragma: no branch
        _check_bidi(s)

    return s


def _map_saslprep(s: str) -> str:
    """Map stringprep table B.1 to nothing and C.1.2 to ASCII space"""

    r = []

    for c in s:
        if stringprep.in_table_c12(c):
            r.append(' ')
        elif not stringprep.in_table_b1(c):
            r.append(c)

    return ''.join(r)


def saslprep(s: str) -> str:
    """Implement SASLprep profile defined in RFC 4013"""

    prohibited = (stringprep.in_table_c12, stringprep.in_table_c21_c22,
                  stringprep.in_table_c3, stringprep.in_table_c4,
                  stringprep.in_table_c5, stringprep.in_table_c6,
                  stringprep.in_table_c7, stringprep.in_table_c8,
                  stringprep.in_table_c9)

    return _stringprep(s, True, _map_saslprep, 'NFKC', prohibited, True)
