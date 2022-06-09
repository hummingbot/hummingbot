import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.kucoin import (
    kucoin_constants as CONSTANTS,
    kucoin_utils as utils,
    kucoin_web_utils as web_utils,
)
from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.exchange.kucoin.kucoin_api_user_stream_data_source import KucoinAPIUserStreamDataSource
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class KucoinExchange(ExchangePyBase):

    web_utils = web_utils

    def __init__(self,
                 kucoin_api_key: str,
                 kucoin_passphrase: str,
                 kucoin_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        self.kucoin_api_key = kucoin_api_key
        self.kucoin_passphrase = kucoin_passphrase
        self.kucoin_secret_key = kucoin_secret_key
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__()

    @property
    def authenticator(self):
        return KucoinAuth(
            api_key=self.kucoin_api_key,
            passphrase=self.kucoin_passphrase,
            secret_key=self.kucoin_secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "kucoin"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return ""

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.SYMBOLS_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.SERVER_TIME_PATH_URL

    def supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self.domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return KucoinAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return KucoinAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
            throttler=self._throttler,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:

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

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal) -> (str, float):
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
                api_factory=self._web_assistants_factory,
                throttler=self._throttler),
            "type": order_type_str,
        }
        if order_type is OrderType.LIMIT:
            data["price"] = str(price)
        elif order_type is OrderType.LIMIT_MAKER:
            data["price"] = str(price)
            data["postOnly"] = True
        exchange_order_id = await self._api_post(
            path_url=path_url,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.POST_ORDER_LIMIT_ID,
        )
        return str(exchange_order_id["data"]["orderId"]), self.current_timestamp

    async def _place_cancel(self, order_id, tracked_order):
        """ This implementation specific function is called by _cancel, and returns True if successful
        """
        exchange_order_id = await tracked_order.get_exchange_order_id()
        cancel_result = await self._api_delete(
            f"{CONSTANTS.ORDERS_PATH_URL}/{exchange_order_id}",
            is_auth_required=True,
            limit_id=CONSTANTS.DELETE_ORDER_LIMIT_ID
        )
        if tracked_order.exchange_order_id in cancel_result["data"].get("cancelledOrderIds", []):
            return True
        return False

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
                            updated_status = OrderState.CANCELED

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

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        response = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            params={"type": "trade"},
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
                        api_factory=self._web_assistants_factory,
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

    async def _update_trading_fees(self):
        trading_symbols = [await self._orderbook_ds.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair,
            domain=self._domain,
            api_factory=self._web_assistants_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer) for trading_pair in self._trading_pairs]
        params = {"symbols": ",".join(trading_symbols)}
        resp = await self._api_get(
            path_url=CONSTANTS.FEE_PATH_URL,
            params=params,
            is_auth_required=True,
        )
        fees_json = resp["data"]
        for fee_json in fees_json:
            trading_pair = await self._orderbook_ds.trading_pair_associated_to_exchange_symbol(
                symbol=fee_json["symbol"],
                domain=self._domain,
                api_factory=self._web_assistants_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer,
            )
            self._trading_fees[trading_pair] = fee_json

    async def _update_order_status(self):
        tracked_orders = list(self.in_flight_orders.values())
        if len(tracked_orders) <= 0:
            return

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
            request_tasks.append(asyncio.get_event_loop().create_task(self._api_get(
                path_url=f"{CONSTANTS.ORDERS_PATH_URL}/{exchange_order_id}",
                is_auth_required=True,
                limit_id=CONSTANTS.GET_ORDER_LIMIT_ID)))

        self.logger().debug(f"Polling for order status updates of {len(reviewed_orders)} orders.")
        responses = await safe_gather(*request_tasks, return_exceptions=True)

        for update_result, tracked_order in zip(responses, reviewed_orders):
            client_order_id = tracked_order.client_order_id

            # If the order has already been canceled or has failed do nothing
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
                        new_state = OrderState.CANCELED
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
