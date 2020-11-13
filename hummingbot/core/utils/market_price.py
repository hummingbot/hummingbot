from typing import Optional
from decimal import Decimal
import importlib
from hummingbot.client.settings import ALL_CONNECTORS, CONNECTOR_SETTINGS, ConnectorType


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


async def get_last_price(exchange: str, trading_pair: str) -> Optional[Decimal]:
    if exchange in CONNECTOR_SETTINGS:
        conn_setting = CONNECTOR_SETTINGS[exchange]
        if CONNECTOR_SETTINGS[exchange].type in (ConnectorType.Exchange, ConnectorType.Derivative):
            module_name = f"{conn_setting.base_name()}_api_order_book_data_source"
            class_name = "".join([o.capitalize() for o in conn_setting.base_name().split("_")]) + \
                         "APIOrderBookDataSource"
            module_path = f"hummingbot.connector.{conn_setting.type.name.lower()}." \
                          f"{conn_setting.base_name()}.{module_name}"
            module = getattr(importlib.import_module(module_path), class_name)
            args = {"trading_pairs": [trading_pair]}
            if conn_setting.is_sub_domain:
                args["domain"] = conn_setting.domain_parameter
            last_prices = await module.get_last_traded_prices(**args)
            if last_prices:
                return Decimal(str(last_prices[trading_pair]))
