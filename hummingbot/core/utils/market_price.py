from typing import Optional, Dict
from decimal import Decimal
import importlib
from hummingbot.client.settings import AllConnectorSettings, ConnectorType
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource


async def get_binance_mid_price(trading_pair: str) -> Dict[str, Decimal]:
    # Binance is the place to go to for pricing atm
    prices = await BinanceAPIOrderBookDataSource.get_all_mid_prices()
    return prices.get(trading_pair, None)


async def get_last_price(exchange: str, trading_pair: str) -> Optional[Decimal]:
    if exchange in AllConnectorSettings.get_connector_settings():
        conn_setting = AllConnectorSettings.get_connector_settings()[exchange]
        if AllConnectorSettings.get_connector_settings()[exchange].type in (ConnectorType.Exchange, ConnectorType.Derivative):
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
