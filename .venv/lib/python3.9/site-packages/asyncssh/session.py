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

"""SSH session handlers"""

from typing import TYPE_CHECKING, Any, AnyStr, Callable, Generic
from typing import Mapping, Optional, Tuple


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .channel import SSHClientChannel, SSHServerChannel
    from .channel import SSHTCPChannel, SSHUNIXChannel,  SSHTunTapChannel

DataType = Optional[int]


class SSHSession(Generic[AnyStr]):
    """SSH session handler"""

    # pylint: disable=no-self-use,unused-argument

    def connection_made(self, chan: Any) -> None:
        """Called when a channel is opened successfully"""

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when a channel is closed

           This method is called when a channel is closed. If the channel
           is shut down cleanly, *exc* will be `None`. Otherwise, it
           will be an exception explaining the reason for the channel close.

           :param exc:
               The exception which caused the channel to close, or
               `None` if the channel closed cleanly.
           :type exc: :class:`Exception`

        """

    def session_started(self) -> None:
        """Called when the session is started

           This method is called when a session has started up. For
           client and server sessions, this will be called once a
           shell, exec, or subsystem request has been successfully
           completed. For TCP and UNIX domain socket sessions, it will
           be called immediately after the connection is opened.

        """

    def data_received(self, data: AnyStr, datatype: DataType) -> None:
        """Called when data is received on the channel

           This method is called when data is received on the channel.
           If an encoding was specified when the channel was created,
           the data will be delivered as a string after decoding with
           the requested encoding. Otherwise, the data will be delivered
           as bytes.

           :param data:
               The data received on the channel
           :param datatype:
               The extended data type of the data, from :ref:`extended
               data types <ExtendedDataTypes>`
           :type data: `str` or `bytes`

        """

    def eof_received(self) -> bool:
        """Called when EOF is received on the channel

           This method is called when an end-of-file indication is received
           on the channel, after which no more data will be received. If this
           method returns `True`, the channel remains half open and data
           may still be sent. Otherwise, the channel is automatically closed
           after this method returns. This is the default behavior for
           classes derived directly from :class:`SSHSession`, but not when
           using the higher-level streams API. Because input is buffered
           in that case, streaming sessions enable half-open channels to
           allow applications to respond to input read after an end-of-file
           indication is received.

        """

        return False # pragma: no cover

    def pause_writing(self) -> None:
        """Called when the write buffer becomes full

           This method is called when the channel's write buffer becomes
           full and no more data can be sent until the remote system
           adjusts its window. While data can still be buffered locally,
           applications may wish to stop producing new data until the
           write buffer has drained.

        """

    def resume_writing(self) -> None:
        """Called when the write buffer has sufficiently drained

           This method is called when the channel's send window reopens
           and enough data has drained from the write buffer to allow the
           application to produce more data.

        """


class SSHClientSession(SSHSession[AnyStr]):
    """SSH client session handler

       Applications should subclass this when implementing an SSH client
       session handler. The functions listed below should be implemented
       to define application-specific behavior. In particular, the standard
       `asyncio` protocol methods such as :meth:`connection_made`,
       :meth:`connection_lost`, :meth:`data_received`, :meth:`eof_received`,
       :meth:`pause_writing`, and :meth:`resume_writing` are all supported.
       In addition, :meth:`session_started` is called as soon as the SSH
       session is fully started, :meth:`xon_xoff_requested` can be used to
       determine if the server wants the client to support XON/XOFF flow
       control, and :meth:`exit_status_received` and
       :meth:`exit_signal_received` can be used to receive session exit
       information.

    """

    # pylint: disable=no-self-use,unused-argument

    def connection_made(self, chan: 'SSHClientChannel[AnyStr]') -> None:
        """Called when a channel is opened successfully

           This method is called when a channel is opened successfully. The
           channel parameter should be stored if needed for later use.

           :param chan:
               The channel which was successfully opened.
           :type chan: :class:`SSHClientChannel`

        """

    def xon_xoff_requested(self, client_can_do: bool) -> None:
        """XON/XOFF flow control has been enabled or disabled

           This method is called to notify the client whether or not
           to enable XON/XOFF flow control. If client_can_do is
           `True` and output is being sent to an interactive
           terminal the application should allow input of Control-S
           and Control-Q to pause and resume output, respectively.
           If client_can_do is `False`, Control-S and Control-Q
           should be treated as normal input and passed through to
           the server. Non-interactive applications can ignore this
           request.

           By default, this message is ignored.

           :param client_can_do:
               Whether or not to enable XON/XOFF flow control
           :type client_can_do: `bool`

        """

    def exit_status_received(self, status: int) -> None:
        """A remote exit status has been received for this session

           This method is called when the shell, command, or subsystem
           running on the server terminates and returns an exit status.
           A zero exit status generally means that the operation was
           successful. This call will generally be followed by a call
           to :meth:`connection_lost`.

           By default, the exit status is ignored.

           :param status:
               The exit status returned by the remote process
           :type status: `int`

        """

    def exit_signal_received(self, signal: str, core_dumped: bool,
                             msg: str, lang: str) -> None:
        """A remote exit signal has been received for this session

           This method is called when the shell, command, or subsystem
           running on the server terminates abnormally with a signal.
           A more detailed error may also be provided, along with an
           indication of whether the remote process dumped core. This call
           will generally be followed by a call to :meth:`connection_lost`.

           By default, exit signals are ignored.

           :param signal:
               The signal which caused the remote process to exit
           :param core_dumped:
               Whether or not the remote process dumped core
           :param msg:
               Details about what error occurred
           :param lang:
               The language the error message is in
           :type signal: `str`
           :type core_dumped: `bool`
           :type msg: `str`
           :type lang: `str`

        """


class SSHServerSession(SSHSession[AnyStr]):
    """SSH server session handler

       Applications should subclass this when implementing an SSH server
       session handler. The functions listed below should be implemented
       to define application-specific behavior. In particular, the
       standard `asyncio` protocol methods such as :meth:`connection_made`,
       :meth:`connection_lost`, :meth:`data_received`, :meth:`eof_received`,
       :meth:`pause_writing`, and :meth:`resume_writing` are all supported.
       In addition, :meth:`pty_requested` is called when the client requests a
       pseudo-terminal, one of :meth:`shell_requested`, :meth:`exec_requested`,
       or :meth:`subsystem_requested` is called depending on what type of
       session the client wants to start, :meth:`session_started` is called
       once the SSH session is fully started, :meth:`terminal_size_changed` is
       called when the client's terminal size changes, :meth:`signal_received`
       is called when the client sends a signal, and :meth:`break_received`
       is called when the client sends a break.

    """

    # pylint: disable=no-self-use,unused-argument

    def connection_made(self, chan: 'SSHServerChannel[AnyStr]') -> None:
        """Called when a channel is opened successfully

           This method is called when a channel is opened successfully. The
           channel parameter should be stored if needed for later use.

           :param chan:
               The channel which was successfully opened.
           :type chan: :class:`SSHServerChannel`

        """

    def pty_requested(self, term_type: str,
                      term_size: Tuple[int, int, int, int],
                      term_modes: Mapping[int, int]) -> bool:
        """A pseudo-terminal has been requested

           This method is called when the client sends a request to allocate
           a pseudo-terminal with the requested terminal type, size, and
           POSIX terminal modes. This method should return `True` if the
           request for the pseudo-terminal is accepted. Otherwise, it should
           return `False` to reject the request.

           By default, requests to allocate a pseudo-terminal are accepted
           but nothing is done with the associated terminal information.
           Applications wishing to use this information should implement
           this method and have it return `True`, or call
           :meth:`get_terminal_type() <SSHServerChannel.get_terminal_type>`,
           :meth:`get_terminal_size() <SSHServerChannel.get_terminal_size>`,
           or :meth:`get_terminal_mode() <SSHServerChannel.get_terminal_mode>`
           on the :class:`SSHServerChannel` to get the information they need
           after a shell, command, or subsystem is started.

           :param term_type:
               Terminal type to set for this session
           :param term_size:
               Terminal size to set for this session provided as a
               tuple of four `int` values: the width and height of the
               terminal in characters followed by the width and height
               of the terminal in pixels
           :param term_modes:
               POSIX terminal modes to set for this session, where keys
               are taken from :ref:`POSIX terminal modes <PTYModes>` with
               values defined in section 8 of :rfc:`RFC 4254 <4254#section-8>`.
           :type term_type: `str`
           :type term_size: tuple of 4 `int` values
           :type term_modes: `dict`

           :returns: A `bool` indicating if the request for a
                     pseudo-terminal was allowed or not

        """

        return True # pragma: no cover

    def terminal_size_changed(self, width: int, height: int,
                              pixwidth: int, pixheight: int) -> None:
        """The terminal size has changed

           This method is called when a client requests a
           pseudo-terminal and again whenever the the size of
           he client's terminal window changes.

           By default, this information is ignored, but applications
           wishing to use the terminal size can implement this method
           to get notified whenever it changes.

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

        """

    def shell_requested(self) -> bool:
        """The client has requested a shell

           This method should be implemented by the application to
           perform whatever processing is required when a client makes
           a request to open an interactive shell. It should return
           `True` to accept the request, or `False` to reject it.

           If the application returns `True`, the :meth:`session_started`
           method will be called once the channel is fully open. No output
           should be sent until this method is called.

           By default this method returns `False` to reject all requests.

           :returns: A `bool` indicating if the shell request was
                     allowed or not

        """

        return False # pragma: no cover

    def exec_requested(self, command: str) -> bool:
        """The client has requested to execute a command

           This method should be implemented by the application to
           perform whatever processing is required when a client makes
           a request to execute a command. It should return `True` to
           accept the request, or `False` to reject it.

           If the application returns `True`, the :meth:`session_started`
           method will be called once the channel is fully open. No output
           should be sent until this method is called.

           By default this method returns `False` to reject all requests.

           :param command:
               The command the client has requested to execute
           :type command: `str`

           :returns: A `bool` indicating if the exec request was
                     allowed or not

        """

        return False # pragma: no cover

    def subsystem_requested(self, subsystem: str) -> bool:
        """The client has requested to start a subsystem

           This method should be implemented by the application to
           perform whatever processing is required when a client makes
           a request to start a subsystem. It should return `True` to
           accept the request, or `False` to reject it.

           If the application returns `True`, the :meth:`session_started`
           method will be called once the channel is fully open. No output
           should be sent until this method is called.

           By default this method returns `False` to reject all requests.

           :param subsystem:
               The subsystem to start
           :type subsystem: `str`

           :returns: A `bool` indicating if the request to open the
                     subsystem was allowed or not

        """

        return False # pragma: no cover

    def break_received(self, msec: int) -> bool:
        """The client has sent a break

           This method is called when the client requests that the
           server perform a break operation on the terminal. If the
           break is performed, this method should return `True`.
           Otherwise, it should return `False`.

           By default, this method returns `False` indicating that
           no break was performed.

           :param msec:
               The duration of the break in milliseconds
           :type msec: `int`

           :returns: A `bool` to indicate if the break operation was
                     performed or not

        """

        return False # pragma: no cover

    def signal_received(self, signal: str) -> None:
        """The client has sent a signal

           This method is called when the client delivers a signal
           on the channel.

           By default, signals from the client are ignored.

           :param signal:
               The name of the signal received
           :type signal: `str`

        """

    def soft_eof_received(self) -> None:
        """The client has sent a soft EOF

           This method is called by the line editor when the client
           send a soft EOF (Ctrl-D on an empty input line).

           By default, soft EOF will trigger an EOF to an outstanding
           read call but still allow additional input to be received
           from the client after that.

        """


class SSHTCPSession(SSHSession[AnyStr]):
    """SSH TCP session handler

       Applications should subclass this when implementing a handler for
       SSH direct or forwarded TCP connections.

       SSH client applications wishing to open a direct connection should call
       :meth:`create_connection() <SSHClientConnection.create_connection>`
       on their :class:`SSHClientConnection`, passing in a factory which
       returns instances of this class.

       Server applications wishing to allow direct connections should
       implement the coroutine :meth:`connection_requested()
       <SSHServer.connection_requested>` on their :class:`SSHServer`
       object and have it return instances of this class.

       Server applications wishing to allow connection forwarding back
       to the client should implement the coroutine :meth:`server_requested()
       <SSHServer.server_requested>` on their :class:`SSHServer` object
       and call :meth:`create_connection()
       <SSHServerConnection.create_connection>` on their
       :class:`SSHServerConnection` for each new connection, passing it a
       factory which returns instances of this class.

       When a connection is successfully opened, :meth:`session_started`
       will be called, after which the application can begin sending data.
       Received data will be passed to the :meth:`data_received` method.

    """

    def connection_made(self, chan: 'SSHTCPChannel[AnyStr]') -> None:
        """Called when a channel is opened successfully

           This method is called when a channel is opened successfully. The
           channel parameter should be stored if needed for later use.

           :param chan:
               The channel which was successfully opened.
           :type chan: :class:`SSHTCPChannel`

        """


class SSHUNIXSession(SSHSession[AnyStr]):
    """SSH UNIX domain socket session handler

       Applications should subclass this when implementing a handler for
       SSH direct or forwarded UNIX domain socket connections.

       SSH client applications wishing to open a direct connection should call
       :meth:`create_unix_connection()
       <SSHClientConnection.create_unix_connection>` on their
       :class:`SSHClientConnection`, passing in a factory which returns
       instances of this class.

       Server applications wishing to allow direct connections should
       implement the coroutine :meth:`unix_connection_requested()
       <SSHServer.unix_connection_requested>` on their :class:`SSHServer`
       object and have it return instances of this class.

       Server applications wishing to allow connection forwarding back
       to the client should implement the coroutine
       :meth:`unix_server_requested() <SSHServer.unix_server_requested>`
       on their :class:`SSHServer` object and call
       :meth:`create_unix_connection()
       <SSHServerConnection.create_unix_connection>` on their
       :class:`SSHServerConnection` for each new connection, passing it a
       factory which returns instances of this class.

       When a connection is successfully opened, :meth:`session_started`
       will be called, after which the application can begin sending data.
       Received data will be passed to the :meth:`data_received` method.

    """

    def connection_made(self, chan: 'SSHUNIXChannel[AnyStr]') -> None:
        """Called when a channel is opened successfully

           This method is called when a channel is opened successfully. The
           channel parameter should be stored if needed for later use.

           :param chan:
               The channel which was successfully opened.
           :type chan: :class:`SSHUNIXChannel`

        """


class SSHTunTapSession(SSHSession[bytes]):
    """SSH TUN/TAP session handler

       Applications should subclass this when implementing a handler for
       SSH TUN/TAP tunnels.

       SSH client applications wishing to open a tunnel should call
       :meth:`create_tun() <SSHClientConnection.create_tun>` or
       :meth:`create_tap() <SSHClientConnection.create_tap>` on their
       :class:`SSHClientConnection`, passing in a factory which returns
       instances of this class.

       Server applications wishing to allow tunnel connections should
       implement the coroutine :meth:`tun_requested()
       <SSHServer.tun_requested>` or :meth:`tap_requested()
       <SSHServer.tap_requested>` on their :class:`SSHServer` object
       and have it return instances of this class.

       When a connection is successfully opened, :meth:`session_started`
       will be called, after which the application can begin sending data.
       Received data will be passed to the :meth:`data_received` method.

    """

    def connection_made(self, chan: 'SSHTunTapChannel') -> None:
        """Called when a channel is opened successfully

           This method is called when a channel is opened successfully. The
           channel parameter should be stored if needed for later use.

           :param chan:
               The channel which was successfully opened.
           :type chan: :class:`SSHTunTapChannel`

        """


SSHSessionFactory = Callable[[], SSHSession[AnyStr]]
SSHClientSessionFactory = Callable[[], SSHClientSession[AnyStr]]
SSHTCPSessionFactory = Callable[[], SSHTCPSession[AnyStr]]
SSHUNIXSessionFactory = Callable[[], SSHUNIXSession[AnyStr]]
SSHTunTapSessionFactory = Callable[[], SSHTunTapSession]
