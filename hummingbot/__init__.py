#!/usr/bin/env python
from typing import Optional

STRUCT_LOGGER_SET = False
_prefix_path = None


def prefix_path() -> str:
    global _prefix_path
    if _prefix_path is None:
        from os.path import realpath, join
        _prefix_path = realpath(join(__file__, "../../"))
    return _prefix_path


def set_prefix_path(path: str):
    global _prefix_path
    _prefix_path = path


def init_logging(conf_filename: str, override_log_level: Optional[str] = None):
    import io
    import logging.config
    from os.path import join
    import pandas as pd
    from typing import Dict
    from ruamel.yaml import YAML

    from hummingbot.cli.config.global_config_map import global_config_map
    from hummingbot.logger import reporting_proxy_handler
    from wings.logger.struct_logger import (
        StructLogRecord,
        StructLogger
    )

    global STRUCT_LOGGER_SET
    if not STRUCT_LOGGER_SET:
        logging.setLogRecordFactory(StructLogRecord)
        logging.setLoggerClass(StructLogger)
        STRUCT_LOGGER_SET = True

    # Do not raise exceptions during log handling
    logging.raiseExceptions = False

    file_path: str = join(prefix_path(), "conf", conf_filename)
    yaml_parser: YAML = YAML()
    with open(file_path) as fd:
        yml_source: str = fd.read()
        yml_source = yml_source.replace("$PROJECT_DIR", prefix_path())
        yml_source = yml_source.replace("$DATETIME", pd.Timestamp.now().strftime("%Y-%m-%d-%H-%M-%S"))
        io_stream: io.StringIO = io.StringIO(yml_source)
        config_dict: Dict = yaml_parser.load(io_stream)
        if override_log_level is not None and "loggers" in config_dict:
            for logger in config_dict["loggers"]:
                if global_config_map["logger_override_whitelist"].value and \
                        logger in global_config_map["logger_override_whitelist"].value:
                    config_dict["loggers"][logger]["level"] = override_log_level
        logging.config.dictConfig(config_dict)
