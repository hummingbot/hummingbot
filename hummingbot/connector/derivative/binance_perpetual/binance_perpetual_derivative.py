import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.binance_perpetual import (
    binance_perpetual_constants as CONSTANTS,
    binance_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_api_order_book_data_source import (
    BinancePerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_auth import BinancePerpetualAuth
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_user_stream_data_source import (
    BinancePerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

bpm_logger = None


class BinancePerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            binance_perpetual_api_key: str = None,
            binance_perpetual_api_secret: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self.binance_perpetual_api_key = binance_perpetual_api_key
        self.binance_perpetual_secret_key = binance_perpetual_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> BinancePerpetualAuth:
        return BinancePerpetualAuth(self.binance_perpetual_api_key, self.binance_perpetual_secret_key,
                                    self._time_synchronizer)

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
        return CONSTANTS.BROKER_ID

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
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 600

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self):
        """
        This method needs to be overridden to provide the accurate information depending on the exchange.
        """
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(
            status_update_exception
        ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(
            cancelation_exception
        ) and CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BinancePerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BinancePerpetualUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

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
        """
        Update fees information from the exchange
        """
        pass

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_fills_from_trades(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "origClientOrderId": order_id,
            "symbol": symbol,
        }
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_URL,
            params=api_params,
            is_auth_required=True)
        if cancel_result.get("code") == -2011 and "Unknown order sent." == cancel_result.get("msg", ""):
            self.logger().debug(f"The order {order_id} does not exist on Binance Perpetuals. "
                                f"No cancelation needed.")
            await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f"{cancel_result.get('code')} - {cancel_result['msg']}")
        if cancel_result.get("status") == "CANCELED":
            return True
        return False

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

        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {"symbol": symbol,
                      "side": "BUY" if trade_type is TradeType.BUY else "SELL",
                      "quantity": amount_str,
                      "type": "MARKET" if order_type is OrderType.MARKET else "LIMIT",
                      "newClientOrderId": order_id
                      }
        if order_type.is_limit_type():
            api_params["price"] = price_str
        if order_type == OrderType.LIMIT:
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC
        if order_type == OrderType.LIMIT_MAKER:
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTX
        if self._position_mode == PositionMode.HEDGE:
            if position_action == PositionAction.OPEN:
                api_params["positionSide"] = "LONG" if trade_type is TradeType.BUY else "SHORT"
            else:
                api_params["positionSide"] = "SHORT" if trade_type is TradeType.BUY else "LONG"
        try:
            order_result = await self._api_post(
                path_url=CONSTANTS.ORDER_URL,
                data=api_params,
                is_auth_required=True)
            o_id = str(order_result["orderId"])
            transact_time = order_result["updateTime"] * 1e-3
        except IOError as e:
            error_description = str(e)
            is_server_overloaded = ("status is 503" in error_description
                                    and "Unknown error, please check your request or try again later." in error_description)
            if is_server_overloaded:
                o_id = "UNKNOWN"
                transact_time = time.time()
            else:
                raise
        return o_id, transact_time

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            exchange_order_id = await order.get_exchange_order_id()
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                params={
                    "symbol": trading_pair,
                },
                is_auth_required=True)

            for trade in all_fills_response:
                order_id = str(trade.get("orderId"))
                if order_id == exchange_order_id:
                    position_side = trade["positionSide"]
                    position_action = (PositionAction.OPEN
                                       if (order.trade_type is TradeType.BUY and position_side == "LONG"
                                           or order.trade_type is TradeType.SELL and position_side == "SHORT")
                                       else PositionAction.CLOSE)
                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema(),
                        position_action=position_action,
                        percent_token=trade["commissionAsset"],
                        flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
                    )
                    trade_update: TradeUpdate = TradeUpdate(
                        trade_id=str(trade["id"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=trade["orderId"],
                        trading_pair=order.trading_pair,
                        fill_timestamp=trade["time"] * 1e-3,
                        fill_price=Decimal(trade["price"]),
                        fill_base_amount=Decimal(trade["qty"]),
                        fill_quote_amount=Decimal(trade["quoteQty"]),
                        fee=fee,
                    )
                    trade_updates.append(trade_update)

        except asyncio.TimeoutError:
            raise IOError(f"Skipped order update with order fills for {order.client_order_id} "
                          "- waiting for exchange order id.")

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        order_update = await self._api_get(
            path_url=CONSTANTS.ORDER_URL,
            params={
                "symbol": trading_pair,
                "origClientOrderId": tracked_order.client_order_id
            },
            is_auth_required=True)
        if "code" in order_update:
            if self._is_request_exception_related_to_time_synchronizer(request_exception=order_update):
                _order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=tracked_order.current_state,
                    client_order_id=tracked_order.client_order_id,
                )
                return _order_update
        _order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,

            update_timestamp=order_update["updateTime"] * 1e-3,
            new_state=CONSTANTS.ORDER_STATE[order_update["status"]],
            client_order_id=order_update["clientOrderId"],
            exchange_order_id=order_update["orderId"],
        )
        return _order_update

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Binance. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Wait for new messages from _user_stream_tracker.user_stream queue and processes them according to their
        message channels. The respective UserStreamDataSource queues these messages.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                await self._process_user_stream_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop: {e}", exc_info=True)
                await self._sleep(5.0)

    async def _process_user_stream_event(self, event_message: Dict[str, Any]):
        event_type = event_message.get("e")
        if event_type == "ORDER_TRADE_UPDATE":
            order_message = event_message.get("o")
            client_order_id = order_message.get("c", None)
            tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
            if tracked_order is not None:
                trade_id: str = str(order_message["t"])

                if trade_id != "0":  # Indicates that there has been a trade

                    fee_asset = order_message.get("N", tracked_order.quote_asset)
                    fee_amount = Decimal(order_message.get("n", "0"))
                    position_side = order_message.get("ps", "LONG")
                    position_action = (PositionAction.OPEN
                                       if (tracked_order.trade_type is TradeType.BUY and position_side == "LONG"
                                           or tracked_order.trade_type is TradeType.SELL and position_side == "SHORT")
                                       else PositionAction.CLOSE)
                    flat_fees = [] if fee_amount == Decimal("0") else [TokenAmount(amount=fee_amount, token=fee_asset)]

                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema(),
                        position_action=position_action,
                        percent_token=fee_asset,
                        flat_fees=flat_fees,
                    )

                    trade_update: TradeUpdate = TradeUpdate(
                        trade_id=trade_id,
                        client_order_id=client_order_id,
                        exchange_order_id=str(order_message["i"]),
                        trading_pair=tracked_order.trading_pair,
                        fill_timestamp=order_message["T"] * 1e-3,
                        fill_price=Decimal(order_message["L"]),
                        fill_base_amount=Decimal(order_message["l"]),
                        fill_quote_amount=Decimal(order_message["L"]) * Decimal(order_message["l"]),
                        fee=fee,
                    )
                    self._order_tracker.process_trade_update(trade_update)

            tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
            if tracked_order is not None:
                order_update: OrderUpdate = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=event_message["T"] * 1e-3,
                    new_state=CONSTANTS.ORDER_STATE[order_message["X"]],
                    client_order_id=client_order_id,
                    exchange_order_id=str(order_message["i"]),
                )

                self._order_tracker.process_order_update(order_update)

        elif event_type == "ACCOUNT_UPDATE":
            update_data = event_message.get("a", {})
            # update balances
            for asset in update_data.get("B", []):
                asset_name = asset["a"]
                self._account_balances[asset_name] = Decimal(asset["wb"])
                self._account_available_balances[asset_name] = Decimal(asset["cw"])

            # update position
            for asset in update_data.get("P", []):
                trading_pair = asset["s"]
                try:
                    hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(trading_pair)
                except KeyError:
                    # Ignore results for which their symbols is not tracked by the connector
                    continue

                side = PositionSide[asset['ps']]
                position = self._perpetual_trading.get_position(hb_trading_pair, side)
                if position is not None:
                    amount = Decimal(asset["pa"])
                    if amount == Decimal("0"):
                        pos_key = self._perpetual_trading.position_key(hb_trading_pair, side)
                        self._perpetual_trading.remove_position(pos_key)
                    else:
                        position.update_position(position_side=PositionSide[asset["ps"]],
                                                 unrealized_pnl=Decimal(asset["up"]),
                                                 entry_price=Decimal(asset["ep"]),
                                                 amount=Decimal(asset["pa"]))
                else:
                    await self._update_positions()
        elif event_type == "MARGIN_CALL":
            positions = event_message.get("p", [])
            total_maint_margin_required = Decimal(0)
            # total_pnl = 0
            negative_pnls_msg = ""
            for position in positions:
                trading_pair = position["s"]
                try:
                    hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(trading_pair)
                except KeyError:
                    # Ignore results for which their symbols is not tracked by the connector
                    continue
                existing_position = self._perpetual_trading.get_position(hb_trading_pair, PositionSide[position['ps']])
                if existing_position is not None:
                    existing_position.update_position(position_side=PositionSide[position["ps"]],
                                                      unrealized_pnl=Decimal(position["up"]),
                                                      amount=Decimal(position["pa"]))
                total_maint_margin_required += Decimal(position.get("mm", "0"))
                if float(position.get("up", 0)) < 1:
                    negative_pnls_msg += f"{hb_trading_pair}: {position.get('up')}, "
            self.logger().warning("Margin Call: Your position risk is too high, and you are at risk of "
                                  "liquidation. Close your positions or add additional margin to your wallet.")
            self.logger().info(f"Margin Required: {total_maint_margin_required}. "
                               f"Negative PnL assets: {negative_pnls_msg}.")

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        Parameters
        ----------
        exchange_info_dict:
            Trading rules dictionary response from the exchange
        """
        rules: list = exchange_info_dict.get("symbols", [])
        return_val: list = []
        for rule in rules:
            try:
                if web_utils.is_exchange_information_valid(rule):
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule["symbol"])
                    filters = rule["filters"]
                    filt_dict = {fil["filterType"]: fil for fil in filters}

                    min_order_size = Decimal(filt_dict.get("LOT_SIZE").get("minQty"))
                    step_size = Decimal(filt_dict.get("LOT_SIZE").get("stepSize"))
                    tick_size = Decimal(filt_dict.get("PRICE_FILTER").get("tickSize"))
                    min_notional = Decimal(filt_dict.get("MIN_NOTIONAL").get("notional"))
                    collateral_token = rule["marginAsset"]

                    return_val.append(
                        TradingRule(
                            trading_pair,
                            min_order_size=min_order_size,
                            min_price_increment=Decimal(tick_size),
                            min_base_amount_increment=Decimal(step_size),
                            min_notional_size=Decimal(min_notional),
                            buy_order_collateral_token=collateral_token,
                            sell_order_collateral_token=collateral_token,
                        )
                    )
            except Exception as e:
                self.logger().error(
                    f"Error parsing the trading pair rule {rule}. Error: {e}. Skipping...", exc_info=True
                )
        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(web_utils.is_exchange_information_valid, exchange_info.get("symbols", [])):
            exchange_symbol = symbol_data["pair"]
            base = symbol_data["baseAsset"]
            quote = symbol_data["quoteAsset"]
            trading_pair = combine_to_hb_trading_pair(base, quote)
            if trading_pair in mapping.inverse:
                self._resolve_trading_pair_symbols_duplicate(mapping, exchange_symbol, base, quote)
            else:
                mapping[exchange_symbol] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {"symbol": exchange_symbol}
        response = await self._api_get(
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL,
            params=params)
        price = float(response["lastPrice"])
        return price

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

    async def _update_balances(self):
        """
        Calls the REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(path_url=CONSTANTS.ACCOUNT_INFO_URL,
                                           is_auth_required=True)
        assets = account_info.get("assets")
        for asset in assets:
            asset_name = asset.get("asset")
            available_balance = Decimal(asset.get("availableBalance"))
            wallet_balance = Decimal(asset.get("walletBalance"))
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = wallet_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        positions = await self._api_get(path_url=CONSTANTS.POSITION_INFORMATION_URL,
                                        is_auth_required=True)
        for position in positions:
            trading_pair = position.get("symbol")
            try:
                hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(trading_pair)
            except KeyError:
                # Ignore results for which their symbols is not tracked by the connector
                continue
            position_side = PositionSide[position.get("positionSide")]
            unrealized_pnl = Decimal(position.get("unRealizedProfit"))
            entry_price = Decimal(position.get("entryPrice"))
            amount = Decimal(position.get("positionAmt"))
            leverage = Decimal(position.get("leverage"))
            pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
            if amount != 0:
                _position = Position(
                    trading_pair=await self.trading_pair_associated_to_exchange_symbol(trading_pair),
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=leverage
                )
                self._perpetual_trading.set_position(pos_key, _position)
            else:
                self._perpetual_trading.remove_position(pos_key)

    async def _update_order_fills_from_trades(self):
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            trading_pairs_to_order_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {})
            for order in self._order_tracker.active_orders.values():
                trading_pairs_to_order_map[order.trading_pair][order.exchange_order_id] = order
            trading_pairs = list(trading_pairs_to_order_map.keys())
            tasks = [
                self._api_get(
                    path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                    params={"symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)},
                    is_auth_required=True,
                )
                for trading_pair in trading_pairs
            ]
            self.logger().debug(f"Polling for order fills of {len(tasks)} trading_pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for trades, trading_pair in zip(results, trading_pairs):
                order_map = trading_pairs_to_order_map.get(trading_pair)
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    order_id = str(trade.get("orderId"))
                    if order_id in order_map:
                        tracked_order: InFlightOrder = order_map.get(order_id)
                        position_side = trade["positionSide"]
                        position_action = (PositionAction.OPEN
                                           if (tracked_order.trade_type is TradeType.BUY and position_side == "LONG"
                                               or tracked_order.trade_type is TradeType.SELL and position_side == "SHORT")
                                           else PositionAction.CLOSE)
                        fee = TradeFeeBase.new_perpetual_fee(
                            fee_schema=self.trade_fee_schema(),
                            position_action=position_action,
                            percent_token=trade["commissionAsset"],
                            flat_fees=[TokenAmount(amount=Decimal(trade["commission"]), token=trade["commissionAsset"])]
                        )
                        trade_update: TradeUpdate = TradeUpdate(
                            trade_id=str(trade["id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=trade["orderId"],
                            trading_pair=tracked_order.trading_pair,
                            fill_timestamp=trade["time"] * 1e-3,
                            fill_price=Decimal(trade["price"]),
                            fill_base_amount=Decimal(trade["qty"]),
                            fill_quote_amount=Decimal(trade["quoteQty"]),
                            fee=fee,
                        )
                        self._order_tracker.process_trade_update(trade_update)

    async def _update_order_status(self):
        """
        Calls the REST API to get order/trade updates for each in-flight order.
        """
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._order_tracker.active_orders) > 0:
            tracked_orders = list(self._order_tracker.active_orders.values())
            tasks = [
                self._api_get(
                    path_url=CONSTANTS.ORDER_URL,
                    params={
                        "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair),
                        "origClientOrderId": order.client_order_id
                    },
                    is_auth_required=True,
                    return_err=True,
                )
                for order in tracked_orders
            ]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if client_order_id not in self._order_tracker.all_orders:
                    continue
                if isinstance(order_update, Exception) or "code" in order_update:
                    if not isinstance(order_update, Exception) and \
                            (order_update["code"] == -2013 or order_update["msg"] == "Order does not exist."):
                        await self._order_tracker.process_order_not_found(client_order_id)
                    else:
                        self.logger().network(
                            f"Error fetching status update for the order {client_order_id}: " f"{order_update}."
                        )
                    continue

                new_order_update: OrderUpdate = OrderUpdate(
                    trading_pair=await self.trading_pair_associated_to_exchange_symbol(order_update['symbol']),
                    update_timestamp=order_update["updateTime"] * 1e-3,
                    new_state=CONSTANTS.ORDER_STATE[order_update["status"]],
                    client_order_id=order_update["clientOrderId"],
                    exchange_order_id=order_update["orderId"],
                )

                self._order_tracker.process_order_update(new_order_update)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        # To-do: ensure there's no active order or contract before changing position mode
        if self._position_mode is None:
            response = await self._api_get(
                path_url=CONSTANTS.CHANGE_POSITION_MODE_URL,
                is_auth_required=True,
                limit_id=CONSTANTS.GET_POSITION_MODE_LIMIT_ID,
                return_err=True
            )
            self._position_mode = PositionMode.HEDGE if response.get("dualSidePosition") else PositionMode.ONEWAY

        return self._position_mode

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        msg = ""
        success = True
        initial_mode = await self._get_position_mode()
        if initial_mode != mode:
            params = {
                "dualSidePosition": True if mode == PositionMode.HEDGE else False,
            }
            response = await self._api_post(
                path_url=CONSTANTS.CHANGE_POSITION_MODE_URL,
                data=params,
                is_auth_required=True,
                limit_id=CONSTANTS.POST_POSITION_MODE_LIMIT_ID,
                return_err=True
            )
            if not (response["msg"] == "success" and response["code"] == 200):
                success = False
                return success, str(response)
            self._position_mode = mode
        return success, msg

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        params = {'symbol': symbol, 'leverage': leverage}
        set_leverage = await self._api_post(
            path_url=CONSTANTS.SET_LEVERAGE_URL,
            data=params,
            is_auth_required=True,
        )
        success = False
        msg = ""
        if set_leverage["leverage"] == leverage:
            success = True
        else:
            msg = 'Unable to set leverage'
        return success, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        payment_response = await self._api_get(
            path_url=CONSTANTS.GET_INCOME_HISTORY_URL,
            params={
                "symbol": exchange_symbol,
                "incomeType": "FUNDING_FEE",
            },
            is_auth_required=True,
        )
        funding_info_response = await self._api_get(
            path_url=CONSTANTS.MARK_PRICE_URL,
            params={
                "symbol": exchange_symbol,
            },
        )
        sorted_payment_response = sorted(payment_response, key=lambda a: a.get('time', 0), reverse=True)
        if len(sorted_payment_response) < 1:
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
            return timestamp, funding_rate, payment
        funding_payment = sorted_payment_response[0]
        _payment = Decimal(funding_payment["income"])
        funding_rate = Decimal(funding_info_response["lastFundingRate"])
        timestamp = funding_payment["time"]
        if _payment != Decimal("0"):
            payment = _payment
        else:
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
        return timestamp, funding_rate, payment
