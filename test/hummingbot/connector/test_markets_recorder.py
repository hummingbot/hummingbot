import asyncio
import time
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Awaitable
from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np
from sqlalchemy import create_engine

from hummingbot.client.config.client_config_map import ClientConfigMap, MarketDataCollectionConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.core.data_type.common import OrderType, PositionAction, PriceType, TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.model.executors import Executors
from hummingbot.model.market_data import MarketData
from hummingbot.model.order import Order
from hummingbot.model.position import Position
from hummingbot.model.sql_connection_manager import SQLConnectionManager, SQLConnectionType
from hummingbot.model.trade_fill import TradeFill
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.executors.position_executor.position_executor import PositionExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class MarketsRecorderTests(IsolatedAsyncioWrapperTestCase):
    @staticmethod
    def create_mock_strategy():
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock(spec=ScriptStrategyBase)
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="ETH-USDT")
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        strategy.connectors = {
            "binance_perpetual": MagicMock(),
        }
        return strategy

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_price_by_type(self, trading_pair, price_type):
        pass

    def get_order_book(self, trading_pair):
        pass

    @patch("hummingbot.model.sql_connection_manager.create_engine")
    def setUp(self, engine_mock) -> None:
        super().setUp()
        self.display_name = "test_market"
        self.config_file_path = "test_config"
        self.strategy_name = "test_strategy"

        self.symbol = "COINALPHAHBOT"
        self.base = "COINALPHA"
        self.quote = "HBOT"
        self.trading_pair = f"{self.base}-{self.quote}"
        self.ready = True
        self.trading_pairs = [self.trading_pair]

        engine_mock.return_value = create_engine("sqlite:///:memory:")
        self.manager = SQLConnectionManager(
            ClientConfigAdapter(ClientConfigMap()), SQLConnectionType.TRADE_FILLS, db_name="test_DB"
        )

        self.tracking_states = dict()

    def add_trade_fills_from_market_recorder(self, current_trade_fills):
        pass

    def add_exchange_order_ids_from_market_recorder(self, current_exchange_order_ids):
        pass

    def test_properties(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        self.assertEqual(self.manager, recorder.sql_manager)
        self.assertEqual(self.config_file_path, recorder.config_file_path)
        self.assertEqual(self.strategy_name, recorder.strategy_name)
        self.assertIsInstance(recorder.logger(), HummingbotLogger)

    def test_get_trade_for_config(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        with self.manager.get_new_session() as session:
            with session.begin():
                trade_fill_record = TradeFill(
                    config_file_path=self.config_file_path,
                    strategy=self.strategy_name,
                    market=self.display_name,
                    symbol=self.symbol,
                    base_asset=self.base,
                    quote_asset=self.quote,
                    timestamp=int(time.time()),
                    order_id="OID1",
                    trade_type=TradeType.BUY.name,
                    order_type=OrderType.LIMIT.name,
                    price=Decimal(1000),
                    amount=Decimal(1),
                    leverage=1,
                    trade_fee=AddedToCostTradeFee().to_json(),
                    exchange_trade_id="EOID1",
                    position=PositionAction.NIL.value)
                session.add(trade_fill_record)

            fill_id = trade_fill_record.exchange_trade_id

        trades = recorder.get_trades_for_config("test_config")
        self.assertEqual(1, len(trades))
        self.assertEqual(fill_id, trades[0].exchange_trade_id)

    def test_buy_order_created_event_creates_order_record(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        event = BuyOrderCreatedEvent(
            timestamp=int(time.time()),
            type=OrderType.LIMIT,
            trading_pair=self.trading_pair,
            amount=Decimal(1),
            price=Decimal(1000),
            order_id="OID1",
            creation_timestamp=1640001112.223,
            exchange_order_id="EOID1",
        )

        recorder._did_create_order(MarketEvent.BuyOrderCreated.value, self, event)

        with self.manager.get_new_session() as session:
            query = session.query(Order)
            orders = query.all()
            order = orders[0]
            order_status = order.status
            trade_fills = order.trade_fills

        self.assertEqual(1, len(orders))
        self.assertEqual(self.config_file_path, orders[0].config_file_path)
        self.assertEqual(event.order_id, orders[0].id)
        self.assertEqual(1640001112223, orders[0].creation_timestamp)
        self.assertEqual(1, len(order_status))
        self.assertEqual(MarketEvent.BuyOrderCreated.name, order_status[0].status)
        self.assertEqual(0, len(trade_fills))

    def test_sell_order_created_event_creates_order_record(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        event = SellOrderCreatedEvent(
            timestamp=int(time.time()),
            type=OrderType.LIMIT,
            trading_pair=self.trading_pair,
            amount=Decimal(1),
            price=Decimal(1000),
            order_id="OID1",
            creation_timestamp=1640001112.223,
            exchange_order_id="EOID1",
        )

        recorder._did_create_order(MarketEvent.SellOrderCreated.value, self, event)

        with self.manager.get_new_session() as session:
            query = session.query(Order)
            orders = query.all()
            order = orders[0]
            order_status = order.status
            trade_fills = order.trade_fills

        self.assertEqual(1, len(orders))
        self.assertEqual(self.config_file_path, orders[0].config_file_path)
        self.assertEqual(event.order_id, orders[0].id)
        self.assertEqual(1640001112223, orders[0].creation_timestamp)
        self.assertEqual(1, len(order_status))
        self.assertEqual(MarketEvent.SellOrderCreated.name, order_status[0].status)
        self.assertEqual(0, len(trade_fills))

    def test_create_order_and_process_fill(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        create_event = BuyOrderCreatedEvent(
            timestamp=1642010000,
            type=OrderType.LIMIT,
            trading_pair=self.trading_pair,
            amount=Decimal(1),
            price=Decimal(1000),
            order_id="OID1-1642010000000000",
            creation_timestamp=1640001112.223,
            exchange_order_id="EOID1",
        )

        recorder._did_create_order(MarketEvent.BuyOrderCreated.value, self, create_event)

        fill_event = OrderFilledEvent(
            timestamp=1642020000,
            order_id=create_event.order_id,
            trading_pair=create_event.trading_pair,
            trade_type=TradeType.BUY,
            order_type=create_event.type,
            price=Decimal(1010),
            amount=create_event.amount,
            trade_fee=AddedToCostTradeFee(),
            exchange_trade_id="TradeId1"
        )

        recorder._did_fill_order(MarketEvent.OrderFilled.value, self, fill_event)

        with self.manager.get_new_session() as session:
            query = session.query(Order)
            orders = query.all()
            order = orders[0]
            order_status = order.status
            trade_fills = order.trade_fills

        self.assertEqual(1, len(orders))
        self.assertEqual(self.config_file_path, orders[0].config_file_path)
        self.assertEqual(create_event.order_id, orders[0].id)
        self.assertEqual(2, len(order_status))
        self.assertEqual(MarketEvent.BuyOrderCreated.name, order_status[0].status)
        self.assertEqual(MarketEvent.OrderFilled.name, order_status[1].status)
        self.assertEqual(1, len(trade_fills))
        self.assertEqual(self.config_file_path, trade_fills[0].config_file_path)
        self.assertEqual(fill_event.order_id, trade_fills[0].order_id)

    def test_trade_fee_in_quote_not_available(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        create_event = BuyOrderCreatedEvent(
            timestamp=1642010000,
            type=OrderType.LIMIT,
            trading_pair=self.trading_pair,
            amount=Decimal(1),
            price=Decimal(1000),
            order_id="OID1-1642010000000000",
            creation_timestamp=1640001112.223,
            exchange_order_id="EOID1",
        )

        recorder._did_create_order(MarketEvent.BuyOrderCreated.value, self, create_event)

        trade_fee = MagicMock()
        trade_fee.fee_amount_in_token = MagicMock(side_effect=[Exception("Fee amount in quote not available")])
        trade_fee.to_json = MagicMock(return_value={"test": "test"})
        fill_event = OrderFilledEvent(
            timestamp=1642020000,
            order_id=create_event.order_id,
            trading_pair=create_event.trading_pair,
            trade_type=TradeType.BUY,
            order_type=create_event.type,
            price=Decimal(1010),
            amount=create_event.amount,
            trade_fee=trade_fee,
            exchange_trade_id="TradeId1"
        )

        recorder._did_fill_order(MarketEvent.OrderFilled.value, self, fill_event)

        with self.manager.get_new_session() as session:
            query = session.query(Order)
            orders = query.all()
            order = orders[0]
            order_status = order.status
            trade_fills = order.trade_fills

        self.assertEqual(1, len(orders))
        self.assertEqual(self.config_file_path, orders[0].config_file_path)
        self.assertEqual(create_event.order_id, orders[0].id)
        self.assertEqual(2, len(order_status))
        self.assertEqual(MarketEvent.BuyOrderCreated.name, order_status[0].status)
        self.assertEqual(MarketEvent.OrderFilled.name, order_status[1].status)
        self.assertEqual(1, len(trade_fills))
        self.assertEqual(self.config_file_path, trade_fills[0].config_file_path)
        self.assertEqual(fill_event.order_id, trade_fills[0].order_id)

    def test_create_order_and_completed(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        create_event = BuyOrderCreatedEvent(
            timestamp=1642010000,
            type=OrderType.LIMIT,
            trading_pair=self.trading_pair,
            amount=Decimal(1),
            price=Decimal(1000),
            order_id="OID1-1642010000000000",
            creation_timestamp=1640001112.223,
            exchange_order_id="EOID1",
        )

        recorder._did_create_order(MarketEvent.BuyOrderCreated.value, self, create_event)

        complete_event = BuyOrderCompletedEvent(
            timestamp=1642020000,
            order_id=create_event.order_id,
            base_asset=self.base,
            quote_asset=self.quote,
            base_asset_amount=create_event.amount,
            quote_asset_amount=create_event.amount * create_event.price,
            order_type=create_event.type)

        recorder._did_complete_order(MarketEvent.BuyOrderCompleted.value, self, complete_event)

        with self.manager.get_new_session() as session:
            query = session.query(Order)
            orders = query.all()
            order = orders[0]
            order_status = order.status
            trade_fills = order.trade_fills

        self.assertEqual(1, len(orders))
        self.assertEqual(self.config_file_path, orders[0].config_file_path)
        self.assertEqual(create_event.order_id, orders[0].id)
        self.assertEqual(2, len(order_status))
        self.assertEqual(MarketEvent.BuyOrderCreated.name, order_status[0].status)
        self.assertEqual(MarketEvent.BuyOrderCompleted.name, order_status[1].status)
        self.assertEqual(0, len(trade_fills))

    @patch("hummingbot.connector.markets_recorder.MarketsRecorder._sleep")
    def test_market_data_collection_enabled(self, sleep_mock):
        sleep_mock.side_effect = [0.1, asyncio.CancelledError]
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=True,
                market_data_collection_interval=1,
                market_data_collection_depth=20,
            ),
        )
        with patch.object(self, "get_price_by_type") as get_price_by_type:
            # Set the side_effect function to determine return values
            def side_effect(trading_pair, price_type):
                if price_type == PriceType.MidPrice:
                    return Decimal("100")
                elif price_type == PriceType.BestBid:
                    return Decimal("99")
                elif price_type == PriceType.BestAsk:
                    return Decimal("101")

            # Assign the side_effect function to the mock method
            get_price_by_type.side_effect = side_effect
            with patch.object(self, "get_order_book") as get_order_book:
                order_book = OrderBook(dex=False)
                bids_array = np.array([[1, 1, 1], [2, 1, 2], [3, 1, 3]], dtype=np.float64)
                asks_array = np.array([[4, 1, 1], [5, 1, 2], [6, 1, 3], [7, 1, 4]], dtype=np.float64)
                order_book.apply_numpy_snapshot(bids_array, asks_array)
                get_order_book.return_value = order_book
                with self.assertRaises(asyncio.CancelledError):
                    self.async_run_with_timeout(recorder._record_market_data())
        with self.manager.get_new_session() as session:
            query = session.query(MarketData)
            market_data = query.all()
        self.assertEqual(market_data[0].best_ask, Decimal("101"))
        self.assertEqual(market_data[0].best_bid, Decimal("99"))
        self.assertEqual(market_data[0].mid_price, Decimal("100"))

    def test_store_position(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        position = Position(id="123", timestamp=123, controller_id="test_controller", connector_name="binance",
                            trading_pair="ETH-USDT", side=TradeType.BUY.name, amount=Decimal("1"), breakeven_price=Decimal("1000"),
                            unrealized_pnl_quote=Decimal("0"), cum_fees_quote=Decimal("0"),
                            volume_traded_quote=Decimal("10"))
        recorder.store_position(position)
        with self.manager.get_new_session() as session:
            query = session.query(Position)
            positions = query.all()
        self.assertEqual(1, len(positions))

    def test_update_or_store_position(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        # Test inserting a new position
        position1 = Position(
            id="123",
            timestamp=123,
            controller_id="test_controller",
            connector_name="binance",
            trading_pair="ETH-USDT",
            side=TradeType.BUY.name,
            amount=Decimal("1"),
            breakeven_price=Decimal("1000"),
            unrealized_pnl_quote=Decimal("0"),
            cum_fees_quote=Decimal("0"),
            volume_traded_quote=Decimal("10")
        )
        recorder.update_or_store_position(position1)

        with self.manager.get_new_session() as session:
            query = session.query(Position)
            positions = query.all()
        self.assertEqual(1, len(positions))
        self.assertEqual(Decimal("1"), positions[0].amount)
        self.assertEqual(Decimal("1000"), positions[0].breakeven_price)
        self.assertEqual(Decimal("10"), positions[0].volume_traded_quote)

        # Test updating an existing position with same controller_id, connector, trading_pair, and side
        position2 = Position(
            id="456",  # Different ID (this will be ignored for existing positions)
            timestamp=456,  # New timestamp
            controller_id="test_controller",  # Same controller
            connector_name="binance",  # Same connector
            trading_pair="ETH-USDT",  # Same trading pair
            side=TradeType.BUY.name,  # Same side
            amount=Decimal("2"),  # Updated amount
            breakeven_price=Decimal("1100"),  # Updated price
            unrealized_pnl_quote=Decimal("100"),  # Updated PnL
            cum_fees_quote=Decimal("5"),  # Updated fees
            volume_traded_quote=Decimal("30")  # Updated volume
        )
        recorder.update_or_store_position(position2)

        with self.manager.get_new_session() as session:
            query = session.query(Position)
            positions = query.all()
        # Should still be only 1 position (updated, not inserted)
        self.assertEqual(1, len(positions))
        self.assertEqual(Decimal("2"), positions[0].amount)
        self.assertEqual(Decimal("1100"), positions[0].breakeven_price)
        self.assertEqual(Decimal("100"), positions[0].unrealized_pnl_quote)
        self.assertEqual(Decimal("5"), positions[0].cum_fees_quote)
        self.assertEqual(Decimal("30"), positions[0].volume_traded_quote)
        self.assertEqual(456, positions[0].timestamp)

        # Test inserting a new position with different side
        position3 = Position(
            id="789",
            timestamp=789,
            controller_id="test_controller",
            connector_name="binance",
            trading_pair="ETH-USDT",
            side=TradeType.SELL.name,  # Different side
            amount=Decimal("0.5"),
            breakeven_price=Decimal("1200"),
            unrealized_pnl_quote=Decimal("-50"),
            cum_fees_quote=Decimal("2"),
            volume_traded_quote=Decimal("15")
        )
        recorder.update_or_store_position(position3)

        with self.manager.get_new_session() as session:
            query = session.query(Position)
            positions = query.all()
        # Should now have 2 positions (one BUY, one SELL)
        self.assertEqual(2, len(positions))

        # Test inserting a new position with different trading pair
        position4 = Position(
            id="1011",
            timestamp=1011,
            controller_id="test_controller",
            connector_name="binance",
            trading_pair="BTC-USDT",  # Different trading pair
            side=TradeType.BUY.name,
            amount=Decimal("0.1"),
            breakeven_price=Decimal("50000"),
            unrealized_pnl_quote=Decimal("500"),
            cum_fees_quote=Decimal("10"),
            volume_traded_quote=Decimal("5000")
        )
        recorder.update_or_store_position(position4)

        with self.manager.get_new_session() as session:
            query = session.query(Position)
            positions = query.all()
        # Should now have 3 positions
        self.assertEqual(3, len(positions))

    def test_get_positions_methods(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        # Create test positions
        position1 = Position(
            id="pos1",
            timestamp=123,
            controller_id="controller1",
            connector_name="binance",
            trading_pair="ETH-USDT",
            side=TradeType.BUY.name,
            amount=Decimal("1"),
            breakeven_price=Decimal("1000"),
            unrealized_pnl_quote=Decimal("0"),
            cum_fees_quote=Decimal("0"),
            volume_traded_quote=Decimal("10")
        )
        position2 = Position(
            id="pos2",
            timestamp=124,
            controller_id="controller1",
            connector_name="binance",
            trading_pair="BTC-USDT",
            side=TradeType.SELL.name,
            amount=Decimal("0.1"),
            breakeven_price=Decimal("50000"),
            unrealized_pnl_quote=Decimal("100"),
            cum_fees_quote=Decimal("5"),
            volume_traded_quote=Decimal("5000")
        )
        position3 = Position(
            id="pos3",
            timestamp=125,
            controller_id="controller2",
            connector_name="kucoin",
            trading_pair="ETH-USDT",
            side=TradeType.BUY.name,
            amount=Decimal("2"),
            breakeven_price=Decimal("1100"),
            unrealized_pnl_quote=Decimal("-50"),
            cum_fees_quote=Decimal("2"),
            volume_traded_quote=Decimal("20")
        )

        recorder.store_position(position1)
        recorder.store_position(position2)
        recorder.store_position(position3)

        # Test get_all_positions
        all_positions = recorder.get_all_positions()
        self.assertEqual(3, len(all_positions))
        self.assertIn("pos1", [p.id for p in all_positions])
        self.assertIn("pos2", [p.id for p in all_positions])
        self.assertIn("pos3", [p.id for p in all_positions])

        # Test get_positions_by_controller
        controller1_positions = recorder.get_positions_by_controller("controller1")
        self.assertEqual(2, len(controller1_positions))
        self.assertIn("pos1", [p.id for p in controller1_positions])
        self.assertIn("pos2", [p.id for p in controller1_positions])

        controller2_positions = recorder.get_positions_by_controller("controller2")
        self.assertEqual(1, len(controller2_positions))
        self.assertEqual("pos3", controller2_positions[0].id)

        # Test get_positions_by_ids
        positions_by_ids = recorder.get_positions_by_ids(["pos1", "pos3"])
        self.assertEqual(2, len(positions_by_ids))
        self.assertIn("pos1", [p.id for p in positions_by_ids])
        self.assertIn("pos3", [p.id for p in positions_by_ids])
        self.assertNotIn("pos2", [p.id for p in positions_by_ids])

    def test_store_or_update_executor(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )
        position_executor_mock = MagicMock(spec=PositionExecutor)
        position_executor_config = PositionExecutorConfig(
            id="123", timestamp=1234, trading_pair="ETH-USDT", connector_name="binance", side=TradeType.BUY,
            entry_price=Decimal("1000"), amount=Decimal("1"), leverage=1,
            triple_barrier_config=TripleBarrierConfig(take_profit=Decimal("0.1"), stop_loss=Decimal("0.2")),
        )
        position_executor_mock.config = position_executor_config
        position_executor_mock.executor_info = ExecutorInfo(
            id="123", timestamp=1234, type="position_executor", close_timestamp=1235, close_type=CloseType.TAKE_PROFIT,
            status=RunnableStatus.TERMINATED, controller_id="test_controller", custom_info={},
            config=position_executor_config, net_pnl_pct=Decimal("0.1"), net_pnl_quote=Decimal("10"),
            cum_fees_quote=Decimal("0.1"), filled_amount_quote=Decimal("1"), is_active=False, is_trading=False)

        recorder.store_or_update_executor(position_executor_mock)
        with self.manager.get_new_session() as session:
            query = session.query(Executors)
            executors = query.all()
        self.assertEqual(1, len(executors))

    def test_add_market(self):
        """Test adding a new market dynamically to the recorder."""
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        # Create a new mock market
        new_market = MagicMock()
        new_market.name = "new_test_market"
        new_market.display_name = "new_test_market"
        new_market.trading_pairs = ["BTC-USDT"]
        new_market.tracking_states = {}  # Empty dict is JSON serializable
        new_market.add_trade_fills_from_market_recorder = MagicMock()
        new_market.add_exchange_order_ids_from_market_recorder = MagicMock()
        new_market.add_listener = MagicMock()

        # Initial state: recorder should have only one market
        self.assertEqual(1, len(recorder._markets))
        self.assertEqual(self, recorder._markets[0])

        # Add the new market
        recorder.add_market(new_market)

        # Verify the new market was added
        self.assertEqual(2, len(recorder._markets))
        self.assertIn(new_market, recorder._markets)

        # Verify trade fills were loaded for the new market
        new_market.add_trade_fills_from_market_recorder.assert_called_once()

        # Verify exchange order IDs were loaded for the new market
        new_market.add_exchange_order_ids_from_market_recorder.assert_called_once()

        # Verify event listeners were added (should be called for each event pair)
        expected_calls = len(recorder._event_pairs)
        self.assertEqual(expected_calls, new_market.add_listener.call_count)

        # Test adding the same market again (should not duplicate)
        recorder.add_market(new_market)
        self.assertEqual(2, len(recorder._markets))  # Should still be 2, not 3

    def test_add_market_with_existing_trade_data(self):
        """Test adding a market when there's existing trade data for that market."""
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        # Create some test trade data in the database
        with self.manager.get_new_session() as session:
            with session.begin():
                trade_fill_record = TradeFill(
                    config_file_path=self.config_file_path,
                    strategy=self.strategy_name,
                    market="specific_market",  # This matches our new market's name
                    symbol="BTC-USDT",
                    base_asset="BTC",
                    quote_asset="USDT",
                    timestamp=int(time.time()),
                    order_id="OID2",
                    trade_type=TradeType.BUY.name,
                    order_type=OrderType.LIMIT.name,
                    price=Decimal(50000),
                    amount=Decimal(0.1),
                    leverage=1,
                    trade_fee=AddedToCostTradeFee().to_json(),
                    exchange_trade_id="EOID2",
                    position=PositionAction.NIL.value
                )
                session.add(trade_fill_record)

                order_record = Order(
                    id="OID2",
                    config_file_path=self.config_file_path,
                    strategy=self.strategy_name,
                    market="specific_market",
                    symbol="BTC-USDT",
                    base_asset="BTC",
                    quote_asset="USDT",
                    creation_timestamp=int(time.time()),
                    order_type=OrderType.LIMIT.name,
                    amount=Decimal(0.1),
                    leverage=1,
                    price=Decimal(50000),
                    position=PositionAction.NIL.value,
                    last_status="CREATED",
                    last_update_timestamp=int(time.time()),
                    exchange_order_id="EOID2"
                )
                session.add(order_record)

        # Create a new mock market
        new_market = MagicMock()
        new_market.name = "specific_market"
        new_market.display_name = "specific_market"
        new_market.trading_pairs = ["BTC-USDT"]
        new_market.tracking_states = {}  # Empty dict is JSON serializable
        new_market.add_trade_fills_from_market_recorder = MagicMock()
        new_market.add_exchange_order_ids_from_market_recorder = MagicMock()
        new_market.add_listener = MagicMock()

        # Add the new market
        recorder.add_market(new_market)

        # Verify the market was added and data loading methods were called
        self.assertIn(new_market, recorder._markets)
        new_market.add_trade_fills_from_market_recorder.assert_called_once()
        new_market.add_exchange_order_ids_from_market_recorder.assert_called_once()

        # Verify the trade fills call included only data for this specific market
        call_args = new_market.add_trade_fills_from_market_recorder.call_args[0][0]
        # The call should have been made with a set of TradeFillOrderDetails
        self.assertIsInstance(call_args, set)

    def test_remove_market(self):
        """Test removing a market dynamically from the recorder."""
        # Create a second mock market
        second_market = MagicMock()
        second_market.name = "second_market"
        second_market.display_name = "second_market"
        second_market.trading_pairs = ["BTC-USDT"]
        second_market.tracking_states = {}  # Empty dict is JSON serializable
        second_market.add_trade_fills_from_market_recorder = MagicMock()
        second_market.add_exchange_order_ids_from_market_recorder = MagicMock()
        second_market.add_listener = MagicMock()
        second_market.remove_listener = MagicMock()

        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self, second_market],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        # Initial state: recorder should have two markets
        self.assertEqual(2, len(recorder._markets))
        self.assertIn(self, recorder._markets)
        self.assertIn(second_market, recorder._markets)

        # Remove the second market
        recorder.remove_market(second_market)

        # Verify the market was removed
        self.assertEqual(1, len(recorder._markets))
        self.assertIn(self, recorder._markets)
        self.assertNotIn(second_market, recorder._markets)

        # Verify event listeners were removed (should be called for each event pair)
        expected_calls = len(recorder._event_pairs)
        self.assertEqual(expected_calls, second_market.remove_listener.call_count)

        # Test removing a market that doesn't exist (should not cause error)
        non_existent_market = MagicMock()
        recorder.remove_market(non_existent_market)
        self.assertEqual(1, len(recorder._markets))  # Should still be 1

    def test_add_remove_market_event_listeners(self):
        """Test that event listeners are properly managed when adding/removing markets."""
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        # Create a new mock market with proper listener methods
        new_market = MagicMock()
        new_market.name = "event_test_market"
        new_market.display_name = "event_test_market"
        new_market.trading_pairs = ["BTC-USDT"]
        new_market.tracking_states = {}  # Empty dict is JSON serializable
        new_market.add_trade_fills_from_market_recorder = MagicMock()
        new_market.add_exchange_order_ids_from_market_recorder = MagicMock()
        new_market.add_listener = MagicMock()
        new_market.remove_listener = MagicMock()

        # Add the market
        recorder.add_market(new_market)

        # Verify all event pairs were registered
        expected_event_types = [pair[0] for pair in recorder._event_pairs]
        expected_forwarders = [pair[1] for pair in recorder._event_pairs]

        # Check that add_listener was called for each event pair
        self.assertEqual(len(recorder._event_pairs), new_market.add_listener.call_count)

        # Verify the correct event types and forwarders were registered
        add_listener_calls = new_market.add_listener.call_args_list
        for i, call in enumerate(add_listener_calls):
            event_type, forwarder = call[0]
            self.assertIn(event_type, expected_event_types)
            self.assertIn(forwarder, expected_forwarders)

        # Now remove the market
        recorder.remove_market(new_market)

        # Verify all event pairs were unregistered
        self.assertEqual(len(recorder._event_pairs), new_market.remove_listener.call_count)

        # Verify the correct event types and forwarders were unregistered
        remove_listener_calls = new_market.remove_listener.call_args_list
        for i, call in enumerate(remove_listener_calls):
            event_type, forwarder = call[0]
            self.assertIn(event_type, expected_event_types)
            self.assertIn(forwarder, expected_forwarders)

    def test_add_market_integration_with_event_processing(self):
        """Test that dynamically added markets can process events correctly."""
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name,
            market_data_collection=MarketDataCollectionConfigMap(
                market_data_collection_enabled=False,
                market_data_collection_interval=60,
                market_data_collection_depth=20,
            ),
        )

        # Create a new mock market
        new_market = MagicMock()
        new_market.name = "integration_test_market"
        new_market.display_name = "integration_test_market"
        new_market.trading_pairs = ["BTC-USDT"]
        new_market.tracking_states = {}  # Empty dict is JSON serializable
        new_market.add_trade_fills_from_market_recorder = MagicMock()
        new_market.add_exchange_order_ids_from_market_recorder = MagicMock()
        new_market.add_listener = MagicMock()
        new_market.remove_listener = MagicMock()

        # Add the market
        recorder.add_market(new_market)

        # Simulate an order creation event on the new market
        create_event = BuyOrderCreatedEvent(
            timestamp=int(time.time()),
            type=OrderType.LIMIT,
            trading_pair="BTC-USDT",
            amount=Decimal(0.1),
            price=Decimal(50000),
            order_id="NEW_MARKET_OID1",
            creation_timestamp=time.time(),
            exchange_order_id="NEW_MARKET_EOID1",
        )

        # Process the event through the recorder
        recorder._did_create_order(MarketEvent.BuyOrderCreated.value, new_market, create_event)

        # Verify the order was recorded in the database
        with self.manager.get_new_session() as session:
            query = session.query(Order).filter(Order.id == "NEW_MARKET_OID1")
            orders = query.all()

        self.assertEqual(1, len(orders))
        self.assertEqual("integration_test_market", orders[0].market)
        self.assertEqual("BTC-USDT", orders[0].symbol)
        self.assertEqual("NEW_MARKET_OID1", orders[0].id)
