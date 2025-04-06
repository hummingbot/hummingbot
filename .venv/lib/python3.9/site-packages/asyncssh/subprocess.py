# Copyright (c) 2019-2023 by Ron Frederick <ronf@timeheart.net> and others.
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

"""SSH subprocess handlers"""

from typing import TYPE_CHECKING, Any, AnyStr, Callable
from typing import Dict, Generic, Iterable, Optional

from .constants import EXTENDED_DATA_STDERR
from .process import SSHClientProcess
from .session import DataType


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .channel import SSHChannel, SSHClientChannel


SubprocessFactory = Callable[[], 'SSHSubprocessProtocol']


class SSHSubprocessPipe(Generic[AnyStr]):
    """SSH subprocess pipe"""

    def __init__(self, chan: 'SSHClientChannel[AnyStr]',
                 datatype: DataType = None):
        self._chan: 'SSHClientChannel[AnyStr]' = chan
        self._datatype = datatype

    def close(self) -> None:
        """Shut down the remote process"""

        self._chan.close()

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        """Return additional information about the remote process

           This method returns extra information about the channel
           associated with this subprocess. See :meth:`get_extra_info()
           <SSHClientChannel.get_extra_info>` on :class:`SSHClientChannel`
           for additional information.

        """

        return self._chan.get_extra_info(name, default)


class SSHSubprocessReadPipe(SSHSubprocessPipe[AnyStr]):
    """SSH subprocess pipe reader"""

    def pause_reading(self) -> None:
        """Pause delivery of incoming data from the remote process"""

        self._chan.pause_reading()

    def resume_reading(self) -> None:
        """Resume delivery of incoming data from the remote process"""

        self._chan.resume_reading()


class SSHSubprocessWritePipe(SSHSubprocessPipe[AnyStr]):
    """SSH subprocess pipe writer"""

    def abort(self) -> None:
        """Forcibly close the channel to the remote process"""

        self._chan.abort()

    def can_write_eof(self) -> bool:
        """Return whether the pipe supports :meth:`write_eof`"""

        return self._chan.can_write_eof()

    def get_write_buffer_size(self) -> int:
        """Return the current size of the pipe's output buffer"""

        return self._chan.get_write_buffer_size()

    def set_write_buffer_limits(self, high: Optional[int] = None,
                                low: Optional[int] = None) -> None:
        """Set the high- and low-water limits for write flow control"""

        self._chan.set_write_buffer_limits(high, low)

    def write(self, data: AnyStr) -> None:
        """Write data on this pipe"""

        self._chan.write(data, self._datatype)

    def writelines(self, list_of_data: Iterable[AnyStr]) -> None:
        """Write a list of data bytes on this pipe"""

        self._chan.writelines(list_of_data, self._datatype)

    def write_eof(self) -> None:
        """Write EOF on this pipe"""

        self._chan.write_eof()


class SSHSubprocessProtocol(Generic[AnyStr]):
    """SSH subprocess protocol

       This class conforms to :class:`asyncio.SubprocessProtocol`, but with
       the following enhancement:

           * If encoding is set when the subprocess is created, all data
             passed to :meth:`pipe_data_received` will be string values
             containing Unicode data. However, for compatibility with
             :class:`asyncio.SubprocessProtocol`, encoding defaults to
             `None`, in which case all data is delivered as bytes.

    """

    def connection_made(self,
                        transport: 'SSHSubprocessTransport[AnyStr]') -> None:
        """Called when a remote process is successfully started

           This method is called when a remote process is successfully
           started. The transport parameter should be stored if needed
           for later use.

           :param transport:
               The transport to use to communicate with the remote process.
           :type transport: :class:`SSHSubprocessTransport`

        """

    def pipe_data_received(self, fd: int, data: AnyStr) -> None:
        """Called when data is received from the remote process

           This method is called when data is received from the remote
           process. If an encoding was specified when the process was
           started, the data will be delivered as a string after decoding
           with the requested encoding. Otherwise, the data will be
           delivered as bytes.

           :param fd:
               The integer file descriptor of the pipe data was received
               on. This will be 1 for stdout or 2 for stderr.
           :param data:
               The data received from the remote process
           :type fd: `int`
           :type data: `str` or `bytes`

        """

    def pipe_connection_lost(self, fd: int, exc: Optional[Exception]) -> None:
        """Called when the pipe to a remote process is closed

           This method is called when a pipe to a remote process is
           closed. If the channel is shut down cleanly, *exc* will be
           `None`. Otherwise, it will be an exception explaining the
           reason the pipe was closed.

           :param fd:
               The integer file descriptor of the pipe which was
               closed. This will be 1 for stdout or 2 for stderr.
           :param exc:
               The exception which caused the channel to close, or
               `None` if the channel closed cleanly.
           :type fd: `int`
           :type exc: :class:`Exception` or `None`

        """

    def process_exited(self) -> None:
        """Called when a remote process has exited

           This method is called when the remote process has exited.
           Exit status information can be retrieved by calling
           :meth:`get_returncode() <SSHSubprocessTransport.get_returncode>`
           on the transport provided in :meth:`connection_made`.

        """


