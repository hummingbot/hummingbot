# Copyright (c) 2015-2024 by Ron Frederick <ronf@timeheart.net> and others.
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
#     Jonathan Slenders - proposed changes to allow SFTP server callbacks
#                         to be coroutines

"""SFTP handlers"""

import asyncio
import errno
from fnmatch import fnmatch
import inspect
import os
from os import SEEK_SET, SEEK_CUR, SEEK_END
from pathlib import PurePath
import posixpath
import stat
import sys
import time
from types import TracebackType
from typing import TYPE_CHECKING, AnyStr, AsyncIterator, Awaitable, Callable
from typing import Dict, Generic, IO, Iterable, List, Mapping, Optional
from typing import Sequence, Set, Tuple, Type, TypeVar, Union, cast, overload
from typing_extensions import Literal, Protocol, Self

from . import constants
from .constants import DEFAULT_LANG

from .constants import FXP_INIT, FXP_VERSION, FXP_OPEN, FXP_CLOSE, FXP_READ
from .constants import FXP_WRITE, FXP_LSTAT, FXP_FSTAT, FXP_SETSTAT
from .constants import FXP_FSETSTAT, FXP_OPENDIR, FXP_READDIR, FXP_REMOVE
from .constants import FXP_MKDIR, FXP_RMDIR, FXP_REALPATH, FXP_STAT, FXP_RENAME
from .constants import FXP_READLINK, FXP_SYMLINK, FXP_LINK, FXP_BLOCK
from .constants import FXP_UNBLOCK, FXP_STATUS, FXP_HANDLE, FXP_DATA
from .constants import FXP_NAME, FXP_ATTRS, FXP_EXTENDED, FXP_EXTENDED_REPLY

from .constants import FXR_OVERWRITE

from .constants import FXRP_NO_CHECK, FXRP_STAT_IF_EXISTS, FXRP_STAT_ALWAYS

from .constants import FXF_READ, FXF_WRITE, FXF_APPEND
from .constants import FXF_CREAT, FXF_TRUNC, FXF_EXCL

from .constants import FXF_ACCESS_DISPOSITION, FXF_CREATE_NEW
from .constants import FXF_CREATE_TRUNCATE, FXF_OPEN_EXISTING
from .constants import FXF_OPEN_OR_CREATE, FXF_TRUNCATE_EXISTING
from .constants import FXF_APPEND_DATA

from .constants import ACE4_READ_DATA, ACE4_WRITE_DATA, ACE4_APPEND_DATA
from .constants import ACE4_READ_ATTRIBUTES, ACE4_WRITE_ATTRIBUTES

from .constants import FILEXFER_ATTR_SIZE, FILEXFER_ATTR_UIDGID
from .constants import FILEXFER_ATTR_PERMISSIONS, FILEXFER_ATTR_ACMODTIME
from .constants import FILEXFER_ATTR_EXTENDED, FILEXFER_ATTR_DEFINED_V3

from .constants import FILEXFER_ATTR_ACCESSTIME, FILEXFER_ATTR_CREATETIME
from .constants import FILEXFER_ATTR_MODIFYTIME, FILEXFER_ATTR_ACL
from .constants import FILEXFER_ATTR_OWNERGROUP, FILEXFER_ATTR_SUBSECOND_TIMES
from .constants import FILEXFER_ATTR_DEFINED_V4

from .constants import FILEXFER_ATTR_BITS, FILEXFER_ATTR_DEFINED_V5

from .constants import FILEXFER_ATTR_ALLOCATION_SIZE, FILEXFER_ATTR_TEXT_HINT
from .constants import FILEXFER_ATTR_MIME_TYPE, FILEXFER_ATTR_LINK_COUNT
from .constants import FILEXFER_ATTR_UNTRANSLATED_NAME, FILEXFER_ATTR_CTIME
from .constants import FILEXFER_ATTR_DEFINED_V6

from .constants import FX_OK, FX_EOF, FX_NO_SUCH_FILE, FX_PERMISSION_DENIED
from .constants import FX_FAILURE, FX_BAD_MESSAGE, FX_NO_CONNECTION
from .constants import FX_CONNECTION_LOST, FX_OP_UNSUPPORTED, FX_V3_END
from .constants import FX_INVALID_HANDLE, FX_NO_SUCH_PATH
from .constants import FX_FILE_ALREADY_EXISTS, FX_WRITE_PROTECT, FX_NO_MEDIA
from .constants import FX_V4_END, FX_NO_SPACE_ON_FILESYSTEM, FX_QUOTA_EXCEEDED
from .constants import FX_UNKNOWN_PRINCIPAL, FX_LOCK_CONFLICT, FX_V5_END
from .constants import FX_DIR_NOT_EMPTY, FX_NOT_A_DIRECTORY
from .constants import FX_INVALID_FILENAME, FX_LINK_LOOP, FX_CANNOT_DELETE
from .constants import FX_INVALID_PARAMETER, FX_FILE_IS_A_DIRECTORY
from .constants import FX_BYTE_RANGE_LOCK_CONFLICT, FX_BYTE_RANGE_LOCK_REFUSED
from .constants import FX_DELETE_PENDING, FX_FILE_CORRUPT, FX_OWNER_INVALID
from .constants import FX_GROUP_INVALID, FX_NO_MATCHING_BYTE_RANGE_LOCK
from .constants import FX_V6_END

from .constants import FILEXFER_TYPE_REGULAR, FILEXFER_TYPE_DIRECTORY
from .constants import FILEXFER_TYPE_SYMLINK, FILEXFER_TYPE_SPECIAL
from .constants import FILEXFER_TYPE_UNKNOWN, FILEXFER_TYPE_SOCKET
from .constants import FILEXFER_TYPE_CHAR_DEVICE, FILEXFER_TYPE_BLOCK_DEVICE
from .constants import FILEXFER_TYPE_FIFO

from .logging import SSHLogger

from .misc import BytesOrStr, Error, FilePath, MaybeAwait, OptExcInfo, Record
from .misc import ConnectionLost
from .misc import async_context_manager, get_symbol_names, hide_empty, plural

from .packet import Boolean, Byte, String, UInt16, UInt32, UInt64
from .packet import PacketDecodeError, SSHPacket, SSHPacketLogger

from .version import __author__, __version__


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .channel import SSHServerChannel
    from .connection import SSHClientConnection, SSHServerConnection
    from .stream import SSHReader, SSHWriter


if TYPE_CHECKING:
    _RequestWaiter = asyncio.Future[Tuple[int, SSHPacket]]
else:
    _RequestWaiter = asyncio.Future

if sys.platform == 'win32': # pragma: no cover
    _LocalPath = str
else:
    _LocalPath = bytes

_SFTPFileObj = IO[bytes]
_SFTPPath = Union[bytes, FilePath]
_SFTPPaths = Union[_SFTPPath, Sequence[_SFTPPath]]
_SFTPPatList = List[Union[bytes, List[bytes]]]
_SFTPStatFunc = Callable[[_SFTPPath], Awaitable['SFTPAttrs']]

_SFTPClientFileOrPath = Union['SFTPClientFile', _SFTPPath]

_SFTPNames = Tuple[Sequence['SFTPName'], bool]
_SFTPOSAttrs = Union[os.stat_result, 'SFTPAttrs']
_SFTPOSVFSAttrs = Union[os.statvfs_result, 'SFTPVFSAttrs']

_SFTPOnErrorHandler = Optional[Callable[[Callable, bytes, OptExcInfo], None]]
_SFTPPacketHandler = Optional[Callable[['SFTPServerHandler', SSHPacket],
                              Awaitable[object]]]

SFTPErrorHandler = Union[None, Literal[False], Callable[[Exception], None]]
SFTPProgressHandler = Optional[Callable[[bytes, bytes, int, int], None]]

_T = TypeVar('_T')


MIN_SFTP_VERSION = 3
MAX_SFTP_VERSION = 6

SAFE_SFTP_READ_LEN = 16*1024                        # 16 KiB
SAFE_SFTP_WRITE_LEN = 16*1024                       # 16 KiB

MAX_SFTP_READ_LEN = 4*1024*1024                     # 4 MiB
MAX_SFTP_WRITE_LEN = 4*1024*1024                    # 4 MiB
MAX_SFTP_PACKET_LEN = MAX_SFTP_WRITE_LEN + 1024

_COPY_DATA_BLOCK_SIZE = 256*1024                    # 256 KiB

_MAX_SFTP_REQUESTS = 128
_MAX_READDIR_NAMES = 128

_NSECS_IN_SEC = 1_000_000_000


_const_dict: Mapping[str, int] = constants.__dict__

_valid_attr_flags = {
    3: FILEXFER_ATTR_DEFINED_V3,
    4: FILEXFER_ATTR_DEFINED_V4,
    5: FILEXFER_ATTR_DEFINED_V5,
    6: FILEXFER_ATTR_DEFINED_V6
}

_open_modes = {
    'r':  FXF_READ,
    'w':  FXF_WRITE | FXF_CREAT | FXF_TRUNC,
    'a':  FXF_WRITE | FXF_CREAT | FXF_APPEND,
    'x':  FXF_WRITE | FXF_CREAT | FXF_EXCL,

    'r+': FXF_READ | FXF_WRITE,
    'w+': FXF_READ | FXF_WRITE | FXF_CREAT | FXF_TRUNC,
    'a+': FXF_READ | FXF_WRITE | FXF_CREAT | FXF_APPEND,
    'x+': FXF_READ | FXF_WRITE | FXF_CREAT | FXF_EXCL
}

_file_types = {k: v.lower() for k, v in
               get_symbol_names(_const_dict, 'FILEXFER_TYPE_', 14).items()}


class _SupportsEncode(Protocol):
    """Protocol for applying encoding to path names"""

    def encode(self, sftp_version: int) -> bytes:
        """Encode result as bytes in an SSH packet"""


class _SFTPGlobProtocol(Protocol):
    """Protocol for getting files to perform glob matching against"""

    async def stat(self, path: bytes) -> 'SFTPAttrs':
        """Get attributes of a file"""

    def scandir(self, path: bytes) -> AsyncIterator['SFTPName']:
        """Return names and attributes of the files in a directory"""


class SFTPFileProtocol(Protocol):
    """Protocol for accessing a file via an SFTP server"""

    async def __aenter__(self) -> Self:
        """Allow SFTPFileProtocol to be used as an async context manager"""

    async def __aexit__(self, _exc_type: Optional[Type[BaseException]],
                        _exc_value: Optional[BaseException],
                        _traceback: Optional[TracebackType]) -> bool:
        """Wait for file close when used as an async context manager"""

    async def read(self, size: int, offset: int) -> bytes:
        """Read data from the local file"""

    async def write(self, data: bytes, offset: int) -> int:
        """Write data to the local file"""

    async def close(self) -> None:
        """Close the local file"""


class _SFTPFSProtocol(Protocol):
    """Protocol for accessing a filesystem via an SFTP server"""

    @property
    def limits(self) -> 'SFTPLimits':
        """SFTP server limits associated with this SFTP session"""

    @staticmethod
    def basename(path: bytes) -> bytes:
        """Return the final component of a POSIX-style path"""

    def encode(self, path: _SFTPPath) -> bytes:
        """Encode path name using configured path encoding"""

    def compose_path(self, path: bytes,
                     parent: Optional[bytes] = None) -> bytes:
        """Compose a path"""

    async def stat(self, path: bytes, *,
                   follow_symlinks: bool = True) -> 'SFTPAttrs':
        """Get attributes of a file, directory, or symlink"""

    async def setstat(self, path: bytes, attrs: 'SFTPAttrs', *,
                      follow_symlinks: bool = True) -> None:
        """Set attributes of a file, directory, or symlink"""

    async def isdir(self, path: bytes) -> bool:
        """Return if the path refers to a directory"""

    def scandir(self, path: bytes) -> AsyncIterator['SFTPName']:
        """Return names and attributes of the files in a directory"""

    async def mkdir(self, path: bytes) -> None:
        """Create a directory"""

    async def readlink(self, path: bytes) -> bytes:
        """Return the target of a symbolic link"""

    async def symlink(self, oldpath: bytes, newpath: bytes) -> None:
        """Create a symbolic link"""

    @async_context_manager
    async def open(self, path: bytes, mode: str,
                   block_size: int = -1) -> SFTPFileProtocol:
        """Open a file"""


def _parse_acl_supported(data: bytes) -> int:
    """Parse an SFTPv6 "acl-supported" extension"""

    packet = SSHPacket(data)
    capabilities = packet.get_uint32()
    packet.check_end()

    return capabilities


def _parse_supported(data: bytes) -> \
        Tuple[int, int, int, int, int, Sequence[bytes]]:
    """Parse an SFTPv5 "supported" extension"""

    packet = SSHPacket(data)
    attr_mask = packet.get_uint32()
    attrib_mask = packet.get_uint32()
    open_flags = packet.get_uint32()
    access_mask = packet.get_uint32()
    max_read_size = packet.get_uint32()

    ext_names: List[bytes] = []

    while packet:
        name = packet.get_string()
        ext_names.append(name)

    return (attr_mask, attrib_mask, open_flags, access_mask,
            max_read_size, ext_names)


def _parse_supported2(data: bytes) -> Tuple[int, int, int, int, int, int, int,
                                            Sequence[bytes], Sequence[bytes]]:
    """Parse an SFTPv6 "supported2" extension"""

    packet = SSHPacket(data)
    attr_mask = packet.get_uint32()
    attrib_mask = packet.get_uint32()
    open_flags = packet.get_uint32()
    access_mask = packet.get_uint32()
    max_read_size = packet.get_uint32()
    open_block_vector = packet.get_uint16()
    block_vector = packet.get_uint16()

    attrib_ext_count = packet.get_uint32()
    attrib_ext_names: List[bytes] = []

    for _ in range(attrib_ext_count):
        attrib_ext_names.append(packet.get_string())

    ext_count = packet.get_uint32()
    ext_names: List[bytes] = []

    for _ in range(ext_count):
        ext_names.append(packet.get_string())

    packet.check_end()

    return (attr_mask, attrib_mask, open_flags, access_mask,
            max_read_size, open_block_vector, block_vector,
            attrib_ext_names, ext_names)


def _parse_vendor_id(data: bytes) -> Tuple[str, str, str, int]:
    """Parse a "vendor-id" extension"""

    packet = SSHPacket(data)

    vendor_name = packet.get_string().decode('utf-8', 'backslashreplace')
    product_name = packet.get_string().decode('utf-8', 'backslashreplace')
    product_version = packet.get_string().decode('utf-8', 'backslashreplace')
    product_build = packet.get_uint64()

    return vendor_name, product_name, product_version, product_build


def _stat_mode_to_filetype(mode: int) -> int:
    """Convert stat mode/permissions to file type"""

    if stat.S_ISREG(mode):
        filetype = FILEXFER_TYPE_REGULAR
    elif stat.S_ISDIR(mode):
        filetype = FILEXFER_TYPE_DIRECTORY
    elif stat.S_ISLNK(mode):
        filetype = FILEXFER_TYPE_SYMLINK
    elif stat.S_ISSOCK(mode):
        filetype = FILEXFER_TYPE_SOCKET
    elif stat.S_ISCHR(mode):
        filetype = FILEXFER_TYPE_CHAR_DEVICE
    elif stat.S_ISBLK(mode):
        filetype = FILEXFER_TYPE_BLOCK_DEVICE
    elif stat.S_ISFIFO(mode):
        filetype = FILEXFER_TYPE_FIFO
    elif stat.S_IFMT(mode) != 0:
        filetype = FILEXFER_TYPE_SPECIAL
    else:
        filetype = FILEXFER_TYPE_UNKNOWN

    return filetype


def _nsec_to_tuple(nsec: int) -> Tuple[int, int]:
    """Convert nanoseconds since epoch to seconds & remainder"""

    return divmod(nsec, _NSECS_IN_SEC)


def _float_sec_to_tuple(sec: float) -> Tuple[int, int]:
    """Convert float seconds since epoch to seconds & remainder"""

    return (int(sec), int((sec % 1) * _NSECS_IN_SEC))


def _tuple_to_float_sec(sec: int, nsec: Optional[int]) -> float:
    """Convert seconds and remainder to float seconds since epoch"""

    return sec + float(nsec or 0) / _NSECS_IN_SEC


def _tuple_to_nsec(sec: int, nsec: Optional[int]) -> int:
    """Convert seconds and remainder to nanoseconds since epoch"""

    return sec * _NSECS_IN_SEC + (nsec or 0)


def _utime_to_attrs(times: Optional[Tuple[float, float]] = None,
                    ns: Optional[Tuple[int, int]] = None) -> 'SFTPAttrs':
    """Convert utime arguments to SFTPAttrs"""

    if ns:
        atime, atime_ns = _nsec_to_tuple(ns[0])
        mtime, mtime_ns = _nsec_to_tuple(ns[1])
    elif times:
        atime, atime_ns = _float_sec_to_tuple(times[0])
        mtime, mtime_ns = _float_sec_to_tuple(times[1])
    else:
        if hasattr(time, 'time_ns'):
            atime, atime_ns = _nsec_to_tuple(time.time_ns())
        else: # pragma: no cover
            atime, atime_ns = _float_sec_to_tuple(time.time())

        mtime, mtime_ns = atime, atime_ns

    return SFTPAttrs(atime=atime, atime_ns=atime_ns,
                     mtime=mtime, mtime_ns=mtime_ns)


def _lookup_uid(user: Optional[str]) -> Optional[int]:
    """Return the uid associated with a user name"""

    if user is not None:
        try:
            # pylint: disable=import-outside-toplevel
            import pwd
            uid = pwd.getpwnam(user).pw_uid
        except (ImportError, KeyError):
            try:
                uid = int(user)
            except ValueError:
                raise SFTPOwnerInvalid(f'Invalid owner: {user}') from None
    else:
        uid = None

    return uid


def _lookup_gid(group: Optional[str]) -> Optional[int]:
    """Return the gid associated with a group name"""

    if group is not None:
        try:
            # pylint: disable=import-outside-toplevel
            import grp
            gid = grp.getgrnam(group).gr_gid
        except (ImportError, KeyError):
            try:
                gid = int(group)
            except ValueError:
                raise SFTPGroupInvalid(f'Invalid group: {group}') from None
    else:
        gid = None

    return gid


def _lookup_user(uid: Optional[int]) -> str:
    """Return the user name associated with a uid"""

    if uid is not None:
        try:
            # pylint: disable=import-outside-toplevel
            import pwd
            user = pwd.getpwuid(uid).pw_name
        except (ImportError, KeyError):
            user = str(uid)
    else:
        user = ''

    return user


def _lookup_group(gid: Optional[int]) -> str:
    """Return the group name associated with a gid"""

    if gid is not None:
        try:
            # pylint: disable=import-outside-toplevel
            import grp
            group = grp.getgrgid(gid).gr_name
        except (ImportError, KeyError):
            group = str(gid)
    else:
        group = ''

    return group


def _mode_to_pflags(mode: str) -> Tuple[int, bool]:
    """Convert open mode to SFTP open flags"""

    if 'b' in mode:
        mode = mode.replace('b', '')
        binary = True
    else:
        binary = False

    pflags = _open_modes.get(mode)

    if not pflags:
        raise ValueError(f'Invalid mode: {mode!r}')

    return pflags, binary


def _pflags_to_flags(pflags: int) -> Tuple[int, int]:
    """Convert SFTPv3 pflags to SFTPv5 desired-access and flags"""

    desired_access = 0
    flags = 0

    if pflags & (FXF_CREAT | FXF_EXCL) == (FXF_CREAT | FXF_EXCL):
        flags = FXF_CREATE_NEW
    elif pflags & (FXF_CREAT | FXF_TRUNC) == (FXF_CREAT | FXF_TRUNC):
        flags = FXF_CREATE_TRUNCATE
    elif pflags & FXF_CREAT:
        flags = FXF_OPEN_OR_CREATE
    elif pflags & FXF_TRUNC:
        flags = FXF_TRUNCATE_EXISTING
    else:
        flags = FXF_OPEN_EXISTING

    if pflags & FXF_READ:
        desired_access |= ACE4_READ_DATA | ACE4_READ_ATTRIBUTES

    if pflags & FXF_WRITE:
        desired_access |= ACE4_WRITE_DATA | ACE4_WRITE_ATTRIBUTES

    if pflags & FXF_APPEND:
        desired_access |= ACE4_APPEND_DATA
        flags |= FXF_APPEND_DATA

    return desired_access, flags


def _from_local_path(path: _SFTPPath) -> bytes:
    """Convert local path to SFTP path"""

    path = os.fsencode(path)

    if sys.platform == 'win32': # pragma: no cover
        path = path.replace(b'\\', b'/')

        if path[:1] != b'/' and path[1:2] == b':':
            path = b'/' + path

    return path


def _to_local_path(path: bytes) -> _LocalPath:
    """Convert SFTP path to local path"""

    if sys.platform == 'win32': # pragma: no cover
        path = os.fsdecode(path)

        if path[:1] == '/' and path[2:3] == ':':
            path = path[1:]

        path = path.replace('/', '\\')
    else:
        path = os.fsencode(path)

    return path


def _setstat(path: Union[int, _SFTPPath], attrs: 'SFTPAttrs', *,
             follow_symlinks: bool = True) -> None:
    """Utility function to set file attributes"""

    if attrs.size is not None:
        os.truncate(path, attrs.size)

    uid = _lookup_uid(attrs.owner) if attrs.uid is None else attrs.uid
    gid = _lookup_gid(attrs.group) if attrs.gid is None else attrs.gid

    atime_ns = _tuple_to_nsec(attrs.atime, attrs.atime_ns) \
        if attrs.atime is not None else None

    mtime_ns = _tuple_to_nsec(attrs.mtime, attrs.mtime_ns) \
        if attrs.mtime is not None else None

    if ((atime_ns is None and mtime_ns is not None) or
            (atime_ns is not None and mtime_ns is None)):
        stat_result = os.stat(path, follow_symlinks=follow_symlinks)

        if atime_ns is None and mtime_ns is not None:
            atime_ns = stat_result.st_atime_ns

        if atime_ns is not None and mtime_ns is None:
            mtime_ns = stat_result.st_mtime_ns

    if uid is not None and gid is not None:
        try:
            os.chown(path, uid, gid, follow_symlinks=follow_symlinks)
        except NotImplementedError: # pragma: no cover
            pass
        except AttributeError: # pragma: no cover
            raise NotImplementedError from None

    if attrs.permissions is not None:
        try:
            os.chmod(path, stat.S_IMODE(attrs.permissions),
                     follow_symlinks=follow_symlinks)
        except NotImplementedError: # pragma: no cover
            pass

    if atime_ns is not None and mtime_ns is not None:
        try:
            os.utime(path, ns=(atime_ns, mtime_ns),
                     follow_symlinks=follow_symlinks)
        except NotImplementedError: # pragma: no cover
            pass


class _SFTPParallelIO(Generic[_T]):
    """Parallelize I/O requests on files

       This class issues parallel read and write requests on files.

    """

    def __init__(self, block_size: int, max_requests: int,
                 offset: int, size: int):
        self._block_size = block_size
        self._max_requests = max_requests
        self._offset = offset
        self._bytes_left = size
        self._pending: Set['asyncio.Task[Tuple[int, int, int, _T]]'] = set()

    async def _start_task(self, offset: int, size: int) -> \
                Tuple[int, int, int, _T]:
        """Start a task to perform file I/O on a particular byte range"""

        count, result = await self.run_task(offset, size)
        return offset, size, count, result

    def _start_tasks(self) -> None:
        """Create parallel file I/O tasks"""

        while self._bytes_left and len(self._pending) < self._max_requests:
            size = min(self._bytes_left, self._block_size)

            task = asyncio.ensure_future(self._start_task(self._offset, size))
            self._pending.add(task)

            self._offset += size
            self._bytes_left -= size

    async def run_task(self, offset: int, size: int) -> Tuple[int, _T]:
        """Perform file I/O on a particular byte range"""

        raise NotImplementedError

    async def iter(self) -> AsyncIterator[Tuple[int, _T]]:
        """Perform file I/O and return async iterator of results"""

        self._start_tasks()

        while self._pending:
            done, self._pending = await asyncio.wait(
                self._pending, return_when=asyncio.FIRST_COMPLETED)

            exceptions = []

            for task in done:
                try:
                    offset, size, count, result = task.result()
                    yield offset, result

                    if count and count < size:
                        self._pending.add(asyncio.ensure_future(
                            self._start_task(offset+count, size-count)))
                except SFTPEOFError:
                    self._bytes_left = 0
                except (OSError, SFTPError) as exc:
                    exceptions.append(exc)

            if exceptions:
                for task in self._pending:
                    task.cancel()

                raise exceptions[0]

            self._start_tasks()


class _SFTPFileReader(_SFTPParallelIO[bytes]):
    """Parallelized SFTP file reader"""

    def __init__(self, block_size: int, max_requests: int,
                 handler: 'SFTPClientHandler', handle: bytes,
                 offset: int, size: int):
        super().__init__(block_size, max_requests, offset, size)

        self._handler = handler
        self._handle = handle
        self._start = offset

    async def run_task(self, offset: int, size: int) -> Tuple[int, bytes]:
        """Read a block of the file"""

        data, _ = await self._handler.read(self._handle, offset, size)

        return len(data), data

    async def run(self) -> bytes:
        """Reassemble and return data from parallel reads"""

        result = bytearray()

        async for offset, data in self.iter():
            pos = offset - self._start
            pad = pos - len(result)

            if pad > 0:
                result += pad * b'\0'

            result[pos:pos+len(data)] = data

        return bytes(result)


class _SFTPFileWriter(_SFTPParallelIO[int]):
    """Parallelized SFTP file writer"""

    def __init__(self, block_size: int, max_requests: int,
                 handler: 'SFTPClientHandler', handle: bytes,
                 offset: int, data: bytes):
        super().__init__(block_size, max_requests, offset, len(data))

        self._handler = handler
        self._handle = handle
        self._start = offset
        self._data = data

    async def run_task(self, offset: int, size: int) -> Tuple[int, int]:
        """Write a block to the file"""

        pos = offset - self._start
        await self._handler.write(self._handle, offset,
                                  self._data[pos:pos+size])
        return size, size

    async def run(self):
        """Perform parallel writes"""

        async for _ in self.iter():
            pass

class _SFTPFileCopier(_SFTPParallelIO[int]):
    """SFTP file copier

       This class parforms an SFTP file copy, initiating multiple
       read and write requests to copy chunks of the file in parallel.

    """

    def __init__(self, block_size: int, max_requests: int, offset: int,
                 total_bytes: int, srcfs: _SFTPFSProtocol,
                 dstfs: _SFTPFSProtocol, srcpath: bytes, dstpath: bytes,
                 progress_handler: SFTPProgressHandler):
        super().__init__(block_size, max_requests, offset, total_bytes)

        self._srcfs = srcfs
        self._dstfs = dstfs

        self._srcpath = srcpath
        self._dstpath = dstpath

        self._src: Optional[SFTPFileProtocol] = None
        self._dst: Optional[SFTPFileProtocol] = None

        self._bytes_copied = 0
        self._total_bytes = total_bytes
        self._progress_handler = progress_handler

    async def run_task(self, offset: int, size: int) -> Tuple[int, int]:
        """Copy a block of the source file"""

        assert self._src is not None
        assert self._dst is not None

        data = await self._src.read(size, offset)
        await self._dst.write(data, offset)
        datalen = len(data)

        return datalen, datalen

    async def run(self) -> None:
        """Perform parallel file copy"""

        try:
            self._src = await self._srcfs.open(self._srcpath, 'rb',
                                               block_size=0)
            self._dst = await self._dstfs.open(self._dstpath, 'wb',
                                               block_size=0)

            if self._progress_handler and self._total_bytes == 0:
                self._progress_handler(self._srcpath, self._dstpath, 0, 0)

            if self._srcfs == self._dstfs and \
                    isinstance(self._srcfs, SFTPClient) and \
                    self._srcfs.supports_remote_copy:
                await self._srcfs.remote_copy(cast(SFTPClientFile, self._src),
                                              cast(SFTPClientFile, self._dst))

                self._bytes_copied = self._total_bytes

                if self._progress_handler:
                    self._progress_handler(self._srcpath, self._dstpath,
                                           self._bytes_copied,
                                           self._total_bytes)
            else:
                async for _, datalen in self.iter():
                    if datalen:
                        self._bytes_copied += datalen

                        if self._progress_handler:
                            self._progress_handler(self._srcpath, self._dstpath,
                                                   self._bytes_copied,
                                                   self._total_bytes)

                if self._bytes_copied != self._total_bytes:
                    exc = SFTPFailure('Unexpected EOF during file copy')

                    setattr(exc, 'filename', self._srcpath)
                    setattr(exc, 'offset', self._bytes_copied)

                    raise exc
        finally:
            if self._src: # pragma: no branch
                await self._src.close()

            if self._dst: # pragma: no branch
                await self._dst.close()


