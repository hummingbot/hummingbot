import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from bidict import bidict

import hummingbot.connector.derivative.okx_perpetual.okx_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.okx_perpetual.okx_perpetual_utils as okx_utils
from hummingbot.connector.derivative.okx_perpetual import okx_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.okx_perpetual.okx_perpetual_api_order_book_data_source import (
    OkxPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.okx_perpetual.okx_perpetual_auth import OkxPerpetualAuth
from hummingbot.connector.derivative.okx_perpetual.okx_perpetual_user_stream_data_source import (
    OkxPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class OkxPerpetualDerivative(PerpetualDerivativePyBase):

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        okx_perpetual_api_key: str = None,
        okx_perpetual_secret_key: str = None,
        okx_perpetual_passphrase: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):

        self.okx_perpetual_api_key = okx_perpetual_api_key
        self.okx_perpetual_secret_key = okx_perpetual_secret_key
        self.okx_perpetual_passphrase = okx_perpetual_passphrase
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._last_trade_history_timestamp = None
        self._contract_sizes = {}

        super().__init__(client_config_map)

    @property
    def authenticator(self) -> OkxPerpetualAuth:
        return OkxPerpetualAuth(self.okx_perpetual_api_key,
                                self.okx_perpetual_secret_key,
                                self.okx_perpetual_passphrase,
                                self._time_synchronizer)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return web_utils.build_rate_limits(self.trading_pairs)

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.CLIENT_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.REST_GET_INSTRUMENTS[CONSTANTS.ENDPOINT]

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.REST_GET_INSTRUMENTS[CONSTANTS.ENDPOINT]

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.REST_SERVER_TIME[CONSTANTS.ENDPOINT]

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

    def _format_amount_to_size(self, trading_pair, amount: Decimal) -> Decimal:
        return amount / self._contract_sizes[trading_pair]

    def _format_size_to_amount(self, trading_pair, size: Decimal) -> Decimal:
        return size * self._contract_sizes[trading_pair]

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        # TODO: Check if it's market or limit_maker
        return [OrderType.LIMIT, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = '"code":"50113"' in error_description
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

    async def _make_trading_pairs_request(self) -> Any:
        params = {"instType": "SWAP"}
        exchange_info = await self._api_get(path_url=self.trading_pairs_request_path, params=params)
        return exchange_info

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return OkxPerpetualAPIOrderBookDataSource(
            self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return OkxPerpetualUserStreamDataSource(
            auth=self._auth,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def start(self, clock: Clock, timestamp: float):
        super().start(clock, timestamp)
        if self._domain == CONSTANTS.DEFAULT_DOMAIN and self.is_trading_required:
            self.set_position_mode(PositionMode.HEDGE)

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 position_action: PositionAction,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker or False
        # TODO: Check if replacing build_trade_fee by build_perpetual_trade_fee is correct. ExchangePyBase has
        # different signature from PerpetualDerivativePyBase
        fee = build_perpetual_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            position_action=position_action,
            amount=amount,
            price=price,
        )
        return fee

    async def _initialize_trading_pair_symbol_map(self):
        # This has to be reimplemented because the request requires an extra parameter
        try:
            exchange_info = await self._api_get(
                path_url=self.trading_pairs_request_path,
                params={"instType": "SWAP"},
            )
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

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
        if position_action == PositionAction.NIL:
            raise NotImplementedError
        ex_trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair)
        data = {
            "clOrdId": order_id,
            "tdMode": "cross",
            "ordType": CONSTANTS.ORDER_TYPE_MAP[order_type],
            "instId": ex_trading_pair,
            "side": "buy" if trade_type.name == "BUY" else "sell",
            "sz": str(self._format_amount_to_size(trading_pair, amount)),
        }
        if order_type.is_limit_type():
            data["px"] = str(price)
        if self.position_mode == PositionMode.HEDGE:
            if position_action == PositionAction.OPEN:
                data["posSide"] = "long" if trade_type is TradeType.BUY else "short"
            else:
                data["posSide"] = "short" if trade_type is TradeType.BUY else "long"
        else:
            data["posSide"] = "net"

        exchange_order_id = await self._api_post(
            path_url=CONSTANTS.REST_PLACE_ACTIVE_ORDER[CONSTANTS.ENDPOINT],
            data=data,
            is_auth_required=True,
            trading_pair=ex_trading_pair,
            headers={"referer": CONSTANTS.HBOT_BROKER_ID},
            **kwargs,
        )

        data = exchange_order_id["data"][0]
        if data["sCode"] != "0":
            raise IOError(f"Error submitting order {order_id}: {data['sMsg']}")
        return str(data["ordId"]), self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        data = {"instId": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)}
        if tracked_order.exchange_order_id:
            data["ordId"] = tracked_order.exchange_order_id
        if tracked_order.client_order_id:
            data["clOrdId"] = tracked_order.client_order_id
        cancel_result = await self._api_post(
            path_url=CONSTANTS.REST_CANCEL_ACTIVE_ORDER[CONSTANTS.ENDPOINT],
            data=data,
            is_auth_required=True,
            trading_pair=tracked_order.trading_pair,
        )
        data = cancel_result["data"][0]
        ret_code_ok = data["sCode"] == CONSTANTS.RET_CODE_OK
        ret_code_order_not_exists = data["sCode"] == CONSTANTS.RET_CODE_CANCEL_FAILED_BECAUSE_ORDER_NOT_EXISTS
        ret_code_already_canceled = data["sCode"] == CONSTANTS.RET_CODE_ORDER_ALREADY_CANCELLED
        if ret_code_ok or ret_code_order_not_exists or ret_code_already_canceled:
            final_result = True
        else:
            raise IOError(f"Error cancelling order {order_id}: {cancel_result}")
        return final_result

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {"uly": trading_pair, "instType": "SWAP"}

        resp_json = await self._api_get(
            path_url=CONSTANTS.REST_LATEST_SYMBOL_INFORMATION[CONSTANTS.ENDPOINT],
            params=params,
        )

        price = float(resp_json["data"][0]["last"])
        return price

    async def get_last_traded_prices(self, trading_pairs: List[str] = None) -> Dict[str, float]:
        params = {"instType": "SWAP"}

        resp_json = await self._api_get(
            path_url=CONSTANTS.REST_LATEST_SYMBOL_INFORMATION[CONSTANTS.ENDPOINT],
            params=params,
        )

        last_traded_prices = {ticker["instId"]: float(ticker["last"]) for ticker in resp_json["data"]}
        return last_traded_prices

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances
        """
        wallet_balance: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.REST_GET_WALLET_BALANCE[CONSTANTS.ENDPOINT],
            is_auth_required=True,
            params={"ccy": "USDT,USDC"},
        )

        if wallet_balance['code'] == CONSTANTS.RET_CODE_OK:
            balances = wallet_balance['data'][0]['details']
        else:
            raise Exception(wallet_balance['msg'])

        self._account_available_balances.clear()
        self._account_balances.clear()

        for balance in balances:
            self._update_balance_from_details(balance_details=balance)

    def _update_balance_from_details(self, balance_details: Dict[str, Any]):
        equity_text = balance_details["eq"]
        available_equity_text = balance_details["availEq"]

        if equity_text and available_equity_text:
            total = Decimal(equity_text)
            available = Decimal(available_equity_text)
        else:
            available = Decimal(balance_details["availBal"])
            total = available + Decimal(balance_details["frozenBal"])
        self._account_balances[balance_details["ccy"]] = total
        self._account_available_balances[balance_details["ccy"]] = available

    async def _update_trading_rules(self):
        # This has to be reimplemented because the request requires an extra parameter
        exchange_info = await self._api_get(
            path_url=self.trading_rules_request_path,
            is_auth_required=False,
            params={"instType": "SWAP"},
        )
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _format_trading_rules(self, instrument_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Converts JSON API response into a local dictionary of trading rules.
        :param instrument_info_dict: The JSON API response.
        :returns: A dictionary of trading pair to its respective TradingRule.
        """
        trading_rules = {}
        for rule in instrument_info_dict["data"]:
            try:
                if okx_utils.is_exchange_information_valid(rule):
                    trading_pair = combine_to_hb_trading_pair(rule['ctValCcy'], rule['settleCcy'])
                    contract_size = Decimal(rule["ctVal"])
                    self._contract_sizes[trading_pair] = contract_size
                    minimum_order_quantity = Decimal(rule["minSz"])
                    min_order_size = minimum_order_quantity * contract_size

                    min_price_increment = Decimal(rule["tickSz"])

                    lot_size = Decimal(rule["lotSz"])
                    min_base_amount_increment = lot_size * contract_size

                    collateral_token = rule["settleCcy"]
                    trading_rules[trading_pair] = TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(str(min_order_size)),
                        min_price_increment=Decimal(str(min_price_increment)),
                        min_base_amount_increment=Decimal(str(min_base_amount_increment)),
                        buy_order_collateral_token=collateral_token,
                        sell_order_collateral_token=collateral_token,
                    )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule: {rule}. Skipping...")
        return list(trading_rules.values())

    async def _update_trading_fees(self):
        pass

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
        body_params = {
            "instType": "SWAP",
            "ordId": order.exchange_order_id,
            "clOrdId": order.client_order_id,
            "instId": exchange_symbol,
        }
        res = await self._api_get(
            path_url=CONSTANTS.REST_USER_TRADE_RECORDS[CONSTANTS.ENDPOINT],
            params=body_params,
            is_auth_required=True,
            trading_pair=order.trading_pair,
        )
        return res

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            try:
                all_fills_response = await self._request_order_fills(order=order)
                fills_data = all_fills_response["data"]

                for fill_data in fills_data:
                    trade_update = self._parse_trade_update(trade_msg=fill_data, tracked_order=order)
                    trade_updates.append(trade_update)
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                    raise

        return trade_updates

    def _parse_trade_update(self, trade_msg: Dict, tracked_order: InFlightOrder) -> TradeUpdate:
        trade_id: str = str(trade_msg["tradeId"])
        position_side = trade_msg["posSide"]
        position_action = (PositionAction.OPEN
                           if (tracked_order.trade_type is TradeType.BUY and position_side == "long"
                               or tracked_order.trade_type is TradeType.SELL and position_side == "short")
                           else PositionAction.CLOSE)
        fill_base_amount = abs(self._format_size_to_amount(tracked_order.trading_pair, (Decimal(str(trade_msg["fillSz"])))))

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=trade_msg["feeCcy"],
            flat_fees=[TokenAmount(amount=-Decimal(trade_msg["fee"]), token=trade_msg["feeCcy"])]
        )

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=trade_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(trade_msg["ordId"]),
            trading_pair=tracked_order.trading_pair,
            fee=fee,
            fill_base_amount=fill_base_amount,
            fill_quote_amount=Decimal(trade_msg["fillPx"]) * fill_base_amount,
            fill_price=Decimal(trade_msg["fillPx"]),
            fill_timestamp=int(trade_msg["ts"]) * 1e-3,
        )
        return trade_update

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._request_order_update(order=tracked_order)

        order_data = updated_order_data["data"][0]
        new_state = CONSTANTS.ORDER_STATE[order_data["state"]]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order_data["ordId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=int(order_data["uTime"]),
            new_state=new_state,
        )
        return order_update

    async def _request_order_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.REST_QUERY_ACTIVE_ORDER[CONSTANTS.ENDPOINT],
            params={
                "instId": await self.exchange_symbol_associated_to_pair(order.trading_pair),
                "clOrdId": order.client_order_id},
            is_auth_required=True)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                endpoint = web_utils.endpoint_from_message(event_message)
                payload = web_utils.payload_from_message(event_message)
                if endpoint == "subscribe":
                    continue
                if endpoint == "error":
                    self.logger().error(f"Error message received from user stream: {payload}.")
                    continue
                if endpoint == CONSTANTS.WS_POSITIONS_CHANNEL:
                    for position_msg in payload:
                        await self._process_account_position_event(position_msg)
                elif endpoint == CONSTANTS.WS_ORDERS_CHANNEL:
                    for order_msg in payload:
                        self._process_order_event_message(order_msg)
                elif endpoint == CONSTANTS.WS_ACCOUNT_CHANNEL:
                    for wallet_msg in payload:
                        self._process_wallet_event_message(wallet_msg)
                elif endpoint is None:
                    self.logger().error(f"Could not extract endpoint from {event_message}.")
                    raise ValueError
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_trade_history(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_trade_history(self):
        """
        Calls REST API to get trade history (order fills)
        """

        trade_history_tasks = []

        for trading_pair in self._trading_pairs:
            exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
            body_params = {
                "instId": exchange_symbol,
                "limit": 100,
            }
            if self._last_trade_history_timestamp:
                body_params["begin"] = int(int(self._last_trade_history_timestamp) * 1e3)

            trade_history_tasks.append(
                asyncio.create_task(self._api_get(
                    path_url=CONSTANTS.REST_USER_TRADE_RECORDS[CONSTANTS.ENDPOINT],
                    params=body_params,
                    is_auth_required=True,
                    trading_pair=trading_pair,
                ))
            )

        raw_responses: List[Dict[str, Any]] = await safe_gather(*trade_history_tasks, return_exceptions=True)

        # Initial parsing of responses. Joining all the responses
        parsed_history_resps: List[Dict[str, Any]] = []
        for trading_pair, resp in zip(self._trading_pairs, raw_responses):
            if not isinstance(resp, Exception):
                timestamps = [int(trade["ts"]) * 1e-3 for trade in resp["data"]]
                self._last_trade_history_timestamp = max(timestamps) if timestamps else None
                entries = resp["data"]
                if entries:
                    parsed_history_resps.extend(entries)
            else:
                self.logger().network(
                    f"Error fetching status update for {trading_pair}: {resp}.",
                    app_warning_msg=f"Failed to fetch status update for {trading_pair}."
                )

        # Trade updates must be handled before any order status updates.
        for trade in parsed_history_resps:
            self._process_trade_event_message(trade)

    async def _update_positions(self):
        """
        Retrieves all positions using the REST API.
        """
        position_tasks = []

        for trading_pair in self._trading_pairs:
            ex_trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair)
            body_params = {"instId": ex_trading_pair}
            position_tasks.append(
                asyncio.create_task(self._api_get(
                    path_url=CONSTANTS.REST_GET_POSITIONS[CONSTANTS.ENDPOINT],
                    params=body_params,
                    is_auth_required=True,
                    trading_pair=trading_pair,
                ))
            )

        raw_responses: List[Dict[str, Any]] = await safe_gather(*position_tasks, return_exceptions=True)

        # Initial parsing of responses. Joining all the responses
        parsed_resps: List[Dict[str, Any]] = []
        for resp, trading_pair in zip(raw_responses, self._trading_pairs):
            if not isinstance(resp, Exception):
                result = resp["data"]
                if result:
                    position_entries = result if isinstance(result, list) else [result]
                    parsed_resps.extend(position_entries)
            else:
                self.logger().error(f"Error fetching positions for {trading_pair}. Response: {resp}")

        for data in parsed_resps:
            ex_trading_pair = data["instId"]
            hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(ex_trading_pair)
            position_side = self.get_position_side(data)
            unrealized_pnl = Decimal(data["upl"]) if bool(data["upl"]) else Decimal(str(0.0))
            entry_price = Decimal(data["avgPx"]) if bool(data["avgPx"]) else Decimal(str(0.0))
            amount = self.get_position_amount(data)
            leverage = Decimal(data["lever"]) if bool(data["lever"]) else Decimal(str(0.0))
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

    @staticmethod
    def get_position_side(position_msg: Dict[str, Any]) -> PositionSide:
        if position_msg.get("posSide") == "net":
            position_side = PositionSide.LONG if int(position_msg["pos"]) > 0 else PositionSide.SHORT
        else:
            position_side = PositionSide.LONG if position_msg.get("posSide") == "long" else PositionSide.SHORT
        return position_side

    @staticmethod
    def get_position_amount(position_msg: Dict[str, Any]) -> Decimal:
        if bool(position_msg["notionalUsd"]):
            notional_usd = Decimal(position_msg["notionalUsd"])
            avg_px = Decimal(position_msg["avgPx"])
            amount = abs(notional_usd / avg_px) if notional_usd != s_decimal_0 else s_decimal_0
            return max(amount, round(amount))
        else:
            return Decimal("0.0")

    async def _process_account_position_event(self, position_msg: Dict[str, Any]):
        """
        Updates position
        :param position_msg: The position event message payload
        """
        if bool(position_msg.get("instId")):
            ex_trading_pair = position_msg["instId"]
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=ex_trading_pair)
            position_side = self.get_position_side(position_msg)
            entry_price = Decimal(position_msg["avgPx"]) if bool(position_msg["avgPx"]) else Decimal("0")
            amount = self.get_position_amount(position_msg)
            leverage = Decimal(position_msg["lever"]) if bool(position_msg["lever"]) else Decimal("0")
            unrealized_pnl = Decimal(position_msg["upl"]) if bool(position_msg["upl"]) else Decimal("0")
            pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
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
            # safe_ensure_future(self._update_balances())

    def _process_trade_event_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        :param trade_msg: The trade event message payload
        """

        client_order_id = str(trade_msg["clOrdId"])
        fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)

        if fillable_order is not None:
            trade_update = self._parse_trade_update(trade_msg=trade_msg, tracked_order=fillable_order)
            self._order_tracker.process_trade_update(trade_update)

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order event message payload
        """
        client_order_id = order_msg["clOrdId"]
        order_status = CONSTANTS.ORDER_STATE[order_msg["state"]]
        trade_type = TradeType.BUY if order_msg["side"] == "buy" else TradeType.SELL
        position_side = PositionSide.LONG if order_msg["posSide"] == "long" else PositionSide.SHORT
        position_action = (PositionAction.OPEN
                           if (trade_type == TradeType.BUY and position_side == PositionSide.LONG) or
                              (trade_type == TradeType.SELL and position_side == PositionSide.SHORT)
                           else PositionAction.CLOSE)
        fill_fee_currency = order_msg.get("fillFeeCcy")
        fill_fee = -Decimal(order_msg.get("fillFee", "0"))

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

        fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        if fillable_order is not None and order_status in [OrderState.PARTIALLY_FILLED, OrderState.FILLED]:
            fill_base_amount = abs(self._format_size_to_amount(fillable_order.trading_pair, (Decimal(str(order_msg["fillSz"])))))
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fill_fee_currency,
                flat_fees=[TokenAmount(amount=fill_fee, token=fill_fee_currency)]
            )
            trade_update = TradeUpdate(
                trade_id=str(order_msg["tradeId"]),
                client_order_id=fillable_order.client_order_id,
                exchange_order_id=str(order_msg["ordId"]),
                trading_pair=fillable_order.trading_pair,
                fee=fee,
                fill_base_amount=fill_base_amount,
                fill_quote_amount=fill_base_amount * Decimal(order_msg["fillPx"]),
                fill_price=Decimal(order_msg["fillPx"]),
                fill_timestamp=int(order_msg["uTime"]),
            )
            self._order_tracker.process_trade_update(trade_update)

    def _process_wallet_event_message(self, wallet_msg: Dict[str, Any]):
        """
        Updates account balances.
        :param wallet_msg: The account balance update message payload
        """
        for balance_detail in wallet_msg["details"]:
            self._update_balance_from_details(balance_details=balance_detail)

    async def _make_trading_rules_request(self) -> Any:
        params = {"instType": "SWAP"}
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path, params=params)
        return exchange_info

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(okx_utils.is_exchange_information_valid, exchange_info["data"]):
            mapping[symbol_data["instId"]] = combine_to_hb_trading_pair(base=symbol_data["ctValCcy"],
                                                                        quote=symbol_data["settleCcy"])
        self._set_trading_pair_symbol_map(mapping)

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        msg = ""
        success = True

        api_mode = CONSTANTS.POSITION_MODE_MAP[mode]

        data = {"posMode": api_mode}

        response = await self._api_post(
            path_url=CONSTANTS.REST_SET_POSITION_MODE[CONSTANTS.ENDPOINT],
            data=data,
            is_auth_required=True,
        )

        response_code = response["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            formatted_ret_code = self._format_ret_code_for_print(response_code)
            msg = f"{formatted_ret_code} - {response['msg']}"
            success = False

        return success, msg

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        success = False
        msg = ""

        data = {
            "instId": exchange_symbol,
            "lever": leverage,
            "mgnMode": "cross"
        }
        resp: Dict[str, Any] = await self._api_post(
            path_url=CONSTANTS.REST_SET_LEVERAGE[CONSTANTS.ENDPOINT],
            data=data,
            is_auth_required=True,
            trading_pair=trading_pair,
        )

        if resp["code"] == CONSTANTS.RET_CODE_OK:
            success = True
        else:
            formatted_ret_code = self._format_ret_code_for_print(resp['code'])
            msg = f"{formatted_ret_code} - {resp['msg']}"

        return success, msg

    async def trading_pair_associated_to_exchange_symbol(self, symbol: str):
        return symbol.rstrip("-SWAP")

    async def exchange_symbol_associated_to_pair(self, trading_pair: str):
        return f"{trading_pair}-SWAP"

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        """
        Fetches the last funding fee/payment for the given trading pair.

        Type 8 represents funding fee/payment. Subtypes 173 and 174 represent funding fee expense and
        income respectively.

        Funding Fee expense (subType = 173)

        You may refer to "pnl" for the fee payment
        """
        params = {
            "instType": "SWAP",
            "type": 8
        }
        raw_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.REST_BILLS_DETAILS[CONSTANTS.ENDPOINT],
            params=params,
            is_auth_required=True,
            trading_pair=trading_pair,
        )
        data: List[Dict[str, Any]] = raw_response.get("data")
        ex_trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair)
        trading_pair_data = [bill for bill in data if bill["instId"] == ex_trading_pair]
        payment = Decimal("-1")
        if not trading_pair_data:
            # An empty funding fee/payment is retrieved.
            timestamp, funding_rate = 0, Decimal("-1")
        else:
            timestamp: int = int(trading_pair_data[0]["ts"])
            funding_rate: Decimal = self._orderbook_ds._last_rate if self._orderbook_ds._last_rate is not None else Decimal(str(-1))
            if trading_pair_data[0].get("type") == CONSTANTS.FUNDING_PAYMENT_TYPE:
                payment: Decimal = Decimal(str(trading_pair_data[0]["pnl"]))

        return timestamp, funding_rate, payment

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
                method=method.value,
                endpoint=path_url,
            )
        url = web_utils.get_rest_url_for_endpoint(endpoint=path_url, domain=self._domain)

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

    @staticmethod
    def _format_ret_code_for_print(ret_code: Union[str, int]) -> str:
        return f"ret_code <{ret_code}>"
