import asyncio
import json
import logging
import os.path
import threading
import time
from decimal import Decimal
from shutil import move
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from sqlalchemy.orm import Query, Session

from hummingbot import data_path
from hummingbot.client.config.client_config_map import MarketDataCollectionConfigMap
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.utils import TradeFillOrderDetails
from hummingbot.core.data_type.common import PriceType
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
    PositionAction,
    RangePositionClosedEvent,
    RangePositionFeeCollectedEvent,
    RangePositionLiquidityAddedEvent,
    RangePositionLiquidityRemovedEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.model.controllers import Controllers
from hummingbot.model.executors import Executors
from hummingbot.model.funding_payment import FundingPayment
from hummingbot.model.market_data import MarketData
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.order_status import OrderStatus
from hummingbot.model.range_position_collected_fees import RangePositionCollectedFees
from hummingbot.model.range_position_update import RangePositionUpdate
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.model.trade_fill import TradeFill
from hummingbot.strategy_v2.controllers.controller_base import ControllerConfigBase
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class MarketsRecorder:
    _logger = None
    _shared_instance: "MarketsRecorder" = None
    market_event_tag_map: Dict[int, MarketEvent] = {
        event_obj.value: event_obj
        for event_obj in MarketEvent.__members__.values()
    }

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    def get_instance(cls, *args, **kwargs) -> "MarketsRecorder":
        if cls._shared_instance is None:
            cls._shared_instance = MarketsRecorder(*args, **kwargs)
        return cls._shared_instance

    def __init__(self,
                 sql: SQLConnectionManager,
                 markets: List[ConnectorBase],
                 config_file_path: str,
                 strategy_name: str,
                 market_data_collection: MarketDataCollectionConfigMap):
        if threading.current_thread() != threading.main_thread():
            raise EnvironmentError("MarketsRecorded can only be initialized from the main thread.")

        self._ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self._sql_manager: SQLConnectionManager = sql
        self._markets: List[ConnectorBase] = markets
        self._config_file_path: str = config_file_path
        self._strategy_name: str = strategy_name
        self._market_data_collection_config: MarketDataCollectionConfigMap = market_data_collection
        self._market_data_collection_task: Optional[asyncio.Task] = None
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
        self._update_range_position_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(
            self._did_update_range_position)
        self._close_range_position_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(
            self._did_close_position)

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
            (MarketEvent.RangePositionLiquidityAdded, self._update_range_position_forwarder),
            (MarketEvent.RangePositionLiquidityRemoved, self._update_range_position_forwarder),
            (MarketEvent.RangePositionFeeCollected, self._update_range_position_forwarder),
            (MarketEvent.RangePositionClosed, self._close_range_position_forwarder),
        ]
        MarketsRecorder._shared_instance = self

    def _start_market_data_recording(self):
        self._market_data_collection_task = self._ev_loop.create_task(self._record_market_data())

    async def _record_market_data(self):
        while True:
            try:
                if all(ex.ready for ex in self._markets):
                    with self._sql_manager.get_new_session() as session:
                        with session.begin():
                            for market in self._markets:
                                exchange = market.display_name
                                for trading_pair in market.trading_pairs:
                                    mid_price = market.get_price_by_type(trading_pair, PriceType.MidPrice)
                                    best_bid = market.get_price_by_type(trading_pair, PriceType.BestBid)
                                    best_ask = market.get_price_by_type(trading_pair, PriceType.BestAsk)
                                    order_book = market.get_order_book(trading_pair)
                                    depth = self._market_data_collection_config.market_data_collection_depth + 1
                                    market_data = MarketData(
                                        timestamp=self.db_timestamp,
                                        exchange=exchange,
                                        trading_pair=trading_pair,
                                        mid_price=mid_price,
                                        best_bid=best_bid,
                                        best_ask=best_ask,
                                        order_book={
                                            "bid": list(order_book.bid_entries())[:depth],
                                            "ask": list(order_book.ask_entries())[:depth]}
                                    )
                                    session.add(market_data)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error("Unexpected error while recording market data.", e)
            finally:
                await self._sleep(self._market_data_collection_config.market_data_collection_interval)

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
        if self._market_data_collection_config.market_data_collection_enabled:
            self._start_market_data_recording()

    def stop(self):
        for market in self._markets:
            for event_pair in self._event_pairs:
                market.remove_listener(event_pair[0], event_pair[1])
        if self._market_data_collection_task is not None:
            self._market_data_collection_task.cancel()

    def store_or_update_executor(self, executor):
        with self._sql_manager.get_new_session() as session:
            existing_executor = session.query(Executors).filter(Executors.id == executor.config.id).one_or_none()

            if existing_executor:
                # Update existing executor
                for attr, value in vars(executor).items():
                    setattr(existing_executor, attr, value)
            else:
                # Insert new executor
                serialized_config = executor.executor_info.json()
                new_executor = Executors(**json.loads(serialized_config))
                session.add(new_executor)
            session.commit()

    def store_controller_config(self, controller_config: ControllerConfigBase):
        with self._sql_manager.get_new_session() as session:
            config = json.loads(controller_config.json())
            base_columns = ["id", "timestamp", "type"]
            controller = Controllers(id=config["id"],
                                     timestamp=time.time(),
                                     type=config["controller_type"],
                                     config={k: v for k, v in config.items() if k not in base_columns})
            session.add(controller)
            session.commit()

    def get_executors_by_ids(self, executor_ids: List[str]):
        with self._sql_manager.get_new_session() as session:
            executors = session.query(Executors).filter(Executors.id.in_(executor_ids)).all()
            return executors

    def get_executors_by_controller(self, controller_id: str = None) -> List[ExecutorInfo]:
        with self._sql_manager.get_new_session() as session:
            executors = session.query(Executors).filter(Executors.controller_id == controller_id).all()
            return [executor.to_executor_info() for executor in executors]

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
        timestamp = int(evt.creation_timestamp * 1e3)
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
                                            position=evt.position if evt.position else PositionAction.NIL.value,
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
        timestamp: int = int(evt.timestamp * 1e3) if evt.timestamp is not None else self.db_timestamp
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
                try:
                    fee_in_quote = evt.trade_fee.fee_amount_in_token(
                        trading_pair=evt.trading_pair,
                        price=evt.price,
                        order_amount=evt.amount,
                        token=quote_asset,
                        exchange=market
                    )
                except Exception as e:
                    self.logger().error(f"Error calculating fee in quote: {e}, will be stored in the DB as 0.")
                    fee_in_quote = 0
                trade_fill_record: TradeFill = TradeFill(
                    config_file_path=self.config_file_path,
                    strategy=self.strategy_name,
                    market=market.display_name,
                    symbol=evt.trading_pair,
                    base_asset=base_asset,
                    quote_asset=quote_asset,
                    timestamp=timestamp,
                    order_id=order_id,
                    trade_type=evt.trade_type.name,
                    order_type=evt.order_type.name,
                    price=evt.price,
                    amount=evt.amount,
                    leverage=evt.leverage if evt.leverage else 1,
                    trade_fee=evt.trade_fee.to_json(),
                    trade_fee_in_quote=fee_in_quote,
                    exchange_trade_id=evt.exchange_trade_id,
                    position=evt.position if evt.position else PositionAction.NIL.value,
                )
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
    def _csv_matches_header(file_path: str, header: tuple) -> bool:
        df = pd.read_csv(file_path, header=None)
        return tuple(df.iloc[0].values) == header

    def append_to_csv(self, trade: TradeFill):
        csv_filename = "trades_" + trade.config_file_path[:-4] + ".csv"
        csv_path = os.path.join(data_path(), csv_filename)

        field_names = tuple(trade.attribute_names_for_file_export())
        field_data = tuple(getattr(trade, attr) for attr in field_names)

        # adding extra field "age"
        # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
        age = pd.Timestamp(int((trade.timestamp * 1e-3) - (trade.order.creation_timestamp * 1e-3)), unit='s').strftime(
            '%H:%M:%S') if (trade.order is not None and "//" not in trade.order_id) else "n/a"
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

    def _did_update_range_position(self,
                                   event_tag: int,
                                   connector: ConnectorBase,
                                   evt: Union[RangePositionLiquidityAddedEvent, RangePositionLiquidityRemovedEvent, RangePositionFeeCollectedEvent]):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._did_update_range_position, event_tag, connector, evt)
            return

        timestamp: int = self.db_timestamp

        with self._sql_manager.get_new_session() as session:
            with session.begin():
                rp_update: RangePositionUpdate = RangePositionUpdate(hb_id=evt.order_id,
                                                                     timestamp=timestamp,
                                                                     tx_hash=evt.exchange_order_id,
                                                                     token_id=evt.token_id,
                                                                     trade_fee=evt.trade_fee.to_json())
                session.add(rp_update)
                self.save_market_states(self._config_file_path, connector, session=session)

    def _did_close_position(self,
                            event_tag: int,
                            connector: ConnectorBase,
                            evt: RangePositionClosedEvent):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._did_close_position, event_tag, connector, evt)
            return

        with self._sql_manager.get_new_session() as session:
            with session.begin():
                rp_fees: RangePositionCollectedFees = RangePositionCollectedFees(config_file_path=self._config_file_path,
                                                                                 strategy=self._strategy_name,
                                                                                 token_id=evt.token_id,
                                                                                 token_0=evt.token_0,
                                                                                 token_1=evt.token_1,
                                                                                 claimed_fee_0=Decimal(evt.claimed_fee_0),
                                                                                 claimed_fee_1=Decimal(evt.claimed_fee_1))
                session.add(rp_fees)
                self.save_market_states(self._config_file_path, connector, session=session)

    @staticmethod
    async def _sleep(delay):
        """
        A wrapper function that facilitates patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)
