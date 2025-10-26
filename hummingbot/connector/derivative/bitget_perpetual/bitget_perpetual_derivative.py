import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bitget_perpetual import (
    bitget_perpetual_utils,
    bitget_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_api_order_book_data_source import (
    BitgetPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_api_user_stream_data_source import (
    BitgetPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_auth import BitgetPerpetualAuth
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_constants import MarginMode
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class BitgetPerpetualDerivative(PerpetualDerivativePyBase):

    web_utils = web_utils

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        bitget_perpetual_api_key: str = None,
        bitget_perpetual_secret_key: str = None,
        bitget_perpetual_passphrase: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ) -> None:

        self.bitget_perpetual_api_key = bitget_perpetual_api_key
        self.bitget_perpetual_secret_key = bitget_perpetual_secret_key
        self.bitget_perpetual_passphrase = bitget_perpetual_passphrase
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trade_history_timestamp = None

        self._margin_mode = MarginMode.CROSS

        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> BitgetPerpetualAuth:
        return BitgetPerpetualAuth(
            api_key=self.bitget_perpetual_api_key,
            secret_key=self.bitget_perpetual_secret_key,
            passphrase=self.bitget_perpetual_passphrase,
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
        return CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT

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

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    @staticmethod
    def _formatted_error(code: int, message: str) -> str:
        return f"Error: {code} - {message}"

    async def start_network(self):
        await super().start_network()
        await self.set_margin_mode(self._margin_mode)

        if self.is_trading_required:
            self.set_position_mode(PositionMode.HEDGE)

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    def _is_request_exception_related_to_time_synchronizer(
        self,
        request_exception: Exception
    ) -> bool:
        error_description = str(request_exception)
        ts_error_target_str = "Request timestamp expired"

        return ts_error_target_str in error_description

    def _collateral_token_based_on_trading_pair(self, trading_pair: str) -> str:
        """
        Returns the collateral token based on the trading pair
        (For example this method need for order cancellation)

        :return: The collateral token
        """
        base, quote = split_hb_trading_pair(trading_pair=trading_pair)

        if quote == "USD":
            collateral_token = base
        else:
            collateral_token = quote

        return collateral_token

    async def get_exchange_position_mode(self, trading_pair: str) -> None:
        """
        Returns the current exchange position mode.
        """
        product_type = await self.product_type_associated_to_trading_pair(trading_pair)
        account_info_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_INFO_ENDPOINT,
            params={
                "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
                "productType": product_type,
                "marginCoin": self.get_buy_collateral_token(trading_pair),
            },
            is_auth_required=True,
        )
        if account_info_response["code"] != CONSTANTS.RET_CODE_OK:
            self.logger().error(self._formatted_error(
                account_info_response["code"],
                f"Error getting position mode for {trading_pair}: {account_info_response['msg']}"
            ))
            return

        position_modes = {
            "one_way_mode": PositionMode.ONEWAY,
            "hedge_mode": PositionMode.HEDGE,
        }

        position_mode = position_modes[account_info_response["data"]["posMode"]]

        self.logger().info(f"Position mode for {trading_pair}: {position_mode}")

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules.get(trading_pair, None)
        if trading_rule is None:
            collateral_token = self._collateral_token_based_on_trading_pair(
                trading_pair=trading_pair
            )
        else:
            collateral_token = trading_rule.buy_order_collateral_token

        return collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return self.get_buy_collateral_token(trading_pair=trading_pair)

    async def product_type_associated_to_trading_pair(self, trading_pair: str) -> str:
        """
        Returns the product type associated with the trading pair
        """
        _, quote = split_hb_trading_pair(trading_pair)

        if quote == "USDT":
            return CONSTANTS.USDT_PRODUCT_TYPE

        if quote == "USDC":
            return CONSTANTS.USDC_PRODUCT_TYPE

        return CONSTANTS.USD_PRODUCT_TYPE

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
        if isinstance(cancelation_exception, IOError):
            return any(
                value in str(cancelation_exception)
                for value in CONSTANTS.RET_CODES_ORDER_NOT_EXISTS
            )

        return False

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)
        product_type = await self.product_type_associated_to_trading_pair(
            tracked_order.trading_pair
        )
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_ENDPOINT,
            data={
                "symbol": symbol,
                "productType": product_type,
                "marginCoin": self.get_buy_collateral_token(tracked_order.trading_pair),
                "orderId": tracked_order.exchange_order_id
            },
            is_auth_required=True,
        )
        response_code = cancel_result["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(response_code, cancel_result["msg"]))

        return True

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ) -> Tuple[str, float]:
        product_type = await self.product_type_associated_to_trading_pair(trading_pair)
        margin_modes = {
            MarginMode.CROSS: "crossed",
            MarginMode.ISOLATED: "isolated"
        }
        data = {
            "marginCoin": self.get_buy_collateral_token(trading_pair),
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "productType": product_type,
            "size": str(amount),
            "force": CONSTANTS.DEFAULT_TIME_IN_FORCE,
            "clientOid": order_id,
            "side": trade_type.name.lower(),
            "marginMode": margin_modes[self._margin_mode],
            "orderType": "limit" if order_type.is_limit_type() else "market",
        }
        if order_type.is_limit_type():
            data["price"] = str(price)

        if self.position_mode is PositionMode.HEDGE:
            if position_action is PositionAction.CLOSE:
                data["side"] = "sell" if trade_type is TradeType.BUY else "buy"
            data["tradeSide"] = position_action.name.lower()

        resp = await self._api_post(
            path_url=CONSTANTS.PLACE_ORDER_ENDPOINT,
            data=data,
            is_auth_required=True,
            headers={
                "X-CHANNEL-API-CODE": CONSTANTS.API_CODE,
            }
        )

        if resp["code"] != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                resp["code"],
                f"Error submitting order {order_id}: {resp['msg']}"
            ))

        return str(resp["data"]["orderId"]), self.current_timestamp

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None
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
        symbol_data = []

        for product_type in CONSTANTS.ALL_PRODUCT_TYPES:
            exchange_info = await self._api_get(
                path_url=self.trading_rules_request_path,
                params={
                    "productType": product_type
                }
            )
            symbol_data.extend(exchange_info["data"])

        for symbol_details in symbol_data:
            if bitget_perpetual_utils.is_exchange_information_valid(exchange_info=symbol_details):
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
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BitgetPerpetualAPIOrderBookDataSource(
            self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BitgetPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances
        """
        balances = []
        product_types: set[str] = {
            await self.product_type_associated_to_trading_pair(trading_pair)
            for trading_pair in self._trading_pairs
        } or CONSTANTS.ALL_PRODUCT_TYPES

        for product_type in product_types:
            accounts_info_response: Dict[str, Any] = await self._api_get(
                path_url=CONSTANTS.ACCOUNTS_INFO_ENDPOINT,
                params={
                    "productType": product_type
                },
                is_auth_required=True,
            )

            if accounts_info_response["code"] != CONSTANTS.RET_CODE_OK:
                raise IOError(
                    self._formatted_error(
                        accounts_info_response["code"],
                        accounts_info_response["msg"]
                    )
                )

            balances.extend(accounts_info_response["data"])

        self._account_available_balances.clear()
        self._account_balances.clear()

        for balance_data in balances:
            quote_asset_name = balance_data["marginCoin"]
            queried_available = Decimal(balance_data["crossedMaxAvailable"])
            queried_total = Decimal(balance_data["accountEquity"])
            current_total = self._account_balances.get(quote_asset_name, Decimal(0))
            current_available = self._account_available_balances.get(quote_asset_name, Decimal(0))

            total = current_total + queried_total
            available = current_available + queried_available

            if total or available:
                self._account_available_balances[quote_asset_name] = available
                self._account_balances[quote_asset_name] = total

            if "assetList" in balance_data:
                for base_asset in balance_data["assetList"]:
                    base_asset_name = base_asset["coin"]
                    queried_available = Decimal(base_asset["available"])
                    queried_total = Decimal(base_asset["balance"])
                    current_total = self._account_balances.get(base_asset_name, Decimal(0))
                    current_available = self._account_available_balances.get(
                        base_asset_name,
                        Decimal(0)
                    )

                    total = current_total + queried_total
                    available = current_available + queried_available

                    if total or available:
                        self._account_available_balances[base_asset_name] = available
                        self._account_balances[base_asset_name] = total

    async def _update_positions(self):
        """
        Retrieves all positions using the REST API.
        """
        product_types: set[str] = {
            await self.product_type_associated_to_trading_pair(trading_pair)
            for trading_pair in self._trading_pairs
        }
        position_sides = {
            "long": PositionSide.LONG,
            "short": PositionSide.SHORT
        }

        for product_type in product_types:
            all_positions_response: Dict[str, Any] = await self._api_get(
                path_url=CONSTANTS.ALL_POSITIONS_ENDPOINT,
                params={
                    "productType": product_type
                },
                is_auth_required=True,
            )
            all_positions_data = all_positions_response["data"]

            for position in all_positions_data:
                symbol = position["symbol"]
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
                position_side = position_sides[position["holdSide"]]
                unrealized_pnl = Decimal(position["unrealizedPL"])
                entry_price = Decimal(position["openPriceAvg"])
                amount = Decimal(position["total"])
                leverage = Decimal(position["leverage"])

                pos_key = self._perpetual_trading.position_key(
                    trading_pair,
                    position_side
                )

                if amount != s_decimal_0:
                    position_amount = (
                        amount * (
                            Decimal("-1.0")
                            if position_side == PositionSide.SHORT
                            else Decimal("1.0")
                        )
                    )
                    position = Position(
                        trading_pair=trading_pair,
                        position_side=position_side,
                        unrealized_pnl=unrealized_pnl,
                        entry_price=entry_price,
                        amount=position_amount,
                        leverage=leverage,
                    )
                    self._perpetual_trading.set_position(pos_key, position)
                else:
                    self._perpetual_trading.remove_position(pos_key)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            try:
                all_fills_response = await self._request_order_fills(order=order)
                all_fills_data = all_fills_response["data"]["fillList"]

                for fill_data in all_fills_data:
                    trade_update = self._parse_trade_update(
                        trade_msg=fill_data,
                        tracked_order=order
                    )
                    trade_updates.append(trade_update)
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(
                    request_exception=ex
                ):
                    raise

        return trade_updates

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        symbol = await self.exchange_symbol_associated_to_pair(order.trading_pair)
        product_type = await self.product_type_associated_to_trading_pair(order.trading_pair)
        order_fills_response = await self._api_get(
            path_url=CONSTANTS.ORDER_FILLS_ENDPOINT,
            params={
                "orderId": order.exchange_order_id,
                "productType": product_type,
                "symbol": symbol,
            },
            is_auth_required=True,
        )
        return order_fills_response

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        try:
            order_status_data = await self._request_order_status_data(tracked_order=tracked_order)
            updated_order_data = order_status_data["data"]

            if len(updated_order_data) == 0:
                raise ValueError(f"Can't parse order status data. Data: {updated_order_data}")

            client_order_id = str(updated_order_data["clientOid"])

            order_update: OrderUpdate = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=CONSTANTS.STATE_TYPES[updated_order_data["state"]],
                client_order_id=client_order_id,
                exchange_order_id=updated_order_data["orderId"],
            )

            return order_update

        except IOError as ex:
            if self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                order_update = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=tracked_order.current_state,
                )
            else:
                raise

        return order_update

    async def _request_order_status_data(self, tracked_order: InFlightOrder) -> Dict:
        query_params = {
            "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
            "productType": await self.product_type_associated_to_trading_pair(
                tracked_order.trading_pair
            )
        }
        if tracked_order.exchange_order_id:
            query_params["orderId"] = tracked_order.exchange_order_id
        else:
            query_params["clientOid"] = tracked_order.client_order_id

        order_detail_response = await self._api_get(
            path_url=CONSTANTS.ORDER_DETAIL_ENDPOINT,
            params=query_params,
            is_auth_required=True,
        )

        return order_detail_response

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        product_type = await self.product_type_associated_to_trading_pair(trading_pair)
        ticker_response = await self._api_get(
            path_url=CONSTANTS.PUBLIC_TICKER_ENDPOINT,
            params={
                "symbol": symbol,
                "productType": product_type
            },
        )

        return float(ticker_response["data"][0]["lastPr"])

    async def set_margin_mode(
        self,
        mode: MarginMode
    ) -> None:
        """
        Change the margin mode of the exchange (cross/isolated)
        """
        margin_mode = CONSTANTS.MARGIN_MODE_TYPES[mode]

        for trading_pair in self.trading_pairs:
            product_type = await self.product_type_associated_to_trading_pair(trading_pair)

            response = await self._api_post(
                path_url=CONSTANTS.SET_MARGIN_MODE_ENDPOINT,
                data={
                    "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
                    "productType": product_type,
                    "marginMode": margin_mode,
                    "marginCoin": self.get_buy_collateral_token(trading_pair),
                },
                is_auth_required=True,
            )

            if response["code"] != CONSTANTS.RET_CODE_OK:
                self.logger().error(
                    self._formatted_error(
                        response["code"],
                        f"There was an error changing the margin mode ({response['msg']})"
                    )
                )
                return

            self.logger().info(f"Margin mode set to {margin_mode}")

    async def _trading_pair_position_mode_set(
        self,
        mode: PositionMode,
        trading_pair: str
    ) -> Tuple[bool, str]:
        if len(self.account_positions) > 0:
            return False, "Cannot change position because active positions exist"

        try:
            position_mode = CONSTANTS.POSITION_MODE_TYPES[mode]
            product_type = await self.product_type_associated_to_trading_pair(trading_pair)

            response = await self._api_post(
                path_url=CONSTANTS.SET_POSITION_MODE_ENDPOINT,
                data={
                    "productType": product_type,
                    "posMode": position_mode,
                },
                is_auth_required=True,
            )

            if response["code"] != CONSTANTS.RET_CODE_OK:
                return (
                    False,
                    self._formatted_error(response["code"], response["msg"])
                )
        except Exception as exception:
            return (
                False,
                f"There was an error changing the position mode ({exception})"
            )

        return True, ""

    async def _set_trading_pair_leverage(
        self,
        trading_pair: str,
        leverage: int
    ) -> Tuple[bool, str]:
        if len(self.account_positions) > 0:
            return False, "cannot change leverage because active positions exist"

        try:
            product_type = await self.product_type_associated_to_trading_pair(trading_pair)
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

            response: Dict[str, Any] = await self._api_post(
                path_url=CONSTANTS.SET_LEVERAGE_ENDPOINT,
                data={
                    "symbol": symbol,
                    "productType": product_type,
                    "marginCoin": self.get_buy_collateral_token(trading_pair),
                    "leverage": str(leverage)
                },
                is_auth_required=True,
            )

            if response["code"] != CONSTANTS.RET_CODE_OK:
                return False, self._formatted_error(response["code"], response["msg"])
        except Exception as exception:
            return (
                False,
                f"There was an error setting the leverage for {trading_pair} ({exception})"
            )

        return True, ""

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")

        product_type = await self.product_type_associated_to_trading_pair(trading_pair)
        payment_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_BILLS_ENDPOINT,
            params={
                "productType": product_type,
                "businessType": "contract_settle_fee",
            },
            is_auth_required=True,
        )
        payment_data: Dict[str, Any] = payment_response["data"]["bills"]

        if payment_data:
            last_data = payment_data[0]
            funding_info = self._perpetual_trading._funding_info.get(trading_pair)
            payment: Decimal = Decimal(last_data["amount"])
            funding_rate: Decimal = funding_info.rate if funding_info is not None else Decimal(0)
            timestamp: float = int(last_data["cTime"]) * 1e-3

        return timestamp, funding_rate, payment

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message["arg"]["channel"]
                data = event_message["data"]

                if channel == CONSTANTS.WS_POSITIONS_ENDPOINT:
                    await self._process_account_position_event(data)
                elif channel == CONSTANTS.WS_ORDERS_ENDPOINT:
                    for order_msg in data:
                        self._process_trade_event_message(order_msg)
                        self._process_order_event_message(order_msg)
                        self._process_balance_update_from_order_event(order_msg)
                elif channel == CONSTANTS.WS_ACCOUNT_ENDPOINT:
                    for wallet_msg in data:
                        self._process_wallet_event_message(wallet_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")

    async def _process_account_position_event(self, position_entries: List[Dict[str, Any]]):
        """
        Updates position
        :param position_msg: The position event message payload
        """
        all_position_keys = []
        position_sides = {
            "long": PositionSide.LONG,
            "short": PositionSide.SHORT
        }

        for position in position_entries:
            symbol = position["instId"]
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
            position_side = position_sides[position["holdSide"]]
            entry_price = Decimal(position["openPriceAvg"])
            amount = Decimal(position["total"])
            leverage = Decimal(position["leverage"])
            unrealized_pnl = Decimal(position["unrealizedPL"])

            pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
            all_position_keys.append(pos_key)

            if amount != s_decimal_0:
                position_amount = (
                    amount * (
                        Decimal("-1.0")
                        if position_side == PositionSide.SHORT
                        else Decimal("1.0")
                    )
                )
                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=position_amount,
                    leverage=leverage,
                )
                self._perpetual_trading.set_position(pos_key, position)
            else:
                self._perpetual_trading.remove_position(pos_key)

        # Bitget sends position events as snapshots.
        # If a position is closed it is just not included in the snapshot
        position_keys = list(self.account_positions.keys())
        positions_to_remove = (
            position_key
            for position_key in position_keys
            if position_key not in all_position_keys
        )
        for position_key in positions_to_remove:
            self._perpetual_trading.remove_position(position_key)

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.

        :param order_msg: The order event message payload
        """
        order_status = CONSTANTS.STATE_TYPES[order_msg["status"]]
        client_order_id = str(order_msg["clientOid"])
        updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if updatable_order is not None:
            new_order_update: OrderUpdate = OrderUpdate(
                trading_pair=updatable_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=order_status,
                client_order_id=client_order_id,
                exchange_order_id=order_msg["orderId"],
            )
            self._order_tracker.process_order_update(new_order_update)

    def _process_balance_update_from_order_event(self, order_msg: Dict[str, Any]):
        order_status = CONSTANTS.STATE_TYPES[order_msg["status"]]
        symbol = order_msg["marginCoin"]
        states_to_consider = [OrderState.OPEN, OrderState.CANCELED]
        order_amount = Decimal(order_msg["size"])
        order_price = Decimal(order_msg["price"])
        margin_amount = (order_amount * order_price) / Decimal(order_msg["leverage"])
        is_opening = order_msg["tradeSide"] in [
            "open",
            "buy_single",
            "sell_single",
        ]

        if (
            symbol in self._account_available_balances
            and order_status in states_to_consider
            and is_opening
        ):
            multiplier = Decimal(-1) if order_status == OrderState.OPEN else Decimal(1)
            self._account_available_balances[symbol] += margin_amount * multiplier

    def _process_trade_event_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received.
        Triggers order completed event if the total executed amount equals to the specified order amount.

        :param trade_msg: The trade event message payload
        """

        client_order_id = str(trade_msg["clientOid"])
        fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)

        if fillable_order and "tradeId" in trade_msg:
            trade_update = self._parse_websocket_trade_update(
                trade_msg=trade_msg,
                tracked_order=fillable_order
            )
            if trade_update:
                self._order_tracker.process_trade_update(trade_update)

    def _parse_websocket_trade_update(
        self,
        trade_msg: Dict,
        tracked_order: InFlightOrder
    ) -> TradeUpdate:
        trade_id: str = trade_msg["tradeId"]

        if trade_id is not None:
            trade_id = str(trade_id)
            fee_asset = trade_msg["fillFeeCoin"]
            fee_amount = Decimal(trade_msg["fillFee"])
            position_actions = {
                "open": PositionAction.OPEN,
                "close": PositionAction.CLOSE,
            }
            position_action = position_actions.get(trade_msg["tradeSide"], PositionAction.NIL)
            flat_fees = (
                [] if fee_amount == Decimal("0")
                else [TokenAmount(amount=fee_amount, token=fee_asset)]
            )

            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=flat_fees,
            )

            exec_price = (
                Decimal(trade_msg["fillPrice"])
                if "fillPrice" in trade_msg
                else Decimal(trade_msg["price"])
            )
            exec_time = int(trade_msg["fillTime"]) * 1e-3

            trade_update: TradeUpdate = TradeUpdate(
                trade_id=trade_id,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(trade_msg["orderId"]),
                trading_pair=tracked_order.trading_pair,
                fill_timestamp=exec_time,
                fill_price=exec_price,
                fill_base_amount=Decimal(trade_msg["baseVolume"]),
                fill_quote_amount=exec_price * Decimal(trade_msg["baseVolume"]),
                fee=fee,
            )

            return trade_update

    def _parse_trade_update(self, trade_msg: Dict, tracked_order: InFlightOrder) -> TradeUpdate:
        fee_detail = trade_msg["feeDetail"][0]
        fee_asset = fee_detail["feeCoin"]
        fee_amount = abs(Decimal((
            fee_detail["totalDeductionFee"]
            if fee_detail.get("deduction") == "yes"
            else fee_detail["totalFee"]
        )))
        position_actions = {
            "open": PositionAction.OPEN,
            "close": PositionAction.CLOSE,
        }
        position_action = position_actions.get(trade_msg["tradeSide"], PositionAction.NIL)
        flat_fees = (
            [] if fee_amount == Decimal("0")
            else [TokenAmount(amount=fee_amount, token=fee_asset)]
        )

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=flat_fees,
        )

        exec_price = Decimal(trade_msg["price"])
        exec_time = int(trade_msg["cTime"]) * 1e-3

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=trade_msg["tradeId"],
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=trade_msg["orderId"],
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=exec_time,
            fill_price=exec_price,
            fill_base_amount=Decimal(trade_msg["baseVolume"]),
            fill_quote_amount=exec_price * Decimal(trade_msg["baseVolume"]),
            fee=fee,
        )

        return trade_update

    def _process_wallet_event_message(self, wallet_msg: Dict[str, Any]):
        """
        Updates account balances.
        :param wallet_msg: The account balance update message payload
        """
        symbol = wallet_msg["marginCoin"]
        available = Decimal(wallet_msg["maxOpenPosAvailable"])
        total = Decimal(wallet_msg["equity"])

        self._account_balances[symbol] = total
        self._account_available_balances[symbol] = available

    async def _make_trading_pairs_request(self) -> Any:
        all_exchange_info: List[Dict[str, Any]] = []

        for product_type in CONSTANTS.ALL_PRODUCT_TYPES:
            exchange_info = await self._api_get(
                path_url=self.trading_pairs_request_path,
                params={
                    "productType": product_type
                }
            )
            all_exchange_info.extend(exchange_info["data"])

        return all_exchange_info

    async def _make_trading_rules_request(self) -> Any:
        return await self._make_trading_pairs_request()

    def _initialize_trading_pair_symbols_from_exchange_info(
        self,
        exchange_info: List[Dict[str, Any]]
    ) -> None:
        mapping = bidict()
        for symbol_data in exchange_info:
            if bitget_perpetual_utils.is_exchange_information_valid(exchange_info=symbol_data):
                try:
                    symbol = symbol_data["symbol"]
                    base = symbol_data["baseCoin"]
                    quote = symbol_data["quoteCoin"]
                    trading_pair = combine_to_hb_trading_pair(base, quote)
                    mapping[symbol] = trading_pair
                except Exception as exception:
                    self.logger().error(
                        f"There was an error parsing a trading pair information ({exception}). Symbol: {symbol}. Trading pair: {trading_pair}"
                    )
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(
        self,
        exchange_info_dict: Dict[str, List[Dict[str, Any]]]
    ) -> List[TradingRule]:
        """
        Converts JSON API response into a local dictionary of trading rules.

        :param instrument_info_dict: The JSON API response.

        :returns: A dictionary of trading pair to its respective TradingRule.
        """
        trading_rules = []
        for rule in exchange_info_dict:
            if bitget_perpetual_utils.is_exchange_information_valid(exchange_info=rule):
                try:
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                        symbol=rule["symbol"]
                    )
                    max_order_size = Decimal(rule["maxOrderQty"]) if rule["maxOrderQty"] else None
                    margin_coin = rule["supportMarginCoins"][0]

                    trading_rules.append(
                        TradingRule(
                            trading_pair=trading_pair,
                            min_order_value=Decimal(rule["minTradeUSDT"]),
                            max_order_size=max_order_size,
                            min_order_size=Decimal(rule["minTradeNum"]),
                            min_price_increment=Decimal(f"1e-{int(rule['pricePlace'])}"),
                            min_base_amount_increment=Decimal(rule["sizeMultiplier"]),
                            buy_order_collateral_token=margin_coin,
                            sell_order_collateral_token=margin_coin,
                        )
                    )
                except Exception:
                    self.logger().exception(
                        f"Error parsing the trading pair rule: {rule}. Skipping."
                    )

        return trading_rules
