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

"""X11 forwarding support"""

import asyncio
import os
from pathlib import Path
import socket
import time
from typing import TYPE_CHECKING, Callable, Dict, Iterable
from typing import NamedTuple, Optional, Sequence, Set, Tuple

from .constants import OPEN_CONNECT_FAILED
from .forward import SSHForwarder, SSHForwarderCoro
from .listener import SSHListener, create_tcp_forward_listener
from .logging import logger
from .misc import ChannelOpenError
from .session import DataType


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .channel import SSHChannel
    from .connection import SSHServerConnection


_RecvHandler = Optional[Callable[[bytes], None]]


# Xauth address families
XAUTH_FAMILY_IPV4     = 0
XAUTH_FAMILY_DECNET   = 1
XAUTH_FAMILY_IPV6     = 6
XAUTH_FAMILY_HOSTNAME = 256
XAUTH_FAMILY_WILD     = 65535

# Xauth protocol values
XAUTH_PROTO_COOKIE    = b'MIT-MAGIC-COOKIE-1'
XAUTH_COOKIE_LEN      = 16

# Xauth lock information
XAUTH_LOCK_SUFFIX     = '-c'
XAUTH_LOCK_TRIES      = 5
XAUTH_LOCK_DELAY      = 0.2
XAUTH_LOCK_DEAD       = 5

# X11 display and port numbers
X11_BASE_PORT         = 6000
X11_DISPLAY_START     = 10
X11_MAX_DISPLAYS      = 64

# Host to listen on when doing X11 forwarding
X11_LISTEN_HOST       = 'localhost'


def _parse_display(display: str) -> Tuple[str, str, int]:
    """Parse an X11 display value"""

    try:
        host, dpynum = display.rsplit(':', 1)

        if host.startswith('[') and host.endswith(']'):
            host = host[1:-1]

        idx = dpynum.find('.')
        if idx >= 0:
            screen = int(dpynum[idx+1:])
            dpynum = dpynum[:idx]
        else:
            screen = 0
    except (ValueError, UnicodeEncodeError):
        raise ValueError('Invalid X11 display') from None

    return host, dpynum, screen