class SSHSubprocessTransport(SSHClientProcess[AnyStr]):
    """SSH subprocess transport

       This class conforms to :class:`asyncio.SubprocessTransport`, but with
       the following enhancements:

           * All functionality available through :class:`SSHClientProcess`
             is also available here, such as the ability to dynamically
             redirect stdin, stdout, and stderr at any time during the
             lifetime of the process.

           * If encoding is set when the subprocess is created, all data
             written to the transports created by :meth:`get_pipe_transport`
             should be strings containing Unicode data. The encoding defaults
             to `None`, though, to preserve compatibility with
             :class:`asyncio.SubprocessTransport`, which expects data
             to be written as bytes.

    """

    _chan: 'SSHClientChannel[AnyStr]'

    def __init__(self, protocol_factory: SubprocessFactory):
        super().__init__()

        self._pipes: Dict[int, SSHSubprocessPipe[AnyStr]] = {}
        self._protocol: SSHSubprocessProtocol[AnyStr] = protocol_factory()

    def get_protocol(self) -> SSHSubprocessProtocol[AnyStr]:
        """Return the subprocess protocol associated with this transport"""

        return self._protocol

    def connection_made(self, chan: 'SSHChannel[AnyStr]') -> None:
        """Handle a newly opened channel"""

        super().connection_made(chan)

        self._protocol.connection_made(self)

        self._pipes = {
            0: SSHSubprocessWritePipe(self._chan),
            1: SSHSubprocessReadPipe(self._chan),
            2: SSHSubprocessReadPipe(self._chan, EXTENDED_DATA_STDERR)
        }

    def session_started(self) -> None:
        """Override SSHClientProcess to avoid creating SSHReader/SSHWriter
           streams, since this class uses read/write pipe objects instead"""

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle an incoming channel close"""

        self._protocol.pipe_connection_lost(1, exc)
        self._protocol.pipe_connection_lost(2, exc)
        super().connection_lost(exc)

    def data_received(self, data: AnyStr, datatype: DataType) -> None:
        """Handle incoming data from the remote process"""

        writer = self._writers.get(datatype)

        if writer:
            writer.write(data)
        else:
            fd = 2 if datatype == EXTENDED_DATA_STDERR else 1
            self._protocol.pipe_data_received(fd, data)

    def exit_status_received(self, status: int) -> None:
        """Handle exit status for the remote process"""

        super().exit_status_received(status)
        self._protocol.process_exited()

    def exit_signal_received(self, signal: str, core_dumped: bool,
                             msg: str, lang: str) -> None:
        """Handle exit signal for the remote process"""

        super().exit_signal_received(signal, core_dumped, msg, lang)
        self._protocol.process_exited()

    def get_pid(self) -> Optional[int]:
        """Return the PID of the remote process

           This method always returns `None`, since SSH doesn't report
           remote PIDs.

        """

        # pylint: disable=no-self-use

        return None

    def get_pipe_transport(self, fd: int) -> \
            Optional[SSHSubprocessPipe[AnyStr]]:
        """Return a transport for the requested stream

           :param fd:
               The integer file descriptor (0-2) to return the transport for,
               where 0 means stdin, 1 means stdout, and 2 means stderr.
           :type fd: `int`

           :returns: an :class:`SSHSubprocessReadPipe` or
                     :class:`SSHSubprocessWritePipe`

        """

        return self._pipes.get(fd)

    def get_returncode(self) -> Optional[int]:
        """Return the exit status or signal for the remote process

           This method returns the exit status of the session if one has
           been sent. If an exit signal was sent, this method returns
           the negative of the numeric value of that signal, matching
           the behavior of :meth:`asyncio.SubprocessTransport.get_returncode`.
           If neither has been sent, this method returns `None`.

           :returns: `int` or `None`

        """

        return self.returncode
