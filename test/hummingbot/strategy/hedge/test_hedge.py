import unittest
from decimal import Decimal
from test.mock.mock_perp_connector import MockPerpConnector

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.data_type.common import PositionMode, PositionSide
from hummingbot.strategy.hedge.hedge import HedgeStrategy
from hummingbot.strategy.hedge.hedge_config_map_pydantic import HedgeConfigMap
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


class HedgeConfigMapPydanticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def setUp(self) -> None:
        super().setUp()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.markets = {
            "kucoin": MockPaperExchange(client_config_map=self.client_config_map),
            "binance": MockPaperExchange(client_config_map=self.client_config_map),
            "binance_perpetual": MockPerpConnector(client_config_map=self.client_config_map),
        }
        base_asset = "BTC"
        quote_asset = "USDT"
        trading_pair = f"{base_asset}-{quote_asset}"
        perp_leverage = 25
        order_book_config = {
            "trading_pair": trading_pair,
            "mid_price": 100,
            "min_price": 1,
            "max_price": 200,
            "price_step_size": 1,
            "volume_step_size": 1,

        }
        self.markets["kucoin"].set_balance(base_asset, 1)
        self.markets["kucoin"].set_balanced_order_book(**order_book_config)
        self.markets["binance"].set_balance(base_asset, 0.5)
        self.markets["binance"].set_balanced_order_book(**order_book_config)
        self.markets["binance_perpetual"].set_balance(quote_asset, 100000)
        self.markets["binance_perpetual"].set_balanced_order_book(**order_book_config)
        self.markets["binance_perpetual"].set_leverage(trading_pair, perp_leverage)
        self.markets["binance_perpetual"].set_position_mode(PositionMode.ONEWAY)
        self.markets["binance_perpetual"]._account_positions[trading_pair] = Position(
            trading_pair,
            PositionSide.BOTH,
            Decimal("0"),
            Decimal("95"),
            Decimal("-1"),
            self.markets["binance_perpetual"].get_leverage(trading_pair)
        )
        self.market_trading_pairs = {
            "kucoin": MarketTradingPairTuple(
                self.markets["kucoin"],
                trading_pair,
                *trading_pair.split("-")
            ),
            "binance": MarketTradingPairTuple(
                self.markets["binance"],
                trading_pair,
                *trading_pair.split("-")
            ),
            "binance_perpetual": MarketTradingPairTuple(
                self.markets["binance_perpetual"],
                trading_pair,
                *trading_pair.split("-")
            ),
        }
        self.config_map = self.get_default_map()

    def get_default_map(self) -> HedgeConfigMap:
        config_settings = {
            'strategy': 'hedge',
            'value_mode': True,
            'hedge_ratio': 1.0,
            'hedge_interval': 60.0,
            'min_trade_size': 0.0,
            'slippage': 0.02,
            'hedge_offsets': [0],
            'hedge_leverage': 1,
            'hedge_position_mode': 'ONEWAY',
            "hedge_connector": 'binance_perpetual',
            "hedge_markets": 'BTC-USDT',
            "connector_0": 'n',
            "connector_1": 'n',
            "connector_2": 'n',
            "connector_3": 'n',
            "connector_4": 'n',
        }
        return HedgeConfigMap(**config_settings)

    def test_hedge_ratio(self):
        ...

    def test_offsets(self):
        offsets = {
            self.market_trading_pairs["kucoin"]: Decimal("0"),
            self.market_trading_pairs["binance"]: Decimal("0"),
            self.market_trading_pairs["binance_perpetual"]: Decimal("0"),
        }
        # value mode = True
        strategy = HedgeStrategy(
            config_map = self.config_map,
            hedge_market_pairs = [self.market_trading_pairs["binance_perpetual"]],
            market_pairs = [self.market_trading_pairs["kucoin"], self.market_trading_pairs["binance"]],
            offsets = offsets,
        )

        self.assertEqual(strategy._offsets, offsets)
        is_buy, value = strategy.get_hedge_direction_and_value()

        self.assertEqual(is_buy, False)
        self.assertEqual(value, Decimal("150"))
        strategy._offsets[self.market_trading_pairs["kucoin"]] = Decimal("1")
        is_buy, value = strategy.get_hedge_direction_and_value()
        self.assertEqual(is_buy, False)
        self.assertEqual(value, Decimal("250"))
        strategy._offsets[self.market_trading_pairs["kucoin"]] = Decimal("-1")
        is_buy, value = strategy.get_hedge_direction_and_value()
        self.assertEqual(is_buy, False)
        self.assertEqual(value, Decimal("50"))
        # value mode = False
        self.config_map.value_mode = False
        strategy = HedgeStrategy(
            config_map = self.config_map,
            hedge_market_pairs = [self.market_trading_pairs["binance_perpetual"]],
            market_pairs = [self.market_trading_pairs["kucoin"], self.market_trading_pairs["binance"]],
            offsets = offsets,
        )
        for hedge_market, market_list in strategy._market_pair_by_asset.items():
            is_buy, amount_to_hedge = strategy.get_hedge_direction_and_amount_by_asset(hedge_market, market_list)
            self.assertEqual(is_buy, False)
            self.assertEqual(amount_to_hedge, Decimal("0.5"))
        strategy._offsets[self.market_trading_pairs["kucoin"]] = Decimal("1")
        for hedge_market, market_list in strategy._market_pair_by_asset.items():
            is_buy, amount_to_hedge = strategy.get_hedge_direction_and_amount_by_asset(hedge_market, market_list)
            self.assertEqual(is_buy, False)
            self.assertEqual(amount_to_hedge, Decimal("2.5"))

    # def test_hedge_by_value(self):
    #     ...

    # def test_hedge_by_amount(self):
    #     ...
