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

"""SSH packet encoding and decoding functions"""

from typing import Any, Awaitable, Callable, Iterable, Mapping, Optional
from typing import Sequence, Union

from .logging import SSHLogger
from .misc import MaybeAwait, plural


_LoggedPacket = Union[bytes, 'SSHPacket']
_PacketHandler = Callable[[Any, int, int, 'SSHPacket'], MaybeAwait[None]]


class PacketDecodeError(ValueError):
    """Packet decoding error"""


def Byte(value: int) -> bytes:
    """Encode a single byte"""

    return bytes((value,))


def Boolean(value: bool) -> bytes:
    """Encode a boolean value"""

    return Byte(bool(value))


def UInt16(value: int) -> bytes:
    """Encode a 16-bit integer value"""

    return value.to_bytes(2, 'big')


def UInt32(value: int) -> bytes:
    """Encode a 32-bit integer value"""

    return value.to_bytes(4, 'big')


def UInt64(value: int) -> bytes:
    """Encode a 64-bit integer value"""

    return value.to_bytes(8, 'big')


def String(value: Union[bytes, str]) -> bytes:
    """Encode a byte string or UTF-8 string value"""

    if isinstance(value, str):
        value = value.encode('utf-8', errors='strict')

    return len(value).to_bytes(4, 'big') + value


def MPInt(value: int) -> bytes:
    """Encode a multiple precision integer value"""

    l = value.bit_length()
    l += (l % 8 == 0 and value != 0 and value != -1 << (l - 1))
    l = (l + 7) // 8

    return l.to_bytes(4, 'big') + value.to_bytes(l, 'big', signed=True)


def NameList(value: Iterable[bytes]) -> bytes:
    """Encode a comma-separated list of byte strings"""

    return String(b','.join(value))


class SSHPacket:
    """Decoder class for SSH packets"""

    def __init__(self, packet: bytes):
        self._packet = packet
        self._idx = 0
        self._len = len(packet)

    def __bool__(self) -> bool:
        return self._idx != self._len

    def check_end(self) -> None:
        """Confirm that all of the data in the packet has been consumed"""

        if self:
            raise PacketDecodeError('Unexpected data at end of packet')

    def get_consumed_payload(self) -> bytes:
        """Return the portion of the packet consumed so far"""

        return self._packet[:self._idx]

    def get_remaining_payload(self) -> bytes:
        """Return the portion of the packet not yet consumed"""

        return self._packet[self._idx:]

    def get_full_payload(self) -> bytes:
        """Return the full packet"""

        return self._packet

    def get_bytes(self, size: int) -> bytes:
        """Extract the requested number of bytes from the packet"""

        if self._idx + size > self._len:
            raise PacketDecodeError('Incomplete packet')

        value = self._packet[self._idx:self._idx+size]
        self._idx += size
        return value

    def get_byte(self) -> int:
        """Extract a single byte from the packet"""

        return self.get_bytes(1)[0]

    def get_boolean(self) -> bool:
        """Extract a boolean from the packet"""

        return bool(self.get_byte())

    def get_uint16(self) -> int:
        """Extract a 16-bit integer from the packet"""

        return int.from_bytes(self.get_bytes(2), 'big')

    def get_uint32(self) -> int:
        """Extract a 32-bit integer from the packet"""

        return int.from_bytes(self.get_bytes(4), 'big')

    def get_uint64(self) -> int:
        """Extract a 64-bit integer from the packet"""

        return int.from_bytes(self.get_bytes(8), 'big')

    def get_string(self) -> bytes:
        """Extract a UTF-8 string from the packet"""

        return self.get_bytes(self.get_uint32())

    def get_mpint(self) -> int:
        """Extract a multiple precision integer from the packet"""

        return int.from_bytes(self.get_string(), 'big', signed=True)

    def get_namelist(self) -> Sequence[bytes]:
        """Extract a comma-separated list of byte strings from the packet"""

        namelist = self.get_string()
        return namelist.split(b',') if namelist else []


class SSHPacketLogger:
    """Parent class for SSH packet loggers"""

    _handler_names: Mapping[int, str] = {}

    @property
    def logger(self) -> SSHLogger:
        """The logger to use for packet logging"""

        raise NotImplementedError

    def _log_packet(self, msg: str, pkttype: int, pktid: Optional[int],
                    packet: _LoggedPacket, note: str) -> None:
        """Log a sent/received packet"""

        if isinstance(packet, SSHPacket):
            packet = packet.get_full_payload()

        try:
            name = f'{self._handler_names[pkttype]} ({pkttype})'
        except KeyError:
            name = f'packet type {pkttype}'

        count = plural(len(packet), 'byte')

        if note:
            note = f' ({note})'

        self.logger.packet(pktid, packet, '%s %s, %s%s',
                           msg, name, count, note)

    def log_sent_packet(self, pkttype: int, pktid: Optional[int],
                        packet: _LoggedPacket, note: str = '') -> None:
        """Log a sent packet"""

        self._log_packet('Sent', pkttype, pktid, packet, note)


    def log_received_packet(self, pkttype: int, pktid: Optional[int],
                            packet: _LoggedPacket, note: str = '') -> None:
        """Log a received packet"""

        self._log_packet('Received', pkttype, pktid, packet, note)


class SSHPacketHandler(SSHPacketLogger):
    """Parent class for SSH packet handlers"""

    _packet_handlers: Mapping[int, _PacketHandler] = {}

    @property
    def logger(self) -> SSHLogger:
        """The logger associated with this packet handler"""

        raise NotImplementedError

    def process_packet(self, pkttype: int, pktid: int,
                       packet: SSHPacket) -> Union[bool, Awaitable[None]]:
        """Log and process a received packet"""

        if pkttype in self._packet_handlers:
            return self._packet_handlers[pkttype](self, pkttype,
                                                  pktid, packet) or True
        else:
            return False
