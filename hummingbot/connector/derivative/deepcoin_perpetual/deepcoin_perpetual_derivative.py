import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

import bidict as bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.deepcoin_perpetual import (
    deepcoin_perpetual_constants as CONSTANTS,
    deepcoin_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_auth import DeepcoinPerpetualAuth
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DeepcoinPerpetualDerivative(PerpetualDerivativePyBase):
    """
    DeepcoinPerpetualDerivative connects with Deepcoin Perpetual exchange and provides order book pricing,
    user account tracking and trading functionality for perpetual contracts.
    """

    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            deepcoin_perpetual_api_key: str = None,
            deepcoin_perpetual_api_secret: str = None,
            deepcoin_perpetual_passphrase: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.deepcoin_perpetual_api_key = deepcoin_perpetual_api_key
        self.deepcoin_perpetual_secret_key = deepcoin_perpetual_api_secret
        self.deepcoin_perpetual_passphrase = deepcoin_perpetual_passphrase
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> DeepcoinPerpetualAuth:
        return DeepcoinPerpetualAuth(
            self.deepcoin_perpetual_api_key,
            self.deepcoin_perpetual_secret_key,
            self.deepcoin_perpetual_passphrase,
            self._time_synchronizer
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self.authenticator,
        )

    def _validate_exchange_response(self, response: Dict[str, Any], before_text: str = ""):
        """
        Validates exchange response and raises appropriate errors
        """
        if "code" in response and response["code"] != 0:
            error_code = response.get("code", "Unknown")
            error_msg = response.get("message", "Unknown error")
            raise IOError(f"{before_text}Error {error_code}: {error_msg}")

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        # TODO: Implement order book data source
        return None

    def _create_user_stream_tracker_data_source(self) -> UserStreamTrackerDataSource:
        # TODO: Implement user stream data source
        return None

    async def _update_balances(self):
        """
        Updates the account balances
        """
        try:
            account_info = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_INFO_URL,
                is_auth_required=True
            )
            self._validate_exchange_response(account_info, "Error fetching account balance: ")

            self._account_balances.clear()
            self._account_available_balances.clear()

            if "data" in account_info:
                for balance_info in account_info["data"]:
                    asset = balance_info.get("currency", "")
                    total_balance = Decimal(balance_info.get("balance", "0"))
                    available_balance = Decimal(balance_info.get("available", "0"))

                    self._account_balances[asset] = total_balance
                    self._account_available_balances[asset] = available_balance

        except Exception as e:
            self.logger().error(f"Error updating balances: {e}")

    async def _update_positions(self):
        """
        Updates the account positions
        """
        try:
            positions_info = await self._api_get(
                path_url=CONSTANTS.POSITION_INFORMATION_URL,
                is_auth_required=True
            )

            self._account_positions.clear()

            if "data" in positions_info:
                for position_data in positions_info["data"]:
                    try:
                        from hummingbot.connector.derivative.deepcoin_perpetual import deepcoin_perpetual_utils as utils
                        parsed_position = utils.parse_position_data(position_data)

                        trading_pair = parsed_position["trading_pair"]
                        position_side = parsed_position["position_side"]
                        amount = parsed_position["amount"]

                        if amount > 0:  # Only track non-zero positions
                            position_key = f"{trading_pair}_{position_side.value}"
                            self._account_positions[position_key] = Position(
                                trading_pair=trading_pair,
                                position_side=position_side,
                                amount=amount,
                                entry_price=parsed_position["entry_price"],
                                leverage=parsed_position["leverage"]
                            )
                    except Exception as e:
                        self.logger().error(f"Error parsing position: {e}")
                        continue

        except Exception as e:
            self.logger().error(f"Error updating positions: {e}")

    async def _update_trading_rules(self):
        """
        Updates the trading rules
        """
        try:
            exchange_info = await self._api_get(
                path_url=CONSTANTS.EXCHANGE_INFO_URL
            )

            trading_rules = []
            if "data" in exchange_info:
                for symbol_info in exchange_info["data"]:
                    try:
                        from hummingbot.connector.derivative.deepcoin_perpetual import deepcoin_perpetual_utils as utils
                        trading_pair = utils.get_trading_pair_from_exchange_info(symbol_info)
                        if trading_pair:
                            trading_rules.append(TradingRule(
                                trading_pair=trading_pair,
                                min_order_size=Decimal(symbol_info.get("minOrderSize", "0.001")),
                                max_order_size=Decimal(symbol_info.get("maxOrderSize", "1000000")),
                                min_price_increment=Decimal(symbol_info.get("tickSize", "0.01")),
                                min_base_amount_increment=Decimal(symbol_info.get("stepSize", "0.001")),
                                min_notional_size=Decimal(symbol_info.get("minNotional", "5.0")),
                                buy_order_fee=Decimal(symbol_info.get("makerFeeRate", "0.001")),
                                sell_order_fee=Decimal(symbol_info.get("takerFeeRate", "0.001")),
                            ))
                    except Exception as e:
                        self.logger().error(f"Error parsing trading rule: {e}")
                        continue

            self._trading_rules.clear()
            for trading_rule in trading_rules:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

        except Exception as e:
            self.logger().error(f"Error updating trading rules: {e}")

    async def _update_order_status(self):
        """
        Updates the status of all in-flight orders
        """
        try:
            tracked_orders = list(self._in_flight_orders.values())
            if not tracked_orders:
                return

            for tracked_order in tracked_orders:
                try:
                    order_info = await self._api_get(
                        path_url=f"{CONSTANTS.ORDER_URL}?orderId={tracked_order.exchange_order_id}",
                        is_auth_required=True
                    )

                    if "data" in order_info:
                        order_data = order_info["data"]
                        from hummingbot.connector.derivative.deepcoin_perpetual import deepcoin_perpetual_utils as utils
                        new_status = utils.parse_order_status(order_data)

                        if new_status != tracked_order.current_state:
                            tracked_order.current_state = new_status

                            if new_status == "filled":
                                tracked_order.is_done = True
                                tracked_order.is_cancelled = False
                            elif new_status == "canceled":
                                tracked_order.is_done = True
                                tracked_order.is_cancelled = True

                except Exception as e:
                    self.logger().error(f"Error updating order status: {e}")

        except Exception as e:
            self.logger().error(f"Error updating order status: {e}")

    async def _place_order(self, order_id: str, trading_pair: str, amount: Decimal, order_type: OrderType,
                           trade_type: TradeType, price: Decimal = s_decimal_NaN,
                           position_action: PositionAction = PositionAction.OPEN) -> Optional[str]:
        """
        Places an order
        """
        try:
            from hummingbot.connector.derivative.deepcoin_perpetual import deepcoin_perpetual_utils as utils

            order_data = {
                "symbol": utils.convert_to_exchange_trading_pair(trading_pair),
                "side": utils.convert_to_exchange_side(trade_type),
                "type": utils.convert_to_exchange_order_type(order_type),
                "quantity": str(amount),
                "clientOrderId": order_id,
                "positionAction": position_action.value.lower(),
            }

            if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]:
                order_data["price"] = str(price)
                order_data["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC

            response = await self._api_post(
                path_url=CONSTANTS.ORDER_URL,
                data=order_data,
                is_auth_required=True
            )

            if "data" in response:
                return response["data"].get("orderId")
            else:
                self.logger().error(f"Error placing order: {response}")
                return None

        except Exception as e:
            self.logger().error(f"Error placing order: {e}")
            return None

    async def _cancel_order(self, order_id: str) -> bool:
        """
        Cancels an order
        """
        try:
            response = await self._api_delete(
                path_url=f"{CONSTANTS.ORDER_URL}?orderId={order_id}",
                is_auth_required=True
            )

            return "data" in response and response["data"].get("success", False)

        except Exception as e:
            self.logger().error(f"Error canceling order: {e}")
            return False

    async def set_leverage(self, trading_pair: str, leverage: int) -> bool:
        """
        Sets leverage for a trading pair
        """
        try:
            from hummingbot.connector.derivative.deepcoin_perpetual import deepcoin_perpetual_utils as utils

            leverage_data = {
                "symbol": utils.convert_to_exchange_trading_pair(trading_pair),
                "leverage": leverage
            }

            response = await self._api_post(
                path_url=CONSTANTS.SET_LEVERAGE_URL,
                data=leverage_data,
                is_auth_required=True
            )

            return "data" in response and response["data"].get("success", False)

        except Exception as e:
            self.logger().error(f"Error setting leverage: {e}")
            return False

    async def set_position_mode(self, position_mode: PositionMode) -> bool:
        """
        Sets position mode (one-way or hedge)
        """
        try:

            position_mode_data = {
                "dualSidePosition": position_mode == PositionMode.HEDGE
            }

            response = await self._api_post(
                path_url=CONSTANTS.CHANGE_POSITION_MODE_URL,
                data=position_mode_data,
                is_auth_required=True
            )

            if "data" in response and response["data"].get("success", False):
                self._position_mode = position_mode
                return True
            return False

        except Exception as e:
            self.logger().error(f"Error setting position mode: {e}")
            return False

    def _create_in_flight_order(self, client_order_id: str, exchange_order_id: str, trading_pair: str,
                                order_type: OrderType, trade_type: TradeType, price: Decimal, amount: Decimal,
                                position_action: PositionAction = PositionAction.OPEN) -> InFlightOrder:
        """
        Creates an in-flight order
        """
        return InFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            creation_timestamp=self.current_timestamp,
        )

    def _get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType,
                 order_side: TradeType, amount: Decimal, price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        """
        Calculates the trade fee
        """
        trading_pair = f"{base_currency}{quote_currency}"
        if trading_pair in self._trading_rules:
            trading_rule = self._trading_rules[trading_pair]
            if order_side == TradeType.BUY:
                fee_rate = trading_rule.buy_order_fee
            else:
                fee_rate = trading_rule.sell_order_fee
        else:
            fee_rate = Decimal("0.001")

        return TradeFeeBase.new_spot_fee(
            fee_schema=TradeFeeBase.new_spot_fee_schema(),
            maker_percent=fee_rate,
            taker_percent=fee_rate
        )

    async def _update_trading_fees(self):
        """
        Updates the trading fees
        """
        # Trading fees are updated as part of trading rules
        pass

    async def _user_stream_event_listener(self):
        """
        Listens to user stream events
        """
        # TODO: Implement user stream event listener
        pass

    async def _status_polling_loop(self):
        """
        Polls for order status updates
        """
        while True:
            try:
                await self._update_order_status()
                await asyncio.sleep(self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error in status polling loop: {e}")
                await asyncio.sleep(5.0)

    async def _trading_rules_polling_loop(self):
        """
        Polls for trading rules updates
        """
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(self.TRADING_RULES_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error in trading rules polling loop: {e}")
                await asyncio.sleep(60.0)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return None

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return True

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        return True

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        pass

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return ""

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return True

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return ""

    async def _trading_fees_polling_loop(self):
        """
        Polls for trading fees updates
        """
        while True:
            try:
                await self._update_trading_fees()
                await asyncio.sleep(self.TRADING_FEES_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error in trading fees polling loop: {e}")
                await asyncio.sleep(3600.0)

    async def _make_network_check_request(self):
        """
        Makes a network check request
        """
        await self._api_get(path_url=CONSTANTS.PING_URL)

    async def _format_trading_rules(self, exchange_info: Dict[str, Any]) -> List[TradingRule]:
        """
        Formats trading rules from exchange info
        """
        return None

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        """
        Initializes trading pair symbols from exchange info
        """
        pass

    def _make_trading_rules_request(self) -> Any:
        """
        Makes a trading rules request
        """
        return self._api_get(path_url=CONSTANTS.EXCHANGE_INFO_URL)

    def _make_trading_pairs_request(self) -> Any:
        """
        Makes a trading pairs request
        """
        return self._api_get(path_url=CONSTANTS.EXCHANGE_INFO_URL)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:

        return None

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        return

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        return None

    async def _request_order_status_data(self, tracked_order: InFlightOrder) -> Dict:
        return None

    async def _process_account_position_event(self, position_msg: Dict[str, Any]):
        """
        Updates position
        :param position_msg: The position event message payload
        """
        pass

    def _process_trade_event_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        :param trade_msg: The trade event message payload
        """

        pass

    def _parse_trade_update(self, trade_msg: Dict, tracked_order: InFlightOrder) -> TradeUpdate:
        return None

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order event message payload
        """
        pass

    def _resolve_trading_pair_symbols_duplicate(self, mapping: bidict, new_exchange_symbol: str, base: str, quote: str):
        """Resolves name conflicts provoked by futures contracts.

        If the expected BASEQUOTE combination matches one of the exchange symbols, it is the one taken, otherwise,
        the trading pair is removed from the map and an error is logged.
        """
        pass

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        return 123

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        msg = ""
        success = True

        return success, msg

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        data = {
            "category": "linear",
            "symbol": exchange_symbol,
            "buyLeverage": str(leverage),
            "sellLeverage": str(leverage)
        }
        resp: Dict[str, Any] = await self._api_post(
            path_url=CONSTANTS.SET_LEVERAGE_PATH_URL,
            data=data,
            is_auth_required=True,
            trading_pair=trading_pair,
        )

        success = False
        msg = ""
        if resp["retCode"] in [CONSTANTS.RET_CODE_OK, CONSTANTS.RET_CODE_LEVERAGE_NOT_MODIFIED]:
            success = True
        else:
            formatted_ret_code = self._format_ret_code_for_print(resp['retCode'])
            msg = f"{formatted_ret_code} - {resp['retMsg']}"

        return success, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        # exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

        params = {
            "type": "SETTLEMENT",
        }

        raw_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.FUNDING_INFO_URL,
            params=params,
            is_auth_required=True,
            trading_pair=trading_pair
        )
        data: Dict[str, Any] = raw_response["result"]["list"]

        if not data:
            # An empty funding fee/payment is retrieved.
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
        else:
            # TODO: Check how to handle - signs and filter by exchange_symbol
            last_data = data[0]
            funding_rate: Decimal = Decimal(str(last_data["funding"]))
            position_size: Decimal = Decimal(str(last_data["size"]))
            payment: Decimal = funding_rate * position_size
            timestamp: int = int(last_data["transactionTime"]) / 1e3

        return timestamp, funding_rate, payment

    @staticmethod
    def _format_ret_code_for_print(ret_code: Union[str, int]) -> str:
        return f"ret_code <{ret_code}>"

    async def _api_request(self,
                           path_url,
                           method: RESTMethod = RESTMethod.GET,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           return_err: bool = False,
                           limit_id: Optional[str] = None,
                           trading_pair: Optional[str] = None,
                           **kwargs) -> Dict[str, Any]:

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        if limit_id is None:
            limit_id = web_utils.get_rest_api_limit_id_for_endpoint(
                endpoint=path_url,
                trading_pair=trading_pair,
            )
        url = web_utils.get_rest_url_for_endpoint(endpoint=path_url, trading_pair=trading_pair, domain=self._domain)

        resp = await rest_assistant.execute_request(
            url=url,
            params=params,
            data=data,
            method=method,
            is_auth_required=is_auth_required,
            return_err=return_err,
            throttler_limit_id=limit_id if limit_id else path_url,
        )
        return resp
