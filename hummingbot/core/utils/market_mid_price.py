from typing import Optional
from decimal import Decimal
import importlib


def get_mid_price(exchange: str, trading_pair: str) -> Optional[Decimal]:
    from hummingbot.client.config.config_helpers import get_all_connectors

    mid_price = None
    all_connectors = get_all_connectors()
    for connector_type, connectors in all_connectors.items():
        if exchange in connectors:
            try:
                module_name = f"{exchange}_api_order_book_data_source"
                class_name = "".join([o.capitalize() for o in exchange.split("_")]) + "APIOrderBookDataSource"
                module_path = f"hummingbot.connector.{connector_type}.{exchange}.{module_name}"
                module = getattr(importlib.import_module(module_path), class_name)
                mid_price = module.get_mid_price(trading_pair)
            except Exception:
                pass
    if not mid_price:
        module_name = "binance_api_order_book_data_source"
        class_name = "BinanceAPIOrderBookDataSource"
        module_path = f"hummingbot.connector.exchange.binance.{module_name}"
        module = getattr(importlib.import_module(module_path), class_name)
        mid_price = module.get_mid_price(trading_pair)

    return mid_price
