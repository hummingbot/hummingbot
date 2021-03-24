
# TODO: Question: anyone planing to use this file? if not I will delete them in next PR

# #!/usr/bin/env python
# import sys
# import logging
# import conf
# import os
# import unittest
# from decimal import Decimal
#
# from os.path import join, realpath
# from eth_account import Account
#
#
# from hummingbot.connector.exchange.idex.idex_exchange import IdexExchange
# from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
#
# from hummingbot.connector.exchange.idex.idex_auth import IdexAuth
# from hummingbot.connector.exchange.idex.client.asyncio import AsyncIdexClient
# from hummingbot.core.event.events import OrderType, TradeType
# from hummingbot.connector.exchange.idex.utils import create_nonce
#
# API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
# API_KEY = os.getenv("IDEX_API_KEY") if API_MOCK_ENABLED else conf.idex_api_key
# API_SECRET = os.getenv("IDEX_API_SECRET") if API_MOCK_ENABLED else conf.idex_api_secret_key
#
#
# sys.path.insert(0, realpath(join(__file__, "../../../")))
#
#
# class IdexMarketUnitTest2(unittest.TestCase):
#
#     market: IdexExchange
#
#     async def get_tickers(self):
#         return markets.get_tickers(
#             market="DIL-ETH"
#         )
#
#     def test_get_tickers(self):
#       print("AAAAAAAAAAAAAAAAA")
#       markets = AsyncIdexClient().market;
#       # result = markets.get_tickers(
#       #     market="DIL-ETH"
#       # )
#       # print(f"BBBB: {result}")
#
#     def test_get_order_price_quantum(self):
#       order_price_quantum = self.market.get_order_price_quantum('DIL-ETH', '0.001')
#       self.assertEqual(order_price_quantum, Decimal(0.00000001))
#
#     def test_get_order_size_quantum(self):
#       order_size_quantum = self.market.get_order_size_quantum('DIL-ETH', '0.001')
#       self.assertEqual(order_size_quantum, Decimal(0.00000001))
#
#     def test_get_fee(self):
#         maker_buy_trade_fee: TradeFee = self.market.get_fee("ETH", "DIL", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal(1), Decimal(4000))
#         self.assertGreater(maker_buy_trade_fee.percent, 0)
#         self.assertEqual(len(maker_buy_trade_fee.flat_fees), 0)
#         taker_buy_trade_fee: TradeFee = self.market.get_fee("ETH", "DIL", OrderType.LIMIT, TradeType.BUY, Decimal(1))
#         self.assertGreater(taker_buy_trade_fee.percent, 0)
#         self.assertEqual(len(taker_buy_trade_fee.flat_fees), 0)
#         sell_trade_fee: TradeFee = self.market.get_fee("ETH", "DIL", OrderType.LIMIT, TradeType.SELL, Decimal(1), Decimal(4000))
#         self.assertGreater(sell_trade_fee.percent, 0)
#         self.assertEqual(len(sell_trade_fee.flat_fees), 0)
#         sell_trade_fee: TradeFee = self.market.get_fee("ETH", "DIL", OrderType.LIMIT_MAKER, TradeType.SELL, Decimal(1),
#                                                        Decimal(4000))
#         self.assertGreater(sell_trade_fee.percent, 0)
#         self.assertEqual(len(sell_trade_fee.flat_fees), 0)
#
#     def test_fee_overrides_config(self):
#         fee_overrides_config_map["idex_taker_fee"].value = None
#         taker_fee: TradeFee = self.market.get_fee("DIL", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
#                                                   Decimal('0.1'))
#         self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
#         fee_overrides_config_map["idex_taker_fee"].value = Decimal('0.2')
#         taker_fee: TradeFee = self.market.get_fee("DIL", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
#                                                   Decimal('0.1'))
#         self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
#         fee_overrides_config_map["idex_taker_fee"].value = None
#         maker_fee: TradeFee = self.market.get_fee("DIL", "ETH", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal(1),
#                                                   Decimal('0.1'))
#         self.assertAlmostEqual(Decimal("0.002"), maker_fee.percent)
#         fee_overrides_config_map["idex_taker_fee"].value = Decimal('0.5')
#         maker_fee: TradeFee = self.market.get_fee("DIL", "ETH", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal(1),
#                                                   Decimal('0.1'))
#         self.assertAlmostEqual(Decimal("0.005"), maker_fee.percent)
#
#     @classmethod
#     def setUpClass(cls):
#         cls.market: IdexExchange = IdexExchange(API_KEY, API_SECRET, ["DIL-ETH", "PIP-ETH", "CUR-ETH"], True)
#         print("Ready.")
#
#
#     def main():
#         logging.basicConfig(level=logging.INFO)
#         unittest.main()
#
#
# if __name__ == "__main__":
#     main()
