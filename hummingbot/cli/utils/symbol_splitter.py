import re
from typing import Tuple


BINANCE_SYMBOL_SPLITTER = re.compile(r"^(\w+)(BTC|ETH|BNB|XRP|USDT|USDS|USDC|TUSD|PAX)$")


class SymbolSplitter:
    def __init__(self, market: str, symbol: str):
        self._symbol: Tuple[str, str] = self.split(market, symbol)

    @property
    def base_asset(self):
        return self._symbol[0]

    @property
    def quote_asset(self):
        return self._symbol[1]

    @staticmethod
    def split(market, symbol) -> Tuple[str, str]:
        """
        Takes an exchange pair and return
        :param market: lowercase market e.g. binance
        :param symbol: uppercase exchange pair e.g. ETHUSDT
        :return: tuple: (base_asset, quote_asset)
        """
        try:
            if market == "binance":
                m = BINANCE_SYMBOL_SPLITTER.match(symbol)
                result: Tuple = (m.group(1), m.group(2))
            elif market in ["ddex", "radar_relay", "bamboo_relay", "coinbase_pro"]:
                result: Tuple = tuple(symbol.split('-'))
            else:
                raise ValueError("Market %s not supported" % (market,))
        except Exception:
            raise ValueError("Error parsing %s symbol. Symbol %s is not a valid %s symbol" % (market, symbol, market))

        if len(result) != 2:
            raise ValueError("Symbol %s does not match %s's format" % (symbol, market))

        return result