async def _lookup_host(loop: asyncio.AbstractEventLoop, host: str,
                       family: int) -> Sequence[str]:
    """Look up IPv4 or IPv6 addresses of a host name"""

    try:
        addrinfo = await loop.getaddrinfo(host, 0, family=family,
                                          type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []

    return [ai[4][0] for ai in addrinfo]


class SSHXAuthorityEntry(NamedTuple):
    """An entry in an Xauthority file"""

    family: int
    addr: bytes
    dpynum: bytes
    proto: bytes
    data: bytes

    def __bytes__(self) -> bytes:
        """Construct an Xauthority entry"""

        def _uint16(value: int) -> bytes:
            """Construct a big-endian 16-bit unsigned integer"""

            return value.to_bytes(2, 'big')

        def _string(data: bytes) -> bytes:
            """Construct a binary string with a 16-bit length"""

            return _uint16(len(data)) + data

        return b''.join((_uint16(self.family), _string(self.addr),
                         _string(self.dpynum), _string(self.proto),
                         _string(self.data)))


class SSHX11ClientForwarder(SSHForwarder):
    """X11 forwarding connection handler"""

    def __init__(self, listener: 'SSHX11ClientListener', peer: SSHForwarder):
        super().__init__(peer)

        self._listener = listener

        self._inpbuf = b''
        self._bytes_needed = 12
        self._recv_handler: _RecvHandler = self._recv_prefix

        self._endian = b''
        self._prefix = b''
        self._auth_proto_len = 0
        self._auth_data_len = 0

        self._auth_proto = b''
        self._auth_proto_pad = b''

        self._auth_data = b''
        self._auth_data_pad = b''

    def _encode_uint16(self, value: int) -> bytes:
        """Encode a 16-bit unsigned integer"""

        if self._endian == b'B':
            return bytes((value >> 8, value & 255))
        else:
            return bytes((value & 255, value >> 8))

    def _decode_uint16(self, value: bytes) -> int:
        """Decode a 16-bit unsigned integer"""

        if self._endian == b'B':
            return (value[0] << 8) + value[1]
        else:
            return (value[1] << 8) + value[0]

    @staticmethod
    def _padded_len(length: int) -> int:
        """Return length rounded up to the next multiple of 4 bytes"""

        return ((length + 3) // 4) * 4

    @staticmethod
    def _pad(data: bytes) -> bytes:
        """Pad a string to a multiple of 4 bytes"""

        length = len(data) % 4
        return data + ((4 - length) * b'\00' if length else b'')

    def _recv_prefix(self, data: bytes) -> None:
        """Parse X11 client prefix"""

        self._endian = data[:1]
        self._prefix = data

        self._auth_proto_len = self._decode_uint16(data[6:8])
        self._auth_data_len = self._decode_uint16(data[8:10])

        self._recv_handler = self._recv_auth_proto
        self._bytes_needed = self._padded_len(self._auth_proto_len)

    def _recv_auth_proto(self, data: bytes) -> None:
        """Extract X11 auth protocol"""

        self._auth_proto = data[:self._auth_proto_len]
        self._auth_proto_pad = data[self._auth_proto_len:]

        self._recv_handler = self._recv_auth_data
        self._bytes_needed = self._padded_len(self._auth_data_len)

    def _recv_auth_data(self, data: bytes) -> None:
        """Extract X11 auth data"""

        self._auth_data = data[:self._auth_data_len]
        self._auth_data_pad = data[self._auth_data_len:]

        try:
            self._auth_data = self._listener.validate_auth(self._auth_data)
        except KeyError:
            reason = b'Invalid authentication key\n'

            response = b''.join((bytes((0, len(reason))),
                                 self._encode_uint16(11),
                                 self._encode_uint16(0),
                                 self._encode_uint16((len(reason) + 3) // 4),
                                 self._pad(reason)))

            try:
                self.write(response)
                self.write_eof()
            except OSError: # pragma: no cover
                pass

            self._inpbuf = b''
        else:
            self._inpbuf = (self._prefix + self._auth_proto +
                            self._auth_proto_pad + self._auth_data +
                            self._auth_data_pad)

        self._recv_handler = None
        self._bytes_needed = 0

    def data_received(self, data: bytes, datatype: DataType = None) -> None:
        """Handle incoming data from the X11 client"""

        if self._recv_handler:
            self._inpbuf += data

            while self._recv_handler: # type: ignore[truthy-function]
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


class SSHX11ClientListener:
    """Client listener used to accept forwarded X11 connections"""

    def __init__(self, loop: asyncio.AbstractEventLoop, host: str, dpynum: str,
                 auth_proto: bytes, auth_data: bytes):
        self._host = host
        self._dpynum = dpynum
        self._auth_proto = auth_proto
        self._local_auth = auth_data

        if host.startswith('/'):
            self._connect_coro: SSHForwarderCoro = loop.create_unix_connection
            self._connect_args: Sequence[object] = (host + ':' + dpynum,)
        elif host in ('', 'unix'):
            self._connect_coro = loop.create_unix_connection
            self._connect_args = ('/tmp/.X11-unix/X' + dpynum,)
        else:
            self._connect_coro = loop.create_connection
            self._connect_args = (host, X11_BASE_PORT + int(dpynum))

        self._remote_auth: Dict['SSHChannel', bytes] = {}
        self._channel: Dict[bytes, Tuple['SSHChannel', bool]] = {}

    def attach(self, display: str, chan: 'SSHChannel',
               single_connection: bool) -> Tuple[bytes, bytes, int]:
        """Attach a channel to this listener"""

        host, dpynum, screen = _parse_display(display)

        if self._host != host or self._dpynum != dpynum:
            raise ValueError('Already forwarding to another X11 display')

        remote_auth = os.urandom(len(self._local_auth))

        self._remote_auth[chan] = remote_auth
        self._channel[remote_auth] = chan, single_connection

        return self._auth_proto, remote_auth, screen

    def detach(self, chan: 'SSHChannel') -> bool:
        """Detach a channel from this listener"""

        try:
            remote_auth = self._remote_auth.pop(chan)
            del self._channel[remote_auth]
        except KeyError:
            pass

        return not bool(self._remote_auth)

    async def forward_connection(self) -> SSHX11ClientForwarder:
        """Forward an incoming connection to the local X server"""

        peer: SSHForwarder

        try:
            _, peer = await self._connect_coro(SSHForwarder,
                                               *self._connect_args)
        except OSError as exc:
            raise ChannelOpenError(OPEN_CONNECT_FAILED, str(exc)) from None

        return SSHX11ClientForwarder(self, peer)

    def validate_auth(self, remote_auth: bytes) -> bytes:
        """Validate client auth and enforce single connection flag"""

        chan, single_connection = self._channel[remote_auth]

        if single_connection:
            del self._channel[remote_auth]
            del self._remote_auth[chan]

        return self._local_auth


class SSHX11ServerListener:
    """Server listener used to forward X11 connections"""

    def __init__(self, tcp_listener: SSHListener, display: str):
        self._tcp_listener = tcp_listener
        self._display = display
        self._channels: Set[object] = set()

    def attach(self, chan: 'SSHChannel', screen: int) -> str:
        """Attach a channel to this listener and return its display"""

        self._channels.add(chan)

        return f'{self._display}.{screen}'

    def detach(self, chan: 'SSHChannel') -> bool:
        """Detach a channel from this listener"""

        try:
            self._channels.remove(chan)
        except KeyError:
            pass

        if not self._channels:
            self._tcp_listener.close()
            return True
        else:
            return False


def get_xauth_path(auth_path: Optional[str]) -> str:
    """Compute the path to the Xauthority file"""

    if not auth_path:
        auth_path = os.environ.get('XAUTHORITY')

    if not auth_path:
        auth_path = str(Path('~', '.Xauthority').expanduser())

    return auth_path


def walk_xauth(auth_path: str) -> Iterable[SSHXAuthorityEntry]:
    """Walk the entries in an Xauthority file"""

    def _read_bytes(n: int) -> bytes:
        """Read exactly n bytes"""

        data = auth_file.read(n)

        if len(data) != n:
            raise EOFError

        return data

    def _read_uint16() -> int:
        """Read a 16-bit unsigned integer"""

        return int.from_bytes(_read_bytes(2), 'big')

    def _read_string() -> bytes:
        """Read a string"""

        return _read_bytes(_read_uint16())

    try:
        with open(auth_path, 'rb') as auth_file:
            while True:
                try:
                    family = _read_uint16()
                except EOFError:
                    break

                try:
                    yield SSHXAuthorityEntry(family, _read_string(),
                                             _read_string(), _read_string(),
                                             _read_string())
                except EOFError:
                    raise ValueError('Incomplete Xauthority entry') from None
    except OSError:
        pass


async def lookup_xauth(loop: asyncio.AbstractEventLoop,
                       auth_path: Optional[str], host: str,
                       dpynum: str) -> Tuple[bytes, bytes]:
    """Look up Xauthority data for the specified display"""

    auth_path = get_xauth_path(auth_path)

    if host.startswith('/') or host in ('', 'unix', 'localhost'):
        host = socket.gethostname()

    dpynum = dpynum.encode('ascii')

    ipv4_addrs: Sequence[str] = []
    ipv6_addrs: Sequence[str] = []

    for entry in walk_xauth(auth_path):
        if entry.dpynum and entry.dpynum != dpynum:
            continue

        if entry.family == XAUTH_FAMILY_IPV4:
            if not ipv4_addrs:
                ipv4_addrs = await _lookup_host(loop, host, socket.AF_INET)

            addr = socket.inet_ntop(socket.AF_INET, entry.addr)
            match = addr in ipv4_addrs
        elif entry.family == XAUTH_FAMILY_IPV6:
            if not ipv6_addrs:
                ipv6_addrs = await _lookup_host(loop, host, socket.AF_INET6)

            addr = socket.inet_ntop(socket.AF_INET6, entry.addr)
            match = addr in ipv6_addrs
        elif entry.family == XAUTH_FAMILY_HOSTNAME:
            match = entry.addr == host.encode('idna')
        elif entry.family == XAUTH_FAMILY_WILD:
            match = True
        else:
            match = False

        if match:
            return entry.proto, entry.data

    logger.debug1('No xauth entry found for display: using random auth')
    return XAUTH_PROTO_COOKIE, os.urandom(XAUTH_COOKIE_LEN)


async def update_xauth(auth_path: Optional[str], host: str, dpynum: str,
                       auth_proto: bytes, auth_data: bytes) -> None:
    """Update Xauthority data for the specified display"""

    if host.startswith('/') or host in ('', 'unix', 'localhost'):
        host = socket.gethostname()

    host = host.encode('idna')
    dpynum = str(dpynum).encode('ascii')

    auth_path = get_xauth_path(auth_path)
    new_auth_path = auth_path + XAUTH_LOCK_SUFFIX
    new_file = None

    try:
        if time.time() - os.stat(new_auth_path).st_ctime > XAUTH_LOCK_DEAD:
            os.unlink(new_auth_path)
    except FileNotFoundError:
        pass

    for _ in range(XAUTH_LOCK_TRIES):
        try:
            new_file = open(new_auth_path, 'xb')
        except FileExistsError:
            await asyncio.sleep(XAUTH_LOCK_DELAY)
        else:
            break

    if not new_file:
        raise ValueError('Unable to acquire Xauthority lock')

    new_entry = SSHXAuthorityEntry(XAUTH_FAMILY_HOSTNAME, host,
                                   dpynum, auth_proto, auth_data)

    new_file.write(bytes(new_entry))

    for entry in walk_xauth(auth_path):
        if (entry.family != new_entry.family or entry.addr != new_entry.addr or
                entry.dpynum != new_entry.dpynum):
            new_file.write(bytes(entry))

    new_file.close()

    os.replace(new_auth_path, auth_path)


async def create_x11_client_listener(loop: asyncio.AbstractEventLoop,
                                     display: str,
                                     auth_path: Optional[str]) -> \
        SSHX11ClientListener:
    """Create a listener to accept X11 connections forwarded over SSH"""

    host, dpynum, _ = _parse_display(display)

    auth_proto, auth_data = await lookup_xauth(loop, auth_path, host, dpynum)

    return SSHX11ClientListener(loop, host, dpynum, auth_proto, auth_data)


async def create_x11_server_listener(conn: 'SSHServerConnection',
                                     loop: asyncio.AbstractEventLoop,
                                     auth_path: Optional[str],
                                     auth_proto: bytes, auth_data: bytes) -> \
        Optional[SSHX11ServerListener]:
    """Create a listener to forward X11 connections over SSH"""

    for dpynum in range(X11_DISPLAY_START, X11_MAX_DISPLAYS):
        try:
            tcp_listener = await create_tcp_forward_listener(
                conn, loop, conn.create_x11_connection,
                X11_LISTEN_HOST, X11_BASE_PORT + dpynum)
        except OSError:
            continue

        display = f'{X11_LISTEN_HOST}:{dpynum}'

        try:
            await update_xauth(auth_path, X11_LISTEN_HOST, str(dpynum),
                               auth_proto, auth_data)
        except ValueError:
            tcp_listener.close()
            break

        return SSHX11ServerListener(tcp_listener, display)

    return None
