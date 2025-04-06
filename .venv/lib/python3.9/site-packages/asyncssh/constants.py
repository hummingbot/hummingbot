# Copyright (c) 2013-2021 by Ron Frederick <ronf@timeheart.net> and others.
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

"""SSH constants"""

# Default language for error messages
DEFAULT_LANG                        = 'en-US'

# Default SSH listening port
DEFAULT_PORT                        = 22

# SSH message codes
MSG_DISCONNECT                      = 1
MSG_IGNORE                          = 2
MSG_UNIMPLEMENTED                   = 3
MSG_DEBUG                           = 4
MSG_SERVICE_REQUEST                 = 5
MSG_SERVICE_ACCEPT                  = 6
MSG_EXT_INFO                        = 7

MSG_KEXINIT                         = 20
MSG_NEWKEYS                         = 21

MSG_KEX_FIRST                       = 30
MSG_KEX_LAST                        = 49

MSG_USERAUTH_REQUEST                = 50
MSG_USERAUTH_FAILURE                = 51
MSG_USERAUTH_SUCCESS                = 52
MSG_USERAUTH_BANNER                 = 53

MSG_USERAUTH_FIRST                  = 60
MSG_USERAUTH_LAST                   = 79

MSG_GLOBAL_REQUEST                  = 80
MSG_REQUEST_SUCCESS                 = 81
MSG_REQUEST_FAILURE                 = 82

MSG_CHANNEL_OPEN                    = 90
MSG_CHANNEL_OPEN_CONFIRMATION       = 91
MSG_CHANNEL_OPEN_FAILURE            = 92

MSG_CHANNEL_WINDOW_ADJUST           = 93
MSG_CHANNEL_DATA                    = 94
MSG_CHANNEL_EXTENDED_DATA           = 95
MSG_CHANNEL_EOF                     = 96
MSG_CHANNEL_CLOSE                   = 97
MSG_CHANNEL_REQUEST                 = 98
MSG_CHANNEL_SUCCESS                 = 99
MSG_CHANNEL_FAILURE                 = 100

# Messages 90-92 are excluded here as they relate to opening a new channel
MSG_CHANNEL_FIRST                   = 93
MSG_CHANNEL_LAST                    = 127

# SSH disconnect reason codes
DISC_HOST_NOT_ALLOWED_TO_CONNECT    = 1
DISC_PROTOCOL_ERROR                 = 2
DISC_KEY_EXCHANGE_FAILED            = 3
DISC_RESERVED                       = 4
DISC_MAC_ERROR                      = 5
DISC_COMPRESSION_ERROR              = 6
DISC_SERVICE_NOT_AVAILABLE          = 7
DISC_PROTOCOL_VERSION_NOT_SUPPORTED = 8
DISC_HOST_KEY_NOT_VERIFIABLE        = 9
DISC_CONNECTION_LOST                = 10
DISC_BY_APPLICATION                 = 11
DISC_TOO_MANY_CONNECTIONS           = 12
DISC_AUTH_CANCELLED_BY_USER         = 13
DISC_NO_MORE_AUTH_METHODS_AVAILABLE = 14
DISC_ILLEGAL_USER_NAME              = 15

DISC_HOST_KEY_NOT_VERIFYABLE        = 9   # Error in naming, left here to not
                                          # break backward compatibility

# SSH channel open failure reason codes
OPEN_ADMINISTRATIVELY_PROHIBITED    = 1
OPEN_CONNECT_FAILED                 = 2
OPEN_UNKNOWN_CHANNEL_TYPE           = 3
OPEN_RESOURCE_SHORTAGE              = 4

# Internal failure reason codes
OPEN_REQUEST_X11_FORWARDING_FAILED  = 0xfffffffd
OPEN_REQUEST_PTY_FAILED             = 0xfffffffe
OPEN_REQUEST_SESSION_FAILED         = 0xffffffff

