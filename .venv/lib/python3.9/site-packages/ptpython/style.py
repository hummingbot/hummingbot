from __future__ import annotations

from prompt_toolkit.styles import BaseStyle, Style, merge_styles
from prompt_toolkit.styles.pygments import style_from_pygments_cls
from prompt_toolkit.utils import is_conemu_ansi, is_windows, is_windows_vt100_supported
from pygments.styles import get_all_styles, get_style_by_name

__all__ = ["get_all_code_styles", "get_all_ui_styles", "generate_style"]


def get_all_code_styles() -> dict[str, BaseStyle]:
    """
    Return a mapping from style names to their classes.
    """
    result: dict[str, BaseStyle] = {
        name: style_from_pygments_cls(get_style_by_name(name))
        for name in get_all_styles()
    }
    result["win32"] = Style.from_dict(win32_code_style)
    return result


def get_all_ui_styles() -> dict[str, BaseStyle]:
    """
    Return a dict mapping {ui_style_name -> style_dict}.
    """
    return {
        "default": Style.from_dict(default_ui_style),
        "blue": Style.from_dict(blue_ui_style),
    }


def generate_style(python_style: BaseStyle, ui_style: BaseStyle) -> BaseStyle:
    """
    Generate Pygments Style class from two dictionaries
    containing style rules.
    """
    return merge_styles([python_style, ui_style])


# Code style for Windows consoles. They support only 16 colors,
# so we choose a combination that displays nicely.
win32_code_style = {
    "pygments.comment": "#00ff00",
    "pygments.keyword": "#44ff44",
    "pygments.number": "",
    "pygments.operator": "",
    "pygments.string": "#ff44ff",
    "pygments.name": "",
    "pygments.name.decorator": "#ff4444",
    "pygments.name.class": "#ff4444",
    "pygments.name.function": "#ff4444",
    "pygments.name.builtin": "#ff4444",
    "pygments.name.attribute": "",
    "pygments.name.constant": "",
    "pygments.name.entity": "",
    "pygments.name.exception": "",
    "pygments.name.label": "",
    "pygments.name.namespace": "",
    "pygments.name.tag": "",
    "pygments.name.variable": "",
}


default_ui_style = {
    "control-character": "ansiblue",
    # Classic prompt.
    "prompt": "bold",
    "prompt.dots": "noinherit",
    # (IPython <5.0) Prompt: "In [1]:"
    "in": "bold #008800",
    "in.number": "",
    # Return value.
    "out": "#ff0000",
    "out.number": "#ff0000",
    # Completions.
    "completion.builtin": "",
    "completion.param": "#006666 italic",
    "completion.keyword": "fg:#008800",
    "completion.keyword fuzzymatch.inside": "fg:#008800",
    "completion.keyword fuzzymatch.outside": "fg:#44aa44",
    # Separator between windows. (Used above docstring.)
    "separator": "#bbbbbb",
    # System toolbar
    "system-toolbar": "#22aaaa noinherit",
    # "arg" toolbar.
    "arg-toolbar": "#22aaaa noinherit",
    "arg-toolbar.text": "noinherit",
    # Signature toolbar.
    "signature-toolbar": "bg:#44bbbb #000000",
    "signature-toolbar current-name": "bg:#008888 #ffffff bold",
    "signature-toolbar operator": "#000000 bold",
    "docstring": "#888888",
    # Validation toolbar.
    "validation-toolbar": "bg:#440000 #aaaaaa",
    # Status toolbar.
    "status-toolbar": "bg:#222222 #aaaaaa",
    "status-toolbar.title": "underline",
    "status-toolbar.inputmode": "bg:#222222 #ffffaa",
    "status-toolbar.key": "bg:#000000 #888888",
    "status-toolbar key": "bg:#000000 #888888",
    "status-toolbar.pastemodeon": "bg:#aa4444 #ffffff",
    "status-toolbar.pythonversion": "bg:#222222 #ffffff bold",
    "status-toolbar paste-mode-on": "bg:#aa4444 #ffffff",
    "record": "bg:#884444 white",
    "status-toolbar more": "#ffff44",
    "status-toolbar.input-mode": "#ffff44",
    # The options sidebar.
    "sidebar": "bg:#bbbbbb #000000",
    "sidebar.title": "bg:#668866 #ffffff",
    "sidebar.label": "bg:#bbbbbb #222222",
    "sidebar.status": "bg:#dddddd #000011",
    "sidebar.label selected": "bg:#222222 #eeeeee",
    "sidebar.status selected": "bg:#444444 #ffffff bold",
    "sidebar.separator": "underline",
    "sidebar.key": "bg:#bbddbb #000000 bold",
    "sidebar.key.description": "bg:#bbbbbb #000000",
    "sidebar.helptext": "bg:#fdf6e3 #000011",
    #        # Styling for the history layout.
    #        history.line:                          '',
    #        history.line.selected:                 'bg:#008800  #000000',
    #        history.line.current:                  'bg:#ffffff #000000',
    #        history.line.selected.current:         'bg:#88ff88 #000000',
    #        history.existinginput:                  '#888888',
    # Help Window.
    "window-border": "#aaaaaa",
    "window-title": "bg:#bbbbbb #000000",
    # Meta-enter message.
    "accept-message": "bg:#ffff88 #444444",
    # Exit confirmation.
    "exit-confirmation": "bg:#884444 #ffffff",
}


# Some changes to get a bit more contrast on Windows consoles.
# (They only support 16 colors.)
if is_windows() and not is_conemu_ansi() and not is_windows_vt100_supported():
    default_ui_style.update(
        {
            "sidebar.title": "bg:#00ff00 #ffffff",
            "exitconfirmation": "bg:#ff4444 #ffffff",
            "toolbar.validation": "bg:#ff4444 #ffffff",
            "menu.completions.completion": "bg:#ffffff #000000",
            "menu.completions.completion.current": "bg:#aaaaaa #000000",
        }
    )


blue_ui_style = {}
blue_ui_style.update(default_ui_style)
# blue_ui_style.update({
#        # Line numbers.
#        Token.LineNumber:                             '#aa6666',
#
#        # Highlighting of search matches in document.
#        Token.SearchMatch:                            '#ffffff bg:#4444aa',
#        Token.SearchMatch.Current:                    '#ffffff bg:#44aa44',
#
#        # Highlighting of select text in document.
#        Token.SelectedText:                           '#ffffff bg:#6666aa',
#
#        # Completer toolbar.
#        Token.Toolbar.Completions:                    'bg:#44bbbb #000000',
#        Token.Toolbar.Completions.Arrow:              'bg:#44bbbb #000000 bold',
#        Token.Toolbar.Completions.Completion:         'bg:#44bbbb #000000',
#        Token.Toolbar.Completions.Completion.Current: 'bg:#008888 #ffffff',
#
#        # Completer menu.
#        Token.Menu.Completions.Completion:            'bg:#44bbbb #000000',
#        Token.Menu.Completions.Completion.Current:    'bg:#008888 #ffffff',
#        Token.Menu.Completions.Meta:                  'bg:#449999 #000000',
#        Token.Menu.Completions.Meta.Current:          'bg:#00aaaa #000000',
#        Token.Menu.Completions.ProgressBar:           'bg:#aaaaaa',
#        Token.Menu.Completions.ProgressButton:        'bg:#000000',
# })
