import unittest

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange import CoinbaseAdvancedTradeExchange
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_exchange_protocols import (
    CoinbaseAdvancedTradeAccountsMixinProtocol,
    CoinbaseAdvancedTradeAPICallsMixinProtocol,
    CoinbaseAdvancedTradeTradingPairsMixinProtocol,
    CoinbaseAdvancedTradeUtilitiesMixinProtocol,
    CoinbaseAdvancedTradeWebsocketMixinProtocol,
)


def conforms_to_protocol(obj, protocol):
    for attr in dir(protocol):
        if attr.startswith('__') and attr.endswith('__'):  # Ignore magic methods
            continue
        if attr == "_is_protocol" or attr == "_is_runtime_protocol":  # Ignore _is_protocol attribute
            continue
        if not hasattr(obj, attr):
            return False
        if callable(getattr(protocol, attr)) and not callable(getattr(obj, attr)):
            print(protocol, attr)
            return False
    return True


class TestExchangeProtocols(unittest.TestCase):
    def test_conforms_to_protocol(self):
        self.assertTrue(isinstance(CoinbaseAdvancedTradeExchange, CoinbaseAdvancedTradeUtilitiesMixinProtocol))
        self.assertTrue(isinstance(CoinbaseAdvancedTradeExchange, CoinbaseAdvancedTradeAPICallsMixinProtocol))
        self.assertTrue(isinstance(CoinbaseAdvancedTradeExchange, CoinbaseAdvancedTradeTradingPairsMixinProtocol))
        self.assertTrue(isinstance(CoinbaseAdvancedTradeExchange, CoinbaseAdvancedTradeAccountsMixinProtocol))
        self.assertTrue(isinstance(CoinbaseAdvancedTradeExchange, CoinbaseAdvancedTradeWebsocketMixinProtocol))

        self.assertTrue(conforms_to_protocol(CoinbaseAdvancedTradeExchange, CoinbaseAdvancedTradeUtilitiesMixinProtocol))
        self.assertTrue(conforms_to_protocol(CoinbaseAdvancedTradeExchange, CoinbaseAdvancedTradeAPICallsMixinProtocol))
        self.assertTrue(conforms_to_protocol(CoinbaseAdvancedTradeExchange, CoinbaseAdvancedTradeTradingPairsMixinProtocol))
        self.assertTrue(conforms_to_protocol(CoinbaseAdvancedTradeExchange, CoinbaseAdvancedTradeAccountsMixinProtocol))
        self.assertTrue(conforms_to_protocol(CoinbaseAdvancedTradeExchange, CoinbaseAdvancedTradeWebsocketMixinProtocol))


if __name__ == "__main__":
    unittest.main()
