# Copyright (c) 2018-2023 by Ron Frederick <ronf@timeheart.net> and others.
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

"""SOCKS forwarding support"""

from ipaddress import ip_address
from typing import TYPE_CHECKING, Callable, Optional

from .forward import SSHForwarderCoro, SSHLocalForwarder
from .session import DataType


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .connection import SSHConnection


_RecvHandler = Optional[Callable[[bytes], None]]


SOCKS4                  = 0x04
SOCKS5                  = 0x05

SOCKS_CONNECT           = 0x01

SOCKS4_OK               = 0x5a
SOCKS5_OK               = 0x00

SOCKS5_AUTH_NONE        = 0x00

SOCKS5_ADDR_IPV4        = 0x01
SOCKS5_ADDR_HOSTNAME    = 0x03
SOCKS5_ADDR_IPV6        = 0x04

SOCKS4_OK_RESPONSE      = bytes((0, SOCKS4_OK, 0, 0, 0, 0, 0, 0))
SOCKS5_OK_RESPONSE_HDR  = bytes((SOCKS5, SOCKS5_OK, 0))

_socks5_addr_len = { SOCKS5_ADDR_IPV4: 4, SOCKS5_ADDR_IPV6: 16 }


class SSHSOCKSForwarder(SSHLocalForwarder):
    """SOCKS dynamic port forwarding connection handler"""

    def __init__(self, conn: 'SSHConnection', coro: SSHForwarderCoro):
        super().__init__(conn, coro)

        self._inpbuf = b''
        self._bytes_needed = 2
        self._recv_handler: _RecvHandler = self._recv_version
        self._addrtype = 0
        self._host = ''
        self._port = 0

    def _connect(self) -> None:
        """Send request to open a new tunnel connection"""

        assert self._transport is not None

        self._recv_handler = None

        orig_host, orig_port = self._transport.get_extra_info('peername')[:2]
        self.forward(self._host, self._port, orig_host, orig_port)

    def _send_socks4_ok(self) -> None:
        """Send SOCKS4 success response"""

        assert self._transport is not None

        self._transport.write(SOCKS4_OK_RESPONSE)

    def _send_socks5_ok(self) -> None:
        """Send SOCKS5 success response"""

        assert self._transport is not None

        addrlen = _socks5_addr_len[self._addrtype] + 2

        self._transport.write(SOCKS5_OK_RESPONSE_HDR +
                              bytes((self._addrtype,)) +
                              addrlen * b'\0')

    def _recv_version(self, data: bytes) -> None:
        """Parse SOCKS version"""

        if data[0] == SOCKS4:
            if data[1] == SOCKS_CONNECT:
                self._bytes_needed = 6
                self._recv_handler = self._recv_socks4_addr
            else:
                self.close()
        elif data[0] == SOCKS5:
            self._bytes_needed = data[1]
            self._recv_handler = self._recv_socks5_authlist
        else:
            self.close()

    def _recv_socks4_addr(self, data: bytes) -> None:
        """Parse SOCKSv4 address and port"""

        self._port = (data[0] << 8) + data[1]

        # If address is 0.0.0.x, read a hostname later
        if data[2:5] != b'\0\0\0' or data[5] == 0:
            self._host = str(ip_address(data[2:]))

        self._bytes_needed = -1
        self._recv_handler = self._recv_socks4_user

    def _recv_socks4_user(self, data: bytes) -> None:
        """Parse SOCKSv4 username"""

        # pylint: disable=unused-argument

        if self._host:
            self._send_socks4_ok()
            self._connect()
        else:
            self._bytes_needed = -1
            self._recv_handler = self._recv_socks4_hostname

    def _recv_socks4_hostname(self, data: bytes) -> None:
        """Parse SOCKSv4 hostname"""

        try:
            self._host = data.decode('utf-8')
        except UnicodeDecodeError:
            self.close()
            return

        self._send_socks4_ok()
        self._connect()

    def _recv_socks5_authlist(self, data: bytes) -> None:
        """Parse SOCKSv5 list of authentication methods"""

        assert self._transport is not None

        if SOCKS5_AUTH_NONE in data:
            self._transport.write(bytes((SOCKS5, SOCKS5_AUTH_NONE)))

            self._bytes_needed = 4
            self._recv_handler = self._recv_socks5_command
        else:
            self.close()

    def _recv_socks5_command(self, data: bytes) -> None:
        """Parse SOCKSv5 command"""

        if data[0] == SOCKS5 and data[1] == SOCKS_CONNECT and data[2] == 0:
            if data[3] == SOCKS5_ADDR_HOSTNAME:
                self._bytes_needed = 1
                self._recv_handler = self._recv_socks5_hostlen
                self._addrtype = SOCKS5_ADDR_IPV4
            else:
                addrlen = _socks5_addr_len.get(data[3])

                if addrlen:
                    self._bytes_needed = addrlen
                    self._recv_handler = self._recv_socks5_addr
                    self._addrtype = data[3]
                else:
                    self.close()
        else:
            self.close()

    def _recv_socks5_addr(self, data: bytes) -> None:
        """Parse SOCKSv5 address"""

        self._host = str(ip_address(data))

        self._bytes_needed = 2
        self._recv_handler = self._recv_socks5_port

    def _recv_socks5_hostlen(self, data: bytes) -> None:
        """Parse SOCKSv5 host length"""

        self._bytes_needed = data[0]
        self._recv_handler = self._recv_socks5_host

    def _recv_socks5_host(self, data: bytes) -> None:
        """Parse SOCKSv5 host"""

        try:
            self._host = data.decode('utf-8')
        except UnicodeDecodeError:
            self.close()
            return

        self._bytes_needed = 2
        self._recv_handler = self._recv_socks5_port

    def _recv_socks5_port(self, data: bytes) -> None:
        """Parse SOCKSv5 port"""

        self._port = (data[0] << 8) + data[1]
        self._send_socks5_ok()
        self._connect()

    def data_received(self, data: bytes, datatype: DataType = None) -> None:
        """Handle incoming data from the SOCKS client"""

        if self._recv_handler:
            self._inpbuf += data

            while self._recv_handler: # type: ignore[truthy-function]
                if self._bytes_needed < 0:
                    idx = self._inpbuf.find(b'\0')
                    if idx >= 0:
                        data = self._inpbuf[:idx]
                        self._inpbuf = self._inpbuf[idx+1:]
                        self._recv_handler(data)
                    elif len(self._inpbuf) > 255:
                        # SOCKSv4 user or hostname too long
                        self.close()
                        return
                    else:
                        return
                else:
                    if len(self._inpbuf) >= self._bytes_needed:
                        data = self._inpbuf[:self._bytes_needed]
                        self._inpbuf = self._inpbuf[self._bytes_needed:]
                        self._recv_handler(data)
                    else:
                        return

            data = self._inpbuf
            self._inpbuf = b''

        if data:
            super().data_received(data, datatype)
