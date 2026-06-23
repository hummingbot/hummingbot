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
        # Initialize symbol mappings before starting network
        # This ensures get_funding_info can convert trading pairs to exchange symbols
        await self._initialize_trading_pair_symbol_map()
        await super().start_network()
        if self.is_trading_required:
            await self.set_margin_mode(self._margin_mode)
            await self._initialize_position_mode()

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

    async def _fetch_account_position_mode(self) -> Optional[PositionMode]:
        """
        Fetches the current position mode from the Bitget exchange account.
        Uses the first trading pair to query the account info.
        """
        if not self.trading_pairs:
            return None
        trading_pair = self.trading_pairs[0]
        # V3 UTA account settings are account-level (no symbol/productType/marginCoin params).
        account_info_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_INFO_ENDPOINT,
            is_auth_required=True,
        )
        if account_info_response["code"] != CONSTANTS.RET_CODE_OK:
            self.logger().error(self._formatted_error(
                account_info_response["code"],
                f"Error getting position mode for {trading_pair}: {account_info_response['msg']}"
            ))
            return None

        position_modes = {
            "one_way_mode": PositionMode.ONEWAY,
            "hedge_mode": PositionMode.HEDGE,
            # V3 holdMode spellings
            "single_hold": PositionMode.ONEWAY,
            "double_hold": PositionMode.HEDGE,
        }

        # V3 renames posMode -> holdMode in the account settings payload.
        settings_data = account_info_response["data"]
        hold_mode = settings_data.get("holdMode", settings_data.get("posMode"))
        position_mode = position_modes[hold_mode]
        self.logger().info(f"Position mode for {trading_pair}: {position_mode}")
        return position_mode

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
        # V3 UTA cancel-order identifies the order by orderId/clientOid across the unified account.
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_ENDPOINT,
            data={
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
        # V3 UTA place-order: productType -> category, size -> qty, force -> timeInForce, and the
        # marginCoin is implicit for the unified account.
        data = {
            "category": product_type,
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "qty": str(amount),
            "timeInForce": CONSTANTS.DEFAULT_TIME_IN_FORCE,
            "clientOid": order_id,
            "side": trade_type.name.lower(),
            "marginMode": margin_modes[self._margin_mode],
            "orderType": "limit" if order_type.is_limit_type() else "market",
        }
        if order_type.is_limit_type():
            data["price"] = str(price)

        if self.position_mode is PositionMode.HEDGE:
            # V3 hedge mode uses posSide (long/short) instead of the V2 tradeSide (open/close).
            # A close flips the order side and targets the existing position side; reduceOnly is set.
            if position_action is PositionAction.CLOSE:
                data["side"] = "sell" if trade_type is TradeType.BUY else "buy"
                data["reduceOnly"] = "yes"
                data["posSide"] = "long" if trade_type is TradeType.BUY else "short"
            else:
                data["posSide"] = "long" if trade_type is TradeType.BUY else "short"

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
                    "category": product_type
                }
            )
            symbol_data.extend(exchange_info["data"])

        for symbol_details in symbol_data:
            maker_fee = symbol_details.get("makerFeeRate")
            taker_fee = symbol_details.get("takerFeeRate")
            if (
                bitget_perpetual_utils.is_exchange_information_valid(exchange_info=symbol_details)
                and maker_fee is not None
                and taker_fee is not None
            ):
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                    symbol=symbol_details["symbol"]
                )
                self._trading_fees[trading_pair] = TradeFeeSchema(
                    maker_percent_fee_decimal=Decimal(maker_fee),
                    taker_percent_fee_decimal=Decimal(taker_fee)
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
        Calls REST API to update total and available balances.

        Under the V3 UTA account this is a single /api/v3/account/assets call returning one unified
        wallet (data.assets[*] = {coin, available, locked, balance, ...}). The legacy per-product-type
        accounts shape (marginCoin/crossedMaxAvailable/accountEquity + nested assetList) is still
        parsed as a fallback.
        """
        accounts_info_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_INFO_ENDPOINT,
            is_auth_required=True,
        )

        if accounts_info_response["code"] != CONSTANTS.RET_CODE_OK:
            raise IOError(
                self._formatted_error(
                    accounts_info_response["code"],
                    accounts_info_response["msg"]
                )
            )

        self._account_available_balances.clear()
        self._account_balances.clear()

        data = accounts_info_response["data"]

        if isinstance(data, dict):
            for asset in data.get("assets", []):
                self._accumulate_balance(
                    asset["coin"],
                    Decimal(str(asset["available"])),
                    Decimal(str(asset.get("balance", asset["available"]))),
                )
        else:
            for balance_data in data:
                self._accumulate_balance(
                    balance_data["marginCoin"],
                    Decimal(balance_data["crossedMaxAvailable"]),
                    Decimal(balance_data["accountEquity"]),
                )
                for base_asset in balance_data.get("assetList", []):
                    self._accumulate_balance(
                        base_asset["coin"],
                        Decimal(base_asset["available"]),
                        Decimal(base_asset["balance"]),
                    )

    def _accumulate_balance(self, coin: str, available: Decimal, total: Decimal) -> None:
        new_total = self._account_balances.get(coin, Decimal(0)) + total
        new_available = self._account_available_balances.get(coin, Decimal(0)) + available
        if new_total or new_available:
            self._account_available_balances[coin] = new_available
            self._account_balances[coin] = new_total

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
                    "category": product_type
                },
                is_auth_required=True,
            )
            all_positions_data = all_positions_response["data"]

            for position in all_positions_data:
                # V3 current-position (CurrentPositionV3) fields.
                symbol = position["symbol"]
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
                position_side = position_sides[position["posSide"]]
                unrealized_pnl = Decimal(str(position["unrealisedPnl"]))
                entry_price = Decimal(str(position["avgPrice"]))
                amount = Decimal(str(position["total"]))
                leverage = Decimal(str(position["leverage"]))

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
                # V3 fills returns data as a list; tolerate the legacy {"fillList": [...]} wrapper.
                fills_payload = all_fills_response["data"]
                all_fills_data = (
                    fills_payload.get("fillList", []) if isinstance(fills_payload, dict) else fills_payload
                )

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
        # V3 UTA fills query identifies fills by orderId across the unified account.
        order_fills_response = await self._api_get(
            path_url=CONSTANTS.ORDER_FILLS_ENDPOINT,
            params={
                "orderId": order.exchange_order_id,
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

            # V3 order-info returns a single object; state -> orderStatus.
            if isinstance(updated_order_data, list):
                updated_order_data = updated_order_data[0]
            client_order_id = str(updated_order_data["clientOid"])

            order_update: OrderUpdate = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=CONSTANTS.STATE_TYPES[
                    updated_order_data.get("orderStatus", updated_order_data.get("state"))
                ],
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
        # V3 UTA order-info identifies the order by orderId/clientOid across the unified account.
        query_params = {}
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
                "category": product_type
            },
        )

        ticker = ticker_response["data"][0]
        # V3 renames the last price field lastPr -> lastPrice.
        return float(ticker.get("lastPrice", ticker.get("lastPr")))

    async def set_margin_mode(
        self,
        mode: MarginMode
    ) -> None:
        """
        Change the margin mode of the exchange (cross/isolated)
        """
        margin_mode = CONSTANTS.MARGIN_MODE_TYPES[mode]

        # NOTE: Under the V3 UTA account the per-order marginMode is also sent on place-order. The
        # account-level margin/account mode endpoint and its exact request body should be confirmed
        # against the live UTA docs (productType -> category here).
        for trading_pair in self.trading_pairs:
            product_type = await self.product_type_associated_to_trading_pair(trading_pair)

            response = await self._api_post(
                path_url=CONSTANTS.SET_MARGIN_MODE_ENDPOINT,
                data={
                    "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
                    "category": product_type,
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

    async def _execute_set_position_mode(self, mode: PositionMode):
        """Bitget derives productType from trading_pair, so we must loop over all trading pairs."""
        async with self._set_position_mode_lock:
            try:
                exchange_mode = await self._fetch_account_position_mode()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().warning(f"Could not fetch position mode from exchange: {e}")
                exchange_mode = None

            self.logger().info(
                f"Setting position mode: requested={mode}, current_exchange={exchange_mode}")

            if exchange_mode == mode:
                self._perpetual_trading.set_position_mode(mode)
                self._fire_position_mode_events(mode, success=True)
                self.logger().info(f"Position mode already set to {mode} on exchange.")
                return

            all_success = True
            msg = ""
            for trading_pair in self.trading_pairs:
                success, msg = await self._trading_pair_position_mode_set(mode, trading_pair)
                if not success:
                    all_success = False
                    self.logger().network(f"Error switching {trading_pair} mode to {mode}: {msg}")
                    break

            if all_success:
                self._perpetual_trading.set_position_mode(mode)
                self.logger().info(f"Position mode switched to {mode}.")
            else:
                self.logger().error(f"Failed to set position mode to {mode}: {msg}")
            self._fire_position_mode_events(mode, success=all_success, message=msg)

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

            # V3 set-hold-mode: productType -> category, posMode -> holdMode.
            response = await self._api_post(
                path_url=CONSTANTS.SET_POSITION_MODE_ENDPOINT,
                data={
                    "category": product_type,
                    "holdMode": position_mode,
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

            # V3 set-leverage params: category, symbol, leverage, coin (the position/margin currency).
            response: Dict[str, Any] = await self._api_post(
                path_url=CONSTANTS.SET_LEVERAGE_ENDPOINT,
                data={
                    "symbol": symbol,
                    "category": product_type,
                    "coin": self.get_buy_collateral_token(trading_pair),
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
        # V3 financial-records: productType -> category, businessType -> type; data is a list of
        # records (FinancialRecordV3) instead of the legacy {"bills": [...]} wrapper, ts replaces cTime.
        payment_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_BILLS_ENDPOINT,
            params={
                "category": product_type,
                "type": "contract_settle_fee",
            },
            is_auth_required=True,
        )
        payment_payload = payment_response["data"]
        # V3 financial-records returns the records under data.list (FinancialRecordPage), with ts.
        payment_data = (
            payment_payload.get("list", []) if isinstance(payment_payload, dict) else payment_payload
        )

        if payment_data:
            last_data = payment_data[0]
            funding_info = self._perpetual_trading._funding_info.get(trading_pair)
            payment: Decimal = Decimal(str(last_data["amount"]))
            funding_rate: Decimal = funding_info.rate if funding_info is not None else Decimal(0)
            timestamp: float = int(last_data["ts"]) * 1e-3

        return timestamp, funding_rate, payment

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                # V3 UTA push envelope uses arg.topic (the V2 API used arg.channel). Fills now arrive
                # on the dedicated "fill" channel; the "order" channel carries order state only.
                arg = event_message["arg"]
                channel = arg.get("topic", arg.get("channel"))
                data = event_message["data"]

                if channel == CONSTANTS.WS_POSITIONS_ENDPOINT:
                    await self._process_account_position_event(data)
                elif channel == CONSTANTS.WS_ORDERS_ENDPOINT:
                    for order_msg in data:
                        self._process_order_event_message(order_msg)
                        self._process_balance_update_from_order_event(order_msg)
                elif channel == CONSTANTS.WS_FILL_ENDPOINT:
                    for fill_msg in data:
                        self._process_trade_event_message(fill_msg)
                elif channel == CONSTANTS.WS_ACCOUNT_ENDPOINT:
                    # The V3 account channel nests per-coin balances in each entry's "coin" array.
                    for account_msg in data:
                        for coin_balance in account_msg.get("coin", []):
                            self._process_wallet_event_message(coin_balance)
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
            # V3 UTA position channel (BitgetUaPositionUpdate): symbol (not instId), posSide, size
            # (not total), avgPrice, unrealisedPnl.
            symbol = position["symbol"]
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
            position_side = position_sides[position["posSide"]]
            entry_price = Decimal(str(position["avgPrice"]))
            amount = Decimal(str(position["size"]))
            leverage = Decimal(str(position["leverage"]))
            unrealized_pnl = Decimal(str(position["unrealisedPnl"]))

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
        order_status = CONSTANTS.STATE_TYPES[order_msg["orderStatus"]]
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
        # V3 order channel (BitgetUaOrder): orderStatus, marginCoin, qty (was size), price, leverage.
        order_status = CONSTANTS.STATE_TYPES[order_msg["orderStatus"]]
        symbol = order_msg["marginCoin"]
        states_to_consider = [OrderState.OPEN, OrderState.CANCELED]
        order_amount = Decimal(order_msg["qty"])
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

        # The V3 UTA "fill" channel shares the BitgetUaUserTrade shape with the REST fills endpoint,
        # so the same parser is used for both.
        if fillable_order and "execId" in trade_msg:
            trade_update = self._parse_trade_update(
                trade_msg=trade_msg,
                tracked_order=fillable_order
            )
            if trade_update:
                self._order_tracker.process_trade_update(trade_update)

    def _parse_trade_update(self, trade_msg: Dict, tracked_order: InFlightOrder) -> TradeUpdate:
        # V3 fills (FillV3) rename fields: tradeId->execId, price->execPrice, baseVolume->execQty,
        # cTime->createdTime, and feeDetail[].{totalFee/totalDeductionFee}->feeDetail[].fee. Legacy
        # names are kept as fallbacks so V2-shaped payloads keep parsing.
        fee_detail = trade_msg["feeDetail"][0]
        fee_asset = fee_detail["feeCoin"]
        if "fee" in fee_detail:
            fee_amount = abs(Decimal(str(fee_detail["fee"])))
        else:
            fee_amount = abs(Decimal((
                fee_detail["totalDeductionFee"]
                if fee_detail.get("deduction") == "yes"
                else fee_detail["totalFee"]
            )))
        position_actions = {
            "open": PositionAction.OPEN,
            "close": PositionAction.CLOSE,
        }
        position_action = position_actions.get(trade_msg.get("tradeSide"), PositionAction.NIL)
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

        exec_price = Decimal(str(trade_msg.get("execPrice", trade_msg.get("price"))))
        exec_qty = Decimal(str(trade_msg.get("execQty", trade_msg.get("baseVolume"))))
        exec_time = int(trade_msg.get("createdTime", trade_msg.get("cTime"))) * 1e-3

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=str(trade_msg.get("execId", trade_msg.get("tradeId"))),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=trade_msg["orderId"],
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=exec_time,
            fill_price=exec_price,
            fill_base_amount=exec_qty,
            fill_quote_amount=exec_price * exec_qty,
            fee=fee,
        )

        return trade_update

    def _process_wallet_event_message(self, coin_balance: Dict[str, Any]):
        """
        Updates account balances from a single V3 UTA account-channel coin entry
        (coin/available/balance).
        :param coin_balance: One per-coin balance entry from the account channel "coin" array
        """
        symbol = coin_balance["coin"]
        available = Decimal(str(coin_balance["available"]))
        total = Decimal(str(coin_balance["balance"]))

        self._account_balances[symbol] = total
        self._account_available_balances[symbol] = available

    async def _make_trading_pairs_request(self) -> Any:
        all_exchange_info: List[Dict[str, Any]] = []

        for product_type in CONSTANTS.ALL_PRODUCT_TYPES:
            exchange_info = await self._api_get(
                path_url=self.trading_pairs_request_path,
                params={
                    "category": product_type
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
                    # V3 instruments field names (with V2 fallbacks): minTradeUSDT -> minOrderAmount,
                    # minTradeNum -> minOrderQty, pricePlace -> pricePrecision, sizeMultiplier ->
                    # 1e-quantityPrecision. supportMarginCoins is gone; the collateral coin is the
                    # quote coin for USDT/USDC futures and the base coin for coin-margined futures.
                    max_order_qty = rule.get("maxOrderQty")
                    max_order_size = Decimal(str(max_order_qty)) if max_order_qty else None
                    min_order_value = rule.get("minOrderAmount", rule.get("minTradeUSDT"))
                    min_order_size = rule.get("minOrderQty", rule.get("minTradeNum"))

                    if "pricePrecision" in rule:
                        min_price_increment = Decimal(f"1e-{int(rule['pricePrecision'])}")
                    else:
                        min_price_increment = Decimal(f"1e-{int(rule['pricePlace'])}")

                    if "quantityPrecision" in rule:
                        min_base_amount_increment = Decimal(f"1e-{int(rule['quantityPrecision'])}")
                    else:
                        min_base_amount_increment = Decimal(str(rule["sizeMultiplier"]))

                    if "supportMarginCoins" in rule:
                        margin_coin = rule["supportMarginCoins"][0]
                    else:
                        base, quote = split_hb_trading_pair(trading_pair)
                        margin_coin = base if rule.get("category") == CONSTANTS.USD_PRODUCT_TYPE else quote

                    trading_rules.append(
                        TradingRule(
                            trading_pair=trading_pair,
                            min_order_value=Decimal(str(min_order_value)),
                            max_order_size=max_order_size,
                            min_order_size=Decimal(str(min_order_size)),
                            min_price_increment=min_price_increment,
                            min_base_amount_increment=min_base_amount_increment,
                            buy_order_collateral_token=margin_coin,
                            sell_order_collateral_token=margin_coin,
                        )
                    )
                except Exception:
                    self.logger().exception(
                        f"Error parsing the trading pair rule: {rule}. Skipping."
                    )

        return trading_rules
