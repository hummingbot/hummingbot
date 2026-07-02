import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.twofinance import (
    twofinance_constants as CONSTANTS,
    twofinance_web_utils as web_utils,
)
from hummingbot.connector.exchange.twofinance.twofinance_api_order_book_data_source import (
    TwoFinanceAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.twofinance.twofinance_api_user_stream_data_source import (
    TwoFinanceAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.twofinance.twofinance_auth import TwoFinanceAuth
from hummingbot.connector.exchange.twofinance.twofinance_matchengine_client import MatchEngineClient
from hummingbot.connector.exchange.twofinance.twofinance_matchengine_schemas import (
    MatchEngineEvent,
    OrderCommand,
    event_order_state,
    to_decimal,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class TwoFinanceExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    SHORT_POLL_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(
        self,
        twofinance_matchengine_bearer_token: str,
        twofinance_engine_id: str,
        twofinance_wallet_id: int,
        twofinance_state_api_url: str = CONSTANTS.REST_URL,
        twofinance_matchengine_ws_url: str = CONSTANTS.WSS_URL,
        twofinance_account_id: str = "",
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        ack_timeout: float = 1.0,
    ):
        self._domain = domain
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._state_api_url = twofinance_state_api_url.rstrip("/")
        self._matchengine_ws_url = twofinance_matchengine_ws_url
        self._bearer_token = (
            twofinance_matchengine_bearer_token.get_secret_value()
            if hasattr(twofinance_matchengine_bearer_token, "get_secret_value")
            else str(twofinance_matchengine_bearer_token)
        )
        self._engine_id = twofinance_engine_id
        self._wallet_id = int(twofinance_wallet_id)
        self._account_id = twofinance_account_id
        self._ack_timeout = ack_timeout
        self._symbol_metadata: Dict[str, Dict[str, Any]] = {}

        super().__init__(balance_asset_limit, rate_limits_share_pct)
        self._matchengine_client = MatchEngineClient(
            api_factory=self._web_assistants_factory,
            ws_url=self._matchengine_ws_url,
            auth_headers=self._auth_headers,
        )

    @property
    def authenticator(self):
        return TwoFinanceAuth(self._bearer_token)

    @property
    def _auth_headers(self) -> Dict[str, str]:
        auth = self.authenticator.authorization_header
        return {"Authorization": auth} if auth else {}

    @property
    def name(self) -> str:
        return self._domain

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.TRADING_RULES_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.SYMBOLS_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return "not found" in str(status_update_exception).lower()

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return "not found" in str(cancelation_exception).lower()

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return TwoFinanceAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
            ws_url=self._matchengine_ws_url,
            rest_url=self._state_api_url,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return TwoFinanceAPIUserStreamDataSource(
            api_factory=self._web_assistants_factory,
            auth_headers=self._auth_headers,
            engine_id=self._engine_id,
            wallet_id=self._wallet_id,
            domain=self._domain,
            ws_url=self._matchengine_ws_url,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> AddedToCostTradeFee:
        return AddedToCostTradeFee(percent=Decimal("0"))

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        command = await self._build_order_command(
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            trade_type=trade_type,
            order_type=order_type,
            price=price,
            time_in_force=kwargs.get("time_in_force"),
        )
        await self._matchengine_client.send_command(command)
        response = await self._matchengine_client.wait_for_ack(order_id, self._ack_timeout)
        if response is not None and not response.accepted:
            raise IOError(response.reason or f"2Finance rejected order {order_id}")
        exchange_order_id = response.order_id if response is not None and response.order_id is not None else None
        if exchange_order_id is None:
            exchange_order_id = await self._matchengine_client.wait_for_exchange_order_id(order_id, self._ack_timeout)
        return exchange_order_id or f"UNKNOWN:{order_id}", self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = await tracked_order.get_exchange_order_id()
        metadata = await self._metadata_for_pair(tracked_order.trading_pair)
        command = OrderCommand(
            client_order_id=order_id,
            engine_id=self._engine_id,
            symbol_id=int(metadata["symbol_id"]),
            market=tracked_order.trading_pair,
            wallet_id=self._wallet_id,
            side="BUY",
            order_type="LIMIT",
            quantity="0",
            operation="DELETE",
            order_id=exchange_order_id,
            idempotency_key=f"{order_id}:cancel",
        )
        await self._matchengine_client.send_command(command)
        return True

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                event = MatchEngineEvent.from_payload(event_message)
                self._matchengine_client.apply_event(event)
                if event.event_type in {"TRADE", "TRADE_EXECUTED", "ORDER_TRADE"}:
                    trade_update = self._trade_update_from_event(event)
                    if trade_update is not None:
                        self._order_tracker.process_trade_update(trade_update)
                order_update = self._order_update_from_event(event)
                if order_update is not None:
                    self._order_tracker.process_order_update(order_update)
                self._process_balance_event(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error processing 2Finance user stream event.")

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        data = (
            exchange_info_dict.get("data", exchange_info_dict)
            if isinstance(exchange_info_dict, dict)
            else exchange_info_dict
        )
        if isinstance(data, dict) and "trading_rules" in data:
            data = data["trading_rules"]
        rules = data.items() if isinstance(data, dict) else enumerate(data if isinstance(data, list) else [])
        trading_rules = []
        for key, item in rules:
            rule = item if isinstance(item, dict) else {}
            trading_pair = web_utils.normalize_trading_pair(
                rule.get("symbol") or rule.get("trading_pair") or rule.get("market") or rule.get("name") or key
            )
            if not trading_pair:
                continue
            trading_rules.append(
                TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=to_decimal(rule.get("min_order_size") or rule.get("min_base_amount") or "0"),
                    min_price_increment=to_decimal(rule.get("tick_size") or rule.get("min_price_increment") or "0"),
                    min_base_amount_increment=to_decimal(
                        rule.get("step_size") or rule.get("min_base_amount_increment") or "0"
                    ),
                    min_notional_size=to_decimal(rule.get("min_notional_size") or rule.get("min_notional") or "0"),
                )
            )
        return trading_rules

    async def _update_balances(self):
        payload = await self._api_get(path_url=CONSTANTS.BALANCES_PATH_URL, is_auth_required=True)
        data = payload.get("data", payload) if isinstance(payload, dict) else payload
        if isinstance(data, dict) and "balances" in data:
            data = data["balances"]
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        iterable = data.items() if isinstance(data, dict) else enumerate(data if isinstance(data, list) else [])
        for asset, balance_payload in iterable:
            balance = balance_payload if isinstance(balance_payload, dict) else {}
            total = to_decimal(balance.get("total") or balance.get("balance") or balance.get("quantity") or "0")
            locked = to_decimal(balance.get("locked") or balance.get("lock_balance") or "0")
            available = to_decimal(balance.get("available") or (total - locked))
            asset_name = str(balance.get("asset") or balance.get("asset_id") or asset)
            self._account_balances[asset_name] = total
            self._account_available_balances[asset_name] = available
            remote_asset_names.add(asset_name)
        for asset_name in local_asset_names.difference(remote_asset_names):
            self._account_balances.pop(asset_name, None)
            self._account_available_balances.pop(asset_name, None)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        payload = await self._api_get(
            path_url=CONSTANTS.ORDER_TRADES_PATH_URL.format(client_order_id=order.client_order_id),
            is_auth_required=True,
        )
        data = payload.get("data", payload) if isinstance(payload, dict) else payload
        if isinstance(data, dict) and "trades" in data:
            data = data["trades"]
        updates = []
        for item in data if isinstance(data, list) else []:
            updates.append(self._trade_update_from_payload(item, order))
        return updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        payload = await self._api_get(
            path_url=CONSTANTS.ORDER_STATUS_PATH_URL.format(client_order_id=tracked_order.client_order_id),
            is_auth_required=True,
        )
        data = payload.get("data", payload) if isinstance(payload, dict) else payload
        state = CONSTANTS.ORDER_STATE.get(str(data.get("status") or "OPEN").upper(), OrderState.OPEN)
        return OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(data.get("order_id") or tracked_order.exchange_order_id),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=state,
            misc_updates=data,
        )

    async def _update_trading_fees(self):
        return None

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        data = exchange_info.get("data", exchange_info) if isinstance(exchange_info, dict) else exchange_info
        if isinstance(data, dict) and "symbols" in data:
            data = data["symbols"]
        items = data.items() if isinstance(data, dict) else enumerate(data if isinstance(data, list) else [])
        mapping = bidict()
        self._symbol_metadata.clear()
        for key, item in items:
            symbol = item if isinstance(item, dict) else {}
            trading_pair = web_utils.normalize_trading_pair(
                symbol.get("symbol") or symbol.get("trading_pair") or symbol.get("market") or symbol.get("name") or key
            )
            if not trading_pair:
                continue
            exchange_symbol = str(
                symbol.get("exchange_symbol") or symbol.get("name") or symbol.get("symbol_id") or trading_pair
            )
            mapping[exchange_symbol] = trading_pair
            self._symbol_metadata[trading_pair] = {
                **symbol,
                "exchange_symbol": exchange_symbol,
                "symbol_id": int(symbol.get("symbol_id") or symbol.get("id") or 0),
            }
        self._set_trading_pair_symbol_map(mapping)

    async def _api_request_url(self, path_url: str, is_auth_required: bool = False) -> str:
        return self._state_api_url + path_url

    async def _api_get(self, *args, **kwargs):
        kwargs["method"] = RESTMethod.GET
        return await self._api_request(*args, **kwargs)

    async def _api_post(self, *args, **kwargs):
        kwargs["method"] = RESTMethod.POST
        return await self._api_request(*args, **kwargs)

    async def _metadata_for_pair(self, trading_pair: str) -> Dict[str, Any]:
        if trading_pair not in self._symbol_metadata:
            await self._initialize_trading_pair_symbol_map()
        if trading_pair not in self._symbol_metadata:
            raise KeyError(f"2Finance symbol metadata not found for {trading_pair}")
        return self._symbol_metadata[trading_pair]

    async def _build_order_command(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        time_in_force: Optional[str],
    ) -> OrderCommand:
        metadata = await self._metadata_for_pair(trading_pair)
        return OrderCommand(
            client_order_id=order_id,
            engine_id=self._engine_id,
            symbol_id=int(metadata["symbol_id"]),
            market=trading_pair,
            wallet_id=self._wallet_id,
            side="BUY" if trade_type is TradeType.BUY else "SELL",
            order_type="MARKET" if order_type is OrderType.MARKET else "LIMIT",
            quantity=amount,
            price=None if order_type is OrderType.MARKET else price,
            time_in_force=time_in_force if time_in_force in {"GTC", "IOC", "FOK", "AON"} else None,
            idempotency_key=order_id,
        )

    def _order_update_from_event(self, event: MatchEngineEvent) -> Optional[OrderUpdate]:
        new_state = event_order_state(event)
        if new_state is None:
            return None
        client_order_id = event.payload.get("client_order_id")
        exchange_order_id = event.payload.get("order_id") or event.payload.get("new_order_id")
        if client_order_id is None and exchange_order_id is not None:
            client_order_id = self._matchengine_client.orders_by_exchange_id.get(str(exchange_order_id))
        if client_order_id is None:
            return None
        return OrderUpdate(
            trading_pair=web_utils.normalize_trading_pair(event.market or event.payload.get("market")),
            update_timestamp=self._timestamp(event),
            new_state=new_state,
            client_order_id=str(client_order_id),
            exchange_order_id=str(exchange_order_id) if exchange_order_id is not None else None,
            misc_updates={"event_id": event.event_id, "sequence": event.sequence, **event.payload},
        )

    def _trade_update_from_event(self, event: MatchEngineEvent) -> Optional[TradeUpdate]:
        exchange_order_id = (
            event.payload.get("order_id") or event.payload.get("taker_order_id") or event.payload.get("maker_order_id")
        )
        client_order_id = event.payload.get("client_order_id")
        if client_order_id is None and exchange_order_id is not None:
            client_order_id = self._matchengine_client.orders_by_exchange_id.get(str(exchange_order_id))
        if client_order_id is None or exchange_order_id is None:
            return None
        tracked_order = self._order_tracker.all_fillable_orders.get(str(client_order_id))
        trading_pair = web_utils.normalize_trading_pair(
            event.market or (tracked_order.trading_pair if tracked_order is not None else "")
        )
        return TradeUpdate(
            trade_id=str(event.payload.get("trade_id") or event.event_id),
            client_order_id=str(client_order_id),
            exchange_order_id=str(exchange_order_id),
            trading_pair=trading_pair,
            fill_timestamp=self._timestamp(event),
            fill_price=to_decimal(event.payload.get("price") or "0"),
            fill_base_amount=to_decimal(event.payload.get("quantity") or event.payload.get("amount") or "0"),
            fill_quote_amount=to_decimal(event.payload.get("quote_quantity") or "0")
            or to_decimal(event.payload.get("quantity") or event.payload.get("amount") or "0")
            * to_decimal(event.payload.get("price") or "0"),
            fee=self._fee_from_payload(event.payload),
        )

    def _trade_update_from_payload(self, payload: Dict[str, Any], order: InFlightOrder) -> TradeUpdate:
        quantity = to_decimal(payload.get("quantity") or payload.get("amount") or "0")
        price = to_decimal(payload.get("price") or "0")
        return TradeUpdate(
            trade_id=str(payload.get("trade_id") or payload.get("id")),
            client_order_id=order.client_order_id,
            exchange_order_id=str(payload.get("order_id") or order.exchange_order_id),
            trading_pair=order.trading_pair,
            fill_timestamp=float(payload.get("timestamp") or self.current_timestamp),
            fill_price=price,
            fill_base_amount=quantity,
            fill_quote_amount=to_decimal(payload.get("quote_quantity") or quantity * price),
            fee=self._fee_from_payload(payload),
        )

    def _fee_from_payload(self, payload: Dict[str, Any]) -> TradeFeeBase:
        fee_amount = to_decimal(payload.get("fee_amount") or payload.get("fee") or "0")
        fee_asset = payload.get("fee_asset") or payload.get("asset")
        flat_fees = [TokenAmount(str(fee_asset), fee_amount)] if fee_asset and fee_amount > Decimal("0") else []
        return AddedToCostTradeFee(percent=Decimal("0"), flat_fees=flat_fees)

    def _process_balance_event(self, event: MatchEngineEvent):
        if event.event_type not in {"BALANCE_UPDATED", "BALANCE_SNAPSHOT"}:
            return
        asset = event.payload.get("asset") or event.payload.get("asset_id")
        if asset is None:
            return
        total = to_decimal(
            event.payload.get("total") or event.payload.get("balance") or self._account_balances.get(str(asset), "0")
        )
        locked = to_decimal(event.payload.get("locked") or event.payload.get("lock_balance") or "0")
        available = to_decimal(event.payload.get("available") or (total - locked))
        self._account_balances[str(asset)] = total
        self._account_available_balances[str(asset)] = available

    @staticmethod
    def _timestamp(event: MatchEngineEvent) -> float:
        if event.timestamp_ns is not None:
            return event.timestamp_ns / 1_000_000_000
        return float(event.payload.get("timestamp") or 0)
