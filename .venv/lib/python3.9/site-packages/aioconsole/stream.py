"""Provide an asynchronous equivalent to *input*."""

import os
import sys
import stat
import weakref
import asyncio
import selectors
from collections import deque
from threading import Thread
from concurrent.futures import Future

from . import compat


class ProtectedPipe:
    """Wrapper to protect a pipe from being closed."""

    def __init__(self, pipe):
        self.pipe = pipe

    def fileno(self):
        return self.pipe.fileno()

    def close(self):
        pass


def is_pipe_transport_compatible(pipe):
    if compat.platform == "win32":
        return False
    try:
        fileno = pipe.fileno()
    except (OSError, AttributeError):
        return False
    mode = os.fstat(fileno).st_mode
    is_char = stat.S_ISCHR(mode)
    is_fifo = stat.S_ISFIFO(mode)
    is_socket = stat.S_ISSOCK(mode)
    if not (is_char or is_fifo or is_socket):
        return False
    # Fail early when the file descriptor cannot be registered.
    # This happens with docker containers for instance.
    # See issue #102: https://github.com/vxgmichel/aioconsole/issues/102
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(fileno, selectors.EVENT_READ | selectors.EVENT_WRITE)
    except OSError:
        return False
    return True


async def run_as_daemon(func, *args):
    future = Future()
    future.set_running_or_notify_cancel()

    # A bug in python 3.7 makes it a bad idea to set a BaseException
    # in a wrapped future (see except statement in asyncio.Task.__wakeup)
    # Instead, we'll wrap base exceptions into exceptions and unwrap them
    # on the other side of the call.
    class BaseExceptionWrapper(Exception):
        pass

    def daemon():
        try:
            result = func(*args)
        except Exception as e:
            future.set_exception(e)
        except BaseException as e:
            future.set_exception(BaseExceptionWrapper(e))
        else:
            future.set_result(result)

    Thread(target=daemon, daemon=True).start()
    try:
        return await asyncio.wrap_future(future)
    except BaseExceptionWrapper as exc:
        raise exc.args[0]


class StandardStreamReaderProtocol(asyncio.StreamReaderProtocol):
    def connection_made(self, transport):
        # The connection is already made
        if self._stream_reader._transport is not None:
            return
        # Make the connection
        super().connection_made(transport)

    def connection_lost(self, exc):
        # Copy the inner state
        state = self.__dict__.copy()
        # Call the parent
        super().connection_lost(exc)
        # Restore the inner state
        self.__dict__.update(state)


class StandardStreamReader(asyncio.StreamReader):
    async def readuntil(self, separator=b"\n"):
        # Re-implement `readuntil` to work around self._limit.
        # The limit is still useful to prevent the internal buffer
        # from growing too large when it's not necessary, but it
        # needs to be disabled when the user code is purposely
        # reading from stdin.
        while True:
            try:
                return await super().readuntil(separator)
            except asyncio.LimitOverrunError as e:
                if self._buffer.startswith(separator, e.consumed):
                    chunk = self._buffer[: e.consumed + len(separator)]
                    del self._buffer[: e.consumed + len(separator)]
                    self._maybe_resume_transport()
                    return bytes(chunk)
                await self._wait_for_data("readuntil")


class StandardStreamWriter(asyncio.StreamWriter):
    def __del__(self):
        # No `__del__` method for StreamWriter in Python 3.10 and before
        try:
            parent_del = super().__del__
        except AttributeError:
            return
        # Do not attempt to close the transport if the loop is closed
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        parent_del()

    def write(self, data):
        if isinstance(data, str):
            data = data.encode()
        super().write(data)


