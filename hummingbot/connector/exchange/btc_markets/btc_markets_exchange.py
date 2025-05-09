import asyncio
import math
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict
from dateutil.parser import parse as dateparse

import hummingbot.connector.exchange.btc_markets.btc_markets_constants as CONSTANTS
import hummingbot.connector.exchange.btc_markets.btc_markets_utils as utils
import hummingbot.connector.exchange.btc_markets.btc_markets_web_utils as web_utils
from hummingbot.connector.exchange.btc_markets.btc_markets_api_order_book_data_source import (
    BtcMarketsAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.btc_markets.btc_markets_api_user_stream_data_source import (
    BtcMarketsAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.btc_markets.btc_markets_auth import BtcMarketsAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")


class BtcMarketsExchange(ExchangePyBase):
    """
    BtcMarketsExchange connects with BtcMarkets exchange and provides order book pricing, user account tracking and
    trading functionality.
    """

    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 btc_markets_api_key: str,
                 btc_markets_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        """
        :param btc_markets_api_key: The API key to connect to private BTCMarkets APIs.
        :param btc_markets_api_secret: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        self._api_key: str = btc_markets_api_key
        self._secret_key: str = btc_markets_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        super().__init__(client_config_map)
        self.real_time_balance_update = False

    @property
    def authenticator(self):
        return BtcMarketsAuth(
            api_key=self._api_key,
            secret_key=self._secret_key,
            time_provider=self._time_synchronizer)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self.authenticator)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BtcMarketsAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BtcMarketsAPIUserStreamDataSource(
            auth=self.authenticator,
            trading_pairs=self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.MARKETS_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.MARKETS_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.SERVER_TIME_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def name_cap(self) -> str:
        return self.name.capitalize()

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @staticmethod
    def btc_markets_order_type(order_type: OrderType) -> str:
        return order_type.name  # .upper()

    @staticmethod
    def to_hb_order_type(btc_markets_type: str) -> OrderType:
        return OrderType[btc_markets_type]

    # https://docs.btcmarkets.net/v3/#tag/OrderTypes
    def supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    # https://docs.btcmarkets.net/v3/#tag/ErrorCodes
    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_code = str(request_exception)
        is_time_synchronizer_related = CONSTANTS.INVALID_TIME_WINDOW in error_code or CONSTANTS.INVALID_TIMESTAMP in error_code or CONSTANTS.INVALID_AUTH_TIMESTAMP in error_code or CONSTANTS.INVALID_AUTH_SIGNATURE in error_code
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_FOUND) in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_FOUND) in str(cancelation_exception)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        response = await self._api_delete(
            path_url=f"{CONSTANTS.ORDERS_URL}/{tracked_order.exchange_order_id}",
            is_auth_required=True,
            limit_id=f"{CONSTANTS.ORDERS_URL}"
        )
        cancelled = True if response["clientOrderId"] == order_id else False

        return cancelled

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs
    ) -> Tuple[str, float]:
        order_result = None
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        type_str = 'Bid' if trade_type is TradeType.BUY else 'Ask'

        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        post_data = {
            "marketId": symbol,
            "side": type_str,
            "amount": amount_str,
            "selfTrade": "P",  # prevents self trading
            "clientOrderId": order_id,
            "timeInForce": CONSTANTS.TIME_IN_FORCE_GTC
        }

        if order_type == OrderType.MARKET:
            post_data["type"] = "Market"
        elif order_type == OrderType.LIMIT:
            post_data["type"] = "Limit"
            post_data["price"] = price_str
        elif order_type == OrderType.LIMIT_MAKER:
            post_data["type"] = "Limit"
            post_data["price"] = price_str
            post_data["postOnly"] = "true"

        order_result = await self._api_post(
            path_url = CONSTANTS.ORDERS_URL,
            data = post_data,
            is_auth_required = True
        )
        exchange_order_id = str(order_result["orderId"])

        return exchange_order_id, self.current_timestamp

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None
    ) -> AddedToCostTradeFee:
        """
        Calculates the estimated fee an order would pay based on the connector configuration
        :param base_currency: the order base currency
        :param quote_currency: the order quote currency
        :param order_type: the type of order (MARKET, LIMIT, LIMIT_MAKER)
        :param order_side: if the order is for buying or selling
        :param amount: the order amount
        :param price: the order price
        :return: the estimated fee for the order
        """
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
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

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        resp = await self._api_get(
            path_url=CONSTANTS.FEES_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.FEES_URL
        )
        fees_json = resp["feeByMarkets"]
        for fee_json in fees_json:
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=fee_json["marketId"])
            self._trading_fees[trading_pair] = fee_json

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            if order.exchange_order_id is not None:
                all_fills_response = await self._request_order_fills(order=order)
                updates = self._create_order_fill_updates(order=order, fill_update=all_fills_response)
                trade_updates.extend(updates)
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            is_error_caused_by_unexistent_order = '"code":"OrderNotFound"' in str(ex)
            if not is_error_caused_by_unexistent_order:
                raise

        return trade_updates

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        orderId = await order.get_exchange_order_id()
        return await self._api_get(
            path_url=CONSTANTS.TRADES_URL,
            params={
                "orderId": orderId
            },
            is_auth_required=True,
            limit_id=CONSTANTS.TRADES_URL
        )

    async def _request_order_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return await self._get_order_update(order.exchange_order_id)

    async def _get_order_update(self, orderId: int) -> Dict[str, Any]:
        return await self._api_get(
            path_url=f"{CONSTANTS.ORDERS_URL}/{orderId}",
            is_auth_required=True,
            limit_id=CONSTANTS.ORDERS_URL
        )

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._request_order_update(order=tracked_order)

        order_update = self._create_order_update(order=tracked_order, order_update=updated_order_data)
        return order_update

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
                [
                    {
                        "marketId": "BTC-AUD",
                        "baseAssetName": "BTC",
                        "quoteAssetName": "AUD",
                        "minOrderAmount": "0.0001",
                        "maxOrderAmount": "1000000",
                        "amountDecimals": "8",
                        "priceDecimals": "2",
                        "status": "Online"
                    },
                    {
                        "marketId": "LTC-AUD",
                        "baseAssetName": "LTC",
                        "quoteAssetName": "AUD",
                        "minOrderAmount": "0.001",
                        "maxOrderAmount": "1000000",
                        "amountDecimals": "8",
                        "priceDecimals": "2",
                        "status": "Post Only"
                    }
                ]
        """

        trading_pair_rules = exchange_info_dict
        retval = []
        for rule in trading_pair_rules:
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule["marketId"])

                min_order_size = Decimal(str(rule["minOrderAmount"]))
                # E.g. a price decimal of 2 means 0.01 incremental.
                price_decimal = Decimal(str(rule["priceDecimals"]))
                price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimal)))
                amount_decimal = Decimal(str(rule["amountDecimals"]))
                amount_step = Decimal("1") / Decimal(str(math.pow(10, amount_decimal)))

                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=Decimal(min_order_size),
                        max_order_size=Decimal(str(rule["maxOrderAmount"])),
                        min_price_increment=Decimal(price_step),
                        min_base_amount_increment=Decimal(amount_step),
                    )
                )

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("messageType")

                if event_type == CONSTANTS.HEARTBEAT:
                    continue
                elif event_type == CONSTANTS.ORDER_CHANGE_EVENT_TYPE:
                    exchange_order_id: Optional[str] = event_message.get("orderId")
                    client_order_id: Optional[str] = event_message.get("clientOrderId")
                    if client_order_id is None:
                        infligthOrder = await self._get_order_update(exchange_order_id)
                        client_order_id: Optional[str] = infligthOrder.get("clientOrderId")

                    fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                    updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)

                    new_state = CONSTANTS.ORDER_STATE[event_message["status"]]
                    event_timestamp = int(dateparse(event_message["timestamp"]).timestamp())

                    if fillable_order is not None:
                        is_fill_candidate_by_state = new_state in [OrderState.PARTIALLY_FILLED, OrderState.FILLED]
                        # is_fill_candidate_by_amount = fillable_order.executed_amount_base < Decimal(event_message["filled_size"])
                        if is_fill_candidate_by_state:  # and is_fill_candidate_by_amount:
                            try:
                                for trade in event_message["trades"]:
                                    fee = TradeFeeBase.new_spot_fee(
                                        fee_schema = self.trade_fee_schema(),
                                        trade_type = fillable_order.trade_type,
                                        percent_token = fillable_order.quote_asset,
                                        flat_fees = [TokenAmount(amount=Decimal(trade["fee"]), token = fillable_order.quote_asset)]
                                    )

                                    try:
                                        trade_update = TradeUpdate(
                                            trade_id=str(trade["tradeId"]),
                                            client_order_id=client_order_id,
                                            exchange_order_id=exchange_order_id,
                                            trading_pair=fillable_order.trading_pair,
                                            fee=fee,
                                            fill_base_amount=Decimal(trade["volume"]),
                                            fill_quote_amount=Decimal(trade["valueInQuoteAsset"]),
                                            fill_price=Decimal(trade["price"]),
                                            fill_timestamp=event_timestamp
                                        )

                                        self._order_tracker.process_trade_update(trade_update)
                                    except asyncio.CancelledError:
                                        raise
                                    except Exception:
                                        self.logger().exception(
                                            f"Unexpected error requesting order fills for {fillable_order.client_order_id}")

                            except asyncio.CancelledError:
                                raise
                            except Exception:
                                self.logger().exception(
                                    "Unexpected error requesting order fills for {fillable_order.client_order_id}")

                    if updatable_order is not None:
                        order_update = OrderUpdate(
                            trading_pair=updatable_order.trading_pair,
                            update_timestamp=event_timestamp,
                            new_state=new_state,
                            client_order_id=client_order_id,
                            exchange_order_id=exchange_order_id,
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == CONSTANTS.FUND_CHANGE_EVENT_TYPE:
                    asset_name = event_message.get("currency")
                    type = event_message.get("type")
                    status = event_message.get("status")
                    amount = Decimal(event_message.get("amount"))
                    if status == "Complete":
                        if type == "Deposit":
                            self._account_available_balances[asset_name] = self._account_available_balances[asset_name] + amount
                            self._account_balances[asset_name] = self._account_balances[asset_name] + amount
                        elif type == "Withdrawal":
                            self._account_balances[asset_name] = self._account_balances[asset_name] - amount
                    if status == "Pending Authorization" and type == "Withdrawal":
                        self._account_available_balances[asset_name] = self._account_available_balances[asset_name] - amount

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error while reading user events queue. Retrying after 1 second.")
                await asyncio.sleep(1.0)

    def _create_order_fill_updates(
        self,
        order: InFlightOrder,
        fill_update: Dict[str, Any]
    ) -> List[TradeUpdate]:
        updates = []
        fills_data = fill_update

        for fill_data in fills_data:
            fee = TradeFeeBase.new_spot_fee(
                fee_schema = self.trade_fee_schema(),
                trade_type = order.trade_type,
                percent_token = order.quote_asset,
                flat_fees = [TokenAmount(amount=Decimal(fill_data.get("fee")), token = order.quote_asset)]
            )

            trade_update = TradeUpdate(
                trade_id = str(fill_data.get("id")),
                client_order_id = fill_data.get("clientOrderId"),
                exchange_order_id = fill_data.get("orderId"),
                trading_pair = order.trading_pair,
                fee = fee,
                fill_base_amount = Decimal(fill_data.get("amount")),
                fill_price = Decimal(fill_data.get("price")),
                fill_quote_amount=Decimal(fill_data.get("amount")) * Decimal(fill_data["price"]),
                fill_timestamp = int(dateparse(fill_data.get("timestamp")).timestamp())
            )
            updates.append(trade_update)

        return updates

    def _create_order_update(self, order: InFlightOrder, order_update: Dict[str, Any]) -> OrderUpdate:
        new_state = CONSTANTS.ORDER_STATE[order_update["status"]]
        return OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp = int(dateparse(order_update["creationTime"]).timestamp()),
            new_state = new_state,
            client_order_id = order.client_order_id,
            exchange_order_id = str(order_update["orderId"])
        )

    async def _get_balances(self):
        return await self._api_get(
            method=RESTMethod.GET,
            path_url=CONSTANTS.BALANCE_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.BALANCE_URL
        )

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self._get_balances()

        for balance_entry in account_info:
            asset_name = balance_entry["assetName"]
            free_balance = Decimal(balance_entry["available"])
            total_balance = Decimal(balance_entry["balance"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[Dict[str, Any]]):
        mapping = bidict()
        for symbol_data in filter(utils.is_exchange_information_valid, exchange_info):
            instrument_id = symbol_data["marketId"]
            trading_pair = combine_to_hb_trading_pair(
                base = symbol_data["baseAssetName"],
                quote = symbol_data["quoteAssetName"]
            )
            if instrument_id in mapping:
                self.logger().error(
                    f"Instrument ID {instrument_id} (trading pair {trading_pair}) already present in the map "
                    f"(with trading pair {mapping[instrument_id]})."
                )
                continue
            elif trading_pair in mapping.inverse:
                self.logger().error(
                    f"Trading pair {trading_pair} (instrument ID {instrument_id}) already present in the map "
                    f"(with ID {mapping.inverse[trading_pair]})."
                )
                continue
            mapping[instrument_id] = trading_pair

        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair)
        data = await self._api_request(
            method=RESTMethod.GET,
            path_url=f"{CONSTANTS.MARKETS_URL}/{trading_pair}/ticker",
            limit_id=CONSTANTS.MARKETS_URL
        )

        return float(data["lastPrice"])
