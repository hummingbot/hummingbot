from typing import Optional, Dict
from decimal import Decimal
import importlib
from hummingbot.client.settings import ALL_CONNECTORS, CONNECTOR_SETTINGS, ConnectorType
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.connector.exchange.binance.binance_utils import USD_QUOTES


def usd_value(token: str, amount: Decimal) -> Optional[Decimal]:
    pass


async def token_usd_values() -> Dict[str, Decimal]:
    prices = await BinanceAPIOrderBookDataSource.get_all_mid_prices()
    tokens = {t.split("-")[0] for t in prices}
    ret_val = {}
    for token in tokens:
        token_usds = [t for t in prices if t.split("-")[0] == token and t.split("-")[1] in USD_QUOTES]
        if token_usds:
            ret_val[token] = prices[token_usds[0]]
        else:
            token_anys = [t for t in prices if t.split("-")[0] == token]
            quote = token_anys[0].split("-")[1]
            quote_usds = [t for t in prices if t.split("-")[0] == quote and t.split("-")[1] in USD_QUOTES]
            if quote_usds:
                price = prices[token_anys[0]] * prices[quote_usds[0]]
                ret_val[token] = price
    return ret_val


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
