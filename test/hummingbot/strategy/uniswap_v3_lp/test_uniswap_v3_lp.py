"""
Unit tests for hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp
"""

from decimal import Decimal
import pandas as pd
import numpy as np
from typing import Dict, List
import unittest.mock
import asyncio

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp import UniswapV3LpStrategy
from hummingbot.connector.connector.uniswap_v3.uniswap_v3_in_flight_position import UniswapV3InFlightPosition
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from test.mock.mock_paper_exchange import MockPaperExchange


class ExtendedMockPaperExchange(MockPaperExchange):
    def __init__(self):
        super().__init__()
        self._trading_pairs = ["ETH-USDT"]
        np.random.seed(123456789)
        self._in_flight_positions = {}
        self._in_flight_orders = {}

    async def get_price_by_fee_tier(self, trading_pair: str, tier: str, seconds: int = 1, twap: bool = False):
        if twap:
            original_price = 100
            volatility = 0.1
            return np.random.normal(original_price, volatility, 3599)
        else:
            return Decimal("100")

    def add_position(self,
                     trading_pair: str,
                     fee_tier: str,
                     base_amount: Decimal,
                     quote_amount: Decimal,
                     lower_price: Decimal,
                     upper_price: Decimal,
                     token_id: int = 0):
        self._in_flight_positions["pos1"] = UniswapV3InFlightPosition(hb_id="pos1",
                                                                      token_id=token_id,
                                                                      trading_pair=trading_pair,
                                                                      fee_tier=fee_tier,
                                                                      base_amount=base_amount,
                                                                      quote_amount=quote_amount,
                                                                      lower_price=lower_price,
                                                                      upper_price=upper_price)

    async def _remove_position(self, hb_id: str, token_id: str = "1", reducePercent: Decimal = Decimal("100.0"), fee_estimate: bool = False):
        return self.remove_position(hb_id, token_id, reducePercent, fee_estimate)

    def remove_position(self, hb_id: str, token_id: str = "1", reducePercent: Decimal = Decimal("100.0"), fee_estimate: bool = False):
        if fee_estimate:
            return Decimal("0")
        else:
            self._in_flight_positions.pop(hb_id)


