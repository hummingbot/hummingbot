import asyncio
import secrets
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.woo_x import woo_x_constants as CONSTANTS, woo_x_utils, woo_x_web_utils as web_utils
from hummingbot.connector.exchange.woo_x.woo_x_api_order_book_data_source import WooXAPIOrderBookDataSource
from hummingbot.connector.exchange.woo_x.woo_x_api_user_stream_data_source import WooXAPIUserStreamDataSource
from hummingbot.connector.exchange.woo_x.woo_x_auth import WooXAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class WooXExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        public_api_key: str,
        secret_api_key: str,
        application_id: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.api_key = public_api_key
        self.secret_key = secret_api_key
        self.application_id = application_id
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_woo_x_timestamp = 1.0
        super().__init__(client_config_map)

    @staticmethod
    def woo_x_order_type(order_type: OrderType) -> str:
        if order_type.name == 'LIMIT_MAKER':
            return 'POST_ONLY'
        else:
            return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(woo_x_type: str) -> OrderType:
        return OrderType[woo_x_type]

    @property
    def authenticator(self) -> WooXAuth:
        return WooXAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer
        )

    @property
    def name(self) -> str:
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
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

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

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)

        is_time_synchronizer_related = (
            "-1021" in error_description and "Timestamp for this request" in error_description
        )

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
            auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return WooXAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return WooXAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None
    ) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER

        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

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
        order_id = str(secrets.randbelow(9223372036854775807))

        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs)
        )

        return order_id

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

        order_id = str(secrets.randbelow(9223372036854775807))

        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs)
        )

        return order_id

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
        data = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "order_type": self.woo_x_order_type(order_type),
            "side": trade_type.name.upper(),
            "order_quantity": float(amount),
            "client_order_id": order_id
        }

        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            data["order_price"] = float(price)

        response = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=data,
            is_auth_required=True
        )

        return str(response["order_id"]), int(float(response['timestamp']) * 1e3)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        params = {
            "client_order_id": order_id,
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair),
        }

        cancel_result = await self._api_delete(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            params=params,
            is_auth_required=True
        )

        if cancel_result.get("status") != "CANCEL_SENT":
            raise IOError()

        return True

    async def _format_trading_rules(self, exchange_info: Dict[str, Any]) -> List[TradingRule]:
        result = []

        for entry in filter(woo_x_utils.is_exchange_information_valid, exchange_info.get("rows", [])):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=entry.get("symbol"))
                trading_rule = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=Decimal(str(entry['base_min'])),
                    min_price_increment=Decimal(str(entry['quote_tick'])),
                    min_base_amount_increment=Decimal(str(entry['base_tick'])),
                    min_notional_size=Decimal(str(entry['min_notional']))
                )

                result.append(trading_rule)

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {entry}. Skipping.")
        return result

    async def _status_polling_loop_fetch_updates(self):
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
                event_type = event_message.get("topic")

                if event_type == "executionreport":
                    event_data = event_message.get("data")

                    execution_type = event_data.get("status")

                    client_order_id = event_data.get("clientOrderId")

                    if execution_type in ["PARTIAL_FILLED", "FILLED"]:
                        tracked_order = self._order_tracker.all_fillable_orders.get(str(client_order_id))

                        if tracked_order is not None:
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=tracked_order.trade_type,
                                percent_token=event_data["feeAsset"],
                                flat_fees=[
                                    TokenAmount(
                                        amount=Decimal(event_data["fee"]),
                                        token=event_data["feeAsset"]
                                    )
                                ]
                            )

                            trade_update = TradeUpdate(
                                trade_id=str(event_data["tradeId"]),
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=str(event_data["orderId"]),
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=Decimal(str(event_data["executedQuantity"])),
                                fill_quote_amount=Decimal(str(event_data["executedQuantity"])) * Decimal(str(event_data["executedPrice"])),
                                fill_price=Decimal(str(event_data["executedPrice"])),
                                fill_timestamp=event_data["timestamp"] * 1e-3,
                            )

                            self._order_tracker.process_trade_update(trade_update)

                    tracked_order = self._order_tracker.all_updatable_orders.get(str(client_order_id))

                    if tracked_order is not None:
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=event_data["timestamp"] * 1e-3,
                            new_state=CONSTANTS.ORDER_STATE[event_data["status"]],
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=tracked_order.exchange_order_id,
                        )

                        self._order_tracker.process_order_update(order_update=order_update)
                elif event_type == "balance":
                    balances = event_message["data"]["balances"]

                    for asset_name, balance_entry in balances.items():
                        free, frozen = Decimal(str(balance_entry["holding"])), Decimal(str(balance_entry["frozen"]))

                        total = free + frozen

                        self._account_available_balances[asset_name] = free

                        self._account_balances[asset_name] = total
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)

            content = await self._api_get(
                path_url=CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH.format(order.client_order_id),
                limit_id=CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH,
                is_auth_required=True,
            )

            for trade in content['Transactions']:
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=trade["fee_asset"],
                    flat_fees=[
                        TokenAmount(
                            amount=Decimal(str(trade["fee"])),
                            token=trade["fee_asset"]
                        )
                    ]
                )

                trade_update = TradeUpdate(
                    trade_id=str(trade["id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    trading_pair=symbol,
                    fee=fee,
                    fill_base_amount=Decimal(str(trade["executed_quantity"])),
                    fill_quote_amount=Decimal(str(trade["executed_price"])) * Decimal(str(trade["executed_quantity"])),
                    fill_price=Decimal(str(trade["executed_price"])),
                    fill_timestamp=float(trade["executed_timestamp"]) * 1e-3,
                )

                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH.format(tracked_order.client_order_id),
            is_auth_required=True,
            limit_id=CONSTANTS.GET_ORDER_BY_CLIENT_ORDER_ID_PATH
        )

        new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["order_id"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=float(updated_order_data["created_time"]),
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=True
        )

        balances = account_info.get('holding', [])

        for balance_info in balances:
            asset = balance_info['token']
            holding = balance_info['holding']
            frozen = balance_info['frozen']

            self._account_available_balances[asset] = Decimal(holding)
            self._account_balances[asset] = Decimal(holding) + Decimal(frozen)
            remote_asset_names.add(asset)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)

        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()

        for entry in filter(woo_x_utils.is_exchange_information_valid, exchange_info["rows"]):
            base, quote = entry['symbol'].split('_')[1:]

            mapping[entry["symbol"]] = combine_to_hb_trading_pair(
                base=base,
                quote=quote
            )

        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        content = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.MARKET_TRADES_PATH,
            params={
                "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            }
        )

        return content['rows'][0]['executed_price']
