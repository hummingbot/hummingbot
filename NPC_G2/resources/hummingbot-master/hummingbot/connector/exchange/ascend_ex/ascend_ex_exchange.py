import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.ascend_ex import (
    ascend_ex_constants as CONSTANTS,
    ascend_ex_utils as utils,
    ascend_ex_web_utils as web_utils,
)
from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source import AscendExAPIOrderBookDataSource
from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_user_stream_data_source import (
    AscendExAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
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


class AscendExExchange(ExchangePyBase):
    """
    AscendExExchange connects with AscendEx exchange and provides order book pricing, user account tracking and
    trading functionality.
    """

    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        ascend_ex_api_key: str,
        ascend_ex_secret_key: str,
        ascend_ex_group_id: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        """
        :param client_config_map: The config map of the client instance.
        :param ascend_ex_api_key: The API key to connect to private AscendEx APIs.
        :param ascend_ex_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        self.ascend_ex_api_key = ascend_ex_api_key
        self.ascend_ex_secret_key = ascend_ex_secret_key
        self.ascend_ex_group_id = ascend_ex_group_id
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__(client_config_map=client_config_map)

        self._last_known_sequence_number = 0

    @property
    def domain(self):
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def authenticator(self):
        return AscendExAuth(self.ascend_ex_api_key, self.ascend_ex_secret_key)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.PRODUCTS_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.PRODUCTS_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.SERVER_LIMIT_INFO

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
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> Dict[str, Any]:
        """
        This method executes a request to the exchange to get the current price for all trades.
        It returns the response of the exchange (expected to be used by the AscendEx RateSource for the RateOracle)

        :return: the response from the tickers endpoint
        """
        symbol_to_trading_pair_map = await self.trading_pair_symbol_map()
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_PATH_URL)
        spot_valid_token_entries = [
            data_dict for data_dict in pairs_prices["data"] if data_dict["symbol"] in symbol_to_trading_pair_map
        ]
        pairs_prices["data"] = spot_valid_token_entries
        return pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # API documentation does not clarify the error message for timestamp related problems
        return False

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

    async def _api_request_url(self, path_url: str, is_auth_required: bool = False) -> str:
        url = await super()._api_request_url(path_url, is_auth_required)

        if is_auth_required:
            url = url.format(group_id=self.ascend_ex_group_id)

        return url

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return AscendExAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return AscendExAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> AddedToCostTradeFee:

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        if trading_pair in self._trading_fees:
            fees_data = self._trading_fees[trading_pair]
            fee_value = Decimal(fees_data["maker"]) if is_maker else Decimal(fees_data["taker"])
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

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(utils.is_pair_information_valid, exchange_info.get("data", [])):
            if len(symbol_data["symbol"].split("/")) == 2:
                base, quote = symbol_data["symbol"].split("/")
                mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base, quote)
        self._set_trading_pair_symbol_map(mapping)

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
        side = trade_type.name.lower()
        timestamp = utils.get_ms_timestamp()
        data = {
            "time": timestamp,
            "orderQty": str(amount),
            "id": order_id,
            "side": side,
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        }
        if order_type.is_limit_type():
            data["orderPrice"] = str(price)
            data["orderType"] = "limit"
            data["timeInForce"] = "GTC"
        else:
            data["orderType"] = "market"
            data["timeInForce"] = "IOC"
        if order_type is OrderType.LIMIT_MAKER:
            data["postOnly"] = True
        exchange_order = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
        )

        if exchange_order.get("code") == 0:
            return (
                str(exchange_order["data"]["info"]["orderId"]),
                int(exchange_order["data"]["info"].get("timestamp") or exchange_order["data"]["info"]
                    ["lastExecTime"]) * 1e-3,
            )
        else:
            raise IOError(str(exchange_order))

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        This implementation specific function is called by _cancel, and returns True if successful
        """
        exchange_order_id = await tracked_order.get_exchange_order_id()
        timestamp = utils.get_ms_timestamp()
        data = {
            "time": timestamp,
            "orderId": exchange_order_id,
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair),
        }
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
        )
        if cancel_result.get("code") == 0:
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
                acct_type = event_message.get("ac")
                event_subject = event_message.get("m")
                execution_data = event_message.get("data")

                # Refer to https://ascendex.github.io/ascendex-pro-api/#channel-order-and-balance
                if acct_type == CONSTANTS.ACCOUNT_TYPE and event_subject == CONSTANTS.ORDER_CHANGE_EVENT_TYPE:
                    order_event_type = execution_data["st"]
                    order_id: Optional[str] = execution_data.get("orderId")
                    event_timestamp = execution_data["t"] * 1e-3
                    updated_status = CONSTANTS.ORDER_STATE[order_event_type]

                    fillable_order_list = list(
                        filter(
                            lambda order: order.exchange_order_id == order_id,
                            list(self._order_tracker.all_fillable_orders.values()),
                        )
                    )
                    updatable_order_list = list(
                        filter(
                            lambda order: order.exchange_order_id == order_id,
                            list(self._order_tracker.all_updatable_orders.values()),
                        )
                    )

                    fillable_order = None
                    if len(fillable_order_list) > 0:
                        fillable_order = fillable_order_list[0]

                    updatable_order = None
                    if len(updatable_order_list) > 0:
                        updatable_order = updatable_order_list[0]

                    if fillable_order is not None and updated_status in [
                        OrderState.PARTIALLY_FILLED,
                        OrderState.FILLED,
                    ]:
                        executed_amount_diff = Decimal(execution_data["cfq"]) - fillable_order.executed_amount_base
                        execute_price = Decimal(execution_data["ap"])
                        fee_asset = execution_data["fa"]
                        total_order_fee = Decimal(execution_data["cf"])
                        current_accumulated_fee = 0
                        for fill in fillable_order.order_fills.values():
                            current_accumulated_fee += sum(
                                (fee.amount for fee in fill.fee.flat_fees if fee.token == fee_asset)
                            )

                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=fillable_order.trade_type,
                            percent_token=fee_asset,
                            flat_fees=[TokenAmount(amount=total_order_fee - current_accumulated_fee, token=fee_asset)],
                        )

                        trade_update = TradeUpdate(
                            trade_id=str(execution_data["sn"]),
                            client_order_id=fillable_order.client_order_id,
                            exchange_order_id=order_id,
                            trading_pair=updatable_order.trading_pair,
                            fee=fee,
                            fill_base_amount=executed_amount_diff,
                            fill_quote_amount=executed_amount_diff * execute_price,
                            fill_price=execute_price,
                            fill_timestamp=event_timestamp,
                        )
                        self._order_tracker.process_trade_update(trade_update)

                    if updatable_order is not None:
                        order_update = OrderUpdate(
                            trading_pair=updatable_order.trading_pair,
                            update_timestamp=event_timestamp,
                            new_state=updated_status,
                            client_order_id=fillable_order.client_order_id,
                            exchange_order_id=order_id,
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                    # Update the balance with the balance status details included in the order event
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=execution_data["s"])
                    base_asset, quote_asset = split_hb_trading_pair(trading_pair=trading_pair)
                    self._account_balances.update({base_asset: Decimal(execution_data["btb"])})
                    self._account_available_balances.update({base_asset: Decimal(execution_data["bab"])})
                    self._account_balances.update({quote_asset: Decimal(execution_data["qtb"])})
                    self._account_available_balances.update({quote_asset: Decimal(execution_data["qab"])})

                # The balance event is not processed because it only sends transfers information
                # We need to use the offline balance estimation for AscendEx

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        response = await self._api_get(path_url=CONSTANTS.BALANCE_PATH_URL, is_auth_required=True)

        if response.get("code") == 0:
            for balance_entry in response["data"]:
                asset_name = balance_entry["asset"]
                self._account_available_balances[asset_name] = Decimal(balance_entry["availableBalance"])
                self._account_balances[asset_name] = Decimal(balance_entry["totalBalance"])
                remote_asset_names.add(asset_name)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]
        else:
            self.logger().error(f"There was an error during the balance request to AscendEx ({response})")
            raise IOError(f"Error requesting balances from AscendEx ({response})")

    async def _format_trading_rules(self, raw_trading_pair_info: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []

        for info in filter(utils.is_pair_information_valid, raw_trading_pair_info.get("data", [])):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=info.get("symbol"))
                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(info["minQty"]),
                        max_order_size=Decimal(info["maxQty"]),
                        min_price_increment=Decimal(info["tickSize"]),
                        min_base_amount_increment=Decimal(info["lotSize"]),
                        min_notional_size=Decimal(info["minNotional"]),
                    )
                )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def _update_trading_fees(self):
        resp = await self._api_get(
            path_url=CONSTANTS.FEE_PATH_URL,
            is_auth_required=True,
        )
        fees_json = resp.get("data", {}).get("fees", [])
        for fee_json in fees_json:
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=fee_json["symbol"])
                self._trading_fees[trading_pair] = fee_json["fee"]
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # AscendEx does not have an endpoint to retrieve trades for a particular order
        # Thus it overrides the _update_orders_fills method
        pass

    def _trade_update_from_fill_data(self, fill_data: Dict[str, Any], order: InFlightOrder) -> TradeUpdate:
        trade_id = str(fill_data["sn"])
        timestamp = fill_data["transactTime"] * 1e3
        asset_amount_detail = {}
        fee_amount = 0
        fee_asset = order.quote_asset

        for asset_detail in fill_data["data"]:
            asset = asset_detail["asset"]
            amount = abs(Decimal(str(asset_detail["deltaQty"])))
            if asset_detail["dataType"] == "fee":
                fee_asset = asset
                fee_amount = amount
            else:
                asset_amount_detail[asset] = amount

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,
            percent_token=fee_asset,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)],
        )
        trade_update = TradeUpdate(
            trade_id=trade_id,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=asset_amount_detail[order.base_asset],
            fill_quote_amount=asset_amount_detail[order.quote_asset],
            fill_price=asset_amount_detail[order.quote_asset] / asset_amount_detail[order.base_asset],
            fill_timestamp=timestamp,
        )

        return trade_update

    async def _all_trade_updates_for_orders(
        self, orders: List[InFlightOrder], sequence_number: int
    ) -> Tuple[List[TradeUpdate], int]:
        # This endpoint determines the URL in an adhoc way because it is very different compare to the other endpoints
        url = await self._api_request_url(path_url="")
        balance_hist_url = url.replace("/v1/", f"/{CONSTANTS.BALANCE_HISTORY_PATH_URL}")
        params = {"sn": sequence_number, "limit": 500}
        trade_updates = []
        orders_to_process = {order.exchange_order_id: order for order in orders if order.exchange_order_id is not None}
        should_request_next_page = True
        max_sequence_number = -1

        # If there are many pages of result, query at most two pages each time, to not delay the update status loop
        for _ in range(2):
            result = await self._api_get(
                path_url=CONSTANTS.BALANCE_HISTORY_PATH_URL,
                params=params,
                is_auth_required=True,
                overwrite_url=balance_hist_url,
            )

            if "order" in result:
                for order_fill_data in result["order"]:
                    max_sequence_number = max(max_sequence_number, order_fill_data["sn"])
                    if order_fill_data["orderId"] in orders_to_process:
                        order_id = order_fill_data["orderId"]
                        try:
                            trade_update = self._trade_update_from_fill_data(
                                fill_data=order_fill_data, order=orders_to_process[order_id]
                            )
                            trade_updates.append(trade_update)
                        except asyncio.CancelledError:
                            raise
                        except Exception as request_error:
                            self.logger().warning(
                                f"Failed to fetch trade updates for order {order_id}. Error: {request_error}"
                            )
                params["sn"] = max_sequence_number
                should_request_next_page = len(result["order"]) + len(result.get("balance", [])) == params["limit"]
                if not should_request_next_page:
                    break
            else:
                self.logger().warning(f"An error occurred when requesting order fills ({result})")
                break

        return trade_updates, max_sequence_number

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        if orders:
            # Since we are keeping the last order fill sequence number referenced to improve the query performance
            # it is necessary to evaluate updates for all possible fillable orders every time (to avoid loosing updates)
            candidate_orders = list(self._order_tracker.all_fillable_orders.values())
            try:
                if candidate_orders:
                    trade_updates, max_sequence_number = await self._all_trade_updates_for_orders(
                        orders=candidate_orders, sequence_number=self._last_known_sequence_number
                    )
                    # Update the _last_known_sequence_number to reduce the amount of information requested next time
                    self._last_known_sequence_number = max(self._last_known_sequence_number, max_sequence_number)
                    for trade_update in trade_updates:
                        self._order_tracker.process_trade_update(trade_update)
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                order_ids = [order.client_order_id for order in candidate_orders]
                self.logger().warning(f"Failed to fetch trade updates for orders {order_ids}. Error: {request_error}")

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        params = {"orderId": exchange_order_id}
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.ORDER_STATUS_PATH_URL, params=params, is_auth_required=True
        )

        if updated_order_data.get("code") == 0:
            order_update_data = updated_order_data["data"]
            ordered_state = order_update_data["status"]
            new_state = CONSTANTS.ORDER_STATE[ordered_state]

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=order_update_data["orderId"],
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=new_state,
            )

            return order_update
        else:
            raise IOError(f"Error requesting status for order {tracked_order.client_order_id} ({updated_order_data})")

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {"symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)}

        resp_json = await self._api_request(path_url=CONSTANTS.TICKER_PATH_URL, method=RESTMethod.GET, params=params)

        return float(resp_json["data"]["close"])
