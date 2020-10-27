import importlib
from typing import (
    Dict,
    Any,
    Optional,
)
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.client.settings import CONNECTOR_SETTINGS, ConnectorType
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
        tasks = []
        fetched_connectors = []
        for conn_setting in CONNECTOR_SETTINGS.values():
            module_name = f"{conn_setting.base_name()}_utils" if conn_setting.type is ConnectorType.Connector \
                else f"{conn_setting.base_name()}_api_order_book_data_source"
            module_path = f"hummingbot.connector.{conn_setting.type.name.lower()}." \
                          f"{conn_setting.base_name()}.{module_name}"
            if conn_setting.type is ConnectorType.Connector:
                module = importlib.import_module(module_path)
            else:
                class_name = "".join([o.capitalize() for o in conn_setting.base_name().split("_")]) + \
                             "APIOrderBookDataSource"
                module = getattr(importlib.import_module(module_path), class_name)
            args = {}
            args = conn_setting.add_domain_parameter(args)
            tasks.append(module.fetch_trading_pairs(**args))
            fetched_connectors.append(conn_setting.name)

        results = await safe_gather(*tasks, return_exceptions=True)
        self.trading_pairs = dict(zip(fetched_connectors, results))
        self.ready = True