class NonFileStreamReader:
    def __init__(self, stream, *, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.stream = stream
        self.eof = False

    def at_eof(self):
        return self.eof

    async def readline(self):
        try:
            data = await run_as_daemon(self.stream.readline)
        except AttributeError:
            raise RuntimeError("ainput(): lost sys.stdin")
        if isinstance(data, str):
            data = data.encode()
        self.eof = not data
        return data

    async def read(self, n=-1):
        try:
            data = await run_as_daemon(self.stream.read, n)
        except AttributeError:
            raise RuntimeError("ainput(): lost sys.stdin")
        if isinstance(data, str):
            data = data.encode()
        self.eof = not data
        return data

    def __aiter__(self):
        return self

    async def __anext__(self):
        val = await self.readline()
        if val == b"":
            raise StopAsyncIteration
        return val


class NonFileStreamWriter:
    def __init__(self, stream, *, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.stream = stream
        self.buffer = deque()
        self.write_task = None
        self.task_finalizer = None

    def write(self, data):
        if self.stream is None:
            raise RuntimeError("This writer stream is already closed")
        if isinstance(data, bytes):
            data = data.decode()
        self.buffer.append(data)
        if self.write_task is not None and not self.write_task.done():
            return
        if self.write_task is not None and self.write_task.done():
            self.write_task = None
            self.task_finalizer()
        self.write_task = asyncio.ensure_future(
            _nonfile_stream_writer_task_target(self.buffer, self.stream)
        )
        self.task_finalizer = weakref.finalize(self, self.write_task.result)

    async def drain(self):
        if self.write_task is not None:
            try:
                await self.write_task
            finally:
                self.write_task = None
                self.task_finalizer.detach()

    def close(self):
        self.stream = None

    def is_closing(self):
        return self.stream is None and self.write_task is not None

    async def wait_closed(self):
        await self.drain()


async def _nonfile_stream_writer_task_target(data_buffer, stream):
    loop = asyncio.get_event_loop()
    while data_buffer:
        data = data_buffer.popleft()
        await loop.run_in_executor(None, stream.write, data)
    if hasattr(stream, "flush"):
        await loop.run_in_executor(None, stream.flush)


async def open_standard_pipe_connection(pipe_in, pipe_out, pipe_err, *, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()

    # Reader
    in_reader = StandardStreamReader(loop=loop)
    protocol = StandardStreamReaderProtocol(in_reader, loop=loop)
    await loop.connect_read_pipe(lambda: protocol, ProtectedPipe(pipe_in))

    # Out writer
    out_transport, _ = await loop.connect_write_pipe(
        lambda: protocol, ProtectedPipe(pipe_out)
    )
    out_writer = StandardStreamWriter(out_transport, protocol, in_reader, loop)

    # Err writer
    err_transport, _ = await loop.connect_write_pipe(
        lambda: protocol, ProtectedPipe(pipe_err)
    )
    err_writer = StandardStreamWriter(err_transport, protocol, in_reader, loop)

    # Set the write buffer limits to zero
    # This way, `await stream.drain()` can be used to make sure the buffer is flushed
    out_transport.set_write_buffer_limits(high=0, low=0)
    err_transport.set_write_buffer_limits(high=0, low=0)

    # Return
    return in_reader, out_writer, err_writer


async def create_standard_streams(stdin, stdout, stderr, *, loop=None):
    if all(map(is_pipe_transport_compatible, (stdin, stdout, stderr))):
        return await open_standard_pipe_connection(stdin, stdout, stderr, loop=loop)
    return (
        NonFileStreamReader(stdin, loop=loop),
        NonFileStreamWriter(stdout, loop=loop),
        NonFileStreamWriter(stderr, loop=loop),
    )


async def get_standard_streams(*, cache={}, use_stderr=False, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    args = sys.stdin, sys.stdout, sys.stderr
    key = args, loop
    if cache.get(key) is None:
        cache[key] = await create_standard_streams(*args, loop=loop)
    in_reader, out_writer, err_writer = cache[key]
    return in_reader, err_writer if use_stderr else out_writer


async def ainput(prompt="", *, streams=None, use_stderr=False, loop=None):
    """Asynchronous equivalent to *input*."""
    # Get standard streams
    if streams is None:
        streams = await get_standard_streams(use_stderr=use_stderr, loop=loop)
    reader, writer = streams
    # Write prompt
    writer.write(prompt.encode())
    await writer.drain()
    # Get data
    data = await reader.readline()
    # Decode data
    data = data.decode()
    # Return or raise EOF
    if not data.endswith("\n"):
        raise EOFError
    return data.rstrip("\n")


async def aprint(
    *values, sep=None, end="\n", flush=True, streams=None, use_stderr=False, loop=None
):
    """Asynchronous equivalent to *print*."""
    # Get standard streams
    if streams is None:
        streams = await get_standard_streams(use_stderr=use_stderr, loop=loop)
    _, writer = streams

    print(*values, sep=sep, end=end, flush=False, file=writer)

    if flush:
        await writer.drain()
