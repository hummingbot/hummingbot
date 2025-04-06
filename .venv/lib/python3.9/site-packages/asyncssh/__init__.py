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

"""An asynchronous SSH2 library for Python"""

from .version import __author__, __author_email__, __url__, __version__

# pylint: disable=wildcard-import

from .constants import *

# pylint: enable=wildcard-import

from .agent import SSHAgentClient, SSHAgentKeyPair, connect_agent

from .auth_keys import SSHAuthorizedKeys
from .auth_keys import import_authorized_keys, read_authorized_keys

from .channel import SSHClientChannel, SSHServerChannel
from .channel import SSHTCPChannel, SSHUNIXChannel, SSHTunTapChannel

from .client import SSHClient

from .config import ConfigParseError

from .forward import SSHForwarder

from .connection import SSHAcceptor, SSHClientConnection, SSHServerConnection
from .connection import SSHClientConnectionOptions, SSHServerConnectionOptions
from .connection import SSHAcceptHandler
from .connection import create_connection, create_server, connect, listen
from .connection import connect_reverse, listen_reverse, get_server_host_key
from .connection import get_server_auth_methods, run_client, run_server

from .editor import SSHLineEditorChannel

from .known_hosts import SSHKnownHosts
from .known_hosts import import_known_hosts, read_known_hosts
from .known_hosts import match_known_hosts

from .listener import SSHListener

from .logging import logger, set_log_level, set_sftp_log_level, set_debug_level

from .misc import BytesOrStr
from .misc import Error, DisconnectError, ChannelOpenError, ChannelListenError
from .misc import ConnectionLost, CompressionError, HostKeyNotVerifiable
from .misc import KeyExchangeFailed, IllegalUserName, MACError
from .misc import PermissionDenied, ProtocolError, ProtocolNotSupported
from .misc import ServiceNotAvailable, PasswordChangeRequired
from .misc import BreakReceived, SignalReceived, TerminalSizeChanged

from .pbe import KeyEncryptionError

from .pkcs11 import load_pkcs11_keys

from .process import SSHServerProcessFactory
from .process import SSHClientProcess, SSHServerProcess
from .process import SSHCompletedProcess, ProcessError
from .process import TimeoutError # pylint: disable=redefined-builtin
from .process import DEVNULL, PIPE, STDOUT

from .public_key import SSHKey, SSHKeyPair, SSHCertificate
from .public_key import KeyGenerationError, KeyImportError, KeyExportError
from .public_key import generate_private_key, import_private_key
from .public_key import import_public_key, import_certificate
from .public_key import read_private_key, read_public_key, read_certificate
from .public_key import read_private_key_list, read_public_key_list
from .public_key import read_certificate_list
from .public_key import load_keypairs, load_public_keys, load_certificates
from .public_key import load_resident_keys

from .rsa import set_default_skip_rsa_key_validation

from .scp import scp

from .session import DataType, SSHClientSession, SSHServerSession
from .session import SSHTCPSession, SSHUNIXSession, SSHTunTapSession

from .server import SSHServer

from .sftp import SFTPClient, SFTPClientFile, SFTPServer, SFTPError
from .sftp import SFTPEOFError, SFTPNoSuchFile, SFTPPermissionDenied
from .sftp import SFTPFailure, SFTPBadMessage, SFTPNoConnection
from .sftp import SFTPInvalidHandle, SFTPNoSuchPath, SFTPFileAlreadyExists
from .sftp import SFTPWriteProtect, SFTPNoMedia, SFTPNoSpaceOnFilesystem
from .sftp import SFTPQuotaExceeded, SFTPUnknownPrincipal, SFTPLockConflict
from .sftp import SFTPDirNotEmpty, SFTPNotADirectory, SFTPInvalidFilename
from .sftp import SFTPLinkLoop, SFTPCannotDelete, SFTPInvalidParameter
from .sftp import SFTPFileIsADirectory, SFTPByteRangeLockConflict
from .sftp import SFTPByteRangeLockRefused, SFTPDeletePending
from .sftp import SFTPFileCorrupt, SFTPOwnerInvalid, SFTPGroupInvalid
from .sftp import SFTPNoMatchingByteRangeLock
from .sftp import SFTPConnectionLost, SFTPOpUnsupported
from .sftp import SFTPAttrs, SFTPVFSAttrs, SFTPName, SFTPLimits
from .sftp import SEEK_SET, SEEK_CUR, SEEK_END

from .stream import SSHSocketSessionFactory, SSHServerSessionFactory
from .stream import SFTPServerFactory, SSHReader, SSHWriter

