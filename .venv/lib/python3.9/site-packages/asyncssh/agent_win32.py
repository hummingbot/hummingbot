# Copyright (c) 2016-2024 by Ron Frederick <ronf@timeheart.net> and others.
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

"""SSH agent support code for Windows"""

# Some of the imports below won't be found when running pylint on UNIX
# pylint: disable=import-error

import asyncio
import ctypes
import ctypes.wintypes
import errno
from typing import TYPE_CHECKING, Tuple, Union, cast

from .misc import open_file


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .agent import AgentReader, AgentWriter


try:
    import mmapfile
    import win32api
    import win32con
    import win32ui
    _pywin32_available = True
except ImportError:
    _pywin32_available = False


_AGENT_COPYDATA_ID = 0x804e50ba
_AGENT_MAX_MSGLEN = 8192
_AGENT_NAME = 'Pageant'

_DEFAULT_OPENSSH_PATH = r'\\.\pipe\openssh-ssh-agent'


def _find_agent_window() -> 'win32ui.PyCWnd':
    """Find and return the Pageant window"""

    if _pywin32_available:
        try:
            return win32ui.FindWindow(_AGENT_NAME, _AGENT_NAME)
        except win32ui.error:
            raise OSError(errno.ENOENT, 'Agent not found') from None
    else:
        raise OSError(errno.ENOENT, 'PyWin32 not installed') from None


class _CopyDataStruct(ctypes.Structure):
    """Windows COPYDATASTRUCT argument for WM_COPYDATA message"""

    _fields_ = (('dwData', ctypes.wintypes.LPARAM),
                ('cbData', ctypes.wintypes.DWORD),
                ('lpData', ctypes.c_char_p))


class _PageantTransport:
    """Transport to connect to Pageant agent on Windows"""

    def __init__(self) -> None:
        self._mapname = f'{_AGENT_NAME}{win32api.GetCurrentThreadId():08x}'

        try:
            self._mapfile = mmapfile.mmapfile('', self._mapname,
                                              _AGENT_MAX_MSGLEN, 0, 0)
        except mmapfile.error as exc:
            raise OSError(errno.EIO, str(exc)) from None

        self._cds = _CopyDataStruct(_AGENT_COPYDATA_ID, len(self._mapname) + 1,
                                    self._mapname.encode())

        self._writing = False

    def write(self, data: bytes) -> None:
        """Write request data to Pageant agent"""

        if not self._writing:
            self._mapfile.seek(0)
            self._writing = True

        try:
            self._mapfile.write(data)
        except ValueError as exc:
            raise OSError(errno.EIO, str(exc)) from None

    async def readexactly(self, n: int) -> bytes:
        """Read response data from Pageant agent"""

        if self._writing:
            cwnd = _find_agent_window()

            if not cwnd.SendMessage(win32con.WM_COPYDATA, 0,
                                    cast(int, self._cds)):
                raise OSError(errno.EIO, 'Unable to send agent request')

            self._writing = False
            self._mapfile.seek(0)

        result = self._mapfile.read(n)

        if len(result) != n:
            raise asyncio.IncompleteReadError(result, n)

        return result

    def close(self) -> None:
        """Close the connection to Pageant"""

        if self._mapfile:
            self._mapfile.close()

    async def wait_closed(self) -> None:
        """Wait for the transport to close"""


class _W10OpenSSHTransport:
    """Transport to connect to OpenSSH agent on Windows 10"""

    def __init__(self, agent_path: str):
        self._agentfile = open_file(agent_path, 'r+b')

    async def readexactly(self, n: int) -> bytes:
        """Read response data from OpenSSH agent"""

        result = self._agentfile.read(n)

        if len(result) != n:
            raise asyncio.IncompleteReadError(result, n)

        return result

    def write(self, data: bytes) -> None:
        """Write request data to OpenSSH agent"""

        self._agentfile.write(data)

    def close(self) -> None:
        """Close the connection to OpenSSH"""

        if self._agentfile:
            self._agentfile.close()

    async def wait_closed(self) -> None:
        """Wait for the transport to close"""


async def open_agent(agent_path: str) -> Tuple['AgentReader', 'AgentWriter']:
    """Open a connection to the Pageant or Windows 10 OpenSSH agent"""

    transport: Union[None, _PageantTransport, _W10OpenSSHTransport] = None

    if not agent_path:
        try:
            _find_agent_window()
            transport = _PageantTransport()
        except OSError:
            agent_path = _DEFAULT_OPENSSH_PATH

    if not transport:
        transport = _W10OpenSSHTransport(agent_path)

    return transport, transport
