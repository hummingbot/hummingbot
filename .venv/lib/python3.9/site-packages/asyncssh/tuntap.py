# Copyright (c) 2024 by Ron Frederick <ronf@timeheart.net> and others.
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

"""SSH TUN/TAP forwarding support"""

import asyncio
import errno
import os
import socket
import struct
import sys
import threading

from typing import Callable, Optional, Tuple, cast

if sys.platform != 'win32': # pragma: no branch
    import fcntl


SSH_TUN_MODE_POINTTOPOINT = 1   # layer 3 IP packets
SSH_TUN_MODE_ETHERNET = 2       # layer 2 Ethenet frames

SSH_TUN_UNIT_ANY = 0x7fffffff   # The server may choose the unit

SSH_TUN_AF_INET = 2             # IPv4
SSH_TUN_AF_INET6 = 24           # IPv6

DARWIN_CTLIOCGINFO = 0xc0644e03
DARWIN_CTLIOCGINFO_FMT = 'I96s'

DARWIN_SIOCGIFFLAGS = 0xc0206911
DARWIN_SIOCSIFFLAGS = 0x80206910

LINUX_TUNSETIFF = 0x400454ca
LINUX_IFF_TUN = 0x1
LINUX_IFF_TAP = 0x2
LINUX_IFF_NO_PI = 0x1000

IFF_FMT = '16sH'
IFF_UP = 0x1


class SSHTunTapTransport(asyncio.Transport):
    """Layer 2/3 tunnel transport"""

    def __init__(self, loop: asyncio.AbstractEventLoop, interface: str):
        super().__init__(extra={'interface': interface})

        self._loop = loop
        self._protocol: Optional[asyncio.Protocol] = None

    def get_protocol(self) -> asyncio.BaseProtocol: # pragma: no cover
        """Get protocol object associated with transport"""

        assert self._protocol is not None

        return self._protocol

    def set_protocol(self, protocol: asyncio.BaseProtocol) -> None:
        """Set protocol associated with transport"""

        self._protocol = cast(asyncio.Protocol, protocol)

    def abort(self) -> None: # pragma: no cover
        """Abort this transport"""

        self.close()

    def is_reading(self) -> bool:
        """Return if the transport is reading data"""

        raise NotImplementedError

    def pause_reading(self) -> None:
        """Pause reading"""

        raise NotImplementedError

    def resume_reading(self) -> None:
        """Resume reading"""

        raise NotImplementedError

    def can_write_eof(self) -> bool: # pragma: no cover
        """This transport doesn't support writing EOF"""

        return False

    def get_write_buffer_size(self) -> int: # pragma: no cover
        """This transport has no output buffer"""

        return 0

    def get_write_buffer_limits(self) -> Tuple[int, int]: # pragma: no cover
        """This transport doesn't support write buffer limits"""

        return 0, 0

    def set_write_buffer_limits(self, high: Optional[int] = None,
                                low: Optional[int] = None) -> None:
        """This transport doesn't support write buffer limits"""

    def write_eof(self) -> None:
        """Ignore writing EOF on this transport"""

    def write(self, data: bytes) -> None:
        """Write a packet"""

        raise NotImplementedError

    def is_closing(self) -> bool: # pragma: no cover
        """Return if the transport is closing"""

        return False

    def close(self) -> None:
        """Close this transport"""

        raise NotImplementedError


class SSHTunTapOSXTransport(SSHTunTapTransport):
    """TunTapOSX transport"""

    def __init__(self, loop: asyncio.AbstractEventLoop, mode: int,
                 unit: Optional[int]):
        prefix = 'tun' if mode == SSH_TUN_MODE_POINTTOPOINT else 'tap'

        if unit is None:
            for i in range(16):
                try:
                    file = open(f'/dev/{prefix}{i}', 'rb+', buffering=0)
                except OSError:
                    pass
                else:
                    unit = i
                    break
            else:
                raise OSError(errno.EBUSY, f'No {prefix} devices available')
        else:
            file = open(f'/dev/{prefix}{unit}', 'rb+', buffering=0)

        interface = f'{prefix}{unit}'
        name = interface.encode()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            ifr = struct.pack(IFF_FMT, name, 0)
            ifr = fcntl.ioctl(sock, DARWIN_SIOCGIFFLAGS, ifr)

            _, flags = struct.unpack(IFF_FMT, ifr)
            flags |= IFF_UP

            ifr = struct.pack(IFF_FMT, name, flags)
            fcntl.ioctl(sock, DARWIN_SIOCSIFFLAGS, ifr)
        finally:
            sock.close()

        super().__init__(loop, interface)

        self._file = file
        self._read_thread: Optional[threading.Thread] = None
        os.set_blocking(file.fileno(), True)

    def is_reading(self) -> bool:
        """Return if the transport is reading data"""

        return self._read_thread is not None # pragma: no cover

    def pause_reading(self) -> None:
        """Pause reading"""

        if self._read_thread: # pragma: no branch
            self._read_thread.join()
            self._read_thread = None

    def resume_reading(self) -> None:
        """Resume reading"""

        if not self._read_thread: # pragma: no branch
            self._read_thread = threading.Thread(target=self._read_loop)
            self._read_thread.daemon = True
            self._read_thread.start()

    def _read_loop(self) -> None:
        """Loop reading packets until read is paused or done"""

        assert self._protocol is not None

        while True:
            try:
                data = self._file.read(65536)
            except OSError as exc:
                if exc.errno != errno.EBADF: # pragma: no cover
                    self._loop.call_soon_threadsafe(
                        self._protocol.connection_lost, exc)

                break
            else:
                self._loop.call_soon_threadsafe(
                    self._protocol.data_received, data)

    def write(self, data: bytes) -> None:
        """Write a packet"""

        self._file.write(data)

    def close(self) -> None:
        """Close this transport"""

        self._file.close()
        self.pause_reading()


