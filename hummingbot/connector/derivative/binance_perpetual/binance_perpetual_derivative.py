from collections import defaultdict
from enum import Enum
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from hummingbot.connector.derivative.position import Position

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.estimate_fee import estimate_fee

from async_timeout import timeout

from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_in_flight_order import BinancePerpetualsInFlightOrder

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

import asyncio
import hashlib
import hmac
import time
import logging
import ujson
import websockets
from websockets.exceptions import ConnectionClosed
from decimal import Decimal
from typing import Optional, List, Dict, Any, AsyncIterable
from urllib.parse import urlencode

import aiohttp

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import (
    FundingInfo,
    OrderType,
    TradeType,
    MarketOrderFailureEvent,
    MarketEvent,
    OrderCancelledEvent,
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    FundingPaymentCompletedEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent, PositionSide, PositionMode, PositionAction)
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.asyncio_throttle import Throttler
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_order_book_tracker import BinancePerpetualOrderBookTracker
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_user_stream_tracker import BinancePerpetualUserStreamTracker
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils import convert_from_exchange_trading_pair, convert_to_exchange_trading_pair
from hummingbot.connector.derivative.binance_perpetual.constants import (
    PERPETUAL_BASE_URL,
    TESTNET_BASE_URL,
    DIFF_STREAM_URL,
    TESTNET_STREAM_URL
)
from hummingbot.connector.exchange_base import ExchangeBase, s_decimal_NaN
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.exchange.binance.binance_time import BinanceTime
from hummingbot.connector.perpetual_trading import PerpetualTrading


