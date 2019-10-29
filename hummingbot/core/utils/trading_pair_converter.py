import aiohttp
import re
from typing import (
    List,
    Dict,
    Any,
)

from hummingbot.core.data_type.trading_pair import TradingPair


class TradingPairConverter:

    @staticmethod
    def convert_to_hummingbot_trading_pair(exchange_trading_pair: str, exchange_name: str) -> TradingPair:
        if exchange_name == "binance":
            return TradingPairConverter.convert_from_binance(exchange_trading_pair)
        elif exchange_name == "coinbase_pro":
            return TradingPairConverter.convert_from_coinbase_pro(exchange_trading_pair)
        elif exchange_name == "ddex":
            return TradingPairConverter.convert_from_ddex(exchange_trading_pair)
        elif exchange_name == "radar_relay" or exchange_name == "bamboo_relay":
            return TradingPairConverter.convert_from_radar_relay(exchange_trading_pair)
        elif exchange_name == "bittrex":
            return TradingPairConverter.convert_from_bittrex(exchange_trading_pair)
        elif exchange_name == "idex":
            return TradingPairConverter.convert_from_idex(exchange_trading_pair)
        elif exchange_name == "huobi":
            return TradingPairConverter.convert_from_huobi(exchange_trading_pair)
        else:
            raise ValueError(f"Unrecognized exchange: {exchange_name}")

    @staticmethod
    def convert_to_exchange_trading_pair(hb_trading_pair: str, exchange_name: str) -> str:
        if exchange_name == "binance":
            return TradingPairConverter.convert_to_binance(hb_trading_pair)
        elif exchange_name == "coinbase_pro":
            return TradingPairConverter.convert_to_coinbase_pro(hb_trading_pair)
        elif exchange_name == "ddex":
            return TradingPairConverter.convert_to_ddex(hb_trading_pair)
        elif exchange_name == "radar_relay" or exchange_name == "bamboo_relay":
            return TradingPairConverter.convert_to_radar_relay(hb_trading_pair)
        elif exchange_name == "bittrex":
            return TradingPairConverter.convert_to_bittrex(hb_trading_pair)
        elif exchange_name == "idex":
            return TradingPairConverter.convert_to_idex(hb_trading_pair)
        elif exchange_name == "huobi":
            return TradingPairConverter.convert_to_huobi(hb_trading_pair)
        else:
            raise ValueError(f"Unrecognized exchange: {exchange_name}")

    @staticmethod
    def convert_from_bittrex(exchange_trading_pair: str) -> TradingPair:
        # Bittrex uses QUOTE-BASE (USDT-BTC)
        quote_asset, base_asset = exchange_trading_pair.split("-")
        return TradingPair(exchange_trading_pair, base_asset, quote_asset)

    @staticmethod
    def convert_to_bittrex(hb_trading_pair: str) -> str:
        assets = hb_trading_pair.split("-")
        assets.reverse()
        return "-".join(assets)

