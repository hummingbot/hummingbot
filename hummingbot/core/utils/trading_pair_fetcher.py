import importlib
from typing import (
    Dict,
    Any,
    Optional,
    Callable,
    Awaitable,
    List
)
from hummingbot.logger import HummingbotLogger
from hummingbot.client.settings import AllConnectorSettings, ConnectorType
import logging

from .async_utils import safe_ensure_future


class TradingPairFetcher:
    _sf_shared_instance: "TradingPairFetcher" = None
    _tpf_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._tpf_logger is None:
            cls._tpf_logger = logging.getLogger(__name__)
        return cls._tpf_logger

    @classmethod
    def get_instance(cls) -> "TradingPairFetcher":
        if cls._sf_shared_instance is None:
            cls._sf_shared_instance = TradingPairFetcher()
        return cls._sf_shared_instance

    def __init__(self):
        self.ready = False
        self.trading_pairs: Dict[str, Any] = {}
        safe_ensure_future(self.fetch_all())

    async def fetch_all(self):
        for conn_setting in AllConnectorSettings.get_connector_settings().values():
            if conn_setting.base_name().endswith("paper_trade"):
                if conn_setting.parent_name in self.trading_pairs:
                    self.trading_pairs[conn_setting.base_name()] = self.trading_pairs[conn_setting.parent_name]
                    continue
                exchange_name = conn_setting.parent_name
            else:
                exchange_name = conn_setting.base_name()

            module_name = f"{exchange_name}_connector" if conn_setting.type is ConnectorType.Connector \
                else f"{exchange_name}_api_order_book_data_source"
            module_path = f"hummingbot.connector.{conn_setting.type.name.lower()}." \
                          f"{exchange_name}.{module_name}"
            class_name = "".join([o.capitalize() for o in exchange_name.split("_")]) + \
                         "APIOrderBookDataSource" if conn_setting.type is not ConnectorType.Connector \
                         else "".join([o.capitalize() for o in exchange_name.split("_")]) + "Connector"
            module = getattr(importlib.import_module(module_path), class_name)
            args = {}
            args = conn_setting.add_domain_parameter(args)
            safe_ensure_future(self.call_fetch_pairs(module.fetch_trading_pairs(**args), conn_setting.name))

        self.ready = True

    async def call_fetch_pairs(self, fetch_fn: Callable[[], Awaitable[List[str]]], exchange_name: str):
        try:
            self.trading_pairs[exchange_name] = await fetch_fn
        except Exception:
            self.logger().error(f"Connector {exchange_name} failed to retrieve its trading pairs. "
                                f"Trading pairs autocompletion won't work.", exc_info=True)
            # In case of error just assign empty list, this is st. the bot won't stop working
            self.trading_pairs[exchange_name] = []