class SFTPError(Error):
    """SFTP error

       This exception is raised when an error occurs while processing
       an SFTP request. Exception codes should be taken from
       :ref:`SFTP error codes <SFTPErrorCodes>`.

       :param code:
           Disconnect reason, taken from :ref:`disconnect reason
           codes <DisconnectReasons>`
       :param reason:
           A human-readable reason for the disconnect
       :param lang: (optional)
           The language the reason is in
       :type code: `int`
       :type reason: `str`
       :type lang: `str`

    """

    @staticmethod
    def construct(packet: SSHPacket) -> Optional['SFTPError']:
        """Construct an SFTPError from an FXP_STATUS response"""

        code = packet.get_uint32()

        if packet:
            try:
                reason = packet.get_string().decode('utf-8')
                lang = packet.get_string().decode('ascii')
            except UnicodeDecodeError:
                raise SFTPBadMessage('Invalid status message') from None
        else:
            # Some servers may not always send reason and lang (usually
            # when responding with FX_OK). Tolerate this, automatically
            # filling in empty strings for them if they're not present.

            reason = ''
            lang = ''

        if code == FX_OK:
            return None
        else:
            try:
                exc = _sftp_error_map[code](reason, lang)
            except KeyError:
                exc = SFTPError(code, f'{reason} (error {code})', lang)

            exc.decode(packet)
            return exc

    def encode(self, version: int) -> bytes:
        """Encode an SFTPError as bytes in an SSHPacket"""

        if self.code == FX_NOT_A_DIRECTORY and version < 6:
            code = FX_NO_SUCH_FILE
        elif (self.code <= FX_V6_END and
                ((self.code > FX_V3_END and version <= 3) or
                 (self.code > FX_V4_END and version <= 4) or
                 (self.code > FX_V5_END and version <= 5))):
            code = FX_FAILURE
        else:
            code = self.code

        return UInt32(code) + String(self.reason) + String(self.lang)

    def decode(self, packet: SSHPacket) -> None:
        """Decode error-specific data"""

        # pylint: disable=no-self-use

        # By default, expect no error-specific data


class SFTPEOFError(SFTPError):
    """SFTP EOF error

       This exception is raised when end of file is reached when
       reading a file or directory.

       :param reason: (optional)
           Details about the EOF
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str = '', lang: str = DEFAULT_LANG):
        super().__init__(FX_EOF, reason, lang)


class SFTPNoSuchFile(SFTPError):
    """SFTP no such file

       This exception is raised when the requested file is not found.

       :param reason:
           Details about the missing file
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_NO_SUCH_FILE, reason, lang)


class SFTPPermissionDenied(SFTPError):
    """SFTP permission denied

       This exception is raised when the permissions are not available
       to perform the requested operation.

       :param reason:
           Details about the invalid permissions
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_PERMISSION_DENIED, reason, lang)


class SFTPFailure(SFTPError):
    """SFTP failure

       This exception is raised when an unexpected SFTP failure occurs.

       :param reason:
           Details about the failure
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_FAILURE, reason, lang)


class SFTPBadMessage(SFTPError):
    """SFTP bad message

       This exception is raised when an invalid SFTP message is
       received.

       :param reason:
           Details about the invalid message
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_BAD_MESSAGE, reason, lang)


class SFTPNoConnection(SFTPError):
    """SFTP no connection

       This exception is raised when an SFTP request is made on a
       closed SSH connection.

       :param reason:
           Details about the closed connection
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_NO_CONNECTION, reason, lang)


class SFTPConnectionLost(SFTPError):
    """SFTP connection lost

       This exception is raised when the SSH connection is lost or
       closed while making an SFTP request.

       :param reason:
           Details about the connection failure
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_CONNECTION_LOST, reason, lang)


class SFTPOpUnsupported(SFTPError):
    """SFTP operation unsupported

       This exception is raised when the requested SFTP operation
       is not supported.

       :param reason:
           Details about the unsupported operation
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_OP_UNSUPPORTED, reason, lang)


class SFTPInvalidHandle(SFTPError):
    """SFTP invalid handle (SFTPv4+)

       This exception is raised when the handle provided is invalid.

       :param reason:
           Details about the invalid handle
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_INVALID_HANDLE, reason, lang)


class SFTPNoSuchPath(SFTPError):
    """SFTP no such path (SFTPv4+)

       This exception is raised when the requested path is not found.

       :param reason:
           Details about the missing path
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_NO_SUCH_PATH, reason, lang)


class SFTPFileAlreadyExists(SFTPError):
    """SFTP file already exists (SFTPv4+)

       This exception is raised when the requested file already exists.

       :param reason:
           Details about the existing file
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_FILE_ALREADY_EXISTS, reason, lang)


class SFTPWriteProtect(SFTPError):
    """SFTP write protect (SFTPv4+)

       This exception is raised when a write is attempted to a file
       on read-only or write protected media.

       :param reason:
           Details about the requested file
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_WRITE_PROTECT, reason, lang)


class SFTPNoMedia(SFTPError):
    """SFTP no media (SFTPv4+)

       This exception is raised when there is no media in the
       requested drive.

       :param reason:
           Details about the requested drive
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_NO_MEDIA, reason, lang)


class SFTPNoSpaceOnFilesystem(SFTPError):
    """SFTP no space on filesystem (SFTPv5+)

       This exception is raised when there is no space available
       on the filesystem a file is being written to.

       :param reason:
           Details about the filesystem which has filled up
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_NO_SPACE_ON_FILESYSTEM, reason, lang)


