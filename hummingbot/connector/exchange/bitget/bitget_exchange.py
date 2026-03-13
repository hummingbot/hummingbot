import asyncio
from decimal import ROUND_UP, Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from bidict import bidict

import hummingbot.connector.exchange.bitget.bitget_constants as CONSTANTS
from hummingbot.connector.exchange.bitget import bitget_utils, bitget_web_utils as web_utils
from hummingbot.connector.exchange.bitget.bitget_api_order_book_data_source import BitgetAPIOrderBookDataSource
from hummingbot.connector.exchange.bitget.bitget_api_user_stream_data_source import BitgetAPIUserStreamDataSource
from hummingbot.connector.exchange.bitget.bitget_auth import BitgetAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

s_decimal_NaN = Decimal("nan")


class BitgetExchange(ExchangePyBase):

    web_utils = web_utils

    def __init__(
        self,
        bitget_api_key: str = None,
        bitget_secret_key: str = None,
        bitget_passphrase: str = None,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ) -> None:
        self._api_key = bitget_api_key
        self._secret_key = bitget_secret_key
        self._passphrase = bitget_passphrase
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs

        self._expected_market_amounts: Dict[str, Decimal] = {}

        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> BitgetAuth:
        return BitgetAuth(
            api_key=self._api_key,
            secret_key=self._secret_key,
            passphrase=self._passphrase,
            time_provider=self._time_synchronizer
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
        return CONSTANTS.PUBLIC_SYMBOLS_ENDPOINT

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.PUBLIC_SYMBOLS_ENDPOINT

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PUBLIC_TIME_ENDPOINT

    @property
    def trading_pairs(self) -> Optional[List[str]]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @staticmethod
    def _formatted_error(code: int, message: str) -> str:
        return f"Error: {code} - {message}"

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(
        self,
        request_exception: Exception
    ) -> bool:
        error_description = str(request_exception)
        ts_error_target_str = "Request timestamp expired"

        return ts_error_target_str in error_description

    def _is_order_not_found_during_status_update_error(
        self,
        status_update_exception: Exception
    ) -> bool:
        # Error example:
        # { "code": "00000", "msg": "success", "requestTime": 1710327684832, "data": [] }

        if isinstance(status_update_exception, IOError):
            return any(
                value in str(status_update_exception)
                for value in CONSTANTS.RET_CODES_ORDER_NOT_EXISTS
            )

        if isinstance(status_update_exception, ValueError):
            return True

        return False

    def _is_order_not_found_during_cancelation_error(
        self,
        cancelation_exception: Exception
    ) -> bool:
        # Error example:
        # { "code": "43001", "msg": "订单不存在", "requestTime": 1710327684832, "data": null }

        if isinstance(cancelation_exception, IOError):
            return any(
                value in str(cancelation_exception)
                for value in CONSTANTS.RET_CODES_ORDER_NOT_EXISTS
            )

        return False

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        cancel_order_response = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_ENDPOINT,
            data={
                "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
                "clientOid": tracked_order.client_order_id
            },
            is_auth_required=True,
        )
        response_code = cancel_order_response["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                response_code,
                f"Can't cancel order {order_id}: {cancel_order_response}"
            ))

        self._expected_market_amounts.pop(tracked_order.client_order_id, None)

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
        if order_type is OrderType.MARKET and trade_type is TradeType.BUY:
            current_price: Decimal = self.get_price(trading_pair, True)
            step_size = Decimal(self.trading_rules[trading_pair].min_base_amount_increment)
            amount = (amount * current_price).quantize(step_size, rounding=ROUND_UP)
            self._expected_market_amounts[order_id] = amount
        data = {
            "side": CONSTANTS.TRADE_TYPES[trade_type],
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "size": str(amount),
            "orderType": CONSTANTS.ORDER_TYPES[order_type],
            "force": CONSTANTS.DEFAULT_TIME_IN_FORCE,
            "clientOid": order_id,
        }
        if order_type.is_limit_type():
            data["price"] = str(price)

        create_order_response = await self._api_post(
            path_url=CONSTANTS.PLACE_ORDER_ENDPOINT,
            data=data,
            is_auth_required=True,
            headers={
                "X-CHANNEL-API-CODE": CONSTANTS.API_CODE,
            }
        )
        response_code = create_order_response["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                response_code,
                f"Error submitting order {order_id}: {create_order_response}"
            ))

        return str(create_order_response["data"]["orderId"]), self.current_timestamp

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

    async def _update_trading_fees(self) -> None:
        exchange_info = await self._api_get(
            path_url=self.trading_rules_request_path
        )
        symbol_data = exchange_info["data"]

        for symbol_details in symbol_data:
            if bitget_utils.is_exchange_information_valid(exchange_info=symbol_details):
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                    symbol=symbol_details["symbol"]
                )
                self._trading_fees[trading_pair] = TradeFeeSchema(
                    maker_percent_fee_decimal=Decimal(symbol_details["makerFeeRate"]),
                    taker_percent_fee_decimal=Decimal(symbol_details["takerFeeRate"])
                )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BitgetAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BitgetAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    async def _update_balances(self) -> None:
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        wallet_balance_response: Dict[str, Union[str, List[Dict[str, Any]]]] = await self._api_get(
            path_url=CONSTANTS.ASSETS_ENDPOINT,
            is_auth_required=True,
        )
        response_code = wallet_balance_response["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                response_code,
                f"Error while balance update: {wallet_balance_response}"
            ))

        for balance_data in wallet_balance_response["data"]:
            self._set_account_balances(balance_data)
            remote_asset_names.add(balance_data["coin"])

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            try:
                all_fills_response = await self._request_order_fills(order=order)
                fills_data = all_fills_response.get("data", [])

                for fill_data in fills_data:
                    trade_update = self._parse_trade_update(
                        trade_msg=fill_data,
                        tracked_order=order,
                        source_type="rest"
                    )
                    trade_updates.append(trade_update)
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(
                    request_exception=ex
                ):
                    raise
        if len(trade_updates) > 0:
            self.logger().info(
                f"{len(trade_updates)} trades updated for order {order.client_order_id}"
            )

        return trade_updates

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        order_fills_response = await self._api_get(
            path_url=CONSTANTS.USER_FILLS_ENDPOINT,
            params={
                "orderId": order.exchange_order_id
            },
            is_auth_required=True,
        )

        return order_fills_response

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        order_info_response = await self._request_order_update(tracked_order=tracked_order)

        order_update = self._create_order_update(
            order=tracked_order,
            order_update_response=order_info_response
        )

        return order_update

    def _create_order_update(
        self, order: InFlightOrder, order_update_response: Dict[str, Any]
    ) -> OrderUpdate:
        updated_order_data = order_update_response["data"]

        if not updated_order_data:
            raise ValueError(f"Can't parse order status data. Data: {updated_order_data}")

        updated_info = updated_order_data[0]

        if (
            order.trade_type is TradeType.BUY
            and order.order_type is OrderType.MARKET
            and order.client_order_id not in self._expected_market_amounts
        ):
            self._expected_market_amounts[order.client_order_id] = Decimal(updated_info["size"])

        new_state = CONSTANTS.STATE_TYPES[updated_info["status"]]
        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=new_state,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
        )

        return order_update

    async def _request_order_update(self, tracked_order: InFlightOrder) -> Dict[str, Any]:
        order_info_response = await self._api_get(
            path_url=CONSTANTS.ORDER_INFO_ENDPOINT,
            params={
                "clientOid": tracked_order.client_order_id
            },
            is_auth_required=True,
        )

        return order_info_response

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        resp_json = await self._api_get(
            path_url=CONSTANTS.PUBLIC_TICKERS_ENDPOINT,
            params={
                "symbol": await self.exchange_symbol_associated_to_pair(trading_pair)
            },
        )

        return float(resp_json["data"][0]["lastPr"])

    def _parse_trade_update(
        self,
        trade_msg: Dict,
        tracked_order: InFlightOrder,
        source_type: Literal["websocket", "rest"]
    ) -> Optional[TradeUpdate]:
        self.logger().debug(f"Data for {source_type} trade update: {trade_msg}")

        fee_detail = trade_msg["feeDetail"]
        trade_fee_data = fee_detail[0] if isinstance(fee_detail, list) else fee_detail
        fee_amount = abs(Decimal(trade_fee_data["totalFee"]))
        fee_coin = trade_fee_data["feeCoin"]
        side = TradeType.BUY if trade_msg["side"] == "buy" else TradeType.SELL

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=side,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_coin)],
        )

        trade_id: str = trade_msg["tradeId"]
        trading_pair = tracked_order.trading_pair
        fill_price = Decimal(trade_msg["priceAvg"])
        base_amount = Decimal(trade_msg["size"])
        quote_amount = Decimal(trade_msg["amount"])

        if (
            tracked_order.trade_type is TradeType.BUY
            and tracked_order.order_type is OrderType.MARKET
        ):
            expected_price = (
                self._expected_market_amounts[tracked_order.client_order_id] / tracked_order.amount
            )
            base_amount = (quote_amount / expected_price).quantize(
                Decimal(self.trading_rules[trading_pair].min_base_amount_increment),
                rounding=ROUND_UP
            )

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=trade_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(trade_msg["orderId"]),
            trading_pair=trading_pair,
            fill_timestamp=int(trade_msg["uTime"]) * 1e-3,
            fill_price=fill_price,
            fill_base_amount=base_amount,
            fill_quote_amount=quote_amount,
            fee=fee
        )

        return trade_update

    async def _user_stream_event_listener(self) -> None:
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message["arg"]["channel"]
                data = event_message["data"]

                self.logger().debug(f"Channel: {channel} - Data: {data}")

                if channel == CONSTANTS.WS_ORDERS_ENDPOINT:
                    for order_msg in data:
                        self._process_order_event_message(order_msg)
                elif channel == CONSTANTS.WS_FILL_ENDPOINT:
                    for fill_msg in data:
                        self._process_fill_event_message(fill_msg)
                elif channel == CONSTANTS.WS_ACCOUNT_ENDPOINT:
                    for wallet_msg in data:
                        self._set_account_balances(wallet_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")

    def _process_order_event_message(self, order_msg: Dict[str, Any]) -> None:
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order event message payload
        """
        order_status = CONSTANTS.STATE_TYPES[order_msg["status"]]
        client_order_id = str(order_msg["clientOid"])
        updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if updatable_order is not None:
            if (
                updatable_order.trade_type is TradeType.BUY
                and updatable_order.order_type is OrderType.MARKET
                and client_order_id not in self._expected_market_amounts
            ):
                self._expected_market_amounts[client_order_id] = Decimal(order_msg["notional"])

            if order_status is OrderState.PARTIALLY_FILLED:
                side = TradeType.BUY if order_msg["side"] == "buy" else TradeType.SELL
                fee_amount = abs(Decimal(order_msg["fillFee"]))
                fee_coin = order_msg["fillFeeCoin"]

                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=side,
                    flat_fees=[TokenAmount(amount=fee_amount, token=fee_coin)],
                )
                trading_pair = updatable_order.trading_pair
                fill_price = Decimal(order_msg["fillPrice"])
                base_amount = Decimal(order_msg["baseVolume"])
                quote_amount = base_amount * fill_price

                if (
                    updatable_order.trade_type is TradeType.BUY
                    and updatable_order.order_type is OrderType.MARKET
                ):
                    expected_price = Decimal(order_msg["notional"]) / updatable_order.amount
                    base_amount = (quote_amount / expected_price).quantize(
                        Decimal(self.trading_rules[trading_pair].min_base_amount_increment),
                        rounding=ROUND_UP
                    )

                new_trade_update: TradeUpdate = TradeUpdate(
                    trade_id=order_msg["tradeId"],
                    client_order_id=client_order_id,
                    exchange_order_id=updatable_order.exchange_order_id,
                    trading_pair=updatable_order.trading_pair,
                    fill_timestamp=int(order_msg["fillTime"]) * 1e-3,
                    fill_price=fill_price,
                    fill_base_amount=base_amount,
                    fill_quote_amount=quote_amount,
                    fee=fee
                )
                self._order_tracker.process_trade_update(new_trade_update)

            new_order_update: OrderUpdate = OrderUpdate(
                trading_pair=updatable_order.trading_pair,
                update_timestamp=int(order_msg["uTime"]) * 1e-3,
                new_state=order_status,
                client_order_id=client_order_id,
                exchange_order_id=order_msg["orderId"],
            )
            self._order_tracker.process_order_update(new_order_update)

    def _process_fill_event_message(self, fill_msg: Dict[str, Any]) -> None:
        try:
            order_id = str(fill_msg.get("orderId", ""))
            trade_id = str(fill_msg.get("tradeId", ""))
            fillable_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(
                order_id
            )

            if not fillable_order:
                self.logger().debug(
                    f"Ignoring fill message for order {order_id}: not in in_flight_orders."
                )
                return

            trade_update = self._parse_trade_update(
                trade_msg=fill_msg,
                tracked_order=fillable_order,
                source_type="websocket"
            )
            if trade_update:
                self._order_tracker.process_trade_update(trade_update)

                self.logger().debug(
                    f"Processed fill event for order {fillable_order.client_order_id}: "
                    f"Trade {trade_id}: {fill_msg.get('size')} at {fill_msg.get('priceAvg')}."
                )
        except Exception as e:
            self.logger().error(f"Error processing fill event: {e}", exc_info=True)

    def _set_account_balances(self, data: Dict[str, Any]) -> None:
        symbol = data["coin"]
        available = Decimal(str(data["available"]))
        frozen = Decimal(str(data["frozen"]))
        self._account_balances[symbol] = frozen + available
        self._account_available_balances[symbol] = available

    def _initialize_trading_pair_symbols_from_exchange_info(
        self,
        exchange_info: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        mapping = bidict()
        for symbol_data in exchange_info["data"]:
            if bitget_utils.is_exchange_information_valid(exchange_info=symbol_data):
                try:
                    exchange_symbol = symbol_data["symbol"]
                    base = symbol_data["baseCoin"]
                    quote = symbol_data["quoteCoin"]
                    trading_pair = combine_to_hb_trading_pair(base, quote)
                    mapping[exchange_symbol] = trading_pair
                except Exception as exception:
                    self.logger().error(
                        f"There was an error parsing a trading pair information ({exception})"
                    )
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(
        self,
        exchange_info_dict: Dict[str, List[Dict[str, Any]]]
    ) -> List[TradingRule]:
        trading_rules = []
        for rule in exchange_info_dict["data"]:
            if bitget_utils.is_exchange_information_valid(exchange_info=rule):
                try:
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                        symbol=rule["symbol"]
                    )
                    trading_rules.append(
                        TradingRule(
                            trading_pair=trading_pair,
                            min_order_size=Decimal(f"1e-{rule['quantityPrecision']}"),
                            min_price_increment=Decimal(f"1e-{rule['pricePrecision']}"),
                            min_base_amount_increment=Decimal(f"1e-{rule['quantityPrecision']}"),
                            min_quote_amount_increment=Decimal(f"1e-{rule['quotePrecision']}"),
                            min_notional_size=Decimal(rule["minTradeUSDT"]),
                        )
                    )
                except Exception:
                    self.logger().exception(
                        f"Error parsing the trading pair rule: {rule}. Skipping."
                    )
        return trading_rules
