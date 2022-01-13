import time
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine

from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
)
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import SQLConnectionManager, SQLConnectionType
from hummingbot.model.trade_fill import TradeFill


class MarketsRecorderTests(TestCase):

    @patch("hummingbot.model.sql_connection_manager.SQLConnectionManager.get_db_engine")
    def setUp(self, engine_mock) -> None:
        super().setUp()
        self.display_name = "test_market"
        self.config_file_path = "test_config"
        self.strategy_name = "test_strategy"

        self.symbol = "COINALPHAHBOT"
        self.base = "COINALPHA"
        self.quote = "HBOT"
        self.trading_pair = f"{self.base}-{self.quote}"

        engine_mock.return_value = create_engine("sqlite:///:memory:")
        self.manager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_name="test_DB")

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
            strategy_name=self.strategy_name
        )

        self.assertEqual(self.manager, recorder.sql_manager)
        self.assertEqual(self.config_file_path, recorder.config_file_path)
        self.assertEqual(self.strategy_name, recorder.strategy_name)

    def test_get_trade_for_config(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name
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
                    position="NILL")
                session.add(trade_fill_record)

            fill_id = trade_fill_record.exchange_trade_id

        trades = recorder.get_trades_for_config("test_config")
        self.assertEqual(1, len(trades))
        self.assertEqual(fill_id, trades[0].exchange_trade_id)

    def test_create_order_event_creates_order_record(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name
        )

        event = BuyOrderCreatedEvent(
            timestamp=int(time.time()),
            type=OrderType.LIMIT,
            trading_pair=self.trading_pair,
            amount=Decimal(1),
            price=Decimal(1000),
            order_id="OID1",
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
        self.assertEqual(1, len(order_status))
        self.assertEqual(MarketEvent.BuyOrderCreated.name, order_status[0].status)
        self.assertEqual(0, len(trade_fills))

    def test_create_order_and_process_fill(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name
        )

        create_event = BuyOrderCreatedEvent(
            timestamp=1642010000,
            type=OrderType.LIMIT,
            trading_pair=self.trading_pair,
            amount=Decimal(1),
            price=Decimal(1000),
            order_id="OID1-1642010000000000",
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
            exchange_trade_id=create_event.exchange_order_id
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
            strategy_name=self.strategy_name
        )

        create_event = BuyOrderCreatedEvent(
            timestamp=1642010000,
            type=OrderType.LIMIT,
            trading_pair=self.trading_pair,
            amount=Decimal(1),
            price=Decimal(1000),
            order_id="OID1-1642010000000000",
            exchange_order_id="EOID1",
        )

        recorder._did_create_order(MarketEvent.BuyOrderCreated.value, self, create_event)

        complete_event = BuyOrderCompletedEvent(
            timestamp=1642020000,
            order_id=create_event.order_id,
            base_asset=self.base,
            quote_asset=self.quote,
            fee_asset=self.base,
            base_asset_amount=create_event.amount,
            quote_asset_amount=create_event.amount * create_event.price,
            fee_amount=Decimal(0),
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
