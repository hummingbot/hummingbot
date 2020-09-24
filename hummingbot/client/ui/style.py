from prompt_toolkit.styles import Style
from prompt_toolkit.utils import is_windows


def load_style():
    """
    Return a dict mapping {ui_style_name -> style_dict}.
    """
    if is_windows():
        return Style.from_dict(win32_code_style)
    else:
        return Style.from_dict(default_ui_style)


default_ui_style = {
    "output-field":               "bg:#171E2B #1CD085",  # noqa: E241
    "input-field":                "bg:#000000 #FFFFFF",  # noqa: E241
    "log-field":                  "bg:#171E2B #FFFFFF",  # noqa: E241
    "title":                      "bg:#000000 #AAAAAA",  # noqa: E241
    "search":                     "bg:#000000 #93C36D",  # noqa: E241
    "search.current":             "bg:#000000 #1CD085",  # noqa: E241
    "primary":                    "#1CD085",  # noqa: E241
    "warning":                    "#93C36D",  # noqa: E241
    "error":                      "#F5634A",  # noqa: E241
}


# Style for an older version of Windows consoles. They support only 16 colors,
# so we choose a combination that displays nicely.
win32_code_style = {
    "output-field":               "#ansigreen",  # noqa: E241
    "input-field":                "#ansiwhite",  # noqa: E241
    "log-field":                  "#ansiwhite",  # noqa: E241
    "search":                     "#ansigreen",  # noqa: E241
    "search.current":             "#ansigreen",  # noqa: E241
    "primary":                    "#ansigreen",  # noqa: E241
    "warning":                    "#ansibrightyellow",  # noqa: E241
    "error":                      "#ansired",  # noqa: E241
}
