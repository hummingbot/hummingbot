#!/usr/bin/env python

import os.path
import pandas as pd
import asyncio
from sqlalchemy.orm import (
    Session,
    Query
)
import time
import threading
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
    Union
)

from hummingbot import data_path
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderFilledEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    MarketEvent,
    TradeFee
)
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.market.market_base import MarketBase
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.order_status import OrderStatus
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.model.trade_fill import TradeFill


class MarketsRecorder:
    market_event_tag_map: Dict[int, MarketEvent] = {
        event_obj.value: event_obj
        for event_obj in MarketEvent.__members__.values()
    }

    def __init__(self,
                 sql: SQLConnectionManager,
                 markets: List[MarketBase],
                 config_file_path: str,
                 strategy_name: str):
        if threading.current_thread() != threading.main_thread():
            raise EnvironmentError("MarketsRecorded can only be initialized from the main thread.")

        self._ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self._sql: SQLConnectionManager = sql
        self._markets: List[MarketBase] = markets
        self._config_file_path: str = config_file_path
        self._strategy_name: str = strategy_name

        self._create_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_create_order)
        self._fill_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_fill_order)
        self._cancel_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_cancel_order)
        self._fail_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_fail_order)
        self._complete_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_complete_order)
        self._expire_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_expire_order)

        self._event_pairs: List[Tuple[MarketEvent, SourceInfoEventForwarder]] = [
            (MarketEvent.BuyOrderCreated, self._create_order_forwarder),
            (MarketEvent.SellOrderCreated, self._create_order_forwarder),
            (MarketEvent.OrderFilled, self._fill_order_forwarder),
            (MarketEvent.OrderCancelled, self._cancel_order_forwarder),
            (MarketEvent.OrderFailure, self._fail_order_forwarder),
            (MarketEvent.BuyOrderCompleted, self._complete_order_forwarder),
            (MarketEvent.SellOrderCompleted, self._complete_order_forwarder),
            (MarketEvent.OrderExpired, self._expire_order_forwarder)
        ]

    @property
    def sql(self) -> SQLConnectionManager:
        return self._sql

    @property
    def session(self) -> Session:
        return self._sql.get_shared_session()

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

    def get_orders_for_config_and_market(self, config_file_path: str, market: MarketBase) -> List[Order]:
        session: Session = self.session
        query: Query = (session
                        .query(Order)
                        .filter(Order.config_file_path == config_file_path,
                                Order.market == market.display_name)
                        .order_by(Order.creation_timestamp))
        return query.all()

    def get_trades_for_config(self, config_file_path: str, number_of_rows: Optional[int] = None) -> List[TradeFill]:
        session: Session = self.session
        query: Query = (session
                        .query(TradeFill)
                        .filter(TradeFill.config_file_path == config_file_path)
                        .order_by(TradeFill.timestamp.desc()))
        if number_of_rows is None:
            return query.all()
        else:
            return query.limit(number_of_rows).all()

    def save_market_states(self, config_file_path: str, market: MarketBase, no_commit: bool = False):
        session: Session = self.session
        market_states: Optional[MarketState] = self.get_market_states(config_file_path, market)
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

        if not no_commit:
            session.commit()

    def restore_market_states(self, config_file_path: str, market: MarketBase):
        market_states: Optional[MarketState] = self.get_market_states(config_file_path, market)

        if market_states is not None:
            market.restore_tracking_states(market_states.saved_state)

    def get_market_states(self, config_file_path: str, market: MarketBase) -> Optional[MarketState]:
        session: Session = self.session
        query: Query = (session
                        .query(MarketState)
                        .filter(MarketState.config_file_path == config_file_path,
                                MarketState.market == market.display_name))
        market_states: Optional[MarketState] = query.one_or_none()
        return market_states

    def _did_create_order(self,
                          event_tag: int,
                          market: MarketBase,
                          evt: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._did_create_order, event_tag, market, evt)
            return

        session: Session = self.session
        base_asset, quote_asset = market.split_trading_pair(evt.trading_pair)
        timestamp: int = self.db_timestamp
        event_type: MarketEvent = self.market_event_tag_map[event_tag]
        order_record: Order = Order(id=evt.order_id,
                                    config_file_path=self._config_file_path,
                                    strategy=self._strategy_name,
                                    market=market.display_name,
                                    symbol=evt.trading_pair,
                                    base_asset=base_asset,
                                    quote_asset=quote_asset,
                                    creation_timestamp=timestamp,
                                    order_type=evt.type.name,
                                    amount=float(evt.amount),
                                    price=float(evt.price) if evt.price == evt.price else 0,
                                    last_status=event_type.name,
                                    last_update_timestamp=timestamp)
        order_status: OrderStatus = OrderStatus(order=order_record,
                                                timestamp=timestamp,
                                                status=event_type.name)
        session.add(order_record)
        session.add(order_status)
        self.save_market_states(self._config_file_path, market, no_commit=True)
        session.commit()

    def _did_fill_order(self,
                        event_tag: int,
                        market: MarketBase,
                        evt: OrderFilledEvent):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._did_fill_order, event_tag, market, evt)
            return

        session: Session = self.session
        base_asset, quote_asset = market.split_trading_pair(evt.trading_pair)
        timestamp: int = self.db_timestamp
        event_type: MarketEvent = self.market_event_tag_map[event_tag]
        order_id: str = evt.order_id

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
                                                 price=float(evt.price) if evt.price == evt.price else 0,
                                                 amount=float(evt.amount),
                                                 trade_fee=TradeFee.to_json(evt.trade_fee),
                                                 exchange_trade_id=evt.exchange_trade_id)
        session.add(order_status)
        session.add(trade_fill_record)
        self.save_market_states(self._config_file_path, market, no_commit=True)
        session.commit()
        self.append_to_csv(trade_fill_record)

    def append_to_csv(self, trade: TradeFill):
        csv_file = "trades_" + trade.config_file_path[:-4] + ".csv"
        csv_path = os.path.join(data_path(), csv_file)
        # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
        age = "n/a"
        if "//" not in trade.order_id:
            age = pd.Timestamp(int(trade.timestamp / 1e3 - int(trade.order_id[-16:]) / 1e6), unit='s').strftime('%H:%M:%S')
        if not os.path.exists(csv_path):
            df_header = pd.DataFrame([["Config File", "Strategy", "Exchange", "Timestamp", "Market", "Base", "Quote",
                                       "Trade", "Type", "Price", "Amount", "Fee", "Age", "Order ID", "Exchange Trade ID"]])
            df_header.to_csv(csv_path, mode='a', header=False, index=False)
        df = pd.DataFrame([[trade.config_file_path, trade.strategy, trade.market, trade.timestamp, trade.symbol, trade.base_asset, trade.quote_asset,
                            trade.trade_type, trade.order_type, trade.price, trade.amount, trade.trade_fee, age, trade.order_id, trade.exchange_trade_id]])
        df.to_csv(csv_path, mode='a', header=False, index=False)

    def _update_order_status(self,
                             event_tag: int,
                             market: MarketBase,
                             evt: Union[OrderCancelledEvent,
                                        MarketOrderFailureEvent,
                                        BuyOrderCompletedEvent,
                                        SellOrderCompletedEvent,
                                        OrderExpiredEvent]):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._update_order_status, event_tag, market, evt)
            return

        session: Session = self.session
        timestamp: int = self.db_timestamp
        event_type: MarketEvent = self.market_event_tag_map[event_tag]
        order_id: str = evt.order_id
        order_record: Optional[Order] = session.query(Order).filter(Order.id == order_id).one_or_none()

        if order_record is not None:
            order_record.last_status = event_type.name
            order_record.last_update_timestamp = timestamp
            order_status: OrderStatus = OrderStatus(order_id=order_id,
                                                    timestamp=timestamp,
                                                    status=event_type.name)
            session.add(order_status)
            self.save_market_states(self._config_file_path, market, no_commit=True)
            session.commit()
        else:
            session.rollback()

    def _did_cancel_order(self,
                          event_tag: int,
                          market: MarketBase,
                          evt: OrderCancelledEvent):
        self._update_order_status(event_tag, market, evt)

    def _did_fail_order(self,
                        event_tag: int,
                        market: MarketBase,
                        evt: MarketOrderFailureEvent):
        self._update_order_status(event_tag, market, evt)

    def _did_complete_order(self,
                            event_tag: int,
                            market: MarketBase,
                            evt: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        self._update_order_status(event_tag, market, evt)

    def _did_expire_order(self,
                          event_tag: int,
                          market: MarketBase,
                          evt: OrderExpiredEvent):
        self._update_order_status(event_tag, market, evt)