# SFTPv3-v5 packet types
FXP_INIT                            = 1
FXP_VERSION                         = 2
FXP_OPEN                            = 3
FXP_CLOSE                           = 4
FXP_READ                            = 5
FXP_WRITE                           = 6
FXP_LSTAT                           = 7
FXP_FSTAT                           = 8
FXP_SETSTAT                         = 9
FXP_FSETSTAT                        = 10
FXP_OPENDIR                         = 11
FXP_READDIR                         = 12
FXP_REMOVE                          = 13
FXP_MKDIR                           = 14
FXP_RMDIR                           = 15
FXP_REALPATH                        = 16
FXP_STAT                            = 17
FXP_RENAME                          = 18
FXP_READLINK                        = 19
FXP_SYMLINK                         = 20
FXP_STATUS                          = 101
FXP_HANDLE                          = 102
FXP_DATA                            = 103
FXP_NAME                            = 104
FXP_ATTRS                           = 105
FXP_EXTENDED                        = 200
FXP_EXTENDED_REPLY                  = 201

# SFTPv6 packet types
FXP_LINK                            = 21
FXP_BLOCK                           = 22
FXP_UNBLOCK                         = 23

# SFTPv3 open flags
FXF_READ                            = 0x00000001
FXF_WRITE                           = 0x00000002
FXF_APPEND                          = 0x00000004
FXF_CREAT                           = 0x00000008
FXF_TRUNC                           = 0x00000010
FXF_EXCL                            = 0x00000020

# SFTPv4 open flags
FXF_TEXT                            = 0x00000040

# SFTPv5 open flags
FXF_ACCESS_DISPOSITION              = 0x00000007
FXF_CREATE_NEW                      = 0x00000000
FXF_CREATE_TRUNCATE                 = 0x00000001
FXF_OPEN_EXISTING                   = 0x00000002
FXF_OPEN_OR_CREATE                  = 0x00000003
FXF_TRUNCATE_EXISTING               = 0x00000004
FXF_APPEND_DATA                     = 0x00000008
FXF_APPEND_DATA_ATOMIC              = 0x00000010
FXF_TEXT_MODE                       = 0x00000020
FXF_BLOCK_READ                      = 0x00000040
FXF_BLOCK_WRITE                     = 0x00000080
FXF_BLOCK_DELETE                    = 0x00000100

# SFTPv6 open flags
FXF_BLOCK_ADVISORY                  = 0x00000200
FXF_NOFOLLOW                        = 0x00000400
FXF_DELETE_ON_CLOSE                 = 0x00000800
FXF_ACCESS_AUDIT_ALARM_INFO         = 0x00001000
FXF_ACCESS_BACKUP                   = 0x00002000
FXF_BACKUP_STREAM                   = 0x00004000
FXF_OVERRIDE_OWNER                  = 0x00008000

# SFTPv5-v6 ACE mask values used in desired-access
ACE4_READ_DATA                      = 0x00000001
ACE4_WRITE_DATA                     = 0x00000002
ACE4_APPEND_DATA                    = 0x00000004
ACE4_READ_ATTRIBUTES                = 0x00000080
ACE4_WRITE_ATTRIBUTES               = 0x00000100

# SFTPv3 attribute flags
FILEXFER_ATTR_SIZE                  = 0x00000001
FILEXFER_ATTR_UIDGID                = 0x00000002
FILEXFER_ATTR_PERMISSIONS           = 0x00000004
FILEXFER_ATTR_ACMODTIME             = 0x00000008
FILEXFER_ATTR_EXTENDED              = 0x80000000
FILEXFER_ATTR_DEFINED_V3            = 0x8000000f

# SFTPv4 attribute flags
FILEXFER_ATTR_ACCESSTIME            = 0x00000008
FILEXFER_ATTR_CREATETIME            = 0x00000010
FILEXFER_ATTR_MODIFYTIME            = 0x00000020
FILEXFER_ATTR_ACL                   = 0x00000040
FILEXFER_ATTR_OWNERGROUP            = 0x00000080
FILEXFER_ATTR_SUBSECOND_TIMES       = 0x00000100
FILEXFER_ATTR_DEFINED_V4            = 0x800001fd

