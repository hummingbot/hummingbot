import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS, lighter_web_utils as web_utils
from hummingbot.connector.exchange.lighter.lighter_api_order_book_data_source import LighterAPIOrderBookDataSource
from hummingbot.connector.exchange.lighter.lighter_api_user_stream_data_source import LighterAPIUserStreamDataSource
from hummingbot.connector.exchange.lighter.lighter_api_utils import (
    account_index_from_account,
    decimal_to_exchange_int,
    extract_account_snapshot,
    market_info_from_raw,
    markets_by_exchange_symbol,
    markets_by_id,
    markets_by_trading_pair,
    normalize_timestamp_to_seconds,
    order_state_from_order_data,
    own_trade_details,
    spot_markets_from_exchange_info,
    trading_pair_symbol_map,
)
from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_numeric_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterExchange(ExchangePyBase):
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 60.0

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        lighter_l1_address: str = None,
        lighter_account_index: int = None,
        lighter_api_key_index: int = None,
        lighter_api_private_key: str = None,
        lighter_account_limit: str = "Standard",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._l1_address = lighter_l1_address
        self._account_index = int(lighter_account_index) if lighter_account_index not in (None, "") else None
        self._api_key_index = int(lighter_api_key_index) if lighter_api_key_index not in (None, "") else None
        self._api_private_key = lighter_api_private_key
        self._api_account_limit = lighter_account_limit
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs or []
        self._domain = domain
        self._nonce_creator = NonceCreator.for_milliseconds()
        self._markets_by_id = {}
        self._markets_by_trading_pair = {}
        self._markets_by_exchange_symbol = {}
        self._tx_lock = asyncio.Lock()
        # Serializes the lazy account/signer/auth bootstrap so concurrent callers can't each
        # rebuild the authenticated web-assistants factory and race the user-stream tracker.
        self._account_ready_lock = asyncio.Lock()
        self._signer_client = self._create_signer_client() if trading_required and self._account_index is not None else None
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def account_index(self) -> int:
        return self._account_index

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[LighterAuth]:
        if self._trading_required and self._signer_client is not None:
            return LighterAuth(self._signer_client, api_key_index=self._api_key_index)
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.generate_account_limit(self._api_account_limit)

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
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    async def _make_network_check_request(self):
        await self._api_get(path_url=self.check_network_request_path)

    async def start_network(self):
        if self.is_trading_required:
            await self._ensure_account_ready()
        await super().start_network()

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type=OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = self._new_client_order_id()
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return order_id

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = self._new_client_order_id()
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return order_id

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        exchange_info = await self._api_get(
            path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL,
            params={"filter": "all"},
        )
        prices = []
        for market in spot_markets_from_exchange_info(exchange_info):
            prices.append({"symbol": market.exchange_symbol, "price": str(market.raw_info["last_trade_price"])})
        return prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    async def _make_trading_rules_request(self) -> Any:
        return await self._api_get(
            path_url=self.trading_rules_request_path,
            params={"filter": "all"},
        )

    async def _make_trading_pairs_request(self) -> Any:
        return await self._make_trading_rules_request()

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LighterAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LighterAPIUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _status_polling_loop_fetch_updates(self):
        await self._ensure_account_ready()
        await safe_gather(self._update_trade_history(), self._update_orders(), self._update_balances())

    async def _update_order_status(self):
        await self._update_orders()

    async def _update_lost_orders_status(self):
        await self._update_lost_orders()

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
        await self._ensure_account_ready()
        market = self.market_info_for_trading_pair(trading_pair)
        price = self._effective_order_price(
            trading_pair=trading_pair,
            trade_type=trade_type,
            order_type=order_type,
            price=price,
        )
        base_amount = decimal_to_exchange_int(amount, market.size_decimals)
        price_int = decimal_to_exchange_int(price, market.price_decimals)
        client_order_index = int(order_id)

        async with self._tx_lock:
            if order_type is OrderType.MARKET:
                _, tx_response, error = await self._signer_client.create_market_order(
                    market_index=market.market_id,
                    client_order_index=client_order_index,
                    base_amount=base_amount,
                    avg_execution_price=price_int,
                    is_ask=trade_type is TradeType.SELL,
                )
            else:
                tif = self._signer_client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME
                if order_type is OrderType.LIMIT_MAKER:
                    tif = self._signer_client.ORDER_TIME_IN_FORCE_POST_ONLY
                _, tx_response, error = await self._signer_client.create_order(
                    market_index=market.market_id,
                    client_order_index=client_order_index,
                    base_amount=base_amount,
                    price=price_int,
                    is_ask=trade_type is TradeType.SELL,
                    order_type=self._signer_client.ORDER_TYPE_LIMIT,
                    time_in_force=tif,
                )

        if error is not None:
            raise IOError(f"Error submitting Lighter order {order_id}: {error}")
        if not self._is_tx_response_success(tx_response):
            raise IOError(f"Error submitting Lighter order {order_id}: {tx_response}")
        return order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        await self._ensure_account_ready()
        market = self.market_info_for_trading_pair(tracked_order.trading_pair)
        order_data = await self._find_order(tracked_order=tracked_order, include_inactive=True)
        if order_data is None:
            raise IOError(f"{CONSTANTS.ORDER_NOT_EXIST_MESSAGE}: {order_id}")

        async with self._tx_lock:
            _, tx_response, error = await self._signer_client.cancel_order(
                market_index=market.market_id,
                order_index=int(order_data["order_id"]),
            )
        if error is not None:
            raise IOError(f"Error cancelling Lighter order {order_id}: {error}")
        if not self._is_tx_response_success(tx_response):
            raise IOError(f"Error cancelling Lighter order {order_id}: {tx_response}")
        return True

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        return build_trade_fee(
            exchange=self.name,
            is_maker=is_maker if is_maker is not None else order_type is OrderType.LIMIT_MAKER,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )

    async def _update_trading_fees(self):
        return

    async def _update_trade_history(self):
        if not self._order_tracker.all_fillable_orders:
            return
        await self._ensure_account_ready()

        market_ids = {
            self.market_info_for_trading_pair(order.trading_pair).market_id
            for order in self._order_tracker.all_fillable_orders.values()
        }
        for market_id in market_ids:
            response = await self._api_get(
                path_url=CONSTANTS.TRADES_PATH_URL,
                params={
                    "sort_by": "timestamp",
                    "sort_dir": "desc",
                    "limit": 100,
                    "account_index": self._account_index,
                    "market_id": market_id,
                },
                is_auth_required=True,
            )
            for trade in response.get("trades", []):
                trade_update = self._trade_update_from_trade(trade)
                if trade_update is not None:
                    self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        return []

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        order_data = await self._find_order(tracked_order=tracked_order, include_inactive=True)
        if order_data is None:
            # Lighter's REST endpoints may not have indexed a just-submitted order yet.
            # Within the grace window, report it as still open rather than not-found, so the
            # order tracker doesn't escalate a live order to "lost".
            age = self.current_timestamp - tracked_order.creation_timestamp
            if age < CONSTANTS.ORDER_NOT_FOUND_GRACE_PERIOD:
                return OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=tracked_order.current_state,
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                )
            raise IOError(f"{CONSTANTS.ORDER_NOT_EXIST_MESSAGE}: {tracked_order.client_order_id}")
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=normalize_timestamp_to_seconds(
                order_data.get("updated_at", order_data.get("transaction_time"))
            ),
            new_state=order_state_from_order_data(order_data),
            client_order_id=str(order_data["client_order_id"]),
            exchange_order_id=str(order_data["order_id"]),
        )

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_response = await self._api_get(
            path_url=CONSTANTS.BALANCE_PATH_URL,
            params=self._account_lookup_params(),
        )
        account = extract_account_snapshot(
            account_response, account_index=self._account_index, l1_address=self._l1_address
        )
        self._set_account_index_from_account(account)
        for asset in account.get("assets", []):
            asset_name = str(asset["symbol"]).upper()
            total_balance = self._safe_decimal(asset.get("balance", asset.get("margin_balance", "0")))
            locked_balance = self._safe_decimal(asset.get("locked_balance", "0"))
            self._account_balances[asset_name] = total_balance
            self._account_available_balances[asset_name] = total_balance - locked_balance
            remote_asset_names.add(asset_name)

        for asset_name in local_asset_names.difference(remote_asset_names):
            del self._account_balances[asset_name]
            del self._account_available_balances[asset_name]

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        market = self.market_info_for_trading_pair(trading_pair)
        response = await self._api_get(
            path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL,
            params={"market_id": market.market_id},
        )
        refreshed_market = spot_markets_from_exchange_info(response)[0]
        return float(Decimal(str(refreshed_market.raw_info["last_trade_price"])))

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                channel = str(event_message.get("channel", ""))
                if channel.startswith(f"{CONSTANTS.ACCOUNT_ALL_ORDERS_CHANNEL}:"):
                    self._process_order_events(event_message.get("orders", {}))
                elif channel.startswith(f"{CONSTANTS.ACCOUNT_ALL_TRADES_CHANNEL}:"):
                    self._process_trade_events(event_message.get("trades", {}))
                elif channel.startswith(f"{CONSTANTS.ACCOUNT_ALL_ASSETS_CHANNEL}:"):
                    self._process_balance_events(event_message.get("assets", {}))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in Lighter user stream listener.", exc_info=True)
                await self._sleep(5.0)

    def _parse_spot_markets(self, exchange_info: Dict[str, Any], log_errors: bool) -> List[Any]:
        markets = []
        for raw_market in exchange_info.get("spot_order_book_details", []):
            if not web_utils.is_exchange_information_valid(raw_market):
                continue
            try:
                markets.append(market_info_from_raw(raw_market))
            except Exception:
                if log_errors:
                    self.logger().exception(f"Error parsing the trading pair rule {raw_market}. Skipping.")
        self._markets_by_id = markets_by_id(markets)
        self._markets_by_trading_pair = markets_by_trading_pair(markets)
        self._markets_by_exchange_symbol = markets_by_exchange_symbol(markets)
        return markets

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        markets = self._parse_spot_markets(exchange_info_dict, log_errors=True)
        return [market.trading_rule() for market in markets]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        markets = self._parse_spot_markets(exchange_info, log_errors=False)
        self._set_trading_pair_symbol_map(trading_pair_symbol_map(markets))

    def market_info_for_trading_pair(self, trading_pair: str):
        if trading_pair not in self._markets_by_trading_pair:
            available = sorted(self._markets_by_trading_pair.keys())
            raise ValueError(
                f"{trading_pair} is not a Lighter spot market. "
                f"Lighter spot pairs available: {available or '(none loaded)'}. "
                f"Note: most pairs on Lighter (including XRP) only exist as perpetuals — "
                f"use the lighter_perpetual connector instead."
            )
        return self._markets_by_trading_pair[trading_pair]

    def market_info_for_market_id(self, market_id: int):
        return self._markets_by_id[int(market_id)]

    def _new_client_order_id(self) -> str:
        return str(
            get_new_numeric_client_order_id(
                nonce_creator=self._nonce_creator,
                max_id_bit_count=CONSTANTS.MAX_CLIENT_ORDER_ID_BIT_COUNT,
            )
        )

    def _effective_order_price(
        self,
        trading_pair: str,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
    ) -> Decimal:
        if order_type is not OrderType.MARKET:
            return price
        if price.is_nan():
            reference_price = self.get_mid_price(trading_pair)
            multiplier = Decimal("1") + CONSTANTS.MARKET_ORDER_SLIPPAGE
            if trade_type is TradeType.SELL:
                multiplier = Decimal("1") - CONSTANTS.MARKET_ORDER_SLIPPAGE
            price = reference_price * multiplier
        return self.quantize_order_price(trading_pair, price)

    def _create_signer_client(self):
        if self._account_index is None or self._api_key_index is None or self._api_private_key is None:
            raise ValueError(
                "Lighter trading requires an L1 address or account index, plus API key index and API private key."
            )
        try:
            from lighter import SignerClient
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "The lighter-sdk package is required to use the Lighter connector."
            ) from exc
        return SignerClient(
            url=web_utils.public_rest_url(domain=self._domain),
            account_index=self._account_index,
            api_private_keys={self._api_key_index: self._api_private_key},
        )

    async def _find_order(self, tracked_order: InFlightOrder, include_inactive: bool) -> Optional[Dict[str, Any]]:
        await self._ensure_account_ready()
        market = self.market_info_for_trading_pair(tracked_order.trading_pair)
        active_orders = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_ACTIVE_ORDERS_PATH_URL,
            params={
                "account_index": self._account_index,
                "market_id": market.market_id,
            },
            is_auth_required=True,
        )
        order = self._match_order(tracked_order=tracked_order, orders=active_orders.get("orders", []))
        if order is not None or not include_inactive:
            return order

        inactive_orders = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_INACTIVE_ORDERS_PATH_URL,
            params={
                "account_index": self._account_index,
                "market_id": market.market_id,
                "limit": 100,
            },
            is_auth_required=True,
        )
        return self._match_order(tracked_order=tracked_order, orders=inactive_orders.get("orders", []))

    def _account_lookup_params(self) -> Dict[str, Any]:
        if self._account_index is not None:
            return {"by": CONSTANTS.ACCOUNT_LOOKUP_BY_INDEX, "value": self._account_index, "active_only": "true"}
        if self._l1_address is not None:
            return {"by": CONSTANTS.ACCOUNT_LOOKUP_BY_L1_ADDRESS, "value": self._l1_address, "active_only": "true"}
        raise ValueError("Lighter requires an L1 address or account index to look up account balances.")

    def _set_account_index_from_account(self, account: Dict[str, Any]):
        if self._account_index is None:
            self._account_index = account_index_from_account(account)

    async def _ensure_account_ready(self):
        if not self.is_trading_required:
            return
        async with self._account_ready_lock:
            if self._markets_by_exchange_symbol == {}:
                await self._update_trading_rules()
            if self._account_index is None:
                account_response = await self._api_get(
                    path_url=CONSTANTS.BALANCE_PATH_URL,
                    params=self._account_lookup_params(),
                )
                account = extract_account_snapshot(account_response, l1_address=self._l1_address)
                self._set_account_index_from_account(account)
            if self._signer_client is None:
                self._signer_client = self._create_signer_client()
                self._auth = self.authenticator
                self._web_assistants_factory = self._create_web_assistants_factory()
                self._user_stream_tracker = self._create_user_stream_tracker()

    @staticmethod
    def _match_order(tracked_order: InFlightOrder, orders: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for order in orders:
            if str(order.get("client_order_id", "")) == tracked_order.client_order_id:
                return order
            if tracked_order.exchange_order_id is not None and str(order.get("order_id", "")) == tracked_order.exchange_order_id:
                return order
        return None

    def _process_order_events(self, order_payload: Any):
        if isinstance(order_payload, dict):
            groups = order_payload.values()
        else:
            groups = [order_payload]
        for group in groups:
            if isinstance(group, dict):
                group = [group]
            if not isinstance(group, list):
                continue
            for order in group:
                client_order_id = str(order.get("client_order_id", ""))
                if client_order_id == "":
                    continue
                tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                if tracked_order is None:
                    continue
                order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=normalize_timestamp_to_seconds(
                        order.get("updated_at", order.get("transaction_time"))
                    ),
                    new_state=order_state_from_order_data(order),
                    client_order_id=client_order_id,
                    exchange_order_id=str(order.get("order_id")),
                )
                self._order_tracker.process_order_update(order_update)

    def _process_trade_events(self, trade_payload: Any):
        if isinstance(trade_payload, dict):
            groups = trade_payload.values()
        else:
            groups = [trade_payload]
        for trades in groups:
            if isinstance(trades, dict):
                trades = [trades]
            if not isinstance(trades, list):
                continue
            for trade in trades:
                trade_update = self._trade_update_from_trade(trade)
                if trade_update is not None:
                    self._order_tracker.process_trade_update(trade_update)

    def _process_balance_events(self, assets: Dict[str, Dict[str, Any]]):
        if not isinstance(assets, dict):
            return
        self._account_balances.clear()
        self._account_available_balances.clear()
        for asset in assets.values():
            asset_name = str(asset["symbol"]).upper()
            total_balance = self._safe_decimal(asset.get("balance", asset.get("margin_balance", "0")))
            locked_balance = self._safe_decimal(asset.get("locked_balance", "0"))
            self._account_balances[asset_name] = total_balance
            self._account_available_balances[asset_name] = total_balance - locked_balance

    def _trade_update_from_trade(self, trade: Dict[str, Any]) -> Optional[TradeUpdate]:
        details = own_trade_details(trade, account_index=self._account_index)
        if details is None:
            return None

        trade_type, client_order_id, exchange_order_id, is_maker = details
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        if tracked_order is None and exchange_order_id:
            tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)
        if tracked_order is None:
            return None

        market = self.market_info_for_market_id(int(trade["market_id"]))
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=trade_type,
            percent=market.maker_fee if is_maker else market.taker_fee,
        )
        price = Decimal(str(trade["price"]))
        size = Decimal(str(trade["size"]))
        return TradeUpdate(
            trade_id=str(trade["trade_id"]),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=normalize_timestamp_to_seconds(trade.get("transaction_time")),
            fill_price=price,
            fill_base_amount=size,
            fill_quote_amount=price * size,
            fee=fee,
            is_taker=not is_maker,
        )

    @staticmethod
    def _safe_decimal(value: Any) -> Decimal:
        return Decimal(str(value if value is not None else "0"))

    @staticmethod
    def _extract_tx_code(tx_response: Any) -> Optional[int]:
        if tx_response is None:
            return None
        if isinstance(tx_response, dict):
            code = tx_response.get("code")
            if code is not None:
                try:
                    return int(code)
                except (TypeError, ValueError):
                    return None
        if hasattr(tx_response, "code"):
            try:
                return int(getattr(tx_response, "code"))
            except (TypeError, ValueError):
                return None
        return None

    def _is_tx_response_success(self, tx_response: Any) -> bool:
        code = self._extract_tx_code(tx_response)
        if code is None:
            return True
        return code == 200