from .subprocess import SSHSubprocessReadPipe, SSHSubprocessWritePipe
from .subprocess import SSHSubprocessProtocol, SSHSubprocessTransport

# Import these explicitly to trigger register calls in them
from . import sk_eddsa, sk_ecdsa, eddsa, ecdsa, rsa, dsa, kex_dh, kex_rsa

__all__ = [
    '__author__', '__author_email__', '__url__', '__version__',
    'BreakReceived', 'BytesOrStr', 'ChannelListenError',
    'ChannelOpenError', 'CompressionError', 'ConfigParseError',
    'ConnectionLost', 'DEVNULL', 'DataType', 'DisconnectError', 'Error',
    'HostKeyNotVerifiable', 'IllegalUserName', 'KeyEncryptionError',
    'KeyExchangeFailed', 'KeyExportError', 'KeyGenerationError',
    'KeyImportError', 'MACError', 'PIPE', 'PasswordChangeRequired',
    'PermissionDenied', 'ProcessError', 'ProtocolError',
    'ProtocolNotSupported', 'SEEK_CUR', 'SEEK_END', 'SEEK_SET',
    'SFTPAttrs', 'SFTPBadMessage', 'SFTPByteRangeLockConflict',
    'SFTPByteRangeLockRefused', 'SFTPCannotDelete', 'SFTPClient',
    'SFTPClientFile', 'SFTPConnectionLost', 'SFTPDeletePending',
    'SFTPDirNotEmpty', 'SFTPEOFError', 'SFTPError', 'SFTPFailure',
    'SFTPFileAlreadyExists', 'SFTPFileCorrupt', 'SFTPFileIsADirectory',
    'SFTPGroupInvalid', 'SFTPInvalidFilename', 'SFTPInvalidHandle',
    'SFTPInvalidParameter', 'SFTPLimits', 'SFTPLinkLoop', 'SFTPLockConflict',
    'SFTPName', 'SFTPNoConnection', 'SFTPNoMatchingByteRangeLock',
    'SFTPNoMedia', 'SFTPNoSpaceOnFilesystem', 'SFTPNoSuchFile',
    'SFTPNoSuchPath', 'SFTPNotADirectory', 'SFTPOpUnsupported',
    'SFTPOwnerInvalid', 'SFTPPermissionDenied', 'SFTPQuotaExceeded',
    'SFTPServer', 'SFTPServerFactory', 'SFTPUnknownPrincipal', 'SFTPVFSAttrs',
    'SFTPWriteProtect', 'SSHAcceptHandler', 'SSHAcceptor', 'SSHAgentClient',
    'SSHAgentKeyPair', 'SSHAuthorizedKeys', 'SSHCertificate', 'SSHClient',
    'SSHClientChannel', 'SSHClientConnection', 'SSHClientConnectionOptions',
    'SSHClientProcess', 'SSHClientSession', 'SSHCompletedProcess',
    'SSHForwarder', 'SSHKey', 'SSHKeyPair', 'SSHKnownHosts',
    'SSHLineEditorChannel', 'SSHListener', 'SSHReader', 'SSHServer',
    'SSHServerChannel', 'SSHServerConnection',
    'SSHServerConnectionOptions', 'SSHServerProcess',
    'SSHServerProcessFactory', 'SSHServerSession',
    'SSHServerSessionFactory', 'SSHSocketSessionFactory',
    'SSHSubprocessProtocol', 'SSHSubprocessReadPipe',
    'SSHSubprocessTransport', 'SSHSubprocessWritePipe', 'SSHTCPChannel',
    'SSHTCPSession', 'SSHTunTapChannel', 'SSHTunTapSession',
    'SSHUNIXChannel', 'SSHUNIXSession', 'SSHWriter',
    'STDOUT', 'ServiceNotAvailable', 'SignalReceived', 'TerminalSizeChanged',
    'TimeoutError', 'connect', 'connect_agent', 'connect_reverse',
    'create_connection', 'create_server', 'generate_private_key',
    'get_server_auth_methods', 'get_server_host_key',
    'import_authorized_keys', 'import_certificate', 'import_known_hosts',
    'import_private_key', 'import_public_key', 'listen', 'listen_reverse',
    'load_certificates', 'load_keypairs', 'load_pkcs11_keys',
    'load_public_keys', 'load_resident_keys', 'logger', 'match_known_hosts',
    'read_authorized_keys', 'read_certificate', 'read_certificate_list',
    'read_known_hosts', 'read_private_key', 'read_private_key_list',
    'read_public_key', 'read_public_key_list', 'run_client', 'run_server',
    'scp', 'set_debug_level', 'set_default_skip_rsa_key_validation',
    'set_log_level', 'set_sftp_log_level'
]