# SFTPv5 attribute flags
FILEXFER_ATTR_BITS                  = 0x00000200
FILEXFER_ATTR_DEFINED_V5            = 0x800003fd

# SFTPv6 attribute flags
FILEXFER_ATTR_ALLOCATION_SIZE       = 0x00000400
FILEXFER_ATTR_TEXT_HINT             = 0x00000800
FILEXFER_ATTR_MIME_TYPE             = 0x00001000
FILEXFER_ATTR_LINK_COUNT            = 0x00002000
FILEXFER_ATTR_UNTRANSLATED_NAME     = 0x00004000
FILEXFER_ATTR_CTIME                 = 0x00008000
FILEXFER_ATTR_DEFINED_V6            = 0x8000fffd

# SFTPv4 file types
FILEXFER_TYPE_REGULAR               = 1
FILEXFER_TYPE_DIRECTORY             = 2
FILEXFER_TYPE_SYMLINK               = 3
FILEXFER_TYPE_SPECIAL               = 4
FILEXFER_TYPE_UNKNOWN               = 5

# SFTPv5 file types
FILEXFER_TYPE_SOCKET                = 6
FILEXFER_TYPE_CHAR_DEVICE           = 7
FILEXFER_TYPE_BLOCK_DEVICE          = 8
FILEXFER_TYPE_FIFO                  = 9

# SFTPv5 attrib bits
FILEXFER_ATTR_BITS_READONLY         = 0x00000001
FILEXFER_ATTR_BITS_SYSTEM           = 0x00000002
FILEXFER_ATTR_BITS_HIDDEN           = 0x00000004
FILEXFER_ATTR_BITS_CASE_INSENSITIVE = 0x00000008
FILEXFER_ATTR_BITS_ARCHIVE          = 0x00000010
FILEXFER_ATTR_BITS_ENCRYPTED        = 0x00000020
FILEXFER_ATTR_BITS_COMPRESSED       = 0x00000040
FILEXFER_ATTR_BITS_SPARSE           = 0x00000080
FILEXFER_ATTR_BITS_APPEND_ONLY      = 0x00000100
FILEXFER_ATTR_BITS_IMMUTABLE        = 0x00000200
FILEXFER_ATTR_BITS_SYNC             = 0x00000400

# SFTPv6 attrib bits
FILEXFER_ATTR_BITS_TRANSLATION_ERR  = 0x00000800

# SFTPv6 text hint flags
FILEXFER_ATTR_KNOWN_TEXT            = 0
FILEXFER_ATTR_GUESSED_TEXT          = 1
FILEXFER_ATTR_KNOWN_BINARY          = 2
FILEXFER_ATTR_GUESSED_BINARY        = 3

# SFTPv5 rename flags
FXR_OVERWRITE                       = 0x00000001
FXR_ATOMIC                          = 0x00000002
FXR_NATIVE                          = 0x00000004

# SFTPv6 realpath control byte
FXRP_NO_CHECK                       = 1
FXRP_STAT_IF_EXISTS                 = 2
FXRP_STAT_ALWAYS                    = 3

# OpenSSH statvfs attribute flags
FXE_STATVFS_ST_RDONLY               = 0x1
FXE_STATVFS_ST_NOSUID               = 0x2

# SFTPv3 error codes
FX_OK                               = 0
FX_EOF                              = 1
FX_NO_SUCH_FILE                     = 2
FX_PERMISSION_DENIED                = 3
FX_FAILURE                          = 4
FX_BAD_MESSAGE                      = 5
FX_NO_CONNECTION                    = 6
FX_CONNECTION_LOST                  = 7
FX_OP_UNSUPPORTED                   = 8
FX_V3_END                           = FX_OP_UNSUPPORTED

