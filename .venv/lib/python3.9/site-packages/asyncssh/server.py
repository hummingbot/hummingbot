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

"""SSH server protocol handler"""

from typing import TYPE_CHECKING, Optional, Tuple, Union

from .auth import KbdIntChallenge, KbdIntResponse
from .listener import SSHListener
from .misc import MaybeAwait
from .public_key import SSHKey
from .stream import SSHSocketSessionFactory, SSHServerSessionFactory


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .connection import SSHServerConnection, SSHAcceptHandler
    from .channel import SSHServerChannel, SSHTCPChannel, SSHUNIXChannel
    from .channel import SSHTunTapChannel
    from .session import SSHServerSession, SSHTCPSession, SSHUNIXSession
    from .session import SSHTunTapSession


_NewSession = Union[bool, 'SSHServerSession', SSHServerSessionFactory,
                    Tuple['SSHServerChannel', 'SSHServerSession'],
                    Tuple['SSHServerChannel', SSHServerSessionFactory]]
_NewTCPSession = Union[bool, 'SSHTCPSession', SSHSocketSessionFactory,
                       Tuple['SSHTCPChannel', 'SSHTCPSession'],
                       Tuple['SSHTCPChannel', SSHSocketSessionFactory]]
_NewUNIXSession = Union[bool, 'SSHUNIXSession', SSHSocketSessionFactory,
                        Tuple['SSHUNIXChannel', 'SSHUNIXSession'],
                        Tuple['SSHUNIXChannel', SSHSocketSessionFactory]]
_NewTunTapSession = Union[bool, 'SSHTunTapSession', SSHSocketSessionFactory,
                          Tuple['SSHTunTapChannel', 'SSHTunTapSession'],
                          Tuple['SSHTunTapChannel', SSHSocketSessionFactory]]
_NewListener = Union[bool, 'SSHAcceptHandler', SSHListener]


