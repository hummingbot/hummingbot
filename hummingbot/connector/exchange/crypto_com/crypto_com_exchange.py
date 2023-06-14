import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.crypto_com import (
    crypto_com_constants as CONSTANTS,
    crypto_com_utils,
    crypto_com_web_utils as web_utils,
)
from hummingbot.connector.exchange.crypto_com.crypto_com_api_order_book_data_source import (
    CryptoComAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.crypto_com.crypto_com_api_user_stream_data_source import (
    CryptoComAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.crypto_com.crypto_com_auth import CryptoComAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CryptoComExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 crypto_com_api_key: str,
                 crypto_com_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = crypto_com_api_key
        self.secret_key = crypto_com_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_crypto_com_timestamp = 1
        super().__init__(client_config_map)

    @staticmethod
    def crypto_com_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(crypto_com_type: str) -> OrderType:
        return OrderType[crypto_com_type]

    @property
    def authenticator(self):
        return CryptoComAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "crypto_com"
        else:
            return f"crypto_com_{self._domain}"

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
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_BOOK_PATH_URL)
        return pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("40102" in error_description
                                        and "INVALID_NONCE" in error_description)
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return any(str(code) in str(status_update_exception) for code in CONSTANTS.ORDER_NOT_EXIST_ERROR_CODES)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return any(str(code) in str(cancelation_exception) for code in CONSTANTS.ORDER_NOT_EXIST_ERROR_CODES)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CryptoComAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return CryptoComAPIUserStreamDataSource(
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
        type_str = CryptoComExchange.crypto_com_order_type(order_type)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {
            "instrument_name": symbol,
            "side": side_str,
            "type": type_str,
            "quantity": amount_str,
            "client_oid": order_id,
            "spot_margin": "SPOT"
        }
        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            price_str = f"{price:f}"
            api_params["price"] = price_str
        if order_type == OrderType.LIMIT:
            api_params["time_in_force"] = CONSTANTS.TIME_IN_FORCE_GTC

        api_params = self.generate_crypto_com_request(method=CONSTANTS.CREATE_ORDER_PATH_URL, params=api_params)

        try:
            order_result = await self._api_post(
                path_url=CONSTANTS.CREATE_ORDER_PATH_URL,
                data=api_params,
                is_auth_required=True)
            o_id = str(order_result["result"]["order_id"])
            transact_time = self._time_synchronizer.time()
        except IOError:
            raise
        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        api_params = {
            "client_oid": order_id,
        }

        api_params = self.generate_crypto_com_request(method=CONSTANTS.CANCEL_ORDER_PATH_URL, params=api_params)

        cancel_result = await self._api_delete(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            params=api_params,
            is_auth_required=True)
        if int(cancel_result.get("code")) == 0:
            return True
        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "id": 1,
            "method": "public/get-instruments",
            "code": 0,
            "result": {
                "data": [
                    {
                        symbol: "BTC_USDT",
                        inst_type: "CCY_PAIR",
                        display_name: "BTC/USDT",
                        base_ccy: "BTC",
                        quote_ccy: "USDT",
                        quote_decimals: 2,
                        quantity_decimals: 5,
                        price_tick_size: "0.01",
                        qty_tick_size: "0.00001",
                        max_leverage: "50",
                        tradable: true,
                        expiry_timestamp_ms: 0,
                        beta_product: false,
                        margin_buy_enabled: false,
                        margin_sell_enabled: true,
                    },
                    ...
                ]
            }
        }
        """
        trading_pair_rules = exchange_info_dict["result"].get("data", [])
        retval = []
        for rule in filter(crypto_com_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("symbol"))

                min_order_size = min_base_amount_increment = Decimal(rule.get("qty_tick_size"))
                min_price_increment = Decimal(rule.get("price_tick_size"))

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=min_price_increment,
                                min_base_amount_increment=min_base_amount_increment))

            except Exception:
                self.logger().exception(f"Error parsing the Crypto.com trading pair rule {rule}. Skipping.")
        return retval

    async def _status_polling_loop_fetch_updates(self):
        await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message["result"]["channel"]

                if CONSTANTS.WS_USER_TRADE_CHANNEL in event_type:
                    trades = event_message["result"]["data"]
                    for trade in trades:
                        client_order_id = trade.get("client_oid", "")
                        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        if tracked_order is None:
                            continue
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=trade["fee_instrument_name"],
                            flat_fees=[TokenAmount(amount=abs(Decimal(trade["fees"])), token=trade["fee_instrument_name"])]
                        )
                        trade_update = TradeUpdate(
                            trade_id=str(trade["trade_id"]),
                            client_order_id=client_order_id,
                            exchange_order_id=str(trade["order_id"]),
                            trading_pair=tracked_order.trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(trade["traded_quantity"]),
                            fill_quote_amount=Decimal(trade["traded_quantity"]) * Decimal(trade["traded_price"]),
                            fill_price=Decimal(trade["traded_price"]),
                            fill_timestamp=trade["create_time"] * 1e-3,
                        )
                        self._order_tracker.process_trade_update(trade_update)
                elif CONSTANTS.WS_USER_ORDER_CHANNEL in event_type:
                    orders = event_message["result"]["data"]
                    for order in orders:
                        client_order_id = order.get("client_oid", "")
                        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                        if tracked_order is None:
                            continue

                        if order["status"] == "ACTIVE" and float(order["cumulative_quantity"]) != 0:
                            new_state = CONSTANTS.ORDER_STATE["PARTIALLY_FILLED"]
                        else:
                            new_state = CONSTANTS.ORDER_STATE[order["result"]["status"]]

                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=order["update_time"] * 1e-3,
                            new_state=new_state,
                            client_order_id=client_order_id,
                            exchange_order_id=str(order["order_id"]),
                        )
                        self._order_tracker.process_order_update(order_update=order_update)
                elif CONSTANTS.WS_USER_BALANCE_CHANNEL in event_type:
                    balances = event_message["result"]["data"][0]["position_balances"]
                    for balance_entry in balances:
                        asset_name = balance_entry["instrument_name"]
                        free_balance = Decimal(balance_entry["max_withdrawal_balance"])
                        total_balance = Decimal(balance_entry["quantity"])
                        self._account_available_balances[asset_name] = free_balance
                        self._account_balances[asset_name] = total_balance

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _update_order_fills_from_trades(self):
        """
        This is intended to be a backup measure to get filled events with trade ID for orders,
        in case Crypto.com's user stream events are not working.
        This is separated from _update_order_status as there is no endpoint to get order fills
        for an individual order from Crypto.com.
        """

        query_time = self._last_trades_poll_crypto_com_timestamp
        self._last_trades_poll_crypto_com_timestamp = int(time.time_ns())    # Nanosecond is recommended by Crypto.com
        order_by_exchange_id_map = {}
        for order in self._order_tracker.all_fillable_orders.values():
            order_by_exchange_id_map[order.exchange_order_id] = order

        tasks = []
        trading_pairs = self.trading_pairs
        for trading_pair in trading_pairs:
            params = {
                "instrument_name": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            }
            if self._last_poll_timestamp > 0:
                params["start_time"] = query_time

            params = self.generate_crypto_com_request(method=CONSTANTS.TRADE_HISTORY_PATH_URL, params=params)
            tasks.append(self._api_post(
                path_url=CONSTANTS.TRADE_HISTORY_PATH_URL,
                data=params,
                is_auth_required=True))

        self.logger().debug(f"Polling for order fills of {len(tasks)} trading pairs on Crypto.com.")
        responses = await safe_gather(*tasks, return_exceptions=True)

        for response, trading_pair in zip(responses, trading_pairs):

            if isinstance(response, Exception):
                self.logger().network(
                    f"Error fetching trades update for the order {trading_pair} in Crypto.com: {response}.",
                    app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                )
                continue

            trades = response["result"]["data"]
            for trade in trades:
                exchange_order_id = str(trade["order_id"])
                if exchange_order_id in order_by_exchange_id_map:
                    # This is a fill for a tracked order
                    tracked_order = order_by_exchange_id_map[exchange_order_id]
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=tracked_order.trade_type,
                        percent_token=trade["fee_instrument_name"],
                        flat_fees=[TokenAmount(amount=abs(Decimal(trade["fees"])), token=trade["fee_instrument_name"])]
                    )
                    trade_update = TradeUpdate(
                        trade_id=str(trade["trade_id"]),
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(trade["traded_quantity"]),
                        fill_quote_amount=(Decimal(trade["traded_quantity"]) * Decimal(trade["traded_price"])),
                        fill_price=Decimal(trade["traded_price"]),
                        fill_timestamp=trade["create_time"] * 1e-3,
                    )
                    self._order_tracker.process_trade_update(trade_update)
                elif self.is_confirmed_new_order_filled_event(str(trade["trade_id"]), exchange_order_id, trading_pair):
                    # This is a fill of an order registered in the DB but not tracked any more
                    self._current_trade_fills.add(TradeFillOrderDetails(
                        market=self.display_name,
                        exchange_trade_id=str(trade["trade_id"]),
                        symbol=trading_pair))
                    self.trigger_event(
                        MarketEvent.OrderFilled,
                        OrderFilledEvent(
                            timestamp=float(trade["create_time"]) * 1e-3,
                            order_id=self._exchange_order_ids.get(str(trade["order_id"]), None),
                            trading_pair=trading_pair,
                            trade_type=TradeType.BUY if trade["side"] == "BUY" else TradeType.SELL,
                            order_type=OrderType.LIMIT if trade["taker_side"] == "MAKER" else OrderType.MARKET,
                            price=Decimal(trade["traded_price"]),
                            amount=Decimal(trade["traded_quantity"]),
                            trade_fee=DeductedFromReturnsTradeFee(
                                flat_fees=[
                                    TokenAmount(
                                        trade["fee_instrument_name"],
                                        Decimal(trade["fees"])
                                    )
                                ]
                            ),
                            exchange_trade_id=str(trade["trade_id"])
                        ))
                    self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        api_params = {
            "client_oid": tracked_order.client_order_id
        }

        api_params = self.generate_crypto_com_request(method=CONSTANTS.ORDER_DETAIL_PATH_URL, params=api_params)

        updated_order_data = await self._api_post(
            path_url=CONSTANTS.ORDER_DETAIL_PATH_URL,
            data=api_params,
            is_auth_required=True)

        # see note under https://exchange-docs.crypto.com/exchange/v1/rest-ws/index.html#user-order-instrument_name on
        # how to handle partial filled order status
        if updated_order_data["status"] == "ACTIVE" and float(updated_order_data["cumulative_quantity"]) != 0:
            new_state = CONSTANTS.ORDER_STATE["PARTIALLY_FILLED"]
        else:
            new_state = CONSTANTS.ORDER_STATE[updated_order_data["result"]["status"]]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["result"]["order_id"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=int(updated_order_data["result"]["update_time"]) * 1e-3,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        api_params = self.generate_crypto_com_request(method=CONSTANTS.ACCOUNTS_PATH_URL)

        account_info = await self._api_post(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            data=api_params,
            is_auth_required=True)

        balances = account_info["result"]["data"][0]["position_balances"]
        for balance_entry in balances:
            asset_name = balance_entry["instrument_name"]
            total_balance = Decimal(balance_entry["quantity"])
            reserved_balance = Decimal(balance_entry["reserved_qty"])
            self._account_available_balances[asset_name] = total_balance - reserved_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(crypto_com_utils.is_exchange_information_valid, exchange_info["result"]["data"]):
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=symbol_data["base_ccy"],
                                                                        quote=symbol_data["quote_ccy"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "instrument_name": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        params = self.generate_crypto_com_request(method=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, params=params)

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            params=params
        )

        data = resp_json["result"]["data"][0]

        # when there are no trades, the response for last price is an None
        last_price = data["a"] if data["a"] else 0

        return float(last_price)

    def generate_crypto_com_request(self, method: str, params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Generates a Crypto.com request dictionary with the given method and params.
        """
        request = {
            "id": int(time.time() * 1e6),
            "method": method,
            "params": params,
            "nonce": int(self._time_synchronizer * 1e3)
        }
        return request