class SSHDarwinUTunTransport(SSHTunTapTransport):
    """Darwin UTun transport"""

    def __init__(self, loop: asyncio.AbstractEventLoop, unit: Optional[int]):
        sock = socket.socket(socket.PF_SYSTEM, socket.SOCK_DGRAM,
                             socket.SYSPROTO_CONTROL)

        try:
            arg = struct.pack(DARWIN_CTLIOCGINFO_FMT, 0,
                              b'com.apple.net.utun_control')

            ctl_info = fcntl.ioctl(sock, DARWIN_CTLIOCGINFO, arg)
            ctl_id, _ = struct.unpack(DARWIN_CTLIOCGINFO_FMT, ctl_info)

            unit = 0 if unit is None else unit - 15

            sock.setblocking(False)
            sock.connect((ctl_id, unit))

            _, unit = sock.getpeername()
        except OSError:
            sock.close()
            raise

        unit: int

        super().__init__(loop, f'utun{unit-1}')

        self._sock = sock
        self._reading = False

    def is_reading(self) -> bool: # pragma: no cover
        """Return if the transport is reading data"""

        return self._reading

    def pause_reading(self) -> None:
        """Pause reading"""

        self._reading = False
        self._loop.remove_reader(self._sock)

    def resume_reading(self) -> None:
        """Resume reading"""

        self._reading = True
        self._loop.add_reader(self._sock, self._read_ready)

    def _read_ready(self) -> None:
        """Read available packets from the transport"""

        assert self._protocol is not None

        while True:
            try:
                data = self._sock.recv(65540)[4:]
            except (BlockingIOError, InterruptedError):
                break
            except OSError as exc: # pragma: no cover
                self._protocol.connection_lost(exc)
                break
            else:
                self._protocol.data_received(data)

    def write(self, data: bytes) -> None:
        """Write a packet"""

        version = data[0] >> 4
        family = socket.AF_INET if version == 4 else socket.AF_INET6
        data = family.to_bytes(4, 'big') + data

        self._sock.send(data)

    def close(self) -> None:
        """Close this transport"""

        self._sock.close()
        self.pause_reading()


class SSHLinuxTunTapTransport(SSHTunTapTransport):
    """Linux TUN/TAP transport"""

    def __init__(self, loop: asyncio.AbstractEventLoop, mode: int,
                 unit: Optional[int]):
        file = open('/dev/net/tun', 'rb+', buffering=0)

        if mode == SSH_TUN_MODE_POINTTOPOINT:
            flags = LINUX_IFF_TUN | LINUX_IFF_NO_PI
            prefix = 'tun'
        else:
            flags = LINUX_IFF_TAP | LINUX_IFF_NO_PI
            prefix = 'tap'

        name = b'' if unit is None else f'{prefix}{unit}'.encode()

        ifr = struct.pack(IFF_FMT, name, flags)

        try:
            ifr = fcntl.ioctl(file, LINUX_TUNSETIFF, ifr)
        except OSError:
            file.close()
            raise

        name, _ = struct.unpack(IFF_FMT, ifr)
        interface = name.strip(b'\0').decode()

        super().__init__(loop, interface)

        self._file = file
        self._reading = False
        os.set_blocking(file.fileno(), False)

    def is_reading(self) -> bool: # pragma: no cover
        """Return if the transport is reading data"""

        return self._reading

    def pause_reading(self) -> None:
        """Pause reading"""

        self._reading = False

        try:
            self._loop.remove_reader(self._file)
        except OSError: # pragma: no cover
            pass

    def resume_reading(self) -> None:
        """Resume reading"""

        self._reading = True
        self._loop.add_reader(self._file, self._read_ready)

    def _read_ready(self) -> None:
        """Read available packets from the transport"""

        assert self._protocol is not None

        while True:
            try:
                data = self._file.read(65536)
            except OSError as exc: # pragma: no cover
                self._protocol.connection_lost(exc)
                break
            else:
                if data is None:
                    break

                self._protocol.data_received(data)

    def write(self, data: bytes) -> None:
        """Write a packet"""

        self._file.write(data)

    def close(self) -> None:
        """Close this transport"""

        self._file.close()
        self.pause_reading()


def create_tuntap(protocol_factory: Callable[[], asyncio.BaseProtocol],
                  mode: int, unit: Optional[int]) -> \
        Tuple[SSHTunTapTransport, asyncio.BaseProtocol]:
    """Create a local TUN or TAP network interface"""

    loop = asyncio.get_event_loop()
    transport: Optional[SSHTunTapTransport] = None

    if sys.platform == 'darwin':
        if unit is None:
            try:
                transport = SSHTunTapOSXTransport(loop, mode, unit)
            except OSError:
                if mode == SSH_TUN_MODE_POINTTOPOINT:
                    transport = SSHDarwinUTunTransport(loop, unit)
                else:
                    raise
        elif mode == SSH_TUN_MODE_POINTTOPOINT and unit >= 16:
            transport = SSHDarwinUTunTransport(loop, unit)
        else:
            transport = SSHTunTapOSXTransport(loop, mode, unit)
    elif sys.platform == 'linux':
        transport = SSHLinuxTunTapTransport(loop, mode, unit)
    else:
        raise OSError(errno.EPROTONOSUPPORT,
                      f'TunTap not supported on {sys.platform}')

    assert transport is not None

    protocol = protocol_factory()
    protocol.connection_made(transport)

    transport.set_protocol(protocol)
    transport.resume_reading()

    return transport, protocol
