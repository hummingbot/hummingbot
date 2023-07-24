import inspect
import logging
import os
from dataclasses import dataclass
from decimal import Decimal
from os.path import join

from pydantic import Field, SecretStr

from hummingbot import prefix_path
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.web_assistant.connections.data_types import EndpointRESTRequest

from . import coinbase_advanced_trade_v2_constants as constants

CENTRALIZED = True
EXAMPLE_PAIR = "ZRX-ETH"

DEFAULT_FEES = TradeFeeSchema(
    percent_fee_token="USD",
    maker_percent_fee_decimal=Decimal("0.004"),
    taker_percent_fee_decimal=Decimal("0.006"),
    buy_percent_fee_deducted_from_returns=False
)


@dataclass
class CoinbaseAdvancedTradeV2RESTRequest(EndpointRESTRequest):
    def __post_init__(self):
        super().__post_init__()
        self._ensure_endpoint_for_auth()

    @property
    def base_url(self) -> str:
        return constants.REST_URL

    def _ensure_endpoint_for_auth(self):
        if self.is_auth_required and self.endpoint is None:
            raise ValueError("The endpoint must be specified if authentication is required.")


class CoinbaseAdvancedTradeV2ConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="coinbase_advanced_trade_v2", const=True, client_data=None)
    coinbase_advanced_trade_v2_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinbase Advanced Trade API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    coinbase_advanced_trade_v2_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinbase Advanced Trade API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "coinbase_advanced_trade_v2"


KEYS = CoinbaseAdvancedTradeV2ConfigMap.construct()


class FlushingFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)  # First, do the original emit work.
        self.flush()  # Then, force an immediate flush.


class DebugToFile:
    indent: str = ""
    _logger: logging.Logger
    _csv_logger: logging.Logger

    @classmethod
    def setup_logger(cls, log_file: str, level=logging.NOTSET):
        if os.environ.get("DEBUG_FILE_LOGGING", "0") == "0":
            return
        log_file = join(prefix_path(), "logs", log_file)
        csv_file = f"{log_file}.csv"

        if not hasattr(cls, "_logger"):
            file_handler = FlushingFileHandler(log_file, mode='w')
            csv_handler = FlushingFileHandler(csv_file, mode='w')
            file_handler.close()
            csv_handler.close()
        file_handler = FlushingFileHandler(log_file, mode='a')
        csv_handler = FlushingFileHandler(csv_file, mode='a')

        cls._logger = logging.getLogger("DebugLogger")
        cls._csv_logger = logging.getLogger("CSVLogger")

        cls._logger.disabled = False
        cls._csv_logger.disabled = False

        cls._logger.propagate = False
        cls._csv_logger.propagate = False
        # stream_handler = logging.StreamHandler()

        cls._logger.setLevel(level)
        cls._csv_logger.setLevel(level)

        # Remove all handlers associated with the logger object.
        for handler in cls._logger.handlers[:]:
            cls._logger.removeHandler(handler)

        for handler in cls._csv_logger.handlers[:]:
            cls._csv_logger.removeHandler(handler)

        if file_handler not in cls._logger.handlers:
            cls._logger.addHandler(file_handler)
            cls._csv_logger.addHandler(csv_handler)
        # cls._logger.addHandler(stream_handler)

    @classmethod
    def stop_logger(cls):
        if os.environ.get("DEBUG_FILE_LOGGING", "0") == "0":
            return
        if hasattr(cls, "_logger"):
            cls._logger.disabled = True
            cls._csv_logger.disabled = True

    class LogDebugContext:
        def __init__(self, outer, *, message: str, bullet: str = " "):
            self.outer = outer
            self.message = message
            self.bullet = bullet

        def __enter__(self):
            self.outer.log_debug(message=self.message, bullet=self.bullet)
            self.outer.add_indent(bullet=self.bullet)
            return self.outer

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.outer.remove_indent()
            self.outer.log_debug("Done")

    @classmethod
    def log_with_bullet(cls, *, message, bullet: str):
        if os.environ.get("DEBUG_FILE_LOGGING", "0") == "0":
            return
        return cls.LogDebugContext(cls, message=message, bullet=bullet)

    @classmethod
    def log_debug(cls, message,
                  indent_next: bool = False,
                  unindent_next: bool = False,
                  *,
                  condition: bool = True,
                  bullet: str = " "):
        if os.environ.get("DEBUG_FILE_LOGGING", "0") == "0":
            return
        if cls._logger is None:
            print("DebugToFile.setup_logger() must be called before using DebugToFile.log_debug()")
            return
        if not condition:
            return

        caller_frame = inspect.stack()[1]
        filename = os.path.basename(caller_frame.filename).split('.')[0]
        lineno = caller_frame.lineno
        func_name = caller_frame.function

        if len(filename) > 17:
            filename = f"...{filename[-17:]}"
        if len(func_name) > 17:
            func_name = f"...{func_name[-17:]}"
        if len(message) > 100:
            message = f"{message[:200]}..."

        indented_message = message.replace('\n', '\n' + cls.indent)

        cls._logger.debug(f"{cls.indent}{indented_message}")

        cls._csv_logger.debug(f"[{filename:>20}:{func_name:>20}:{lineno:>4}],"
                              f"{cls.indent}{indented_message}")

        if indent_next:
            cls.add_indent(bullet=bullet)
        if unindent_next:
            cls.remove_indent()

    @classmethod
    def add_indent(cls, *, bullet: str = " "):
        if os.environ.get("DEBUG_FILE_LOGGING", "0") == "0":
            return
        cls.indent += f"{bullet}   "

    @classmethod
    def remove_indent(cls):
        if os.environ.get("DEBUG_FILE_LOGGING", "0") == "0":
            return
        cls.indent = cls.indent[:-4]
