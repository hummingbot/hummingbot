import importlib
from typing import (
    Dict,
    Any,
    Optional,
)
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.client.settings import ALL_CONNECTORS
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
        for connector_type, connectors in ALL_CONNECTORS.items():
            if connector_type != "connector":
                for connector in connectors:
                    module_name = f"{connector}_api_order_book_data_source"
                    class_name = "".join([o.capitalize() for o in connector.split("_")]) + "APIOrderBookDataSource"
                    module_path = f"hummingbot.connector.{connector_type}.{connector}.{module_name}"
                    module = getattr(importlib.import_module(module_path), class_name)
                    tasks.append(module.fetch_trading_pairs())
                    fetched_connectors.append(connector)

        results = await safe_gather(*tasks, return_exceptions=True)
        self.trading_pairs = dict(zip(fetched_connectors, results))
        self.ready = True