class MethodType(Enum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
    PUT = "PUT"


bpm_logger = None


BROKER_ID = "x-3QreWesy"


def get_client_order_id(order_side: str, trading_pair: object):
    nonce = get_tracking_nonce()
    symbols: str = trading_pair.split("-")
    base: str = symbols[0].upper()
    quote: str = symbols[1].upper()
    return f"{BROKER_ID}-{order_side.upper()[0]}{base[0]}{base[-1]}{quote[0]}{quote[-1]}{nonce}"


class BinancePerpetualDerivative(ExchangeBase, PerpetualTrading):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated
    MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG = MarketEvent.FundingPaymentCompleted

    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0
    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global bpm_logger
        if bpm_logger is None:
            bpm_logger = logging.getLogger(__name__)
        return bpm_logger

    def __init__(self,
                 binance_perpetual_api_key: str = None,
                 binance_perpetual_api_secret: str = None,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 **domain):
        self._testnet = True if len(domain) > 0 else False
        ExchangeBase.__init__(self)
        PerpetualTrading.__init__(self)
        BinanceTime.get_instance().start()
        self._api_key = binance_perpetual_api_key
        self._api_secret = binance_perpetual_api_secret
        self._trading_required = trading_required
        # self._account_balances = {}
        # self._account_available_balances = {}

        self._base_url = PERPETUAL_BASE_URL if self._testnet is False else TESTNET_BASE_URL
        self._stream_url = DIFF_STREAM_URL if self._testnet is False else TESTNET_STREAM_URL
        self._user_stream_tracker = BinancePerpetualUserStreamTracker(base_url=self._base_url, stream_url=self._stream_url, api_key=self._api_key)
        self._order_book_tracker = BinancePerpetualOrderBookTracker(trading_pairs=trading_pairs, **domain)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._in_flight_orders = {}
        self._order_not_found_records = {}
        self._last_timestamp = 0
        self._trading_rules = {}
        self._trading_pairs = trading_pairs
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._funding_info_polling_task = None
        self._funding_fee_polling_task = None
        self._last_poll_timestamp = 0
        self._throttler = Throttler((10.0, 1.0))
        self._funding_payment_span = [0, 30]

    @property
    def name(self) -> str:
        return "binance_perpetual_testnet" if self._testnet else "binance_perpetual"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def ready(self):
        return all(self.status_dict.values())

    @property
    def in_flight_orders(self) -> Dict[str, BinancePerpetualsInFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self):
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "funding_info": len(self._funding_info) > 0
        }

    @property
    def limit_orders(self):
        return [in_flight_order.to_limit_order() for in_flight_order in self._in_flight_orders.values()]

    def start(self, clock: Clock, timestamp: float):
        super().start(clock, timestamp)

    def stop(self, clock: Clock):
        super().stop(clock)
        BinanceTime.get_instance().stop()

    async def start_network(self):
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        self._funding_info_polling_task = safe_ensure_future(self._funding_info_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
            self._funding_fee_polling_task = safe_ensure_future(self._funding_fee_polling_loop())

    def _stop_network(self):
        # Reset timestamps and _poll_notifier for status_polling_loop
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._poll_notifier = asyncio.Event()

        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
        if self._funding_info_polling_task is not None:
            self._funding_info_polling_task.cancel()
        if self._funding_fee_polling_task is not None:
            self._funding_fee_polling_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = self._funding_info_polling_task = \
            self._funding_fee_polling_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self.request("/fapi/v1/ping")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.LIMIT, OrderType.MARKET]

    # ORDER PLACE AND CANCEL EXECUTIONS ---
    async def create_order(self,
                           trade_type: TradeType,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           position_action: PositionAction,
                           price: Optional[Decimal] = Decimal("NaN")):

        trading_rule: TradingRule = self._trading_rules[trading_pair]
        if position_action not in [PositionAction.OPEN, PositionAction.CLOSE]:
            raise ValueError("Specify either OPEN_POSITION or CLOSE_POSITION position_action.")

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)

        if amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}")

        order_result = None
        api_params = {"symbol": convert_to_exchange_trading_pair(trading_pair),
                      "side": "BUY" if trade_type is TradeType.BUY else "SELL",
                      "type": "LIMIT" if order_type is OrderType.LIMIT else "MARKET",
                      "quantity": f"{amount}",
                      "newClientOrderId": order_id
                      }
        if order_type == OrderType.LIMIT:
            api_params["price"] = f"{price}"
            api_params["timeInForce"] = "GTC"

        if self._position_mode == PositionMode.HEDGE:
            if position_action == PositionAction.OPEN:
                api_params["positionSide"] = "LONG" if trade_type is TradeType.BUY else "SHORT"
            else:
                api_params["positionSide"] = "SHORT" if trade_type is TradeType.BUY else "LONG"

        self.start_tracking_order(order_id, "", trading_pair, trade_type, price, amount, order_type, self._leverage[trading_pair], position_action.name)

        try:
            order_result = await self.request(path="/fapi/v1/order",
                                              params=api_params,
                                              method=MethodType.POST,
                                              add_timestamp = True,
                                              is_signed=True)
            exchange_order_id = str(order_result["orderId"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name.lower()} {trade_type.name.lower()} order {order_id} for "
                                   f"{amount} {trading_pair}.")
                tracked_order.exchange_order_id = exchange_order_id

            event_tag = self.MARKET_BUY_ORDER_CREATED_EVENT_TAG if trade_type is TradeType.BUY \
                else self.MARKET_SELL_ORDER_CREATED_EVENT_TAG
            event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
            self.trigger_event(event_tag,
                               event_class(self.current_timestamp,
                                           order_type,
                                           trading_pair,
                                           amount,
                                           price,
                                           order_id,
                                           leverage=self._leverage[trading_pair],
                                           position=position_action.name))
            return order_result
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting order to Binance Perpetuals for {amount} {trading_pair} "
                f"{'' if order_type is OrderType.MARKET else price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          position_action: PositionAction,
                          price: Optional[Decimal] = s_decimal_NaN):
        return await self.create_order(TradeType.BUY, order_id, trading_pair, amount, order_type, position_action, price)

    def buy(self, trading_pair: str, amount: object, order_type: object = OrderType.MARKET,
            price: object = s_decimal_NaN, **kwargs) -> str:

        t_pair: str = trading_pair
        order_id: str = get_client_order_id("sell", t_pair)
        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, kwargs["position_action"], price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           position_action: PositionAction,
                           price: Optional[Decimal] = s_decimal_NaN):
        return await self.create_order(TradeType.SELL, order_id, trading_pair, amount, order_type, position_action, price)

    def sell(self, trading_pair: str, amount: object, order_type: object = OrderType.MARKET,
             price: object = s_decimal_NaN, **kwargs) -> str:

        t_pair: str = trading_pair
        order_id: str = get_client_order_id("sell", t_pair)
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, kwargs["position_action"], price))
        return order_id

    async def cancel_all(self, timeout_seconds: float):
        incomplete_orders = [order for order in self._in_flight_orders.values() if not order.is_done]
        tasks = [self.execute_cancel(order.trading_pair, order.client_order_id) for order in incomplete_orders]
        order_id_set = set([order.client_order_id for order in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cancel_result in cancellation_results:
                    # TODO: QUESTION --- SHOULD I CHECK FOR THE BinanceAPIException CONSIDERING WE ARE MOVING AWAY FROM BINANCE-CLIENT?
                    if isinstance(cancel_result, dict) and "clientOrderId" in cancel_result:
                        client_order_id = cancel_result.get("clientOrderId")
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                "Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Binance Perpetual. Check API key and network connection."
            )
        failed_cancellations = [CancellationResult(order_id, False) for order_id in order_id_set]
        return successful_cancellations + failed_cancellations

    async def cancel_all_account_orders(self, trading_pair: str):
        try:
            params = {
                "symbol": trading_pair
            }
            response = await self.request(
                path="/fapi/v1/allOpenOrders",
                params=params,
                method=MethodType.DELETE,
                add_timestamp=True,
                is_signed=True
            )
            if response.get("code") == 200:
                for order_id in list(self._in_flight_orders.keys()):
                    self.stop_tracking_order(order_id)
            else:
                raise IOError(f"Error cancelling all account orders. Server Response: {response}")
        except Exception as e:
            self.logger().error("Could not cancel all account orders.")
            raise e

    def cancel(self, trading_pair: str, client_order_id: str):
        safe_ensure_future(self.execute_cancel(trading_pair, client_order_id))
        return client_order_id

    async def execute_cancel(self, trading_pair: str, client_order_id: str):
        try:
            params = {
                "origClientOrderId": client_order_id,
                "symbol": convert_to_exchange_trading_pair(trading_pair)
            }
            response = await self.request(
                path="/fapi/v1/order",
                params=params,
                method=MethodType.DELETE,
                is_signed=True,
                add_timestamp = True,
                return_err=True
            )
            if response.get("code") == -2011 or "Unknown order sent" in response.get("msg", ""):
                self.logger().debug(f"The order {client_order_id} does not exist on Binance Perpetuals. "
                                    f"No cancellation needed.")
                self.stop_tracking_order(client_order_id)
                self.trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                   OrderCancelledEvent(self.current_timestamp, client_order_id))
                return {
                    "origClientOrderId": client_order_id
                }
        except Exception as e:
            self.logger().error(f"Could not cancel order {client_order_id} (on Binance Perp. {trading_pair})")
            raise e
        if response.get("status", None) == "CANCELED":
            self.logger().info(f"Successfully canceled order {client_order_id}")
            self.stop_tracking_order(client_order_id)
            self.trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                               OrderCancelledEvent(self.current_timestamp, client_order_id))
        return response

    def quantize_order_amount(self, trading_pair: str, amount: object, price: object = Decimal(0)):
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        # current_price: object = self.get_price(trading_pair, False)
        notional_size: object
        quantized_amount = ExchangeBase.quantize_order_amount(self, trading_pair, amount)
        if quantized_amount < trading_rule.min_order_size:
            return Decimal(0)
        """
        if price == Decimal(0):
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount
        """

        # TODO: NOTIONAL MIN SIZE DOES NOT EXIST
        # if notional_size < trading_rule.min_notional_size * Decimal("1.01"):
        #     return Decimal(0)

        return quantized_amount

    def get_order_price_quantum(self, trading_pair: str, price: object):
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: object):
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    # ORDER TRACKING ---
    def start_tracking_order(self, order_id: str, exchange_order_id: str, trading_pair: str, trading_type: object,
                             price: object, amount: object, order_type: object, leverage: int, position: str):
        self._in_flight_orders[order_id] = BinancePerpetualsInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trading_type,
            price=price,
            amount=amount,
            leverage=leverage,
            position=position

        )

    def stop_tracking_order(self, order_id: str):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]
        if order_id in self._order_not_found_records:
            del self._order_not_found_records[order_id]

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Binance. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("e")
                if event_type == "ORDER_TRADE_UPDATE":
                    order_message = event_message.get("o")
                    client_order_id = order_message.get("c")

                    # If the order has already been cancelled
                    if client_order_id not in self._in_flight_orders:
                        continue

                    tracked_order = self._in_flight_orders.get(client_order_id)
                    tracked_order.update_with_execution_report(event_message)

                    # Execution Type: Trade => Filled
                    trade_type = TradeType.BUY if order_message.get("S") == "BUY" else TradeType.SELL
                    if order_message.get("X") in ["PARTIALLY_FILLED", "FILLED"]:
                        order_filled_event = OrderFilledEvent(
                            timestamp=event_message.get("E") * 1e-3,
                            order_id=client_order_id,
                            trading_pair=convert_from_exchange_trading_pair(order_message.get("s")),
                            trade_type=trade_type,
                            order_type=OrderType.LIMIT if order_message.get("o") == "LIMIT" else OrderType.MARKET,
                            price=Decimal(order_message.get("L")),
                            amount=Decimal(order_message.get("l")),
                            leverage=self._leverage[convert_from_exchange_trading_pair(order_message.get("s"))],
                            trade_fee=self.get_fee(
                                base_currency=tracked_order.base_asset,
                                quote_currency=tracked_order.quote_asset,
                                order_type=tracked_order.order_type,
                                order_side=trade_type,
                                amount=Decimal(order_message.get("q")),
                                price=Decimal(order_message.get("p"))
                            ),
                            exchange_trade_id=order_message.get("t"),
                            position=tracked_order.position
                        )
                        self.trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

                    if tracked_order.is_done:
                        if not tracked_order.is_failure:
                            event_tag = None
                            event_class = None
                            if trade_type is TradeType.BUY:
                                event_tag = self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG
                                event_class = BuyOrderCompletedEvent
                            else:
                                event_tag = self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG
                                event_class = SellOrderCompletedEvent
                            self.logger().info(f"The {tracked_order.order_type.name.lower()} {trade_type} order {client_order_id} has completed "
                                               f"according to websocket delta.")
                            self.trigger_event(event_tag,
                                               event_class(self.current_timestamp,
                                                           client_order_id,
                                                           tracked_order.base_asset,
                                                           tracked_order.quote_asset,
                                                           (tracked_order.fee_asset or tracked_order.quote_asset),
                                                           tracked_order.executed_amount_base,
                                                           tracked_order.executed_amount_quote,
                                                           tracked_order.fee_paid,
                                                           tracked_order.order_type))
                        else:
                            if tracked_order.is_cancelled:
                                if tracked_order.client_order_id in self._in_flight_orders:
                                    self.logger().info(f"Successfully cancelled order {tracked_order.client_order_id} according to websocket delta.")
                                    self.trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                                       OrderCancelledEvent(self.current_timestamp,
                                                                           tracked_order.client_order_id))
                                else:
                                    self.logger().info(f"The {tracked_order.order_type.name.lower()} order {tracked_order.client_order_id} has failed "
                                                       f"according to websocket delta.")
                                    self.trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                                       MarketOrderFailureEvent(self.current_timestamp,
                                                                               tracked_order.client_order_id,
                                                                               tracked_order.order_type))
                        self.stop_tracking_order(tracked_order.client_order_id)
                elif event_type == "ACCOUNT_UPDATE":
                    update_data = event_message.get("a", {})
                    # update balances
                    for asset in update_data.get("B", []):
                        asset_name = asset["a"]
                        self._account_balances[asset_name] = Decimal(asset["wb"])
                        self._account_available_balances[asset_name] = Decimal(asset["cw"])

                    # update position
                    for asset in update_data.get("P", []):
                        position = self.get_position(asset['s'], PositionSide[asset['ps']])
                        if position is not None:
                            position.update_position(position_side=PositionSide[asset["ps"]],
                                                     unrealized_pnl = Decimal(asset["up"]),
                                                     entry_price = Decimal(asset["ep"]),
                                                     amount = Decimal(asset["pa"]))
                        else:
                            await self._update_positions()
                elif event_type == "MARGIN_CALL":
                    positions = event_message.get("p", [])
                    total_maint_margin_required = 0
                    # total_pnl = 0
                    negative_pnls_msg = ""
                    for position in positions:
                        existing_position = self.get_position(asset['s'], PositionSide[asset['ps']])
                        if existing_position is not None:
                            existing_position.update_position(position_side=PositionSide[asset["ps"]],
                                                              unrealized_pnl=Decimal(asset["up"]),
                                                              amount=Decimal(asset["pa"]))
                        total_maint_margin_required += position.get("mm", 0)
                        if position.get("up", 0) < 1:
                            negative_pnls_msg += f"{position.get('s')}: {position.get('up')}, "
                    self.logger().warning("Margin Call: Your position risk is too high, and you are at risk of "
                                          "liquidation. Close your positions or add additional margin to your wallet.")
                    self.logger().info(f"Margin Required: {total_maint_margin_required}. Total Unrealized PnL: "
                                       f"{negative_pnls_msg}. Negative PnL assets: {negative_pnls_msg}.")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        now = time.time()
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if now - self._user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    # MARKET AND ACCOUNT INFO ---
    def get_fee(self, base_currency: str, quote_currency: str, order_type: object, order_side: object,
                amount: object, price: object):
        is_maker = order_type is OrderType.LIMIT
        return estimate_fee("binance_perpetual", is_maker)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        order_books: dict = self._order_book_tracker.order_books
        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    async def _update_trading_rules(self):
        last_tick = int(self._last_timestamp / 60.0)
        current_tick = int(self.current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self.request(path="/fapi/v1/exchangeInfo", method=MethodType.GET, is_signed=False)
            trading_rules_list = self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        rules: list = exchange_info_dict.get("symbols", [])
        return_val: list = []
        for rule in rules:
            try:
                if rule["contractType"] == "PERPETUAL":
                    trading_pair = convert_from_exchange_trading_pair(rule["symbol"])
                    filters = rule["filters"]
                    filt_dict = {fil["filterType"]: fil for fil in filters}

                    min_order_size = Decimal(filt_dict.get("LOT_SIZE").get("minQty"))
                    step_size = Decimal(filt_dict.get("LOT_SIZE").get("stepSize"))
                    tick_size = Decimal(filt_dict.get("PRICE_FILTER").get("tickSize"))

                    # TODO: BINANCE PERPETUALS DOES NOT HAVE A MIN NOTIONAL VALUE, NEED TO CREATE NEW DERIVATIVES INFRASTRUCTURE
                    # min_notional = 0

                    return_val.append(
                        TradingRule(trading_pair,
                                    min_order_size=min_order_size,
                                    min_price_increment=Decimal(tick_size),
                                    min_base_amount_increment=Decimal(step_size),
                                    # min_notional_size=Decimal(min_notional))
                                    )
                    )
            except Exception as e:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Error: {e}. Skipping...",
                                    exc_info=True)
        return return_val

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await safe_gather(
                    self._update_trading_rules()
                )
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.", exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Binance Perpetuals. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _funding_info_polling_loop(self):
        while True:
            try:
                ws_subscription_path: str = "/".join([f"{convert_to_exchange_trading_pair(trading_pair).lower()}@markPrice"
                                                      for trading_pair in self._trading_pairs])
                stream_url: str = f"{self._stream_url}/stream?streams={ws_subscription_path}"
                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    while True:
                        try:
                            raw_msg: str = await asyncio.wait_for(ws.recv(), timeout=10.0)
                            msg = ujson.loads(raw_msg)
                            trading_pair = convert_from_exchange_trading_pair(msg["data"]["s"])
                            self._funding_info[trading_pair] = FundingInfo(
                                trading_pair,
                                Decimal(str(msg["data"]["i"])),
                                Decimal(str(msg["data"]["p"])),
                                int(msg["data"]["T"]),
                                Decimal(str(msg["data"]["r"]))
                            )
                        except asyncio.TimeoutError:
                            await ws.pong(data=b'')
                        except ConnectionClosed:
                            raise
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error updating funding info. Retrying after 10 seconds... ",
                                    exc_info=True)
                await asyncio.sleep(10.0)

    def get_next_funding_timestamp(self):
        # On Binance Futures, Funding occurs every 8 hours at 00:00 UTC; 08:00 UTC and 16:00
        int_ts = int(self.current_timestamp)
        eight_hours = 8 * 60 * 60
        mod = int_ts % eight_hours
        return float(int_ts - mod + eight_hours)

    async def _funding_fee_polling_loop(self):
        # get our first funding time
        next_funding_fee_timestamp = self.get_next_funding_timestamp()

        # funding payment loop
        while True:
            # wait for funding timestamp plus payment span
            if self.current_timestamp > next_funding_fee_timestamp + self._funding_payment_span[1]:
                # get a start time to query funding payments
                startTime = next_funding_fee_timestamp - self._funding_payment_span[0]
                try:
                    # generate funding payment events
                    await self.get_funding_payment(startTime)
                    next_funding_fee_timestamp = self.get_next_funding_timestamp()
                except Exception:
                    self.logger().error("Unexpected error whilst retrieving funding payments. Retrying after 10 seconds... ",
                                        exc_info=True)
                    await asyncio.sleep(10.0)

            await asyncio.sleep(10)

    async def _status_polling_loop(self):
        while True:
            try:
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_positions()
                )
                await self._update_order_fills_from_trades(),
                await self._update_order_status()
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Binance Perpetuals. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)
            finally:
                self._poll_notifier = asyncio.Event()

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self.request(path="/fapi/v2/account", is_signed=True, add_timestamp=True)
        assets = account_info.get("assets")
        for asset in assets:
            asset_name = asset.get("asset")
            available_balance = Decimal(asset.get("availableBalance"))
            wallet_balance = Decimal(asset.get("walletBalance"))
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = wallet_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        positions = await self.request(path="/fapi/v2/positionRisk", add_timestamp=True, is_signed=True)
        for position in positions:
            trading_pair = position.get("symbol")
            position_side = PositionSide[position.get("positionSide")]
            unrealized_pnl = Decimal(position.get("unRealizedProfit"))
            entry_price = Decimal(position.get("entryPrice"))
            amount = Decimal(position.get("positionAmt"))
            leverage = Decimal(position.get("leverage"))
            if amount != 0:
                self._account_positions[self.position_key(trading_pair, position_side)] = Position(
                    trading_pair=convert_from_exchange_trading_pair(trading_pair),
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=leverage
                )
            else:
                if (trading_pair + position_side.name) in self._account_positions:
                    del self._account_positions[trading_pair + position_side.name]

    async def _update_order_fills_from_trades(self):
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            trading_pairs_to_order_map = defaultdict(lambda: {})
            for order in self._in_flight_orders.values():
                trading_pairs_to_order_map[order.trading_pair][order.exchange_order_id] = order
            trading_pairs = list(trading_pairs_to_order_map.keys())
            tasks = [
                self.request(
                    path="/fapi/v1/userTrades",
                    params={
                        "symbol": convert_to_exchange_trading_pair(trading_pair)
                    },
                    is_signed=True,
                    add_timestamp=True
                ) for trading_pair in trading_pairs]
            self.logger().debug(f"Polling for order fills of {len(tasks)} trading_pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for trades, trading_pair in zip(results, trading_pairs):
                order_map = trading_pairs_to_order_map.get(trading_pair)
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    order_id = str(trade.get("orderId"))
                    if order_id in order_map:
                        tracked_order = order_map.get(order_id)
                        order_type = tracked_order.order_type
                        applied_trade = tracked_order.update_with_trade_updates(trade)
                        if applied_trade:
                            self.trigger_event(
                                self.MARKET_ORDER_FILLED_EVENT_TAG,
                                OrderFilledEvent(
                                    self.current_timestamp,
                                    tracked_order.client_order_id,
                                    tracked_order.trading_pair,
                                    tracked_order.trade_type,
                                    order_type,
                                    Decimal(trade.get("price")),
                                    Decimal(trade.get("qty")),
                                    self.get_fee(
                                        tracked_order.base_asset,
                                        tracked_order.quote_asset,
                                        order_type,
                                        tracked_order.trade_type,
                                        Decimal(trade["price"]),
                                        Decimal(trade["qty"])),
                                    exchange_trade_id=trade["id"],
                                    leverage=self._leverage[tracked_order.trading_pair],
                                    position=tracked_order.position
                                )
                            )

    async def _update_order_status(self):
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = [self.request(path="/fapi/v1/order",
                                  params={
                                      "symbol": convert_to_exchange_trading_pair(order.trading_pair),
                                      "origClientOrderId": order.client_order_id
                                  },
                                  method=MethodType.GET,
                                  add_timestamp=True,
                                  is_signed=True,
                                  return_err=True)
                     for order in tracked_orders]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if client_order_id not in self._in_flight_orders:
                    continue
                if isinstance(order_update, Exception):
                    # NO_SUCH_ORDER code
                    if order_update["code"] == -2013 or order_update["msg"] == "Order does not exist.":
                        self._order_not_found_records[client_order_id] = \
                            self._order_not_found_records.get(client_order_id, 0) + 1
                        if self._order_not_found_records[client_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                            continue
                        self.trigger_event(
                            self.MARKET_ORDER_FAILURE_EVENT_TAG,
                            MarketOrderFailureEvent(self.current_timestamp, client_order_id, tracked_order.order_type)
                        )
                        self.stop_tracking_order(client_order_id)
                    else:
                        self.logger().network(f"Error fetching status update for the order {client_order_id}: "
                                              f"{order_update}.")
                    continue

                tracked_order.last_state = order_update.get("status")
                order_type = OrderType.LIMIT if order_update.get("type") == "LIMIT" else OrderType.MARKET
                executed_amount_base = Decimal(order_update.get("executedQty", "0"))
                executed_amount_quote = Decimal(order_update.get("cumQuote", "0"))

                if tracked_order.is_done:
                    if not tracked_order.is_failure:
                        event_tag = None
                        event_class = None
                        if tracked_order.trade_type is TradeType.BUY:
                            event_tag = self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG
                            event_class = BuyOrderCompletedEvent
                        else:

                            event_tag = self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG
                            event_class = SellOrderCompletedEvent
                        self.logger().info(f"The {order_type.name.lower()} {tracked_order.trade_type.name.lower()} order {client_order_id} has "
                                           f"completed according to order status API.")
                        self.trigger_event(event_tag,
                                           event_class(self.current_timestamp,
                                                       client_order_id,
                                                       tracked_order.base_asset,
                                                       tracked_order.quote_asset,
                                                       (tracked_order.fee_asset or tracked_order.base_asset),
                                                       executed_amount_base,
                                                       executed_amount_quote,
                                                       tracked_order.fee_paid,
                                                       order_type))
                    else:
                        if tracked_order.is_cancelled:
                            self.logger().info(f"Successfully cancelled order {client_order_id} according to order status API.")
                            self.trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                               OrderCancelledEvent(self.current_timestamp,
                                                                   client_order_id))
                        else:
                            self.logger().info(f"The {order_type.name.lower()} order {client_order_id} has failed according to "
                                               f"order status API.")
                            self.trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                               MarketOrderFailureEvent(self.current_timestamp,
                                                                       client_order_id,
                                                                       order_type))
                    self.stop_tracking_order(client_order_id)

    async def _set_leverage(self, trading_pair: str, leverage: int = 1):
        params = {
            "symbol": convert_to_exchange_trading_pair(trading_pair),
            "leverage": leverage
        }
        set_leverage = await self.request(
            path="/fapi/v1/leverage",
            params=params,
            method=MethodType.POST,
            add_timestamp=True,
            is_signed=True
        )
        if set_leverage["leverage"] == leverage:
            self._leverage[trading_pair] = leverage
            self.logger().info(f"Leverage Successfully set to {leverage} for {trading_pair}.")
        else:
            self.logger().error("Unable to set leverage.")
        return leverage

    def set_leverage(self, trading_pair: str, leverage: int = 1):
        safe_ensure_future(self._set_leverage(trading_pair, leverage))

    async def get_funding_payment(self, startTime):
        funding_payment_tasks = []
        for pair in self._trading_pairs:
            funding_payment_tasks.append(self.request(path="/fapi/v1/income",
                                                      params={"symbol": convert_to_exchange_trading_pair(pair), "incomeType": "FUNDING_FEE", "startTime": int(startTime * 1000)},
                                                      method=MethodType.GET,
                                                      add_timestamp=True,
                                                      is_signed=True))
        funding_payment_results = await safe_gather(*funding_payment_tasks, return_exceptions=True)
        for funding_payments in funding_payment_results:
            for funding_payment in funding_payments:
                payment = Decimal(funding_payment["income"])
                action = "paid" if payment < 0 else "received"
                trading_pair = convert_from_exchange_trading_pair(funding_payment["symbol"])
                if payment != Decimal("0"):
                    self.logger().info(f"Funding payment of {payment} {action} on {trading_pair} market.")
                    self.trigger_event(self.MARKET_FUNDING_PAYMENT_COMPLETED_EVENT_TAG,
                                       FundingPaymentCompletedEvent(timestamp=funding_payment["time"],
                                                                    market=self.name,
                                                                    funding_rate=self._funding_info[trading_pair].rate,
                                                                    trading_pair=trading_pair,
                                                                    amount=payment))

    async def _set_position_mode(self, position_mode: PositionMode):
        initial_mode = await self._get_position_mode()
        if initial_mode != position_mode:
            params = {
                "dualSidePosition": position_mode.value
            }
            mode = await self.request(
                path="/fapi/v1/positionSide/dual",
                params=params,
                method=MethodType.POST,
                add_timestamp=True,
                is_signed=True
            )
            if mode["msg"] == "success" and mode["code"] == 200:
                self.logger().info(f"Using {position_mode.name} position mode.")
            else:
                self.logger().error(f"Unable to set postion mode to {position_mode.name}.")
        else:
            self.logger().info(f"Using {position_mode.name} position mode.")

    async def _get_position_mode(self):
        # To-do: ensure there's no active order or contract before changing position mode
        if self._position_mode is None:
            mode = await self.request(
                path="/fapi/v1/positionSide/dual",
                method=MethodType.GET,
                add_timestamp=True,
                is_signed=True
            )
            self._position_mode = PositionMode.HEDGE if mode["dualSidePosition"] else PositionMode.ONEWAY

        return self._position_mode

    def set_position_mode(self, position_mode: PositionMode):
        safe_ensure_future(self._set_position_mode(position_mode))

    def supported_position_modes(self):
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    async def request(self, path: str, params: Dict[str, Any] = {}, method: MethodType = MethodType.GET,
                      add_timestamp: bool = False, is_signed: bool = False, request_weight: int = 1, return_err: bool = False):
        async with self._throttler.weighted_task(request_weight):
            try:
                if add_timestamp:
                    params["timestamp"] = str(int(BinanceTime.get_instance().time()) * 1000)
                    params["recvWindow"] = f"{20000}"
                query = urlencode(sorted(params.items()))
                if is_signed:
                    secret = bytes(self._api_secret.encode("utf-8"))
                    signature = hmac.new(secret, query.encode("utf-8"), hashlib.sha256).hexdigest()
                    query += f"&signature={signature}"

                async with aiohttp.request(
                        method=method.value,
                        url=self._base_url + path + "?" + query,
                        headers={"X-MBX-APIKEY": self._api_key}) as response:
                    if response.status != 200:
                        error_response = await response.json()
                        if return_err:
                            return error_response
                        else:
                            raise IOError(f"Error fetching data from {path}. HTTP status is {response.status}. "
                                          f"Request Error: {error_response}")
                    return await response.json()
            except Exception as e:
                if "Timestamp for this request" in str(e):
                    self.logger().warning("Got Binance timestamp error. "
                                          "Going to force update Binance server time offset...")
                    binance_time = BinanceTime.get_instance()
                    binance_time.clear_time_offset_ms_samples()
                    await binance_time.schedule_update_server_time_offset()
                else:
                    self.logger().error(f"Error fetching {path}", exc_info=True)
                    self.logger().warning(f"{e}")
                raise e