class SFTPQuotaExceeded(SFTPError):
    """SFTP quota exceeded (SFTPv5+)

       This exception is raised when the user's storage quota
       is exceeded.

       :param reason:
           Details about the exceeded quota
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_QUOTA_EXCEEDED, reason, lang)


class SFTPUnknownPrincipal(SFTPError):
    """SFTP unknown principal (SFTPv5+)

       This exception is raised when a file owner or group is
       not reocgnized.

       :param reason:
           Details about the unknown principal
       :param lang: (optional)
           The language the reason is in
       :param unknown_names: (optional)
           A list of unknown principal names
       :type reason: `str`
       :type lang: `str`
       :type unknown_names: list of `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG,
                 unknown_names: Sequence[str] = ()):
        super().__init__(FX_UNKNOWN_PRINCIPAL, reason, lang)
        self.unknown_names = unknown_names

    def encode(self, version: int) -> bytes:
        """Encode an SFTPUnknownPrincipal as bytes in an SSHPacket"""

        return super().encode(version) + \
            b''.join(String(name) for name in self.unknown_names)

    def decode(self, packet: SSHPacket) -> None:
        """Decode error-specific data"""

        self.unknown_names = []

        try:
            while packet:
                self.unknown_names.append(
                    packet.get_string().decode('utf-8'))
        except UnicodeDecodeError:
            raise SFTPBadMessage('Invalid status message') from None


class SFTPLockConflict(SFTPError):
    """SFTP lock conflict (SFTPv5+)

       This exception is raised when a requested lock is held by
       another process.

       :param reason:
           Details about the conflicting lock
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_LOCK_CONFLICT, reason, lang)


class SFTPDirNotEmpty(SFTPError):
    """SFTP directory not empty (SFTPv6+)

       This exception is raised when a directory is not empty.

       :param reason:
           Details about the non-empty directory
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_DIR_NOT_EMPTY, reason, lang)


class SFTPNotADirectory(SFTPError):
    """SFTP not a directory (SFTPv6+)

       This exception is raised when a specified file is
       not a directory where one was expected.

       :param reason:
           Details about the file expected to be a directory
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_NOT_A_DIRECTORY, reason, lang)


class SFTPInvalidFilename(SFTPError):
    """SFTP invalid filename (SFTPv6+)

       This exception is raised when a filename is not valid.

       :param reason:
           Details about the invalid filename
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_INVALID_FILENAME, reason, lang)


class SFTPLinkLoop(SFTPError):
    """SFTP link loop (SFTPv6+)

       This exception is raised when a symbolic link loop is detected.

       :param reason:
           Details about the link loop
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_LINK_LOOP, reason, lang)


class SFTPCannotDelete(SFTPError):
    """SFTP cannot delete (SFTPv6+)

       This exception is raised when a file cannot be deleted.

       :param reason:
           Details about the undeletable file
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_CANNOT_DELETE, reason, lang)


class SFTPInvalidParameter(SFTPError):
    """SFTP invalid parameter (SFTPv6+)

       This exception is raised when parameters in a request are
       out of range or incompatible with one another.

       :param reason:
           Details about the invalid parameter
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_INVALID_PARAMETER, reason, lang)


class SFTPFileIsADirectory(SFTPError):
    """SFTP file is a directory (SFTPv6+)

       This exception is raised when a specified file is a
       directory where one isn't allowed.

       :param reason:
           Details about the unexpected directory
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_FILE_IS_A_DIRECTORY, reason, lang)


class SFTPByteRangeLockConflict(SFTPError):
    """SFTP byte range lock conflict (SFTPv6+)

       This exception is raised when a read or write request overlaps
       a byte range lock held by another process.

       :param reason:
           Details about the conflicting byte range lock
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_BYTE_RANGE_LOCK_CONFLICT, reason, lang)


class SFTPByteRangeLockRefused(SFTPError):
    """SFTP byte range lock refused (SFTPv6+)

       This exception is raised when a request for a byte range
       lock was refused.

       :param reason:
           Details about the refused byte range lock
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_BYTE_RANGE_LOCK_REFUSED, reason, lang)


class SFTPDeletePending(SFTPError):
    """SFTP delete pending (SFTPv6+)

       This exception is raised when an operation was attempted
       on a file for which a delete operation is pending.
       another process.

       :param reason:
           Details about the file being deleted
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_DELETE_PENDING, reason, lang)


class SFTPFileCorrupt(SFTPError):
    """SFTP file corrupt (SFTPv6+)

       This exception is raised when filesystem corruption is detected.

       :param reason:
           Details about the corrupted filesystem
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_FILE_CORRUPT, reason, lang)


class SFTPOwnerInvalid(SFTPError):
    """SFTP owner invalid (SFTPv6+)

       This exception is raised when a principal cannot be assigned
       as the owner of a file.

       :param reason:
           Details about the principal being set as a file's owner
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_OWNER_INVALID, reason, lang)


class SFTPGroupInvalid(SFTPError):
    """SFTP group invalid (SFTPv6+)

       This exception is raised when a principal cannot be assigned
       as the primary group of a file.

       :param reason:
           Details about the principal being set as a file's group
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_GROUP_INVALID, reason, lang)


class SFTPNoMatchingByteRangeLock(SFTPError):
    """SFTP no matching byte range lock (SFTPv6+)

       This exception is raised when an unlock is requested for a
       byte range lock which is not currently held.

       :param reason:
           Details about the byte range lock being released
       :param lang: (optional)
           The language the reason is in
       :type reason: `str`
       :type lang: `str`

    """

    def __init__(self, reason: str, lang: str = DEFAULT_LANG):
        super().__init__(FX_NO_MATCHING_BYTE_RANGE_LOCK, reason, lang)


_sftp_error_map: Dict[int, Callable[[str, str], SFTPError]] = {
    FX_EOF: SFTPEOFError,
    FX_NO_SUCH_FILE: SFTPNoSuchFile,
    FX_PERMISSION_DENIED: SFTPPermissionDenied,
    FX_FAILURE: SFTPFailure,
    FX_BAD_MESSAGE: SFTPBadMessage,
    FX_NO_CONNECTION: SFTPNoConnection,
    FX_CONNECTION_LOST: SFTPConnectionLost,
    FX_OP_UNSUPPORTED: SFTPOpUnsupported,
    FX_INVALID_HANDLE: SFTPInvalidHandle,
    FX_NO_SUCH_PATH: SFTPNoSuchPath,
    FX_FILE_ALREADY_EXISTS: SFTPFileAlreadyExists,
    FX_WRITE_PROTECT: SFTPWriteProtect,
    FX_NO_MEDIA: SFTPNoMedia,
    FX_NO_SPACE_ON_FILESYSTEM: SFTPNoSpaceOnFilesystem,
    FX_QUOTA_EXCEEDED: SFTPQuotaExceeded,
    FX_UNKNOWN_PRINCIPAL: SFTPUnknownPrincipal,
    FX_LOCK_CONFLICT: SFTPLockConflict,
    FX_DIR_NOT_EMPTY: SFTPDirNotEmpty,
    FX_NOT_A_DIRECTORY: SFTPNotADirectory,
    FX_INVALID_FILENAME: SFTPInvalidFilename,
    FX_LINK_LOOP: SFTPLinkLoop,
    FX_CANNOT_DELETE: SFTPCannotDelete,
    FX_INVALID_PARAMETER: SFTPInvalidParameter,
    FX_FILE_IS_A_DIRECTORY: SFTPFileIsADirectory,
    FX_BYTE_RANGE_LOCK_CONFLICT: SFTPByteRangeLockConflict,
    FX_BYTE_RANGE_LOCK_REFUSED: SFTPByteRangeLockRefused,
    FX_DELETE_PENDING: SFTPDeletePending,
    FX_FILE_CORRUPT: SFTPFileCorrupt,
    FX_OWNER_INVALID: SFTPOwnerInvalid,
    FX_GROUP_INVALID: SFTPGroupInvalid,
    FX_NO_MATCHING_BYTE_RANGE_LOCK: SFTPNoMatchingByteRangeLock
}


class SFTPAttrs(Record):
    """SFTP file attributes

       SFTPAttrs is a simple record class with the following fields:

         ============ ================================================= ======
         Field        Description                                       Type
         ============ ================================================= ======
         type         File type (SFTPv4+)                               byte
         size         File size in bytes                                uint64
         alloc_size   Allocation file size in bytes (SFTPv6+)           uint64
         uid          User id of file owner                             uint32
         gid          Group id of file owner                            uint32
         owner        User name of file owner (SFTPv4+)                 string
         group        Group name of file owner (SFTPv4+)                string
         permissions  Bit mask of POSIX file permissions                uint32
         atime        Last access time, UNIX epoch seconds              uint64
         atime_ns     Last access time, nanoseconds (SFTPv4+)           uint32
         crtime       Creation time, UNIX epoch seconds (SFTPv4+)       uint64
         crtime_ns    Creation time, nanoseconds (SFTPv4+)              uint32
         mtime        Last modify time, UNIX epoch seconds              uint64
         mtime_ns     Last modify time, nanoseconds (SFTPv4+)           uint32
         ctime        Last change time, UNIX epoch seconds (SFTPv6+)    uint64
         ctime_ns     Last change time, nanoseconds (SFTPv6+)           uint32
         acl          Access control list for file (SFTPv4+)            bytes
         attrib_bits  Attribute bits set for file (SFTPv5+)             uint32
         attrib_valid Valid attribute bits for file (SFTPv5+)           uint32
         text_hint    Text/binary hint for file (SFTPv6+)               byte
         mime_type    MIME type for file (SFTPv6+)                      string
         nlink        Link count for file (SFTPv6+)                     uint32
         untrans_name Untranslated name for file (SFTPv6+)              bytes
         ============ ================================================= ======

       Extended attributes can also be added via a field named
       `extended` which is a list of bytes name/value pairs.

       When setting attributes using an :class:`SFTPAttrs`, only fields
       which have been initialized will be changed on the selected file.

    """

    type: int = FILEXFER_TYPE_UNKNOWN
    size: Optional[int]
    alloc_size: Optional[int]
    uid: Optional[int]
    gid: Optional[int]
    owner: Optional[str]
    group: Optional[str]
    permissions: Optional[int]
    atime: Optional[int]
    atime_ns: Optional[int]
    crtime: Optional[int]
    crtime_ns: Optional[int]
    mtime: Optional[int]
    mtime_ns: Optional[int]
    ctime: Optional[int]
    ctime_ns: Optional[int]
    acl: Optional[bytes]
    attrib_bits: Optional[int]
    attrib_valid: Optional[int]
    text_hint: Optional[int]
    mime_type: Optional[str]
    nlink: Optional[int]
    untrans_name: Optional[bytes]
    extended: Sequence[Tuple[bytes, bytes]] = ()

    def _format_ns(self, k: str):
        """Convert epoch seconds & nanoseconds to a string date & time"""

        result = time.ctime(getattr(self, k))
        nsec = getattr(self, k + '_ns')

        if result and nsec:
            result = result[:19] + f'.{nsec:09d}' + result[19:]

        return result

    def _format(self, k: str, v: object) -> Optional[str]:
        """Convert attributes to more readable values"""

        if v is None or k == 'extended' and not v:
            return None

        if k == 'type':
            return _file_types.get(cast(int, v), str(v)) \
                if v != FILEXFER_TYPE_UNKNOWN else None
        elif k == 'permissions':
            return f'{cast(int, v):04o}'
        elif k in ('atime', 'crtime', 'mtime', 'ctime'):
            return self._format_ns(k)
        elif k in ('atime_ns', 'crtime_ns', 'mtime_ns', 'ctime_ns'):
            return None
        else:
            return str(v) or None

    def encode(self, sftp_version: int) -> bytes:
        """Encode SFTP attributes as bytes in an SSH packet"""

        flags = 0
        attrs = []

        if sftp_version >= 4:
            if sftp_version < 5 and self.type >= FILEXFER_TYPE_SOCKET:
                filetype = FILEXFER_TYPE_SPECIAL
            else:
                filetype = self.type

            attrs.append(Byte(filetype))

        if self.size is not None:
            flags |= FILEXFER_ATTR_SIZE
            attrs.append(UInt64(self.size))

        if self.alloc_size is not None:
            flags |= FILEXFER_ATTR_ALLOCATION_SIZE
            attrs.append(UInt64(self.alloc_size))

        if sftp_version == 3:
            if self.uid is not None and self.gid is not None:
                flags |= FILEXFER_ATTR_UIDGID
                attrs.append(UInt32(self.uid) + UInt32(self.gid))
            elif self.owner is not None and self.group is not None:
                raise ValueError('Setting owner and group requires SFTPv4 '
                                 'or later')
        else:
            if self.owner is not None and self.group is not None:
                flags |= FILEXFER_ATTR_OWNERGROUP
                attrs.append(String(self.owner) + String(self.group))
            elif self.uid is not None and self.gid is not None:
                flags |= FILEXFER_ATTR_OWNERGROUP
                attrs.append(String(str(self.uid)) + String(str(self.gid)))

        if self.permissions is not None:
            flags |= FILEXFER_ATTR_PERMISSIONS
            attrs.append(UInt32(self.permissions))

        if sftp_version == 3:
            if self.atime is not None and self.mtime is not None:
                flags |= FILEXFER_ATTR_ACMODTIME
                attrs.append(UInt32(int(self.atime)) + UInt32(int(self.mtime)))
        else:
            subsecond = (self.atime_ns is not None or
                         self.crtime_ns is not None or
                         self.mtime_ns is not None or
                         self.ctime_ns is not None)

            if subsecond:
                flags |= FILEXFER_ATTR_SUBSECOND_TIMES

            if self.atime is not None:
                flags |= FILEXFER_ATTR_ACCESSTIME
                attrs.append(UInt64(int(self.atime)))

                if subsecond:
                    attrs.append(UInt32(self.atime_ns or 0))

            if self.crtime is not None:
                flags |= FILEXFER_ATTR_CREATETIME
                attrs.append(UInt64(int(self.crtime)))

                if subsecond:
                    attrs.append(UInt32(self.crtime_ns or 0))

            if self.mtime is not None:
                flags |= FILEXFER_ATTR_MODIFYTIME
                attrs.append(UInt64(int(self.mtime)))

                if subsecond:
                    attrs.append(UInt32(self.mtime_ns or 0))

            if sftp_version >= 6 and self.ctime is not None:
                flags |= FILEXFER_ATTR_CTIME
                attrs.append(UInt64(int(self.ctime)))

                if subsecond:
                    attrs.append(UInt32(self.ctime_ns or 0))

        if sftp_version >= 4 and self.acl is not None:
            flags |= FILEXFER_ATTR_ACL
            attrs.append(String(self.acl))

        if sftp_version >= 5 and \
                self.attrib_bits is not None and \
                self.attrib_valid is not None:
            flags |= FILEXFER_ATTR_BITS
            attrs.append(UInt32(self.attrib_bits) + UInt32(self.attrib_valid))

        if sftp_version >= 6:
            if self.text_hint is not None:
                flags |= FILEXFER_ATTR_TEXT_HINT
                attrs.append(Byte(self.text_hint))

            if self.mime_type is not None:
                flags |= FILEXFER_ATTR_MIME_TYPE
                attrs.append(String(self.mime_type))

            if self.nlink is not None:
                flags |= FILEXFER_ATTR_LINK_COUNT
                attrs.append(UInt32(self.nlink))

            if self.untrans_name is not None:
                flags |= FILEXFER_ATTR_UNTRANSLATED_NAME
                attrs.append(String(self.untrans_name))

        if self.extended:
            flags |= FILEXFER_ATTR_EXTENDED
            attrs.append(UInt32(len(self.extended)))
            attrs.extend(String(type) + String(data)
                         for type, data in self.extended)

        return UInt32(flags) + b''.join(attrs)

    @classmethod
    def decode(cls, packet: SSHPacket, sftp_version: int) -> 'SFTPAttrs':
        """Decode bytes in an SSH packet as SFTP attributes"""

        flags = packet.get_uint32()
        attrs = cls()

        # Work around a bug seen in a Huawei SFTP server where
        # FILEXFER_ATTR_MODIFYTIME is included in flags, even though
        # the SFTP version is set to 3. That flag is only defined for
        # SFTPv4 and later.
        if sftp_version == 3 and flags & (FILEXFER_ATTR_ACMODTIME |
                                          FILEXFER_ATTR_MODIFYTIME):
            flags &= ~FILEXFER_ATTR_MODIFYTIME

        unsupported_attrs = flags & ~_valid_attr_flags[sftp_version]

        if unsupported_attrs:
            raise SFTPBadMessage(
                f'Unsupported attribute flags: 0x{unsupported_attrs:08x}')

        if sftp_version >= 4:
            attrs.type = packet.get_byte()

        if flags & FILEXFER_ATTR_SIZE:
            attrs.size = packet.get_uint64()

        if flags & FILEXFER_ATTR_ALLOCATION_SIZE:
            attrs.alloc_size = packet.get_uint64()

        if sftp_version == 3:
            if flags & FILEXFER_ATTR_UIDGID:
                attrs.uid = packet.get_uint32()
                attrs.gid = packet.get_uint32()
        else:
            if flags & FILEXFER_ATTR_OWNERGROUP:
                owner = packet.get_string()

                try:
                    attrs.owner = owner.decode('utf-8')
                except UnicodeDecodeError:
                    raise SFTPOwnerInvalid('Invalid owner name: ' +
                        owner.decode('utf-8', 'backslashreplace')) from None

                group = packet.get_string()

                try:
                    attrs.group = group.decode('utf-8')
                except UnicodeDecodeError:
                    raise SFTPGroupInvalid('Invalid group name: ' +
                        group.decode('utf-8', 'backslashreplace')) from None

        if flags & FILEXFER_ATTR_PERMISSIONS:
            mode = packet.get_uint32()

            if sftp_version == 3:
                attrs.type = _stat_mode_to_filetype(mode)
                attrs.permissions = mode & 0xffff
            else:
                attrs.permissions = mode & 0xfff

        if sftp_version == 3:
            if flags & FILEXFER_ATTR_ACMODTIME:
                attrs.atime = packet.get_uint32()
                attrs.mtime = packet.get_uint32()
        else:
            if flags & FILEXFER_ATTR_ACCESSTIME:
                attrs.atime = packet.get_uint64()

                if flags & FILEXFER_ATTR_SUBSECOND_TIMES:
                    attrs.atime_ns = packet.get_uint32()

            if flags & FILEXFER_ATTR_CREATETIME:
                attrs.crtime = packet.get_uint64()

                if flags & FILEXFER_ATTR_SUBSECOND_TIMES:
                    attrs.crtime_ns = packet.get_uint32()

            if flags & FILEXFER_ATTR_MODIFYTIME:
                attrs.mtime = packet.get_uint64()

                if flags & FILEXFER_ATTR_SUBSECOND_TIMES:
                    attrs.mtime_ns = packet.get_uint32()

            if flags & FILEXFER_ATTR_CTIME:
                attrs.ctime = packet.get_uint64()

                if flags & FILEXFER_ATTR_SUBSECOND_TIMES:
                    attrs.ctime_ns = packet.get_uint32()

        if flags & FILEXFER_ATTR_ACL:
            attrs.acl = packet.get_string()

        if flags & FILEXFER_ATTR_BITS:
            attrs.attrib_bits = packet.get_uint32()
            attrs.attrib_valid = packet.get_uint32()

        if flags & FILEXFER_ATTR_TEXT_HINT:
            attrs.text_hint = packet.get_byte()

        if flags & FILEXFER_ATTR_MIME_TYPE:
            try:
                attrs.mime_type = packet.get_string().decode('utf-8')
            except UnicodeDecodeError:
                raise SFTPBadMessage('Invalid MIME type') from None

        if flags & FILEXFER_ATTR_LINK_COUNT:
            attrs.nlink = packet.get_uint32()

        if flags & FILEXFER_ATTR_UNTRANSLATED_NAME:
            attrs.untrans_name = packet.get_string()

        if flags & FILEXFER_ATTR_EXTENDED:
            count = packet.get_uint32()
            attrs.extended = []

            for _ in range(count):
                attr = packet.get_string()
                data = packet.get_string()
                attrs.extended.append((attr, data))

        return attrs

    @classmethod
    def from_local(cls, result: os.stat_result) -> 'SFTPAttrs':
        """Convert from local stat attributes"""

        mode = result.st_mode
        filetype = _stat_mode_to_filetype(mode)

        if sys.platform == 'win32': # pragma: no cover
            uid = 0
            gid = 0
            owner = ''
            group = ''
        else:
            uid = result.st_uid
            gid = result.st_gid
            owner = _lookup_user(uid)
            group = _lookup_group(gid)

        atime, atime_ns = _nsec_to_tuple(result.st_atime_ns)
        mtime, mtime_ns = _nsec_to_tuple(result.st_mtime_ns)
        ctime, ctime_ns = _nsec_to_tuple(result.st_ctime_ns)

        if sys.platform == 'win32': # pragma: no cover
            crtime, crtime_ns = ctime, ctime_ns
        elif hasattr(result, 'st_birthtime'): # pragma: no cover
            crtime, crtime_ns = _float_sec_to_tuple(result.st_birthtime)
        else: # pragma: no cover
            crtime, crtime_ns = mtime, mtime_ns

        return cls(filetype, result.st_size, None, uid, gid, owner, group,
                   mode, atime, atime_ns, crtime, crtime_ns, mtime, mtime_ns,
                   ctime, ctime_ns, None, None, None, None, None,
                   result.st_nlink, None)


class SFTPVFSAttrs(Record):
    """SFTP file system attributes

       SFTPVFSAttrs is a simple record class with the following fields:

         ============ =========================================== ======
         Field        Description                                 Type
         ============ =========================================== ======
         bsize        File system block size (I/O size)           uint64
         frsize       Fundamental block size (allocation size)    uint64
         blocks       Total data blocks (in frsize units)         uint64
         bfree        Free data blocks                            uint64
         bavail       Available data blocks (for non-root)        uint64
         files        Total file inodes                           uint64
         ffree        Free file inodes                            uint64
         favail       Available file inodes (for non-root)        uint64
         fsid         File system id                              uint64
         flags        File system flags (read-only, no-setuid)    uint64
         namemax      Maximum filename length                     uint64
         ============ =========================================== ======

    """

    bsize: int = 0
    frsize: int = 0
    blocks: int = 0
    bfree: int = 0
    bavail: int = 0
    files: int = 0
    ffree: int = 0
    favail: int = 0
    fsid: int = 0
    flags: int = 0
    namemax: int = 0

    def encode(self, sftp_version: int) -> bytes:
        """Encode SFTP statvfs attributes as bytes in an SSH packet"""

        # pylint: disable=unused-argument

        return b''.join((UInt64(self.bsize), UInt64(self.frsize),
                         UInt64(self.blocks), UInt64(self.bfree),
                         UInt64(self.bavail), UInt64(self.files),
                         UInt64(self.ffree), UInt64(self.favail),
                         UInt64(self.fsid), UInt64(self.flags),
                         UInt64(self.namemax)))

    @classmethod
    def decode(cls, packet: SSHPacket, sftp_version: int) -> 'SFTPVFSAttrs':
        """Decode bytes in an SSH packet as SFTP statvfs attributes"""

        # pylint: disable=unused-argument

        vfsattrs = cls()

        vfsattrs.bsize = packet.get_uint64()
        vfsattrs.frsize = packet.get_uint64()
        vfsattrs.blocks = packet.get_uint64()
        vfsattrs.bfree = packet.get_uint64()
        vfsattrs.bavail = packet.get_uint64()
        vfsattrs.files = packet.get_uint64()
        vfsattrs.ffree = packet.get_uint64()
        vfsattrs.favail = packet.get_uint64()
        vfsattrs.fsid = packet.get_uint64()
        vfsattrs.flags = packet.get_uint64()
        vfsattrs.namemax = packet.get_uint64()

        return vfsattrs

    @classmethod
    def from_local(cls, result: os.statvfs_result) -> 'SFTPVFSAttrs':
        """Convert from local statvfs attributes"""

        return cls(result.f_bsize, result.f_frsize, result.f_blocks,
                   result.f_bfree, result.f_bavail, result.f_files,
                   result.f_ffree, result.f_favail, 0, result.f_flag,
                   result.f_namemax)


class SFTPName(Record):
    """SFTP file name and attributes

       SFTPName is a simple record class with the following fields:

         ========= ================================== ==================
         Field     Description                        Type
         ========= ================================== ==================
         filename  Filename                           `str` or `bytes`
         longname  Expanded form of filename & attrs  `str` or `bytes`
         attrs     File attributes                    :class:`SFTPAttrs`
         ========= ================================== ==================

       A list of these is returned by :meth:`readdir() <SFTPClient.readdir>`
       in :class:`SFTPClient` when retrieving the contents of a directory.

    """

    filename: BytesOrStr = ''
    longname: BytesOrStr = ''
    attrs: SFTPAttrs = SFTPAttrs()

    def _format(self, k: str, v: object) -> Optional[str]:
        """Convert name fields to more readable values"""

        if k == 'longname' and not v:
            return None

        if isinstance(v, bytes):
            v = v.decode('utf-8', 'backslashreplace')

        return str(v) or None

    def encode(self, sftp_version: int) -> bytes:
        """Encode an SFTP name as bytes in an SSH packet"""

        longname = String(self.longname) if sftp_version == 3 else b''

        return (String(self.filename) + longname +
                self.attrs.encode(sftp_version))

    @classmethod
    def decode(cls, packet: SSHPacket, sftp_version: int) -> 'SFTPName':
        """Decode bytes in an SSH packet as an SFTP name"""

        filename = packet.get_string()
        longname = packet.get_string() if sftp_version == 3 else None
        attrs = SFTPAttrs.decode(packet, sftp_version)

        return cls(filename, longname, attrs)


class SFTPLimits(Record):
    """SFTP server limits

       SFTPLimits is a simple record class with the following fields:

         ================= ========================================= ======
         Field             Description                               Type
         ================= ========================================= ======
         max_packet_len    Max allowed size of an SFTP packet        uint64
         max_read_len      Max allowed size of an SFTP read request  uint64
         max_write_len     Max allowed size of an SFTP write request uint64
         max_open_handles  Max allowed number of open file handles   uint64
         ================= ========================================= ======

    """

    max_packet_len: int
    max_read_len: int
    max_write_len: int
    max_open_handles: int

    def encode(self, sftp_version: int) -> bytes:
        """Encode SFTP server limits in an SSH packet"""

        # pylint: disable=unused-argument

        return (UInt64(self.max_packet_len) + UInt64(self.max_read_len) +
                UInt64(self.max_write_len) + UInt64(self.max_open_handles))

    @classmethod
    def decode(cls, packet: SSHPacket, sftp_version: int) -> 'SFTPLimits':
        """Decode bytes in an SSH packet as SFTP server limits"""

        # pylint: disable=unused-argument

        max_packet_len = packet.get_uint64()
        max_read_len = packet.get_uint64()
        max_write_len = packet.get_uint64()
        max_open_handles = packet.get_uint64()

        return cls(max_packet_len, max_read_len,
                   max_write_len, max_open_handles)


class SFTPGlob:
    """SFTP glob matcher"""

    def __init__(self, fs: _SFTPGlobProtocol, multiple=False):
        self._fs = fs
        self._multiple = multiple
        self._prev_matches: Set[bytes] = set()
        self._new_matches: List[SFTPName] = []
        self._matched = False
        self._stat_cache: Dict[bytes, Optional[SFTPAttrs]] = {}
        self._scandir_cache: Dict[bytes, List[SFTPName]] = {}

    def _split(self, pattern: bytes) -> Tuple[bytes, _SFTPPatList]:
        """Split out exact parts of a glob pattern"""

        patlist: _SFTPPatList = []

        if any(c in pattern for c in b'*?[]'):
            path = b''
            plain: List[bytes] = []

            for current in pattern.split(b'/'):
                if any(c in current for c in b'*?[]'):
                    if plain:
                        if patlist:
                            patlist.append(plain)
                        else:
                            path = b'/'.join(plain) or b'/'

                        plain = []

                    patlist.append(current)
                else:
                    plain.append(current)

            if plain:
                patlist.append(plain)
        else:
            path = pattern

        return path, patlist

    def _report_match(self, path, attrs):
        """Report a matching name"""

        self._matched = True

        if self._multiple:
            if path not in self._prev_matches:
                self._prev_matches.add(path)
            else:
                return

        self._new_matches.append(SFTPName(path, attrs=attrs))

    async def _stat(self, path) -> Optional[SFTPAttrs]:
        """Cache results of calls to stat"""

        try:
            return self._stat_cache[path]
        except KeyError:
            pass

        try:
            attrs = await self._fs.stat(path)
        except (SFTPNoSuchFile, SFTPPermissionDenied, SFTPNoSuchPath):
            attrs = None

        self._stat_cache[path] = attrs
        return attrs

    async def _scandir(self, path) -> AsyncIterator[SFTPName]:
        """Cache results of calls to scandir"""

        try:
            for entry in self._scandir_cache[path]:
                yield entry

            return
        except KeyError:
            pass

        entries: List[SFTPName] = []

        try:
            async for entry in self._fs.scandir(path):
                entries.append(entry)
                yield entry
        except (SFTPNoSuchFile, SFTPPermissionDenied, SFTPNoSuchPath):
            pass

        self._scandir_cache[path] = entries

    async def _match_exact(self, path: bytes, pattern: Sequence[bytes],
                           patlist: _SFTPPatList) -> None:
        """Match on an exact portion of a path"""

        newpath = posixpath.join(path, *pattern)
        newpatlist = patlist[1:]

        attrs = await self._stat(newpath)

        if attrs is None:
            return

        if newpatlist:
            if attrs.type == FILEXFER_TYPE_DIRECTORY:
                await self._match(newpath, attrs, newpatlist)
        else:
            self._report_match(newpath, attrs)

    async def _match_pattern(self, path: bytes, attrs: SFTPAttrs,
                             pattern: bytes, patlist: _SFTPPatList) -> None:
        """Match on a pattern portion of a path"""

        newpatlist = patlist[1:]

        if pattern == b'**':
            if newpatlist:
                await self._match(path, attrs, newpatlist)
            else:
                self._report_match(path, attrs)

        async for entry in self._scandir(path or b'.'):
            filename = cast(bytes, entry.filename)

            if filename in (b'.', b'..'):
                continue

            if not pattern or fnmatch(filename, pattern):
                newpath = posixpath.join(path, filename)
                attrs = entry.attrs

                if pattern == b'**' and attrs.type == FILEXFER_TYPE_DIRECTORY:
                    await self._match(newpath, attrs, patlist)
                elif newpatlist:
                    if attrs.type == FILEXFER_TYPE_DIRECTORY:
                        await self._match(newpath, attrs, newpatlist)
                else:
                    self._report_match(newpath, attrs)

    async def _match(self, path: bytes, attrs: SFTPAttrs,
                     patlist: _SFTPPatList) -> None:
        """Recursively match against a glob pattern"""

        pattern = patlist[0]

        if isinstance(pattern, list):
            await self._match_exact(path, pattern, patlist)
        else:
            await self._match_pattern(path, attrs, pattern, patlist)

    async def match(self, pattern: bytes,
                    error_handler: SFTPErrorHandler = None,
                    sftp_version = MIN_SFTP_VERSION) -> Sequence[SFTPName]:
        """Match against a glob pattern"""

        self._new_matches = []
        self._matched = False

        path, patlist = self._split(pattern)

        try:
            attrs = await self._stat(path or b'.')

            if attrs:
                if patlist:
                    if attrs.type == FILEXFER_TYPE_DIRECTORY:
                        await self._match(path, attrs, patlist)
                elif path:
                    self._report_match(path, attrs)

            if pattern and not self._matched:
                exc = SFTPNoSuchPath if sftp_version >= 4 else SFTPNoSuchFile
                raise exc('No matches found')
        except (OSError, SFTPError) as exc:
            setattr(exc, 'srcpath', pattern)

            if error_handler:
                error_handler(exc)
            else:
                raise

        return self._new_matches


class SFTPHandler(SSHPacketLogger):
    """SFTP session handler"""

    _data_pkttypes = {FXP_WRITE, FXP_DATA}

    _handler_names = get_symbol_names(_const_dict, 'FXP_')
    _realpath_check_names = get_symbol_names(_const_dict, 'FXRP_', 5)

    # SFTP implementations with broken order for SYMLINK arguments
    _nonstandard_symlink_impls = ['OpenSSH', 'paramiko']

    # Return types by message -- unlisted entries always return FXP_STATUS,
    #                            those below return FXP_STATUS on error
    _return_types = {
        FXP_OPEN:                 FXP_HANDLE,
        FXP_READ:                 FXP_DATA,
        FXP_LSTAT:                FXP_ATTRS,
        FXP_FSTAT:                FXP_ATTRS,
        FXP_OPENDIR:              FXP_HANDLE,
        FXP_READDIR:              FXP_NAME,
        FXP_REALPATH:             FXP_NAME,
        FXP_STAT:                 FXP_ATTRS,
        FXP_READLINK:             FXP_NAME,
        b'statvfs@openssh.com':   FXP_EXTENDED_REPLY,
        b'fstatvfs@openssh.com':  FXP_EXTENDED_REPLY,
        b'limits@openssh.com':    FXP_EXTENDED_REPLY
    }

    def __init__(self, reader: 'SSHReader[bytes]', writer: 'SSHWriter[bytes]'):
        self._reader: Optional['SSHReader[bytes]'] = reader
        self._writer: Optional['SSHWriter[bytes]'] = writer
        self._logger = reader.logger.get_child('sftp')

        self.limits = SFTPLimits(0, SAFE_SFTP_READ_LEN, SAFE_SFTP_WRITE_LEN, 0)

    @property
    def logger(self) -> SSHLogger:
        """A logger associated with this SFTP handler"""

        return self._logger

    async def _cleanup(self, exc: Optional[Exception]) -> None:
        """Clean up this SFTP session"""

        # pylint: disable=unused-argument

        if self._writer: # pragma: no branch
            self._writer.close()
            self._reader = None
            self._writer = None

    def _log_extensions(self, extensions: Sequence[Tuple[bytes, bytes]]):
        """Dump a formatted list of extensions to the debug log"""

        for name, data in extensions:
            if name == b'acl-supported':
                capabilities = _parse_acl_supported(data)

                self.logger.debug1('  acl-supported:')
                self.logger.debug1('    capabilities: 0x%08x', capabilities)
            elif name == b'supported':
                attr_mask, attrib_mask, open_flags, access_mask, \
                    max_read_size, ext_names = _parse_supported(data)

                self.logger.debug1('  supported:')
                self.logger.debug1('    attr_mask: 0x%08x', attr_mask)
                self.logger.debug1('    attrib_mask: 0x%08x', attrib_mask)
                self.logger.debug1('    open_flags: 0x%08x', open_flags)
                self.logger.debug1('    access_mask: 0x%08x', access_mask)
                self.logger.debug1('    max_read_size: %d', max_read_size)

                if ext_names:
                    self.logger.debug1('    extensions:')

                    for ext_name in ext_names:
                        self.logger.debug1('      %s', ext_name)
            elif name == b'supported2':
                attr_mask, attrib_mask, open_flags, access_mask, \
                    max_read_size, open_block_vector, block_vector, \
                    attrib_ext_names, ext_names = _parse_supported2(data)

                self.logger.debug1('  supported2:')
                self.logger.debug1('    attr_mask: 0x%08x', attr_mask)
                self.logger.debug1('    attrib_mask: 0x%08x', attrib_mask)
                self.logger.debug1('    open_flags: 0x%08x', open_flags)
                self.logger.debug1('    access_mask: 0x%08x', access_mask)
                self.logger.debug1('    max_read_size: %d', max_read_size)
                self.logger.debug1('    open_block_vector: 0x%04x',
                    open_block_vector)
                self.logger.debug1('    block_vector: 0x%04x', block_vector)

                if attrib_ext_names:
                    self.logger.debug1('    attrib_extensions:')

                    for attrib_ext_name in attrib_ext_names:
                        self.logger.debug1('      %s', attrib_ext_name)

                if ext_names:
                    self.logger.debug1('    extensions:')

                    for ext_name in ext_names:
                        self.logger.debug1('      %s', ext_name)
            elif name == b'vendor-id':
                vendor_name, product_name, product_version, product_build = \
                    _parse_vendor_id(data)

                self.logger.debug1('  vendor-id:')
                self.logger.debug1('    vendor_name: %s', vendor_name)
                self.logger.debug1('    product_name: %s', product_name)
                self.logger.debug1('    product_version: %s', product_version)
                self.logger.debug1('    product_build: %d', product_build)
            else:
                self.logger.debug1('  %s%s%s', name,
                                   ': ' if data else '', data)

    def _log_limits(self, limits: SFTPLimits) -> None:
        """Log SFTP server limits"""

        self.logger.debug1('  Max packet len: %d', limits.max_packet_len)
        self.logger.debug1('  Max read len: %d', limits.max_read_len)
        self.logger.debug1('  Max write len: %d', limits.max_write_len)
        self.logger.debug1('  Max open handles: %d', limits.max_open_handles)

    async def _process_packet(self, pkttype: int, pktid: int,
                              packet: SSHPacket) -> None:
        """Abstract method for processing SFTP packets"""

        raise NotImplementedError

    def send_packet(self, pkttype: int, pktid: Optional[int],
                    *args: bytes) -> None:
        """Send an SFTP packet"""

        if not self._writer:
            raise SFTPNoConnection('Connection not open')

        payload = Byte(pkttype) + b''.join(args)

        try:
            self._writer.write(UInt32(len(payload)) + payload)
        except ConnectionError as exc:
            raise SFTPConnectionLost(str(exc)) from None

        self.log_sent_packet(pkttype, pktid, payload)

    async def recv_packet(self) -> SSHPacket:
        """Receive an SFTP packet"""

        assert self._reader is not None

        pktlen = await self._reader.readexactly(4)
        pktlen = int.from_bytes(pktlen, 'big')

        packet = await self._reader.readexactly(pktlen)
        return SSHPacket(packet)

    async def recv_packets(self) -> None:
        """Receive and process SFTP packets"""

        try:
            while self._reader: # pragma: no branch
                packet = await self.recv_packet()

                pkttype = packet.get_byte()
                pktid = packet.get_uint32()

                self.log_received_packet(pkttype, pktid, packet)

                await self._process_packet(pkttype, pktid, packet)
        except PacketDecodeError as exc:
            await self._cleanup(SFTPBadMessage(str(exc)))
        except EOFError:
            await self._cleanup(None)
        except (OSError, Error) as exc:
            await self._cleanup(exc)


class SFTPClientHandler(SFTPHandler):
    """An SFTP client session handler"""

    def __init__(self, loop: asyncio.AbstractEventLoop,
                 reader: 'SSHReader[bytes]', writer: 'SSHWriter[bytes]',
                 sftp_version: int):
        super().__init__(reader, writer)

        self._loop = loop
        self._version = sftp_version
        self._next_pktid = 0
        self._requests: Dict[int, _RequestWaiter] = {}
        self._nonstandard_symlink = False
        self._supports_posix_rename = False
        self._supports_statvfs = False
        self._supports_fstatvfs = False
        self._supports_hardlink = False
        self._supports_fsync = False
        self._supports_lsetstat = False
        self._supports_limits = False
        self._supports_copy_data = False

    @property
    def version(self) -> int:
        """SFTP version associated with this SFTP session"""

        return self._version

    @property
    def supports_copy_data(self) -> bool:
        """Return whether or not SFTP remote copy is supported"""

        return self._supports_copy_data

    async def _cleanup(self, exc: Optional[Exception]) -> None:
        """Clean up this SFTP client session"""

        req_exc = exc or SFTPConnectionLost('Connection closed')

        for waiter in list(self._requests.values()):
            if not waiter.cancelled(): # pragma: no branch
                waiter.set_exception(req_exc)

        self._requests = {}

        self.logger.info('SFTP client exited%s', ': ' + str(exc) if exc else '')

        await super()._cleanup(exc)

    async def _process_packet(self, pkttype: int, pktid: int,
                              packet: SSHPacket) -> None:
        """Process incoming SFTP responses"""

        try:
            waiter = self._requests.pop(pktid)
        except KeyError:
            await self._cleanup(SFTPBadMessage('Invalid response id'))
        else:
            if not waiter.cancelled(): # pragma: no branch
                waiter.set_result((pkttype, packet))

    def _send_request(self, pkttype: Union[int, bytes], args: Sequence[bytes],
                      waiter: _RequestWaiter) -> None:
        """Send an SFTP request"""

        pktid = self._next_pktid
        self._next_pktid = (self._next_pktid + 1) & 0xffffffff

        self._requests[pktid] = waiter

        if isinstance(pkttype, bytes):
            hdr = UInt32(pktid) + String(pkttype)
            pkttype = FXP_EXTENDED
        else:
            hdr = UInt32(pktid)

        self.send_packet(pkttype, pktid, hdr, *args)

    async def _make_request(self, pkttype: Union[int, bytes],
                            *args: bytes) -> object:
        """Make an SFTP request and wait for a response"""

        waiter: _RequestWaiter = self._loop.create_future()
        self._send_request(pkttype, args, waiter)
        resptype, resp = await waiter

        return_type = self._return_types.get(pkttype)

        if resptype not in (FXP_STATUS, return_type):
            raise SFTPBadMessage(f'Unexpected response type: {resptype}')

        result = self._packet_handlers[resptype](self, resp)

        if result is not None or return_type is None:
            return result
        else:
            raise SFTPBadMessage('Unexpected FX_OK response')

    def _process_status(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP status response"""

        exc = SFTPError.construct(packet)

        if self._version < 6:
            packet.check_end()

        if exc:
            raise exc
        else:
            self.logger.debug1('Received OK')

    def _process_handle(self, packet: SSHPacket) -> bytes:
        """Process an incoming SFTP handle response"""

        handle = packet.get_string()

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received handle %s', handle.hex())

        return handle

    def _process_data(self, packet: SSHPacket) -> Tuple[bytes, bool]:
        """Process an incoming SFTP data response"""

        data = packet.get_string()
        at_end = packet.get_boolean() if packet and self._version >= 6 \
            else False

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received %s%s', plural(len(data), 'data byte'),
                           ' (at end)' if at_end else '')

        return data, at_end

    def _process_name(self, packet: SSHPacket) -> _SFTPNames:
        """Process an incoming SFTP name response"""

        count = packet.get_uint32()
        names = [SFTPName.decode(packet, self._version) for _ in range(count)]
        at_end = packet.get_boolean() if packet and self._version >= 6 \
            else False

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received %s%s', plural(len(names), 'name'),
                           ' (at end)' if at_end else '')

        for name in names:
            self.logger.debug1('  %s', name)

        return names, at_end

    def _process_attrs(self, packet: SSHPacket) -> SFTPAttrs:
        """Process an incoming SFTP attributes response"""

        attrs = SFTPAttrs().decode(packet, self._version)

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received %s', attrs)

        return attrs

    def _process_extended_reply(self, packet: SSHPacket) -> SSHPacket:
        """Process an incoming SFTP extended reply response"""

        # pylint: disable=no-self-use

        # Let the caller do the decoding for extended replies
        return packet

    _packet_handlers = {
        FXP_STATUS:         _process_status,
        FXP_HANDLE:         _process_handle,
        FXP_DATA:           _process_data,
        FXP_NAME:           _process_name,
        FXP_ATTRS:          _process_attrs,
        FXP_EXTENDED_REPLY: _process_extended_reply
    }

    async def start(self) -> None:
        """Start an SFTP client"""

        assert self._reader is not None

        self.logger.debug1('Sending init, version=%d', self._version)

        self.send_packet(FXP_INIT, None, UInt32(self._version))

        try:
            resp = await self.recv_packet()

            resptype = resp.get_byte()

            self.log_received_packet(resptype, None, resp)

            if resptype != FXP_VERSION:
                raise SFTPBadMessage('Expected version message')

            version = resp.get_uint32()

            if not MIN_SFTP_VERSION <= version <= MAX_SFTP_VERSION:
                raise SFTPBadMessage(f'Unsupported version: {version}')

            rcvd_extensions: List[Tuple[bytes, bytes]] = []

            while resp:
                name = resp.get_string()
                data = resp.get_string()
                rcvd_extensions.append((name, data))
        except PacketDecodeError as exc:
            raise SFTPBadMessage(str(exc)) from None
        except SFTPError:
            raise
        except ConnectionLost as exc:
            raise SFTPConnectionLost(str(exc)) from None
        except (asyncio.IncompleteReadError, Error) as exc:
            raise SFTPConnectionLost(str(exc)) from None

        self.logger.debug1('Received version=%d%s', version,
                           ', extensions:' if rcvd_extensions else '')

        self._log_extensions(rcvd_extensions)

        self._version = version

        for name, data in rcvd_extensions:
            if name == b'posix-rename@openssh.com' and data == b'1':
                self._supports_posix_rename = True
            elif name == b'statvfs@openssh.com' and data == b'2':
                self._supports_statvfs = True
            elif name == b'fstatvfs@openssh.com' and data == b'2':
                self._supports_fstatvfs = True
            elif name == b'hardlink@openssh.com' and data == b'1':
                self._supports_hardlink = True
            elif name == b'fsync@openssh.com' and data == b'1':
                self._supports_fsync = True
            elif name == b'lsetstat@openssh.com' and data == b'1':
                self._supports_lsetstat = True
            elif name == b'limits@openssh.com' and data == b'1':
                self._supports_limits = True
            elif name == b'copy-data' and data == b'1':
                self._supports_copy_data = True

        if version == 3:
            # Check if the server has a buggy SYMLINK implementation

            server_version = cast(str,
                self._reader.get_extra_info('server_version', ''))

            if any(name in server_version
                   for name in self._nonstandard_symlink_impls):
                self.logger.debug1('Adjusting for non-standard symlink '
                                   'implementation')
                self._nonstandard_symlink = True

    async def request_limits(self) -> None:
        """Request SFTP server limits"""

        if self._supports_limits:
            packet = cast(SSHPacket, await self._make_request(
                b'limits@openssh.com'))

            limits = SFTPLimits.decode(packet, self._version)
            packet.check_end()

            self.logger.debug1('Received server limits:')
            self._log_limits(limits)

            if limits.max_read_len:
                self.limits.max_read_len = limits.max_read_len

            if limits.max_write_len:
                self.limits.max_write_len = limits.max_write_len

    async def open(self, filename: bytes, pflags: int,
                   attrs: SFTPAttrs) -> bytes:
        """Make an SFTP open request"""

        if self._version >= 5:
            desired_access, flags = _pflags_to_flags(pflags)

            self.logger.debug1('Sending open for %s, desired_access=0x%08x, '
                               'flags=0x%08x%s', filename, desired_access,
                               flags, hide_empty(attrs))

            return cast(bytes, await self._make_request(
                FXP_OPEN, String(filename), UInt32(desired_access),
                UInt32(flags), attrs.encode(self._version)))
        else:
            self.logger.debug1('Sending open for %s, mode 0x%02x%s',
                               filename, pflags, hide_empty(attrs))

            return cast(bytes, await self._make_request(
                FXP_OPEN, String(filename), UInt32(pflags),
                attrs.encode(self._version)))

    async def open56(self, filename: bytes, desired_access: int,
                     flags: int, attrs: SFTPAttrs) -> bytes:
        """Make an SFTPv5/v6 open request"""

        self.logger.debug1('Sending open for %s, desired_access=0x%08x, '
                           'flags=0x%08x%s', filename, desired_access,
                           flags, hide_empty(attrs))

        if self._version >= 5:
            return cast(bytes, await self._make_request(
                FXP_OPEN, String(filename), UInt32(desired_access),
                UInt32(flags), attrs.encode(self._version)))
        else:
            raise SFTPOpUnsupported('SFTPv5/v6 open not supported by server')

    async def close(self, handle: bytes) -> None:
        """Make an SFTP close request"""

        self.logger.debug1('Sending close for handle %s', handle.hex())

        if self._writer:
            await self._make_request(FXP_CLOSE, String(handle))

    async def read(self, handle: bytes, offset: int,
                   length: int) -> Tuple[bytes, bool]:
        """Make an SFTP read request"""

        self.logger.debug1('Sending read for %s at offset %d in handle %s',
                           plural(length, 'byte'), offset, handle.hex())

        return cast(Tuple[bytes, bool], await self._make_request(
            FXP_READ, String(handle), UInt64(offset), UInt32(length)))

    async def write(self, handle: bytes, offset: int, data: bytes) -> int:
        """Make an SFTP write request"""

        self.logger.debug1('Sending write for %s at offset %d in handle %s',
                           plural(len(data), 'byte'), offset, handle.hex())

        return cast(int, await self._make_request(
            FXP_WRITE, String(handle), UInt64(offset), String(data)))

    async def stat(self, path: bytes, flags: int, *,
                   follow_symlinks: bool = True) -> SFTPAttrs:
        """Make an SFTP stat or lstat request"""

        if self._version >= 4:
            flag_bytes = UInt32(flags)
            flag_text = f', flags 0x{flags:08x}'
        else:
            flag_bytes = b''
            flag_text = ''

        if follow_symlinks:
            self.logger.debug1('Sending stat for %s%s', path, flag_text)

            return cast(SFTPAttrs,  await self._make_request(
                FXP_STAT, String(path), flag_bytes))
        else:
            self.logger.debug1('Sending lstat for %s%s', path, flag_text)

            return cast(SFTPAttrs,  await self._make_request(
                FXP_LSTAT, String(path), flag_bytes))

    async def lstat(self, path: bytes, flags: int) -> SFTPAttrs:
        """Make an SFTP lstat request"""

        if self._version >= 4:
            flag_bytes = UInt32(flags)
            flag_text = f', flags 0x{flags:08x}'
        else:
            flag_bytes = b''
            flag_text = ''

        self.logger.debug1('Sending lstat for %s%s', path, flag_text)

        return cast(SFTPAttrs, await self._make_request(
            FXP_LSTAT, String(path), flag_bytes))

    async def fstat(self, handle: bytes, flags: int) -> SFTPAttrs:
        """Make an SFTP fstat request"""

        if self._version >= 4:
            flag_bytes = UInt32(flags)
            flag_text = f', flags 0x{flags:08x}'
        else:
            flag_bytes = b''
            flag_text = ''

        self.logger.debug1('Sending fstat for handle %s%s',
                           handle.hex(), flag_text)

        return cast(SFTPAttrs, await self._make_request(
            FXP_FSTAT, String(handle), flag_bytes))

    async def setstat(self, path: bytes, attrs: SFTPAttrs, *,
                      follow_symlinks: bool = True) -> None:
        """Make an SFTP setstat or lsetstat request"""

        if follow_symlinks:
            self.logger.debug1('Sending setstat for %s%s',
                               path, hide_empty(attrs))

            await self._make_request(FXP_SETSTAT, String(path),
                                     attrs.encode(self._version))
        elif self._supports_lsetstat:
            self.logger.debug1('Sending lsetstat for %s%s',
                               path, hide_empty(attrs))

            await self._make_request(b'lsetstat@openssh.com', String(path),
                                     attrs.encode(self._version))
        else:
            raise SFTPOpUnsupported('lsetstat not supported by server')

    async def fsetstat(self, handle: bytes, attrs: SFTPAttrs) -> None:
        """Make an SFTP fsetstat request"""

        self.logger.debug1('Sending fsetstat for handle %s%s',
                           handle.hex(), hide_empty(attrs))

        await self._make_request(FXP_FSETSTAT, String(handle),
                                 attrs.encode(self._version))

    async def statvfs(self, path: bytes) -> SFTPVFSAttrs:
        """Make an SFTP statvfs request"""

        if self._supports_statvfs:
            self.logger.debug1('Sending statvfs for %s', path)

            packet = cast(SSHPacket, await self._make_request(
                b'statvfs@openssh.com', String(path)))

            vfsattrs = SFTPVFSAttrs.decode(packet, self._version)
            packet.check_end()

            self.logger.debug1('Received %s', vfsattrs)

            return vfsattrs
        else:
            raise SFTPOpUnsupported('statvfs not supported')

    async def fstatvfs(self, handle: bytes) -> SFTPVFSAttrs:
        """Make an SFTP fstatvfs request"""

        if self._supports_fstatvfs:
            self.logger.debug1('Sending fstatvfs for handle %s', handle.hex())

            packet = cast(SSHPacket, await self._make_request(
                b'fstatvfs@openssh.com', String(handle)))

            vfsattrs = SFTPVFSAttrs.decode(packet, self._version)
            packet.check_end()

            self.logger.debug1('Received %s', vfsattrs)

            return vfsattrs
        else:
            raise SFTPOpUnsupported('fstatvfs not supported')

    async def remove(self, path: bytes) -> None:
        """Make an SFTP remove request"""

        self.logger.debug1('Sending remove for %s', path)

        await self._make_request(FXP_REMOVE, String(path))

    async def rename(self, oldpath: bytes, newpath: bytes, flags: int) -> None:
        """Make an SFTP rename request"""

        if self._version >= 5:
            self.logger.debug1('Sending rename request from %s to %s%s',
                               oldpath, newpath, f', flags=0x{flags:x}'
                               if flags else '')

            await self._make_request(FXP_RENAME, String(oldpath),
                                     String(newpath), UInt32(flags))
        elif flags and self._supports_posix_rename:
            self.logger.debug1('Sending OpenSSH POSIX rename request '
                               'from %s to %s', oldpath, newpath)

            await self._make_request(b'posix-rename@openssh.com',
                                     String(oldpath), String(newpath))
        elif not flags:
            self.logger.debug1('Sending rename request from %s to %s',
                               oldpath, newpath)

            await self._make_request(FXP_RENAME, String(oldpath),
                                     String(newpath))
        else:
            raise SFTPOpUnsupported('Rename with overwrite not supported')

    async def posix_rename(self, oldpath: bytes, newpath: bytes) -> None:
        """Make an SFTP POSIX rename request"""

        if self._supports_posix_rename:
            self.logger.debug1('Sending OpenSSH POSIX rename request '
                               'from %s to %s', oldpath, newpath)

            await self._make_request(b'posix-rename@openssh.com',
                                     String(oldpath), String(newpath))
        elif self._version >= 5:
            self.logger.debug1('Sending rename request from %s to %s '
                               'with overwrite', oldpath, newpath)

            await self._make_request(FXP_RENAME, String(oldpath),
                                     String(newpath), UInt32(FXR_OVERWRITE))
        else:
            raise SFTPOpUnsupported('POSIX rename not supported')

    async def opendir(self, path: bytes) -> bytes:
        """Make an SFTP opendir request"""

        self.logger.debug1('Sending opendir for %s', path)

        return cast(bytes, await self._make_request(
            FXP_OPENDIR, String(path)))

    async def readdir(self, handle: bytes) -> _SFTPNames:
        """Make an SFTP readdir request"""

        self.logger.debug1('Sending readdir for handle %s', handle.hex())

        return  cast(_SFTPNames, await self._make_request(
            FXP_READDIR, String(handle)))

    async def mkdir(self, path: bytes, attrs: SFTPAttrs) -> None:
        """Make an SFTP mkdir request"""

        self.logger.debug1('Sending mkdir for %s', path)

        await self._make_request(FXP_MKDIR, String(path),
                                 attrs.encode(self._version))

    async def rmdir(self, path: bytes) -> None:
        """Make an SFTP rmdir request"""

        self.logger.debug1('Sending rmdir for %s', path)

        await self._make_request(FXP_RMDIR, String(path))

    async def realpath(self, path: bytes, *compose_paths: bytes,
                       check: int = FXRP_NO_CHECK) -> _SFTPNames:
        """Make an SFTP realpath request"""

        if check == FXRP_NO_CHECK:
            checkmsg = ''
        else:
            try:
                checkmsg = f', check={self._realpath_check_names[check]}'
            except KeyError:
                checkmsg = f', check={check}'

        self.logger.debug1('Sending realpath of %s%s%s', path,
                           b', compose_path: ' + b', '.join(compose_paths)
                           if compose_paths else b'', checkmsg)

        if self._version >= 6:
            return cast(_SFTPNames, await self._make_request(
                FXP_REALPATH, String(path), Byte(check),
                *map(String, compose_paths)))
        else:
            return cast(_SFTPNames, await self._make_request(
                FXP_REALPATH, String(path)))

    async def readlink(self, path: bytes) -> _SFTPNames:
        """Make an SFTP readlink request"""

        self.logger.debug1('Sending readlink for %s', path)

        return cast(_SFTPNames, await self._make_request(
            FXP_READLINK, String(path)))

    async def symlink(self, oldpath: bytes, newpath: bytes) -> None:
        """Make an SFTP symlink request"""

        self.logger.debug1('Sending symlink request from %s to %s',
                           oldpath, newpath)

        if self._version >= 6:
            await self._make_request(FXP_LINK, String(newpath),
                                     String(oldpath), Boolean(True))
        else:
            if self._nonstandard_symlink:
                args = String(oldpath) + String(newpath)
            else:
                args = String(newpath) + String(oldpath)

            await self._make_request(FXP_SYMLINK, args)

    async def link(self, oldpath: bytes, newpath: bytes) -> None:
        """Make an SFTP hard link request"""

        if self._version >= 6 or self._supports_hardlink:
            self.logger.debug1('Sending hardlink request from %s to %s',
                               oldpath, newpath)

            if self._version >= 6:
                await self._make_request(FXP_LINK, String(newpath),
                                         String(oldpath), Boolean(False))
            else:
                await self._make_request(b'hardlink@openssh.com',
                                         String(oldpath), String(newpath))
        else:
            raise SFTPOpUnsupported('link not supported')

    async def lock(self, handle: bytes, offset: int, length: int,
                   flags: int) -> None:
        """Make an SFTP byte range lock request"""

        if self._version >= 6:
            self.logger.debug1('Sending byte range lock request for '
                               'handle %s, offset %d, length %d, '
                               'flags 0x%04x', handle.hex(), offset,
                               length, flags)

            await self._make_request(FXP_BLOCK, String(handle),
                                     UInt64(offset), UInt64(length),
                                     UInt32(flags))
        else:
            raise SFTPOpUnsupported('Byte range locks not supported')

    async def unlock(self, handle: bytes, offset: int, length: int) -> None:
        """Make an SFTP byte range unlock request"""

        if self._version >= 6:
            self.logger.debug1('Sending byte range unlock request for '
                               'handle %s, offset %d, length %d',
                               handle.hex(), offset, length)

            await self._make_request(FXP_UNBLOCK, String(handle),
                                     UInt64(offset), UInt64(length))
        else:
            raise SFTPOpUnsupported('Byte range locks not supported')

    async def fsync(self, handle: bytes) -> None:
        """Make an SFTP fsync request"""

        if self._supports_fsync:
            self.logger.debug1('Sending fsync for handle %s', handle.hex())

            await self._make_request(b'fsync@openssh.com', String(handle))
        else:
            raise SFTPOpUnsupported('fsync not supported')

    async def copy_data(self, read_from_handle: bytes, read_from_offset: int,
                        read_from_length: int, write_to_handle: bytes,
                        write_to_offset: int) -> None:
        """Make an SFTP copy data request"""

        if self._supports_copy_data:
            self.logger.debug1('Sending copy-data from handle %s, '
                               'offset %d, length %d to handle %s, '
                               'offset %d', read_from_handle.hex(),
                               read_from_offset, read_from_length,
                               write_to_handle.hex(), write_to_offset)

            await self._make_request(b'copy-data', String(read_from_handle),
                                     UInt64(read_from_offset),
                                     UInt64(read_from_length),
                                     String(write_to_handle),
                                     UInt64(write_to_offset))
        else:
            raise SFTPOpUnsupported('copy-data not supported')

    def exit(self) -> None:
        """Handle a request to close the SFTP session"""

        if self._writer:
            self._writer.write_eof()

    async def wait_closed(self) -> None:
        """Wait for this SFTP session to close"""

        if self._writer:
            await self._writer.channel.wait_closed()


class SFTPClientFile:
    """SFTP client remote file object

       This class represents an open file on a remote SFTP server. It
       is opened with the :meth:`open() <SFTPClient.open>` method on the
       :class:`SFTPClient` class and provides methods to read and write
       data and get and set attributes on the open file.

    """

    def __init__(self, handler: SFTPClientHandler, handle: bytes,
                 appending: bool, encoding: Optional[str], errors: str,
                 block_size: int, max_requests: int):
        self._handler = handler
        self._handle: Optional[bytes] = handle
        self._appending = appending
        self._encoding = encoding
        self._errors = errors
        self._offset = None if appending else 0

        self.read_len = \
            handler.limits.max_read_len if block_size == -1 else block_size
        self.write_len = \
            handler.limits.max_write_len if block_size == -1 else block_size

        if max_requests <= 0:
            if self.read_len:
                max_requests = max(16, min(MAX_SFTP_READ_LEN //
                                           self.read_len, 128))
            else:
                max_requests = 1

        self._max_requests = max_requests

    async def __aenter__(self) -> Self:
        """Allow SFTPClientFile to be used as an async context manager"""

        return self

    async def __aexit__(self, _exc_type: Optional[Type[BaseException]],
                        _exc_value: Optional[BaseException],
                        _traceback: Optional[TracebackType]) -> bool:
        """Wait for file close when used as an async context manager"""

        await self.close()
        return False

    @property
    def handle(self) -> bytes:
        """Return handle or raise an error if clsoed"""

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        return self._handle

    async def _end(self) -> int:
        """Return the offset of the end of the file"""

        attrs = await self.stat()
        return attrs.size or 0

    async def read(self, size: int = -1,
                   offset: Optional[int] = None) -> AnyStr:
        """Read data from the remote file

           This method reads and returns up to `size` bytes of data
           from the remote file. If size is negative, all data up to
           the end of the file is returned.

           If offset is specified, the read will be performed starting
           at that offset rather than the current file position. This
           argument should be provided if you want to issue parallel
           reads on the same file, since the file position is not
           predictable in that case.

           Data will be returned as a string if an encoding was set when
           the file was opened. Otherwise, data is returned as bytes.

           An empty `str` or `bytes` object is returned when at EOF.

           :param size:
               The number of bytes to read
           :param offset: (optional)
               The offset from the beginning of the file to begin reading
           :type size: `int`
           :type offset: `int`

           :returns: data read from the file, as a `str` or `bytes`

           :raises: | :exc:`ValueError` if the file has been closed
                    | :exc:`UnicodeDecodeError` if the data can't be
                      decoded using the requested encoding
                    | :exc:`SFTPError` if the server returns an error

        """

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        if offset is None:
            offset = self._offset

        # If self._offset is None, we're appending and haven't sought
        # backward in the file since the last write, so there's no
        # data to return

        data = b''

        if offset is not None:
            if size is None or size < 0:
                size = (await self._end()) - offset

            try:
                if self.read_len and size > \
                        min(self.read_len, self._handler.limits.max_read_len):
                    data = await _SFTPFileReader(
                        self.read_len, self._max_requests, self._handler,
                        self._handle, offset, size).run()
                else:
                    data, _ = await self._handler.read(self._handle,
                                                       offset, size)

                self._offset = offset + len(data)
            except SFTPEOFError:
                pass

        if self._encoding:
            return cast(AnyStr, data.decode(self._encoding, self._errors))
        else:
            return cast(AnyStr, data)

    async def read_parallel(self, size: int = -1,
                            offset: Optional[int] = None) -> \
            AsyncIterator[Tuple[int, bytes]]:
        """Read parallel blocks of data from the remote file

           This method reads and returns up to `size` bytes of data
           from the remote file. If size is negative, all data up to
           the end of the file is returned.

           If offset is specified, the read will be performed starting
           at that offset rather than the current file position.

           Data is returned as a series of tuples delivered by an
           async iterator, where each tuple contains an offset and
           data bytes. Encoding is ignored here, since multi-byte
           characters may be split across block boundaries.

           To maximize performance, multiple reads are issued in
           parallel, and data blocks may be returned out of order.
           The size of the blocks and the maximum number of
           outstanding read requests can be controlled using
           the `block_size` and `max_requests` arguments passed
           in the call to the :meth:`open() <SFTPClient.open>`
           method on the :class:`SFTPClient` class.

           :param size:
               The number of bytes to read
           :param offset: (optional)
               The offset from the beginning of the file to begin reading
           :type size: `int`
           :type offset: `int`

           :returns: an async iterator of tuples of offset and data bytes

           :raises: | :exc:`ValueError` if the file has been closed
                    | :exc:`SFTPError` if the server returns an error

        """

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        if offset is None:
            offset = self._offset

        # If self._offset is None, we're appending and haven't sought
        # backward in the file since the last write, so there's no
        # data to return

        if offset is not None:
            if size is None or size < 0:
                size = (await self._end()) - offset
        else:
            offset = 0
            size = 0

        return _SFTPFileReader(self.read_len, self._max_requests,
                               self._handler, self._handle, offset,
                               size).iter()

    async def write(self, data: AnyStr, offset: Optional[int] = None) -> int:
        """Write data to the remote file

           This method writes the specified data at the current
           position in the remote file.

           :param data:
               The data to write to the file
           :param offset: (optional)
               The offset from the beginning of the file to begin writing
           :type data: `str` or `bytes`
           :type offset: `int`

           If offset is specified, the write will be performed starting
           at that offset rather than the current file position. This
           argument should be provided if you want to issue parallel
           writes on the same file, since the file position is not
           predictable in that case.

           :returns: number of bytes written

           :raises: | :exc:`ValueError` if the file has been closed
                    | :exc:`UnicodeEncodeError` if the data can't be
                      encoded using the requested encoding
                    | :exc:`SFTPError` if the server returns an error

        """

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        if offset is None:
            # Offset is ignored when appending, so fill in an offset of 0
            # if we don't have a current file position
            offset = self._offset or 0

        if self._encoding:
            data_bytes = cast(str, data).encode(self._encoding, self._errors)
        else:
            data_bytes = cast(bytes, data)

        datalen = len(data_bytes)

        if self.write_len and datalen > self.write_len:
            await _SFTPFileWriter(
                self.write_len, self._max_requests, self._handler,
                self._handle, offset, data_bytes).run()
        else:
            await self._handler.write(self._handle, offset, data_bytes)

        self._offset = None if self._appending else offset + datalen
        return datalen

    async def seek(self, offset: int, from_what: int = SEEK_SET) -> int:
        """Seek to a new position in the remote file

           This method changes the position in the remote file. The
           `offset` passed in is treated as relative to the beginning
           of the file if `from_what` is set to `SEEK_SET` (the
           default), relative to the current file position if it is
           set to `SEEK_CUR`, or relative to the end of the file
           if it is set to `SEEK_END`.

           :param offset:
               The amount to seek
           :param from_what: (optional)
               The reference point to use
           :type offset: `int`
           :type from_what: `SEEK_SET`, `SEEK_CUR`, or `SEEK_END`

           :returns: The new byte offset from the beginning of the file

        """

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        if from_what == SEEK_SET:
            self._offset = offset
        elif from_what == SEEK_CUR:
            if self._offset is None:
                self._offset = (await self._end()) + offset
            else:
                self._offset += offset
        elif from_what == SEEK_END:
            self._offset = (await self._end()) + offset
        else:
            raise ValueError('Invalid reference point')

        return self._offset

    async def tell(self) -> int:
        """Return the current position in the remote file

           This method returns the current position in the remote file.

           :returns: The current byte offset from the beginning of the file

        """

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        if self._offset is None:
            self._offset = await self._end()

        return self._offset

    async def stat(self, flags = FILEXFER_ATTR_DEFINED_V4) -> SFTPAttrs:
        """Return file attributes of the remote file

           This method queries file attributes of the currently open file.

           :param flags: (optional)
               Flags indicating attributes of interest (SFTPv4 or later)
           :type flags: `int`

           :returns: An :class:`SFTPAttrs` containing the file attributes

           :raises: :exc:`SFTPError` if the server returns an error

        """

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        return await self._handler.fstat(self._handle, flags)

    async def setstat(self, attrs: SFTPAttrs) -> None:
        """Set attributes of the remote file

           This method sets file attributes of the currently open file.

           :param attrs:
               File attributes to set on the file
           :type attrs: :class:`SFTPAttrs`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        await self._handler.fsetstat(self._handle, attrs)

    async def statvfs(self) -> SFTPVFSAttrs:
        """Return file system attributes of the remote file

           This method queries attributes of the file system containing
           the currently open file.

           :returns: An :class:`SFTPVFSAttrs` containing the file system
                     attributes

           :raises: :exc:`SFTPError` if the server doesn't support this
                    extension or returns an error

        """

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        return await self._handler.fstatvfs(self._handle)

    async def truncate(self, size: Optional[int] = None) -> None:
        """Truncate the remote file to the specified size

           This method changes the remote file's size to the specified
           value. If a size is not provided, the current file position
           is used.

           :param size: (optional)
               The desired size of the file, in bytes
           :type size: `int`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        if size is None:
            size = self._offset

        await self.setstat(SFTPAttrs(size=size))

    @overload
    async def chown(self, uid: int, gid: int) -> None: ... # pragma: no cover

    @overload
    async def chown(self, owner: str,
                    group: str) -> None: ... # pragma: no cover

    async def chown(self, uid_or_owner = None, gid_or_group = None,
                    uid = None, gid = None, owner = None, group = None):
        """Change the owner user and group of the remote file

           This method changes the user and group of the currently open file.

           :param uid:
               The new user id to assign to the file
           :param gid:
               The new group id to assign to the file
           :param owner:
               The new owner to assign to the file (SFTPv4 only)
           :param group:
               The new group to assign to the file (SFTPv4 only)
           :type uid: `int`
           :type gid: `int`
           :type owner: `str`
           :type group: `str`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        if isinstance(uid_or_owner, int):
            uid = uid_or_owner
        elif isinstance(uid_or_owner, str):
            owner = uid_or_owner

        if isinstance(gid_or_group, int):
            gid = gid_or_group
        elif isinstance(gid_or_group, str):
            group = gid_or_group

        await self.setstat(SFTPAttrs(uid=uid, gid=gid,
                                     owner=owner, group=group))

    async def chmod(self, mode: int) -> None:
        """Change the file permissions of the remote file

           This method changes the permissions of the currently
           open file.

           :param mode:
               The new file permissions, expressed as an int
           :type mode: `int`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        await self.setstat(SFTPAttrs(permissions=mode))

    async def utime(self, times: Optional[Tuple[float, float]] = None,
                    ns: Optional[Tuple[int, int]] = None) -> None:
        """Change the access and modify times of the remote file

           This method changes the access and modify times of the
           currently open file. If `times` is not provided,
           the times will be changed to the current time.

           :param times: (optional)
               The new access and modify times, as seconds relative to
               the UNIX epoch
           :param ns: (optional)
               The new access and modify times, as nanoseconds relative to
               the UNIX epoch
           :type times: tuple of two `int` or `float` values
           :type ns: tuple of two `int` values

           :raises: :exc:`SFTPError` if the server returns an error

        """

        await self.setstat(_utime_to_attrs(times, ns))

    async def lock(self, offset: int, length: int, flags: int) -> None:
        """Acquire a byte range lock on the remote file"""

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        await self._handler.lock(self._handle, offset, length, flags)

    async def unlock(self, offset: int, length: int) -> None:
        """Release a byte range lock on the remote file"""

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        await self._handler.unlock(self._handle, offset, length)

    async def fsync(self) -> None:
        """Force the remote file data to be written to disk"""

        if self._handle is None:
            raise ValueError('I/O operation on closed file')

        await self._handler.fsync(self._handle)

    async def close(self) -> None:
        """Close the remote file"""

        if self._handle:
            await self._handler.close(self._handle)
            self._handle = None


class SFTPClient:
    """SFTP client

       This class represents the client side of an SFTP session. It is
       started by calling the :meth:`start_sftp_client()
       <SSHClientConnection.start_sftp_client>` method on the
       :class:`SSHClientConnection` class.

    """

    def __init__(self, handler: SFTPClientHandler,
                 path_encoding: Optional[str], path_errors: str):
        self._handler = handler
        self._path_encoding = path_encoding
        self._path_errors = path_errors
        self._cwd: Optional[bytes] = None

    async def __aenter__(self) -> Self:
        """Allow SFTPClient to be used as an async context manager"""

        return self

    async def __aexit__(self, _exc_type: Optional[Type[BaseException]],
                        _exc_value: Optional[BaseException],
                        _traceback: Optional[TracebackType]) -> bool:
        """Wait for client close when used as an async context manager"""

        self.exit()
        await self.wait_closed()
        return False

    @property
    def logger(self) -> SSHLogger:
        """A logger associated with this SFTP client"""

        return self._handler.logger

    @property
    def version(self) -> int:
        """SFTP version associated with this SFTP session"""

        return self._handler.version

    @property
    def limits(self) -> SFTPLimits:
        """:class:`SFTPLimits` associated with this SFTP session"""

        return self._handler.limits

    @property
    def supports_remote_copy(self) -> bool:
        """Return whether or not SFTP remote copy is supported"""

        return self._handler.supports_copy_data

    @staticmethod
    def basename(path: bytes) -> bytes:
        """Return the final component of a POSIX-style path"""

        return posixpath.basename(path)

    def encode(self, path: _SFTPPath) -> bytes:
        """Encode path name using configured path encoding

           This method has no effect if the path is already bytes.

        """

        if isinstance(path, PurePath):
            path = str(path)

        if isinstance(path, str):
            if self._path_encoding:
                path = path.encode(self._path_encoding, self._path_errors)
            else:
                raise SFTPBadMessage('Path must be bytes when '
                                     'encoding is not set')

        return path

    def decode(self, path: bytes, want_string: bool = True) -> BytesOrStr:
        """Decode path name using configured path encoding

           This method has no effect if want_string is set to `False`.

        """

        if want_string and self._path_encoding:
            try:
                return path.decode(self._path_encoding, self._path_errors)
            except UnicodeDecodeError:
                raise SFTPBadMessage('Unable to decode name') from None

        return path

    def compose_path(self, path: _SFTPPath,
                     parent: Optional[bytes] = None) -> bytes:
        """Compose a path

           If parent is not specified, return a path relative to the
           current remote working directory.

        """

        if parent is None:
            parent = self._cwd

        path = self.encode(path)

        return posixpath.join(parent, path) if parent else path

    async def _type(self, path: _SFTPPath,
                    statfunc: Optional[_SFTPStatFunc] = None) -> int:
        """Return the file type of a remote path, or FILEXFER_TYPE_UNKNOWN
           if it can't be accessed"""

        if statfunc is None:
            statfunc = self.stat

        try:
            return (await statfunc(path)).type
        except (SFTPNoSuchFile, SFTPNoSuchPath, SFTPPermissionDenied):
            return FILEXFER_TYPE_UNKNOWN

    async def _copy(self, srcfs: _SFTPFSProtocol, dstfs: _SFTPFSProtocol,
                    srcpath: bytes, dstpath: bytes, srcattrs: SFTPAttrs,
                    preserve: bool, recurse: bool, follow_symlinks: bool,
                    block_size: int, max_requests: int,
                    progress_handler: SFTPProgressHandler,
                    error_handler: SFTPErrorHandler,
                    remote_only: bool) -> None:
        """Copy a file, directory, or symbolic link"""

        try:
            filetype = srcattrs.type

            if follow_symlinks and filetype == FILEXFER_TYPE_SYMLINK:
                srcattrs = await srcfs.stat(srcpath)
                filetype = srcattrs.type

            if filetype == FILEXFER_TYPE_DIRECTORY:
                if not recurse:
                    exc = SFTPFileIsADirectory if self.version >= 6 \
                        else SFTPFailure

                    raise exc(srcpath.decode('utf-8', 'backslashreplace') +
                              ' is a directory')

                self.logger.info('  Starting copy of directory %s to %s',
                                 srcpath, dstpath)

                if not await dstfs.isdir(dstpath):
                    await dstfs.mkdir(dstpath)

                async for srcname in srcfs.scandir(srcpath):
                    filename = cast(bytes, srcname.filename)

                    if filename in (b'.', b'..'):
                        continue

                    srcfile = posixpath.join(srcpath, filename)
                    dstfile = posixpath.join(dstpath, filename)

                    await self._copy(srcfs, dstfs, srcfile, dstfile,
                                     srcname.attrs, preserve, recurse,
                                     follow_symlinks, block_size, max_requests,
                                     progress_handler, error_handler,
                                     remote_only)

                self.logger.info('  Finished copy of directory %s to %s',
                                 srcpath, dstpath)

            elif filetype == FILEXFER_TYPE_SYMLINK:
                targetpath = await srcfs.readlink(srcpath)

                self.logger.info('  Copying symlink %s to %s', srcpath, dstpath)
                self.logger.info('    Target path: %s', targetpath)

                await dstfs.symlink(targetpath, dstpath)
            else:
                self.logger.info('  Copying file %s to %s', srcpath, dstpath)

                if remote_only and not self.supports_remote_copy:
                    raise SFTPOpUnsupported('Remote copy not supported')

                await _SFTPFileCopier(block_size, max_requests, 0,
                                      srcattrs.size or 0, srcfs, dstfs,
                                      srcpath, dstpath, progress_handler).run()

            if preserve:
                attrs = await srcfs.stat(srcpath,
                                         follow_symlinks=follow_symlinks)

                attrs = SFTPAttrs(permissions=attrs.permissions,
                                  atime=attrs.atime, atime_ns=attrs.atime_ns,
                                  mtime=attrs.mtime, mtime_ns=attrs.mtime_ns)

                try:
                    await dstfs.setstat(dstpath, attrs,
                                        follow_symlinks=follow_symlinks or
                                        filetype != FILEXFER_TYPE_SYMLINK)

                    self.logger.info('    Preserved attrs: %s', attrs)
                except SFTPOpUnsupported:
                    self.logger.info('    Preserving symlink attrs unsupported')

        except (OSError, SFTPError) as exc:
            setattr(exc, 'srcpath', srcpath)
            setattr(exc, 'dstpath', dstpath)

            if error_handler:
                error_handler(exc)
            else:
                raise

    async def _begin_copy(self, srcfs: _SFTPFSProtocol, dstfs: _SFTPFSProtocol,
                          srcpaths: _SFTPPaths, dstpath: Optional[_SFTPPath],
                          copy_type: str, expand_glob: bool, preserve: bool,
                          recurse: bool, follow_symlinks: bool,
                          block_size: int, max_requests: int,
                          progress_handler: SFTPProgressHandler,
                          error_handler: SFTPErrorHandler,
                          remote_only: bool = False) -> None:
        """Begin a new file upload, download, or copy"""

        if block_size <= 0:
            block_size = min(srcfs.limits.max_read_len,
                             dstfs.limits.max_write_len)

        if max_requests <= 0:
            max_requests = max(16, min(MAX_SFTP_READ_LEN // block_size, 128))

        if isinstance(srcpaths, (bytes, str, PurePath)):
            srcpaths = [srcpaths]
        elif not isinstance(srcpaths, list):
            srcpaths = list(srcpaths)

        self.logger.info('Starting SFTP %s of %s to %s',
                         copy_type, srcpaths, dstpath)

        srcnames: List[SFTPName] = []

        if expand_glob:
            glob = SFTPGlob(srcfs, len(srcpaths) > 1)

            for srcpath in srcpaths:
                srcnames.extend(await glob.match(srcfs.encode(srcpath),
                                                 error_handler, self.version))
        else:
            for srcpath in srcpaths:
                srcpath = srcfs.encode(srcpath)
                srcattrs = await srcfs.stat(srcpath,
                                            follow_symlinks=follow_symlinks)
                srcnames.append(SFTPName(srcpath, attrs=srcattrs))

        if dstpath:
            dstpath = dstfs.encode(dstpath)

        dstpath: Optional[bytes]

        dst_isdir = dstpath is None or (await dstfs.isdir(dstpath))

        if len(srcnames) > 1 and not dst_isdir:
            assert dstpath is not None
            exc = SFTPNotADirectory if self.version >= 6 else SFTPFailure

            raise exc(dstpath.decode('utf-8', 'backslashreplace') +
                      ' must be a directory')

        for srcname in srcnames:
            srcfile = cast(bytes, srcname.filename)
            basename = srcfs.basename(srcfile)

            if dstpath is None:
                dstfile = basename
            elif dst_isdir:
                dstfile = dstfs.compose_path(basename, parent=dstpath)
            else:
                dstfile = dstpath

            await self._copy(srcfs, dstfs, srcfile, dstfile, srcname.attrs,
                             preserve, recurse, follow_symlinks, block_size,
                             max_requests, progress_handler, error_handler,
                             remote_only)

    async def get(self, remotepaths: _SFTPPaths,
                  localpath: Optional[_SFTPPath] = None, *,
                  preserve: bool = False, recurse: bool = False,
                  follow_symlinks: bool = False, block_size: int = -1,
                  max_requests: int = -1,
                  progress_handler: SFTPProgressHandler = None,
                  error_handler: SFTPErrorHandler = None) -> None:
        """Download remote files

           This method downloads one or more files or directories from
           the remote system. Either a single remote path or a sequence
           of remote paths to download can be provided.

           When downloading a single file or directory, the local path can
           be either the full path to download data into or the path to an
           existing directory where the data should be placed. In the
           latter case, the base file name from the remote path will be
           used as the local name.

           When downloading multiple files, the local path must refer to
           an existing directory.

           If no local path is provided, the file is downloaded
           into the current local working directory.

           If preserve is `True`, the access and modification times
           and permissions of the original file are set on the
           downloaded file.

           If recurse is `True` and the remote path points at a
           directory, the entire subtree under that directory is
           downloaded.

           If follow_symlinks is set to `True`, symbolic links found
           on the remote system will have the contents of their target
           downloaded rather than creating a local symbolic link. When
           using this option during a recursive download, one needs to
           watch out for links that result in loops.

           The block_size argument specifies the size of read and write
           requests issued when downloading the files, defaulting to
           the maximum allowed by the server, or 16 KB if the server
           doesn't advertise limits.

           The max_requests argument specifies the maximum number of
           parallel read or write requests issued, defaulting to a
           value between 16 and 128 depending on the selected block
           size to avoid excessive memory usage.

           If progress_handler is specified, it will be called after
           each block of a file is successfully downloaded. The arguments
           passed to this handler will be the source path, destination
           path, bytes downloaded so far, and total bytes in the file
           being downloaded. If multiple source paths are provided or
           recurse is set to `True`, the progress_handler will be
           called consecutively on each file being downloaded.

           If error_handler is specified and an error occurs during
           the download, this handler will be called with the exception
           instead of it being raised. This is intended to primarily be
           used when multiple remote paths are provided or when recurse
           is set to `True`, to allow error information to be collected
           without aborting the download of the remaining files. The
           error handler can raise an exception if it wants the download
           to completely stop. Otherwise, after an error, the download
           will continue starting with the next file.

           :param remotepaths:
               The paths of the remote files or directories to download
           :param localpath: (optional)
               The path of the local file or directory to download into
           :param preserve: (optional)
               Whether or not to preserve the original file attributes
           :param recurse: (optional)
               Whether or not to recursively copy directories
           :param follow_symlinks: (optional)
               Whether or not to follow symbolic links
           :param block_size: (optional)
               The block size to use for file reads and writes
           :param max_requests: (optional)
               The maximum number of parallel read or write requests
           :param progress_handler: (optional)
               The function to call to report download progress
           :param error_handler: (optional)
               The function to call when an error occurs
           :type remotepaths:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`,
               or a sequence of these
           :type localpath:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type preserve: `bool`
           :type recurse: `bool`
           :type follow_symlinks: `bool`
           :type block_size: `int`
           :type max_requests: `int`
           :type progress_handler: `callable`
           :type error_handler: `callable`

           :raises: | :exc:`OSError` if a local file I/O error occurs
                    | :exc:`SFTPError` if the server returns an error

        """

        await self._begin_copy(self, local_fs, remotepaths, localpath, 'get',
                               False, preserve, recurse, follow_symlinks,
                               block_size, max_requests, progress_handler,
                               error_handler)

    async def put(self, localpaths: _SFTPPaths,
                  remotepath: Optional[_SFTPPath] = None, *,
                  preserve: bool = False, recurse: bool = False,
                  follow_symlinks: bool = False, block_size: int = -1,
                  max_requests: int = -1,
                  progress_handler: SFTPProgressHandler = None,
                  error_handler: SFTPErrorHandler = None) -> None:
        """Upload local files

           This method uploads one or more files or directories to the
           remote system. Either a single local path or a sequence of
           local paths to upload can be provided.

           When uploading a single file or directory, the remote path can
           be either the full path to upload data into or the path to an
           existing directory where the data should be placed. In the
           latter case, the base file name from the local path will be
           used as the remote name.

           When uploading multiple files, the remote path must refer to
           an existing directory.

           If no remote path is provided, the file is uploaded into the
           current remote working directory.

           If preserve is `True`, the access and modification times
           and permissions of the original file are set on the
           uploaded file.

           If recurse is `True` and the local path points at a
           directory, the entire subtree under that directory is
           uploaded.

           If follow_symlinks is set to `True`, symbolic links found
           on the local system will have the contents of their target
           uploaded rather than creating a remote symbolic link. When
           using this option during a recursive upload, one needs to
           watch out for links that result in loops.

           The block_size argument specifies the size of read and write
           requests issued when uploading the files, defaulting to
           the maximum allowed by the server, or 16 KB if the server
           doesn't advertise limits.

           The max_requests argument specifies the maximum number of
           parallel read or write requests issued, defaulting to a
           value between 16 and 128 depending on the selected block
           size to avoid excessive memory usage.

           If progress_handler is specified, it will be called after
           each block of a file is successfully uploaded. The arguments
           passed to this handler will be the source path, destination
           path, bytes uploaded so far, and total bytes in the file
           being uploaded. If multiple source paths are provided or
           recurse is set to `True`, the progress_handler will be
           called consecutively on each file being uploaded.

           If error_handler is specified and an error occurs during
           the upload, this handler will be called with the exception
           instead of it being raised. This is intended to primarily be
           used when multiple local paths are provided or when recurse
           is set to `True`, to allow error information to be collected
           without aborting the upload of the remaining files. The
           error handler can raise an exception if it wants the upload
           to completely stop. Otherwise, after an error, the upload
           will continue starting with the next file.

           :param localpaths:
               The paths of the local files or directories to upload
           :param remotepath: (optional)
               The path of the remote file or directory to upload into
           :param preserve: (optional)
               Whether or not to preserve the original file attributes
           :param recurse: (optional)
               Whether or not to recursively copy directories
           :param follow_symlinks: (optional)
               Whether or not to follow symbolic links
           :param block_size: (optional)
               The block size to use for file reads and writes
           :param max_requests: (optional)
               The maximum number of parallel read or write requests
           :param progress_handler: (optional)
               The function to call to report upload progress
           :param error_handler: (optional)
               The function to call when an error occurs
           :type localpaths:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`,
               or a sequence of these
           :type remotepath:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type preserve: `bool`
           :type recurse: `bool`
           :type follow_symlinks: `bool`
           :type block_size: `int`
           :type max_requests: `int`
           :type progress_handler: `callable`
           :type error_handler: `callable`

           :raises: | :exc:`OSError` if a local file I/O error occurs
                    | :exc:`SFTPError` if the server returns an error

        """

        await self._begin_copy(local_fs, self, localpaths, remotepath, 'put',
                               False, preserve, recurse, follow_symlinks,
                               block_size, max_requests, progress_handler,
                               error_handler)

    async def copy(self, srcpaths: _SFTPPaths,
                   dstpath: Optional[_SFTPPath] = None, *,
                   preserve: bool = False, recurse: bool = False,
                   follow_symlinks: bool = False, block_size: int = -1,
                   max_requests: int = -1,
                   progress_handler: SFTPProgressHandler = None,
                   error_handler: SFTPErrorHandler = None,
                   remote_only: bool = False) -> None:
        """Copy remote files to a new location

           This method copies one or more files or directories on the
           remote system to a new location. Either a single source path
           or a sequence of source paths to copy can be provided.

           When copying a single file or directory, the destination path
           can be either the full path to copy data into or the path to
           an existing directory where the data should be placed. In the
           latter case, the base file name from the source path will be
           used as the destination name.

           When copying multiple files, the destination path must refer
           to an existing remote directory.

           If no destination path is provided, the file is copied into
           the current remote working directory.

           If preserve is `True`, the access and modification times
           and permissions of the original file are set on the
           copied file.

           If recurse is `True` and the source path points at a
           directory, the entire subtree under that directory is
           copied.

           If follow_symlinks is set to `True`, symbolic links found
           in the source will have the contents of their target copied
           rather than creating a copy of the symbolic link. When
           using this option during a recursive copy, one needs to
           watch out for links that result in loops.

           The block_size argument specifies the size of read and write
           requests issued when copying the files, defaulting to the
           maximum allowed by the server, or 16 KB if the server
           doesn't advertise limits.

           The max_requests argument specifies the maximum number of
           parallel read or write requests issued, defaulting to a
           value between 16 and 128 depending on the selected block
           size to avoid excessive memory usage.

           If progress_handler is specified, it will be called after
           each block of a file is successfully copied. The arguments
           passed to this handler will be the source path, destination
           path, bytes copied so far, and total bytes in the file
           being copied. If multiple source paths are provided or
           recurse is set to `True`, the progress_handler will be
           called consecutively on each file being copied.

           If error_handler is specified and an error occurs during
           the copy, this handler will be called with the exception
           instead of it being raised. This is intended to primarily be
           used when multiple source paths are provided or when recurse
           is set to `True`, to allow error information to be collected
           without aborting the copy of the remaining files. The error
           handler can raise an exception if it wants the copy to
           completely stop. Otherwise, after an error, the copy will
           continue starting with the next file.

           :param srcpaths:
               The paths of the remote files or directories to copy
           :param dstpath: (optional)
               The path of the remote file or directory to copy into
           :param preserve: (optional)
               Whether or not to preserve the original file attributes
           :param recurse: (optional)
               Whether or not to recursively copy directories
           :param follow_symlinks: (optional)
               Whether or not to follow symbolic links
           :param block_size: (optional)
               The block size to use for file reads and writes
           :param max_requests: (optional)
               The maximum number of parallel read or write requests
           :param progress_handler: (optional)
               The function to call to report copy progress
           :param error_handler: (optional)
               The function to call when an error occurs
           :param remote_only: (optional)
               Whether or not to only allow this to be a remote copy
           :type srcpaths:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`,
               or a sequence of these
           :type dstpath:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type preserve: `bool`
           :type recurse: `bool`
           :type follow_symlinks: `bool`
           :type block_size: `int`
           :type max_requests: `int`
           :type progress_handler: `callable`
           :type error_handler: `callable`
           :type remote_only: `bool`

           :raises: | :exc:`OSError` if a local file I/O error occurs
                    | :exc:`SFTPError` if the server returns an error

        """

        await self._begin_copy(self, self, srcpaths, dstpath, 'remote copy',
                               False, preserve, recurse, follow_symlinks,
                               block_size, max_requests, progress_handler,
                               error_handler, remote_only)

    async def mget(self, remotepaths: _SFTPPaths,
                   localpath: Optional[_SFTPPath] = None, *,
                   preserve: bool = False, recurse: bool = False,
                   follow_symlinks: bool = False, block_size: int = -1,
                   max_requests: int = -1,
                   progress_handler: SFTPProgressHandler = None,
                   error_handler: SFTPErrorHandler = None) -> None:
        """Download remote files with glob pattern match

           This method downloads files and directories from the remote
           system matching one or more glob patterns.

           The arguments to this method are identical to the :meth:`get`
           method, except that the remote paths specified can contain
           wildcard patterns.

        """

        await self._begin_copy(self, local_fs, remotepaths, localpath, 'mget',
                               True, preserve, recurse, follow_symlinks,
                               block_size, max_requests, progress_handler,
                               error_handler)

    async def mput(self, localpaths: _SFTPPaths,
                   remotepath: Optional[_SFTPPath] = None, *,
                   preserve: bool = False, recurse: bool = False,
                   follow_symlinks: bool = False, block_size: int = -1,
                   max_requests: int = -1,
                   progress_handler: SFTPProgressHandler = None,
                   error_handler: SFTPErrorHandler = None) -> None:
        """Upload local files with glob pattern match

           This method uploads files and directories to the remote
           system matching one or more glob patterns.

           The arguments to this method are identical to the :meth:`put`
           method, except that the local paths specified can contain
           wildcard patterns.

        """

        await self._begin_copy(local_fs, self, localpaths, remotepath, 'mput',
                               True, preserve, recurse, follow_symlinks,
                               block_size, max_requests, progress_handler,
                               error_handler)

    async def mcopy(self, srcpaths: _SFTPPaths,
                    dstpath: Optional[_SFTPPath] = None, *,
                    preserve: bool = False, recurse: bool = False,
                    follow_symlinks: bool = False, block_size: int = -1,
                    max_requests: int = -1,
                    progress_handler: SFTPProgressHandler = None,
                    error_handler: SFTPErrorHandler = None,
                    remote_only: bool = False) -> None:
        """Copy remote files with glob pattern match

           This method copies files and directories on the remote
           system matching one or more glob patterns.

           The arguments to this method are identical to the :meth:`copy`
           method, except that the source paths specified can contain
           wildcard patterns.

        """

        await self._begin_copy(self, self, srcpaths, dstpath, 'remote mcopy',
                               True, preserve, recurse, follow_symlinks,
                               block_size, max_requests, progress_handler,
                               error_handler, remote_only)

    async def remote_copy(self, src: _SFTPClientFileOrPath,
                          dst: _SFTPClientFileOrPath, src_offset: int = 0,
                          src_length: int = 0, dst_offset: int = 0) -> None:
        """Copy data between remote files

           :param src:
               The remote file object to read data from
           :param dst:
               The remote file object to write data to
           :param src_offset: (optional)
               The offset to begin reading data from
           :param src_length: (optional)
               The number of bytes to attempt to copy
           :param dst_offset: (optional)
               The offset to begin writing data to
           :type src:
               :class:`SFTPClientFile`, :class:`PurePath <pathlib.PurePath>`,
               `str`, or `bytes`
           :type dst:
               :class:`SFTPClientFile`, :class:`PurePath <pathlib.PurePath>`,
               `str`, or `bytes`
           :type src_offset: `int`
           :type src_length: `int`
           :type dst_offset: `int`

           :raises: :exc:`SFTPError` if the server doesn't support this
                    extension or returns an error

        """

        if isinstance(src, (bytes, str, PurePath)):
            src = await self.open(src, 'rb', block_size=0)

        if isinstance(dst, (bytes, str, PurePath)):
            dst = await self.open(dst, 'wb', block_size=0)

        await self._handler.copy_data(src.handle, src_offset, src_length,
                                      dst.handle, dst_offset)

    async def glob(self, patterns: _SFTPPaths,
                   error_handler: SFTPErrorHandler = None) -> \
            Sequence[BytesOrStr]:
        """Match remote files against glob patterns

           This method matches remote files against one or more glob
           patterns. Either a single pattern or a sequence of patterns
           can be provided to match against.

           Supported wildcard characters include '*', '?', and
           character ranges in square brackets. In addition, '**'
           can be used to trigger a recursive directory search at
           that point in the pattern, and a trailing slash can be
           used to request that only directories get returned.

           If error_handler is specified and an error occurs during
           the match, this handler will be called with the exception
           instead of it being raised. This is intended to primarily be
           used when multiple patterns are provided to allow error
           information to be collected without aborting the match
           against the remaining patterns. The error handler can raise
           an exception if it wants to completely abort the match.
           Otherwise, after an error, the match will continue starting
           with the next pattern.

           An error will be raised if any of the patterns completely
           fail to match, and this can either stop the match against
           the remaining patterns or be handled by the error_handler
           just like other errors.

           :param patterns:
               Glob patterns to try and match remote files against
           :param error_handler: (optional)
               The function to call when an error occurs
           :type patterns:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`,
               or a sequence of these
           :type error_handler: `callable`

           :raises: :exc:`SFTPError` if the server returns an error
                    or no match is found

        """

        return [name.filename for name in
                await self.glob_sftpname(patterns, error_handler)]

    async def glob_sftpname(self, patterns: _SFTPPaths,
                            error_handler: SFTPErrorHandler = None) -> \
            Sequence[SFTPName]:
        """Match glob patterns and return SFTPNames

           This method is similar to :meth:`glob`, but it returns matching
           file names and attributes as :class:`SFTPName` objects.

        """

        if isinstance(patterns, (bytes, str, PurePath)):
            patterns = [patterns]

        glob = SFTPGlob(self, len(patterns) > 1)
        matches: List[SFTPName] = []

        for pattern in patterns:
            new_matches = await glob.match(self.encode(pattern),
                                           error_handler, self.version)

            if isinstance(pattern, (str, PurePath)):
                for name in new_matches:
                    name.filename = self.decode(cast(bytes, name.filename))

            matches.extend(new_matches)

        return matches

    async def makedirs(self, path: _SFTPPath, attrs: SFTPAttrs = SFTPAttrs(),
                       exist_ok: bool = False) -> None:
        """Create a remote directory with the specified attributes

           This method creates a remote directory at the specified path
           similar to :meth:`mkdir`, but it will also create any
           intermediate directories which don't yet exist.

           If the target directory already exists and exist_ok is set
           to `False`, this method will raise an error.

           :param path:
               The path of where the new remote directory should be created
           :param attrs: (optional)
               The file attributes to use when creating the directory or
               any intermediate directories
           :param exist_ok: (optional)
               Whether or not to raise an error if thet target directory
               already exists
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type attrs: :class:`SFTPAttrs`
           :type exist_ok: `bool`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        path = self.encode(path)
        curpath = b'/' if posixpath.isabs(path) else (self._cwd or b'')
        exists = True
        parts = path.split(b'/')
        last = len(parts) - 1

        exc: Type[SFTPError]

        for i, part in enumerate(parts):
            curpath = posixpath.join(curpath, part)

            try:
                await self.mkdir(curpath, attrs)
                exists = False
            except (SFTPFailure, SFTPFileAlreadyExists):
                filetype = await self._type(curpath)

                if filetype != FILEXFER_TYPE_DIRECTORY:
                    curpath_str = curpath.decode('utf-8', 'backslashreplace')

                    exc = SFTPNotADirectory if self.version >= 6 \
                        else SFTPFailure

                    raise exc(f'{curpath_str} is not a directory') from None
            except SFTPPermissionDenied:
                if i == last:
                    raise

        if exists and not exist_ok:
            exc = SFTPFileAlreadyExists if self.version >= 6 else SFTPFailure

            raise exc(curpath.decode('utf-8', 'backslashreplace') +
                      ' already exists')

    async def rmtree(self, path: _SFTPPath, ignore_errors: bool = False,
                     onerror: _SFTPOnErrorHandler = None) -> None:
        """Recursively delete a directory tree

           This method removes all the files in a directory tree.

           If ignore_errors is set, errors are ignored. Otherwise,
           if onerror is set, it will be called with arguments of
           the function which failed, the path it failed on, and
           exception information returns by :func:`sys.exc_info()`.

           If follow_symlinks is set, files or directories pointed at by
           symlinks (and their subdirectories, if any) will be removed
           in addition to the links pointing at them.

           :param path:
               The path of the parent directory to remove
           :param ignore_errors: (optional)
               Whether or not to ignore errors during the remove
           :param onerror: (optional)
               A function to call when errors occur
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type ignore_errors: `bool`
           :type onerror: `callable`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        async def _unlink(path: bytes) -> None:
            """Internal helper for unlinking non-directories"""

            assert onerror is not None

            try:
                await self.unlink(path)
            except SFTPError:
                onerror(self.unlink, path, sys.exc_info())

        async def _rmtree(path: bytes) -> None:
            """Internal helper for rmtree recursion"""

            assert onerror is not None

            tasks = []

            try:
                async with sem:
                    async for entry in self.scandir(path):
                        filename = cast(bytes, entry.filename)

                        if filename in (b'.', b'..'):
                            continue

                        filename = posixpath.join(path, filename)

                        if entry.attrs.type == FILEXFER_TYPE_DIRECTORY:
                            task = _rmtree(filename)
                        else:
                            task = _unlink(filename)

                        tasks.append(asyncio.ensure_future(task))
            except SFTPError:
                onerror(self.scandir, path, sys.exc_info())

            results = await asyncio.gather(*tasks, return_exceptions=True)
            exc = next((result for result in results
                        if isinstance(result, Exception)), None)

            if exc:
                raise exc

            try:
                await self.rmdir(path)
            except SFTPError:
                onerror(self.rmdir, path, sys.exc_info())

        # pylint: disable=function-redefined
        if ignore_errors:
            def onerror(*_args: object) -> None:
                pass
        elif onerror is None:
            def onerror(*_args: object) -> None:
                raise # pylint: disable=misplaced-bare-raise
        # pylint: enable=function-redefined

        assert onerror is not None

        path = self.encode(path)
        sem = asyncio.Semaphore(_MAX_SFTP_REQUESTS)

        try:
            if await self.islink(path):
                raise SFTPNoSuchFile(path.decode('utf-8', 'backslashreplace') +
                                     ' must not be a symlink')
        except SFTPError:
            onerror(self.islink, path, sys.exc_info())
            return

        await _rmtree(path)

    @async_context_manager
    async def open(self, path: _SFTPPath,
                   pflags_or_mode: Union[int, str] = FXF_READ,
                   attrs: SFTPAttrs = SFTPAttrs(),
                   encoding: Optional[str] = 'utf-8', errors: str = 'strict',
                   block_size: int = -1,
                   max_requests: int = -1) -> SFTPClientFile:
        """Open a remote file

           This method opens a remote file and returns an
           :class:`SFTPClientFile` object which can be used to read and
           write data and get and set file attributes.

           The path can be either a `str` or `bytes` value. If it is a
           str, it will be encoded using the file encoding specified
           when the :class:`SFTPClient` was started.

           The following open mode flags are supported:

             ========== ======================================================
             Mode       Description
             ========== ======================================================
             FXF_READ   Open the file for reading.
             FXF_WRITE  Open the file for writing. If both this and FXF_READ
                        are set, open the file for both reading and writing.
             FXF_APPEND Force writes to append data to the end of the file
                        regardless of seek position.
             FXF_CREAT  Create the file if it doesn't exist. Without this,
                        attempts to open a non-existent file will fail.
             FXF_TRUNC  Truncate the file to zero length if it already exists.
             FXF_EXCL   Return an error when trying to open a file which
                        already exists.
             ========== ======================================================

           Instead of these flags, a Python open mode string can also be
           provided. Python open modes map to the above flags as follows:

             ==== =============================================
             Mode Flags
             ==== =============================================
             r    FXF_READ
             w    FXF_WRITE | FXF_CREAT | FXF_TRUNC
             a    FXF_WRITE | FXF_CREAT | FXF_APPEND
             x    FXF_WRITE | FXF_CREAT | FXF_EXCL

             r+   FXF_READ | FXF_WRITE
             w+   FXF_READ | FXF_WRITE | FXF_CREAT | FXF_TRUNC
             a+   FXF_READ | FXF_WRITE | FXF_CREAT | FXF_APPEND
             x+   FXF_READ | FXF_WRITE | FXF_CREAT | FXF_EXCL
             ==== =============================================

           Including a 'b' in the mode causes the `encoding` to be set
           to `None`, forcing all data to be read and written as bytes
           in binary format.

           Most applications should be able to use this method regardless
           of the version of the SFTP protocol negotiated with the SFTP
           server. A conversion from the pflags_or_mode values to the
           SFTPv5/v6 flag values will happen automatically. However, if
           an application wishes to set flags only available in SFTPv5/v6,
           the :meth:`open56` method may be used to specify these flags
           explicitly.

           The attrs argument is used to set initial attributes of the
           file if it needs to be created. Otherwise, this argument is
           ignored.

           The block_size argument specifies the size of parallel read and
           write requests issued on the file. If set to `None`, each read
           or write call will become a single request to the SFTP server.
           Otherwise, read or write calls larger than this size will be
           turned into parallel requests to the server of the requested
           size, defaulting to the maximum allowed by the server, or 16 KB
           if the server doesn't advertise limits.

               .. note:: The OpenSSH SFTP server will close the connection
                         if it receives a message larger than 256 KB. So,
                         when connecting to an OpenSSH SFTP server, it is
                         recommended that the block_size be left at its
                         default of using the server-advertised limits.

           The max_requests argument specifies the maximum number of
           parallel read or write requests issued, defaulting to a
           value between 16 and 128 depending on the selected block
           size to avoid excessive memory usage.

           :param path:
               The name of the remote file to open
           :param pflags_or_mode: (optional)
               The access mode to use for the remote file (see above)
           :param attrs: (optional)
               File attributes to use if the file needs to be created
           :param encoding: (optional)
               The Unicode encoding to use for data read and written
               to the remote file
           :param errors: (optional)
               The error-handling mode if an invalid Unicode byte
               sequence is detected, defaulting to 'strict' which
               raises an exception
           :param block_size: (optional)
               The block size to use for read and write requests
           :param max_requests: (optional)
               The maximum number of parallel read or write requests
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type pflags_or_mode: `int` or `str`
           :type attrs: :class:`SFTPAttrs`
           :type encoding: `str`
           :type errors: `str`
           :type block_size: `int` or `None`
           :type max_requests: `int`

           :returns: An :class:`SFTPClientFile` to use to access the file

           :raises: | :exc:`ValueError` if the mode is not valid
                    | :exc:`SFTPError` if the server returns an error

        """

        if isinstance(pflags_or_mode, str):
            pflags, binary = _mode_to_pflags(pflags_or_mode)

            if binary:
                encoding = None
        else:
            pflags = pflags_or_mode

        path = self.compose_path(path)
        handle = await self._handler.open(path, pflags, attrs)

        return SFTPClientFile(self._handler, handle, bool(pflags & FXF_APPEND),
                              encoding, errors, block_size, max_requests)

    @async_context_manager
    async def open56(self, path: _SFTPPath,
                     desired_access: int = ACE4_READ_DATA |
                                           ACE4_READ_ATTRIBUTES,
                     flags: int = FXF_OPEN_EXISTING,
                     attrs: SFTPAttrs = SFTPAttrs(),
                     encoding: Optional[str] = 'utf-8', errors: str = 'strict',
                     block_size: int = -1,
                     max_requests: int = -1) -> SFTPClientFile:
        """Open a remote file using SFTP v5/v6 flags

           This method is very similar to :meth:`open`, but the pflags_or_mode
           argument is replaced with SFTPv5/v6 desired_access and flags
           arguments. Most applications can continue to use :meth:`open`
           even when talking to an SFTPv5/v6 server and the translation of
           the flags will happen automatically. However, if an application
           wishes to set flags only available in SFTPv5/v6, this method
           provides that capability.

           The following desired_access flags can be specified:

               | ACE4_READ_DATA
               | ACE4_WRITE_DATA
               | ACE4_APPEND_DATA
               | ACE4_READ_ATTRIBUTES
               | ACE4_WRITE_ATTRIBUTES

           The following flags can be specified:

               | FXF_CREATE_NEW
               | FXF_CREATE_TRUNCATE
               | FXF_OPEN_EXISTING
               | FXF_OPEN_OR_CREATE
               | FXF_TRUNCATE_EXISTING
               | FXF_APPEND_DATA
               | FXF_APPEND_DATA_ATOMIC
               | FXF_BLOCK_READ
               | FXF_BLOCK_WRITE
               | FXF_BLOCK_DELETE
               | FXF_BLOCK_ADVISORY (SFTPv6)
               | FXF_NOFOLLOW (SFTPv6)
               | FXF_DELETE_ON_CLOSE (SFTPv6)
               | FXF_ACCESS_AUDIT_ALARM_INFO (SFTPv6)
               | FXF_ACCESS_BACKUP (SFTPv6)
               | FXF_BACKUP_STREAM (SFTPv6)
               | FXF_OVERRIDE_OWNER (SFTPv6)

           At this time, FXF_TEXT_MODE is not supported. Also, servers
           may support only a subset of these flags. For example,
           the AsyncSSH SFTP server doesn't currently support ACLs,
           file locking, or most of the SFTPv6 open flags, but
           support for some of these may be added over time.

           :param path:
               The name of the remote file to open
           :param desired_access: (optional)
               The access mode to use for the remote file (see above)
           :param flags: (optional)
               The access flags to use for the remote file (see above)
           :param attrs: (optional)
               File attributes to use if the file needs to be created
           :param encoding: (optional)
               The Unicode encoding to use for data read and written
               to the remote file
           :param errors: (optional)
               The error-handling mode if an invalid Unicode byte
               sequence is detected, defaulting to 'strict' which
               raises an exception
           :param block_size: (optional)
               The block size to use for read and write requests
           :param max_requests: (optional)
               The maximum number of parallel read or write requests
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type desired_access: int
           :type flags: int
           :type attrs: :class:`SFTPAttrs`
           :type encoding: `str`
           :type errors: `str`
           :type block_size: `int` or `None`
           :type max_requests: `int`

           :returns: An :class:`SFTPClientFile` to use to access the file

           :raises: | :exc:`ValueError` if the mode is not valid
                    | :exc:`SFTPError` if the server returns an error

        """

        path = self.compose_path(path)
        handle = await self._handler.open56(path, desired_access, flags, attrs)

        return SFTPClientFile(self._handler, handle,
                              bool(desired_access & ACE4_APPEND_DATA or
                                   flags & FXF_APPEND_DATA),
                              encoding, errors, block_size, max_requests)

    async def stat(self, path: _SFTPPath, flags = FILEXFER_ATTR_DEFINED_V4, *,
                   follow_symlinks: bool = True) -> SFTPAttrs:
        """Get attributes of a remote file, directory, or symlink

           This method queries the attributes of a remote file, directory,
           or symlink. If the path provided is a symlink and follow_symlinks
           is `True`, the returned attributes will correspond to the target
           of the link.

           :param path:
               The path of the remote file or directory to get attributes for
           :param flags: (optional)
               Flags indicating attributes of interest (SFTPv4 only)
           :param follow_symlinks: (optional)
               Whether or not to follow symbolic links
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type flags: `int`
           :type follow_symlinks: `bool`

           :returns: An :class:`SFTPAttrs` containing the file attributes

           :raises: :exc:`SFTPError` if the server returns an error

        """

        path = self.compose_path(path)
        return await self._handler.stat(path, flags,
                                        follow_symlinks=follow_symlinks)

    async def lstat(self, path: _SFTPPath,
                    flags = FILEXFER_ATTR_DEFINED_V4) -> SFTPAttrs:
        """Get attributes of a remote file, directory, or symlink

           This method queries the attributes of a remote file,
           directory, or symlink. Unlike :meth:`stat`, this method
           returns the attributes of a symlink itself rather than
           the target of that link.

           :param path:
               The path of the remote file, directory, or link to get
               attributes for
           :param flags: (optional)
               Flags indicating attributes of interest (SFTPv4 only)
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type flags: `int`

           :returns: An :class:`SFTPAttrs` containing the file attributes

           :raises: :exc:`SFTPError` if the server returns an error

        """

        path = self.compose_path(path)
        return await self._handler.lstat(path, flags)

    async def setstat(self, path: _SFTPPath, attrs: SFTPAttrs, *,
                      follow_symlinks: bool = True) -> None:
        """Set attributes of a remote file, directory, or symlink

           This method sets attributes of a remote file, directory, or
           symlink. If the path provided is a symlink and follow_symlinks
           is `True`, the attributes will be set on the target of the link.
           A subset of the fields in `attrs` can be initialized and only
           those attributes will be changed.

           :param path:
               The path of the remote file or directory to set attributes for
           :param attrs:
               File attributes to set
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type attrs: :class:`SFTPAttrs`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        path = self.compose_path(path)

        await self._handler.setstat(path, attrs,
                                    follow_symlinks=follow_symlinks)

    async def statvfs(self, path: _SFTPPath) -> SFTPVFSAttrs:
        """Get attributes of a remote file system

           This method queries the attributes of the file system containing
           the specified path.

           :param path:
               The path of the remote file system to get attributes for
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :returns: An :class:`SFTPVFSAttrs` containing the file system
                     attributes

           :raises: :exc:`SFTPError` if the server doesn't support this
                    extension or returns an error

        """

        path = self.compose_path(path)
        return await self._handler.statvfs(path)

    async def truncate(self, path: _SFTPPath, size: int) -> None:
        """Truncate a remote file to the specified size

           This method truncates a remote file to the specified size.
           If the path provided is a symbolic link, the target of
           the link will be truncated.

           :param path:
               The path of the remote file to be truncated
           :param size:
               The desired size of the file, in bytes
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type size: `int`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        await self.setstat(path, SFTPAttrs(size=size))

    @overload
    async def chown(self, path: _SFTPPath, uid: int, gid: int, *,
                    follow_symlinks: bool = True) -> \
        None: ... # pragma: no cover

    @overload
    async def chown(self, path: _SFTPPath, owner: str, group: str, *,
                    follow_symlinks: bool = True) -> \
        None: ... # pragma: no cover

    async def chown(self, path, uid_or_owner = None, gid_or_group = None,
                    uid = None, gid = None, owner = None, group = None, *,
                    follow_symlinks = True):
        """Change the owner of a remote file, directory, or symlink

           This method changes the user and group id of a remote file,
           directory, or symlink. If the path provided is a symlink and
           follow_symlinks is `True`, the target of the link will be changed.

           :param path:
               The path of the remote file to change
           :param uid:
               The new user id to assign to the file
           :param gid:
               The new group id to assign to the file
           :param owner:
               The new owner to assign to the file (SFTPv4 only)
           :param group:
               The new group to assign to the file (SFTPv4 only)
           :param follow_symlinks: (optional)
               Whether or not to follow symbolic links
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type uid: `int`
           :type gid: `int`
           :type owner: `str`
           :type group: `str`
           :type follow_symlinks: `bool`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        if isinstance(uid_or_owner, int):
            uid = uid_or_owner
        elif isinstance(uid_or_owner, str):
            owner = uid_or_owner

        if isinstance(gid_or_group, int):
            gid = gid_or_group
        elif isinstance(gid_or_group, str):
            group = gid_or_group

        await self.setstat(path, SFTPAttrs(uid=uid, gid=gid,
                                           owner=owner, group=group),
                           follow_symlinks=follow_symlinks)

    async def chmod(self, path: _SFTPPath, mode: int, *,
                    follow_symlinks: bool = True) -> None:
        """Change the permissions of a remote file, directory, or symlink

           This method changes the permissions of a remote file, directory,
           or symlink. If the path provided is a symlink and follow_symlinks
           is `True`, the target of the link will be changed.

           :param path:
               The path of the remote file to change
           :param mode:
               The new file permissions, expressed as an int
           :param follow_symlinks: (optional)
               Whether or not to follow symbolic links
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type mode: `int`
           :type follow_symlinks: `bool`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        await self.setstat(path, SFTPAttrs(permissions=mode),
                           follow_symlinks=follow_symlinks)

    async def utime(self, path: _SFTPPath,
                    times: Optional[Tuple[float, float]] = None,
                    ns: Optional[Tuple[int, int]] = None, *,
                    follow_symlinks: bool = True) -> None:
        """Change the timestamps of a remote file, directory, or symlink

           This method changes the access and modify times of a remote file,
           directory, or symlink. If neither `times` nor '`ns` is provided,
           the times will be changed to the current time.

           If the path provided is a symlink and follow_symlinks is `True`,
           the target of the link will be changed.

           :param path:
               The path of the remote file to change
           :param times: (optional)
               The new access and modify times, as seconds relative to
               the UNIX epoch
           :param ns: (optional)
               The new access and modify times, as nanoseconds relative to
               the UNIX epoch
           :param follow_symlinks: (optional)
               Whether or not to follow symbolic links
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type times: tuple of two `int` or `float` values
           :type ns: tuple of two `int` values
           :type follow_symlinks: `bool`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        await self.setstat(path, _utime_to_attrs(times, ns),
                           follow_symlinks=follow_symlinks)

    async def exists(self, path: _SFTPPath) -> bool:
        """Return if the remote path exists and isn't a broken symbolic link

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        return (await self._type(path)) != FILEXFER_TYPE_UNKNOWN

    async def lexists(self, path: _SFTPPath) -> bool:
        """Return if the remote path exists, without following symbolic links

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        return (await self._type(path, statfunc=self.lstat)) != \
            FILEXFER_TYPE_UNKNOWN

    async def getatime(self, path: _SFTPPath) -> Optional[float]:
        """Return the last access time of a remote file or directory

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        attrs = await self.stat(path)

        return _tuple_to_float_sec(attrs.atime, attrs.atime_ns) \
            if attrs.atime is not None else None

    async def getatime_ns(self, path: _SFTPPath) -> Optional[int]:
        """Return the last access time of a remote file or directory

           The time returned is nanoseconds since the epoch.

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        attrs = await self.stat(path)

        return _tuple_to_nsec(attrs.atime, attrs.atime_ns) \
            if attrs.atime is not None else None

    async def getcrtime(self, path: _SFTPPath) -> Optional[float]:
        """Return the creation time of a remote file or directory (SFTPv4 only)

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        attrs = await self.stat(path)

        return _tuple_to_float_sec(attrs.crtime, attrs.crtime_ns) \
            if attrs.crtime is not None else None

    async def getcrtime_ns(self, path: _SFTPPath) -> Optional[int]:
        """Return the creation time of a remote file or directory

           The time returned is nanoseconds since the epoch.

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        attrs = await self.stat(path)

        return _tuple_to_nsec(attrs.crtime, attrs.crtime_ns) \
            if attrs.crtime is not None else None

    async def getmtime(self, path: _SFTPPath) -> Optional[float]:
        """Return the last modification time of a remote file or directory

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        attrs = await self.stat(path)

        return _tuple_to_float_sec(attrs.mtime, attrs.mtime_ns) \
            if attrs.mtime is not None else None

    async def getmtime_ns(self, path: _SFTPPath) -> Optional[int]:
        """Return the last modification time of a remote file or directory

           The time returned is nanoseconds since the epoch.

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        attrs = await self.stat(path)

        return _tuple_to_nsec(attrs.mtime, attrs.mtime_ns) \
            if attrs.mtime is not None else None

    async def getsize(self, path: _SFTPPath) -> Optional[int]:
        """Return the size of a remote file or directory

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        return (await self.stat(path)).size

    async def isdir(self, path: _SFTPPath) -> bool:
        """Return if the remote path refers to a directory

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        return (await self._type(path)) == FILEXFER_TYPE_DIRECTORY

    async def isfile(self, path: _SFTPPath) -> bool:
        """Return if the remote path refers to a regular file

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        return (await self._type(path)) == FILEXFER_TYPE_REGULAR

    async def islink(self, path: _SFTPPath) -> bool:
        """Return if the remote path refers to a symbolic link

           :param path:
               The remote path to check
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        return (await self._type(path, statfunc=self.lstat)) == \
            FILEXFER_TYPE_SYMLINK

    async def remove(self, path: _SFTPPath) -> None:
        """Remove a remote file

           This method removes a remote file or symbolic link.

           :param path:
               The path of the remote file or link to remove
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        path = self.compose_path(path)
        await self._handler.remove(path)

    async def unlink(self, path: _SFTPPath) -> None:
        """Remove a remote file (see :meth:`remove`)"""

        await self.remove(path)

    async def rename(self, oldpath: _SFTPPath, newpath: _SFTPPath,
                     flags: int = 0) -> None:
        """Rename a remote file, directory, or link

           This method renames a remote file, directory, or link.

           .. note:: By default, this version of rename will not overwrite
                     the new path if it already exists. However, this
                     can be controlled using the `flags` argument,
                     available in SFTPv5 and later. When a connection
                     is negotiated to use an earliler version of SFTP
                     and `flags` is set, this method will attempt to
                     fall back to the OpenSSH "posix-rename" extension
                     if it is available. That can also be invoked
                     directly by calling :meth:`posix_rename`.

           :param oldpath:
               The path of the remote file, directory, or link to rename
           :param newpath:
               The new name for this file, directory, or link
           :param flags: (optional)
               A combination of the `FXR_OVERWRITE`, `FXR_ATOMIC`, and
               `FXR_NATIVE` flags to specify what happens when `newpath`
               already exists, defaulting to not allowing the overwrite
               (SFTPv5 and later)
           :type oldpath:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type newpath:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type flags: `int`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        oldpath = self.compose_path(oldpath)
        newpath = self.compose_path(newpath)
        await self._handler.rename(oldpath, newpath, flags)

    async def posix_rename(self, oldpath: _SFTPPath,
                           newpath: _SFTPPath) -> None:
        """Rename a remote file, directory, or link with POSIX semantics

           This method renames a remote file, directory, or link,
           removing the prior instance of new path if it previously
           existed.

           This method may not be supported by all SFTP servers. If it
           is not available but the server supports SFTPv5 or later,
           this method will attempt to send the standard SFTP rename
           request with the `FXR_OVERWRITE` flag set.

           :param oldpath:
               The path of the remote file, directory, or link to rename
           :param newpath:
               The new name for this file, directory, or link
           :type oldpath:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type newpath:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server doesn't support this
                    extension or returns an error

        """

        oldpath = self.compose_path(oldpath)
        newpath = self.compose_path(newpath)
        await self._handler.posix_rename(oldpath, newpath)

    async def scandir(self, path: _SFTPPath = '.') -> AsyncIterator[SFTPName]:
        """Return names and attributes of the files in a remote directory

           This method reads the contents of a directory, returning
           the names and attributes of what is contained there as an
           async iterator. If no path is provided, it defaults to the
           current remote working directory.

           :param path: (optional)
               The path of the remote directory to read
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :returns: An async iterator of :class:`SFTPName` entries, with
                     path names matching the type used to pass in the path

           :raises: :exc:`SFTPError` if the server returns an error

        """

        dirpath = self.compose_path(path)
        handle = await self._handler.opendir(dirpath)
        at_end = False

        try:
            while not at_end:
                names, at_end = await self._handler.readdir(handle)

                for entry in names:
                    if isinstance(path, (str, PurePath)):
                        entry.filename = \
                            self.decode(cast(bytes, entry.filename))

                        if entry.longname is not None:
                            entry.longname = \
                                self.decode(cast(bytes, entry.longname))

                    yield entry
        except SFTPEOFError:
            pass
        finally:
            await self._handler.close(handle)

    async def readdir(self, path: _SFTPPath = '.') -> Sequence[SFTPName]:
        """Read the contents of a remote directory

           This method reads the contents of a directory, returning
           the names and attributes of what is contained there. If no
           path is provided, it defaults to the current remote working
           directory.

           :param path: (optional)
               The path of the remote directory to read
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :returns: A list of :class:`SFTPName` entries, with path
                     names matching the type used to pass in the path

           :raises: :exc:`SFTPError` if the server returns an error

        """

        return [entry async for entry in self.scandir(path)]

    @overload
    async def listdir(self, path: bytes) -> \
        Sequence[bytes]: ... # pragma: no cover

    @overload
    async def listdir(self, path: FilePath = ...) -> \
        Sequence[str]: ... # pragma: no cover

    async def listdir(self, path: _SFTPPath = '.') -> Sequence[BytesOrStr]:
        """Read the names of the files in a remote directory

           This method reads the names of files and subdirectories
           in a remote directory. If no path is provided, it defaults
           to the current remote working directory.

           :param path: (optional)
               The path of the remote directory to read
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :returns: A list of file/subdirectory names, as a `str` or `bytes`
                     matching the type used to pass in the path

           :raises: :exc:`SFTPError` if the server returns an error

        """

        names = await self.readdir(path)
        return [name.filename for name in names]

    async def mkdir(self, path: _SFTPPath,
                    attrs: SFTPAttrs = SFTPAttrs()) -> None:
        """Create a remote directory with the specified attributes

           This method creates a new remote directory at the
           specified path with the requested attributes.

           :param path:
               The path of where the new remote directory should be created
           :param attrs: (optional)
               The file attributes to use when creating the directory
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type attrs: :class:`SFTPAttrs`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        path = self.compose_path(path)
        await self._handler.mkdir(path, attrs)

    async def rmdir(self, path: _SFTPPath) -> None:
        """Remove a remote directory

           This method removes a remote directory. The directory
           must be empty for the removal to succeed.

           :param path:
               The path of the remote directory to remove
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        path = self.compose_path(path)
        await self._handler.rmdir(path)

    @overload
    async def realpath(self, path: bytes, # pragma: no cover
                       *compose_paths: bytes) -> bytes: ...

    @overload
    async def realpath(self, path: FilePath, # pragma: no cover
                       *compose_paths: FilePath) -> str: ...

    @overload
    async def realpath(self, path: bytes, # pragma: no cover
                       *compose_paths: bytes, check: int) -> SFTPName: ...

    @overload
    async def realpath(self, path: FilePath, # pragma: no cover
                       *compose_paths: FilePath, check: int) -> SFTPName: ...

    async def realpath(self, path: _SFTPPath, *compose_paths: _SFTPPath,
                       check: int = FXRP_NO_CHECK) -> \
            Union[BytesOrStr, SFTPName]:
        """Return the canonical version of a remote path

           This method returns a canonical version of the requested path.

           :param path: (optional)
               The path of the remote directory to canonicalize
           :param compose_paths: (optional)
               A list of additional paths that the server should compose
               with `path` before canonicalizing it
           :param check: (optional)
               One of `FXRP_NO_CHECK`, `FXRP_STAT_IF_EXISTS`, and
               `FXRP_STAT_ALWAYS`, specifying when to perform a
               stat operation on the resulting path, defaulting to
               `FXRP_NO_CHECK`
           :type path:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type compose_paths:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type check: int

           :returns: The canonical path as a `str` or `bytes`, matching
                     the type used to pass in the path if `check` is set
                     to `FXRP_NO_CHECK`, or an :class:`SFTPName`
                     containing the canonical path name and attributes
                     otherwise

           :raises: :exc:`SFTPError` if the server returns an error

        """

        if compose_paths and isinstance(compose_paths[-1], int):
            check = compose_paths[-1]
            compose_paths = compose_paths[:-1]

        path_bytes = self.compose_path(path)

        if self.version >= 6:
            names, _ = await self._handler.realpath(
                path_bytes, *map(self.encode, compose_paths), check=check)
        else:
            for cpath in compose_paths:
                path_bytes = self.compose_path(cpath, path_bytes)

            names, _ = await self._handler.realpath(path_bytes)

        if len(names) > 1:
            raise SFTPBadMessage('Too many names returned')

        if check != FXRP_NO_CHECK:
            if self.version < 6:
                try:
                    names[0].attrs = await self._handler.stat(
                        self.encode(names[0].filename),
                        _valid_attr_flags[self.version])
                except SFTPError:
                    if check == FXRP_STAT_IF_EXISTS:
                        names[0].attrs = SFTPAttrs(type=FILEXFER_TYPE_UNKNOWN)
                    else:
                        raise

            return names[0]
        else:
            return self.decode(cast(bytes, names[0].filename),
                               isinstance(path, (str, PurePath)))

    async def getcwd(self) -> BytesOrStr:
        """Return the current remote working directory

           :returns: The current remote working directory, decoded using
                     the specified path encoding

           :raises: :exc:`SFTPError` if the server returns an error

        """

        if self._cwd is None:
            self._cwd = await self.realpath(b'.')

        return self.decode(self._cwd)

    async def chdir(self, path: _SFTPPath) -> None:
        """Change the current remote working directory

           :param path:
               The path to set as the new remote working directory
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        self._cwd = await self.realpath(self.encode(path))

    @overload
    async def readlink(self, path: bytes) -> bytes: ... # pragma: no cover

    @overload
    async def readlink(self, path: FilePath) -> str: ... # pragma: no cover

    async def readlink(self, path: _SFTPPath) -> BytesOrStr:
        """Return the target of a remote symbolic link

           This method returns the target of a symbolic link.

           :param path:
               The path of the remote symbolic link to follow
           :type path: :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :returns: The target path of the link as a `str` or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        linkpath = self.compose_path(path)
        names, _ = await self._handler.readlink(linkpath)

        if len(names) > 1:
            raise SFTPBadMessage('Too many names returned')

        return self.decode(cast(bytes, names[0].filename),
                           isinstance(path, (str, PurePath)))

    async def symlink(self, oldpath: _SFTPPath, newpath: _SFTPPath) -> None:
        """Create a remote symbolic link

           This method creates a symbolic link. The argument order here
           matches the standard Python :meth:`os.symlink` call. The
           argument order sent on the wire is automatically adapted
           depending on the version information sent by the server, as
           a number of servers (OpenSSH in particular) did not follow
           the SFTP standard when implementing this call.

           :param oldpath:
               The path the link should point to
           :param newpath:
               The path of where to create the remote symbolic link
           :type oldpath:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type newpath:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server returns an error

        """

        oldpath = self.encode(oldpath)
        newpath = self.compose_path(newpath)
        await self._handler.symlink(oldpath, newpath)

    async def link(self, oldpath: _SFTPPath, newpath: _SFTPPath) -> None:
        """Create a remote hard link

           This method creates a hard link to the remote file specified
           by oldpath at the location specified by newpath.

           This method may not be supported by all SFTP servers.

           :param oldpath:
               The path of the remote file the hard link should point to
           :param newpath:
               The path of where to create the remote hard link
           :type oldpath:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`
           :type newpath:
               :class:`PurePath <pathlib.PurePath>`, `str`, or `bytes`

           :raises: :exc:`SFTPError` if the server doesn't support this
                    extension or returns an error

        """

        oldpath = self.compose_path(oldpath)
        newpath = self.compose_path(newpath)
        await self._handler.link(oldpath, newpath)

    def exit(self) -> None:
        """Exit the SFTP client session

           This method exits the SFTP client session, closing the
           corresponding channel opened on the server.

        """

        self._handler.exit()

    async def wait_closed(self) -> None:
        """Wait for this SFTP client session to close"""

        await self._handler.wait_closed()


class SFTPServerHandler(SFTPHandler):
    """An SFTP server session handler"""

    # Supported attribute flags in setstat/fsetstat/lsetstat
    _supported_attr_mask = FILEXFER_ATTR_SIZE | \
                           FILEXFER_ATTR_PERMISSIONS | \
                           FILEXFER_ATTR_ACCESSTIME | \
                           FILEXFER_ATTR_MODIFYTIME | \
                           FILEXFER_ATTR_OWNERGROUP | \
                           FILEXFER_ATTR_SUBSECOND_TIMES

    # No attrib bits currently supported
    _supported_attrib_mask = 0

    # Supported SFTPv5/v6 open flags
    _supported_open_flags = FXF_ACCESS_DISPOSITION | FXF_APPEND_DATA

    # Supported SFTPv5/v6 desired access flags
    _supported_access_mask = ACE4_READ_DATA | ACE4_WRITE_DATA | \
                             ACE4_APPEND_DATA | ACE4_READ_ATTRIBUTES | \
                             ACE4_WRITE_ATTRIBUTES

    # Locking not currently supported
    _supported_open_block_vector = _supported_block_vector = 0x0001

    _vendor_id = String(__author__) + String('AsyncSSH') + \
        String(__version__) + UInt64(0)

    _extensions: List[Tuple[bytes, bytes]] = [
        (b'newline', os.linesep.encode('utf-8')),
        (b'vendor-id', _vendor_id),
        (b'posix-rename@openssh.com', b'1'),
        (b'hardlink@openssh.com', b'1'),
        (b'fsync@openssh.com', b'1'),
        (b'lsetstat@openssh.com', b'1'),
        (b'limits@openssh.com', b'1'),
        (b'copy-data', b'1')]

    _attrib_extensions: List[bytes] = []

    if hasattr(os, 'statvfs'): # pragma: no branch
        _extensions += [(b'statvfs@openssh.com', b'2'),
                        (b'fstatvfs@openssh.com', b'2')]

    def __init__(self, server: 'SFTPServer', reader: 'SSHReader[bytes]',
                 writer: 'SSHWriter[bytes]', sftp_version: int):
        super().__init__(reader, writer)

        self._server = server
        self._version = sftp_version
        self._nonstandard_symlink = False
        self._next_handle = 0
        self._file_handles: Dict[bytes, object] = {}
        self._dir_handles: Dict[bytes, AsyncIterator[SFTPName]] = {}

    async def _cleanup(self, exc: Optional[Exception]) -> None:
        """Clean up this SFTP server session"""

        if self._server: # pragma: no branch
            for file_obj in list(self._file_handles.values()):
                result = self._server.close(file_obj)

                if inspect.isawaitable(result):
                    assert result is not None
                    await result

            self._server.exit()

            self._file_handles = {}
            self._dir_handles = {}

        self.logger.info('SFTP server exited%s', ': ' + str(exc) if exc else '')

        await super()._cleanup(exc)

    def _get_next_handle(self) -> bytes:
        """Get the next available unique file handle number"""

        while True:
            handle = self._next_handle.to_bytes(4, 'big')
            self._next_handle = (self._next_handle + 1) & 0xffffffff

            if (handle not in self._file_handles and
                    handle not in self._dir_handles):
                return handle

    async def _process_packet(self, pkttype: int, pktid: int,
                              packet: SSHPacket) -> None:
        """Process incoming SFTP requests"""

        # pylint: disable=broad-except
        try:
            if pkttype == FXP_EXTENDED:
                handler_type: Union[int, bytes] = packet.get_string()
            else:
                handler_type = pkttype

            handler = self._packet_handlers.get(handler_type)
            if not handler:
                raise SFTPOpUnsupported(f'Unsupported request type: {pkttype}')

            return_type = self._return_types.get(handler_type, FXP_STATUS)
            result = await handler(self, packet)

            if return_type == FXP_STATUS:
                self.logger.debug1('Sending OK')

                response = UInt32(FX_OK) + String('') + String('')
            elif return_type == FXP_HANDLE:
                handle = cast(bytes, result)

                self.logger.debug1('Sending handle %s', handle.hex())

                response = String(handle)
            elif return_type == FXP_DATA:
                data, at_end = cast(Tuple[bytes, bool], result)

                self.logger.debug1('Sending %s%s',
                                   plural(len(data), 'data byte'),
                                   ' (at end)' if at_end else '')

                end = Boolean(at_end) if at_end and self._version >= 6 else b''

                response = String(data) + end
            elif return_type == FXP_NAME:
                names, at_end = cast(_SFTPNames, result)

                self.logger.debug1('Sending %s%s', plural(len(names), 'name'),
                                   ' (at end)' if at_end else '')

                for name in names:
                    self.logger.debug1('  %s', name)

                end = Boolean(at_end) if at_end and self._version >= 6 else b''

                response = (UInt32(len(names)) +
                            b''.join(name.encode(self._version)
                                     for name in names) + end)
            elif isinstance(result, SFTPLimits):
                self.logger.debug1('Sending server limits:')
                self._log_limits(result)
                response = result.encode(self._version)
            else:
                attrs: _SupportsEncode

                if isinstance(result, os.stat_result):
                    attrs = SFTPAttrs.from_local(cast(os.stat_result, result))
                elif isinstance(result, os.statvfs_result):
                    attrs = SFTPVFSAttrs.from_local(cast(os.statvfs_result,
                                                         result))
                else:
                    attrs = cast(_SupportsEncode, result)

                self.logger.debug1('Sending %s', attrs)
                response = attrs.encode(self._version)
        except PacketDecodeError as exc:
            return_type = FXP_STATUS

            self.logger.debug1('Sending bad message error: %s', str(exc))

            response = (UInt32(FX_BAD_MESSAGE) + String(str(exc)) +
                        String(DEFAULT_LANG))
        except SFTPError as exc:
            return_type = FXP_STATUS

            if exc.code == FX_EOF:
                self.logger.debug1('Sending EOF')
            else:
                self.logger.debug1('Sending %s: %s', exc.__class__.__name__,
                                   str(exc.reason))

            response = exc.encode(self._version)
        except NotImplementedError:
            assert handler is not None

            return_type = FXP_STATUS
            op_name = handler.__name__[9:]

            self.logger.debug1('Sending operation not supported: %s', op_name)

            response = (UInt32(FX_OP_UNSUPPORTED) +
                        String(f'Operation not supported: {op_name}') +
                        String(DEFAULT_LANG))
        except OSError as exc:
            return_type = FXP_STATUS
            reason = exc.strerror or str(exc)

            if exc.errno == errno.ENOENT:
                self.logger.debug1('Sending no such file: %s', reason)
                code = FX_NO_SUCH_FILE
            elif exc.errno == errno.EACCES:
                self.logger.debug1('Sending permission denied: %s', reason)
                code = FX_PERMISSION_DENIED
            elif exc.errno == errno.EEXIST:
                self.logger.debug1('Sending file already exists: %s', reason)
                code = FX_FILE_ALREADY_EXISTS
            elif exc.errno == errno.EROFS:
                self.logger.debug1('Sending write protect: %s', reason)
                code = FX_WRITE_PROTECT
            elif exc.errno == errno.ENOSPC:
                self.logger.debug1('Sending no space on '
                                   'filesystem: %s', reason)
                code = FX_NO_SPACE_ON_FILESYSTEM
            elif exc.errno == errno.EDQUOT:
                self.logger.debug1('Sending disk quota exceeded: %s', reason)
                code = FX_QUOTA_EXCEEDED
            elif exc.errno == errno.ENOTEMPTY:
                self.logger.debug1('Sending directory not empty: %s', reason)
                code = FX_DIR_NOT_EMPTY
            elif exc.errno == errno.ENOTDIR:
                self.logger.debug1('Sending not a directory: %s', reason)
                code = FX_NOT_A_DIRECTORY
            elif exc.errno in (errno.ENAMETOOLONG, errno.EILSEQ):
                self.logger.debug1('Sending invalid filename: %s', reason)
                code = FX_INVALID_FILENAME
            elif exc.errno == errno.ELOOP:
                self.logger.debug1('Sending link loop: %s', reason)
                code = FX_LINK_LOOP
            elif exc.errno == errno.EINVAL:
                self.logger.debug1('Sending invalid parameter: %s', reason)
                code = FX_INVALID_PARAMETER
            elif exc.errno == errno.EISDIR:
                self.logger.debug1('Sending file is a directory: %s', reason)
                code = FX_FILE_IS_A_DIRECTORY
            else:
                self.logger.debug1('Sending failure: %s', reason)
                code = FX_FAILURE

            response = SFTPError(code, reason).encode(self._version)
        except Exception as exc: # pragma: no cover
            return_type = FXP_STATUS
            reason = f'Uncaught exception: {exc}'

            self.logger.debug1('Sending failure: %s', reason,
                               exc_info=sys.exc_info)

            response = (UInt32(FX_FAILURE) + String(reason) +
                        String(DEFAULT_LANG))

        self.send_packet(return_type, pktid, UInt32(pktid), response)

    async def _process_open(self, packet: SSHPacket) -> bytes:
        """Process an incoming SFTP open request"""

        path = packet.get_string()

        if self._version >= 5:
            desired_access = packet.get_uint32()
            flags = packet.get_uint32()
            flagmsg = f'access=0x{desired_access:04x}, flags=0x{flags:04x}'
        else:
            pflags = packet.get_uint32()
            flagmsg = f'pflags=0x{pflags:02x}'

        attrs = SFTPAttrs.decode(packet, self._version)

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received open request for %s, %s%s',
                           path, flagmsg, hide_empty(attrs))

        if self._version >= 5:
            unsupported_access = desired_access & ~self._supported_access_mask

            if unsupported_access:
                raise SFTPInvalidParameter(
                    f'Unsupported access flags: 0x{unsupported_access:08x}')

            unsupported_flags = flags & ~self._supported_open_flags

            if unsupported_flags:
                raise SFTPInvalidParameter(
                    f'Unsupported open flags: 0x{unsupported_flags:08x}')

            result = self._server.open56(path, desired_access, flags, attrs)
        else:
            result = self._server.open(path, pflags, attrs)

        if inspect.isawaitable(result):
            result = await cast(Awaitable[object], result)

        handle = self._get_next_handle()
        self._file_handles[handle] = result
        return handle

    async def _process_close(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP close request"""

        handle = packet.get_string()

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received close for handle %s', handle.hex())

        file_obj = self._file_handles.pop(handle, None)
        if file_obj:
            result = self._server.close(file_obj)

            if inspect.isawaitable(result):
                assert result is not None
                await result

            return

        if self._dir_handles.pop(handle, None) is not None:
            return

        raise SFTPInvalidHandle('Invalid file handle')

    async def _process_read(self, packet: SSHPacket) -> Tuple[bytes, bool]:
        """Process an incoming SFTP read request"""

        handle = packet.get_string()
        offset = packet.get_uint64()
        length = packet.get_uint32()

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received read for %s at offset %d in handle %s',
                           plural(length, 'byte'), offset, handle.hex())

        file_obj = self._file_handles.get(handle)

        if file_obj:
            result = self._server.read(file_obj, offset, length)

            if inspect.isawaitable(result):
                result = await cast(Awaitable[bytes], result)

            result: bytes

            if self._version >= 6:
                attrs = await self._server.convert_attrs(
                    self._server.fstat(file_obj))

                at_end = offset + len(result) == attrs.size
            else:
                at_end = False

            if result:
                return cast(bytes, result), at_end
            else:
                raise SFTPEOFError
        else:
            raise SFTPInvalidHandle('Invalid file handle')

    async def _process_write(self, packet: SSHPacket) -> int:
        """Process an incoming SFTP write request"""

        handle = packet.get_string()
        offset = packet.get_uint64()
        data = packet.get_string()

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received write for %s at offset %d in handle %s',
                           plural(len(data), 'byte'), offset, handle.hex())

        file_obj = self._file_handles.get(handle)

        if file_obj:
            result = self._server.write(file_obj, offset, data)

            if inspect.isawaitable(result):
                result = await cast(Awaitable[int], result)

            return cast(int, result)
        else:
            raise SFTPInvalidHandle('Invalid file handle')

    async def _process_lstat(self, packet: SSHPacket) -> _SFTPOSAttrs:
        """Process an incoming SFTP lstat request"""

        path = packet.get_string()

        flags = packet.get_uint32()if self._version >= 4 else 0

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received lstat for %s%s', path,
                           f', flags=0x{flags:08x}' if flags else '')

        # Ignore flags for now, returning all available fields

        result = self._server.lstat(path)

        if inspect.isawaitable(result):
            result = await cast(Awaitable[_SFTPOSAttrs], result)

        result: _SFTPOSAttrs

        return result

    async def _process_fstat(self, packet: SSHPacket) -> _SFTPOSAttrs:
        """Process an incoming SFTP fstat request"""

        handle = packet.get_string()

        flags = packet.get_uint32() if self._version >= 4 else 0

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received fstat for handle %s%s', handle.hex(),
                           f', flags=0x{flags:08x}' if flags else '')

        file_obj = self._file_handles.get(handle)

        if file_obj:
            # Ignore flags for now, returning all available fields
            result = self._server.fstat(file_obj)

            if inspect.isawaitable(result):
                result = await cast(Awaitable[_SFTPOSAttrs], result)

            result: _SFTPOSAttrs

            return result
        else:
            raise SFTPInvalidHandle('Invalid file handle')

    async def _process_setstat(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP setstat request"""

        path = packet.get_string()
        attrs = SFTPAttrs.decode(packet, self._version)

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received setstat for %s%s', path, hide_empty(attrs))

        result = self._server.setstat(path, attrs)

        if inspect.isawaitable(result):
            assert result is not None
            await result

    async def _process_fsetstat(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP fsetstat request"""

        handle = packet.get_string()
        attrs = SFTPAttrs.decode(packet, self._version)

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received fsetstat for handle %s%s',
                           handle.hex(), hide_empty(attrs))

        file_obj = self._file_handles.get(handle)

        if file_obj:
            result = self._server.fsetstat(file_obj, attrs)

            if inspect.isawaitable(result):
                assert result is not None
                await result
        else:
            raise SFTPInvalidHandle('Invalid file handle')

    async def _process_opendir(self, packet: SSHPacket) -> bytes:
        """Process an incoming SFTP opendir request"""

        path = packet.get_string()

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received opendir for %s', path)

        handle = self._get_next_handle()
        self._dir_handles[handle] = self._server.scandir(path)
        return handle

    async def _process_readdir(self, packet: SSHPacket) -> _SFTPNames:
        """Process an incoming SFTP readdir request"""

        handle = packet.get_string()

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received readdir for handle %s', handle.hex())

        names = self._dir_handles.get(handle)

        if names:
            count = 0
            result: List[SFTPName] = []

            async for name in names:
                if not name.longname and self._version == 3:
                    longname_result = self._server.format_longname(name)

                    if inspect.isawaitable(longname_result):
                        assert longname_result is not None
                        await longname_result

                result.append(name)
                count += 1

                if count == _MAX_READDIR_NAMES:
                    break

            if result:
                return result, count < _MAX_READDIR_NAMES
            else:
                raise SFTPEOFError
        else:
            raise SFTPInvalidHandle('Invalid file handle')

    async def _process_remove(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP remove request"""

        path = packet.get_string()

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received remove for %s', path)

        result = self._server.remove(path)

        if inspect.isawaitable(result):
            assert result is not None
            await result

    async def _process_mkdir(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP mkdir request"""

        path = packet.get_string()
        attrs = SFTPAttrs.decode(packet, self._version)

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received mkdir for %s', path)

        result = self._server.mkdir(path, attrs)

        if inspect.isawaitable(result):
            assert result is not None
            await result

    async def _process_rmdir(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP rmdir request"""

        path = packet.get_string()

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received rmdir for %s', path)

        result = self._server.rmdir(path)

        if inspect.isawaitable(result):
            assert result is not None
            await result

    async def _process_realpath(self, packet: SSHPacket) -> _SFTPNames:
        """Process an incoming SFTP realpath request"""

        path = packet.get_string()

        checkmsg = ''
        compose_paths: List[bytes] = []

        if self._version >= 6:
            check = packet.get_byte()

            while packet:
                compose_paths.append(packet.get_string())

            try:
                checkmsg = f', check={self._realpath_check_names[check]}'
            except KeyError:
                raise SFTPInvalidParameter('Invalid check value') from None
        else:
            check = FXRP_NO_CHECK

        self.logger.debug1('Received realpath for %s%s%s', path,
                           b', compose_path: ' + b', '.join(compose_paths)
                           if compose_paths else b'', checkmsg)

        for cpath in compose_paths:
            path = posixpath.join(path, cpath)

        result = self._server.realpath(path)

        if inspect.isawaitable(result):
            result = await cast(Awaitable[bytes], result)

        result: bytes

        attrs = SFTPAttrs()

        if check != FXRP_NO_CHECK:
            try:
                attrs = await self._server.convert_attrs(
                    self._server.stat(result))
            except (OSError, SFTPError):
                if check == FXRP_STAT_ALWAYS:
                    raise

        return [SFTPName(result, attrs=attrs)], False

    async def _process_stat(self, packet: SSHPacket) -> _SFTPOSAttrs:
        """Process an incoming SFTP stat request"""

        path = packet.get_string()

        flags = packet.get_uint32() if self._version >= 4 else 0

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received stat for %s%s', path,
                           f', flags=0x{flags:08x}' if flags else '')

        # Ignore flags for now, returning all available fields
        result = self._server.stat(path)

        if inspect.isawaitable(result):
            result = await cast(Awaitable[_SFTPOSAttrs], result)

        result: _SFTPOSAttrs

        return result

    async def _process_rename(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP rename request"""

        oldpath = packet.get_string()
        newpath = packet.get_string()

        if self._version >= 5:
            flags = packet.get_uint32()
            flag_text = f', flags=0x{flags:08x}'
        else:
            flags = 0
            flag_text = ''

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received rename request from %s to %s%s',
                           oldpath, newpath, flag_text)

        if flags:
            result = self._server.posix_rename(oldpath, newpath)
        else:
            result = self._server.rename(oldpath, newpath)

        if inspect.isawaitable(result):
            assert result is not None
            await result

    async def _process_readlink(self, packet: SSHPacket) -> _SFTPNames:
        """Process an incoming SFTP readlink request"""

        path = packet.get_string()

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received readlink for %s', path)

        result = self._server.readlink(path)

        if inspect.isawaitable(result):
            result = await cast(Awaitable[bytes], result)

        result: bytes

        return [SFTPName(result)], False

    async def _process_symlink(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP symlink request"""

        if self._nonstandard_symlink:
            oldpath = packet.get_string()
            newpath = packet.get_string()
        else:
            newpath = packet.get_string()
            oldpath = packet.get_string()

        packet.check_end()

        self.logger.debug1('Received symlink request from %s to %s',
                           oldpath, newpath)

        result = self._server.symlink(oldpath, newpath)

        if inspect.isawaitable(result):
            assert result is not None
            await result

    async def _process_link(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP hard link request"""

        newpath = packet.get_string()
        oldpath = packet.get_string()
        symlink = packet.get_boolean()

        if symlink:
            self.logger.debug1('Received symlink request from %s to %s',
                               oldpath, newpath)

            result = self._server.symlink(oldpath, newpath)
        else:
            self.logger.debug1('Received hardlink request from %s to %s',
                               oldpath, newpath)

            result = self._server.link(oldpath, newpath)

        if inspect.isawaitable(result):
            assert result is not None
            await result

    async def _process_lock(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP byte range lock request"""

        handle = packet.get_string()
        offset = packet.get_uint64()
        length = packet.get_uint64()
        flags = packet.get_uint32()

        self.logger.debug1('Received byte range lock request for '
                           'handle %s, offset %d, length %d, '
                           'flags 0x%04x', handle.hex(), offset,
                           length, flags)

        file_obj = self._file_handles.get(handle)

        if file_obj:
            result = self._server.lock(file_obj, offset, length, flags)

            if inspect.isawaitable(result): # pragma: no branch
                assert result is not None
                await result
        else:
            raise SFTPInvalidHandle('Invalid file handle')

    async def _process_unlock(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP byte range unlock request"""

        handle = packet.get_string()
        offset = packet.get_uint64()
        length = packet.get_uint64()

        self.logger.debug1('Received byte range lock request for '
                           'handle %s, offset %d, length %d',
                           handle.hex(), offset, length)

        file_obj = self._file_handles.get(handle)

        if file_obj:
            result = self._server.unlock(file_obj, offset, length)

            if inspect.isawaitable(result): # pragma: no branch
                assert result is not None
                await result
        else:
            raise SFTPInvalidHandle('Invalid file handle')

    async def _process_posix_rename(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP POSIX rename request"""

        oldpath = packet.get_string()
        newpath = packet.get_string()
        packet.check_end()

        self.logger.debug1('Received POSIX rename request from %s to %s',
                           oldpath, newpath)

        result = self._server.posix_rename(oldpath, newpath)

        if inspect.isawaitable(result):
            assert result is not None
            await result

    async def _process_statvfs(self, packet: SSHPacket) -> _SFTPOSVFSAttrs:
        """Process an incoming SFTP statvfs request"""

        path = packet.get_string()
        packet.check_end()

        self.logger.debug1('Received statvfs for %s', path)

        result = self._server.statvfs(path)

        if inspect.isawaitable(result):
            result = await cast(Awaitable[_SFTPOSVFSAttrs], result)

        result: _SFTPOSVFSAttrs

        return result

    async def _process_fstatvfs(self, packet: SSHPacket) -> _SFTPOSVFSAttrs:
        """Process an incoming SFTP fstatvfs request"""

        handle = packet.get_string()
        packet.check_end()

        self.logger.debug1('Received fstatvfs for handle %s', handle.hex())

        file_obj = self._file_handles.get(handle)

        if file_obj:
            result = self._server.fstatvfs(file_obj)

            if inspect.isawaitable(result):
                result = await cast(Awaitable[_SFTPOSVFSAttrs], result)

            result: _SFTPOSVFSAttrs

            return result
        else:
            raise SFTPInvalidHandle('Invalid file handle')

    async def _process_openssh_link(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP hard link request"""

        oldpath = packet.get_string()
        newpath = packet.get_string()
        packet.check_end()

        self.logger.debug1('Received hardlink request from %s to %s',
                           oldpath, newpath)

        result = self._server.link(oldpath, newpath)

        if inspect.isawaitable(result):
            assert result is not None
            await result

    async def _process_fsync(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP fsync request"""

        handle = packet.get_string()
        packet.check_end()

        self.logger.debug1('Received fsync for handle %s', handle.hex())

        file_obj = self._file_handles.get(handle)

        if file_obj:
            result = self._server.fsync(file_obj)

            if inspect.isawaitable(result):
                assert result is not None
                await result
        else:
            raise SFTPInvalidHandle('Invalid file handle')

    async def _process_lsetstat(self, packet: SSHPacket) -> None:
        """Process an incoming SFTP lsetstat request"""

        path = packet.get_string()
        attrs = SFTPAttrs.decode(packet, self._version)

        if self._version < 6:
            packet.check_end()

        self.logger.debug1('Received lsetstat for %s%s',
                           path, hide_empty(attrs))

        result = self._server.lsetstat(path, attrs)

        if inspect.isawaitable(result):
            assert result is not None
            await result

    async def _process_limits(self, packet: SSHPacket) -> SFTPLimits:
        """Process an incoming SFTP limits request"""

        packet.check_end()

        nfiles = os.sysconf('SC_OPEN_MAX') - 5 if hasattr(os, 'sysconf') else 0

        return SFTPLimits(MAX_SFTP_PACKET_LEN, MAX_SFTP_READ_LEN,
                          MAX_SFTP_WRITE_LEN, nfiles)

    async def _process_copy_data(self, packet: SSHPacket) -> None:
        """Process an incoming copy data request"""

        read_from_handle = packet.get_string()
        read_from_offset = packet.get_uint64()
        read_from_length = packet.get_uint64()
        write_to_handle = packet.get_string()
        write_to_offset = packet.get_uint64()
        packet.check_end()

        self.logger.debug1('Received copy-data from handle %s, '
                           'offset %d, length %d to handle %s, '
                           'offset %d', read_from_handle.hex(),
                           read_from_offset, read_from_length,
                           write_to_handle.hex(), write_to_offset)

        src = self._file_handles.get(read_from_handle)
        dst = self._file_handles.get(write_to_handle)

        if src and dst:
            read_to_end = read_from_length == 0

            while read_to_end or read_from_length:
                if read_to_end:
                    size = _COPY_DATA_BLOCK_SIZE
                else:
                    size = min(read_from_length, _COPY_DATA_BLOCK_SIZE)

                data = self._server.read(src, read_from_offset, size)

                if inspect.isawaitable(data):
                    data = await cast(Awaitable[bytes], data)

                result = self._server.write(dst, write_to_offset, data)

                if inspect.isawaitable(result):
                    await result

                if len(data) < size:
                    break

                read_from_offset += size
                write_to_offset += size

                if not read_to_end:
                    read_from_length -= size
        else:
            raise SFTPInvalidHandle('Invalid file handle')

    _packet_handlers: Dict[Union[int, bytes], _SFTPPacketHandler] = {
        FXP_OPEN:                     _process_open,
        FXP_CLOSE:                    _process_close,
        FXP_READ:                     _process_read,
        FXP_WRITE:                    _process_write,
        FXP_LSTAT:                    _process_lstat,
        FXP_FSTAT:                    _process_fstat,
        FXP_SETSTAT:                  _process_setstat,
        FXP_FSETSTAT:                 _process_fsetstat,
        FXP_OPENDIR:                  _process_opendir,
        FXP_READDIR:                  _process_readdir,
        FXP_REMOVE:                   _process_remove,
        FXP_MKDIR:                    _process_mkdir,
        FXP_RMDIR:                    _process_rmdir,
        FXP_REALPATH:                 _process_realpath,
        FXP_STAT:                     _process_stat,
        FXP_RENAME:                   _process_rename,
        FXP_READLINK:                 _process_readlink,
        FXP_SYMLINK:                  _process_symlink,
        FXP_LINK:                     _process_link,
        FXP_BLOCK:                    _process_lock,
        FXP_UNBLOCK:                  _process_unlock,
        b'posix-rename@openssh.com':  _process_posix_rename,
        b'statvfs@openssh.com':       _process_statvfs,
        b'fstatvfs@openssh.com':      _process_fstatvfs,
        b'hardlink@openssh.com':      _process_openssh_link,
        b'fsync@openssh.com':         _process_fsync,
        b'lsetstat@openssh.com':      _process_lsetstat,
        b'limits@openssh.com':        _process_limits,
        b'copy-data':                 _process_copy_data
    }

    async def run(self) -> None:
        """Run an SFTP server"""

        assert self._reader is not None

        try:
            packet = await self.recv_packet()
            pkttype = packet.get_byte()
            self.log_received_packet(pkttype, None, packet)

            if pkttype != FXP_INIT:
                await self._cleanup(SFTPBadMessage('Expected init message'))
                return

            version = packet.get_uint32()
            rcvd_extensions: List[Tuple[bytes, bytes]] = []

            if version == 3:
                while packet:
                    name = packet.get_string()
                    data = packet.get_string()
                    rcvd_extensions.append((name, data))
            else:
                packet.check_end()
        except PacketDecodeError as exc:
            await self._cleanup(SFTPBadMessage(str(exc)))
            return
        except Error as exc:
            await self._cleanup(exc)
            return

        self.logger.debug1('Received init, version=%d%s', version,
                           ', extensions:' if rcvd_extensions else '')

        self._log_extensions(rcvd_extensions)

        self._version = min(version, self._version)

        extensions: List[Tuple[bytes, bytes]] = []

        ext_names = b''.join(String(name) for (name, _) in self._extensions)

        attrib_ext_names = b''.join(String(name) for name in
                                    self._attrib_extensions)

        if self._version == 5:
            supported = UInt32(self._supported_attr_mask) + \
                        UInt32(self._supported_attrib_mask) + \
                        UInt32(self._supported_open_flags) + \
                        UInt32(self._supported_access_mask) + \
                        UInt32(MAX_SFTP_READ_LEN) + ext_names + \
                        attrib_ext_names

            extensions.append((b'supported', supported))
        elif self._version == 6:
            acl_supported = UInt32(0) # No ACL support yet

            supported2 = UInt32(self._supported_attr_mask) + \
                         UInt32(self._supported_attrib_mask) + \
                         UInt32(self._supported_open_flags) + \
                         UInt32(self._supported_access_mask) + \
                         UInt32(MAX_SFTP_READ_LEN) + \
                         UInt16(self._supported_open_block_vector) + \
                         UInt16(self._supported_block_vector) + \
                         UInt32(len(self._attrib_extensions)) + \
                         attrib_ext_names + \
                         UInt32(len(self._extensions)) + \
                         ext_names

            extensions.append((b'acl-supported', acl_supported))
            extensions.append((b'supported2', supported2))

        extensions.extend(self._extensions)

        self.logger.debug1('Sending version=%d%s', self._version,
                           ', extensions:' if extensions else '')

        self._log_extensions(extensions)

        sent_extensions: Iterable[bytes] = \
            (String(name) + String(data) for name, data in extensions)

        try:
            self.send_packet(FXP_VERSION, None, UInt32(self._version),
                             *sent_extensions)
        except SFTPError as exc:
            await self._cleanup(exc)
            return

        if self._version == 3:
            # Check if the client has a buggy SYMLINK implementation

            client_version = cast(str,
                self._reader.get_extra_info('client_version', ''))

            if any(name in client_version
                   for name in self._nonstandard_symlink_impls):
                self.logger.debug1('Adjusting for non-standard symlink '
                                   'implementation')
                self._nonstandard_symlink = True

        await self.recv_packets()


class SFTPServer:
    """SFTP server

       Applications should subclass this when implementing an SFTP
       server. The methods listed below should be implemented to
       provide the desired application behavior.

           .. note:: Any method can optionally be defined as a
                     coroutine if that method needs to perform
                     blocking operations to determine its result.

       The `chan` object provided here is the :class:`SSHServerChannel`
       instance this SFTP server is associated with. It can be queried to
       determine which user the client authenticated as, environment
       variables set on the channel when it was opened, and key and
       certificate options or permissions associated with this session.

           .. note:: In AsyncSSH 1.x, this first argument was an
                     :class:`SSHServerConnection`, not an
                     :class:`SSHServerChannel`. When moving to AsyncSSH
                     2.x, subclasses of :class:`SFTPServer` which
                     implement an __init__ method will need to be
                     updated to account for this change, and pass this
                     through to the parent.

       If the `chroot` argument is specified when this object is
       created, the default :meth:`map_path` and :meth:`reverse_map_path`
       methods will enforce a virtual root directory starting in that
       location, limiting access to only files within that directory
       tree. This will also affect path names returned by the
       :meth:`realpath` and :meth:`readlink` methods.

    """

    # The default implementation of a number of these methods don't need self
    # pylint: disable=no-self-use

    def __init__(self, chan: 'SSHServerChannel',
                 chroot: Optional[bytes] = None):
        self._chan = chan

        self._chroot: Optional[bytes]

        if chroot:
            self._chroot = _from_local_path(os.path.realpath(chroot))
        else:
            self._chroot = None

    @property
    def channel(self) -> 'SSHServerChannel':
        """The channel associated with this SFTP server session"""

        return self._chan

    @property
    def connection(self) -> 'SSHServerConnection':
        """The channel associated with this SFTP server session"""

        return cast('SSHServerConnection', self._chan.get_connection())

    @property
    def env(self) -> Mapping[str, str]:
        """The environment associated with this SFTP server session

           This method returns the environment set by the client
           when this SFTP session was opened.

           :returns: A dictionary containing the environment variables
                     set by the client

        """

        return self._chan.get_environment()

    @property
    def logger(self) -> SSHLogger:
        """A logger associated with this SFTP server"""

        return self._chan.logger

    async def convert_attrs(self, result: MaybeAwait[_SFTPOSAttrs]) -> \
            SFTPAttrs:
        """Convert stat result to SFTPAttrs"""

        if inspect.isawaitable(result):
            result = await cast(Awaitable[_SFTPOSAttrs], result)

        result: _SFTPOSAttrs

        if isinstance(result, os.stat_result):
            result = SFTPAttrs.from_local(result)

        result: SFTPAttrs

        return result

    async def _to_sftpname(self, parent: bytes, name: bytes) -> SFTPName:
        """Construct an SFTPName for a filename in a directory"""

        path = posixpath.join(parent, name)
        attrs = await self.convert_attrs(self.lstat(path))
        return SFTPName(name, attrs=attrs)

    def format_user(self, uid: Optional[int]) -> str:
        """Return the user name associated with a uid

           This method returns a user name string to insert into
           the `longname` field of an :class:`SFTPName` object.

           By default, it calls the Python :func:`pwd.getpwuid`
           function if it is available, or returns the numeric
           uid as a string if not. If there is no uid, it returns
           an empty string.

           :param uid:
               The uid value to look up
           :type uid: `int` or `None`

           :returns: The formatted user name string

        """

        return _lookup_user(uid)

    def format_group(self, gid: Optional[int]) -> str:
        """Return the group name associated with a gid

           This method returns a group name string to insert into
           the `longname` field of an :class:`SFTPName` object.

           By default, it calls the Python :func:`grp.getgrgid`
           function if it is available, or returns the numeric
           gid as a string if not. If there is no gid, it returns
           an empty string.

           :param gid:
               The gid value to look up
           :type gid: `int` or `None`

           :returns: The formatted group name string

        """

        return _lookup_group(gid)

    def format_longname(self, name: SFTPName) -> MaybeAwait[None]:
        """Format the long name associated with an SFTP name

           This method fills in the `longname` field of a
           :class:`SFTPName` object. By default, it generates
           something similar to UNIX "ls -l" output. The `filename`
           and `attrs` fields of the :class:`SFTPName` should
           already be filled in before this method is called.

           :param name:
               The :class:`SFTPName` instance to format the long name for
           :type name: :class:`SFTPName`

        """

        if name.attrs.permissions is not None:
            mode = stat.filemode(name.attrs.permissions)
        else:
            mode = ''

        nlink = str(name.attrs.nlink) if name.attrs.nlink else ''

        user = self.format_user(name.attrs.uid)
        group = self.format_group(name.attrs.gid)

        size = str(name.attrs.size) if name.attrs.size is not None else ''

        if name.attrs.mtime is not None:
            now = time.time()
            mtime = time.localtime(name.attrs.mtime)
            modtime = time.strftime('%b ', mtime)

            try:
                modtime += time.strftime('%e', mtime)
            except ValueError:
                modtime += time.strftime('%d', mtime)

            if now - 365*24*60*60/2 < name.attrs.mtime <= now:
                modtime += time.strftime(' %H:%M', mtime)
            else:
                modtime += time.strftime('  %Y', mtime)
        else:
            modtime = ''

        detail = f'{mode:10s} {nlink:>4s} {user:8s} {group:8s} ' \
                 f'{size:>8s} {modtime:12s} '

        name.longname = detail.encode('utf-8') + cast(bytes, name.filename)

        return None

    def map_path(self, path: bytes) -> bytes:
        """Map the path requested by the client to a local path

           This method can be overridden to provide a custom mapping
           from path names requested by the client to paths in the local
           filesystem. By default, it will enforce a virtual "chroot"
           if one was specified when this server was created. Otherwise,
           path names are left unchanged, with relative paths being
           interpreted based on the working directory of the currently
           running process.

           :param path:
               The path name to map
           :type path: `bytes`

           :returns: bytes containing the local path name to operate on

        """

        if self._chroot:
            normpath = posixpath.normpath(posixpath.join(b'/', path))
            return posixpath.join(self._chroot, normpath[1:])
        else:
            return path

    def reverse_map_path(self, path: bytes) -> bytes:
        """Reverse map a local path into the path reported to the client

           This method can be overridden to provide a custom reverse
           mapping for the mapping provided by :meth:`map_path`. By
           default, it hides the portion of the local path associated
           with the virtual "chroot" if one was specified.

           :param path:
               The local path name to reverse map
           :type path: `bytes`

           :returns: bytes containing the path name to report to the client

        """

        if self._chroot:
            if path == self._chroot:
                return b'/'
            elif path.startswith(self._chroot + b'/'):
                return path[len(self._chroot):]
            else:
                raise SFTPNoSuchFile('File not found')
        else:
            return path

    def open(self, path: bytes, pflags: int, attrs: SFTPAttrs) -> \
            MaybeAwait[object]:
        """Open a file to serve to a remote client

           This method returns a file object which can be used to read
           and write data and get and set file attributes.

           The possible open mode flags and their meanings are:

             ========== ======================================================
             Mode       Description
             ========== ======================================================
             FXF_READ   Open the file for reading. If neither FXF_READ nor
                        FXF_WRITE are set, this is the default.
             FXF_WRITE  Open the file for writing. If both this and FXF_READ
                        are set, open the file for both reading and writing.
             FXF_APPEND Force writes to append data to the end of the file
                        regardless of seek position.
             FXF_CREAT  Create the file if it doesn't exist. Without this,
                        attempts to open a non-existent file will fail.
             FXF_TRUNC  Truncate the file to zero length if it already exists.
             FXF_EXCL   Return an error when trying to open a file which
                        already exists.
             ========== ======================================================

           The attrs argument is used to set initial attributes of the
           file if it needs to be created. Otherwise, this argument is
           ignored.

           :param path:
               The name of the file to open
           :param pflags:
               The access mode to use for the file (see above)
           :param attrs:
               File attributes to use if the file needs to be created
           :type path: `bytes`
           :type pflags: `int`
           :type attrs: :class:`SFTPAttrs`

           :returns: A file object to use to access the file

           :raises: :exc:`SFTPError` to return an error to the client

        """

        if pflags & FXF_EXCL:
            mode = 'xb'
        elif pflags & FXF_APPEND:
            mode = 'ab'
        elif pflags & FXF_WRITE and not pflags & FXF_READ:
            mode = 'wb'
        else:
            mode = 'rb'

        if pflags & FXF_READ and pflags & FXF_WRITE:
            mode += '+'
            flags = os.O_RDWR
        elif pflags & FXF_WRITE:
            flags = os.O_WRONLY
        else:
            flags = os.O_RDONLY

        if pflags & FXF_APPEND:
            flags |= os.O_APPEND

        if pflags & FXF_CREAT:
            flags |= os.O_CREAT

        if pflags & FXF_TRUNC:
            flags |= os.O_TRUNC

        if pflags & FXF_EXCL:
            flags |= os.O_EXCL

        try:
            flags |= os.O_BINARY
        except AttributeError: # pragma: no cover
            pass

        perms = 0o666 if attrs.permissions is None else attrs.permissions
        return open(_to_local_path(self.map_path(path)), mode, buffering=0,
                    opener=lambda path, _: os.open(path, flags, perms))

    def open56(self, path: bytes, desired_access: int, flags: int,
               attrs: SFTPAttrs) -> MaybeAwait[object]:
        """Open a file to serve to a remote client (SFTPv5 and later)

           This method returns a file object which can be used to read
           and write data and get and set file attributes.

           Supported desired_access bits include `ACE4_READ_DATA`,
           `ACE4_WRITE_DATA`, `ACE4_APPEND_DATA`, `ACE4_READ_ATTRIBUTES`,
           and `ACE4_WRITE_ATTRIBUTES`.

           Supported disposition bits in flags and their meanings are:

             ===================== ============================================
             Disposition           Description
             ===================== ============================================
             FXF_OPEN_EXISTING     Open an existing file
             FXF_OPEN_OR_CREATE    Open an existing file or create a new one
             FXF_CREATE_NEW        Create a new file
             FXF_CREATE_TRUNCATE   Create a new file or truncate an existing
                                   one
             FXF_TRUNCATE_EXISTING Truncate an existing file
             ===================== ============================================

           Other supported flag bits are:

             ===================== ============================================
             Flag                  Description
             ===================== ============================================
             FXF_APPEND_DATA       Append data writes to the end of the file
             ===================== ============================================

           The attrs argument is used to set initial attributes of the
           file if it needs to be created. Otherwise, this argument is
           ignored.

           :param path:
               The name of the file to open
           :param desired_access:
               The access mode to use for the file (see above)
           :param flags:
               The access flags to use for the file (see above)
           :param attrs:
               File attributes to use if the file needs to be created
           :type path: `bytes`
           :type desired_access: `int`
           :type flags: `int`
           :type attrs: :class:`SFTPAttrs`

           :returns: A file object to use to access the file

           :raises: :exc:`SFTPError` to return an error to the client

        """

        if desired_access & ACE4_READ_DATA and \
                desired_access &  ACE4_WRITE_DATA:
            open_flags = os.O_RDWR
        elif desired_access & ACE4_WRITE_DATA:
            open_flags = os.O_WRONLY
        else:
            open_flags = os.O_RDONLY

        disp = flags & FXF_ACCESS_DISPOSITION

        if disp == FXF_CREATE_NEW:
            mode = 'xb'
            open_flags |= os.O_CREAT | os.O_EXCL
        elif disp == FXF_CREATE_TRUNCATE:
            mode = 'wb'
            open_flags |= os.O_CREAT | os.O_TRUNC
        elif disp == FXF_OPEN_OR_CREATE:
            mode = 'wb'
            open_flags |= os.O_CREAT
        elif disp == FXF_TRUNCATE_EXISTING:
            mode = 'wb'
            open_flags |= os.O_TRUNC
        else:
            mode = 'wb' if desired_access & ACE4_WRITE_DATA else 'rb'

        if desired_access & ACE4_APPEND_DATA or flags & FXF_APPEND_DATA:
            mode = 'ab'
            open_flags |= os.O_APPEND

        if desired_access & ACE4_READ_DATA and \
                desired_access & ACE4_WRITE_DATA:
            mode += '+'

        try:
            open_flags |= os.O_BINARY
        except AttributeError: # pragma: no cover
            pass

        perms = 0o666 if attrs.permissions is None else attrs.permissions
        return open(_to_local_path(self.map_path(path)), mode, buffering=0,
                    opener=lambda path, _: os.open(path, open_flags, perms))

    def close(self, file_obj: object) -> MaybeAwait[None]:
        """Close an open file or directory

           :param file_obj:
               The file or directory object to close
           :type file_obj: file

           :raises: :exc:`SFTPError` to return an error to the client

        """

        file_obj = cast(_SFTPFileObj, file_obj)
        file_obj.close()
        return None

    def read(self, file_obj: object, offset: int, size: int) -> \
            MaybeAwait[bytes]:
        """Read data from an open file

           :param file_obj:
               The file to read from
           :param offset:
               The offset from the beginning of the file to begin reading
           :param size:
               The number of bytes to read
           :type file_obj: file
           :type offset: `int`
           :type size: `int`

           :returns: bytes read from the file

           :raises: :exc:`SFTPError` to return an error to the client

        """

        file_obj = cast(_SFTPFileObj, file_obj)
        file_obj.seek(offset)
        return file_obj.read(size)

    def write(self, file_obj: object, offset: int, data: bytes) -> \
            MaybeAwait[int]:
        """Write data to an open file

           :param file_obj:
               The file to write to
           :param offset:
               The offset from the beginning of the file to begin writing
           :param data:
               The data to write to the file
           :type file_obj: file
           :type offset: `int`
           :type data: `bytes`

           :returns: number of bytes written

           :raises: :exc:`SFTPError` to return an error to the client

        """

        file_obj = cast(_SFTPFileObj, file_obj)
        file_obj.seek(offset)
        return file_obj.write(data)

    def lstat(self, path: bytes) -> MaybeAwait[_SFTPOSAttrs]:
        """Get attributes of a file, directory, or symlink

           This method queries the attributes of a file, directory,
           or symlink. Unlike :meth:`stat`, this method should
           return the attributes of a symlink itself rather than
           the target of that link.

           :param path:
               The path of the file, directory, or link to get attributes for
           :type path: `bytes`

           :returns: An :class:`SFTPAttrs` or an os.stat_result containing
                     the file attributes

           :raises: :exc:`SFTPError` to return an error to the client

        """

        return os.lstat(_to_local_path(self.map_path(path)))

    def fstat(self, file_obj: object) -> MaybeAwait[_SFTPOSAttrs]:
        """Get attributes of an open file

           :param file_obj:
               The file to get attributes for
           :type file_obj: file

           :returns: An :class:`SFTPAttrs` or an os.stat_result containing
                     the file attributes

           :raises: :exc:`SFTPError` to return an error to the client

        """

        file_obj = cast(_SFTPFileObj, file_obj)
        file_obj.flush()
        return os.fstat(file_obj.fileno())

    def setstat(self, path: bytes, attrs: SFTPAttrs) -> MaybeAwait[None]:
        """Set attributes of a file or directory

           This method sets attributes of a file or directory. If
           the path provided is a symbolic link, the attributes
           should be set on the target of the link. A subset of the
           fields in `attrs` can be initialized and only those
           attributes should be changed.

           :param path:
               The path of the remote file or directory to set attributes for
           :param attrs:
               File attributes to set
           :type path: `bytes`
           :type attrs: :class:`SFTPAttrs`

           :raises: :exc:`SFTPError` to return an error to the client

        """

        _setstat(_to_local_path(self.map_path(path)), attrs)

        return None

    def lsetstat(self, path: bytes, attrs: SFTPAttrs) -> MaybeAwait[None]:
        """Set attributes of a file, directory, or symlink

           This method sets attributes of a file, directory, or symlink.
           A subset of the fields in `attrs` can be initialized and only
           those attributes should be changed.

           :param path:
               The path of the remote file or directory to set attributes for
           :param attrs:
               File attributes to set
           :type path: `bytes`
           :type attrs: :class:`SFTPAttrs`

           :raises: :exc:`SFTPError` to return an error to the client

        """

        _setstat(_to_local_path(self.map_path(path)), attrs,
                 follow_symlinks=False)

        return None

    def fsetstat(self, file_obj: object, attrs: SFTPAttrs) -> MaybeAwait[None]:
        """Set attributes of an open file

           :param file_obj:
               The file to set attributes for
           :param attrs:
               File attributes to set on the file
           :type file_obj: file
           :type attrs: :class:`SFTPAttrs`

           :raises: :exc:`SFTPError` to return an error to the client

        """

        file_obj = cast(_SFTPFileObj, file_obj)
        file_obj.flush()

        if sys.platform == 'win32': # pragma: no cover
            _setstat(file_obj.name, attrs)
        else:
            _setstat(file_obj.fileno(), attrs)

        return None

    async def scandir(self, path: bytes) -> AsyncIterator[SFTPName]:
        """Return names and attributes of the files in a directory

           This function returns an async iterator of :class:`SFTPName`
           entries corresponding to files in the requested directory.

           :param path:
               The path of the directory to scan
           :type path: `bytes`

           :returns: An async iterator of :class:`SFTPName`

           :raises: :exc:`SFTPError` to return an error to the client

        """

        if hasattr(self, 'listdir'):
            # Support backward compatibility with older AsyncSSH versions
            # which allowed listdir() to be overridden, returning a list
            # of either :class:`SFTPName` objects or plain filenames, in
            # which case :meth:`lstat` is called to retrieve attribute
            # information.

            # pylint: disable=no-member
            listdir_result = self.listdir(path) # type: ignore

            if inspect.isawaitable(listdir_result):
                listdir_result = await cast(
                    Awaitable[Sequence[Union[bytes, SFTPName]]],
                    listdir_result)

            listdir_result: Sequence[Union[bytes, SFTPName]]

            for name in listdir_result:
                if isinstance(name, bytes):
                    yield await self._to_sftpname(path, name)
                else:
                    yield name
        else:
            for name in (b'.', b'..'):
                yield await self._to_sftpname(path, name)

            with os.scandir(_to_local_path(self.map_path(path))) as entries:
                for entry in entries:
                    filename = entry.name

                    if sys.platform == 'win32': # pragma: no cover
                        filename = os.fsencode(filename)

                    attrs = SFTPAttrs.from_local(
                        entry.stat(follow_symlinks=False))

                    yield SFTPName(filename, attrs=attrs)

    def remove(self, path: bytes) -> MaybeAwait[None]:
        """Remove a file or symbolic link

           :param path:
               The path of the file or link to remove
           :type path: `bytes`

           :raises: :exc:`SFTPError` to return an error to the client

        """

        os.remove(_to_local_path(self.map_path(path)))
        return None

    def mkdir(self, path: bytes, attrs: SFTPAttrs) -> MaybeAwait[None]:
        """Create a directory with the specified attributes

           :param path:
               The path of where the new directory should be created
           :param attrs:
               The file attributes to use when creating the directory
           :type path: `bytes`
           :type attrs: :class:`SFTPAttrs`

           :raises: :exc:`SFTPError` to return an error to the client

        """

        mode = 0o777 if attrs.permissions is None else attrs.permissions
        os.mkdir(_to_local_path(self.map_path(path)), mode)
        return None

    def rmdir(self, path: bytes) -> MaybeAwait[None]:
        """Remove a directory

           :param path:
               The path of the directory to remove
           :type path: `bytes`

           :raises: :exc:`SFTPError` to return an error to the client

        """

        os.rmdir(_to_local_path(self.map_path(path)))
        return None

    def realpath(self, path: bytes) -> MaybeAwait[bytes]:
        """Return the canonical version of a path

           :param path:
               The path of the directory to canonicalize
           :type path: `bytes`

           :returns: bytes containing the canonical path

           :raises: :exc:`SFTPError` to return an error to the client

        """

        path = os.path.realpath(_to_local_path(self.map_path(path)))
        return self.reverse_map_path(_from_local_path(path))

    def stat(self, path: bytes) -> MaybeAwait[_SFTPOSAttrs]:
        """Get attributes of a file or directory, following symlinks

           This method queries the attributes of a file or directory.
           If the path provided is a symbolic link, the returned
           attributes should correspond to the target of the link.

           :param path:
               The path of the remote file or directory to get attributes for
           :type path: `bytes`

           :returns: An :class:`SFTPAttrs` or an os.stat_result containing
                     the file attributes

           :raises: :exc:`SFTPError` to return an error to the client

        """

        return os.stat(_to_local_path(self.map_path(path)))

    def rename(self, oldpath: bytes, newpath: bytes) -> MaybeAwait[None]:
        """Rename a file, directory, or link

           This method renames a file, directory, or link.

           .. note:: This is a request for the standard SFTP version
                     of rename which will not overwrite the new path
                     if it already exists. The :meth:`posix_rename`
                     method will be called if the client requests the
                     POSIX behavior where an existing instance of the
                     new path is removed before the rename.

           :param oldpath:
               The path of the file, directory, or link to rename
           :param newpath:
               The new name for this file, directory, or link
           :type oldpath: `bytes`
           :type newpath: `bytes`

           :raises: :exc:`SFTPError` to return an error to the client

        """

        oldpath = _to_local_path(self.map_path(oldpath))
        newpath = _to_local_path(self.map_path(newpath))

        if os.path.exists(newpath):
            raise SFTPFileAlreadyExists('File already exists')

        os.rename(oldpath, newpath)
        return None

    def readlink(self, path: bytes) -> MaybeAwait[bytes]:
        """Return the target of a symbolic link

           :param path:
               The path of the symbolic link to follow
           :type path: `bytes`

           :returns: bytes containing the target path of the link

           :raises: :exc:`SFTPError` to return an error to the client

        """

        path = os.readlink(_to_local_path(self.map_path(path)))

        if sys.platform == 'win32' and \
                path.startswith('\\\\?\\'): # pragma: no cover
            path = path[4:]

        if self._chroot:
            path = os.path.realpath(path)

        return self.reverse_map_path(_from_local_path(path))

    def symlink(self, oldpath: bytes, newpath: bytes) -> MaybeAwait[None]:
        """Create a symbolic link

           :param oldpath:
               The path the link should point to
           :param newpath:
               The path of where to create the symbolic link
           :type oldpath: `bytes`
           :type newpath: `bytes`

           :raises: :exc:`SFTPError` to return an error to the client

        """

        if posixpath.isabs(oldpath):
            oldpath = self.map_path(oldpath)
        else:
            newdir = posixpath.dirname(newpath)
            abspath1 = self.map_path(posixpath.join(newdir, oldpath))

            mapped_newdir = self.map_path(newdir)
            abspath2 = os.path.join(mapped_newdir, oldpath)

            # Make sure the symlink doesn't point outside the chroot
            if os.path.realpath(abspath1) != os.path.realpath(abspath2):
                oldpath = os.path.relpath(abspath1, start=mapped_newdir)

        newpath = self.map_path(newpath)

        os.symlink(_to_local_path(oldpath), _to_local_path(newpath))
        return None

    def link(self, oldpath: bytes, newpath: bytes) -> MaybeAwait[None]:
        """Create a hard link

           :param oldpath:
               The path of the file the hard link should point to
           :param newpath:
               The path of where to create the hard link
           :type oldpath: `bytes`
           :type newpath: `bytes`

           :raises: :exc:`SFTPError` to return an error to the client

        """

        oldpath = _to_local_path(self.map_path(oldpath))
        newpath = _to_local_path(self.map_path(newpath))

        os.link(oldpath, newpath)
        return None

    def lock(self, file_obj: object, offset: int, length: int,
             flags: int) -> MaybeAwait[None]:
        """Acquire a byte range lock on an open file"""

        raise SFTPOpUnsupported('Byte range locks not supported')

    def unlock(self, file_obj: object, offset: int,
               length: int) -> MaybeAwait[None]:
        """Release a byte range lock on an open file"""

        raise SFTPOpUnsupported('Byte range locks not supported')

    def posix_rename(self, oldpath: bytes, newpath: bytes) -> MaybeAwait[None]:
        """Rename a file, directory, or link with POSIX semantics

           This method renames a file, directory, or link, removing
           the prior instance of new path if it previously existed.

           :param oldpath:
               The path of the file, directory, or link to rename
           :param newpath:
               The new name for this file, directory, or link
           :type oldpath: `bytes`
           :type newpath: `bytes`

           :raises: :exc:`SFTPError` to return an error to the client

        """

        oldpath = _to_local_path(self.map_path(oldpath))
        newpath = _to_local_path(self.map_path(newpath))

        os.replace(oldpath, newpath)
        return None

    def statvfs(self, path: bytes) -> MaybeAwait[_SFTPOSVFSAttrs]:
        """Get attributes of the file system containing a file

           :param path:
               The path of the file system to get attributes for
           :type path: `bytes`

           :returns: An :class:`SFTPVFSAttrs` or an os.statvfs_result
                     containing the file system attributes

           :raises: :exc:`SFTPError` to return an error to the client

        """

        try:
            return os.statvfs(_to_local_path(self.map_path(path)))
        except AttributeError: # pragma: no cover
            raise SFTPOpUnsupported('statvfs not supported') from None

    def fstatvfs(self, file_obj: object) -> MaybeAwait[_SFTPOSVFSAttrs]:
        """Return attributes of the file system containing an open file

           :param file_obj:
               The open file to get file system attributes for
           :type file_obj: file

           :returns: An :class:`SFTPVFSAttrs` or an os.statvfs_result
                     containing the file system attributes

           :raises: :exc:`SFTPError` to return an error to the client

        """

        file_obj = cast(_SFTPFileObj, file_obj)

        try:
            return os.statvfs(file_obj.fileno())
        except AttributeError: # pragma: no cover
            raise SFTPOpUnsupported('fstatvfs not supported') from None

    def fsync(self, file_obj: object) -> MaybeAwait[None]:
        """Force file data to be written to disk

           :param file_obj:
               The open file containing the data to flush to disk
           :type file_obj: file

           :raises: :exc:`SFTPError` to return an error to the client

        """

        file_obj = cast(_SFTPFileObj, file_obj)
        os.fsync(file_obj.fileno())
        return None

    def exit(self) -> MaybeAwait[None]:
        """Shut down this SFTP server"""

        return None

class LocalFile:
    """An async wrapper around local file I/O"""

    def __init__(self, file: _SFTPFileObj):
        self._file = file

    async def __aenter__(self) -> Self: # pragma: no cover
        """Allow LocalFile to be used as an async context manager"""

        return self

    async def __aexit__(self, _exc_type: Optional[Type[BaseException]],
                        _exc_value: Optional[BaseException],
                        _traceback: Optional[TracebackType]) -> \
            bool: # pragma: no cover
        """Wait for file close when used as an async context manager"""

        await self.close()
        return False

    async def read(self, size: int, offset: int) -> bytes:
        """Read data from the local file"""

        self._file.seek(offset)
        return self._file.read(size)

    async def write(self, data: bytes, offset: int) -> int:
        """Write data to the local file"""

        self._file.seek(offset)
        return self._file.write(data)

    async def close(self) -> None:
        """Close the local file"""

        self._file.close()


class LocalFS:
    """An async wrapper around local filesystem access"""

    limits = SFTPLimits(0, MAX_SFTP_READ_LEN, MAX_SFTP_WRITE_LEN, 0)

    @staticmethod
    def basename(path: bytes) -> bytes:
        """Return the final component of a local file path"""

        return os.path.basename(path)

    def encode(self, path: _SFTPPath) -> bytes:
        """Encode path name using filesystem native encoding

           This method has no effect if the path is already bytes.

        """

        # pylint: disable=no-self-use

        return os.fsencode(path)

    def compose_path(self, path: bytes,
                     parent: Optional[bytes] = None) -> bytes:
        """Compose a path

           If parent is not specified, just encode the path.

        """

        path = self.encode(path)

        return posixpath.join(parent, path) if parent else path

    async def stat(self, path: bytes, *,
                   follow_symlinks: bool = True) -> 'SFTPAttrs':
        """Get attributes of a local file, directory, or symlink"""

        return SFTPAttrs.from_local(os.stat(_to_local_path(path),
                                            follow_symlinks=follow_symlinks))

    async def setstat(self, path: bytes, attrs: 'SFTPAttrs', *,
                      follow_symlinks: bool = True) -> None:
        """Set attributes of a local file, directory, or symlink"""

        _setstat(_to_local_path(path), attrs, follow_symlinks=follow_symlinks)

    async def exists(self, path: bytes) -> bool:
        """Return if the local path exists and isn't a broken symbolic link"""

        return os.path.exists(_to_local_path(path))

    async def isdir(self, path: bytes) -> bool:
        """Return if the local path refers to a directory"""

        return os.path.isdir(_to_local_path(path))

    async def scandir(self, path: bytes) -> AsyncIterator[SFTPName]:
        """Return names and attributes of the files in a local directory"""

        with os.scandir(_to_local_path(path)) as entries:
            for entry in entries:
                filename = entry.name

                if sys.platform == 'win32': # pragma: no cover
                    filename = os.fsencode(filename)

                attrs = SFTPAttrs.from_local(entry.stat(follow_symlinks=False))
                yield SFTPName(filename, attrs=attrs)

    async def mkdir(self, path: bytes) -> None:
        """Create a local directory with the specified attributes"""

        os.mkdir(_to_local_path(path))

    async def readlink(self, path: bytes) -> bytes:
        """Return the target of a local symbolic link"""

        path = os.readlink(_to_local_path(path))

        if sys.platform == 'win32' and \
                path.startswith('\\\\?\\'): # pragma: no cover
            path = path[4:]

        return _from_local_path(path)

    async def symlink(self, oldpath: bytes, newpath: bytes) -> None:
        """Create a local symbolic link"""

        os.symlink(_to_local_path(oldpath), _to_local_path(newpath))

    @async_context_manager
    async def open(self, path: bytes, mode: str,
                   block_size: int = -1) -> LocalFile:
        """Open a local file"""

        # pylint: disable=unused-argument

        return LocalFile(open(_to_local_path(path), mode))

local_fs = LocalFS()


class SFTPServerFile:
    """A wrapper around SFTPServer used to access files it manages"""

    def __init__(self, server: SFTPServer, file_obj: object):
        self._server = server
        self._file_obj = file_obj

    async def __aenter__(self) -> Self: # pragma: no cover
        """Allow SFTPServerFile to be used as an async context manager"""

        return self

    async def __aexit__(self, _exc_type: Optional[Type[BaseException]],
                        _exc_value: Optional[BaseException],
                        _traceback: Optional[TracebackType]) -> \
            bool: # pragma: no cover
        """Wait for client close when used as an async context manager"""

        await self.close()
        return False

    async def read(self, size: int, offset: int) -> bytes:
        """Read bytes from the file"""

        data = self._server.read(self._file_obj, offset, size)

        if inspect.isawaitable(data):
            data = await cast(Awaitable[bytes], data)

        data: bytes

        return data

    async def write(self, data: bytes, offset: int) -> int:
        """Write bytes to the file"""

        size = self._server.write(self._file_obj, offset, data)

        if inspect.isawaitable(size):
            size = await cast(Awaitable[int], size)

        size: int

        return size

    async def close(self) -> None:
        """Close a file managed by the associated SFTPServer"""

        result = self._server.close(self._file_obj)

        if inspect.isawaitable(result):
            assert result is not None
            await result


class SFTPServerFS:
    """A wrapper around SFTPServer used to access its filesystem"""

    def __init__(self, server: SFTPServer):
        self._server = server

    @staticmethod
    def basename(path: bytes) -> bytes:
        """Return the final component of a POSIX-style path"""

        return posixpath.basename(path)

    async def stat(self, path: bytes) -> SFTPAttrs:
        """Get attributes of a file or directory, following symlinks"""

        attrs = self._server.stat(path)

        if inspect.isawaitable(attrs):
            attrs = await cast(Awaitable[_SFTPOSAttrs], attrs)

        attrs: _SFTPOSAttrs

        if isinstance(attrs, os.stat_result):
            attrs = SFTPAttrs.from_local(attrs)

        return attrs

    async def setstat(self, path: bytes, attrs: SFTPAttrs) -> None:
        """Set attributes of a file or directory"""

        result = self._server.setstat(path, attrs)

        if inspect.isawaitable(result):
            assert result is not None
            await result

    async def _type(self, path: bytes) -> int:
        """Return the file type of a path, or 0 if it can't be accessed"""

        try:
            return (await self.stat(path)).type
        except OSError as exc:
            if exc.errno in (errno.ENOENT, errno.EACCES):
                return FILEXFER_TYPE_UNKNOWN
            else:
                raise
        except (SFTPNoSuchFile, SFTPNoSuchPath, SFTPPermissionDenied):
            return FILEXFER_TYPE_UNKNOWN

    async def exists(self, path: bytes) -> bool:
        """Return if a path exists"""

        return (await self._type(path)) != FILEXFER_TYPE_UNKNOWN

    async def isdir(self, path: bytes) -> bool:
        """Return if the path refers to a directory"""

        return (await self._type(path)) == FILEXFER_TYPE_DIRECTORY

    def scandir(self, path: bytes) -> AsyncIterator[SFTPName]:
        """Return names and attributes of the files in a directory"""

        return self._server.scandir(path)

    async def mkdir(self, path: bytes) -> None:
        """Create a directory"""

        result = self._server.mkdir(path, SFTPAttrs())

        if inspect.isawaitable(result):
            assert result is not None
            await result

    @async_context_manager
    async def open(self, path: bytes, mode: str) -> SFTPServerFile:
        """Open a file"""

        pflags, _ = _mode_to_pflags(mode)
        file_obj = self._server.open(path, pflags, SFTPAttrs())

        if inspect.isawaitable(file_obj):
            file_obj = await cast(Awaitable[object], file_obj)

        return SFTPServerFile(self._server, file_obj)


async def start_sftp_client(conn: 'SSHClientConnection',
                            loop: asyncio.AbstractEventLoop,
                            reader: 'SSHReader[bytes]',
                            writer: 'SSHWriter[bytes]',
                            path_encoding: Optional[str],
                            path_errors: str, sftp_version: int) -> SFTPClient:
    """Start an SFTP client"""

    handler = SFTPClientHandler(loop, reader, writer, sftp_version)

    handler.logger.info('Starting SFTP client')

    await handler.start()

    conn.create_task(handler.recv_packets(), handler.logger)

    await handler.request_limits()

    return SFTPClient(handler, path_encoding, path_errors)


def run_sftp_server(sftp_server: SFTPServer, reader: 'SSHReader[bytes]',
                    writer: 'SSHWriter[bytes]',
                    sftp_version: int) -> Awaitable[None]:
    """Return a handler for an SFTP server session"""

    handler = SFTPServerHandler(sftp_server, reader, writer, sftp_version)

    handler.logger.info('Starting SFTP server')

    return handler.run()
