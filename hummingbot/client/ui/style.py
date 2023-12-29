from typing import Union

from prompt_toolkit.styles import Style
from prompt_toolkit.utils import is_windows

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter, save_to_yml
from hummingbot.client.settings import CLIENT_CONFIG_PATH


def load_style(config_map: ClientConfigAdapter):
    """
    Return a dict mapping {ui_style_name -> style_dict}.
    """
    config_map: Union[ClientConfigAdapter, ClientConfigMap] = config_map  # to enable IDE auto-complete
    # Load config
    color_top_pane = config_map.color.top_pane
    color_bottom_pane = config_map.color.bottom_pane
    color_output_pane = config_map.color.output_pane
    color_input_pane = config_map.color.input_pane
    color_logs_pane = config_map.color.logs_pane
    color_terminal_primary = config_map.color.terminal_primary

    color_primary_label = config_map.color.primary_label
    color_secondary_label = config_map.color.secondary_label
    color_success_label = config_map.color.success_label
    color_warning_label = config_map.color.warning_label
    color_info_label = config_map.color.info_label
    color_error_label = config_map.color.error_label
    color_gold_label = config_map.color.gold_label
    color_silver_label = config_map.color.silver_label
    color_bronze_label = config_map.color.bronze_label

    if is_windows():
        # Load default style for Windows
        style = win32_code_style

        # Translate HEX to ANSI
        color_top_pane = hex_to_ansi(color_top_pane)
        color_bottom_pane = hex_to_ansi(color_bottom_pane)
        color_output_pane = hex_to_ansi(color_output_pane)
        color_input_pane = hex_to_ansi(color_input_pane)
        color_logs_pane = hex_to_ansi(color_logs_pane)
        color_terminal_primary = hex_to_ansi(color_terminal_primary)

        color_primary_label = hex_to_ansi(color_primary_label)
        color_secondary_label = hex_to_ansi(color_secondary_label)
        color_success_label = hex_to_ansi(color_success_label)
        color_warning_label = hex_to_ansi(color_warning_label)
        color_info_label = hex_to_ansi(color_info_label)
        color_error_label = hex_to_ansi(color_error_label)
        color_gold_label = hex_to_ansi(color_gold_label)
        color_silver_label = hex_to_ansi(color_silver_label)
        color_bronze_label = hex_to_ansi(color_bronze_label)

        # Apply custom configuration
        style["output_field"] = "bg:" + color_output_pane + " " + color_terminal_primary
        style["input_field"] = "bg:" + color_input_pane + " " + style["input_field"].split(' ')[-1]
        style["log_field"] = "bg:" + color_logs_pane + " " + style["log_field"].split(' ')[-1]
        style["tab_button.focused"] = "bg:" + color_terminal_primary + " " + color_logs_pane
        style["tab_button"] = style["tab_button"].split(' ')[0] + " " + color_logs_pane
        style["header"] = "bg:" + color_top_pane + " " + style["header"].split(' ')[-1]
        style["footer"] = "bg:" + color_bottom_pane + " " + style["footer"].split(' ')[-1]
        style["primary"] = color_terminal_primary
        style["dialog.body"] = style["dialog.body"].split(' ')[0] + " " + color_terminal_primary
        style["dialog frame.label"] = "bg:" + color_terminal_primary + " " + style["dialog frame.label"].split(' ')[-1]
        style["text-area"] = style["text-area"].split(' ')[0] + " " + color_terminal_primary
        style["search"] = color_terminal_primary
        style["search.current"] = color_terminal_primary

        style["primary_label"] = "bg:" + color_primary_label + " " + color_output_pane
        style["secondary_label"] = "bg:" + color_secondary_label + " " + color_output_pane
        style["success_label"] = "bg:" + color_success_label + " " + color_output_pane
        style["warning_label"] = "bg:" + color_warning_label + " " + color_output_pane
        style["info_label"] = "bg:" + color_info_label + " " + color_output_pane
        style["error_label"] = "bg:" + color_error_label + " " + color_output_pane
        style["gold_label"] = "bg:" + color_output_pane + " " + color_gold_label
        style["silver_label"] = "bg:" + color_output_pane + " " + color_silver_label
        style["bronze_label"] = "bg:" + color_output_pane + " " + color_bronze_label

        return Style.from_dict(style)

    else:
        # Load default style
        style = default_ui_style

        # Apply custom configuration
        style["output_field"] = "bg:" + color_output_pane + " " + color_terminal_primary
        style["input_field"] = "bg:" + color_input_pane + " " + style["input_field"].split(' ')[-1]
        style["log_field"] = "bg:" + color_logs_pane + " " + style["log_field"].split(' ')[-1]
        style["header"] = "bg:" + color_top_pane + " " + style["header"].split(' ')[-1]
        style["footer"] = "bg:" + color_bottom_pane + " " + style["footer"].split(' ')[-1]
        style["primary"] = color_terminal_primary
        style["dialog.body"] = style["dialog.body"].split(' ')[0] + " " + color_terminal_primary
        style["dialog frame.label"] = "bg:" + color_terminal_primary + " " + style["dialog frame.label"].split(' ')[-1]
        style["text-area"] = style["text-area"].split(' ')[0] + " " + color_terminal_primary
        style["tab_button.focused"] = "bg:" + color_terminal_primary + " " + color_logs_pane
        style["tab_button"] = style["tab_button"].split(' ')[0] + " " + color_logs_pane

        style["primary_label"] = "bg:" + color_primary_label + " " + color_output_pane
        style["secondary_label"] = "bg:" + color_secondary_label + " " + color_output_pane
        style["success_label"] = "bg:" + color_success_label + " " + color_output_pane
        style["warning_label"] = "bg:" + color_warning_label + " " + color_output_pane
        style["info_label"] = "bg:" + color_info_label + " " + color_output_pane
        style["error_label"] = "bg:" + color_error_label + " " + color_output_pane
        style["gold_label"] = "bg:" + color_output_pane + " " + color_gold_label
        style["silver_label"] = "bg:" + color_output_pane + " " + color_silver_label
        style["bronze_label"] = "bg:" + color_output_pane + " " + color_bronze_label
        return Style.from_dict(style)