# SFTPv4 error codes
FX_INVALID_HANDLE                   = 9
FX_NO_SUCH_PATH                     = 10
FX_FILE_ALREADY_EXISTS              = 11
FX_WRITE_PROTECT                    = 12
FX_NO_MEDIA                         = 13
FX_V4_END                           = FX_NO_MEDIA

# SFTPv5 error codes
FX_NO_SPACE_ON_FILESYSTEM           = 14
FX_QUOTA_EXCEEDED                   = 15
FX_UNKNOWN_PRINCIPAL                = 16
FX_LOCK_CONFLICT                    = 17
FX_V5_END                           = FX_LOCK_CONFLICT

# SFTPv6 error codes
FX_DIR_NOT_EMPTY                    = 18
FX_NOT_A_DIRECTORY                  = 19
FX_INVALID_FILENAME                 = 20
FX_LINK_LOOP                        = 21
FX_CANNOT_DELETE                    = 22
FX_INVALID_PARAMETER                = 23
FX_FILE_IS_A_DIRECTORY              = 24
FX_BYTE_RANGE_LOCK_CONFLICT         = 25
FX_BYTE_RANGE_LOCK_REFUSED          = 26
FX_DELETE_PENDING                   = 27
FX_FILE_CORRUPT                     = 28
FX_OWNER_INVALID                    = 29
FX_GROUP_INVALID                    = 30
FX_NO_MATCHING_BYTE_RANGE_LOCK      = 31
FX_V6_END                           = FX_NO_MATCHING_BYTE_RANGE_LOCK

# SSH channel data type codes
EXTENDED_DATA_STDERR                = 1

# SSH pty mode opcodes
PTY_OP_END                          = 0
PTY_VINTR                           = 1
PTY_VQUIT                           = 2
PTY_VERASE                          = 3
PTY_VKILL                           = 4
PTY_VEOF                            = 5
PTY_VEOL                            = 6
PTY_VEOL2                           = 7
PTY_VSTART                          = 8
PTY_VSTOP                           = 9
PTY_VSUSP                           = 10
PTY_VDSUSP                          = 11
PTY_VREPRINT                        = 12
PTY_WERASE                          = 13
PTY_VLNEXT                          = 14
PTY_VFLUSH                          = 15
PTY_VSWTCH                          = 16
PTY_VSTATUS                         = 17
PTY_VDISCARD                        = 18
PTY_IGNPAR                          = 30
PTY_PARMRK                          = 31
PTY_INPCK                           = 32
PTY_ISTRIP                          = 33
PTY_INLCR                           = 34
PTY_IGNCR                           = 35
PTY_ICRNL                           = 36
PTY_IUCLC                           = 37
PTY_IXON                            = 38
PTY_IXANY                           = 39
PTY_IXOFF                           = 40
PTY_IMAXBEL                         = 41
PTY_IUTF8                           = 42
PTY_ISIG                            = 50
PTY_ICANON                          = 51
PTY_XCASE                           = 52
PTY_ECHO                            = 53
PTY_ECHOE                           = 54
PTY_ECHOK                           = 55
PTY_ECHONL                          = 56
PTY_NOFLSH                          = 57
PTY_TOSTOP                          = 58
PTY_IEXTEN                          = 59
PTY_ECHOCTL                         = 60
PTY_ECHOKE                          = 61
PTY_PENDIN                          = 62
PTY_OPOST                           = 70
PTY_OLCUC                           = 71
PTY_ONLCR                           = 72
PTY_OCRNL                           = 73
PTY_ONOCR                           = 74
PTY_ONLRET                          = 75
PTY_CS7                             = 90
PTY_CS8                             = 91
PTY_PARENB                          = 92
PTY_PARODD                          = 93
PTY_OP_ISPEED                       = 128
PTY_OP_OSPEED                       = 129
PTY_OP_RESERVED                     = 160