class UniswapV3LpStrategyTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    market_infos: Dict[str, MarketTradingPairTuple] = {}

    @staticmethod
    def create_market(trading_pairs: List[str], mid_price, balances: Dict[str, int]) -> (MockPaperExchange, Dict[str, MarketTradingPairTuple]):
        """
        Create a BacktestMarket and marketinfo dictionary to be used by the liquidity mining strategy
        """
        market: ExtendedMockPaperExchange = ExtendedMockPaperExchange()
        market_infos: Dict[str, MarketTradingPairTuple] = {}

        for trading_pair in trading_pairs:
            base_asset = trading_pair.split("-")[0]
            quote_asset = trading_pair.split("-")[1]

            market.set_balanced_order_book(trading_pair=trading_pair,
                                           mid_price=mid_price,
                                           min_price=1,
                                           max_price=200,
                                           price_step_size=1,
                                           volume_step_size=10)
            market.set_quantization_param(QuantizationParams(trading_pair, 6, 6, 6, 6))
            market_infos[trading_pair] = MarketTradingPairTuple(market, trading_pair, base_asset, quote_asset)

        for asset, value in balances.items():
            market.set_balance(asset, value)

        return market, market_infos

    def setUp(self) -> None:
        self.loop = asyncio.get_event_loop()
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)

        self.mid_price = 100
        self.bid_spread = 0.01
        self.ask_spread = 0.01
        self.order_refresh_time = 1

        trading_pairs = list(map(lambda quote_asset: "ETH-" + quote_asset, ["USDT", "BTC"]))
        market, market_infos = self.create_market(trading_pairs, self.mid_price, {"USDT": 5000, "ETH": 500, "BTC": 100})
        self.market = market
        self.market_infos = market_infos

        self.default_strategy = UniswapV3LpStrategy(
            self.market_infos[trading_pairs[0]],
            "MEDIUM",
            True,
            Decimal('144'),
            Decimal('2'),
            Decimal('0.01'),
            Decimal('0.01'),
            Decimal('1'),
            Decimal('1'),
            Decimal('0.05')
        )

    def test_generate_proposal_with_volatility_above_zero(self):
        """
        Test generate proposal function works correctly when volatility is above zero
        """

        orders = self.loop.run_until_complete(self.default_strategy.propose_position_creation())
        self.assertEqual(orders[0][0], Decimal("0"))
        self.assertEqual(orders[0][1], Decimal("100"))
        self.assertEqual(orders[1][0], Decimal("100"))
        self.assertAlmostEqual(orders[1][1], Decimal("305.35"), 1)

    def test_generate_proposal_with_volatility_equal_zero(self):
        """
        Test generate proposal function works correctly when volatility is zero
        """

        for x in range(3600):
            self.default_strategy._volatility.add_sample(100)
        orders = self.loop.run_until_complete(self.default_strategy.propose_position_creation())
        self.assertEqual(orders[0][0], Decimal("99"))
        self.assertEqual(orders[0][1], Decimal("100"))
        self.assertEqual(orders[1][0], Decimal("100"))
        self.assertEqual(orders[1][1], Decimal("101"))

    def test_generate_proposal_without_volatility(self):
        """
        Test generate proposal function works correctly using user set spreads
        """

        self.default_strategy._use_volatility = False
        orders = self.loop.run_until_complete(self.default_strategy.propose_position_creation())
        self.assertEqual(orders[0][0], Decimal("99"))
        self.assertEqual(orders[0][1], Decimal("100"))
        self.assertEqual(orders[1][0], Decimal("100"))
        self.assertEqual(orders[1][1], Decimal("101"))

    def test_profitability_calculation(self):
        """
        Test profitability calculation function works correctly
        """

        pos = UniswapV3InFlightPosition(hb_id="pos1",
                                        token_id=1,
                                        trading_pair="HBOT-USDT",
                                        fee_tier="MEDIUM",
                                        base_amount=Decimal("0"),
                                        quote_amount=Decimal("100"),
                                        lower_price=Decimal("100"),
                                        upper_price=Decimal("101"))
        pos.current_base_amount = Decimal("1")
        pos.current_quote_amount = Decimal("0")
        pos.unclaimed_base_amount = Decimal("1")
        pos.unclaimed_quote_amount = Decimal("10")
        pos.gas_price = Decimal("5")
        self.default_strategy._last_price = Decimal("100")
        result = self.loop.run_until_complete(self.default_strategy.calculate_profitability(pos))
        self.assertEqual(result["profitability"], (Decimal("110") - result["tx_fee"]) / Decimal("100"))

    def test_position_creation(self):
        """
        Test that positions are created properly.
        """
        self.assertEqual(len(self.default_strategy._market_info.market._in_flight_positions), 0)
        self.default_strategy.execute_proposal([[95, 100], []])
        self.assertEqual(len(self.default_strategy._market_info.market._in_flight_positions), 1)

    def test_range_calculation(self):
        """
        Test that the overall range of all positions cover are calculated correctly.
        """
        self.default_strategy._market_info.market._in_flight_positions["pos1"] = UniswapV3InFlightPosition(hb_id="pos1",
                                                                                                           token_id=1,
                                                                                                           trading_pair="ETH-USDT",
                                                                                                           fee_tier="MEDIUM",
                                                                                                           base_amount=Decimal("0"),
                                                                                                           quote_amount=Decimal("100"),
                                                                                                           lower_price=Decimal("90"),
                                                                                                           upper_price=Decimal("95"))
        self.default_strategy._market_info.market._in_flight_positions["pos2"] = UniswapV3InFlightPosition(hb_id="pos2",
                                                                                                           token_id=2,
                                                                                                           trading_pair="ETH-USDT",
                                                                                                           fee_tier="MEDIUM",
                                                                                                           base_amount=Decimal("0"),
                                                                                                           quote_amount=Decimal("100"),
                                                                                                           lower_price=Decimal("95"),
                                                                                                           upper_price=Decimal("100"))
        self.default_strategy._market_info.market._in_flight_positions["pos3"] = UniswapV3InFlightPosition(hb_id="pos3",
                                                                                                           token_id=3,
                                                                                                           trading_pair="ETH-USDT",
                                                                                                           fee_tier="MEDIUM",
                                                                                                           base_amount=Decimal("0"),
                                                                                                           quote_amount=Decimal("100"),
                                                                                                           lower_price=Decimal("100"),
                                                                                                           upper_price=Decimal("105"))
        self.default_strategy._market_info.market._in_flight_positions["pos4"] = UniswapV3InFlightPosition(hb_id="pos4",
                                                                                                           token_id=4,
                                                                                                           trading_pair="ETH-USDT",
                                                                                                           fee_tier="MEDIUM",
                                                                                                           base_amount=Decimal("0"),
                                                                                                           quote_amount=Decimal("100"),
                                                                                                           lower_price=Decimal("105"),
                                                                                                           upper_price=Decimal("110"))
        self.assertEqual(len(self.default_strategy._market_info.market._in_flight_positions), 4)
        lower_bound, upper_bound = self.default_strategy.total_position_range()
        self.assertEqual(lower_bound, Decimal("90"))
        self.assertEqual(upper_bound, Decimal("110"))
