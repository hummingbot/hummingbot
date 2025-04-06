# Copyright (c) 2016-2023 by Ron Frederick <ronf@timeheart.net> and others.
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

"""Input line editor"""

import re

from functools import partial
from typing import TYPE_CHECKING, Callable, Dict, List
from typing import Optional, Set, Tuple, Union, cast
from unicodedata import east_asian_width

from .session import DataType


if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from .channel import SSHServerChannel
    from .session import SSHServerSession


_CharDict = Dict[str, object]
_CharHandler = Callable[['SSHLineEditor'], None]
_KeyHandler = Callable[[str, int], Union[bool, Tuple[str, int]]]


_DEFAULT_WIDTH = 80

_ansi_terminals = ('ansi', 'cygwin', 'linux', 'putty', 'screen', 'teraterm',
                   'cit80', 'vt100', 'vt102', 'vt220', 'vt320', 'xterm',
                   'xterm-color', 'xterm-16color', 'xterm-256color', 'rxvt',
                   'rxvt-color')


def _is_wide(ch: str) -> bool:
    """Return display width of character"""

    return east_asian_width(ch) in 'WF'


class SSHLineEditor:
    """Input line editor"""

    def __init__(self, chan: 'SSHServerChannel[str]',
                 session: 'SSHServerSession[str]', line_echo: bool,
                 history_size: int, max_line_length: int, term_type: str,
                 width: int):
        self._chan = chan
        self._session = session
        self._line_echo = line_echo
        self._line_pending = False
        self._history_size = history_size if history_size > 0 else 0
        self._max_line_length = max_line_length
        self._wrap = term_type in _ansi_terminals
        self._width = width or _DEFAULT_WIDTH
        self._line_mode = True
        self._echo = True
        self._start_column = 0
        self._end_column = 0
        self._cursor = 0
        self._left_pos = 0
        self._right_pos = 0
        self._pos = 0
        self._line = ''
        self._bell_rung = False
        self._early_wrap: Set[int] = set()
        self._outbuf: List[str] = []
        self._keymap: _CharDict = {}
        self._key_state = self._keymap
        self._erased = ''
        self._history: List[str] = []
        self._history_index = 0

        for func, keys in self._keylist:
            for key in keys:
                self._add_key(key, func)

        self._build_printable()

    def _add_key(self, key: str, func: _CharHandler) -> None:
        """Add a key to the keymap"""

        keymap = self._keymap

        for ch in key[:-1]:
            if ch not in keymap:
                keymap[ch] = {}

            keymap = cast(_CharDict, keymap[ch])

        keymap[key[-1]] = func

    def _del_key(self, key: str) -> None:
        """Delete a key from the keymap"""

        keymap = self._keymap

        for ch in key[:-1]:
            if ch not in keymap:
                return

            keymap = cast(_CharDict, keymap[ch])

        keymap.pop(key[-1], None)

    def _build_printable(self) -> None:
        """Build a regex of printable ASCII non-registered keys"""

        def _escape(c: int) -> str:
            """Backslash escape special characters in regex character range"""

            ch = chr(c)
            return ('\\' if (ch in '-&|[]\\^~') else '') + ch

        def _is_printable(ch: str) -> bool:
            """Return if character is printable and has no handler"""

            return ch.isprintable() and ch not in keys

        pat: List[str] = []
        keys = self._keymap.keys()
        start = ord(' ')
        limit = 0x10000

        while start < limit:
            while start < limit and not _is_printable(chr(start)):
                start += 1

            end = start

            while _is_printable(chr(end)):
                end += 1

            pat.append(_escape(start))

            if start != end - 1:
                pat.append('-' + _escape(end - 1))

            start = end + 1

        self._printable = re.compile('[' + ''.join(pat) + ']*')

    def _char_width(self, pos: int) -> int:
        """Return width of character at specified position"""

        return 1 + _is_wide(self._line[pos]) + ((pos + 1) in self._early_wrap)

    def _determine_column(self, data: str, column: int,
                          pos: Optional[int] = None) -> Tuple[str, int]:
        """Determine new output column after output occurs"""

        escaped = False
        offset = pos
        last_wrap_pos = pos
        wrapped_data = []

        for ch in data:
            if ch == '\b':
                column -= 1
            elif ch == '\x1b':
                escaped = True
            elif escaped:
                if ch == 'm':
                    escaped = False
            else:
                if _is_wide(ch) and (column % self._width) == self._width - 1:
                    column += 1

                    if pos is not None:
                        assert last_wrap_pos is not None
                        assert offset is not None

                        wrapped_data.append(data[last_wrap_pos - offset:
                                                 pos - offset])
                        last_wrap_pos = pos

                        self._early_wrap.add(pos)
                else:
                    if pos is not None:
                        self._early_wrap.discard(pos)

                column += 1 + _is_wide(ch)

            if pos is not None:
                pos += 1

        if pos is not None:
            assert last_wrap_pos is not None
            assert offset is not None

            wrapped_data.append(data[last_wrap_pos - offset:])
            return ' '.join(wrapped_data), column
        else:
            return data, column

    def _output(self, data: str, pos: Optional[int] = None) -> None:
        """Generate output and calculate new output column"""

        idx = data.rfind('\n')

        if idx >= 0:
            self._outbuf.append(data[:idx+1])
            tail = data[idx+1:]
            self._cursor = 0
        else:
            tail = data

        data, self._cursor = self._determine_column(tail, self._cursor, pos)

        self._outbuf.append(data)

        if self._cursor and self._cursor % self._width == 0:
            self._outbuf.append(' \b')

    def _ring_bell(self) -> None:
        """Ring the terminal bell"""

        if not self._bell_rung:
            self._outbuf.append('\a')
            self._bell_rung = True

    def _update_input_window(self, new_pos: int) -> int:
        """Update visible input window when not wrapping onto multiple lines"""

        line_len = len(self._line)

        if new_pos < self._left_pos:
            self._left_pos = new_pos
        else:
            if new_pos < line_len:
                new_pos += 1

            pos = self._pos
            column = self._cursor

            while pos < new_pos:
                column += self._char_width(pos)
                pos += 1

            if column >= self._width:
                while column >= self._width:
                    column -= self._char_width(self._left_pos)
                    self._left_pos += 1
            else:
                while self._left_pos > 0:
                    column += self._char_width(self._left_pos)

                    if column < self._width:
                        self._left_pos -= 1
                    else:
                        break

        column = self._start_column
        self._right_pos = self._left_pos

        while self._right_pos < line_len:
            ch_width = self._char_width(self._right_pos)

            if column + ch_width < self._width:
                self._right_pos += 1
                column += ch_width
            else:
                break

        return column

    def _move_cursor(self, column: int) -> None:
        """Move the cursor to selected position in input line"""

        start_row = self._cursor // self._width
        start_col = self._cursor % self._width

        end_row = column // self._width
        end_col = column % self._width

        if end_row < start_row:
            self._outbuf.append('\x1b[' + str(start_row-end_row) + 'A')
        elif end_row > start_row:
            self._outbuf.append('\x1b[' + str(end_row-start_row) + 'B')

        if end_col > start_col:
            self._outbuf.append('\x1b[' + str(end_col-start_col) + 'C')
        elif end_col < start_col:
            self._outbuf.append('\x1b[' + str(start_col-end_col) + 'D')

        self._cursor = column

    def _move_back(self, column: int) -> None:
        """Move the cursor backward to selected position in input line"""

        if self._wrap:
            self._move_cursor(column)
        else:
            self._outbuf.append('\b' * (self._cursor - column))
            self._cursor = column

    def _clear_to_end(self) -> None:
        """Clear any remaining characters from previous input line"""

        column = self._cursor
        remaining = self._end_column - column

        if remaining > 0:
            self._outbuf.append(' ' * remaining)
            self._cursor = self._end_column

            if self._cursor % self._width == 0:
                self._outbuf.append(' \b')

        self._move_back(column)
        self._end_column = column

    def _erase_input(self) -> None:
        """Erase current input line"""

        self._move_cursor(self._start_column)
        self._clear_to_end()
        self._early_wrap.clear()

    def _draw_input(self) -> None:
        """Draw current input line"""

        if self._line and self._echo:
            if self._wrap:
                self._output(self._line[:self._pos], 0)
                column = self._cursor
                self._output(self._line[self._pos:], self._pos)
            else:
                self._update_input_window(self._pos)
                self._output(self._line[self._left_pos:self._pos])
                column = self._cursor
                self._output(self._line[self._pos:self._right_pos])

            self._end_column = self._cursor
            self._move_back(column)

    def _reposition(self, new_pos: int, new_column: int) -> None:
        """Reposition the cursor to selected position in input"""

        if self._echo:
            if self._wrap:
                self._move_cursor(new_column)
            else:
                self._update_input(self._pos, self._cursor, new_pos)

        self._pos = new_pos

    def _update_input(self, pos: int, column: int, new_pos: int) -> None:
        """Update selected portion of current input line"""

        if self._echo:
            if self._wrap:
                if pos in self._early_wrap:
                    column -= 1

                self._move_cursor(column)
                prev_wrap = new_pos in self._early_wrap
                self._output(self._line[pos:new_pos], pos)
                column = self._cursor
                self._output(self._line[new_pos:], new_pos)
                column += (new_pos in self._early_wrap) - prev_wrap
            else:
                self._update_input_window(new_pos)
                self._move_back(self._start_column)
                self._output(self._line[self._left_pos:new_pos])
                column = self._cursor
                self._output(self._line[new_pos:self._right_pos])

            self._clear_to_end()
            self._move_back(column)

        self._pos = new_pos

    def _reset_line(self) -> None:
        """Reset input line to empty"""

        self._line = ''
        self._left_pos = 0
        self._right_pos = 0
        self._pos = 0
        self._start_column = self._cursor
        self._end_column = self._cursor

    def _reset_pending(self) -> None:
        """Reset a pending echoed line if any"""

        if self._line_pending:
            self._erase_input()
            self._reset_line()
            self._line_pending = False

    def _insert_printable(self, data: str) -> None:
        """Insert data into the input line"""

        line_len = len(self._line)
        data_len = len(data)

        if self._max_line_length:
            if line_len + data_len > self._max_line_length:
                self._ring_bell()
                data_len = self._max_line_length - line_len
                data = data[:data_len]

        if data:
            pos = self._pos
            new_pos = pos + data_len
            self._line = self._line[:pos] + data + self._line[pos:]

            self._update_input(pos, self._cursor, new_pos)

    def _end_line(self) -> None:
        """End the current input line and send it to the session"""

        line = self._line

        need_wrap = (self._echo and not self._wrap and
                     (self._left_pos > 0 or self._right_pos < len(line)))

        if self._line_echo or need_wrap:
            if need_wrap:
                self._output('\b' * (self._cursor - self._start_column) + line)
            else:
                self._move_to_end()

            self._output('\r\n')
            self._reset_line()
        else:
            self._move_to_end()
            self._line_pending = True

        if self._echo and self._history_size and line:
            self._history.append(line)
            self._history = self._history[-self._history_size:]

        self._history_index = len(self._history)

        self._session.data_received(line + '\n', None)

    def _eof_or_delete(self) -> None:
        """Erase character to the right, or send EOF if input line is empty"""

        if not self._line:
            self._session.soft_eof_received()
        else:
            self._erase_right()

    def _erase_left(self) -> None:
        """Erase character to the left"""

        if self._pos > 0:
            pos = self._pos - 1
            column = self._cursor - self._char_width(pos)
            self._line = self._line[:pos] + self._line[pos+1:]
            self._update_input(pos, column, pos)
        else:
            self._ring_bell()

    def _erase_right(self) -> None:
        """Erase character to the right"""

        if self._pos < len(self._line):
            pos = self._pos
            self._line = self._line[:pos] + self._line[pos+1:]
            self._update_input(pos, self._cursor, pos)
        else:
            self._ring_bell()

    def _erase_line(self) -> None:
        """Erase entire input line"""

        self._erased = self._line
        self._line = ''
        self._update_input(0, self._start_column, 0)

    def _erase_to_end(self) -> None:
        """Erase to end of input line"""

        pos = self._pos
        self._erased = self._line[pos:]
        self._line = self._line[:pos]
        self._update_input(pos, self._cursor, pos)

    def _handle_key(self, key: str, handler: _KeyHandler) -> None:
        """Call an external key handler"""

        result = handler(self._line, self._pos)

        if result is True:
            if key.isprintable():
                self._insert_printable(key)
            else:
                self._ring_bell()
        elif result is False:
            self._ring_bell()
        else:
            line, new_pos = cast(Tuple[str, int], result)

            if new_pos < 0:
                self._session.signal_received(line)
            else:
                self._line = line
                self._update_input(0, self._start_column, new_pos)

    def _history_prev(self) -> None:
        """Replace input with previous line in history"""

        if self._history_index > 0:
            self._history_index -= 1
            self._line = self._history[self._history_index]
            self._update_input(0, self._start_column, len(self._line))
        else:
            self._ring_bell()

    def _history_next(self) -> None:
        """Replace input with next line in history"""

        if self._history_index < len(self._history):
            self._history_index += 1

            if self._history_index < len(self._history):
                self._line = self._history[self._history_index]
            else:
                self._line = ''

            self._update_input(0, self._start_column, len(self._line))
        else:
            self._ring_bell()

    def _move_left(self) -> None:
        """Move left in input line"""

        if self._pos > 0:
            pos = self._pos - 1
            column = self._cursor - self._char_width(pos)
            self._reposition(pos, column)
        else:
            self._ring_bell()

    def _move_right(self) -> None:
        """Move right in input line"""

        if self._pos < len(self._line):
            pos = self._pos
            column = self._cursor + self._char_width(pos)
            self._reposition(pos + 1, column)
        else:
            self._ring_bell()

    def _move_to_start(self) -> None:
        """Move to start of input line"""

        self._reposition(0, self._start_column)

    def _move_to_end(self) -> None:
        """Move to end of input line"""

        self._reposition(len(self._line), self._end_column)

    def _redraw(self) -> None:
        """Redraw input line"""

        self._erase_input()
        self._draw_input()

    def _insert_erased(self) -> None:
        """Insert previously erased input"""

        self._insert_printable(self._erased)

    def _send_break(self) -> None:
        """Send break to session"""

        self._session.break_received(0)

    _keylist = ((_end_line,      ('\n', '\r', '\x1bOM')),
                (_eof_or_delete, ('\x04',)),
                (_erase_left,    ('\x08', '\x7f')),
                (_erase_right,   ('\x1b[3~',)),
                (_erase_line,    ('\x15',)),
                (_erase_to_end,  ('\x0b',)),
                (_history_prev,  ('\x10', '\x1b[A', '\x1bOA')),
                (_history_next,  ('\x0e', '\x1b[B', '\x1bOB')),
                (_move_left,     ('\x02', '\x1b[D', '\x1bOD')),
                (_move_right,    ('\x06', '\x1b[C', '\x1bOC')),
                (_move_to_start, ('\x01', '\x1b[H', '\x1b[1~')),
                (_move_to_end,   ('\x05', '\x1b[F', '\x1b[4~')),
                (_redraw,        ('\x12',)),
                (_insert_erased, ('\x19',)),
                (_send_break,    ('\x03', '\x1b[33~')))

    def register_key(self, key: str, handler: _KeyHandler) -> None:
        """Register a handler to be called when a key is pressed"""

        self._add_key(key, partial(SSHLineEditor._handle_key,
                                   key=key, handler=handler))
        self._build_printable()

    def unregister_key(self, key: str) -> None:
        """Remove the handler associated with a key"""

        self._del_key(key)
        self._build_printable()

    def set_input(self, line: str, pos: int) -> None:
        """Set input line and cursor position"""

        self._reset_pending()

        self._line = line
        self._update_input(0, self._start_column, pos)

    def set_line_mode(self, line_mode: bool) -> None:
        """Enable/disable input line editing"""

        self._reset_pending()

        if self._line and not line_mode:
            data = self._line
            self._erase_input()
            self._line = ''

            self._session.data_received(data, None)

        self._line_mode = line_mode

    def set_echo(self, echo: bool) -> None:
        """Enable/disable echoing of input in line mode"""

        self._reset_pending()

        if self._echo and not echo:
            self._erase_input()
            self._echo = False
        elif echo and not self._echo:
            self._echo = True
            self._draw_input()

    def set_width(self, width: int) -> None:
        """Set terminal line width"""

        self._reset_pending()

        self._width = width or _DEFAULT_WIDTH

        if self._wrap:
            _, self._cursor = self._determine_column(self._line,
                                                     self._start_column, 0)

        self._redraw()

    def process_input(self, data: str, datatype: DataType) -> None:
        """Process input from channel"""

        if self._line_mode:
            data_len = len(data)
            idx = 0

            while idx < data_len:
                self._reset_pending()

                ch = data[idx]
                idx += 1

                if ch in self._key_state:
                    key_state = self._key_state[ch]

                    if callable(key_state):
                        try:
                            cast(_CharHandler, key_state)(self)
                        finally:
                            self._key_state = self._keymap
                    else:
                        self._key_state = cast(_CharDict, key_state)
                elif self._key_state == self._keymap and ch.isprintable():
                    match = self._printable.match(data, idx - 1)

                    assert match is not None
                    match = match[0]

                    if match:
                        self._insert_printable(match)
                        idx += len(match) - 1
                    else:
                        self._insert_printable(ch)
                else:
                    self._key_state = self._keymap
                    self._ring_bell()

            self._bell_rung = False

            if self._outbuf:
                self._chan.write(''.join(self._outbuf))
                self._outbuf.clear()
        else:
            self._session.data_received(data, datatype)

    def process_output(self, data: str) -> None:
        """Process output to channel"""

        if self._line_pending:
            if data.startswith(self._line):
                self._start_column = self._cursor
                data = data[len(self._line):]
            else:
                self._erase_input()

            self._reset_line()
            self._line_pending = False

        data = data.replace('\n', '\r\n')

        self._erase_input()
        self._output(data)

        if not self._wrap:
            self._cursor %= self._width

        self._start_column = self._cursor
        self._end_column = self._cursor
        self._draw_input()

        self._chan.write(''.join(self._outbuf))
        self._outbuf.clear()


