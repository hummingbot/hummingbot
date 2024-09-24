import asyncio
import math
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.bit2c import bit2c_constants as CONSTANTS, bit2c_utils, bit2c_web_utils as web_utils
from hummingbot.connector.exchange.bit2c.bit2c_api_order_book_data_source import Bit2cAPIOrderBookDataSource
from hummingbot.connector.exchange.bit2c.bit2c_api_user_stream_data_source import Bit2cAPIUserStreamDataSource
from hummingbot.connector.exchange.bit2c.bit2c_auth import Bit2cAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class Bit2cExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    SHORT_POLL_INTERVAL = 1.0
    LONG_POLL_INTERVAL = 1.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 bit2c_api_key: str,
                 bit2c_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = bit2c_api_key
        self.secret_key = bit2c_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_bit2c_timestamp = 1.0
        self._last_order_time = 0  # Initialize last order time
        self._order_wait_time = 0.75  # Set this after rigorous testing and finetuning on bit2c exchange
        self._last_balance_time = 0  # Initialize last balance time
        self._balance_wait_time = 0.75  # Set this after rigorous testing and finetuning on bit2c exchange
        super().__init__(client_config_map)

    @staticmethod
    def bit2c_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(bit2c_type: str) -> OrderType:
        return OrderType[bit2c_type]

    @property
    def authenticator(self):
        return Bit2cAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "bit2c"

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
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_BOOK_PATH_URL)
        return pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return Bit2cAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return Bit2cAPIUserStreamDataSource(
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
        # Ensure that sufficient time has passed since the last order
        time_since_last_order = time.time() - self._last_order_time
        if time_since_last_order < self._order_wait_time:
            await asyncio.sleep(self._order_wait_time - time_since_last_order)

        amount_str = f"{amount:f}"
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {"Pair": symbol}
        if order_type is OrderType.LIMIT:
            price_str = f"{price:f}"
            api_params["Price"] = price_str
            api_params["Amount"] = amount_str
            isBid = True if trade_type is TradeType.BUY else False
            api_params["isBid"] = isBid
        if order_type is OrderType.MARKET:
            if trade_type is TradeType.SELL:
                api_params["Amount"] = amount_str
            if trade_type is TradeType.BUY:
                total_str = f"{amount * price:f}"   # TODO: Check if this is correct
                api_params["Total"] = total_str

        path_url = ""
        if order_type is OrderType.LIMIT:
            path_url = CONSTANTS.CREATE_LIMIT_ORDER_PATH_URL
        elif order_type is OrderType.MARKET:
            if trade_type is TradeType.SELL:
                path_url = CONSTANTS.CREATE_MARKET_SELL_ORDER_PATH_URL
            if trade_type is TradeType.BUY:
                path_url = CONSTANTS.CREATE_MARKET_SELL_ORDER_PATH_URL
        order_result = await self._api_post(
            path_url=path_url,
            data=api_params,
            is_auth_required=True)

        # Update the last order time
        self._last_order_time = time.time()

        if order_result.get("OrderResponse", {}).get("HasError", False):
            error_message = order_result["OrderResponse"].get("Error", "Unknown error") if order_result.get("OrderResponse").get("Error") else order_result["OrderResponse"].get("Message", "Unknown error")
            raise Exception(f"Error placing order on Bit2c: {error_message}")
        if order_result.get("error") is not None:
            raise Exception(f"Error placing order on Bit2c: {order_result.get('error')}")

        o_id = str(order_result.get("NewOrder", {}).get("id"))
        transact_time = time.time()

        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = await tracked_order.get_exchange_order_id()
        api_params = {
            "id": int(exchange_order_id),
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            data=api_params,
            is_auth_required=True)

        error_message = None
        if cancel_result.get("OrderResponse", {}).get("HasError", False):
            error_message = cancel_result["OrderResponse"].get("Error", "Unknown error") if cancel_result.get("OrderResponse").get("Error") else cancel_result["OrderResponse"].get("Message", "Unknown error")

        if cancel_result.get("error") is not None:
            error_message = cancel_result.get("error")

        if error_message is not None:
            raise Exception(f"Error cancelling order on Bit2c: {error_message}")

        return True

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "symbols": [
                {
                    "symbol": "BtcNis",
                    "baseAsset": "BTC",
                    "quoteAsset": "NIS",
                    "baseAssetPrecision": 8,
                    "quoteAssetPrecision": 2,
                    "minNotional": 13.0,
                },
                ...
            ]
        }
        """
        trading_pair_rules = exchange_info_dict.get("symbols", [])
        retval = []
        for rule in filter(bit2c_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("symbol"))

                min_order_size = min_base_amount_increment = Decimal("1") / (Decimal("10") ** rule.get("baseAssetPrecision"))
                min_price_increment = Decimal("1") / (Decimal("10") ** rule.get("quoteAssetPrecision"))
                min_notional = Decimal(rule.get("minNotional"))

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=min_price_increment,
                                min_base_amount_increment=min_base_amount_increment,
                                min_notional_size=min_notional))

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        Bit2c does not provide a way to listen to user stream events through the websocket.
        """
        pass

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.GET_TRADES_PATH_URL,
                params={
                    "id": exchange_order_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.GET_TRADES_PATH_URL)

            for trade in all_fills_response:
                # Bit2c API returns the action as 0 for buy and 1 for sell, we are only concerned with buy and sell
                action = int(trade.get("action"))
                if action not in [0, 1]:
                    continue

                # Skip the trade if the action does not match the order's trade type
                if (action == 0 and order.trade_type is TradeType.SELL) or \
                        (action == 1 and order.trade_type is TradeType.BUY):
                    continue
                exchange_order_id = str(exchange_order_id)

                # Bit2c API returns the fee coin as "₪" for NIS
                if trade.get("feeCoin") == "₪":     # \u20aa is the unicode for "₪", symbol for NIS
                    trade["feeCoin"] = "NIS"

                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=trade["feeCoin"],
                    flat_fees=[TokenAmount(amount=Decimal(trade["feeAmount"]), token=trade["feeCoin"])]
                )
                trade_update = TradeUpdate(
                    trade_id=f'{exchange_order_id}-{trade["reference"]}-{trade["ticks"]}-{trade["secondAmount"]}',
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=abs(Decimal(trade["firstAmount"])),
                    fill_quote_amount=abs(Decimal(trade["secondAmount"])),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=float(trade["ticks"]),
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.GET_ORDER_PATH_URL,
            params={
                "id": int(exchange_order_id)},
            is_auth_required=True)

        status = int(updated_order_data["status_type"])

        new_state = OrderState.PENDING_CREATE
        if status == 1:
            if math.isclose(Decimal(str(updated_order_data["amount"])), Decimal(str(updated_order_data["initialAmount"]))):
                new_state = OrderState.OPEN
            else:
                new_state = OrderState.PARTIALLY_FILLED
        if status == 5:
            if math.isclose(Decimal(str(updated_order_data["amount"])), Decimal("0")):
                new_state = OrderState.FILLED
            else:
                new_state = OrderState.CANCELED

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(exchange_order_id),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=time.time(),
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        # Ensure that sufficient time has passed since the last order
        time_since_last_balance = time.time() - self._last_balance_time
        if time_since_last_balance < self._balance_wait_time:
            await asyncio.sleep(self._balance_wait_time - time_since_last_balance)

        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=True)

        """
        {
            "AVAILABLE_NIS": 68299.5000000000000000,
            "NIS": 100000.00000000,
            "AVAILABLE_BTC": 24.2409524700000000,
            "BTC": 24.33095247,
        }
        """

        # let's separate the coin balances and available balances
        # traverse the dict, separate based on the key having "AVAILABLE_" prefix
        total_balances = {}
        available_balances = {}
        for key, value in account_info.items():
            if key.startswith("AVAILABLE_"):
                asset_name = key.replace("AVAILABLE_", "")
                available_balances[asset_name] = Decimal(value)
            else:
                asset_name = key
                total_balances[asset_name] = Decimal(value)

        for asset_name in total_balances.keys():
            if asset_name not in available_balances:
                available_balances[asset_name] = Decimal(0)
            self._account_available_balances[asset_name] = available_balances[asset_name]
            self._account_balances[asset_name] = total_balances[asset_name]
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(bit2c_utils.is_exchange_information_valid, exchange_info["symbols"]):
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=symbol_data["baseAsset"],
                                                                        quote=symbol_data["quoteAsset"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL.format(symbol)
        )

        return float(resp_json["ll"])

    async def _make_trading_rules_request(self) -> Any:
        return CONSTANTS.EXCHANGE_INFO

    async def _make_trading_pairs_request(self) -> Any:
        return CONSTANTS.EXCHANGE_INFO

    async def _api_request(
            self,
            path_url,
            overwrite_url: Optional[str] = None,
            method: RESTMethod = RESTMethod.GET,
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            is_auth_required: bool = False,
            return_err: bool = False,
            limit_id: Optional[str] = None,
            headers: Optional[Dict[str, Any]] = None,
            **kwargs,
    ) -> Dict[str, Any]:

        last_exception = None
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()

        url = overwrite_url or await self._api_request_url(path_url=path_url, is_auth_required=is_auth_required)

        for _ in range(2):
            try:
                request_result = await rest_assistant.execute_request(
                    url=url,
                    params=params,
                    data=data,
                    method=method,
                    is_auth_required=is_auth_required,
                    return_err=return_err,
                    throttler_limit_id=limit_id if limit_id else path_url,
                    headers=headers,
                )

                if "error" in request_result and "is not bigger than last nonce" in request_result["error"]:
                    request_result = await self._api_request(
                        path_url,
                        overwrite_url=overwrite_url,
                        method=method,
                        params=params,
                        data=data,
                        is_auth_required=is_auth_required,
                        return_err=return_err,
                        limit_id=limit_id,
                        headers=headers,
                    )
                    return request_result

                return request_result
            except IOError as request_exception:
                last_exception = request_exception
                if self._is_request_exception_related_to_time_synchronizer(request_exception=request_exception):
                    self._time_synchronizer.clear_time_offset_ms_samples()
                    await self._update_time_synchronizer()
                else:
                    raise

        # Failed even after the last retry
        raise last_exception
