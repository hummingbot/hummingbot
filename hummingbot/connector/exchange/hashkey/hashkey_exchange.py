import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

import hummingbot.connector.exchange.hashkey.hashkey_constants as CONSTANTS
import hummingbot.connector.exchange.hashkey.hashkey_utils as hashkey_utils
import hummingbot.connector.exchange.hashkey.hashkey_web_utils as web_utils
from hummingbot.connector.exchange.hashkey.hashkey_api_order_book_data_source import HashkeyAPIOrderBookDataSource
from hummingbot.connector.exchange.hashkey.hashkey_api_user_stream_data_source import HashkeyAPIUserStreamDataSource
from hummingbot.connector.exchange.hashkey.hashkey_auth import HashkeyAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None
s_decimal_NaN = Decimal("nan")


class HashkeyExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 hashkey_api_key: str,
                 hashkey_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = hashkey_api_key
        self.secret_key = hashkey_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_hashkey_timestamp = 1.0
        super().__init__(client_config_map)

    @staticmethod
    def hashkey_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(hashkey_type: str) -> OrderType:
        return OrderType[hashkey_type]

    @property
    def authenticator(self):
        return HashkeyAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "hashkey_global":
            return "hashkey"
        else:
            return self._domain

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
        return CONSTANTS.SERVER_TIME_PATH_URL

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
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for the request" in error_description)
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_cancel_order_not_found_in_the_exchange when replacing the
        # dummy implementation
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return HashkeyAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return HashkeyAPIUserStreamDataSource(
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
        trade_base_fee = build_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            order_side=order_side,
            order_type=order_type,
            amount=amount,
            price=price,
            base_currency=base_currency,
            quote_currency=quote_currency
        )
        return trade_base_fee

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        amount_str = f"{amount:f}"
        type_str = self.hashkey_order_type(order_type)

        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {"symbol": symbol,
                      "side": side_str,
                      "quantity": amount_str,
                      "type": type_str,
                      "recvWindow": 10000,
                      "newClientOrderId": order_id}
        path_url = CONSTANTS.ORDER_PATH_URL

        if order_type != OrderType.MARKET:
            api_params["price"] = f"{price:f}"
        else:
            path_url = CONSTANTS.MARKET_ORDER_PATH_URL

        if order_type == OrderType.LIMIT:
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC

        order_result = await self._api_post(
            path_url=path_url,
            params=api_params,
            is_auth_required=True,
            trading_pair=trading_pair,
            headers={"INPUT-SOURCE": CONSTANTS.HBOT_BROKER_ID},
        )

        o_id = str(order_result["orderId"])
        transact_time = int(order_result["transactTime"]) * 1e-3
        return (o_id, transact_time)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        api_params = {}
        if tracked_order.exchange_order_id:
            api_params["orderId"] = tracked_order.exchange_order_id
        else:
            api_params["clientOrderId"] = tracked_order.client_order_id
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params=api_params,
            is_auth_required=True)

        if isinstance(cancel_result, dict) and "clientOrderId" in cancel_result:
            return True
        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "timezone": "UTC",
            "serverTime": "1703696385826",
            "brokerFilters": [],
            "symbols": [
                {
                    "symbol": "ETHUSD",
                    "symbolName": "ETHUSD",
                    "status": "TRADING",
                    "baseAsset": "ETH",
                    "baseAssetName": "ETH",
                    "baseAssetPrecision": "0.0001",
                    "quoteAsset": "USD",
                    "quoteAssetName": "USD",
                    "quotePrecision": "0.0000001",
                    "retailAllowed": true,
                    "piAllowed": true,
                    "corporateAllowed": true,
                    "omnibusAllowed": true,
                    "icebergAllowed": false,
                    "isAggregate": false,
                    "allowMargin": false,
                    "filters": [
                        {
                            "minPrice": "0.01",
                            "maxPrice": "100000.00000000",
                            "tickSize": "0.01",
                            "filterType": "PRICE_FILTER"
                        },
                        {
                            "minQty": "0.005",
                            "maxQty": "53",
                            "stepSize": "0.0001",
                            "filterType": "LOT_SIZE"
                        },
                        {
                            "minNotional": "10",
                            "filterType": "MIN_NOTIONAL"
                        },
                        {
                            "minAmount": "10",
                            "maxAmount": "10000000",
                            "minBuyPrice": "0",
                            "filterType": "TRADE_AMOUNT"
                        },
                        {
                            "maxSellPrice": "0",
                            "buyPriceUpRate": "0.2",
                            "sellPriceDownRate": "0.2",
                            "filterType": "LIMIT_TRADING"
                        },
                        {
                            "buyPriceUpRate": "0.2",
                            "sellPriceDownRate": "0.2",
                            "filterType": "MARKET_TRADING"
                        },
                        {
                            "noAllowMarketStartTime": "0",
                            "noAllowMarketEndTime": "0",
                            "limitOrderStartTime": "0",
                            "limitOrderEndTime": "0",
                            "limitMinPrice": "0",
                            "limitMaxPrice": "0",
                            "filterType": "OPEN_QUOTE"
                        }
                    ]
                }
            ],
            "options": [],
            "contracts": [],
            "coins": [
                {
                    "orgId": "9001",
                    "coinId": "BTC",
                    "coinName": "BTC",
                    "coinFullName": "Bitcoin",
                    "allowWithdraw": true,
                    "allowDeposit": true,
                    "chainTypes": [
                        {
                            "chainType": "Bitcoin",
                            "withdrawFee": "0",
                            "minWithdrawQuantity": "0.0005",
                            "maxWithdrawQuantity": "0",
                            "minDepositQuantity": "0.0001",
                            "allowDeposit": true,
                            "allowWithdraw": true
                        }
                    ]
                },
                {
                    "orgId": "9001",
                    "coinId": "ETH",
                    "coinName": "ETH",
                    "coinFullName": "Ethereum",
                    "allowWithdraw": true,
                    "allowDeposit": true,
                    "chainTypes": [
                        {
                            "chainType": "ERC20",
                            "withdrawFee": "0",
                            "minWithdrawQuantity": "0",
                            "maxWithdrawQuantity": "0",
                            "minDepositQuantity": "0.0075",
                            "allowDeposit": true,
                            "allowWithdraw": true
                        }
                    ]
                },
                {
                    "orgId": "9001",
                    "coinId": "USD",
                    "coinName": "USD",
                    "coinFullName": "USD",
                    "allowWithdraw": true,
                    "allowDeposit": true,
                    "chainTypes": []
                }
            ]
        }
        """
        trading_pair_rules = exchange_info_dict.get("symbols", [])
        retval = []
        for rule in trading_pair_rules:
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("symbol"))

                trading_filter_info = {item["filterType"]: item for item in rule.get("filters", [])}

                min_order_size = trading_filter_info.get("LOT_SIZE", {}).get("minQty")
                min_price_increment = trading_filter_info.get("PRICE_FILTER", {}).get("minPrice")
                min_base_amount_increment = rule.get("baseAssetPrecision")
                min_notional_size = trading_filter_info.get("TRADE_AMOUNT", {}).get("minAmount")

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=Decimal(min_order_size),
                                min_price_increment=Decimal(min_price_increment),
                                min_base_amount_increment=Decimal(min_base_amount_increment),
                                min_notional_size=Decimal(min_notional_size)))

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule.get('symbol')}. Skipping.")
        return retval

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
        async for event_messages in self._iter_user_event_queue():
            if isinstance(event_messages, dict) and "ping" in event_messages:
                continue

            for event_message in event_messages:
                try:
                    event_type = event_message.get("e")
                    if event_type == "executionReport":
                        execution_type = event_message.get("X")
                        client_order_id = event_message.get("c")
                        tracked_order = self._order_tracker.fetch_order(client_order_id=client_order_id)
                        if tracked_order is not None:
                            if execution_type in ["PARTIALLY_FILLED", "FILLED"]:
                                fee = TradeFeeBase.new_spot_fee(
                                    fee_schema=self.trade_fee_schema(),
                                    trade_type=tracked_order.trade_type,
                                    flat_fees=[TokenAmount(amount=Decimal(event_message["n"]), token=event_message["N"])]
                                )
                                trade_update = TradeUpdate(
                                    trade_id=str(event_message["d"]),
                                    client_order_id=client_order_id,
                                    exchange_order_id=str(event_message["i"]),
                                    trading_pair=tracked_order.trading_pair,
                                    fee=fee,
                                    fill_base_amount=Decimal(event_message["l"]),
                                    fill_quote_amount=Decimal(event_message["l"]) * Decimal(event_message["L"]),
                                    fill_price=Decimal(event_message["L"]),
                                    fill_timestamp=int(event_message["E"]) * 1e-3,
                                )
                                self._order_tracker.process_trade_update(trade_update)

                            order_update = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=int(event_message["E"]) * 1e-3,
                                new_state=CONSTANTS.ORDER_STATE[event_message["X"]],
                                client_order_id=client_order_id,
                                exchange_order_id=str(event_message["i"]),
                            )
                            self._order_tracker.process_order_update(order_update=order_update)

                    elif event_type == "outboundAccountInfo":
                        balances = event_message["B"]
                        for balance_entry in balances:
                            asset_name = balance_entry["a"]
                            free_balance = Decimal(balance_entry["f"])
                            total_balance = Decimal(balance_entry["f"]) + Decimal(balance_entry["l"])
                            self._account_available_balances[asset_name] = free_balance
                            self._account_balances[asset_name] = total_balance

                except asyncio.CancelledError:
                    raise
                except Exception:
                    self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                    await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = int(order.exchange_order_id)
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            fills_data = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "clientOrderId": order.client_order_id,
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_PATH_URL)
            if fills_data is not None:
                for trade in fills_data:
                    exchange_order_id = str(trade["orderId"])
                    if exchange_order_id != str(order.exchange_order_id):
                        continue
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent_token=trade["commissionAsset"],
                        flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
                    )
                    trade_update = TradeUpdate(
                        trade_id=str(trade["ticketId"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(trade["qty"]),
                        fill_quote_amount=Decimal(trade["price"]) * Decimal(trade["qty"]),
                        fill_price=Decimal(trade["price"]),
                        fill_timestamp=int(trade["time"]) * 1e-3,
                    )
                    trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params={
                "origClientOrderId": tracked_order.client_order_id},
            is_auth_required=True)

        new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["orderId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=int(updated_order_data["updateTime"]) * 1e-3,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=True)
        balances = account_info["balances"]
        for balance_entry in balances:
            asset_name = balance_entry["asset"]
            free_balance = Decimal(balance_entry["free"])
            total_balance = Decimal(balance_entry["total"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(hashkey_utils.is_exchange_information_valid, exchange_info["symbols"]):
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=symbol_data["baseAsset"],
                                                                        quote=symbol_data["quoteAsset"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        }
        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.LAST_TRADED_PRICE_PATH,
            params=params,
        )

        return float(resp_json["price"])

    async def _api_request(self,
                           path_url,
                           method: RESTMethod = RESTMethod.GET,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           return_err: bool = False,
                           limit_id: Optional[str] = None,
                           trading_pair: Optional[str] = None,
                           **kwargs) -> Dict[str, Any]:
        last_exception = None
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.rest_url(path_url, domain=self.domain)
        local_headers = {
            "Content-Type": "application/x-www-form-urlencoded"}
        for _ in range(2):
            try:
                request_result = await rest_assistant.execute_request(
                    url=url,
                    params=params,
                    data=data,
                    method=method,
                    is_auth_required=is_auth_required,
                    return_err=return_err,
                    headers=local_headers,
                    throttler_limit_id=limit_id if limit_id else path_url,
                )
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
