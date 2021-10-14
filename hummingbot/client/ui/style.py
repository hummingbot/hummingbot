from prompt_toolkit.styles import Style
from prompt_toolkit.utils import is_windows
from hummingbot.client.config.global_config_map import global_config_map


def load_style(config_map=global_config_map):
    """
    Return a dict mapping {ui_style_name -> style_dict}.
    """

    # Load config
    color_top_pane = config_map.get("top-pane").value
    color_bottom_pane = config_map.get("bottom-pane").value
    color_output_pane = config_map.get("output-pane").value
    color_input_pane = config_map.get("input-pane").value
    color_logs_pane = config_map.get("logs-pane").value
    color_terminal_primary = config_map.get("terminal-primary").value

    if is_windows():
        # Load default style
        style = win32_code_style

        # Translate HEX to ANSI
        color_top_pane = hex_to_ansi(color_top_pane)
        color_bottom_pane = hex_to_ansi(color_bottom_pane)
        color_output_pane = hex_to_ansi(color_output_pane)
        color_input_pane = hex_to_ansi(color_input_pane)
        color_logs_pane = hex_to_ansi(color_logs_pane)
        color_terminal_primary = hex_to_ansi(color_terminal_primary)

        # Apply custom configuration
        style["output-field"] = "bg:" + color_output_pane + " " + color_terminal_primary
        style["input-field"] = "bg:" + color_input_pane + " " + style["input-field"].split(' ')[-1]
        style["log-field"] = "bg:" + color_logs_pane + " " + style["log-field"].split(' ')[-1]
        style["header"] = "bg:" + color_top_pane + " " + style["header"].split(' ')[-1]
        style["footer"] = "bg:" + color_bottom_pane + " " + style["footer"].split(' ')[-1]
        style["primary"] = color_terminal_primary
        style["search"] = color_terminal_primary
        style["search.current"] = color_terminal_primary

        return Style.from_dict(style)

    else:
        # Load default style
        style = default_ui_style

        # Apply custom configuration
        style["output-field"] = "bg:" + color_output_pane + " " + color_terminal_primary
        style["input-field"] = "bg:" + color_input_pane + " " + style["input-field"].split(' ')[-1]
        style["log-field"] = "bg:" + color_logs_pane + " " + style["log-field"].split(' ')[-1]
        style["header"] = "bg:" + color_top_pane + " " + style["header"].split(' ')[-1]
        style["footer"] = "bg:" + color_bottom_pane + " " + style["footer"].split(' ')[-1]
        style["primary"] = color_terminal_primary

        return Style.from_dict(style)


def reset_style(config_map=global_config_map):
    # Reset config
    config_map.get("top-pane").value = config_map.get("top-pane").default
    config_map.get("bottom-pane").value = config_map.get("bottom-pane").default
    config_map.get("output-pane").value = config_map.get("output-pane").default
    config_map.get("input-pane").value = config_map.get("input-pane").default
    config_map.get("logs-pane").value = config_map.get("logs-pane").default
    config_map.get("terminal-primary").value = config_map.get("terminal-primary").default

    # Apply & return style
    return load_style(config_map)


def hex_to_ansi(color_hex):
    ansi_palette = {"000000": "ansiblack",
                    "FF0000": "ansired",
                    "00FF00": "ansigreen",
                    "FFFF00": "ansiyellow",
                    "0000FF": "ansiblue",
                    "FF00FF": "ansimagenta",
                    "00FFFF": "ansicyan",
                    "F0F0F0": "ansigray"}

    # Sanitization
    color_hex = color_hex.replace('#', '')

    # Calculate distance, choose the closest ANSI color
    hex_r = int(color_hex[0:2], 16)
    hex_g = int(color_hex[2:4], 16)
    hex_b = int(color_hex[4:6], 16)

    distance_min = None

    for ansi_hex in ansi_palette:
        ansi_r = int(ansi_hex[0:2], 16)
        ansi_g = int(ansi_hex[2:4], 16)
        ansi_b = int(ansi_hex[4:6], 16)

        distance = abs(ansi_r - hex_r) + abs(ansi_g - hex_g) + abs(ansi_b - hex_b)

        if distance_min is None or distance < distance_min:
            distance_min = distance
            color_ansi = ansi_palette[ansi_hex]

    return "#" + color_ansi


default_ui_style = {
    "output-field":               "bg:#171E2B #1CD085",  # noqa: E241
    "input-field":                "bg:#000000 #FFFFFF",  # noqa: E241
    "log-field":                  "bg:#171E2B #FFFFFF",  # noqa: E241
    "header":                     "bg:#000000 #AAAAAA",  # noqa: E241
    "footer":                     "bg:#000000 #AAAAAA",  # noqa: E241
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