def reset_style(config_map: ClientConfigAdapter, save=True):
    # Reset config

    config_map.color.top_pane = config_map.color.get_default("top_pane")
    config_map.color.bottom_pane = config_map.color.get_default("bottom_pane")
    config_map.color.output_pane = config_map.color.get_default("output_pane")
    config_map.color.input_pane = config_map.color.get_default("input_pane")
    config_map.color.logs_pane = config_map.color.get_default("logs_pane")
    config_map.color.terminal_primary = config_map.color.get_default("terminal_primary")

    config_map.color.primary_label = config_map.color.get_default("primary_label")
    config_map.color.secondary_label = config_map.color.get_default("secondary_label")
    config_map.color.success_label = config_map.color.get_default("success_label")
    config_map.color.warning_label = config_map.color.get_default("warning_label")
    config_map.color.info_label = config_map.color.get_default("info_label")
    config_map.color.error_label = config_map.color.get_default("error_label")
    config_map.color.gold_label = config_map.color.get_default("gold_label")
    config_map.color.silver_label = config_map.color.get_default("silver_label")
    config_map.color.bronze_label = config_map.color.get_default("bronze_label")

    # Save configuration
    if save:
        save_to_yml(CLIENT_CONFIG_PATH, config_map)

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
                    "F0F0F0": "ansigray",
                    "FFFFFF": "ansiwhite",
                    "FFD700": "ansiyellow",
                    "C0C0C0": "ansilightgray",
                    "CD7F32": "ansibrown"
                    }

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


text_ui_style = {
    "&cGOLD": "gold_label",
    "&cSILVER": "silver_label",
    "&cBRONZE": "bronze_label",
}

default_ui_style = {
    "output_field":               "bg:#171E2B #1CD085",  # noqa: E241
    "input_field":                "bg:#000000 #FFFFFF",  # noqa: E241
    "log_field":                  "bg:#171E2B #FFFFFF",  # noqa: E241
    "header":                     "bg:#000000 #AAAAAA",  # noqa: E241
    "footer":                     "bg:#000000 #AAAAAA",  # noqa: E241
    "search":                     "bg:#000000 #93C36D",  # noqa: E241
    "search.current":             "bg:#000000 #1CD085",  # noqa: E241
    "primary":                    "#1CD085",  # noqa: E241
    "warning":                    "#93C36D",  # noqa: E241
    "error":                      "#F5634A",  # noqa: E241
    "tab_button.focused":         "bg:#1CD085 #171E2B",  # noqa: E241
    "tab_button":                 "bg:#FFFFFF #000000",  # noqa: E241
    "dialog": "bg:#171E2B",
    "dialog frame.label": "bg:#FFFFFF #000000",
    "dialog.body": "bg:#000000 ",
    "dialog shadow": "bg:#171E2B",
    "button": "bg:#FFFFFF #000000",
    "text-area": "bg:#000000 #FFFFFF",
}


# Style for an older version of Windows consoles. They support only 16 colors,
# so we choose a combination that displays nicely.
win32_code_style = {
    "output_field":               "#ansigreen",  # noqa: E241
    "input_field":                "#ansiwhite",  # noqa: E241
    "log_field":                  "#ansiwhite",  # noqa: E241
    "header":                     "#ansiwhite",  # noqa: E241
    "footer":                     "#ansiwhite",  # noqa: E241
    "search":                     "#ansigreen",  # noqa: E241
    "search.current":             "#ansigreen",  # noqa: E241
    "primary":                    "#ansigreen",  # noqa: E241
    "warning":                    "#ansibrightyellow",  # noqa: E241
    "error":                      "#ansired",  # noqa: E241
    "tab_button.focused":         "bg:#ansigreen #ansiblack",  # noqa: E241
    "tab_button":                 "bg:#ansiwhite #ansiblack",  # noqa: E241
    "dialog": "bg:#ansigreen",
    "dialog frame.label": "bg:#ansiwhite #ansiblack",
    "dialog.body": "bg:#ansiblack ",
    "dialog shadow": "bg:#ansigreen",
    "button": "bg:#ansiwhite #ansiblack",
    "text-area": "bg:#ansiblack #ansigreen",
}
