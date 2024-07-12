import asyncio
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.bitstamp import (
    bitstamp_constants as CONSTANTS,
    bitstamp_utils,
    bitstamp_web_utils as web_utils,
)
from hummingbot.connector.exchange.bitstamp.bitstamp_api_order_book_data_source import BitstampAPIOrderBookDataSource
from hummingbot.connector.exchange.bitstamp.bitstamp_api_user_stream_data_source import BitstampAPIUserStreamDataSource
from hummingbot.connector.exchange.bitstamp.bitstamp_auth import BitstampAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class BitstampExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 bitstamp_api_key: str,
                 bitstamp_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 time_provider: Optional[Callable] = None,
                 ):
        self.api_key = bitstamp_api_key
        self.secret_key = bitstamp_api_secret
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._domain = domain
        self._time_provider = time_provider
        self._last_trades_poll_bitstamp_timestamp = 1.0

        super().__init__(client_config_map)
        self._real_time_balance_update = False
        self._trading_fees

    @staticmethod
    def bitstamp_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(bitstamp_type: str) -> OrderType:
        return OrderType[bitstamp_type]

    @property
    def authenticator(self):
        return BitstampAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "bitstamp"

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
        return CONSTANTS.STATUS_URL

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
        pairs_prices = await self._api_get(path_url=CONSTANTS.CURRENCIES_URL)
        return pairs_prices

    def convert_from_exchange_trading_pair(self, exchange_trading_pair: str) -> Optional[str]:
        try:
            base_asset, quote_asset = exchange_trading_pair.split("/")
        except Exception as e:
            raise ValueError(f"Error parsing the trading pair {exchange_trading_pair}: {e}")

        return f"{base_asset}-{quote_asset}"

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return CONSTANTS.TIMESTAMP_ERROR_CODE in str(
            request_exception
        ) and CONSTANTS.TIMESTAMP_ERROR_MESSAGE in str(request_exception)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE in str(
            status_update_exception
        ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE in str(
            cancelation_exception
        ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            time_provider=self._time_provider,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BitstampAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BitstampAPIUserStreamDataSource(
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

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)

        trade_fee_schema = self._trading_fees.get(trading_pair)
        if trade_fee_schema:
            fee_percent: Decimal = (
                trade_fee_schema.maker_percent_fee_decimal if is_maker else trade_fee_schema.taker_percent_fee_decimal
            )
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=trade_fee_schema,
                trade_type=order_side,
                percent=fee_percent
            )
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
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        api_params = {
            "amount": f"{amount:f}",
            "client_order_id": order_id
        }

        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        if order_type.is_limit_type():
            order_url = f"/{side_str}/{symbol}/"
            api_params["price"] = f"{price:f}"
            if order_type == OrderType.LIMIT_MAKER:
                # Set Maker-Or-Cancel, this ensures that the order is not fully or partially filled when placed.
                # In case it would be, the order is cancelled.
                api_params["moc_order"] = True
        else:
            order_url = f"/{side_str}/market/{symbol}/"

        order_result = await self._api_post(
            path_url=order_url,
            data=api_params,
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_CREATE_URL_LIMIT_ID
        )

        if order_result.get("status", "") == "error":
            raise IOError(f"Error placing order. Error: {order_result}")

        o_id = str(order_result["id"])
        transact_time = datetime.fromisoformat(order_result["datetime"]).timestamp()

        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = await tracked_order.get_exchange_order_id()

        cancel_response = await self._api_post(
            path_url=f"{CONSTANTS.ORDER_CANCEL_URL}",
            data={"id": exchange_order_id},
            is_auth_required=True
        )
        if cancel_response.get("status", "") == "error":
            raise IOError(f"Error canceling order. Error: {cancel_response}")

        return str(cancel_response.get("id", "")) == exchange_order_id

    async def _format_trading_rules(self, exchange_info: List[Dict[str, Any]]) -> List[TradingRule]:
        retval = []
        for info in filter(bitstamp_utils.is_exchange_information_valid, exchange_info):
            try:
                retval.append(
                    TradingRule(
                        trading_pair=self.convert_from_exchange_trading_pair(info["name"]),
                        min_price_increment=Decimal(f"1e-{info['counter_decimals']}"),
                        min_base_amount_increment=Decimal(f"1e-{info['base_decimals']}"),
                        min_quote_amount_increment=Decimal(f"1e-{info['counter_decimals']}"),
                        min_notional_size=Decimal(info["minimum_order"].split(" ")[0]))
                )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {info}. Skipping.")
        return retval

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        trading_fees: List[Dict[str, Any]] = await self._api_post(
            path_url=CONSTANTS.TRADING_FEES_URL,
            is_auth_required=True
        )

        for fee_info in trading_fees:
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=fee_info.get("market"))
            except KeyError:
                continue

            if trading_pair:
                fees = fee_info["fees"]
                self._trading_fees[trading_pair] = TradeFeeSchema(
                    maker_percent_fee_decimal=Decimal(fees["maker"]),
                    taker_percent_fee_decimal=Decimal(fees["taker"])
                )

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        trade_events = {
            CONSTANTS.USER_TRADE,
            CONSTANTS.USER_SELF_TRADE,
        }
        async for event_message in self._iter_user_event_queue():
            try:
                event = event_message.get("event")

                if event in trade_events:
                    self._process_user_stream_trade_event(event, event_message)
                else:
                    self._process_user_stream_order_event(event, event_message)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    def _process_user_stream_trade_event(self, event: str, event_message: Dict[str, Any]):
        try:
            event_data = event_message.get("data", {})

            if event == CONSTANTS.USER_TRADE:
                client_order_id = str(event_data.get("client_order_id"))
                order: InFlightOrder = self._order_tracker.all_fillable_orders.get(client_order_id)
                if order is None:
                    self.logger().debug(f"Received event for unknown order ID: {event_message}")
                    return

                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    flat_fees=[TokenAmount(amount=Decimal(event_data["fee"]), token=order.quote_asset)]
                )

                amount = Decimal(event_data["amount"])
                price = Decimal(event_data["price"])
                trade_update = TradeUpdate(
                    trade_id=str(event_data["id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=event_data["order_id"],
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=amount,
                    fill_quote_amount=price * amount,
                    fill_price=price,
                    fill_timestamp=float(event_data["microtimestamp"]) * 1e-3,
                )
                self._order_tracker.process_trade_update(trade_update)
            else:
                # These trades don't incur any fees, but they do offset each other.
                # We register them as regular fills so that the executed amount is updated correctly.

                buy_order_id = str(event_data.get("buy_order_id"))
                sell_order_id = str(event_data.get("sell_order_id"))

                amount = Decimal(event_data["amount"])
                price = Decimal(event_data["price"])

                buy_order: InFlightOrder = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(buy_order_id)
                if buy_order:
                    buy_trade_update = TradeUpdate(
                        trade_id=f"{buy_order_id}-{sell_order_id}",
                        client_order_id=buy_order.client_order_id,
                        exchange_order_id=buy_order_id,
                        trading_pair=buy_order.trading_pair,
                        fee=TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=buy_order.trade_type,
                            flat_fees=TokenAmount(amount=Decimal(0), token=buy_order.quote_asset)),
                        fill_base_amount=amount,
                        fill_quote_amount=price * amount,
                        fill_price=price,
                        fill_timestamp=float(event_data["timestamp"])
                    )
                    self._order_tracker.process_trade_update(buy_trade_update)

                sell_order: InFlightOrder = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(sell_order_id)
                if sell_order:
                    sell_trade_update = TradeUpdate(
                        trade_id=f"{buy_order_id}-{sell_order_id}",
                        client_order_id=sell_order.client_order_id,
                        exchange_order_id=sell_order_id,
                        trading_pair=sell_order.trading_pair,
                        fee=TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=sell_order.trade_type,
                            flat_fees=TokenAmount(amount=Decimal(0), token=sell_order.quote_asset)),
                        fill_base_amount=amount,
                        fill_quote_amount=price * amount,
                        fill_price=price,
                        fill_timestamp=float(event_data["timestamp"]),
                    )
                    self._order_tracker.process_trade_update(sell_trade_update)

        except Exception as e:
            raise ValueError(f"Error parsing the user stream trade event {event_message}: {e}")

    def _process_user_stream_order_event(self, event: str, event_message: Dict[str, Any]):
        try:
            event_data = event_message.get("data", {})
            client_order_id = str(event_data.get("client_order_id"))
            order: InFlightOrder = self._order_tracker.all_fillable_orders.get(client_order_id)
            if order is None:
                self.logger().debug(f"Received event for unknown order ID: {event_message}")
                return

            # Determine the new state of the order
            new_state = OrderState.OPEN
            if event == CONSTANTS.USER_ORDER_CHANGED and Decimal(event_data["amount_traded"]) > 0:
                new_state = OrderState.PARTIALLY_FILLED
            elif event == CONSTANTS.USER_ORDER_DELETED:
                new_state = OrderState.FILLED if event_data["amount"] == 0 else OrderState.CANCELED

            order_update = OrderUpdate(
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=float(event_data["datetime"]),
                new_state=new_state,
            )
            self._order_tracker.process_order_update(order_update)
        except Exception as e:
            raise ValueError(f"Error parsing the user stream order event {event_message}: {e}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        all_fills_response = await self._api_post(
            path_url=CONSTANTS.ORDER_STATUS_URL,
            data={
                "client_order_id": order.client_order_id,
                "omit_transactions": "false",
            },
            is_auth_required=True
        )

        exchange_order_id = await order.get_exchange_order_id()
        trade_updates = []
        for trade in all_fills_response.get("transactions", []):
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                trade_type=order.trade_type,
                flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=order.quote_asset)]
            )
            trade_update = TradeUpdate(
                trade_id=str(trade["tid"]),
                client_order_id=order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=order.trading_pair,
                fee=fee,
                fill_base_amount=Decimal(trade[order.base_asset.lower()]),
                fill_quote_amount=Decimal(trade[order.quote_asset.lower()]),
                fill_price=Decimal(trade["price"]),
                fill_timestamp=datetime.fromisoformat(trade["datetime"]).timestamp(),
            )
            trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._api_post(
            path_url=CONSTANTS.ORDER_STATUS_URL,
            data={
                "client_order_id": tracked_order.client_order_id,
                "omit_transactions": "true"
            },
            is_auth_required = True
        )

        if updated_order_data.get("status", "") == "error":
            raise IOError(f"Error requesting order status. Error: {updated_order_data}")

        new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]
        amount_remaining = Decimal(updated_order_data["amount_remaining"])
        if new_state == OrderState.OPEN and amount_remaining < tracked_order.amount:
            new_state = OrderState.PARTIALLY_FILLED

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=updated_order_data["id"],
            trading_pair=tracked_order.trading_pair,
            update_timestamp=datetime.fromisoformat(updated_order_data["datetime"]).timestamp(),
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        balances = await self._api_post(
            path_url=CONSTANTS.ACCOUNT_BALANCES_URL,
            is_auth_required=True
        )

        for balance_entry in balances:
            asset_name = balance_entry["currency"].upper()
            self._account_available_balances[asset_name] = Decimal(balance_entry["available"])
            self._account_balances[asset_name] = Decimal(balance_entry["total"])
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[Dict[str, Any]]):
        mapping = bidict()
        for info in filter(bitstamp_utils.is_exchange_information_valid, exchange_info):
            try:
                mapping[info["url_symbol"]] = self.convert_from_exchange_trading_pair(info["name"])
            except Exception:
                self.logger().error(f"Error parsing trading pair symbol data {info}. Skipping.")

        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        resp_json = await self._api_get(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_URL.format(symbol),
            limit_id=CONSTANTS.TICKER_URL_LIMIT_ID
        )

        return float(resp_json["last"])
