import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

import hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_constants as CONSTANTS
from hummingbot.connector.constants import s_decimal_0, s_decimal_NaN
from hummingbot.connector.derivative.dydx_v4_perpetual import dydx_v4_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.dydx_v4_perpetual.data_sources.dydx_v4_data_source import DydxPerpetualV4Client
from hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_api_order_book_data_source import (
    DydxV4PerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_user_stream_data_source import (
    DydxV4PerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import AccountEvent, PositionModeChangeEvent
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class DydxV4PerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            dydx_v4_perpetual_secret_phrase: str,
            dydx_v4_perpetual_chain_address: str,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self._dydx_v4_perpetual_secret_phrase = dydx_v4_perpetual_secret_phrase
        self._dydx_v4_perpetual_chain_address = dydx_v4_perpetual_chain_address
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._domain = domain
        self._client_order_id_nonce_provider = NonceCreator.for_microseconds()

        self._tx_client: DydxPerpetualV4Client = self._create_tx_client()

        self._margin_fractions = {}
        self._position_id = None

        self._allocated_collateral = {}
        self.subaccount_id = 0

        super().__init__(client_config_map=client_config_map)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> AuthBase:
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

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
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_request_result_an_error_related_to_time_synchronizer(self, request_result: Dict[str, Any]) -> bool:
        if "errors" in request_result and "msg" in request_result["errors"]:
            if "Timestamp must be within" in request_result["errors"]["msg"]:
                return True
        return False

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path,
                                            params={})
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_pairs_request_path,
                                            params={})
        return exchange_info

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_cancel_order_not_found_in_the_exchange when replacing the
        # dummy implementation
        return False

    async def start_network(self):
        await super().start_network()
        await self._update_trading_rules()
        await self._tx_client.initialize_trading_account()

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        async with self._throttler.execute_task(limit_id=CONSTANTS.LIMIT_ID_ORDER_CANCEL):
            if not self._margin_fractions:
                await self._update_trading_rules()
            for i in range(3):
                resp = await self._tx_client.cancel_order(
                    client_id=int(tracked_order.client_order_id),
                    clob_pair_id=self._margin_fractions[tracked_order.trading_pair]["clob_pair_id"],
                    order_flags=CONSTANTS.ORDER_FLAGS_LONG_TERM,
                    good_til_block_time=int(time.time()) + CONSTANTS.ORDER_EXPIRATION
                )
                if CONSTANTS.ACCOUNT_SEQUENCE_MISMATCH_ERROR in resp['raw_log']:
                    self.logger().warning(
                        f"Failed to cancel order {tracked_order.client_order_id} (retry {i + 1}), {resp['raw_log']}")
                    await asyncio.sleep(1)
                    continue
                else:
                    break
        if resp["raw_log"] != "[]" and CONSTANTS.ERR_MSG_NO_ORDER_FOUND not in resp['raw_log']:
            raise ValueError(f"Error sending the order cancel transaction ({resp['raw_log']})")
        else:
            return True

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
        order_id = str(get_new_numeric_client_order_id(
            nonce_creator=self._client_order_id_nonce_provider,
            max_id_bit_count=CONSTANTS.MAX_ID_BIT_COUNT,
        ))
        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
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
        order_id = str(get_new_numeric_client_order_id(
            nonce_creator=self._client_order_id_nonce_provider,
            max_id_bit_count=CONSTANTS.MAX_ID_BIT_COUNT,
        ))
        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return order_id

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
    ):
        if not self._margin_fractions:
            await self._update_trading_rules()
        if order_type.is_limit_type():
            _order_type = "LIMIT"
            limit_id = CONSTANTS.LIMIT_LONG_TERM_ORDER_PLACE
        else:
            limit_id = CONSTANTS.MARKET_SHORT_TERM_ORDER_PLACE
            _order_type = "MARKET"
            if trade_type.name.lower() == 'buy':
                # The price needs to be relatively high before the transaction, whether the test will be cancelled
                price = Decimal("1.5") * self.get_price_for_volume(
                    trading_pair,
                    True,
                    amount
                ).result_price
            else:
                price = Decimal("0.75") * self.get_price_for_volume(
                    trading_pair,
                    False,
                    amount
                ).result_price
            price = self.quantize_order_price(trading_pair, price)
        side = "BUY" if trade_type == TradeType.BUY else "SELL"
        expiration = CONSTANTS.ORDER_EXPIRATION
        reduce_only = False

        post_only = order_type is OrderType.LIMIT_MAKER
        market = await self.exchange_symbol_associated_to_pair(trading_pair)
        try:
            async with self._throttler.execute_task(limit_id=limit_id):
                for i in range(3):
                    resp = await self._tx_client.place_order(
                        market=market,
                        type=_order_type,
                        side=side,
                        price=price,
                        size=amount,
                        client_id=int(order_id),
                        post_only=post_only,
                        reduce_only=reduce_only,
                        good_til_time_in_seconds=expiration,
                    )
                    if CONSTANTS.ACCOUNT_SEQUENCE_MISMATCH_ERROR in resp['raw_log']:
                        self.logger().warning(f"Failed to submit order {order_id} (retry {i + 1}), {resp['raw_log']}")
                        await asyncio.sleep(1)
                        continue
                    else:
                        break
            if resp["raw_log"] != "[]" or resp["txhash"] in [None, ""]:
                raise ValueError(f"Error sending the order creation transaction ({resp['raw_log']})")
        except asyncio.CancelledError:
            raise
        except Exception:
            raise
        # no exchange order id
        return None, self._time()

    async def _place_order_and_process_update(self, order: InFlightOrder, **kwargs) -> str:
        exchange_order_id, update_timestamp = await self._place_order(
            order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            amount=order.amount,
            trade_type=order.trade_type,
            order_type=order.order_type,
            price=order.price,
            **kwargs,
        )

        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=OrderState.OPEN,
        )
        self._order_tracker.process_order_update(order_update)

        return exchange_order_id

    def _on_order_failure(
            self,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            trade_type: TradeType,
            order_type: OrderType,
            price: Optional[Decimal],
            exception: Exception,
            **kwargs,
    ):
        self.logger().network(
            f"Error submitting {trade_type.name.lower()} {order_type.name.upper()} order to {self.name_cap} for "
            f"{amount} {trading_pair} {price}.",
            exc_info=exception,
            app_warning_msg=f"Failed to submit {trade_type.name.upper()} order to {self.name_cap}. Check API key and network connection."
        )
        self._update_order_after_failure(order_id=order_id, trading_pair=trading_pair)

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
        return fee

    async def _update_trading_fees(self):
        pass

    async def _user_stream_event_listener(self):

        async for event_message in self._iter_user_event_queue():
            try:
                event: Dict[str, Any] = event_message
                data: Dict[str, Any] = event["contents"]
                quote = "USD"
                if "subaccount" in data.keys() and len(data["subaccount"]) > 0:
                    self._account_balances[quote] = Decimal(data["subaccount"]["equity"])
                    self._account_available_balances[quote] = Decimal(data["subaccount"]["freeCollateral"])
                    if "openPerpetualPositions" in data["subaccount"]:
                        await self._process_open_positions(data["subaccount"]["openPerpetualPositions"])
                if "orders" in data.keys() and len(data["orders"]) > 0:
                    for order in data["orders"]:
                        client_order_id: str = order["clientId"]
                        exchange_order_id: str = order["id"]
                        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                        trading_pair = await self.trading_pair_associated_to_exchange_symbol(order["ticker"])
                        if tracked_order is not None:
                            state = CONSTANTS.ORDER_STATE[order["status"]]
                            new_order_update: OrderUpdate = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=self.current_timestamp,
                                new_state=state,
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=exchange_order_id,
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
                            # self._allocated_collateral_sum += initial_margin_requirement
                            self._account_available_balances[quote] -= initial_margin_requirement
                        if order["status"] in ["FILLED", "CANCELED"]:
                            if order["id"] in self._allocated_collateral:
                                # Only deduct orders that were previously in the OPEN state
                                # Some orders are filled instantly and reach only the PENDING state
                                # self._allocated_collateral_sum -= self._allocated_collateral[order["id"]]
                                self._account_available_balances[quote] += self._allocated_collateral[order["id"]]
                                del self._allocated_collateral[order["id"]]
                if "fills" in data.keys() and len(data["fills"]) > 0:
                    trade_updates = await self._process_ws_fills(data["fills"])
                    for trade_update in trade_updates:
                        self._order_tracker.process_trade_update(trade_update)

                if "perpetualPositions" in data.keys() and len(data["perpetualPositions"]) > 0:
                    # this is hit when a position is closed
                    positions = data["perpetualPositions"]
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

                # if "fundingPayments" in data:
                #     if event["type"] != CONSTANTS.WS_TYPE_SUBSCRIBED:  # Only subsequent funding payments
                #         funding_payments = await self._process_funding_payments(data["fundingPayments"])
                #         for trading_pair in funding_payments:
                #             timestamp = funding_payments[trading_pair]["timestamp"]
                #             funding_rate = funding_payments[trading_pair]["funding_rate"]
                #             payment = funding_payments[trading_pair]["payment"]
                #             self._emit_funding_payment_event(trading_pair, timestamp, funding_rate, payment, False)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []
        markets_info = exchange_info_dict["markets"]
        for market_name, market_info in markets_info.items():
            if web_utils.is_exchange_information_valid(market_info):
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=market_name)
                market = markets_info[market_name]
                try:
                    collateral_token = CONSTANTS.CURRENCY
                    trading_rules += [
                        TradingRule(
                            trading_pair=trading_pair,
                            min_price_increment=Decimal(market["tickSize"]),
                            min_base_amount_increment=Decimal(market["stepSize"]),
                            supports_limit_orders=True,
                            supports_market_orders=True,
                            buy_order_collateral_token=collateral_token,
                            sell_order_collateral_token=collateral_token,
                        )
                    ]
                    self._margin_fractions[trading_pair] = {
                        "initial": Decimal(market["initialMarginFraction"]),
                        "maintenance": Decimal(market["maintenanceMarginFraction"]),
                        "clob_pair_id": market["clobPairId"],
                        "atomicResolution": market["atomicResolution"],
                        "stepBaseQuantums": market["stepBaseQuantums"],
                        "quantumConversionExponent": market["quantumConversionExponent"],
                        "subticksPerTick": market["subticksPerTick"],
                    }
                except Exception:
                    self.logger().exception("Error updating trading rules")
        return trading_rules

    async def _update_balances(self):
        path = f"{CONSTANTS.PATH_SUBACCOUNT}/{self._dydx_v4_perpetual_chain_address}/subaccountNumber/{self.subaccount_id}"
        response: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=path, params={}, limit_id=CONSTANTS.PATH_SUBACCOUNT
        )
        quote = CONSTANTS.CURRENCY
        self._account_available_balances.clear()
        self._account_balances.clear()

        self._account_balances[quote] = Decimal(response["subaccount"]["equity"])
        self._account_available_balances[quote] = Decimal(response["subaccount"]["freeCollateral"])

    async def _process_ws_fills(self, fills_data: List) -> List[TradeUpdate]:
        trade_updates = []

        for fill_data in fills_data:
            exchange_order_id: str = fill_data["orderId"]
            all_orders = self._order_tracker.all_fillable_orders
            try:
                for k, v in all_orders.items():
                    await v.get_exchange_order_id()
            except Exception as e:
                self.logger().info(
                    f"Unable to locate order {exchange_order_id} on exchange. Pending update from blockchain {e}")
            _cli_tracked_orders = [o for o in all_orders.values() if exchange_order_id == o.exchange_order_id]
            if len(_cli_tracked_orders) == 0 or _cli_tracked_orders[0] is None:
                order_update: OrderUpdate = await self._request_order_status(tracked_order=None,
                                                                             exchange_order_id=exchange_order_id)
                # NOTE: Untracked order
                if order_update is None:
                    self.logger().debug(f"Received untracked order with exchange order id of {exchange_order_id}")
                    return trade_updates
                client_order_id = order_update.client_order_id
                tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
            else:
                tracked_order = _cli_tracked_orders[0]
            trade_update = self._process_order_fills(fill_data=fill_data, order=tracked_order)
            if trade_update is not None:
                trade_updates.append(trade_update)
        return trade_updates

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

            position_action = (PositionAction.OPEN
                               if (order.trade_type is TradeType.BUY and position_side == "BUY"
                                   or order.trade_type is TradeType.SELL and position_side == "SELL")
                               else PositionAction.CLOSE)

            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=flat_fees,
            )

            trade_update = TradeUpdate(
                trade_id=fill_data["id"],
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
            'address': self._dydx_v4_perpetual_chain_address,
            'subaccountNumber': self.subaccount_id,
            'marketType': 'PERPETUAL',
            'market': order.trading_pair,
            'limit': CONSTANTS.LAST_FILLS_MAX,
        }

        res = await self._api_get(
            path_url=CONSTANTS.PATH_FILLS,
            params=body_params,
        )
        return res

    async def _request_order_status(self, tracked_order: InFlightOrder, exchange_order_id=None) -> OrderUpdate:
        try:
            orders_rsp = await self._api_get(
                path_url=CONSTANTS.PATH_ORDERS,
                limit_id=CONSTANTS.PATH_ORDERS,
                params={
                    'address': self._dydx_v4_perpetual_chain_address,
                    'subaccountNumber': self.subaccount_id,
                    'goodTilBlockBeforeOrAt': CONSTANTS.TX_MAX_HEIGHT,
                    'limit': CONSTANTS.LAST_FILLS_MAX,
                }
            )
            if exchange_order_id:
                updated_order_data = next(
                    (order for order in orders_rsp if
                     order["id"] == exchange_order_id), None
                )
                if updated_order_data is None:
                    return None
                tracked_order = self._order_tracker.all_updatable_orders.get(str(updated_order_data["clientId"]))
            else:
                updated_order_data = next(
                    (order for order in orders_rsp if
                     int(order["clientId"]) == int(tracked_order.client_order_id)), None
                )

            if updated_order_data is None:
                # If the order is not found in the response, return an OrderUpdate with the same status as before
                return OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self._time_synchronizer.time(),
                    new_state=tracked_order.current_state,
                )
            client_order_id = str(updated_order_data["clientId"])

            order_update: OrderUpdate = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=CONSTANTS.ORDER_STATE[updated_order_data["status"]],
                client_order_id=client_order_id,
                exchange_order_id=updated_order_data["id"],
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

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
        )

    def _create_tx_client(self) -> DydxPerpetualV4Client:
        return DydxPerpetualV4Client(
            self._dydx_v4_perpetual_secret_phrase,
            self._dydx_v4_perpetual_chain_address,
            connector=self
        )

    def _create_order_book_data_source(self) -> DydxV4PerpetualAPIOrderBookDataSource:
        return DydxV4PerpetualAPIOrderBookDataSource(
            self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return DydxV4PerpetualUserStreamDataSource(api_factory=self._web_assistants_factory,
                                                   connector=self)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        markets = exchange_info["markets"]

        mapping = bidict()
        for key, val in markets.items():
            if web_utils.is_exchange_information_valid(val):
                exchange_symbol = val["ticker"]
                base = exchange_symbol.split("-")[0]
                quote = CONSTANTS.CURRENCY
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
        params = {}

        response: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.PATH_MARKETS, params=params, is_auth_required=False
        )
        price = float(response["markets"][exchange_symbol]["oraclePrice"])
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
        params = {}
        path = f"{CONSTANTS.PATH_SUBACCOUNT}/{self._dydx_v4_perpetual_chain_address}/subaccountNumber/{self.subaccount_id}"
        response: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=path, params=params, limit_id=CONSTANTS.PATH_SUBACCOUNT
        )

        # account = await self._get_account()
        await self._process_open_positions(response["subaccount"]["openPerpetualPositions"])

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        """
        :return: A tuple of boolean (true if success) and error message if the exchange returns one on failure.
        """
        if mode != PositionMode.ONEWAY:
            self.trigger_event(
                AccountEvent.PositionModeChangeFailed,
                PositionModeChangeEvent(
                    self.current_timestamp, trading_pair, mode, "dydx_v4 only supports the ONEWAY position mode."
                ),
            )
            self.logger().debug(
                f"dydx_v4 encountered a problem switching position mode to "
                f"{mode} for {trading_pair}"
                f" (dydx_v4 only supports the ONEWAY position mode)"
            )
        else:
            self._position_mode = PositionMode.ONEWAY
            super().set_position_mode(PositionMode.ONEWAY)
            self.trigger_event(
                AccountEvent.PositionModeChangeSucceeded,
                PositionModeChangeEvent(self.current_timestamp, trading_pair, mode),
            )
            self.logger().debug(f"dydx_v4 switching position mode to " f"{mode} for {trading_pair} succeeded.")

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
            markets_info = response["markets"][trading_pair]
            self._margin_fractions[trading_pair] = {
                "initial": Decimal(markets_info["initialMarginFraction"]),
                "maintenance": Decimal(markets_info["maintenanceMarginFraction"]),
                "clob_pair_id": markets_info["clobPairId"],
                "atomicResolution": markets_info["atomicResolution"],
                "stepBaseQuantums": markets_info["stepBaseQuantums"],
                "quantumConversionExponent": markets_info["quantumConversionExponent"],
                "subticksPerTick": markets_info["subticksPerTick"],
            }

            max_leverage = int(Decimal("1") / self._margin_fractions[trading_pair]["initial"])
            if leverage > max_leverage:
                self._perpetual_trading.set_leverage(trading_pair=trading_pair, leverage=max_leverage)
                self.logger().warning(f"Exceeded max leverage allowed."
                                      f" Leverage for {trading_pair} has been reduced to {max_leverage}")
            else:
                self._perpetual_trading.set_leverage(trading_pair=trading_pair, leverage=leverage)
                self.logger().info(f"Leverage for {trading_pair} successfully set to {leverage}.")
        return success, msg

    async def _execute_set_leverage(self, trading_pair: str, leverage: int):
        try:
            success, msg = await self._set_trading_pair_leverage(trading_pair, leverage)
            if not success:
                self.logger().network(f"Error setting leverage {leverage} for {trading_pair}: {msg}")
        except Exception:
            self.logger().network(f"Error setting leverage {leverage} for {trading_pair}")

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        pass

    async def _update_funding_payment(self, trading_pair: str, fire_event_on_new: bool) -> bool:
        return True
