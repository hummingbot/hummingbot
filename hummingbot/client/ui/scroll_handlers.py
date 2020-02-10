from prompt_toolkit.layout.containers import Window
from prompt_toolkit.buffer import Buffer
from typing import Optional


def scroll_down(event, window: Optional[Window] = None, buffer: Optional[Buffer] = None):
    w = window or event.app.layout.current_window
    b = buffer or event.app.current_buffer

    if w and w.render_info:
        info = w.render_info
        ui_content = info.ui_content

        # Height to scroll.
        scroll_height = info.window_height // 2

        # Calculate how many lines is equivalent to that vertical space.
        y = b.document.cursor_position_row + 1
        height = 0
        while y < ui_content.line_count:
            line_height = info.get_height_for_line(y)

            if height + line_height < scroll_height:
                height += line_height
                y += 1
            else:
                break

        b.cursor_position = b.document.translate_row_col_to_index(y, 0)


def scroll_up(event, window: Optional[Window] = None, buffer: Optional[Buffer] = None):
    w = window or event.app.layout.current_window
    b = buffer or event.app.current_buffer

    if w and w.render_info:
        info = w.render_info

        # Height to scroll.
        scroll_height = info.window_height // 2

        # Calculate how many lines is equivalent to that vertical space.
        y = max(0, b.document.cursor_position_row - 1)
        height = 0
        while y > 0:
            line_height = info.get_height_for_line(y)

            if height + line_height < scroll_height:
                height += line_height
                y -= 1
            else:
                break

        b.cursor_position = b.document.translate_row_col_to_index(y, 0)
