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

"""SSH stream handlers"""

import asyncio
import inspect
import re
from typing import TYPE_CHECKING, Any, AnyStr, AsyncIterator
from typing import Callable, Dict, Generic, Iterable, List
from typing import Optional, Pattern, Set, Tuple, Union, cast

from .constants import EXTENDED_DATA_STDERR
from .logging import SSHLogger
from .misc import MaybeAwait, BreakReceived, SignalReceived
from .misc import SoftEOFReceived, TerminalSizeChanged
from .session import DataType, SSHClientSession, SSHServerSession
from .session import SSHTCPSession, SSHUNIXSession, SSHTunTapSession
from .sftp import SFTPServer, run_sftp_server
from .scp import run_scp_server


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .channel import SSHChannel
    from .connection import SSHConnection


if TYPE_CHECKING:
    _WaiterFuture = asyncio.Future[None]
else:
    _WaiterFuture = asyncio.Future

_RecvBuf = List[Union[AnyStr, Exception]]
_RecvBufMap = Dict[DataType, _RecvBuf[AnyStr]]
_ReadLocks = Dict[DataType, asyncio.Lock]
_ReadWaiters = Dict[DataType, Optional[_WaiterFuture]]
_DrainWaiters = Dict[DataType, Set[_WaiterFuture]]

SSHSocketSessionFactory = Callable[['SSHReader', 'SSHWriter'],
                                    MaybeAwait[None]]
_OptSocketSessionFactory = Optional[SSHSocketSessionFactory]

SSHServerSessionFactory = Callable[['SSHReader', 'SSHWriter',
                                    'SSHWriter'], MaybeAwait[None]]
_OptServerSessionFactory = Optional[SSHServerSessionFactory]

SFTPServerFactory = Callable[['SSHChannel[bytes]'], SFTPServer]
_OptSFTPServerFactory = Optional[SFTPServerFactory]


_NEWLINE = object()


