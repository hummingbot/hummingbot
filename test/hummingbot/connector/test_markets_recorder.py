import time
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import SQLConnectionManager, SQLConnectionType
from hummingbot.model.trade_fill import TradeFill


class MockExchange(ExchangeBase):
    tracking_states = dict()


class MarketsRecorderTests(TestCase):

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

        self.market = MockExchange(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        self.market._set_current_timestamp(1640000000.0)
        self.market.tracking_states = {}

        engine_mock.return_value = create_engine("sqlite:///:memory:")
        self.manager = SQLConnectionManager(
            ClientConfigAdapter(ClientConfigMap()), SQLConnectionType.TRADE_FILLS, db_name="test_DB"
        )

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
            strategy_name=self.strategy_name
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

        recorder._did_create_order(MarketEvent.BuyOrderCreated.value, self.market, event)

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
            strategy_name=self.strategy_name
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

        recorder._did_create_order(MarketEvent.SellOrderCreated.value, self.market, event)

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
            strategy_name=self.strategy_name
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

        recorder._did_create_order(MarketEvent.BuyOrderCreated.value, self.market, create_event)

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

        recorder._did_fill_order(MarketEvent.OrderFilled.value, self.market, fill_event)

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
            creation_timestamp=1640001112.223,
            exchange_order_id="EOID1",
        )

        recorder._did_create_order(MarketEvent.BuyOrderCreated.value, self.market, create_event)

        complete_event = BuyOrderCompletedEvent(
            timestamp=1642020000,
            order_id=create_event.order_id,
            base_asset=self.base,
            quote_asset=self.quote,
            base_asset_amount=create_event.amount,
            quote_asset_amount=create_event.amount * create_event.price,
            order_type=create_event.type)

        recorder._did_complete_order(MarketEvent.BuyOrderCompleted.value, self.market, complete_event)

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

    def test_save_market_states_w_market_states(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self.market],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name
        )

        order = InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.223,
            price=Decimal("1.0"),
        )

        self.market.tracking_states = {order.client_order_id: order.to_json()}

        with patch.object(MarketsRecorder, 'get_market_states') as get_market_states:
            get_market_states.return_value = None
            with self.manager.get_new_session() as session:
                recorder.save_market_states(self.config_file_path, self.market, session)
                query = session.query(MarketState)
                states = query.all()

        self.assertEqual(self.config_file_path, states[0].config_file_path)
        self.assertEqual(True, 'OID1' in states[0].saved_state.keys())
        self.assertEqual(order.creation_timestamp, states[0].saved_state['OID1']['creation_timestamp'])

    def test_save_market_states_wo_market_states(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self.market],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name
        )

        order = InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            creation_timestamp=1640001112.223,
            price=Decimal("1.0"),
        )

        self.market.tracking_states = {order.client_order_id: order.to_json()}

        market_states = MarketState(id='1', config_file_path='test_config', market='MockExchange',
                                    timestamp=1657227811659, saved_state={})

        with patch.object(MarketsRecorder, 'get_market_states') as get_market_states:
            get_market_states.return_value = market_states
            with self.manager.get_new_session() as session:
                recorder.save_market_states(self.config_file_path, self.market, session)

        get_market_states.assert_called_with(self.config_file_path, self.market, session=session)
        self.assertNotEqual(1657227811659, market_states.timestamp)
        self.assertEqual(True, 'OID1' in market_states.saved_state.keys())
        self.assertEqual(order.creation_timestamp, market_states.saved_state['OID1']['creation_timestamp'])

    def test_get_market_states(self):
        recorder = MarketsRecorder(
            sql=self.manager,
            markets=[self.market],
            config_file_path=self.config_file_path,
            strategy_name=self.strategy_name
        )

        with self.manager.get_new_session() as session:
            with session.begin():
                ms = MarketState(id='1',
                                 config_file_path='test_config',
                                 market='MockExchange',
                                 timestamp=1657227811659,
                                 saved_state={
                                     'OID1': {'client_order_id': 'OID1', 'exchange_order_id': 'EOID1',
                                              'trading_pair': 'COINALPHA-HBOT', 'order_type': 'LIMIT',
                                              'trade_type': 'BUY',
                                              'price': '1.0', 'amount': '1000.0', 'executed_amount_base': '0',
                                              'executed_amount_quote': '0', 'last_state': '0', 'leverage': '1',
                                              'position': 'NIL',
                                              'creation_timestamp': 1640001112.223, 'order_fills': {}}})
                session.add(ms)

            market_state = recorder.get_market_states(self.config_file_path, self.market, session)

        self.assertEqual(self.config_file_path, market_state.config_file_path)
        self.assertEqual(True, 'OID1' in market_state.saved_state.keys())
        self.assertEqual(1640001112.223, market_state.saved_state['OID1']['creation_timestamp'])
