# Copyright (c) 2017-2024 by Ron Frederick <ronf@timeheart.net> and others.
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

"""GSSAPI wrapper"""

import sys

from typing import Optional

from .misc import BytesOrStrDict


try:
    # pylint: disable=unused-import

    if sys.platform == 'win32': # pragma: no cover
        from .gss_win32 import GSSBase, GSSClient, GSSServer, GSSError
    else:
        from .gss_unix import GSSBase, GSSClient, GSSServer, GSSError

    gss_available = True
except ImportError: # pragma: no cover
    gss_available = False

    class GSSError(ValueError): # type: ignore
        """Stub class for reporting that GSS is not available"""

        def __init__(self, maj_code: int, min_code: int,
                 token: Optional[bytes] = None):
            super().__init__('GSS not available')

            self.maj_code = maj_code
            self.min_code = min_code
            self.token = token

    class GSSBase: # type: ignore
        """Base class for reporting that GSS is not available"""

    class GSSClient(GSSBase): # type: ignore
        """Stub client class for reporting that GSS is not available"""

        def __init__(self, _host: str, _store: Optional[BytesOrStrDict],
                     _delegate_creds: bool):
            raise GSSError(0, 0)

    class GSSServer(GSSBase): # type: ignore
        """Stub client class for reporting that GSS is not available"""

        def __init__(self, _host: str, _store: Optional[BytesOrStrDict]):
            raise GSSError(0, 0)
