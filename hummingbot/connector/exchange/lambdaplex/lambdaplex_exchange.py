import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.lambdaplex import (
    lambdaplex_constants as CONSTANTS,
    lambdaplex_web_utils as web_utils,
)
from hummingbot.connector.exchange.lambdaplex.lambdaplex_api_order_book_data_source import (
    LambdaplexAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.lambdaplex.lambdaplex_api_user_stream_data_source import (
    LambdaplexAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.lambdaplex.lambdaplex_auth import LambdaplexAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LambdaplexExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(
        self,
        lambdaplex_api_key: str,
        lambdaplex_private_key: str,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        self._api_key = lambdaplex_api_key
        self._private_key = lambdaplex_private_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_lambdaplex_timestamp = 1.0
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> AuthBase:
        return LambdaplexAuth(
            api_key=self._api_key,
            private_key=self._private_key,
            time_provider=self._time_synchronizer,
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.ORDER_ID_MAX_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.SERVER_AVAILABILITY_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def user_fee_request_path(self) -> str:
        return CONSTANTS.USER_FEES_PATH_URL

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def start(self, *args, **kwargs):
        super().start(*args, **kwargs)

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return "Timestamp outside allowed skew" in str(request_exception)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return "Not Found" in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return "\"status\": 404" in str(cancelation_exception) and "Not Found" in str(cancelation_exception)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        try:
            cancel_order_response = await self._api_delete(
                path_url=CONSTANTS.ORDER_PATH_URL,
                params={
                    "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
                    "origClientOrderId": tracked_order.client_order_id,
                },
                is_auth_required=True,
            )
        except OSError as e:
            if "already CANCELED" not in str(e):
                raise
            else:
                response_code = "CANCELED"
        else:
            response_code = cancel_order_response["status"]

        if response_code != "CANCELED":
            raise IOError(f"Failed to cancel order {order_id}: {cancel_order_response}")

        return True

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
        data = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "side": trade_type.name,
            "quantity": str(amount),
            "newClientOrderId": order_id,
        }
        if order_type.is_limit_type():
            data["type"] = "LIMIT"
            data["timeInForce"] = "GTC"
            data["price"] = str(price)
        else:
            data["type"] = "MARKET"

        create_order_response = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
        )
        status = create_order_response.get("status", None)

        if status is not None:
            raise IOError(f"Error submitting order {order_id}: {create_order_response}")

        return str(create_order_response["orderId"]), self.current_timestamp

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)

        if trading_pair in self._trading_fees:
            fee_schema: TradeFeeSchema = self._trading_fees[trading_pair]
            fee_rate = (
                fee_schema.maker_percent_fee_decimal
                if is_maker
                else fee_schema.taker_percent_fee_decimal
            )
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=fee_schema,
                trade_type=order_side,
                percent=fee_rate,
                percent_token=base_currency,
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

    async def _update_trading_fees(self):
        if self._trading_required:
            await self._update_trading_fees_for_user()
        else:
            pass

    async def _update_trading_fees_for_user(self):
        request_tasks = []

        for trading_pair in self.trading_pairs:
            exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            request_tasks.append(
                self._api_get(
                    path_url=self.user_fee_request_path,
                    params={"symbol": exchange_symbol},
                    is_auth_required=True,
                )
            )

        responses = await safe_gather(*request_tasks)

        for trading_pair, response in zip(self.trading_pairs, responses):
            self._trading_fees[trading_pair] = TradeFeeSchema(
                maker_percent_fee_decimal=Decimal(response["maker"]),
                taker_percent_fee_decimal=Decimal(response["taker"]),
                buy_percent_fee_deducted_from_returns=True,
            )

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("e")
                if event_type in ["orderUpdate", "executionReport"]:
                    self._process_order_update(event_message=event_message)

                elif event_type == "balanceChange":
                    self._process_balance_change(event_message=event_message)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    def _process_order_update(self, event_message: Dict):
        execution_type = event_message.get("x")
        if execution_type != "CANCELED":
            client_order_id = event_message.get("c")
        else:
            client_order_id = event_message.get("C")

        if execution_type == "TRADE":
            tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
            if tracked_order is not None:
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=tracked_order.trade_type,
                    # percent_token=event_message["N"]
                    flat_fees=[TokenAmount(amount=Decimal(event_message["n"]), token=event_message["N"])]
                )
                trade_update = TradeUpdate(
                    trade_id=str(event_message["t"]),
                    client_order_id=client_order_id,
                    exchange_order_id=str(event_message["i"]),
                    trading_pair=tracked_order.trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(event_message["l"]),
                    fill_quote_amount=Decimal(event_message["l"]) * Decimal(event_message["L"]),
                    fill_price=Decimal(event_message["L"]),
                    fill_timestamp=event_message["T"] * 1e-3,
                )
                self._order_tracker.process_trade_update(trade_update)

        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if tracked_order is not None:
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=event_message["E"] * 1e-3,
                new_state=CONSTANTS.ORDER_STATE[event_message["X"]],
                client_order_id=client_order_id,
                exchange_order_id=str(event_message["i"]),
            )
            self._order_tracker.process_order_update(order_update=order_update)

    def _process_balance_change(self, event_message: Dict):
        balances = event_message["B"]
        for balance_entry in balances:
            asset_name = balance_entry["a"]
            free_balance = Decimal(balance_entry["f"])
            total_balance = Decimal(balance_entry["f"]) + Decimal(balance_entry["l"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "exchangeSymbols": [
                {
                    "symbol": self.exchange_trading_pair,
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "baseAssetPrecision": 6,
                    "quoteAssetPrecision": 8,
                    "filters": [
                        {
                            "filterType": "PRICE_FILTER",
                            "minPrice": "0.01000000",
                            "maxPrice": "100000.00000000",
                            "tickSize": "0.01000000"
                        },
                        {
                            "filterType": "LOT_SIZE",
                            "minQty": "0.00001000",
                            "maxQty": "9000.00000000",
                            "stepSize": "0.00001000"
                        },
                        {
                            "filterType": "MIN_NOTIONAL",
                            "minNotional": "10.00",
                            "applyToMarket": True,
                            "avgPriceMins": 5
                        }
                    ]
                }
            ]
        }
        """
        trading_pair_rules = exchange_info_dict.get("exchangeSymbols", [])
        retval = []
        for rule in trading_pair_rules:
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("symbol"))
                filters = rule.get("filters")
                price_filter = [f for f in filters if f.get("filterType") == "PRICE_FILTER"][0]
                lot_size_filter = [f for f in filters if f.get("filterType") == "LOT_SIZE"][0]
                min_notional_filter = [f for f in filters if f.get("filterType") in ["MIN_NOTIONAL", "NOTIONAL"]][0]

                min_order_size = Decimal(lot_size_filter.get("minQty"))
                tick_size = price_filter.get("tickSize")
                step_size = Decimal(lot_size_filter.get("stepSize"))
                min_notional = Decimal(min_notional_filter.get("minNotional"))

                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=Decimal(tick_size),
                        min_base_amount_increment=Decimal(step_size),
                        min_notional_size=Decimal(min_notional),
                    ),
                )

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=True,
        )

        balances = account_info["balances"]
        for balance_entry in balances:
            asset_name = balance_entry["asset"]
            free_balance = Decimal(balance_entry["free"])
            total_balance = Decimal(balance_entry["free"]) + Decimal(balance_entry["locked"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = order.exchange_order_id
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "symbol": trading_pair,
                    "orderId": exchange_order_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_PATH_URL,
            )

            for trade in all_fills_response:
                exchange_order_id = trade["orderId"]
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade["id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["qty"]),
                    fill_quote_amount=Decimal(trade["quoteQty"]),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=trade["time"] * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        updated_data = await self._api_get(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params={
                "symbol": trading_pair,
                "origClientOrderId": tracked_order.client_order_id,
            },
            is_auth_required=True,
            # GET /order is a heavier request (weight 4) and should not consume from the orders mutation bucket.
            limit_id=CONSTANTS.ORDER_QUERY_LIMIT,
        )

        new_state = CONSTANTS.ORDER_STATE[updated_data["status"]]
        if new_state == OrderState.FILLED and Decimal(updated_data["executedQty"]) < Decimal(updated_data["origQty"]):
            new_state = OrderState.PARTIALLY_FILLED

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_data["orderId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=updated_data["updateTime"] * 1e-3,
            new_state=new_state,
        )

        return order_update

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LambdaplexAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LambdaplexAPIUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in exchange_info["exchangeSymbols"]:
            try:
                exchange_symbol = symbol_data["symbol"]
                base = symbol_data["baseAsset"]
                quote = symbol_data["quoteAsset"]
                trading_pair = combine_to_hb_trading_pair(base, quote)
                mapping[exchange_symbol] = trading_pair
            except Exception as exception:
                self.logger().error(
                    f"There was an error parsing a trading pair information ({exception})"
                )
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        resp_json = await self._api_get(
            path_url=CONSTANTS.LAST_PRICE_URL,
            params={
                "symbol": await self.exchange_symbol_associated_to_pair(trading_pair)
            },
            limit_id=CONSTANTS.LAST_PRICE_SINGLE_LIMIT,
        )

        return float(resp_json["price"])
