#!/usr/bin/env python

from sqlalchemy.orm import Session
import time
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
    Union
)

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

    def _did_create_order(self,
                          event_tag: int,
                          market: MarketBase,
                          evt: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        session: Session = self.session
        base_asset, quote_asset = market.split_symbol(evt.symbol)
        timestamp: int = self.db_timestamp
        event_type: MarketEvent = self.market_event_tag_map[event_tag]
        order_record: Order = Order(config_file_path=self._config_file_path,
                                    strategy=self._strategy_name,
                                    market=market.name,
                                    symbol=evt.symbol,
                                    base_asset=base_asset,
                                    quote_asset=quote_asset,
                                    creation_timestamp=timestamp,
                                    order_type=evt.type.name,
                                    amount=evt.amount,
                                    price=evt.price)
        order_status: OrderStatus = OrderStatus(order=order_record,
                                                timestamp=timestamp,
                                                status=event_type.name)
        session.add(order_record)
        session.add(order_status)
        session.commit()

    def _did_fill_order(self,
                        event_tag: int,
                        market: MarketBase,
                        evt: OrderFilledEvent):
        session: Session = self.session
        base_asset, quote_asset = market.split_symbol(evt.symbol)
        timestamp: int = self.db_timestamp
        event_type: MarketEvent = self.market_event_tag_map[event_tag]
        order_id: str = evt.order_id

        # Try to find the order record, and then add an order status entry and trade fill entry.
        order_record: Optional[Order] = session.query(Order).filter(Order.id == order_id).one_or_none()
        if order_record is not None:
            order_status: OrderStatus = OrderStatus(order_id=order_id,
                                                    timestamp=timestamp,
                                                    status=event_type.name)
            trade_fill_record: TradeFill = TradeFill(config_file_path=self.config_file_path,
                                                     strategy=self.strategy_name,
                                                     market=market.name,
                                                     symbol=evt.symbol,
                                                     base_asset=base_asset,
                                                     quote_asset=quote_asset,
                                                     timestamp=timestamp,
                                                     order_id=order_id,
                                                     trade_type=evt.trade_type.name,
                                                     order_type=evt.order_type.name,
                                                     price=evt.price,
                                                     amount=evt.amount,
                                                     trade_fee=TradeFee.to_json(evt.trade_fee)
                                                     )
            session.add(order_status)
            session.add(trade_fill_record)
            session.commit()
        else:
            session.rollback()

    def _update_order_status(self, event_tag: int, evt: Union[OrderCancelledEvent,
                                                              MarketOrderFailureEvent,
                                                              BuyOrderCompletedEvent,
                                                              SellOrderCompletedEvent,
                                                              OrderExpiredEvent]):
        session: Session = self.session
        timestamp: int = self.db_timestamp
        event_type: MarketEvent = self.market_event_tag_map[event_tag]
        order_id: str = evt.order_id
        order_record: Optional[Order] = session.query(Order).filter(Order.id == order_id).one_or_none()

        if order_record is not None:
            order_status: OrderStatus = OrderStatus(order_id=order_id,
                                                    timestamp=timestamp,
                                                    status=event_type.name)
            session.add(order_status)
            session.commit()
        else:
            session.rollback()

    def _did_cancel_order(self,
                          event_tag: int,
                          _: MarketBase,
                          evt: OrderCancelledEvent):
        self._update_order_status(event_tag, evt)

    def _did_fail_order(self,
                        event_tag: int,
                        _: MarketBase,
                        evt: MarketOrderFailureEvent):
        self._update_order_status(event_tag, evt)

    def _did_complete_order(self,
                            event_tag: int,
                            _: MarketBase,
                            evt: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        self._update_order_status(event_tag, evt)

    def _did_expire_order(self,
                          event_tag: int,
                          _: MarketBase,
                          evt: OrderExpiredEvent):
        self._update_order_status(event_tag, evt)
