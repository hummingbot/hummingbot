import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.bitmart_perpetual import (
    bitmart_perpetual_constants as CONSTANTS,
    bitmart_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_api_order_book_data_source import (
    BitmartPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_auth import BitmartPerpetualAuth
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_user_stream_data_source import (
    BitmartPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, PriceType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

bpm_logger = None


class BitmartPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            bitmart_perpetual_api_key: str = None,
            bitmart_perpetual_api_secret: str = None,
            bitmart_perpetual_memo: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self.bitmart_perpetual_api_key = bitmart_perpetual_api_key
        self.bitmart_perpetual_secret_key = bitmart_perpetual_api_secret
        self.bitmart_perpetual_memo = bitmart_perpetual_memo
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        self._contract_sizes = {}
        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> BitmartPerpetualAuth:
        return BitmartPerpetualAuth(api_key=self.bitmart_perpetual_api_key,
                                    api_secret=self.bitmart_perpetual_secret_key,
                                    memo=self.bitmart_perpetual_memo,
                                    time_provider=self._time_synchronizer)

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
        return CONSTANTS.SERVER_TIME_PATH_URL

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
        return [PositionMode.HEDGE]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("40039" in error_description
                                        and "The timestamp is invalid" in error_description)
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
        return BitmartPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BitmartPerpetualUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _format_amount_to_size(self, trading_pair, amount: Decimal) -> Decimal:
        return int(amount / self._contract_sizes[trading_pair])

    def _format_size_to_amount(self, trading_pair, size: Decimal) -> Decimal:
        return Decimal(size) * self._contract_sizes[trading_pair]

    @property
    def side_mapping(self):
        return bidict(
            {
                (PositionAction.OPEN, TradeType.BUY): 1,  # buy_open_long
                (PositionAction.CLOSE, TradeType.BUY): 2,  # buy_close_short
                (PositionAction.CLOSE, TradeType.SELL): 3,  # sell_close_long
                (PositionAction.OPEN, TradeType.SELL): 4,  # sell_open_short
            }
        )

    @property
    def mode_mapping(self):
        return bidict(
            {
                OrderType.LIMIT: CONSTANTS.TIME_IN_FORCE_GTC,  # GTC
                OrderType.LIMIT_MAKER: CONSTANTS.TIME_IN_FORCE_MAKER_ONLY  # Maker only
            }
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

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "client_order_id": order_id,
            "symbol": symbol,
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=api_params,
            is_auth_required=True)
        unknown_order_code = cancel_result.get("code") == CONSTANTS.UNKNOWN_ORDER_ERROR_CODE
        unknown_order_msg = cancel_result.get("msg", "") == CONSTANTS.UNKNOWN_ORDER_MESSAGE
        if unknown_order_msg and unknown_order_code:
            self.logger().debug(f"The order {order_id} does not exist on Bitmart Perpetual. "
                                f"No cancelation needed.")
            await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f"{cancel_result.get('code')} - {cancel_result['msg']}")
        return cancel_result.get("code") == CONSTANTS.CODE_OK

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
        price_str = f"{price:f}"
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {
            "symbol": symbol,
            "client_order_id": order_id,
            "type": "market" if order_type == OrderType.MARKET else "limit",
            "side": self.side_mapping.get((position_action, trade_type)),
            "mode": self.mode_mapping.get(order_type),
            "size": self._format_amount_to_size(trading_pair, amount),
        }
        if order_type.is_limit_type():
            api_params["price"] = price_str
        order_result = await self._api_post(
            path_url=CONSTANTS.SUBMIT_ORDER_URL,
            data=api_params,
            is_auth_required=True)
        response_code = order_result.get("code")
        if response_code != 1000:
            raise IOError(f"Error submitting order {order_id}: {order_result['message']}")
        o_id = str(order_result["data"]["order_id"])
        transact_time = self._time_synchronizer.time()
        return o_id, transact_time

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        order_update = await self._api_get(
            path_url=CONSTANTS.ORDER_DETAILS,
            params={
                "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
                "order_id": tracked_order.exchange_order_id
            },
            is_auth_required=True)
        if order_update["code"] != 1000:
            if self._is_request_exception_related_to_time_synchronizer(request_exception=order_update):
                _order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=tracked_order.current_state,
                    client_order_id=tracked_order.client_order_id,
                )
                return _order_update
        order_update_data = order_update.get("data")
        if order_update is not None:
            deal_size = Decimal(order_update_data["deal_size"])
            size = Decimal(order_update_data["size"])
            state = order_update_data["state"]
            order_state = self.get_order_state(size, state, deal_size)
            _order_update: OrderUpdate = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=order_update_data["update_time"] * 1e-3,
                new_state=order_state,
                client_order_id=order_update_data["client_order_id"],
                exchange_order_id=order_update_data["order_id"],
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
                    app_warning_msg="Could not fetch user events from Bitmart. Check API key and network connection.",
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

    @staticmethod
    def get_order_state(size: Decimal, state: int, deal_size: Decimal) -> OrderState:
        """
        Determines the state of an order based on the provided parameters. Valid until Bitmart implements spot order
        states.

        Args:
            size (Decimal): The total size of the order.
            state (int): The state code of the order (e.g., 2 for active, 4 for closed).
            deal_size (Decimal): The size of the order that has been executed.

        Returns:
            OrderState: The determined order state (OPEN, PARTIALLY_FILLED, CANCELED, FILLED).

        Raises:
            UnknownOrderStateException: If the order state is not tracked or does not match any known conditions.
        """
        if state == 2 and deal_size == 0:
            return OrderState.OPEN
        elif state == 2 and (0 < deal_size < size):
            return OrderState.PARTIALLY_FILLED
        elif state == 4 and deal_size < size:
            return OrderState.CANCELED
        elif state == 4 and deal_size == size:
            return OrderState.FILLED
        else:
            raise UnknownOrderStateException(state, size, deal_size)

    async def _process_user_stream_event(self, event_message: Dict[str, Any]):
        event_data = event_message.get("data", {})
        event_group: str = event_message.get("group", "")
        if CONSTANTS.WS_ORDERS_CHANNEL in event_group and bool(event_data):
            order_message = event_data[0].get("order")
            client_order_id = order_message.get("client_order_id", None)
            tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
            position_side = order_message.get("side")
            position_action = self.side_mapping.inv[position_side][0]
            if tracked_order is not None:
                trades_dict = order_message.get("last_trade")
                if trades_dict is not None:
                    trade_id: str = str(trades_dict["lastTradeID"])
                    fee_asset = trades_dict.get("feeCcy", tracked_order.quote_asset)
                    fee_amount = Decimal(trades_dict.get("fee", "0"))
                    flat_fees = [] if fee_amount == Decimal("0") else [TokenAmount(amount=fee_amount, token=fee_asset)]
                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema(),
                        position_action=position_action,
                        percent_token=fee_asset,
                        flat_fees=flat_fees,
                    )
                    fill_base_amount = Decimal(self._format_size_to_amount(tracked_order.trading_pair,
                                                                           trades_dict["fillQty"]))
                    trade_update: TradeUpdate = TradeUpdate(
                        trade_id=trade_id,
                        client_order_id=client_order_id,
                        exchange_order_id=str(order_message["order_id"]),
                        trading_pair=tracked_order.trading_pair,
                        fill_timestamp=order_message["update_time"] * 1e-3,
                        fill_price=Decimal(trades_dict["fillPrice"]),
                        fill_base_amount=fill_base_amount,
                        fill_quote_amount=Decimal(str(fill_base_amount)) * Decimal(trades_dict["fillPrice"]),
                        fee=fee,
                    )
                    self._order_tracker.process_trade_update(trade_update)

            tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
            if tracked_order is not None:
                deal_size = Decimal(order_message["deal_size"])
                size = Decimal(order_message["size"])
                state = order_message["state"]
                order_state = self.get_order_state(size, state, deal_size)
                order_update: OrderUpdate = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=order_message["update_time"] * 1e-3,
                    new_state=order_state,
                    client_order_id=client_order_id,
                    exchange_order_id=str(order_message["order_id"]),
                )

                self._order_tracker.process_order_update(order_update)

        elif CONSTANTS.WS_ACCOUNT_CHANNEL in event_group and bool(event_data):
            asset_name = event_data["currency"]
            self._account_balances[asset_name] = Decimal(event_data["available_balance"]) + Decimal(event_data["frozen_balance"])
            self._account_available_balances[asset_name] = Decimal(event_data["available_balance"])

        elif CONSTANTS.WS_POSITIONS_CHANNEL in event_group and bool(event_data):
            for asset in event_data:
                trading_pair = asset["symbol"]
                try:
                    hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(trading_pair)
                    if hb_trading_pair in self.trading_pairs:
                        position_side = PositionSide["LONG" if asset['position_type'] == 1 else "SHORT"]
                        position = self._perpetual_trading.get_position(hb_trading_pair, position_side)
                        if position is not None:
                            amount = Decimal(asset["hold_volume"])
                            if amount == Decimal("0"):
                                pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
                                self._perpetual_trading.remove_position(pos_key)
                            else:
                                price = self.get_price_by_type(hb_trading_pair, PriceType.MidPrice)
                                bep = Decimal(asset["hold_avg_price"])
                                sign = 1 if position_side == PositionSide.LONG else -1
                                unrealized_pnl = Decimal(str(sign)) * (price / bep - 1)
                                position.update_position(position_side=position_side,
                                                         unrealized_pnl=unrealized_pnl,
                                                         entry_price=bep,
                                                         amount=Decimal(
                                                             "-1") * amount if position_side == PositionSide.SHORT else amount)
                        else:
                            await self._update_positions()
                except KeyError:
                    continue

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        Parameters
        ----------
        exchange_info_dict:
            Trading rules dictionary response from the exchange
        """
        rules: list = exchange_info_dict.get("data", [])
        return_val: list = []
        for rule in rules["symbols"]:
            try:
                if web_utils.is_exchange_information_valid(rule):
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule["symbol"])
                    contract_size = Decimal(rule.get("contract_size"))
                    self._contract_sizes[trading_pair] = contract_size
                    min_order_size_in_contracts = Decimal(rule.get("min_volume"))
                    min_order_size = contract_size * min_order_size_in_contracts
                    step_size = Decimal(rule.get("vol_precision"))
                    tick_size = Decimal(rule.get("price_precision"))
                    last_price = Decimal(rule.get("last_price"))
                    min_notional = Decimal(min_order_size * last_price)
                    collateral_token = rule["quote_currency"]

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
        symbols_data = exchange_info.get("data", {})
        for symbol_data in filter(web_utils.is_exchange_information_valid, symbols_data.get("symbols", [])):
            exchange_symbol = symbol_data["base_currency"] + symbol_data["quote_currency"]
            base = symbol_data["base_currency"]
            quote = symbol_data["quote_currency"]
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
            path_url=CONSTANTS.EXCHANGE_INFO_URL,
            params=params)
        price = float(response["last_price"])
        return price

    async def get_last_traded_prices(self, trading_pairs: List[str] = None) -> Dict[str, float]:
        response = await self._api_get(path_url=CONSTANTS.EXCHANGE_INFO_URL)
        symbol_map = await self.trading_pair_symbol_map()
        last_traded_prices = {
            await self.trading_pair_associated_to_exchange_symbol(ticker["symbol"]): float(ticker["last_price"])
            for ticker in response["data"]["symbols"] if ticker["symbol"] in symbol_map.keys()
        }
        return last_traded_prices

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

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_trade_history(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_balances(self):
        """
        Calls the REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(path_url=CONSTANTS.ASSETS_DETAIL,
                                           is_auth_required=True)
        assets = account_info.get("data", [])
        for asset in assets:
            asset_name = asset.get("currency")
            available_balance = Decimal(asset.get("available_balance"))
            wallet_balance = Decimal(asset.get("equity"))
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
        for position in positions["data"]:
            trading_pair = position.get("symbol")
            try:
                hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(trading_pair)
            except KeyError:
                # Ignore results for which their symbols is not tracked by the connector
                continue
            position_type = position["position_type"]
            position_side = PositionSide["LONG" if position_type == 1 else "SHORT"]
            unrealized_pnl = Decimal(position.get("unrealized_value"))
            entry_price = Decimal(position.get("entry_price"))
            amount = Decimal(position.get("current_amount"))
            leverage = Decimal(position.get("leverage"))
            pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
            if amount != 0:
                _position = Position(
                    trading_pair=await self.trading_pair_associated_to_exchange_symbol(trading_pair),
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=Decimal("-1") * amount if position_side == PositionSide.SHORT else amount,
                    leverage=leverage
                )
                self._perpetual_trading.set_position(pos_key, _position)
            else:
                self._perpetual_trading.remove_position(pos_key)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # since current connector standard reimplemented _update_order_status this method is never reached
        pass

    async def _update_trade_history(self):
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
                for trade in trades["data"]:
                    order_id = trade.get("order_id")
                    if order_id is not None and order_id in order_map:
                        tracked_order: InFlightOrder = order_map.get(order_id)
                        position_side = PositionSide.LONG if trade["side"] == 1 else PositionSide.SHORT
                        position_action = (PositionAction.OPEN
                                           if (tracked_order.trade_type is TradeType.BUY and position_side == "LONG"
                                               or tracked_order.trade_type is TradeType.SELL and position_side == "SHORT")
                                           else PositionAction.CLOSE)
                        quote_asset = trading_pair.split("-")[1]
                        fee_amount = Decimal(trade["paid_fees"])
                        fee = TradeFeeBase.new_perpetual_fee(
                            fee_schema=self.trade_fee_schema(),
                            position_action=position_action,
                            percent_token=quote_asset,
                            flat_fees=[TokenAmount(amount=fee_amount, token=quote_asset)]
                        )
                        fill_base_amount = Decimal(self._format_size_to_amount(tracked_order.trading_pair,
                                                                               trade["vol"]))
                        trade_update: TradeUpdate = TradeUpdate(
                            trade_id=str(trade["trade_id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=trade["order_id"],
                            trading_pair=tracked_order.trading_pair,
                            fill_timestamp=trade["create_time"] * 1e-3,
                            fill_price=Decimal(trade["price"]),
                            fill_base_amount=fill_base_amount,
                            fill_quote_amount=Decimal(str(fill_base_amount)) * Decimal(trade["price"]),
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
                    path_url=CONSTANTS.ORDER_DETAILS,
                    params={
                        "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair),
                        "order_id": order.exchange_order_id
                    },
                    is_auth_required=True,
                    return_err=True,
                )
                for order in tracked_orders
            ]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results: List[Dict[str, Any]] = await safe_gather(*tasks, return_exceptions=True)

            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if client_order_id not in self._order_tracker.all_orders:
                    continue
                if isinstance(order_update, Exception) or order_update["code"] != 1000:
                    not_found_error = (order_update["code"] in (CONSTANTS.UNKNOWN_ORDER_ERROR_CODE,
                                                                CONSTANTS.UNKNOWN_ORDER_ERROR_CODE))
                    if not isinstance(order_update, Exception) and not_found_error:
                        await self._order_tracker.process_order_not_found(client_order_id)
                    else:
                        self.logger().network(
                            f"Error fetching status update for the order {client_order_id}: " f"{order_update}."
                        )
                    continue
                order_update_data = order_update["data"]
                size = Decimal(order_update_data["size"])
                deal_size = Decimal(order_update_data["deal_size"])
                state = order_update_data["state"]
                order_state = self.get_order_state(size, state, deal_size)
                new_order_update: OrderUpdate = OrderUpdate(
                    trading_pair=await self.trading_pair_associated_to_exchange_symbol(order_update_data['symbol']),
                    update_timestamp=order_update_data["update_time"] * 1e-3,
                    new_state=order_state,
                    client_order_id=order_update_data["client_order_id"],
                    exchange_order_id=order_update_data["order_id"],
                )

                self._order_tracker.process_order_update(new_order_update)

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        # TODO: Currently there are no position mode settings in Bitmart
        return True, ""

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        leverage_str = str(leverage)
        # TODO: Check if there is something to handle cross/isolated
        payload = {"symbol": symbol, "leverage": leverage_str, "open_type": "cross"}
        set_leverage = await self._api_post(
            path_url=CONSTANTS.SET_LEVERAGE_URL,
            data=payload,
            is_auth_required=True,
        )
        success = False
        msg = ""
        if set_leverage["code"] == CONSTANTS.CODE_OK:
            success = set_leverage["data"]["leverage"] == leverage_str
        else:
            msg = 'Unable to set leverage'
        return success, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")

        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        payment_response = await self._api_get(
            path_url=CONSTANTS.GET_INCOME_HISTORY_URL,
            params={
                "symbol": exchange_symbol,
                "flow_type": 3,
            },
            is_auth_required=True,
        )
        payment_data = payment_response.get("data")
        funding_info_response = await self._api_get(
            path_url=CONSTANTS.FUNDING_INFO_URL,
            params={
                "symbol": exchange_symbol,
            },
        )
        if bool(payment_data):
            sorted_payment_response = sorted(payment_data, key=lambda a: a["time"], reverse=True)
            funding_payment = sorted_payment_response[0]
            payment = Decimal(funding_payment["amount"])
            timestamp = int(funding_payment["time"])
            funding_rate = Decimal(funding_info_response["data"]["rate_value"])
        return timestamp, funding_rate, payment


class UnknownOrderStateException(Exception):
    """Custom exception for unknown order states."""
    def __init__(self, state, size, deal_size):
        super().__init__(f"Order state {state} with size {size} and deal size {deal_size} not tracked. "
                         f"Please report this to a developer for review.")
