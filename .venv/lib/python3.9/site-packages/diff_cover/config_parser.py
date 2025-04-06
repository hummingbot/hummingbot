import abc
import enum

try:
    import tomli as toml

    _HAS_TOML = True
except ImportError:  # pragma: no cover
    _HAS_TOML = False

if not _HAS_TOML:
    try:
        import tomllib as toml

        _HAS_TOML = True
    except ImportError:  # pragma: no cover
        pass


class Tool(enum.Enum):
    DIFF_COVER = enum.auto()
    DIFF_QUALITY = enum.auto()


class ParserError(Exception):
    pass


class ConfigParser(abc.ABC):
    def __init__(self, file_name, tool):
        self._file_name = file_name
        self._tool = tool

    @abc.abstractmethod
    def parse(self):
        """Returns a dict of the parsed data or None if the file cannot be handled."""


class TOMLParser(ConfigParser):
    def __init__(self, file_name, tool):
        super().__init__(file_name, tool)
        self._section = "diff_cover" if tool == Tool.DIFF_COVER else "diff_quality"

    def parse(self):
        if not self._file_name.endswith(".toml"):
            return None

        if not _HAS_TOML:
            raise ParserError("No Toml lib installed")

        with open(self._file_name, "rb") as file_handle:
            config = toml.load(file_handle)

        config = config.get("tool", {}).get(self._section, {})
        if not config:
            raise ParserError(f"No 'tool.{self._section}' configuration available")
        return config


_PARSERS = [TOMLParser]


def _parse_config_file(file_name, tool):
    for parser_class in _PARSERS:
        parser = parser_class(file_name, tool)
        config = parser.parse()
        if config:
            return config

    raise ParserError(f"No config parser could handle {file_name}")


def get_config(parser, argv, defaults, tool):
    cli_config = vars(parser.parse_args(argv))
    if cli_config["config_file"]:
        file_config = _parse_config_file(cli_config["config_file"], tool)
    else:
        file_config = {}

    config = defaults
    for config_dict in [file_config, cli_config]:
        for key, value in config_dict.items():
            if value is None:
                # if the value is None, it's a default one; only override if not present
                config.setdefault(key, value)
            else:
                # else just override the existing value
                config[key] = value

    return config