class SSHServer:
    """SSH server protocol handler

       Applications may subclass this when implementing an SSH server to
       provide custom authentication and request handlers.

       Whenever a new SSH server connection is accepted, a corresponding
       SSHServer object is created and the method :meth:`connection_made`
       is called, passing in the :class:`SSHServerConnection` object.

       When the connection is closed, the method :meth:`connection_lost`
       is called with an exception representing the reason for the
       disconnect, or `None` if the connection was closed cleanly.

       The method :meth:`begin_auth` can be overridden decide whether
       or not authentication is required, and additional callbacks are
       provided for each form of authentication in cases where authentication
       information is not provided in the call to :func:`create_server`.

       In addition, the methods :meth:`session_requested`,
       :meth:`connection_requested`, :meth:`server_requested`,
       :meth:`unix_connection_requested`, or :meth:`unix_server_requested`
       can be overridden to handle requests to open sessions or direct
       connections or set up listeners for forwarded connections.

       .. note:: The authentication callbacks described here can be
                 defined as coroutines. However, they may be cancelled if
                 they are running when the SSH connection is closed by
                 the client. If they attempt to catch the CancelledError
                 exception to perform cleanup, they should make sure to
                 re-raise it to allow AsyncSSH to finish its own cleanup.

    """

    # pylint: disable=no-self-use,unused-argument

    def connection_made(self, conn: 'SSHServerConnection') -> None:
        """Called when a connection is made

           This method is called when a new TCP connection is accepted. The
           `conn` parameter should be stored if needed for later use.

           :param conn:
               The connection which was successfully opened
           :type conn: :class:`SSHServerConnection`

        """

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when a connection is lost or closed

           This method is called when a connection is closed. If the
           connection is shut down cleanly, *exc* will be `None`.
           Otherwise, it will be an exception explaining the reason for
           the disconnect.

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

    def begin_auth(self, username: str) -> MaybeAwait[bool]:
        """Authentication has been requested by the client

           This method will be called when authentication is attempted for
           the specified user. Applications should use this method to
           prepare whatever state they need to complete the authentication,
           such as loading in the set of authorized keys for that user. If
           no authentication is required for this user, this method should
           return `False` to cause the authentication to immediately
           succeed. Otherwise, it should return `True` to indicate that
           authentication should proceed.

           If blocking operations need to be performed to prepare the
           state needed to complete the authentication, this method may
           be defined as a coroutine.

           :param username:
               The name of the user being authenticated
           :type username: `str`

           :returns: A `bool` indicating whether authentication is required

        """

        return True # pragma: no cover

    def auth_completed(self) -> None:
        """Authentication was completed successfully

           This method is called when authentication has completed
           successfully. Applications may use this method to perform
           processing based on the authenticated username or options in
           the authorized keys list or certificate associated with the
           user before any sessions are opened or forwarding requests
           are handled.

        """

    def validate_gss_principal(self, username: str, user_principal: str,
                               host_principal: str) -> MaybeAwait[bool]:
        """Return whether a GSS principal is valid for this user

           This method should return `True` if the specified user
           principal is valid for the user being authenticated. It can
           be overridden by applications wishing to perform their own
           authentication.

           If blocking operations need to be performed to determine the
           validity of the principal, this method may be defined as a
           coroutine.

           By default, this method will return `True` only when the
           name in the user principal exactly matches the username and
           the domain of the user principal matches the domain of the
           host principal.

           :param username:
               The user being authenticated
           :param user_principal:
               The user principal sent by the client
           :param host_principal:
               The host principal sent by the server
           :type username: `str`
           :type user_principal: `str`
           :type host_principal: `str`

           :returns: A `bool` indicating if the specified user principal
                     is valid for the user being authenticated

        """

        host_domain = host_principal.rsplit('@')[-1]
        return user_principal == username + '@' + host_domain

    def host_based_auth_supported(self) -> bool:
        """Return whether or not host-based authentication is supported

           This method should return `True` if client host-based
           authentication is supported. Applications wishing to support
           it must have this method return `True` and implement
           :meth:`validate_host_public_key` and/or :meth:`validate_host_ca_key`
           to return whether or not the key provided by the client is valid
           for the client host being authenticated.

           By default, it returns `False` indicating the client host
           based authentication is not supported.

           :returns: A `bool` indicating if host-based authentication is
                     supported or not

        """

        return False # pragma: no cover

    def validate_host_public_key(self, client_host: str, client_addr: str,
                                 client_port: int, key: SSHKey) -> bool:
        """Return whether key is an authorized host key for this client host

           Host key based client authentication can be supported by
           passing authorized host keys in the `known_client_hosts`
           argument of :func:`create_server`. However, for more flexibility
           in matching on the allowed set of keys, this method can be
           implemented by the application to do the matching itself. It
           should return `True` if the specified key is a valid host key
           for the client host being authenticated.

           This method may be called multiple times with different keys
           provided by the client. Applications should precompute as
           much as possible in the :meth:`begin_auth` method so that
           this function can quickly return whether the key provided is
           in the list.

           By default, this method returns `False` for all client host keys.

               .. note:: This function only needs to report whether the
                         public key provided is a valid key for this client
                         host. If it is, AsyncSSH will verify that the
                         client possesses the corresponding private key
                         before allowing the authentication to succeed.

           :param client_host:
               The hostname of the client host
           :param client_addr:
               The IP address of the client host
           :param client_port:
               The port number on the client host
           :param key:
               The host public key sent by the client
           :type client_host: `str`
           :type client_addr: `str`
           :type client_port: `int`
           :type key: :class:`SSHKey` *public key*

           :returns: A `bool` indicating if the specified key is a valid
                     key for the client host being authenticated

        """

        return False # pragma: no cover

    def validate_host_ca_key(self, client_host: str, client_addr: str,
                             client_port: int, key: SSHKey) -> bool:
        """Return whether key is an authorized CA key for this client host

           Certificate based client host authentication can be
           supported by passing authorized host CA keys in the
           `known_client_hosts` argument of :func:`create_server`.
           However, for more flexibility in matching on the allowed
           set of keys, this method can be implemented by the application
           to do the matching itself. It should return `True` if the
           specified key is a valid certificate authority key for the
           client host being authenticated.

           This method may be called multiple times with different keys
           provided by the client. Applications should precompute as
           much as possible in the :meth:`begin_auth` method so that
           this function can quickly return whether the key provided is
           in the list.

           By default, this method returns `False` for all CA keys.

               .. note:: This function only needs to report whether the
                         public key provided is a valid CA key for this
                         client host. If it is, AsyncSSH will verify that
                         the certificate is valid, that the client host is
                         one of the valid principals for the certificate,
                         and that the client possesses the private key
                         corresponding to the public key in the certificate
                         before allowing the authentication to succeed.

           :param client_host:
               The hostname of the client host
           :param client_addr:
               The IP address of the client host
           :param client_port:
               The port number on the client host
           :param key:
               The public key which signed the certificate sent by the client
           :type client_host: `str`
           :type client_addr: `str`
           :type client_port: `int`
           :type key: :class:`SSHKey` *public key*

           :returns: A `bool` indicating if the specified key is a valid
                     CA key for the client host being authenticated

        """

        return False # pragma: no cover

    def validate_host_based_user(self, username: str, client_host: str,
                                 client_username: str) -> MaybeAwait[bool]:
        """Return whether remote host and user is authorized for this user

           This method should return `True` if the specified client host
           and user is valid for the user being authenticated. It can be
           overridden by applications wishing to enforce restrictions on
           which remote users are allowed to authenticate as particular
           local users.

           If blocking operations need to be performed to determine the
           validity of the client host and user, this method may be defined
           as a coroutine.

           By default, this method will return `True` when the client
           username matches the name of the user being authenticated.

           :param username:
               The user being authenticated
           :param client_host:
               The hostname of the client host making the request
           :param client_username:
               The username of the user on the client host
           :type username: `str`
           :type client_host: `str`
           :type client_username: `str`

           :returns: A `bool` indicating if the specified client host
                     and user is valid for the user being authenticated

        """

        return username == client_username

    def public_key_auth_supported(self) -> bool:
        """Return whether or not public key authentication is supported

           This method should return `True` if client public key
           authentication is supported. Applications wishing to support
           it must have this method return `True` and implement
           :meth:`validate_public_key` and/or :meth:`validate_ca_key`
           to return whether or not the key provided by the client is
           valid for the user being authenticated.

           By default, it returns `False` indicating the client public
           key authentication is not supported.

           :returns: A `bool` indicating if public key authentication is
                     supported or not

        """

        return False # pragma: no cover

    def validate_public_key(self, username: str, key: SSHKey) -> \
            MaybeAwait[bool]:
        """Return whether key is an authorized client key for this user

           Key based client authentication can be supported by
           passing authorized keys in the `authorized_client_keys`
           argument of :func:`create_server`, or by calling
           :meth:`set_authorized_keys
           <SSHServerConnection.set_authorized_keys>` on the server
           connection from the :meth:`begin_auth` method. However, for
           more flexibility in matching on the allowed set of keys, this
           method can be implemented by the application to do the
           matching itself. It should return `True` if the specified
           key is a valid client key for the user being authenticated.

           This method may be called multiple times with different keys
           provided by the client. Applications should precompute as
           much as possible in the :meth:`begin_auth` method so that
           this function can quickly return whether the key provided is
           in the list.

           If blocking operations need to be performed to determine the
           validity of the key, this method may be defined as a coroutine.

           By default, this method returns `False` for all client keys.

               .. note:: This function only needs to report whether the
                         public key provided is a valid client key for this
                         user. If it is, AsyncSSH will verify that the
                         client possesses the corresponding private key
                         before allowing the authentication to succeed.

           :param username:
               The user being authenticated
           :param key:
               The public key sent by the client
           :type username: `str`
           :type key: :class:`SSHKey` *public key*

           :returns: A `bool` indicating if the specified key is a valid
                     client key for the user being authenticated

        """

        return False # pragma: no cover

    def validate_ca_key(self, username: str, key: SSHKey) -> MaybeAwait[bool]:
        """Return whether key is an authorized CA key for this user

           Certificate based client authentication can be supported by
           passing authorized CA keys in the `authorized_client_keys`
           argument of :func:`create_server`, or by calling
           :meth:`set_authorized_keys
           <SSHServerConnection.set_authorized_keys>` on the server
           connection from the :meth:`begin_auth` method. However, for
           more flexibility in matching on the allowed set of keys, this
           method can be implemented by the application to do the
           matching itself. It should return `True` if the specified
           key is a valid certificate authority key for the user being
           authenticated.

           This method may be called multiple times with different keys
           provided by the client. Applications should precompute as
           much as possible in the :meth:`begin_auth` method so that
           this function can quickly return whether the key provided is
           in the list.

           If blocking operations need to be performed to determine the
           validity of the key, this method may be defined as a coroutine.

           By default, this method returns `False` for all CA keys.

               .. note:: This function only needs to report whether the
                         public key provided is a valid CA key for this
                         user. If it is, AsyncSSH will verify that the
                         certificate is valid, that the user is one of
                         the valid principals for the certificate, and
                         that the client possesses the private key
                         corresponding to the public key in the certificate
                         before allowing the authentication to succeed.

           :param username:
               The user being authenticated
           :param key:
               The public key which signed the certificate sent by the client
           :type username: `str`
           :type key: :class:`SSHKey` *public key*

           :returns: A `bool` indicating if the specified key is a valid
                     CA key for the user being authenticated

        """

        return False # pragma: no cover

    def password_auth_supported(self) -> bool:
        """Return whether or not password authentication is supported

           This method should return `True` if password authentication
           is supported. Applications wishing to support it must have
           this method return `True` and implement :meth:`validate_password`
           to return whether or not the password provided by the client
           is valid for the user being authenticated.

           By default, this method returns `False` indicating that
           password authentication is not supported.

           :returns: A `bool` indicating if password authentication is
                     supported or not

        """

        return False # pragma: no cover

    def validate_password(self, username: str, password: str) -> \
            MaybeAwait[bool]:
        """Return whether password is valid for this user

           This method should return `True` if the specified password
           is a valid password for the user being authenticated. It must
           be overridden by applications wishing to support password
           authentication.

           If the password provided is valid but expired, this method
           may raise :exc:`PasswordChangeRequired` to request that the
           client provide a new password before authentication is
           allowed to complete. In this case, the application must
           override :meth:`change_password` to handle the password
           change request.

           This method may be called multiple times with different
           passwords provided by the client. Applications may wish
           to limit the number of attempts which are allowed. This
           can be done by having :meth:`password_auth_supported` begin
           returning `False` after the maximum number of attempts is
           exceeded.

           If blocking operations need to be performed to determine the
           validity of the password, this method may be defined as a
           coroutine.

           By default, this method returns `False` for all passwords.

           :param username:
               The user being authenticated
           :param password:
               The password sent by the client
           :type username: `str`
           :type password: `str`

           :returns: A `bool` indicating if the specified password is
                     valid for the user being authenticated

           :raises: :exc:`PasswordChangeRequired` if the password
                    provided is expired and needs to be changed

        """

        return False # pragma: no cover

    def change_password(self, username: str, old_password: str,
                        new_password: str) -> MaybeAwait[bool]:
        """Handle a request to change a user's password

           This method is called when a user makes a request to
           change their password. It should first validate that
           the old password provided is correct and then attempt
           to change the user's password to the new value.

           If the old password provided is valid and the change to
           the new password is successful, this method should
           return `True`. If the old password is not valid or
           password changes are not supported, it should return
           `False`. It may also raise :exc:`PasswordChangeRequired`
           to request that the client try again if the new password
           is not acceptable for some reason.

           If blocking operations need to be performed to determine the
           validity of the old password or to change to the new password,
           this method may be defined as a coroutine.

           By default, this method returns `False`, rejecting all
           password changes.

           :param username:
               The user whose password should be changed
           :param old_password:
               The user's current password
           :param new_password:
               The new password being requested
           :type username: `str`
           :type old_password: `str`
           :type new_password: `str`

           :returns: A `bool` indicating if the password change
                     is successful or not

           :raises: :exc:`PasswordChangeRequired` if the new password
                    is not acceptable and the client should be asked
                    to provide another

        """

        return False # pragma: no cover

    def kbdint_auth_supported(self) -> bool:
        """Return whether or not keyboard-interactive authentication
           is supported

           This method should return `True` if keyboard-interactive
           authentication is supported. Applications wishing to support
           it must have this method return `True` and implement
           :meth:`get_kbdint_challenge` and :meth:`validate_kbdint_response`
           to generate the appropriate challenges and validate the responses
           for the user being authenticated.

           By default, this method returns `NotImplemented` tying
           this authentication to password authentication. If the
           application implements password authentication and this
           method is not overridden, keyboard-interactive authentication
           will be supported by prompting for a password and passing
           that to the password authentication callbacks.

           :returns: A `bool` indicating if keyboard-interactive
                     authentication is supported or not

        """

        return NotImplemented # pragma: no cover

    def get_kbdint_challenge(self, username: str, lang: str,
                             submethods: str) -> MaybeAwait[KbdIntChallenge]:
        """Return a keyboard-interactive auth challenge

           This method should return `True` if authentication should
           succeed without any challenge, `False` if authentication
           should fail without any challenge, or an auth challenge
           consisting of a challenge name, instructions, a language tag,
           and a list of tuples containing prompt strings and booleans
           indicating whether input should be echoed when a value is
           entered for that prompt.

           If blocking operations need to be performed to determine the
           challenge to issue, this method may be defined as a coroutine.

           :param username:
               The user being authenticated
           :param lang:
               The language requested by the client for the challenge
           :param submethods:
               A comma-separated list of the types of challenges the client
               can support, or the empty string if the server should choose
           :type username: `str`
           :type lang: `str`
           :type submethods: `str`

           :returns: An authentication challenge as described above

        """

        return False # pragma: no cover

    def validate_kbdint_response(
            self, username: str, responses: KbdIntResponse) -> \
                MaybeAwait[KbdIntChallenge]:
        """Return whether the keyboard-interactive response is valid
           for this user

           This method should validate the keyboard-interactive responses
           provided and return `True` if authentication should succeed
           with no further challenge, `False` if authentication should
           fail, or an additional auth challenge in the same format returned
           by :meth:`get_kbdint_challenge`. Any series of challenges can be
           returned this way. To print a message in the middle of a sequence
           of challenges without prompting for additional data, a challenge
           can be returned with an empty list of prompts. After the client
           acknowledges this message, this function will be called again
           with an empty list of responses to continue the authentication.

           If blocking operations need to be performed to determine the
           validity of the response or the next challenge to issue, this
           method may be defined as a coroutine.

           :param username:
               The user being authenticated
           :param responses:
               A list of responses to the last challenge
           :type username: `str`
           :type responses: `list` of `str`

           :returns: `True`, `False`, or the next challenge

        """

        return False # pragma: no cover

    def session_requested(self) -> MaybeAwait[_NewSession]:
        """Handle an incoming session request

           This method is called when a session open request is received
           from the client, indicating it wishes to open a channel to be
           used for running a shell, executing a command, or connecting
           to a subsystem. If the application wishes to accept the session,
           it must override this method to return either an
           :class:`SSHServerSession` object to use to process
           the data received on the channel or a tuple consisting of an
           :class:`SSHServerChannel` object created with
           :meth:`create_server_channel
           <SSHServerConnection.create_server_channel>` and an
           :class:`SSHServerSession`, if the application
           wishes to pass non-default arguments when creating the channel.

           If blocking operations need to be performed before the session
           can be created, a coroutine which returns an
           :class:`SSHServerSession` object can be returned instead of
           the session itself. This can be either returned directly or as
           a part of a tuple with an :class:`SSHServerChannel` object.

           To reject this request, this method should return `False`
           to send back a "Session refused" response or raise a
           :exc:`ChannelOpenError` exception with the reason for
           the failure.

           The details of what type of session the client wants to start
           will be delivered to methods on the :class:`SSHServerSession`
           object which is returned, along with other information such
           as environment variables, terminal type, size, and modes.

           By default, all session requests are rejected.

           :returns: One of the following:

                       * An :class:`SSHServerSession` object or a coroutine
                         which returns an :class:`SSHServerSession`
                       * A tuple consisting of an :class:`SSHServerChannel`
                         and the above
                       * A `callable` or coroutine handler function which
                         takes AsyncSSH stream objects for stdin, stdout,
                         and stderr as arguments
                       * A tuple consisting of an :class:`SSHServerChannel`
                         and the above
                       * `False` to refuse the request

           :raises: :exc:`ChannelOpenError` if the session shouldn't
                    be accepted

        """

        return False # pragma: no cover

    def connection_requested(self, dest_host: str, dest_port: int,
                             orig_host: str, orig_port: int) -> _NewTCPSession:
        """Handle a direct TCP/IP connection request

           This method is called when a direct TCP/IP connection
           request is received by the server. Applications wishing
           to accept such connections must override this method.

           To allow standard port forwarding of data on the connection
           to the requested destination host and port, this method
           should return `True`.

           To reject this request, this method should return `False`
           to send back a "Connection refused" response or raise an
           :exc:`ChannelOpenError` exception with the reason for
           the failure.

           If the application wishes to process the data on the
           connection itself, this method should return either an
           :class:`SSHTCPSession` object which can be used to process the
           data received on the channel or a tuple consisting of of an
           :class:`SSHTCPChannel` object created with
           :meth:`create_tcp_channel()
           <SSHServerConnection.create_tcp_channel>` and an
           :class:`SSHTCPSession`, if the application wishes
           to pass non-default arguments when creating the channel.

           If blocking operations need to be performed before the session
           can be created, a coroutine which returns an
           :class:`SSHTCPSession` object can be returned instead of
           the session itself. This can be either returned directly or as
           a part of a tuple with an :class:`SSHTCPChannel` object.

           By default, all connection requests are rejected.

           :param dest_host:
               The address the client wishes to connect to
           :param dest_port:
               The port the client wishes to connect to
           :param orig_host:
               The address the connection was originated from
           :param orig_port:
               The port the connection was originated from
           :type dest_host: `str`
           :type dest_port: `int`
           :type orig_host: `str`
           :type orig_port: `int`

           :returns: One of the following:

                     * An :class:`SSHTCPSession` object or a coroutine
                       which returns an :class:`SSHTCPSession`
                     * A tuple consisting of an :class:`SSHTCPChannel`
                       and the above
                     * A `callable` or coroutine handler function which
                       takes AsyncSSH stream objects for reading from
                       and writing to the connection
                     * A tuple consisting of an :class:`SSHTCPChannel`
                       and the above
                     * `True` to request standard port forwarding
                     * `False` to refuse the connection

           :raises: :exc:`ChannelOpenError` if the connection shouldn't
                    be accepted

        """

        return False # pragma: no cover

    def server_requested(self, listen_host: str,
                         listen_port: int) -> MaybeAwait[_NewListener]:
        """Handle a request to listen on a TCP/IP address and port

           This method is called when a client makes a request to
           listen on an address and port for incoming TCP connections.
           The port to listen on may be `0` to request a dynamically
           allocated port. Applications wishing to allow TCP/IP connection
           forwarding must override this method.

           To set up standard port forwarding of connections received
           on this address and port, this method should return `True`.

           If the application wishes to manage listening for incoming
           connections itself, this method should return an
           :class:`SSHListener` object that listens for new connections
           and calls :meth:`create_connection
           <SSHServerConnection.create_connection>` on each of them to
           forward them back to the client or return `None` if the
           listener can't be set up.

           If blocking operations need to be performed to set up the
           listener, a coroutine which returns an :class:`SSHListener`
           can be returned instead of the listener itself.

           To reject this request, this method should return `False`.

           By default, this method rejects all server requests.

           :param listen_host:
               The address the server should listen on
           :param listen_port:
               The port the server should listen on, or the value `0`
               to request that the server dynamically allocate a port
           :type listen_host: `str`
           :type listen_port: `int`

           :returns: One of the following:

                     * An :class:`SSHListener` object
                     * `True` to set up standard port forwarding
                     * `False` to reject the request
                     * A coroutine object which returns one of the above

        """

        return False # pragma: no cover

    def unix_connection_requested(self, dest_path: str) -> _NewUNIXSession:
        """Handle a direct UNIX domain socket connection request

           This method is called when a direct UNIX domain socket connection
           request is received by the server. Applications wishing to accept
           such connections must override this method.

           To allow standard path forwarding of data on the connection to the
           requested destination path, this method should return `True`.

           To reject this request, this method should return `False`
           to send back a "Connection refused" response or raise an
           :exc:`ChannelOpenError` exception with the reason for
           the failure.

           If the application wishes to process the data on the
           connection itself, this method should return either an
           :class:`SSHUNIXSession` object which can be used to process the
           data received on the channel or a tuple consisting of of an
           :class:`SSHUNIXChannel` object created with
           :meth:`create_unix_channel()
           <SSHServerConnection.create_unix_channel>` and an
           :class:`SSHUNIXSession`, if the application wishes
           to pass non-default arguments when creating the channel.

           If blocking operations need to be performed before the session
           can be created, a coroutine which returns an
           :class:`SSHUNIXSession` object can be returned instead of
           the session itself. This can be either returned directly or as
           a part of a tuple with an :class:`SSHUNIXChannel` object.

           By default, all connection requests are rejected.

           :param dest_path:
               The path the client wishes to connect to
           :type dest_path: `str`

           :returns: One of the following:

                     * An :class:`SSHUNIXSession` object or a coroutine
                       which returns an :class:`SSHUNIXSession`
                     * A tuple consisting of an :class:`SSHUNIXChannel`
                       and the above
                     * A `callable` or coroutine handler function which
                       takes AsyncSSH stream objects for reading from
                       and writing to the connection
                     * A tuple consisting of an :class:`SSHUNIXChannel`
                       and the above
                     * `True` to request standard path forwarding
                     * `False` to refuse the connection

           :raises: :exc:`ChannelOpenError` if the connection shouldn't
                    be accepted

        """

        return False # pragma: no cover

    def unix_server_requested(self, listen_path: str) -> \
            MaybeAwait[_NewListener]:
        """Handle a request to listen on a UNIX domain socket

           This method is called when a client makes a request to
           listen on a path for incoming UNIX domain socket connections.
           Applications wishing to allow UNIX domain socket forwarding
           must override this method.

           To set up standard path forwarding of connections received
           on this path, this method should return `True`.

           If the application wishes to manage listening for incoming
           connections itself, this method should return an
           :class:`SSHListener` object that listens for new connections
           and calls :meth:`create_unix_connection
           <SSHServerConnection.create_unix_connection>` on each of them to
           forward them back to the client or return `None` if the
           listener can't be set up.

           If blocking operations need to be performed to set up the
           listener, a coroutine which returns an :class:`SSHListener`
           can be returned instead of the listener itself.

           To reject this request, this method should return `False`.

           By default, this method rejects all server requests.

           :param listen_path:
               The path the server should listen on
           :type listen_path: `str`

           :returns: One of the following:

                     * An :class:`SSHListener` object or a coroutine
                       which returns an :class:`SSHListener` or `False`
                       if the listener can't be opened
                     * `True` to set up standard path forwarding
                     * `False` to reject the request

        """

        return False # pragma: no cover

    def tun_requested(self, unit: Optional[int]) -> _NewTunTapSession:
        """Handle a layer 3 tunnel request

           This method is called when a layer 3 tunnel request is received
           by the server. Applications wishing to accept such tunnels must
           override this method.

           To allow standard path forwarding of data on the connection to the
           requested TUN device, this method should return `True`.

           To reject this request, this method should return `False`
           to send back a "Connection refused" response or raise an
           :exc:`ChannelOpenError` exception with the reason for
           the failure.

           If the application wishes to process the data on the
           connection itself, this method should return either an
           :class:`SSHTunTapSession` object which can be used to process the
           data received on the channel or a tuple consisting of of an
           :class:`SSHTunTapChannel` object created with
           :meth:`create_tuntap_channel()
           <SSHServerConnection.create_tuntap_channel>` and an
           :class:`SSHTunTapSession`, if the application wishes
           to pass non-default arguments when creating the channel.

           If blocking operations need to be performed before the session
           can be created, a coroutine which returns an
           :class:`SSHTunTapSession` object can be returned instead of
           the session itself. This can be either returned directly or as
           a part of a tuple with an :class:`SSHTunTapChannel` object.

           By default, all layer 3 tunnel requests are rejected.

           :param dest_path:
               The path the client wishes to connect to
           :type dest_path: `str`

           :returns: One of the following:

                     * An :class:`SSHTunTapSession` object or a coroutine
                       which returns an :class:`SSHTunTapSession`
                     * A tuple consisting of an :class:`SSHTunTapChannel`
                       and the above
                     * A `callable` or coroutine handler function which
                       takes AsyncSSH stream objects for reading from
                       and writing to the connection
                     * A tuple consisting of an :class:`SSHTunTapChannel`
                       and the above
                     * `True` to request standard layer 3 tunnel forwarding
                     * `False` to refuse the connection

           :raises: :exc:`ChannelOpenError` if the connection shouldn't
                    be accepted

        """

        return False # pragma: no cover

    def tap_requested(self, unit: Optional[int]) -> _NewTunTapSession:
        """Handle a layer 2 tunnel request

           This method is called when a layer 2 tunnel request is received
           by the server. Applications wishing to accept such tunnels must
           override this method.

           To allow standard path forwarding of data on the connection to the
           requested TUN device, this method should return `True`.

           To reject this request, this method should return `False`
           to send back a "Connection refused" response or raise an
           :exc:`ChannelOpenError` exception with the reason for
           the failure.

           If the application wishes to process the data on the
           connection itself, this method should return either an
           :class:`SSHTunTapSession` object which can be used to process the
           data received on the channel or a tuple consisting of of an
           :class:`SSHTunTapChannel` object created with
           :meth:`create_tuntap_channel()
           <SSHServerConnection.create_tuntap_channel>` and an
           :class:`SSHTunTapSession`, if the application wishes
           to pass non-default arguments when creating the channel.

           If blocking operations need to be performed before the session
           can be created, a coroutine which returns an
           :class:`SSHTunTapSession` object can be returned instead of
           the session itself. This can be either returned directly or as
           a part of a tuple with an :class:`SSHTunTapChannel` object.

           By default, all layer 2 tunnel requests are rejected.

           :param dest_path:
               The path the client wishes to connect to
           :type dest_path: `str`

           :returns: One of the following:

                     * An :class:`SSHTunTapSession` object or a coroutine
                       which returns an :class:`SSHTunTapSession`
                     * A tuple consisting of an :class:`SSHTunTapChannel`
                       and the above
                     * A `callable` or coroutine handler function which
                       takes AsyncSSH stream objects for reading from
                       and writing to the connection
                     * A tuple consisting of an :class:`SSHTunTapChannel`
                       and the above
                     * `True` to request standard layer 2 tunnel forwarding
                     * `False` to refuse the connection

           :raises: :exc:`ChannelOpenError` if the connection shouldn't
                    be accepted

        """

        return False # pragma: no cover
