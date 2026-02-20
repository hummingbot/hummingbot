import asyncio
import hashlib
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.decibel_perpetual import (
    decibel_perpetual_constants as CONSTANTS,
    decibel_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_api_order_book_data_source import (
    DecibelPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_user_stream_data_source import (
    DecibelPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DecibelPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Hummingbot connector for Decibel perpetual derivatives exchange.

    Decibel is an on-chain DEX on Aptos blockchain.
    - REST API is read-only (market data + account queries)
    - Order placement/cancellation is via on-chain Aptos transactions
    - WebSocket for real-time updates
    """

    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            decibel_perpetual_api_key: str = None,
            decibel_perpetual_account_address: str = None,
            decibel_perpetual_subaccount_address: str = None,
            decibel_perpetual_private_key: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self.decibel_api_key = decibel_perpetual_api_key
        self.decibel_account_address = decibel_perpetual_account_address
        self.decibel_subaccount_address = decibel_perpetual_subaccount_address
        self.decibel_private_key = decibel_perpetual_private_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        # Maps market symbol name to on-chain market address
        self.market_name_to_address: Dict[str, str] = {}
        # Maps market address to symbol name
        self.market_address_to_name: Dict[str, str] = {}
        # Aptos client for on-chain transactions
        self._aptos_client = None
        self._aptos_account = None
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[DecibelPerpetualAuth]:
        if self._trading_required:
            return DecibelPerpetualAuth(
                api_key=self.decibel_api_key,
                account_address=self.decibel_account_address,
                subaccount_address=self.decibel_subaccount_address,
                private_key=self.decibel_private_key,
            )
        return None

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
        return CONSTANTS.MARKETS_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.MARKETS_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True  # On-chain cancel is synchronous (waits for tx confirmation)

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    async def start(self, *args, **kwargs):
        """Initialize Aptos client for on-chain transactions."""
        await super().start(*args, **kwargs)
        if self._trading_required:
            await self._initialize_aptos_client()

    async def _initialize_aptos_client(self):
        """Initialize the Aptos SDK client and account for on-chain transactions."""
        try:
            from aptos_sdk.account import Account
            from aptos_sdk.async_client import RestClient

            node_url = web_utils.aptos_node_url(self._domain)
            self._aptos_client = RestClient(node_url)
            self._aptos_account = Account.load_key(self.decibel_private_key)
            self.logger().info("Aptos client initialized for on-chain transactions")
        except ImportError:
            self.logger().error(
                "aptos-sdk not installed. Install with: pip install aptos-sdk. "
                "On-chain order placement will not work."
            )
        except Exception as e:
            self.logger().error(f"Failed to initialize Aptos client: {e}")

    async def _make_network_check_request(self):
        await self._api_get(path_url=self.check_network_request_path, params={})

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return DecibelPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return DecibelPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _api_get(self, path_url: str, params: Dict[str, Any] = None, **kwargs) -> Any:
        """Make an authenticated GET request to the Decibel REST API."""
        url = web_utils.rest_url(path_url, self._domain)
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=url,
            params=params or {},
            method=RESTMethod.GET,
            throttler_limit_id=path_url,
            is_auth_required=kwargs.get("is_auth_required", True),
        )
        return response

    # ========== Trading Rules ==========

    async def _make_trading_rules_request(self) -> Any:
        return await self._api_get(path_url=CONSTANTS.MARKETS_URL, params={})

    async def _make_trading_pairs_request(self) -> Any:
        return await self._api_get(path_url=CONSTANTS.MARKETS_URL, params={})

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    async def _update_trading_rules(self):
        markets_data = await self._api_get(path_url=CONSTANTS.MARKETS_URL, params={})
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=markets_data)
        trading_rules_list = await self._format_trading_rules(markets_data)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _initialize_trading_pair_symbol_map(self):
        try:
            markets_data = await self._api_get(path_url=CONSTANTS.MARKETS_URL, params={})
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=markets_data)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    async def _format_trading_rules(self, exchange_info: Any) -> List[TradingRule]:
        """
        Parse market data into TradingRule objects.
        Expected format: list of market objects with fields like:
        {
            "market_address": "0x...",
            "symbol": "BTC-PERP",
            "base_currency": "BTC",
            "quote_currency": "USD",
            "tick_size": "0.1",
            "step_size": "0.001",
            "min_order_size": "0.001",
            ...
        }
        """
        return_val = []
        markets = exchange_info if isinstance(exchange_info, list) else exchange_info.get("markets", [])

        for market in markets:
            try:
                symbol = market.get("symbol", "")
                market_address = market.get("market_address", market.get("address", ""))
                base = market.get("base_currency", symbol.split("-")[0] if "-" in symbol else symbol)
                quote = market.get("quote_currency", CONSTANTS.CURRENCY)

                self.market_name_to_address[symbol] = market_address
                self.market_address_to_name[market_address] = symbol

                trading_pair = combine_to_hb_trading_pair(base, quote)

                tick_size = Decimal(str(market.get("tick_size", "0.01")))
                step_size = Decimal(str(market.get("step_size", "0.001")))
                min_order_size = Decimal(str(market.get("min_order_size", "0.001")))
                collateral_token = quote

                return_val.append(
                    TradingRule(
                        trading_pair,
                        min_base_amount_increment=step_size,
                        min_price_increment=tick_size,
                        min_order_size=min_order_size,
                        buy_order_collateral_token=collateral_token,
                        sell_order_collateral_token=collateral_token,
                    )
                )
            except Exception:
                self.logger().error(
                    f"Error parsing the trading pair rule {market}. Skipping.",
                    exc_info=True,
                )
        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Any):
        mapping = bidict()
        markets = exchange_info if isinstance(exchange_info, list) else exchange_info.get("markets", [])

        for market in markets:
            symbol = market.get("symbol", "")
            market_address = market.get("market_address", market.get("address", ""))
            base = market.get("base_currency", symbol.split("-")[0] if "-" in symbol else symbol)
            quote = market.get("quote_currency", CONSTANTS.CURRENCY)

            self.market_name_to_address[symbol] = market_address
            self.market_address_to_name[market_address] = symbol

            trading_pair = combine_to_hb_trading_pair(base, quote)
            if trading_pair not in mapping.inverse:
                mapping[symbol] = trading_pair

        self._set_trading_pair_symbol_map(mapping)

    # ========== Order Placement (On-Chain) ==========

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type=OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode("utf-8"))
        hex_order_id = f"0x{md5.hexdigest()}"

        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            price = self.quantize_order_price(
                trading_pair, reference_price * Decimal(1 + CONSTANTS.MARKET_ORDER_SLIPPAGE)
            )

        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
                order_id=hex_order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return hex_order_id

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode("utf-8"))
        hex_order_id = f"0x{md5.hexdigest()}"

        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            price = self.quantize_order_price(
                trading_pair, reference_price * Decimal(1 - CONSTANTS.MARKET_ORDER_SLIPPAGE)
            )

        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
                order_id=hex_order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return hex_order_id

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
        """
        Place order via on-chain Aptos transaction.
        Uses the aptos-sdk to build and submit a transaction calling
        {PACKAGE}::dex_accounts_entry::place_order_to_subaccount
        """
        if self._aptos_client is None or self._aptos_account is None:
            raise IOError("Aptos client not initialized. Cannot place on-chain orders.")

        ex_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        market_address = self.market_name_to_address.get(ex_symbol, ex_symbol)

        # Convert price and size to 9-decimal integer format
        price_u64 = web_utils.price_to_int(float(price))
        size_u64 = web_utils.size_to_int(float(amount))

        is_buy = trade_type is TradeType.BUY

        # Determine time-in-force
        tif = 0  # GTC
        if order_type is OrderType.LIMIT_MAKER:
            tif = 1  # PostOnly
        elif order_type is OrderType.MARKET:
            tif = 2  # IOC

        is_reduce_only = position_action == PositionAction.CLOSE

        try:
            payload = {
                "function": f"{CONSTANTS.DECIBEL_PACKAGE_ADDRESS}::{CONSTANTS.PLACE_ORDER_FUNCTION}",
                "type_arguments": [],
                "function_arguments": [
                    self.decibel_subaccount_address,  # subaccount_addr
                    market_address,                    # market_addr
                    str(price_u64),                    # price with 9 decimals
                    str(size_u64),                     # size with 9 decimals
                    is_buy,                            # is_buy
                    tif,                               # timeInForce
                    is_reduce_only,                    # isReduceOnly
                    order_id,                          # client_order_id
                    None,                              # stopPrice
                    None,                              # tpTriggerPrice
                    None,                              # tpLimitPrice
                    None,                              # slTriggerPrice
                    None,                              # slLimitPrice
                    None,                              # builderAddr
                    None,                              # builderFee
                ],
            }

            txn = await self._aptos_client.build_transaction(
                sender=self._aptos_account.address(),
                payload=payload,
            )
            signed_txn = self._aptos_client.sign_transaction(self._aptos_account, txn)
            tx_result = await self._aptos_client.submit_and_wait_for_transaction(signed_txn)

            tx_hash = tx_result.get("hash", "")
            if not tx_result.get("success", False):
                vm_status = tx_result.get("vm_status", "unknown error")
                raise IOError(f"Transaction failed: {vm_status}")

            self.logger().info(f"Order {order_id} placed on-chain. TX: {tx_hash}")
            return (tx_hash, self.current_timestamp)

        except Exception as e:
            raise IOError(f"Error placing on-chain order {order_id}: {e}")

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancel order via on-chain Aptos transaction.
        Uses {PACKAGE}::dex_accounts_entry::cancel_order
        """
        if self._aptos_client is None or self._aptos_account is None:
            raise IOError("Aptos client not initialized. Cannot cancel on-chain orders.")

        ex_symbol = await self.exchange_symbol_associated_to_pair(
            trading_pair=tracked_order.trading_pair
        )
        market_address = self.market_name_to_address.get(ex_symbol, ex_symbol)

        try:
            exchange_order_id = tracked_order.exchange_order_id or order_id

            payload = {
                "function": f"{CONSTANTS.DECIBEL_PACKAGE_ADDRESS}::{CONSTANTS.CANCEL_ORDER_FUNCTION}",
                "type_arguments": [],
                "function_arguments": [
                    self.decibel_subaccount_address,  # subaccount
                    market_address,                    # market
                    exchange_order_id,                 # order_id
                ],
            }

            txn = await self._aptos_client.build_transaction(
                sender=self._aptos_account.address(),
                payload=payload,
            )
            signed_txn = self._aptos_client.sign_transaction(self._aptos_account, txn)
            tx_result = await self._aptos_client.submit_and_wait_for_transaction(signed_txn)

            if not tx_result.get("success", False):
                vm_status = tx_result.get("vm_status", "unknown error")
                raise IOError(f"Cancel transaction failed: {vm_status}")

            self.logger().info(f"Order {order_id} canceled on-chain.")
            return True

        except Exception as e:
            self.logger().error(f"Error canceling order {order_id}: {e}")
            await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f"Error canceling order {order_id}: {e}")

    # ========== Status Polling ==========

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_trade_history(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_order_status(self):
        await self._update_orders()

    async def _update_lost_orders_status(self):
        await self._update_lost_orders()

    async def _update_trade_history(self):
        orders = list(self._order_tracker.all_fillable_orders.values())
        all_fillable_orders = self._order_tracker.all_fillable_orders_by_exchange_order_id
        if len(orders) > 0:
            try:
                trade_history = await self._api_get(
                    path_url=CONSTANTS.TRADE_HISTORY_URL,
                    params={"account": self.decibel_account_address},
                )
                trades = trade_history if isinstance(trade_history, list) else trade_history.get("trades", [])
                for trade_fill in trades:
                    self._process_trade_rs_event_message(
                        order_fill=trade_fill,
                        all_fillable_order=all_fillable_orders,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().warning(f"Failed to fetch trade updates. Error: {e}", exc_info=e)

    def _process_trade_rs_event_message(self, order_fill: Dict[str, Any], all_fillable_order):
        exchange_order_id = str(order_fill.get("order_id", ""))
        fillable_order = all_fillable_order.get(exchange_order_id)
        if fillable_order is not None:
            fee_asset = fillable_order.quote_asset
            fill_price = Decimal(str(order_fill.get("price", "0")))
            fill_size = Decimal(str(order_fill.get("size", order_fill.get("quantity", "0"))))

            position_action = (
                PositionAction.OPEN
                if order_fill.get("side", "").lower() in ("buy", "open_long", "open_short")
                else PositionAction.CLOSE
            )

            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=Decimal(str(order_fill.get("fee", "0"))), token=fee_asset)],
            )

            trade_update = TradeUpdate(
                trade_id=str(order_fill.get("trade_id", order_fill.get("id", ""))),
                client_order_id=fillable_order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=fillable_order.trading_pair,
                fee=fee,
                fill_base_amount=fill_size,
                fill_quote_amount=fill_price * fill_size,
                fill_price=fill_price,
                fill_timestamp=order_fill.get("timestamp", time.time()),
            )
            self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        pass

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        client_order_id = tracked_order.client_order_id
        try:
            exchange_order_id = tracked_order.exchange_order_id or await tracked_order.get_exchange_order_id()
        except asyncio.TimeoutError:
            exchange_order_id = None

        order_data = await self._api_get(
            path_url=CONSTANTS.ORDERS_URL,
            params={"order_id": exchange_order_id or client_order_id},
        )

        order_info = order_data if isinstance(order_data, dict) else order_data[0] if order_data else {}
        current_state = order_info.get("status", "open")
        _exchange_order_id = str(tracked_order.exchange_order_id or order_info.get("order_id", ""))

        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_info.get("timestamp", time.time()),
            new_state=CONSTANTS.ORDER_STATE.get(current_state, CONSTANTS.ORDER_STATE["open"]),
            client_order_id=client_order_id,
            exchange_order_id=_exchange_order_id,
        )

    async def _handle_update_error_for_active_order(self, order: InFlightOrder, error: Exception):
        try:
            raise error
        except (asyncio.TimeoutError, KeyError):
            self.logger().debug(
                f"Tracked order {order.client_order_id} does not have an exchange id. "
                f"Attempting fetch in next polling interval."
            )
            await self._order_tracker.process_order_not_found(order.client_order_id)
        except asyncio.CancelledError:
            raise
        except Exception as request_error:
            self.logger().warning(
                f"Error fetching status update for the active order {order.client_order_id}: {request_error}.",
            )
            await self._order_tracker.process_order_not_found(order.client_order_id)

    # ========== Balances ==========

    async def _update_balances(self):
        try:
            account_info = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_OVERVIEWS_URL,
                params={"account": self.decibel_account_address},
            )
            overview = account_info if isinstance(account_info, dict) else (account_info[0] if account_info else {})
            quote = CONSTANTS.CURRENCY
            self._account_balances[quote] = Decimal(str(overview.get("equity", "0")))
            self._account_available_balances[quote] = Decimal(str(overview.get("available_balance", overview.get("withdrawable", "0"))))
        except Exception as e:
            self.logger().warning(f"Error updating balances: {e}")

    # ========== Positions ==========

    async def _update_positions(self):
        try:
            positions_data = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_POSITIONS_URL,
                params={"account": self.decibel_account_address},
            )
            positions = positions_data if isinstance(positions_data, list) else positions_data.get("positions", [])

            processed_pairs = set()
            for position in positions:
                try:
                    ex_symbol = position.get("market", position.get("symbol", ""))
                    # Resolve market address to symbol if needed
                    if ex_symbol in self.market_address_to_name:
                        ex_symbol = self.market_address_to_name[ex_symbol]

                    hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(ex_symbol)
                    processed_pairs.add(hb_trading_pair)

                    size = Decimal(str(position.get("size", "0")))
                    position_side = PositionSide.LONG if size > 0 else PositionSide.SHORT
                    unrealized_pnl = Decimal(str(position.get("unrealized_pnl", "0")))
                    entry_price = Decimal(str(position.get("entry_price", "0")))
                    leverage = Decimal(str(position.get("leverage", "1")))

                    pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
                    if size != 0:
                        _position = Position(
                            trading_pair=hb_trading_pair,
                            position_side=position_side,
                            unrealized_pnl=unrealized_pnl,
                            entry_price=entry_price,
                            amount=size,
                            leverage=leverage,
                        )
                        self._perpetual_trading.set_position(pos_key, _position)
                    else:
                        self._perpetual_trading.remove_position(pos_key)
                except KeyError:
                    continue

            if not positions:
                keys = list(self._perpetual_trading.account_positions.keys())
                for key in keys:
                    self._perpetual_trading.remove_position(key)

        except Exception as e:
            self.logger().warning(f"Error updating positions: {e}")

    # ========== Fees ==========

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

    # ========== Position Mode & Leverage ==========

    async def _get_position_mode(self) -> Optional[PositionMode]:
        return PositionMode.ONEWAY

    async def _trading_pair_position_mode_set(
        self, mode: PositionMode, trading_pair: str
    ) -> Tuple[bool, str]:
        if mode != PositionMode.ONEWAY:
            return False, "Decibel only supports the ONEWAY position mode."
        return True, ""

    async def _set_trading_pair_leverage(
        self, trading_pair: str, leverage: int
    ) -> Tuple[bool, str]:
        # Decibel may handle leverage differently on-chain
        # For now, leverage is set per-order or per-account on the exchange side
        self.logger().info(f"Leverage setting for {trading_pair} to {leverage}x noted. "
                           f"Actual leverage is managed on-chain.")
        return True, ""

    # ========== Funding ==========

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        try:
            exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
            funding_data = await self._api_get(
                path_url=CONSTANTS.FUNDING_RATE_HISTORY_URL,
                params={"account": self.decibel_account_address},
            )
            history = funding_data if isinstance(funding_data, list) else funding_data.get("history", [])

            # Filter for this market
            relevant = [
                f for f in history
                if f.get("market", f.get("symbol", "")) == exchange_symbol
                   or self.market_name_to_address.get(exchange_symbol, "") == f.get("market", "")
            ]

            if not relevant:
                return 0, Decimal("-1"), Decimal("-1")

            latest = relevant[0]  # Assuming sorted by time descending
            payment = Decimal(str(latest.get("payment", "0")))
            funding_rate = Decimal(str(latest.get("funding_rate", "0")))
            timestamp = latest.get("timestamp", 0)

            if payment != Decimal("0"):
                return timestamp, funding_rate, payment
            return 0, Decimal("-1"), Decimal("-1")

        except Exception as e:
            self.logger().debug(f"Error fetching funding info for {trading_pair}: {e}")
            return 0, Decimal("-1"), Decimal("-1")

    # ========== User Stream Event Listener ==========

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
                    app_warning_msg="Could not fetch user events from Decibel. Check API key and network.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                if not isinstance(event_message, dict):
                    if event_message is asyncio.CancelledError:
                        raise asyncio.CancelledError
                    raise Exception(event_message)

                topic = event_message.get("topic", "")
                data = event_message.get("data", {})

                if topic.startswith(CONSTANTS.WS_ORDER_UPDATE_TOPIC):
                    orders = data if isinstance(data, list) else [data]
                    for order_msg in orders:
                        self._process_order_message(order_msg)

                elif topic.startswith(CONSTANTS.WS_ACCOUNT_POSITIONS_TOPIC):
                    # Position updates handled via polling
                    pass

                elif topic.startswith(CONSTANTS.WS_ACCOUNT_OVERVIEW_TOPIC):
                    # Balance updates handled via polling
                    pass

                elif topic.startswith(CONSTANTS.WS_ACCOUNT_OPEN_ORDERS_TOPIC):
                    # Open order updates
                    orders = data if isinstance(data, list) else [data]
                    for order_msg in orders:
                        self._process_order_message(order_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True
                )
                await self._sleep(5.0)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        client_order_id = str(order_msg.get("client_order_id", order_msg.get("cloid", "")))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return

        current_state = order_msg.get("status", "open")
        exchange_order_id = str(order_msg.get("order_id", order_msg.get("id", "")))
        tracked_order.update_exchange_order_id(exchange_order_id)

        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_msg.get("timestamp", time.time()),
            new_state=CONSTANTS.ORDER_STATE.get(current_state, CONSTANTS.ORDER_STATE["open"]),
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
        )
        self._order_tracker.process_order_update(order_update=order_update)

    async def _process_trade_message(self, trade: Dict[str, Any], client_order_id: Optional[str] = None):
        exchange_order_id = str(trade.get("order_id", ""))
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

        if tracked_order is None:
            all_orders = self._order_tracker.all_fillable_orders
            _cli_tracked = [o for o in all_orders.values() if exchange_order_id == o.exchange_order_id]
            if not _cli_tracked:
                return
            tracked_order = _cli_tracked[0]

        fee_asset = tracked_order.quote_asset
        fill_price = Decimal(str(trade.get("price", "0")))
        fill_size = Decimal(str(trade.get("size", trade.get("quantity", "0"))))

        position_action = (
            PositionAction.OPEN
            if trade.get("side", "").lower() in ("buy", "open")
            else PositionAction.CLOSE
        )

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=[TokenAmount(amount=Decimal(str(trade.get("fee", "0"))), token=fee_asset)],
        )

        trade_update = TradeUpdate(
            trade_id=str(trade.get("trade_id", trade.get("id", ""))),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=trade.get("timestamp", time.time()),
            fill_price=fill_price,
            fill_base_amount=fill_size,
            fill_quote_amount=fill_price * fill_size,
            fee=fee,
        )
        self._order_tracker.process_trade_update(trade_update)

    # ========== Price Helpers ==========

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        res = []
        try:
            prices_data = await self._api_get(path_url=CONSTANTS.PRICES_URL, params={})
            prices = prices_data if isinstance(prices_data, list) else prices_data.get("prices", [])
            for price_info in prices:
                symbol = price_info.get("symbol", self.market_address_to_name.get(price_info.get("market", ""), ""))
                res.append({
                    "symbol": symbol,
                    "price": str(price_info.get("mark_price", price_info.get("mid_price", "0"))),
                })
        except Exception as e:
            self.logger().error(f"Error fetching all pairs prices: {e}")
        return res

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        try:
            ex_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        except KeyError:
            ex_symbol = trading_pair.split("-")[0]

        try:
            prices_data = await self._api_get(path_url=CONSTANTS.PRICES_URL, params={})
            prices = prices_data if isinstance(prices_data, list) else prices_data.get("prices", [])
            market_address = self.market_name_to_address.get(ex_symbol, "")

            for price_info in prices:
                if price_info.get("symbol") == ex_symbol or price_info.get("market") == market_address:
                    return float(price_info.get("mark_price", price_info.get("mid_price", 0)))
        except Exception as e:
            self.logger().error(f"Error fetching last traded price for {trading_pair}: {e}")

        raise RuntimeError(f"Price not found for trading_pair={trading_pair}")

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        d_price = Decimal(round(float(f"{price:.5g}"), 6))
        return d_price
