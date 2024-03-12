import asyncio
import time
from decimal import Decimal
from typing import Awaitable
from unittest import TestCase
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
from hummingbot.model.market_data import MarketData
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import SQLConnectionManager, SQLConnectionType
from hummingbot.model.trade_fill import TradeFill
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MarketsRecorderTests(TestCase):
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
