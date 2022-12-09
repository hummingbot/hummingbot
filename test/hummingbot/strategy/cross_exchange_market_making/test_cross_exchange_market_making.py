import asyncio
import unittest
from copy import deepcopy
from decimal import Decimal
from math import ceil, floor
from typing import Awaitable, List
from unittest.mock import patch

import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import ConnectorSetting, ConnectorType
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TradeFeeSchema
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    OrderBookTradeEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making import (
    CrossExchangeMarketMakingStrategy,
    LogOption,
)
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making_config_map_pydantic import (
    ActiveOrderRefreshMode,
    CrossExchangeMarketMakingConfigMap,
    TakerToMakerConversionRateMode,
)
from hummingbot.strategy.maker_taker_market_pair import MakerTakerMarketPair
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


class HedgedMarketMakingUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    exchange_name_maker = "mock_paper_exchange"
    exchange_name_taker = "mock_paper_exchange"
    trading_pairs_maker: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]
    trading_pairs_taker: List[str] = ["COINALPHA-ETH", "COINALPHA", "ETH"]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    @patch("hummingbot.client.settings.AllConnectorSettings.get_exchange_names")
    @patch("hummingbot.client.settings.AllConnectorSettings.get_connector_settings")
    def setUp(self, get_connector_settings_mock, get_exchange_names_mock):
        get_exchange_names_mock.return_value = set(self.get_mock_connector_settings().keys())
        get_connector_settings_mock.return_value = self.get_mock_connector_settings()

        self.clock: Clock = Clock(ClockMode.BACKTEST, 1.0, self.start_timestamp, self.end_timestamp)
        self.min_profitability = Decimal("0.5")
        self.maker_market: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap()))
        self.taker_market: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap()))
        self.maker_market.set_balanced_order_book(self.trading_pairs_maker[0], 1.0, 0.5, 1.5, 0.01, 10)
        self.taker_market.set_balanced_order_book(self.trading_pairs_taker[0], 1.0, 0.5, 1.5, 0.001, 4)
        self.maker_market.set_balance("COINALPHA", 5)
        self.maker_market.set_balance("WETH", 5)
        self.maker_market.set_balance("QETH", 5)
        self.taker_market.set_balance("COINALPHA", 5)
        self.taker_market.set_balance("ETH", 5)
        self.maker_market.set_quantization_param(QuantizationParams(self.trading_pairs_maker[0], 5, 5, 5, 5))
        self.taker_market.set_quantization_param(QuantizationParams(self.trading_pairs_taker[0], 5, 5, 5, 5))

        self.market_pair: MakerTakerMarketPair = MakerTakerMarketPair(
            MarketTradingPairTuple(self.maker_market, *self.trading_pairs_maker),
            MarketTradingPairTuple(self.taker_market, *self.trading_pairs_taker),
        )

        self.config_map_raw = CrossExchangeMarketMakingConfigMap(
            maker_market=self.exchange_name_maker,
            taker_market=self.exchange_name_taker,
            maker_market_trading_pair=self.trading_pairs_maker[0],
            taker_market_trading_pair=self.trading_pairs_taker[0],
            min_profitability=Decimal(self.min_profitability),
            slippage_buffer=Decimal("0"),
            order_amount=Decimal("0"),
            # Default values folllow
            order_size_taker_volume_factor=Decimal("25"),
            order_size_taker_balance_factor=Decimal("99.5"),
            order_size_portfolio_ratio_limit=Decimal("30"),
            adjust_order_enabled=True,
            anti_hysteresis_duration=60.0,
            order_refresh_mode=ActiveOrderRefreshMode(),
            top_depth_tolerance=Decimal(0),
            conversion_rate_mode=TakerToMakerConversionRateMode(),
        )

        self.config_map_raw.conversion_rate_mode.taker_to_maker_base_conversion_rate = Decimal("1.0")
        self.config_map_raw.conversion_rate_mode.taker_to_maker_quote_conversion_rate = Decimal("1.0")

        self.config_map = ClientConfigAdapter(self.config_map_raw)
        config_map_with_top_depth_tolerance_raw = deepcopy(self.config_map_raw)
        config_map_with_top_depth_tolerance_raw.top_depth_tolerance = Decimal("1")
        config_map_with_top_depth_tolerance = ClientConfigAdapter(
            config_map_with_top_depth_tolerance_raw
        )

        logging_options = (
            LogOption.NULL_ORDER_SIZE,
            LogOption.REMOVING_ORDER,
            LogOption.ADJUST_ORDER,
            LogOption.CREATE_ORDER,
            LogOption.MAKER_ORDER_FILLED,
            LogOption.STATUS_REPORT,
            LogOption.MAKER_ORDER_HEDGED
        )
        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy()
        self.strategy.init_params(
            config_map=self.config_map,
            market_pairs=[self.market_pair],
            logging_options=logging_options,
        )
        self.strategy_with_top_depth_tolerance: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy()
        self.strategy_with_top_depth_tolerance.init_params(
            config_map=config_map_with_top_depth_tolerance,
            market_pairs=[self.market_pair],
            logging_options=logging_options,
        )
        self.logging_options = logging_options
        self.clock.add_iterator(self.maker_market)
        self.clock.add_iterator(self.taker_market)
        self.clock.add_iterator(self.strategy)

        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.taker_order_fill_logger: EventLogger = EventLogger()
        self.maker_cancel_order_logger: EventLogger = EventLogger()
        self.taker_cancel_order_logger: EventLogger = EventLogger()
        self.maker_order_created_logger: EventLogger = EventLogger()
        self.taker_order_created_logger: EventLogger = EventLogger()
        self.maker_market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.taker_market.add_listener(MarketEvent.OrderFilled, self.taker_order_fill_logger)
        self.maker_market.add_listener(MarketEvent.OrderCancelled, self.maker_cancel_order_logger)
        self.taker_market.add_listener(MarketEvent.OrderCancelled, self.taker_cancel_order_logger)
        self.maker_market.add_listener(MarketEvent.BuyOrderCreated, self.maker_order_created_logger)
        self.maker_market.add_listener(MarketEvent.SellOrderCreated, self.maker_order_created_logger)
        self.taker_market.add_listener(MarketEvent.BuyOrderCreated, self.taker_order_created_logger)
        self.taker_market.add_listener(MarketEvent.SellOrderCreated, self.taker_order_created_logger)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_mock_connector_settings(self):

        conf_var_connector_maker = ConfigVar(key='mock_paper_exchange', prompt="")
        conf_var_connector_maker.value = 'mock_paper_exchange'

        conf_var_connector_taker = ConfigVar(key='mock_paper_exchange', prompt="")
        conf_var_connector_taker.value = 'mock_paper_exchange'

        settings = {
            "mock_paper_exchange": ConnectorSetting(
                name='mock_paper_exchange',
                type=ConnectorType.Exchange,
                example_pair='ZRX-ETH',
                centralised=True,
                use_ethereum_wallet=False,
                trade_fee_schema=TradeFeeSchema(
                    percent_fee_token=None,
                    maker_percent_fee_decimal=Decimal('0.001'),
                    taker_percent_fee_decimal=Decimal('0.001'),
                    buy_percent_fee_deducted_from_returns=False,
                    maker_fixed_fees=[],
                    taker_fixed_fees=[]),
                config_keys={
                    'connector': conf_var_connector_maker
                },
                is_sub_domain=False,
                parent_name=None,
                domain_parameter=None,
                use_eth_gas_lookup=False)
        }

        return settings

    def simulate_maker_market_trade(self, is_buy: bool, quantity: Decimal, price: Decimal):
        maker_trading_pair: str = self.trading_pairs_maker[0]
        order_book: OrderBook = self.maker_market.get_order_book(maker_trading_pair)
        trade_event: OrderBookTradeEvent = OrderBookTradeEvent(
            maker_trading_pair, self.clock.current_timestamp, TradeType.BUY if is_buy else TradeType.SELL, price, quantity
        )
        order_book.apply_trade(trade_event)

    @staticmethod
    def simulate_order_book_widening(order_book: OrderBook, top_bid: float, top_ask: float):
        bid_diffs: List[OrderBookRow] = []
        ask_diffs: List[OrderBookRow] = []
        update_id: int = order_book.last_diff_uid + 1
        for row in order_book.bid_entries():
            if row.price > top_bid:
                bid_diffs.append(OrderBookRow(row.price, 0, update_id))
            else:
                break
        for row in order_book.ask_entries():
            if row.price < top_ask:
                ask_diffs.append(OrderBookRow(row.price, 0, update_id))
            else:
                break
        order_book.apply_diffs(bid_diffs, ask_diffs, update_id)

    @staticmethod
    def simulate_limit_order_fill(market: MockPaperExchange, limit_order: LimitOrder):
        quote_currency_traded: Decimal = limit_order.price * limit_order.quantity
        base_currency_traded: Decimal = limit_order.quantity
        quote_currency: str = limit_order.quote_currency
        base_currency: str = limit_order.base_currency

        if limit_order.is_buy:
            market.set_balance(quote_currency, market.get_balance(quote_currency) - quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) + base_currency_traded)
            market.trigger_event(
                MarketEvent.BuyOrderCreated,
                BuyOrderCreatedEvent(
                    market.current_timestamp,
                    OrderType.LIMIT,
                    limit_order.trading_pair,
                    limit_order.quantity,
                    limit_order.price,
                    limit_order.client_order_id,
                    limit_order.creation_timestamp * 1e-6
                )
            )
            market.trigger_event(
                MarketEvent.OrderFilled,
                OrderFilledEvent(
                    market.current_timestamp,
                    limit_order.client_order_id,
                    limit_order.trading_pair,
                    TradeType.BUY,
                    OrderType.LIMIT,
                    limit_order.price,
                    limit_order.quantity,
                    AddedToCostTradeFee(Decimal(0)),
                    "exchid_" + limit_order.client_order_id
                ),
            )
            market.trigger_event(
                MarketEvent.BuyOrderCompleted,
                BuyOrderCompletedEvent(
                    market.current_timestamp,
                    limit_order.client_order_id,
                    base_currency,
                    quote_currency,
                    base_currency_traded,
                    quote_currency_traded,
                    OrderType.LIMIT,
                ),
            )
        else:
            market.set_balance(quote_currency, market.get_balance(quote_currency) + quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) - base_currency_traded)
            market.trigger_event(
                MarketEvent.BuyOrderCreated,
                SellOrderCreatedEvent(
                    market.current_timestamp,
                    OrderType.LIMIT,
                    limit_order.trading_pair,
                    limit_order.quantity,
                    limit_order.price,
                    limit_order.client_order_id,
                    limit_order.creation_timestamp * 1e-6,
                )
            )
            market.trigger_event(
                MarketEvent.OrderFilled,
                OrderFilledEvent(
                    market.current_timestamp,
                    limit_order.client_order_id,
                    limit_order.trading_pair,
                    TradeType.SELL,
                    OrderType.LIMIT,
                    limit_order.price,
                    limit_order.quantity,
                    AddedToCostTradeFee(Decimal(0)),
                    "exchid_" + limit_order.client_order_id
                ),
            )
            market.trigger_event(
                MarketEvent.SellOrderCompleted,
                SellOrderCompletedEvent(
                    market.current_timestamp,
                    limit_order.client_order_id,
                    base_currency,
                    quote_currency,
                    base_currency_traded,
                    quote_currency_traded,
                    OrderType.LIMIT,
                ),
            )

    @staticmethod
    def emit_order_created_event(market: MockPaperExchange, order: LimitOrder):
        event_cls = BuyOrderCreatedEvent if order.is_buy else SellOrderCreatedEvent
        event_tag = MarketEvent.BuyOrderCreated if order.is_buy else MarketEvent.SellOrderCreated
        market.trigger_event(
            event_tag,
            message=event_cls(
                order.creation_timestamp,
                OrderType.LIMIT,
                order.trading_pair,
                order.quantity,
                order.price,
                order.client_order_id,
                order.creation_timestamp * 1e-6
            )
        )

    @patch("hummingbot.client.settings.AllConnectorSettings.get_exchange_names")
    @patch("hummingbot.client.settings.AllConnectorSettings.get_connector_settings")
    @patch('hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making.'
           'CrossExchangeMarketMakingStrategy.is_gateway_market')
    def test_both_sides_profitable(self,
                                   is_gateway_mock: unittest.mock.Mock,
                                   get_connector_settings_mock,
                                   get_exchange_names_mock):
        is_gateway_mock.return_value = False

        get_exchange_names_mock.return_value = set(self.get_mock_connector_settings().keys())
        get_connector_settings_mock.return_value = self.get_mock_connector_settings()

        self.clock.backtest_til(self.start_timestamp + 5)
        if len(self.maker_order_created_logger.event_log) == 0:
            self.async_run_with_timeout(self.maker_order_created_logger.wait_for(BuyOrderCreatedEvent))

        self.assertEqual(1, len(self.strategy.active_maker_bids))
        self.assertEqual(1, len(self.strategy.active_maker_asks))

        bid_order: LimitOrder = self.strategy.active_maker_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_maker_asks[0][1]
        self.assertEqual(Decimal("0.99451"), bid_order.price)
        self.assertEqual(Decimal("1.0055"), ask_order.price)
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

        self.simulate_maker_market_trade(False, Decimal("10.0"), bid_order.price * Decimal("0.99"))

        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))

        is_gateway_mock.return_value = True

        self.clock.backtest_til(self.start_timestamp + 10)
        if len(self.taker_order_created_logger.event_log) == 0:
            self.async_run_with_timeout(self.taker_order_created_logger.wait_for(SellOrderCreatedEvent))

        self.clock.backtest_til(self.start_timestamp + 20)
        if len(self.taker_order_fill_logger.event_log) == 0:
            self.async_run_with_timeout(self.taker_order_fill_logger.wait_for(OrderFilledEvent))

        self.assertEqual(1, len(self.taker_order_fill_logger.event_log))

        maker_fill: OrderFilledEvent = self.maker_order_fill_logger.event_log[0]
        taker_fill: OrderFilledEvent = self.taker_order_fill_logger.event_log[0]
        self.assertEqual(TradeType.BUY, maker_fill.trade_type)
        self.assertEqual(TradeType.SELL, taker_fill.trade_type)
        self.assertAlmostEqual(Decimal("0.99451"), maker_fill.price)
        self.assertAlmostEqual(Decimal("0.9995"), taker_fill.price)
        self.assertAlmostEqual(Decimal("3.0"), maker_fill.amount)
        self.assertAlmostEqual(Decimal("3.0"), taker_fill.amount)

    def test_top_depth_tolerance(self):  # TODO
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.strategy_with_top_depth_tolerance)
        self.clock.backtest_til(self.start_timestamp + 5)
        self.ev_loop.run_until_complete(self.maker_order_created_logger.wait_for(BuyOrderCreatedEvent))
        bid_order: LimitOrder = self.strategy_with_top_depth_tolerance.active_maker_bids[0][1]
        ask_order: LimitOrder = self.strategy_with_top_depth_tolerance.active_maker_asks[0][1]

        self.taker_market.trigger_event(
            MarketEvent.BuyOrderCreated,
            BuyOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                bid_order.trading_pair,
                bid_order.quantity,
                bid_order.price,
                bid_order.client_order_id,
                bid_order.creation_timestamp * 1e-6,
            )
        )

        self.taker_market.trigger_event(
            MarketEvent.SellOrderCreated,
            SellOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                ask_order.trading_pair,
                ask_order.quantity,
                ask_order.price,
                ask_order.client_order_id,
                ask_order.creation_timestamp * 1e-6,
            )
        )

        self.assertEqual(Decimal("0.99451"), bid_order.price)
        self.assertEqual(Decimal("1.0055"), ask_order.price)
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

        prev_maker_orders_created_len = len(self.maker_order_created_logger.event_log)

        self.simulate_order_book_widening(self.taker_market.order_books[self.trading_pairs_taker[0]], 0.99, 1.01)

        self.clock.backtest_til(self.start_timestamp + 100)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.clock.backtest_til(self.start_timestamp + 101)

        if len(self.maker_order_created_logger.event_log) == prev_maker_orders_created_len:
            self.async_run_with_timeout(self.maker_order_created_logger.wait_for(SellOrderCreatedEvent))

        self.assertEqual(2, len(self.maker_cancel_order_logger.event_log))
        self.assertEqual(1, len(self.strategy_with_top_depth_tolerance.active_maker_bids))
        self.assertEqual(1, len(self.strategy_with_top_depth_tolerance.active_maker_asks))

        bid_order = self.strategy_with_top_depth_tolerance.active_maker_bids[0][1]
        ask_order = self.strategy_with_top_depth_tolerance.active_maker_asks[0][1]
        self.assertEqual(Decimal("0.98457"), bid_order.price)
        self.assertEqual(Decimal("1.0155"), ask_order.price)

    def test_market_became_wider(self):
        self.clock.backtest_til(self.start_timestamp + 5)
        self.ev_loop.run_until_complete(self.maker_order_created_logger.wait_for(BuyOrderCreatedEvent))

        bid_order: LimitOrder = self.strategy.active_maker_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_maker_asks[0][1]
        self.assertEqual(Decimal("0.99451"), bid_order.price)
        self.assertEqual(Decimal("1.0055"), ask_order.price)
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

        self.taker_market.trigger_event(
            MarketEvent.BuyOrderCreated,
            BuyOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                bid_order.trading_pair,
                bid_order.quantity,
                bid_order.price,
                bid_order.client_order_id,
                bid_order.creation_timestamp * 1e-6,
            )
        )

        self.taker_market.trigger_event(
            MarketEvent.SellOrderCreated,
            SellOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                ask_order.trading_pair,
                ask_order.quantity,
                ask_order.price,
                ask_order.client_order_id,
                bid_order.creation_timestamp * 1e-6,
            )
        )

        prev_maker_orders_created_len = len(self.maker_order_created_logger.event_log)

        self.simulate_order_book_widening(self.taker_market.order_books[self.trading_pairs_taker[0]], 0.99, 1.01)

        self.clock.backtest_til(self.start_timestamp + 100)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.clock.backtest_til(self.start_timestamp + 101)

        if len(self.maker_order_created_logger.event_log) == prev_maker_orders_created_len:
            self.async_run_with_timeout(self.maker_order_created_logger.wait_for(SellOrderCreatedEvent))

        self.assertEqual(2, len(self.maker_cancel_order_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_maker_bids))
        self.assertEqual(1, len(self.strategy.active_maker_asks))

        bid_order = self.strategy.active_maker_bids[0][1]
        ask_order = self.strategy.active_maker_asks[0][1]
        self.assertEqual(Decimal("0.98457"), bid_order.price)
        self.assertEqual(Decimal("1.0155"), ask_order.price)

    def test_market_became_narrower(self):
        self.clock.backtest_til(self.start_timestamp + 5)
        self.ev_loop.run_until_complete(self.maker_order_created_logger.wait_for(BuyOrderCreatedEvent))
        bid_order: LimitOrder = self.strategy.active_maker_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_maker_asks[0][1]
        self.assertEqual(Decimal("0.99451"), bid_order.price)
        self.assertEqual(Decimal("1.0055"), ask_order.price)
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

        self.maker_market.order_books[self.trading_pairs_maker[0]].apply_diffs(
            [OrderBookRow(0.996, 30, 2)], [OrderBookRow(1.004, 30, 2)], 2)

        self.clock.backtest_til(self.start_timestamp + 10)

        if len(self.maker_order_created_logger.event_log) == 0:
            self.async_run_with_timeout(self.maker_order_created_logger.wait_for(SellOrderCreatedEvent))

        self.assertEqual(0, len(self.maker_cancel_order_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_maker_bids))
        self.assertEqual(1, len(self.strategy.active_maker_asks))

        bid_order = self.strategy.active_maker_bids[0][1]
        ask_order = self.strategy.active_maker_asks[0][1]
        self.assertEqual(Decimal("0.99451"), bid_order.price)
        self.assertEqual(Decimal("1.0055"), ask_order.price)

    def test_order_fills_after_cancellation(self):  # TODO
        self.clock.backtest_til(self.start_timestamp + 5)
        self.ev_loop.run_until_complete(self.maker_order_created_logger.wait_for(BuyOrderCreatedEvent))
        bid_order: LimitOrder = self.strategy.active_maker_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_maker_asks[0][1]
        self.assertEqual(Decimal("0.99451"), bid_order.price)
        self.assertEqual(Decimal("1.0055"), ask_order.price)
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

        self.taker_market.trigger_event(
            MarketEvent.BuyOrderCreated,
            BuyOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                bid_order.trading_pair,
                bid_order.quantity,
                bid_order.price,
                bid_order.client_order_id,
                bid_order.creation_timestamp * 1e-6,
            )
        )

        self.taker_market.trigger_event(
            MarketEvent.SellOrderCreated,
            SellOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                ask_order.trading_pair,
                ask_order.quantity,
                ask_order.price,
                ask_order.client_order_id,
                ask_order.creation_timestamp * 1e-6,
            )
        )

        self.simulate_order_book_widening(self.taker_market.order_books[self.trading_pairs_taker[0]], 0.99, 1.01)

        self.clock.backtest_til(self.start_timestamp + 10)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        prev_maker_orders_created_len = len(self.maker_order_created_logger.event_log)

        self.clock.backtest_til(self.start_timestamp + 11)

        if len(self.maker_order_created_logger.event_log) == prev_maker_orders_created_len:
            self.async_run_with_timeout(self.maker_order_created_logger.wait_for(SellOrderCreatedEvent))

        self.assertEqual(2, len(self.maker_cancel_order_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_maker_bids))
        self.assertEqual(1, len(self.strategy.active_maker_asks))

        bid_order = self.strategy.active_maker_bids[0][1]
        ask_order = self.strategy.active_maker_asks[0][1]
        self.assertEqual(Decimal("0.98457"), bid_order.price)
        self.assertEqual(Decimal("1.0155"), ask_order.price)

        self.simulate_limit_order_fill(self.maker_market, bid_order)
        self.simulate_limit_order_fill(self.maker_market, ask_order)

        prev_taker_orders_created_len = len(self.taker_order_created_logger.event_log)

        self.clock.backtest_til(self.start_timestamp + 20)

        if len(self.taker_order_created_logger.event_log) == prev_taker_orders_created_len:
            self.async_run_with_timeout(self.taker_order_created_logger.wait_for(SellOrderCreatedEvent))

        prev_taker_orders_filled_len = len(self.taker_order_fill_logger.event_log)

        self.clock.backtest_til(self.start_timestamp + 30)

        if len(self.taker_order_fill_logger.event_log) == prev_taker_orders_filled_len:
            self.async_run_with_timeout(self.taker_order_fill_logger.wait_for(OrderFilledEvent))

        fill_events: List[OrderFilledEvent] = self.taker_order_fill_logger.event_log

        bid_hedges: List[OrderFilledEvent] = [evt for evt in fill_events if evt.trade_type is TradeType.SELL]
        ask_hedges: List[OrderFilledEvent] = [evt for evt in fill_events if evt.trade_type is TradeType.BUY]

        self.assertEqual(1, len(bid_hedges))
        self.assertEqual(1, len(ask_hedges))
        self.assertGreater(
            self.maker_market.get_balance(self.trading_pairs_maker[2]) + self.taker_market.get_balance(self.trading_pairs_taker[2]),
            Decimal("10"),
        )
        self.assertEqual(2, len(self.taker_order_fill_logger.event_log))
        taker_fill1: OrderFilledEvent = self.taker_order_fill_logger.event_log[1]
        self.assertEqual(TradeType.SELL, taker_fill1.trade_type)
        self.assertAlmostEqual(Decimal("0.9895"), taker_fill1.price)
        self.assertAlmostEqual(Decimal("3.0"), taker_fill1.amount)
        taker_fill2: OrderFilledEvent = self.taker_order_fill_logger.event_log[0]
        self.assertEqual(TradeType.BUY, taker_fill2.trade_type)
        self.assertAlmostEqual(Decimal("1.0104"), taker_fill2.price)
        self.assertAlmostEqual(Decimal("3.0"), taker_fill2.amount)

    def test_with_conversion_rate_mode_not_set(self):
        self.clock.remove_iterator(self.strategy)
        self.market_pair: MakerTakerMarketPair = MakerTakerMarketPair(
            MarketTradingPairTuple(self.maker_market, *["COINALPHA-QETH", "COINALPHA", "QETH"]),
            MarketTradingPairTuple(self.taker_market, *self.trading_pairs_taker),
        )
        self.maker_market.set_balanced_order_book("COINALPHA-QETH", 1.05, 0.55, 1.55, 0.01, 10)

        config_map_with_conversion_rate_mode_not_set = ClientConfigAdapter(
            CrossExchangeMarketMakingConfigMap(
                maker_market=self.exchange_name_maker,
                taker_market=self.exchange_name_taker,
                maker_market_trading_pair=self.trading_pairs_maker[0],
                taker_market_trading_pair=self.trading_pairs_taker[0],
                min_profitability=Decimal("1"),
                order_amount = Decimal("1"),
            )
        )

        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy()
        self.strategy.init_params(
            config_map=config_map_with_conversion_rate_mode_not_set,
            market_pairs=[self.market_pair],
            logging_options=self.logging_options,
        )
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp + 5)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.assertEqual(0, len(self.strategy.active_maker_bids))
        self.assertEqual(0, len(self.strategy.active_maker_asks))

    def test_with_conversion(self):
        self.clock.remove_iterator(self.strategy)
        self.market_pair: MakerTakerMarketPair = MakerTakerMarketPair(
            MarketTradingPairTuple(self.maker_market, *["COINALPHA-QETH", "COINALPHA", "QETH"]),
            MarketTradingPairTuple(self.taker_market, *self.trading_pairs_taker),
        )
        self.maker_market.set_balanced_order_book("COINALPHA-QETH", 1.05, 0.55, 1.55, 0.01, 10)

        config_map_raw = deepcopy(self.config_map_raw)
        config_map_raw.min_profitability = Decimal("1")
        config_map_raw.order_size_portfolio_ratio_limit = Decimal("30")
        config_map_raw.conversion_rate_mode.taker_to_maker_base_conversion_rate = Decimal("0.95")
        config_map = ClientConfigAdapter(
            config_map_raw
        )

        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy()
        self.strategy.init_params(
            config_map=config_map,
            market_pairs=[self.market_pair],
            logging_options=self.logging_options,
        )
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp + 5)
        self.ev_loop.run_until_complete(self.maker_order_created_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual(1, len(self.strategy.active_maker_bids))
        self.assertEqual(1, len(self.strategy.active_maker_asks))
        bid_order: LimitOrder = self.strategy.active_maker_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_maker_asks[0][1]
        self.assertAlmostEqual(Decimal("1.0417"), round(bid_order.price, 4))
        self.assertAlmostEqual(Decimal("1.0636"), round(ask_order.price, 4))
        self.assertAlmostEqual(Decimal("2.9286"), round(bid_order.quantity, 4))
        self.assertAlmostEqual(Decimal("2.9286"), round(ask_order.quantity, 4))

    def test_maker_price(self):
        task = self.ev_loop.create_task(self.strategy.calculate_effective_hedging_price(self.market_pair, False, 3))
        buy_taker_price: Decimal = self.ev_loop.run_until_complete(task)

        task = self.ev_loop.create_task(self.strategy.calculate_effective_hedging_price(self.market_pair, True, 3))
        sell_taker_price: Decimal = self.ev_loop.run_until_complete(task)

        self.assertEqual(Decimal("1.0004"), buy_taker_price)
        self.assertEqual(Decimal("0.99949"), sell_taker_price)
        self.clock.backtest_til(self.start_timestamp + 5)
        self.ev_loop.run_until_complete(self.maker_order_created_logger.wait_for(BuyOrderCreatedEvent))
        bid_order: LimitOrder = self.strategy.active_maker_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_maker_asks[0][1]
        bid_maker_price = sell_taker_price * (1 - self.min_profitability / Decimal("100"))
        price_quantum = self.maker_market.get_order_price_quantum(self.trading_pairs_maker[0], bid_maker_price)
        bid_maker_price = (floor(bid_maker_price / price_quantum)) * price_quantum
        ask_maker_price = buy_taker_price * (1 + self.min_profitability / Decimal("100"))
        price_quantum = self.maker_market.get_order_price_quantum(self.trading_pairs_maker[0], ask_maker_price)
        ask_maker_price = (ceil(ask_maker_price / price_quantum) * price_quantum)
        self.assertEqual(round(bid_maker_price, 4), round(bid_order.price, 4))
        self.assertEqual(round(ask_maker_price, 4), round(ask_order.price, 4))
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

    def test_with_adjust_orders_enabled(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.remove_iterator(self.maker_market)
        self.maker_market: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap())
        )
        self.maker_market.set_balanced_order_book(self.trading_pairs_maker[0], 1.0, 0.5, 1.5, 0.1, 10)
        self.market_pair: MakerTakerMarketPair = MakerTakerMarketPair(
            MarketTradingPairTuple(self.maker_market, *self.trading_pairs_maker),
            MarketTradingPairTuple(self.taker_market, *self.trading_pairs_taker),
        )

        config_map_raw = deepcopy(self.config_map_raw)
        config_map_raw.order_size_portfolio_ratio_limit = Decimal("30")
        config_map_raw.min_profitability = Decimal("0.5")
        config_map_raw.adjust_order_enabled = True
        config_map = ClientConfigAdapter(
            config_map_raw
        )

        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy()
        self.strategy.init_params(
            config_map=config_map,
            market_pairs=[self.market_pair],
            logging_options=self.logging_options,
        )
        self.maker_market.set_balance("COINALPHA", 5)
        self.maker_market.set_balance("WETH", 5)
        self.maker_market.set_balance("QETH", 5)
        self.maker_market.set_quantization_param(QuantizationParams(self.trading_pairs_maker[0], 4, 4, 4, 4))
        self.clock.add_iterator(self.strategy)
        self.clock.add_iterator(self.maker_market)
        self.clock.backtest_til(self.start_timestamp + 5)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.assertEqual(1, len(self.strategy.active_maker_bids))
        self.assertEqual(1, len(self.strategy.active_maker_asks))
        bid_order: LimitOrder = self.strategy.active_maker_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_maker_asks[0][1]
        # place above top bid (at 0.95)
        self.assertAlmostEqual(Decimal("0.9501"), bid_order.price)
        # place below top ask (at 1.05)
        self.assertAlmostEqual(Decimal("1.049"), ask_order.price)
        self.assertAlmostEqual(Decimal("3"), round(bid_order.quantity, 4))
        self.assertAlmostEqual(Decimal("3"), round(ask_order.quantity, 4))

    def test_with_adjust_orders_disabled(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.remove_iterator(self.maker_market)
        self.maker_market: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap())
        )

        self.maker_market.set_balanced_order_book(self.trading_pairs_maker[0], 1.0, 0.5, 1.5, 0.1, 10)
        self.taker_market.set_balanced_order_book(self.trading_pairs_taker[0], 1.0, 0.5, 1.5, 0.001, 20)
        self.market_pair: MakerTakerMarketPair = MakerTakerMarketPair(
            MarketTradingPairTuple(self.maker_market, *self.trading_pairs_maker),
            MarketTradingPairTuple(self.taker_market, *self.trading_pairs_taker),
        )

        config_map_raw = deepcopy(self.config_map_raw)
        config_map_raw.order_size_portfolio_ratio_limit = Decimal("30")
        config_map_raw.min_profitability = Decimal("0.5")
        config_map_raw.adjust_order_enabled = False
        config_map = ClientConfigAdapter(
            config_map_raw
        )

        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy()
        self.strategy.init_params(
            config_map=config_map,
            market_pairs=[self.market_pair],
            logging_options=self.logging_options,
        )
        self.maker_market.set_balance("COINALPHA", 5)
        self.maker_market.set_balance("WETH", 5)
        self.maker_market.set_balance("QETH", 5)
        self.maker_market.set_quantization_param(QuantizationParams(self.trading_pairs_maker[0], 4, 4, 4, 4))
        self.clock.add_iterator(self.strategy)
        self.clock.add_iterator(self.maker_market)
        self.clock.backtest_til(self.start_timestamp + 5)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.assertEqual(1, len(self.strategy.active_maker_bids))
        self.assertEqual(1, len(self.strategy.active_maker_asks))
        bid_order: LimitOrder = self.strategy.active_maker_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_maker_asks[0][1]
        self.assertEqual(Decimal("0.9945"), bid_order.price)
        self.assertEqual(Decimal("1.006"), ask_order.price)
        self.assertAlmostEqual(Decimal("3"), round(bid_order.quantity, 4))
        self.assertAlmostEqual(Decimal("3"), round(ask_order.quantity, 4))

    def test_price_and_size_limit_calculation(self):
        self.taker_market.set_balanced_order_book(self.trading_pairs_taker[0], 1.0, 0.5, 1.5, 0.001, 20)

        task = self.ev_loop.create_task(self.strategy.get_market_making_size(self.market_pair, True))
        bid_size: Decimal = self.ev_loop.run_until_complete(task)

        task = self.ev_loop.create_task(self.strategy.get_market_making_price(self.market_pair, True, bid_size))
        bid_price: Decimal = self.ev_loop.run_until_complete(task)

        task = self.ev_loop.create_task(self.strategy.get_market_making_size(self.market_pair, False))
        ask_size: Decimal = self.ev_loop.run_until_complete(task)

        task = self.ev_loop.create_task(self.strategy.get_market_making_price(self.market_pair, False, ask_size))
        ask_price: Decimal = self.ev_loop.run_until_complete(task)

        self.assertEqual((Decimal("0.99451"), Decimal("3.0000")), (bid_price, bid_size))
        self.assertEqual((Decimal("1.0055"), Decimal("3.0000")), (ask_price, ask_size))

    @patch("hummingbot.client.settings.AllConnectorSettings.get_exchange_names")
    @patch("hummingbot.client.settings.AllConnectorSettings.get_connector_settings")
    def test_price_and_size_limit_calculation_with_slippage_buffer(self,
                                                                   get_connector_settings_mock,
                                                                   get_exchange_names_mock):
        self.taker_market.set_balance("ETH", 3)
        self.taker_market.set_balanced_order_book(
            self.trading_pairs_taker[0],
            mid_price=Decimal("1.0"),
            min_price=Decimal("0.5"),
            max_price=Decimal("1.5"),
            price_step_size=Decimal("0.1"),
            volume_step_size=Decimal("100"),
        )

        config_map_raw = deepcopy(self.config_map_raw)
        config_map_raw.order_size_taker_volume_factor = Decimal("100")
        config_map_raw.order_size_taker_balance_factor = Decimal("100")
        config_map_raw.order_size_portfolio_ratio_limit = Decimal("100")
        config_map_raw.min_profitability = Decimal("25")
        config_map_raw.slippage_buffer = Decimal("0")
        config_map_raw.order_amount = Decimal("4")
        config_map = ClientConfigAdapter(
            config_map_raw
        )

        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy()
        self.strategy.init_params(
            config_map=config_map,
            market_pairs=[self.market_pair],
            logging_options=self.logging_options,
        )

        get_exchange_names_mock.return_value = set(self.get_mock_connector_settings().keys())
        get_connector_settings_mock.return_value = self.get_mock_connector_settings()

        config_map_with_slippage_buffer = ClientConfigAdapter(
            CrossExchangeMarketMakingConfigMap(
                maker_market=self.exchange_name_maker,
                taker_market=self.exchange_name_taker,
                maker_market_trading_pair=self.trading_pairs_maker[0],
                taker_market_trading_pair=self.trading_pairs_taker[0],
                order_amount=Decimal("4"),
                min_profitability=Decimal("25"),
                order_size_taker_volume_factor=Decimal("100"),
                order_size_taker_balance_factor=Decimal("100"),
                order_size_portfolio_ratio_limit=Decimal("100"),
                slippage_buffer=Decimal("25"),
            )
        )
        strategy_with_slippage_buffer: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy()
        strategy_with_slippage_buffer.init_params(
            config_map=config_map_with_slippage_buffer,
            market_pairs=[self.market_pair],
            logging_options=self.logging_options,
        )

        task = self.ev_loop.create_task(self.strategy.get_market_making_size(self.market_pair, True))
        bid_size: Decimal = self.ev_loop.run_until_complete(task)

        task = self.ev_loop.create_task(self.strategy.get_market_making_price(self.market_pair, True, bid_size))
        bid_price: Decimal = self.ev_loop.run_until_complete(task)

        task = self.ev_loop.create_task(self.strategy.get_market_making_size(self.market_pair, False))
        ask_size: Decimal = self.ev_loop.run_until_complete(task)

        task = self.ev_loop.create_task(self.strategy.get_market_making_price(self.market_pair, False, ask_size))
        ask_price: Decimal = self.ev_loop.run_until_complete(task)

        task = self.ev_loop.create_task(strategy_with_slippage_buffer.get_market_making_size(self.market_pair, True))
        slippage_bid_size: Decimal = self.ev_loop.run_until_complete(task)

        task = self.ev_loop.create_task(strategy_with_slippage_buffer.get_market_making_price(
            self.market_pair, True, slippage_bid_size
        ))
        slippage_bid_price: Decimal = self.ev_loop.run_until_complete(task)

        task = self.ev_loop.create_task(strategy_with_slippage_buffer.get_market_making_size(self.market_pair, False))
        slippage_ask_size: Decimal = self.ev_loop.run_until_complete(task)

        task = self.ev_loop.create_task(strategy_with_slippage_buffer.get_market_making_price(
            self.market_pair, False, slippage_ask_size
        ))
        slippage_ask_price: Decimal = self.ev_loop.run_until_complete(task)

        self.assertEqual(Decimal("4"), bid_size)  # the user size
        self.assertEqual(Decimal("0.75999"), bid_price)  # price = bid_VWAP(4) / profitability = 0.95 / 1.25
        self.assertEqual(Decimal("2.8571"), ask_size)  # size = balance / (ask_VWAP(3) * slippage) = 3 / (1.05 * 1)
        self.assertEqual(Decimal("1.3125"), ask_price)  # price = ask_VWAP(2.8571) * profitability = 1.05 * 1.25
        self.assertEqual(Decimal("4"), slippage_bid_size)  # the user size
        self.assertEqual(Decimal("0.75999"), slippage_bid_price)  # price = bid_VWAP(4) / profitability = 0.9 / 1.25
        self.assertEqual(Decimal("2.2857"), slippage_ask_size)  # size = balance / (ask_VWAP(3) * slippage) = 3 / (1.05 * 1.25)
        self.assertEqual(Decimal("1.3125"), slippage_ask_price)  # price = ask_VWAP(2.2857) * profitability = 1.05 * 1.25

    def test_check_if_sufficient_balance_adjusts_including_slippage(self):
        self.taker_market.set_balance("COINALPHA", 4)
        self.taker_market.set_balance("ETH", 3)
        self.taker_market.set_balanced_order_book(
            self.trading_pairs_taker[0],
            mid_price=Decimal("1.0"),
            min_price=Decimal("0.5"),
            max_price=Decimal("1.5"),
            price_step_size=Decimal("0.1"),
            volume_step_size=Decimal("1"),
        )

        config_map_raw = deepcopy(self.config_map_raw)
        config_map_raw.order_size_taker_volume_factor = Decimal("100")
        config_map_raw.order_size_taker_balance_factor = Decimal("100")
        config_map_raw.order_size_portfolio_ratio_limit = Decimal("100")
        config_map_raw.min_profitability = Decimal("25")
        config_map_raw.slippage_buffer = Decimal("25")
        config_map_raw.order_amount = Decimal("4")

        config_map = ClientConfigAdapter(
            config_map_raw
        )

        strategy_with_slippage_buffer: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy()
        strategy_with_slippage_buffer.init_params(
            config_map=config_map,
            market_pairs=[self.market_pair],
            logging_options=self.logging_options,
        )
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(strategy_with_slippage_buffer)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.ev_loop.run_until_complete(self.maker_order_created_logger.wait_for(BuyOrderCreatedEvent))

        active_maker_bids = strategy_with_slippage_buffer.active_maker_bids
        active_maker_asks = strategy_with_slippage_buffer.active_maker_asks

        self.assertEqual(1, len(active_maker_bids))
        self.assertEqual(1, len(active_maker_asks))

        active_bid = active_maker_bids[0][1]
        active_ask = active_maker_asks[0][1]

        self.emit_order_created_event(self.maker_market, active_bid)
        self.emit_order_created_event(self.maker_market, active_ask)

        self.clock.backtest_til(self.start_timestamp + 2)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.clock.backtest_til(self.start_timestamp + 3)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        active_maker_bids = strategy_with_slippage_buffer.active_maker_bids
        active_maker_asks = strategy_with_slippage_buffer.active_maker_asks

        self.assertEqual(1, len(active_maker_bids))
        self.assertEqual(1, len(active_maker_asks))

        active_bid = active_maker_bids[0][1]
        active_ask = active_maker_asks[0][1]
        bids_quantum = self.taker_market.get_order_size_quantum(
            self.trading_pairs_taker[0], active_bid.quantity
        )
        asks_quantum = self.taker_market.get_order_size_quantum(
            self.trading_pairs_taker[0], active_ask.quantity
        )

        self.taker_market.set_balance("COINALPHA", Decimal("4") - bids_quantum)
        self.taker_market.set_balance("ETH", Decimal("3") - asks_quantum * 1)

        self.clock.backtest_til(self.start_timestamp + 4)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        active_maker_bids = strategy_with_slippage_buffer.active_maker_bids
        active_maker_asks = strategy_with_slippage_buffer.active_maker_asks

        self.assertEqual(0, len(active_maker_bids))  # cancelled
        self.assertEqual(0, len(active_maker_asks))  # cancelled

        prev_maker_orders_created_len = len(self.maker_order_created_logger.event_log)

        self.clock.backtest_til(self.start_timestamp + 5)

        if len(self.maker_order_created_logger.event_log) == prev_maker_orders_created_len:
            self.async_run_with_timeout(self.maker_order_created_logger.wait_for(BuyOrderCreatedEvent))

        new_active_maker_bids = strategy_with_slippage_buffer.active_maker_bids
        new_active_maker_asks = strategy_with_slippage_buffer.active_maker_asks

        self.assertEqual(1, len(new_active_maker_bids))
        self.assertEqual(1, len(new_active_maker_asks))

        new_active_bid = new_active_maker_bids[0][1]
        new_active_ask = new_active_maker_asks[0][1]

        self.assertEqual(Decimal(str(active_bid.quantity - bids_quantum)), new_active_bid.quantity)
        self.assertEqual(Decimal(str(active_ask.quantity - asks_quantum)), new_active_ask.quantity)

    def test_empty_maker_orderbook(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.remove_iterator(self.maker_market)
        self.maker_market: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap())
        )

        # Orderbook is empty
        self.maker_market.new_empty_order_book(self.trading_pairs_maker[0])
        self.market_pair: MakerTakerMarketPair = MakerTakerMarketPair(
            MarketTradingPairTuple(self.maker_market, *self.trading_pairs_maker),
            MarketTradingPairTuple(self.taker_market, *self.trading_pairs_taker),
        )

        config_map_raw = deepcopy(self.config_map_raw)
        config_map_raw.min_profitability = Decimal("0.5")
        config_map_raw.adjust_order_enabled = False
        config_map_raw.order_amount = Decimal("1")

        config_map = ClientConfigAdapter(
            config_map_raw
        )

        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy()
        self.strategy.init_params(
            config_map=config_map,
            market_pairs=[self.market_pair],
            logging_options=self.logging_options,
        )
        self.maker_market.set_balance("COINALPHA", 5)
        self.maker_market.set_balance("WETH", 5)
        self.maker_market.set_balance("QETH", 5)
        self.maker_market.set_quantization_param(QuantizationParams(self.trading_pairs_maker[0], 4, 4, 4, 4))
        self.clock.add_iterator(self.strategy)
        self.clock.add_iterator(self.maker_market)
        self.clock.backtest_til(self.start_timestamp + 5)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.assertEqual(1, len(self.strategy.active_maker_bids))
        self.assertEqual(1, len(self.strategy.active_maker_asks))
        bid_order: LimitOrder = self.strategy.active_maker_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_maker_asks[0][1]
        # Places orders based on taker orderbook
        self.assertEqual(Decimal("0.9945"), bid_order.price)
        self.assertEqual(Decimal("1.006"), ask_order.price)
        self.assertAlmostEqual(Decimal("1"), round(bid_order.quantity, 4))
        self.assertAlmostEqual(Decimal("1"), round(ask_order.quantity, 4))
