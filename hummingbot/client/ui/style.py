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
    "output-field":               "bg:#171E2B #1CD085",
    "input-field":                "bg:#000000 #FFFFFF",
    "log-field":                  "bg:#171E2B #FFFFFF",
    "title":                      "bg:#000000 #AAAAAA",
    "search":                     "bg:#000000 #93C36D",
    "search.current":             "bg:#000000 #1CD085",
    "primary":                    "#1CD085",
    "warning":                    "#93C36D",
    "error":                      "#F5634A",
}


# Style for an older version of Windows consoles. They support only 16 colors,
# so we choose a combination that displays nicely.
win32_code_style = {
    "output-field":               "#ansigreen",
    "input-field":                "#ansiwhite",
    "log-field":                  "#ansiwhite",
    "search":                     "#ansigreen",
    "search.current":             "#ansigreen",
    "primary":                    "#ansigreen",
    "warning":                    "#ansibrightyellow",
    "error":                      "#ansired",
}

