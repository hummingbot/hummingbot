import asyncio
import math
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from async_timeout import timeout
from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.cape_crypto import (
    cape_crypto_constants as CONSTANTS,
    cape_crypto_utils,
    cape_crypto_web_utils as web_utils,
)
from hummingbot.connector.exchange.cape_crypto.cape_crypto_api_order_book_data_source import (
    CapeCryptoAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.cape_crypto.cape_crypto_api_user_stream_data_source import (
    CapeCryptoAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.cape_crypto.cape_crypto_auth import CapeCryptoAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None


class CapeCryptoExchange(ExchangePyBase):
    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 5.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 cape_crypto_api_key: str,
                 cape_crypto_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = cape_crypto_api_key
        self.secret_key = cape_crypto_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_cape_crypto_timestamp = 1.0
        super().__init__(client_config_map)

    @staticmethod
    def cape_crypto_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(cape_crypto_type: str) -> OrderType:
        return OrderType[cape_crypto_type]

    @property
    def authenticator(self):
        return CapeCryptoAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "cape_crypto"

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
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.GET_MARKET_SUMMARY_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.GET_MARKET_SUMMARY_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.GET_STATUS_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_BOOK_PATH_URL)
        return pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CapeCryptoAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return CapeCryptoAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        order_result = None
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        path = CONSTANTS.CREATE_ORDER_PATH_URL
        ord_type = 'limit' if order_type.is_limit_type else "market"
        api_params = {"market": symbol,
                      "side": side_str,
                      "ord_type": ord_type,
                      "price": price_str,
                      "volume": amount_str,
                      "custom_order_id": order_id,
                      "post_only": True
                      }
        if not order_type.is_limit_type:
            api_params.pop('price', None)
          
        if order_type is not OrderType.LIMIT_MAKER:
            api_params.pop('post_only', None)
        try:
            order_result = await self._api_post(
                path_url=path,
                data=api_params,
                is_auth_required=True)
            o_id = str(order_result.get("id")) if "id" in order_result else None
            if o_id is None:
                self.logger().info(f"Error creating order on CAPE_CRYPTO")
                raise Exception(f"Error creating order on CAPE_CRYPTO: {order_result}")
            return o_id, time.time()
        except Exception as e:
            self.logger().error(f"Error placing order: {e}")
            raise

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        ex_order_id = tracked_order.exchange_order_id
        api_params = {}
        try:
            if ex_order_id is None:
                return False
            cancel_result = await self._api_post(
                path_url=CONSTANTS.CANCEL_ORDER_PATH_URL.format(ex_order_id),
                data=api_params,
                is_auth_required=True,
                limit_id=CONSTANTS.CANCEL_ORDER_PATH_URL)
            if cancel_result["state"] == "wait":
                # check if the order was cancelled
                cancel_check = await self._api_get(
                    path_url=CONSTANTS.GET_ORDER_DETAIL_PATH_URL.format(ex_order_id),
                    is_auth_required=True,
                    limit_id=CONSTANTS.GET_ORDER_DETAIL_PATH_URL)
                if cancel_check['state'] == 'cancel':
                    return True
                return False
            return True 
        except Exception as e: 
            self.logger().exception(f"Error Cacnelling order on CAPE_CRYPTO {e}")
            return False
        

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
          Response Example:
        [
            {
                id: "btczar",
                name: "BTC/ZAR",
                base_unit: "btc",
                quote_unit: "zar",
                min_price: "100000.0",
                max_price: "1100000.0",
                min_amount: "0.00001",
                amount_precision: 8,
                price_precision: 2,
                state: "enabled",
            }
        ]
        """
        trading_pair_rules = exchange_info_dict
        retval = []
        for rule in filter(cape_crypto_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("id"))
                min_order_size = Decimal(rule['min_amount'])
                price_decimals = Decimal(str(rule["price_precision"]))
                quantity_decimals = Decimal(str(rule["amount_precision"]))
                price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimals)))
                quantity_step = Decimal("1") / Decimal(str(math.pow(10, quantity_decimals)))

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=Decimal(price_step),
                                min_base_amount_increment=Decimal(quantity_step),
                                )
                            )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _status_polling_loop_fetch_updates(self):
        # We rely on the trades from the websocket. If we enabled this, it would cause duplicate fills
        # await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _process_order_update(self, order_update: OrderUpdate):
        if not order_update.client_order_id and not order_update.exchange_order_id:
            self.logger().error("OrderUpdate does not contain any client_order_id or exchange_order_id", exc_info=True)
            return

        tracked_order: Optional[InFlightOrder] = self.fetch_order(
            order_update.client_order_id, order_update.exchange_order_id
        )

        if tracked_order:
            if order_update.new_state == OrderState.FILLED and not tracked_order.is_done:
                try:
                    await asyncio.wait_for(
                        tracked_order.wait_until_completely_filled(),
                        timeout=10)
                except asyncio.TimeoutError:
                    self.logger().warning(
                        f"The order fill updates did not arrive on time for {tracked_order.client_order_id}. "
                        f"The complete update will be processed with incomplete information.")

            previous_state: OrderState = tracked_order.current_state

            updated: bool = tracked_order.update_with_order_update(order_update)
            if updated:
                self._trigger_order_creation(tracked_order, previous_state, order_update.new_state)
                self._trigger_order_completion(tracked_order, order_update)

        elif order_update.client_order_id in self._lost_orders:
            if order_update.new_state in [OrderState.CANCELED, OrderState.FILLED]:
                # If the order officially reaches a final state after being lost it should be removed from the lost list
                del self._lost_orders[order_update.client_order_id]
        else:
            self.logger().debug(f"Order is not/no longer being tracked ({order_update})")

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                self.logger().debug(f"Event Type user stream received: {next(iter(event_message))}")
                if next(iter(event_message)) == CONSTANTS.TRADE_CHANNEL_ID:
                    order_msg=event_message["trade"]
                    self.logger().debug(f"New Trade wss feed: {order_msg}")
                    exchange_order_id = str(order_msg["order_id"])
                    tracked_order = next(
                        (order for order in self._order_tracker.all_updatable_orders.values() if order.exchange_order_id == exchange_order_id),
                        None)
                    if tracked_order is not None:
                        trade_type = tracked_order.trade_type
                        if 'fee' not in order_msg:
                            fee_multiplier = cape_crypto_utils.DEFAULT_FEES.maker_percent_fee_decimal
                            order_msg["fee"] = Decimal(str(order_msg["amount"])) * Decimal(str(fee_multiplier))  \
                                if trade_type is TradeType.BUY else Decimal(str(order_msg["total"])) * Decimal(str(fee_multiplier))
                            order_msg["fee_currency"] = tracked_order.base_asset if trade_type is TradeType.BUY else tracked_order.quote_asset

                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            flat_fees=[TokenAmount(amount=Decimal(order_msg["fee"]), token=order_msg["fee_currency"])]
                        )
                        trade_update = TradeUpdate(
                            trade_id=order_msg["id"],
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=tracked_order.trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(str(order_msg["amount"])),
                            fill_quote_amount=Decimal(str(order_msg["total"])),
                            fill_price=Decimal(str(order_msg["price"])),
                            fill_timestamp=order_msg["created_at"],
                        )
                        self._order_tracker.process_trade_update(trade_update)

                if next(iter(event_message)) == CONSTANTS.ORDER_CHANNEL_ID:
                    order_msg = event_message['order']
                    self.logger().debug(f"New Order wss feed: {order_msg}")
                    if  CONSTANTS.ORDER_STATE[order_msg['state']] == OrderState.PENDING_CREATE:
                        continue
                    exchange_order_id = str(order_msg['id'])
                    tracked_order = next(
                        (order for order in self._order_tracker.all_updatable_orders.values() if order.exchange_order_id == exchange_order_id),
                        None)
                    if tracked_order is not None:
                        if order_msg['state'] == 'Failed':
                            self.logger().error(f"Order status is Failed")
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=order_msg["updated_at"],
                            new_state=CONSTANTS.ORDER_STATE[order_msg["state"]],
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=order_msg["id"],
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                if next(iter(event_message)) == CONSTANTS.BALANCE_CHANNEL_ID:
                    balance = event_message["balance"]
                    asset_name = balance["currency_id"]
                    self._account_available_balances[asset_name] = Decimal(str(balance["balance"]))
                    self._account_balances[asset_name] = Decimal(str(balance["balance"])) + Decimal(str(balance["locked"]))

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)


    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        return []
        
    
    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        order_id = await tracked_order.get_exchange_order_id()
        try:
            updated_order_data = await self._api_get(
                path_url=CONSTANTS.GET_ORDER_DETAIL_PATH_URL.format(order_id),
                is_auth_required=True,
                limit_id=CONSTANTS.GET_ORDER_DETAIL_PATH_URL)

            new_state = CONSTANTS.ORDER_STATE[updated_order_data["state"]]

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(updated_order_data["id"]),
                trading_pair=tracked_order.trading_pair,
                update_timestamp=cape_crypto_utils.convert_exchange_timestamp_to_ms(updated_order_data["updated_at"]),
                new_state=new_state,
            )

            return order_update
        except Exception as e:
             self.logger().info(
                f"Failed to fetch order status {e}")
          

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(
            path_url=CONSTANTS.GET_BALANCES_PATH_URL,
            is_auth_required=True)

        for account in account_info:
            asset_name = account["currency"]
            self._account_available_balances[asset_name] = Decimal(str(account["balance"]))
            self._account_balances[asset_name] = Decimal(str(account["balance"])) + Decimal(str(account["locked"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in exchange_info:
            mapping[symbol_data["id"]] = combine_to_hb_trading_pair(base=symbol_data["base_unit"],
                                                                        quote=symbol_data["quote_unit"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.GET_MARKET_TICKER_PATH_URL.format(trading_pair),
            limit_id=CONSTANTS.GET_MARKET_TICKER_PATH_URL
        )

        return float(resp_json["ticker"]["last"])

        
    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(
            status_update_exception
        ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(
            cancelation_exception
        ) and CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)