class SSHReader(Generic[AnyStr]):
    """SSH read stream handler"""

    def __init__(self, session: 'SSHStreamSession[AnyStr]',
                 chan: 'SSHChannel[AnyStr]', datatype: DataType = None):
        self._session: 'SSHStreamSession[AnyStr]' = session
        self._chan: 'SSHChannel[AnyStr]' = chan
        self._datatype = datatype

    async def __aiter__(self) -> AsyncIterator[AnyStr]:
        """Allow SSHReader to be an async iterator"""

        async for result in self._session.aiter(self._datatype):
            yield result

    @property
    def channel(self) -> 'SSHChannel[AnyStr]':
        """The SSH channel associated with this stream"""

        return self._chan

    @property
    def logger(self) -> SSHLogger:
        """The SSH logger associated with this stream"""

        return self._chan.logger

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        """Return additional information about this stream

           This method returns extra information about the channel
           associated with this stream. See :meth:`get_extra_info()
           <SSHClientChannel.get_extra_info>` on :class:`SSHClientChannel`
           for additional information.

        """

        return self._chan.get_extra_info(name, default)

    def feed_data(self, data: AnyStr) -> None:
        """Feed data to the associated session

           This method feeds data to the SSH session associated with
           this stream, providing compatibility with the
           :meth:`feed_data() <asyncio.StreamReader.feed_data>` method
           on :class:`asyncio.StreamReader`. This is mostly useful
           for testing.

        """

        self._session.data_received(data, self._datatype)

    def feed_eof(self) -> None:
        """Feed EOF to the associated session

           This method feeds an end-of-file indication to the SSH session
           associated with this stream, providing compatibility with the
           :meth:`feed_eof() <asyncio.StreamReader.feed_data>` method
           on :class:`asyncio.StreamReader`. This is mostly useful
           for testing.

        """

        self._session.eof_received()

    async def read(self, n: int = -1) -> AnyStr:
        """Read data from the stream

           This method is a coroutine which reads up to `n` bytes
           or characters from the stream. If `n` is not provided or
           set to `-1`, it reads until EOF or a signal is received.

           If EOF is received and the receive buffer is empty, an
           empty `bytes` or `str` object is returned.

           If the next data in the stream is a signal, the signal is
           delivered as a raised exception.

           .. note:: Unlike traditional `asyncio` stream readers,
                     the data will be delivered as either `bytes` or
                     a `str` depending on whether an encoding was
                     specified when the underlying channel was opened.

        """

        return await self._session.read(self._datatype, n, exact=False)

    async def readline(self) -> AnyStr:
        """Read one line from the stream

           This method is a coroutine which reads one line, ending in
           `'\\n'`.

           If EOF is received before `'\\n'` is found, the partial
           line is returned. If EOF is received and the receive buffer
           is empty, an empty `bytes` or `str` object is returned.

           If the next data in the stream is a signal, the signal is
           delivered as a raised exception.

           .. note:: In Python 3.5 and later, :class:`SSHReader` objects
                     can also be used as async iterators, returning input
                     data one line at a time.

        """

        return await self._session.readline(self._datatype)

    async def readuntil(self, separator: object,
                        max_separator_len = 0) -> AnyStr:
        """Read data from the stream until `separator` is seen

           This method is a coroutine which reads from the stream until
           the requested separator is seen. If a match is found, the
           returned data will include the separator at the end.

           The `separator` argument can be a single `bytes` or `str`
           value, a sequence of multiple `bytes` or `str` values,
           or a compiled regex (`re.Pattern`) to match against,
           returning data as soon as a matching separator is found
           in the stream.

           When passing a regex pattern as the separator, the
           `max_separator_len` argument should be set to the
           maximum length of an expected separator match. This
           can greatly improve performance, by minimizing how far
           back into the stream must be searched for a match.
           When passing literal separators to match against, the
           max separator length will be set automatically.

           .. note:: For best results, a separator regex should
                     both begin and end with data which is as
                     unique as possible, and should not start or
                     end with optional or repeated elements.
                     Otherwise, you run the risk of failing to
                     match parts of a separator when it is split
                     across multiple reads.

           If EOF or a signal is received before a match occurs, an
           :exc:`IncompleteReadError <asyncio.IncompleteReadError>`
           is raised and its `partial` attribute will contain the
           data in the stream prior to the EOF or signal.

           If the next data in the stream is a signal, the signal is
           delivered as a raised exception.

        """

        return await self._session.readuntil(separator, self._datatype,
                                             max_separator_len)

    async def readexactly(self, n: int) -> AnyStr:
        """Read an exact amount of data from the stream

           This method is a coroutine which reads exactly n bytes or
           characters from the stream.

           If EOF or a signal is received in the stream before `n`
           bytes are read, an :exc:`IncompleteReadError
           <asyncio.IncompleteReadError>` is raised and its `partial`
           attribute will contain the data before the EOF or signal.

           If the next data in the stream is a signal, the signal is
           delivered as a raised exception.

        """

        return await self._session.read(self._datatype, n, exact=True)

    def at_eof(self) -> bool:
        """Return whether the stream is at EOF

           This method returns `True` when EOF has been received and
           all data in the stream has been read.

        """

        return self._session.at_eof(self._datatype)

    def get_redirect_info(self) -> Tuple['SSHStreamSession[AnyStr]', DataType]:
        """Get information needed to redirect from this SSHReader"""

        return self._session, self._datatype


