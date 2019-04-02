from prompt_toolkit.styles import Style
from prompt_toolkit.utils import is_windows, is_windows_vt100_supported


def load_style():
    """
    Return a dict mapping {ui_style_name -> style_dict}.
    """
    if is_windows() and not is_windows_vt100_supported():
        return Style.from_dict(win32_code_style)
    else:
        return Style.from_dict(default_ui_style)


default_ui_style = {
    'output-field':               'bg:#171E2B #1CD085',
    'input-field':                'bg:#000000 #ffffff',
    'log-field':                  'bg:#171E2B #ffffff',
    'line':                       '#1CD085',
    'label':                      'bg:#000000 #1CD085',
}


# Style for Windows consoles. They support only 16 colors,
# so we choose a combination that displays nicely.
win32_code_style = {
    'output-field':               'bg:#000000 #44ff44',
    'input-field':                'bg:#000000 #ffffff',
    'log-field':                  'bg:#000000 #ffffff',
    'line':                       '#44ff44',
    'label':                      'bg:#000000 #44ff44',
}
