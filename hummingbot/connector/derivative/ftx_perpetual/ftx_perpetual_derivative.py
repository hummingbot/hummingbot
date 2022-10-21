import asyncio
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from bidict import bidict

import hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_utils as ftx_perpetual_utils
from hummingbot.connector.derivative.ftx_perpetual import ftx_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_api_order_book_data_source import (
    FtxPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_api_user_stream_data_source import (
    FtxPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_auth import FtxPerpetualAuth
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
from hummingbot.core.event.events import AccountEvent, PositionModeChangeEvent
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class FtxPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            ftx_perpetual_api_key: str = None,
            ftx_perpetual_secret_key: str = None,
            ftx_subaccount_name: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
    ):

        self.ftx_perpetual_api_key = ftx_perpetual_api_key
        self.ftx_perpetual_secret_key = ftx_perpetual_secret_key
        self._subaccount_name = ftx_subaccount_name
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trade_history_timestamp = None

        super().__init__(client_config_map)

        self._real_time_balance_update = False

    @property
    def name(self) -> str:
        return "ftx_perpetual"

    @property
    def authenticator(self) -> AuthBase:
        return FtxPerpetualAuth(
            api_key=self.ftx_perpetual_api_key,
            secret_key=self.ftx_perpetual_secret_key,
            subaccount_name=self._subaccount_name)

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.FTX_MARKETS_PATH

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.FTX_MARKETS_PATH

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.FTX_NETWORK_STATUS_PATH

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
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def start(self, clock: Clock, timestamp: float):
        super().start(clock, timestamp)
        self.set_position_mode(PositionMode.ONEWAY)

    def set_position_mode(self, mode: PositionMode):
        if mode in self.supported_position_modes():
            self._perpetual_trading.set_position_mode(PositionMode.ONEWAY)
            self.logger().debug(f"Only {PositionMode.ONEWAY} is supported")
        else:
            msg = "FTX Perpetual don't allow position mode change"
            self.logger().debug(msg)
            self.trigger_event(
                AccountEvent.PositionModeChangeFailed,
                PositionModeChangeEvent(
                    self.current_timestamp,
                    "ALL",
                    mode,
                    msg,
                ),
            )

    async def _trading_pair_position_mode_set(self, mode, trading_pair):
        pass

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        # FTX API does not include an endpoint to get the server time, thus the TimeSynchronizer is not used
        return False

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.FTX_ORDER_WITH_CLIENT_ID_PATH.format(order_id),
            is_auth_required=True,
            limit_id=CONSTANTS.FTX_CANCEL_ORDER_LIMIT_ID)

        if not cancel_result.get("success", False):
            self.logger().warning(
                f"Failed to cancel order {order_id} ({cancel_result})")

        return cancel_result.get("success", False)

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
        api_params = {
            "market": await self.exchange_symbol_associated_to_pair(trading_pair),
            "side": trade_type.name.lower(),
            "price": float(price),
            "type": "market" if trade_type == OrderType.MARKET else "limit",
            "size": float(amount),
            "clientId": order_id,
            "reduceOnly": position_action == PositionAction.CLOSE,
        }
        order_result = await self._api_post(
            path_url=CONSTANTS.FTX_PLACE_ORDER_PATH,
            data=api_params,
            is_auth_required=True)
        exchange_order_id = str(order_result["result"]["id"])

        return exchange_order_id, self.current_timestamp

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker or False
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
        pass

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return FtxPerpetualAPIOrderBookDataSource(
            self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return FtxPerpetualAPIUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

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
                "symbol": exchange_symbol,
                "limit": 200,
            }
            if self._last_trade_history_timestamp:
                body_params["start_time"] = int(int(self._last_trade_history_timestamp) * 1e3)

            trade_history_tasks.append(
                asyncio.create_task(self._api_get(
                    path_url=CONSTANTS.USER_TRADE_RECORDS_PATH_URL,
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
                self._last_trade_history_timestamp = float(resp["time_now"])
                trade_entries = (resp["result"]["trade_list"]
                                 if "trade_list" in resp["result"]
                                 else resp["result"]["data"])
                if trade_entries:
                    parsed_history_resps.extend(trade_entries)
            else:
                self.logger().network(
                    f"Error fetching status update for {trading_pair}: {resp}.",
                    app_warning_msg=f"Failed to fetch status update for {trading_pair}."
                )

        # Trade updates must be handled before any order status updates.
        for trade in parsed_history_resps:
            self._process_trade_event_message(trade)

    async def _update_balances(self):
        msg = await self._api_request(
            path_url=CONSTANTS.FTX_BALANCES_PATH,
            is_auth_required=True)

        if msg.get("success", False):
            balances = msg["result"]
        else:
            raise Exception(msg['msg'])

        self._account_available_balances.clear()
        self._account_balances.clear()

        for balance in balances:
            self._account_balances[balance["coin"]] = Decimal(str(balance["total"]))
            self._account_available_balances[balance["coin"]] = Decimal(str(balance["free"]))

    async def _update_positions(self):
        """
        Retrieves all positions using the REST API.
        """
        position_tasks = []

        for trading_pair in self._trading_pairs:
            ex_trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair)
            body_params = {"symbol": ex_trading_pair}
            position_tasks.append(
                asyncio.create_task(self._api_get(
                    path_url=CONSTANTS.GET_POSITIONS_PATH_URL,
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
                result = resp["result"]
                if result:
                    position_entries = result if isinstance(result, list) else [result]
                    parsed_resps.extend(position_entries)
            else:
                self.logger().error(f"Error fetching positions for {trading_pair}. Response: {resp}")

        for position in parsed_resps:
            data = position
            ex_trading_pair = data.get("symbol")
            hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(ex_trading_pair)
            position_side = PositionSide.LONG if data["side"] == "Buy" else PositionSide.SHORT
            unrealized_pnl = Decimal(str(data["unrealised_pnl"]))
            entry_price = Decimal(str(data["entry_price"]))
            amount = Decimal(str(data["size"]))
            leverage = Decimal(str(data["leverage"])) if ftx_perpetual_utils.is_linear_perpetual(hb_trading_pair) \
                else Decimal(str(data["effective_leverage"]))
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

        try:
            exchange_order_id = await order.get_exchange_order_id()
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.FTX_ORDER_FILLS_PATH,
                params={
                    "market": trading_pair,
                    "orderId": int(exchange_order_id)
                },
                is_auth_required=True)

            for trade_fill in all_fills_response.get("result", []):
                trade_update = self._create_trade_update_with_order_fill_data(order_fill_msg=trade_fill, order=order)
                trade_updates.append(trade_update)

        except asyncio.TimeoutError:
            raise IOError(f"Skipped order update with order fills for {order.client_order_id} "
                          "- waiting for exchange order id.")

        return trade_updates

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
        body_params = {
            "order_id": order.exchange_order_id,
            "symbol": exchange_symbol,
        }
        res = await self._api_get(
            path_url=CONSTANTS.USER_TRADE_RECORDS_PATH_URL,
            params=body_params,
            is_auth_required=True,
            trading_pair=order.trading_pair,
        )
        return res

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.FTX_ORDER_WITH_CLIENT_ID_PATH.format(tracked_order.client_order_id),
            is_auth_required=True,
            limit_id=CONSTANTS.FTX_GET_ORDER_LIMIT_ID)

        order_update = self._create_order_update_with_order_status_data(
            order_status_msg=updated_order_data["result"],
            order=tracked_order)

        return order_update

    async def _request_order_status_data(self, tracked_order: InFlightOrder) -> Dict:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)
        query_params = {
            "symbol": exchange_symbol,
            "order_link_id": tracked_order.client_order_id
        }
        if tracked_order.exchange_order_id is not None:
            query_params["order_id"] = tracked_order.exchange_order_id

        resp = await self._api_get(
            path_url=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL,
            params=query_params,
            is_auth_required=True,
            trading_pair=tracked_order.trading_pair,
        )

        return resp

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                channel: str = event_message["channel"]
                data: Dict[str, Any] = event_message["data"]
                if channel == CONSTANTS.WS_PRIVATE_FILLS_CHANNEL:
                    exchange_order_id = str(data["orderId"])
                    order = next((order for order in self._order_tracker.all_fillable_orders.values()
                                  if order.exchange_order_id == exchange_order_id),
                                 None)
                    if order is not None:
                        trade_update = self._create_trade_update_with_order_fill_data(
                            order_fill_msg=data,
                            order=order)
                        self._order_tracker.process_trade_update(trade_update=trade_update)
                elif channel == CONSTANTS.WS_PRIVATE_ORDERS_CHANNEL:
                    client_order_id = data["clientId"]
                    order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if order is not None:
                        order_update = self._create_order_update_with_order_status_data(
                            order_status_msg=data,
                            order=order)
                        self._order_tracker.process_order_update(order_update=order_update)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)

    async def _process_account_position_event(self, position_msg: Dict[str, Any]):
        """
        Updates position
        :param position_msg: The position event message payload
        """
        ex_trading_pair = position_msg["symbol"]
        trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=ex_trading_pair)
        position_side = PositionSide.LONG if position_msg["side"] == "Buy" else PositionSide.SHORT
        position_value = Decimal(str(position_msg["position_value"]))
        entry_price = Decimal(str(position_msg["entry_price"]))
        amount = Decimal(str(position_msg["size"]))
        leverage = Decimal(str(position_msg["leverage"]))
        unrealized_pnl = position_value - (amount * entry_price * leverage)
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

        # Trigger balance update because Ftx doesn't have balance updates through the websocket
        safe_ensure_future(self._update_balances())

    def _process_trade_event_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        :param trade_msg: The trade event message payload
        """

        client_order_id = str(trade_msg["order_link_id"])
        fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)

        if fillable_order is not None:
            trade_update = self._parse_trade_update(trade_msg=trade_msg, tracked_order=fillable_order)
            self._order_tracker.process_trade_update(trade_update)

    def _parse_trade_update(self, trade_msg: Dict, tracked_order: InFlightOrder) -> TradeUpdate:
        trade_id: str = str(trade_msg["exec_id"])

        fee_asset = tracked_order.quote_asset
        fee_amount = Decimal(trade_msg["exec_fee"])
        position_side = trade_msg["side"]
        position_action = (PositionAction.OPEN
                           if (tracked_order.trade_type is TradeType.BUY and position_side == "Buy"
                               or tracked_order.trade_type is TradeType.SELL and position_side == "Sell")
                           else PositionAction.CLOSE)

        flat_fees = [] if fee_amount == Decimal("0") else [TokenAmount(amount=fee_amount, token=fee_asset)]

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=flat_fees,
        )

        exec_price = Decimal(trade_msg["exec_price"]) if "exec_price" in trade_msg else Decimal(trade_msg["price"])
        exec_time = (
            trade_msg["exec_time"]
            if "exec_time" in trade_msg
            else pd.Timestamp(trade_msg["trade_time"]).timestamp()
        )

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=trade_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(trade_msg["order_id"]),
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=exec_time,
            fill_price=exec_price,
            fill_base_amount=Decimal(trade_msg["exec_qty"]),
            fill_quote_amount=exec_price * Decimal(trade_msg["exec_qty"]),
            fee=fee,
        )

        return trade_update

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order event message payload
        """
        order_status = CONSTANTS.ORDER_STATE[order_msg["order_status"]]
        client_order_id = str(order_msg["order_link_id"])
        updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if updatable_order is not None:
            new_order_update: OrderUpdate = OrderUpdate(
                trading_pair=updatable_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=order_status,
                client_order_id=client_order_id,
                exchange_order_id=order_msg["order_id"],
            )
            self._order_tracker.process_order_update(new_order_update)

    def _process_wallet_event_message(self, wallet_msg: Dict[str, Any]):
        """
        Updates account balances.
        :param wallet_msg: The account balance update message payload
        """
        if "coin" in wallet_msg:  # non-linear
            symbol = wallet_msg["coin"]
        else:  # linear
            symbol = "USDT"
        self._account_balances[symbol] = Decimal(str(wallet_msg["wallet_balance"]))
        self._account_available_balances[symbol] = Decimal(str(wallet_msg["available_balance"]))

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
            Example:
            {{
              "success": true,
              "result": [
                {
                  "name": "BTC-PERP",
                  "baseCurrency": null,
                  "quoteCurrency": null,
                  "quoteVolume24h": 28914.76,
                  "change1h": 0.012,
                  "change24h": 0.0299,
                  "changeBod": 0.0156,
                  "highLeverageFeeExempt": false,
                  "minProvideSize": 0.001,
                  "type": "future",
                  "underlying": "BTC",
                  "enabled": true,
                  "ask": 3949.25,
                  "bid": 3949,
                  "last": 10579.52,
                  "postOnly": false,
                  "price": 10579.52,
                  "priceIncrement": 0.25,
                  "sizeIncrement": 0.0001,
                  "restricted": false,
                  "volumeUsd24h": 28914.76,
                  "largeOrderThreshold": 5000.0,
                  "isEtfMarket": false,
                }
              ]
            }
            """
        trading_pair_rules = exchange_info_dict.get("result", [])
        retval = []
        for rule in filter(ftx_perpetual_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("name"))
                min_trade_size = Decimal(str(rule.get("minProvideSize")))
                price_increment = Decimal(str(rule.get("priceIncrement")))
                size_increment = Decimal(str(rule.get("sizeIncrement")))
                min_quote_amount_increment = price_increment * size_increment
                min_order_value = min_trade_size * price_increment

                retval.append(TradingRule(trading_pair,
                                          min_order_size=min_trade_size,
                                          min_price_increment=price_increment,
                                          min_base_amount_increment=size_increment,
                                          min_quote_amount_increment=min_quote_amount_increment,
                                          min_order_value=min_order_value,
                                          min_notional_size=min_order_value
                                          ))
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(ftx_perpetual_utils.is_exchange_information_valid, exchange_info["result"]):
            mapping[symbol_data["name"]] = symbol_data["name"]
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
                f"Could not resolve the exchange symbols {new_exchange_symbol} and {current_exchange_symbol}")
            mapping.pop(current_exchange_symbol)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        resp_json = await self._api_get(
            path_url=CONSTANTS.FTX_SINGLE_MARKET_PATH.format(symbol),
            limit_id=CONSTANTS.FTX_MARKETS_PATH
        )

        return float(resp_json["result"][0]["last"])

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        data = {
            "leverage": leverage
        }
        resp: Dict[str, Any] = await self._api_post(
            path_url=CONSTANTS.SET_LEVERAGE_PATH_URL,
            data=data,
            is_auth_required=True,
        )
        success = resp.get("success", False)
        msg = resp.get("result")
        return success, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

        params = {
            "future": exchange_symbol
        }
        raw_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.FTX_FUNDING_PAYMENTS,
            params=params,
            is_auth_required=True,
            trading_pair=trading_pair,
        )
        data: Dict[str, Any] = raw_response["result"]

        if not data:
            # An empty funding fee/payment is retrieved.
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
        else:
            funding_rate: Decimal = Decimal(str(data["rate"]))
            payment: Decimal = Decimal(str(data["payment"]))
            timestamp: int = int(pd.Timestamp(data["time"], tz="UTC").timestamp())

        return timestamp, funding_rate, payment

    def _create_trade_update_with_order_fill_data(self, order_fill_msg: Dict[str, Any], order: InFlightOrder):

        # Estimated fee token implemented according to https://help.ftx.com/hc/en-us/articles/360024479432-Fees
        is_maker = order_fill_msg["liquidity"] == "maker"
        if is_maker:
            estimated_fee_token = order.base_asset if order.trade_type == TradeType.BUY else order.quote_asset
        else:
            estimated_fee_token = order.quote_asset

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,
            percent_token=order_fill_msg.get("feeCurrency", estimated_fee_token),
            flat_fees=[TokenAmount(
                amount=Decimal(str(order_fill_msg["fee"])),
                token=order_fill_msg.get("feeCurrency", estimated_fee_token)
            )]
        )
        trade_update = TradeUpdate(
            trade_id=str(order_fill_msg["tradeId"]),
            client_order_id=order.client_order_id,
            exchange_order_id=str(order_fill_msg.get("orderId", order.exchange_order_id)),
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=Decimal(str(order_fill_msg["size"])),
            fill_quote_amount=Decimal(str(order_fill_msg["size"])) * Decimal(str(order_fill_msg["price"])),
            fill_price=Decimal(str(order_fill_msg["price"])),
            fill_timestamp=datetime.fromisoformat(order_fill_msg["time"]).timestamp(),
        )
        return trade_update

    def _create_order_update_with_order_status_data(self, order_status_msg: Dict[str, Any], order: InFlightOrder):
        state = order.current_state
        msg_status = order_status_msg["status"]
        if msg_status == "new":
            state = OrderState.OPEN
        elif msg_status == "open" and (Decimal(str(order_status_msg["filledSize"])) > s_decimal_0):
            state = OrderState.PARTIALLY_FILLED
        elif msg_status == "closed":
            state = (OrderState.CANCELED
                     if Decimal(str(order_status_msg["filledSize"])) == s_decimal_0
                     else OrderState.FILLED)

        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=state,
            client_order_id=order.client_order_id,
            exchange_order_id=str(order_status_msg["id"]),
        )
        return order_update

    @staticmethod
    def _format_ret_code_for_print(ret_code: Union[str, int]) -> str:
        return f"ret_code <{ret_code}>"
