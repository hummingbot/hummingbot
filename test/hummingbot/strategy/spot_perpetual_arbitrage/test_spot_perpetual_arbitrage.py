from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

from decimal import Decimal
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
import unittest
import asyncio

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderType
)
from hummingbot.strategy.spot_perpetual_arbitrage.spot_perpetual_arbitrage import (
    SpotPerpetualArbitrageStrategy,
    StrategyState,
)
from hummingbot.strategy.spot_perpetual_arbitrage.arb_proposal import ArbProposal, ArbProposalSide
from hummingbot.connector.derivative.position import Position
from hummingbot.core.event.events import PositionMode, PositionSide
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from test.mock.mock_perp_connector import MockPerpConnector
from test.mock.mock_paper_exchange import MockPaperExchange

trading_pair = "HBOT-USDT"
base_asset = trading_pair.split("-")[0]
quote_asset = trading_pair.split("-")[1]


class TestSpotPerpetualArbitrage(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    level = 0
    log_records = []

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and message in record.getMessage()
                   for record in self.log_records)

    def setUp(self):
        self.log_records = []
        self.order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1, self.start_timestamp, self.end_timestamp)
        self.spot_connector: MockPaperExchange = MockPaperExchange()
        self.spot_connector.set_balanced_order_book(trading_pair=trading_pair,
                                                    mid_price=100,
                                                    min_price=1,
                                                    max_price=200,
                                                    price_step_size=1,
                                                    volume_step_size=10)
        self.spot_connector.set_balance(base_asset, 5)
        self.spot_connector.set_balance(quote_asset, 500)
        self.spot_connector.set_quantization_param(
            QuantizationParams(
                trading_pair, 6, 6, 6, 6
            )
        )
        self.spot_market_info = MarketTradingPairTuple(self.spot_connector, trading_pair,
                                                       base_asset, quote_asset)

        self.perp_connector: MockPerpConnector = MockPerpConnector()
        self.perp_connector.set_leverage(trading_pair, 5)
        self.perp_connector.set_balanced_order_book(trading_pair=trading_pair,
                                                    mid_price=110,
                                                    min_price=1,
                                                    max_price=200,
                                                    price_step_size=1,
                                                    volume_step_size=10)
        self.perp_connector.set_balance(base_asset, 5)
        self.perp_connector.set_balance(quote_asset, 500)
        self.perp_connector.set_quantization_param(
            QuantizationParams(
                trading_pair, 6, 6, 6, 6
            )
        )
        self.perp_market_info = MarketTradingPairTuple(self.perp_connector, trading_pair,
                                                       base_asset, quote_asset)

        self.clock.add_iterator(self.spot_connector)
        self.clock.add_iterator(self.perp_connector)

        self.spot_connector.add_listener(MarketEvent.OrderFilled, self.order_fill_logger)
        self.spot_connector.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)
        self.perp_connector.add_listener(MarketEvent.OrderFilled, self.order_fill_logger)
        self.perp_connector.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

        self.strategy = SpotPerpetualArbitrageStrategy()
        self.strategy.init_params(
            spot_market_info=self.spot_market_info,
            perp_market_info=self.perp_market_info,
            order_amount=Decimal("1"),
            perp_leverage=5,
            min_opening_arbitrage_pct=Decimal("0.05"),
            min_closing_arbitrage_pct=Decimal("0.01"),
            next_arbitrage_opening_delay=10,
        )
        self.strategy.logger().setLevel(1)
        self.strategy.logger().addHandler(self)
        self._last_tick = 0

    def test_strategy_starts_with_unsupported_position_mode(self):
        self.clock.add_iterator(self.strategy)
        self.perp_connector.set_position_mode(PositionMode.HEDGE)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertTrue(self._is_logged("INFO", "Markets are ready."))
        self.assertTrue(self._is_logged("INFO", "Trading started."))
        self.assertTrue(self._is_logged("INFO", "This strategy supports only Oneway position mode. Please update your "
                                                "position mode before starting this strategy."))
        # assert the strategy stopped here
        # self.assertIsNone(self.strategy.clock)

    def test_strategy_starts_with_multiple_active_position(self):
        # arbitrary adding multiple actuve positions here, which should never happen in real trading on oneway mode
        self.perp_connector._account_positions[trading_pair + "SHORT"] = Position(
            trading_pair,
            PositionSide.SHORT,
            Decimal("0"),
            Decimal("95"),
            Decimal("-1"),
            self.perp_connector.get_leverage(trading_pair)
        )
        self.perp_connector._account_positions[trading_pair + "LONG"] = Position(
            trading_pair,
            PositionSide.LONG,
            Decimal("0"),
            Decimal("95"),
            Decimal("1"),
            self.perp_connector.get_leverage(trading_pair)
        )
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertTrue(self._is_logged("INFO", "Markets are ready."))
        self.assertTrue(self._is_logged("INFO", "Trading started."))
        self.assertTrue(self._is_logged("INFO", "This strategy supports only Oneway position mode. Please update your "
                                                "position mode before starting this strategy."))
        # self.assertIsNone(self.strategy.clock)

    def test_strategy_starts_with_existing_position(self):
        """
        Tests if the strategy can start
        """

        self.clock.add_iterator(self.strategy)
        self.perp_connector._account_positions[trading_pair] = Position(
            trading_pair,
            PositionSide.SHORT,
            Decimal("0"),
            Decimal("95"),
            Decimal("-1"),
            self.perp_connector.get_leverage(trading_pair)
        )
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertTrue(self._is_logged("INFO", "Markets are ready."))
        self.assertTrue(self._is_logged("INFO", "Trading started."))
        self.assertTrue(self._is_logged("INFO", f"There is an existing {trading_pair} "
                                                f"{PositionSide.SHORT.name} position. The bot resumes "
                                                f"operation to close out the arbitrage position"))
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))
        self.clock.backtest_til(self.start_timestamp + 2)

    def test_strategy_starts_with_existing_position_unmatched_pos_amount(self):
        """
        Tests if the strategy start then stop when there is an existing position where position amount doesn't match
        strategy order amount
        """
        self.clock.add_iterator(self.strategy)
        self.perp_connector._account_positions[trading_pair] = Position(
            trading_pair,
            PositionSide.SHORT,
            Decimal("0"),
            Decimal("95"),
            Decimal("-10"),
            self.perp_connector.get_leverage(trading_pair)
        )
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertTrue(self._is_logged("INFO", "Markets are ready."))
        self.assertTrue(self._is_logged("INFO", "Trading started."))
        self.assertTrue(self._is_logged("INFO", f"There is an existing {trading_pair} "
                                                f"{PositionSide.SHORT.name} position with unmatched position amount. "
                                                f"Please manually close out the position before starting this "
                                                f"strategy."))
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))
        self.clock.backtest_til(self.start_timestamp + 2)
        # assert the strategy stopped here
        self.assertIsNone(self.strategy.clock)

    def test_create_base_proposals(self):
        asyncio.get_event_loop().run_until_complete(self._test_create_base_proposals())

    async def _test_create_base_proposals(self):
        self.clock.add_iterator(self.strategy)
        props = await self.strategy.create_base_proposals()
        self.assertEqual(2, len(props))
        self.assertEqual(True, props[0].spot_side.is_buy)
        self.assertEqual(Decimal("100.5"), props[0].spot_side.order_price)
        self.assertEqual(False, props[0].perp_side.is_buy)
        self.assertEqual(Decimal("109.5"), props[0].perp_side.order_price)
        self.assertEqual(Decimal("1"), props[0].order_amount)

        self.assertEqual(False, props[1].spot_side.is_buy)
        self.assertEqual(Decimal("99.5"), props[1].spot_side.order_price)
        self.assertEqual(True, props[1].perp_side.is_buy)
        self.assertEqual(Decimal("110.5"), props[1].perp_side.order_price)
        self.assertEqual(Decimal("1"), props[1].order_amount)

    def test_apply_slippage_buffers(self):
        proposal = ArbProposal(ArbProposalSide(self.spot_market_info, True, Decimal("100")),
                               ArbProposalSide(self.perp_market_info, False, Decimal("100")),
                               Decimal("1"))
        self.strategy._spot_market_slippage_buffer = Decimal("0.01")
        self.strategy._perp_market_slippage_buffer = Decimal("0.02")
        self.strategy.apply_slippage_buffers(proposal)
        self.assertEqual(Decimal("101"), proposal.spot_side.order_price)
        self.assertEqual(Decimal("98"), proposal.perp_side.order_price)

    def test_check_budget_available(self):
        self.spot_connector.set_balance(base_asset, 0)
        self.spot_connector.set_balance(quote_asset, 0)
        self.perp_connector.set_balance(base_asset, 0)
        self.perp_connector.set_balance(quote_asset, 10)
        # Since spot has 0 HBOT and 0 USDT, not enough to do any trade
        self.assertFalse(self.strategy.check_budget_available())

        self.spot_connector.set_balance(base_asset, 10)
        self.spot_connector.set_balance(quote_asset, 10)
        self.perp_connector.set_balance(base_asset, 10)
        self.perp_connector.set_balance(quote_asset, 0)
        # Since perp has 0, not enough to do any trade
        self.assertFalse(self.strategy.check_budget_available())

        self.spot_connector.set_balance(base_asset, 10)
        self.spot_connector.set_balance(quote_asset, 10)
        self.perp_connector.set_balance(base_asset, 10)
        self.perp_connector.set_balance(quote_asset, 10)
        # All assets are available
        self.assertTrue(self.strategy.check_budget_available())

    def test_check_budget_constraint(self):
        proposal = ArbProposal(ArbProposalSide(self.spot_market_info, False, Decimal("100")),
                               ArbProposalSide(self.perp_market_info, True, Decimal("100")),
                               Decimal("1"))
        self.spot_connector.set_balance(base_asset, 0.5)
        self.spot_connector.set_balance(quote_asset, 0)
        self.perp_connector.set_balance(base_asset, 0)
        self.perp_connector.set_balance(quote_asset, 21)
        # Since spot has 0.5 HBOT, not enough to sell on 1 order amount
        self.assertFalse(self.strategy.check_budget_constraint(proposal))

        self.spot_connector.set_balance(base_asset, 1)
        self.assertTrue(self.strategy.check_budget_constraint(proposal))

        # on perpetual you need at least 100/5 to open a position
        self.perp_connector.set_balance(quote_asset, 10)
        self.assertFalse(self.strategy.check_budget_constraint(proposal))

        # There is no balance required to close a position
        self.perp_connector._account_positions[trading_pair] = Position(
            trading_pair,
            PositionSide.SHORT,
            Decimal("0"),
            Decimal("95"),
            Decimal("-1"),
            self.perp_connector.get_leverage(trading_pair)
        )
        self.assertTrue(self.strategy.check_budget_constraint(proposal))

    def test_no_arbitrage_opportunity(self):
        self.perp_connector.set_balanced_order_book(trading_pair=trading_pair,
                                                    mid_price=100,
                                                    min_price=1,
                                                    max_price=200,
                                                    price_step_size=1,
                                                    volume_step_size=10)
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))
        taker_orders = self.strategy.tracked_limit_orders + self.strategy.tracked_market_orders
        self.assertTrue(len(taker_orders) == 0)

    def test_arbitrage_buy_spot_sell_perp(self):
        self.clock.add_iterator(self.strategy)
        self.assertEqual(StrategyState.Closed, self.strategy.strategy_state)
        self.turn_clock(1)
        # self.clock.backtest_til(self.start_timestamp + 1)
        # asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))
        self.assertTrue(self._is_logged("INFO", "Arbitrage position opening opportunity found."))
        self.assertTrue(self._is_logged("INFO", "Profitability (8.96%) is now above min_opening_arbitrage_pct."))
        self.assertTrue(self._is_logged("INFO", "Placing BUY order for 1 HBOT at MockPaperExchange at 100.500 price"))
        self.assertTrue(self._is_logged("INFO", "Placing SELL order for 1 HBOT at MockPerpConnector at 109.500 price "
                                                "to OPEN position."))
        placed_orders = self.strategy.tracked_market_orders
        self.assertEqual(2, len(placed_orders))
        spot_order = [order for market, order in placed_orders if market == self.spot_connector][0]
        self.assertTrue(spot_order.is_buy)
        self.assertEqual(Decimal("1"), Decimal(str(spot_order.amount)))
        perp_order = [order for market, order in placed_orders if market == self.perp_connector][0]
        self.assertFalse(perp_order.is_buy)
        self.assertEqual(Decimal("1"), Decimal(str(perp_order.amount)))
        self.assertEqual(StrategyState.Opening, self.strategy.strategy_state)

        self.trigger_order_complete(True, self.spot_connector, Decimal("1"), Decimal("100.5"), spot_order.order_id)
        self.trigger_order_complete(False, self.perp_connector, Decimal("1"), Decimal("109.5"), perp_order.order_id)
        self.perp_connector._account_positions[trading_pair] = Position(
            trading_pair,
            PositionSide.SHORT,
            Decimal("0"),
            Decimal("109.5"),
            Decimal("-1"),
            self.perp_connector.get_leverage(trading_pair)
        )
        self.turn_clock(1)
        status = asyncio.get_event_loop().run_until_complete(self.strategy.format_status())
        expected_status = ("""
  Markets:
             Exchange    Market  Sell Price  Buy Price  Mid Price
    MockPaperExchange HBOT-USDT        99.5      100.5        100
    MockPerpConnector HBOT-USDT       109.5      110.5        110

  Positions:
       Symbol  Type Entry Price Amount  Leverage Unrealized PnL
    HBOT-USDT SHORT       109.5     -1         5              0

  Assets:
                Exchange Asset  Total Balance  Available Balance
    0  MockPaperExchange  HBOT              5                  5
    1  MockPaperExchange  USDT            500                500
    2  MockPerpConnector  HBOT              5                  5
    3  MockPerpConnector  USDT            500                500

  Opportunity:
    buy at MockPaperExchange, sell at MockPerpConnector: 8.96%
    sell at MockPaperExchange, buy at MockPerpConnector: -9.95%""")

        self.assertEqual(expected_status, status)

        self.assertEqual(StrategyState.Opened, self.strategy.strategy_state)
        self.perp_connector.set_balanced_order_book(trading_pair=trading_pair,
                                                    mid_price=90,
                                                    min_price=1,
                                                    max_price=200,
                                                    price_step_size=1,
                                                    volume_step_size=10)
        self.turn_clock(1)
        placed_orders = self.strategy.tracked_market_orders
        self.assertEqual(4, len(placed_orders))
        spot_order = [o for m, o in placed_orders if m == self.spot_connector and o.order_id != spot_order.order_id][0]
        self.assertFalse(spot_order.is_buy)
        self.assertEqual(Decimal("1"), Decimal(str(spot_order.amount)))
        perp_order = [o for m, o in placed_orders if m == self.perp_connector and o.order_id != perp_order.order_id][0]
        self.assertTrue(perp_order.is_buy)
        self.assertEqual(Decimal("1"), Decimal(str(perp_order.amount)))
        self.assertEqual(StrategyState.Closing, self.strategy.strategy_state)

        self.trigger_order_complete(False, self.spot_connector, Decimal("1"), Decimal("99.5"), spot_order.order_id)
        self.trigger_order_complete(True, self.perp_connector, Decimal("1"), Decimal("90.5"), perp_order.order_id)
        self.perp_connector._account_positions.clear()
        self.turn_clock(1)
        # Due to the next_arbitrage_opening_delay, new arb position is not opened yet
        self.assertEqual(StrategyState.Closed, self.strategy.strategy_state)
        # Set balance on perpetual to 0 to test the strategy shouldn't submit orders
        self.spot_connector.set_balance(base_asset, 0)
        self.turn_clock(12)
        self.assertEqual(StrategyState.Closed, self.strategy.strategy_state)
        self.assertEqual(4, len(self.strategy.tracked_market_orders))

        self.spot_connector.set_balance(base_asset, 10)
        self.turn_clock(1)
        # After next_arbitrage_opening_delay, new arb orders are submitted
        self.assertEqual(StrategyState.Opening, self.strategy.strategy_state)
        self.assertEqual(6, len(self.strategy.tracked_market_orders))

    def test_arbitrage_sell_spot_buy_perp_opening(self):
        self.perp_connector.set_balanced_order_book(trading_pair=trading_pair,
                                                    mid_price=90,
                                                    min_price=1,
                                                    max_price=200,
                                                    price_step_size=1,
                                                    volume_step_size=10)
        self.clock.add_iterator(self.strategy)
        self.assertEqual(StrategyState.Closed, self.strategy.strategy_state)
        self.turn_clock(1)
        # self.clock.backtest_til(self.start_timestamp + 1)
        # asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))
        self.assertTrue(self._is_logged("INFO", "Arbitrage position opening opportunity found."))
        self.assertTrue(self._is_logged("INFO", "Profitability (9.94%) is now above min_opening_arbitrage_pct."))
        self.assertTrue(self._is_logged("INFO", "Placing SELL order for 1 HBOT at MockPaperExchange at 99.5000 price"))
        self.assertTrue(self._is_logged("INFO", "Placing BUY order for 1 HBOT at MockPerpConnector at 90.5000 price to "
                                                "OPEN position."))
        placed_orders = self.strategy.tracked_market_orders
        self.assertEqual(2, len(placed_orders))
        spot_order = [order for market, order in placed_orders if market == self.spot_connector][0]
        self.assertFalse(spot_order.is_buy)
        self.assertEqual(Decimal("1"), Decimal(str(spot_order.amount)))
        perp_order = [order for market, order in placed_orders if market == self.perp_connector][0]
        self.assertTrue(perp_order.is_buy)
        self.assertEqual(Decimal("1"), Decimal(str(perp_order.amount)))
        self.assertEqual(StrategyState.Opening, self.strategy.strategy_state)

    def turn_clock(self, no_ticks: int):
        for i in range(self._last_tick, self._last_tick + no_ticks + 1):
            self.clock.backtest_til(self.start_timestamp + i)
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))
        self._last_tick += no_ticks

    @staticmethod
    def trigger_order_complete(is_buy: bool, connector: ConnectorBase, amount: Decimal, price: Decimal,
                               order_id: str):
        # This function triggers order complete event for our mock connector, this is to simulate scenarios more
        # precisely taker orders are fully filled.
        event_tag = MarketEvent.BuyOrderCompleted if is_buy else MarketEvent.SellOrderCompleted
        event_class = BuyOrderCompletedEvent if is_buy else SellOrderCompletedEvent
        connector.trigger_event(event_tag,
                                event_class(connector.current_timestamp, order_id, base_asset, quote_asset,
                                            quote_asset, amount, amount * price, Decimal("0"), OrderType.LIMIT))
