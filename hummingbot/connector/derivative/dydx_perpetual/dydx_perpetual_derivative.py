import asyncio
import time
from copy import deepcopy
from decimal import Decimal
from math import ceil
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict
from dateutil.parser import parse as dateparse
from dydx3.helpers.request_helpers import epoch_seconds_to_iso, generate_now_iso, iso_to_epoch_seconds

import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_constants as CONSTANTS
from hummingbot.connector.constants import s_decimal_0, s_decimal_NaN
from hummingbot.connector.derivative.dydx_perpetual import dydx_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_api_order_book_data_source import (
    DydxPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth import DydxPerpetualAuth
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_data_source import (
    DydxPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_utils import clamp
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import AccountEvent, PositionModeChangeEvent
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class DydxPerpetualDerivative(PerpetualDerivativePyBase):

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        dydx_perpetual_api_key: str,
        dydx_perpetual_api_secret: str,
        dydx_perpetual_passphrase: str,
        dydx_perpetual_ethereum_address: str,
        dydx_perpetual_stark_private_key: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self._dydx_perpetual_api_key = dydx_perpetual_api_key
        self._dydx_perpetual_api_secret = dydx_perpetual_api_secret
        self._dydx_perpetual_passphrase = dydx_perpetual_passphrase
        self._dydx_perpetual_ethereum_address = dydx_perpetual_ethereum_address
        self._dydx_perpetual_stark_private_key = dydx_perpetual_stark_private_key
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._domain = domain

        self._order_notional_amounts = {}
        self._current_place_order_requests = 0
        self._rate_limits_config = {}
        self._margin_fractions = {}
        self._position_id = None

        self._allocated_collateral = {}
        self._allocated_collateral_sum = Decimal("0")

        super().__init__(client_config_map=client_config_map)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> DydxPerpetualAuth:
        return DydxPerpetualAuth(
            dydx_perpetual_api_key=self._dydx_perpetual_api_key,
            dydx_perpetual_api_secret=self._dydx_perpetual_api_secret,
            dydx_perpetual_passphrase=self._dydx_perpetual_passphrase,
            dydx_perpetual_ethereum_address=self._dydx_perpetual_ethereum_address,
            dydx_perpetual_stark_private_key=self._dydx_perpetual_stark_private_key,
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        rate_limits = deepcopy(CONSTANTS.RATE_LIMITS)

        # Order cancelation
        for trading_pair in self._trading_pairs:
            rate_limits += [
                RateLimit(
                    limit_id=CONSTANTS.LIMIT_ID_ORDER_CANCEL + "_" + trading_pair,
                    limit=425,
                    time_interval=CONSTANTS.ONE_SECOND * 10,
                )
            ]

        # Order placement
        if "placeOrderRateLimiting" in self._rate_limits_config:
            for trading_pair in self._trading_pairs:
                rate_limits += [
                    RateLimit(
                        limit_id=CONSTANTS.LIMIT_ID_ORDER_PLACE + "_" + trading_pair,
                        limit=self._rate_limits_config["placeOrderRateLimiting"]["maxPoints"],
                        time_interval=self._rate_limits_config["placeOrderRateLimiting"]["windowSec"],
                    )
                ]

        for amount, amount_id in self._order_notional_amounts.items():
            weight = clamp(
                ceil(self._rate_limits_config["placeOrderRateLimiting"]["targetNotional"] / amount),
                self._rate_limits_config["placeOrderRateLimiting"]["minLimitConsumption"],
                self._rate_limits_config["placeOrderRateLimiting"]["maxOrderConsumption"],
            )

            for trading_pair in self._trading_pairs:
                rate_limits += [
                    RateLimit(
                        limit_id=CONSTANTS.LIMIT_ID_ORDER_PLACE + "_" + trading_pair + "_" + str(amount_id),
                        limit=self._rate_limits_config["placeOrderRateLimiting"]["maxPoints"],
                        time_interval=self._rate_limits_config["placeOrderRateLimiting"]["windowSec"],
                        linked_limits=[
                            LinkedLimitWeightPair(CONSTANTS.LIMIT_ID_ORDER_PLACE + "_" + trading_pair, weight)
                        ],
                    )
                ]

        return rate_limits

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.PATH_MARKETS

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.PATH_MARKETS

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PATH_TIME

    @property
    def trading_pairs(self) -> List[str]:
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

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_request_result_an_error_related_to_time_synchronizer(self, request_result: Dict[str, Any]) -> bool:
        if "errors" in request_result and "msg" in request_result["errors"]:
            if "Timestamp must be within" in request_result["errors"]["msg"]:
                return True
        return False

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        try:
            body_params = {
                "market": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
                "side": "BUY" if tracked_order.trade_type == TradeType.BUY else "SELL",
                "id": tracked_order.exchange_order_id,
            }

            resp = await self._api_delete(
                path_url=CONSTANTS.PATH_ACTIVE_ORDERS,
                params=body_params,
                is_auth_required=True,
                limit_id=CONSTANTS.LIMIT_ID_ORDER_CANCEL + "_" + tracked_order.trading_pair,
            )
            if "cancelOrders" not in resp.keys():
                raise IOError(f"Error canceling order {order_id}.")
        except IOError as e:
            if any(error in str(e) for error in [CONSTANTS.ERR_MSG_NO_ORDER_FOR_MARKET]):
                await self._order_tracker.process_order_not_found(order_id)
            else:
                raise
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
        if self._current_place_order_requests == 0:
            # No requests are under way, the dictionary can be cleaned
            self._order_notional_amounts = {}

        # Increment number of currently undergoing requests
        self._current_place_order_requests += 1

        notional_amount = amount * price
        if notional_amount not in self._order_notional_amounts.keys():
            self._order_notional_amounts[notional_amount] = len(self._order_notional_amounts.keys())
            # Set updated rate limits
            self._throttler.set_rate_limits(self.rate_limits_rules)

        size = str(amount)
        price = str(price)
        side = "BUY" if trade_type == TradeType.BUY else "SELL"
        expiration = int(time.time()) + CONSTANTS.ORDER_EXPIRATION
        limit_fee = str(CONSTANTS.LIMIT_FEE)
        reduce_only = False

        post_only = order_type is OrderType.LIMIT_MAKER
        time_in_force = CONSTANTS.TIF_GOOD_TIL_TIME
        market = await self.exchange_symbol_associated_to_pair(trading_pair)

        signature = self._auth.get_order_signature(
            position_id=self._position_id,
            client_id=order_id,
            market=market,
            side=side,
            size=size,
            price=price,
            limit_fee=limit_fee,
            expiration_epoch_seconds=expiration,
        )

        data = {
            "clientId": order_id,
            "market": market,
            "side": side,
            "price": str(price),
            "size": str(amount),
            "type": CONSTANTS.ORDER_TYPE_MAP[order_type],
            "limitFee": limit_fee,
            "expiration": epoch_seconds_to_iso(expiration),
            "timeInForce": time_in_force,
            "reduceOnly": reduce_only,
            "postOnly": post_only,
            "signature": signature,
        }

        try:
            resp = await self._api_post(
                path_url=CONSTANTS.PATH_ORDERS,
                data=data,
                is_auth_required=True,
                limit_id=CONSTANTS.LIMIT_ID_ORDER_PLACE
                + "_"
                + trading_pair
                + "_"
                + str(self._order_notional_amounts[notional_amount]),
            )
        except Exception:
            self._current_place_order_requests -= 1
            raise

        # Decrement number of currently undergoing requests
        self._current_place_order_requests -= 1

        if "order" not in resp:
            raise IOError(f"Error submitting order {order_id}.")

        return str(resp["order"]["id"]), iso_to_epoch_seconds(resp["order"]["createdAt"])

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = is_maker or False
        if CONSTANTS.FEES_KEY not in self._trading_fees.keys():
            fee = build_perpetual_trade_fee(
                self.name,
                is_maker,
                position_action=position_action,
                base_currency=base_currency,
                quote_currency=quote_currency,
                order_type=order_type,
                order_side=order_side,
                amount=amount,
                price=price,
            )
        else:
            fee_data = self._trading_fees[CONSTANTS.FEES_KEY]
            if is_maker:
                fee_value = Decimal(fee_data[CONSTANTS.FEE_MAKER_KEY])
            else:
                fee_value = Decimal(fee_data[CONSTANTS.FEE_TAKER_KEY])
            fee = AddedToCostTradeFee(percent=fee_value)
        return fee

    async def start_network(self):
        await super().start_network()
        await self._update_rate_limits()
        await self._update_position_id()

    async def _update_rate_limits(self):
        # Initialize rate limits for statically allocatedrequests
        self._throttler.set_rate_limits(self.rate_limits_rules)

        response: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.PATH_CONFIG,
            is_auth_required=False,
        )

        self._rate_limits_config["cancelOrderRateLimiting"] = response["cancelOrderRateLimiting"]
        self._rate_limits_config["placeOrderRateLimiting"] = response["placeOrderRateLimiting"]

        # Update rate limits with the obtained information
        self._throttler.set_rate_limits(self.rate_limits_rules)

    async def _update_position_id(self):
        if self._position_id is None:
            account = await self._get_account()
            self._position_id = account["positionId"]

    async def _update_trading_fees(self):
        response: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.PATH_CONFIG,
            is_auth_required=False,
        )

        self._trading_fees[CONSTANTS.FEES_KEY] = {
            CONSTANTS.FEE_MAKER_KEY: response["defaultMakerFee"],
            CONSTANTS.FEE_TAKER_KEY: response["defaultTakerFee"],
        }

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                event: Dict[str, Any] = event_message
                data: Dict[str, Any] = event["contents"]
                if "account" in data.keys() and len(data["account"]) > 0:
                    quote = "USD"
                    self._account_balances[quote] = Decimal(data["account"]["equity"])
                    # freeCollateral is sent only on start
                    self._account_available_balances[quote] = (
                        Decimal(data["account"]["quoteBalance"]) - self._allocated_collateral_sum
                    )
                    if "openPositions" in data["account"]:
                        await self._process_open_positions(data["account"]["openPositions"])

                if "accounts" in data.keys() and len(data["accounts"]) > 0:
                    for account in data["accounts"]:
                        quote = "USD"
                        # freeCollateral is sent only on start
                        self._account_available_balances[quote] = (
                            Decimal(account["quoteBalance"]) - self._allocated_collateral_sum
                        )

                if "orders" in data.keys() and len(data["orders"]) > 0:
                    for order in data["orders"]:
                        client_order_id: str = order["clientId"]
                        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                        if tracked_order is not None:
                            trading_pair = await self.trading_pair_associated_to_exchange_symbol(order["market"])
                            state = CONSTANTS.ORDER_STATE[order["status"]]
                            new_order_update: OrderUpdate = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=self.current_timestamp,
                                new_state=state,
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=tracked_order.exchange_order_id,
                            )
                            self._order_tracker.process_order_update(new_order_update)
                        # Processing all orders of the account, not just the client's
                        if order["status"] in ["OPEN"]:
                            initial_margin_requirement = (
                                Decimal(order["price"])
                                * Decimal(order["size"])
                                * self._margin_fractions[trading_pair]["initial"]
                            )
                            initial_margin_requirement = abs(initial_margin_requirement)
                            self._allocated_collateral[order["id"]] = initial_margin_requirement
                            self._allocated_collateral_sum += initial_margin_requirement
                            self._account_available_balances[quote] -= initial_margin_requirement
                        if order["status"] in ["FILLED", "CANCELED"]:
                            if order["id"] in self._allocated_collateral:
                                # Only deduct orders that were previously in the OPEN state
                                # Some orders are filled instantly and reach only the PENDING state
                                self._allocated_collateral_sum -= self._allocated_collateral[order["id"]]
                                self._account_available_balances[quote] += self._allocated_collateral[order["id"]]
                                del self._allocated_collateral[order["id"]]

                if "fills" in data.keys() and len(data["fills"]) > 0:
                    trade_updates = self._process_ws_fills(data["fills"])
                    for trade_update in trade_updates:
                        self._order_tracker.process_trade_update(trade_update)

                if "positions" in data.keys() and len(data["positions"]) > 0:
                    # this is hit when a position is closed
                    positions = data["positions"]
                    for position in positions:
                        trading_pair = position["market"]
                        if trading_pair not in self._trading_pairs:
                            continue
                        position_side = PositionSide[position["side"]]
                        pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
                        amount = Decimal(position.get("size"))

                        if amount != s_decimal_0:
                            position = Position(
                                trading_pair=trading_pair,
                                position_side=position_side,
                                unrealized_pnl=Decimal(position.get("unrealizedPnl", 0)),
                                entry_price=Decimal(position.get("entryPrice")),
                                amount=amount,
                                leverage=self.get_leverage(trading_pair),
                            )
                            self._perpetual_trading.set_position(pos_key, position)
                        else:
                            if self._perpetual_trading.get_position(pos_key):
                                self._perpetual_trading.remove_position(pos_key)

                if "fundingPayments" in data:
                    if event["type"] != CONSTANTS.WS_TYPE_SUBSCRIBED:  # Only subsequent funding payments
                        funding_payments = await self._process_funding_payments(data["fundingPayments"])
                        for trading_pair in funding_payments:
                            timestamp = funding_payments[trading_pair]["timestamp"]
                            funding_rate = funding_payments[trading_pair]["funding_rate"]
                            payment = funding_payments[trading_pair]["payment"]
                            self._emit_funding_payment_event(trading_pair, timestamp, funding_rate, payment, False)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []
        markets_info = exchange_info_dict["markets"]
        for market_name in markets_info:
            market = markets_info[market_name]
            try:
                collateral_token = market["quoteAsset"]
                trading_rules += [
                    TradingRule(
                        trading_pair=market_name,
                        min_order_size=Decimal(market["minOrderSize"]),
                        min_price_increment=Decimal(market["tickSize"]),
                        min_base_amount_increment=Decimal(market["stepSize"]),
                        min_notional_size=Decimal(market["minOrderSize"]) * Decimal(market["tickSize"]),
                        supports_limit_orders=True,
                        supports_market_orders=True,
                        buy_order_collateral_token=collateral_token,
                        sell_order_collateral_token=collateral_token,
                    )
                ]
                self._margin_fractions[market_name] = {
                    "initial": Decimal(market["initialMarginFraction"]),
                    "maintenance": Decimal(market["maintenanceMarginFraction"]),
                }
            except Exception:
                self.logger().exception("Error updating trading rules")
        return trading_rules

    async def _update_balances(self):
        account = await self._get_account()
        quote = "USD"
        self._account_balances[quote] = Decimal(account["equity"])
        # freeCollateral is sent only on start
        self._account_available_balances[quote] = Decimal(account["quoteBalance"]) - self._allocated_collateral_sum

    def _process_ws_fills(self, fills_data: List) -> List[TradeUpdate]:
        trade_updates = []
        all_fillable_orders = self._order_tracker.all_fillable_orders
        for fill_data in fills_data:
            client_order_id: str = fill_data["orderClientId"]
            order = all_fillable_orders.get(client_order_id)
            trade_update = self._process_order_fills(fill_data=fill_data, order=order)
            if trade_update is not None:
                trade_updates.append(trade_update)
        return trade_updates

    async def _process_funding_payments(self, funding_payments: List):
        data = {}

        for trading_pair in self._trading_pairs:
            data[trading_pair] = {}
            data[trading_pair]["timestamp"] = 0
            data[trading_pair]["funding_rate"] = Decimal("-1")
            data[trading_pair]["payment"] = Decimal("-1")
            if trading_pair in self._last_funding_fee_payment_ts:
                data[trading_pair]["timestamp"] = self._last_funding_fee_payment_ts[trading_pair]

        prev_timestamps = {}

        for funding_payment in funding_payments:
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(funding_payment["market"])

            if trading_pair not in prev_timestamps.keys():
                prev_timestamps[trading_pair] = None
            if (
                prev_timestamps[trading_pair] is not None
                and dateparse(funding_payment["effectiveAt"]).timestamp() <= prev_timestamps[trading_pair]
            ):
                continue
            timestamp = dateparse(funding_payment["effectiveAt"]).timestamp()
            funding_rate: Decimal = Decimal(funding_payment["rate"])
            payment: Decimal = Decimal(funding_payment["payment"])

            if trading_pair not in data:
                data[trading_pair] = {}

            data[trading_pair]["timestamp"] = timestamp
            data[trading_pair]["funding_rate"] = funding_rate
            data[trading_pair]["payment"] = payment

            prev_timestamps[trading_pair] = timestamp

        return data

    async def _process_open_positions(self, open_positions: Dict):
        for market, position in open_positions.items():
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=market)
            position_side = PositionSide[position["side"]]
            pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
            amount = Decimal(position.get("size"))
            if amount != s_decimal_0:
                entry_price = Decimal(position.get("entryPrice"))
                unrealized_pnl = Decimal(position.get("unrealizedPnl"))
                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=self.get_leverage(trading_pair),
                )
                self._perpetual_trading.set_position(pos_key, position)
            else:
                self._perpetual_trading.remove_position(pos_key)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            try:
                all_fills_response = await self._request_order_fills(order=order)
                fills_data = all_fills_response["fills"]
                trade_updates_tmp = self._process_rest_fills(fills_data)
                trade_updates += trade_updates_tmp

            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                    raise
        return trade_updates

    def _process_rest_fills(self, fills_data: List) -> List[TradeUpdate]:
        trade_updates = []
        all_fillable_orders_by_exchange_order_id = {
            order.exchange_order_id: order for order in self._order_tracker.all_fillable_orders.values()
        }
        for fill_data in fills_data:
            exchange_order_id: str = fill_data["orderId"]
            order = all_fillable_orders_by_exchange_order_id.get(exchange_order_id)
            trade_update = self._process_order_fills(fill_data=fill_data, order=order)
            if trade_update is not None:
                trade_updates.append(trade_update)
        return trade_updates

    def _process_order_fills(self, fill_data: Dict, order: InFlightOrder) -> Optional[TradeUpdate]:
        trade_update = None
        if order is not None:
            fee_asset = order.quote_asset
            fee_amount = Decimal(fill_data["fee"])
            flat_fees = [] if fee_amount == Decimal("0") else [TokenAmount(amount=fee_amount, token=fee_asset)]
            position_side = fill_data["side"]
            position_action = (
                PositionAction.OPEN
                if (
                    order.trade_type is TradeType.BUY
                    and position_side == "BUY"
                    or order.trade_type is TradeType.SELL
                    and position_side == "SELL"
                )
                else PositionAction.CLOSE
            )

            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=flat_fees,
            )

            trade_update = TradeUpdate(
                trade_id=fill_data["createdAt"],
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                trading_pair=order.trading_pair,
                fill_timestamp=fill_data["createdAt"],
                fill_price=Decimal(fill_data["price"]),
                fill_base_amount=Decimal(fill_data["size"]),
                fill_quote_amount=Decimal(fill_data["price"]) * Decimal(fill_data["size"]),
                fee=fee,
            )
        return trade_update

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:

        body_params = {
            "orderId": order.exchange_order_id,
            "limit": CONSTANTS.LAST_FILLS_MAX,
        }

        res = await self._api_get(
            path_url=CONSTANTS.PATH_FILLS,
            params=body_params,
            is_auth_required=True,
        )
        return res

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        if tracked_order.exchange_order_id is None:
            # Order placement failed previously
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED,
            )
        else:
            try:
                order_status_data = await self._request_order_status_data(tracked_order=tracked_order)
                order = order_status_data["order"]
                client_order_id = str(order["clientId"])

                order_update: OrderUpdate = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=CONSTANTS.ORDER_STATE[order["status"]],
                    client_order_id=client_order_id,
                    exchange_order_id=order["id"],
                )
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
        try:
            resp = await self._api_get(
                path_url=CONSTANTS.PATH_ORDERS + "/" + str(tracked_order.exchange_order_id),
                is_auth_required=True,
                limit_id=CONSTANTS.PATH_ORDERS,
            )
        except IOError as e:
            if any(error in str(e) for error in [CONSTANTS.ERR_MSG_NO_ORDER_FOUND]):
                await self._order_tracker.process_order_not_found(tracked_order.client_order_id)
            raise
        return resp

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> DydxPerpetualAPIOrderBookDataSource:
        return DydxPerpetualAPIOrderBookDataSource(
            self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return DydxPerpetualUserStreamDataSource(dydx_auth=self._auth, api_factory=self._web_assistants_factory)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        markets = exchange_info["markets"]

        mapping = bidict()
        for key, val in markets.items():
            if val["status"] == "ONLINE":
                exchange_symbol = val["market"]
                base = val["baseAsset"]
                quote = val["quoteAsset"]
                trading_pair = combine_to_hb_trading_pair(base, quote)
                if trading_pair in mapping.inverse:
                    self._resolve_trading_pair_symbols_duplicate(mapping, exchange_symbol, base, quote)
                else:
                    mapping[exchange_symbol] = trading_pair

        self._set_trading_pair_symbol_map(mapping)

    def _resolve_trading_pair_symbols_duplicate(self, mapping: bidict, new_exchange_symbol: str, base: str, quote: str):
        """Resolves name conflicts provoked by futures contracts.
        If the expected BASEQUOTE combination matches one of the exchange symbols, it is the one taken, otherwise,
        the trading pair is removed from the map and an error is logged.
        """
        expected_exchange_symbol = f"{base}{quote}"
        trading_pair = combine_to_hb_trading_pair(base, quote)
        current_exchange_symbol = mapping.inverse[trading_pair]
        if current_exchange_symbol == expected_exchange_symbol:
            pass
        elif new_exchange_symbol == expected_exchange_symbol:
            mapping.pop(current_exchange_symbol)
            mapping[new_exchange_symbol] = trading_pair
        else:
            self.logger().error(
                f"Could not resolve the exchange symbols {new_exchange_symbol} and {current_exchange_symbol}"
            )
            mapping.pop(current_exchange_symbol)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        params = {"market": exchange_symbol}

        response: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.PATH_MARKETS, params=params, is_auth_required=False
        )

        price = float(response["markets"][exchange_symbol]["indexPrice"])
        return price

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    async def _update_positions(self):
        account = await self._get_account()
        await self._process_open_positions(account["openPositions"])

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        """
        :return: A tuple of boolean (true if success) and error message if the exchange returns one on failure.
        """
        if mode != PositionMode.ONEWAY:
            self.trigger_event(
                AccountEvent.PositionModeChangeFailed,
                PositionModeChangeEvent(
                    self.current_timestamp, trading_pair, mode, "dYdX only supports the ONEWAY position mode."
                ),
            )
            self.logger().debug(
                f"dYdX encountered a problem switching position mode to "
                f"{mode} for {trading_pair}"
                f" (dYdX only supports the ONEWAY position mode)"
            )
        else:
            self._position_mode = PositionMode.ONEWAY
            super().set_position_mode(PositionMode.ONEWAY)
            self.trigger_event(
                AccountEvent.PositionModeChangeSucceeded,
                PositionModeChangeEvent(self.current_timestamp, trading_pair, mode),
            )
            self.logger().debug(f"dYdX switching position mode to " f"{mode} for {trading_pair} succeeded.")

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        success = True
        msg = ""

        response: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.PATH_MARKETS,
            is_auth_required=False,
        )

        if "markets" not in response:
            msg = "Failed to obtain markets information."
            success = False

        if success:
            markets_info = response["markets"]

            self._margin_fractions[trading_pair] = {
                "initial": Decimal(markets_info[trading_pair]["initialMarginFraction"]),
                "maintenance": Decimal(markets_info[trading_pair]["maintenanceMarginFraction"]),
            }

            max_leverage = int(Decimal("1") / self._margin_fractions[trading_pair]["initial"])
            if leverage > max_leverage:
                self._perpetual_trading.set_leverage(trading_pair=trading_pair, leverage=max_leverage)
                self.logger().warning(f"Leverage has been reduced to {max_leverage}")
            else:
                self._perpetual_trading.set_leverage(trading_pair=trading_pair, leverage=leverage)
        return success, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        """
        Returns a tuple of the latest funding payment timestamp, funding rate, and payment amount.
        If no payment exists, return (0, -1, -1)
        """
        market = await self.exchange_symbol_associated_to_pair(trading_pair)

        body_params = {
            "market": market,
            "limit": CONSTANTS.LAST_FEE_PAYMENTS_MAX,
            "effectiveBeforeOrAt": generate_now_iso(),
        }

        response: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.PATH_FUNDING,
            params=body_params,
            is_auth_required=True,
        )

        funding_payments = await self._process_funding_payments(response["fundingPayments"])

        timestamp = funding_payments[trading_pair]["timestamp"]
        funding_rate = funding_payments[trading_pair]["funding_rate"]
        payment = funding_payments[trading_pair]["payment"]

        return timestamp, funding_rate, payment

    async def _get_account(self):
        account_id = self._auth.get_account_id()
        response: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.PATH_ACCOUNTS + "/" + str(account_id),
            limit_id=CONSTANTS.PATH_ACCOUNTS,
            is_auth_required=True,
        )

        if "account" not in response:
            raise IOError(f"Unable to get account info for account id {account_id}")

        return response["account"]
