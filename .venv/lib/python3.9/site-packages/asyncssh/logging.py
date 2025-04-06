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
#     Sam Crooks - initial implementation
#     Ron Frederick - minor cleanup

"""Logging functions"""

import logging
from typing import MutableMapping, Optional, Tuple, Union, cast


_LogArg = object
_ObjDict = MutableMapping[str, object]


class SSHLogger(logging.LoggerAdapter):
    """Adapter to add context to AsyncSSH log messages"""

    _debug_level = 1
    _pkg_logger = logging.getLogger(__package__ or 'asyncssh')

    def __init__(self, parent: logging.Logger = _pkg_logger,
                 child: str = '', context: str = ''):
        self._context = context
        self._logger = parent.getChild(child) if child else parent

        super().__init__(self._logger, {})

    def _extend_context(self, context: str) -> str:
        """Extend context provided by this logger"""

        if context:
            if self._context:
                context = self._context + ', ' + context
        else:
            context = self._context

        return context

    def get_child(self, child: str = '', context: str = '') -> 'SSHLogger':
        """Return child logger with optional added context"""

        return type(self)(self._logger, child, self._extend_context(context))

    def log(self, level: int, msg: object, *args, **kwargs) -> None:
        """Log a message to the underlying logger"""

        def _item_text(item: _LogArg) -> str:
            """Convert a list item to text"""

            if isinstance(item, bytes):
                result = item.decode('utf-8', errors='backslashreplace')

                if not result.isprintable():
                    result = repr(result)[1:-1]
            elif not isinstance(item, str):
                result = str(item)
            else:
                result = item

            return result

        def _text(arg: _LogArg) -> _LogArg:
            """Convert a log argument to text"""

            result: _LogArg

            if isinstance(arg, list):
                result = ','.join(_item_text(item) for item in arg)
            elif isinstance(arg, tuple):
                host, port = arg

                if host:
                    result = f'{host}, port {port}' if port else host
                else:
                    result = f'port {port}' if port else 'dynamic port'
            elif isinstance(arg, bytes):
                result = _item_text(arg)
            else:
                result = arg

            return result

        log_args = [_text(arg) for arg in args]

        super().log(level, msg, *log_args, **kwargs)

    def process(self, msg: str, kwargs: _ObjDict) -> Tuple[str, _ObjDict]:
        """Add context to log message"""

        extra = cast(_ObjDict, kwargs.get('extra', {}))

        context = self._extend_context(cast(str, extra.get('context')))
        context = '[' + context + '] ' if context else ''

        packet = cast(bytes, extra.get('packet'))
        pktdata = ''
        offset = 0

        while packet:
            line = f'\n  {offset:08x}:'

            for b in packet[:16]:
                line += f' {b:02x}'

            line += (62 - len(line)) * ' '

            for b in packet[:16]:
                if b < 0x20 or b >= 0x80:
                    c = '.'
                elif b == ord('%'):
                    c = '%%'
                else:
                    c = chr(b)

                line += c

            pktdata += line

            packet = packet[16:]
            offset += 16

        return context + msg + pktdata, kwargs

    @classmethod
    def set_debug_level(cls, level: int) -> None:
        """Set AsyncSSH debug log level"""

        if level < 1 or level > 3:
            raise ValueError('Debug log level must be between 1 and 3')

        cls._debug_level = level

    def debug1(self, msg: str, *args: _LogArg, **kwargs: object) -> None:
        """Write a level 1 debug log message"""

        self.log(logging.DEBUG, msg, *args, **kwargs)

    def debug2(self, msg: str, *args: _LogArg, **kwargs: object) -> None:
        """Write a level 2 debug log message"""

        if self._debug_level >= 2:
            self.log(logging.DEBUG, msg, *args, **kwargs)

    def packet(self, pktid: Optional[int], packet: bytes, msg: str,
               *args: _LogArg, **kwargs: object) -> None:
        """Write a control packet debug log message"""

        if self._debug_level >= 3:
            kwargs.setdefault('extra', {})
            extra = cast(_ObjDict, kwargs.get('extra'))

            if pktid is not None:
                extra.update(context=f'pktid={pktid}')

            extra.update(packet=packet)

            self.log(logging.DEBUG, msg, *args, **kwargs)


def set_log_level(level: Union[int, str]) -> None:
    """Set the AsyncSSH log level

       This function sets the log level of the AsyncSSH logger. It
       defaults to `'NOTSET`', meaning that it will track the debug
       level set on the root Python logger.

       For additional control over the level of debug logging, see the
       function :func:`set_debug_level` for additional information.

       :param level:
           The log level to set, as defined by the `logging` module
       :type level: `int` or `str`

    """

    logger.setLevel(level)


def set_sftp_log_level(level: Union[int, str]) -> None:
    """Set the AsyncSSH SFTP/SCP log level

       This function sets the log level of the AsyncSSH SFTP/SCP logger.
       It defaults to `'NOTSET`', meaning that it will track the debug
       level set on the main AsyncSSH logger.

       For additional control over the level of debug logging, see the
       function :func:`set_debug_level` for additional information.

       :param level:
           The log level to set, as defined by the `logging` module
       :type level: `int` or `str`

    """

    sftp_logger.setLevel(level)


def set_debug_level(level: int) -> None:
    """Set the AsyncSSH debug log level

       This function sets the level of debugging logging done by the
       AsyncSSH logger, from the following options:

           ===== ====================================
           Level Description
           ===== ====================================
           1     Minimal debug logging
           2     Full debug logging
           3     Full debug logging with packet dumps
           ===== ====================================

       The debug level defaults to level 1 (minimal debug logging).

       .. note:: For this setting to have any effect, the effective log
                 level of the AsyncSSH logger must be set to DEBUG.

       .. warning:: Extreme caution should be used when setting debug
                    level to 3, as this can expose user passwords in
                    clear text. This level should generally only be
                    needed when tracking down issues with malformed
                    or incomplete packets.

       :param level:
           The debug level to set, as defined above.
       :type level: `int`

    """

    logger.set_debug_level(level)


logger = SSHLogger()
sftp_logger = logger.get_child('sftp')
