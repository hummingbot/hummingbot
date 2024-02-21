import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from bidict import bidict

import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bitget_perpetual import (
    bitget_perpetual_utils,
    bitget_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_api_order_book_data_source import (
    BitgetPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_auth import BitgetPerpetualAuth
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_user_stream_data_source import (
    BitgetPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class BitgetPerpetualDerivative(PerpetualDerivativePyBase):

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        bitget_perpetual_api_key: str = None,
        bitget_perpetual_secret_key: str = None,
        bitget_perpetual_passphrase: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = "",
    ):

        self.bitget_perpetual_api_key = bitget_perpetual_api_key
        self.bitget_perpetual_secret_key = bitget_perpetual_secret_key
        self.bitget_perpetual_passphrase = bitget_perpetual_passphrase
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._last_trade_history_timestamp = None

        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> BitgetPerpetualAuth:
        return BitgetPerpetualAuth(
            api_key=self.bitget_perpetual_api_key,
            secret_key=self.bitget_perpetual_secret_key,
            passphrase=self.bitget_perpetual_passphrase,
            time_provider=self._time_synchronizer)

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        # No instruction about client_oid length in the doc
        return None

    @property
    def client_order_id_prefix(self) -> str:
        return ""

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.QUERY_SYMBOL_ENDPOINT

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.QUERY_SYMBOL_ENDPOINT

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.SERVER_TIME_PATH_URL

    @property
    def trading_pairs(self):
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
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules.get(trading_pair, None)
        if trading_rule is None:
            collateral_token = self._collateral_token_based_on_product_type(trading_pair=trading_pair)
        else:
            collateral_token = trading_rule.buy_order_collateral_token

        return collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return self.get_buy_collateral_token(trading_pair=trading_pair)

    def start(self, clock: Clock, timestamp: float):
        super().start(clock, timestamp)
        if self.is_trading_required:
            self.set_position_mode(PositionMode.HEDGE)

    async def check_network(self) -> NetworkStatus:
        """
        Checks connectivity with the exchange using the API

        We need to reimplement this for Bitget exchange because the endpoint that returns the server status and time
        by default responds with a 400 status that includes a valid content.
        """
        result = NetworkStatus.NOT_CONNECTED
        try:
            response = await self._api_get(path_url=self.check_network_request_path, return_err=True)
            if response.get("flag", False):
                result = NetworkStatus.CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            result = NetworkStatus.NOT_CONNECTED
        return result

    async def exchange_symbol_associated_to_pair_without_product_type(self, trading_pair: str) -> str:
        full_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        return self._symbol_and_product_type(full_symbol=full_symbol)[0]

    async def trading_pair_associated_to_exchange_instrument_id(self, instrument_id: str) -> str:
        symbol_without_product_type = instrument_id

        full_symbol = None
        for product_type in [CONSTANTS.USDT_PRODUCT_TYPE, CONSTANTS.USD_PRODUCT_TYPE, CONSTANTS.USDC_PRODUCT_TYPE]:
            candidate_symbol = (f"{symbol_without_product_type}"
                                f"{CONSTANTS.SYMBOL_AND_PRODUCT_TYPE_SEPARATOR}"
                                f"{product_type}")
            try:
                full_symbol = await self.trading_pair_associated_to_exchange_symbol(symbol=candidate_symbol)
            except KeyError:
                # If the trading pair was not found, the product type is not the correct one. Continue to keep trying
                continue
            else:
                break

        if full_symbol is None:
            raise ValueError(f"No trading pair associated to instrument ID {instrument_id}")

        return full_symbol

    async def product_type_for_trading_pair(self, trading_pair: str) -> str:
        full_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        return self._symbol_and_product_type(full_symbol=full_symbol)[-1]

    def _symbol_and_product_type(self, full_symbol: str) -> str:
        return full_symbol.split(CONSTANTS.SYMBOL_AND_PRODUCT_TYPE_SEPARATOR)

    def _collateral_token_based_on_product_type(self, trading_pair: str) -> str:
        base, quote = split_hb_trading_pair(trading_pair=trading_pair)

        if quote == "USD":
            collateral_token = base
        else:
            collateral_token = quote

        return collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        ts_error_target_str = "Request timestamp expired"
        is_time_synchronizer_related = (
            ts_error_target_str in error_description
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

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        data = {
            "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
            "marginCoin": self.get_buy_collateral_token(tracked_order.trading_pair),
            "orderId": tracked_order.exchange_order_id
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
        )
        response_code = cancel_result["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            if response_code == CONSTANTS.RET_CODE_ORDER_NOT_EXISTS:
                await self._order_tracker.process_order_not_found(order_id)
            formatted_ret_code = self._format_ret_code_for_print(response_code)
            raise IOError(f"{formatted_ret_code} - {cancel_result['msg']}")

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
        if position_action is PositionAction.OPEN:
            contract = "long" if trade_type == TradeType.BUY else "short"
        else:
            contract = "short" if trade_type == TradeType.BUY else "long"
        margin_coin = (self.get_buy_collateral_token(trading_pair)
                       if trade_type == TradeType.BUY
                       else self.get_sell_collateral_token(trading_pair))
        data = {
            "side": f"{position_action.name.lower()}_{contract}",
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "marginCoin": margin_coin,
            "size": str(amount),
            "orderType": "limit" if order_type.is_limit_type() else "market",
            "timeInForceValue": CONSTANTS.DEFAULT_TIME_IN_FORCE,
            "clientOid": order_id,
        }
        if order_type.is_limit_type():
            data["price"] = str(price)

        resp = await self._api_post(
            path_url=CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
        )

        if resp["code"] != CONSTANTS.RET_CODE_OK:
            formatted_ret_code = self._format_ret_code_for_print(resp["code"])
            raise IOError(f"Error submitting order {order_id}: {formatted_ret_code} - {resp['msg']}")

        return str(resp["data"]["orderId"]), self.current_timestamp

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
            fee_rate = fee_schema.maker_percent_fee_decimal if is_maker else fee_schema.taker_percent_fee_decimal
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
        product_types = CONSTANTS.ALL_PRODUCT_TYPES

        for product_type in product_types:
            exchange_info = await self._api_get(
                path_url=self.trading_rules_request_path,
                params={"productType": product_type.lower()})
            symbol_data.extend(exchange_info["data"])

        for symbol_details in symbol_data:
            if bitget_perpetual_utils.is_exchange_information_valid(exchange_info=symbol_details):
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=symbol_details["symbol"])
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
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BitgetPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances
        """
        balances = {}
        trading_pairs_product_types = set([await self.product_type_for_trading_pair(trading_pair=trading_pair)
                                           for trading_pair in self.trading_pairs])
        product_types = trading_pairs_product_types or CONSTANTS.ALL_PRODUCT_TYPES

        for product_type in product_types:
            body_params = {"productType": product_type.lower()}
            wallet_balance: Dict[str, Union[str, List[Dict[str, Any]]]] = await self._api_get(
                path_url=CONSTANTS.GET_WALLET_BALANCE_PATH_URL,
                params=body_params,
                is_auth_required=True,
            )

            if wallet_balance["code"] != CONSTANTS.RET_CODE_OK:
                formatted_ret_code = self._format_ret_code_for_print(wallet_balance["code"])
                raise IOError(f"{formatted_ret_code} - {wallet_balance['msg']}")

            balances[product_type] = wallet_balance["data"]

        self._account_available_balances.clear()
        self._account_balances.clear()
        for product_type_balances in balances.values():
            for balance_data in product_type_balances:
                asset_name = balance_data["marginCoin"]
                current_available = self._account_available_balances.get(asset_name, Decimal(0))
                queried_available = (Decimal(str(balance_data["fixedMaxAvailable"]))
                                     if self.position_mode is PositionMode.ONEWAY
                                     else Decimal(str(balance_data["crossMaxAvailable"])))
                self._account_available_balances[asset_name] = current_available + queried_available
                current_total = self._account_balances.get(asset_name, Decimal(0))
                queried_total = Decimal(str(balance_data["equity"]))
                self._account_balances[asset_name] = current_total + queried_total

    async def _update_positions(self):
        """
        Retrieves all positions using the REST API.
        """
        position_data = []
        product_types = CONSTANTS.ALL_PRODUCT_TYPES

        for product_type in product_types:
            body_params = {"productType": product_type.lower()}
            raw_response: Dict[str, Any] = await self._api_get(
                path_url=CONSTANTS.GET_POSITIONS_PATH_URL,
                params=body_params,
                is_auth_required=True,
            )
            position_data.extend(raw_response["data"])

        # Initial parsing of responses.
        for position in position_data:
            data = position
            ex_trading_pair = data.get("symbol")
            hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(ex_trading_pair)
            position_side = PositionSide.LONG if data["holdSide"] == "long" else PositionSide.SHORT
            unrealized_pnl = Decimal(str(data["unrealizedPL"]))
            entry_price = Decimal(str(data["averageOpenPrice"]))
            amount = Decimal(str(data["total"]))
            leverage = Decimal(str(data["leverage"]))
            pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
            if amount != s_decimal_0:
                position = Position(
                    trading_pair=hb_trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount * (Decimal("-1.0") if position_side == PositionSide.SHORT else Decimal("1.0")),
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
                fills_data = all_fills_response.get("data", [])

                for fill_data in fills_data:
                    trade_update = self._parse_trade_update(trade_msg=fill_data, tracked_order=order)
                    trade_updates.append(trade_update)
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                    raise

        return trade_updates

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(order.trading_pair)
        body_params = {
            "orderId": order.exchange_order_id,
            "symbol": exchange_symbol,
        }
        res = await self._api_get(
            path_url=CONSTANTS.USER_TRADE_RECORDS_PATH_URL,
            params=body_params,
            is_auth_required=True,
        )
        return res

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        try:
            order_status_data = await self._request_order_status_data(tracked_order=tracked_order)
            order_msg = order_status_data["data"]
            client_order_id = str(order_msg["clientOid"])

            order_update: OrderUpdate = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=CONSTANTS.ORDER_STATE[order_msg["state"]],
                client_order_id=client_order_id,
                exchange_order_id=order_msg["orderId"],
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
        exchange_symbol = await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)
        query_params = {
            "symbol": exchange_symbol,
            "clientOid": tracked_order.client_order_id
        }
        if tracked_order.exchange_order_id is not None:
            query_params["orderId"] = tracked_order.exchange_order_id

        resp = await self._api_get(
            path_url=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL,
            params=query_params,
            is_auth_required=True,
        )

        return resp

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        params = {"symbol": exchange_symbol}

        resp_json = await self._api_get(
            path_url=CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT,
            params=params,
        )

        price = float(resp_json["data"]["last"])
        return price

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if len(self.account_positions) > 0:
            return False, "Cannot change position because active positions exist"

        msg = ""
        success = True

        try:
            api_mode = CONSTANTS.POSITION_MODE_MAP[mode]

            exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
            data = {
                "symbol": exchange_symbol,
                "marginMode": api_mode,
                "marginCoin": self.get_buy_collateral_token(trading_pair)
            }

            response = await self._api_post(
                path_url=CONSTANTS.SET_POSITION_MODE_URL,
                data=data,
                is_auth_required=True,
            )

            response_code = response["code"]

            if response_code != CONSTANTS.RET_CODE_OK:
                formatted_ret_code = self._format_ret_code_for_print(response_code)
                msg = f"{formatted_ret_code} - {response['msg']}"
                success = False
        except Exception as exception:
            success = False
            msg = f"There was an error changing the position mode ({exception})"

        return success, msg

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        if len(self.account_positions) > 0:
            return False, "cannot change leverage because active positions exist"

        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        success = True
        msg = ""

        try:
            data = {
                "symbol": exchange_symbol,
                "marginCoin": self.get_buy_collateral_token(trading_pair),
                "leverage": leverage
            }

            resp: Dict[str, Any] = await self._api_post(
                path_url=CONSTANTS.SET_LEVERAGE_PATH_URL,
                data=data,
                is_auth_required=True,
            )

            if resp["code"] != CONSTANTS.RET_CODE_OK:
                formatted_ret_code = self._format_ret_code_for_print(resp["code"])
                success = False
                msg = f"{formatted_ret_code} - {resp['msg']}"
        except Exception as exception:
            success = False
            msg = f"There was an error setting the leverage for {trading_pair} ({exception})"

        return success, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        now = self._time_synchronizer.time()
        start_time = self._last_funding_fee_payment_ts.get(trading_pair, now - (2 * self.funding_fee_poll_interval))
        params = {
            "symbol": exchange_symbol,
            "marginCoin": self.get_buy_collateral_token(trading_pair),
            "startTime": str(int(start_time * 1e3)),
            "endTime": str(int(now * 1e3)),
        }
        raw_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.GET_FUNDING_FEES_PATH_URL,
            params=params,
            is_auth_required=True,
        )
        data: Dict[str, Any] = raw_response["data"]["result"]
        settlement_fee: Optional[Dict[str, Any]] = next(
            (fee_payment for fee_payment in data if "settle_fee" in fee_payment.get("business", "")),
            None)

        if settlement_fee is None:
            # An empty funding fee/payment is retrieved.
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
        else:
            funding_info = self._perpetual_trading._funding_info.get(trading_pair)
            payment: Decimal = Decimal(str(settlement_fee["amount"]))
            funding_rate: Decimal = funding_info.rate if funding_info is not None else Decimal(0)
            timestamp: float = int(settlement_fee["cTime"]) * 1e-3
        return timestamp, funding_rate, payment

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                endpoint = event_message["arg"]["channel"]
                payload = event_message["data"]

                if endpoint == CONSTANTS.WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME:
                    await self._process_account_position_event(payload)
                elif endpoint == CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME:
                    for order_msg in payload:
                        self._process_trade_event_message(order_msg)
                        self._process_order_event_message(order_msg)
                        self._process_balance_update_from_order_event(order_msg)
                elif endpoint == CONSTANTS.WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME:
                    for wallet_msg in payload:
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

        for position_msg in position_entries:
            ex_trading_pair = position_msg["instId"]
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=ex_trading_pair)
            position_side = PositionSide.LONG if position_msg["holdSide"] == "long" else PositionSide.SHORT
            entry_price = Decimal(str(position_msg["averageOpenPrice"]))
            amount = Decimal(str(position_msg["total"]))
            leverage = Decimal(str(position_msg["leverage"]))
            unrealized_pnl = Decimal(str(position_msg["upl"]))
            pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
            all_position_keys.append(pos_key)
            if amount != s_decimal_0:
                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount * (Decimal("-1.0") if position_side == PositionSide.SHORT else Decimal("1.0")),
                    leverage=leverage,
                )
                self._perpetual_trading.set_position(pos_key, position)
            else:
                self._perpetual_trading.remove_position(pos_key)

        # Bitget sends position events as snapshots. If a position is closed it is just not included in the snapshot
        position_keys = list(self.account_positions.keys())
        positions_to_remove = (position_key for position_key in position_keys
                               if position_key not in all_position_keys)
        for position_key in positions_to_remove:
            self._perpetual_trading.remove_position(position_key)

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.

        :param order_msg: The order event message payload
        """
        order_status = CONSTANTS.ORDER_STATE[order_msg["status"]]
        client_order_id = str(order_msg["clOrdId"])
        updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if updatable_order is not None:
            new_order_update: OrderUpdate = OrderUpdate(
                trading_pair=updatable_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=order_status,
                client_order_id=client_order_id,
                exchange_order_id=order_msg["ordId"],
            )
            self._order_tracker.process_order_update(new_order_update)

    def _process_balance_update_from_order_event(self, order_msg: Dict[str, Any]):
        order_status = CONSTANTS.ORDER_STATE[order_msg["status"]]
        position_side = PositionSide[order_msg["posSide"].upper()]
        trade_type = TradeType[order_msg["side"].upper()]
        collateral_token = order_msg["tgtCcy"]
        states_to_consider = [OrderState.OPEN, OrderState.CANCELED]

        is_open_long = position_side == PositionSide.LONG and trade_type == TradeType.BUY
        is_open_short = position_side == PositionSide.SHORT and trade_type == TradeType.SELL

        order_amount = Decimal(order_msg["sz"])
        order_price = Decimal(order_msg["px"])
        margin_amount = (order_amount * order_price) / Decimal(order_msg["lever"])

        if (collateral_token in self._account_available_balances
                and order_status in states_to_consider
                and (is_open_long or is_open_short)):

            multiplier = Decimal(-1) if order_status == OrderState.OPEN else Decimal(1)
            self._account_available_balances[collateral_token] += margin_amount * multiplier

    def _process_trade_event_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.

        :param trade_msg: The trade event message payload
        """

        client_order_id = str(trade_msg["clOrdId"])
        fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)

        if fillable_order is not None and "tradeId" in trade_msg:
            trade_update = self._parse_websocket_trade_update(trade_msg=trade_msg, tracked_order=fillable_order)
            if trade_update:
                self._order_tracker.process_trade_update(trade_update)

    def _parse_websocket_trade_update(self, trade_msg: Dict, tracked_order: InFlightOrder) -> TradeUpdate:
        trade_id: str = trade_msg["tradeId"]

        if trade_id is not None:
            trade_id = str(trade_id)
            fee_asset = trade_msg["fillFeeCcy"]
            fee_amount = Decimal(trade_msg["fillFee"])
            position_side = trade_msg["side"]
            position_action = (PositionAction.OPEN
                               if (tracked_order.trade_type is TradeType.BUY and position_side == "buy"
                                   or tracked_order.trade_type is TradeType.SELL and position_side == "sell")
                               else PositionAction.CLOSE)

            flat_fees = [] if fee_amount == Decimal("0") else [TokenAmount(amount=fee_amount, token=fee_asset)]

            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=flat_fees,
            )

            exec_price = Decimal(trade_msg["fillPx"]) if "fillPx" in trade_msg else Decimal(trade_msg["px"])
            exec_time = int(trade_msg["fillTime"]) * 1e-3

            trade_update: TradeUpdate = TradeUpdate(
                trade_id=trade_id,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(trade_msg["ordId"]),
                trading_pair=tracked_order.trading_pair,
                fill_timestamp=exec_time,
                fill_price=exec_price,
                fill_base_amount=Decimal(trade_msg["fillSz"]),
                fill_quote_amount=exec_price * Decimal(trade_msg["fillSz"]),
                fee=fee,
            )

            return trade_update

    def _parse_trade_update(self, trade_msg: Dict, tracked_order: InFlightOrder) -> TradeUpdate:
        trade_id: str = str(trade_msg["tradeId"])

        fee_asset = tracked_order.quote_asset
        fee_amount = Decimal(trade_msg["fee"])
        position_action = (PositionAction.OPEN if "open" == trade_msg["side"] else PositionAction.CLOSE)

        flat_fees = [] if fee_amount == Decimal("0") else [TokenAmount(amount=fee_amount, token=fee_asset)]

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=flat_fees,
        )

        exec_price = Decimal(trade_msg["price"])
        exec_time = int(trade_msg["cTime"]) * 1e-3

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=trade_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(trade_msg["orderId"]),
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=exec_time,
            fill_price=exec_price,
            fill_base_amount=Decimal(trade_msg["sizeQty"]),
            fill_quote_amount=exec_price * Decimal(trade_msg["sizeQty"]),
            fee=fee,
        )

        return trade_update

    def _process_wallet_event_message(self, wallet_msg: Dict[str, Any]):
        """
        Updates account balances.
        :param wallet_msg: The account balance update message payload
        """
        symbol = wallet_msg.get("marginCoin", None)
        if symbol is not None:
            available = Decimal(str(wallet_msg["maxOpenPosAvailable"]))
            total = Decimal(str(wallet_msg["equity"]))
            self._account_balances[symbol] = total
            self._account_available_balances[symbol] = available

    @staticmethod
    def _format_ret_code_for_print(ret_code: Union[str, int]) -> str:
        return f"ret_code <{ret_code}>"

    async def _market_data_for_all_product_types(self) -> List[Dict[str, Any]]:
        all_exchange_info = []
        product_types = [CONSTANTS.USDT_PRODUCT_TYPE, CONSTANTS.USD_PRODUCT_TYPE]

        for product_type in product_types:
            exchange_info = await self._api_get(
                path_url=self.trading_pairs_request_path,
                params={"productType": product_type.lower()})
            all_exchange_info.extend(exchange_info["data"])

        # For USDC collateralized products we need to change the quote asset from USD to USDC, to avoid colitions
        # in the trading pairs with markets for product type DMCBL
        exchange_info = await self._api_get(
            path_url=self.trading_pairs_request_path,
            params={"productType": CONSTANTS.USDC_PRODUCT_TYPE.lower()})
        markets = exchange_info["data"]
        for market_info in markets:
            market_info["quoteCoin"] = market_info["supportMarginCoins"][0]
        all_exchange_info.extend(markets)

        return all_exchange_info

    async def _initialize_trading_pair_symbol_map(self):
        try:
            all_exchange_info = await self._market_data_for_all_product_types()
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=all_exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[Dict[str, Any]]):
        mapping = bidict()
        for symbol_data in exchange_info:
            if bitget_perpetual_utils.is_exchange_information_valid(exchange_info=symbol_data):
                try:
                    exchange_symbol = symbol_data["symbol"]
                    base = symbol_data["baseCoin"]
                    quote = symbol_data["quoteCoin"]
                    trading_pair = combine_to_hb_trading_pair(base, quote)
                    mapping[exchange_symbol] = trading_pair
                except Exception as exception:
                    self.logger().error(f"There was an error parsing a trading pair information ({exception})")
        self._set_trading_pair_symbol_map(mapping)

    async def _update_trading_rules(self):
        markets_data = await self._market_data_for_all_product_types()
        trading_rules_list = await self._format_trading_rules(markets_data)

        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=markets_data)

    async def _format_trading_rules(self, instruments_info: List[Dict[str, Any]]) -> List[TradingRule]:
        """
        Converts JSON API response into a local dictionary of trading rules.

        :param instrument_info_dict: The JSON API response.

        :returns: A dictionary of trading pair to its respective TradingRule.
        """
        trading_rules = {}
        for instrument in instruments_info:
            if bitget_perpetual_utils.is_exchange_information_valid(exchange_info=instrument):
                try:
                    exchange_symbol = instrument["symbol"]
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=exchange_symbol)
                    collateral_token = instrument["supportMarginCoins"][0]
                    trading_rules[trading_pair] = TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(str(instrument["minTradeNum"])),
                        min_price_increment=(Decimal(str(instrument["priceEndStep"]))
                                             * Decimal(f"1e-{instrument['pricePlace']}")),
                        min_base_amount_increment=Decimal(str(instrument["sizeMultiplier"])),
                        buy_order_collateral_token=collateral_token,
                        sell_order_collateral_token=collateral_token,
                    )
                except Exception:
                    self.logger().exception(f"Error parsing the trading pair rule: {instrument}. Skipping.")
        return list(trading_rules.values())
