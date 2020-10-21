#!/usr/bin/env python
from typing import (
    List,
    Optional
)
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from os import (
    listdir,
    path,
)
import sys

from hummingbot.logger.struct_logger import (
    StructLogRecord,
    StructLogger
)

STRUCT_LOGGER_SET = False
DEV_STRATEGY_PREFIX = "dev"
_prefix_path = None

# Do not raise exceptions during log handling
logging.setLogRecordFactory(StructLogRecord)
logging.setLoggerClass(StructLogger)

_shared_executor = None
_data_path = None
_cert_path = None


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
        from os.path import (
            realpath,
            join
        )
        _prefix_path = realpath(join(__file__, "../../"))
    return _prefix_path


def set_prefix_path(path: str):
    global _prefix_path
    _prefix_path = path


def data_path() -> str:
    global _data_path
    if _data_path is None:
        from os.path import (
            realpath,
            join
        )
        _data_path = realpath(join(prefix_path(), "data"))

    import os
    if not os.path.exists(_data_path):
        os.makedirs(_data_path)
    return _data_path


def set_data_path(path: str):
    global _data_path
    _data_path = path


def cert_path() -> str:
    global _cert_path
    if _cert_path is None:
        from os.path import (
            realpath,
            join
        )
        _cert_path = realpath(join(prefix_path(), "certs"))

    import os
    if not os.path.exists(_cert_path):
        os.makedirs(_cert_path)
    return _cert_path


def set_cert_path(path: str):
    global _cert_path
    _cert_path = path


_independent_package: Optional[bool] = None


def is_independent_package() -> bool:
    global _independent_package
    import os
    if _independent_package is None:
        _independent_package = not os.path.basename(sys.executable).startswith("python")
    return _independent_package


def check_dev_mode():
    try:
        if is_independent_package():
            return False
        if not path.isdir(".git"):
            return False
        current_branch = subprocess.check_output(["git", "symbolic-ref", "--short", "HEAD"]).decode("utf8").rstrip()
        if current_branch != "master":
            return True
    except Exception:
        return False


def chdir_to_data_directory():
    if not is_independent_package():
        # Do nothing.
        return

    import appdirs
    import os
    app_data_dir: str = appdirs.user_data_dir("Hummingbot", "hummingbot.io")
    os.makedirs(os.path.join(app_data_dir, "logs"), 0o711, exist_ok=True)
    os.makedirs(os.path.join(app_data_dir, "conf"), 0o711, exist_ok=True)
    os.makedirs(os.path.join(app_data_dir, "scripts"), 0o711, exist_ok=True)
    os.makedirs(os.path.join(app_data_dir, "certs"), 0o711, exist_ok=True)
    os.chdir(app_data_dir)
    set_prefix_path(app_data_dir)


def add_remote_logger_handler(loggers):
    from hummingbot.logger.reporting_proxy_handler import ReportingProxyHandler
    root_logger = logging.getLogger()
    try:
        from hummingbot.client.config.global_config_map import global_config_map
        log_server_url = global_config_map.get("log_server_url", "https://api.coinalpha.com/reporting-proxy")
        remote_logger = ReportingProxyHandler(level="ERROR",
                                              proxy_url=log_server_url,
                                              capacity=5)
        root_logger.addHandler(remote_logger)
        for logger_name in loggers:
            logger = logging.getLogger(logger_name)
            logger.addHandler(remote_logger)
    except Exception:
        root_logger.error("Error adding remote log handler.", exc_info=True)


def init_logging(conf_filename: str,
                 override_log_level: Optional[str] = None,
                 dev_mode: bool = False,
                 strategy_file_path: str = "hummingbot"):
    import io
    import logging.config
    from os.path import join
    import pandas as pd
    from typing import Dict
    from ruamel.yaml import YAML

    from hummingbot.client.config.global_config_map import global_config_map
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
        yml_source = yml_source.replace("$STRATEGY_FILE_PATH", strategy_file_path.replace(".yml", ""))
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


def get_strategy_list() -> List[str]:
    """
    Search `hummingbot.strategy` folder for all available strategies
    Automatically hide all strategies that starts with "dev" if on master branch
    """
    try:
        folder = path.realpath(path.join(__file__, "../strategy"))
        # Only include valid directories
        strategies = [d for d in listdir(folder) if path.isdir(path.join(folder, d)) and not d.startswith("__")]
        on_dev_mode = check_dev_mode()
        if not on_dev_mode:
            strategies = [s for s in strategies if not s.startswith(DEV_STRATEGY_PREFIX)]
        return sorted(strategies)
    except Exception as e:
        logging.getLogger().warning(f"Error getting strategy set: {str(e)}")
        return []
