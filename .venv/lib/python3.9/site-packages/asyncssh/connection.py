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

"""SSH connection handlers"""

import asyncio
import functools
import getpass
import inspect
import io
import ipaddress
import os
import shlex
import socket
import sys
import tempfile
import time

from collections import OrderedDict
from functools import partial
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, AnyStr, Awaitable, Callable, Dict
from typing import Generic, List, Mapping, Optional, Sequence, Set, Tuple
from typing import Type, TypeVar, Union, cast
from typing_extensions import Protocol, Self

from .agent import SSHAgentClient, SSHAgentListener

from .auth import Auth, ClientAuth, KbdIntChallenge, KbdIntPrompts
from .auth import KbdIntResponse, PasswordChangeResponse
from .auth import get_supported_client_auth_methods, lookup_client_auth
from .auth import get_supported_server_auth_methods, lookup_server_auth

from .auth_keys import SSHAuthorizedKeys, read_authorized_keys

from .channel import SSHChannel, SSHClientChannel, SSHServerChannel
from .channel import SSHTCPChannel, SSHUNIXChannel, SSHTunTapChannel
from .channel import SSHX11Channel, SSHAgentChannel

from .client import SSHClient

from .compression import Compressor, Decompressor, get_compression_algs
from .compression import get_default_compression_algs, get_compression_params
from .compression import get_compressor, get_decompressor

from .config import ConfigPaths, SSHConfig, SSHClientConfig, SSHServerConfig

from .constants import DEFAULT_LANG, DEFAULT_PORT
from .constants import DISC_BY_APPLICATION
from .constants import EXTENDED_DATA_STDERR
from .constants import MSG_DISCONNECT, MSG_IGNORE, MSG_UNIMPLEMENTED, MSG_DEBUG
from .constants import MSG_SERVICE_REQUEST, MSG_SERVICE_ACCEPT, MSG_EXT_INFO
from .constants import MSG_CHANNEL_OPEN, MSG_CHANNEL_OPEN_CONFIRMATION
from .constants import MSG_CHANNEL_OPEN_FAILURE
from .constants import MSG_CHANNEL_FIRST, MSG_CHANNEL_LAST
from .constants import MSG_KEXINIT, MSG_NEWKEYS, MSG_KEX_FIRST, MSG_KEX_LAST
from .constants import MSG_USERAUTH_REQUEST, MSG_USERAUTH_FAILURE
from .constants import MSG_USERAUTH_SUCCESS, MSG_USERAUTH_BANNER
from .constants import MSG_USERAUTH_FIRST, MSG_USERAUTH_LAST
from .constants import MSG_GLOBAL_REQUEST, MSG_REQUEST_SUCCESS
from .constants import MSG_REQUEST_FAILURE
from .constants import OPEN_ADMINISTRATIVELY_PROHIBITED, OPEN_CONNECT_FAILED
from .constants import OPEN_UNKNOWN_CHANNEL_TYPE

from .encryption import Encryption, get_encryption_algs
from .encryption import get_default_encryption_algs
from .encryption import get_encryption_params, get_encryption

from .forward import SSHForwarder

from .gss import GSSBase, GSSClient, GSSServer, GSSError

from .kex import Kex, get_kex_algs, get_default_kex_algs
from .kex import expand_kex_algs, get_kex

from .keysign import KeySignPath, SSHKeySignKeyPair
from .keysign import find_keysign, get_keysign_keys

from .known_hosts import KnownHostsArg, match_known_hosts

from .listener import ListenKey, SSHListener
from .listener import SSHTCPClientListener, SSHUNIXClientListener
from .listener import TCPListenerFactory, UNIXListenerFactory
from .listener import create_tcp_forward_listener, create_unix_forward_listener
from .listener import create_socks_listener

from .logging import SSHLogger, logger

from .mac import get_mac_algs, get_default_mac_algs

from .misc import BytesOrStr, BytesOrStrDict, DefTuple, Env, EnvSeq, FilePath
from .misc import HostPort, IPNetwork, MaybeAwait, OptExcInfo, Options, SockAddr
from .misc import ChannelListenError, ChannelOpenError, CompressionError
from .misc import DisconnectError, ConnectionLost, HostKeyNotVerifiable
from .misc import KeyExchangeFailed, IllegalUserName, MACError
from .misc import PasswordChangeRequired, PermissionDenied, ProtocolError
from .misc import ProtocolNotSupported, ServiceNotAvailable
from .misc import TermModesArg, TermSizeArg
from .misc import async_context_manager, construct_disc_error, encode_env
from .misc import get_symbol_names, ip_address, lookup_env, map_handler_name
from .misc import parse_byte_count, parse_time_interval, split_args

from .packet import Boolean, Byte, NameList, String, UInt32, PacketDecodeError
from .packet import SSHPacket, SSHPacketHandler, SSHPacketLogger

from .pattern import WildcardPattern, WildcardPatternList

from .pkcs11 import load_pkcs11_keys

from .process import PIPE, ProcessSource, ProcessTarget
from .process import SSHServerProcessFactory, SSHCompletedProcess
from .process import SSHClientProcess, SSHServerProcess

from .public_key import CERT_TYPE_HOST, CERT_TYPE_USER, KeyImportError
from .public_key import CertListArg, IdentityListArg, KeyListArg, SigningKey
from .public_key import KeyPairListArg, X509CertPurposes, SSHKey, SSHKeyPair
from .public_key import SSHCertificate, SSHOpenSSHCertificate
from .public_key import SSHX509Certificate, SSHX509CertificateChain
from .public_key import decode_ssh_public_key, decode_ssh_certificate
from .public_key import get_public_key_algs, get_default_public_key_algs
from .public_key import get_certificate_algs, get_default_certificate_algs
from .public_key import get_x509_certificate_algs
from .public_key import get_default_x509_certificate_algs
from .public_key import load_keypairs, load_default_keypairs
from .public_key import load_public_keys, load_default_host_public_keys
from .public_key import load_certificates
from .public_key import load_identities, load_default_identities

from .saslprep import saslprep, SASLPrepError

from .server import SSHServer

from .session import DataType, SSHClientSession, SSHServerSession
from .session import SSHTCPSession, SSHUNIXSession, SSHTunTapSession
from .session import SSHClientSessionFactory, SSHTCPSessionFactory
from .session import SSHUNIXSessionFactory, SSHTunTapSessionFactory

from .sftp import MIN_SFTP_VERSION, SFTPClient, SFTPServer
from .sftp import start_sftp_client

from .stream import SSHReader, SSHWriter, SFTPServerFactory
from .stream import SSHSocketSessionFactory, SSHServerSessionFactory
from .stream import SSHClientStreamSession, SSHServerStreamSession
from .stream import SSHTCPStreamSession, SSHUNIXStreamSession
from .stream import SSHTunTapStreamSession

from .subprocess import SSHSubprocessTransport, SSHSubprocessProtocol
from .subprocess import SubprocessFactory, SSHSubprocessWritePipe

from .tuntap import SSH_TUN_MODE_POINTTOPOINT, SSH_TUN_MODE_ETHERNET
from .tuntap import SSH_TUN_UNIT_ANY, create_tuntap

from .version import __version__

from .x11 import SSHX11ClientForwarder
from .x11 import SSHX11ClientListener, SSHX11ServerListener
from .x11 import create_x11_client_listener, create_x11_server_listener

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from .crypto import X509NamePattern


_ClientFactory = Callable[[], SSHClient]
_ServerFactory = Callable[[], SSHServer]
_ProtocolFactory = Union[_ClientFactory, _ServerFactory]

_Conn = TypeVar('_Conn', bound='SSHConnection')
_Options = TypeVar('_Options', bound='SSHConnectionOptions')

_ServerHostKeysHandler = Optional[Callable[[List[SSHKey], List[SSHKey],
                                            List[SSHKey], List[SSHKey]],
                                           MaybeAwait[None]]]

class _TunnelProtocol(Protocol):
    """Base protocol for connections to tunnel SSH over"""

    def close(self) -> None:
        """Close this tunnel"""

class _TunnelConnectorProtocol(_TunnelProtocol, Protocol):
    """Protocol to open a connection to tunnel an SSH connection over"""

    async def create_connection(
            self, session_factory: SSHTCPSessionFactory[bytes],
            remote_host: str, remote_port: int) -> \
                Tuple[SSHTCPChannel[bytes], SSHTCPSession[bytes]]:
        """Create an outbound tunnel connection"""

class _TunnelListenerProtocol(_TunnelProtocol, Protocol):
    """Protocol to open a listener to tunnel SSH connections over"""

    async def create_server(self, session_factory: TCPListenerFactory,
                            listen_host: str, listen_port: int) -> SSHListener:
        """Create an inbound tunnel listener"""

_AcceptHandler = Optional[Callable[['SSHConnection'], MaybeAwait[None]]]
_ErrorHandler = Optional[Callable[['SSHConnection',
                                   Optional[Exception]], None]]

_OpenHandler = Callable[[SSHPacket], Tuple[SSHClientChannel, SSHClientSession]]
_PacketHandler = Callable[[SSHPacket], None]

_AlgsArg = DefTuple[Union[str, Sequence[str]]]
_AuthArg = DefTuple[bool]
_AuthKeysArg = DefTuple[Union[None, str, List[str], SSHAuthorizedKeys]]
_ClientHostKey = Union[SSHKeyPair, SSHKeySignKeyPair]
_ClientKeysArg = Union[KeyListArg, KeyPairListArg]
_CNAMEArg = DefTuple[Union[Sequence[str], Sequence[Tuple[str, str]]]]

_GlobalRequest = Tuple[Optional[_PacketHandler], SSHPacket, bool]
_GlobalRequestResult = Tuple[int, SSHPacket]
_KeyOrCertOptions = Mapping[str, object]
_ListenerArg = Union[bool, SSHListener]
_ProxyCommand = Optional[Union[str, Sequence[str]]]
_RequestPTY = Union[bool, str]

_TCPServerHandlerFactory = Callable[[str, int], SSHSocketSessionFactory]
_UNIXServerHandlerFactory = Callable[[], SSHSocketSessionFactory]

_TunnelConnector = Union[None, str, _TunnelConnectorProtocol]
_TunnelListener = Union[None, str, _TunnelListenerProtocol]

_VersionArg = DefTuple[BytesOrStr]

SSHAcceptHandler = Callable[[str, int], MaybeAwait[bool]]

# SSH service names
_USERAUTH_SERVICE = b'ssh-userauth'
_CONNECTION_SERVICE = b'ssh-connection'

# Max banner and version line length and count
_MAX_BANNER_LINES = 1024
_MAX_BANNER_LINE_LEN = 8192
_MAX_VERSION_LINE_LEN = 255

# Max allowed username length
_MAX_USERNAME_LEN = 1024

# Default rekey parameters
_DEFAULT_REKEY_BYTES = 1 << 30      # 1 GiB
_DEFAULT_REKEY_SECONDS = 3600       # 1 hour

# Default login timeout
_DEFAULT_LOGIN_TIMEOUT = 120        # 2 minutes

# Default keepalive interval and count max
_DEFAULT_KEEPALIVE_INTERVAL = 0     # disabled by default
_DEFAULT_KEEPALIVE_COUNT_MAX = 3

# Default channel parameters
_DEFAULT_WINDOW = 2*1024*1024       # 2 MiB
_DEFAULT_MAX_PKTSIZE = 32768        # 32 kiB

# Default line editor parameters
_DEFAULT_LINE_HISTORY = 1000        # 1000 lines
_DEFAULT_MAX_LINE_LENGTH = 1024     # 1024 characters


async def _canonicalize_host(loop: asyncio.AbstractEventLoop,
                             options: 'SSHConnectionOptions') -> Optional[str]:
    """Canonicalize a host name"""

    host = options.host

    if not options.canonicalize_hostname or not options.canonical_domains:
        logger.info('Host canonicalization disabled')
        return None

    if host.count('.') > options.canonicalize_max_dots:
        logger.info('Host canonicalization skipped due to max dots')
        return None

    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        logger.info('Hostname canonicalization skipped on IP address')
        return None

    logger.debug1('Beginning hostname canonicalization')

    for domain in options.canonical_domains:
        logger.debug1('  Checking domain %s', domain)

        canon_host = f'{host}.{domain}'

        try:
            addrinfo = await loop.getaddrinfo(
                canon_host, 0, flags=socket.AI_CANONNAME)
        except socket.gaierror:
            continue

        cname = addrinfo[0][3]

        if cname and cname != canon_host:
            logger.debug1('  Checking CNAME rules for hostname %s '
                          'with CNAME %s', canon_host, cname)

            for patterns in options.canonicalize_permitted_cnames:
                host_pat, cname_pat = map(WildcardPatternList, patterns)

                if host_pat.matches(canon_host) and cname_pat.matches(cname):
                    logger.info('Hostname canonicalization to CNAME '
                                'applied: %s -> %s', options.host, cname)
                    return cname

        logger.info('Hostname canonicalization applied: %s -> %s',
                    options.host, canon_host)

        return canon_host

    if not options.canonicalize_fallback_local:
        logger.info('Hostname canonicalization failed (fallback disabled)')
        raise OSError(f'Unable to canonicalize hostname "{host}"')

    logger.info('Hostname canonicalization failed, using local resolver')
    return None


async def _open_proxy(
        loop: asyncio.AbstractEventLoop, command: Sequence[str],
        conn_factory: Callable[[], _Conn]) -> _Conn:
    """Open a tunnel running a proxy command"""

    class _ProxyCommandTunnel(asyncio.SubprocessProtocol):
        """SSH proxy command tunnel"""

        def __init__(self) -> None:
            super().__init__()

            self._transport: Optional[asyncio.SubprocessTransport] = None
            self._stdin: Optional[asyncio.WriteTransport] = None
            self._conn = conn_factory()
            self._close_event = asyncio.Event()

        def get_extra_info(self, name: str, default: Any = None) -> Any:
            """Return extra information associated with this tunnel"""

            assert self._transport is not None
            return self._transport.get_extra_info(name, default)

        def get_conn(self) -> _Conn:
            """Return the connection associated with this tunnel"""

            return self._conn

        def connection_made(self, transport: asyncio.BaseTransport) -> None:
            """Handle startup of the subprocess"""

            self._transport = cast(asyncio.SubprocessTransport, transport)
            self._stdin = cast(asyncio.WriteTransport,
                               self._transport.get_pipe_transport(0))
            self._conn.connection_made(cast(asyncio.BaseTransport, self))

        def pipe_data_received(self, fd: int, data: bytes) -> None:
            """Handle data received from this tunnel"""

            # pylint: disable=unused-argument

            self._conn.data_received(data)

        def pipe_connection_lost(self, fd: int,
                                 exc: Optional[Exception]) -> None:
            """Handle when this tunnel is closed"""

            # pylint: disable=unused-argument

            self._conn.connection_lost(exc)

        def write(self, data: bytes) -> None:
            """Write data to this tunnel"""

            assert self._stdin is not None
            self._stdin.write(data)

        def abort(self) -> None:
            """Forcibly close this tunnel"""

            self.close()

        def close(self) -> None:
            """Close this tunnel"""

            if self._transport: # pragma: no cover
                self._transport.close()

            self._close_event.set()


    _, tunnel = await loop.subprocess_exec(_ProxyCommandTunnel, *command)

    return cast(_Conn, cast(_ProxyCommandTunnel, tunnel).get_conn())


async def _open_tunnel(tunnels: object, options: _Options,
                       config: DefTuple[ConfigPaths]) -> \
        Optional['SSHClientConnection']:
    """Parse and open connection to tunnel over"""

    username: DefTuple[str]
    port: DefTuple[int]

    if isinstance(tunnels, str):
        conn: Optional[SSHClientConnection] = None

        for tunnel in tunnels.split(','):
            if '@' in tunnel:
                username, host = tunnel.rsplit('@', 1)
            else:
                username, host = (), tunnel

            if ':' in host:
                host, port_str = host.rsplit(':', 1)
                port = int(port_str)
            else:
                port = ()

            last_conn = conn
            conn = await connect(host, port, username=username,
                                 passphrase=options.passphrase, tunnel=conn,
                                 config=config)
            conn.set_tunnel(last_conn)

            if options.canonicalize_hostname != 'always':
                options.canonicalize_hostname = False

        return conn
    else:
        return None


async def _connect(options: _Options, config: DefTuple[ConfigPaths],
                   loop: asyncio.AbstractEventLoop, flags: int,
                   sock: Optional[socket.socket],
                   conn_factory: Callable[[], _Conn], msg: str) -> _Conn:
    """Make outbound TCP or SSH tunneled connection"""

    options.waiter = loop.create_future()

    canon_host = await _canonicalize_host(loop, options)

    host = canon_host if canon_host else options.host
    canonical = bool(canon_host)
    final = options.config.has_match_final()

    if canonical or final:
        options.update(host=host, reload=True, canonical=canonical, final=final)

    host = options.host
    port = options.port
    tunnel = options.tunnel
    family = options.family
    local_addr = options.local_addr
    proxy_command = options.proxy_command
    free_conn = True

    new_tunnel = await _open_tunnel(tunnel, options, config)
    tunnel: _TunnelConnectorProtocol

    try:
        if sock:
            logger.info('%s already-connected socket', msg)

            _, session = await loop.create_connection(conn_factory, sock=sock)

            conn = cast(_Conn, session)
        elif new_tunnel:
            new_tunnel.logger.info('%s %s via %s', msg, (host, port), tunnel)

            # pylint: disable=broad-except
            try:
                _, tunnel_session = await new_tunnel.create_connection(
                    cast(SSHTCPSessionFactory[bytes], conn_factory),
                    host, port)
            except Exception:
                new_tunnel.close()
                await new_tunnel.wait_closed()
                raise
            else:
                conn = cast(_Conn, tunnel_session)
                conn.set_tunnel(new_tunnel)
        elif tunnel:
            tunnel_logger = getattr(tunnel, 'logger', logger)
            tunnel_logger.info('%s %s via SSH tunnel', msg, (host, port))

            _, tunnel_session = await tunnel.create_connection(
                cast(SSHTCPSessionFactory[bytes], conn_factory),
                host, port)

            conn = cast(_Conn, tunnel_session)
        elif proxy_command:
            conn = await _open_proxy(loop, proxy_command, conn_factory)
        else:
            logger.info('%s %s', msg, (host, port))

            _, session = await loop.create_connection(
                conn_factory, host, port, family=family,
                flags=flags, local_addr=local_addr)

            conn = cast(_Conn, session)
    except asyncio.CancelledError:
        options.waiter.cancel()
        raise

    conn.set_extra_info(host=host, port=port)

    try:
        await options.waiter
        free_conn = False
        return conn
    finally:
        if free_conn:
            conn.abort()
            await conn.wait_closed()


async def _listen(options: _Options, config: DefTuple[ConfigPaths],
                  loop: asyncio.AbstractEventLoop, flags: int,
                  backlog: int, sock: Optional[socket.socket],
                  reuse_address: bool, reuse_port: bool,
                  conn_factory: Callable[[], _Conn],
                  msg: str) -> 'SSHAcceptor':
    """Make inbound TCP or SSH tunneled listener"""

    def tunnel_factory(_orig_host: str, _orig_port: int) -> SSHTCPSession:
        """Ignore original host and port"""

        return cast(SSHTCPSession, conn_factory())

    host = options.host
    port = options.port
    tunnel = options.tunnel
    family = options.family

    new_tunnel = await _open_tunnel(tunnel, options, config)
    tunnel: _TunnelListenerProtocol

    if sock:
        logger.info('%s already-connected socket', msg)

        server: asyncio.AbstractServer = await loop.create_server(
            conn_factory, sock=sock, backlog=backlog,
            reuse_address=reuse_address, reuse_port=reuse_port)
    elif new_tunnel:
        new_tunnel.logger.info('%s %s via %s', msg, (host, port), tunnel)

        # pylint: disable=broad-except
        try:
            tunnel_server = await new_tunnel.create_server(
                tunnel_factory, host, port)
        except Exception:
            new_tunnel.close()
            await new_tunnel.wait_closed()
            raise
        else:
            tunnel_server.set_tunnel(new_tunnel)
            server = cast(asyncio.AbstractServer, tunnel_server)
    elif tunnel:
        tunnel_logger = getattr(tunnel, 'logger', logger)
        tunnel_logger.info('%s %s via SSH tunnel', msg, (host, port))

        tunnel_server = await tunnel.create_server(tunnel_factory, host, port)
        server = cast(asyncio.AbstractServer, tunnel_server)
    else:
        logger.info('%s %s', msg, (host, port))

        server = await loop.create_server(
            conn_factory, host, port, family=family, flags=flags,
            backlog=backlog, reuse_address=reuse_address,
            reuse_port=reuse_port)

    return SSHAcceptor(server, options)


def _validate_version(version: DefTuple[BytesOrStr]) -> bytes:
    """Validate requested SSH version"""

    if version == ():
        version = b'AsyncSSH_' + __version__.encode('ascii')
    else:
        if isinstance(version, str):
            version = version.encode('ascii')
        else:
            assert isinstance(version, bytes)

        # Version including 'SSH-2.0-' and CRLF must be 255 chars or less
        if len(version) > 245:
            raise ValueError('Version string is too long')

        for b in version:
            if b < 0x20 or b > 0x7e:
                raise ValueError('Version string must be printable ASCII')

    return version


def _expand_algs(alg_type: str, algs: str,
                 possible_algs: List[bytes],
                 default_algs: List[bytes],
                 strict_match: bool) -> Sequence[bytes]:
    """Expand the set of allowed algorithms"""

    if algs[:1] in '^+-':
        prefix = algs[:1]
        algs = algs[1:]
    else:
        prefix = ''

    matched: List[bytes] = []

    for pat in algs.split(','):
        pattern = WildcardPattern(pat)

        matches = [alg for alg in possible_algs
                   if pattern.matches(alg.decode('ascii'))]

        if not matches and strict_match:
            raise ValueError(f'"{pat}" matches no valid {alg_type} algorithms')

        matched.extend(matches)

    if prefix == '^':
        return matched + default_algs
    elif prefix == '+':
        return default_algs + matched
    elif prefix == '-':
        return [alg for alg in default_algs if alg not in matched]
    else:
        return matched


def _select_algs(alg_type: str, algs: _AlgsArg, config_algs: _AlgsArg,
                 possible_algs: List[bytes], default_algs: List[bytes],
                 none_value: Optional[bytes] = None) -> Sequence[bytes]:
    """Select a set of allowed algorithms"""

    if algs == ():
        algs = config_algs
        strict_match = False
    else:
        strict_match = True

    if algs in ((), 'default'):
        return default_algs
    elif algs:
        if isinstance(algs, str):
            expanded_algs = _expand_algs(alg_type, algs, possible_algs,
                                         default_algs, strict_match)
        else:
            expanded_algs = [alg.encode('ascii') for alg in algs]

        result: List[bytes] = []

        for alg in expanded_algs:
            if alg not in possible_algs:
                raise ValueError(f'{alg.decode("ascii")} is not a valid '
                                 f'{alg_type} algorithm')

            if alg not in result:
                result.append(alg)

        return result
    elif none_value:
        return [none_value]
    else:
        raise ValueError(f'No {alg_type} algorithms selected')


def _select_host_key_algs(algs: _AlgsArg, config_algs: _AlgsArg,
                          default_algs: List[bytes]) -> Sequence[bytes]:
    """Select a set of allowed host key algorithms"""

    possible_algs = (get_x509_certificate_algs() + get_certificate_algs() +
                     get_public_key_algs())

    return _select_algs('host key', algs, config_algs,
                        possible_algs, default_algs)


def _validate_algs(config: SSHConfig, kex_algs_arg: _AlgsArg,
                   enc_algs_arg: _AlgsArg, mac_algs_arg: _AlgsArg,
                   cmp_algs_arg: _AlgsArg, sig_algs_arg: _AlgsArg,
                   allow_x509: bool) -> \
        Tuple[Sequence[bytes], Sequence[bytes], Sequence[bytes],
              Sequence[bytes], Sequence[bytes]]:
    """Validate requested algorithms"""

    kex_algs = _select_algs('key exchange', kex_algs_arg,
                            cast(_AlgsArg, config.get('KexAlgorithms', ())),
                            get_kex_algs(), get_default_kex_algs())
    enc_algs = _select_algs('encryption', enc_algs_arg,
                            cast(_AlgsArg, config.get('Ciphers', ())),
                            get_encryption_algs(),
                            get_default_encryption_algs())
    mac_algs = _select_algs('MAC', mac_algs_arg,
                            cast(_AlgsArg, config.get('MACs', ())),
                            get_mac_algs(), get_default_mac_algs())
    cmp_algs = _select_algs('compression', cmp_algs_arg,
                            cast(_AlgsArg, config.get_compression_algs()),
                            get_compression_algs(),
                            get_default_compression_algs(), b'none')

    allowed_sig_algs = get_x509_certificate_algs() if allow_x509 else []
    allowed_sig_algs = allowed_sig_algs + get_public_key_algs()

    default_sig_algs = get_default_x509_certificate_algs() if allow_x509 else []
    default_sig_algs = allowed_sig_algs + get_default_public_key_algs()

    sig_algs = _select_algs('signature', sig_algs_arg,
                            cast(_AlgsArg,
                                 config.get('CASignatureAlgorithms', ())),
                            allowed_sig_algs, default_sig_algs)

    return kex_algs, enc_algs, mac_algs, cmp_algs, sig_algs


class SSHAcceptor:
    """SSH acceptor

       This class in a wrapper around an :class:`asyncio.Server` listener
       which provides the ability to update the the set of SSH client or
       server connection options associated with that listener. This is
       accomplished by calling the :meth:`update` method, which takes the
       same keyword arguments as the :class:`SSHClientConnectionOptions`
       and :class:`SSHServerConnectionOptions` classes.

       In addition, this class supports all of the methods supported by
       :class:`asyncio.Server` to control accepting of new connections.

    """

    def __init__(self, server: asyncio.AbstractServer,
                 options: 'SSHConnectionOptions'):
        self._server = server
        self._options = options

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, _exc_type: Optional[Type[BaseException]],
                        _exc_value: Optional[BaseException],
                        _traceback: Optional[TracebackType]) -> bool:
        self.close()
        await self.wait_closed()
        return False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._server, name)

    def get_addresses(self) -> List[Tuple]:
        """Return socket addresses being listened on

           This method returns the socket addresses being listened on.
           It returns tuples of the form returned by
           :meth:`socket.getsockname`.  If the listener was created
           using a hostname, the host's resolved IPs will be returned.
           If the requested listening port was `0`, the selected
           listening ports will be returned.

           :returns: A list of socket addresses being listened on

        """

        if hasattr(self._server, 'get_addresses'):
            return self._server.get_addresses()
        else:
            return [sock.getsockname() for sock in self.sockets]

    def get_port(self) -> int:
        """Return the port number being listened on

           This method returns the port number being listened on.
           If it is listening on multiple sockets with different port
           numbers, this function will return `0`. In that case,
           :meth:`get_addresses` can be used to retrieve the full
           list of listening addresses and ports.

           :returns: The port number being listened on, if there's only one

        """

        if hasattr(self._server, 'get_port'):
            return self._server.get_port()
        else:
            ports = {addr[1] for addr in self.get_addresses()}
            return ports.pop() if len(ports) == 1 else 0

    def close(self) -> None:
        """Stop listening for new connections

           This method can be called to stop listening for new
           SSH connections. Existing connections will remain open.

        """

        self._server.close()

    async def wait_closed(self) -> None:
        """Wait for this listener to close

           This method is a coroutine which waits for this
           listener to be closed.

        """

        await self._server.wait_closed()

    def update(self, **kwargs: object) -> None:
        """Update options on an SSH listener

           Acceptors started by :func:`listen` support options defined
           in :class:`SSHServerConnectionOptions`. Acceptors started
           by :func:`listen_reverse` support options defined in
           :class:`SSHClientConnectionOptions`.

           Changes apply only to SSH client/server connections accepted
           after the change is made. Previously accepted connections
           will continue to use the options set when they were accepted.

        """

        self._options.update(**kwargs)


class SSHConnection(SSHPacketHandler, asyncio.Protocol):
    """Parent class for SSH connections"""

    _handler_names = get_symbol_names(globals(), 'MSG_')

    next_conn = 0    # Next connection number, for logging

    @staticmethod
    def _get_next_conn() -> int:
        """Return the next available connection number (for logging)"""

        next_conn = SSHConnection.next_conn
        SSHConnection.next_conn += 1
        return next_conn

    def __init__(self, loop: asyncio.AbstractEventLoop,
                 options: 'SSHConnectionOptions',
                 acceptor: _AcceptHandler, error_handler: _ErrorHandler,
                 wait: Optional[str], server: bool):
        self._loop = loop
        self._options = options
        self._protocol_factory = options.protocol_factory
        self._acceptor = acceptor
        self._error_handler = error_handler
        self._server = server
        self._wait = wait
        self._waiter = options.waiter if wait else None

        self._transport: Optional[asyncio.Transport] = None
        self._local_addr = ''
        self._local_port = 0
        self._peer_host = ''
        self._peer_addr = ''
        self._peer_port = 0
        self._tcp_keepalive = options.tcp_keepalive
        self._owner: Optional[Union[SSHClient, SSHServer]] = None
        self._extra: Dict[str, object] = {}

        self._inpbuf = b''
        self._packet = b''
        self._pktlen = 0
        self._banner_lines = 0

        self._version = options.version
        self._client_version = b''
        self._server_version = b''
        self._client_kexinit = b''
        self._server_kexinit = b''
        self._session_id = b''

        self._send_seq = 0
        self._send_encryption: Optional[Encryption] = None
        self._send_enchdrlen = 5
        self._send_blocksize = 8
        self._compressor: Optional[Compressor] = None
        self._compress_after_auth = False
        self._deferred_packets: List[Tuple[int, Sequence[bytes]]] = []

        self._recv_handler = self._recv_version
        self._recv_seq = 0
        self._recv_encryption: Optional[Encryption] = None
        self._recv_blocksize = 8
        self._recv_macsize = 0
        self._decompressor: Optional[Decompressor] = None
        self._decompress_after_auth = False
        self._next_recv_encryption: Optional[Encryption] = None
        self._next_recv_blocksize = 0
        self._next_recv_macsize = 0
        self._next_decompressor: Optional[Decompressor] = None
        self._next_decompress_after_auth = False

        self._trusted_host_keys: Optional[Set[SSHKey]] = set()
        self._trusted_host_key_algs: List[bytes] = []
        self._trusted_ca_keys: Optional[Set[SSHKey]] = set()
        self._revoked_host_keys: Set[SSHKey] = set()

        self._x509_trusted_certs = options.x509_trusted_certs
        self._x509_trusted_cert_paths = options.x509_trusted_cert_paths
        self._x509_revoked_certs: Set[SSHX509Certificate] = set()
        self._x509_trusted_subjects: Sequence['X509NamePattern'] = []
        self._x509_revoked_subjects: Sequence['X509NamePattern'] = []
        self._x509_purposes = options.x509_purposes

        self._kex_algs = options.kex_algs
        self._enc_algs = options.encryption_algs
        self._mac_algs = options.mac_algs
        self._cmp_algs = options.compression_algs
        self._sig_algs = options.signature_algs

        self._host_based_auth = options.host_based_auth
        self._public_key_auth = options.public_key_auth
        self._kbdint_auth = options.kbdint_auth
        self._password_auth = options.password_auth

        self._kex: Optional[Kex] = None
        self._kexinit_sent = False
        self._kex_complete = False
        self._ignore_first_kex = False
        self._strict_kex = False

        self._gss: Optional[GSSBase] = None
        self._gss_kex = False
        self._gss_auth = False
        self._gss_kex_auth = False
        self._gss_mic_auth = False

        self._preferred_auth: Optional[Sequence[bytes]] = None

        self._rekey_bytes = options.rekey_bytes
        self._rekey_seconds = options.rekey_seconds
        self._rekey_bytes_sent = 0
        self._rekey_time = 0.

        self._keepalive_count = 0
        self._keepalive_count_max = options.keepalive_count_max
        self._keepalive_interval = options.keepalive_interval
        self._keepalive_timer: Optional[asyncio.TimerHandle] = None

        self._tunnel: Optional[_TunnelProtocol] = None

        self._enc_alg_cs = b''
        self._enc_alg_sc = b''

        self._mac_alg_cs = b''
        self._mac_alg_sc = b''

        self._cmp_alg_cs = b''
        self._cmp_alg_sc = b''

        self._can_send_ext_info = False
        self._extensions_to_send: 'OrderedDict[bytes, bytes]' = OrderedDict()

        self._can_recv_ext_info = False

        self._server_sig_algs: Set[bytes] = set()

        self._next_service: Optional[bytes] = None

        self._agent: Optional[SSHAgentClient] = None

        self._auth: Optional[Auth] = None
        self._auth_in_progress = False
        self._auth_complete = False
        self._auth_final = False
        self._auth_methods = [b'none']
        self._auth_was_trivial = True
        self._username = ''

        self._channels: Dict[int, SSHChannel] = {}
        self._next_recv_chan = 0

        self._global_request_queue: List[_GlobalRequest] = []
        self._global_request_waiters: \
            'List[asyncio.Future[_GlobalRequestResult]]' = []

        self._local_listeners: Dict[ListenKey, SSHListener] = {}

        self._x11_listener: Union[None, SSHX11ClientListener,
                                  SSHX11ServerListener] = None

        self._tasks: Set[asyncio.Task[None]] = set()
        self._close_event = asyncio.Event()

        self._server_host_key_algs: Optional[Sequence[bytes]] = None

        self._logger = logger.get_child(
            context=f'conn={self._get_next_conn()}')

        self._login_timer: Optional[asyncio.TimerHandle]

        if options.login_timeout:
            self._login_timer = self._loop.call_later(
                options.login_timeout, self._login_timer_callback)
        else:
            self._login_timer = None

        self._disable_trivial_auth = False

    async def __aenter__(self) -> Self:
        """Allow SSHConnection to be used as an async context manager"""

        return self

    async def __aexit__(self, _exc_type: Optional[Type[BaseException]],
                        _exc_value: Optional[BaseException],
                        _traceback: Optional[TracebackType]) -> bool:
        """Wait for connection close when used as an async context manager"""

        if not self._loop.is_closed(): # pragma: no branch
            self.close()

        await self.wait_closed()
        return False

    @property
    def logger(self) -> SSHLogger:
        """A logger associated with this connection"""

        return self._logger

    def _cleanup(self, exc: Optional[Exception]) -> None:
        """Clean up this connection"""

        self._cancel_keepalive_timer()

        for chan in list(self._channels.values()):
            chan.process_connection_close(exc)

        for listener in list(self._local_listeners.values()):
            listener.close()

        while self._global_request_waiters:
            self._process_global_response(MSG_REQUEST_FAILURE, 0,
                                          SSHPacket(b''))

        if self._auth:
            self._auth.cancel()
            self._auth = None

        if self._error_handler:
            self._error_handler(self, exc)
            self._acceptor = None
            self._error_handler = None

        if self._wait and self._waiter and not self._waiter.cancelled():
            if exc:
                self._waiter.set_exception(exc)
            else: # pragma: no cover
                self._waiter.set_result(None)

            self._wait = None

        if self._owner: # pragma: no branch
            self._owner.connection_lost(exc)
            self._owner = None

        self._cancel_login_timer()
        self._close_event.set()

        self._inpbuf = b''

        if self._tunnel:
            self._tunnel.close()
            self._tunnel = None

    def _cancel_login_timer(self) -> None:
        """Cancel the login timer"""

        if self._login_timer:
            self._login_timer.cancel()
            self._login_timer = None

    def _login_timer_callback(self) -> None:
        """Close the connection if authentication hasn't completed yet"""

        self._login_timer = None

        self.connection_lost(ConnectionLost('Login timeout expired'))

    def _cancel_keepalive_timer(self) -> None:
        """Cancel the keepalive timer"""

        if self._keepalive_timer:
            self._keepalive_timer.cancel()
            self._keepalive_timer = None

    def _set_keepalive_timer(self) -> None:
        """Set the keepalive timer"""

        if self._keepalive_interval:
            self._keepalive_timer = self._loop.call_later(
                self._keepalive_interval, self._keepalive_timer_callback)

    def _reset_keepalive_timer(self) -> None:
        """Reset the keepalive timer"""

        if self._auth_complete:
            self._cancel_keepalive_timer()
            self._set_keepalive_timer()

    async def _make_keepalive_request(self) -> None:
        """Send keepalive request"""

        self.logger.debug1('Sending keepalive request')

        await self._make_global_request(b'keepalive@openssh.com')

        if self._keepalive_timer:
            self.logger.debug1('Got keepalive response')

        self._keepalive_count = 0

    def _keepalive_timer_callback(self) -> None:
        """Handle keepalive check"""

        self._keepalive_count += 1

        if self._keepalive_count > self._keepalive_count_max:
            self.connection_lost(
                ConnectionLost(('Server' if self.is_client() else 'Client') +
                               ' not responding to keepalive'))
        else:
            self._set_keepalive_timer()
            self.create_task(self._make_keepalive_request())

    def _force_close(self, exc: Optional[Exception]) -> None:
        """Force this connection to close immediately"""

        if not self._transport:
            return

        self._loop.call_soon(self._transport.abort)
        self._transport = None

        self._loop.call_soon(self._cleanup, exc)

    def _reap_task(self, task_logger: Optional[SSHLogger],
                   task: 'asyncio.Task[None]') -> None:
        """Collect result of an async task, reporting errors"""

        self._tasks.discard(task)

        # pylint: disable=broad-except
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except DisconnectError as exc:
            self._send_disconnect(exc.code, exc.reason, exc.lang)
            self._force_close(exc)
        except Exception:
            self.internal_error(error_logger=task_logger)

    def create_task(self, coro: Awaitable[None],
                    task_logger: Optional[SSHLogger] = None) -> \
            'asyncio.Task[None]':
        """Create an asynchronous task which catches and reports errors"""

        task = asyncio.ensure_future(coro)
        task.add_done_callback(partial(self._reap_task, task_logger))
        self._tasks.add(task)

        return task

    def is_client(self) -> bool:
        """Return if this is a client connection"""

        return not self._server

    def is_server(self) -> bool:
        """Return if this is a server connection"""

        return self._server

    def is_closed(self):
        """Return whether the connection is closed"""

        return self._close_event.is_set()

    def get_owner(self) -> Optional[Union[SSHClient, SSHServer]]:
        """Return the SSHClient or SSHServer which owns this connection"""

        return self._owner

    def get_hash_prefix(self) -> bytes:
        """Return the bytes used in calculating unique connection hashes

           This methods returns a packetized version of the client and
           server version and kexinit strings which is needed to perform
           key exchange hashes.

        """

        return b''.join((String(self._client_version),
                         String(self._server_version),
                         String(self._client_kexinit),
                         String(self._server_kexinit)))

    def set_tunnel(self, tunnel: Optional[_TunnelProtocol]) -> None:
        """Set tunnel used to open this connection"""

        self._tunnel = tunnel

    def _match_known_hosts(self, known_hosts: KnownHostsArg, host: str,
                           addr: str, port: Optional[int]) -> None:
        """Determine the set of trusted host keys and certificates"""

        trusted_host_keys, trusted_ca_keys, revoked_host_keys, \
            trusted_x509_certs, revoked_x509_certs, \
            trusted_x509_subjects, revoked_x509_subjects = \
                match_known_hosts(known_hosts, host, addr, port)

        assert self._trusted_host_keys is not None

        for key in trusted_host_keys:
            self._trusted_host_keys.add(key)

            if key.algorithm not in self._trusted_host_key_algs:
                self._trusted_host_key_algs.extend(key.sig_algorithms)

        self._trusted_ca_keys = set(trusted_ca_keys)
        self._revoked_host_keys = set(revoked_host_keys)

        if self._x509_trusted_certs is not None:
            self._x509_trusted_certs = list(self._x509_trusted_certs)
            self._x509_trusted_certs.extend(trusted_x509_certs)
            self._x509_revoked_certs = set(revoked_x509_certs)

            self._x509_trusted_subjects = trusted_x509_subjects
            self._x509_revoked_subjects = revoked_x509_subjects

    def _validate_openssh_host_certificate(
            self, host: str, addr: str, port: int,
            cert: SSHOpenSSHCertificate) -> SSHKey:
        """Validate an OpenSSH host certificate"""

        if self._trusted_ca_keys is not None:
            if cert.signing_key in self._revoked_host_keys:
                raise ValueError('Host CA key is revoked')

            if not self._owner: # pragma: no cover
                raise ValueError('Connection closed')

            if cert.signing_key not in self._trusted_ca_keys and \
               not self._owner.validate_host_ca_key(host, addr, port,
                                                    cert.signing_key):
                raise ValueError('Host CA key is not trusted')

            cert.validate(CERT_TYPE_HOST, host)

        return cert.key

    def _validate_x509_host_certificate_chain(
            self, host: str, cert: SSHX509CertificateChain) -> SSHKey:
        """Validate an X.509 host certificate"""

        if (self._x509_revoked_subjects and
                any(pattern.matches(cert.subject)
                    for pattern in self._x509_revoked_subjects)):
            raise ValueError('X.509 subject name is revoked')

        if (self._x509_trusted_subjects and
                not any(pattern.matches(cert.subject)
                        for pattern in self._x509_trusted_subjects)):
            raise ValueError('X.509 subject name is not trusted')

        # Only validate hostname against X.509 certificate host
        # principals when there are no X.509 trusted subject
        # entries matched in known_hosts.
        if self._x509_trusted_subjects:
            host = ''

        assert self._x509_trusted_certs is not None

        cert.validate_chain(self._x509_trusted_certs,
                            self._x509_trusted_cert_paths,
                            self._x509_revoked_certs,
                            self._x509_purposes,
                            host_principal=host)

        return cert.key

    def _validate_host_key(self, host: str, addr: str, port: int,
                           key_data: bytes) -> SSHKey:
        """Validate and return a trusted host key"""

        try:
            cert = decode_ssh_certificate(key_data)
        except KeyImportError:
            pass
        else:
            if cert.is_x509_chain:
                return self._validate_x509_host_certificate_chain(
                    host, cast(SSHX509CertificateChain, cert))
            else:
                return self._validate_openssh_host_certificate(
                    host, addr, port, cast(SSHOpenSSHCertificate, cert))

        try:
            key = decode_ssh_public_key(key_data)
        except KeyImportError:
            pass
        else:
            if self._trusted_host_keys is not None:
                if key in self._revoked_host_keys:
                    raise ValueError('Host key is revoked')

                if not self._owner: # pragma: no cover
                    raise ValueError('Connection closed')

                if key not in self._trusted_host_keys and \
                   not self._owner.validate_host_public_key(host, addr,
                                                            port, key):
                    raise ValueError('Host key is not trusted')

            return key

        raise ValueError('Unable to decode host key')

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Handle a newly opened connection"""

        self._transport = cast(asyncio.Transport, transport)

        sock = cast(socket.socket, transport.get_extra_info('socket'))

        if sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE,
                            1 if self._tcp_keepalive else 0)

            if sock.family in (socket.AF_INET, socket.AF_INET6):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        sockname = cast(SockAddr, transport.get_extra_info('sockname'))

        if sockname: # pragma: no branch
            self._local_addr, self._local_port = sockname[:2]

        peername = cast(SockAddr, transport.get_extra_info('peername'))

        if peername: # pragma: no branch
            self._peer_addr, self._peer_port = peername[:2]

        self._owner = self._protocol_factory()

        # pylint: disable=broad-except
        try:
            self._connection_made()
            self._owner.connection_made(self) # type: ignore
            self._send_version()
        except Exception:
            self._loop.call_soon(self.internal_error, sys.exc_info())

    def connection_lost(self, exc: Optional[Exception] = None) -> None:
        """Handle the closing of a connection"""

        if exc is None and self._transport:
            exc = ConnectionLost('Connection lost')

        self._force_close(exc)

    def internal_error(self, exc_info: Optional[OptExcInfo] = None,
                       error_logger: Optional[SSHLogger] = None) -> None:
        """Handle a fatal error in connection processing"""

        if not exc_info:
            exc_info = sys.exc_info()

        if not error_logger:
            error_logger = self.logger

        error_logger.debug1('Uncaught exception', exc_info=exc_info)
        self._force_close(cast(Exception, exc_info[1]))

    def session_started(self) -> None:
        """Handle session start when opening tunneled SSH connection"""

    # pylint: disable=arguments-differ
    def data_received(self, data: bytes, datatype: DataType = None) -> None:
        """Handle incoming data on the connection"""

        # pylint: disable=unused-argument

        self._inpbuf += data

        self._recv_data()
    # pylint: enable=arguments-differ

    def eof_received(self) -> None:
        """Handle an incoming end of file on the connection"""

        self.connection_lost(None)

    def pause_writing(self) -> None:
        """Handle a request from the transport to pause writing data"""

        # Do nothing with this for now

    def resume_writing(self) -> None:
        """Handle a request from the transport to resume writing data"""

        # Do nothing with this for now

    def add_channel(self, chan: SSHChannel[AnyStr]) -> int:
        """Add a new channel, returning its channel number"""

        if not self._transport:
            raise ChannelOpenError(OPEN_CONNECT_FAILED,
                                   'SSH connection closed')

        while self._next_recv_chan in self._channels: # pragma: no cover
            self._next_recv_chan = (self._next_recv_chan + 1) & 0xffffffff

        recv_chan = self._next_recv_chan
        self._next_recv_chan = (self._next_recv_chan + 1) & 0xffffffff

        self._channels[recv_chan] = chan
        return recv_chan

    def remove_channel(self, recv_chan: int) -> None:
        """Remove the channel with the specified channel number"""

        del self._channels[recv_chan]

    def get_gss_context(self) -> GSSBase:
        """Return the GSS context associated with this connection"""

        assert self._gss is not None
        return self._gss

    def enable_gss_kex_auth(self) -> None:
        """Enable GSS key exchange authentication"""

        self._gss_kex_auth = self._gss_auth

    def _choose_alg(self, alg_type: str, local_algs: Sequence[bytes],
                    remote_algs: Sequence[bytes]) -> bytes:
        """Choose a common algorithm from the client & server lists

           This method returns the earliest algorithm on the client's
           list which is supported by the server.

        """

        if self.is_client():
            client_algs, server_algs = local_algs, remote_algs
        else:
            client_algs, server_algs = remote_algs, local_algs

        for alg in client_algs:
            if alg in server_algs:
                return alg

        raise KeyExchangeFailed(
            f'No matching {alg_type} algorithm found, sent '
            f'{b",".join(local_algs).decode("ascii")} and received '
            f'{b",".join(remote_algs).decode("ascii")}')

    def _get_extra_kex_algs(self) -> List[bytes]:
        """Return the extra kex algs to add"""

        if self.is_client():
            return [b'ext-info-c', b'kex-strict-c-v00@openssh.com']
        else:
            return [b'ext-info-s', b'kex-strict-s-v00@openssh.com']

    def _send(self, data: bytes) -> None:
        """Send data to the SSH connection"""

        if self._transport:
            try:
                self._transport.write(data)
            except ConnectionError: # pragma: no cover
                pass

    def _send_version(self) -> None:
        """Start the SSH handshake"""

        version = b'SSH-2.0-' + self._version

        self.logger.debug1('Sending version %s', version)

        if self.is_client():
            self._client_version = version
            self.set_extra_info(client_version=version.decode('ascii'))
        else:
            self._server_version = version
            self.set_extra_info(server_version=version.decode('ascii'))

        self._send(version + b'\r\n')

    def _recv_data(self) -> None:
        """Parse received data"""

        self._reset_keepalive_timer()

        # pylint: disable=broad-except
        try:
            while self._inpbuf and self._recv_handler():
                pass
        except DisconnectError as exc:
            self._send_disconnect(exc.code, exc.reason, exc.lang)
            self._force_close(exc)
        except Exception:
            self.internal_error()

    def _recv_version(self) -> bool:
        """Receive and parse the remote SSH version"""

        idx = self._inpbuf.find(b'\n', 0, _MAX_BANNER_LINE_LEN)
        if idx < 0:
            if len(self._inpbuf) >= _MAX_BANNER_LINE_LEN:
                self._force_close(ProtocolError('Banner line too long'))

            return False

        version = self._inpbuf[:idx]
        if version.endswith(b'\r'):
            version = version[:-1]

        self._inpbuf = self._inpbuf[idx+1:]

        if (version.startswith(b'SSH-2.0-') or
                (self.is_client() and version.startswith(b'SSH-1.99-'))):
            if len(version) > _MAX_VERSION_LINE_LEN:
                self._force_close(ProtocolError('Version too long'))

            # Accept version 2.0, or 1.99 if we're a client
            if self.is_server():
                self._client_version = version
                self.set_extra_info(client_version=version.decode('ascii'))
            else:
                self._server_version = version
                self.set_extra_info(server_version=version.decode('ascii'))

            self.logger.debug1('Received version %s', version)

            self._send_kexinit()
            self._kexinit_sent = True
            self._recv_handler = self._recv_pkthdr
        elif self.is_client() and not version.startswith(b'SSH-'):
            # As a client, ignore the line if it doesn't appear to be a version
            self._banner_lines += 1

            if self._banner_lines > _MAX_BANNER_LINES:
                self._force_close(ProtocolError('Too many banner lines'))
                return False
        else:
            # Otherwise, reject the unknown version
            self._force_close(ProtocolNotSupported('Unsupported SSH version'))
            return False

        return True

    def _recv_pkthdr(self) -> bool:
        """Receive and parse an SSH packet header"""

        if len(self._inpbuf) < self._recv_blocksize:
            return False

        self._packet = self._inpbuf[:self._recv_blocksize]
        self._inpbuf = self._inpbuf[self._recv_blocksize:]

        if self._recv_encryption:
            self._packet, pktlen = \
                self._recv_encryption.decrypt_header(self._recv_seq,
                                                     self._packet, 4)
        else:
            pktlen = self._packet[:4]

        self._pktlen = int.from_bytes(pktlen, 'big')
        self._recv_handler = self._recv_packet
        return True

    def _recv_packet(self) -> bool:
        """Receive the remainder of an SSH packet and process it"""

        rem = 4 + self._pktlen + self._recv_macsize - self._recv_blocksize
        if len(self._inpbuf) < rem:
            return False

        seq = self._recv_seq
        rest = self._inpbuf[:rem-self._recv_macsize]
        mac = self._inpbuf[rem-self._recv_macsize:rem]

        if self._recv_encryption:
            packet_data = self._recv_encryption.decrypt_packet(
                seq, self._packet, rest, 4, mac)

            if not packet_data:
                raise MACError('MAC verification failed')
        else:
            packet_data = self._packet[4:] + rest

        self._inpbuf = self._inpbuf[rem:]
        self._packet = b''

        orig_payload = packet_data[1:-packet_data[0]]

        if self._decompressor and (self._auth_complete or
                                   not self._decompress_after_auth):
            payload = self._decompressor.decompress(orig_payload)

            if payload is None:
                raise CompressionError('Decompression failed')
        else:
            payload = orig_payload

        packet = SSHPacket(payload)
        pkttype = packet.get_byte()
        handler: SSHPacketHandler = self
        skip_reason = ''
        exc_reason = ''

        if MSG_KEX_FIRST <= pkttype <= MSG_KEX_LAST:
            if self._kex:
                if self._ignore_first_kex: # pragma: no cover
                    skip_reason = 'ignored first kex'
                    self._ignore_first_kex = False
                else:
                    handler = self._kex
            else:
                skip_reason = 'kex not in progress'
                exc_reason = 'Key exchange not in progress'
        elif self._strict_kex and not self._recv_encryption and \
                MSG_IGNORE <= pkttype <= MSG_DEBUG:
            skip_reason = 'strict kex violation'
            exc_reason = 'Strict key exchange violation: ' \
                         f'unexpected packet type {pkttype} received'
        elif MSG_USERAUTH_FIRST <= pkttype <= MSG_USERAUTH_LAST:
            if self._auth:
                handler = self._auth
            else:
                skip_reason = 'auth not in progress'
                exc_reason = 'Authentication not in progress'
        elif pkttype > MSG_KEX_LAST and not self._recv_encryption:
            skip_reason = 'invalid request before kex complete'
            exc_reason = 'Invalid request before key exchange was complete'
        elif pkttype > MSG_USERAUTH_LAST and not self._auth_complete:
            skip_reason = 'invalid request before auth complete'
            exc_reason = 'Invalid request before authentication was complete'
        elif MSG_CHANNEL_FIRST <= pkttype <= MSG_CHANNEL_LAST:
            try:
                recv_chan = packet.get_uint32()
            except PacketDecodeError:
                skip_reason = 'incomplete channel request'
                exc_reason = 'Incomplete channel request received'
            else:
                try:
                    handler = self._channels[recv_chan]
                except KeyError:
                    skip_reason = 'invalid channel number'
                    exc_reason = f'Invalid channel number {recv_chan} received'

        handler.log_received_packet(pkttype, seq, packet, skip_reason)

        if not skip_reason:
            try:
                result = handler.process_packet(pkttype, seq, packet)
            except PacketDecodeError as exc:
                raise ProtocolError(str(exc)) from None

            if inspect.isawaitable(result):
                # Buffer received data until current packet is processed
                self._recv_handler = lambda: False

                task = self.create_task(result)
                task.add_done_callback(functools.partial(
                    self._finish_recv_packet, pkttype, seq, is_async=True))

                return False
            elif not result:
                if self._strict_kex and not self._recv_encryption:
                    exc_reason = 'Strict key exchange violation: ' \
                                 f'unexpected packet type {pkttype} received'
                else:
                    self.logger.debug1('Unknown packet type %d received',
                                       pkttype)
                    self.send_packet(MSG_UNIMPLEMENTED, UInt32(seq))

        if exc_reason:
            raise ProtocolError(exc_reason)

        self._finish_recv_packet(pkttype, seq)
        return True

    def _finish_recv_packet(self, pkttype: int, seq: int,
                            _task: Optional[asyncio.Task] = None,
                            is_async: bool = False) -> None:
        """Finish processing a packet"""

        if pkttype > MSG_USERAUTH_LAST:
            self._auth_final = True

        if self._transport:
            if self._recv_seq == 0xffffffff and not self._recv_encryption:
                raise ProtocolError('Sequence rollover before kex complete')

            if pkttype == MSG_NEWKEYS and self._strict_kex:
                self._recv_seq = 0
            else:
                self._recv_seq = (seq + 1) & 0xffffffff

        self._recv_handler = self._recv_pkthdr

        if is_async and self._inpbuf:
            self._recv_data()

    def send_packet(self, pkttype: int, *args: bytes,
                    handler: Optional[SSHPacketLogger] = None) -> None:
        """Send an SSH packet"""

        if (self._auth_complete and self._kex_complete and
                (self._rekey_bytes_sent >= self._rekey_bytes or
                 (self._rekey_seconds and
                  time.monotonic() >= self._rekey_time))):
            self._send_kexinit()
            self._kexinit_sent = True

        if (((pkttype in {MSG_DEBUG, MSG_SERVICE_REQUEST, MSG_SERVICE_ACCEPT} or
              pkttype > MSG_KEX_LAST) and not self._kex_complete) or
                (pkttype == MSG_USERAUTH_BANNER and
                 not (self._auth_in_progress or self._auth_complete)) or
                (pkttype > MSG_USERAUTH_LAST and not self._auth_complete)):
            self._deferred_packets.append((pkttype, args))
            return

        # If we're encrypting and we have no data outstanding, insert an
        # ignore packet into the stream
        if self._send_encryption and pkttype > MSG_KEX_LAST:
            self.send_packet(MSG_IGNORE, String(b''))

        orig_payload = Byte(pkttype) + b''.join(args)

        if self._compressor and (self._auth_complete or
                                 not self._compress_after_auth):
            payload = self._compressor.compress(orig_payload)

            if payload is None: # pragma: no cover
                raise CompressionError('Compression failed')
        else:
            payload = orig_payload

        padlen = -(self._send_enchdrlen + len(payload)) % self._send_blocksize
        if padlen < 4:
            padlen += self._send_blocksize

        packet = Byte(padlen) + payload + os.urandom(padlen)
        pktlen = len(packet)
        hdr = UInt32(pktlen)
        seq = self._send_seq

        if self._send_encryption:
            packet, mac = self._send_encryption.encrypt_packet(seq, hdr, packet)
        else:
            packet = hdr + packet
            mac = b''

        self._send(packet + mac)

        if self._send_seq == 0xffffffff and not self._send_encryption:
            self._send_seq = 0
            raise ProtocolError('Sequence rollover before kex complete')

        if pkttype == MSG_NEWKEYS and self._strict_kex:
            self._send_seq = 0
        else:
            self._send_seq = (seq + 1) & 0xffffffff

        if self._kex_complete:
            self._rekey_bytes_sent += pktlen

        if not handler:
            handler = self

        handler.log_sent_packet(pkttype, seq, orig_payload)

    def _send_deferred_packets(self) -> None:
        """Send packets deferred due to key exchange or auth"""

        deferred_packets = self._deferred_packets
        self._deferred_packets = []

        for pkttype, args in deferred_packets:
            self.send_packet(pkttype, *args)

    def _send_disconnect(self, code: int, reason: str, lang: str) -> None:
        """Send a disconnect packet"""

        self.logger.info('Sending disconnect: %s (%d)', reason, code)

        self.send_packet(MSG_DISCONNECT, UInt32(code),
                         String(reason), String(lang))

    def _send_kexinit(self) -> None:
        """Start a key exchange"""

        self._kex_complete = False
        self._rekey_bytes_sent = 0

        if self._rekey_seconds:
            self._rekey_time = time.monotonic() + self._rekey_seconds

        if self._gss_kex:
            assert self._gss is not None
            gss_mechs = self._gss.mechs
        else:
            gss_mechs = []

        kex_algs = expand_kex_algs(self._kex_algs, gss_mechs,
                                   bool(self._server_host_key_algs)) + \
                   self._get_extra_kex_algs()

        host_key_algs = self._server_host_key_algs or [b'null']

        self.logger.debug1('Requesting key exchange')
        self.logger.debug2('  Key exchange algs: %s', kex_algs)
        self.logger.debug2('  Host key algs: %s', host_key_algs)
        self.logger.debug2('  Encryption algs: %s', self._enc_algs)
        self.logger.debug2('  MAC algs: %s', self._mac_algs)
        self.logger.debug2('  Compression algs: %s', self._cmp_algs)

        cookie = os.urandom(16)
        kex_algs = NameList(kex_algs)
        host_key_algs = NameList(host_key_algs)
        enc_algs = NameList(self._enc_algs)
        mac_algs = NameList(self._mac_algs)
        cmp_algs = NameList(self._cmp_algs)
        langs = NameList([])

        packet = b''.join((Byte(MSG_KEXINIT), cookie, kex_algs, host_key_algs,
                           enc_algs, enc_algs, mac_algs, mac_algs, cmp_algs,
                           cmp_algs, langs, langs, Boolean(False), UInt32(0)))

        if self.is_server():
            self._server_kexinit = packet
        else:
            self._client_kexinit = packet

        self.send_packet(MSG_KEXINIT, packet[1:])

    def _send_ext_info(self) -> None:
        """Send extension information"""

        packet = UInt32(len(self._extensions_to_send))

        self.logger.debug2('Sending extension info')

        for name, value in self._extensions_to_send.items():
            packet += String(name) + String(value)

            self.logger.debug2('  %s: %s', name, value)

        self.send_packet(MSG_EXT_INFO, packet)

    def send_newkeys(self, k: bytes, h: bytes) -> None:
        """Finish a key exchange and send a new keys message"""

        if not self._session_id:
            first_kex = True
            self._session_id = h
        else:
            first_kex = False

        enc_keysize_cs, enc_ivsize_cs, enc_blocksize_cs, \
        mac_keysize_cs, mac_hashsize_cs, etm_cs = \
            get_encryption_params(self._enc_alg_cs, self._mac_alg_cs)

        enc_keysize_sc, enc_ivsize_sc, enc_blocksize_sc, \
        mac_keysize_sc, mac_hashsize_sc, etm_sc = \
            get_encryption_params(self._enc_alg_sc, self._mac_alg_sc)

        if mac_keysize_cs == 0:
            self._mac_alg_cs = self._enc_alg_cs

        if mac_keysize_sc == 0:
            self._mac_alg_sc = self._enc_alg_sc

        cmp_after_auth_cs = get_compression_params(self._cmp_alg_cs)
        cmp_after_auth_sc = get_compression_params(self._cmp_alg_sc)

        self.logger.debug2('  Client to server:')
        self.logger.debug2('    Encryption alg: %s', self._enc_alg_cs)
        self.logger.debug2('    MAC alg: %s', self._mac_alg_cs)
        self.logger.debug2('    Compression alg: %s', self._cmp_alg_cs)
        self.logger.debug2('  Server to client:')
        self.logger.debug2('    Encryption alg: %s', self._enc_alg_sc)
        self.logger.debug2('    MAC alg: %s', self._mac_alg_sc)
        self.logger.debug2('    Compression alg: %s', self._cmp_alg_sc)

        assert self._kex is not None

        iv_cs = self._kex.compute_key(k, h, b'A', self._session_id,
                                      enc_ivsize_cs)
        iv_sc = self._kex.compute_key(k, h, b'B', self._session_id,
                                      enc_ivsize_sc)
        enc_key_cs = self._kex.compute_key(k, h, b'C', self._session_id,
                                           enc_keysize_cs)
        enc_key_sc = self._kex.compute_key(k, h, b'D', self._session_id,
                                           enc_keysize_sc)
        mac_key_cs = self._kex.compute_key(k, h, b'E', self._session_id,
                                           mac_keysize_cs)
        mac_key_sc = self._kex.compute_key(k, h, b'F', self._session_id,
                                           mac_keysize_sc)
        self._kex = None

        next_enc_cs = get_encryption(self._enc_alg_cs, enc_key_cs, iv_cs,
                                     self._mac_alg_cs, mac_key_cs, etm_cs)
        next_enc_sc = get_encryption(self._enc_alg_sc, enc_key_sc, iv_sc,
                                     self._mac_alg_sc, mac_key_sc, etm_sc)

        self.send_packet(MSG_NEWKEYS)

        self._extensions_to_send[b'global-requests-ok'] = b''

        if self.is_client():
            self._send_encryption = next_enc_cs
            self._send_enchdrlen = 1 if etm_cs else 5
            self._send_blocksize = max(8, enc_blocksize_cs)
            self._compressor = get_compressor(self._cmp_alg_cs)
            self._compress_after_auth = cmp_after_auth_cs

            self._next_recv_encryption = next_enc_sc
            self._next_recv_blocksize = max(8, enc_blocksize_sc)
            self._next_recv_macsize = mac_hashsize_sc
            self._next_decompressor = get_decompressor(self._cmp_alg_sc)
            self._next_decompress_after_auth = cmp_after_auth_sc

            self.set_extra_info(
                send_cipher=self._enc_alg_cs.decode('ascii'),
                send_mac=self._mac_alg_cs.decode('ascii'),
                send_compression=self._cmp_alg_cs.decode('ascii'),
                recv_cipher=self._enc_alg_sc.decode('ascii'),
                recv_mac=self._mac_alg_sc.decode('ascii'),
                recv_compression=self._cmp_alg_sc.decode('ascii'))

            if first_kex:
                if self._wait == 'kex' and self._waiter and \
                        not self._waiter.cancelled():
                    self._waiter.set_result(None)
                    self._wait = None
                    return
        else:
            self._extensions_to_send[b'server-sig-algs'] = \
                b','.join(self._sig_algs)

            self._send_encryption = next_enc_sc
            self._send_enchdrlen = 1 if etm_sc else 5
            self._send_blocksize = max(8, enc_blocksize_sc)
            self._compressor = get_compressor(self._cmp_alg_sc)
            self._compress_after_auth = cmp_after_auth_sc

            self._next_recv_encryption = next_enc_cs
            self._next_recv_blocksize = max(8, enc_blocksize_cs)
            self._next_recv_macsize = mac_hashsize_cs
            self._next_decompressor = get_decompressor(self._cmp_alg_cs)
            self._next_decompress_after_auth = cmp_after_auth_cs

            self.set_extra_info(
                send_cipher=self._enc_alg_sc.decode('ascii'),
                send_mac=self._mac_alg_sc.decode('ascii'),
                send_compression=self._cmp_alg_sc.decode('ascii'),
                recv_cipher=self._enc_alg_cs.decode('ascii'),
                recv_mac=self._mac_alg_cs.decode('ascii'),
                recv_compression=self._cmp_alg_cs.decode('ascii'))

        if self._can_send_ext_info:
            self._send_ext_info()
            self._can_send_ext_info = False

        self._kex_complete = True

        if first_kex:
            if self.is_client():
                self.send_service_request(_USERAUTH_SERVICE)
            else:
                self._next_service = _USERAUTH_SERVICE

        self._send_deferred_packets()

    def send_service_request(self, service: bytes) -> None:
        """Send a service request"""

        self.logger.debug2('Requesting service %s', service)

        self._next_service = service
        self.send_packet(MSG_SERVICE_REQUEST, String(service))

    def _get_userauth_request_packet(self, method: bytes,
                                     args: Tuple[bytes, ...]) -> bytes:
        """Get packet data for a user authentication request"""

        return b''.join((Byte(MSG_USERAUTH_REQUEST), String(self._username),
                         String(_CONNECTION_SERVICE), String(method)) + args)

    def get_userauth_request_data(self, method: bytes, *args: bytes) -> bytes:
        """Get signature data for a user authentication request"""

        return (String(self._session_id) +
                self._get_userauth_request_packet(method, args))

    def send_userauth_packet(self, pkttype: int, *args: bytes,
                             handler: Optional[SSHPacketLogger] = None,
                             trivial: bool = True) -> None:
        """Send a user authentication packet"""

        self._auth_was_trivial &= trivial
        self.send_packet(pkttype, *args, handler=handler)

    async def send_userauth_request(self, method: bytes, *args: bytes,
                                    key: Optional[SigningKey] = None,
                                    trivial: bool = True) -> None:
        """Send a user authentication request"""

        packet = self._get_userauth_request_packet(method, args)

        if key:
            data = String(self._session_id) + packet

            sign_async: Optional[Callable[[bytes], Awaitable[bytes]]] = \
                getattr(key, 'sign_async', None)

            if sign_async:
                # pylint: disable=not-callable
                sig = await sign_async(data)
            elif getattr(key, 'use_executor', False):
                sig = await self._loop.run_in_executor(None, key.sign, data)
            else:
                sig = key.sign(data)

            packet += String(sig)

        self.send_userauth_packet(MSG_USERAUTH_REQUEST, packet[1:],
                                  trivial=trivial)

    def send_userauth_failure(self, partial_success: bool) -> None:
        """Send a user authentication failure response"""

        methods = get_supported_server_auth_methods(
            cast(SSHServerConnection, self))

        self.logger.debug2('Remaining auth methods: %s', methods or 'None')

        self._auth = None
        self.send_packet(MSG_USERAUTH_FAILURE, NameList(methods),
                         Boolean(partial_success))

    def send_userauth_success(self) -> None:
        """Send a user authentication success response"""

        self.logger.info('Auth for user %s succeeded', self._username)

        self.send_packet(MSG_USERAUTH_SUCCESS)
        self._auth = None
        self._auth_in_progress = False
        self._auth_complete = True
        self._next_service = None
        self.set_extra_info(username=self._username)
        self._send_deferred_packets()

        self._cancel_login_timer()
        self._set_keepalive_timer()

        if self._owner: # pragma: no branch
            self._owner.auth_completed()

        if self._acceptor:
            result = self._acceptor(self)

            if inspect.isawaitable(result):
                assert result is not None
                self.create_task(result)

            self._acceptor = None
            self._error_handler = None

        if self._wait == 'auth' and self._waiter and \
                not self._waiter.cancelled():
            self._waiter.set_result(None)
            self._wait = None
            return

        # This method is only in SSHServerConnection
        # pylint: disable=no-member
        cast(SSHServerConnection, self).send_server_host_keys()

    def send_channel_open_confirmation(self, send_chan: int, recv_chan: int,
                                       recv_window: int, recv_pktsize: int,
                                       *result_args: bytes) -> None:
        """Send a channel open confirmation"""

        self.send_packet(MSG_CHANNEL_OPEN_CONFIRMATION, UInt32(send_chan),
                         UInt32(recv_chan), UInt32(recv_window),
                         UInt32(recv_pktsize), *result_args)

    def send_channel_open_failure(self, send_chan: int, code: int,
                                  reason: str, lang: str) -> None:
        """Send a channel open failure"""

        self.send_packet(MSG_CHANNEL_OPEN_FAILURE, UInt32(send_chan),
                         UInt32(code), String(reason), String(lang))

    def _send_global_request(self, request: bytes, *args: bytes,
                             want_reply: bool = False) -> None:
        """Send a global request"""

        self.send_packet(MSG_GLOBAL_REQUEST, String(request),
                         Boolean(want_reply), *args)

    async def _make_global_request(self, request: bytes,
                                   *args: bytes) -> Tuple[int, SSHPacket]:
        """Send a global request and wait for the response"""

        if not self._transport:
            return MSG_REQUEST_FAILURE, SSHPacket(b'')

        waiter: 'asyncio.Future[_GlobalRequestResult]' = \
            self._loop.create_future()

        self._global_request_waiters.append(waiter)

        self._send_global_request(request, *args, want_reply=True)

        return await waiter

    def _report_global_response(self, result: Union[bool, bytes]) -> None:
        """Report back the response to a previously issued global request"""

        _, _, want_reply = self._global_request_queue.pop(0)

        if want_reply: # pragma: no branch
            if result:
                response = b'' if result is True else cast(bytes, result)
                self.send_packet(MSG_REQUEST_SUCCESS, response)
            else:
                self.send_packet(MSG_REQUEST_FAILURE)

        if self._global_request_queue:
            self._service_next_global_request()

    def _service_next_global_request(self) -> None:
        """Process next item on global request queue"""

        handler, packet, _ = self._global_request_queue[0]
        if callable(handler):
            handler(packet)
        else:
            self._report_global_response(False)

    def _connection_made(self) -> None:
        """Handle the opening of a new connection"""

        raise NotImplementedError

    def _process_disconnect(self, _pkttype: int, _pktid: int,
                            packet: SSHPacket) -> None:
        """Process a disconnect message"""

        code = packet.get_uint32()
        reason_bytes = packet.get_string()
        lang_bytes = packet.get_string()
        packet.check_end()

        try:
            reason = reason_bytes.decode('utf-8')
            lang = lang_bytes.decode('ascii')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid disconnect message') from None

        self.logger.debug1('Received disconnect: %s (%d)', reason, code)

        if code != DISC_BY_APPLICATION or self._wait:
            exc: Optional[Exception] = construct_disc_error(code, reason, lang)
        else:
            exc = None

        self._force_close(exc)

    def _process_ignore(self, _pkttype: int, _pktid: int,
                        packet: SSHPacket) -> None:
        """Process an ignore message"""

        # Work around missing payload bytes in an ignore message
        # in some Cisco SSH servers
        if b'Cisco' not in self._server_version: # pragma: no branch
            _ = packet.get_string()     # data
            packet.check_end()

    def _process_unimplemented(self, _pkttype: int, _pktid: int,
                               packet: SSHPacket) -> None:
        """Process an unimplemented message response"""

        # pylint: disable=no-self-use

        _ = packet.get_uint32()     # seq
        packet.check_end()

    def _process_debug(self, _pkttype: int, _pktid: int,
                       packet: SSHPacket) -> None:
        """Process a debug message"""

        always_display = packet.get_boolean()
        msg_bytes = packet.get_string()
        lang_bytes = packet.get_string()
        packet.check_end()

        try:
            msg = msg_bytes.decode('utf-8')
            lang = lang_bytes.decode('ascii')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid debug message') from None

        self.logger.debug1('Received debug message: %s%s', msg,
                           ' (always display)' if always_display else '')

        if self._owner: # pragma: no branch
            self._owner.debug_msg_received(msg, lang, always_display)

    def _process_service_request(self, _pkttype: int, _pktid: int,
                                 packet: SSHPacket) -> None:
        """Process a service request"""

        service = packet.get_string()
        packet.check_end()

        if self.is_client():
            raise ProtocolError('Unexpected service request received')

        if not self._recv_encryption:
            raise ProtocolError('Service request received before kex complete')

        if service != self._next_service:
            raise ServiceNotAvailable('Unexpected service in service request')

        self.logger.debug2('Accepting request for service %s', service)

        self.send_packet(MSG_SERVICE_ACCEPT, String(service))

        self._next_service = None

        if service == _USERAUTH_SERVICE: # pragma: no branch
            self._auth_in_progress = True
            self._can_recv_ext_info = False
            self._send_deferred_packets()

    def _process_service_accept(self, _pkttype: int, _pktid: int,
                                packet: SSHPacket) -> None:
        """Process a service accept response"""

        service = packet.get_string()
        packet.check_end()

        if self.is_server():
            raise ProtocolError('Unexpected service accept received')

        if not self._recv_encryption:
            raise ProtocolError('Service accept received before kex complete')

        if service != self._next_service:
            raise ServiceNotAvailable('Unexpected service in service accept')

        self.logger.debug2('Request for service %s accepted', service)

        self._next_service = None

        if service == _USERAUTH_SERVICE: # pragma: no branch
            self.logger.info('Beginning auth for user %s', self._username)

            self._auth_in_progress = True

            if self._owner: # pragma: no branch
                self._owner.begin_auth(self._username)

            # This method is only in SSHClientConnection
            # pylint: disable=no-member
            cast('SSHClientConnection', self).try_next_auth()

    def _process_ext_info(self, _pkttype: int, _pktid: int,
                          packet: SSHPacket) -> None:
        """Process extension information"""

        if not self._can_recv_ext_info:
            raise ProtocolError('Unexpected ext_info received')

        extensions: Dict[bytes, bytes] = {}

        self.logger.debug2('Received extension info')

        num_extensions = packet.get_uint32()
        for _ in range(num_extensions):
            name = packet.get_string()
            value = packet.get_string()
            extensions[name] = value

            self.logger.debug2('  %s: %s', name, value)

        packet.check_end()

        if self.is_client():
            self._server_sig_algs = \
                set(extensions.get(b'server-sig-algs', b'').split(b','))

    async def _process_kexinit(self, _pkttype: int, _pktid: int,
                               packet: SSHPacket) -> None:
        """Process a key exchange request"""

        if self._kex:
            raise ProtocolError('Key exchange already in progress')

        _ = packet.get_bytes(16)                        # cookie
        peer_kex_algs = packet.get_namelist()
        peer_host_key_algs = packet.get_namelist()
        enc_algs_cs = packet.get_namelist()
        enc_algs_sc = packet.get_namelist()
        mac_algs_cs = packet.get_namelist()
        mac_algs_sc = packet.get_namelist()
        cmp_algs_cs = packet.get_namelist()
        cmp_algs_sc = packet.get_namelist()
        _ = packet.get_namelist()                       # lang_cs
        _ = packet.get_namelist()                       # lang_sc
        first_kex_follows = packet.get_boolean()
        _ = packet.get_uint32()                         # reserved
        packet.check_end()

        if self.is_server():
            self._client_kexinit = packet.get_consumed_payload()

            if not self._session_id:
                if b'ext-info-c' in peer_kex_algs:
                    self._can_send_ext_info = True

                if b'kex-strict-c-v00@openssh.com' in peer_kex_algs:
                    self._strict_kex = True
        else:
            self._server_kexinit = packet.get_consumed_payload()

            if not self._session_id:
                if b'ext-info-s' in peer_kex_algs:
                    self._can_send_ext_info = True

                if b'kex-strict-s-v00@openssh.com' in peer_kex_algs:
                    self._strict_kex = True

        if self._strict_kex and not self._recv_encryption and \
                self._recv_seq != 0:
            raise ProtocolError('Strict key exchange violation: '
                                'KEXINIT was not the first packet')


        if self._kexinit_sent:
            self._kexinit_sent = False
        else:
            self._send_kexinit()

        if self._gss:
            self._gss.reset()

        if self._gss_kex:
            assert self._gss is not None
            gss_mechs = self._gss.mechs
        else:
            gss_mechs = []

        kex_algs = expand_kex_algs(self._kex_algs, gss_mechs,
                                   bool(self._server_host_key_algs))

        self.logger.debug1('Received key exchange request')
        self.logger.debug2('  Key exchange algs: %s', peer_kex_algs)
        self.logger.debug2('  Host key algs: %s', peer_host_key_algs)
        self.logger.debug2('  Client to server:')
        self.logger.debug2('    Encryption algs: %s', enc_algs_cs)
        self.logger.debug2('    MAC algs: %s', mac_algs_cs)
        self.logger.debug2('    Compression algs: %s', cmp_algs_cs)
        self.logger.debug2('  Server to client:')
        self.logger.debug2('    Encryption algs: %s', enc_algs_sc)
        self.logger.debug2('    MAC algs: %s', mac_algs_sc)
        self.logger.debug2('    Compression algs: %s', cmp_algs_sc)

        kex_alg = self._choose_alg('key exchange', kex_algs, peer_kex_algs)
        self._kex = get_kex(self, kex_alg)
        self._ignore_first_kex = (first_kex_follows and
                                  self._kex.algorithm != peer_kex_algs[0])

        if self.is_server():
            # This method is only in SSHServerConnection
            # pylint: disable=no-member
            if (not cast(SSHServerConnection, self).choose_server_host_key(
                    peer_host_key_algs) and not kex_alg.startswith(b'gss-')):
                raise KeyExchangeFailed('Unable to find compatible '
                                        'server host key')

        self._enc_alg_cs = self._choose_alg('encryption', self._enc_algs,
                                            enc_algs_cs)
        self._enc_alg_sc = self._choose_alg('encryption', self._enc_algs,
                                            enc_algs_sc)

        self._mac_alg_cs = self._choose_alg('MAC', self._mac_algs, mac_algs_cs)
        self._mac_alg_sc = self._choose_alg('MAC', self._mac_algs, mac_algs_sc)

        self._cmp_alg_cs = self._choose_alg('compression', self._cmp_algs,
                                            cmp_algs_cs)
        self._cmp_alg_sc = self._choose_alg('compression', self._cmp_algs,
                                            cmp_algs_sc)

        self.logger.debug1('Beginning key exchange')
        self.logger.debug2('  Key exchange alg: %s', self._kex.algorithm)

        await self._kex.start()

    def _process_newkeys(self, _pkttype: int, _pktid: int,
                         packet: SSHPacket) -> None:
        """Process a new keys message, finishing a key exchange"""

        packet.check_end()

        if self._next_recv_encryption:
            self._recv_encryption = self._next_recv_encryption
            self._recv_blocksize = self._next_recv_blocksize
            self._recv_macsize = self._next_recv_macsize
            self._decompressor = self._next_decompressor
            self._decompress_after_auth = self._next_decompress_after_auth

            self._next_recv_encryption = None
            self._can_recv_ext_info = True
        else:
            raise ProtocolError('New keys not negotiated')

        self.logger.debug1('Completed key exchange')

    def _process_userauth_request(self, _pkttype: int, _pktid: int,
                                  packet: SSHPacket) -> None:
        """Process a user authentication request"""

        username_bytes = packet.get_string()
        service = packet.get_string()
        method = packet.get_string()

        if len(username_bytes) >= _MAX_USERNAME_LEN:
            raise IllegalUserName('Username too long')

        if service != _CONNECTION_SERVICE:
            raise ServiceNotAvailable('Unexpected service in auth request')

        try:
            username = saslprep(username_bytes.decode('utf-8'))
        except (UnicodeDecodeError, SASLPrepError) as exc:
            raise IllegalUserName(str(exc)) from None

        if self.is_client():
            raise ProtocolError('Unexpected userauth request')
        elif self._auth_complete:
            # Silently ignore additional auth requests after auth succeeds,
            # until the client sends a non-auth message
            if self._auth_final:
                raise ProtocolError('Unexpected userauth request')
        else:
            if username != self._username:
                self.logger.info('Beginning auth for user %s', username)

                self._username = username
                begin_auth = True
            else:
                begin_auth = False

            self.create_task(self._finish_userauth(begin_auth, method, packet))

    async def _finish_userauth(self, begin_auth: bool, method: bytes,
                               packet: SSHPacket) -> None:
        """Finish processing a user authentication request"""

        if not self._owner: # pragma: no cover
            return

        if begin_auth:
            # This method is only in SSHServerConnection
            # pylint: disable=no-member
            await cast(SSHServerConnection, self).reload_config()

            result = cast(SSHServer, self._owner).begin_auth(self._username)

            if inspect.isawaitable(result):
                result = await cast(Awaitable[bool], result)

            if not result:
                self.send_userauth_success()
                return

        if not self._owner: # pragma: no cover
            return

        if self._auth:
            self._auth.cancel()

        self._auth = lookup_server_auth(cast(SSHServerConnection, self),
                                             self._username, method, packet)

    def _process_userauth_failure(self, _pkttype: int, _pktid: int,
                                  packet: SSHPacket) -> None:
        """Process a user authentication failure response"""

        auth_methods = packet.get_namelist()
        partial_success = packet.get_boolean()
        packet.check_end()

        self.logger.debug2('Remaining auth methods: %s',
                           auth_methods or 'None')

        if self._wait == 'auth_methods' and self._waiter and \
                not self._waiter.cancelled():
            self._waiter.set_result(None)
            self._auth_methods = list(auth_methods)
            self._wait = None
            return

        if self._preferred_auth:
            self.logger.debug2('Preferred auth methods: %s',
                               self._preferred_auth or 'None')

            auth_methods = [method for method in self._preferred_auth
                            if method in auth_methods]

        self._auth_methods = list(auth_methods)

        if self.is_client() and self._auth:
            auth = cast(ClientAuth, self._auth)

            if partial_success: # pragma: no cover
                # Partial success not implemented yet
                auth.auth_succeeded()
            else:
                auth.auth_failed()

            # This method is only in SSHClientConnection
            # pylint: disable=no-member
            cast(SSHClientConnection, self).try_next_auth()
        else:
            raise ProtocolError('Unexpected userauth failure response')

    def _process_userauth_success(self, _pkttype: int, _pktid: int,
                                  packet: SSHPacket) -> None:
        """Process a user authentication success response"""

        packet.check_end()

        if self.is_client() and self._auth:
            auth = cast(ClientAuth, self._auth)

            if self._auth_was_trivial and self._disable_trivial_auth:
                raise PermissionDenied('Trivial auth disabled')

            self.logger.info('Auth for user %s succeeded', self._username)

            if self._wait == 'auth_methods' and self._waiter and \
                    not self._waiter.cancelled():
                self._waiter.set_result(None)
                self._auth_methods = [b'none']
                self._wait = None
                return

            auth.auth_succeeded()
            auth.cancel()
            self._auth = None
            self._auth_in_progress = False
            self._auth_complete = True
            self._can_recv_ext_info = False

            if self._agent:
                self._agent.close()

            self.set_extra_info(username=self._username)
            self._cancel_login_timer()
            self._send_deferred_packets()
            self._set_keepalive_timer()

            if self._owner: # pragma: no branch
                self._owner.auth_completed()

            if self._acceptor:
                result = self._acceptor(self)

                if inspect.isawaitable(result):
                    assert result is not None
                    self.create_task(result)

                self._acceptor = None
                self._error_handler = None

            if self._wait == 'auth' and self._waiter and \
                    not self._waiter.cancelled():
                self._waiter.set_result(None)
                self._wait = None
        else:
            raise ProtocolError('Unexpected userauth success response')

    def _process_userauth_banner(self, _pkttype: int, _pktid: int,
                                 packet: SSHPacket) -> None:
        """Process a user authentication banner message"""

        msg_bytes = packet.get_string()
        lang_bytes = packet.get_string()

        # Work around an extra NUL byte appearing in the user
        # auth banner message in some versions of cryptlib
        if b'cryptlib' in self._server_version and \
                packet.get_remaining_payload() == b'\0': # pragma: no cover
            packet.get_byte()

        packet.check_end()

        try:
            msg = msg_bytes.decode('utf-8')
            lang = lang_bytes.decode('ascii')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid userauth banner') from None

        self.logger.debug1('Received authentication banner')

        if self.is_client():
            cast(SSHClient, self._owner).auth_banner_received(msg, lang)
        else:
            raise ProtocolError('Unexpected userauth banner')

    def _process_global_request(self, _pkttype: int, _pktid: int,
                                packet: SSHPacket) -> None:
        """Process a global request"""

        request_bytes = packet.get_string()
        want_reply = packet.get_boolean()

        try:
            request = request_bytes.decode('ascii')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid global request') from None

        name = '_process_' + map_handler_name(request) + '_global_request'
        handler = cast(Optional[_PacketHandler], getattr(self, name, None))

        if not handler:
            self.logger.debug1('Received unknown global request: %s', request)

        self._global_request_queue.append((handler, packet, want_reply))
        if len(self._global_request_queue) == 1:
            self._service_next_global_request()

    def _process_global_response(self, pkttype: int, _pktid: int,
                                 packet: SSHPacket) -> None:
        """Process a global response"""

        if self._global_request_waiters:
            waiter = self._global_request_waiters.pop(0)
            if not waiter.cancelled(): # pragma: no branch
                waiter.set_result((pkttype, packet))
        else:
            raise ProtocolError('Unexpected global response')

    def _process_channel_open(self, _pkttype: int, _pktid: int,
                              packet: SSHPacket) -> None:
        """Process a channel open request"""

        chantype_bytes = packet.get_string()
        send_chan = packet.get_uint32()
        send_window = packet.get_uint32()
        send_pktsize = packet.get_uint32()

        # Work around an off-by-one error in dropbear introduced in
        # https://github.com/mkj/dropbear/commit/49263b5
        if b'dropbear' in self._client_version and self._compressor:
            send_pktsize -= 1

        try:
            chantype = chantype_bytes.decode('ascii')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid channel open request') from None

        try:
            name = '_process_' + map_handler_name(chantype) + '_open'
            handler = cast(Optional[_OpenHandler], getattr(self, name, None))

            if callable(handler):
                chan, session = handler(packet)
                chan.process_open(send_chan, send_window,
                                  send_pktsize, session)
            else:
                raise ChannelOpenError(OPEN_UNKNOWN_CHANNEL_TYPE,
                                       'Unknown channel type')
        except ChannelOpenError as exc:
            self.logger.debug1('Open failed for channel type %s: %s',
                               chantype, exc.reason)

            self.send_channel_open_failure(send_chan, exc.code,
                                           exc.reason, exc.lang)

    def _process_channel_open_confirmation(self, _pkttype: int, _pktid: int,
                                           packet: SSHPacket) -> None:
        """Process a channel open confirmation response"""

        recv_chan = packet.get_uint32()
        send_chan = packet.get_uint32()
        send_window = packet.get_uint32()
        send_pktsize = packet.get_uint32()

        # Work around an off-by-one error in dropbear introduced in
        # https://github.com/mkj/dropbear/commit/49263b5
        if b'dropbear' in self._server_version and self._compressor:
            send_pktsize -= 1

        chan = self._channels.get(recv_chan)
        if chan:
            chan.process_open_confirmation(send_chan, send_window,
                                           send_pktsize, packet)
        else:
            self.logger.debug1('Received open confirmation for unknown '
                               'channel %d', recv_chan)

            raise ProtocolError('Invalid channel number')

    def _process_channel_open_failure(self, _pkttype: int, _pktid: int,
                                      packet: SSHPacket) -> None:
        """Process a channel open failure response"""

        recv_chan = packet.get_uint32()
        code = packet.get_uint32()
        reason_bytes = packet.get_string()
        lang_bytes = packet.get_string()
        packet.check_end()

        try:
            reason = reason_bytes.decode('utf-8')
            lang = lang_bytes.decode('ascii')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid channel open failure') from None

        chan = self._channels.get(recv_chan)
        if chan:
            chan.process_open_failure(code, reason, lang)
        else:
            self.logger.debug1('Received open failure for unknown '
                               'channel %d', recv_chan)

            raise ProtocolError('Invalid channel number')

    def _process_keepalive_at_openssh_dot_com_global_request(
            self, packet: SSHPacket) -> None:
        """Process an incoming OpenSSH keepalive request"""

        packet.check_end()

        self.logger.debug2('Received OpenSSH keepalive request')
        self._report_global_response(True)

    _packet_handlers = {
        MSG_DISCONNECT:                 _process_disconnect,
        MSG_IGNORE:                     _process_ignore,
        MSG_UNIMPLEMENTED:              _process_unimplemented,
        MSG_DEBUG:                      _process_debug,
        MSG_SERVICE_REQUEST:            _process_service_request,
        MSG_SERVICE_ACCEPT:             _process_service_accept,
        MSG_EXT_INFO:                   _process_ext_info,

        MSG_KEXINIT:                    _process_kexinit,
        MSG_NEWKEYS:                    _process_newkeys,

        MSG_USERAUTH_REQUEST:           _process_userauth_request,
        MSG_USERAUTH_FAILURE:           _process_userauth_failure,
        MSG_USERAUTH_SUCCESS:           _process_userauth_success,
        MSG_USERAUTH_BANNER:            _process_userauth_banner,

        MSG_GLOBAL_REQUEST:             _process_global_request,
        MSG_REQUEST_SUCCESS:            _process_global_response,
        MSG_REQUEST_FAILURE:            _process_global_response,

        MSG_CHANNEL_OPEN:               _process_channel_open,
        MSG_CHANNEL_OPEN_CONFIRMATION:  _process_channel_open_confirmation,
        MSG_CHANNEL_OPEN_FAILURE:       _process_channel_open_failure
    }

    def abort(self) -> None:
        """Forcibly close the SSH connection

           This method closes the SSH connection immediately, without
           waiting for pending operations to complete and without sending
           an explicit SSH disconnect message. Buffered data waiting to be
           sent will be lost and no more data will be received. When the
           the connection is closed, :meth:`connection_lost()
           <SSHClient.connection_lost>` on the associated :class:`SSHClient`
           object will be called with the value `None`.

        """

        self.logger.info('Aborting connection')

        self._force_close(None)

    def close(self) -> None:
        """Cleanly close the SSH connection

           This method calls :meth:`disconnect` with the reason set to
           indicate that the connection was closed explicitly by the
           application.

        """

        self.logger.info('Closing connection')

        self.disconnect(DISC_BY_APPLICATION, 'Disconnected by application')

    async def wait_closed(self) -> None:
        """Wait for this connection to close

           This method is a coroutine which can be called to block until
           this connection has finished closing.

        """

        if self._agent:
            await self._agent.wait_closed()

        await self._close_event.wait()

    def disconnect(self, code: int, reason: str,
                   lang: str = DEFAULT_LANG) -> None:
        """Disconnect the SSH connection

           This method sends a disconnect message and closes the SSH
           connection after buffered data waiting to be written has been
           sent. No more data will be received. When the connection is
           fully closed, :meth:`connection_lost() <SSHClient.connection_lost>`
           on the associated :class:`SSHClient` or :class:`SSHServer` object
           will be called with the value `None`.

           :param code:
               The reason for the disconnect, from
               :ref:`disconnect reason codes <DisconnectReasons>`
           :param reason:
               A human readable reason for the disconnect
           :param lang:
               The language the reason is in
           :type code: `int`
           :type reason: `str`
           :type lang: `str`

        """

        for chan in list(self._channels.values()):
            chan.close()

        self._send_disconnect(code, reason, lang)
        self._force_close(None)

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        """Get additional information about the connection

           This method returns extra information about the connection once
           it is established. Supported values include everything supported
           by a socket transport plus:

             | host
             | port
             | username
             | client_version
             | server_version
             | send_cipher
             | send_mac
             | send_compression
             | recv_cipher
             | recv_mac
             | recv_compression

           See :meth:`get_extra_info() <asyncio.BaseTransport.get_extra_info>`
           in :class:`asyncio.BaseTransport` for more information.

           Additional information stored on the connection by calling
           :meth:`set_extra_info` can also be returned here.

        """

        return self._extra.get(name,
                               self._transport.get_extra_info(name, default)
                               if self._transport else default)

    def set_extra_info(self, **kwargs: Any) -> None:
        """Store additional information associated with the connection

           This method allows extra information to be associated with the
           connection. The information to store should be passed in as
           keyword parameters and can later be returned by calling
           :meth:`get_extra_info` with one of the keywords as the name
           to retrieve.

        """

        self._extra.update(**kwargs)

    def set_keepalive(self, interval: Union[None, float, str] = None,
                      count_max: Optional[int] = None) -> None:
        """Set keep-alive timer on this connection

           This method sets the parameters of the keepalive timer on the
           connection. If *interval* is set to a non-zero value,
           keep-alive requests will be sent whenever the connection is
           idle, and if a response is not received after *count_max*
           attempts, the connection is closed.

           :param interval: (optional)
               The time in seconds to wait before sending a keep-alive message
               if no data has been received. This defaults to 0, which
               disables sending these messages.
           :param count_max: (optional)
               The maximum number of keepalive messages which will be sent
               without getting a response before closing the connection.
               This defaults to 3, but only applies when *interval* is
               non-zero.
           :type interval: `int`, `float`, or `str`
           :type count_max: `int`

        """

        if interval is not None:
            if isinstance(interval, str):
                interval = parse_time_interval(interval)

            if interval < 0:
                raise ValueError('Keepalive interval cannot be negative')

            self._keepalive_interval = interval

        if count_max is not None:
            if count_max < 0:
                raise ValueError('Keepalive count max cannot be negative')

            self._keepalive_count_max = count_max

        self._reset_keepalive_timer()

    def send_debug(self, msg: str, lang: str = DEFAULT_LANG,
                   always_display: bool = False) -> None:
        """Send a debug message on this connection

           This method can be called to send a debug message to the
           other end of the connection.

           :param msg:
               The debug message to send
           :param lang:
               The language the message is in
           :param always_display:
               Whether or not to display the message
           :type msg: `str`
           :type lang: `str`
           :type always_display: `bool`

        """

        self.logger.debug1('Sending debug message: %s%s', msg,
                           ' (always display)' if always_display else '')

        self.send_packet(MSG_DEBUG, Boolean(always_display),
                         String(msg), String(lang))

    def create_tcp_channel(self, encoding: Optional[str] = None,
                           errors: str = 'strict',
                           window: int = _DEFAULT_WINDOW,
                           max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
            SSHTCPChannel:
        """Create an SSH TCP channel for a new direct TCP connection

           This method can be called by :meth:`connection_requested()
           <SSHServer.connection_requested>` to create an
           :class:`SSHTCPChannel` with the desired encoding, Unicode
           error handling strategy, window, and max packet size for
           a newly created SSH direct connection.

           :param encoding: (optional)
               The Unicode encoding to use for data exchanged on the
               connection. This defaults to `None`, allowing the
               application to send and receive raw bytes.
           :param errors: (optional)
               The error handling strategy to apply on encode/decode errors
           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type encoding: `str` or `None`
           :type errors: `str`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: :class:`SSHTCPChannel`

        """

        return SSHTCPChannel(self, self._loop, encoding,
                             errors, window, max_pktsize)

    def create_unix_channel(self, encoding: Optional[str] = None,
                            errors: str = 'strict',
                            window: int = _DEFAULT_WINDOW,
                            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
            SSHUNIXChannel:
        """Create an SSH UNIX channel for a new direct UNIX domain connection

           This method can be called by :meth:`unix_connection_requested()
           <SSHServer.unix_connection_requested>` to create an
           :class:`SSHUNIXChannel` with the desired encoding, Unicode
           error handling strategy, window, and max packet size for
           a newly created SSH direct UNIX domain socket connection.

           :param encoding: (optional)
               The Unicode encoding to use for data exchanged on the
               connection. This defaults to `None`, allowing the
               application to send and receive raw bytes.
           :param errors: (optional)
               The error handling strategy to apply on encode/decode errors
           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type encoding: `str` or `None`
           :type errors: `str`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: :class:`SSHUNIXChannel`

        """

        return SSHUNIXChannel(self, self._loop, encoding,
                              errors, window, max_pktsize)

    def create_tuntap_channel(self, window: int = _DEFAULT_WINDOW,
                              max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
            SSHTunTapChannel:
        """Create a channel to use for TUN/TAP forwarding

           This method can be called by :meth:`tun_requested()
           <SSHServer.tun_requested>` or :meth:`tap_requested()
           <SSHServer.tap_requested>` to create an :class:`SSHTunTapChannel`
           with the desired window and max packet size for a newly created
           TUN/TAP tunnel.

           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type window: `int`
           :type max_pktsize: `int`

           :returns: :class:`SSHTunTapChannel`

        """

        return SSHTunTapChannel(self, self._loop, None, 'strict',
                                window, max_pktsize)

    def create_x11_channel(
            self, window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> SSHX11Channel:
        """Create an SSH X11 channel to use in X11 forwarding"""

        return SSHX11Channel(self, self._loop, None, 'strict',
                             window, max_pktsize)

    def create_agent_channel(
            self, window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> SSHAgentChannel:
        """Create an SSH agent channel to use in agent forwarding"""

        return SSHAgentChannel(self, self._loop, None, 'strict',
                               window, max_pktsize)

    async def create_connection(
            self, session_factory: SSHTCPSessionFactory[AnyStr],
            remote_host: str, remote_port: int, orig_host: str = '',
            orig_port: int = 0, *, encoding: Optional[str] = None,
            errors: str = 'strict', window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
                Tuple[SSHTCPChannel[AnyStr], SSHTCPSession[AnyStr]]:
        """Create an SSH direct or forwarded TCP connection"""

        raise NotImplementedError

    async def create_unix_connection(
            self, session_factory: SSHUNIXSessionFactory[AnyStr],
            remote_path: str, *, encoding: Optional[str] = None,
            errors: str = 'strict', window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
                Tuple[SSHUNIXChannel[AnyStr], SSHUNIXSession[AnyStr]]:

        """Create an SSH direct or forwarded UNIX domain socket connection"""

        raise NotImplementedError

    async def forward_connection(
            self, dest_host: str, dest_port: int) -> SSHForwarder:
        """Forward a tunneled TCP connection

           This method is a coroutine which can be returned by a
           `session_factory` to forward connections tunneled over
           SSH to the specified destination host and port.

           :param dest_host:
               The hostname or address to forward the connections to
           :param dest_port:
               The port number to forward the connections to
           :type dest_host: `str` or `None`
           :type dest_port: `int`

           :returns: :class:`asyncio.BaseProtocol`

        """

        try:
            _, peer = await self._loop.create_connection(SSHForwarder,
                                                         dest_host, dest_port)

            self.logger.info('  Forwarding TCP connection to %s',
                             (dest_host, dest_port))
        except OSError as exc:
            raise ChannelOpenError(OPEN_CONNECT_FAILED, str(exc)) from None

        return SSHForwarder(cast(SSHForwarder, peer))

    async def forward_unix_connection(self, dest_path: str) -> SSHForwarder:
        """Forward a tunneled UNIX domain socket connection

           This method is a coroutine which can be returned by a
           `session_factory` to forward connections tunneled over
           SSH to the specified destination path.

           :param dest_path:
               The path to forward the connection to
           :type dest_path: `str`

           :returns: :class:`asyncio.BaseProtocol`

        """

        try:
            _, peer = \
                await self._loop.create_unix_connection(SSHForwarder, dest_path)

            self.logger.info('  Forwarding UNIX connection to %s', dest_path)
        except OSError as exc:
            raise ChannelOpenError(OPEN_CONNECT_FAILED, str(exc)) from None

        return SSHForwarder(cast(SSHForwarder, peer))

    @async_context_manager
    async def forward_local_port(
            self, listen_host: str, listen_port: int,
            dest_host: str, dest_port: int,
            accept_handler: Optional[SSHAcceptHandler] = None) -> SSHListener:
        """Set up local port forwarding

           This method is a coroutine which attempts to set up port
           forwarding from a local listening port to a remote host and port
           via the SSH connection. If the request is successful, the
           return value is an :class:`SSHListener` object which can be used
           later to shut down the port forwarding.

           :param listen_host:
               The hostname or address on the local host to listen on
           :param listen_port:
               The port number on the local host to listen on
           :param dest_host:
               The hostname or address to forward the connections to
           :param dest_port:
               The port number to forward the connections to
           :param accept_handler:
               A `callable` or coroutine which takes arguments of the
               original host and port of the client and decides whether
               or not to allow connection forwarding, returning `True` to
               accept the connection and begin forwarding or `False` to
               reject and close it.
           :type listen_host: `str`
           :type listen_port: `int`
           :type dest_host: `str`
           :type dest_port: `int`
           :type accept_handler: `callable` or coroutine

           :returns: :class:`SSHListener`

           :raises: :exc:`OSError` if the listener can't be opened

        """

        async def tunnel_connection(
                session_factory: SSHTCPSessionFactory[bytes],
                orig_host: str, orig_port: int) -> \
                    Tuple[SSHTCPChannel[bytes], SSHTCPSession[bytes]]:
            """Forward a local connection over SSH"""

            if accept_handler:
                result = accept_handler(orig_host, orig_port)

                if inspect.isawaitable(result):
                    result = await cast(Awaitable[bool], result)

                if not result:
                    self.logger.info('Request for TCP forwarding from '
                                     '%s to %s denied by application',
                                     (orig_host, orig_port),
                                     (dest_host, dest_port))

                    raise ChannelOpenError(OPEN_ADMINISTRATIVELY_PROHIBITED,
                                           'Connection forwarding denied')

            return (await self.create_connection(session_factory,
                                                 dest_host, dest_port,
                                                 orig_host, orig_port))

        if (listen_host, listen_port) == (dest_host, dest_port):
            self.logger.info('Creating local TCP forwarder on %s',
                             (listen_host, listen_port))
        else:
            self.logger.info('Creating local TCP forwarder from %s to %s',
                             (listen_host, listen_port),
                             (dest_host, dest_port))

        try:
            listener = await create_tcp_forward_listener(self, self._loop,
                                                         tunnel_connection,
                                                         listen_host,
                                                         listen_port)
        except OSError as exc:
            self.logger.debug1('Failed to create local TCP listener: %s', exc)
            raise

        if listen_port == 0:
            listen_port = listener.get_port()

        if dest_port == 0:
            dest_port = listen_port

        self._local_listeners[listen_host, listen_port] = listener

        return listener

    @async_context_manager
    async def forward_local_path(self, listen_path: str,
                                 dest_path: str) -> SSHListener:
        """Set up local UNIX domain socket forwarding

           This method is a coroutine which attempts to set up UNIX domain
           socket forwarding from a local listening path to a remote path
           via the SSH connection. If the request is successful, the
           return value is an :class:`SSHListener` object which can be used
           later to shut down the UNIX domain socket forwarding.

           :param listen_path:
               The path on the local host to listen on
           :param dest_path:
               The path on the remote host to forward the connections to
           :type listen_path: `str`
           :type dest_path: `str`

           :returns: :class:`SSHListener`

           :raises: :exc:`OSError` if the listener can't be opened

        """

        async def tunnel_connection(
                session_factory: SSHUNIXSessionFactory[bytes]) -> \
                    Tuple[SSHUNIXChannel[bytes], SSHUNIXSession[bytes]]:
            """Forward a local connection over SSH"""

            return await self.create_unix_connection(session_factory,
                                                     dest_path)

        self.logger.info('Creating local UNIX forwarder from %s to %s',
                         listen_path, dest_path)

        try:
            listener = await create_unix_forward_listener(self, self._loop,
                                                          tunnel_connection,
                                                          listen_path)
        except OSError as exc:
            self.logger.debug1('Failed to create local UNIX listener: %s', exc)
            raise

        self._local_listeners[listen_path] = listener

        return listener

    def forward_tuntap(self, mode: int, unit: Optional[int]) -> SSHForwarder:
        """Set up TUN/TAP forwarding"""

        try:
            transport, peer = create_tuntap(SSHForwarder, mode, unit)
            interface = transport.get_extra_info('interface')

            self.logger.info('  Forwarding layer %d traffic to %s',
                             3 if mode == SSH_TUN_MODE_POINTTOPOINT else 2,
                             interface)
        except OSError as exc:
            raise ChannelOpenError(OPEN_CONNECT_FAILED, str(exc)) from None

        return SSHForwarder(cast(SSHForwarder, peer),
                            extra={'interface': interface})

    def close_forward_listener(self, listen_key: ListenKey) -> None:
        """Mark a local forwarding listener as closed"""

        self._local_listeners.pop(listen_key, None)

    def detach_x11_listener(self, chan: SSHChannel[AnyStr]) -> None:
        """Detach a session from a local X11 listener"""

        raise NotImplementedError


class SSHClientConnection(SSHConnection):
    """SSH client connection

       This class represents an SSH client connection.

       Once authentication is successful on a connection, new client
       sessions can be opened by calling :meth:`create_session`.

       Direct TCP connections can be opened by calling
       :meth:`create_connection`.

       Remote listeners for forwarded TCP connections can be opened by
       calling :meth:`create_server`.

       Direct UNIX domain socket connections can be opened by calling
       :meth:`create_unix_connection`.

       Remote listeners for forwarded UNIX domain socket connections
       can be opened by calling :meth:`create_unix_server`.

       TCP port forwarding can be set up by calling :meth:`forward_local_port`
       or :meth:`forward_remote_port`.

       UNIX domain socket forwarding can be set up by calling
       :meth:`forward_local_path` or :meth:`forward_remote_path`.

       Mixed forwarding from a TCP port to a UNIX domain socket or
       vice-versa can be set up by calling :meth:`forward_local_port_to_path`,
       :meth:`forward_local_path_to_port`,
       :meth:`forward_remote_port_to_path`, or
       :meth:`forward_remote_path_to_port`.

    """

    _options: 'SSHClientConnectionOptions'
    _owner: SSHClient
    _x11_listener: Optional[SSHX11ClientListener]

    def __init__(self, loop: asyncio.AbstractEventLoop,
                 options: 'SSHClientConnectionOptions',
                 acceptor: _AcceptHandler = None,
                 error_handler: _ErrorHandler = None,
                 wait: Optional[str] = None):
        super().__init__(loop, options, acceptor, error_handler,
                         wait, server=False)

        self._host = options.host
        self._port = options.port

        self._known_hosts = options.known_hosts
        self._host_key_alias = options.host_key_alias

        self._server_host_key_algs: Optional[Sequence[bytes]] = None
        self._server_host_key: Optional[SSHKey] = None

        self._server_host_keys_handler = options.server_host_keys_handler

        self._username = options.username
        self._password = options.password

        self._client_host_keys: List[_ClientHostKey] = []

        self._client_keys: List[SSHKeyPair] = \
            list(options.client_keys) if options.client_keys else []
        self._saved_rsa_key: Optional[_ClientHostKey] = None

        if options.preferred_auth != ():
            self._preferred_auth = [method.encode('ascii') for method in
                                    options.preferred_auth]
        else:
            self._preferred_auth = get_supported_client_auth_methods()

        self._disable_trivial_auth = options.disable_trivial_auth

        if options.agent_path is not None:
            self._agent = SSHAgentClient(options.agent_path)

        self._agent_identities = options.agent_identities
        self._agent_forward_path = options.agent_forward_path
        self._get_agent_keys = bool(self._agent)

        self._pkcs11_provider = options.pkcs11_provider
        self._pkcs11_pin = options.pkcs11_pin
        self._get_pkcs11_keys = bool(self._pkcs11_provider)

        gss_host = options.gss_host if options.gss_host != () else options.host

        if gss_host:
            try:
                self._gss = GSSClient(gss_host, options.gss_store,
                                      options.gss_delegate_creds)
                self._gss_kex = options.gss_kex
                self._gss_auth = options.gss_auth
                self._gss_mic_auth = self._gss_auth
            except GSSError:
                pass

        self._kbdint_password_auth = False

        self._remote_listeners: \
            Dict[ListenKey, Union[SSHTCPClientListener,
                                  SSHUNIXClientListener]] = {}

        self._dynamic_remote_listeners: Dict[str, SSHTCPClientListener] = {}

    def _connection_made(self) -> None:
        """Handle the opening of a new connection"""

        assert self._transport is not None

        if not self._host:
            if self._peer_addr:
                self._host = self._peer_addr
                self._port = self._peer_port
            else:
                remote_peer = self.get_extra_info('remote_peername')
                self._host, self._port = cast(HostPort, remote_peer)

        if self._options.client_host_keysign:
            sock = cast(socket.socket,
                        self._transport.get_extra_info('socket'))

            self._client_host_keys = list(get_keysign_keys(
                self._options.client_host_keysign, sock.fileno(),
                self._options.client_host_pubkeys))
        elif self._options.client_host_keypairs:
            self._client_host_keys = list(self._options.client_host_keypairs)
        else:
            self._client_host_keys = []

        if self._known_hosts is None:
            self._trusted_host_keys = None
            self._trusted_ca_keys = None
        else:
            if not self._known_hosts:
                default_known_hosts = Path('~', '.ssh',
                                           'known_hosts').expanduser()

                if (default_known_hosts.is_file() and
                        os.access(default_known_hosts, os.R_OK)):
                    self._known_hosts = str(default_known_hosts)
                else:
                    self._known_hosts = b''

            port = self._port if self._port != DEFAULT_PORT else None

            self._match_known_hosts(cast(KnownHostsArg, self._known_hosts),
                                    self._host_key_alias or self._host,
                                    self._peer_addr, port)

        default_host_key_algs = []

        if self._options.server_host_key_algs != 'default':
            if self._trusted_host_key_algs:
                default_host_key_algs = self._trusted_host_key_algs

            if self._trusted_ca_keys:
                default_host_key_algs = \
                    get_default_certificate_algs() + default_host_key_algs

        if not default_host_key_algs:
            default_host_key_algs = \
                get_default_certificate_algs() + get_default_public_key_algs()

        if self._x509_trusted_certs is not None:
            if self._x509_trusted_certs or self._x509_trusted_cert_paths:
                default_host_key_algs = \
                    get_default_x509_certificate_algs() + default_host_key_algs

        self._server_host_key_algs = _select_host_key_algs(
            self._options.server_host_key_algs,
            cast(DefTuple[str], self._options.config.get(
                'HostKeyAlgorithms', ())),
            default_host_key_algs)

        self.logger.info('Connected to SSH server at %s',
                         (self._host, self._port))

        if self._options.proxy_command:
            proxy_command = ' '.join(shlex.quote(arg) for arg in
                                     self._options.proxy_command)
            self.logger.info('  Proxy command: %s', proxy_command)
        else:
            self.logger.info('  Local address: %s',
                             (self._local_addr, self._local_port))
            self.logger.info('  Peer address: %s',
                             (self._peer_addr, self._peer_port))


    def _cleanup(self, exc: Optional[Exception]) -> None:
        """Clean up this client connection"""

        if self._agent:
            self._agent.close()

        if self._remote_listeners:
            for tcp_listener in list(self._remote_listeners.values()):
                tcp_listener.close()

            self._remote_listeners = {}
            self._dynamic_remote_listeners = {}

        if exc is None:
            self.logger.info('Connection closed')
        elif isinstance(exc, ConnectionLost):
            self.logger.info(str(exc))
        else:
            self.logger.info('Connection failure: ' + str(exc))

        super()._cleanup(exc)


    def _choose_signature_alg(self, keypair: _ClientHostKey) -> bool:
        """Choose signature algorithm to use for key-based authentication"""

        if self._server_sig_algs:
            for alg in keypair.sig_algorithms:
                if keypair.use_webauthn and not alg.startswith(b'webauthn-'):
                    continue

                if alg in self._sig_algs and alg in self._server_sig_algs:
                    keypair.set_sig_algorithm(alg)
                    return True

        return keypair.sig_algorithms[-1] in self._sig_algs

    def validate_server_host_key(self, key_data: bytes) -> SSHKey:
        """Validate and return the server's host key"""

        try:
            host_key = self._validate_host_key(
                self._host_key_alias or self._host,
                self._peer_addr, self._port, key_data)
        except ValueError as exc:
            host = self._host

            if self._host_key_alias:
                host += f' with alias {self._host_key_alias}'

            raise HostKeyNotVerifiable(f'{exc} for host {host}') from None

        self._server_host_key = host_key
        return host_key

    def get_server_host_key(self) -> Optional[SSHKey]:
        """Return the server host key used in the key exchange

           This method returns the server host key used to complete the
           key exchange with the server.

           If GSS key exchange is used, `None` is returned.

           :returns: An :class:`SSHKey` public key or `None`

        """

        return self._server_host_key

    def get_server_auth_methods(self) -> Sequence[str]:
        """Return the server host key used in the key exchange

           This method returns the auth methods available to authenticate
           to the server.

           :returns: `list` of `str`

        """

        return [method.decode('ascii') for method in self._auth_methods]

    def try_next_auth(self, *, next_method: bool = False) -> None:
        """Attempt client authentication using the next compatible method"""

        if self._auth:
            self._auth.cancel()
            self._auth = None

        if next_method:
            self._auth_methods.pop(0)

        while self._auth_methods:
            self._auth = lookup_client_auth(self, self._auth_methods[0])

            if self._auth:
                return

            self._auth_methods.pop(0)

        self.logger.info('Auth failed for user %s', self._username)

        self._force_close(PermissionDenied('Permission denied for user '
                                           f'{self._username} on host '
                                           f'{self._host}'))

    def gss_kex_auth_requested(self) -> bool:
        """Return whether to allow GSS key exchange authentication or not"""

        if self._gss_kex_auth:
            self._gss_kex_auth = False
            return True
        else:
            return False

    def gss_mic_auth_requested(self) -> bool:
        """Return whether to allow GSS MIC authentication or not"""

        if self._gss_mic_auth:
            self._gss_mic_auth = False
            return True
        else:
            return False

    async def host_based_auth_requested(self) -> \
            Tuple[Optional[_ClientHostKey], str, str]:
        """Return a host key, host, and user to authenticate with"""

        if not self._host_based_auth:
            return None, '', ''

        key: Optional[_ClientHostKey]

        while True:
            if self._saved_rsa_key:
                key = self._saved_rsa_key
                key.algorithm = key.sig_algorithm + b'-cert-v01@openssh.com'
                self._saved_rsa_key = None
            else:
                try:
                    key = self._client_host_keys.pop(0)
                except IndexError:
                    key = None
                    break

            assert key is not None

            if self._choose_signature_alg(key):
                if key.algorithm == b'ssh-rsa-cert-v01@openssh.com' and \
                        key.sig_algorithm != b'ssh-rsa':
                    self._saved_rsa_key = key

                break

        client_host = self._options.client_host

        if client_host is None:
            sockname = cast(SockAddr, self.get_extra_info('sockname'))

            if sockname:
                try:
                    client_host, _ = await self._loop.getnameinfo(
                        sockname, socket.NI_NUMERICSERV)
                except socket.gaierror:
                    client_host = sockname[0]
            else:
                client_host = ''

        # Add a trailing '.' to the client host to be compatible with
        # ssh-keysign from OpenSSH
        if self._options.client_host_keysign and client_host[-1:] != '.':
            client_host += '.'

        return key, client_host, self._options.client_username

    async def public_key_auth_requested(self) -> Optional[SSHKeyPair]:
        """Return a client key pair to authenticate with"""

        if not self._public_key_auth:
            return None

        if self._get_agent_keys:
            assert self._agent is not None

            try:
                agent_keys = await self._agent.get_keys(self._agent_identities)
                self._client_keys[:0] = list(agent_keys)
            except ValueError:
                pass

            self._get_agent_keys = False

        if self._get_pkcs11_keys:
            assert self._pkcs11_provider is not None

            pkcs11_keys = await self._loop.run_in_executor(
                None, load_pkcs11_keys, self._pkcs11_provider, self._pkcs11_pin)

            self._client_keys[:0] = list(pkcs11_keys)
            self._get_pkcs11_keys = False

        while True:
            if not self._client_keys:
                result = self._owner.public_key_auth_requested()

                if inspect.isawaitable(result):
                    result = await cast(Awaitable[KeyPairListArg], result)

                if not result:
                    return None

                result: KeyPairListArg

                self._client_keys = list(load_keypairs(result))

            # OpenSSH versions before 7.8 didn't support RSA SHA-2
            # signature names in certificate key types, requiring the
            # use of ssh-rsa-cert-v01@openssh.com as the key type even
            # when using SHA-2 signatures. However, OpenSSL 8.8 and
            # later reject ssh-rsa-cert-v01@openssh.com as a key type
            # by default, requiring that the RSA SHA-2 version of the key
            # type be used. This makes it difficult to use RSA keys with
            # certificates without knowing the version of the remote
            # server and which key types it will accept.
            #
            # The code below works around this by trying multiple key
            # types during public key and host-based authentication when
            # using SHA-2 signatures with RSA keys signed by certificates.

            if self._saved_rsa_key:
                key = self._saved_rsa_key
                key.algorithm = key.sig_algorithm + b'-cert-v01@openssh.com'
                self._saved_rsa_key = None
            else:
                key = self._client_keys.pop(0)

            if self._choose_signature_alg(key):
                if key.algorithm == b'ssh-rsa-cert-v01@openssh.com' and \
                        key.sig_algorithm != b'ssh-rsa':
                    self._saved_rsa_key = key

                return key

    async def password_auth_requested(self) -> Optional[str]:
        """Return a password to authenticate with"""

        if not self._password_auth and not self._kbdint_password_auth:
            return None

        if self._password is not None:
            password: Optional[str] = self._password

            if callable(password):
                password = cast(Callable[[], Optional[str]], password)()

            if inspect.isawaitable(password):
                password = await cast(Awaitable[Optional[str]], password)
            else:
                password = cast(Optional[str], password)

            self._password = None
        else:
            result = self._owner.password_auth_requested()

            if inspect.isawaitable(result):
                password = await cast(Awaitable[Optional[str]], result)
            else:
                password = cast(Optional[str], result)

        return password

    async def password_change_requested(self, prompt: str,
                                        lang: str) -> Tuple[str, str]:
        """Return a password to authenticate with and what to change it to"""

        result = self._owner.password_change_requested(prompt, lang)

        if inspect.isawaitable(result):
            result = await cast(Awaitable[PasswordChangeResponse], result)

        return cast(PasswordChangeResponse, result)

    def password_changed(self) -> None:
        """Report a successful password change"""

        self._owner.password_changed()

    def password_change_failed(self) -> None:
        """Report a failed password change"""

        self._owner.password_change_failed()

    async def kbdint_auth_requested(self) -> Optional[str]:
        """Return the list of supported keyboard-interactive auth methods

           If keyboard-interactive auth is not supported in the client but
           a password was provided when the connection was opened, this
           will allow sending the password via keyboard-interactive auth.

        """

        if not self._kbdint_auth:
            return None

        result = self._owner.kbdint_auth_requested()

        if inspect.isawaitable(result):
            result = await cast(Awaitable[Optional[str]], result)

        if result is NotImplemented:
            if self._password is not None and not self._kbdint_password_auth:
                self._kbdint_password_auth = True
                result = ''
            else:
                result = None

        return cast(Optional[str], result)

    async def kbdint_challenge_received(
            self, name: str, instructions: str, lang: str,
            prompts: KbdIntPrompts) -> Optional[KbdIntResponse]:
        """Return responses to a keyboard-interactive auth challenge"""

        if self._kbdint_password_auth:
            if not prompts:
                # Silently drop any empty challenges used to print messages
                response: Optional[KbdIntResponse] = []
            elif len(prompts) == 1:
                prompt = prompts[0][0].lower()

                if 'password' in prompt or 'passcode' in prompt:
                    password = await self.password_auth_requested()

                    response = [password] if password is not None else None
                else:
                    response = None
            else:
                response = None
        else:
            result = self._owner.kbdint_challenge_received(name, instructions,
                                                           lang, prompts)

            if inspect.isawaitable(result):
                response = await cast(Awaitable[KbdIntResponse], result)
            else:
                response = cast(KbdIntResponse, result)

        return response

    def _process_session_open(self, _packet: SSHPacket) -> \
            Tuple[SSHServerChannel, SSHServerSession]:
        """Process an inbound session open request

           These requests are disallowed on an SSH client.

        """

        # pylint: disable=no-self-use

        raise ChannelOpenError(OPEN_ADMINISTRATIVELY_PROHIBITED,
                               'Session open forbidden on client')

    def _process_direct_tcpip_open(self, _packet: SSHPacket) -> \
            Tuple[SSHTCPChannel[bytes], SSHTCPSession[bytes]]:
        """Process an inbound direct TCP/IP channel open request

           These requests are disallowed on an SSH client.

        """

        # pylint: disable=no-self-use

        raise ChannelOpenError(OPEN_ADMINISTRATIVELY_PROHIBITED,
                               'Direct TCP/IP open forbidden on client')

    def _process_forwarded_tcpip_open(self, packet: SSHPacket) -> \
            Tuple[SSHTCPChannel, MaybeAwait[SSHTCPSession]]:
        """Process an inbound forwarded TCP/IP channel open request"""

        dest_host_bytes = packet.get_string()
        dest_port = packet.get_uint32()
        orig_host_bytes = packet.get_string()
        orig_port = packet.get_uint32()
        packet.check_end()

        try:
            dest_host = dest_host_bytes.decode('utf-8')
            orig_host = orig_host_bytes.decode('utf-8')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid forwarded TCP/IP channel '
                                'open request') from None

        # Some buggy servers send back a port of `0` instead of the actual
        # listening port when reporting connections which arrive on a listener
        # set up on a dynamic port. This lookup attempts to work around that.
        listener = cast(SSHTCPClientListener[bytes],
            self._remote_listeners.get((dest_host, dest_port)) or
            self._dynamic_remote_listeners.get(dest_host))

        if listener:
            chan, session = listener.process_connection(orig_host, orig_port)

            self.logger.info('Accepted forwarded TCP connection on %s',
                             (dest_host, dest_port))
            self.logger.info('  Client address: %s', (orig_host, orig_port))

            return chan, session
        else:
            raise ChannelOpenError(OPEN_CONNECT_FAILED, 'No such listener')

    async def close_client_tcp_listener(self, listen_host: str,
                                        listen_port: int) -> None:
        """Close a remote TCP/IP listener"""

        await self._make_global_request(
            b'cancel-tcpip-forward', String(listen_host), UInt32(listen_port))

        self.logger.info('Closed remote TCP listener on %s',
                         (listen_host, listen_port))

        listener = self._remote_listeners.get((listen_host, listen_port))

        if listener:
            if self._dynamic_remote_listeners.get(listen_host) == listener:
                del self._dynamic_remote_listeners[listen_host]

            del self._remote_listeners[listen_host, listen_port]

    def _process_direct_streamlocal_at_openssh_dot_com_open(
            self, _packet: SSHPacket) -> \
                Tuple[SSHUNIXChannel, SSHUNIXSession]:
        """Process an inbound direct UNIX domain channel open request

           These requests are disallowed on an SSH client.

        """

        # pylint: disable=no-self-use

        raise ChannelOpenError(OPEN_ADMINISTRATIVELY_PROHIBITED,
                               'Direct UNIX domain socket open '
                               'forbidden on client')

    def _process_tun_at_openssh_dot_com_open(
            self, _packet: SSHPacket) -> \
                Tuple[SSHTunTapChannel, SSHTunTapSession]:
        """Process an inbound TUN/TAP open request

           These requests are disallowed on an SSH client.

        """

        # pylint: disable=no-self-use

        raise ChannelOpenError(OPEN_ADMINISTRATIVELY_PROHIBITED,
                               'TUN/TAP request forbidden on client')

    def _process_forwarded_streamlocal_at_openssh_dot_com_open(
            self, packet: SSHPacket) -> \
                Tuple[SSHUNIXChannel, MaybeAwait[SSHUNIXSession]]:
        """Process an inbound forwarded UNIX domain channel open request"""

        dest_path_bytes = packet.get_string()
        _ = packet.get_string()                         # reserved
        packet.check_end()

        try:
            dest_path = dest_path_bytes.decode('utf-8')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid forwarded UNIX domain channel '
                                'open request') from None

        listener = cast(SSHUNIXClientListener[bytes],
                        self._remote_listeners.get(dest_path))

        if listener:
            chan, session = listener.process_connection()

            self.logger.info('Accepted remote UNIX connection on %s', dest_path)

            return chan, session
        else:
            raise ChannelOpenError(OPEN_CONNECT_FAILED, 'No such listener')

    async def close_client_unix_listener(self, listen_path: str) -> None:
        """Close a remote UNIX domain socket listener"""

        await self._make_global_request(
            b'cancel-streamlocal-forward@openssh.com', String(listen_path))

        self.logger.info('Closed UNIX listener on %s', listen_path)

        if listen_path in self._remote_listeners:
            del self._remote_listeners[listen_path]

    def _process_x11_open(self, packet: SSHPacket) -> \
            Tuple[SSHX11Channel, Awaitable[SSHX11ClientForwarder]]:
        """Process an inbound X11 channel open request"""

        orig_host_bytes = packet.get_string()
        orig_port = packet.get_uint32()

        packet.check_end()

        try:
            orig_host = orig_host_bytes.decode('utf-8')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid forwarded X11 channel '
                                'open request') from None

        if self._x11_listener:
            self.logger.info('Accepted X11 connection')
            self.logger.info('  Client address: %s', (orig_host, orig_port))

            chan = self.create_x11_channel()

            chan.set_inbound_peer_names(orig_host, orig_port)

            return chan, self._x11_listener.forward_connection()
        else:
            raise ChannelOpenError(OPEN_CONNECT_FAILED,
                                   'X11 forwarding disabled')

    def _process_auth_agent_at_openssh_dot_com_open(
            self, packet: SSHPacket) -> \
                Tuple[SSHUNIXChannel, Awaitable[SSHForwarder]]:
        """Process an inbound auth agent channel open request"""

        packet.check_end()

        if self._agent_forward_path:
            self.logger.info('Accepted SSH agent connection')

            return (self.create_unix_channel(),
                    self.forward_unix_connection(self._agent_forward_path))
        else:
            raise ChannelOpenError(OPEN_CONNECT_FAILED,
                                   'Auth agent forwarding disabled')

    def _process_hostkeys_00_at_openssh_dot_com_global_request(
            self, packet: SSHPacket) -> None:
        """Process a list of accepted server host keys"""

        self.create_task(self._finish_hostkeys(packet))

    async def _finish_hostkeys(self, packet: SSHPacket) -> None:
        """Finish processing hostkeys global request"""

        if not self._server_host_keys_handler:
            self.logger.debug1('Ignoring server host key message: no handler')
            self._report_global_response(False)
            return

        if self._trusted_host_keys is None:
            self.logger.info('Server host key not verified: handler disabled')
            self._report_global_response(False)
            return

        added = []
        removed = list(self._trusted_host_keys)
        retained = []
        revoked = []
        prove = []

        while packet:
            try:
                key_data = packet.get_string()
                key = decode_ssh_public_key(key_data)

                if key in self._revoked_host_keys:
                    revoked.append(key)
                elif key in self._trusted_host_keys:
                    retained.append(key)
                    removed.remove(key)
                else:
                    prove.append((key, String(key_data)))
            except KeyImportError:
                pass

        if prove:
            pkttype, packet = await self._make_global_request(
                b'hostkeys-prove-00@openssh.com',
                b''.join(key_str for _, key_str in prove))

            if pkttype == MSG_REQUEST_SUCCESS:
                prefix = String('hostkeys-prove-00@openssh.com') + \
                         String(self._session_id)

                for key, key_str in prove:
                    sig = packet.get_string()

                    if key.verify(prefix + key_str, sig):
                        added.append(key)
                    else:
                        self.logger.debug1('Server host key validation failed')
            else:
                self.logger.debug1('Server host key prove request failed')

        packet.check_end()

        self.logger.info(f'Server host key report: {len(added)} added, '
                         f'{len(removed)} removed, {len(retained)} retained, '
                         f'{len(revoked)} revoked')

        result = self._server_host_keys_handler(added, removed,
                                                retained, revoked)

        if inspect.isawaitable(result):
            assert result is not None
            await result

        self._report_global_response(True)

    async def attach_x11_listener(self, chan: SSHClientChannel[AnyStr],
                                  display: Optional[str],
                                  auth_path: Optional[str],
                                  single_connection: bool) -> \
            Tuple[bytes, bytes, int]:
        """Attach a channel to a local X11 display"""

        if not display:
            display = os.environ.get('DISPLAY')

        if not display:
            raise ValueError('X11 display not set')

        if not self._x11_listener:
            self._x11_listener = await create_x11_client_listener(
                self._loop, display, auth_path)

        return self._x11_listener.attach(display, chan, single_connection)

    def detach_x11_listener(self, chan: SSHChannel[AnyStr]) -> None:
        """Detach a session from a local X11 listener"""

        if self._x11_listener:
            if self._x11_listener.detach(chan):
                self._x11_listener = None

    async def create_session(self, session_factory: SSHClientSessionFactory,
                             command: DefTuple[Optional[str]] = (), *,
                             subsystem: DefTuple[Optional[str]]= (),
                             env: DefTuple[Env] = (),
                             send_env: DefTuple[Optional[EnvSeq]] = (),
                             request_pty: DefTuple[Union[bool, str]] = (),
                             term_type: DefTuple[Optional[str]] = (),
                             term_size: DefTuple[TermSizeArg] = (),
                             term_modes: DefTuple[TermModesArg] = (),
                             x11_forwarding: DefTuple[Union[int, str]] = (),
                             x11_display: DefTuple[Optional[str]] = (),
                             x11_auth_path: DefTuple[Optional[str]] = (),
                             x11_single_connection: DefTuple[bool] = (),
                             encoding: DefTuple[Optional[str]] = (),
                             errors: DefTuple[str] = (),
                             window: DefTuple[int] = (),
                             max_pktsize: DefTuple[int] = ()) -> \
            Tuple[SSHClientChannel, SSHClientSession]:
        """Create an SSH client session

           This method is a coroutine which can be called to create an SSH
           client session used to execute a command, start a subsystem
           such as sftp, or if no command or subsystem is specified run an
           interactive shell. Optional arguments allow terminal and
           environment information to be provided.

           By default, this class expects string data in its send and
           receive functions, which it encodes on the SSH connection in
           UTF-8 (ISO 10646) format. An optional encoding argument can
           be passed in to select a different encoding, or `None` can
           be passed in if the application wishes to send and receive
           raw bytes. When an encoding is set, an optional errors
           argument can be passed in to select what Unicode error
           handling strategy to use.

           Other optional arguments include the SSH receive window size and
           max packet size which default to 2 MB and 32 KB, respectively.

           :param session_factory:
               A `callable` which returns an :class:`SSHClientSession` object
               that will be created to handle activity on this session
           :param command: (optional)
               The remote command to execute. By default, an interactive
               shell is started if no command or subsystem is provided.
           :param subsystem: (optional)
               The name of a remote subsystem to start up.
           :param env: (optional)
               The  environment variables to set for this session. Keys and
               values passed in here will be converted to Unicode strings
               encoded as UTF-8 (ISO 10646) for transmission.

                   .. note:: Many SSH servers restrict which environment
                             variables a client is allowed to set. The
                             server's configuration may need to be edited
                             before environment variables can be
                             successfully set in the remote environment.
           :param send_env: (optional)
               A list of environment variable names to pull from
               `os.environ` and set for this session. Wildcards patterns
               using `'*'` and `'?'` are allowed, and all variables with
               matching names will be sent with whatever value is set
               in the local environment. If a variable is present in both
               env and send_env, the value from env will be used.
           :param request_pty: (optional)
               Whether or not to request a pseudo-terminal (PTY) for this
               session. This defaults to `True`, which means to request a
               PTY whenever the `term_type` is set. Other possible values
               include `False` to never request a PTY, `'force'` to always
               request a PTY even without `term_type` being set, or `'auto'`
               to request a TTY when `term_type` is set but only when
               starting an interactive shell.
           :param term_type: (optional)
               The terminal type to set for this session.
           :param term_size: (optional)
               The terminal width and height in characters and optionally
               the width and height in pixels.
           :param term_modes: (optional)
               POSIX terminal modes to set for this session, where keys are
               taken from :ref:`POSIX terminal modes <PTYModes>` with values
               defined in section 8 of :rfc:`RFC 4254 <4254#section-8>`.
           :param x11_forwarding: (optional)
               Whether or not to request X11 forwarding for this session,
               defaulting to `False`. If set to `True`, X11 forwarding will
               be requested and a failure will raise :exc:`ChannelOpenError`.
               It can also be set to `'ignore_failure'` to attempt X11
               forwarding but ignore failures.
           :param x11_display: (optional)
               The display that X11 connections should be forwarded to,
               defaulting to the value in the environment variable `DISPLAY`.
           :param x11_auth_path: (optional)
               The path to the Xauthority file to read X11 authentication
               data from, defaulting to the value in the environment variable
               `XAUTHORITY` or the file :file:`.Xauthority` in the user's
               home directory if that's not set.
           :param x11_single_connection: (optional)
               Whether or not to limit X11 forwarding to a single connection,
               defaulting to `False`.
           :param encoding: (optional)
               The Unicode encoding to use for data exchanged on this session.
           :param errors: (optional)
               The error handling strategy to apply on Unicode encode/decode
               errors.
           :param window: (optional)
               The receive window size for this session.
           :param max_pktsize: (optional)
               The maximum packet size for this session.
           :type session_factory: `callable`
           :type command: `str`
           :type subsystem: `str`
           :type env: `dict` with `bytes` or `str` keys and values
           :type send_env: `list` of `bytes` or `str`
           :type request_pty: `bool`, `'force'`, or `'auto'`
           :type term_type: `str`
           :type term_size: `tuple` of 2 or 4 `int` values
           :type term_modes: `dict` with `int` keys and values
           :type x11_forwarding: `bool` or `'ignore_failure'`
           :type x11_display: `str`
           :type x11_auth_path: `str`
           :type x11_single_connection: `bool`
           :type encoding: `str` or `None`
           :type errors: `str`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: an :class:`SSHClientChannel` and :class:`SSHClientSession`

           :raises: :exc:`ChannelOpenError` if the session can't be opened

        """

        if command == ():
            command = self._options.command

        if subsystem == ():
            subsystem = self._options.subsystem

        if env == ():
            env = self._options.env

        if send_env == ():
            send_env = self._options.send_env

        if request_pty == ():
            request_pty = self._options.request_pty

        if term_type == ():
            term_type = self._options.term_type

        if term_size == ():
            term_size = self._options.term_size

        if term_modes == ():
            term_modes = self._options.term_modes

        if x11_forwarding == ():
            x11_forwarding = self._options.x11_forwarding

        if x11_display == ():
            x11_display = self._options.x11_display

        if x11_auth_path == ():
            x11_auth_path = self._options.x11_auth_path

        if x11_single_connection == ():
            x11_single_connection = self._options.x11_single_connection

        if encoding == ():
            encoding = self._options.encoding

        if errors == ():
            errors = self._options.errors

        if window == ():
            window = self._options.window

        if max_pktsize == ():
            max_pktsize = self._options.max_pktsize

        new_env: Dict[bytes, bytes] = {}

        if send_env:
            new_env.update(lookup_env(send_env))

        if env:
            new_env.update(encode_env(env))

        if request_pty == 'force':
            request_pty = True
        elif request_pty == 'auto':
            request_pty = bool(term_type and not (command or subsystem))
        elif request_pty:
            request_pty = bool(term_type)

        command: Optional[str]
        subsystem: Optional[str]
        request_pty: bool
        term_type: Optional[str]
        term_size: TermSizeArg
        term_modes: TermModesArg
        x11_forwarding: Union[bool, str]
        x11_display: Optional[str]
        x11_auth_path: Optional[str]
        x11_single_connection: bool
        encoding: Optional[str]
        errors: str
        window: int
        max_pktsize: int

        chan = SSHClientChannel(self, self._loop, encoding, errors,
                                window, max_pktsize)

        session = await chan.create(session_factory, command, subsystem,
                                    new_env, request_pty, term_type, term_size,
                                    term_modes or {}, x11_forwarding,
                                    x11_display, x11_auth_path,
                                    x11_single_connection,
                                    bool(self._agent_forward_path))

        return chan, session

    async def open_session(self, *args: object, **kwargs: object) -> \
            Tuple[SSHWriter, SSHReader, SSHReader]:
        """Open an SSH client session

           This method is a coroutine wrapper around :meth:`create_session`
           designed to provide a "high-level" stream interface for creating
           an SSH client session. Instead of taking a `session_factory`
           argument for constructing an object which will handle activity
           on the session via callbacks, it returns an :class:`SSHWriter`
           and two :class:`SSHReader` objects representing stdin, stdout,
           and stderr which can be used to perform I/O on the session. With
           the exception of `session_factory`, all of the arguments to
           :meth:`create_session` are supported and have the same meaning.

        """

        chan, session = await self.create_session(
            SSHClientStreamSession, *args, **kwargs) # type: ignore

        session: SSHClientStreamSession

        return (SSHWriter(session, chan), SSHReader(session, chan),
                SSHReader(session, chan, EXTENDED_DATA_STDERR))

    # pylint: disable=redefined-builtin
    @async_context_manager # type: ignore
    async def create_process(self, *args: object,
                             input: Optional[AnyStr] = None,
                             stdin: ProcessSource = PIPE,
                             stdout: ProcessTarget = PIPE,
                             stderr: ProcessTarget = PIPE,
                             bufsize: int = io.DEFAULT_BUFFER_SIZE,
                             send_eof: bool = True, recv_eof: bool = True,
                             **kwargs: object) -> SSHClientProcess[AnyStr]:
        """Create a process on the remote system

           This method is a coroutine wrapper around :meth:`create_session`
           which can be used to execute a command, start a subsystem,
           or start an interactive shell, optionally redirecting stdin,
           stdout, and stderr to and from files or pipes attached to
           other local and remote processes.

           By default, the stdin, stdout, and stderr arguments default
           to the special value `PIPE` which means that they can be
           read and written interactively via stream objects which are
           members of the :class:`SSHClientProcess` object this method
           returns. If other file-like objects are provided as arguments,
           input or output will automatically be redirected to them. The
           special value `DEVNULL` can be used to provide no input or
           discard all output, and the special value `STDOUT` can be
           provided as `stderr` to send its output to the same stream
           as `stdout`.

           In addition to the arguments below, all arguments to
           :meth:`create_session` except for `session_factory` are
           supported and have the same meaning.

           :param input: (optional)
               Input data to feed to standard input of the remote process.
               If specified, this argument takes precedence over stdin.
               Data should be a `str` if encoding is set, or `bytes` if not.
           :param stdin: (optional)
               A filename, file-like object, file descriptor, socket, or
               :class:`SSHReader` to feed to standard input of the remote
               process, or `DEVNULL` to provide no input.
           :param stdout: (optional)
               A filename, file-like object, file descriptor, socket, or
               :class:`SSHWriter` to feed standard output of the remote
               process to, or `DEVNULL` to discard this output.
           :param stderr: (optional)
               A filename, file-like object, file descriptor, socket, or
               :class:`SSHWriter` to feed standard error of the remote
               process to, `DEVNULL` to discard this output, or `STDOUT`
               to feed standard error to the same place as stdout.
           :param bufsize: (optional)
               Buffer size to use when feeding data from a file to stdin
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
           :type input: `str` or `bytes`
           :type bufsize: `int`
           :type send_eof: `bool`
           :type recv_eof: `bool`

           :returns: :class:`SSHClientProcess`

           :raises: :exc:`ChannelOpenError` if the channel can't be opened

        """

        chan, process = await self.create_session(
            SSHClientProcess, *args, **kwargs) # type: ignore

        new_stdin: Optional[ProcessSource] = stdin
        process: SSHClientProcess

        if input:
            chan.write(input)
            chan.write_eof()
            new_stdin = None

        await process.redirect(new_stdin, stdout, stderr,
                               bufsize, send_eof, recv_eof)

        return process

    async def create_subprocess(self, protocol_factory: SubprocessFactory,
                                command: DefTuple[Optional[str]] = (),
                                bufsize: int = io.DEFAULT_BUFFER_SIZE,
                                input: Optional[AnyStr] = None,
                                stdin: ProcessSource = PIPE,
                                stdout: ProcessTarget = PIPE,
                                stderr: ProcessTarget = PIPE,
                                encoding: Optional[str] = None,
                                **kwargs: object) -> \
            Tuple[SSHSubprocessTransport, SSHSubprocessProtocol]:
        """Create a subprocess on the remote system

           This method is a coroutine wrapper around :meth:`create_session`
           which can be used to execute a command, start a subsystem,
           or start an interactive shell, optionally redirecting stdin,
           stdout, and stderr to and from files or pipes attached to
           other local and remote processes similar to :meth:`create_process`.
           However, instead of performing interactive I/O using
           :class:`SSHReader` and :class:`SSHWriter` objects, the caller
           provides a function which returns an object which conforms
           to the :class:`asyncio.SubprocessProtocol` and this call
           returns that and an :class:`SSHSubprocessTransport` object which
           conforms to :class:`asyncio.SubprocessTransport`.

           With the exception of the addition of `protocol_factory`, all
           of the arguments are the same as :meth:`create_process`.

           :param protocol_factory:
               A `callable` which returns an :class:`SSHSubprocessProtocol`
               object that will be created to handle activity on this
               session.
           :type protocol_factory: `callable`

           :returns: an :class:`SSHSubprocessTransport` and
                     :class:`SSHSubprocessProtocol`

           :raises: :exc:`ChannelOpenError` if the channel can't be opened

        """

        def transport_factory() -> SSHSubprocessTransport:
            """Return a subprocess transport"""

            return SSHSubprocessTransport(protocol_factory)

        _, transport = await self.create_session(transport_factory, command,
                                                 encoding=encoding,
                                                 **kwargs) # type: ignore

        new_stdin: Optional[ProcessSource] = stdin
        transport: SSHSubprocessTransport

        if input:
            stdin_pipe = cast(SSHSubprocessWritePipe,
                              transport.get_pipe_transport(0))
            stdin_pipe.write(input)
            stdin_pipe.write_eof()
            new_stdin = None

        await transport.redirect(new_stdin, stdout, stderr, bufsize)

        return transport, transport.get_protocol()
    # pylint: enable=redefined-builtin

    async def run(self, *args: object, check: bool = False,
                  timeout: Optional[float] = None,
                  **kwargs: object) -> SSHCompletedProcess:
        """Run a command on the remote system and collect its output

           This method is a coroutine wrapper around :meth:`create_process`
           which can be used to run a process to completion when no
           interactivity is needed. All of the arguments to
           :meth:`create_process` can be passed in to provide input or
           redirect stdin, stdout, and stderr, but this method waits until
           the process exits and returns an :class:`SSHCompletedProcess`
           object with the exit status or signal information and the
           output to stdout and stderr (if not redirected).

           If the check argument is set to `True`, a non-zero exit status
           from the remote process will trigger the :exc:`ProcessError`
           exception to be raised.

           In addition to the argument below, all arguments to
           :meth:`create_process` are supported and have the same meaning.

           If a timeout is specified and it expires before the process
           exits, the :exc:`TimeoutError` exception will be raised. By
           default, no timeout is set and this call will wait indefinitely.

           :param check: (optional)
               Whether or not to raise :exc:`ProcessError` when a non-zero
               exit status is returned
           :param timeout:
               Amount of time in seconds to wait for process to exit or
               `None` to wait indefinitely
           :type check: `bool`
           :type timeout: `int`, `float`, or `None`

           :returns: :class:`SSHCompletedProcess`

           :raises: | :exc:`ChannelOpenError` if the session can't be opened
                    | :exc:`ProcessError` if checking non-zero exit status
                    | :exc:`TimeoutError` if the timeout expires before exit

        """

        process = await self.create_process(*args, **kwargs) # type: ignore

        return await process.wait(check, timeout)

    async def create_connection(
            self, session_factory: SSHTCPSessionFactory[AnyStr],
            remote_host: str, remote_port: int, orig_host: str = '',
            orig_port: int = 0, *, encoding: Optional[str] = None,
            errors: str = 'strict', window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
                Tuple[SSHTCPChannel[AnyStr], SSHTCPSession[AnyStr]]:
        """Create an SSH TCP direct connection

           This method is a coroutine which can be called to request that
           the server open a new outbound TCP connection to the specified
           destination host and port. If the connection is successfully
           opened, a new SSH channel will be opened with data being handled
           by a :class:`SSHTCPSession` object created by `session_factory`.

           Optional arguments include the host and port of the original
           client opening the connection when performing TCP port forwarding.

           By default, this class expects data to be sent and received as
           raw bytes. However, an optional encoding argument can be passed
           in to select the encoding to use, allowing the application send
           and receive string data. When encoding is set, an optional errors
           argument can be passed in to select what Unicode error handling
           strategy to use.

           Other optional arguments include the SSH receive window size and
           max packet size which default to 2 MB and 32 KB, respectively.

           :param session_factory:
               A `callable` which returns an :class:`SSHTCPSession` object
               that will be created to handle activity on this session
           :param remote_host:
               The remote hostname or address to connect to
           :param remote_port:
               The remote port number to connect to
           :param orig_host: (optional)
               The hostname or address of the client requesting the connection
           :param orig_port: (optional)
               The port number of the client requesting the connection
           :param encoding: (optional)
               The Unicode encoding to use for data exchanged on the connection
           :param errors: (optional)
               The error handling strategy to apply on encode/decode errors
           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type session_factory: `callable`
           :type remote_host: `str`
           :type remote_port: `int`
           :type orig_host: `str`
           :type orig_port: `int`
           :type encoding: `str` or `None`
           :type errors: `str`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: an :class:`SSHTCPChannel` and :class:`SSHTCPSession`

           :raises: :exc:`ChannelOpenError` if the connection can't be opened

        """

        self.logger.info('Opening direct TCP connection to %s',
                         (remote_host, remote_port))
        self.logger.info('  Client address: %s', (orig_host, orig_port))

        chan = self.create_tcp_channel(encoding, errors, window, max_pktsize)

        session = await chan.connect(session_factory, remote_host, remote_port,
                                     orig_host, orig_port)

        return chan, session

    async def open_connection(self, *args: object, **kwargs: object) -> \
            Tuple[SSHReader, SSHWriter]:
        """Open an SSH TCP direct connection

           This method is a coroutine wrapper around :meth:`create_connection`
           designed to provide a "high-level" stream interface for creating
           an SSH TCP direct connection. Instead of taking a
           `session_factory` argument for constructing an object which will
           handle activity on the session via callbacks, it returns
           :class:`SSHReader` and :class:`SSHWriter` objects which can be
           used to perform I/O on the connection.

           With the exception of `session_factory`, all of the arguments
           to :meth:`create_connection` are supported and have the same
           meaning here.

           :returns: an :class:`SSHReader` and :class:`SSHWriter`

           :raises: :exc:`ChannelOpenError` if the connection can't be opened

        """

        chan, session = await self.create_connection(
            SSHTCPStreamSession, *args, **kwargs) # type: ignore

        session: SSHTCPStreamSession

        return SSHReader(session, chan), SSHWriter(session, chan)

    @async_context_manager
    async def create_server(
            self, session_factory: TCPListenerFactory[AnyStr],
            listen_host: str, listen_port: int, *,
            encoding: Optional[str] = None, errors: str = 'strict',
            window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> SSHListener:
        """Create a remote SSH TCP listener

           This method is a coroutine which can be called to request that
           the server listen on the specified remote address and port for
           incoming TCP connections. If the request is successful, the
           return value is an :class:`SSHListener` object which can be
           used later to shut down the listener. If the request fails,
           `None` is returned.

           :param session_factory:
               A `callable` or coroutine which takes arguments of the
               original host and port of the client and decides whether
               to accept the connection or not, either returning an
               :class:`SSHTCPSession` object used to handle activity
               on that connection or raising :exc:`ChannelOpenError`
               to indicate that the connection should not be accepted
           :param listen_host:
               The hostname or address on the remote host to listen on
           :param listen_port:
               The port number on the remote host to listen on
           :param encoding: (optional)
               The Unicode encoding to use for data exchanged on the connection
           :param errors: (optional)
               The error handling strategy to apply on encode/decode errors
           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type session_factory: `callable` or coroutine
           :type listen_host: `str`
           :type listen_port: `int`
           :type encoding: `str` or `None`
           :type errors: `str`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: :class:`SSHListener`

           :raises: :class:`ChannelListenError` if the listener can't be opened

        """

        listen_host = listen_host.lower()

        self.logger.info('Creating remote TCP listener on %s',
                         (listen_host, listen_port))

        pkttype, packet = await self._make_global_request(
            b'tcpip-forward', String(listen_host), UInt32(listen_port))

        if pkttype == MSG_REQUEST_SUCCESS:
            if listen_port == 0:
                listen_port = packet.get_uint32()
                dynamic = True
            else:
                # OpenSSH 6.8 introduced a bug which causes the reply
                # to contain an extra uint32 value of 0 when non-dynamic
                # ports are requested, causing the check_end() call below
                # to fail. This check works around this problem.
                if len(packet.get_remaining_payload()) == 4: # pragma: no cover
                    packet.get_uint32()

                dynamic = False

            packet.check_end()

            listener = SSHTCPClientListener[AnyStr](self, session_factory,
                                                    listen_host, listen_port,
                                                    encoding, errors,
                                                    window, max_pktsize)

            if dynamic:
                self.logger.debug1('Assigning dynamic port %d', listen_port)

                self._dynamic_remote_listeners[listen_host] = listener

            self._remote_listeners[listen_host, listen_port] = listener
            return listener
        else:
            packet.check_end()
            self.logger.debug1('Failed to create remote TCP listener')
            raise ChannelListenError('Failed to create remote TCP listener')

    @async_context_manager
    async def start_server(self, handler_factory: _TCPServerHandlerFactory,
                           *args: object, **kwargs: object) -> SSHListener:
        """Start a remote SSH TCP listener

           This method is a coroutine wrapper around :meth:`create_server`
           designed to provide a "high-level" stream interface for creating
           remote SSH TCP listeners. Instead of taking a `session_factory`
           argument for constructing an object which will handle activity on
           the session via callbacks, it takes a `handler_factory` which
           returns a `callable` or coroutine that will be passed
           :class:`SSHReader` and :class:`SSHWriter` objects which can be
           used to perform I/O on each new connection which arrives. Like
           :meth:`create_server`, `handler_factory` can also raise
           :exc:`ChannelOpenError` if the connection should not be accepted.

           With the exception of `handler_factory` replacing
           `session_factory`, all of the arguments to :meth:`create_server`
           are supported and have the same meaning here.

           :param handler_factory:
               A `callable` or coroutine which takes arguments of the
               original host and port of the client and decides whether to
               accept the connection or not, either returning a callback
               or coroutine used to handle activity on that connection
               or raising :exc:`ChannelOpenError` to indicate that the
               connection should not be accepted
           :type handler_factory: `callable` or coroutine

           :returns: :class:`SSHListener`

           :raises: :class:`ChannelListenError` if the listener can't be opened

        """

        def session_factory(orig_host: str, orig_port: int) -> SSHTCPSession:
            """Return a TCP stream session handler"""

            return SSHTCPStreamSession(handler_factory(orig_host, orig_port))

        return await self.create_server(session_factory,
                                        *args, **kwargs) # type: ignore

    async def create_unix_connection(
            self, session_factory: SSHUNIXSessionFactory[AnyStr],
            remote_path: str, *, encoding: Optional[str] = None,
            errors: str = 'strict', window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
                Tuple[SSHUNIXChannel[AnyStr], SSHUNIXSession[AnyStr]]:
        """Create an SSH UNIX domain socket direct connection

           This method is a coroutine which can be called to request that
           the server open a new outbound UNIX domain socket connection to
           the specified destination path. If the connection is successfully
           opened, a new SSH channel will be opened with data being handled
           by a :class:`SSHUNIXSession` object created by `session_factory`.

           By default, this class expects data to be sent and received as
           raw bytes. However, an optional encoding argument can be passed
           in to select the encoding to use, allowing the application to
           send and receive string data. When encoding is set, an optional
           errors argument can be passed in to select what Unicode error
           handling strategy to use.

           Other optional arguments include the SSH receive window size and
           max packet size which default to 2 MB and 32 KB, respectively.

           :param session_factory:
               A `callable` which returns an :class:`SSHUNIXSession` object
               that will be created to handle activity on this session
           :param remote_path:
               The remote path to connect to
           :param encoding: (optional)
               The Unicode encoding to use for data exchanged on the connection
           :param errors: (optional)
               The error handling strategy to apply on encode/decode errors
           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type session_factory: `callable`
           :type remote_path: `str`
           :type encoding: `str` or `None`
           :type errors: `str`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: an :class:`SSHUNIXChannel` and :class:`SSHUNIXSession`

           :raises: :exc:`ChannelOpenError` if the connection can't be opened

        """

        self.logger.info('Opening direct UNIX connection to %s', remote_path)

        chan = self.create_unix_channel(encoding, errors, window, max_pktsize)

        session = await chan.connect(session_factory, remote_path)

        return chan, session

    async def open_unix_connection(self, *args: object, **kwargs: object) -> \
            Tuple[SSHReader, SSHWriter]:
        """Open an SSH UNIX domain socket direct connection

           This method is a coroutine wrapper around
           :meth:`create_unix_connection` designed to provide a "high-level"
           stream interface for creating an SSH UNIX domain socket direct
           connection. Instead of taking a `session_factory` argument for
           constructing an object which will handle activity on the session
           via callbacks, it returns :class:`SSHReader` and :class:`SSHWriter`
           objects which can be used to perform I/O on the connection.

           With the exception of `session_factory`, all of the arguments
           to :meth:`create_unix_connection` are supported and have the same
           meaning here.

           :returns: an :class:`SSHReader` and :class:`SSHWriter`

           :raises: :exc:`ChannelOpenError` if the connection can't be opened

        """

        chan, session = \
            await self.create_unix_connection(SSHUNIXStreamSession,
                                              *args, **kwargs) # type: ignore

        session: SSHUNIXStreamSession

        return SSHReader(session, chan), SSHWriter(session, chan)

    @async_context_manager
    async def create_unix_server(
            self, session_factory: UNIXListenerFactory[AnyStr],
            listen_path: str, *, encoding: Optional[str] = None,
            errors: str = 'strict', window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> SSHListener:
        """Create a remote SSH UNIX domain socket listener

           This method is a coroutine which can be called to request that
           the server listen on the specified remote path for incoming UNIX
           domain socket connections. If the request is successful, the
           return value is an :class:`SSHListener` object which can be
           used later to shut down the listener. If the request fails,
           `None` is returned.

           :param session_factory:
               A `callable` or coroutine which decides whether to accept
               the connection or not, either returning an
               :class:`SSHUNIXSession` object used to handle activity
               on that connection or raising :exc:`ChannelOpenError`
               to indicate that the connection should not be accepted
           :param listen_path:
               The path on the remote host to listen on
           :param encoding: (optional)
               The Unicode encoding to use for data exchanged on the connection
           :param errors: (optional)
               The error handling strategy to apply on encode/decode errors
           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type session_factory: `callable`
           :type listen_path: `str`
           :type encoding: `str` or `None`
           :type errors: `str`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: :class:`SSHListener`

           :raises: :class:`ChannelListenError` if the listener can't be opened

        """

        self.logger.info('Creating remote UNIX listener on %s', listen_path)

        pkttype, packet = await self._make_global_request(
            b'streamlocal-forward@openssh.com', String(listen_path))

        packet.check_end()

        if pkttype == MSG_REQUEST_SUCCESS:
            listener = SSHUNIXClientListener[AnyStr](self, session_factory,
                                                     listen_path, encoding,
                                                     errors, window,
                                                     max_pktsize)

            self._remote_listeners[listen_path] = listener
            return listener
        else:
            self.logger.debug1('Failed to create remote UNIX listener')
            raise ChannelListenError('Failed to create remote UNIX listener')

    @async_context_manager
    async def start_unix_server(
            self, handler_factory: _UNIXServerHandlerFactory,
            *args: object, **kwargs: object) -> SSHListener:
        """Start a remote SSH UNIX domain socket listener

           This method is a coroutine wrapper around :meth:`create_unix_server`
           designed to provide a "high-level" stream interface for creating
           remote SSH UNIX domain socket listeners. Instead of taking a
           `session_factory` argument for constructing an object which
           will handle activity on the session via callbacks, it takes a
           `handler_factory` which returns a `callable` or coroutine that
           will be passed :class:`SSHReader` and :class:`SSHWriter` objects
           which can be used to perform I/O on each new connection which
           arrives. Like :meth:`create_unix_server`, `handler_factory`
           can also raise :exc:`ChannelOpenError` if the connection should
           not be accepted.

           With the exception of `handler_factory` replacing
           `session_factory`, all of the arguments to
           :meth:`create_unix_server` are supported and have the same
           meaning here.

           :param handler_factory:
               A `callable` or coroutine which decides whether to accept
               the UNIX domain socket connection or not, either returning
               a callback or coroutine used to handle activity on that
               connection or raising :exc:`ChannelOpenError` to indicate
               that the connection should not be accepted
           :type handler_factory: `callable` or coroutine

           :returns: :class:`SSHListener`

           :raises: :class:`ChannelListenError` if the listener can't be opened

        """

        def session_factory() -> SSHUNIXStreamSession:
            """Return a UNIX domain socket stream session handler"""

            return SSHUNIXStreamSession(handler_factory())

        return await self.create_unix_server(session_factory,
                                             *args, **kwargs) # type: ignore

    async def create_ssh_connection(self, client_factory: _ClientFactory,
                                    host: str, port: DefTuple[int] = (),
                                    **kwargs: object) -> \
                Tuple['SSHClientConnection', SSHClient]:
        """Create a tunneled SSH client connection

           This method is a coroutine which can be called to open an
           SSH client connection to the requested host and port tunneled
           inside this already established connection. It takes all the
           same arguments as :func:`create_connection` but requests
           that the upstream SSH server open the connection rather than
           connecting directly.

        """

        return (await create_connection(client_factory, host, port,
                                        tunnel=self, **kwargs)) # type: ignore

    @async_context_manager
    async def connect_ssh(self, host: str, port: DefTuple[int] = (),
                          **kwargs: object) -> 'SSHClientConnection':
        """Make a tunneled SSH client connection

           This method is a coroutine which can be called to open an
           SSH client connection to the requested host and port tunneled
           inside this already established connection. It takes all the
           same arguments as :func:`connect` but requests that the upstream
           SSH server open the connection rather than connecting directly.

        """

        return await connect(host, port, tunnel=self, **kwargs) # type: ignore

    @async_context_manager
    async def connect_reverse_ssh(self, host: str, port: DefTuple[int] = (),
                                  **kwargs: object) -> 'SSHServerConnection':
        """Make a tunneled reverse direction SSH connection

           This method is a coroutine which can be called to open an
           SSH client connection to the requested host and port tunneled
           inside this already established connection. It takes all the
           same arguments as :func:`connect` but requests that the upstream
           SSH server open the connection rather than connecting directly.

        """

        return await connect_reverse(host, port, tunnel=self,
                                     **kwargs) # type: ignore

    @async_context_manager
    async def listen_ssh(self, host: str = '', port: DefTuple[int] = (),
                         **kwargs: object) -> SSHAcceptor:
        """Create a tunneled SSH listener

           This method is a coroutine which can be called to open a remote
           SSH listener on the requested host and port tunneled inside this
           already established connection. It takes all the same arguments as
           :func:`listen` but requests that the upstream SSH server open the
           listener rather than listening directly via TCP/IP.

        """

        return await listen(host, port, tunnel=self, **kwargs) # type: ignore

    @async_context_manager
    async def listen_reverse_ssh(self, host: str = '',
                                 port: DefTuple[int] = (),
                                 **kwargs: object) -> SSHAcceptor:
        """Create a tunneled reverse direction SSH listener

           This method is a coroutine which can be called to open a remote
           SSH listener on the requested host and port tunneled inside this
           already established connection. It takes all the same arguments as
           :func:`listen_reverse` but requests that the upstream SSH server
           open the listener rather than listening directly via TCP/IP.

        """

        return await listen_reverse(host, port, tunnel=self,
                                    **kwargs) # type: ignore

    async def create_tun(
            self, session_factory: SSHTunTapSessionFactory,
            remote_unit: Optional[int] = None, *, window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
                Tuple[SSHTunTapChannel, SSHTunTapSession]:
        """Create an SSH layer 3 tunnel

           This method is a coroutine which can be called to request that
           the server open a new outbound layer 3 tunnel to the specified
           remote TUN device. If the tunnel is successfully opened, a new
           SSH channel will be opened with data being handled by a
           :class:`SSHTunTapSession` object created by `session_factory`.

           Optional arguments include the SSH receive window size and max
           packet size which default to 2 MB and 32 KB, respectively.

           :param session_factory:
               A `callable` which returns an :class:`SSHUNIXSession` object
               that will be created to handle activity on this session
           :param remote_unit:
               The remote TUN device to connect to
           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type session_factory: `callable`
           :type remote_unit: `int` or `None`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: an :class:`SSHTunTapChannel` and :class:`SSHTunTapSession`

           :raises: :exc:`ChannelOpenError` if the connection can't be opened

        """

        self.logger.info('Opening layer 3 tunnel to remote unit %s',
                         'any' if remote_unit is None else str(remote_unit))

        chan = self.create_tuntap_channel(window, max_pktsize)

        session = await chan.open(session_factory, SSH_TUN_MODE_POINTTOPOINT,
                                  remote_unit)

        return chan, session

    async def create_tap(
            self, session_factory: SSHTunTapSessionFactory,
            remote_unit: Optional[int] = None, *, window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
                Tuple[SSHTunTapChannel, SSHTunTapSession]:
        """Create an SSH layer 2 tunnel

           This method is a coroutine which can be called to request that
           the server open a new outbound layer 2 tunnel to the specified
           remote TAP device. If the tunnel is successfully opened, a new
           SSH channel will be opened with data being handled by a
           :class:`SSHTunTapSession` object created by `session_factory`.

           Optional arguments include the SSH receive window size and max
           packet size which default to 2 MB and 32 KB, respectively.

           :param session_factory:
               A `callable` which returns an :class:`SSHUNIXSession` object
               that will be created to handle activity on this session
           :param remote_unit:
               The remote TAP device to connect to
           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type session_factory: `callable`
           :type remote_unit: `int` or `None`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: an :class:`SSHTunTapChannel` and :class:`SSHTunTapSession`

           :raises: :exc:`ChannelOpenError` if the connection can't be opened

        """

        self.logger.info('Opening layer 2 tunnel to remote unit %s',
                         'any' if remote_unit is None else str(remote_unit))

        chan = self.create_tuntap_channel(window, max_pktsize)

        session = await chan.open(session_factory, SSH_TUN_MODE_ETHERNET,
                                  remote_unit)

        return chan, session

    async def open_tun(self, *args: object, **kwargs: object) -> \
            Tuple[SSHReader, SSHWriter]:
        """Open an SSH layer 3 tunnel

           This method is a coroutine wrapper around :meth:`create_tun`
           designed to provide a "high-level" stream interface for creating
           an SSH layer 3 tunnel. Instead of taking a `session_factory`
           argument for constructing an object which will handle activity
           on the session via callbacks, it returns :class:`SSHReader` and
           :class:`SSHWriter` objects which can be used to perform I/O on
           the tunnel.

           With the exception of `session_factory`, all of the arguments
           to :meth:`create_tun` are supported and have the same meaning here.

           :returns: an :class:`SSHReader` and :class:`SSHWriter`

           :raises: :exc:`ChannelOpenError` if the connection can't be opened

        """

        chan, session = await self.create_tun(SSHTunTapStreamSession,
                                              *args, **kwargs) # type: ignore

        session: SSHTunTapStreamSession

        return SSHReader(session, chan), SSHWriter(session, chan)

    async def open_tap(self, *args: object, **kwargs: object) -> \
            Tuple[SSHReader, SSHWriter]:
        """Open an SSH layer 2 tunnel

           This method is a coroutine wrapper around :meth:`create_tap`
           designed to provide a "high-level" stream interface for creating
           an SSH layer 2 tunnel. Instead of taking a `session_factory`
           argument for constructing an object which will handle activity
           on the session via callbacks, it returns :class:`SSHReader` and
           :class:`SSHWriter` objects which can be used to perform I/O on
           the tunnel.

           With the exception of `session_factory`, all of the arguments
           to :meth:`create_tap` are supported and have the same meaning here.

           :returns: an :class:`SSHReader` and :class:`SSHWriter`

           :raises: :exc:`ChannelOpenError` if the connection can't be opened

        """

        chan, session = await self.create_tap(SSHTunTapStreamSession,
                                              *args, **kwargs) # type: ignore

        session: SSHTunTapStreamSession

        return SSHReader(session, chan), SSHWriter(session, chan)

    @async_context_manager
    async def forward_local_port_to_path(
            self, listen_host: str, listen_port: int, dest_path: str,
            accept_handler: Optional[SSHAcceptHandler] = None) -> SSHListener:
        """Set up local TCP port forwarding to a remote UNIX domain socket

           This method is a coroutine which attempts to set up port
           forwarding from a local TCP listening port to a remote UNIX
           domain path via the SSH connection. If the request is successful,
           the return value is an :class:`SSHListener` object which can be
           used later to shut down the port forwarding.

           :param listen_host:
               The hostname or address on the local host to listen on
           :param listen_port:
               The port number on the local host to listen on
           :param dest_path:
               The path on the remote host to forward the connections to
           :param accept_handler:
               A `callable` or coroutine which takes arguments of the
               original host and port of the client and decides whether
               or not to allow connection forwarding, returning `True` to
               accept the connection and begin forwarding or `False` to
               reject and close it.
           :type listen_host: `str`
           :type listen_port: `int`
           :type dest_path: `str`
           :type accept_handler: `callable` or coroutine

           :returns: :class:`SSHListener`

           :raises: :exc:`OSError` if the listener can't be opened

        """

        async def tunnel_connection(
                session_factory: SSHUNIXSessionFactory[bytes],
                orig_host: str, orig_port: int) -> \
                    Tuple[SSHUNIXChannel[bytes], SSHUNIXSession[bytes]]:
            """Forward a local connection over SSH"""

            if accept_handler:
                result = accept_handler(orig_host, orig_port)

                if inspect.isawaitable(result):
                    result = await cast(Awaitable[bool], result)

                if not result:
                    self.logger.info('Request for TCP forwarding from '
                                     '%s to %s denied by application',
                                     (orig_host, orig_port), dest_path)

                    raise ChannelOpenError(OPEN_ADMINISTRATIVELY_PROHIBITED,
                                           'Connection forwarding denied')

            return (await self.create_unix_connection(session_factory,
                                                      dest_path))

        self.logger.info('Creating local TCP forwarder from %s to %s',
                         (listen_host, listen_port), dest_path)

        try:
            listener = await create_tcp_forward_listener(self, self._loop,
                                                         tunnel_connection,
                                                         listen_host,
                                                         listen_port)
        except OSError as exc:
            self.logger.debug1('Failed to create local TCP listener: %s', exc)
            raise

        if listen_port == 0:
            listen_port = listener.get_port()

        self._local_listeners[listen_host, listen_port] = listener

        return listener

    @async_context_manager
    async def forward_local_path_to_port(self, listen_path: str,
                                         dest_host: str,
                                         dest_port: int) -> SSHListener:
        """Set up local UNIX domain socket forwarding to a remote TCP port

           This method is a coroutine which attempts to set up UNIX domain
           socket forwarding from a local listening path to a remote host
           and port via the SSH connection. If the request is successful,
           the return value is an :class:`SSHListener` object which can
           be used later to shut down the UNIX domain socket forwarding.

           :param listen_path:
               The path on the local host to listen on
           :param dest_host:
               The hostname or address to forward the connections to
           :param dest_port:
               The port number to forward the connections to
           :type listen_path: `str`
           :type dest_host: `str`
           :type dest_port: `int`

           :returns: :class:`SSHListener`

           :raises: :exc:`OSError` if the listener can't be opened

        """

        async def tunnel_connection(
                session_factory: SSHTCPSessionFactory[bytes]) -> \
                    Tuple[SSHTCPChannel[bytes], SSHTCPSession[bytes]]:
            """Forward a local connection over SSH"""

            return await self.create_connection(session_factory, dest_host,
                                                dest_port, '', 0)

        self.logger.info('Creating local UNIX forwarder from %s to %s',
                         listen_path, (dest_host, dest_port))

        try:
            listener = await create_unix_forward_listener(self, self._loop,
                                                          tunnel_connection,
                                                          listen_path)
        except OSError as exc:
            self.logger.debug1('Failed to create local UNIX listener: %s', exc)
            raise

        self._local_listeners[listen_path] = listener

        return listener

    @async_context_manager
    async def forward_remote_port(self, listen_host: str,
                                  listen_port: int, dest_host: str,
                                  dest_port: int) -> SSHListener:
        """Set up remote port forwarding

           This method is a coroutine which attempts to set up port
           forwarding from a remote listening port to a local host and port
           via the SSH connection. If the request is successful, the
           return value is an :class:`SSHListener` object which can be
           used later to shut down the port forwarding. If the request
           fails, `None` is returned.

           :param listen_host:
               The hostname or address on the remote host to listen on
           :param listen_port:
               The port number on the remote host to listen on
           :param dest_host:
               The hostname or address to forward connections to
           :param dest_port:
               The port number to forward connections to
           :type listen_host: `str`
           :type listen_port: `int`
           :type dest_host: `str`
           :type dest_port: `int`

           :returns: :class:`SSHListener`

           :raises: :class:`ChannelListenError` if the listener can't be opened

        """

        def session_factory(_orig_host: str,
                            _orig_port: int) -> Awaitable[SSHTCPSession]:
            """Return an SSHTCPSession used to do remote port forwarding"""

            return cast(Awaitable[SSHTCPSession],
                        self.forward_connection(dest_host, dest_port))

        self.logger.info('Creating remote TCP forwarder from %s to %s',
                         (listen_host, listen_port), (dest_host, dest_port))

        return await self.create_server(session_factory, listen_host,
                                        listen_port)

    @async_context_manager
    async def forward_remote_path(self, listen_path: str,
                                  dest_path: str) -> SSHListener:
        """Set up remote UNIX domain socket forwarding

           This method is a coroutine which attempts to set up UNIX domain
           socket forwarding from a remote listening path to a local path
           via the SSH connection. If the request is successful, the
           return value is an :class:`SSHListener` object which can be
           used later to shut down the port forwarding. If the request
           fails, `None` is returned.

           :param listen_path:
               The path on the remote host to listen on
           :param dest_path:
               The path on the local host to forward connections to
           :type listen_path: `str`
           :type dest_path: `str`

           :returns: :class:`SSHListener`

           :raises: :class:`ChannelListenError` if the listener can't be opened

        """

        def session_factory() -> Awaitable[SSHUNIXSession[bytes]]:
            """Return an SSHUNIXSession used to do remote path forwarding"""

            return cast(Awaitable[SSHUNIXSession[bytes]],
                        self.forward_unix_connection(dest_path))

        self.logger.info('Creating remote UNIX forwarder from %s to %s',
                         listen_path, dest_path)

        return await self.create_unix_server(session_factory, listen_path)

    @async_context_manager
    async def forward_remote_port_to_path(self, listen_host: str,
                                          listen_port: int,
                                          dest_path: str) -> SSHListener:
        """Set up remote TCP port forwarding to a local UNIX domain socket

           This method is a coroutine which attempts to set up port
           forwarding from a remote TCP listening port to a local UNIX
           domain socket path via the SSH connection. If the request is
           successful, the return value is an :class:`SSHListener` object
           which can be used later to shut down the port forwarding. If
           the request fails, `None` is returned.

           :param listen_host:
               The hostname or address on the remote host to listen on
           :param listen_port:
               The port number on the remote host to listen on
           :param dest_path:
               The path on the local host to forward connections to
           :type listen_host: `str`
           :type listen_port: `int`
           :type dest_path: `str`

           :returns: :class:`SSHListener`

           :raises: :class:`ChannelListenError` if the listener can't be opened

        """

        def session_factory(_orig_host: str,
                            _orig_port: int) -> Awaitable[SSHUNIXSession]:
            """Return an SSHTCPSession used to do remote port forwarding"""

            return cast(Awaitable[SSHUNIXSession],
                        self.forward_unix_connection(dest_path))

        self.logger.info('Creating remote TCP forwarder from %s to %s',
                         (listen_host, listen_port), dest_path)

        return await self.create_server(session_factory, listen_host,
                                        listen_port)

    @async_context_manager
    async def forward_remote_path_to_port(self, listen_path: str,
                                          dest_host: str,
                                          dest_port: int) -> SSHListener:
        """Set up remote UNIX domain socket forwarding to a local TCP port

           This method is a coroutine which attempts to set up UNIX domain
           socket forwarding from a remote listening path to a local TCP
           host and port via the SSH connection. If the request is
           successful, the return value is an :class:`SSHListener` object
           which can be used later to shut down the port forwarding. If
           the request fails, `None` is returned.

           :param listen_path:
               The path on the remote host to listen on
           :param dest_host:
               The hostname or address to forward connections to
           :param dest_port:
               The port number to forward connections to
           :type listen_path: `str`
           :type dest_host: `str`
           :type dest_port: `int`

           :returns: :class:`SSHListener`

           :raises: :class:`ChannelListenError` if the listener can't be opened

        """

        def session_factory() -> Awaitable[SSHTCPSession[bytes]]:
            """Return an SSHUNIXSession used to do remote path forwarding"""

            return cast(Awaitable[SSHTCPSession[bytes]],
                        self.forward_connection(dest_host, dest_port))

        self.logger.info('Creating remote UNIX forwarder from %s to %s',
                         listen_path, (dest_host, dest_port))

        return await self.create_unix_server(session_factory, listen_path)

    @async_context_manager
    async def forward_socks(self, listen_host: str,
                            listen_port: int) -> SSHListener:
        """Set up local port forwarding via SOCKS

           This method is a coroutine which attempts to set up dynamic
           port forwarding via SOCKS on the specified local host and
           port. Each SOCKS request contains the destination host and
           port to connect to and triggers a request to tunnel traffic
           to the requested host and port via the SSH connection.

           If the request is successful, the return value is an
           :class:`SSHListener` object which can be used later to shut
           down the port forwarding.

           :param listen_host:
               The hostname or address on the local host to listen on
           :param listen_port:
               The port number on the local host to listen on
           :type listen_host: `str`
           :type listen_port: `int`

           :returns: :class:`SSHListener`

           :raises: :exc:`OSError` if the listener can't be opened

        """

        async def tunnel_socks(session_factory: SSHTCPSessionFactory[bytes],
                               dest_host: str, dest_port: int,
                               orig_host: str, orig_port: int) -> \
                Tuple[SSHTCPChannel[bytes], SSHTCPSession[bytes]]:
            """Forward a local SOCKS connection over SSH"""

            return await self.create_connection(session_factory,
                                                dest_host, dest_port,
                                                orig_host, orig_port)

        self.logger.info('Creating local SOCKS forwarder on %s',
                         (listen_host, listen_port))

        try:
            listener = await create_socks_listener(self, self._loop,
                                                   tunnel_socks,
                                                   listen_host, listen_port)
        except OSError as exc:
            self.logger.debug1('Failed to create local SOCKS listener: %s', exc)
            raise

        if listen_port == 0:
            listen_port = listener.get_port()

        self._local_listeners[listen_host, listen_port] = listener

        return listener

    @async_context_manager
    async def forward_tun(self, local_unit: Optional[int] = None,
                          remote_unit: Optional[int] = None) -> SSHForwarder:
        """Set up layer 3 forwarding

           This method is a coroutine which attempts to set up layer 3
           packet forwarding between local and remote TUN devices. If the
           request is successful, the return value is an :class:`SSHForwarder`
           object which can be used later to shut down the forwarding.

           :param local_unit:
               The unit number of the local TUN device to use
           :param remote_unit:
               The unit number of the remote TUN device to use
           :type local_unit: `int` or `None`
           :type remote_unit: `int` or `None`

           :returns: :class:`SSHForwarder`

           :raises: | :exc:`OSError` if the local TUN device can't be opened
                    | :exc:`ChannelOpenError` if the SSH channel can't be opened

        """

        def session_factory() -> SSHTunTapSession:
            """Return an SSHTunTapSession used to do layer 3 forwarding"""

            return cast(SSHTunTapSession,
                        self.forward_tuntap(SSH_TUN_MODE_POINTTOPOINT,
                                            local_unit))

        _, peer = await self.create_tun(session_factory, remote_unit)

        return cast(SSHForwarder, peer)

    @async_context_manager
    async def forward_tap(self, local_unit: Optional[int] = None,
                          remote_unit: Optional[int] = None) -> SSHForwarder:
        """Set up layer 2 forwarding

           This method is a coroutine which attempts to set up layer 2
           packet forwarding between local and remote TAP devices. If the
           request is successful, the return value is an :class:`SSHForwarder`
           object which can be used later to shut down the forwarding.

           :param local_unit:
               The unit number of the local TAP device to use
           :param remote_unit:
               The unit number of the remote TAP device to use
           :type local_unit: `int` or `None`
           :type remote_unit: `int` or `None`

           :returns: :class:`SSHForwarder`

           :raises: | :exc:`OSError` if the local TUN device can't be opened
                    | :exc:`ChannelOpenError` if the SSH channel can't be opened

        """

        def session_factory() -> SSHTunTapSession:
            """Return an SSHTunTapSession used to do layer 2 forwarding"""

            return cast(SSHTunTapSession,
                        self.forward_tuntap(SSH_TUN_MODE_ETHERNET, local_unit))

        _, peer = await self.create_tap(session_factory, remote_unit)

        return cast(SSHForwarder, peer)

    @async_context_manager
    async def start_sftp_client(self, env: DefTuple[Env] = (),
                                send_env: DefTuple[Optional[EnvSeq]] = (),
                                path_encoding: Optional[str] = 'utf-8',
                                path_errors = 'strict',
                                sftp_version = MIN_SFTP_VERSION) -> SFTPClient:
        """Start an SFTP client

           This method is a coroutine which attempts to start a secure
           file transfer session. If it succeeds, it returns an
           :class:`SFTPClient` object which can be used to copy and
           access files on the remote host.

           An optional Unicode encoding can be specified for sending and
           receiving pathnames, defaulting to UTF-8 with strict error
           checking. If an encoding of `None` is specified, pathnames
           will be left as bytes rather than being converted to & from
           strings.

           :param env: (optional)
               The environment variables to set for this SFTP session. Keys
               and values passed in here will be converted to Unicode
               strings encoded as UTF-8 (ISO 10646) for transmission.

                   .. note:: Many SSH servers restrict which environment
                             variables a client is allowed to set. The
                             server's configuration may need to be edited
                             before environment variables can be
                             successfully set in the remote environment.
           :param send_env: (optional)
               A list of environment variable names to pull from
               `os.environ` and set for this SFTP session. Wildcards
               patterns using `'*'` and `'?'` are allowed, and all variables
               with matching names will be sent with whatever value is set
               in the local environment. If a variable is present in both
               env and send_env, the value from env will be used.
           :param path_encoding:
               The Unicode encoding to apply when sending and receiving
               remote pathnames
           :param path_errors:
               The error handling strategy to apply on encode/decode errors
           :param sftp_version: (optional)
               The maximum version of the SFTP protocol to support, currently
               either 3 or 4, defaulting to 3.
           :type env: `dict` with `str` keys and values
           :type send_env: `list` of `str`
           :type path_encoding: `str` or `None`
           :type path_errors: `str`
           :type sftp_version: `int`

           :returns: :class:`SFTPClient`

           :raises: :exc:`SFTPError` if the session can't be opened

        """

        writer, reader, _ = await self.open_session(subsystem='sftp',
                                                    env=env, send_env=send_env,
                                                    encoding=None)

        return await start_sftp_client(self, self._loop, reader, writer,
                                       path_encoding, path_errors,
                                       sftp_version)


class SSHServerConnection(SSHConnection):
    """SSH server connection

       This class represents an SSH server connection.

       During authentication, :meth:`send_auth_banner` can be called to
       send an authentication banner to the client.

       Once authenticated, :class:`SSHServer` objects wishing to create
       session objects with non-default channel properties can call
       :meth:`create_server_channel` from their :meth:`session_requested()
       <SSHServer.session_requested>` method and return a tuple of
       the :class:`SSHServerChannel` object returned from that and either
       an :class:`SSHServerSession` object or a coroutine which returns
       an :class:`SSHServerSession`.

       Similarly, :class:`SSHServer` objects wishing to create TCP
       connection objects with non-default channel properties can call
       :meth:`create_tcp_channel` from their :meth:`connection_requested()
       <SSHServer.connection_requested>` method and return a tuple of
       the :class:`SSHTCPChannel` object returned from that and either
       an :class:`SSHTCPSession` object or a coroutine which returns an
       :class:`SSHTCPSession`.

       :class:`SSHServer` objects wishing to create UNIX domain socket
       connection objects with non-default channel properties can call
       :meth:`create_unix_channel` from the :meth:`unix_connection_requested()
       <SSHServer.unix_connection_requested>` method and return a tuple of
       the :class:`SSHUNIXChannel` object returned from that and either
       an :class:`SSHUNIXSession` object or a coroutine which returns an
       :class:`SSHUNIXSession`.

    """

    _options: 'SSHServerConnectionOptions'
    _owner: SSHServer
    _x11_listener: Optional[SSHX11ServerListener]

    def __init__(self, loop: asyncio.AbstractEventLoop,
                 options: 'SSHServerConnectionOptions',
                 acceptor: _AcceptHandler = None,
                 error_handler: _ErrorHandler = None,
                 wait: Optional[str] = None):
        super().__init__(loop, options, acceptor, error_handler,
                         wait, server=True)

        self._options = options

        self._server_host_keys = options.server_host_keys
        self._all_server_host_keys = options.all_server_host_keys
        self._server_host_key_algs = list(options.server_host_keys.keys())
        self._known_client_hosts = options.known_client_hosts
        self._trust_client_host = options.trust_client_host
        self._authorized_client_keys = options.authorized_client_keys
        self._allow_pty = options.allow_pty
        self._line_editor = options.line_editor
        self._line_echo = options.line_echo
        self._line_history = options.line_history
        self._max_line_length = options.max_line_length
        self._rdns_lookup = options.rdns_lookup
        self._x11_forwarding = options.x11_forwarding
        self._x11_auth_path = options.x11_auth_path
        self._agent_forwarding = options.agent_forwarding
        self._process_factory = options.process_factory
        self._session_factory = options.session_factory
        self._encoding = options.encoding
        self._errors = options.errors
        self._sftp_factory = options.sftp_factory
        self._sftp_version = options.sftp_version
        self._allow_scp = options.allow_scp
        self._window = options.window
        self._max_pktsize = options.max_pktsize

        if options.gss_host:
            try:
                self._gss = GSSServer(options.gss_host, options.gss_store)
                self._gss_kex = options.gss_kex
                self._gss_auth = options.gss_auth
                self._gss_mic_auth = self._gss_auth
            except GSSError:
                pass

        self._server_host_key: Optional[SSHKeyPair] = None
        self._key_options: _KeyOrCertOptions = {}
        self._cert_options: Optional[_KeyOrCertOptions] = None
        self._kbdint_password_auth = False

        self._agent_listener: Optional[SSHAgentListener] = None

    def _cleanup(self, exc: Optional[Exception]) -> None:
        """Clean up this server connection"""

        if self._agent_listener:
            self._agent_listener.close()
            self._agent_listener = None

        super()._cleanup(exc)

    def _connection_made(self) -> None:
        """Handle the opening of a new connection"""

        self.logger.info('Accepted SSH client connection')

        if self._options.proxy_command:
            proxy_command = ' '.join(shlex.quote(arg) for arg in
                                     self._options.proxy_command)
            self.logger.info('  Proxy command: %s', proxy_command)
        else:
            self.logger.info('  Local address: %s',
                             (self._local_addr, self._local_port))
            self.logger.info('  Peer address: %s',
                             (self._peer_addr, self._peer_port))

    async def reload_config(self) -> None:
        """Re-evaluate config with updated match options"""

        if self._rdns_lookup:
            self._peer_host, _ = await self._loop.getnameinfo(
                (self._peer_addr, self._peer_port), socket.NI_NUMERICSERV)

        options = await SSHServerConnectionOptions.construct(
            options=self._options, reload=True, accept_addr=self._local_addr,
            accept_port=self._local_port, username=self._username,
            client_host=self._peer_host, client_addr=self._peer_addr)

        self._options = options

        self._host_based_auth = options.host_based_auth
        self._public_key_auth = options.public_key_auth
        self._kbdint_auth = options.kbdint_auth
        self._password_auth = options.password_auth

        self._authorized_client_keys = options.authorized_client_keys
        self._allow_pty = options.allow_pty
        self._x11_forwarding = options.x11_forwarding
        self._agent_forwarding = options.agent_forwarding

        self._rekey_bytes = options.rekey_bytes
        self._rekey_seconds = options.rekey_seconds

        self._keepalive_count_max = options.keepalive_count_max
        self._keepalive_interval = options.keepalive_interval

    def choose_server_host_key(self,
                               peer_host_key_algs: Sequence[bytes]) -> bool:
        """Choose the server host key to use

           Given a list of host key algorithms supported by the client,
           select the first compatible server host key we have and return
           whether or not we were able to find a match.

        """

        for alg in peer_host_key_algs:
            keypair = self._server_host_keys.get(alg)
            if keypair:
                if alg != keypair.algorithm:
                    keypair.set_sig_algorithm(alg)

                self._server_host_key = keypair
                return True

        return False

    def get_server_host_key(self) -> Optional[SSHKeyPair]:
        """Return the chosen server host key

           This method returns a keypair object containing the
           chosen server host key and a corresponding public key
           or certificate.

        """

        return self._server_host_key

    def send_server_host_keys(self) -> None:
        """Send list of available server host keys"""

        if self._all_server_host_keys:
            self.logger.info('Sending server host keys')

            keys = [String(key) for key in self._all_server_host_keys.keys()]
            self._send_global_request(b'hostkeys-00@openssh.com', *keys)
        else:
            self.logger.info('Sending server host keys disabled')

    def gss_kex_auth_supported(self) -> bool:
        """Return whether GSS key exchange authentication is supported"""

        if self._gss_kex_auth:
            assert self._gss is not None
            return self._gss.complete
        else:
            return False

    def gss_mic_auth_supported(self) -> bool:
        """Return whether GSS MIC authentication is supported"""

        return self._gss_mic_auth

    async def validate_gss_principal(self, username: str, user_principal: str,
                                     host_principal: str) -> bool:
        """Validate the GSS principal name for the specified user

           Return whether the user principal acquired during GSS
           authentication is valid for the specified user.

        """

        result = self._owner.validate_gss_principal(username, user_principal,
                                                    host_principal)

        if inspect.isawaitable(result):
            result = await cast(Awaitable[bool], result)

        return cast(bool, result)

    def host_based_auth_supported(self) -> bool:
        """Return whether or not host based authentication is supported"""

        return (self._host_based_auth and
                (bool(self._known_client_hosts) or
                 self._owner.host_based_auth_supported()))

    async def validate_host_based_auth(self, username: str, key_data: bytes,
                                       client_host: str, client_username: str,
                                       msg: bytes, signature: bytes) -> bool:
        """Validate host based authentication for the specified host and user"""

        # Remove a trailing '.' from the client host if present
        if client_host[-1:] == '.':
            client_host = client_host[:-1]

        if self._trust_client_host:
            resolved_host = client_host
        else:
            peername = cast(SockAddr, self.get_extra_info('peername'))

            try:
                resolved_host, _ = await self._loop.getnameinfo(
                    peername, socket.NI_NUMERICSERV)
            except socket.gaierror:
                resolved_host = peername[0]

            if resolved_host != client_host:
                self.logger.info('Client host mismatch: received %s, '
                                 'resolved %s', client_host, resolved_host)

        if self._known_client_hosts:
            self._match_known_hosts(self._known_client_hosts, resolved_host,
                                    self._peer_addr, None)

        try:
            key = self._validate_host_key(resolved_host, self._peer_addr,
                                          self._peer_port, key_data)
        except ValueError as exc:
            self.logger.debug1('Invalid host key: %s', exc)
            return False

        if not key.verify(String(self._session_id) + msg, signature):
            self.logger.debug1('Invalid host-based auth signature')
            return False

        result = self._owner.validate_host_based_user(username, client_host,
                                                      client_username)

        if inspect.isawaitable(result):
            result = await cast(Awaitable[bool], result)

        return cast(bool, result)

    async def _validate_openssh_certificate(
            self, username: str, cert: SSHOpenSSHCertificate) -> \
                Optional[SSHKey]:
        """Validate an OpenSSH client certificate for the specified user"""

        options: Optional[_KeyOrCertOptions] = None

        if self._authorized_client_keys:
            options = self._authorized_client_keys.validate(
                cert.signing_key, self._peer_host,
                self._peer_addr, cert.principals, ca=True)

        if options is None:
            result = self._owner.validate_ca_key(username, cert.signing_key)

            if inspect.isawaitable(result):
                result = await cast(Awaitable[bool], result)

            if not result:
                return None

            options = {}

        self._key_options = options

        cert_user = None if self.get_key_option('principals') else username

        try:
            cert.validate(CERT_TYPE_USER, cert_user)
        except ValueError:
            return None

        allowed_addresses = cast(Sequence[IPNetwork],
                                 cert.options.get('source-address'))
        if allowed_addresses:
            ip = ip_address(self._peer_addr)
            if not any(ip in network for network in allowed_addresses):
                return None

        self._cert_options = cert.options

        cert.key.set_touch_required(
            not (self.get_key_option('no-touch-required', False) and
                 self.get_certificate_option('no-touch-required', False)))

        return cert.key

    async def _validate_x509_certificate_chain(
            self, username: str, cert: SSHX509CertificateChain) -> \
                Optional[SSHKey]:
        """Validate an X.509 client certificate for the specified user"""

        if not self._authorized_client_keys:
            return None

        options, trusted_cert = \
            self._authorized_client_keys.validate_x509(
                cert, self._peer_host, self._peer_addr)

        if options is None:
            return None

        self._key_options = options

        if self.get_key_option('principals'):
            username = ''

        assert self._x509_trusted_certs is not None
        trusted_certs = list(self._x509_trusted_certs)

        if trusted_cert:
            trusted_certs += [trusted_cert]

        try:
            cert.validate_chain(trusted_certs, self._x509_trusted_cert_paths,
                                set(), self._x509_purposes,
                                user_principal=username)
        except ValueError:
            return None

        return cert.key

    async def _validate_client_certificate(
            self, username: str, key_data: bytes) -> Optional[SSHKey]:
        """Validate a client certificate for the specified user"""

        try:
            cert = decode_ssh_certificate(key_data)
        except KeyImportError:
            return None

        if cert.is_x509_chain:
            return await self._validate_x509_certificate_chain(
                username, cast(SSHX509CertificateChain, cert))
        else:
            return await self._validate_openssh_certificate(
                username, cast(SSHOpenSSHCertificate, cert))

    async def _validate_client_public_key(self, username: str,
                                          key_data: bytes) -> Optional[SSHKey]:
        """Validate a client public key for the specified user"""

        try:
            key = decode_ssh_public_key(key_data)
        except KeyImportError:
            return None

        options: Optional[_KeyOrCertOptions] = None

        if self._authorized_client_keys:
            options = self._authorized_client_keys.validate(
                key, self._peer_host, self._peer_addr)

        if options is None:
            result = self._owner.validate_public_key(username, key)

            if inspect.isawaitable(result):
                result = await cast(Awaitable[bool], result)

            if not result:
                return None

            options = {}

        self._key_options = options

        key.set_touch_required(
            not self.get_key_option('no-touch-required', False))

        return key

    def public_key_auth_supported(self) -> bool:
        """Return whether or not public key authentication is supported"""

        return (self._public_key_auth and
                (bool(self._authorized_client_keys) or
                 self._owner.public_key_auth_supported()))

    async def validate_public_key(self, username: str, key_data: bytes,
                                  msg: bytes, signature: bytes) -> bool:
        """Validate the public key or certificate for the specified user

           This method validates that the public key or certificate provided
           is allowed for the specified user. If msg and signature are
           provided, the key is used to also validate the message signature.
           It returns `True` when the key is allowed and the signature (if
           present) is valid. Otherwise, it returns `False`.

        """

        key = ((await self._validate_client_certificate(username, key_data)) or
               (await self._validate_client_public_key(username, key_data)))

        if key is None:
            return False
        elif msg:
            return key.verify(String(self._session_id) + msg, signature)
        else:
            return True

    def password_auth_supported(self) -> bool:
        """Return whether or not password authentication is supported"""

        return self._password_auth and self._owner.password_auth_supported()

    async def validate_password(self, username: str, password: str) -> bool:
        """Return whether password is valid for this user"""

        result = self._owner.validate_password(username, password)

        if inspect.isawaitable(result):
            result = await cast(Awaitable[bool], result)

        return cast(bool, result)

    async def change_password(self, username: str, old_password: str,
                              new_password: str) -> bool:
        """Handle a password change request for a user"""

        result = self._owner.change_password(username, old_password,
                                             new_password)

        if inspect.isawaitable(result):
            result = await cast(Awaitable[bool], result)

        return cast(bool, result)

    def kbdint_auth_supported(self) -> bool:
        """Return whether or not keyboard-interactive authentication
           is supported"""

        result = self._kbdint_auth and self._owner.kbdint_auth_supported()

        if result is True:
            return True
        elif (result is NotImplemented and
              self._owner.password_auth_supported()):
            self._kbdint_password_auth = True
            return True
        else:
            return False

    async def get_kbdint_challenge(self, username: str, lang: str,
                                   submethods: str) -> KbdIntChallenge:
        """Return a keyboard-interactive auth challenge"""

        if self._kbdint_password_auth:
            challenge: KbdIntChallenge = ('', '', DEFAULT_LANG,
                                          (('Password:', False),))
        else:
            result = self._owner.get_kbdint_challenge(username, lang,
                                                      submethods)

            if inspect.isawaitable(result):
                challenge = await cast(Awaitable[KbdIntChallenge], result)
            else:
                challenge = cast(KbdIntChallenge, result)

        return challenge

    async def validate_kbdint_response(self, username: str,
                                       responses: KbdIntResponse) -> \
            KbdIntChallenge:
        """Return whether the keyboard-interactive response is valid
           for this user"""

        next_challenge: KbdIntChallenge

        if self._kbdint_password_auth:
            if len(responses) != 1:
                return False

            try:
                pw_result = self._owner.validate_password(
                    username, responses[0])

                if inspect.isawaitable(pw_result):
                    next_challenge = await cast(Awaitable[bool], pw_result)
                else:
                    next_challenge = cast(bool, pw_result)
            except PasswordChangeRequired:
                # Don't support password change requests for now in
                # keyboard-interactive auth
                next_challenge = False
        else:
            result = self._owner.validate_kbdint_response(username, responses)

            if inspect.isawaitable(result):
                next_challenge = await cast(Awaitable[KbdIntChallenge], result)
            else:
                next_challenge = cast(KbdIntChallenge, result)

        return next_challenge

    def _process_session_open(self, packet: SSHPacket) -> \
            Tuple[SSHServerChannel, SSHServerSession]:
        """Process an incoming session open request"""

        packet.check_end()

        chan: SSHServerChannel
        session: SSHServerSession

        if self._process_factory or self._session_factory or self._sftp_factory:
            chan = self.create_server_channel(self._encoding, self._errors,
                                              self._window, self._max_pktsize)

            if self._process_factory:
                session = SSHServerProcess(self._process_factory,
                                           self._sftp_factory,
                                           self._sftp_version,
                                           self._allow_scp)
            else:
                session = SSHServerStreamSession(self._session_factory,
                                                 self._sftp_factory,
                                                 self._sftp_version,
                                                 self._allow_scp)
        else:
            result = self._owner.session_requested()

            if not result:
                raise ChannelOpenError(OPEN_CONNECT_FAILED, 'Session refused')

            if isinstance(result, tuple):
                chan, result = result
            else:
                chan = self.create_server_channel(self._encoding, self._errors,
                                                  self._window,
                                                  self._max_pktsize)

            if callable(result):
                session = SSHServerStreamSession(result)
            else:
                session = cast(SSHServerSession, result)

        return chan, session

    def _process_direct_tcpip_open(self, packet: SSHPacket) -> \
            Tuple[SSHTCPChannel[bytes], SSHTCPSession[bytes]]:
        """Process an incoming direct TCP/IP open request"""

        dest_host_bytes = packet.get_string()
        dest_port = packet.get_uint32()
        orig_host_bytes = packet.get_string()
        orig_port = packet.get_uint32()
        packet.check_end()

        try:
            dest_host = dest_host_bytes.decode('utf-8')
            orig_host = orig_host_bytes.decode('utf-8')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid direct TCP/IP channel '
                                'open request') from None

        if not self.check_key_permission('port-forwarding') or \
           not self.check_certificate_permission('port-forwarding'):
            raise ChannelOpenError(OPEN_ADMINISTRATIVELY_PROHIBITED,
                                   'Port forwarding not permitted')

        permitted_opens = cast(Set[Tuple[str, int]],
                               self.get_key_option('permitopen'))

        if permitted_opens and \
           (dest_host, dest_port) not in permitted_opens and \
           (dest_host, None) not in permitted_opens:
            raise ChannelOpenError(OPEN_ADMINISTRATIVELY_PROHIBITED,
                                   'Port forwarding not permitted to '
                                   f'{dest_host} port {dest_port}')

        result = self._owner.connection_requested(dest_host, dest_port,
                                                  orig_host, orig_port)

        if not result:
            raise ChannelOpenError(OPEN_CONNECT_FAILED, 'Connection refused')

        if result is True:
            result = cast(SSHTCPSession[bytes],
                          self.forward_connection(dest_host, dest_port))

        if isinstance(result, tuple):
            chan, result = result
        else:
            chan = self.create_tcp_channel()

        session: SSHTCPSession[bytes]

        if callable(result):
            session = SSHTCPStreamSession[bytes](result)
        else:
            session = cast(SSHTCPSession[bytes], result)

        self.logger.info('Accepted direct TCP connection request to %s',
                         (dest_host, dest_port))
        self.logger.info('  Client address: %s', (orig_host, orig_port))

        chan.set_inbound_peer_names(dest_host, dest_port, orig_host, orig_port)

        return chan, session

    def _process_tcpip_forward_global_request(self, packet: SSHPacket) -> None:
        """Process an incoming TCP/IP port forwarding request"""

        listen_host_bytes = packet.get_string()
        listen_port = packet.get_uint32()
        packet.check_end()

        try:
            listen_host = listen_host_bytes.decode('utf-8').lower()
        except UnicodeDecodeError:
            raise ProtocolError('Invalid TCP/IP forward request') from None

        if not self.check_key_permission('port-forwarding') or \
           not self.check_certificate_permission('port-forwarding'):
            self.logger.info('Request for TCP listener on %s denied: port '
                             'forwarding not permitted',
                             (listen_host, listen_port))

            self._report_global_response(False)
            return

        self.create_task(self._finish_port_forward(listen_host, listen_port))

    async def _finish_port_forward(self, listen_host: str,
                                   listen_port: int) -> None:
        """Finish processing a TCP/IP port forwarding request"""

        listener = self._owner.server_requested(listen_host, listen_port)

        try:
            if inspect.isawaitable(listener):
                listener = await cast(Awaitable[_ListenerArg], listener)

            if listener is True:
                listener = await self.forward_local_port(
                    listen_host, listen_port, listen_host, listen_port)
            elif callable(listener):
                listener = await self.forward_local_port(
                    listen_host, listen_port,
                    listen_host, listen_port, listener)
        except OSError:
            self.logger.debug1('Failed to create TCP listener')
            self._report_global_response(False)
            return

        if not listener:
            self.logger.info('Request for TCP listener on %s denied by '
                             'application', (listen_host, listen_port))

            self._report_global_response(False)
            return

        listener: SSHListener
        result: Union[bool, bytes]

        if listen_port == 0:
            listen_port = listener.get_port()
            result = UInt32(listen_port)
        else:
            result = True

        self.logger.info('Created TCP listener on %s',
                         (listen_host, listen_port))

        self._local_listeners[listen_host, listen_port] = listener
        self._report_global_response(result)

    def _process_cancel_tcpip_forward_global_request(
            self, packet: SSHPacket) -> None:
        """Process a request to cancel TCP/IP port forwarding"""

        listen_host_bytes = packet.get_string()
        listen_port = packet.get_uint32()
        packet.check_end()

        try:
            listen_host = listen_host_bytes.decode('utf-8').lower()
        except UnicodeDecodeError:
            raise ProtocolError('Invalid TCP/IP cancel '
                                'forward request') from None

        try:
            listener = self._local_listeners.pop((listen_host, listen_port))
        except KeyError:
            raise ProtocolError('TCP/IP listener not found') from None

        self.logger.info('Closed TCP listener on %s',
                         (listen_host, listen_port))

        listener.close()

        self._report_global_response(True)

    def _process_direct_streamlocal_at_openssh_dot_com_open(
            self, packet: SSHPacket) -> \
                Tuple[SSHUNIXChannel[bytes], SSHUNIXSession[bytes]]:
        """Process an incoming direct UNIX domain socket open request"""

        dest_path_bytes = packet.get_string()

        # OpenSSH appears to have a bug which sends this extra data
        _ = packet.get_string()                         # originator
        _ = packet.get_uint32()                         # originator_port

        packet.check_end()

        try:
            dest_path = dest_path_bytes.decode('utf-8')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid direct UNIX domain channel '
                                'open request') from None

        if not self.check_key_permission('port-forwarding') or \
           not self.check_certificate_permission('port-forwarding'):
            raise ChannelOpenError(OPEN_ADMINISTRATIVELY_PROHIBITED,
                                   'Port forwarding not permitted')

        result = self._owner.unix_connection_requested(dest_path)

        if not result:
            raise ChannelOpenError(OPEN_CONNECT_FAILED, 'Connection refused')

        if result is True:
            result = cast(SSHUNIXSession[bytes],
                          self.forward_unix_connection(dest_path))

        if isinstance(result, tuple):
            chan, result = result
        else:
            chan = self.create_unix_channel()

        session: SSHUNIXSession[bytes]

        if callable(result):
            session = SSHUNIXStreamSession[bytes](result)
        else:
            session = cast(SSHUNIXSession[bytes], result)

        self.logger.info('Accepted direct UNIX connection on %s', dest_path)

        chan.set_inbound_peer_names(dest_path)

        return chan, session

    def _process_streamlocal_forward_at_openssh_dot_com_global_request(
            self, packet: SSHPacket) -> None:
        """Process an incoming UNIX domain socket forwarding request"""

        listen_path_bytes = packet.get_string()
        packet.check_end()

        try:
            listen_path = listen_path_bytes.decode('utf-8')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid UNIX domain socket '
                                'forward request') from None

        if not self.check_key_permission('port-forwarding') or \
           not self.check_certificate_permission('port-forwarding'):
            self.logger.info('Request for UNIX listener on %s denied: port '
                             'forwarding not permitted', listen_path)

            self._report_global_response(False)
            return

        self.create_task(self._finish_path_forward(listen_path))

    async def _finish_path_forward(self, listen_path: str) -> None:
        """Finish processing a UNIX domain socket forwarding request"""

        listener = self._owner.unix_server_requested(listen_path)

        try:
            if inspect.isawaitable(listener):
                listener = await cast(Awaitable[_ListenerArg], listener)

            if listener is True:
                listener = await self.forward_local_path(listen_path,
                                                         listen_path)
        except OSError:
            self.logger.debug1('Failed to create UNIX listener')
            self._report_global_response(False)
            return

        if not listener:
            self.logger.info('Request for UNIX listener on %s denied by '
                             'application', listen_path)

            self._report_global_response(False)
            return

        self.logger.info('Created UNIX listener on %s', listen_path)

        self._local_listeners[listen_path] = cast(SSHListener, listener)
        self._report_global_response(True)

    def _process_cancel_streamlocal_forward_at_openssh_dot_com_global_request(
            self, packet: SSHPacket) -> None:
        """Process a request to cancel UNIX domain socket forwarding"""

        listen_path_bytes = packet.get_string()
        packet.check_end()

        try:
            listen_path = listen_path_bytes.decode('utf-8')
        except UnicodeDecodeError:
            raise ProtocolError('Invalid UNIX domain cancel '
                                'forward request') from None

        try:
            listener = self._local_listeners.pop(listen_path)
        except KeyError:
            raise ProtocolError('UNIX domain listener not found') from None

        self.logger.info('Closed UNIX listener on %s', listen_path)

        listener.close()

        self._report_global_response(True)

    def _process_tun_at_openssh_dot_com_open(
            self, packet: SSHPacket) -> \
                Tuple[SSHTunTapChannel, SSHTunTapSession]:
        """Process an incoming TUN/TAP open request"""

        mode = packet.get_uint32()
        unit: Optional[int] = packet.get_uint32()
        packet.check_end()

        if unit == SSH_TUN_UNIT_ANY:
            unit = None

        if mode == SSH_TUN_MODE_POINTTOPOINT:
            result = self._owner.tun_requested(unit)
        elif mode == SSH_TUN_MODE_ETHERNET:
            result = self._owner.tap_requested(unit)
        else:
            result = False

        if not result:
            raise ChannelOpenError(OPEN_CONNECT_FAILED, 'Connection refused')

        if result is True:
            result = cast(SSHTunTapSession, self.forward_tuntap(mode, unit))

        if isinstance(result, tuple):
            chan, result = result
        else:
            chan = self.create_tuntap_channel()

        session: SSHTunTapSession

        if callable(result):
            session = SSHTunTapStreamSession(result)
        else:
            session = cast(SSHTunTapSession, result)

        self.logger.info('Accepted layer %d tunnel request to unit %s',
                         3 if mode == SSH_TUN_MODE_POINTTOPOINT else 2,
                         'any' if unit == SSH_TUN_UNIT_ANY else str(unit))

        chan.set_mode(mode)

        return chan, session

    def _process_hostkeys_prove_00_at_openssh_dot_com_global_request(
            self, packet: SSHPacket) -> None:
        """Prove the server has private keys for all requested host keys"""

        prefix = String('hostkeys-prove-00@openssh.com') + \
                 String(self._session_id)

        signatures = []

        while packet:
            try:
                key_data = packet.get_string()
                key = self._all_server_host_keys[key_data]
                signatures.append(String(key.sign(prefix + String(key_data))))
            except (KeyError, KeyImportError):
                self._report_global_response(False)
                return

        self._report_global_response(b''.join(signatures))

    async def attach_x11_listener(self, chan: SSHServerChannel[AnyStr],
                                  auth_proto: bytes, auth_data: bytes,
                                  screen: int) -> Optional[str]:
        """Attach a channel to a remote X11 display"""

        if (not self._x11_forwarding or
                not self.check_key_permission('X11-forwarding') or
                not self.check_certificate_permission('X11-forwarding')):
            self.logger.info('X11 forwarding request denied: X11 '
                             'forwarding not permitted')

            return None

        if not self._x11_listener:
            self._x11_listener = await create_x11_server_listener(
                self, self._loop, self._x11_auth_path, auth_proto, auth_data)

        if self._x11_listener:
            return self._x11_listener.attach(chan, screen)
        else:
            return None

    def detach_x11_listener(self, chan: SSHChannel[AnyStr]) -> None:
        """Detach a session from a remote X11 listener"""

        if self._x11_listener:
            if self._x11_listener.detach(chan):
                self._x11_listener = None

    async def create_agent_listener(self) -> bool:
        """Create a listener for forwarding ssh-agent connections"""

        if (not self._agent_forwarding or
                not self.check_key_permission('agent-forwarding') or
                not self.check_certificate_permission('agent-forwarding')):
            self.logger.info('Agent forwarding request denied: Agent '
                             'forwarding not permitted')

            return False

        if self._agent_listener:
            return True

        try:
            tempdir = tempfile.TemporaryDirectory(prefix='asyncssh-')
            path = str(Path(tempdir.name, 'agent'))

            unix_listener = await create_unix_forward_listener(
                self, self._loop, self.create_agent_connection, path)

            self._agent_listener = SSHAgentListener(tempdir, path,
                                                    unix_listener)
            return True
        except OSError:
            return False

    def get_agent_path(self) -> Optional[str]:
        """Return the path of the ssh-agent listener, if one exists"""

        if self._agent_listener:
            return self._agent_listener.get_path()
        else:
            return None

    def send_auth_banner(self, msg: str, lang: str = DEFAULT_LANG) -> None:
        """Send an authentication banner to the client

           This method can be called to send an authentication banner to
           the client, displaying information while authentication is
           in progress. It is an error to call this method after the
           authentication is complete.

           :param msg:
               The message to display
           :param lang:
               The language the message is in
           :type msg: `str`
           :type lang: `str`

           :raises: :exc:`OSError` if authentication is already completed

        """

        if self._auth_complete:
            raise OSError('Authentication already completed')

        self.logger.debug1('Sending authentication banner')

        self.send_packet(MSG_USERAUTH_BANNER, String(msg), String(lang))

    def set_authorized_keys(self, authorized_keys: _AuthKeysArg) -> None:
        """Set the keys trusted for client public key authentication

           This method can be called to set the trusted user and
           CA keys for client public key authentication. It should
           generally be called from the :meth:`begin_auth
           <SSHServer.begin_auth>` method of :class:`SSHServer` to
           set the appropriate keys for the user attempting to
           authenticate.

           :param authorized_keys:
               The keys to trust for client public key authentication
           :type authorized_keys: *see* :ref:`SpecifyingAuthorizedKeys`

        """

        if isinstance(authorized_keys, (str, list)):
            authorized_keys = read_authorized_keys(authorized_keys)

        self._authorized_client_keys = authorized_keys

    def get_key_option(self, option: str, default: object = None) -> object:
        """Return option from authorized_keys

           If a client key or certificate was presented during authentication,
           this method returns the value of the requested option in the
           corresponding authorized_keys entry if it was set. Otherwise, it
           returns the default value provided.

           The following standard options are supported:

               | command (string)
               | environment (dictionary of name/value pairs)
               | from (list of host patterns)
               | no-touch-required (boolean)
               | permitopen (list of host/port tuples)
               | principals (list of usernames)

           Non-standard options are also supported and will return the
           value `True` if the option is present without a value or
           return a list of strings containing the values associated
           with each occurrence of that option name. If the option is
           not present, the specified default value is returned.

           :param option:
               The name of the option to look up.
           :param default:
               The default value to return if the option is not present.
           :type option: `str`

           :returns: The value of the option in authorized_keys, if set

        """

        return self._key_options.get(option, default)

    def check_key_permission(self, permission: str) -> bool:
        """Check permissions in authorized_keys

           If a client key or certificate was presented during
           authentication, this method returns whether the specified
           permission is allowed by the corresponding authorized_keys
           entry. By default, all permissions are granted, but they
           can be revoked by specifying an option starting with
           'no-' without a value.

           The following standard options are supported:

               | X11-forwarding
               | agent-forwarding
               | port-forwarding
               | pty
               | user-rc

           AsyncSSH internally enforces X11-forwarding, agent-forwarding,
           port-forwarding and pty permissions but ignores user-rc since
           it does not implement that feature.

           Non-standard permissions can also be checked, as long as the
           option follows the convention of starting with 'no-'.

           :param permission:
               The name of the permission to check (without the 'no-').
           :type permission: `str`

           :returns: A `bool` indicating if the permission is granted.

        """

        return not self._key_options.get('no-' + permission, False)

    def get_certificate_option(self, option: str,
                               default: object = None) -> object:
        """Return option from user certificate

           If a user certificate was presented during authentication,
           this method returns the value of the requested option in
           the certificate if it was set. Otherwise, it returns the
           default value provided.

           The following options are supported:

               | force-command (string)
               | no-touch-required (boolean)
               | source-address (list of CIDR-style IP network addresses)

           :param option:
               The name of the option to look up.
           :param default:
               The default value to return if the option is not present.
           :type option: `str`

           :returns: The value of the option in the user certificate, if set

        """

        if self._cert_options is not None:
            return self._cert_options.get(option, default)
        else:
            return default

    def check_certificate_permission(self, permission: str) -> bool:
        """Check permissions in user certificate

           If a user certificate was presented during authentication,
           this method returns whether the specified permission was
           granted in the certificate. Otherwise, it acts as if all
           permissions are granted and returns `True`.

           The following permissions are supported:

               | X11-forwarding
               | agent-forwarding
               | port-forwarding
               | pty
               | user-rc

           AsyncSSH internally enforces agent-forwarding, port-forwarding
           and pty permissions but ignores the other values since it does
           not implement those features.

           :param permission:
               The name of the permission to check (without the 'permit-').
           :type permission: `str`

           :returns: A `bool` indicating if the permission is granted.

        """

        if self._cert_options is not None:
            return cast(bool, self._cert_options.get('permit-' + permission,
                                                     False))
        else:
            return True

    def create_server_channel(self, encoding: Optional[str] = '',
                              errors: str = '', window: int = 0,
                              max_pktsize: int = 0) -> SSHServerChannel:
        """Create an SSH server channel for a new SSH session

           This method can be called by :meth:`session_requested()
           <SSHServer.session_requested>` to create an
           :class:`SSHServerChannel` with the desired encoding, Unicode
           error handling strategy, window, and max packet size for a
           newly created SSH server session.

           :param encoding: (optional)
               The Unicode encoding to use for data exchanged on the
               session, defaulting to UTF-8 (ISO 10646) format. If `None`
               is passed in, the application can send and receive raw
               bytes.
           :param errors: (optional)
               The error handling strategy to apply on encode/decode errors
           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type encoding: `str` or `None`
           :type errors: `str`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: :class:`SSHServerChannel`

        """

        return SSHServerChannel(self, self._loop, self._allow_pty,
                                self._line_editor, self._line_echo,
                                self._line_history, self._max_line_length,
                                self._encoding if encoding == '' else encoding,
                                self._errors if errors == '' else errors,
                                window or self._window,
                                max_pktsize or self._max_pktsize)

    async def create_connection(
            self, session_factory: SSHTCPSessionFactory[AnyStr],
            remote_host: str, remote_port: int, orig_host: str = '',
            orig_port: int = 0, *, encoding: Optional[str] = None,
            errors: str = 'strict', window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
                Tuple[SSHTCPChannel[AnyStr], SSHTCPSession[AnyStr]]:
        """Create an SSH TCP forwarded connection

           This method is a coroutine which can be called to notify the
           client about a new inbound TCP connection arriving on the
           specified remote host and port. If the connection is successfully
           opened, a new SSH channel will be opened with data being handled
           by a :class:`SSHTCPSession` object created by `session_factory`.

           Optional arguments include the host and port of the original
           client opening the connection when performing TCP port forwarding.

           By default, this class expects data to be sent and received as
           raw bytes. However, an optional encoding argument can be
           passed in to select the encoding to use, allowing the
           application to send and receive string data. When encoding is
           set, an optional errors argument can be passed in to select
           what Unicode error handling strategy to use.

           Other optional arguments include the SSH receive window size and
           max packet size which default to 2 MB and 32 KB, respectively.

           :param session_factory:
               A `callable` which returns an :class:`SSHTCPSession` object
               that will be created to handle activity on this session
           :param remote_host:
               The hostname or address the connection was received on
           :param remote_port:
               The port number the connection was received on
           :param orig_host: (optional)
               The hostname or address of the client requesting the connection
           :param orig_port: (optional)
               The port number of the client requesting the connection
           :param encoding: (optional)
               The Unicode encoding to use for data exchanged on the connection
           :param errors: (optional)
               The error handling strategy to apply on encode/decode errors
           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type session_factory: `callable`
           :type remote_host: `str`
           :type remote_port: `int`
           :type orig_host: `str`
           :type orig_port: `int`
           :type encoding: `str` or `None`
           :type errors: `str`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: an :class:`SSHTCPChannel` and :class:`SSHTCPSession`

        """

        self.logger.info('Opening forwarded TCP connection to %s',
                         (remote_host, remote_port))
        self.logger.info('  Client address: %s', (orig_host, orig_port))

        chan = self.create_tcp_channel(encoding, errors, window, max_pktsize)

        session = await chan.accept(session_factory, remote_host,
                                    remote_port, orig_host, orig_port)

        return chan, session

    async def open_connection(self, *args: object, **kwargs: object) -> \
            Tuple[SSHReader, SSHWriter]:
        """Open an SSH TCP forwarded connection

           This method is a coroutine wrapper around :meth:`create_connection`
           designed to provide a "high-level" stream interface for creating
           an SSH TCP forwarded connection. Instead of taking a
           `session_factory` argument for constructing an object which will
           handle activity on the session via callbacks, it returns
           :class:`SSHReader` and :class:`SSHWriter` objects which can be
           used to perform I/O on the connection.

           With the exception of `session_factory`, all of the arguments
           to :meth:`create_connection` are supported and have the same
           meaning here.

           :returns: an :class:`SSHReader` and :class:`SSHWriter`

        """

        chan, session = await self.create_connection(
            SSHTCPStreamSession, *args, **kwargs) # type: ignore

        session: SSHTCPStreamSession

        return SSHReader(session, chan), SSHWriter(session, chan)

    async def create_unix_connection(
            self, session_factory: SSHUNIXSessionFactory[AnyStr],
            remote_path: str, *, encoding: Optional[str] = None,
            errors: str = 'strict', window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
                Tuple[SSHUNIXChannel[AnyStr], SSHUNIXSession[AnyStr]]:
        """Create an SSH UNIX domain socket forwarded connection

           This method is a coroutine which can be called to notify the
           client about a new inbound UNIX domain socket connection arriving
           on the specified remote path. If the connection is successfully
           opened, a new SSH channel will be opened with data being handled
           by a :class:`SSHUNIXSession` object created by `session_factory`.

           By default, this class expects data to be sent and received as
           raw bytes. However, an optional encoding argument can be
           passed in to select the encoding to use, allowing the
           application to send and receive string data. When encoding is
           set, an optional errors argument can be passed in to select
           what Unicode error handling strategy to use.

           Other optional arguments include the SSH receive window size and
           max packet size which default to 2 MB and 32 KB, respectively.

           :param session_factory:
               A `callable` which returns an :class:`SSHUNIXSession` object
               that will be created to handle activity on this session
           :param remote_path:
               The path the connection was received on
           :param encoding: (optional)
               The Unicode encoding to use for data exchanged on the connection
           :param errors: (optional)
               The error handling strategy to apply on encode/decode errors
           :param window: (optional)
               The receive window size for this session
           :param max_pktsize: (optional)
               The maximum packet size for this session
           :type session_factory: `callable`
           :type remote_path: `str`
           :type encoding: `str` or `None`
           :type errors: `str`
           :type window: `int`
           :type max_pktsize: `int`

           :returns: an :class:`SSHTCPChannel` and :class:`SSHUNIXSession`

        """

        self.logger.info('Opening forwarded UNIX connection to %s', remote_path)

        chan = self.create_unix_channel(encoding, errors, window, max_pktsize)

        session = await chan.accept(session_factory, remote_path)

        return chan, session

    async def open_unix_connection(self, *args: object, **kwargs: object) -> \
            Tuple[SSHReader, SSHWriter]:
        """Open an SSH UNIX domain socket forwarded connection

           This method is a coroutine wrapper around
           :meth:`create_unix_connection` designed to provide a "high-level"
           stream interface for creating an SSH UNIX domain socket forwarded
           connection. Instead of taking a `session_factory` argument for
           constructing an object which will handle activity on the session
           via callbacks, it returns :class:`SSHReader` and :class:`SSHWriter`
           objects which can be used to perform I/O on the connection.

           With the exception of `session_factory`, all of the arguments
           to :meth:`create_unix_connection` are supported and have the same
           meaning here.

           :returns: an :class:`SSHReader` and :class:`SSHWriter`

        """

        chan, session = \
            await self.create_unix_connection(
                SSHUNIXStreamSession, *args, **kwargs) # type: ignore

        session: SSHUNIXStreamSession

        return SSHReader(session, chan), SSHWriter(session, chan)

    async def create_x11_connection(
            self, session_factory: SSHTCPSessionFactory[bytes],
            orig_host: str = '', orig_port: int = 0, *,
            window: int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
                Tuple[SSHX11Channel, SSHTCPSession[bytes]]:
        """Create an SSH X11 forwarded connection"""

        self.logger.info('Opening forwarded X11 connection')

        chan = self.create_x11_channel(window, max_pktsize)

        session = await chan.open(session_factory, orig_host, orig_port)

        return chan, session

    async def create_agent_connection(
            self, session_factory: SSHUNIXSessionFactory[bytes], *,
            window:int = _DEFAULT_WINDOW,
            max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> \
                Tuple[SSHAgentChannel, SSHUNIXSession[bytes]]:
        """Create a forwarded ssh-agent connection back to the client"""

        if not self._agent_listener:
            raise ChannelOpenError(OPEN_ADMINISTRATIVELY_PROHIBITED,
                                   'Agent forwarding not permitted')

        self.logger.info('Opening forwarded agent connection')

        chan = self.create_agent_channel(window, max_pktsize)

        session = await chan.open(session_factory)

        return chan, session

    async def open_agent_connection(self) -> \
            Tuple[SSHReader[bytes], SSHWriter[bytes]]:
        """Open a forwarded ssh-agent connection back to the client"""

        chan, session = \
            await self.create_agent_connection(SSHUNIXStreamSession)

        session: SSHUNIXStreamSession[bytes]

        return SSHReader[bytes](session, chan), SSHWriter[bytes](session, chan)


class SSHConnectionOptions(Options, Generic[_Options]):
    """SSH connection options"""

    config: SSHConfig
    waiter: Optional[asyncio.Future]
    protocol_factory: _ProtocolFactory
    version: bytes
    host: str
    port: int
    tunnel: object
    proxy_command: Optional[Sequence[str]]
    family: int
    local_addr: HostPort
    tcp_keepalive: bool
    canonicalize_hostname: Union[bool, str]
    canonical_domains: Sequence[str]
    canonicalize_fallback_local: bool
    canonicalize_max_dots: int
    canonicalize_permitted_cnames: Sequence[Tuple[str, str]]
    kex_algs: Sequence[bytes]
    encryption_algs: Sequence[bytes]
    mac_algs: Sequence[bytes]
    compression_algs: Sequence[bytes]
    signature_algs: Sequence[bytes]
    host_based_auth: bool
    public_key_auth: bool
    kbdint_auth: bool
    password_auth: bool
    x509_trusted_certs: Optional[Sequence[SSHX509Certificate]]
    x509_trusted_cert_paths: Sequence[FilePath]
    x509_purposes: Union[None, str, Sequence[str]]
    rekey_bytes: int
    rekey_seconds: float
    connect_timeout: Optional[float]
    login_timeout: float
    keepalive_internal: float
    keepalive_count_max: int

    def __init__(self, options: Optional[_Options] = None, **kwargs: object):
        last_config = options.config if options else None
        super().__init__(options=options, last_config=last_config, **kwargs)

    @classmethod
    async def construct(cls, options: Optional[_Options] = None,
                        **kwargs: object) -> _Options:
        """Construct a new options object from within an async task"""

        loop = asyncio.get_event_loop()

        return cast(_Options, await loop.run_in_executor(
            None, functools.partial(cls, options, loop=loop, **kwargs)))

    # pylint: disable=arguments-differ
    def prepare(self, config: SSHConfig, # type: ignore
                protocol_factory: _ProtocolFactory, version: _VersionArg,
                host: str, port: DefTuple[int], tunnel: object,
                passphrase: Optional[BytesOrStr],
                proxy_command: DefTuple[_ProxyCommand], family: DefTuple[int],
                local_addr: DefTuple[HostPort], tcp_keepalive: DefTuple[bool],
                canonicalize_hostname: DefTuple[Union[bool, str]],
                canonical_domains: DefTuple[Sequence[str]],
                canonicalize_fallback_local: DefTuple[bool],
                canonicalize_max_dots: DefTuple[int],
                canonicalize_permitted_cnames: _CNAMEArg,
                kex_algs: _AlgsArg, encryption_algs: _AlgsArg,
                mac_algs: _AlgsArg, compression_algs: _AlgsArg,
                signature_algs: _AlgsArg, host_based_auth: _AuthArg,
                public_key_auth: _AuthArg, kbdint_auth: _AuthArg,
                password_auth: _AuthArg, x509_trusted_certs: CertListArg,
                x509_trusted_cert_paths: Sequence[FilePath],
                x509_purposes: X509CertPurposes,
                rekey_bytes: DefTuple[Union[int, str]],
                rekey_seconds: DefTuple[Union[float, str]],
                connect_timeout: Optional[Union[float, str]],
                login_timeout: Union[float, str],
                keepalive_interval: Union[float, str],
                keepalive_count_max: int) -> None:
        """Prepare common connection configuration options"""

        def _split_cname_patterns(
                patterns: Union[str, Tuple[str, str]]) -> Tuple[str, str]:
            """Split CNAME patterns"""

            if isinstance(patterns, str):
                domains = patterns.split(':')

                if len(domains) == 2:
                    patterns = cast(Tuple[str, str], tuple(domains))
                else:
                    raise ValueError('CNAME rules must contain two patterns')

            return patterns

        self.config = config
        self.protocol_factory = protocol_factory
        self.version = _validate_version(version)

        self.host = cast(str, config.get('Hostname', host))
        self.port = cast(int, port if port != () else
            config.get('Port', DEFAULT_PORT))

        self.tunnel = tunnel if tunnel != () else config.get('ProxyJump')
        self.passphrase = passphrase

        if proxy_command == ():
            proxy_command = cast(Optional[str], config.get('ProxyCommand'))

        if isinstance(proxy_command, str):
            proxy_command = split_args(proxy_command)

        self.proxy_command = proxy_command

        self.family = cast(int, family if family != () else
            config.get('AddressFamily', socket.AF_UNSPEC))

        bind_addr = config.get('BindAddress')

        self.local_addr = cast(HostPort, local_addr if local_addr != ()
            else (bind_addr, 0) if bind_addr else None)

        self.tcp_keepalive = cast(bool, tcp_keepalive if tcp_keepalive != ()
            else config.get('TCPKeepAlive', True))

        self.canonicalize_hostname = \
            cast(Union[bool, str], canonicalize_hostname
                 if canonicalize_hostname != ()
                 else config.get('CanonicalizeHostname', False))

        self.canonical_domains = \
            cast(Sequence[str], canonical_domains if canonical_domains != ()
                 else config.get('CanonicalDomains', ()))

        self.canonicalize_fallback_local = \
            cast(bool, canonicalize_fallback_local \
                 if canonicalize_fallback_local != ()
                 else config.get('CanonicalizeFallbackLocal', True))

        self.canonicalize_max_dots = \
            cast(int, canonicalize_max_dots if canonicalize_max_dots != ()
                 else config.get('CanonicalizeMaxDots', 1))

        permitted_cnames = \
            cast(Sequence[str], canonicalize_permitted_cnames
                 if canonicalize_permitted_cnames != ()
                 else config.get('CanonicalizePermittedCNAMEs', ()))

        self.canonicalize_permitted_cnames = \
            [_split_cname_patterns(patterns) for patterns in permitted_cnames]

        self.kex_algs, self.encryption_algs, self.mac_algs, \
        self.compression_algs, self.signature_algs = \
            _validate_algs(config, kex_algs, encryption_algs, mac_algs,
                           compression_algs, signature_algs,
                           x509_trusted_certs is not None)

        self.host_based_auth = \
            cast(bool, host_based_auth if host_based_auth != () else
                config.get('HostbasedAuthentication', True))

        self.public_key_auth = \
            cast(bool, public_key_auth if public_key_auth != () else
                config.get('PubkeyAuthentication', True))

        self.kbdint_auth = \
            cast(bool, kbdint_auth if kbdint_auth != () else
                config.get('KbdInteractiveAuthentication',
                    config.get('ChallengeResponseAuthentication', True)))

        self.password_auth = \
            cast(bool, password_auth if password_auth != () else
                config.get('PasswordAuthentication', True))

        if x509_trusted_certs is not None:
            certs = load_certificates(x509_trusted_certs)

            for cert in certs:
                if not cert.is_x509:
                    raise ValueError('OpenSSH certificates not allowed '
                                    'in X.509 trusted certs')

            x509_trusted_certs = cast(Sequence[SSHX509Certificate], certs)

        if x509_trusted_cert_paths:
            for path in x509_trusted_cert_paths:
                if not Path(path).is_dir():
                    raise ValueError('X.509 trusted certificate path not '
                                     f'a directory: {path}')

        self.x509_trusted_certs = x509_trusted_certs
        self.x509_trusted_cert_paths = x509_trusted_cert_paths
        self.x509_purposes = x509_purposes

        config_rekey_bytes, config_rekey_seconds = \
            cast(Tuple[DefTuple[int], DefTuple[int]],
                 config.get('RekeyLimit', ((), ())))

        if rekey_bytes == ():
            rekey_bytes = config_rekey_bytes

        if rekey_bytes == ():
            rekey_bytes = _DEFAULT_REKEY_BYTES
        elif isinstance(rekey_bytes, str):
            rekey_bytes = parse_byte_count(rekey_bytes)

        if cast(int, rekey_bytes) <= 0:
            raise ValueError('Rekey bytes cannot be negative or zero')

        if rekey_seconds == ():
            rekey_seconds = config_rekey_seconds

        if rekey_seconds == ():
            rekey_seconds = _DEFAULT_REKEY_SECONDS
        elif isinstance(rekey_seconds, str):
            rekey_seconds = parse_time_interval(rekey_seconds)

        if rekey_seconds and cast(float, rekey_seconds) <= 0:
            raise ValueError('Rekey seconds cannot be negative or zero')

        if isinstance(connect_timeout, str):
            connect_timeout = parse_time_interval(connect_timeout)

        if connect_timeout and connect_timeout < 0:
            raise ValueError('Connect timeout cannot be negative')

        if isinstance(login_timeout, str):
            login_timeout = parse_time_interval(login_timeout)

        if login_timeout and login_timeout < 0:
            raise ValueError('Login timeout cannot be negative')

        if isinstance(keepalive_interval, str):
            keepalive_interval = parse_time_interval(keepalive_interval)

        if keepalive_interval and keepalive_interval < 0:
            raise ValueError('Keepalive interval cannot be negative')

        if keepalive_count_max <= 0:
            raise ValueError('Keepalive count max cannot be negative or zero')

        self.rekey_bytes = cast(int, rekey_bytes)
        self.rekey_seconds = cast(float, rekey_seconds)
        self.connect_timeout = connect_timeout or None
        self.login_timeout = login_timeout
        self.keepalive_interval = keepalive_interval
        self.keepalive_count_max = keepalive_count_max


class SSHClientConnectionOptions(SSHConnectionOptions):
    """SSH client connection options

       The following options are available to control the establishment
       of SSH client connections:

       :param client_factory: (optional)
           A `callable` which returns an :class:`SSHClient` object that will
           be created for each new connection.
       :param proxy_command: (optional)
           A string or list of strings specifying a command and arguments
           to run to make a connection to the SSH server. Data will be
           forwarded to this process over stdin/stdout instead of opening a
           TCP connection. If specified as a string, standard shell quoting
           will be applied when splitting the command and its arguments.
       :param known_hosts: (optional)
           The list of keys which will be used to validate the server host
           key presented during the SSH handshake. If this is not specified,
           the keys will be looked up in the file :file:`.ssh/known_hosts`.
           If this is explicitly set to `None`, server host key validation
           will be disabled.
       :param host_key_alias: (optional)
           An alias to use instead of the real host name when looking up a host
           key in known_hosts and when validating host certificates.
       :param server_host_key_algs: (optional)
           A list of server host key algorithms to use instead of the
           default of those present in known_hosts when performing the SSH
           handshake, taken from :ref:`server host key algorithms
           <PublicKeyAlgs>`. This is useful when using the
           validate_host_public_key callback to validate server host keys,
           since AsyncSSH can not determine which server host key algorithms
           are preferred. This argument can also be set to 'default' to
           specify that the client should always send its default list of
           supported algorithms to avoid leaking information about what
           algorithms are present for the server in known_hosts.

               .. note:: The 'default' keyword should be used with
                         caution, as it can result in a host key mismatch
                         if the client trusts only a subset of the host
                         keys the server might return.
       :param server_host_keys_handler: (optional)
          A `callable` or coroutine handler function which if set will be
          called when a global request from the server is received which
          provides an updated list of server host keys. The handler takes
          four arguments (added, removed, retained, and revoked), each of
          which is a list of SSHKey public keys, reflecting differences
          between what the server reported and what is currently matching
          in known_hosts.

               .. note:: This handler will only be called when known
                         host checking is enabled and the check succeeded.
       :param x509_trusted_certs: (optional)
           A list of certificates which should be trusted for X.509 server
           certificate authentication. If no trusted certificates are
           specified, an attempt will be made to load them from the file
           :file:`.ssh/ca-bundle.crt`. If this argument is explicitly set
           to `None`, X.509 server certificate authentication will not
           be performed.

               .. note:: X.509 certificates to trust can also be provided
                         through a :ref:`known_hosts <KnownHosts>` file
                         if they are converted into OpenSSH format.
                         This allows their trust to be limited to only
                         specific host names.
       :param x509_trusted_cert_paths: (optional)
           A list of path names to "hash directories" containing certificates
           which should be trusted for X.509 server certificate authentication.
           Each certificate should be in a separate file with a name of the
           form *hash.number*, where *hash* is the OpenSSL hash value of the
           certificate subject name and *number* is an integer counting up
           from zero if multiple certificates have the same hash. If no
           paths are specified, an attempt with be made to use the directory
           :file:`.ssh/crt` as a certificate hash directory.
       :param x509_purposes: (optional)
           A list of purposes allowed in the ExtendedKeyUsage of a
           certificate used for X.509 server certificate authentication,
           defulting to 'secureShellServer'. If this argument is explicitly
           set to `None`, the server certificate's ExtendedKeyUsage will
           not be checked.
       :param username: (optional)
           Username to authenticate as on the server. If not specified,
           the currently logged in user on the local machine will be used.
       :param password: (optional)
           The password to use for client password authentication or
           keyboard-interactive authentication which prompts for a password,
           or a `callable` or coroutine which returns the password to use.
           If this is not specified or set to `None`, client password
           authentication will not be performed.
       :param client_host_keysign: (optional)
           Whether or not to use `ssh-keysign` to sign host-based
           authentication requests. If set to `True`, an attempt will be
           made to find `ssh-keysign` in its typical locations. If set to
           a string, that will be used as the `ssh-keysign` path. When set,
           client_host_keys should be a list of public keys. Otherwise,
           client_host_keys should be a list of private keys with optional
           paired certificates.
       :param client_host_keys: (optional)
           A list of keys to use to authenticate this client via host-based
           authentication. If `client_host_keysign` is set and no host keys
           or certificates are specified, an attempt will be made to find
           them in their typical locations. If `client_host_keysign` is
           not set, host private keys must be specified explicitly or
           host-based authentication will not be performed.
       :param client_host_certs: (optional)
           A list of optional certificates which can be paired with the
           provided client host keys.
       :param client_host: (optional)
           The local hostname to use when performing host-based
           authentication. If not specified, the hostname associated with
           the local IP address of the SSH connection will be used.
       :param client_username: (optional)
           The local username to use when performing host-based
           authentication. If not specified, the username of the currently
           logged in user will be used.
       :param client_keys: (optional)
           A list of keys which will be used to authenticate this client
           via public key authentication. These keys will be used after
           trying keys from a PKCS11 provider or an ssh-agent, if either
           of those are configured. If no client keys are specified,
           an attempt will be made to load them from the files
           :file:`.ssh/id_ed25519_sk`, :file:`.ssh/id_ecdsa_sk`,
           :file:`.ssh/id_ed448`, :file:`.ssh/id_ed25519`,
           :file:`.ssh/id_ecdsa`, :file:`.ssh/id_rsa`, and
           :file:`.ssh/id_dsa` in the user's home directory, with
           optional certificates loaded from the files
           :file:`.ssh/id_ed25519_sk-cert.pub`,
           :file:`.ssh/id_ecdsa_sk-cert.pub`, :file:`.ssh/id_ed448-cert.pub`,
           :file:`.ssh/id_ed25519-cert.pub`, :file:`.ssh/id_ecdsa-cert.pub`,
           :file:`.ssh/id_rsa-cert.pub`, and :file:`.ssh/id_dsa-cert.pub`.
           If this argument is explicitly set to `None`, client public key
           authentication will not be performed.
       :param client_certs: (optional)
           A list of optional certificates which can be paired with the
           provided client keys.
       :param passphrase: (optional)
           The passphrase to use to decrypt client keys if they are
           encrypted, or a `callable` or coroutine which takes a filename
           as a parameter and returns the passphrase to use to decrypt
           that file. If not specified, only unencrypted client keys can
           be loaded. If the keys passed into client_keys are already
           loaded, this argument is ignored.

               .. note:: A callable or coroutine passed in as a passphrase
                         will be called on all filenames configured as
                         client keys or client host keys each time an
                         SSHClientConnectionOptions object is instantiated,
                         even if the keys aren't encrypted or aren't ever
                         used for authentication.

       :param ignore_encrypted: (optional)
           Whether or not to ignore encrypted keys when no passphrase is
           specified. This defaults to `True` when keys are specified via
           the IdentityFile config option, causing encrypted keys in the
           config to be ignored when no passphrase is specified. Note
           that encrypted keys loaded into an SSH agent can still be used
           when this option is set.
       :param host_based_auth: (optional)
           Whether or not to allow host-based authentication. By default,
           host-based authentication is enabled if client host keys are
           made available.
       :param public_key_auth: (optional)
           Whether or not to allow public key authentication. By default,
           public key authentication is enabled if client keys are made
           available.
       :param kbdint_auth: (optional)
           Whether or not to allow keyboard-interactive authentication. By
           default, keyboard-interactive authentication is enabled if a
           password is specified or if callbacks to respond to challenges
           are made available.
       :param password_auth: (optional)
           Whether or not to allow password authentication. By default,
           password authentication is enabled if a password is specified
           or if callbacks to provide a password are made available.
       :param gss_host: (optional)
           The principal name to use for the host in GSS key exchange and
           authentication. If not specified, this value will be the same
           as the `host` argument. If this argument is explicitly set to
           `None`, GSS key exchange and authentication will not be performed.
       :param gss_store: (optional)
           The GSS credential store from which to acquire credentials.
       :param gss_kex: (optional)
           Whether or not to allow GSS key exchange. By default, GSS
           key exchange is enabled.
       :param gss_auth: (optional)
           Whether or not to allow GSS authentication. By default, GSS
           authentication is enabled.
       :param gss_delegate_creds: (optional)
           Whether or not to forward GSS credentials to the server being
           accessed. By default, GSS credential delegation is disabled.
       :param preferred_auth:
           A list of authentication methods the client should attempt to
           use in order of preference. By default, the preferred list is
           gssapi-keyex, gssapi-with-mic, hostbased, publickey,
           keyboard-interactive, and then password. This list may be
           limited by which auth methods are implemented by the client
           and which methods the server accepts.
       :param disable_trivial_auth: (optional)
           Whether or not to allow "trivial" forms of auth where the
           client is not actually challenged for credentials. Setting
           this will cause the connection to fail if a server does not
           perform some non-trivial form of auth during the initial
           SSH handshake. If not specified, all forms of auth supported
           by the server are allowed, including none.
       :param agent_path: (optional)
           The path of a UNIX domain socket to use to contact an ssh-agent
           process which will perform the operations needed for client
           public key authentication, or the :class:`SSHServerConnection`
           to use to forward ssh-agent requests over. If this is not
           specified and the environment variable `SSH_AUTH_SOCK` is
           set, its value will be used as the path. If this argument is
           explicitly set to `None`, an ssh-agent will not be used.
       :param agent_identities: (optional)
           A list of identities used to restrict which SSH agent keys may
           be used. These may be specified as byte strings in binary SSH
           format or as public keys or certificates (*see*
           :ref:`SpecifyingPublicKeys` and :ref:`SpecifyingCertificates`).
           If set to `None`, all keys loaded into the SSH agent will be
           made available for use. This is the default.
       :param agent_forwarding: (optional)
           Whether or not to allow forwarding of ssh-agent requests from
           processes running on the server. This argument can also be set
           to the path of a UNIX domain socket in cases where forwarded
           agent requests should be sent to a different path than client
           agent requests. By default, forwarding ssh-agent requests from
           the server is not allowed.
       :param pkcs11_provider: (optional)
           The path of a shared library which should be used as a PKCS#11
           provider for accessing keys on PIV security tokens. By default,
           no local security tokens will be accessed.
       :param pkcs11_pin: (optional)
           The PIN to use when accessing security tokens via PKCS#11.

               .. note:: If your application opens multiple SSH connections
                         using PKCS#11 keys, you should consider calling
                         :func:`load_pkcs11_keys` explicitly instead of
                         using these arguments. This allows you to pay
                         the cost of loading the key information from the
                         security tokens only once. You can then pass the
                         returned keys via the `client_keys` argument to
                         any calls that need them.

                         Calling :func:`load_pkcs11_keys` explicitly also
                         gives you the ability to load keys from multiple
                         tokens with different PINs and to select which
                         tokens to load keys from and which keys on those
                         tokens to load.

       :param client_version: (optional)
           An ASCII string to advertise to the SSH server as the version of
           this client, defaulting to `'AsyncSSH'` and its version number.
       :param kex_algs: (optional)
           A list of allowed key exchange algorithms in the SSH handshake,
           taken from :ref:`key exchange algorithms <KexAlgs>`.
       :param encryption_algs: (optional)
           A list of encryption algorithms to use during the SSH handshake,
           taken from :ref:`encryption algorithms <EncryptionAlgs>`.
       :param mac_algs: (optional)
           A list of MAC algorithms to use during the SSH handshake, taken
           from :ref:`MAC algorithms <MACAlgs>`.
       :param compression_algs: (optional)
           A list of compression algorithms to use during the SSH handshake,
           taken from :ref:`compression algorithms <CompressionAlgs>`, or
           `None` to disable compression. The client prefers to disable
           compression, but will enable it if the server requires it.
       :param signature_algs: (optional)
           A list of public key signature algorithms to use during the SSH
           handshake, taken from :ref:`signature algorithms <SignatureAlgs>`.
       :param rekey_bytes: (optional)
           The number of bytes which can be sent before the SSH session
           key is renegotiated, defaulting to 1 GB.
       :param rekey_seconds: (optional)
           The maximum time in seconds before the SSH session key is
           renegotiated, defaulting to 1 hour.
       :param connect_timeout: (optional)
           The maximum time in seconds allowed to complete an outbound
           SSH connection. This includes the time to establish the TCP
           connection and the time to perform the initial SSH protocol
           handshake, key exchange, and authentication. This is disabled
           by default, relying on the system's default TCP connect timeout
           and AsyncSSH's login timeout.
       :param login_timeout: (optional)
           The maximum time in seconds allowed for authentication to
           complete, defaulting to 2 minutes. Setting this to 0 will
           disable the login timeout.

               .. note:: This timeout only applies after the SSH TCP
                         connection is established. To set a timeout
                         which includes establishing the TCP connection,
                         use the `connect_timeout` argument above.
       :param keepalive_interval: (optional)
           The time in seconds to wait before sending a keepalive message
           if no data has been received from the server. This defaults to
           0, which disables sending these messages.
       :param keepalive_count_max: (optional)
           The maximum number of keepalive messages which will be sent
           without getting a response before disconnecting from the
           server. This defaults to 3, but only applies when
           keepalive_interval is non-zero.
       :param tcp_keepalive: (optional)
           Whether or not to enable keepalive probes at the TCP level to
           detect broken connections, defaulting to `True`.
       :param canonicalize_hostname: (optional)
           Whether or not to enable hostname canonicalization, defaulting
           to `False`, in which case hostnames are passed as-is to the
           system resolver. If set to `True`, requests that don't involve
           a proxy tunnel or command will attempt to canonicalize the hostname
           using canonical_domains and rules in canonicalize_permitted_cnames.
           If set to `'always'`, hostname canonicalization is also applied
           to proxied requests.
       :param canonical_domains: (optional)
           When canonicalize_hostname is set, this specifies list of domain
           suffixes in which to search for the hostname.
       :param canonicalize_fallback_local: (optional)
           Whether or not to fall back to looking up the hostname against
           the system resolver's search domains when no matches are found
           in canonical_domains, defaulting to `True`.
       :param canonicalize_max_dots: (optional)
           Tha maximum number of dots which can appear in a hostname
           before hostname canonicalization is disabled, defaulting
           to 1. Hostnames with more than this number of dots are
           treated as already being fully qualified and passed as-is
           to the system resolver.
       :param canonicalize_permitted_cnames: (optional)
           Patterns to match against to decide whether hostname
           canonicalization should return a CNAME. This argument
           contains a list of pairs of wildcard pattern lists. The
           first pattern is matched against the hostname found after
           adding one of the search domains from canonical_domains and
           the second pattern is matched against the associated CNAME.
           If a match can be found in the list for both patterns, the
           CNAME is returned as the canonical hostname. The default
           is an empty list, preventing CNAMEs from being returned.
       :param command: (optional)
           The default remote command to execute on client sessions.
           An interactive shell is started if no command or subsystem is
           specified.
       :param subsystem: (optional)
           The default remote subsystem to start on client sessions.
       :param env: (optional)
           The  default environment variables to set for client sessions.
           Keys and values passed in here will be converted to Unicode
           strings encoded as UTF-8 (ISO 10646) for transmission.

               .. note:: Many SSH servers restrict which environment
                         variables a client is allowed to set. The
                         server's configuration may need to be edited
                         before environment variables can be
                         successfully set in the remote environment.
       :param send_env: (optional)
           A list of environment variable names to pull from
           `os.environ` and set by default for client sessions. Wildcards
           patterns using `'*'` and `'?'` are allowed, and all variables
           with matching names will be sent with whatever value is set in
           the local environment. If a variable is present in both env
           and send_env, the value from env will be used.
       :param request_pty: (optional)
           Whether or not to request a pseudo-terminal (PTY) by default for
           client sessions. This defaults to `True`, which means to request
           a PTY whenever the `term_type` is set. Other possible values
           include `False` to never request a PTY, `'force'` to always
           request a PTY even without `term_type` being set, or `'auto'`
           to request a TTY when `term_type` is set but only when starting
           an interactive shell.
       :param term_type: (optional)
           The default terminal type to set for client sessions.
       :param term_size: (optional)
           The terminal width and height in characters and optionally
           the width and height in pixels to set for client sessions.
       :param term_modes: (optional)
           POSIX terminal modes to set for client sessions, where keys are
           taken from :ref:`POSIX terminal modes <PTYModes>` with values
           defined in section 8 of :rfc:`RFC 4254 <4254#section-8>`.
       :param x11_forwarding: (optional)
           Whether or not to request X11 forwarding for client sessions,
           defaulting to `False`. If set to `True`, X11 forwarding will be
           requested and a failure will raise :exc:`ChannelOpenError`. It
           can also be set to `'ignore_failure'` to attempt X11 forwarding
           but ignore failures.
       :param x11_display: (optional)
           The display that X11 connections should be forwarded to,
           defaulting to the value in the environment variable `DISPLAY`.
       :param x11_auth_path: (optional)
           The path to the Xauthority file to read X11 authentication
           data from, defaulting to the value in the environment variable
           `XAUTHORITY` or the file :file:`.Xauthority` in the user's
           home directory if that's not set.
       :param x11_single_connection: (optional)
           Whether or not to limit X11 forwarding to a single connection,
           defaulting to `False`.
       :param encoding: (optional)
           The default Unicode encoding to use for data exchanged on client
           sessions.
       :param errors: (optional)
           The default error handling strategy to apply on Unicode
           encode/decode errors.
       :param window: (optional)
           The default receive window size to set for client sessions.
       :param max_pktsize: (optional)
           The default maximum packet size to set for client sessions.
       :param config: (optional)
           Paths to OpenSSH client configuration files to load. This
           configuration will be used as a fallback to override the
           defaults for settings which are not explicitly specified using
           AsyncSSH's configuration options.

               .. note:: Specifying configuration files when creating an
                         :class:`SSHClientConnectionOptions` object will
                         cause the config file to be read and parsed at
                         the time of creation of the object, including
                         evaluation of any conditional blocks. If you want
                         the config to be parsed for every new connection,
                         this argument should be added to the connect or
                         listen calls instead. However, if you want to
                         save the parsing overhead and your configuration
                         doesn't depend on conditions that would change
                         between calls, this argument may be an option.
       :param options: (optional)
           A previous set of options to use as the base to incrementally
           build up a configuration. When an option is not explicitly
           specified, its value will be pulled from this options object
           (if present) before falling back to the default value.
       :type client_factory: `callable` returning :class:`SSHClient`
       :type proxy_command: `str` or `list` of `str`
       :type known_hosts: *see* :ref:`SpecifyingKnownHosts`
       :type host_key_alias: `str`
       :type server_host_key_algs: `str` or `list` of `str`
       :type server_host_keys_handler: `callable` or coroutine
       :type x509_trusted_certs: *see* :ref:`SpecifyingCertificates`
       :type x509_trusted_cert_paths: `list` of `str`
       :type x509_purposes: *see* :ref:`SpecifyingX509Purposes`
       :type username: `str`
       :type password: `str`
       :type client_host_keysign: `bool` or `str`
       :type client_host_keys:
           *see* :ref:`SpecifyingPrivateKeys` or :ref:`SpecifyingPublicKeys`
       :type client_host_certs: *see* :ref:`SpecifyingCertificates`
       :type client_host: `str`
       :type client_username: `str`
       :type client_keys: *see* :ref:`SpecifyingPrivateKeys`
       :type client_certs: *see* :ref:`SpecifyingCertificates`
       :type passphrase: `str` or `bytes`
       :type ignore_encrypted: `bool`
       :type host_based_auth: `bool`
       :type public_key_auth: `bool`
       :type kbdint_auth: `bool`
       :type password_auth: `bool`
       :type gss_host: `str`
       :type gss_store:
           `str`, `bytes`, or a `dict` with `str` or `bytes` keys and values
       :type gss_kex: `bool`
       :type gss_auth: `bool`
       :type gss_delegate_creds: `bool`
       :type preferred_auth: `str` or `list` of `str`
       :type disable_trivial_auth: `bool`
       :type agent_path: `str`
       :type agent_identities:
           *see* :ref:`SpecifyingPublicKeys` and :ref:`SpecifyingCertificates`
       :type agent_forwarding: `bool` or `str`
       :type pkcs11_provider: `str` or `None`
       :type pkcs11_pin: `str`
       :type client_version: `str`
       :type kex_algs: `str` or `list` of `str`
       :type encryption_algs: `str` or `list` of `str`
       :type mac_algs: `str` or `list` of `str`
       :type compression_algs: `str` or `list` of `str`
       :type signature_algs: `str` or `list` of `str`
       :type rekey_bytes: *see* :ref:`SpecifyingByteCounts`
       :type rekey_seconds: *see* :ref:`SpecifyingTimeIntervals`
       :type connect_timeout: *see* :ref:`SpecifyingTimeIntervals`
       :type login_timeout: *see* :ref:`SpecifyingTimeIntervals`
       :type keepalive_interval: *see* :ref:`SpecifyingTimeIntervals`
       :type keepalive_count_max: `int`
       :type tcp_keepalive: `bool`
       :type canonicalize_hostname: `bool` or `'always'`
       :type canonical_domains: `list` of `str`
       :type canonicalize_fallback_local: `bool`
       :type canonicalize_max_dots: `int`
       :type canonicalize_permitted_cnames: `list` of `tuple` of 2 `str` values
       :type command: `str`
       :type subsystem: `str`
       :type env: `dict` with `str` keys and values
       :type send_env: `list` of `str`
       :type request_pty: `bool`, `'force'`, or `'auto'`
       :type term_type: `str`
       :type term_size: `tuple` of 2 or 4 `int` values
       :type term_modes: `dict` with `int` keys and values
       :type x11_forwarding: `bool` or `'ignore_failure'`
       :type x11_display: `str`
       :type x11_auth_path: `str`
       :type x11_single_connection: `bool`
       :type encoding: `str` or `None`
       :type errors: `str`
       :type window: `int`
       :type max_pktsize: `int`
       :type config: `list` of `str`
       :type options: :class:`SSHClientConnectionOptions`

    """

    config: SSHClientConfig
    client_factory: _ClientFactory
    client_version: bytes
    known_hosts: KnownHostsArg
    host_key_alias: Optional[str]
    server_host_key_algs: Union[str, Sequence[str]]
    server_host_keys_handler: _ServerHostKeysHandler
    username: str
    password: Optional[str]
    client_host_keysign: Optional[str]
    client_host_keypairs: Sequence[SSHKeyPair]
    client_host_pubkeys: Sequence[Union[SSHKey, SSHCertificate]]
    client_host: Optional[str]
    client_username: str
    client_keys: Optional[Sequence[SSHKeyPair]]
    client_certs: Sequence[FilePath]
    ignore_encrypted: bool
    gss_host: DefTuple[Optional[str]]
    gss_store: Optional[Dict[BytesOrStr, BytesOrStr]]
    gss_kex: bool
    gss_auth: bool
    gss_delegate_creds: bool
    preferred_auth: Sequence[str]
    disable_trivial_auth: bool
    agent_path: Optional[str]
    agent_identities: Optional[Sequence[bytes]]
    agent_forward_path: Optional[str]
    pkcs11_provider: Optional[str]
    pkcs11_pin: Optional[str]
    command: Optional[str]
    subsystem: Optional[str]
    env: Env
    send_env: Optional[EnvSeq]
    request_pty: _RequestPTY
    term_type: Optional[str]
    term_size: TermSizeArg
    term_modes: TermModesArg
    x11_forwarding: Union[bool, str]
    x11_display: Optional[str]
    x11_auth_path: Optional[str]
    x11_single_connection: bool
    encoding: Optional[str]
    errors: str
    window: int
    max_pktsize: int

    # pylint: disable=arguments-differ
    def prepare(self, # type: ignore
                loop: Optional[asyncio.AbstractEventLoop] = None,
                last_config: Optional[SSHConfig] = None,
                config: DefTuple[ConfigPaths] = None, reload: bool = False,
                canonical: bool = False, final: bool = False,
                client_factory: Optional[_ClientFactory] = None,
                client_version: _VersionArg = (), host: str = '',
                port: DefTuple[int] = (), tunnel: object = (),
                proxy_command: DefTuple[_ProxyCommand] = (),
                family: DefTuple[int] = (),
                local_addr: DefTuple[HostPort] = (),
                tcp_keepalive: DefTuple[bool] = (),
                canonicalize_hostname: DefTuple[Union[bool, str]] = (),
                canonical_domains: DefTuple[Sequence[str]] = (),
                canonicalize_fallback_local: DefTuple[bool] = (),
                canonicalize_max_dots: DefTuple[int] = (),
                canonicalize_permitted_cnames: DefTuple[Sequence[str]] = (),
                kex_algs: _AlgsArg = (), encryption_algs: _AlgsArg = (),
                mac_algs: _AlgsArg = (), compression_algs: _AlgsArg = (),
                signature_algs: _AlgsArg = (), host_based_auth: _AuthArg = (),
                public_key_auth: _AuthArg = (), kbdint_auth: _AuthArg = (),
                password_auth: _AuthArg = (),
                x509_trusted_certs: CertListArg = (),
                x509_trusted_cert_paths: Sequence[FilePath] = (),
                x509_purposes: X509CertPurposes = 'secureShellServer',
                rekey_bytes: DefTuple[Union[int, str]] = (),
                rekey_seconds: DefTuple[Union[float, str]] = (),
                connect_timeout: DefTuple[Optional[Union[float, str]]] = (),
                login_timeout: Union[float, str] = _DEFAULT_LOGIN_TIMEOUT,
                keepalive_interval: DefTuple[Union[float, str]] = (),
                keepalive_count_max: DefTuple[int] = (),
                known_hosts: KnownHostsArg = (),
                host_key_alias: DefTuple[Optional[str]] = (),
                server_host_key_algs: _AlgsArg = (),
                server_host_keys_handler: _ServerHostKeysHandler = None,
                username: DefTuple[str] = (), password: Optional[str] = None,
                client_host_keysign: DefTuple[KeySignPath] = (),
                client_host_keys: Optional[_ClientKeysArg] = None,
                client_host_certs: Sequence[FilePath] = (),
                client_host: Optional[str] = None,
                client_username: DefTuple[str] = (),
                client_keys: _ClientKeysArg = (),
                client_certs: Sequence[FilePath] = (),
                passphrase: Optional[BytesOrStr] = None,
                ignore_encrypted: DefTuple[bool] = (),
                gss_host: DefTuple[Optional[str]] = (),
                gss_store: Optional[Union[BytesOrStr, BytesOrStrDict]] = None,
                gss_kex: DefTuple[bool] = (), gss_auth: DefTuple[bool] = (),
                gss_delegate_creds: DefTuple[bool] = (),
                preferred_auth: DefTuple[Union[str, Sequence[str]]] = (),
                disable_trivial_auth: bool = False,
                agent_path: DefTuple[Optional[str]] = (),
                agent_identities: DefTuple[Optional[IdentityListArg]] = (),
                agent_forwarding: DefTuple[Union[bool, str]] = (),
                pkcs11_provider: DefTuple[Optional[str]] = (),
                pkcs11_pin: Optional[str] = None,
                command: DefTuple[Optional[str]] = (),
                subsystem: Optional[str] = None, env: DefTuple[Env] = (),
                send_env: DefTuple[Optional[EnvSeq]] = (),
                request_pty: DefTuple[_RequestPTY] = (),
                term_type: Optional[str] = None,
                term_size: TermSizeArg = None,
                term_modes: TermModesArg = None,
                x11_forwarding: DefTuple[Union[bool, str]] = (),
                x11_display: Optional[str] = None,
                x11_auth_path: Optional[str] = None,
                x11_single_connection: bool = False,
                encoding: Optional[str] = 'utf-8', errors: str = 'strict',
                window: int = _DEFAULT_WINDOW,
                max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> None:
        """Prepare client connection configuration options"""

        try:
            local_username = getpass.getuser()
        except KeyError:
            raise ValueError('Unknown local username: set one of '
                             'LOGNAME, USER, LNAME, or USERNAME in '
                             'the environment') from None

        if config == () and (not last_config or not last_config.loaded):
            default_config = Path('~', '.ssh', 'config').expanduser()
            config = [default_config] if os.access(default_config,
                                                   os.R_OK) else []

        config = SSHClientConfig.load(last_config, config, reload, canonical,
                                      final, local_username, username, host,
                                      port)

        if x509_trusted_certs == ():
            default_x509_certs = Path('~', '.ssh', 'ca-bundle.crt').expanduser()

            if os.access(default_x509_certs, os.R_OK):
                x509_trusted_certs = str(default_x509_certs)

        if x509_trusted_cert_paths == ():
            default_x509_cert_path = Path('~', '.ssh', 'crt').expanduser()

            if default_x509_cert_path.is_dir():
                x509_trusted_cert_paths = [str(default_x509_cert_path)]

        if connect_timeout == ():
            connect_timeout = cast(Optional[Union[float, str]],
                                   config.get('ConnectTimeout', None))

        connect_timeout: Optional[Union[float, str]]

        if keepalive_interval == ():
            keepalive_interval = \
                cast(Union[float, str], config.get('ServerAliveInterval',
                                                   _DEFAULT_KEEPALIVE_INTERVAL))

        keepalive_interval: Union[float, str]

        if keepalive_count_max == ():
            keepalive_count_max = \
                cast(int, config.get('ServerAliveCountMax',
                                     _DEFAULT_KEEPALIVE_COUNT_MAX))

        keepalive_count_max: int

        super().prepare(config, client_factory or SSHClient, client_version,
                        host, port, tunnel, passphrase, proxy_command, family,
                        local_addr, tcp_keepalive, canonicalize_hostname,
                        canonical_domains, canonicalize_fallback_local,
                        canonicalize_max_dots, canonicalize_permitted_cnames,
                        kex_algs, encryption_algs, mac_algs, compression_algs,
                        signature_algs, host_based_auth, public_key_auth,
                        kbdint_auth, password_auth, x509_trusted_certs,
                        x509_trusted_cert_paths, x509_purposes, rekey_bytes,
                        rekey_seconds, connect_timeout, login_timeout,
                        keepalive_interval, keepalive_count_max)

        if known_hosts != ():
            self.known_hosts = known_hosts
        else:
            user_known_hosts = \
                cast(List[str], config.get('UserKnownHostsFile', ()))

            if user_known_hosts == []:
                self.known_hosts = None
            else:
                self.known_hosts = list(user_known_hosts) + \
                    cast(List[str], config.get('GlobalKnownHostsFile', []))

        self.host_key_alias = \
            cast(Optional[str], host_key_alias if host_key_alias != () else
                config.get('HostKeyAlias'))

        self.server_host_key_algs = server_host_key_algs

        # Just validate the input here -- the actual server host key
        # selection is done later, after the known_hosts lookup is done.
        _select_host_key_algs(server_host_key_algs,
            cast(DefTuple[str], config.get('HostKeyAlgorithms', ())), [])

        self.server_host_keys_handler = server_host_keys_handler

        self.username = saslprep(cast(str, username if username != () else
                                      config.get('User', local_username)))

        self.password = password

        if client_host_keysign == ():
            client_host_keysign = \
                cast(bool, config.get('EnableSSHKeySign', False))

        if client_host_keysign:
            client_host_keysign = find_keysign(client_host_keysign)

            if client_host_keys:
                self.client_host_pubkeys = \
                    load_public_keys(cast(KeyListArg, client_host_keys))
            else:
                self.client_host_pubkeys = load_default_host_public_keys()
        else:
            client_host_keysign = None

            self.client_host_keypairs = \
                load_keypairs(cast(KeyPairListArg, client_host_keys),
                              passphrase, client_host_certs, loop=loop)

        self.client_host_keysign = client_host_keysign
        self.client_host = client_host

        self.client_username = saslprep(cast(str, client_username
                if client_username != () else local_username))

        self.gss_host = gss_host

        if isinstance(gss_store, (bytes, str)):
            self.gss_store = {'ccache': gss_store}
        else:
            self.gss_store = gss_store

        self.gss_kex = cast(bool, gss_kex if gss_kex != () else
            config.get('GSSAPIKeyExchange', True))

        self.gss_auth = cast(bool, gss_auth if gss_auth != () else
            config.get('GSSAPIAuthentication', True))

        self.gss_delegate_creds = cast(bool,
            gss_delegate_creds if gss_delegate_creds != () else
                config.get('GSSAPIDelegateCredentials', False))

        if preferred_auth == ():
            preferred_auth = \
                cast(str, config.get('PreferredAuthentications', ()))

        if isinstance(preferred_auth, str):
            preferred_auth = preferred_auth.split(',')

        preferred_auth: Sequence[str]

        self.preferred_auth = preferred_auth

        self.disable_trivial_auth = disable_trivial_auth

        if agent_path == ():
            agent_path = cast(DefTuple[str], config.get('IdentityAgent', ()))

        if agent_path == ():
            agent_path = os.environ.get('SSH_AUTH_SOCK', '')

        agent_path = str(Path(agent_path).expanduser()) if agent_path else ''

        if pkcs11_provider == ():
            pkcs11_provider = \
                cast(Optional[str], config.get('PKCS11Provider'))

        pkcs11_provider: Optional[str]

        if ignore_encrypted == ():
            ignore_encrypted = client_keys == ()

        ignore_encrypted: bool

        if client_keys == ():
            client_keys = cast(_ClientKeysArg, config.get('IdentityFile', ()))

        if client_certs == ():
            client_certs = \
                cast(Sequence[FilePath], config.get('CertificateFile', ()))

        identities_only = cast(bool, config.get('IdentitiesOnly'))

        if agent_identities == ():
            if identities_only:
                agent_identities = cast(KeyListArg, client_keys)
            else:
                agent_identities = None

        if agent_identities:
            self.agent_identities = load_identities(agent_identities,
                                                    identities_only)
        elif agent_identities == ():
            self.agent_identities = load_default_identities()
        else:
            self.agent_identities = None

        if client_keys:
            self.client_keys = \
                load_keypairs(cast(KeyPairListArg, client_keys), passphrase,
                              client_certs, identities_only, ignore_encrypted,
                              loop=loop)
        elif client_keys is not None:
            self.client_keys = load_default_keypairs(passphrase, client_certs)
        else:
            self.client_keys = None

        if self.client_keys is not None:
            self.agent_path = agent_path
            self.pkcs11_provider = pkcs11_provider
            self.pkcs11_pin = pkcs11_pin
        else:
            self.agent_path = None
            self.pkcs11_provider = None
            self.pkcs11_pin = None

        if agent_forwarding == ():
            agent_forwarding = cast(Union[bool, str],
                                    config.get('ForwardAgent', False))

        agent_forwarding: Union[bool, str]

        if not agent_forwarding:
            self.agent_forward_path = None
        elif agent_forwarding is True:
            self.agent_forward_path = agent_path
        else:
            self.agent_forward_path = agent_forwarding

        self.command = cast(Optional[str], command if command != () else
            config.get('RemoteCommand'))

        self.subsystem = subsystem

        self.env = cast(Env, env if env != () else config.get('SetEnv'))

        self.send_env = cast(Optional[EnvSeq], send_env if send_env != () else
            config.get('SendEnv'))

        self.request_pty = cast(_RequestPTY, request_pty if request_pty != ()
            else config.get('RequestTTY', True))

        self.term_type = term_type
        self.term_size = term_size
        self.term_modes = term_modes

        self.x11_forwarding = cast(Union[bool, str],
            x11_forwarding if x11_forwarding != () else
                config.get('ForwardX11Trusted') and 'ignore_failure')

        self.x11_display = x11_display
        self.x11_auth_path = x11_auth_path
        self.x11_single_connection = x11_single_connection
        self.encoding = encoding
        self.errors = errors
        self.window = window
        self.max_pktsize = max_pktsize


class SSHServerConnectionOptions(SSHConnectionOptions):
    """SSH server connection options

       The following options are available to control the acceptance
       of SSH server connections:

       :param server_factory:
           A `callable` which returns an :class:`SSHServer` object that will
           be created for each new connection.
       :param proxy_command: (optional)
           A string or list of strings specifying a command and arguments
           to run when using :func:`connect_reverse` to make a reverse
           direction connection to an SSH client. Data will be forwarded
           to this process over stdin/stdout instead of opening a TCP
           connection. If specified as a string, standard shell quoting
           will be applied when splitting the command and its arguments.
       :param server_host_keys: (optional)
           A list of private keys and optional certificates which can be
           used by the server as a host key. Either this argument or
           `gss_host` must be specified. If this is not specified,
           only GSS-based key exchange will be supported.
       :param server_host_certs: (optional)
           A list of optional certificates which can be paired with the
           provided server host keys.
       :param send_server_host_keys: (optional)
           Whether or not to send a list of the allowed server host keys
           for clients to use to update their known hosts like for the
           server.

               .. note:: Enabling this option will allow multiple server
                         host keys of the same type to be configured. Only
                         the first key of each type will be actively used
                         during key exchange, but the others will be
                         reported as reserved keys that clients should
                         begin to trust, to allow for future key rotation.
                         If this option is disabled, specifying multiple
                         server host keys of the same type is treated as
                         a configuration error.
       :param passphrase: (optional)
           The passphrase to use to decrypt server host keys if they are
           encrypted, or a `callable` or coroutine which takes a filename
           as a parameter and returns the passphrase to use to decrypt
           that file. If not specified, only unencrypted server host keys
           can be loaded. If the keys passed into server_host_keys are
           already loaded, this argument is ignored.

               .. note:: A callable or coroutine passed in as a passphrase
                         will be called on all filenames configured as
                         server host keys each time an
                         SSHServerConnectionOptions object is instantiated,
                         even if the keys aren't encrypted or aren't ever
                         used for server validation.

       :param known_client_hosts: (optional)
           A list of client hosts which should be trusted to perform
           host-based client authentication. If this is not specified,
           host-based client authentication will be not be performed.
       :param trust_client_host: (optional)
           Whether or not to use the hostname provided by the client
           when performing host-based authentication. By default, the
           client-provided hostname is not trusted and is instead
           determined by doing a reverse lookup of the IP address the
           client connected from.
       :param authorized_client_keys: (optional)
           A list of authorized user and CA public keys which should be
           trusted for certificate-based client public key authentication.
       :param x509_trusted_certs: (optional)
           A list of certificates which should be trusted for X.509 client
           certificate authentication. If this argument is explicitly set
           to `None`, X.509 client certificate authentication will not
           be performed.

               .. note:: X.509 certificates to trust can also be provided
                         through an :ref:`authorized_keys <AuthorizedKeys>`
                         file if they are converted into OpenSSH format.
                         This allows their trust to be limited to only
                         specific client IPs or user names and allows
                         SSH functions to be restricted when these
                         certificates are used.
       :param x509_trusted_cert_paths: (optional)
           A list of path names to "hash directories" containing certificates
           which should be trusted for X.509 client certificate authentication.
           Each certificate should be in a separate file with a name of the
           form *hash.number*, where *hash* is the OpenSSL hash value of the
           certificate subject name and *number* is an integer counting up
           from zero if multiple certificates have the same hash.
       :param x509_purposes: (optional)
           A list of purposes allowed in the ExtendedKeyUsage of a
           certificate used for X.509 client certificate authentication,
           defulting to 'secureShellClient'. If this argument is explicitly
           set to `None`, the client certificate's ExtendedKeyUsage will
           not be checked.
       :param host_based_auth: (optional)
           Whether or not to allow host-based authentication. By default,
           host-based authentication is enabled if known client host keys
           are specified or if callbacks to validate client host keys
           are made available.
       :param public_key_auth: (optional)
           Whether or not to allow public key authentication. By default,
           public key authentication is enabled if authorized client keys
           are specified or if callbacks to validate client keys are made
           available.
       :param kbdint_auth: (optional)
           Whether or not to allow keyboard-interactive authentication. By
           default, keyboard-interactive authentication is enabled if the
           callbacks to generate challenges are made available.
       :param password_auth: (optional)
           Whether or not to allow password authentication. By default,
           password authentication is enabled if callbacks to validate a
           password are made available.
       :param gss_host: (optional)
           The principal name to use for the host in GSS key exchange and
           authentication. If not specified, the value returned by
           :func:`socket.gethostname` will be used if it is a fully qualified
           name. Otherwise, the value used by :func:`socket.getfqdn` will be
           used. If this argument is explicitly set to `None`, GSS
           key exchange and authentication will not be performed.
       :param gss_store: (optional)
           The GSS credential store from which to acquire credentials.
       :param gss_kex: (optional)
           Whether or not to allow GSS key exchange. By default, GSS
           key exchange is enabled.
       :param gss_auth: (optional)
           Whether or not to allow GSS authentication. By default, GSS
           authentication is enabled.
       :param allow_pty: (optional)
           Whether or not to allow allocation of a pseudo-tty in sessions,
           defaulting to `True`
       :param line_editor: (optional)
           Whether or not to enable input line editing on sessions which
           have a pseudo-tty allocated, defaulting to `True`
       :param line_echo: (bool)
           Whether or not to echo completed input lines when they are
           entered, rather than waiting for the application to read and
           echo them, defaulting to `True`. Setting this to `False`
           and performing the echo in the application can better synchronize
           input and output, especially when there are input prompts.
       :param line_history: (int)
           The number of lines of input line history to store in the
           line editor when it is enabled, defaulting to 1000
       :param max_line_length: (int)
           The maximum number of characters allowed in an input line when
           the line editor is enabled, defaulting to 1024
       :param rdns_lookup: (optional)
           Whether or not to perform reverse DNS lookups on the client's
           IP address to enable hostname-based matches in authorized key
           file "from" options and "Match Host" config options, defaulting
           to `False`.
       :param x11_forwarding: (optional)
           Whether or not to allow forwarding of X11 connections back
           to the client when the client supports it, defaulting to `False`
       :param x11_auth_path: (optional)
           The path to the Xauthority file to write X11 authentication
           data to, defaulting to the value in the environment variable
           `XAUTHORITY` or the file :file:`.Xauthority` in the user's
           home directory if that's not set
       :param agent_forwarding: (optional)
           Whether or not to allow forwarding of ssh-agent requests back
           to the client when the client supports it, defaulting to `True`
       :param process_factory: (optional)
           A `callable` or coroutine handler function which takes an AsyncSSH
           :class:`SSHServerProcess` argument that will be called each time a
           new shell, exec, or subsystem other than SFTP is requested by the
           client. If set, this takes precedence over the `session_factory`
           argument.
       :param session_factory: (optional)
           A `callable` or coroutine handler function which takes AsyncSSH
           stream objects for stdin, stdout, and stderr that will be called
           each time a new shell, exec, or subsystem other than SFTP is
           requested by the client. If not specified, sessions are rejected
           by default unless the :meth:`session_requested()
           <SSHServer.session_requested>` method is overridden on the
           :class:`SSHServer` object returned by `server_factory` to make
           this decision.
       :param encoding: (optional)
           The Unicode encoding to use for data exchanged on sessions on
           this server, defaulting to UTF-8 (ISO 10646) format. If `None`
           is passed in, the application can send and receive raw bytes.
       :param errors: (optional)
           The error handling strategy to apply on Unicode encode/decode
           errors of data exchanged on sessions on this server, defaulting
           to 'strict'.
       :param sftp_factory: (optional)
           A `callable` which returns an :class:`SFTPServer` object that
           will be created each time an SFTP session is requested by the
           client, or `True` to use the base :class:`SFTPServer` class
           to handle SFTP requests. If not specified, SFTP sessions are
           rejected by default.
       :param sftp_version: (optional)
           The maximum version of the SFTP protocol to support, currently
           either 3 or 4, defaulting to 3.
       :param allow_scp: (optional)
           Whether or not to allow incoming scp requests to be accepted.
           This option can only be used in conjunction with `sftp_factory`.
           If not specified, scp requests will be passed as regular
           commands to the `process_factory` or `session_factory`.
           to the client when the client supports it, defaulting to `True`
       :param window: (optional)
           The receive window size for sessions on this server
       :param max_pktsize: (optional)
           The maximum packet size for sessions on this server
       :param server_version: (optional)
           An ASCII string to advertise to SSH clients as the version of
           this server, defaulting to `'AsyncSSH'` and its version number.
       :param kex_algs: (optional)
           A list of allowed key exchange algorithms in the SSH handshake,
           taken from :ref:`key exchange algorithms <KexAlgs>`,
       :param encryption_algs: (optional)
           A list of encryption algorithms to use during the SSH handshake,
           taken from :ref:`encryption algorithms <EncryptionAlgs>`.
       :param mac_algs: (optional)
           A list of MAC algorithms to use during the SSH handshake, taken
           from :ref:`MAC algorithms <MACAlgs>`.
       :param compression_algs: (optional)
           A list of compression algorithms to use during the SSH handshake,
           taken from :ref:`compression algorithms <CompressionAlgs>`, or
           `None` to disable compression. The server defaults to allowing
           either no compression or compression after auth, depending on
           what the client requests.
       :param signature_algs: (optional)
           A list of public key signature algorithms to use during the SSH
           handshake, taken from :ref:`signature algorithms <SignatureAlgs>`.
       :param rekey_bytes: (optional)
           The number of bytes which can be sent before the SSH session
           key is renegotiated, defaulting to 1 GB.
       :param rekey_seconds: (optional)
           The maximum time in seconds before the SSH session key is
           renegotiated, defaulting to 1 hour.
       :param connect_timeout: (optional)
           The maximum time in seconds allowed to complete an outbound
           SSH connection. This includes the time to establish the TCP
           connection and the time to perform the initial SSH protocol
           handshake, key exchange, and authentication. This is disabled
           by default, relying on the system's default TCP connect timeout
           and AsyncSSH's login timeout.
       :param login_timeout: (optional)
           The maximum time in seconds allowed for authentication to
           complete, defaulting to 2 minutes. Setting this to 0 will
           disable the login timeout.

               .. note:: This timeout only applies after the SSH TCP
                         connection is established. To set a timeout
                         which includes establishing the TCP connection,
                         use the `connect_timeout` argument above.
       :param keepalive_interval: (optional)
           The time in seconds to wait before sending a keepalive message
           if no data has been received from the client. This defaults to
           0, which disables sending these messages.
       :param keepalive_count_max: (optional)
           The maximum number of keepalive messages which will be sent
           without getting a response before disconnecting a client.
           This defaults to 3, but only applies when keepalive_interval is
           non-zero.
       :param tcp_keepalive: (optional)
           Whether or not to enable keepalive probes at the TCP level to
           detect broken connections, defaulting to `True`.
       :param canonicalize_hostname: (optional)
           Whether or not to enable hostname canonicalization, defaulting
           to `False`, in which case hostnames are passed as-is to the
           system resolver. If set to `True`, requests that don't involve
           a proxy tunnel or command will attempt to canonicalize the hostname
           using canonical_domains and rules in canonicalize_permitted_cnames.
           If set to `'always'`, hostname canonicalization is also applied
           to proxied requests.
       :param canonical_domains: (optional)
           When canonicalize_hostname is set, this specifies list of domain
           suffixes in which to search for the hostname.
       :param canonicalize_fallback_local: (optional)
           Whether or not to fall back to looking up the hostname against
           the system resolver's search domains when no matches are found
           in canonical_domains, defaulting to `True`.
       :param canonicalize_max_dots: (optional)
           Tha maximum number of dots which can appear in a hostname
           before hostname canonicalization is disabled, defaulting
           to 1. Hostnames with more than this number of dots are
           treated as already being fully qualified and passed as-is
           to the system resolver.
       :param config: (optional)
           Paths to OpenSSH server configuration files to load. This
           configuration will be used as a fallback to override the
           defaults for settings which are not explicitly specified using
           AsyncSSH's configuration options.

               .. note:: Specifying configuration files when creating an
                         :class:`SSHServerConnectionOptions` object will
                         cause the config file to be read and parsed at
                         the time of creation of the object, including
                         evaluation of any conditional blocks. If you want
                         the config to be parsed for every new connection,
                         this argument should be added to the connect or
                         listen calls instead. However, if you want to
                         save the parsing overhead and your configuration
                         doesn't depend on conditions that would change
                         between calls, this argument may be an option.
       :param options: (optional)
           A previous set of options to use as the base to incrementally
           build up a configuration. When an option is not explicitly
           specified, its value will be pulled from this options object
           (if present) before falling back to the default value.
       :type server_factory: `callable` returning :class:`SSHServer`
       :type proxy_command: `str` or `list` of `str`
       :type family: `socket.AF_UNSPEC`, `socket.AF_INET`, or `socket.AF_INET6`
       :type server_host_keys: *see* :ref:`SpecifyingPrivateKeys`
       :type server_host_certs: *see* :ref:`SpecifyingCertificates`
       :type send_server_host_keys: `bool`
       :type passphrase: `str` or `bytes`
       :type known_client_hosts: *see* :ref:`SpecifyingKnownHosts`
       :type trust_client_host: `bool`
       :type authorized_client_keys: *see* :ref:`SpecifyingAuthorizedKeys`
       :type x509_trusted_certs: *see* :ref:`SpecifyingCertificates`
       :type x509_trusted_cert_paths: `list` of `str`
       :type x509_purposes: *see* :ref:`SpecifyingX509Purposes`
       :type host_based_auth: `bool`
       :type public_key_auth: `bool`
       :type kbdint_auth: `bool`
       :type password_auth: `bool`
       :type gss_host: `str`
       :type gss_store:
           `str`, `bytes`, or a `dict` with `str` or `bytes` keys and values
       :type gss_kex: `bool`
       :type gss_auth: `bool`
       :type allow_pty: `bool`
       :type line_editor: `bool`
       :type line_echo: `bool`
       :type line_history: `int`
       :type max_line_length: `int`
       :type rdns_lookup: `bool`
       :type x11_forwarding: `bool`
       :type x11_auth_path: `str`
       :type agent_forwarding: `bool`
       :type process_factory: `callable` or coroutine
       :type session_factory: `callable` or coroutine
       :type encoding: `str` or `None`
       :type errors: `str`
       :type sftp_factory: `callable`
       :type sftp_version: `int`
       :type allow_scp: `bool`
       :type window: `int`
       :type max_pktsize: `int`
       :type server_version: `str`
       :type kex_algs: `str` or `list` of `str`
       :type encryption_algs: `str` or `list` of `str`
       :type mac_algs: `str` or `list` of `str`
       :type compression_algs: `str` or `list` of `str`
       :type signature_algs: `str` or `list` of `str`
       :type rekey_bytes: *see* :ref:`SpecifyingByteCounts`
       :type rekey_seconds: *see* :ref:`SpecifyingTimeIntervals`
       :type connect_timeout: *see* :ref:`SpecifyingTimeIntervals`
       :type login_timeout: *see* :ref:`SpecifyingTimeIntervals`
       :type keepalive_interval: *see* :ref:`SpecifyingTimeIntervals`
       :type keepalive_count_max: `int`
       :type tcp_keepalive: `bool`
       :type canonicalize_hostname: `bool` or `'always'`
       :type canonical_domains: `list` of `str`
       :type canonicalize_fallback_local: `bool`
       :type canonicalize_max_dots: `int`
       :type canonicalize_permitted_cnames: `list` of `tuple` of 2 `str` values
       :type config: `list` of `str`
       :type options: :class:`SSHServerConnectionOptions`

    """

    config: SSHServerConfig
    server_factory: _ServerFactory
    server_version: bytes
    server_host_keys: 'OrderedDict[bytes, SSHKeyPair]'
    all_server_host_keys: 'OrderedDict[bytes, SSHKeyPair]'
    send_server_host_keys: bool
    known_client_hosts: KnownHostsArg
    trust_client_host: bool
    authorized_client_keys: DefTuple[Optional[SSHAuthorizedKeys]]
    gss_host: Optional[str]
    gss_store: Optional[Dict[BytesOrStr, BytesOrStr]]
    gss_kex: bool
    gss_auth: bool
    allow_pty: bool
    line_editor: bool
    line_echo: bool
    line_history: int
    max_line_length: int
    rdns_lookup: bool
    x11_forwarding: bool
    x11_auth_path: Optional[str]
    agent_forwarding: bool
    process_factory: Optional[SSHServerProcessFactory]
    session_factory: Optional[SSHServerSessionFactory]
    encoding: Optional[str]
    errors: str
    sftp_factory: Optional[SFTPServerFactory]
    sftp_version: int
    allow_scp: bool
    window: int
    max_pktsize: int

    # pylint: disable=arguments-differ
    def prepare(self, # type: ignore
                loop: Optional[asyncio.AbstractEventLoop] = None,
                last_config: Optional[SSHConfig] = None,
                config: DefTuple[ConfigPaths] = None, reload: bool = False,
                canonical: bool = False, final: bool = False,
                accept_addr: str = '', accept_port: int = 0,
                username: str = '', client_host: str = '',
                client_addr: str = '',
                server_factory: Optional[_ServerFactory] = None,
                server_version: _VersionArg = (), host: str = '',
                port: DefTuple[int] = (), tunnel: object = (),
                proxy_command: DefTuple[_ProxyCommand] = (),
                family: DefTuple[int] = (),
                local_addr: DefTuple[HostPort] = (),
                tcp_keepalive: DefTuple[bool] = (),
                canonicalize_hostname: DefTuple[Union[bool, str]] = (),
                canonical_domains: DefTuple[Sequence[str]] = (),
                canonicalize_fallback_local: DefTuple[bool] = (),
                canonicalize_max_dots: DefTuple[int] = (),
                canonicalize_permitted_cnames: DefTuple[Sequence[str]] = (),
                kex_algs: _AlgsArg = (), encryption_algs: _AlgsArg = (),
                mac_algs: _AlgsArg = (), compression_algs: _AlgsArg = (),
                signature_algs: _AlgsArg = (), host_based_auth: _AuthArg = (),
                public_key_auth: _AuthArg = (), kbdint_auth: _AuthArg = (),
                password_auth: _AuthArg = (),
                x509_trusted_certs: CertListArg = (),
                x509_trusted_cert_paths: Sequence[FilePath] = (),
                x509_purposes: X509CertPurposes = 'secureShellClient',
                rekey_bytes: DefTuple[Union[int, str]] = (),
                rekey_seconds: DefTuple[Union[float, str]] = (),
                connect_timeout: Optional[Union[float, str]] = None,
                login_timeout: DefTuple[Union[float, str]] = (),
                keepalive_interval: DefTuple[Union[float, str]] = (),
                keepalive_count_max: DefTuple[int] = (),
                server_host_keys: KeyPairListArg = (),
                server_host_certs: CertListArg = (),
                send_server_host_keys: bool = False,
                passphrase: Optional[BytesOrStr] = None,
                known_client_hosts: KnownHostsArg = None,
                trust_client_host: bool = False,
                authorized_client_keys: _AuthKeysArg = (),
                gss_host: DefTuple[Optional[str]] = (),
                gss_store: Optional[Union[BytesOrStr, BytesOrStrDict]] = None,
                gss_kex: DefTuple[bool] = (),
                gss_auth: DefTuple[bool] = (),
                allow_pty: DefTuple[bool] = (),
                line_editor: bool = True,
                line_echo: bool = True,
                line_history: int = _DEFAULT_LINE_HISTORY,
                max_line_length: int = _DEFAULT_MAX_LINE_LENGTH,
                rdns_lookup: DefTuple[bool] = (),
                x11_forwarding: bool = False,
                x11_auth_path: Optional[str] = None,
                agent_forwarding: DefTuple[bool] = (),
                process_factory: Optional[SSHServerProcessFactory] = None,
                session_factory: Optional[SSHServerSessionFactory] = None,
                encoding: Optional[str] = 'utf-8', errors: str = 'strict',
                sftp_factory: Optional[SFTPServerFactory] = None,
                sftp_version: int = MIN_SFTP_VERSION,
                allow_scp: bool = False, window: int = _DEFAULT_WINDOW,
                max_pktsize: int = _DEFAULT_MAX_PKTSIZE) -> None:
        """Prepare server connection configuration options"""

        config = SSHServerConfig.load(last_config, config, reload, canonical,
                                      final, accept_addr, accept_port, username,
                                      client_host, client_addr)

        if login_timeout == ():
            login_timeout = \
                cast(Union[float, str], config.get('LoginGraceTime',
                                                   _DEFAULT_LOGIN_TIMEOUT))

        login_timeout: Union[float, str]

        if keepalive_interval == ():
            keepalive_interval = \
                cast(Union[float, str], config.get('ClientAliveInterval',
                                                   _DEFAULT_KEEPALIVE_INTERVAL))

        keepalive_interval: Union[float, str]

        if keepalive_count_max == ():
            keepalive_count_max = \
                cast(int, config.get('ClientAliveCountMax',
                                     _DEFAULT_KEEPALIVE_COUNT_MAX))

        keepalive_count_max: int

        super().prepare(config, server_factory or SSHServer, server_version,
                        host, port, tunnel, passphrase, proxy_command, family,
                        local_addr, tcp_keepalive, canonicalize_hostname,
                        canonical_domains, canonicalize_fallback_local,
                        canonicalize_max_dots, canonicalize_permitted_cnames,
                        kex_algs, encryption_algs, mac_algs, compression_algs,
                        signature_algs, host_based_auth, public_key_auth,
                        kbdint_auth, password_auth, x509_trusted_certs,
                        x509_trusted_cert_paths, x509_purposes,
                        rekey_bytes, rekey_seconds, connect_timeout,
                        login_timeout, keepalive_interval, keepalive_count_max)

        if server_host_keys == ():
            server_host_keys = cast(Sequence[str], config.get('HostKey'))

        if server_host_certs == ():
            server_host_certs = cast(Sequence[str],
                                     config.get('HostCertificate', ()))

        server_keys = load_keypairs(server_host_keys, passphrase,
                                    server_host_certs, loop=loop)

        self.server_host_keys = OrderedDict()
        self.all_server_host_keys = OrderedDict()

        for keypair in server_keys:
            for alg in keypair.host_key_algorithms:
                if alg in self.server_host_keys and not send_server_host_keys:
                    raise ValueError('Multiple keys of type '
                                     f'{alg.decode("ascii")} found: '
                                     'Enable send_server_host_keys to '
                                     'allow reserved keys to be configured')

                if alg not in self.server_host_keys:
                    self.server_host_keys[alg] = keypair

                if send_server_host_keys:
                    self.all_server_host_keys[keypair.public_data] = keypair

        self.known_client_hosts = known_client_hosts
        self.trust_client_host = trust_client_host

        if authorized_client_keys == () and reload:
            authorized_client_keys = \
                cast(List[str], config.get('AuthorizedKeysFile'))

        if isinstance(authorized_client_keys, (str, list)):
            self.authorized_client_keys = \
                read_authorized_keys(authorized_client_keys)
        else:
            self.authorized_client_keys = authorized_client_keys

        if gss_host == ():
            gss_host = socket.gethostname()

            if '.' not in gss_host:
                gss_host = socket.getfqdn()

        gss_host: Optional[str]

        self.gss_host = gss_host

        if isinstance(gss_store, (bytes, str)):
            self.gss_store = {'ccache': gss_store}
        else:
            self.gss_store = gss_store

        self.gss_kex = cast(bool, gss_kex if gss_kex != () else
            config.get('GSSAPIKeyExchange', True))

        self.gss_auth = cast(bool, gss_auth if gss_auth != () else
            config.get('GSSAPIAuthentication', True))

        if not server_keys and not gss_host:
            raise ValueError('No server host keys provided')

        self.allow_pty = cast(bool, allow_pty if allow_pty != () else
            config.get('PermitTTY', True))

        self.line_editor = line_editor
        self.line_echo = line_echo
        self.line_history = line_history
        self.max_line_length = max_line_length

        self.rdns_lookup = cast(bool, rdns_lookup if rdns_lookup != () else
            config.get('UseDNS', False))

        self.x11_forwarding = x11_forwarding
        self.x11_auth_path = x11_auth_path

        self.agent_forwarding = cast(bool,
            agent_forwarding if agent_forwarding != () else
                config.get('AllowAgentForwarding', True))

        self.process_factory = process_factory
        self.session_factory = session_factory
        self.encoding = encoding
        self.errors = errors
        self.sftp_factory = SFTPServer if sftp_factory is True else sftp_factory
        self.sftp_version = sftp_version
        self.allow_scp = allow_scp
        self.window = window
        self.max_pktsize = max_pktsize


@async_context_manager
async def run_client(sock: socket.socket, config: DefTuple[ConfigPaths] = (),
                     options: Optional[SSHClientConnectionOptions] = None,
                     **kwargs: object) -> SSHClientConnection:
    """Start an SSH client connection on an already-connected socket

       This function is a coroutine which starts an SSH client on an
       existing already-connected socket. It can be used instead of
       :func:`connect` when a socket is connected outside of asyncio.

       :param sock:
           An existing already-connected socket to run an SSH client on,
           instead of opening up a new connection.
       :param config: (optional)
           Paths to OpenSSH client configuration files to load. This
           configuration will be used as a fallback to override the
           defaults for settings which are not explicitly specified using
           AsyncSSH's configuration options. If no paths are specified and
           no config paths were set when constructing the `options`
           argument (if any), an attempt will be made to load the
           configuration from the file :file:`.ssh/config`. If this
           argument is explicitly set to `None`, no new configuration
           files will be loaded, but any configuration loaded when
           constructing the `options` argument will still apply. See
           :ref:`SupportedClientConfigOptions` for details on what
           configuration options are currently supported.
       :param options: (optional)
           Options to use when establishing the SSH client connection. These
           options can be specified either through this parameter or as direct
           keyword arguments to this function.
       :type sock: :class:`socket.socket`
       :type config: `list` of `str`
       :type options: :class:`SSHClientConnectionOptions`

       :returns: :class:`SSHClientConnection`

    """

    def conn_factory() -> SSHClientConnection:
        """Return an SSH client connection factory"""

        return SSHClientConnection(loop, new_options, wait='auth')

    loop = asyncio.get_event_loop()

    new_options = await SSHClientConnectionOptions.construct(
        options, config=config, **kwargs)

    return await asyncio.wait_for(
        _connect(new_options, config, loop, 0, sock, conn_factory,
                 'Starting SSH client on'),
        timeout=new_options.connect_timeout)


@async_context_manager
async def run_server(sock: socket.socket, config: DefTuple[ConfigPaths] = (),
                     options: Optional[SSHServerConnectionOptions] = None,
                      **kwargs: object) -> SSHServerConnection:
    """Start an SSH server connection on an already-connected socket

       This function is a coroutine which starts an SSH server on an
       existing already-connected TCP socket. It can be used instead of
       :func:`listen` when connections are accepted outside of asyncio.

       :param sock:
           An existing already-connected socket to run SSH over, instead of
           opening up a new connection.
       :param config: (optional)
           Paths to OpenSSH server configuration files to load. This
           configuration will be used as a fallback to override the
           defaults for settings which are not explicitly specified using
           AsyncSSH's configuration options. By default, no OpenSSH
           configuration files will be loaded. See
           :ref:`SupportedServerConfigOptions` for details on what
           configuration options are currently supported.
       :param options: (optional)
           Options to use when starting the reverse-direction SSH server.
           These options can be specified either through this parameter
           or as direct keyword arguments to this function.
       :type sock: :class:`socket.socket`
       :type config: `list` of `str`
       :type options: :class:`SSHServerConnectionOptions`

       :returns: :class:`SSHServerConnection`

    """

    def conn_factory() -> SSHServerConnection:
        """Return an SSH server connection factory"""

        return SSHServerConnection(loop, new_options, wait='auth')

    loop = asyncio.get_event_loop()

    new_options = await SSHServerConnectionOptions.construct(
        options, config=config, **kwargs)

    return await asyncio.wait_for(
        _connect(new_options, config, loop, 0, sock, conn_factory,
                 'Starting SSH server on'),
        timeout=new_options.connect_timeout)


@async_context_manager
async def connect(host = '', port: DefTuple[int] = (), *,
                  tunnel: DefTuple[_TunnelConnector] = (),
                  family: DefTuple[int] = (), flags: int = 0,
                  local_addr: DefTuple[HostPort] = (),
                  sock: Optional[socket.socket] = None,
                  config: DefTuple[ConfigPaths] = (),
                  options: Optional[SSHClientConnectionOptions] = None,
                  **kwargs: object) -> SSHClientConnection:
    """Make an SSH client connection

       This function is a coroutine which can be run to create an outbound SSH
       client connection to the specified host and port.

       When successful, the following steps occur:

           1. The connection is established and an instance of
              :class:`SSHClientConnection` is created to represent it.
           2. The `client_factory` is called without arguments and should
              return an instance of :class:`SSHClient` or a subclass.
           3. The client object is tied to the connection and its
              :meth:`connection_made() <SSHClient.connection_made>` method
              is called.
           4. The SSH handshake and authentication process is initiated,
              calling methods on the client object if needed.
           5. When authentication completes successfully, the client's
              :meth:`auth_completed() <SSHClient.auth_completed>` method is
              called.
           6. The coroutine returns the :class:`SSHClientConnection`. At
              this point, the connection is ready for sessions to be opened
              or port forwarding to be set up.

       If an error occurs, it will be raised as an exception and the partially
       open connection and client objects will be cleaned up.

       :param host: (optional)
           The hostname or address to connect to.
       :param port: (optional)
           The port number to connect to. If not specified, the default
           SSH port is used.
       :param tunnel: (optional)
           An existing SSH client connection that this new connection should
           be tunneled over. If set, a direct TCP/IP tunnel will be opened
           over this connection to the requested host and port rather than
           connecting directly via TCP. A string of the form
           [user@]host[:port] may also be specified, in which case a
           connection will be made to that host and then used as a tunnel.
           A comma-separated list may also be specified to establish a
           tunnel through multiple hosts.

               .. note:: When specifying tunnel as a string, any config
                         options in the call will apply only when opening
                         a connection to the final destination host and
                         port. However, settings to use when opening
                         tunnels may be specified via a configuration file.
                         To get more control of config options used to
                         open the tunnel, :func:`connect` can be called
                         explicitly, and the resulting client connection
                         can be passed as the tunnel argument.

       :param family: (optional)
           The address family to use when creating the socket. By default,
           the address family is automatically selected based on the host.
       :param flags: (optional)
           The flags to pass to getaddrinfo() when looking up the host address
       :param local_addr: (optional)
           The host and port to bind the socket to before connecting
       :param sock: (optional)
           An existing already-connected socket to run SSH over, instead of
           opening up a new connection. When this is specified, none of
           host, port family, flags, or local_addr should be specified.
       :param config: (optional)
           Paths to OpenSSH client configuration files to load. This
           configuration will be used as a fallback to override the
           defaults for settings which are not explicitly specified using
           AsyncSSH's configuration options. If no paths are specified and
           no config paths were set when constructing the `options`
           argument (if any), an attempt will be made to load the
           configuration from the file :file:`.ssh/config`. If this
           argument is explicitly set to `None`, no new configuration
           files will be loaded, but any configuration loaded when
           constructing the `options` argument will still apply. See
           :ref:`SupportedClientConfigOptions` for details on what
           configuration options are currently supported.
       :param options: (optional)
           Options to use when establishing the SSH client connection. These
           options can be specified either through this parameter or as direct
           keyword arguments to this function.
       :type host: `str`
       :type port: `int`
       :type tunnel: :class:`SSHClientConnection` or `str`
       :type family: `socket.AF_UNSPEC`, `socket.AF_INET`, or `socket.AF_INET6`
       :type flags: flags to pass to :meth:`getaddrinfo() <socket.getaddrinfo>`
       :type local_addr: tuple of `str` and `int`
       :type sock: :class:`socket.socket` or `None`
       :type config: `list` of `str`
       :type options: :class:`SSHClientConnectionOptions`

       :returns: :class:`SSHClientConnection`

    """

    def conn_factory() -> SSHClientConnection:
        """Return an SSH client connection factory"""

        return SSHClientConnection(loop, new_options, wait='auth')

    loop = asyncio.get_event_loop()

    new_options = await SSHClientConnectionOptions.construct(
        options, config=config, host=host, port=port, tunnel=tunnel,
        family=family, local_addr=local_addr, **kwargs)

    return await asyncio.wait_for(
        _connect(new_options, config, loop, flags, sock, conn_factory,
                 'Opening SSH connection to'),
        timeout=new_options.connect_timeout)


@async_context_manager
async def connect_reverse(
        host = '', port: DefTuple[int] = (), *,
        tunnel: DefTuple[_TunnelConnector] = (),
        family: DefTuple[int] = (), flags: int = 0,
        local_addr: DefTuple[HostPort] = (),
        sock: Optional[socket.socket] = None,
        config: DefTuple[ConfigPaths] = (),
        options: Optional[SSHServerConnectionOptions] = None,
        **kwargs: object) -> SSHServerConnection:
    """Create a reverse direction SSH connection

       This function is a coroutine which behaves similar to :func:`connect`,
       making an outbound TCP connection to a remote server. However, instead
       of starting up an SSH client which runs on that outbound connection,
       this function starts up an SSH server, expecting the remote system to
       start up a reverse-direction SSH client.

       Arguments to this function are the same as :func:`connect`, except
       that the `options` are of type :class:`SSHServerConnectionOptions`
       instead of :class:`SSHClientConnectionOptions`.

       :param host: (optional)
           The hostname or address to connect to.
       :param port: (optional)
           The port number to connect to. If not specified, the default
           SSH port is used.
       :param tunnel: (optional)
           An existing SSH client connection that this new connection should
           be tunneled over. If set, a direct TCP/IP tunnel will be opened
           over this connection to the requested host and port rather than
           connecting directly via TCP. A string of the form
           [user@]host[:port] may also be specified, in which case a
           connection will be made to that host and then used as a tunnel.
           A comma-separated list may also be specified to establish a
           tunnel through multiple hosts.

               .. note:: When specifying tunnel as a string, any config
                         options in the call will apply only when opening
                         a connection to the final destination host and
                         port. However, settings to use when opening
                         tunnels may be specified via a configuration file.
                         To get more control of config options used to
                         open the tunnel, :func:`connect` can be called
                         explicitly, and the resulting client connection
                         can be passed as the tunnel argument.

       :param family: (optional)
           The address family to use when creating the socket. By default,
           the address family is automatically selected based on the host.
       :param flags: (optional)
           The flags to pass to getaddrinfo() when looking up the host address
       :param local_addr: (optional)
           The host and port to bind the socket to before connecting
       :param sock: (optional)
           An existing already-connected socket to run SSH over, instead of
           opening up a new connection. When this is specified, none of
           host, port family, flags, or local_addr should be specified.
       :param config: (optional)
           Paths to OpenSSH server configuration files to load. This
           configuration will be used as a fallback to override the
           defaults for settings which are not explicitly specified using
           AsyncSSH's configuration options. By default, no OpenSSH
           configuration files will be loaded. See
           :ref:`SupportedServerConfigOptions` for details on what
           configuration options are currently supported.
       :param options: (optional)
           Options to use when starting the reverse-direction SSH server.
           These options can be specified either through this parameter
           or as direct keyword arguments to this function.
       :type host: `str`
       :type port: `int`
       :type tunnel: :class:`SSHClientConnection` or `str`
       :type family: `socket.AF_UNSPEC`, `socket.AF_INET`, or `socket.AF_INET6`
       :type flags: flags to pass to :meth:`getaddrinfo() <socket.getaddrinfo>`
       :type local_addr: tuple of `str` and `int`
       :type sock: :class:`socket.socket` or `None`
       :type config: `list` of `str`
       :type options: :class:`SSHServerConnectionOptions`

       :returns: :class:`SSHServerConnection`

    """

    def conn_factory() -> SSHServerConnection:
        """Return an SSH server connection factory"""

        return SSHServerConnection(loop, new_options, wait='auth')

    loop = asyncio.get_event_loop()

    new_options = await SSHServerConnectionOptions.construct(
        options, config=config, host=host, port=port, tunnel=tunnel,
        family=family, local_addr=local_addr, **kwargs)

    return await asyncio.wait_for(
        _connect(new_options, config, loop, flags, sock, conn_factory,
                 'Opening reverse SSH connection to'),
        timeout=new_options.connect_timeout)


@async_context_manager
async def listen(host = '', port: DefTuple[int] = (), *,
                 tunnel: DefTuple[_TunnelListener] = (),
                 family: DefTuple[int] = (), flags:int = socket.AI_PASSIVE,
                 backlog: int = 100, sock: Optional[socket.socket] = None,
                 reuse_address: bool = False, reuse_port: bool = False,
                 acceptor: _AcceptHandler = None,
                 error_handler: _ErrorHandler = None,
                 config: DefTuple[ConfigPaths] = (),
                 options: Optional[SSHServerConnectionOptions] = None,
                 **kwargs: object) -> SSHAcceptor:
    """Start an SSH server

       This function is a coroutine which can be run to create an SSH server
       listening on the specified host and port. The return value is an
       :class:`SSHAcceptor` which can be used to shut down the listener.

       :param host: (optional)
           The hostname or address to listen on. If not specified, listeners
           are created for all addresses.
       :param port: (optional)
           The port number to listen on. If not specified, the default
           SSH port is used.
       :param tunnel: (optional)
           An existing SSH client connection that this new connection should
           be tunneled over. If set, a direct TCP/IP tunnel will be opened
           over this connection to the requested host and port rather than
           connecting directly via TCP. A string of the form
           [user@]host[:port] may also be specified, in which case a
           connection will be made to that host and then used as a tunnel.
           A comma-separated list may also be specified to establish a
           tunnel through multiple hosts.

               .. note:: When specifying tunnel as a string, any config
                         options in the call will apply only when opening
                         a connection to the final destination host and
                         port. However, settings to use when opening
                         tunnels may be specified via a configuration file.
                         To get more control of config options used to
                         open the tunnel, :func:`connect` can be called
                         explicitly, and the resulting client connection
                         can be passed as the tunnel argument.

       :param family: (optional)
           The address family to use when creating the server. By default,
           the address families are automatically selected based on the host.
       :param flags: (optional)
           The flags to pass to getaddrinfo() when looking up the host
       :param backlog: (optional)
           The maximum number of queued connections allowed on listeners
       :param sock: (optional)
           A pre-existing socket to use instead of creating and binding
           a new socket. When this is specified, host and port should not
           be specified.
       :param reuse_address: (optional)
           Whether or not to reuse a local socket in the TIME_WAIT state
           without waiting for its natural timeout to expire. If not
           specified, this will be automatically set to `True` on UNIX.
       :param reuse_port: (optional)
           Whether or not to allow this socket to be bound to the same
           port other existing sockets are bound to, so long as they all
           set this flag when being created. If not specified, the
           default is to not allow this. This option is not supported
           on Windows or Python versions prior to 3.4.4.
       :param acceptor: (optional)
           A `callable` or coroutine which will be called when the
           SSH handshake completes on an accepted connection, taking
           the :class:`SSHServerConnection` as an argument.
       :param error_handler: (optional)
           A `callable` which will be called whenever the SSH handshake
           fails on an accepted connection. It is called with the failed
           :class:`SSHServerConnection` and an exception object describing
           the failure. If not specified, failed handshakes result in the
           connection object being silently cleaned up.
       :param config: (optional)
           Paths to OpenSSH server configuration files to load. This
           configuration will be used as a fallback to override the
           defaults for settings which are not explicitly specified using
           AsyncSSH's configuration options. By default, no OpenSSH
           configuration files will be loaded. See
           :ref:`SupportedServerConfigOptions` for details on what
           configuration options are currently supported.
       :param options: (optional)
           Options to use when accepting SSH server connections. These
           options can be specified either through this parameter or
           as direct keyword arguments to this function.
       :type host: `str`
       :type port: `int`
       :type tunnel: :class:`SSHClientConnection` or `str`
       :type family: `socket.AF_UNSPEC`, `socket.AF_INET`, or `socket.AF_INET6`
       :type flags: flags to pass to :meth:`getaddrinfo() <socket.getaddrinfo>`
       :type backlog: `int`
       :type sock: :class:`socket.socket` or `None`
       :type reuse_address: `bool`
       :type reuse_port: `bool`
       :type acceptor: `callable` or coroutine
       :type error_handler: `callable`
       :type config: `list` of `str`
       :type options: :class:`SSHServerConnectionOptions`

       :returns: :class:`SSHAcceptor`

    """

    def conn_factory() -> SSHServerConnection:
        """Return an SSH server connection factory"""

        return SSHServerConnection(loop, new_options, acceptor, error_handler)

    loop = asyncio.get_event_loop()

    new_options = await SSHServerConnectionOptions.construct(
        options, config=config, host=host, port=port, tunnel=tunnel,
        family=family, **kwargs)

    # pylint: disable=attribute-defined-outside-init
    new_options.proxy_command = None

    return await asyncio.wait_for(
        _listen(new_options, config, loop, flags, backlog, sock, reuse_address,
                reuse_port, conn_factory, 'Creating SSH listener on'),
        timeout=new_options.connect_timeout)


@async_context_manager
async def listen_reverse(host = '', port: DefTuple[int] = (), *,
                         tunnel: DefTuple[_TunnelListener] = (),
                         family: DefTuple[int] = (),
                         flags: int = socket.AI_PASSIVE, backlog: int = 100,
                         sock: Optional[socket.socket] = None,
                         reuse_address: bool = False, reuse_port: bool = False,
                         acceptor: _AcceptHandler = None,
                         error_handler: _ErrorHandler = None,
                         config: DefTuple[ConfigPaths] = (),
                         options: Optional[SSHClientConnectionOptions] = None,
                         **kwargs: object) -> SSHAcceptor:
    """Create a reverse-direction SSH listener

       This function is a coroutine which behaves similar to :func:`listen`,
       creating a listener which accepts inbound connections on the specified
       host and port. However, instead of starting up an SSH server on each
       inbound connection, it starts up a reverse-direction SSH client,
       expecting the remote system making the connection to start up a
       reverse-direction SSH server.

       Arguments to this function are the same as :func:`listen`, except
       that the `options` are of type :class:`SSHClientConnectionOptions`
       instead of :class:`SSHServerConnectionOptions`.

       The return value is an :class:`SSHAcceptor` which can be used to
       shut down the reverse listener.

       :param host: (optional)
           The hostname or address to listen on. If not specified, listeners
           are created for all addresses.
       :param port: (optional)
           The port number to listen on. If not specified, the default
           SSH port is used.
       :param tunnel: (optional)
           An existing SSH client connection that this new connection should
           be tunneled over. If set, a direct TCP/IP tunnel will be opened
           over this connection to the requested host and port rather than
           connecting directly via TCP. A string of the form
           [user@]host[:port] may also be specified, in which case a
           connection will be made to that host and then used as a tunnel.
           A comma-separated list may also be specified to establish a
           tunnel through multiple hosts.

               .. note:: When specifying tunnel as a string, any config
                         options in the call will apply only when opening
                         a connection to the final destination host and
                         port. However, settings to use when opening
                         tunnels may be specified via a configuration file.
                         To get more control of config options used to
                         open the tunnel, :func:`connect` can be called
                         explicitly, and the resulting client connection
                         can be passed as the tunnel argument.

       :param family: (optional)
           The address family to use when creating the server. By default,
           the address families are automatically selected based on the host.
       :param flags: (optional)
           The flags to pass to getaddrinfo() when looking up the host
       :param backlog: (optional)
           The maximum number of queued connections allowed on listeners
       :param sock: (optional)
           A pre-existing socket to use instead of creating and binding
           a new socket. When this is specified, host and port should not
       :param reuse_address: (optional)
           Whether or not to reuse a local socket in the TIME_WAIT state
           without waiting for its natural timeout to expire. If not
           specified, this will be automatically set to `True` on UNIX.
       :param reuse_port: (optional)
           Whether or not to allow this socket to be bound to the same
           port other existing sockets are bound to, so long as they all
           set this flag when being created. If not specified, the
           default is to not allow this. This option is not supported
           on Windows or Python versions prior to 3.4.4.
       :param acceptor: (optional)
           A `callable` or coroutine which will be called when the
           SSH handshake completes on an accepted connection, taking
           the :class:`SSHClientConnection` as an argument.
       :param error_handler: (optional)
           A `callable` which will be called whenever the SSH handshake
           fails on an accepted connection. It is called with the failed
           :class:`SSHClientConnection` and an exception object describing
           the failure. If not specified, failed handshakes result in the
           connection object being silently cleaned up.
       :param config: (optional)
           Paths to OpenSSH client configuration files to load. This
           configuration will be used as a fallback to override the
           defaults for settings which are not explicitly specified using
           AsyncSSH's configuration options. If no paths are specified and
           no config paths were set when constructing the `options`
           argument (if any), an attempt will be made to load the
           configuration from the file :file:`.ssh/config`. If this
           argument is explicitly set to `None`, no new configuration
           files will be loaded, but any configuration loaded when
           constructing the `options` argument will still apply. See
           :ref:`SupportedClientConfigOptions` for details on what
           configuration options are currently supported.
       :param options: (optional)
           Options to use when starting reverse-direction SSH clients.
           These options can be specified either through this parameter
           or as direct keyword arguments to this function.
       :type host: `str`
       :type port: `int`
       :type tunnel: :class:`SSHClientConnection` or `str`
       :type family: `socket.AF_UNSPEC`, `socket.AF_INET`, or `socket.AF_INET6`
       :type flags: flags to pass to :meth:`getaddrinfo() <socket.getaddrinfo>`
       :type backlog: `int`
       :type sock: :class:`socket.socket` or `None`
       :type reuse_address: `bool`
       :type reuse_port: `bool`
       :type acceptor: `callable` or coroutine
       :type error_handler: `callable`
       :type config: `list` of `str`
       :type options: :class:`SSHClientConnectionOptions`

       :returns: :class:`SSHAcceptor`

    """

    def conn_factory() -> SSHClientConnection:
        """Return an SSH client connection factory"""

        return SSHClientConnection(loop, new_options, acceptor, error_handler)

    loop = asyncio.get_event_loop()

    new_options = await SSHClientConnectionOptions.construct(
        options, config=config, host=host, port=port, tunnel=tunnel,
        family=family, **kwargs)

    # pylint: disable=attribute-defined-outside-init
    new_options.proxy_command = None

    return await asyncio.wait_for(
        _listen(new_options, config, loop, flags, backlog, sock,
                reuse_address, reuse_port, conn_factory,
                'Creating reverse direction SSH listener on'),
        timeout=new_options.connect_timeout)


async def create_connection(client_factory: _ClientFactory,
                            host = '', port: DefTuple[int] = (),
                            **kwargs: object) -> \
        Tuple[SSHClientConnection, SSHClient]:
    """Create an SSH client connection

       This is a coroutine which wraps around :func:`connect`, providing
       backward compatibility with older AsyncSSH releases. The only
       differences are that the `client_factory` argument is the first
       positional argument in this call rather than being a keyword argument
       or specified via an :class:`SSHClientConnectionOptions` object and
       the return value is a tuple of an :class:`SSHClientConnection` and
       :class:`SSHClient` rather than just the connection, mirroring
       :meth:`asyncio.AbstractEventLoop.create_connection`.

       :returns: An :class:`SSHClientConnection` and :class:`SSHClient`

    """

    conn = await connect(host, port, client_factory=client_factory,
                         **kwargs) # type: ignore

    return conn, cast(SSHClient, conn.get_owner())


@async_context_manager
async def create_server(server_factory: _ServerFactory,
                        host = '', port: DefTuple[int] = (),
                        **kwargs: object) -> SSHAcceptor:
    """Create an SSH server

       This is a coroutine which wraps around :func:`listen`, providing
       backward compatibility with older AsyncSSH releases. The only
       difference is that the `server_factory` argument is the first
       positional argument in this call rather than being a keyword argument
       or specified via an :class:`SSHServerConnectionOptions` object,
       mirroring :meth:`asyncio.AbstractEventLoop.create_server`.

    """

    return await listen(host, port, server_factory=server_factory,
                        **kwargs) # type: ignore


async def get_server_host_key(
        host = '', port: DefTuple[int] = (), *,
        tunnel: DefTuple[_TunnelConnector] = (),
        proxy_command: DefTuple[_ProxyCommand] = (), family: DefTuple[int] = (),
        flags: int = 0, local_addr: DefTuple[HostPort] = (),
        sock: Optional[socket.socket] = None,
        client_version: DefTuple[BytesOrStr] = (),
        kex_algs: _AlgsArg = (), server_host_key_algs: _AlgsArg = (),
        config: DefTuple[ConfigPaths] = (),
        options: Optional[SSHClientConnectionOptions] = None) \
            -> Optional[SSHKey]:
    """Retrieve an SSH server's host key

       This is a coroutine which can be run to connect to an SSH server and
       return the server host key presented during the SSH handshake.

       A list of server host key algorithms can be provided to specify
       which host key types the server is allowed to choose from. If the
       key exchange is successful, the server host key sent during the
       handshake is returned.

           .. note:: Not all key exchange methods involve the server
                     presenting a host key. If something like GSS key
                     exchange is used without a server host key, this
                     method may return `None` even when the handshake
                     completes.

       :param host: (optional)
           The hostname or address to connect to
       :param port: (optional)
           The port number to connect to. If not specified, the default
           SSH port is used.
       :param tunnel: (optional)
           An existing SSH client connection that this new connection should
           be tunneled over. If set, a direct TCP/IP tunnel will be opened
           over this connection to the requested host and port rather than
           connecting directly via TCP. A string of the form
           [user@]host[:port] may also be specified, in which case a
           connection will be made to that host and then used as a tunnel.
           A comma-separated list may also be specified to establish a
           tunnel through multiple hosts.

               .. note:: When specifying tunnel as a string, any config
                         options in the call will apply only when opening
                         a connection to the final destination host and
                         port. However, settings to use when opening
                         tunnels may be specified via a configuration file.
                         To get more control of config options used to
                         open the tunnel, :func:`connect` can be called
                         explicitly, and the resulting client connection
                         can be passed as the tunnel argument.

       :param proxy_command: (optional)
           A string or list of strings specifying a command and arguments
           to run to make a connection to the SSH server. Data will be
           forwarded to this process over stdin/stdout instead of opening a
           TCP connection. If specified as a string, standard shell quoting
           will be applied when splitting the command and its arguments.
       :param family: (optional)
           The address family to use when creating the socket. By default,
           the address family is automatically selected based on the host.
       :param flags: (optional)
           The flags to pass to getaddrinfo() when looking up the host address
       :param local_addr: (optional)
           The host and port to bind the socket to before connecting
       :param sock: (optional)
           An existing already-connected socket to run SSH over, instead of
           opening up a new connection. When this is specified, none of
           host, port family, flags, or local_addr should be specified.
       :param client_version: (optional)
           An ASCII string to advertise to the SSH server as the version of
           this client, defaulting to `'AsyncSSH'` and its version number.
       :param kex_algs: (optional)
           A list of allowed key exchange algorithms in the SSH handshake,
           taken from :ref:`key exchange algorithms <KexAlgs>`
       :param server_host_key_algs: (optional)
           A list of server host key algorithms to allow during the SSH
           handshake, taken from :ref:`server host key algorithms
           <PublicKeyAlgs>`.
       :param config: (optional)
           Paths to OpenSSH client configuration files to load. This
           configuration will be used as a fallback to override the
           defaults for settings which are not explicitly specified using
           AsyncSSH's configuration options. If no paths are specified and
           no config paths were set when constructing the `options`
           argument (if any), an attempt will be made to load the
           configuration from the file :file:`.ssh/config`. If this
           argument is explicitly set to `None`, no new configuration
           files will be loaded, but any configuration loaded when
           constructing the `options` argument will still apply. See
           :ref:`SupportedClientConfigOptions` for details on what
           configuration options are currently supported.
       :param options: (optional)
           Options to use when establishing the SSH client connection used
           to retrieve the server host key. These options can be specified
           either through this parameter or as direct keyword arguments to
           this function.
       :type host: `str`
       :type port: `int`
       :type tunnel: :class:`SSHClientConnection` or `str`
       :type proxy_command: `str` or `list` of `str`
       :type family: `socket.AF_UNSPEC`, `socket.AF_INET`, or `socket.AF_INET6`
       :type flags: flags to pass to :meth:`getaddrinfo() <socket.getaddrinfo>`
       :type local_addr: tuple of `str` and `int`
       :type sock: :class:`socket.socket` or `None`
       :type client_version: `str`
       :type kex_algs: `str` or `list` of `str`
       :type server_host_key_algs: `str` or `list` of `str`
       :type config: `list` of `str`
       :type options: :class:`SSHClientConnectionOptions`

       :returns: An :class:`SSHKey` public key or `None`

    """

    def conn_factory() -> SSHClientConnection:
        """Return an SSH client connection factory"""

        return SSHClientConnection(loop, new_options, wait='kex')

    loop = asyncio.get_event_loop()

    new_options = await SSHClientConnectionOptions.construct(
        options, config=config, host=host, port=port, tunnel=tunnel,
        proxy_command=proxy_command, family=family, local_addr=local_addr,
        known_hosts=None, server_host_key_algs=server_host_key_algs,
        x509_trusted_certs=None, x509_trusted_cert_paths=None,
        x509_purposes='any', gss_host=None, kex_algs=kex_algs,
        client_version=client_version)

    conn = await asyncio.wait_for(
        _connect(new_options, config, loop, flags, sock, conn_factory,
                 'Fetching server host key from'),
        timeout=new_options.connect_timeout)

    server_host_key = conn.get_server_host_key()

    conn.abort()

    await conn.wait_closed()

    return server_host_key


async def get_server_auth_methods(
        host = '', port: DefTuple[int] = (), username: DefTuple[str] = (), *,
        tunnel: DefTuple[_TunnelConnector] = (),
        proxy_command: DefTuple[_ProxyCommand] = (), family: DefTuple[int] = (),
        flags: int = 0, local_addr: DefTuple[HostPort] = (),
        sock: Optional[socket.socket] = None,
        client_version: DefTuple[BytesOrStr] = (),
        kex_algs: _AlgsArg = (), server_host_key_algs: _AlgsArg = (),
        config: DefTuple[ConfigPaths] = (),
        options: Optional[SSHClientConnectionOptions] = None) -> Sequence[str]:
    """Retrieve an SSH server's allowed auth methods

       This is a coroutine which can be run to connect to an SSH server and
       return the auth methods available to authenticate to it.

           .. note:: The key exchange with the server must complete
                     successfully before the list of available auth
                     methods can be returned, so be sure to specify any
                     arguments needed to complete the key exchange.
                     Also, auth methods may vary by user, so you may
                     want to specify the specific user you would like
                     to get auth methods for.

       :param host: (optional)
           The hostname or address to connect to
       :param port: (optional)
           The port number to connect to. If not specified, the default
           SSH port is used.
       :param username: (optional)
           Username to authenticate as on the server. If not specified,
           the currently logged in user on the local machine will be used.
       :param tunnel: (optional)
           An existing SSH client connection that this new connection should
           be tunneled over. If set, a direct TCP/IP tunnel will be opened
           over this connection to the requested host and port rather than
           connecting directly via TCP. A string of the form
           [user@]host[:port] may also be specified, in which case a
           connection will be made to that host and then used as a tunnel.
           A comma-separated list may also be specified to establish a
           tunnel through multiple hosts.

               .. note:: When specifying tunnel as a string, any config
                         options in the call will apply only when opening
                         a connection to the final destination host and
                         port. However, settings to use when opening
                         tunnels may be specified via a configuration file.
                         To get more control of config options used to
                         open the tunnel, :func:`connect` can be called
                         explicitly, and the resulting client connection
                         can be passed as the tunnel argument.

       :param proxy_command: (optional)
           A string or list of strings specifying a command and arguments
           to run to make a connection to the SSH server. Data will be
           forwarded to this process over stdin/stdout instead of opening a
           TCP connection. If specified as a string, standard shell quoting
           will be applied when splitting the command and its arguments.
       :param family: (optional)
           The address family to use when creating the socket. By default,
           the address family is automatically selected based on the host.
       :param flags: (optional)
           The flags to pass to getaddrinfo() when looking up the host address
       :param local_addr: (optional)
           The host and port to bind the socket to before connecting
       :param sock: (optional)
           An existing already-connected socket to run SSH over, instead of
           opening up a new connection. When this is specified, none of
           host, port family, flags, or local_addr should be specified.
       :param client_version: (optional)
           An ASCII string to advertise to the SSH server as the version of
           this client, defaulting to `'AsyncSSH'` and its version number.
       :param kex_algs: (optional)
           A list of allowed key exchange algorithms in the SSH handshake,
           taken from :ref:`key exchange algorithms <KexAlgs>`
       :param server_host_key_algs: (optional)
           A list of server host key algorithms to allow during the SSH
           handshake, taken from :ref:`server host key algorithms
           <PublicKeyAlgs>`.
       :param config: (optional)
           Paths to OpenSSH client configuration files to load. This
           configuration will be used as a fallback to override the
           defaults for settings which are not explicitly specified using
           AsyncSSH's configuration options. If no paths are specified and
           no config paths were set when constructing the `options`
           argument (if any), an attempt will be made to load the
           configuration from the file :file:`.ssh/config`. If this
           argument is explicitly set to `None`, no new configuration
           files will be loaded, but any configuration loaded when
           constructing the `options` argument will still apply. See
           :ref:`SupportedClientConfigOptions` for details on what
           configuration options are currently supported.
       :param options: (optional)
           Options to use when establishing the SSH client connection used
           to retrieve the server host key. These options can be specified
           either through this parameter or as direct keyword arguments to
           this function.
       :type host: `str`
       :type port: `int`
       :type tunnel: :class:`SSHClientConnection` or `str`
       :type proxy_command: `str` or `list` of `str`
       :type family: `socket.AF_UNSPEC`, `socket.AF_INET`, or `socket.AF_INET6`
       :type flags: flags to pass to :meth:`getaddrinfo() <socket.getaddrinfo>`
       :type local_addr: tuple of `str` and `int`
       :type sock: :class:`socket.socket` or `None`
       :type client_version: `str`
       :type kex_algs: `str` or `list` of `str`
       :type server_host_key_algs: `str` or `list` of `str`
       :type config: `list` of `str`
       :type options: :class:`SSHClientConnectionOptions`

       :returns: a `list` of `str`

    """

    def conn_factory() -> SSHClientConnection:
        """Return an SSH client connection factory"""

        return SSHClientConnection(loop, new_options, wait='auth_methods')

    loop = asyncio.get_event_loop()

    new_options = await SSHClientConnectionOptions.construct(
        options, config=config, host=host, port=port, username=username,
        tunnel=tunnel, proxy_command=proxy_command, family=family,
        local_addr=local_addr, known_hosts=None,
        server_host_key_algs=server_host_key_algs,
        x509_trusted_certs=None, x509_trusted_cert_paths=None,
        x509_purposes='any', gss_host=None, kex_algs=kex_algs,
        client_version=client_version)

    conn = await asyncio.wait_for(
        _connect(new_options, config, loop, flags, sock, conn_factory,
                 'Fetching server auth methods from'),
        timeout=new_options.connect_timeout)

    server_auth_methods = conn.get_server_auth_methods()

    conn.abort()

    await conn.wait_closed()

    return server_auth_methods