class SSHWriter(Generic[AnyStr]):
    """SSH write stream handler"""

    def __init__(self, session: 'SSHStreamSession[AnyStr]',
                 chan: 'SSHChannel[AnyStr]', datatype: DataType = None):
        self._session: 'SSHStreamSession[AnyStr]' = session
        self._chan: 'SSHChannel[AnyStr]' = chan
        self._datatype = datatype

    @property
    def channel(self) -> 'SSHChannel[AnyStr]':
        """The SSH channel associated with this stream"""

        return self._chan

    @property
    def logger(self) -> SSHLogger:
        """The SSH logger associated with this stream"""

        return self._chan.logger

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        """Return additional information about this stream

           This method returns extra information about the channel
           associated with this stream. See :meth:`get_extra_info()
           <SSHClientChannel.get_extra_info>` on :class:`SSHClientChannel`
           for additional information.

        """

        return self._chan.get_extra_info(name, default)

    def can_write_eof(self) -> bool:
        """Return whether the stream supports :meth:`write_eof`"""

        return self._chan.can_write_eof()

    def close(self) -> None:
        """Close the channel

           .. note:: After this is called, no data can be read or written
                     from any of the streams associated with this channel.

        """

        return self._chan.close()

    def is_closing(self) -> bool:
        """Return if the stream is closing or is closed"""

        return self._chan.is_closing()

    async def wait_closed(self) -> None:
        """Wait until the stream is closed

           This should be called after :meth:`close` to wait until
           the underlying connection is closed.

        """

        await self._chan.wait_closed()

    async def drain(self) -> None:
        """Wait until the write buffer on the channel is flushed

           This method is a coroutine which blocks the caller if the
           stream is currently paused for writing, returning when
           enough data has been sent on the channel to allow writing
           to resume. This can be used to avoid buffering an excessive
           amount of data in the channel's send buffer.

        """

        await self._session.drain(self._datatype)

    def write(self, data: AnyStr) -> None:
        """Write data to the stream

           This method writes bytes or characters to the stream.

           .. note:: Unlike traditional `asyncio` stream writers,
                     the data must be supplied as either `bytes` or
                     a `str` depending on whether an encoding was
                     specified when the underlying channel was opened.

        """

        return self._chan.write(data, self._datatype)

    def writelines(self, list_of_data: Iterable[AnyStr]) -> None:
        """Write a collection of data to the stream"""

        return self._chan.writelines(list_of_data, self._datatype)

    def write_eof(self) -> None:
        """Write EOF on the channel

           This method sends an end-of-file indication on the channel,
           after which no more data can be written.

           .. note:: On an :class:`SSHServerChannel` where multiple
                     output streams are created, writing EOF on one
                     stream signals EOF for all of them, since it
                     applies to the channel as a whole.

        """

        return self._chan.write_eof()

    def get_redirect_info(self) -> Tuple['SSHStreamSession[AnyStr]', DataType]:
        """Get information needed to redirect to this SSHWriter"""

        return self._session, self._datatype


class SSHStreamSession(Generic[AnyStr]):
    """SSH stream session handler"""

    def __init__(self) -> None:
        self._chan: Optional['SSHChannel[AnyStr]'] = None
        self._conn: Optional['SSHConnection'] = None
        self._encoding: Optional[str] = None
        self._errors = 'strict'
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._limit = 0
        self._exception: Optional[Exception] = None
        self._eof_received = False
        self._connection_lost = False
        self._read_paused = False
        self._write_paused = False
        self._recv_buf_len = 0
        self._recv_buf: _RecvBufMap[AnyStr] = {None: []}
        self._read_locks: _ReadLocks = {None: asyncio.Lock()}
        self._read_waiters: _ReadWaiters = {None: None}
        self._drain_waiters: _DrainWaiters = {None: set()}

    async def aiter(self, datatype: DataType) -> AsyncIterator[AnyStr]:
        """Allow SSHReader to be an async iterator"""

        while not self.at_eof(datatype):
            yield await self.readline(datatype)

    async def _block_read(self, datatype: DataType) -> None:
        """Wait for more data to arrive on the stream"""

        try:
            assert self._loop is not None
            waiter: _WaiterFuture = self._loop.create_future()
            self._read_waiters[datatype] = waiter
            await waiter
        finally:
            self._read_waiters[datatype] = None

    def _unblock_read(self, datatype: DataType) -> None:
        """Signal that more data has arrived on the stream"""

        waiter = self._read_waiters[datatype]
        if waiter and not waiter.done():
            waiter.set_result(None)

    def _should_block_drain(self, datatype: DataType) -> bool:
        """Return whether output is still being written to the channel"""

        # pylint: disable=unused-argument

        return self._write_paused and not self._connection_lost

    def _unblock_drain(self, datatype: DataType) -> None:
        """Signal that more data can be written on the stream"""

        if not self._should_block_drain(datatype):
            for waiter in self._drain_waiters[datatype]:
                if not waiter.done(): # pragma: no branch
                    waiter.set_result(None)

    def _should_pause_reading(self) -> bool:
        """Return whether to pause reading from the channel"""

        return bool(self._limit) and self._recv_buf_len >= self._limit

    def _maybe_pause_reading(self) -> bool:
        """Pause reading if necessary"""

        if not self._read_paused and self._should_pause_reading():
            assert self._chan is not None
            self._read_paused = True
            self._chan.pause_reading()
            return True
        else:
            return False

    def _maybe_resume_reading(self) -> bool:
        """Resume reading if necessary"""

        if self._read_paused and not self._should_pause_reading():
            assert self._chan is not None
            self._read_paused = False
            self._chan.resume_reading()
            return True
        else:
            return False

    def connection_made(self, chan: 'SSHChannel[AnyStr]') -> None:
        """Handle a newly opened channel"""

        self._chan = chan
        self._conn = chan.get_connection()
        self._encoding, self._errors = chan.get_encoding()
        self._loop = chan.get_loop()
        self._limit = self._chan.get_recv_window()

        for datatype in chan.get_read_datatypes():
            self._recv_buf[datatype] = []
            self._read_locks[datatype] = asyncio.Lock()
            self._read_waiters[datatype] = None

        for datatype in chan.get_write_datatypes():
            self._drain_waiters[datatype] = set()

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle an incoming channel close"""

        self._connection_lost = True
        self._exception = exc

        if not self._eof_received:
            if exc:
                for datatype in self._read_waiters:
                    self._recv_buf[datatype].append(exc)

            self.eof_received()

        for datatype in self._drain_waiters:
            self._unblock_drain(datatype)

    def data_received(self, data: AnyStr, datatype: DataType) -> None:
        """Handle incoming data on the channel"""

        self._recv_buf[datatype].append(data)
        self._recv_buf_len += len(data)
        self._unblock_read(datatype)
        self._maybe_pause_reading()

    def eof_received(self) -> bool:
        """Handle an incoming end of file on the channel"""

        self._eof_received = True

        for datatype in self._read_waiters:
            self._unblock_read(datatype)

        return True

    def at_eof(self, datatype: DataType) -> bool:
        """Return whether end of file has been received on the channel"""

        return self._eof_received and not self._recv_buf[datatype]

    def pause_writing(self) -> None:
        """Handle a request to pause writing on the channel"""

        self._write_paused = True

    def resume_writing(self) -> None:
        """Handle a request to resume writing on the channel"""

        self._write_paused = False

        for datatype in self._drain_waiters:
            self._unblock_drain(datatype)

    async def read(self, datatype: DataType, n: int, exact: bool) -> AnyStr:
        """Read data from the channel"""

        recv_buf = self._recv_buf[datatype]
        data: List[AnyStr] = []
        break_read = False

        async with self._read_locks[datatype]:
            while True:
                while recv_buf and n != 0:
                    if isinstance(recv_buf[0], Exception):
                        if data:
                            break_read = True
                            break
                        else:
                            exc = cast(Exception, recv_buf.pop(0))

                            if isinstance(exc, SoftEOFReceived):
                                n = 0
                                break
                            else:
                                raise exc

                    l = len(recv_buf[0])

                    if l > n > 0:
                        data.append(recv_buf[0][:n])
                        recv_buf[0] = recv_buf[0][n:]
                        self._recv_buf_len -= n
                        n = 0
                        break

                    data.append(cast(AnyStr, recv_buf.pop(0)))
                    self._recv_buf_len -= l
                    n -= l

                if self._maybe_resume_reading():
                    continue

                if n == 0 or (n > 0 and data and not exact) or \
                        (n < 0 and recv_buf) or \
                        self._eof_received or break_read:
                    break

                await self._block_read(datatype)

        result = cast(AnyStr, '' if self._encoding else b'').join(data)

        if n > 0 and exact:
            raise asyncio.IncompleteReadError(cast(bytes, result),
                                              len(result) + n)

        return result

    async def readline(self, datatype: DataType) -> AnyStr:
        """Read one line from the stream"""

        try:
            return await self.readuntil(_NEWLINE, datatype)
        except asyncio.IncompleteReadError as exc:
            return cast(AnyStr, exc.partial)

    async def readuntil(self, separator: object, datatype: DataType,
                        max_separator_len = 0) -> AnyStr:
        """Read data from the channel until a separator is seen"""

        if not separator:
            raise ValueError('Separator cannot be empty')

        buf = cast(AnyStr, '' if self._encoding else b'')
        recv_buf = self._recv_buf[datatype]

        if separator is _NEWLINE:
            seplen = 1
            separators = cast(AnyStr, '\n' if self._encoding else b'\n')
            pat = re.compile(separators)
        elif isinstance(separator, (bytes, str)):
            seplen = len(separator)
            pat = re.compile(re.escape(cast(AnyStr, separator)))
        elif isinstance(separator, Pattern):
            seplen = max_separator_len
            pat = cast(Pattern[AnyStr], separator)
        else:
            bar = cast(AnyStr, '|' if self._encoding else b'|')
            seplist = list(cast(Iterable[AnyStr], separator))
            seplen = max(len(sep) for sep in seplist)
            separators = bar.join(re.escape(sep) for sep in seplist)
            pat = re.compile(separators)

        curbuf = 0
        buflen = 0

        async with self._read_locks[datatype]:
            while True:
                while curbuf < len(recv_buf):
                    if isinstance(recv_buf[curbuf], Exception):
                        if buf:
                            recv_buf[:curbuf] = []
                            self._recv_buf_len -= buflen
                            raise asyncio.IncompleteReadError(
                                cast(bytes, buf), None)
                        else:
                            exc = recv_buf.pop(0)

                            if isinstance(exc, SoftEOFReceived):
                                return buf
                            else:
                                raise cast(Exception, exc)

                    newbuf = cast(AnyStr, recv_buf[curbuf])
                    buf += newbuf
                    start = 0 if seplen == 0 else max(buflen + 1 - seplen, 0)

                    match = pat.search(buf, start)
                    if match:
                        idx = match.end()
                        recv_buf[:curbuf] = []
                        recv_buf[0] = buf[idx:]
                        buf = buf[:idx]
                        self._recv_buf_len -= idx

                        if not recv_buf[0]:
                            recv_buf.pop(0)

                        self._maybe_resume_reading()
                        return buf

                    buflen += len(newbuf)
                    curbuf += 1

                if self._read_paused or self._eof_received:
                    recv_buf[:curbuf] = []
                    self._recv_buf_len -= buflen
                    self._maybe_resume_reading()
                    raise asyncio.IncompleteReadError(cast(bytes, buf), None)

                await self._block_read(datatype)

    async def drain(self, datatype: DataType) -> None:
        """Wait for data written to the channel to drain"""

        while self._should_block_drain(datatype):
            try:
                assert self._loop is not None
                waiter: _WaiterFuture = self._loop.create_future()
                self._drain_waiters[datatype].add(waiter)
                await waiter
            finally:
                self._drain_waiters[datatype].remove(waiter)

        if self._connection_lost:
            exc = self._exception

            if not exc and self._write_paused:
                exc = BrokenPipeError()

            if exc:
                raise exc


class SSHClientStreamSession(SSHStreamSession[AnyStr],
                             SSHClientSession[AnyStr]):
    """SSH client stream session handler"""


class SSHServerStreamSession(SSHStreamSession[AnyStr],
                             SSHServerSession[AnyStr]):
    """SSH server stream session handler"""

    def __init__(self, session_factory: _OptServerSessionFactory,
                 sftp_factory: _OptSFTPServerFactory = None,
                 sftp_version = 0, allow_scp = False):
        super().__init__()

        self._session_factory = session_factory
        self._sftp_factory = sftp_factory
        self._sftp_version = sftp_version
        self._allow_scp = allow_scp and bool(sftp_factory)

    def _init_sftp_server(self) -> SFTPServer:
        """Initialize an SFTP server for this stream to use"""

        assert self._chan is not None

        self._chan.set_encoding(None)
        self._encoding = None

        assert self._sftp_factory is not None
        return self._sftp_factory(cast('SSHChannel[bytes]', self._chan))

    def shell_requested(self) -> bool:
        """Return whether a shell can be requested"""

        return bool(self._session_factory)

    def exec_requested(self, command: str) -> bool:
        """Return whether execution of a command can be requested"""

        # Avoid incorrect pylint suggestion to use ternary
        # pylint: disable=consider-using-ternary

        return ((self._allow_scp and command.startswith('scp ')) or
                bool(self._session_factory))

    def subsystem_requested(self, subsystem: str) -> bool:
        """Return whether starting a subsystem can be requested"""

        if subsystem == 'sftp':
            return bool(self._sftp_factory)
        else:
            return bool(self._session_factory)

    def session_started(self) -> None:
        """Start a session for this newly opened server channel"""

        assert self._chan is not None

        command = self._chan.get_command()

        stdin = SSHReader[AnyStr](self, self._chan)
        stdout = SSHWriter[AnyStr](self, self._chan)
        stderr = SSHWriter[AnyStr](self, self._chan, EXTENDED_DATA_STDERR)

        handler: MaybeAwait[None]

        if self._chan.get_subsystem() == 'sftp':
            stdin_bytes = cast(SSHReader[bytes], stdin)
            stdout_bytes = cast(SSHWriter[bytes], stdout)

            handler = run_sftp_server(self._init_sftp_server(),
                                      stdin_bytes, stdout_bytes,
                                      self._sftp_version)
        elif self._allow_scp and command and command.startswith('scp '):
            stdin_bytes = cast(SSHReader[bytes], stdin)
            stdout_bytes = cast(SSHWriter[bytes], stdout)
            stderr_bytes = cast(SSHWriter[bytes], stderr)

            handler = run_scp_server(self._init_sftp_server(), command,
                                     stdin_bytes, stdout_bytes, stderr_bytes)
        else:
            assert self._session_factory is not None
            handler = self._session_factory(stdin, stdout, stderr)

        if inspect.isawaitable(handler):
            assert self._conn is not None
            assert handler is not None
            self._conn.create_task(handler, stdin.logger)

    def exception_received(self, exc: Exception) -> None:
        """Handle an incoming exception on the channel"""

        self._recv_buf[None].append(exc)
        self._unblock_read(None)

    def break_received(self, msec: int) -> bool:
        """Handle an incoming break on the channel"""

        self.exception_received(BreakReceived(msec))
        return True

    def signal_received(self, signal: str) -> None:
        """Handle an incoming signal on the channel"""

        self.exception_received(SignalReceived(signal))

    def soft_eof_received(self) -> None:
        """Handle an incoming soft EOF on the channel"""

        self.exception_received(SoftEOFReceived())

    def terminal_size_changed(self, width: int, height: int,
                              pixwidth: int, pixheight: int) -> None:
        """Handle an incoming terminal size change on the channel"""

        self.exception_received(TerminalSizeChanged(width, height,
                                                    pixwidth, pixheight))


class SSHSocketStreamSession(SSHStreamSession[AnyStr]):
    """Socket stream session handler"""

    def __init__(self, session_factory: _OptSocketSessionFactory = None):
        super().__init__()

        self._session_factory = session_factory

    def session_started(self) -> None:
        """Start a session for this newly opened socket channel"""

        if self._session_factory:
            assert self._chan is not None
            reader = SSHReader[AnyStr](self, self._chan)
            writer = SSHWriter[AnyStr](self, self._chan)

            handler = self._session_factory(reader, writer)

            if inspect.isawaitable(handler):
                assert self._conn is not None
                assert handler is not None
                self._conn.create_task(handler, reader.logger)


class SSHTCPStreamSession(SSHSocketStreamSession[AnyStr],
                          SSHTCPSession[AnyStr]):
    """TCP stream session handler"""


class SSHUNIXStreamSession(SSHSocketStreamSession[AnyStr],
                           SSHUNIXSession[AnyStr]):
    """UNIX stream session handler"""

class SSHTunTapStreamSession(SSHSocketStreamSession[bytes], SSHTunTapSession):
    """TUN/TAP stream session handler"""

    async def aiter(self, datatype: DataType) -> AsyncIterator[bytes]:
        """Allow SSHReader to be an async iterator"""

        while True:
            packet = await self.read(datatype)

            if packet:
                yield packet
            else:
                break

    async def read(self, datatype: DataType, n: int = -1,
                   exact: bool = False) -> bytes:
        """Override read to preserve TUN/TAP packet boundaries"""

        recv_buf = self._recv_buf[datatype]

        while not self._eof_received:
            if recv_buf:
                data = cast(bytes, recv_buf.pop(0))
                self._recv_buf_len -= len(data)
                self._maybe_resume_reading()
                return data
            else:
                await self._block_read(datatype)

        return b''
