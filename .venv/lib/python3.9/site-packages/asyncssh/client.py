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

"""SSH client protocol handler"""

from typing import TYPE_CHECKING, Optional

from .auth import KbdIntPrompts, KbdIntResponse, PasswordChangeResponse
from .misc import MaybeAwait
from .public_key import KeyPairListArg, SSHKey


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .connection import SSHClientConnection


class SSHClient:
    """SSH client protocol handler

       Applications may subclass this when implementing an SSH client
       to receive callbacks when certain events occur on the SSH
       connection.

       Whenever a new SSH client connection is opened, a corresponding
       SSHClient object is created and the method :meth:`connection_made`
       is called, passing in the :class:`SSHClientConnection` object.

       When the connection is closed, the method :meth:`connection_lost`
       is called with an exception representing the reason for the
       disconnect, or `None` if the connection was closed cleanly.

       For simple password or public key based authentication, nothing
       needs to be defined here if the password or client keys are passed
       in when the connection is created. However, to prompt interactively
       or otherwise dynamically select these values, the methods
       :meth:`password_auth_requested` and/or :meth:`public_key_auth_requested`
       can be defined. Keyboard-interactive authentication is also supported
       via :meth:`kbdint_auth_requested` and :meth:`kbdint_challenge_received`.

       If the server sends an authentication banner, the method
       :meth:`auth_banner_received` will be called.

       If the server requires a password change, the method
       :meth:`password_change_requested` will be called, followed by either
       :meth:`password_changed` or :meth:`password_change_failed` depending
       on whether the password change is successful.

       .. note:: The authentication callbacks described here can be
                 defined as coroutines. However, they may be cancelled if
                 they are running when the SSH connection is closed by
                 the server. If they attempt to catch the CancelledError
                 exception to perform cleanup, they should make sure to
                 re-raise it to allow AsyncSSH to finish its own cleanup.

    """

    # pylint: disable=no-self-use,unused-argument

    def connection_made(self, conn: 'SSHClientConnection') -> None:
        """Called when a connection is made

           This method is called as soon as the TCP connection completes.
           The `conn` parameter should be stored if needed for later use.

           :param conn:
               The connection which was successfully opened
           :type conn: :class:`SSHClientConnection`

        """

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when a connection is lost or closed

           This method is called when a connection is closed. If the
           connection is shut down cleanly, *exc* will be `None`.
           Otherwise, it will be an exception explaining the reason for
           the disconnect.

           :param exc:
               The exception which caused the connection to close, or
               `None` if the connection closed cleanly
           :type exc: :class:`Exception`

        """

    def debug_msg_received(self, msg: str, lang: str,
                           always_display: bool) -> None:
        """A debug message was received on this connection

           This method is called when the other end of the connection sends
           a debug message. Applications should implement this method if
           they wish to process these debug messages.

           :param msg:
               The debug message sent
           :param lang:
               The language the message is in
           :param always_display:
               Whether or not to display the message
           :type msg: `str`
           :type lang: `str`
           :type always_display: `bool`

        """

    def validate_host_public_key(self, host: str, addr: str,
                                 port: int, key: SSHKey) -> bool:
        """Return whether key is an authorized key for this host

           Server host key validation can be supported by passing known
           host keys in the `known_hosts` argument of
           :func:`create_connection`. However, for more flexibility
           in matching on the allowed set of keys, this method can be
           implemented by the application to do the matching itself. It
           should return `True` if the specified key is a valid host key
           for the server being connected to.

           By default, this method returns `False` for all host keys.

               .. note:: This function only needs to report whether the
                         public key provided is a valid key for this
                         host. If it is, AsyncSSH will verify that the
                         server possesses the corresponding private key
                         before allowing the validation to succeed.

           :param host:
               The hostname of the target host
           :param addr:
               The IP address of the target host
           :param port:
               The port number on the target host
           :param key:
               The public key sent by the server
           :type host: `str`
           :type addr: `str`
           :type port: `int`
           :type key: :class:`SSHKey` *public key*

           :returns: A `bool` indicating if the specified key is a valid
                     key for the target host

        """

        return False # pragma: no cover

    def validate_host_ca_key(self, host: str, addr: str,
                             port: int, key: SSHKey) -> bool:
        """Return whether key is an authorized CA key for this host

           Server host certificate validation can be supported by passing
           known host CA keys in the `known_hosts` argument of
           :func:`create_connection`. However, for more flexibility
           in matching on the allowed set of keys, this method can be
           implemented by the application to do the matching itself. It
           should return `True` if the specified key is a valid certificate
           authority key for the server being connected to.

           By default, this method returns `False` for all CA keys.

               .. note:: This function only needs to report whether the
                         public key provided is a valid CA key for this
                         host. If it is, AsyncSSH will verify that the
                         certificate is valid, that the host is one of
                         the valid principals for the certificate, and
                         that the server possesses the private key
                         corresponding to the public key in the certificate
                         before allowing the validation to succeed.

           :param host:
               The hostname of the target host
           :param addr:
               The IP address of the target host
           :param port:
               The port number on the target host
           :param key:
               The public key which signed the certificate sent by the server
           :type host: `str`
           :type addr: `str`
           :type port: `int`
           :type key: :class:`SSHKey` *public key*

           :returns: A `bool` indicating if the specified key is a valid
                     CA key for the target host

        """

        return False # pragma: no cover

    def auth_banner_received(self, msg: str, lang: str) -> None:
        """An incoming authentication banner was received

           This method is called when the server sends a banner to display
           during authentication. Applications should implement this method
           if they wish to do something with the banner.

           :param msg:
               The message the server wanted to display
           :param lang:
               The language the message is in
           :type msg: `str`
           :type lang: `str`

        """

    def begin_auth(self, username: str) -> None:
        """Begin client authentication

           This method is called when client authentication is about to
           begin, Applications may store the username passed here to
           be used in future authentication callbacks.

        """

    def auth_completed(self) -> None:
        """Authentication was completed successfully

           This method is called when authentication has completed
           successfully. Applications may use this method to create
           whatever client sessions and direct TCP/IP or UNIX domain
           connections are needed and/or set up listeners for incoming
           TCP/IP or UNIX domain connections coming from the server.
           However, :func:`create_connection` now blocks until
           authentication is complete, so any code which wishes to
           use the SSH connection can simply follow that call and
           doesn't need to be performed in a callback.

        """

    def public_key_auth_requested(self) -> \
            MaybeAwait[Optional[KeyPairListArg]]:
        """Public key authentication has been requested

           This method should return a private key corresponding to
           the user that authentication is being attempted for.

           This method may be called multiple times and can return a
           different key to try each time it is called. When there are
           no keys left to try, it should return `None` to indicate
           that some other authentication method should be tried.

           If client keys were provided when the connection was opened,
           they will be tried before this method is called.

           If blocking operations need to be performed to determine the
           key to authenticate with, this method may be defined as a
           coroutine.

           :returns: A key as described in :ref:`SpecifyingPrivateKeys`
                     or `None` to move on to another authentication
                     method

        """

        return None # pragma: no cover

    def password_auth_requested(self) -> MaybeAwait[Optional[str]]:
        """Password authentication has been requested

           This method should return a string containing the password
           corresponding to the user that authentication is being
           attempted for. It may be called multiple times and can
           return a different password to try each time, but most
           servers have a limit on the number of attempts allowed.
           When there's no password left to try, this method should
           return `None` to indicate that some other authentication
           method should be tried.

           If a password was provided when the connection was opened,
           it will be tried before this method is called.

           If blocking operations need to be performed to determine the
           password to authenticate with, this method may be defined as
           a coroutine.

           :returns: A string containing the password to authenticate
                     with or `None` to move on to another authentication
                     method

        """

        return None # pragma: no cover

    def password_change_requested(self, prompt: str, lang: str) -> \
            MaybeAwait[PasswordChangeResponse]:
        """A password change has been requested

           This method is called when password authentication was
           attempted and the user's password was expired on the
           server. To request a password change, this method should
           return a tuple or two strings containing the old and new
           passwords. Otherwise, it should return `NotImplemented`.

           If blocking operations need to be performed to determine the
           passwords to authenticate with, this method may be defined
           as a coroutine.

           By default, this method returns `NotImplemented`.

           :param prompt:
               The prompt requesting that the user enter a new password
           :param lang:
               The language that the prompt is in
           :type prompt: `str`
           :type lang: `str`

           :returns: A tuple of two strings containing the old and new
                     passwords or `NotImplemented` if password changes
                     aren't supported

        """

        return NotImplemented # pragma: no cover

    def password_changed(self) -> None:
        """The requested password change was successful

           This method is called to indicate that a requested password
           change was successful. It is generally followed by a call to
           :meth:`auth_completed` since this means authentication was
           also successful.

        """

    def password_change_failed(self) -> None:
        """The requested password change has failed

           This method is called to indicate that a requested password
           change failed, generally because the requested new password
           doesn't meet the password criteria on the remote system.
           After this method is called, other forms of authentication
           will automatically be attempted.

        """

    def kbdint_auth_requested(self) -> MaybeAwait[Optional[str]]:
        """Keyboard-interactive authentication has been requested

           This method should return a string containing a comma-separated
           list of submethods that the server should use for
           keyboard-interactive authentication. An empty string can be
           returned to let the server pick the type of keyboard-interactive
           authentication to perform. If keyboard-interactive authentication
           is not supported, `None` should be returned.

           By default, keyboard-interactive authentication is supported
           if a password was provided when the :class:`SSHClient` was
           created and it hasn't been sent yet. If the challenge is not
           a password challenge, this authentication will fail. This
           method and the :meth:`kbdint_challenge_received` method can be
           overridden if other forms of challenge should be supported.

           If blocking operations need to be performed to determine the
           submethods to request, this method may be defined as a
           coroutine.

           :returns: A string containing the submethods the server should
                     use for authentication or `None` to move on to
                     another authentication method

        """

        return NotImplemented # pragma: no cover

    def kbdint_challenge_received(self, name: str, instructions: str,
                                  lang: str, prompts: KbdIntPrompts) -> \
            MaybeAwait[Optional[KbdIntResponse]]:
        """A keyboard-interactive auth challenge has been received

           This method is called when the server sends a keyboard-interactive
           authentication challenge.

           The return value should be a list of strings of the same length
           as the number of prompts provided if the challenge can be
           answered, or `None` to indicate that some other form of
           authentication should be attempted.

           If blocking operations need to be performed to determine the
           responses to authenticate with, this method may be defined
           as a coroutine.

           By default, this method will look for a challenge consisting
           of a single 'Password:' prompt, and call the method
           :meth:`password_auth_requested` to provide the response.
           It will also ignore challenges with no prompts (generally used
           to provide instructions). Any other form of challenge will
           cause this method to return `None` to move on to another
           authentication method.

           :param name:
               The name of the challenge
           :param instructions:
               Instructions to the user about how to respond to the challenge
           :param lang:
               The language the challenge is in
           :param prompts:
               The challenges the user should respond to and whether or
               not the responses should be echoed when they are entered
           :type name: `str`
           :type instructions: `str`
           :type lang: `str`
           :type prompts: `list` of tuples of `str` and `bool`

           :returns: List of string responses to the challenge or `None`
                     to move on to another authentication method

        """

        return None # pragma: no cover
