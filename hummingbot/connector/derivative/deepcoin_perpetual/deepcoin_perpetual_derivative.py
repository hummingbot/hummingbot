import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

import bidict as bidict

from hummingbot.connector.derivative.deepcoin_perpetual import (
    deepcoin_perpetual_constants as CONSTANTS,
    deepcoin_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_auth import DeepcoinPerpetualAuth
from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_api_order_book_data_source import (
    DeepcoinPerpetualAPIOrderBookDataSource,
)

from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_user_stream_data_source import (
    DeepcoinPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
import hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_utils as deepcoin_utils
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee


s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")

class DeepcoinPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        deepcoin_perpetual_api_key: str = None,
        deepcoin_perpetual_secret_key: str = None,
        deepcoin_perpetual_passphrase: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):

        self.deepcoin_perpetual_api_key = deepcoin_perpetual_api_key
        self.deepcoin_perpetual_secret_key = deepcoin_perpetual_secret_key
        self.deepcoin_perpetual_passphrase = deepcoin_perpetual_passphrase
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._last_trade_history_timestamp = None
        self._contract_sizes = {}

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
        # return [PositionMode.ONEWAY, PositionMode.HEDGE]
        return []


    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return DeepcoinPerpetualAPIOrderBookDataSource(
            self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self.authenticator,
        )

    async def exchange_symbol_associated_to_pair(self, trading_pair: str):
        return f"{trading_pair}-SWAP"

    async def trading_pair_associated_to_exchange_symbol(self, symbol: str):
        return symbol.rstrip("-SWAP")

    def _format_size_to_amount(self, trading_pair, size: Decimal) -> Decimal:
        return size * self._contract_sizes[trading_pair]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(deepcoin_utils.is_exchange_information_valid, exchange_info["data"]):
            mapping[symbol_data["instId"]] = combine_to_hb_trading_pair(base=symbol_data["baseCcy"],
                                                                        quote=symbol_data["quoteCcy"])
        self._set_trading_pair_symbol_map(mapping)

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
            amount_str = f"{amount:f}"
            data = {
                "clOrdId": order_id,
                "tdMode": "cross",
                "mrgPosition": "merge",  # todo 文档里没有
                "ordType": CONSTANTS.ORDER_TYPE_MAP[order_type],
                "instId": ex_trading_pair,
                "side": "buy" if trade_type.name == "BUY" else "sell",
                "sz": amount_str,
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

            order_result = await self._api_post(
                path_url=CONSTANTS.CREATIVE_ORDER_URL,
                data=data,
                is_auth_required=True,
                trading_pair=ex_trading_pair,
                **kwargs,
            )

            data = order_result["data"]
            if data["sCode"] != "0":
                raise IOError(f"Error submitting order {order_id}: {data['sMsg']}")
            return str(data["ordId"]), self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        data = {
            "instId": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
            "ordId": order_id,
        }

        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_OPEN_ORDERS_URL,
            data=data,
            is_auth_required=True,
        )
        data = cancel_result["data"]
        ret_code_ok = data["sCode"] == CONSTANTS.RET_CODE_OK
        if ret_code_ok:
            final_result = True
        else:
            raise IOError(f"Error cancelling order {order_id}: {cancel_result}")
        return final_result

    # Get last traded price for a single trading pair
    async def _get_last_traded_price(self, trading_pair: str) -> float:
            params = {"uly": trading_pair, "instType": "SWAP"}
            resp_json = await self._api_get(
                path_url=CONSTANTS.TICKER_PRICE_URL,
                params=params,
            )

            price = float(resp_json["data"][0]["last"])
            return price

    # Get last traded prices for multiple trading pairs
    async def get_last_traded_prices(self, trading_pairs: List[str] = None) -> Dict[str, float]:
        params = {"instType": "SWAP"}

        resp_json = await self._api_get(
            path_url=CONSTANTS.TICKER_PRICE_URL,
            params=params,
        )

        last_traded_prices = {ticker["instId"].replace("-SWAP", ""): float(ticker["last"]) for ticker in
                              resp_json["data"]}
        return last_traded_prices

    async def _update_balances(self):
        account_info: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_INFO_URL,
            is_auth_required=True,
            params={"instType":"SWAP", "ccy": "USDT"},
        )

        if account_info.get("code") != CONSTANTS.RET_CODE_OK:
            raise Exception(f"Failed to fetch balances: {account_info.get('msg', '')}")

        balances = account_info.get("data", [])
        if not isinstance(balances, list):
            raise Exception(f"Invalid balance format: {balances}")

        # === 3. 清空旧缓存 ===
        self._account_available_balances.clear()
        self._account_balances.clear()

        # === 4. 更新每个币种的余额 ===
        for balance in balances:
            self._update_balance_from_details(balance)

    def _update_balance_from_details(self, balance_details: Dict[str, Any]):
        """
        Parse and update a single balance entry from Deepcoin API
        """
        try:
            currency = balance_details["ccy"]
            total_balance = Decimal(balance_details["bal"])
            available_balance = Decimal(balance_details["availBal"])

            self._account_balances[currency] = total_balance
            self._account_available_balances[currency] = available_balance

        except KeyError as e:
            self.logger().warning(f"Missing field in balance details: {balance_details}, error: {e}")
        except Exception as e:
            self.logger().error(f"Error parsing balance details: {balance_details}, error: {e}", exc_info=True)

    async def _update_trading_rules(self):
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
        Formats trading rules from exchange info
        """
        trading_rules = {}
        for rule in instrument_info_dict["data"]:
            try:
                trading_pair = combine_to_hb_trading_pair(rule['baseCcy'], rule['quoteCcy'])

                # Contract specifications
                ct_val = Decimal(rule.get("ctVal"))
                self._contract_sizes[trading_pair] = ct_val
                min_sz = Decimal(rule["minSz"])
                lot_sz = Decimal(rule["lotSz"])
                tick_sz = Decimal(rule["tickSz"])  # Price tick size
                max_lmt_sz = Decimal(rule["maxLmtSz"])

                # Convert contract-based sizes to base asset amounts
                min_order_size = min_sz * ct_val
                min_base_amount_increment = lot_sz * ct_val
                max_order_size = max_lmt_sz * ct_val

                collateral_token = rule['quoteCcy']
                trading_rules[trading_pair] = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_order_size,
                    max_order_size=max_order_size,
                    min_price_increment=tick_sz,
                    min_base_amount_increment=min_base_amount_increment,
                    buy_order_collateral_token=collateral_token,
                    sell_order_collateral_token=collateral_token,
                )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule: {rule}. Skipping...")
        return list(trading_rules.values())

    # async def _update_trading_fees(self):
    #     pass

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
        body_params = {
            "instType": "SWAP",
            "instId": exchange_symbol,
            "ordId": order.exchange_order_id,
        }
        res = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
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

                if fills_data is not None:
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

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = '"code":"50' in error_description  # 50开头错误码
        return is_time_synchronizer_related

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
            path_url=CONSTANTS.ACTIVE_ORDER_URL,
            params={
                "instId": await self.exchange_symbol_associated_to_pair(order.trading_pair),
                "ordId": order.exchange_order_id
            },
            is_auth_required=True
        )

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                endpoint = web_utils.endpoint_from_message(event_message)
                payload = web_utils.payload_from_message(event_message)

                if endpoint == CONSTANTS.WS_POSITIONS_CHANNEL:
                    for position_msg in payload:
                        data = position_msg["data"]
                        await self._process_account_position_event(data)
                elif endpoint == CONSTANTS.WS_ORDERS_CHANNEL:
                    for order_msg in payload:
                        data = order_msg["data"]
                        self._process_order_event_message(data)
                elif endpoint == CONSTANTS.WS_TRADES_CHANNEL:
                    for trade_msg in payload:
                        data = trade_msg["data"]
                        self._process_trade_order_event_message(data)
                elif endpoint == CONSTANTS.WS_ACCOUNT_CHANNEL:
                    for wallet_msg in payload:
                        data = wallet_msg["data"]
                        self._process_wallet_event_message(data)
                elif endpoint is None:
                    self.logger().error(f"Could not extract endpoint from {event_message}.")
                    raise ValueError
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    @staticmethod
    def get_position_side(position_data: Dict[str, Any]) -> PositionSide:
        if position_data.get("p") == "2":
            position_side = PositionSide.LONG if int(position_data["Po"]) > 0 else PositionSide.SHORT
        else:
            position_side = PositionSide.LONG if position_data.get("p") == "0" else PositionSide.SHORT
        return position_side

    async def _process_account_position_event(self, position_data: Dict[str, Any]):
        """
        Updates position
        :param position_msg: The position event message payload
        """
        ex_trading_pair = position_data["I"]
        trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=ex_trading_pair)
        position_side = self.get_position_side(position_data)
        entry_price = Decimal(position_data["OP"])
        size = Decimal(position_data["Po"])
        amount = abs(self._format_size_to_amount(trading_pair, size))

        leverage = Decimal(position_data["l"])
        unrealized_pnl =  Decimal("0")  #  todo 不支持计算未实现盈亏
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

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order event message payload
        """
        client_order_id = order_msg["OS"]  # todo 这里使用的是：交易所订单ID
        order_status = CONSTANTS.WS_ORDER_STATE[order_msg["Or"]]
        updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if updatable_order is not None:
            new_order_update: OrderUpdate = OrderUpdate(
                trading_pair=updatable_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=order_status,
                client_order_id=client_order_id,
                exchange_order_id=order_msg["OS"],
            )
            self._order_tracker.process_order_update(new_order_update)

    def _process_trade_order_event_message(self, trade_msg: Dict[str, Any]):
        client_order_id = trade_msg["OS"]
        order_status = CONSTANTS.WS_ORDER_STATE["1"] #todo 这么无法区分是【部分成交】还是【全部成交】
        position_action = PositionAction.OPEN if trade_msg["o"] == "0" else PositionAction.CLOSE
        fill_fee_currency = trade_msg.get("f")
        fill_fee = -Decimal(trade_msg.get("F", "0"))

        fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        if fillable_order is not None:
            fill_base_amount = abs(self._format_size_to_amount(fillable_order.trading_pair, (Decimal(str(trade_msg["V"])))))
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fill_fee_currency,
                flat_fees=[TokenAmount(amount=fill_fee, token=fill_fee_currency)]
            )
            trade_update = TradeUpdate(
                trade_id=str(trade_msg["TI"]),
                client_order_id=fillable_order.client_order_id,
                exchange_order_id=str(trade_msg["OS"]),
                trading_pair=fillable_order.trading_pair,
                fee=fee,
                fill_base_amount=fill_base_amount,
                fill_quote_amount=fill_base_amount * Decimal(trade_msg["P"]),
                fill_price=Decimal(trade_msg["P"]),
                fill_timestamp=int(trade_msg["IT"]),
            )
            self._order_tracker.process_trade_update(trade_update)

    def _process_wallet_event_message(self, wallet_msg: Dict[str, Any]):
        """
        Updates account balances.
        :param wallet_msg: The account balance update message payload
        """
        self._update_balance_from_details(balance_details=wallet_msg)

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_trade_history(),
            self._update_order_status(),    # ok
            self._update_balances(),        # ok
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
                "instType": "SWAP",
                "instId": exchange_symbol,
                "limit": 100,
            }
            if self._last_trade_update_order_id:
                body_params["after"] = self._last_trade_update_order_id

            trade_history_tasks.append(
                asyncio.create_task(self._api_get(
                    path_url=CONSTANTS.REST_USER_TRADE_RECORDS,
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
                timestamps = [int(trade["uTime"]) * 1e-3 for trade in resp["data"]]
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

    def _process_trade_event_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        :param trade_msg: The trade event message payload
        """
        client_order_id = str(trade_msg["ordId"])  # todo 统一使用交易所订单ID
        fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)

        if fillable_order is not None:
            trade_update = self._parse_trade_update(trade_msg=trade_msg, tracked_order=fillable_order)
            self._order_tracker.process_trade_update(trade_update)

    async def _update_positions(self):
        """
        Retrieves all positions using the REST API.
        """
        position_tasks = []

        for trading_pair in self._trading_pairs:
            ex_trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair)
            body_params = {
                "instType": "SWAP",
                "instId": ex_trading_pair
            }
            position_tasks.append(
                asyncio.create_task(self._api_get(
                    path_url=CONSTANTS.POSITION_INFORMATION_URL,
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
            unrealized_pnl = Decimal(str(0.0))
            entry_price = Decimal(data["avgPx"]) if bool(data["avgPx"]) else Decimal(str(0.0))
            amount = abs(self._format_size_to_amount(ex_trading_pair, (Decimal(str(data["pos"])))))
            leverage = Decimal(data["lever"])
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

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        success = False
        msg = "Perpetuals don't allow for a position mode change."

        return success, msg

    async def _make_trading_rules_request(self) -> Any:
        params = {"instType": "SWAP"}
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path, params=params)
        return exchange_info

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        success = False
        msg = ""

        data = {
            "instId": exchange_symbol,
            "lever": str(leverage),
            "mgnMode": "cross",
            "mrgPosition": "merge",
        }
        resp: Dict[str, Any] = await self._api_post(
            path_url=CONSTANTS.SET_LEVERAGE_URL,
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

    @staticmethod
    def _format_ret_code_for_print(ret_code: Union[str, int]) -> str:
        return f"ret_code <{ret_code}>"


    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        ts_ms = int(time.time() * 1000)
        params = {
            "instType": "SWAP",
            "after": ts_ms,
        }
        raw_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.GET_BILLS_DETAILS,
            params=params,
            is_auth_required=True,
            trading_pair=trading_pair,
        )
        data: List[Dict[str, Any]] = raw_response.get("data")

        # 暂不支持按照交易对查询
        # ex_trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair)
        # trading_pair_data = [bill for bill in data if bill["instId"] == ex_trading_pair]

        payment = Decimal("-1")
        if not data:
            # An empty funding fee/payment is retrieved.
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
        else:
            # TODO，暂不支持按照交易对查询
            last_data = data[0]
            timestamp: int = int(last_data["ts"] / 1e3)
            funding_rate: Decimal = Decimal("-1")
            if last_data.get("type") == CONSTANTS.FUNDING_PAYMENT_TYPE:
                payment: Decimal = Decimal(str(last_data["balChg"]))
        return timestamp, funding_rate, payment


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


    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        return False

    async def _update_trading_fees(self):
        pass

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return DeepcoinPerpetualUserStreamDataSource(
            auth=self._auth,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )