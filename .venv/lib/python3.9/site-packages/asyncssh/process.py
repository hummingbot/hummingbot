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

"""SSH process handlers"""

import asyncio
from asyncio.subprocess import DEVNULL, PIPE, STDOUT
import codecs
import inspect
import io
import os
from pathlib import PurePath
import socket
import stat
from types import TracebackType
from typing import Any, AnyStr, Awaitable, Callable, Dict, Generic, IO
from typing import Iterable, List, Mapping, Optional, Set, TextIO
from typing import Tuple, Type, TypeVar, Union, cast
from typing_extensions import Protocol, Self

from .channel import SSHChannel, SSHClientChannel, SSHServerChannel

from .constants import DEFAULT_LANG, EXTENDED_DATA_STDERR

from .logging import SSHLogger

from .misc import BytesOrStr, Error, MaybeAwait, TermModes, TermSize
from .misc import ProtocolError, Record, open_file, set_terminal_size
from .misc import BreakReceived, SignalReceived, TerminalSizeChanged

from .session import DataType

from .stream import SSHReader, SSHWriter, SSHStreamSession
from .stream import SSHClientStreamSession, SSHServerStreamSession
from .stream import SFTPServerFactory

_AnyStrContra = TypeVar('_AnyStrContra', bytes, str, contravariant=True)

_File = Union[IO[bytes], '_AsyncFileProtocol[bytes]']

ProcessSource = Union[int, str, socket.socket, PurePath, SSHReader[bytes],
                      asyncio.StreamReader, _File]

ProcessTarget = Union[int, str, socket.socket, PurePath, SSHWriter[bytes],
                      asyncio.StreamWriter, _File]

SSHServerProcessFactory = Callable[['SSHServerProcess[AnyStr]'],
                                   MaybeAwait[None]]


_QUEUE_LOW_WATER = 8
_QUEUE_HIGH_WATER = 16


class _AsyncFileProtocol(Protocol[AnyStr]):
    """Protocol for an async file"""

    async def read(self, n: int = -1) -> AnyStr:
        """Read from an async file"""

    async def write(self, data: AnyStr) -> None:
        """Write to an async file"""

    async def close(self) -> None:
        """Close an async file"""


class _ReaderProtocol(Protocol):
    """A class that can be used as a reader in SSHProcess"""

    def pause_reading(self) -> None:
        """Pause reading"""

    def resume_reading(self) -> None:
        """Resume reading"""

    def close(self) -> None:
        """Stop forwarding data"""


class _WriterProtocol(Protocol[_AnyStrContra]):
    """A class that can be used as a writer in SSHProcess"""

    def write(self, data: _AnyStrContra) -> None:
        """Write data"""

    def write_exception(self, exc: Exception) -> None:
        """Write exception (break, signal, terminal size change)"""

        return # pragma: no cover

    def write_eof(self) -> None:
        """Close output when end of file is received"""

    def close(self) -> None:
        """Stop forwarding data"""


def _is_regular_file(file: IO[bytes]) -> bool:
    """Return if argument is a regular file or file-like object"""

    try:
        return stat.S_ISREG(os.fstat(file.fileno()).st_mode)
    except OSError:
        return True

class _UnicodeReader(_ReaderProtocol, Generic[AnyStr]):
    """Handle buffering partial Unicode data"""

    def __init__(self, encoding: Optional[str], errors: str,
                 textmode: bool = False):
        super().__init__()

        if encoding and not textmode:
            self._decoder: Optional[codecs.IncrementalDecoder] = \
                codecs.getincrementaldecoder(encoding)(errors)
        else:
            self._decoder = None

    def decode(self, data: bytes, final: bool = False) -> AnyStr:
        """Decode Unicode bytes when reading from binary sources"""

        if self._decoder:
            try:
                decoded_data = cast(AnyStr, self._decoder.decode(data, final))
            except UnicodeDecodeError as exc:
                raise ProtocolError(str(exc)) from None
        else:
            decoded_data = cast(AnyStr, data)

        return decoded_data

    def check_partial(self) -> None:
        """Check if there's partial Unicode data left at EOF"""

        self.decode(b'', True)

    def close(self) -> None:
        """Perform necessary cleanup on error (provided by derived classes)"""


class _UnicodeWriter(_WriterProtocol[AnyStr]):
    """Handle encoding Unicode data before writing it"""

    def __init__(self, encoding: Optional[str], errors: str,
                 textmode: bool = False):
        super().__init__()

        if encoding and not textmode:
            self._encoder: Optional[codecs.IncrementalEncoder] = \
                codecs.getincrementalencoder(encoding)(errors)
        else:
            self._encoder = None

    def encode(self, data: AnyStr) -> bytes:
        """Encode Unicode bytes when writing to binary targets"""

        if self._encoder:
            assert self._encoder is not None
            encoded_data = cast(bytes, self._encoder.encode(cast(str, data)))
        else:
            encoded_data = cast(bytes, data)

        return encoded_data


class _FileReader(_UnicodeReader[AnyStr]):
    """Forward data from a file"""

    def __init__(self, process: 'SSHProcess[AnyStr]', file: IO[bytes],
                 bufsize: int, datatype: DataType,
                 encoding: Optional[str], errors: str):
        super().__init__(encoding, errors, hasattr(file, 'encoding'))

        self._process: 'SSHProcess[AnyStr]' = process
        self._file = file
        self._bufsize = bufsize
        self._datatype = datatype
        self._paused = False

    def feed(self) -> None:
        """Feed file data"""

        while not self._paused:
            data = self._file.read(self._bufsize)

            if data:
                self._process.feed_data(self.decode(data), self._datatype)
            else:
                self.check_partial()
                self._process.feed_eof(self._datatype)
                break

    def pause_reading(self) -> None:
        """Pause reading from the file"""

        self._paused = True

    def resume_reading(self) -> None:
        """Resume reading from the file"""

        self._paused = False
        self.feed()

    def close(self) -> None:
        """Stop forwarding data from the file"""

        self._file.close()


class _AsyncFileReader(_UnicodeReader[AnyStr]):
    """Forward data from an aiofile"""

    def __init__(self, process: 'SSHProcess[AnyStr]',
                 file: _AsyncFileProtocol[bytes],
                 bufsize: int, datatype: DataType,
                 encoding: Optional[str], errors: str):
        super().__init__(encoding, errors, hasattr(file, 'encoding'))

        self._conn = process.channel.get_connection()
        self._process: 'SSHProcess[AnyStr]' = process
        self._file = file
        self._bufsize = bufsize
        self._datatype = datatype
        self._paused = False

    async def _feed(self) -> None:
        """Feed file data"""

        while not self._paused:
            data = await self._file.read(self._bufsize)

            if data:
                self._process.feed_data(self.decode(data), self._datatype)
            else:
                self.check_partial()
                self._process.feed_eof(self._datatype)
                break

    def feed(self) -> None:
        """Start feeding file data"""

        self._conn.create_task(self._feed())

    def pause_reading(self) -> None:
        """Pause reading from the file"""

        self._paused = True

    def resume_reading(self) -> None:
        """Resume reading from the file"""

        self._paused = False
        self.feed()

    def close(self) -> None:
        """Stop forwarding data from the file"""

        self._conn.create_task(self._file.close())


class _FileWriter(_UnicodeWriter[AnyStr]):
    """Forward data to a file"""

    def __init__(self, file: IO[bytes], needs_close: bool,
                 encoding: Optional[str], errors: str):
        super().__init__(encoding, errors, hasattr(file, 'encoding'))

        self._file = file
        self._needs_close = needs_close

    def write(self, data: AnyStr) -> None:
        """Write data to the file"""

        self._file.write(self.encode(data))

    def write_eof(self) -> None:
        """Close output file when end of file is received"""

        self.close()

    def close(self) -> None:
        """Stop forwarding data to the file"""

        if self._needs_close:
            self._file.close()


class _AsyncFileWriter(_UnicodeWriter[AnyStr]):
    """Forward data to an aiofile"""

    def __init__(self, process: 'SSHProcess[AnyStr]',
                 file: _AsyncFileProtocol[bytes], needs_close: bool,
                 datatype: Optional[int], encoding: Optional[str], errors: str):
        super().__init__(encoding, errors, hasattr(file, 'encoding'))

        self._process: 'SSHProcess[AnyStr]' = process
        self._file = file
        self._needs_close = needs_close
        self._datatype = datatype
        self._paused = False
        self._queue: asyncio.Queue[Optional[AnyStr]] = asyncio.Queue()
        self._write_task: Optional[asyncio.Task[None]] = \
            process.channel.get_connection().create_task(self._writer())

    async def _writer(self) -> None:
        """Process writes to the file"""

        while True:
            data = await self._queue.get()

            if data is None:
                self._queue.task_done()
                break

            await self._file.write(self.encode(data))
            self._queue.task_done()

            if self._paused and self._queue.qsize() < _QUEUE_LOW_WATER:
                self._process.resume_feeding(self._datatype)
                self._paused = False

        if self._needs_close:
            await self._file.close()

    def write(self, data: AnyStr) -> None:
        """Write data to the file"""

        self._queue.put_nowait(data)

        if not self._paused and self._queue.qsize() >= _QUEUE_HIGH_WATER:
            self._paused = True
            self._process.pause_feeding(self._datatype)

    def write_eof(self) -> None:
        """Close output file when end of file is received"""

        self.close()

    def close(self) -> None:
        """Stop forwarding data to the file"""

        if self._write_task:
            self._write_task = None
            self._queue.put_nowait(None)
            self._process.add_cleanup_task(self._queue.join())


class _PipeReader(_UnicodeReader[AnyStr], asyncio.BaseProtocol):
    """Forward data from a pipe"""

    def __init__(self, process: 'SSHProcess[AnyStr]', datatype: DataType,
                 encoding: Optional[str], errors: str):
        super().__init__(encoding, errors)

        self._process: 'SSHProcess[AnyStr]' = process
        self._datatype = datatype
        self._transport: Optional[asyncio.ReadTransport] = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Handle a newly opened pipe"""

        self._transport = cast(asyncio.ReadTransport, transport)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle closing of the pipe"""

        self._process.feed_close(self._datatype)
        self.close()

    def data_received(self, data: bytes) -> None:
        """Forward data from the pipe"""

        self._process.feed_data(self.decode(data), self._datatype)

    def eof_received(self) -> None:
        """Forward EOF from the pipe"""

        self.check_partial()
        self._process.feed_eof(self._datatype)

    def pause_reading(self) -> None:
        """Pause reading from the pipe"""

        assert self._transport is not None
        self._transport.pause_reading()

    def resume_reading(self) -> None:
        """Resume reading from the pipe"""

        assert self._transport is not None
        self._transport.resume_reading()

    def close(self) -> None:
        """Stop forwarding data from the pipe"""

        assert self._transport is not None
        self._transport.close()


class _PipeWriter(_UnicodeWriter[AnyStr], asyncio.BaseProtocol):
    """Forward data to a pipe"""

    def __init__(self, process: 'SSHProcess[AnyStr]', datatype: DataType,
                 encoding: Optional[str], errors: str):
        super().__init__(encoding, errors)

        self._process: 'SSHProcess[AnyStr]' = process
        self._datatype = datatype
        self._transport: Optional[asyncio.WriteTransport] = None
        self._tty: Optional[IO] = None
        self._close_event = asyncio.Event()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Handle a newly opened pipe"""

        self._transport = cast(asyncio.WriteTransport, transport)

        pipe = transport.get_extra_info('pipe')

        if isinstance(self._process, SSHServerProcess) and pipe.isatty():
            self._tty = pipe
            set_terminal_size(pipe, *self._process.term_size)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle closing of the pipe"""

        self._close_event.set()

    def pause_writing(self) -> None:
        """Pause writing to the pipe"""

        self._process.pause_feeding(self._datatype)

    def resume_writing(self) -> None:
        """Resume writing to the pipe"""

        self._process.resume_feeding(self._datatype)

    def write(self, data: AnyStr) -> None:
        """Write data to the pipe"""

        assert self._transport is not None
        self._transport.write(self.encode(data))

    def write_exception(self, exc: Exception) -> None:
        """Write terminal size changes to the pipe if it is a TTY"""

        if isinstance(exc, TerminalSizeChanged) and self._tty:
            set_terminal_size(self._tty, *exc.term_size)

    def write_eof(self) -> None:
        """Write EOF to the pipe"""

        assert self._transport is not None
        self._transport.write_eof()

    def close(self) -> None:
        """Stop forwarding data to the pipe"""

        assert self._transport is not None
        self._transport.close()
        self._process.add_cleanup_task(self._close_event.wait())


class _ProcessReader(_ReaderProtocol, Generic[AnyStr]):
    """Forward data from another SSH process"""

    def __init__(self, process: 'SSHProcess[AnyStr]', datatype: DataType):
        super().__init__()
        self._process: 'SSHProcess[AnyStr]' = process
        self._datatype = datatype

    def pause_reading(self) -> None:
        """Pause reading from the other channel"""

        self._process.pause_feeding(self._datatype)

    def resume_reading(self) -> None:
        """Resume reading from the other channel"""

        self._process.resume_feeding(self._datatype)

    def close(self) -> None:
        """Stop forwarding data from the other channel"""

        self._process.clear_writer(self._datatype)


class _ProcessWriter(_WriterProtocol[AnyStr]):
    """Forward data to another SSH process"""

    def __init__(self, process: 'SSHProcess[AnyStr]', datatype: DataType):
        super().__init__()
        self._process: 'SSHProcess[AnyStr]' = process
        self._datatype = datatype

    def write(self, data: AnyStr) -> None:
        """Write data to the other channel"""

        self._process.feed_data(data, self._datatype)

    def write_exception(self, exc: Exception) -> None:
        """Write an exception to the other channel"""

        cast(SSHClientProcess, self._process).feed_exception(exc)

    def write_eof(self) -> None:
        """Write EOF to the other channel"""

        self._process.feed_eof(self._datatype)

    def close(self) -> None:
        """Stop forwarding data to the other channel"""

        self._process.clear_reader(self._datatype)


class _StreamReader(_UnicodeReader[AnyStr]):
    """Forward data from an asyncio stream"""

    def __init__(self, process: 'SSHProcess[AnyStr]',
                 reader: asyncio.StreamReader,
                 bufsize: int, datatype: DataType,
                 encoding: Optional[str], errors: str):
        super().__init__(encoding, errors)

        self._process: 'SSHProcess[AnyStr]' = process
        self._conn = process.channel.get_connection()
        self._reader = reader
        self._bufsize = bufsize
        self._datatype = datatype
        self._paused = False

    async def _feed(self) -> None:
        """Feed stream data"""

        while not self._paused:
            data = await self._reader.read(self._bufsize)

            if data:
                self._process.feed_data(self.decode(data), self._datatype)
            else:
                self.check_partial()
                self._process.feed_eof(self._datatype)
                break

    def feed(self) -> None:
        """Start feeding stream data"""

        self._conn.create_task(self._feed())

    def pause_reading(self) -> None:
        """Pause reading from the stream"""

        self._paused = True

    def resume_reading(self) -> None:
        """Resume reading from the stream"""

        self._paused = False
        self.feed()

    def close(self) -> None:
        """Ignore close -- the caller must clean up the associated transport"""


class _StreamWriter(_UnicodeWriter[AnyStr]):
    """Forward data to an asyncio stream"""

    def __init__(self, process: 'SSHProcess[AnyStr]',
                 writer: asyncio.StreamWriter, recv_eof: bool,
                 datatype: Optional[int], encoding: Optional[str], errors: str):
        super().__init__(encoding, errors)

        self._process: 'SSHProcess[AnyStr]' = process
        self._writer = writer
        self._recv_eof = recv_eof
        self._datatype = datatype
        self._paused = False
        self._queue: asyncio.Queue[Optional[AnyStr]] = asyncio.Queue()
        self._write_task: Optional[asyncio.Task[None]] = \
            process.channel.get_connection().create_task(self._feed())

    async def _feed(self) -> None:
        """Feed data to the stream"""

        while True:
            data = await self._queue.get()

            if data is None:
                self._queue.task_done()
                break

            self._writer.write(self.encode(data))
            await self._writer.drain()
            self._queue.task_done()

            if self._paused and self._queue.qsize() < _QUEUE_LOW_WATER:
                self._process.resume_feeding(self._datatype)
                self._paused = False

        if self._recv_eof:
            self._writer.write_eof()

    def write(self, data: AnyStr) -> None:
        """Write data to the stream"""

        self._queue.put_nowait(data)

        if not self._paused and self._queue.qsize() >= _QUEUE_HIGH_WATER:
            self._paused = True
            self._process.pause_feeding(self._datatype)

    def write_eof(self) -> None:
        """Write EOF to the stream"""

        self.close()

    def close(self) -> None:
        """Stop forwarding data to the stream"""

        if self._write_task:
            self._write_task = None
            self._queue.put_nowait(None)
            self._process.add_cleanup_task(self._queue.join())


class _DevNullWriter(_WriterProtocol[AnyStr]):
    """Discard data"""

    def write(self, data: AnyStr) -> None:
        """Discard data being written"""

    def write_eof(self) -> None:
        """Ignore end of file"""

    def close(self) -> None:
        """Ignore close"""


class _StdoutWriter(_WriterProtocol[AnyStr]):
    """Forward data to an SSH process' stdout instead of stderr"""

    def __init__(self, process: 'SSHProcess[AnyStr]'):
        super().__init__()
        self._process: 'SSHProcess[AnyStr]' = process

    def write(self, data: AnyStr) -> None:
        """Pretend data was received on stdout"""

        self._process.data_received(data, None)

    def write_eof(self) -> None:
        """Ignore end of file"""

    def close(self) -> None:
        """Ignore close"""


class ProcessError(Error):
    """SSH Process error

       This exception is raised when an :class:`SSHClientProcess` exits
       with a non-zero exit status and error checking is enabled. In
       addition to the usual error code, reason, and language, it
       contains the following fields:

         ============ ======================================= =================
         Field        Description                             Type
         ============ ======================================= =================
         env          The environment the client requested    `str` or `None`
                      to be set for the process
         command      The command the client requested the    `str` or `None`
                      process to execute (if any)
         subsystem    The subsystem the client requested the  `str` or `None`
                      process to open (if any)
         exit_status  The exit status returned, or -1 if an   `int` or `None`
                      exit signal is sent
         exit_signal  The exit signal sent (if any) in the    `tuple` or `None`
                      form of a tuple containing the signal
                      name, a `bool` for whether a core dump
                      occurred, a message associated with the
                      signal, and the language the message
                      was in
         returncode   The exit status returned, or negative   `int` or `None`
                      of the signal number when an exit
                      signal is sent
         stdout       The output sent by the process to       `str` or `bytes`
                      stdout (if not redirected)
         stderr       The output sent by the process to       `str` or `bytes`
                      stderr (if not redirected)
         ============ ======================================= =================

    """

    def __init__(self, env: Optional[Mapping[str, str]],
                 command: Optional[str], subsystem: Optional[str],
                 exit_status: Optional[int],
                 exit_signal: Optional[Tuple[str, bool, str, str]],
                 returncode: Optional[int], stdout: BytesOrStr,
                 stderr: BytesOrStr, reason: str = '',
                 lang: str = DEFAULT_LANG):
        self.env = env
        self.command = command
        self.subsystem = subsystem
        self.exit_status = exit_status
        self.exit_signal = exit_signal
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

        if exit_signal:
            signal, core_dumped, msg, lang = exit_signal
            reason = 'Process exited with signal ' + signal + \
                     (': ' + msg if msg else '') + \
                     (' (core dumped)' if core_dumped else '')
        elif exit_status:
            reason = f'Process exited with non-zero exit status {exit_status}'

        super().__init__(exit_status or 0, reason, lang)


# pylint: disable=redefined-builtin
class TimeoutError(ProcessError, asyncio.TimeoutError):
    """SSH Process timeout error

       This exception is raised when a timeout occurs when calling the
       :meth:`wait <SSHClientProcess.wait>` method on :class:`SSHClientProcess`
       or the :meth:`run <SSHClientConnection.run>` method on
       :class:`SSHClientConnection`. It is a subclass of :class:`ProcessError`
       and contains all of the fields documented there, including any output
       received on stdout and stderr prior to when the timeout occurred. It
       is also a subclass of :class:`asyncio.TimeoutError`, for code that
       might be expecting that.

    """
# pylint: enable=redefined-builtin


class SSHCompletedProcess(Record):
    """Results from running an SSH process

       This object is returned by the :meth:`run <SSHClientConnection.run>`
       method on :class:`SSHClientConnection` when the requested command
       has finished running. It contains the following fields:

         ============ ======================================= =================
         Field        Description                             Type
         ============ ======================================= =================
         env          The environment the client requested    `dict` or `None`
                      to be set for the process
         command      The command the client requested the    `str` or `None`
                      process to execute (if any)
         subsystem    The subsystem the client requested the  `str` or `None`
                      process to open (if any)
         exit_status  The exit status returned, or -1 if an   `int`
                      exit signal is sent
         exit_signal  The exit signal sent (if any) in the    `tuple` or `None`
                      form of a tuple containing the signal
                      name, a `bool` for whether a core dump
                      occurred, a message associated with the
                      signal, and the language the message
                      was in
         returncode   The exit status returned, or negative   `int`
                      of the signal number when an exit
                      signal is sent
         stdout       The output sent by the process to       `str` or `bytes`
                      stdout (if not redirected)
         stderr       The output sent by the process to       `str` or `bytes`
                      stderr (if not redirected)
         ============ ======================================= =================

    """

    env: Optional[Mapping[str, str]]
    command: Optional[str]
    subsystem: Optional[str]
    exit_status: Optional[int]
    exit_signal: Optional[Tuple[str, bool, str, str]]
    returncode: Optional[int]
    stdout: Optional[BytesOrStr]
    stderr: Optional[BytesOrStr]


