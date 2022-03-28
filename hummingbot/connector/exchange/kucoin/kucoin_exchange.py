import asyncio
import logging
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

from async_timeout import timeout

from hummingbot.connector.exchange.kucoin import (
    kucoin_constants as CONSTANTS,
    kucoin_utils as utils,
    kucoin_web_utils as web_utils,
)
from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.exchange.kucoin.kucoin_api_user_stream_data_source import KucoinAPIUserStreamDataSource
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.connector.exchange_base_v2 import ExchangeBaseV2
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id, combine_to_hb_trading_pair
from hummingbot.connector.exchange_base import ExchangeBase, s_decimal_NaN, s_decimal_0, MINUTE, TWELVE_HOURS
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, OrderState, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod



class KucoinExchange(ExchangeBaseV2):
    RATE_LIMITS = CONSTANTS.RATE_LIMITS
    CHECK_NETWORK_URL = CONSTANTS.SERVER_TIME_PATH_URL
    MAX_ORDER_ID_LEN = CONSTANTS.MAX_ORDER_ID_LEN
    DEFAULT_DOMAIN = CONSTANTS.DEFAULT_DOMAIN
    SYMBOLS_PATH_URL = CONSTANTS.SYMBOLS_PATH_URL
    FEE_PATH_URL = CONSTANTS.FEE_PATH_URL

    def init_auth(self):
        return KucoinAuth(
            api_key=kucoin_api_key,
            passphrase=kucoin_passphrase,
            secret_key=kucoin_secret_key,
            time_provider=self._time_synchronizer)

    def init_ob_datasource(self):
        return KucoinAPIOrderBookDataSource(
                trading_pairs=trading_pairs,
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer)

    def init_us_datasource(self):
        return KucoinAPIUserStreamDataSource(
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler)

    @property
    def name(self) -> str:
        return "kucoin"

    def supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        """
        Calculates the fee to pay based on the fee information provided by the exchange for the account and the token pair.
        If exchange info is not available it calculates the estimated fee an order would pay based on the connector
            configuration

        :param base_currency: the order base currency
        :param quote_currency: the order quote currency
        :param order_type: the type of order (MARKET, LIMIT, LIMIT_MAKER)
        :param order_side: if the order is for buying or selling
        :param amount: the order amount
        :param price: the order price
        :param is_maker: True if the order is a maker order, False if it is a taker order

        :return: the calculated or estimated fee
        """

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        if trading_pair in self._trading_fees:
            fees_data = self._trading_fees[trading_pair]
            fee_value = Decimal(fees_data["makerFeeRate"]) if is_maker else Decimal(fees_data["takerFeeRate"])
            fee = AddedToCostTradeFee(percent=fee_value)
        else:
            fee = build_trade_fee(
                self.name,
                is_maker,
                base_currency=base_currency,
                quote_currency=quote_currency,
                order_type=order_type,
                order_side=order_side,
                amount=amount,
                price=price,
            )
        return fee

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type: OrderType,
                            price: Optional[Decimal] = None):
        """
        Creates a an order in the exchange using the parameters to configure it

        :param trade_type: the side of the order (BUY of SELL)
        :param order_id: the id that should be assigned to the order (the client id)
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        """
        trading_rule = self._trading_rules[trading_pair]

        if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]:
            price = self.quantize_order_price(trading_pair, price)
            amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount, price=price)
        else:
            amount = self.quantize_order_amount(trading_pair, amount)

        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

        if amount < trading_rule.min_order_size:
            self.logger().warning(f"{trade_type.name.title()} order amount {amount} is lower than the minimum order"
                                  f" size {trading_rule.min_order_size}. The order will not be created.")
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)
            return

        try:

            exchange_order_id = await self._place_order(
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                trade_type=trade_type,
                order_type=order_type,
                price=price)

            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.OPEN,
            )
            self._order_tracker.process_order_update(order_update)

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                f"Error submitting {trade_type.name.lower()} {order_type.name.upper()} order to Kucoin for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg="Failed to submit buy order to Kucoin. Check API key and network connection."
            )
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal) -> str:
        path_url = CONSTANTS.ORDERS_PATH_URL
        side = trade_type.name.lower()
        order_type_str = "market" if order_type == OrderType.MARKET else "limit"
        data = {
            "size": str(amount),
            "clientOid": order_id,
            "side": side,
            "symbol": await KucoinAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair,
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler),
            "type": order_type_str,
        }
        if order_type is OrderType.LIMIT:
            data["price"] = str(price)
        elif order_type is OrderType.LIMIT_MAKER:
            data["price"] = str(price)
            data["postOnly"] = True
        exchange_order_id = await self._api_request(
            path_url=path_url,
            method=RESTMethod.POST,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.POST_ORDER_LIMIT_ID,
        )
        return str(exchange_order_id["data"]["orderId"])

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        Requests the exchange to cancel an active order

        :param trading_pair: the trading pair the order to cancel operates with
        :param order_id: the client id of the order to cancel
        """
        tracked_order = self._order_tracker.fetch_tracked_order(order_id)
        if tracked_order is not None:
            try:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                path_url = f"{CONSTANTS.ORDERS_PATH_URL}/{exchange_order_id}"
                cancel_result = await self._api_request(
                    path_url=path_url,
                    method=RESTMethod.DELETE,
                    is_auth_required=True,
                    limit_id=CONSTANTS.DELETE_ORDER_LIMIT_ID
                )

                if tracked_order.exchange_order_id in cancel_result["data"].get("cancelledOrderIds", []):
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.CANCELLED,
                    )
                    self._order_tracker.process_order_update(order_update)
                    return order_id
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                self.logger().warning(f"Failed to cancel the order {order_id} because it does not have an exchange"
                                      f" order id yet")
                await self._order_tracker.process_order_not_found(order_id)
            except Exception as e:
                self.logger().network(
                    f"Failed to cancel order {order_id}: {str(e)}",
                    exc_info=True,
                    app_warning_msg=f"Failed to cancel the order {order_id} on Kucoin. "
                                    f"Check API key and network connection."
                )

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("type")
                event_subject = event_message.get("subject")
                execution_data = event_message.get("data")

                # Refer to https://docs.kucoin.com/#private-order-change-events
                if event_type == "message" and event_subject == CONSTANTS.ORDER_CHANGE_EVENT_TYPE:
                    order_event_type = execution_data["type"]
                    client_order_id: Optional[str] = execution_data.get("clientOid")

                    tracked_order = self._order_tracker.fetch_order(client_order_id=client_order_id)

                    if tracked_order is not None:
                        event_timestamp = execution_data["ts"] * 1e-9

                        if order_event_type == "match":
                            execute_amount_diff = Decimal(execution_data["matchSize"])
                            execute_price = Decimal(execution_data["matchPrice"])

                            fee = self.get_fee(
                                tracked_order.base_asset,
                                tracked_order.quote_asset,
                                tracked_order.order_type,
                                tracked_order.trade_type,
                                execute_price,
                                execute_amount_diff,
                            )

                            trade_update = TradeUpdate(
                                trade_id=execution_data["tradeId"],
                                client_order_id=client_order_id,
                                exchange_order_id=execution_data["orderId"],
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=execute_amount_diff,
                                fill_quote_amount=execute_amount_diff * execute_price,
                                fill_price=execute_price,
                                fill_timestamp=event_timestamp,
                            )
                            self._order_tracker.process_trade_update(trade_update)

                        updated_status = tracked_order.current_state
                        if order_event_type == "open":
                            updated_status = OrderState.OPEN
                        elif order_event_type == "match":
                            updated_status = OrderState.PARTIALLY_FILLED
                        elif order_event_type == "filled":
                            updated_status = OrderState.FILLED
                        elif order_event_type == "canceled":
                            updated_status = OrderState.CANCELLED

                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=event_timestamp,
                            new_state=updated_status,
                            client_order_id=client_order_id,
                            exchange_order_id=execution_data["orderId"],
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == "message" and event_subject == CONSTANTS.BALANCE_EVENT_TYPE:
                    currency = execution_data["currency"]
                    available_balance = Decimal(execution_data["available"])
                    total_balance = Decimal(execution_data["total"])
                    self._account_balances.update({currency: total_balance})
                    self._account_available_balances.update({currency: available_balance})

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _status_polling_loop(self):
        """
        Performs all required operation to keep the connector updated and synchronized with the exchange.
        It contains the backup logic to update status using API requests in case the main update source (the user stream
        data source websocket) fails.
        It also updates the time synchronizer. This is necessary because Kucoin requires the time of the client to be
        the same as the time in the exchange.
        Executes when the _poll_notifier event is enabled by the `tick` function.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                await self._update_time_synchronizer()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp

                self._poll_notifier = asyncio.Event()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Kucoin. "
                                                      "Check API key and network connection.")
                await self._sleep(0.5)

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        response = await self._api_request(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            params={"type": "trade"},
            method=RESTMethod.GET,
            is_auth_required=True)

        if response:
            for balance_entry in response["data"]:
                asset_name = balance_entry["currency"]
                self._account_available_balances[asset_name] = Decimal(balance_entry["available"])
                self._account_balances[asset_name] = Decimal(balance_entry["balance"])
                remote_asset_names.add(asset_name)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

    async def _format_trading_rules(self, raw_trading_pair_info: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []

        for info in raw_trading_pair_info["data"]:
            if utils.is_pair_information_valid(info):
                try:
                    trading_pair = await KucoinAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                        symbol=info.get("symbol"),
                        domain=self._domain,
                        api_factory=self._api_factory,
                        throttler=self._throttler)
                    trading_rules.append(
                        TradingRule(trading_pair=trading_pair,
                                    min_order_size=Decimal(info["baseMinSize"]),
                                    max_order_size=Decimal(info["baseMaxSize"]),
                                    min_price_increment=Decimal(info['priceIncrement']),
                                    min_base_amount_increment=Decimal(info['baseIncrement']),
                                    min_quote_amount_increment=Decimal(info['quoteIncrement']),
                                    min_notional_size=Decimal(info["quoteMinSize"]))
                    )
                except Exception:
                    self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def _update_order_status(self):
        # The poll interval for order status is 10 seconds.
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        tracked_orders = list(self.in_flight_orders.values())
        if current_tick > last_tick and len(tracked_orders) > 0:
            reviewed_orders = []
            request_tasks = []

            for tracked_order in tracked_orders:
                try:
                    exchange_order_id = await tracked_order.get_exchange_order_id()
                except asyncio.TimeoutError:
                    self.logger().debug(
                        f"Tracked order {tracked_order.client_order_id} does not have an exchange id. "
                        f"Attempting fetch in next polling interval."
                    )
                    await self._order_tracker.process_order_not_found(tracked_order.client_order_id)
                    continue
                reviewed_orders.append(tracked_order)
                request_tasks.append(asyncio.get_event_loop().create_task(self._api_request(
                    path_url=f"{CONSTANTS.ORDERS_PATH_URL}/{exchange_order_id}",
                    method=RESTMethod.GET,
                    is_auth_required=True,
                    limit_id=CONSTANTS.GET_ORDER_LIMIT_ID)))

            self.logger().debug(f"Polling for order status updates of {len(reviewed_orders)} orders.")
            results = await safe_gather(*request_tasks, return_exceptions=True)

            for update_result, tracked_order in zip(results, reviewed_orders):
                client_order_id = tracked_order.client_order_id

                # If the order has already been cancelled or has failed do nothing
                if client_order_id in self.in_flight_orders:
                    if isinstance(update_result, Exception):
                        self.logger().network(
                            f"Error fetching status update for the order {client_order_id}: {update_result}.",
                            app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                        )
                        # Wait until the order not found error have repeated a few times before actually treating
                        # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601
                        await self._order_tracker.process_order_not_found(client_order_id)

                    else:
                        # Update order execution status
                        ordered_canceled = update_result["data"]["cancelExist"]
                        is_active = update_result["data"]["isActive"]
                        op_type = update_result["data"]["opType"]

                        new_state = tracked_order.current_state
                        if ordered_canceled or op_type == "CANCEL":
                            new_state = OrderState.CANCELLED
                        elif not is_active:
                            new_state = OrderState.FILLED

                        update = OrderUpdate(
                            client_order_id=client_order_id,
                            exchange_order_id=update_result["data"]["id"],
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=self.current_timestamp,
                            new_state=new_state,
                        )
                        self._order_tracker.process_order_update(update)

