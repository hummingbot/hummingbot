import asyncio
import os.path
import threading
import time
from decimal import Decimal
from shutil import move
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

import pandas as pd
from sqlalchemy.orm import Query, Session

from hummingbot import data_path
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.utils import TradeFillOrderDetails
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    FundingPaymentCompletedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    OrderFilledEvent,
    RangePositionInitiatedEvent,
    RangePositionUpdatedEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.model.funding_payment import FundingPayment
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.order_status import OrderStatus
from hummingbot.model.range_position import RangePosition
from hummingbot.model.range_position_update import RangePositionUpdate
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.model.trade_fill import TradeFill


class MarketsRecorder:
    market_event_tag_map: Dict[int, MarketEvent] = {
        event_obj.value: event_obj
        for event_obj in MarketEvent.__members__.values()
    }

    def __init__(self,
                 sql: SQLConnectionManager,
                 markets: List[ConnectorBase],
                 config_file_path: str,
                 strategy_name: str):
        if threading.current_thread() != threading.main_thread():
            raise EnvironmentError("MarketsRecorded can only be initialized from the main thread.")

        self._ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self._sql_manager: SQLConnectionManager = sql
        self._markets: List[ConnectorBase] = markets
        self._config_file_path: str = config_file_path
        self._strategy_name: str = strategy_name
        # Internal collection of trade fills in connector will be used for remote/local history reconciliation
        for market in self._markets:
            trade_fills = self.get_trades_for_config(self._config_file_path, 2000)
            market.add_trade_fills_from_market_recorder({TradeFillOrderDetails(tf.market,
                                                                               tf.exchange_trade_id,
                                                                               tf.symbol) for tf in trade_fills})

            exchange_order_ids = self.get_orders_for_config_and_market(self._config_file_path, market, True, 2000)
            market.add_exchange_order_ids_from_market_recorder({o.exchange_order_id: o.id for o in exchange_order_ids})

        self._create_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_create_order)
        self._fill_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_fill_order)
        self._cancel_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_cancel_order)
        self._fail_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_fail_order)
        self._complete_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_complete_order)
        self._expire_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_expire_order)
        self._funding_payment_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(
            self._did_complete_funding_payment)
        self._intiate_range_position_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(
            self._did_initiate_range_position)
        self._update_range_position_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(
            self._did_update_range_position)

        self._event_pairs: List[Tuple[MarketEvent, SourceInfoEventForwarder]] = [
            (MarketEvent.BuyOrderCreated, self._create_order_forwarder),
            (MarketEvent.SellOrderCreated, self._create_order_forwarder),
            (MarketEvent.OrderFilled, self._fill_order_forwarder),
            (MarketEvent.OrderCancelled, self._cancel_order_forwarder),
            (MarketEvent.OrderFailure, self._fail_order_forwarder),
            (MarketEvent.BuyOrderCompleted, self._complete_order_forwarder),
            (MarketEvent.SellOrderCompleted, self._complete_order_forwarder),
            (MarketEvent.OrderExpired, self._expire_order_forwarder),
            (MarketEvent.FundingPaymentCompleted, self._funding_payment_forwarder),
            (MarketEvent.RangePositionInitiated, self._intiate_range_position_forwarder),
            (MarketEvent.RangePositionUpdated, self._update_range_position_forwarder),
        ]

    @property
    def sql_manager(self) -> SQLConnectionManager:
        return self._sql_manager

    @property
    def config_file_path(self) -> str:
        return self._config_file_path

    @property
    def strategy_name(self) -> str:
        return self._strategy_name

    @property
    def db_timestamp(self) -> int:
        return int(time.time() * 1e3)

    def start(self):
        for market in self._markets:
            for event_pair in self._event_pairs:
                market.add_listener(event_pair[0], event_pair[1])

    def stop(self):
        for market in self._markets:
            for event_pair in self._event_pairs:
                market.remove_listener(event_pair[0], event_pair[1])

    def get_orders_for_config_and_market(self, config_file_path: str, market: ConnectorBase,
                                         with_exchange_order_id_present: Optional[bool] = False,
                                         number_of_rows: Optional[int] = None) -> List[Order]:
        with self._sql_manager.get_new_session() as session:
            filters = [Order.config_file_path == config_file_path,
                       Order.market == market.display_name]
            if with_exchange_order_id_present:
                filters.append(Order.exchange_order_id.isnot(None))
            query: Query = (session
                            .query(Order)
                            .filter(*filters)
                            .order_by(Order.creation_timestamp))
            if number_of_rows is None:
                return query.all()
            else:
                return query.limit(number_of_rows).all()

    def get_trades_for_config(self, config_file_path: str, number_of_rows: Optional[int] = None) -> List[TradeFill]:
        with self._sql_manager.get_new_session() as session:
            query: Query = (session
                            .query(TradeFill)
                            .filter(TradeFill.config_file_path == config_file_path)
                            .order_by(TradeFill.timestamp.desc()))
            if number_of_rows is None:
                return query.all()
            else:
                return query.limit(number_of_rows).all()

    def save_market_states(self, config_file_path: str, market: ConnectorBase, session: Session):
        market_states: Optional[MarketState] = self.get_market_states(config_file_path, market, session=session)
        timestamp: int = self.db_timestamp

        if market_states is not None:
            market_states.saved_state = market.tracking_states
            market_states.timestamp = timestamp
        else:
            market_states = MarketState(config_file_path=config_file_path,
                                        market=market.display_name,
                                        timestamp=timestamp,
                                        saved_state=market.tracking_states)
            session.add(market_states)

    def restore_market_states(self, config_file_path: str, market: ConnectorBase):
        with self._sql_manager.get_new_session() as session:
            market_states: Optional[MarketState] = self.get_market_states(config_file_path, market, session=session)

            if market_states is not None:
                market.restore_tracking_states(market_states.saved_state)

    def get_market_states(self,
                          config_file_path: str,
                          market: ConnectorBase,
                          session: Session) -> Optional[MarketState]:
        query: Query = (session
                        .query(MarketState)
                        .filter(MarketState.config_file_path == config_file_path,
                                MarketState.market == market.display_name))
        market_states: Optional[MarketState] = query.one_or_none()
        return market_states

    def _did_create_order(self,
                          event_tag: int,
                          market: ConnectorBase,
                          evt: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._did_create_order, event_tag, market, evt)
            return

        base_asset, quote_asset = evt.trading_pair.split("-")
        timestamp: int = self.db_timestamp
        event_type: MarketEvent = self.market_event_tag_map[event_tag]

        with self._sql_manager.get_new_session() as session:
            with session.begin():
                order_record: Order = Order(id=evt.order_id,
                                            config_file_path=self._config_file_path,
                                            strategy=self._strategy_name,
                                            market=market.display_name,
                                            symbol=evt.trading_pair,
                                            base_asset=base_asset,
                                            quote_asset=quote_asset,
                                            creation_timestamp=timestamp,
                                            order_type=evt.type.name,
                                            amount=Decimal(evt.amount),
                                            leverage=evt.leverage if evt.leverage else 1,
                                            price=Decimal(evt.price) if evt.price == evt.price else Decimal(0),
                                            position=evt.position if evt.position else "NILL",
                                            last_status=event_type.name,
                                            last_update_timestamp=timestamp,
                                            exchange_order_id=evt.exchange_order_id)
                order_status: OrderStatus = OrderStatus(order=order_record,
                                                        timestamp=timestamp,
                                                        status=event_type.name)
                session.add(order_record)
                session.add(order_status)
                market.add_exchange_order_ids_from_market_recorder({evt.exchange_order_id: evt.order_id})
                self.save_market_states(self._config_file_path, market, session=session)

    def _did_fill_order(self,
                        event_tag: int,
                        market: ConnectorBase,
                        evt: OrderFilledEvent):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._did_fill_order, event_tag, market, evt)
            return

        base_asset, quote_asset = evt.trading_pair.split("-")
        timestamp: int = self.db_timestamp
        event_type: MarketEvent = self.market_event_tag_map[event_tag]
        order_id: str = evt.order_id

        with self._sql_manager.get_new_session() as session:
            with session.begin():
                # Try to find the order record, and update it if necessary.
                order_record: Optional[Order] = session.query(Order).filter(Order.id == order_id).one_or_none()
                if order_record is not None:
                    order_record.last_status = event_type.name
                    order_record.last_update_timestamp = timestamp

                # Order status and trade fill record should be added even if the order record is not found, because it's
                # possible for fill event to come in before the order created event for market orders.
                order_status: OrderStatus = OrderStatus(order_id=order_id,
                                                        timestamp=timestamp,
                                                        status=event_type.name)

                trade_fill_record: TradeFill = TradeFill(config_file_path=self.config_file_path,
                                                         strategy=self.strategy_name,
                                                         market=market.display_name,
                                                         symbol=evt.trading_pair,
                                                         base_asset=base_asset,
                                                         quote_asset=quote_asset,
                                                         timestamp=timestamp,
                                                         order_id=order_id,
                                                         trade_type=evt.trade_type.name,
                                                         order_type=evt.order_type.name,
                                                         price=Decimal(evt.price) if evt.price == evt.price else Decimal(0),
                                                         amount=Decimal(evt.amount),
                                                         leverage=evt.leverage if evt.leverage else 1,
                                                         trade_fee=evt.trade_fee.to_json(),
                                                         exchange_trade_id=evt.exchange_trade_id,
                                                         position=evt.position if evt.position else "NILL", )
                session.add(order_status)
                session.add(trade_fill_record)
                self.save_market_states(self._config_file_path, market, session=session)

                market.add_trade_fills_from_market_recorder({TradeFillOrderDetails(trade_fill_record.market,
                                                                                   trade_fill_record.exchange_trade_id,
                                                                                   trade_fill_record.symbol)})
                self.append_to_csv(trade_fill_record)

    def _did_complete_funding_payment(self,
                                      event_tag: int,
                                      market: ConnectorBase,
                                      evt: FundingPaymentCompletedEvent):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._did_complete_funding_payment, event_tag, market, evt)
            return

        session: Session = self.session
        timestamp: float = evt.timestamp

        with self._sql_manager.get_new_session() as session:
            with session.begin():
                # Try to find the funding payment has been recorded already.
                payment_record: Optional[FundingPayment] = session.query(FundingPayment).filter(
                    FundingPayment.timestamp == timestamp).one_or_none()
                if payment_record is None:
                    funding_payment_record: FundingPayment = FundingPayment(timestamp=timestamp,
                                                                            config_file_path=self.config_file_path,
                                                                            market=market.display_name,
                                                                            rate=evt.funding_rate,
                                                                            symbol=evt.trading_pair,
                                                                            amount=float(evt.amount))
                    session.add(funding_payment_record)

    @staticmethod
    def _is_primitive_type(obj: object) -> bool:
        return not hasattr(obj, '__dict__')

    @staticmethod
    def _is_protected_method(method_name: str) -> bool:
        return method_name.startswith('_')

    @staticmethod
    def _csv_matches_header(file_path: str, header: tuple) -> bool:
        df = pd.read_csv(file_path, header=None)
        return tuple(df.iloc[0].values) == header

    def append_to_csv(self, trade: TradeFill):
        csv_filename = "trades_" + trade.config_file_path[:-4] + ".csv"
        csv_path = os.path.join(data_path(), csv_filename)

        field_names = ("exchange_trade_id",)  # id field should be first
        field_names += tuple(attr for attr in dir(trade) if (not self._is_protected_method(attr) and
                                                             self._is_primitive_type(getattr(trade, attr)) and
                                                             (attr not in field_names)))
        field_data = tuple(getattr(trade, attr) for attr in field_names)

        # adding extra field "age"
        # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
        age = pd.Timestamp(int(trade.timestamp / 1e3 - int(trade.order_id[-16:]) / 1e6), unit='s').strftime(
            '%H:%M:%S') if "//" not in trade.order_id else "n/a"
        field_names += ("age",)
        field_data += (age,)

        if (os.path.exists(csv_path) and (not self._csv_matches_header(csv_path, field_names))):
            move(csv_path, csv_path[:-4] + '_old_' + pd.Timestamp.utcnow().strftime("%Y%m%d-%H%M%S") + ".csv")

        if not os.path.exists(csv_path):
            df_header = pd.DataFrame([field_names])
            df_header.to_csv(csv_path, mode='a', header=False, index=False)
        df = pd.DataFrame([field_data])
        df.to_csv(csv_path, mode='a', header=False, index=False)

    def _update_order_status(self,
                             event_tag: int,
                             market: ConnectorBase,
                             evt: Union[OrderCancelledEvent,
                                        MarketOrderFailureEvent,
                                        BuyOrderCompletedEvent,
                                        SellOrderCompletedEvent,
                                        OrderExpiredEvent]):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._update_order_status, event_tag, market, evt)
            return

        timestamp: int = self.db_timestamp
        event_type: MarketEvent = self.market_event_tag_map[event_tag]
        order_id: str = evt.order_id

        with self._sql_manager.get_new_session() as session:
            with session.begin():
                order_record: Optional[Order] = session.query(Order).filter(Order.id == order_id).one_or_none()

                if order_record is not None:
                    order_record.last_status = event_type.name
                    order_record.last_update_timestamp = timestamp
                    order_status: OrderStatus = OrderStatus(order_id=order_id,
                                                            timestamp=timestamp,
                                                            status=event_type.name)
                    session.add(order_status)
                    self.save_market_states(self._config_file_path, market, session=session)

    def _did_cancel_order(self,
                          event_tag: int,
                          market: ConnectorBase,
                          evt: OrderCancelledEvent):
        self._update_order_status(event_tag, market, evt)

    def _did_fail_order(self,
                        event_tag: int,
                        market: ConnectorBase,
                        evt: MarketOrderFailureEvent):
        self._update_order_status(event_tag, market, evt)

    def _did_complete_order(self,
                            event_tag: int,
                            market: ConnectorBase,
                            evt: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        self._update_order_status(event_tag, market, evt)

    def _did_expire_order(self,
                          event_tag: int,
                          market: ConnectorBase,
                          evt: OrderExpiredEvent):
        self._update_order_status(event_tag, market, evt)

    def _did_initiate_range_position(self,
                                     event_tag: int,
                                     connector: ConnectorBase,
                                     evt: RangePositionInitiatedEvent):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._did_initiate_range_position, event_tag, connector, evt)
            return

        timestamp: int = self.db_timestamp

        with self._sql_manager.get_new_session() as session:
            with session.begin():
                r_pos: RangePosition = RangePosition(hb_id=evt.hb_id,
                                                     config_file_path=self._config_file_path,
                                                     strategy=self._strategy_name,
                                                     tx_hash=evt.tx_hash,
                                                     connector=connector.display_name,
                                                     trading_pair=evt.trading_pair,
                                                     fee_tier=str(evt.fee_tier),
                                                     lower_price=float(evt.lower_price),
                                                     upper_price=float(evt.upper_price),
                                                     base_amount=float(evt.base_amount),
                                                     quote_amount=float(evt.quote_amount),
                                                     status=evt.status,
                                                     creation_timestamp=timestamp,
                                                     last_update_timestamp=timestamp)
                session.add(r_pos)
                self.save_market_states(self._config_file_path, connector, session=session)

    def _did_update_range_position(self,
                                   event_tag: int,
                                   connector: ConnectorBase,
                                   evt: RangePositionUpdatedEvent):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._did_update_range_position, event_tag, connector, evt)
            return

        timestamp: int = self.db_timestamp

        with self._sql_manager.get_new_session() as session:
            with session.begin():
                rp_record: Optional[RangePosition] = session.query(RangePosition).filter(
                    RangePosition.hb_id == evt.hb_id).one_or_none()
                if rp_record is not None:
                    rp_update: RangePositionUpdate = RangePositionUpdate(hb_id=evt.hb_id,
                                                                         timestamp=timestamp,
                                                                         tx_hash=evt.tx_hash,
                                                                         token_id=evt.token_id,
                                                                         base_amount=float(evt.base_amount),
                                                                         quote_amount=float(evt.quote_amount),
                                                                         status=evt.status,
                                                                         )
                    session.add(rp_update)
                    self.save_market_states(self._config_file_path, connector, session=session)