class SSHProcess(SSHStreamSession, Generic[AnyStr]):
    """SSH process handler"""

    def __init__(self, *args) -> None:
        super().__init__(*args)

        self._cleanup_tasks: List[Awaitable[None]] = []

        self._readers: Dict[Optional[int], _ReaderProtocol] = {}
        self._send_eof: Dict[Optional[int], bool] = {}

        self._writers: Dict[Optional[int], _WriterProtocol[AnyStr]] = {}
        self._recv_eof: Dict[Optional[int], bool] = {}

        self._paused_write_streams: Set[Optional[int]] = set()

    async def __aenter__(self) -> Self:
        """Allow SSHProcess to be used as an async context manager"""

        return self

    async def __aexit__(self, _exc_type: Optional[Type[BaseException]],
                        _exc_value: Optional[BaseException],
                        _traceback: Optional[TracebackType]) -> bool:
        """Wait for a full channel close when exiting the async context"""

        self.close()
        await self.wait_closed()
        return False

    @property
    def channel(self) -> SSHChannel[AnyStr]:
        """The channel associated with the process"""

        assert self._chan is not None
        return self._chan

    @property
    def logger(self) -> SSHLogger:
        """The logger associated with the process"""

        assert self._chan is not None
        return self._chan.logger

    @property
    def command(self) -> Optional[str]:
        """The command the client requested to execute, if any

           If the client did not request that a command be executed,
           this property will be set to `None`.

        """

        assert self._chan is not None
        return self._chan.get_command()

    @property
    def subsystem(self) -> Optional[str]:
        """The subsystem the client requested to open, if any

           If the client did not request that a subsystem be opened,
           this property will be set to `None`.

        """

        assert self._chan is not None
        return self._chan.get_subsystem()

    @property
    def env(self) -> Mapping[str, str]:
        """A mapping containing the environment set by the client"""

        assert self._chan is not None
        return self._chan.get_environment()

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        """Return additional information about this process

           This method returns extra information about the channel
           associated with this process. See :meth:`get_extra_info()
           <SSHClientChannel.get_extra_info>` on :class:`SSHClientChannel`
           for additional information.

        """

        assert self._chan is not None
        return self._chan.get_extra_info(name, default)

    async def _create_reader(self, source: ProcessSource, bufsize: int,
                             send_eof: bool, recv_eof: bool,
                             datatype: DataType = None) -> None:
        """Create a reader to forward data to the SSH channel"""

        def pipe_factory() -> _PipeReader:
            """Return a pipe read handler"""

            return _PipeReader(self, datatype, self._encoding, self._errors)

        if source == PIPE:
            reader: Optional[_ReaderProtocol] = None
        elif source == DEVNULL:
            assert self._chan is not None
            self._chan.write_eof()
            reader = None
        elif isinstance(source, SSHReader):
            reader_stream, reader_datatype = source.get_redirect_info()
            reader_process = cast('SSHProcess[AnyStr]', reader_stream)
            writer = _ProcessWriter[AnyStr](self, datatype)
            reader_process.set_writer(writer, recv_eof, reader_datatype)
            reader = _ProcessReader(reader_process, reader_datatype)
        elif isinstance(source, asyncio.StreamReader):
            reader = _StreamReader(self, source, bufsize, datatype,
                                   self._encoding, self._errors)
        else:
            file: _File

            if isinstance(source, str):
                file = open_file(source, 'rb', buffering=bufsize)
            elif isinstance(source, PurePath):
                file = open_file(str(source), 'rb', buffering=bufsize)
            elif isinstance(source, int):
                file = os.fdopen(source, 'rb', buffering=bufsize)
            elif isinstance(source, socket.socket):
                file = os.fdopen(source.detach(), 'rb', buffering=bufsize)
            else:
                file = source

            if hasattr(file, 'read') and \
                    (inspect.iscoroutinefunction(file.read) or
                     inspect.isgeneratorfunction(file.read)):
                reader = _AsyncFileReader(self, cast(_AsyncFileProtocol, file),
                                          bufsize, datatype, self._encoding,
                                          self._errors)
            elif _is_regular_file(cast(IO[bytes], file)):
                reader = _FileReader(self, cast(IO[bytes], file), bufsize,
                                     datatype, self._encoding, self._errors)
            else:
                if hasattr(source, 'buffer'):
                    # If file was opened in text mode, remove that wrapper
                    file = cast(TextIO, source).buffer

                assert self._loop is not None
                _, protocol = \
                    await self._loop.connect_read_pipe(pipe_factory, file)
                reader = cast(_PipeReader, protocol)

        self.set_reader(reader, send_eof, datatype)

        if isinstance(reader, (_FileReader, _AsyncFileReader, _StreamReader)):
            reader.feed()
        elif isinstance(reader, _ProcessReader):
            reader_process.feed_recv_buf(reader_datatype, writer)

    async def _create_writer(self, target: ProcessTarget, bufsize: int,
                             send_eof: bool, recv_eof: bool,
                             datatype: DataType = None) -> None:
        """Create a writer to forward data from the SSH channel"""

        def pipe_factory() -> _PipeWriter:
            """Return a pipe write handler"""

            return _PipeWriter(self, datatype, self._encoding, self._errors)

        if target == PIPE:
            writer: Optional[_WriterProtocol[AnyStr]] = None
        elif target == DEVNULL:
            writer = _DevNullWriter()
        elif target == STDOUT:
            writer = _StdoutWriter(self)
        elif isinstance(target, SSHWriter):
            writer_stream, writer_datatype = target.get_redirect_info()
            writer_process = cast('SSHProcess[AnyStr]', writer_stream)
            reader = _ProcessReader(self, datatype)
            writer_process.set_reader(reader, send_eof, writer_datatype)
            writer = _ProcessWriter[AnyStr](writer_process, writer_datatype)
        elif isinstance(target, asyncio.StreamWriter):
            writer = _StreamWriter(self, target, recv_eof, datatype,
                                   self._encoding, self._errors)
        else:
            file: _File
            needs_close = True

            if isinstance(target, str):
                file = open_file(target, 'wb', buffering=bufsize)
            elif isinstance(target, PurePath):
                file = open_file(str(target), 'wb', buffering=bufsize)
            elif isinstance(target, int):
                file = os.fdopen(target, 'wb',
                                 buffering=bufsize, closefd=recv_eof)
            elif isinstance(target, socket.socket):
                fd = target.detach() if recv_eof else target.fileno()
                file = os.fdopen(fd, 'wb', buffering=bufsize, closefd=recv_eof)
            else:
                file = target
                needs_close = recv_eof

            if hasattr(file, 'write') and \
                    (inspect.iscoroutinefunction(file.write) or
                     inspect.isgeneratorfunction(file.write)):
                writer = _AsyncFileWriter(
                    self, cast(_AsyncFileProtocol, file), needs_close,
                    datatype, self._encoding, self._errors)
            elif _is_regular_file(cast(IO[bytes], file)):
                writer = _FileWriter(cast(IO[bytes], file), needs_close,
                                    self._encoding, self._errors)
            else:
                if hasattr(target, 'buffer'):
                    # If file was opened in text mode, remove that wrapper
                    file = cast(TextIO, target).buffer

                if not recv_eof:
                    fd = os.dup(cast(IO[bytes], file).fileno())
                    file = os.fdopen(fd, 'wb', buffering=0)

                assert self._loop is not None
                _, protocol = \
                    await self._loop.connect_write_pipe(pipe_factory, file)
                writer = cast(_PipeWriter, protocol)

        self.set_writer(writer, recv_eof, datatype)

        if writer:
            self.feed_recv_buf(datatype, writer)

    def _should_block_drain(self, datatype: DataType) -> bool:
        """Return whether output is still being written to the channel"""

        return (datatype in self._readers or
                super()._should_block_drain(datatype))

    def _should_pause_reading(self) -> bool:
        """Return whether to pause reading from the channel"""

        return bool(self._paused_write_streams) or \
            super()._should_pause_reading()

    def add_cleanup_task(self, task: Awaitable) -> None:
        """Add a task to run when the process exits"""

        self._cleanup_tasks.append(task)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle a close of the SSH channel"""

        super().connection_lost(exc) # type: ignore

        for reader in list(self._readers.values()):
            reader.close()

        for writer in list(self._writers.values()):
            writer.close()

        self._readers = {}
        self._writers = {}

    def data_received(self, data: AnyStr, datatype: DataType) -> None:
        """Handle incoming data from the SSH channel"""

        writer = self._writers.get(datatype)

        if writer:
            writer.write(data)
        else:
            super().data_received(data, datatype)

    def eof_received(self) -> bool:
        """Handle an incoming end of file from the SSH channel"""

        for datatype, writer in list(self._writers.items()):
            if self._recv_eof[datatype]:
                writer.write_eof()

        return super().eof_received()

    def pause_writing(self) -> None:
        """Pause forwarding data to the channel"""

        super().pause_writing()

        for reader in list(self._readers.values()):
            reader.pause_reading()

    def resume_writing(self) -> None:
        """Resume forwarding data to the channel"""

        super().resume_writing()

        for reader in list(self._readers.values()):
            reader.resume_reading()

    def feed_data(self, data: AnyStr, datatype: DataType) -> None:
        """Feed data to the channel"""

        assert self._chan is not None
        self._chan.write(data, datatype)

    def feed_eof(self, datatype: DataType) -> None:
        """Feed EOF to the channel"""

        if self._send_eof[datatype]:
            assert self._chan is not None
            self._chan.write_eof()

        self._readers[datatype].close()
        self.clear_reader(datatype)

    def feed_close(self, datatype: DataType) -> None:
        """Feed pipe close to the channel"""

        if datatype in self._readers:
            self.feed_eof(datatype)

    def feed_recv_buf(self, datatype: DataType,
                      writer: _WriterProtocol[AnyStr]) -> None:
        """Feed current receive buffer to a newly set writer"""

        for buf in self._recv_buf[datatype]:
            if isinstance(buf, Exception):
                writer.write_exception(buf)
            else:
                writer.write(buf)
                self._recv_buf_len -= len(buf)

        self._recv_buf[datatype].clear()

        if self._eof_received:
            writer.write_eof()

        self._maybe_resume_reading()

    def pause_feeding(self, datatype: DataType) -> None:
        """Pause feeding data from the channel"""

        self._paused_write_streams.add(datatype)
        self._maybe_pause_reading()

    def resume_feeding(self, datatype: DataType) -> None:
        """Resume feeding data from the channel"""

        self._paused_write_streams.remove(datatype)
        self._maybe_resume_reading()

    def set_reader(self, reader: Optional[_ReaderProtocol],
                   send_eof: bool, datatype: DataType) -> None:
        """Set a reader used to forward data to the channel"""

        old_reader = self._readers.get(datatype)

        if old_reader:
            old_reader.close()

        if reader:
            self._readers[datatype] = reader
            self._send_eof[datatype] = send_eof

            if self._write_paused:
                reader.pause_reading()
        elif old_reader:
            self.clear_reader(datatype)

    def clear_reader(self, datatype: DataType) -> None:
        """Clear a reader forwarding data to the channel"""

        del self._readers[datatype]
        del self._send_eof[datatype]
        self._unblock_drain(datatype)

    def set_writer(self, writer: Optional[_WriterProtocol[AnyStr]],
                   recv_eof: bool, datatype: DataType) -> None:
        """Set a writer used to forward data from the channel"""

        old_writer = self._writers.get(datatype)

        if old_writer:
            old_writer.close()
            self.clear_writer(datatype)

        if writer:
            self._writers[datatype] = writer
            self._recv_eof[datatype] = recv_eof

    def clear_writer(self, datatype: DataType) -> None:
        """Clear a writer forwarding data from the channel"""

        if datatype in self._paused_write_streams:
            self.resume_feeding(datatype)

        del self._writers[datatype]

    def close(self) -> None:
        """Shut down the process"""

        assert self._chan is not None
        self._chan.close()

    def is_closing(self) -> bool:
        """Return if the channel is closing or is closed"""

        assert self._chan is not None
        return self._chan.is_closing()

    async def wait_closed(self) -> None:
        """Wait for the process to finish shutting down"""

        assert self._chan is not None
        await self._chan.wait_closed()

        for task in self._cleanup_tasks:
            await task

        self._cleanup_tasks = []


class SSHClientProcess(SSHProcess[AnyStr], SSHClientStreamSession[AnyStr]):
    """SSH client process handler"""

    _chan: SSHClientChannel[AnyStr]
    channel: SSHClientChannel[AnyStr]

    def __init__(self) -> None:
        super().__init__()

        self._stdin: Optional[SSHWriter[AnyStr]] = None
        self._stdout: Optional[SSHReader[AnyStr]] = None
        self._stderr: Optional[SSHReader[AnyStr]] = None

    def _collect_output(self, datatype: DataType = None) -> AnyStr:
        """Return output from the process"""

        recv_buf = self._recv_buf[datatype]

        if recv_buf and isinstance(recv_buf[-1], Exception):
            recv_buf, self._recv_buf[datatype] = recv_buf[:-1], recv_buf[-1:]
        else:
            self._recv_buf[datatype] = []

        buf = cast(AnyStr, '' if self._encoding else b'')
        return buf.join(cast(Iterable[AnyStr], recv_buf))

    def session_started(self) -> None:
        """Start a process for this newly opened client channel"""

        self._stdin = SSHWriter[AnyStr](self, self._chan)
        self._stdout = SSHReader[AnyStr](self, self._chan)
        self._stderr = SSHReader[AnyStr](self, self._chan, EXTENDED_DATA_STDERR)

    @property
    def exit_status(self) -> Optional[int]:
        """The exit status of the process"""

        return self._chan.get_exit_status()

    @property
    def exit_signal(self) -> Optional[Tuple[str, bool, str, str]]:
        """Exit signal information for the process"""

        return self._chan.get_exit_signal()

    @property
    def returncode(self) -> Optional[int]:
        """The exit status or negative exit signal number for the process"""

        return self._chan.get_returncode()

    @property
    def stdin(self) -> SSHWriter[AnyStr]:
        """The :class:`SSHWriter` to use to write to stdin of the process"""

        assert self._stdin is not None
        return self._stdin

    @property
    def stdout(self) -> SSHReader[AnyStr]:
        """The :class:`SSHReader` to use to read from stdout of the process"""

        assert self._stdout is not None
        return self._stdout

    @property
    def stderr(self) -> SSHReader[AnyStr]:
        """The :class:`SSHReader` to use to read from stderr of the process"""

        assert self._stderr is not None
        return self._stderr

    def feed_exception(self, exc: Exception) -> None:
        """Feed exception to the channel"""

        if isinstance(exc, TerminalSizeChanged):
            self._chan.change_terminal_size(exc.width, exc.height,
                                            exc.pixwidth, exc.pixheight)
        elif isinstance(exc, BreakReceived):
            self._chan.send_break(exc.msec)
        elif isinstance(exc, SignalReceived): # pragma: no branch
            self._chan.send_signal(exc.signal)

    async def redirect(self, stdin: Optional[ProcessSource] = None,
                       stdout: Optional[ProcessTarget] = None,
                       stderr: Optional[ProcessTarget] = None,
                       bufsize: int =io.DEFAULT_BUFFER_SIZE,
                       send_eof: bool = True, recv_eof: bool = True) -> None:
        """Perform I/O redirection for the process

           This method redirects data going to or from any or all of
           standard input, standard output, and standard error for
           the process.

           The `stdin` argument can be any of the following:

               * An :class:`SSHReader` object
               * An :class:`asyncio.StreamReader` object
               * A file object open for read
               * An `int` file descriptor open for read
               * A connected socket object
               * A string or :class:`PurePath <pathlib.PurePath>` containing
                 the name of a file or device to open
               * `DEVNULL` to provide no input to standard input
               * `PIPE` to interactively write standard input

           The `stdout` and `stderr` arguments can be any of the following:

               * An :class:`SSHWriter` object
               * An :class:`asyncio.StreamWriter` object
               * A file object open for write
               * An `int` file descriptor open for write
               * A connected socket object
               * A string or :class:`PurePath <pathlib.PurePath>` containing
                 the name of a file or device to open
               * `DEVNULL` to discard standard error output
               * `PIPE` to interactively read standard error output

           The `stderr` argument also accepts the value `STDOUT` to
           request that standard error output be delivered to stdout.

           File objects passed in can be associated with plain files, pipes,
           sockets, or ttys.

           The default value of `None` means to not change redirection
           for that stream.

           .. note:: While it is legal to use buffered I/O streams such
                     as sys.stdin, sys.stdout, and sys.stderr as redirect
                     targets, you must make sure buffers are flushed
                     before redirection begins and that these streams
                     are put back into blocking mode before attempting
                     to go back using buffered I/O again. Also, no buffered
                     I/O should be performed while redirection is active.

           .. note:: When passing in asyncio streams, it is the responsibility
                     of the caller to close the associated transport when it
                     is no longer needed.

           :param stdin:
               Source of data to feed to standard input
           :param stdout:
               Target to feed data from standard output to
           :param stderr:
               Target to feed data from standard error to
           :param bufsize:
               Buffer size to use when forwarding data from a file
           :param send_eof:
               Whether or not to send EOF to the channel when EOF is
               received from stdin, defaulting to `True`. If set to `False`,
               the channel will remain open after EOF is received on stdin,
               and multiple sources can be redirected to the channel.
           :param recv_eof:
               Whether or not to send EOF to stdout and stderr when EOF is
               received from the channel, defaulting to `True`. If set to
               `False`, the redirect targets of stdout and stderr will remain
               open after EOF is received on the channel and can be used for
               multiple redirects.
           :type bufsize: `int`
           :type send_eof: `bool`
           :type recv_eof: `bool`

        """

        if stdin:
            await self._create_reader(stdin, bufsize, send_eof, recv_eof)

        if stdout:
            await self._create_writer(stdout, bufsize, send_eof, recv_eof)

        if stderr:
            await self._create_writer(stderr, bufsize, send_eof, recv_eof,
                                      EXTENDED_DATA_STDERR)

    async def redirect_stdin(self, source: ProcessSource,
                             bufsize: int = io.DEFAULT_BUFFER_SIZE,
                             send_eof: bool = True) -> None:
        """Redirect standard input of the process"""

        await self.redirect(source, None, None, bufsize, send_eof, True)

    async def redirect_stdout(self, target: ProcessTarget,
                              bufsize: int = io.DEFAULT_BUFFER_SIZE,
                              recv_eof: bool = True) -> None:
        """Redirect standard output of the process"""

        await self.redirect(None, target, None, bufsize, True, recv_eof)

    async def redirect_stderr(self, target: ProcessTarget,
                              bufsize: int = io.DEFAULT_BUFFER_SIZE,
                              recv_eof: bool = True) -> None:
        """Redirect standard error of the process"""

        await self.redirect(None, None, target, bufsize, True, recv_eof)

    def collect_output(self) -> Tuple[AnyStr, AnyStr]:
        """Collect output from the process without blocking

           This method returns a tuple of the output that the process
           has written to stdout and stderr which has not yet been read.
           It is intended to be called instead of read() by callers
           that want to collect received data without blocking.

           :returns: A tuple of output to stdout and stderr

        """

        return (self._collect_output(),
                self._collect_output(EXTENDED_DATA_STDERR))

    # pylint: disable=redefined-builtin
    async def communicate(self, input: Optional[AnyStr] = None) -> \
            Tuple[AnyStr, AnyStr]:
        """Send input to and/or collect output from the process

           This method is a coroutine which optionally provides input
           to the process and then waits for the process to exit,
           returning a tuple of the data written to stdout and stderr.

           :param input:
               Input data to feed to standard input of the process. Data
               should be a `str` if encoding is set, or `bytes` if not.
           :type input: `str` or `bytes`

           :returns: A tuple of output to stdout and stderr

        """

        self._limit = 0
        self._maybe_resume_reading()

        if input:
            self._chan.write(input)
            self._chan.write_eof()

        await self.wait_closed()

        return self.collect_output()
    # pylint: enable=redefined-builtin

    def change_terminal_size(self, width: int, height: int,
                             pixwidth: int = 0, pixheight: int = 0) -> None:
        """Change the terminal window size for this process

           This method changes the width and height of the terminal
           associated with this process.

           :param width:
               The width of the terminal in characters
           :param height:
               The height of the terminal in characters
           :param pixwidth: (optional)
               The width of the terminal in pixels
           :param pixheight: (optional)
               The height of the terminal in pixels
           :type width: `int`
           :type height: `int`
           :type pixwidth: `int`
           :type pixheight: `int`

           :raises: :exc:`OSError` if the SSH channel is not open

        """

        self._chan.change_terminal_size(width, height, pixwidth, pixheight)

    def send_break(self, msec: int) -> None:
        """Send a break to the process

           :param msec:
               The duration of the break in milliseconds
           :type msec: `int`

           :raises: :exc:`OSError` if the SSH channel is not open

        """

        self._chan.send_break(msec)

    def send_signal(self, signal: str) -> None:
        """Send a signal to the process

           :param signal:
               The signal to deliver
           :type signal: `str`

           :raises: :exc:`OSError` if the SSH channel is not open

        """

        self._chan.send_signal(signal)

    def terminate(self) -> None:
        """Terminate the process

           :raises: :exc:`OSError` if the SSH channel is not open

        """

        self._chan.terminate()

    def kill(self) -> None:
        """Forcibly kill the process

           :raises: :exc:`OSError` if the SSH channel is not open

        """

        self._chan.kill()

    async def wait(self, check: bool = False,
                   timeout: Optional[float] = None) -> SSHCompletedProcess:
        """Wait for process to exit

           This method is a coroutine which waits for the process to
           exit. It returns an :class:`SSHCompletedProcess` object with
           the exit status or signal information and the output sent
           to stdout and stderr if those are redirected to pipes.

           If the check argument is set to `True`, a non-zero exit
           status from the process with trigger the :exc:`ProcessError`
           exception to be raised.

           If a timeout is specified and it expires before the process
           exits, the :exc:`TimeoutError` exception will be raised. By
           default, no timeout is set and this call will wait indefinitely.

           :param check:
               Whether or not to raise an error on non-zero exit status
           :param timeout:
               Amount of time in seconds to wait for process to exit, or
               `None` to wait indefinitely
           :type check: `bool`
           :type timeout: `int`, `float`, or `None`

           :returns: :class:`SSHCompletedProcess`

           :raises: | :exc:`ProcessError` if check is set to `True`
                      and the process returns a non-zero exit status
                    | :exc:`TimeoutError` if the timeout expires
                      before the process exits

        """

        try:
            stdout_data, stderr_data = \
                await asyncio.wait_for(self.communicate(), timeout)
        except asyncio.TimeoutError:
            stdout_data, stderr_data = self.collect_output()

            raise TimeoutError(self.env, self.command, self.subsystem,
                               self.exit_status, self.exit_signal,
                               self.returncode, stdout_data,
                               stderr_data) from None

        if check and self.exit_status:
            raise ProcessError(self.env, self.command, self.subsystem,
                               self.exit_status, self.exit_signal,
                               self.returncode, stdout_data, stderr_data)
        else:
            return SSHCompletedProcess(self.env, self.command, self.subsystem,
                                       self.exit_status, self.exit_signal,
                                       self.returncode, stdout_data,
                                       stderr_data)


class SSHServerProcess(SSHProcess[AnyStr], SSHServerStreamSession[AnyStr]):
    """SSH server process handler"""

    _chan: SSHServerChannel[AnyStr]
    channel: SSHServerChannel[AnyStr]

    def __init__(self, process_factory: SSHServerProcessFactory,
                 sftp_factory: Optional[SFTPServerFactory],
                 sftp_version: int, allow_scp: bool):
        super().__init__(self._start_process, sftp_factory,
                         sftp_version, allow_scp)

        self._process_factory = process_factory

        self._stdin: Optional[SSHReader[AnyStr]] = None
        self._stdout: Optional[SSHWriter[AnyStr]] = None
        self._stderr: Optional[SSHWriter[AnyStr]] = None

    def _start_process(self, stdin: SSHReader[AnyStr],
                       stdout: SSHWriter[AnyStr],
                       stderr: SSHWriter[AnyStr]) -> MaybeAwait[None]:
        """Start a new server process"""

        self._stdin = stdin
        self._stdout = stdout
        self._stderr = stderr

        return self._process_factory(self)

    @property
    def term_type(self) -> Optional[str]:
        """The terminal type set by the client

           If the client didn't request a pseudo-terminal, this
           property will be set to `None`.

        """

        return self._chan.get_terminal_type()

    @property
    def term_size(self) -> TermSize:
        """The terminal size set by the client

           This property contains a tuple of four `int` values
           representing the width and height of the terminal in
           characters followed by the width and height of the
           terminal in pixels. If the client hasn't set terminal
           size information, the values will be set to zero.

        """

        return self._chan.get_terminal_size()

    @property
    def term_modes(self) -> TermModes:
        """A mapping containing the TTY modes set by the client

           If the client didn't request a pseudo-terminal, this
           property will be set to an empty mapping.

        """

        return self._chan.get_terminal_modes()

    @property
    def stdin(self) -> SSHReader[AnyStr]:
        """The :class:`SSHReader` to use to read from stdin of the process"""

        assert self._stdin is not None
        return self._stdin

    @property
    def stdout(self) -> SSHWriter[AnyStr]:
        """The :class:`SSHWriter` to use to write to stdout of the process"""

        assert self._stdout is not None
        return self._stdout

    @property
    def stderr(self) -> SSHWriter[AnyStr]:
        """The :class:`SSHWriter` to use to write to stderr of the process"""

        assert self._stderr is not None
        return self._stderr

    def exception_received(self, exc: Exception) -> None:
        """Handle an incoming exception on the channel"""

        writer = self._writers.get(None)

        if writer:
            writer.write_exception(exc)
        else:
            super().exception_received(exc)

    async def redirect(self, stdin: Optional[ProcessTarget] = None,
                       stdout: Optional[ProcessSource] = None,
                       stderr: Optional[ProcessSource] = None,
                       bufsize: int = io.DEFAULT_BUFFER_SIZE,
                       send_eof: bool = True, recv_eof: bool = True) -> None:
        """Perform I/O redirection for the process

           This method redirects data going to or from any or all of
           standard input, standard output, and standard error for
           the process.

           The `stdin` argument can be any of the following:

               * An :class:`SSHWriter` object
               * An :class:`asyncio.StreamWriter` object
               * A file object open for write
               * An `int` file descriptor open for write
               * A connected socket object
               * A string or :class:`PurePath <pathlib.PurePath>` containing
                 the name of a file or device to open
               * `DEVNULL` to discard standard error output
               * `PIPE` to interactively read standard error output

           The `stdout` and `stderr` arguments can be any of the following:

               * An :class:`SSHReader` object
               * An :class:`asyncio.StreamReader` object
               * A file object open for read
               * An `int` file descriptor open for read
               * A connected socket object
               * A string or :class:`PurePath <pathlib.PurePath>` containing
                 the name of a file or device to open
               * `DEVNULL` to provide no input to standard input
               * `PIPE` to interactively write standard input

           File objects passed in can be associated with plain files, pipes,
           sockets, or ttys.

           The default value of `None` means to not change redirection
           for that stream.

           .. note:: When passing in asyncio streams, it is the responsibility
                     of the caller to close the associated transport when it
                     is no longer needed.

           :param stdin:
               Target to feed data from standard input to
           :param stdout:
               Source of data to feed to standard output
           :param stderr:
               Source of data to feed to standard error
           :param bufsize:
               Buffer size to use when forwarding data from a file
           :param send_eof:
               Whether or not to send EOF to the channel when EOF is
               received from stdout or stderr, defaulting to `True`. If
               set to `False`, the channel will remain open after EOF is
               received on stdout or stderr, and multiple sources can be
               redirected to the channel.
           :param recv_eof:
               Whether or not to send EOF to stdin when EOF is received
               on the channel, defaulting to `True`. If set to `False`,
               the redirect target of stdin will remain open after EOF
               is received on the channel and can be used for multiple
               redirects.
           :type bufsize: `int`
           :type send_eof: `bool`
           :type recv_eof: `bool`

        """

        if stdin:
            await self._create_writer(stdin, bufsize, send_eof, recv_eof)

        if stdout:
            await self._create_reader(stdout, bufsize, send_eof, recv_eof)

        if stderr:
            await self._create_reader(stderr, bufsize, send_eof, recv_eof,
                                      EXTENDED_DATA_STDERR)

    async def redirect_stdin(self, target: ProcessTarget,
                             bufsize: int = io.DEFAULT_BUFFER_SIZE,
                             recv_eof: bool = True) -> None:
        """Redirect standard input of the process"""

        await self.redirect(target, None, None, bufsize, True, recv_eof)

    async def redirect_stdout(self, source: ProcessSource,
                              bufsize: int = io.DEFAULT_BUFFER_SIZE,
                              send_eof: bool = True) -> None:
        """Redirect standard output of the process"""

        await self.redirect(None, source, None, bufsize, send_eof, True)

    async def redirect_stderr(self, source: ProcessSource,
                              bufsize: int = io.DEFAULT_BUFFER_SIZE,
                              send_eof: bool = True) -> None:
        """Redirect standard error of the process"""

        await self.redirect(None, None, source, bufsize, send_eof, True)

    def get_terminal_type(self) -> Optional[str]:
        """Return the terminal type set by the client for the process

           This method returns the terminal type set by the client
           when the process was started. If the client didn't request
           a pseudo-terminal, this method will return `None`.

           :returns: A `str` containing the terminal type or `None` if
                     no pseudo-terminal was requested

        """

        return self.term_type

    def get_terminal_size(self) -> Tuple[int, int, int, int]:
        """Return the terminal size set by the client for the process

           This method returns the latest terminal size information set
           by the client. If the client didn't set any terminal size
           information, all values returned will be zero.

           :returns: A tuple of four `int` values containing the width and
                     height of the terminal in characters and the width
                     and height of the terminal in pixels

        """

        return self.term_size

    def get_terminal_mode(self, mode: int) -> Optional[int]:
        """Return the requested TTY mode for this session

           This method looks up the value of a POSIX terminal mode
           set by the client when the process was started. If the client
           didn't request a pseudo-terminal or didn't set the requested
           TTY mode opcode, this method will return `None`.

           :param mode:
               POSIX terminal mode taken from :ref:`POSIX terminal modes
               <PTYModes>` to look up
           :type mode: `int`

           :returns: An `int` containing the value of the requested
                     POSIX terminal mode or `None` if the requested
                     mode was not set

        """

        return self.term_modes.get(mode)

    def exit(self, status: int) -> None:
        """Send exit status and close the channel

           This method can be called to report an exit status for the
           process back to the client and close the channel.

           :param status:
               The exit status to report to the client
           :type status: `int`

        """

        self._chan.exit(status)

    def exit_with_signal(self, signal: str, core_dumped: bool = False,
                         msg: str = '', lang: str = DEFAULT_LANG) -> None:
        """Send exit signal and close the channel

           This method can be called to report that the process
           terminated abnormslly with a signal. A more detailed
           error message may also provided, along with an indication
           of whether or not the process dumped core. After
           reporting the signal, the channel is closed.

           :param signal:
               The signal which caused the process to exit
           :param core_dumped: (optional)
               Whether or not the process dumped core
           :param msg: (optional)
               Details about what error occurred
           :param lang: (optional)
               The language the error message is in
           :type signal: `str`
           :type core_dumped: `bool`
           :type msg: `str`
           :type lang: `str`

        """

        return self._chan.exit_with_signal(signal, core_dumped, msg, lang)
