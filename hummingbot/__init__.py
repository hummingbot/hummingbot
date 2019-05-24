#!/usr/bin/env python
import logging
from typing import Optional
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from hummingbot.logger.struct_logger import (
    StructLogRecord,
    StructLogger
)

STRUCT_LOGGER_SET = False
_prefix_path = None

__all__ = ["root_path", "get_executor"]


# Do not raise exceptions during log handling
logging.setLogRecordFactory(StructLogRecord)
logging.setLoggerClass(StructLogger)

_shared_executor = None


def root_path() -> str:
    from os.path import realpath, join
    return realpath(join(__file__, "../../"))


def get_executor() -> ThreadPoolExecutor:
    global _shared_executor
    if _shared_executor is None:
        _shared_executor = ThreadPoolExecutor()
    return _shared_executor


def prefix_path() -> str:
    global _prefix_path
    if _prefix_path is None:
        from os.path import realpath, join
        _prefix_path = realpath(join(__file__, "../../"))
    return _prefix_path


def set_prefix_path(path: str):
    global _prefix_path
    _prefix_path = path


def check_dev_mode():
    try:
        current_branch = subprocess.check_output(["git", "symbolic-ref", "--short", "HEAD"]).decode("utf8").rstrip()
        if current_branch != "master":
            return True
    except:
        return False


def add_remote_logger_handler(loggers):
    from hummingbot.logger.reporting_proxy_handler import ReportingProxyHandler
    root_logger = logging.getLogger()
    try:
        remote_logger = ReportingProxyHandler(level="DEBUG",
                                              proxy_url="https://api.coinalpha.com/reporting-proxy",
                                              capacity=5
                                              )
        root_logger.addHandler(remote_logger)
        for logger_name in loggers:
            logger = logging.getLogger(logger_name)
            logger.addHandler(remote_logger)
    except Exception:
        root_logger.error("Error adding remote log handler.", exc_info=True)


def init_logging(conf_filename: str, override_log_level: Optional[str] = None, dev_mode: bool = False):
    import io
    import logging.config
    from os.path import join
    import pandas as pd
    from typing import Dict
    from ruamel.yaml import YAML

    from hummingbot.client.config.global_config_map import global_config_map
    from hummingbot.logger import reporting_proxy_handler
    from hummingbot.logger.struct_logger import (
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
        # add remote logging to logger if in dev mode
        if dev_mode:
            add_remote_logger_handler(config_dict.get("loggers", []))