class SSHLineEditorChannel:
    """Input line editor channel wrapper

       When creating server channels with `line_editor` set to `True`,
       this class is wrapped around the channel, providing the caller with
       the ability to enable and disable input line editing and echoing.

       .. note:: Line editing is only available when a pseudo-terminal
                 is requested on the server channel and the character
                 encoding on the channel is not set to `None`.

    """

    def __init__(self, orig_chan: 'SSHServerChannel[str]',
                 orig_session: 'SSHServerSession[str]', line_echo: bool,
                 history_size: int, max_line_length: int):
        self._orig_chan = orig_chan
        self._orig_session = orig_session
        self._line_echo = line_echo
        self._history_size = history_size
        self._max_line_length = max_line_length
        self._editor: Optional[SSHLineEditor] = None

    def __getattr__(self, attr: str):
        """Delegate most channel functions to original channel"""

        return getattr(self._orig_chan, attr)

    def create_editor(self) -> Optional[SSHLineEditor]:
        """Create input line editor if encoding and terminal type are set"""

        encoding, _ = self._orig_chan.get_encoding()
        term_type = self._orig_chan.get_terminal_type()
        width = self._orig_chan.get_terminal_size()[0]

        if encoding and term_type:
            self._editor = SSHLineEditor(
                self._orig_chan, self._orig_session, self._line_echo,
                self._history_size, self._max_line_length, term_type, width)

        return self._editor

    def register_key(self, key: str, handler: _KeyHandler) -> None:
        """Register a handler to be called when a key is pressed

           This method registers a handler function which will be called
           when a user presses the specified key while inputting a line.

           The handler will be called with arguments of the current
           input line and cursor position, and updated versions of these
           two values should be returned as a tuple.

           The handler can also return a tuple of a signal name and
           negative cursor position to cause a signal to be delivered
           on the channel. In this case, the current input line is left
           unchanged but the signal is delivered before processing any
           additional input. This can be used to define "hot keys" that
           trigger actions unrelated to editing the input.

           If the registered key is printable text, returning `True` will
           insert that text at the current cursor position, acting as if
           no handler was registered for that key. This is useful if you
           want to perform a special action in some cases but not others,
           such as based on the current cursor position.

           Returning `False` will ring the bell and leave the input
           unchanged, indicating the requested action could not be
           performed.

           :param key:
               The key sequence to look for
           :param handler:
               The handler function to call when the key is pressed
           :type key: `str`
           :type handler: `callable`

        """

        assert self._editor is not None
        self._editor.register_key(key, handler)

    def unregister_key(self, key: str) -> None:
        """Remove the handler associated with a key

           This method removes a handler function associated with
           the specified key. If the key sequence is printable,
           this will cause it to return to being inserted at the
           current position when pressed. Otherwise, it will cause
           the bell to ring to signal the key is not understood.

           :param key:
               The key sequence to look for
           :type key: `str`

        """

        assert self._editor is not None
        self._editor.unregister_key(key)

    def clear_input(self) -> None:
        """Clear input line

           This method clears the current input line.

        """

        assert self._editor is not None
        self._editor.set_input('', 0)

    def set_input(self, line: str, pos: int) -> None:
        """Clear input line

           This method sets the current input line and cursor position.

           :param line:
               The new input line
           :param pos:
               The new cursor position within the input line
           :type line: `str`
           :type pos: `int`

        """

        assert self._editor is not None
        self._editor.set_input(line, pos)

    def set_line_mode(self, line_mode: bool) -> None:
        """Enable/disable input line editing

           This method enabled or disables input line editing. When set,
           only full lines of input are sent to the session, and each
           line of input can be edited before it is sent.

           :param line_mode:
               Whether or not to process input a line at a time
           :type line_mode: `bool`

        """

        self._orig_chan.logger.info('%s line editor',
                                    'Enabling' if line_mode else 'Disabling')

        assert self._editor is not None
        self._editor.set_line_mode(line_mode)

    def set_echo(self, echo: bool) -> None:
        """Enable/disable echoing of input in line mode

           This method enables or disables echoing of input data when
           input line editing is enabled.

           :param echo:
               Whether or not input to echo input as it is entered
           :type echo: `bool`

        """

        self._orig_chan.logger.info('%s echo',
                                    'Enabling' if echo else 'Disabling')

        assert self._editor is not None
        self._editor.set_echo(echo)

    def write(self, data: str, datatype: DataType = None) -> None:
        """Process data written to the channel"""

        if self._editor and datatype is None:
            self._editor.process_output(data)
        else:
            self._orig_chan.write(data, datatype)


class SSHLineEditorSession:
    """Input line editor session wrapper"""

    def __init__(self, chan: SSHLineEditorChannel,
                 orig_session: 'SSHServerSession[str]'):
        self._chan = chan
        self._orig_session = orig_session
        self._editor: Optional[SSHLineEditor] = None

    def __getattr__(self, attr: str):
        """Delegate most channel functions to original session"""

        return getattr(self._orig_session, attr)

    def session_started(self) -> None:
        """Start a session for this newly opened server channel"""

        self._editor = self._chan.create_editor()
        self._orig_session.session_started()

    def terminal_size_changed(self, width: int, height: int,
                              pixwidth: int, pixheight: int) -> None:
        """The terminal size has changed"""

        if self._editor:
            self._editor.set_width(width)

        self._orig_session.terminal_size_changed(width, height,
                                                 pixwidth, pixheight)

    def data_received(self, data: str, datatype: DataType) -> None:
        """Process data received from the channel"""

        if self._editor:
            self._editor.process_input(data, datatype)
        else:
            self._orig_session.data_received(data, datatype)

    def eof_received(self) -> Optional[bool]:
        """Process EOF received from the channel"""

        if self._editor:
            self._editor.set_line_mode(False)

        return self._orig_session.eof_received()
