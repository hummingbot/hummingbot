from typing import Optional
from decimal import Decimal
import importlib
from hummingbot.client.settings import ALL_CONNECTORS


def get_mid_price(exchange: str, trading_pair: str) -> Optional[Decimal]:

    mid_price = None
    for connector_type, connectors in ALL_CONNECTORS.items():
        if exchange in connectors:
            try:
                module_name = f"{exchange}_api_order_book_data_source"
                class_name = "".join([o.capitalize() for o in exchange.split("_")]) + "APIOrderBookDataSource"
                module_path = f"hummingbot.connector.{connector_type}.{exchange}.{module_name}"
                module = getattr(importlib.import_module(module_path), class_name)
                mid_price = module.get_mid_price(trading_pair)
            except Exception:
                pass
    if mid_price is None:
        module_name = "binance_api_order_book_data_source"
        class_name = "BinanceAPIOrderBookDataSource"
        module_path = f"hummingbot.connector.exchange.binance.{module_name}"
        module = getattr(importlib.import_module(module_path), class_name)
        mid_price = module.get_mid_price(trading_pair)

    return mid_price
