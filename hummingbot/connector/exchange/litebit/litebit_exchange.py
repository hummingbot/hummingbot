import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.exchange.litebit import (
    litebit_constants as constants,
    litebit_utils,
    litebit_web_utils as web_utils,
)
from hummingbot.connector.exchange.litebit.litebit_api_order_book_data_source import LitebitAPIOrderBookDataSource
from hummingbot.connector.exchange.litebit.litebit_api_user_stream_data_source import LitebitAPIUserStreamDataSource
from hummingbot.connector.exchange.litebit.litebit_auth import LitebitAuth
from hummingbot.connector.exchange.litebit.litebit_utils import convert_to_order_state
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_decimal_NaN = Decimal("nan")


class LitebitExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 litebit_api_key: str,
                 litebit_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        self.api_key = litebit_api_key
        self.secret_key = litebit_secret_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs

        super().__init__(client_config_map)

        self._real_time_balance_update = False

    @property
    def name(self) -> str:
        return "litebit"

    @property
    def authenticator(self):
        return LitebitAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer
        )

    @property
    def rate_limits_rules(self):
        return constants.RATE_LIMITS

    @property
    def domain(self):
        return constants.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self):
        return constants.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return constants.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return constants.GET_MARKETS_PATH

    @property
    def trading_pairs_request_path(self):
        return constants.GET_MARKETS_PATH

    @property
    def check_network_request_path(self):
        return constants.GET_TIME_PATH

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.§
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("50000" in error_description
                                        and "time window" in error_description)
        return is_time_synchronizer_related

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs,
                           ) -> Tuple[str, float]:
        api_params = {"market": litebit_utils.convert_to_exchange_trading_pair(trading_pair),
                      "side": trade_type.name.lower(),
                      "type": "limit",
                      "price": f"{price:f}",
                      "amount": f"{amount:f}",
                      "client_id": order_id,
                      }
        if order_type is OrderType.LIMIT_MAKER:
            api_params["post_only"] = True

        order_result = await self._api_post(
            path_url=constants.CREATE_ORDER_PATH,
            data=api_params,
            is_auth_required=True,
            limit_id=f"{RESTMethod.POST}{constants.CREATE_ORDER_PATH}",
        )

        o_id = str(order_result["uuid"])
        transact_time = order_result["created_at"] * 1e-3
        return (o_id, transact_time)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        if tracked_order.exchange_order_id is None:
            await tracked_order.get_exchange_order_id()
        ex_order_id = tracked_order.exchange_order_id
        cancel_result = await self._api_delete(
            path_url=constants.CANCEL_ORDERS_PATH,
            data={
                "market": litebit_utils.convert_to_exchange_trading_pair(tracked_order.trading_pair),
                "orders": [ex_order_id]
            },
            is_auth_required=True
        )

        if type(cancel_result) == list and len(cancel_result) == 1 and cancel_result[0].get("uuid") == ex_order_id:
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.PENDING_CANCEL
            )
            self._order_tracker.process_order_update(order_update)
            return True
        else:
            return False

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        LitebitAPIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event = event_message.get("event")
                data = event_message.get("data")

                if event == "order":
                    tracked_order = self._order_tracker.all_updatable_orders.get(data["client_id"])
                    if tracked_order is not None:
                        new_state = convert_to_order_state(data)

                        order_update = OrderUpdate(
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=str(data["uuid"]),
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=data["updated_at"] * 1e-3,
                            new_state=new_state,
                        )
                        self._order_tracker.process_order_update(order_update=order_update)
                elif event == "fill":
                    exchange_order_id = data["order_uuid"]
                    order = next((order for order in self._order_tracker.all_fillable_orders.values()
                                  if order.exchange_order_id == exchange_order_id),
                                 None)

                    if order is not None:
                        # quote asset
                        fee_token = data["market"].split("-")[1]
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=order.trade_type,
                            percent_token=fee_token,
                            flat_fees=[TokenAmount(amount=Decimal(data["fee"]), token=fee_token)]
                        )

                        if data["side"] == "buy":
                            quote_amount = Decimal(data["amount_quote"]) - Decimal(data["fee"])
                        elif data["side"] == "sell":
                            quote_amount = Decimal(data["amount_quote"]) + Decimal(data["fee"])
                        else:
                            raise ValueError(f"unexpected side: {data['side']}")

                        trade_update = TradeUpdate(
                            trade_id=str(data["uuid"]),
                            client_order_id=order.client_order_id,
                            exchange_order_id=data["order_uuid"],
                            trading_pair=order.trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(data["amount"]),
                            fill_quote_amount=quote_amount,
                            fill_price=Decimal(data["price"]),
                            fill_timestamp=data["timestamp"] * 1e-3,
                        )
                        self._order_tracker.process_trade_update(trade_update)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _format_trading_rules(self, instruments_info: List[dict]) -> List[TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param instruments_info: The json API response
        :return A dictionary of trading rules.
        """
        result = []
        for market in instruments_info:
            try:
                trading_pair = litebit_utils.convert_from_exchange_trading_pair(market["market"])
                result.append(
                    TradingRule(trading_pair,
                                min_price_increment=Decimal(market["tick_size"]),
                                min_base_amount_increment=Decimal(market["step_size"]),
                                min_notional_size=Decimal(market["minimum_amount_quote"]),
                                min_order_size=Decimal(market["step_size"])))
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {market}. Skipping.", exc_info=True)
        return result

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(path_url=constants.GET_BALANCES_PATH, is_auth_required=True)

        for account in account_info:
            asset_name = account["asset"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["total"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=constants.GET_FILLS_PATH,
                params={
                    "market": trading_pair,
                    "order_uuid": order.exchange_order_id
                },
                is_auth_required=True,
                limit_id=constants.GET_FILLS_PATH
            )

            for trade in all_fills_response:
                # quote asset
                fee_token = trade["market"].split("-")[1]
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=fee_token,
                    flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=fee_token)]
                )

                if trade["side"] == "buy":
                    quote_amount = Decimal(trade["amount_quote"]) - Decimal(trade["fee"])
                elif trade["side"] == "sell":
                    quote_amount = Decimal(trade["amount_quote"]) + Decimal(trade["fee"])
                else:
                    raise ValueError(f"unexpected side: {trade['side']}")

                trade_update = TradeUpdate(
                    trade_id=str(trade["uuid"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=trade["order_uuid"],
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["amount"]),
                    fill_quote_amount=quote_amount,
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=trade["timestamp"] * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        updated_order_data = await self._api_get(
            path_url=constants.GET_ORDER_PATH,
            params={
                "market": trading_pair,
                "uuid": tracked_order.exchange_order_id
            },
            is_auth_required=True,
            limit_id=f"{RESTMethod.GET}{constants.GET_ORDER_PATH}",
        )

        new_state = convert_to_order_state(updated_order_data)

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["uuid"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=updated_order_data["updated_at"] * 1e-3,
            new_state=new_state,
        )

        return order_update

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LitebitAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LitebitAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[dict]):
        mapping = bidict()
        for trading_pair in filter(litebit_utils.is_exchange_information_valid, exchange_info):
            mapping[trading_pair["market"]] = combine_to_hb_trading_pair(base=trading_pair["base_asset"],
                                                                         quote=trading_pair["quote_asset"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "market": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        resp_json = await self._api_get(
            path_url=constants.GET_TICKERS_PATH,
            params=params
        )

        return float(resp_json["last"])
