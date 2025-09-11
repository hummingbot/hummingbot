import asyncio
import hashlib
from copy import deepcopy
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import SECOND, TWELVE_HOURS, s_decimal_NaN
from hummingbot.connector.exchange.derive import derive_constants as CONSTANTS, derive_web_utils as web_utils
from hummingbot.connector.exchange.derive.derive_api_order_book_data_source import DeriveAPIOrderBookDataSource
from hummingbot.connector.exchange.derive.derive_api_user_stream_data_source import DeriveAPIUserStreamDataSource
from hummingbot.connector.exchange.derive.derive_auth import DeriveAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DeriveExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            derive_api_secret: str = None,
            sub_id: int = None,
            account_type: str = None,
            derive_api_key: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.derive_api_key = derive_api_key
        self.derive_secret_key = derive_api_secret
        self._sub_id = sub_id
        self._account_type = account_type
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._last_trade_history_timestamp = None
        self._last_trades_poll_timestamp = 1.0
        self._instrument_ticker = []
        super().__init__(balance_asset_limit, rate_limits_share_pct)
        self.real_time_balance_update = False
        self.currencies = []

    @property
    def name(self) -> str:
        # Note: domain here refers to the entire exchange name. i.e. derive_ or derive_testnet
        return self._domain

    @staticmethod
    def derive_order_type(order_type: OrderType) -> str:
        return order_type.name.lower()

    @property
    def authenticator(self) -> DeriveAuth:
        return DeriveAuth(self.derive_api_key, self.derive_secret_key, self._sub_id, self._trading_required, self._domain)

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_currencies_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_CURRENCIES_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> Dict[str, Any]:
        res = []
        tasks = []
        if len(self._instrument_ticker) == 0:
            await self._make_trading_rules_request()
        for token in self._instrument_ticker:
            payload = {"instrument_name": token["instrument_name"]}
            tasks.append(self._api_post(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, data=payload))
        results = await safe_gather(*tasks, return_exceptions=True)
        for result in results:
            pair_price_data = result["result"]

            data = {
                "symbol": {
                    "instrument_name": pair_price_data["instrument_name"],
                    "best_bid": pair_price_data["best_bid_price"],
                    "best_ask": pair_price_data["best_ask_price"],
                }
            }
            res.append(data)
        return res

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return DeriveAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return DeriveAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Applies trading rule to quantize order price.
        """
        d_price = Decimal(round(float(f"{price:.5g}"), 6))
        return d_price

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        trade_base_fee = build_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            order_side=order_side,
            order_type=order_type,
            amount=amount,
            price=price,
            base_currency=base_currency.upper(),
            quote_currency=quote_currency.upper()
        )
        return trade_base_fee

    async def start_network(self):
        await super().start_network()
        self._rate_limits_polling_task = safe_ensure_future(self._rate_limits_polling_loop())

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_trade_history(),
            self._update_order_status(),
            self._update_balances(),
        )

    async def _update_order_status(self):
        await self._update_orders()

    async def _update_lost_orders_status(self):
        await self._update_lost_orders()

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        oid = await tracked_order.get_exchange_order_id()
        symbol = tracked_order.trading_pair
        api_params = {
            "instrument_name": symbol,
            "order_id": oid,
            "subaccount_id": int(self._sub_id)
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=api_params,
            is_auth_required=True)

        if "error" in cancel_result:
            if 'Does not exist' in cancel_result['error']['message']:
                self.logger().debug(f"The order {order_id} does not exist on Derive s. "
                                    f"No cancelation needed.")
                await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f'{cancel_result["error"]["message"]}')
        if "result" in cancel_result:
            if cancel_result["result"]["order_status"] == "cancelled":
                return True
        return False

    # === Orders placing ===

    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.LIMIT,
            price: Decimal = s_decimal_NaN,
            **kwargs) -> str:
        """
        Creates a promise to create a buy order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode('utf-8'))
        hex_order_id = f"0x{md5.hexdigest()}"
        if order_type is OrderType.MARKET:
            mid_price = self.get_mid_price(trading_pair)
            slippage = CONSTANTS.MARKET_ORDER_SLIPPAGE
            market_price = mid_price * Decimal(1 + slippage)
            price = self.quantize_order_price(trading_pair, market_price)

        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

    def sell(self,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType = OrderType.LIMIT,
             price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode('utf-8'))
        hex_order_id = f"0x{md5.hexdigest()}"
        if order_type is OrderType.MARKET:
            mid_price = self.get_mid_price(trading_pair)
            slippage = CONSTANTS.MARKET_ORDER_SLIPPAGE
            market_price = mid_price * Decimal(1 - slippage)
            price = self.quantize_order_price(trading_pair, market_price)

        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

    async def _place_order(
            self,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            trade_type: TradeType,
            order_type: OrderType,
            price: Decimal,
            **kwargs,
    ) -> Tuple[str, float]:
        """
        Creates an order on the exchange using the specified parameters.
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        if len(self._instrument_ticker) == 0:
            await self._make_trading_rules_request(self, trading_pair=symbol, fetch_pair=True)
        instrument = [next((pair for pair in self._instrument_ticker if symbol == pair["instrument_name"]), None)]
        param_order_type = "gtc"
        if order_type is OrderType.LIMIT_MAKER:
            param_order_type = "gtc"
        if order_type is OrderType.MARKET:
            param_order_type = "ioc"
        type_str = DeriveExchange.derive_order_type(order_type)

        price_type = "limit" if type_str == "limit_maker" or type_str == "limit" else "market"
        new_price = float(f"{price:.4g}")
        api_params = {
            "asset_address": instrument[0]["base_asset_address"],
            "sub_id": instrument[0]["base_asset_sub_id"],
            "limit_price": str(new_price),
            "type": "order",
            "max_fee": str(1000),
            "amount": str(amount),
            "instrument_name": symbol,
            "label": order_id,
            "is_bid": True if trade_type is TradeType.BUY else False,
            "direction": "buy" if trade_type is TradeType.BUY else "sell",
            "referral_code": CONSTANTS.REFERRAL_CODE,
            "order_type": price_type,
            "mmp": False,
            "time_in_force": param_order_type,
            "recipient_id": self._sub_id,
        }

        order_result = await self._api_post(
            path_url = CONSTANTS.CREATE_ORDER_URL,
            data=api_params,
            is_auth_required=True)

        if "error" in order_result:
            if "Self-crossing disallowed" in order_result["error"]["message"]:
                self.logger().warning(f"Error submitting order: {order_result['error']['message']}")
            else:
                raise IOError(f"Error submitting order {order_id}: {order_result['error']['message']}")
        else:
            o_order_result = order_result['result']
            o_data = o_order_result.get("order")
            o_id = str(o_data["order_id"])
            timestamp = o_data["creation_timestamp"] * 1e-3
            return (o_id, timestamp)

    async def _update_trade_history(self):
        orders = list(self._order_tracker.all_fillable_orders.values())
        all_fillable_orders = self._order_tracker.all_fillable_orders_by_exchange_order_id
        all_fills_response = []
        if len(orders) > 0:
            try:
                all_fills_response = await self._api_get(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    params={
                        "subaccount_id": self._sub_id
                    },
                    is_auth_required=True,
                    limit_id=CONSTANTS.MY_TRADES_PATH_URL)
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                self.logger().warning(
                    f"Failed to fetch trade updates. Error: {request_error}",
                    exc_info = request_error,
                )
            for trade_fill in all_fills_response["result"]["trades"]:
                self._process_trade_rs_event_message(order_fill=trade_fill, all_fillable_order=all_fillable_orders)

    def _process_trade_rs_event_message(self, order_fill: Dict[str, Any], all_fillable_order):
        exchange_order_id = str(order_fill.get("order_id"))
        fillable_order = all_fillable_order.get(exchange_order_id)
        if fillable_order is not None:
            token = order_fill["instrument_name"].split("-")[1]
            fee_asset = token

            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                trade_type=fillable_order.trade_type,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=Decimal(order_fill["trade_fee"]), token=fee_asset)]
            )

            trade_update = TradeUpdate(
                trade_id=str(order_fill["trade_id"]),
                client_order_id=fillable_order.client_order_id,
                exchange_order_id=str(order_fill["order_id"]),
                trading_pair=fillable_order.trading_pair,
                fee=fee,
                fill_base_amount=Decimal(order_fill["trade_amount"]),
                fill_quote_amount=Decimal(order_fill["trade_price"]) * Decimal(order_fill["trade_amount"]),
                fill_price=Decimal(order_fill["trade_price"]),
                fill_timestamp=order_fill["timestamp"] * 1e-3,
            )

            self._order_tracker.process_trade_update(trade_update)

        # === loops and sync related methods === #
    async def _rate_limits_polling_loop(self):
        """
        Updates the rate limits.
        """
        try:
            await self._update_rate_limits()
            await self._sleep(TWELVE_HOURS)
        except NotImplementedError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().info(
                "Unexpected error while Updating rate limits."
            )

    async def _update_rate_limits(self):
        await self._initialize_rate_limits()

    async def _initialize_rate_limits(self):
        # Update rate limits
        for r_limit_id in CONSTANTS.ENDPOINTS["limits"]["non_matching"]:
            limit_id = None
            rate_limits_copy = deepcopy(self._throttler._rate_limits)

            if self._account_type == CONSTANTS.MARKET_MAKER_ACCOUNTS_TYPE:
                limit_id = r_limit_id
                interval = SECOND
                limit = CONSTANTS.TRADER_NON_MATCHING
            else:
                limit_id = r_limit_id
                interval = SECOND
                limit = CONSTANTS.MARKET_MAKER_NON_MATCHING

            if limit_id is not None and interval is not None:
                for r_l in rate_limits_copy:
                    if r_l.limit_id == limit_id:
                        rate_limits_copy.remove(r_l)
                rate_limits_copy.append(
                    RateLimit(
                        limit_id=limit_id,
                        limit=limit,
                        time_interval=interval,
                    )
                )
            self._throttler.set_rate_limits(rate_limits_copy)

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
                    app_warning_msg="Could not fetch user events from Derive. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        user_channels = [
            f"{self._sub_id}.{CONSTANTS.USER_ORDERS_ENDPOINT_NAME}",
            f"{self._sub_id}.{CONSTANTS.USEREVENT_ENDPOINT_NAME}",
        ]
        async for event_message in self._iter_user_event_queue():
            try:
                if isinstance(event_message, dict):
                    channel: str = event_message.get("channel", None)
                    results = event_message.get("data", None)
                elif event_message is asyncio.CancelledError:
                    raise asyncio.CancelledError
                else:
                    raise Exception(event_message)
                if channel not in user_channels:
                    self.logger().error(
                        f"Unexpected message in user stream: {event_message}.", exc_info=True)
                    continue
                if channel == user_channels[0] and results is not None:
                    for order_msg in results:
                        self._process_order_message(order_msg)
                elif channel == user_channels[1] and results is not None:
                    for trade_msg in results:
                        await self._process_trade_message(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _process_trade_message(self, trade: Dict[str, Any], client_order_id: Optional[str] = None):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        Example Trade:
        """
        exchange_order_id = str(trade.get("order_id", ""))
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

        if tracked_order is None:
            all_orders = self._order_tracker.all_fillable_orders
            for k, v in all_orders.items():
                await v.get_exchange_order_id()
            _cli_tracked_orders = [o for o in all_orders.values() if exchange_order_id == o.exchange_order_id]
            if not _cli_tracked_orders:
                self.logger().debug(f"Ignoring trade message with id {client_order_id}: not in in_flight_orders.")
                return
            tracked_order = _cli_tracked_orders[0]
        trading_pair = tracked_order.trading_pair
        if trade["instrument_name"] == trading_pair:
            fee_asset = trading_pair.split("-")[1]
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                trade_type=tracked_order.trade_type,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=Decimal(trade["trade_fee"]), token=fee_asset)]
            )
            trade_update: TradeUpdate = TradeUpdate(
                trade_id=str(trade["trade_id"]),
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(trade["order_id"]),
                trading_pair=tracked_order.trading_pair,
                fill_timestamp=trade["timestamp"] * 1e-3,
                fill_price=Decimal(trade["trade_price"]),
                fill_base_amount=Decimal(trade["trade_amount"]),
                fill_quote_amount=Decimal(trade["trade_price"]) * Decimal(trade["trade_amount"]),
                fee=fee,
            )
            self._order_tracker.process_trade_update(trade_update)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancelation or failure event if needed.

        :param order_msg: The order response from either REST or web socket API (they are of the same format)

        Example Order:
        """
        client_order_id = str(order_msg.get("label", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return
        current_state = order_msg["order_status"]
        order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_msg["last_update_timestamp"] * 1e-3,
            new_state=CONSTANTS.ORDER_STATE[current_state],
            client_order_id=order_msg["label"],
            exchange_order_id=str(order_msg["order_id"]),
        )
        self._order_tracker.process_order_update(order_update=order_update)

    async def _format_trading_rules(self, exchange_info_dict: List) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        Parameters
        ----------
        exchange_info_dict:
            Trading rules dictionary response from the exchange

        {
            "result": {
                "instruments": [
                {
                    "instrument_type": "erc20",
                    "instrument_name": "ETH-USDC",
                    "scheduled_activation": 1728508925,
                    "scheduled_deactivation": 9223372036854776000,
                    "is_active": true,
                    "tick_size": "0.01",
                    "minimum_amount": "0.1",
                    "maximum_amount": "1000",
                    "amount_step": "0.01",
                    "mark_price_fee_rate_cap": "0",
                    "maker_fee_rate": "0.0015",
                    "taker_fee_rate": "0.0015",
                    "base_fee": "0.1",
                    "base_currency": "ETH",
                    "quote_currency": "USDC",
                    "option_details": null,
                    "perp_details": null,
                    "erc20_details": {
                    "decimals": 18,
                    "underlying_erc20_address": "0x15CEcd5190A43C7798dD2058308781D0662e678E",
                    "borrow_index": "1",
                    "supply_index": "1"
                    },
                    "base_asset_address": "0xE201fCEfD4852f96810C069f66560dc25B2C7A55",
                    "base_asset_sub_id": "0",
                    "pro_rata_fraction": "0",
                    "fifo_min_allocation": "0",
                    "pro_rata_amount_step": "1"
                }
                ],
                "pagination": {
                "num_pages": 1,
                "count": 1
                }
            },
            "id": "0f9131b4-2502-4f8e-afa4-adfce67a6509"
        }
        """

        trading_pair_rules = exchange_info_dict
        retval = []
        for rule in filter(web_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule["instrument_name"])
                min_order_size = rule["minimum_amount"]
                step_size = rule["amount_step"]
                tick_size = rule["tick_size"]
                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=Decimal(min_order_size),
                        min_price_increment=Decimal(str(tick_size)),
                        min_base_amount_increment=Decimal(step_size),
                    )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {exchange_info_dict}. Skipping.",
                                    exc_info=True)
        return retval

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List):
        mapping = bidict()

        for _info in filter(web_utils.is_exchange_information_valid, exchange_info):
            ex_name = _info["instrument_name"]

            base, quote = ex_name.split("-")
            trading_pair = combine_to_hb_trading_pair(base, quote)
            mapping[ex_name] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _update_balances(self):
        """
        Calls the REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_post(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            data={"subaccount_id": self._sub_id},
            is_auth_required=True)
        if "error" in account_info:
            self.logger().error(f"Error fetching account balances: {account_info['error']['message']}")
            raise
        else:
            balances = account_info["result"]["collaterals"]
            for balance_entry in balances:
                asset_name = balance_entry["asset_name"]
                free_balance = Decimal(balance_entry["amount"])
                total_balance = Decimal(balance_entry["amount"])
                self._account_available_balances[asset_name] = free_balance
                self._account_balances[asset_name] = total_balance
                remote_asset_names.add(asset_name)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        oid = await tracked_order.get_exchange_order_id()
        client_order_id = tracked_order.client_order_id
        order_update = await self._api_post(
            path_url=CONSTANTS.ORDER_STATUS_PAATH_URL,
            data={
                "subaccount_id": self._sub_id,
                "order_id": oid
            },
            is_auth_required=True)
        if "error" in order_update:
            self.logger().debug(f"Error fetching order status for {client_order_id}: {order_update['error']['message']}")
        if "result" in order_update:
            current_state = order_update["result"]["order_status"]
            _order_update: OrderUpdate = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=order_update["result"]["last_update_timestamp"] * 1e-3,
                new_state=CONSTANTS.ORDER_STATE[current_state],
                client_order_id=order_update["result"]["label"] or client_order_id,
                exchange_order_id=str(order_update["result"]["order_id"]),
            )
            return _order_update

    async def _update_order_fills_from_trades(self):
        """
        This is intended to be a backup measure to get filled events with trade ID for orders,
        in case derive's user stream events are not working.
        NOTE: It is not required to copy this functionality in other connectors.
        This is separated from _update_order_status which only updates the order status without producing filled
        events, since derive's get order endpoint does not return trade IDs.
        The minimum poll interval for order status is 10 seconds.
        """
        small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

        if (long_interval_current_tick > long_interval_last_tick
                or (self.in_flight_orders and small_interval_current_tick > small_interval_last_tick)):
            query_time = int(self._last_trades_poll_timestamp * 1e3)
            self._last_trades_poll_timestamp = self._time_synchronizer.time()
            order_by_exchange_id_map = {}
            for order in self._order_tracker.all_fillable_orders.values():
                order_by_exchange_id_map[order.exchange_order_id] = order

            tasks = []
            trading_pairs = self.trading_pairs
            for trading_pair in trading_pairs:
                params = {
                    "instrument_name": trading_pair,
                    "subaccount_id": self._sub_id,
                }
                if self._last_poll_timestamp > 0:
                    params["from_timestamp"] = query_time
                tasks.append(self._api_get(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    params=params,
                    is_auth_required=True))

            self.logger().debug(f"Polling for order fills of {len(tasks)} trading pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for trades, trading_pair in zip(results, trading_pairs):
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                if len(trades) == 0:
                    continue
                for trade in trades["result"]["trades"]:
                    exchange_order_id = str(trade["order_id"])
                    if exchange_order_id in order_by_exchange_id_map:
                        # This is a fill for a tracked order
                        tracked_order = order_by_exchange_id_map[exchange_order_id]
                        token = trade["instrument_name"].split("-")[1]
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=token,
                            flat_fees=[TokenAmount(amount=Decimal(trade["trade_fee"]), token=token)]
                        )
                        trade_update = TradeUpdate(
                            trade_id=str(trade["trade_id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(trade["trade_amount"]),
                            fill_quote_amount=Decimal(trade["trade_amount"]) * Decimal(trade["trade_price"]),
                            fill_price=Decimal(trade["trade_price"]),
                            fill_timestamp=trade["timestamp"] * 1e-3,
                        )
                        self._order_tracker.process_trade_update(trade_update)
                    elif self.is_confirmed_new_order_filled_event(str(trade["trade_id"]), exchange_order_id, trading_pair):
                        token = trade["instrument_name"].split("-")[1]
                        # This is a fill of an order registered in the DB but not tracked any more
                        self._current_trade_fills.add(TradeFillOrderDetails(
                            market=self.display_name,
                            exchange_trade_id=str(trade["trade_id"]),
                            symbol=trading_pair))
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                timestamp=float(trade["timestamp"]) * 1e-3,
                                order_id=self._exchange_order_ids.get(str(trade["order_id"]), None),
                                trading_pair=trading_pair,
                                trade_type=TradeType.BUY if trade["direction"] == 'buy' else TradeType.SELL,
                                order_type=OrderType.MARKET if trade["liquidity_role"] == 'taker' else OrderType.LIMIT,
                                price=Decimal(trade["trade_price"]),
                                amount=Decimal(trade["trade_amount"]),
                                trade_fee=DeductedFromReturnsTradeFee(
                                    flat_fees=[
                                        TokenAmount(
                                            token,
                                            Decimal(trade["trade_fee"])
                                        )
                                    ]
                                ),
                                exchange_trade_id=str(trade["trade_id"])
                            ))
                        self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "instrument_name": trading_pair,
                    "order_id": exchange_order_id,
                    "subaccount_id": self._sub_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_PATH_URL)

            for trade in all_fills_response["result"]["trades"]:
                token = trade["instrument_name"].split("-")[1]
                exchange_order_id = str(trade["order_id"])
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=token,
                    flat_fees=[TokenAmount(amount=Decimal(trade["trade_fee"]), token=token)]
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade["trade_id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["trade_amount"]),
                    fill_quote_amount=Decimal(trade["trade_amount"]) * Decimal(trade["trade_price"]),
                    fill_price=Decimal(trade["trade_price"]),
                    fill_timestamp=trade["timestamp"] * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        await self.trading_pair_symbol_map()
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        payload = {"instrument_name": exchange_symbol}
        response = await self._api_post(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
                                        data=payload)

        return response["result"]["mark_price"]

    async def get_last_traded_prices(self, trading_pairs: List[str] = None) -> Dict[str, float]:
        if trading_pairs is None:
            trading_pairs = []

        symbol_map = await self.trading_pair_symbol_map()
        exchange_symbols = await asyncio.gather(*[
            self.exchange_symbol_associated_to_pair(trading_pair=pair) for pair in trading_pairs
        ])
        payloads = [{"instrument_name": symbol} for symbol in exchange_symbols]
        responses = await asyncio.gather(*[
            self._api_post(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, data=payload)
            for payload in payloads
        ])
        last_traded_prices = {}
        for ticker in responses:
            instrument_name = ticker["result"]["instrument_name"]
            if instrument_name in symbol_map.keys():
                mapped_name = await self.trading_pair_associated_to_exchange_symbol(instrument_name)
                last_traded_prices[mapped_name] = float(ticker["result"]["mark_price"])
        return last_traded_prices

    async def _make_network_check_request(self):
        await self._api_get(path_url=self.check_network_request_path)

    async def _make_currency_request(self) -> Any:
        currencies = await self._api_post(path_url=self.trading_pairs_request_path, data={
            "instrument_type": "erc20",
        })
        self.currencies.append(currencies)
        return currencies

    async def _make_trading_rules_request(self, trading_pair: Optional[str] = None, fetch_pair: Optional[bool] = False) -> Any:
        self._instrument_ticker = []
        exchange_infos = []
        if not fetch_pair:
            if len(self.currencies) == 0:
                self.currencies.append(await self._make_currency_request())
            for currency in self.currencies[0]["result"]:
                payload = {
                    "expired": True,
                    "instrument_type": "erc20",
                    "currency": currency["currency"],
                }

                exchange_info = await self._api_post(path_url=self.trading_currencies_request_path, data=payload)
                if "error" in exchange_info:
                    if 'Instrument not found' in exchange_info['error']['message']:
                        self.logger().debug(f"Ignoring currency {currency['currency']}: not supported sport.")
                        continue
                    self.logger().warning(f"Error: {exchange_info['error']['message']}")
                    raise

                exchange_info["result"]["instruments"][0]["spot_price"] = currency["spot_price"]
                self._instrument_ticker.append(exchange_info["result"]["instruments"][0])
                exchange_infos.append(exchange_info["result"]["instruments"][0])
        else:
            exchange_info = await self._api_post(path_url=self.trading_pairs_request_path, data={
                "expired": True,
                "instrument_type": "erc20",
                "currency": trading_pair.split("-")[0],
            })
            exchange_info["result"]["instruments"][0]["spot_price"] = currency["spot_price"]
            self._instrument_ticker.append(exchange_info["result"]["instruments"][0])
            exchange_infos.append(exchange_info["result"]["instruments"][0])
        return exchange_infos

    async def _make_trading_pairs_request(self) -> Any:
        exchange_infos = []
        if len(self.currencies) == 0:
            self.currencies.append(await self._make_currency_request())
        for currency in self.currencies[0]["result"]:

            payload = {
                "expired": True,
                "instrument_type": "erc20",
                "currency": currency["currency"],
            }

            exchange_info = await self._api_post(path_url=self.trading_currencies_request_path, data=payload)
            if "error" in exchange_info:
                if 'Instrument not found' in exchange_info['error']['message']:
                    self.logger().debug(f"Ignoring currency {currency['currency']}: not supported sport.")
                    continue
                self.logger().error(f"Error: {currency['message']}")
                raise
            exchange_infos.append(exchange_info["result"]["instruments"][0])
        return exchange_infos
