import asyncio
import hashlib
import math
import time
from decimal import Decimal
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from bidict import bidict

import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_web_utils as web_utils
from hummingbot.connector.constants import DAY
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_order_book_data_source import (
    LighterPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth import LighterPerpetualAuth
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_user_stream_data_source import (
    LighterPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, PriceType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")


class LighterPerpetualPriceRecord(NamedTuple):
    """
    Price record for the specific trading pair

    :param timestamp: the timestamp of the price (in seconds)
    :param index_price: the index price
    :param mark_price: the mark price
    """
    timestamp: float
    index_price: Decimal
    mark_price: Decimal


class LighterPerpetualDerivative(PerpetualDerivativePyBase):

    web_utils = web_utils

    TRADING_FEES_INTERVAL = DAY
    EMPTY_MARKET_DATA_WARNING_INTERVAL = 30.0
    _CLIENT_ORDER_INDEX_MAX = (1 << 48) - 1
    _CLIENT_ORDER_INDEX_TIME_MULTIPLIER = 140

    def __init__(
        self,
        lighter_perpetual_api_key: str,
        lighter_perpetual_api_secret: str,
        lighter_perpetual_account_index: str,
        lighter_perpetual_api_key_index: str = "",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
    ):
        self.api_key = lighter_perpetual_api_key
        self.api_secret = lighter_perpetual_api_secret
        self.account_index = lighter_perpetual_account_index
        self.api_key_index = lighter_perpetual_api_key_index
        self.api_config_key = self.api_key
        self.user_wallet_public_key = self.account_index

        configured_api_key_index = next(
            (
                str(int(str(candidate).strip()))
                for candidate in (
                    lighter_perpetual_api_key_index,
                    lighter_perpetual_api_secret,
                    lighter_perpetual_api_key,
                )
                if self._is_int_string(candidate)
            ),
            "",
        )
        self.api_key_index = configured_api_key_index
        if not self.api_config_key:
            self.api_config_key = configured_api_key_index

        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs

        self._prices: Dict[str, Optional[LighterPerpetualPriceRecord]] = {
            trading_pair: None for trading_pair in trading_pairs
        }

        self._order_history_last_poll_timestamp: Dict[str, float] = {}
        self._market_id_by_symbol: Dict[str, int] = {}
        self._size_decimals_by_symbol: Dict[str, int] = {}
        self._price_decimals_by_symbol: Dict[str, int] = {}
        self._lighter_signer_client = None
        self._signer_request_lock = asyncio.Lock()

        self._fee_tier = 0
        self._last_client_order_index: int = 0
        # Maps our client_order_index (str) -> exchange-assigned order_index (str)
        # Populated by WS account_all order updates and REST active-order queries.
        self._client_order_index_to_order_index: Dict[str, str] = {}
        self._last_empty_order_book_warning_timestamp: Dict[str, float] = {}
        self._last_no_candle_warning_timestamp: Dict[str, float] = {}

        super().__init__(balance_asset_limit=balance_asset_limit, rate_limits_share_pct=rate_limits_share_pct)

    @staticmethod
    def _client_order_index_from_order_id(order_id: str) -> int:
        digest = hashlib.sha256(order_id.encode()).digest()
        return int.from_bytes(digest[:8], byteorder="big", signed=False) & 0x7FFFFFFFFFFFFFFF

    def _allocate_client_order_index(self) -> int:
        """Allocate a unique client order index using current timestamp as base.

        Time-based allocation: base = int(time_ms) * TIME_MULTIPLIER.
        Consecutive calls within the same millisecond bump the counter by 1.
        """
        base = int(time.time() * 1000) * self._CLIENT_ORDER_INDEX_TIME_MULTIPLIER
        if base > self._last_client_order_index:
            self._last_client_order_index = base
        else:
            self._last_client_order_index += 1
        return self._last_client_order_index

    @staticmethod
    def _is_int_string(value: str) -> bool:
        if value is None:
            return False
        try:
            int(str(value).strip())
            return True
        except Exception:
            return False

    def _should_emit_throttled_warning(self, warning_key: str, warning_timestamps: Dict[str, float]) -> bool:
        now = time.time()
        last_warning_timestamp = warning_timestamps.get(warning_key, 0.0)
        if now - last_warning_timestamp >= self.EMPTY_MARKET_DATA_WARNING_INTERVAL:
            warning_timestamps[warning_key] = now
            return True
        return False

    def _get_top_order_book_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        try:
            order_book = self.get_order_book(trading_pair)
        except Exception:
            warning_key = f"{trading_pair}:{'ask' if is_buy else 'bid'}:missing"
            if self._should_emit_throttled_warning(warning_key, self._last_empty_order_book_warning_timestamp):
                self.logger().warning(f"{'Ask' if is_buy else 'Bid'} orderbook for {trading_pair} is empty.")
            return s_decimal_NaN

        entries = order_book.ask_entries() if is_buy else order_book.bid_entries()
        top_entry = next(entries, None)

        if top_entry is None:
            warning_key = f"{trading_pair}:{'ask' if is_buy else 'bid'}"
            if self._should_emit_throttled_warning(warning_key, self._last_empty_order_book_warning_timestamp):
                self.logger().warning(f"{'Ask' if is_buy else 'Bid'} orderbook for {trading_pair} is empty.")
            return s_decimal_NaN

        top_price = Decimal(str(top_entry.price))
        return self.quantize_order_price(trading_pair, top_price)

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self._get_top_order_book_price(trading_pair=trading_pair, is_buy=is_buy)

    def get_price_by_type(self, trading_pair: str, price_type: PriceType) -> Decimal:
        if price_type is PriceType.BestBid:
            return self._get_top_order_book_price(trading_pair=trading_pair, is_buy=False)
        elif price_type is PriceType.BestAsk:
            return self._get_top_order_book_price(trading_pair=trading_pair, is_buy=True)
        elif price_type is PriceType.MidPrice:
            ask_price = self._get_top_order_book_price(trading_pair=trading_pair, is_buy=True)
            bid_price = self._get_top_order_book_price(trading_pair=trading_pair, is_buy=False)
            if ask_price.is_nan() or bid_price.is_nan():
                return s_decimal_NaN
            return (ask_price + bid_price) / Decimal("2")
        elif price_type is PriceType.LastTrade:
            try:
                price = Decimal(str(self.get_order_book(trading_pair).last_trade_price))
                if price > s_decimal_0:
                    return price
            except Exception:
                pass
            return s_decimal_NaN
        else:
            return s_decimal_NaN

    def _get_rest_api_key(self) -> str:
        if self._is_int_string(self.api_key):
            return self.api_key
        if self.api_secret:
            return self.api_secret
        return self.api_key

    @staticmethod
    def _is_hex_private_key(value: str) -> bool:
        """Return True only if value is a 64+ char hex string (valid signer private key)."""
        if not value:
            return False
        key = value[2:] if value.lower().startswith("0x") else value
        return len(key) >= 64 and all(c in "0123456789abcdefABCDEF" for c in key)

    def _get_signer_private_key(self) -> str:
        if self.api_key and not self._is_int_string(self.api_key) and self._is_hex_private_key(self.api_key):
            return self.api_key
        if self.api_secret and not self._is_int_string(self.api_secret) and self._is_hex_private_key(self.api_secret):
            return self.api_secret
        raise ValueError(
            "Lighter signer private key is required for signed transactions. "
            "Set lighter_perpetual_api_key to your API private key (64+ char hex string)."
        )

    @property
    def rest_api_key(self) -> str:
        return self._get_rest_api_key()

    def _api_host_for_signer(self) -> str:
        url = CONSTANTS.REST_URL if self._domain == CONSTANTS.DEFAULT_DOMAIN else CONSTANTS.TESTNET_REST_URL
        return url.split("/api/v1")[0]

    def _get_api_key_index(self) -> int:
        if self._is_int_string(self.api_key_index):
            return int(self.api_key_index)
        if self._is_int_string(self.api_key):
            return int(self.api_key)
        if self._is_int_string(self.api_secret):
            return int(self.api_secret)
        raise ValueError(
            "Lighter API key index must be provided as an integer string in lighter_perpetual_api_key "
            "or lighter_perpetual_api_secret (compatibility mode)."
        )

    def _get_account_index(self) -> int:
        try:
            return int(self.account_index)
        except Exception as e:
            raise ValueError("Lighter account index must be an integer string") from e

    @staticmethod
    def _is_ok_response(response: Dict[str, Any]) -> bool:
        if response.get("success") is True:
            return True
        code = response.get("code")
        try:
            # Lighter API uses code=0 for success; HTTP 200 is also accepted.
            code_int = int(code)
            return code_int == 0 or code_int == 200
        except Exception:
            return False

    def _account_query_params(self) -> Dict[str, Any]:
        return {
            "by": "index",
            "value": str(self._get_account_index()),
        }

    @staticmethod
    def _account_from_response(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = response.get("data")
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        accounts = response.get("accounts")
        if isinstance(accounts, list) and len(accounts) > 0:
            return accounts[0]
        # Top-level account response (no data/accounts wrapper)
        if response.get("collateral") is not None or response.get("available_balance") is not None:
            return response
        if not response:
            return None
        return None

    def _get_lighter_signer_client(self):
        if self._lighter_signer_client is None:
            import lighter

            # connector-side signer override removed

            self._lighter_signer_client = lighter.signer_client.SignerClient(
                url=self._api_host_for_signer(),
                account_index=self._get_account_index(),
                api_private_keys={self._get_api_key_index(): self._get_signer_private_key()},
            )

        return self._lighter_signer_client

    async def _refresh_market_metadata(self):
        response = await self._api_get(
            path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL,
            return_err=True,
        )

        for market in response.get("order_books", []):
            if market.get("market_type") != "perp":
                continue

            symbol = market["symbol"]
            self._market_id_by_symbol[symbol] = int(market["market_id"])
            self._size_decimals_by_symbol[symbol] = int(market.get("supported_size_decimals", 0))
            self._price_decimals_by_symbol[symbol] = int(market.get("supported_price_decimals", 0))

    async def _get_market_spec(self, trading_pair: str) -> Tuple[int, int, int, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

        if symbol not in self._market_id_by_symbol:
            await self._refresh_market_metadata()

        if symbol not in self._market_id_by_symbol:
            raise ValueError(f"Market metadata not found for symbol {symbol}")

        return (
            self._market_id_by_symbol[symbol],
            self._size_decimals_by_symbol.get(symbol, 0),
            self._price_decimals_by_symbol.get(symbol, 0),
            symbol,
        )

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> LighterPerpetualAuth:
        return LighterPerpetualAuth(
            api_key=self.rest_api_key,
            api_secret=self.api_secret,
            account_identifier=self.account_index,
        )

    @property
    def rate_limits_rules(self):
        if not self.api_key:
            return CONSTANTS.RATE_LIMITS

        tier2_limit = CONSTANTS.FEE_TIER_LIMITS.get(self._fee_tier, CONSTANTS.LIGHTER_TIER_2_LIMIT)

        global_limit = RateLimit(
            limit_id=CONSTANTS.LIGHTER_LIMIT_ID,
            limit=tier2_limit,
            time_interval=CONSTANTS.LIGHTER_LIMIT_INTERVAL
        )

        return [global_limit] + CONSTANTS.RATE_LIMITS_TIER_2[1:]

    async def _api_request(
        self,
        path_url,
        overwrite_url: Optional[str] = None,
        method: RESTMethod = RESTMethod.GET,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_auth_required: bool = False,
        return_err: bool = False,
        limit_id: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:

        if is_auth_required and self.rest_api_key:
            api_headers = {"X-Api-Key": self.rest_api_key}
            if headers:
                headers.update(api_headers)
            else:
                headers = api_headers

        return await super()._api_request(
            path_url=path_url,
            overwrite_url=overwrite_url,
            method=method,
            params=params,
            data=data,
            is_auth_required=is_auth_required,
            return_err=return_err,
            limit_id=limit_id,
            headers=headers,
            **kwargs
        )

    async def _api_request_url(self, path_url: str, is_auth_required: bool = False) -> str:
        return web_utils.private_rest_url(path_url, domain=self._domain)

    async def _fetch_or_create_api_config_key(self):
        configured_api_key_index = next(
            (
                str(int(str(candidate).strip()))
                for candidate in (self.api_key_index, self.api_secret, self.api_key)
                if self._is_int_string(candidate)
            ),
            None,
        )
        if configured_api_key_index is not None:
            self.api_key_index = configured_api_key_index
            if not self.api_config_key:
                self.api_config_key = configured_api_key_index
            return

        if not self.account_index or not self.rest_api_key:
            self.logger().warning("Lighter account index or REST API key is missing; skipping API key discovery")
            return

        response = await self._api_get(
            path_url=CONSTANTS.GET_ACCOUNT_API_CONFIG_KEYS,
            params={"account_index": self._get_account_index(), "api_key_index": 255},
            is_auth_required=True,
            return_err=True,
        )

        api_keys = response.get("api_keys") or []
        matching_key = next(
            (
                api_key
                for api_key in api_keys
                if str(api_key.get("public_key", "")).lower() == str(self.rest_api_key).lower()
            ),
            None,
        )

        if matching_key is not None:
            self.api_key_index = str(matching_key.get("api_key_index"))
            self.api_config_key = self.rest_api_key
            self.logger().info(f"Resolved Lighter API key index: {self.api_key_index}")
            if self._throttler:
                self._throttler.set_rate_limits(self.rate_limits_rules)
            return

        self.logger().warning(
            "Configured Lighter REST API key was not found in /apikeys response. "
            "Provide lighter_perpetual_api_key_index explicitly or onboard/register the API key on Lighter first."
        )

    def generate_api_key_pair(self) -> Tuple[str, str]:
        try:
            import lighter
        except Exception as e:
            raise ImportError("lighter SDK package is required for Lighter API key generation") from e

        private_key, public_key, error = lighter.create_api_key()
        if error:
            raise ValueError(f"Failed to generate Lighter API key pair: {error}")
        return private_key, public_key

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return 32

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HB_OT_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        # LIGHTER does not expose a dedicated ping or time endpoint.
        # Use the lighter market-stats route instead of the full metadata payload.
        return CONSTANTS.GET_PRICES_PATH_URL

    @property
    def trading_pairs(self) -> Optional[List[str]]:
        return self._trading_pairs

    async def all_trading_pairs(self) -> List[str]:
        """
        Returns all active perpetual trading pairs on Lighter.
        Uses /orderBooks (same as _initialize_trading_pair_symbols_from_exchange_info)
        filtered for market_type == 'perp'. Works on both mainnet and testnet.
        """
        try:
            result = await self._api_get(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL)
            pairs = []
            for market in result.get("order_books") or []:
                if str(market.get("market_type", "")).lower() != "perp":
                    continue
                if str(market.get("status", "active")).lower() in {
                    "inactive", "disabled", "halted", "suspended", "delisted"
                }:
                    continue
                symbol = market.get("symbol", "")
                if symbol:
                    pairs.append(combine_to_hb_trading_pair(symbol, "USDC"))
            return pairs
        except Exception:
            return []

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        # actually it updates every hour
        # but there's a chance that the bot was started 5 minutes before update
        # so we would wait extra hour
        # so query every 2 minutes should work
        return 120

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return "USDC"

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return "USDC"

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        """
        e.g.
        {"success":false,"data":null,"error":"Order history not found for order ID: 28416222569","code":404}
        """
        return "not found" in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        """
        e.g.
        {"success":false,"data":null,"error":"Failed to cancel order","code":5}
        https://docs.lighter.fi/api-documentation/api/error-codes

        """
        return '"code":5' in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LighterPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LighterPerpetualUserStreamDataSource(
            connector=self,
            api_factory=self._web_assistants_factory,
            auth=self._auth,
            domain=self._domain,
        )

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        https://docs.lighter.fi/api-documentation/api/rest-api/markets/get-market-info

        {
            "success": true,
            "data": [
                {
                "symbol": "ETH",
                "tick_size": "0.1",
                "min_tick": "0",
                "max_tick": "1000000",
                "lot_size": "0.0001",
                "max_leverage": 50,
                "isolated_only": false,
                "min_order_size": "10",
                "max_order_size": "5000000",
                "funding_rate": "0.0000125",
                "next_funding_rate": "0.0000125",
                "created_at": 1748881333944
                },
                {
                "symbol": "BTC",
                "tick_size": "1",
                "min_tick": "0",
                "max_tick": "1000000",
                "lot_size": "0.00001",
                "max_leverage": 50,
                "isolated_only": false,
                "min_order_size": "10",
                "max_order_size": "5000000",
                "funding_rate": "0.0000125",
                "next_funding_rate": "0.0000125",
                "created_at": 1748881333944
                },
                ....
            ],
            "error": null,
            "code": null
        }
        """
        rules = []

        order_books = exchange_info_dict.get("order_books")
        if order_books:
            for pair_info in order_books:
                if pair_info.get("market_type") != "perp":
                    continue

                symbol = pair_info["symbol"]
                size_decimals = int(pair_info.get("supported_size_decimals", 0))
                price_decimals = int(pair_info.get("supported_price_decimals", 0))
                lot_size = Decimal(f"1e-{size_decimals}")
                tick_size = Decimal(f"1e-{price_decimals}")
                min_notional = Decimal(str(pair_info.get("min_quote_amount", "10")))

                self._market_id_by_symbol[symbol] = int(pair_info["market_id"])
                self._size_decimals_by_symbol[symbol] = size_decimals
                self._price_decimals_by_symbol[symbol] = price_decimals

                rules.append(
                    TradingRule(
                        trading_pair=await self.trading_pair_associated_to_exchange_symbol(symbol=symbol),
                        min_order_size=lot_size,
                        min_price_increment=tick_size,
                        min_base_amount_increment=lot_size,
                        min_notional_size=min_notional,
                        min_order_value=min_notional,
                    )
                )

            return rules

        for pair_info in exchange_info_dict.get("data", []):
            rules.append(
                TradingRule(
                    trading_pair=await self.trading_pair_associated_to_exchange_symbol(symbol=pair_info["symbol"]),
                    min_order_size=Decimal(pair_info["lot_size"]),
                    min_price_increment=Decimal(pair_info["tick_size"]),
                    min_base_amount_increment=Decimal(pair_info["lot_size"]),
                    min_notional_size=Decimal(pair_info["min_order_size"]),
                    min_order_value=Decimal(pair_info["min_order_size"]),
                )
            )

        return rules

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
        https://docs.lighter.fi/api-documentation/api/rest-api/orders/create-market-order
        https://docs.lighter.fi/api-documentation/api/rest-api/orders/create-limit-order
        """

        if order_type not in self.supported_order_types():
            raise ValueError(f"Order type {order_type} is not supported by {self.name}.")

        market_id, size_decimals, price_decimals, _ = await self._get_market_spec(trading_pair)
        signer_client = self._get_lighter_signer_client()

        base_amount_scaled = int((amount * Decimal(f"1e{size_decimals}")).to_integral_value())
        price_scaled = int((price * Decimal(f"1e{price_decimals}")).to_integral_value())

        signer_order_type = signer_client.ORDER_TYPE_LIMIT
        signer_tif = signer_client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME
        order_expiry = signer_client.DEFAULT_28_DAY_ORDER_EXPIRY
        if order_type == OrderType.MARKET:
            signer_order_type = signer_client.ORDER_TYPE_MARKET
            signer_tif = signer_client.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL
            order_expiry = signer_client.DEFAULT_IOC_EXPIRY
        elif order_type == OrderType.LIMIT_MAKER:
            signer_tif = signer_client.ORDER_TIME_IN_FORCE_POST_ONLY

        async with self._signer_request_lock:
            signer_client = self._get_lighter_signer_client()
            tx_response = None
            error = None
            for attempt in range(5):
                client_order_index = self._allocate_client_order_index()
                _, tx_response, error = await signer_client.create_order(
                    market_index=market_id,
                    client_order_index=client_order_index,
                    base_amount=base_amount_scaled,
                    price=price_scaled,
                    is_ask=(trade_type == TradeType.SELL),
                    order_type=signer_order_type,
                    time_in_force=signer_tif,
                    reduce_only=position_action == PositionAction.CLOSE,
                    order_expiry=order_expiry,
                    api_key_index=self._get_api_key_index(),
                )
                if error is None and getattr(tx_response, "code", None) == 200:
                    break
                if attempt < 4 and "invalid nonce" in str(error or tx_response).lower():
                    self._lighter_signer_client = None
                    signer_client = self._get_lighter_signer_client()
                    await self._sleep(0.3)
                    continue
                break

        if error is not None:
            raise IOError(f"Lighter create_order signing/send failed: {error}")
        if tx_response is None or getattr(tx_response, "code", None) != 200:
            raise IOError(f"Lighter create_order failed: {tx_response}")

        return str(client_order_index), self.current_timestamp

    def _set_usdc_balances(self, total_balance: Decimal, available_balance: Decimal):
        asset = "USDC"

        self._account_balances[asset] = total_balance
        self._account_available_balances[asset] = available_balance

        for balances_dict in (self._account_balances, self._account_available_balances):
            stale_assets = [tracked_asset for tracked_asset in balances_dict if tracked_asset != asset]
            for stale_asset in stale_assets:
                del balances_dict[stale_asset]

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        """
        https://docs.lighter.fi/api-documentation/api/rest-api/orders/cancel-order
        """
        if tracked_order.exchange_order_id is None:
            self.logger().warning(
                "[_place_cancel] exchange_order_id is None for order %s, skipping cancel.",
                order_id,
            )
            return False

        market_id, _, _, _ = await self._get_market_spec(tracked_order.trading_pair)
        signer_client = self._get_lighter_signer_client()

        # Resolve the actual exchange order_index from our client_order_index.
        # _place_order stores client_order_index as exchange_order_id initially;
        # the real order_index is populated from WS updates or REST lookup.
        client_oid = str(tracked_order.exchange_order_id)
        actual_order_index = self._client_order_index_to_order_index.get(client_oid)
        if actual_order_index is None:
            actual_order_index = await self._resolve_order_index_from_active_orders(
                market_id=market_id,
                client_order_index=client_oid,
            )
        if actual_order_index is None:
            self.logger().warning(
                "[_place_cancel] Cannot resolve actual order_index for "
                f"client_order_index={client_oid}. Order may already be filled/cancelled."
            )
            return False

        async with self._signer_request_lock:
            signer_client = self._get_lighter_signer_client()
            tx_response = None
            error = None
            for attempt in range(5):
                _, tx_response, error = await signer_client.cancel_order(
                    market_index=market_id,
                    order_index=int(actual_order_index),
                    api_key_index=self._get_api_key_index(),
                )
                if error is None and getattr(tx_response, "code", None) == 200:
                    break
                if attempt < 4 and "invalid nonce" in str(error or tx_response).lower():
                    self._lighter_signer_client = None
                    signer_client = self._get_lighter_signer_client()
                    await self._sleep(0.3)
                    continue
                break

        if error is not None:
            raise IOError(f"Lighter cancel_order signing/send failed: {error}")
        if tx_response is None or getattr(tx_response, "code", None) != 200:
            raise IOError(f"Lighter cancel_order failed: {tx_response}")

        return True

    async def _update_balances(self):
        """
        https://docs.lighter.fi/api-documentation/api/rest-api/account/get-account-info
        ```
        {
          "success": true,
          "data": [{
            "balance": "2000.000000",
            "fee_level": 0,
            "maker_fee": "0.00015",
            "taker_fee": "0.0004",
            "account_equity": "2150.250000",
            "available_to_spend": "1800.750000",
            "available_to_withdraw": "1500.850000",
            "pending_balance": "0.000000",
            "total_margin_used": "349.500000",
            "cross_mmr": "420.690000",
            "positions_count": 2,
            "orders_count": 3,
            "stop_orders_count": 1,
            "updated_at": 1716200000000,
            "use_ltp_for_stop_orders": false
          }
        ],
          "error": null,
          "code": null
        }
        ```
        """
        # Generate a signed auth token so the server validates the private key.
        # Without this, GET /account is unauthenticated and accepts any valid account_index
        # even with a wrong API key — causing a false "connected" result.
        params = self._account_query_params()
        try:
            signer_client = self._get_lighter_signer_client()
            auth_token, auth_error = signer_client.create_auth_token_with_expiry(
                api_key_index=self._get_api_key_index()
            )
            if auth_error or not auth_token:
                raise IOError(
                    f"Cannot connect to Lighter Perpetual: failed to generate auth token. {auth_error} "
                    "Check your API private key and API key index."
                )
            params["auth"] = auth_token
        except IOError:
            raise
        except Exception as e:
            raise IOError(
                f"Cannot connect to Lighter Perpetual: failed to build auth token — {e}. "
                "Check your API private key and API key index."
            )

        response = await self._api_get(
            path_url=CONSTANTS.GET_ACCOUNT_INFO_PATH_URL,
            params=params,
            is_auth_required=True,
            return_err=True
        )

        if not self._is_ok_response(response):
            code = response.get("code") if isinstance(response, dict) else ""
            msg = response.get("message") or response.get("error") or "" if isinstance(response, dict) else str(response)
            raise IOError(
                f"Cannot connect to Lighter Perpetual: server returned code {code}. "
                f"{msg} — check your account index, API key index, and API private key."
            )

        data = self._account_from_response(response)
        if not data:
            raise IOError(
                f"Cannot connect to Lighter Perpetual: no account data returned. "
                f"Verify your account index is correct (large number, e.g. 693751 — NOT the API key index). "
                f"Response: {response}"
            )

        total_balance = data.get("account_equity") or data.get("equity") or data.get("collateral") or "0"
        available_balance = data.get("available_to_spend") or data.get("availableForTrade") or data.get("available_balance") or total_balance

        self._set_usdc_balances(
            total_balance=Decimal(str(total_balance)),
            available_balance=Decimal(str(available_balance)),
        )
        self._fee_tier = data.get("fee_level", 0)

    async def _update_positions(self):
        """
        https://docs.lighter.fi/api-documentation/api/rest-api/account/get-positions
        Positions Info
        ```
          {
            "success": true,
            "data": [
                {
                "symbol": "AAVE",
                "side": "ask",
                "amount": "223.72",
                "entry_price": "279.283134",
                "margin": "0", // only shown for isolated margin
                "funding": "13.159593",
                "isolated": false,
                "created_at": 1754928414996,
                "updated_at": 1759223365538
                }
            ],
            "error": null,
            "code": null,
            "last_order_id": 1557431179
        }
        ```

        https://docs.lighter.fi/api-documentation/api/rest-api/markets/get-prices
        Prices Info
        ```
         {
            "success": true,
            "data": [
                {
                "funding": "0.00010529",
                "mark": "1.084819",
                "mid": "1.08615",
                "next_funding": "0.00011096",
                "open_interest": "3634796",
                "oracle": "1.084524",
                "symbol": "XPL",
                "timestamp": 1759222967974,
                "volume_24h": "20896698.0672",
                "yesterday_price": "1.3412"
                }
            ],
            "error": null,
            "code": null
        }
        ```
        """
        response = await self._api_get(
            path_url=CONSTANTS.GET_ACCOUNT_INFO_PATH_URL,
            params=self._account_query_params(),
            return_err=True,
        )

        if not self._is_ok_response(response):
            self.logger().error(f"[_update_positions] Failed to update positions (api responded with failure): {response}")
            return

        account_data = self._account_from_response(response)
        if not account_data:
            self.logger().error(f"[_update_positions] Failed to update positions (no account data): {response}")
            return

        position_entries = account_data.get("positions") or response.get("data") or []

        # Clear first so a partial refresh cannot leave stale position state visible to the strategy.
        self._perpetual_trading.account_positions.clear()

        position_symbols = [position_entry["symbol"] for position_entry in position_entries if position_entry.get("symbol")]
        position_trading_pairs = [
            await self.trading_pair_associated_to_exchange_symbol(position_symbol) for position_symbol in position_symbols
        ]
        if any([self.get_LIGHTER_price(position_trading_pair) is None for position_trading_pair in position_trading_pairs]):
            self.logger().debug("[_update_positions] Prices cache is empty. Going to fetch prices via HTTP.")
            # we should update the cache
            # in future we could also consider to add some cache invalidation rules (e.g. timestamp too old)
            prices_response = await self._api_get(
                path_url=CONSTANTS.GET_PRICES_PATH_URL,
                return_err=True,
            )
            if not self._is_ok_response(prices_response):
                self.logger().error(f"[_update_positions] Failed to update prices cache using HTTP API: {prices_response}")
                return
            price_entries = prices_response.get("data") or prices_response.get("order_book_stats") or []
            for price_entry in price_entries:
                if price_entry["symbol"] not in position_symbols:
                    continue
                hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(price_entry["symbol"])
                mark_price = price_entry.get("mark") or price_entry.get("mid") or price_entry.get("last_trade_price") or "0"
                index_price = price_entry.get("oracle") or price_entry.get("mid") or price_entry.get("last_trade_price") or mark_price
                timestamp = price_entry.get("timestamp") or int(time.time() * 1000)
                self.set_LIGHTER_price(
                    trading_pair=hb_trading_pair,
                    timestamp=timestamp / 1000,
                    index_price=Decimal(str(index_price)),
                    mark_price=Decimal(str(mark_price)),
                )

        for position_entry in position_entries:
            hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(position_entry["symbol"])
            sign = int(position_entry.get("sign", 1))
            position_side = PositionSide.LONG if sign >= 0 else PositionSide.SHORT
            position_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
            amount = Decimal(str(position_entry.get("amount") or position_entry.get("position") or "0"))
            if amount == Decimal("0"):
                # Skip closed positions (exchange sends trailing zero-amount entries after close)
                continue
            entry_price = Decimal(str(position_entry.get("entry_price") or position_entry.get("avg_entry_price") or "0"))

            price_record = self.get_LIGHTER_price(hb_trading_pair)
            if price_record is not None:
                mark_price = price_record.mark_price
            else:
                # Use the unrealized_pnl from the event if available, otherwise default to entry_price
                upnl_str = position_entry.get("unrealized_pnl")
                if upnl_str is not None:
                    unrealized_pnl = Decimal(str(upnl_str))
                else:
                    unrealized_pnl = Decimal("0")
                mark_price = entry_price  # fallback so PnL calc below yields zero if no event pnl

            if price_record is not None:
                if position_side == PositionSide.LONG:
                    unrealized_pnl = (mark_price - entry_price) * amount
                else:
                    unrealized_pnl = (entry_price - mark_price) * amount

            # Include cumulative funding P&L (positive = received, negative = paid)
            cumulative_funding = Decimal(str(position_entry.get("funding") or "0"))
            unrealized_pnl += cumulative_funding

            position = Position(
                trading_pair=hb_trading_pair,
                position_side=position_side,
                unrealized_pnl=unrealized_pnl,
                entry_price=entry_price,
                amount=amount * (Decimal("-1.0") if position_side == PositionSide.SHORT else Decimal("1.0")),
                leverage=Decimal(self.get_leverage(hb_trading_pair))
            )
            self._perpetual_trading.set_position(position_key, position)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Fetch fill history for a specific order via GET /trades.

        /trades requires sort_by (required) + auth (passed via is_auth_required).
        Response: {"code": 200, "trades": [...], "next_cursor": "..."}
        Each trade: trade_id, ask_id, bid_id, size, price, timestamp (ms), is_maker_ask, etc.
        """
        trade_updates = []

        last_poll_timestamp = self._order_history_last_poll_timestamp.get(order.exchange_order_id)
        if last_poll_timestamp and not math.isnan(last_poll_timestamp):
            from_ts = int(last_poll_timestamp)  # seconds
        else:
            from_ts = int(order.creation_timestamp)  # seconds

        try:
            current_time = self.current_timestamp
        except AttributeError:
            current_time = None
        current_time_is_valid = current_time is not None and not math.isnan(current_time)
        if not current_time_is_valid:
            current_time = time.time()

        market_id_trades, _, _, _ = await self._get_market_spec(order.trading_pair)

        signer_client_trades = self._get_lighter_signer_client()
        auth_token_trades, _ = signer_client_trades.create_auth_token_with_expiry(
            api_key_index=self._get_api_key_index()
        )

        params: Dict[str, Any] = {
            "account_index": self._get_account_index(),
            "market_id": market_id_trades,
            "sort_by": "timestamp",
            "from": from_ts,
            "limit": 100,
            "auth": auth_token_trades or "",
        }
        # Narrow to this specific order when exchange_order_id is numeric.
        try:
            params["order_index"] = int(order.exchange_order_id)
        except (ValueError, TypeError):
            pass

        try:
            our_order_id_int = int(order.exchange_order_id) if order.exchange_order_id else None
        except (ValueError, TypeError):
            our_order_id_int = None

        while True:
            response = await self._api_get(
                path_url=CONSTANTS.GET_TRADE_HISTORY_PATH_URL,
                params=params,
                is_auth_required=True,
                return_err=True,
            )

            trades_list = response.get("trades") or response.get("data") or []
            if not trades_list:
                break

            for trade in trades_list:
                ask_id = trade.get("ask_id")
                bid_id = trade.get("bid_id")

                if our_order_id_int is not None:
                    our_is_ask = our_order_id_int == ask_id
                    our_is_bid = our_order_id_int == bid_id
                else:
                    our_is_ask = str(trade.get("ask_client_id") or "") == str(order.exchange_order_id)
                    our_is_bid = str(trade.get("bid_client_id") or "") == str(order.exchange_order_id)

                if not our_is_ask and not our_is_bid:
                    continue

                fill_timestamp = float(trade.get("timestamp") or 0)
                if fill_timestamp > 1e12:
                    fill_timestamp /= 1000.0

                fill_price = Decimal(str(trade.get("price") or "0"))
                fill_base_amount = Decimal(str(trade.get("size") or "0"))

                is_maker_ask = trade.get("is_maker_ask", False)
                is_taker = (our_is_ask and not is_maker_ask) or (our_is_bid and is_maker_ask)

                trade_id = self.get_LIGHTER_finance_trade_id(
                    order_id=trade.get("trade_id") or 0,
                    timestamp=fill_timestamp,
                    fill_base_amount=fill_base_amount,
                    fill_price=fill_price,
                )

                fee = TradeFeeBase.new_perpetual_fee(
                    fee_schema=self.trade_fee_schema(),
                    position_action=order.position,
                    percent_token=order.quote_asset,
                )

                trade_updates.append(TradeUpdate(
                    trade_id=trade_id,
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    trading_pair=order.trading_pair,
                    fill_timestamp=fill_timestamp,
                    fill_price=fill_price,
                    fill_base_amount=fill_base_amount,
                    fill_quote_amount=fill_price * fill_base_amount,
                    fee=fee,
                    is_taker=is_taker,
                ))

            next_cursor = response.get("next_cursor")
            if next_cursor:
                params["cursor"] = next_cursor
            else:
                break

        # Guard: do not store NaN (or fallback wall-time) timestamps.
        if current_time_is_valid:
            self._order_history_last_poll_timestamp[order.exchange_order_id] = current_time

        return trade_updates
    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        https://docs.lighter.fi/api-documentation/api/rest-api/orders/get-order-history-by-id

        Example API response:
        ```
        {
            "success": true,
            "data": [
                {
                "history_id": 641452639,
                "order_id": 315992721,
                "client_order_id": "ade1aa6...",
                "symbol": "XPL",
                "side": "ask",
                "price": "1.0865",
                "initial_amount": "984",
                "filled_amount": "0",
                "cancelled_amount": "984",
                "event_type": "cancel",
                "order_type": "limit",
                "order_status": "cancelled",
                "stop_price": null,
                "stop_parent_order_id": null,
                "reduce_only": false,
                "created_at": 1759224895038
                },
                {
                "history_id": 641452513,
                "order_id": 315992721,
                "client_order_id": "ade1aa6...",
                "symbol": "XPL",
                "side": "ask",
                "price": "1.0865",
                "initial_amount": "984",
                "filled_amount": "0",
                "cancelled_amount": "0",
                "event_type": "make",
                "order_type": "limit",
                "order_status": "open",
                "stop_price": null,
                "stop_parent_order_id": null,
                "reduce_only": false,
                "created_at": 1759224893638
                }
            ],
            "error": null,
            "code": null
        }
        ```
        """
        # Step 1: check whether the order is still active.
        client_oid = str(tracked_order.exchange_order_id)
        actual_order_index = self._client_order_index_to_order_index.get(client_oid)

        if actual_order_index is None:
            # Try to find it in active orders and populate the mapping.
            try:
                market_id, _, _, _ = await self._get_market_spec(tracked_order.trading_pair)
                actual_order_index = await self._resolve_order_index_from_active_orders(
                    market_id=market_id,
                    client_order_index=client_oid,
                )
            except Exception:
                actual_order_index = None

        if actual_order_index is not None:
            # Order is still active – return OPEN with real exchange_order_id.
            return OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.OPEN,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=actual_order_index,
            )

        # Step 2: order is not active – look in historical/inactive orders.
        query_oid = client_oid
        signer_client_oi = self._get_lighter_signer_client()
        auth_token_oi, _ = signer_client_oi.create_auth_token_with_expiry(
            api_key_index=self._get_api_key_index()
        )
        market_id_oi, _, _, _ = await self._get_market_spec(tracked_order.trading_pair)
        response = await self._api_get(
            path_url=CONSTANTS.GET_ORDER_HISTORY_PATH_URL,
            params={
                "account_index": self._get_account_index(),
                "market_id": market_id_oi,
                "limit": 50,
                "auth": auth_token_oi or "",
            },
            is_auth_required=True,
            return_err=True,
        )

        data = response.get("data") or response.get("orders") or []
        if not data:
            raise IOError(
                f"Order status query returned empty data for order {tracked_order.exchange_order_id}: {response}"
            )

        # Filter to find the specific order by client_order_id or order_id
        order_entry = None
        for row in data:
            row_cid = str(row.get("client_order_id") or row.get("client_order_index") or row.get("I") or "")
            row_oid = str(row.get("order_id") or row.get("order_index") or row.get("i") or "")
            if row_cid == query_oid or row_oid == query_oid:
                order_entry = row
                break

        if order_entry is None:
            self.logger().debug(
                f"Order {tracked_order.exchange_order_id} not found in inactive orders response; treating as canceled."
            )
            return OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.CANCELED,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(tracked_order.exchange_order_id),
            )

        raw_status = order_entry.get("order_status", "") or order_entry.get("status", "")
        order_status = CONSTANTS.ORDER_STATE.get(raw_status)
        if order_status is None:
            if not raw_status:
                # Empty status from inactive orders � treat as cancelled
                order_status = CONSTANTS.ORDER_STATE["cancelled"]
            else:
                raise IOError(f"Unknown order status '{raw_status}' for order {tracked_order.exchange_order_id}")

        resolved_eid = str(
            order_entry.get("order_id") or order_entry.get("order_index")
            or tracked_order.exchange_order_id
        )
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_entry.get("created_at", 0) / 1000,
            new_state=order_status,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=resolved_eid,
        )

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """
        https://docs.lighter.fi/api-documentation/api/rest-api/markets/get-candle-data

        Example API response:
        ```
        {
            "success": true,
            "data": [
                {
                "t": 1748954160000,
                "T": 1748954220000,
                "s": "BTC",
                "i": "1m",
                "o": "105376",
                "c": "105376",
                "h": "105376",
                "l": "105376",
                "v": "0.00022",
                "n": 2
                }
            ],
            "error": null,
            "code": null
        }
        ```
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        params = {
            "symbol": symbol,
            "interval": "1m",
            "start_time": int(time.time() * 1000) - 5 * 60 * 1000,
        }

        response = await self._api_get(
            path_url=CONSTANTS.GET_CANDLES_PATH_URL,
            params=params,
        )

        candles = response.get("data") or []
        if not candles:
            warning_key = f"{trading_pair}:candles"
            if self._should_emit_throttled_warning(warning_key, self._last_no_candle_warning_timestamp):
                self.logger().warning(f"No candle data returned for {trading_pair}, returning 0.0")
            return 0.0
        return float(candles[0]["c"])

    async def _update_trading_fees(self):
        """
        https://docs.lighter.fi/api-documentation/api/rest-api/account/get-account-info
        ```
        {
          "success": true,
          "data": [{
            "balance": "2000.000000",
            "fee_level": 0,
            "maker_fee": "0.00015",
            "taker_fee": "0.0004",
            "account_equity": "2150.250000",
            "available_to_spend": "1800.750000",
            "available_to_withdraw": "1500.850000",
            "pending_balance": "0.000000",
            "total_margin_used": "349.500000",
            "cross_mmr": "420.690000",
            "positions_count": 2,
            "orders_count": 3,
            "stop_orders_count": 1,
            "updated_at": 1716200000000,
            "use_ltp_for_stop_orders": false
          }
        ],
          "error": null,
          "code": null
        }
        ```
        """
        response = await self._api_get(
            path_url=CONSTANTS.GET_ACCOUNT_INFO_PATH_URL,
            params=self._account_query_params(),
            return_err=True
        )

        # comparison with True is needed, bc we might expect a string to be there
        # while the only indicator of success here is True boolean value
        if not self._is_ok_response(response):
            self.logger().error(f"[_update_trading_fees] Failed to update trading fees (api responded with failure): {response}")
            return

        data = self._account_from_response(response)
        if not data:
            self.logger().error(f"[_update_trading_fees] Failed to update trading fees (no data): {response}")
            return

        maker_fee = data.get("maker_fee")
        taker_fee = data.get("taker_fee")
        if maker_fee is None or taker_fee is None:
            self.logger().debug("[_update_trading_fees] Live account response does not expose maker/taker fee rates; keeping existing/default fees")
            return

        trade_fee_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal(data["maker_fee"]),
            taker_percent_fee_decimal=Decimal(data["taker_fee"]),
        )

        for trading_pair in self._trading_pairs:
            self._trading_fees[trading_pair] = trade_fee_schema

        self.logger().debug("Trading fees updated")

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        """
        Fetch the most recent funding payment for a trading pair.

        The /positionFunding endpoint returns:
            {"code": 200, "position_fundings": [{"timestamp": <seconds>, "market_id": ..., "change": ..., "rate": ..., ...}]}
        """
        market_id, _, _, _ = await self._get_market_spec(trading_pair)

        signer_client_ff = self._get_lighter_signer_client()
        auth_token_ff, _ = signer_client_ff.create_auth_token_with_expiry(
            api_key_index=self._get_api_key_index()
        )
        response = await self._api_get(
            path_url=CONSTANTS.GET_FUNDING_HISTORY_PATH_URL,
            params={
                "account_index": self._get_account_index(),
                "market_id": market_id,
                "limit": 100,
                "auth": auth_token_ff or "",
            },
            is_auth_required=True,
            return_err=True
        )

        if not self._is_ok_response(response):
            self.logger().error(f"Failed to fetch last fee payment (api responded with failure): {response}")
            return 0, Decimal("-1"), Decimal("-1")

        # Support both response shapes: {"data": [...]} and {"position_fundings": [...]}
        data = response.get("data") or response.get("position_fundings")
        if not data:
            self.logger().debug(f"Failed to fetch last fee payment (no data): {response}")
            return 0, Decimal("-1"), Decimal("-1")

        for item in data:
            if item.get("market_id") == market_id:
                # timestamp may be in seconds; normalize to ms
                ts = item.get("created_at") or item.get("timestamp", 0)
                if ts < 1e12:
                    ts = int(ts) * 1000
                rate = item.get("rate", "0")
                payout = item.get("payout") or item.get("change", "0")
                return float(ts), Decimal(str(rate)), Decimal(str(payout))

        return 0, Decimal("-1"), Decimal("-1")

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """Set leverage using signer_client.update_leverage() (signed tx via /sendTx)."""
        market_id, _, _, _ = await self._get_market_spec(trading_pair)
        signer_client = self._get_lighter_signer_client()
        margin_mode = signer_client.CROSS_MARGIN_MODE  # 0 = cross
        _, tx_response, error = await signer_client.update_leverage(
            market_index=market_id,
            margin_mode=margin_mode,
            leverage=leverage,
            api_key_index=self._get_api_key_index(),
        )
        if error is not None:
            return False, f"Error when setting leverage: {error}"
        return True, ""

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        return True, ""

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        order_books = exchange_info.get("order_books")
        if order_books:
            for symbol_data in order_books:
                if symbol_data.get("market_type") != "perp":
                    continue

                exchange_symbol = symbol_data["symbol"]
                base = exchange_symbol
                quote = "USDC"
                trading_pair = combine_to_hb_trading_pair(base, quote)
                mapping[exchange_symbol] = trading_pair

                self._market_id_by_symbol[exchange_symbol] = int(symbol_data["market_id"])
                self._size_decimals_by_symbol[exchange_symbol] = int(symbol_data.get("supported_size_decimals", 0))
                self._price_decimals_by_symbol[exchange_symbol] = int(symbol_data.get("supported_price_decimals", 0))
        else:
            for symbol_data in exchange_info.get("data", []):
                exchange_symbol = symbol_data["symbol"]
                base = exchange_symbol
                quote = "USDC"
                trading_pair = combine_to_hb_trading_pair(base, quote)
                mapping[exchange_symbol] = trading_pair

        self._set_trading_pair_symbol_map(mapping)

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 position_action: PositionAction,
                 amount: Decimal,
                 price: Decimal = Decimal("nan"),
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

    async def _user_stream_event_listener(self):
        """
        Wait for new messages from _user_stream_tracker.user_stream queue and processes them according to their
        message channels. The respective UserStreamDataSource queues these messages.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message.get("channel")
                event_type = event_message.get("type")
                if channel == CONSTANTS.WS_ACCOUNT_ORDER_UPDATES_CHANNEL:
                    await self._process_account_order_updates_ws_event_message(event_message)
                elif channel == CONSTANTS.WS_ACCOUNT_POSITIONS_CHANNEL:
                    await self._process_account_positions_ws_event_message(event_message)
                elif channel == CONSTANTS.WS_ACCOUNT_INFO_CHANNEL:
                    await self._process_account_info_ws_event_message(event_message)
                elif channel == CONSTANTS.WS_ACCOUNT_TRADES_CHANNEL:
                    await self._process_account_trades_ws_event_message(event_message)
                elif (
                    event_type in {"subscribed/account_all", "update/account_all"}
                    or str(channel).startswith(f"{CONSTANTS.WS_ACCOUNT_ALL_CHANNEL}:")
                ):
                    await self._process_account_all_ws_event_message(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop: {e}", exc_info=True)
                await self._sleep(5.0)

    async def _process_account_all_ws_event_message(self, event_message: Dict[str, Any]):
        await self._process_account_trades_ws_event_message(event_message)
        await self._process_account_positions_ws_event_message(event_message)
        # Process the 'orders' section to populate client_order_index -> order_index mapping.
        await self._process_account_all_orders_ws_event_message(event_message)
        # Extract balance info from account_all assets payload (USDC asset)
        assets = event_message.get("assets")
        if isinstance(assets, dict):
            for asset_entry in assets.values():
                if str(asset_entry.get("symbol", "")).upper() == "USDC":
                    total_balance = Decimal(str(asset_entry.get("balance", "0")))
                    locked = Decimal(str(asset_entry.get("locked_balance", "0")))
                    self._set_usdc_balances(
                        total_balance=total_balance,
                        available_balance=total_balance - locked,
                    )
                    break

    @staticmethod
    def _normalized_position_entries_from_event(event_message: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_entries = event_message.get("data")
        if isinstance(raw_entries, dict):
            raw_entries = None
        if raw_entries is None:
            positions = event_message.get("positions") or {}
            raw_entries = list(positions.values()) if isinstance(positions, dict) else positions

        normalized_entries: List[Dict[str, Any]] = []
        for position_entry in raw_entries or []:
            if "s" in position_entry:
                normalized_entries.append(position_entry)
                continue

            symbol = position_entry.get("symbol")
            if not symbol:
                continue

            raw_amount = Decimal(str(position_entry.get("position") or "0"))
            if raw_amount == s_decimal_0:
                continue

            sign = int(position_entry.get("sign", 1) or 1)
            normalized_entries.append({
                "s": symbol,
                "d": "bid" if sign >= 0 else "ask",
                "a": str(abs(raw_amount)),
                "p": str(position_entry.get("avg_entry_price") or "0"),
                "upnl": str(position_entry.get("unrealized_pnl")) if position_entry.get("unrealized_pnl") is not None else None,
                # cumulative funding P&L for this position (positive = received, negative = paid)
                "f": str(position_entry.get("funding") or "0"),
            })

        return normalized_entries

    def _normalized_trade_entries_from_event(self, event_message: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_entries = event_message.get("data")
        if raw_entries is not None:
            return list(raw_entries or [])

        trades = event_message.get("trades") or {}
        if isinstance(trades, dict):
            trade_buckets = trades.values()
        elif isinstance(trades, list):
            trade_buckets = trades
        else:
            trade_buckets = []

        normalized_entries: List[Dict[str, Any]] = []
        for trade_bucket in trade_buckets:
            entries = trade_bucket if isinstance(trade_bucket, list) else [trade_bucket]
            for trade_entry in entries:
                if not isinstance(trade_entry, dict):
                    continue
                if "i" in trade_entry:
                    normalized_entries.append(trade_entry)
                    continue

                own_bid = str(trade_entry.get("bid_account_id")) == str(self._get_account_index())
                own_ask = str(trade_entry.get("ask_account_id")) == str(self._get_account_index())
                if not own_bid and not own_ask:
                    continue

                exchange_order_id = (
                    str(trade_entry.get("bid_client_id_str") or trade_entry.get("bid_client_id") or "")
                    if own_bid
                    else str(trade_entry.get("ask_client_id_str") or trade_entry.get("ask_client_id") or "")
                )
                if not exchange_order_id:
                    continue

                is_taker = (own_bid and bool(trade_entry.get("is_maker_ask"))) or (own_ask and not bool(trade_entry.get("is_maker_ask")))
                fee_rate_ppm = Decimal(str(trade_entry.get("taker_fee") if is_taker else trade_entry.get("maker_fee") or 0))
                fee_amount = Decimal(str(trade_entry.get("usd_amount") or "0")) * fee_rate_ppm / Decimal("1000000")

                normalized_entries.append({
                    "i": exchange_order_id,
                    "p": str(trade_entry.get("price") or "0"),
                    "a": str(trade_entry.get("size") or "0"),
                    "f": str(fee_amount),
                    "t": trade_entry.get("timestamp") or trade_entry.get("transaction_time") or 0,
                    "ts": "open_long" if own_bid else "open_short",
                    "trade_id": trade_entry.get("trade_id_str") or trade_entry.get("trade_id"),
                })

        return normalized_entries

    async def _process_account_order_updates_ws_event_message(self, event_message: Dict[str, Any]):
        """
        https://docs.lighter.fi/api-documentation/api/websocket/subscriptions/account-order-updates
        {
            "channel": "account_order_updates",
            "data": [
                {
                "i": 1559665358,
                "I": null,
                "u": "BrZp5bidJ3WUvceSq7X78bhjTfZXeezzGvGEV4hAYKTa",
                "s": "BTC",
                "d": "bid",
                "p": "89501",
                "ip": "89501",
                "lp": "89501",
                "a": "0.00012",
                "f": "0.00012",
                "oe": "fulfill_limit",
                "os": "filled",
                "ot": "limit",
                "sp": null,
                "si": null,
                "r": false,
                "ct": 1765017049008,
                "ut": 1765017219639,
                "li": 1559696133
                }
            ]
        }
        """
        # Build two indices: by exchange order_index AND by client_order_index.
        tracked_orders_by_oid = {order.exchange_order_id: order for order in self._order_tracker.all_updatable_orders.values()}
        tracked_orders_by_client = {order.exchange_order_id: order for order in self._order_tracker.all_updatable_orders.values()}

        raw_entries = event_message.get("data")
        if not isinstance(raw_entries, list):
            return

        for order_update_message in raw_entries:
            exchange_order_id = str(order_update_message.get("i") or "")
            client_order_index = str(order_update_message.get("I") or "")

            # Populate mapping regardless of whether we have a tracked order.
            if exchange_order_id and client_order_index:
                self._client_order_index_to_order_index[client_order_index] = exchange_order_id

            # Try direct lookup by exchange order_index first (works once exchange_order_id is updated).
            tracked_order = tracked_orders_by_oid.get(exchange_order_id)
            # Then try by client_order_index (works on first WS update after placement).
            if tracked_order is None and client_order_index:
                tracked_order = tracked_orders_by_client.get(client_order_index)

            if tracked_order is None:
                continue

            raw_status = order_update_message.get("os", "")
            order_status = CONSTANTS.ORDER_STATE.get(raw_status)
            if order_status is None:
                self.logger().warning(f"Unknown order status '{raw_status}' in WS update")
                continue

            # Use real exchange order_index as exchange_order_id going forward.
            resolved_eid = exchange_order_id if exchange_order_id else tracked_order.exchange_order_id
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=order_update_message.get("ut", 0) / 1000,
                new_state=order_status,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=resolved_eid,
            )
            self._order_tracker.process_order_update(order_update)

    async def _process_account_positions_ws_event_message(self, event_message: Dict[str, Any]):
        """
        https://docs.lighter.fi/api-documentation/api/websocket/subscriptions/account-positions
        {
            "channel": "subscribe",
            "data": {
                "source": "account_positions",
                "account": "BrZp5..."
            }
            }
            // this is the initialization snapshot
            {
            "channel": "account_positions",
            "data": [
                {
                "s": "BTC",
                "d": "bid",
                "a": "0.00022",
                "p": "87185",
                "m": "0",
                "f": "-0.00023989",
                "i": false,
                "l": null,
                "t": 1764133203991
                }
            ],
            "li": 1559395580
            }
            // this shows the position being increased by an order filling
            {
            "channel": "account_positions",
            "data": [
                {
                "s": "BTC",
                "d": "bid",
                "a": "0.00044",
                "p": "87285.5",
                "m": "0",
                "f": "-0.00023989",
                "i": false,
                "l": "-95166.79231",
                "t": 1764133656974
                }
            ],
            "li": 1559412952
            }
            // this shows the position being closed
            {
            "channel": "account_positions",
            "data": [],
            "li": 1559438203
        }
        """
        # LIGHTER provides full snapshot of positions
        # if there're 2 positions available, it will only show those 2
        # if one of those 2 positions is closed -- you will see only 1
        # so it make sense to clear the storage of positions
        # and fill it with the positions from the response

        # the implementation is actually the same as the one for
        # HTTP calls self._update_positions()
        self._perpetual_trading.account_positions.clear()

        for position_entry in self._normalized_position_entries_from_event(event_message):
            hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(position_entry["s"])
            position_side = PositionSide.LONG if position_entry["d"] == "bid" else PositionSide.SHORT
            position_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
            amount = Decimal(position_entry["a"])
            if amount == Decimal("0"):
                # Skip closed positions (exchange may still send a trailing zero-amount entry)
                continue
            entry_price = Decimal(position_entry["p"])

            provided_unrealized_pnl = position_entry.get("upnl")
            if provided_unrealized_pnl is not None:
                unrealized_pnl = Decimal(str(provided_unrealized_pnl))
            else:
                price_record = self.get_LIGHTER_price(hb_trading_pair)
                mark_price = price_record.mark_price if price_record is not None else entry_price

                if position_side == PositionSide.LONG:
                    unrealized_pnl = (mark_price - entry_price) * amount
                else:
                    unrealized_pnl = (entry_price - mark_price) * amount

            # "f" field = cumulative funding P&L (positive = received, negative = paid)
            cumulative_funding = Decimal(str(position_entry.get("f") or "0"))
            unrealized_pnl += cumulative_funding

            position = Position(
                trading_pair=hb_trading_pair,
                position_side=position_side,
                unrealized_pnl=unrealized_pnl,
                entry_price=entry_price,
                amount=amount * (Decimal("-1.0") if position_side == PositionSide.SHORT else Decimal("1.0")),
                leverage=Decimal(self.get_leverage(hb_trading_pair))
            )
            self._perpetual_trading.set_position(position_key, position)

    async def _process_account_info_ws_event_message(self, event_message: Dict[str, Any]):
        """
        https://docs.lighter.fi/api-documentation/api/websocket/subscriptions/account-info
        {
            "channel": "account_info",
            "data": {
                "ae": "2000",
                "as": "1500",
                "aw": "1400",
                "b": "2000",
                "f": 1,
                "mu": "500",
                "cm": "400",
                "oc": 10,
                "pb": "0",
                "pc": 2,
                "sc": 2,
                "t": 1234567890
            }
        }
        """
        self._set_usdc_balances(
            total_balance=Decimal(event_message["data"]["ae"]),
            available_balance=Decimal(event_message["data"]["as"]),
        )
        self._fee_tier = int(event_message["data"].get("f", self._fee_tier))

    async def _process_account_trades_ws_event_message(self, event_message: Dict[str, Any]):
        """
        https://docs.lighter.fi/api-documentation/api/websocket/subscriptions/account-trades
        {
            "channel": "account_trades",
            "data": [
                {
                "h": 80063441,
                "i": 1559912767,
                "I": null,
                "u": "BrZp5bidJ3WUvceSq7X78bhjTfZXeezzGvGEV4hAYKTa",
                "s": "BTC",
                "p": "89477",
                "o": "89505",
                "a": "0.00036",
                "te": "fulfill_taker",
                "ts": "close_long",
                "tc": "normal",
                "f": "0.012885",
                "n": "-0.022965",
                "t": 1765018588190,
                "li": 1559912767
                }
            ]
        }
        """
        tracked_orders = {order.exchange_order_id: order for order in self._order_tracker.all_fillable_orders.values()}

        for trade_message in self._normalized_trade_entries_from_event(event_message):
            exchange_order_id = str(trade_message["i"])
            tracked_order = tracked_orders.get(exchange_order_id)
            if not tracked_order:
                continue

            trade_timestamp = Decimal(str(trade_message["t"]))
            fill_timestamp = float(trade_timestamp / Decimal("1000")) if trade_timestamp > Decimal("1000000000000") else float(trade_timestamp)

            trade_id = trade_message.get("trade_id") or self.get_LIGHTER_finance_trade_id(
                order_id=trade_message["i"],
                timestamp=fill_timestamp,
                fill_base_amount=Decimal(trade_message["a"]),
                fill_price=Decimal(trade_message["p"]),
            )

            # it would always be USDC
            fee_asset = tracked_order.quote_asset

            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=tracked_order.position,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(
                    amount=Decimal(trade_message["f"]),
                    token=fee_asset
                )]
            )

            trade_update = TradeUpdate(
                trade_id=trade_id,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                fee=fee,
                fill_base_amount=Decimal(trade_message["a"]),
                fill_quote_amount=Decimal(trade_message["p"]) * Decimal(trade_message["a"]),
                fill_price=Decimal(trade_message["p"]),
                fill_timestamp=fill_timestamp,
            )

            self._order_tracker.process_trade_update(trade_update)

    def set_LIGHTER_price(self, trading_pair: str, timestamp: float, index_price: Decimal, mark_price: Decimal):
        """
        Set the price information for the given trading pair

        :param trading_pair: the trading pair
        :param timestamp: the timestamp of the price (in seconds)
        :param index_price: the index price
        :param mark_price: the mark price
        """
        existing = self._prices.get(trading_pair)
        if existing is None or timestamp >= existing.timestamp:
            self._prices[trading_pair] = LighterPerpetualPriceRecord(
                timestamp=timestamp,
                index_price=index_price,
                mark_price=mark_price
            )

    def get_LIGHTER_price(self, trading_pair: str) -> Optional[LighterPerpetualPriceRecord]:
        """
        Get the price information for the given trading pair

        :param trading_pair: the trading pair

        :return: the price information for the given trading pair or None if the trading pair is not found
        """
        return self._prices.get(trading_pair)

    def get_LIGHTER_finance_trade_id(self, order_id: int, timestamp: float, fill_base_amount: Decimal, fill_price: Decimal) -> str:
        """
        Generate a trade ID for the given order ID, timestamp, base amount, and price

        :param order_id: the order ID
        :param timestamp: the timestamp of the trade (in seconds)
        :param fill_base_amount: the base amount of the trade
        :param fill_price: the price of the trade

        :return: the trade ID
        """
        return f"{order_id}_{timestamp}_{fill_base_amount}_{fill_price}"

    def round_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        """
        Round the given amount to the lot size defined in the trading rules for the given symbol
        Sample lot size is 0.001

        :param trading_pair: the trading pair
        :param amount: the amount to round

        :return: the rounded amount
        """
        return amount.quantize(self._trading_rules[trading_pair].min_base_amount_increment)

    def round_fee(self, fee_amount: Decimal) -> Decimal:
        """
        Round the given fee amount to the lot size defined in the trading rules for the given symbol

        :param fee_amount: the fee amount to round

        :return: the rounded fee amount
        """
        return round(fee_amount, 6)

    async def start_network(self):
        await self._fetch_or_create_api_config_key()
        # status polling is already started in super().start_network() -> _status_polling_loop()
        # but we need to ensure fee tier is fetched immediately
        # we call it before super() so that the rate limits are correctly set before the periodic loops start
        await self._update_balances()

        # super().start_network() calls restore_tracking_states() which re-populates the order tracker
        # with orders from the previous session.  We must call it first so that we only cancel the
        # bot-tracked stale orders and NOT any manually-placed orders on the exchange.
        await super().start_network()

        # Cancel only tracked stale orders from the previous session (not user-placed orders).
        # This avoids wiping manual orders while still cleaning up bot orders that survived a crash.
        if self._trading_required and self._trading_pairs:
            try:
                await self._cancel_tracked_stale_orders()
            except Exception as ex:
                self.logger().warning(f"[start_network] stale order cleanup error (non-fatal): {ex}")

    async def stop_network(self):
        # If any in-flight orders are still awaiting exchange confirmation (exchange_order_id
        # is None), briefly wait so they land on the exchange before we sweep.  This prevents
        # orders placed within ~3 s of "stop" from being silently abandoned on the exchange.
        pending = [o for o in self.in_flight_orders.values() if o.exchange_order_id is None]
        if pending:
            self.logger().info(
                "[stop_network] Waiting up to 3 s for %d in-flight order(s) to be confirmed "
                "before final cancel sweep.",
                len(pending),
            )
            await asyncio.sleep(3.0)
        try:
            await self._cancel_all_exchange_active_orders()
        except Exception as ex:
            self.logger().warning(f"[stop_network] Exchange order sweep error (non-fatal): {ex}")
        await super().stop_network()

    async def _place_modify(
        self,
        tracked_order,
        amount: Decimal,
        price: Decimal,
    ) -> bool:
        """Modify an existing order via the lighter signer client.

        :param tracked_order: the InFlightOrder (or compatible SimpleNamespace) to modify
        :param amount: new base amount
        :param price: new price
        :return: True if modify succeeded
        :raises IOError: if the signing/send operation fails
        """
        market_id, size_decimals, price_decimals, _ = await self._get_market_spec(tracked_order.trading_pair)
        signer_client = self._get_lighter_signer_client()

        base_amount_int = int(amount * Decimal(10 ** size_decimals))
        price_int = int(price * Decimal(10 ** price_decimals))

        _, response_obj, error = await signer_client.modify_order(
            market_index=market_id,
            order_index=int(tracked_order.exchange_order_id),
            base_amount=base_amount_int,
            price=price_int,
        )

        if error is not None:
            raise IOError(f"modify_order signing/send failed: {error}")

        return True

    async def _cancel_tracked_stale_orders(self) -> int:
        """
        Cancel only orders that are tracked in the local order tracker (restored from the previous
        session via restore_tracking_states).  This is the startup sweep — it cleans up bot-placed
        orders from a crashed or stopped previous session WITHOUT cancelling any orders the user
        placed manually on the exchange.

        Returns the number of orders successfully cancelled.
        """
        stale_orders = list(self._order_tracker.all_updatable_orders.values())
        if not stale_orders:
            return 0

        canceled_count = 0
        now = self.current_timestamp
        signer_client = self._refresh_signer_client()

        for stale_order in stale_orders:
            exchange_order_id = stale_order.exchange_order_id
            if not exchange_order_id:
                # Order wasn't confirmed by the exchange — mark cancelled locally, nothing to cancel on exchange
                self._order_tracker.process_order_update(OrderUpdate(
                    trading_pair=stale_order.trading_pair,
                    update_timestamp=now,
                    new_state=OrderState.CANCELED,
                    client_order_id=stale_order.client_order_id,
                    exchange_order_id=None,
                ))
                continue

            try:
                market_id, _, _, _ = await self._get_market_spec(stale_order.trading_pair)
            except Exception:
                market_id = None

            if market_id is None:
                self.logger().warning(
                    "[_cancel_tracked_stale_orders] Cannot resolve market for %s, skipping",
                    stale_order.client_order_id,
                )
                continue

            try:
                async with self._signer_request_lock:
                    _, _, error = await signer_client.cancel_order(
                        market_index=int(market_id),
                        order_index=int(exchange_order_id),
                        api_key_index=self._get_api_key_index(),
                    )
                if error is None:
                    canceled_count += 1
                    self.logger().info(
                        "[start_network] Canceled stale bot order %s (exchange_id=%s)",
                        stale_order.client_order_id,
                        exchange_order_id,
                    )
                else:
                    # Order may already be gone — still mark locally as cancelled
                    self.logger().debug(
                        "[_cancel_tracked_stale_orders] cancel_order error for %s (may already be gone): %s",
                        exchange_order_id, error,
                    )
            except Exception as ex:
                self.logger().warning(
                    "[_cancel_tracked_stale_orders] Exception cancelling %s: %s",
                    exchange_order_id, ex,
                )

            # Mark cancelled in local tracker regardless (prevents re-submission)
            self._order_tracker.process_order_update(OrderUpdate(
                trading_pair=stale_order.trading_pair,
                update_timestamp=now,
                new_state=OrderState.CANCELED,
                client_order_id=stale_order.client_order_id,
                exchange_order_id=exchange_order_id,
            ))

        if canceled_count > 0:
            self.logger().info(
                "[start_network] startup sweep canceled %d tracked stale orders", canceled_count
            )
        return canceled_count

    async def _cancel_all_exchange_active_orders(self) -> int:
        """
        Cancel all currently active exchange orders for configured trading pairs.
        This is a safety net for orders not tracked in local in-flight state.
        """
        if not self._trading_pairs:
            return 0

        signer_client = self._get_lighter_signer_client()
        active_orders_by_id: Dict[str, int] = {}

        for trading_pair in self._trading_pairs:
            try:
                market_id, _, _, _ = await self._get_market_spec(trading_pair)
                signer_client = self._get_lighter_signer_client()
                auth_token, _auth_err = signer_client.create_auth_token_with_expiry(
                    api_key_index=self._get_api_key_index()
                )
                params: Dict[str, Any] = {
                    "account_index": self._get_account_index(),
                    "market_id": market_id,
                    "limit": 200,
                    "auth": auth_token or "",
                }
                while True:
                    response = await self._api_get(
                        path_url="/accountActiveOrders",
                        params=params,
                        is_auth_required=True,
                        return_err=True,
                    )
                    if not self._is_ok_response(response):
                        self.logger().warning(
                            f"[_cancel_all_exchange_active_orders] Failed fetching active orders for {trading_pair}: {response}"
                        )
                        break

                    rows = response.get("data") or response.get("orders") or []
                    for row in rows:
                        order_id = str(row.get("order_id") or row.get("order_index") or row.get("i") or "")
                        if order_id:
                            active_orders_by_id[order_id] = market_id

                    if response.get("has_more") and response.get("next_cursor"):
                        params["cursor"] = response["next_cursor"]
                    else:
                        break
            except Exception as ex:
                self.logger().warning(
                    f"[_cancel_all_exchange_active_orders] Error fetching active orders for {trading_pair}: {ex}"
                )

        canceled_count = 0
        for order_id, market_id in active_orders_by_id.items():
            try:
                _, _, error = await signer_client.cancel_order(
                    market_index=int(market_id),
                    order_index=int(order_id),
                    api_key_index=self._get_api_key_index(),
                )
                if error is None:
                    canceled_count += 1
                else:
                    self.logger().warning(
                        f"[_cancel_all_exchange_active_orders] Failed to cancel order {order_id}: {error}"
                    )
            except Exception as ex:
                self.logger().warning(
                    f"[_cancel_all_exchange_active_orders] Exception cancelling order {order_id}: {ex}"
                )

        return canceled_count

    async def _resolve_order_index_from_active_orders(
        self,
        market_id: int,
        client_order_index: str,
        max_pages: int = 5,
    ) -> Optional[str]:
        """Query /accountActiveOrders to resolve client_order_index -> actual order_index.

        Returns the exchange-assigned order_index string, or None if not found.
        Also populates self._client_order_index_to_order_index as a side-effect.
        """
        try:
            signer_client = self._get_lighter_signer_client()
            auth_token, _auth_err = signer_client.create_auth_token_with_expiry(
                api_key_index=self._get_api_key_index()
            )
            params: Dict[str, Any] = {
                "account_index": self._get_account_index(),
                "market_id": market_id,
                "limit": 200,
                "auth": auth_token or "",
            }

            for _ in range(max_pages):
                response = await self._api_get(
                    path_url=CONSTANTS.GET_ACTIVE_ORDERS_PATH_URL,
                    params=params,
                    is_auth_required=True,
                    return_err=True,
                )
                if not self._is_ok_response(response):
                    break

                rows = response.get("data") or response.get("orders") or []
                for row in rows:
                    row_oid = str(row.get("order_id") or row.get("order_index") or row.get("i") or "")
                    row_cid = str(row.get("client_order_id") or row.get("client_order_index") or row.get("I") or "")
                    if row_oid and row_cid:
                        self._client_order_index_to_order_index[row_cid] = row_oid
                    if row_cid == client_order_index and row_oid:
                        return row_oid

                if not response.get("has_more") or not response.get("next_cursor"):
                    break
                params["cursor"] = response["next_cursor"]
        except Exception as ex:
            self.logger().warning(f"[_resolve_order_index_from_active_orders] Error: {ex}")
        return None

    async def _refresh_signer_nonce(self) -> None:
        """Fetch fresh nonce from /nextNonce and update the signer client state.

        Called on 21104 (stale nonce) errors to resynchronise with the exchange.
        """
        try:
            response = await self._api_get(
                path_url=CONSTANTS.GET_NEXT_NONCE_PATH_URL,
                params={
                    "account_index": self._get_account_index(),
                    "api_key_index": self._get_api_key_index(),
                },
                return_err=True,
            )
            nonce = response.get("nonce") or response.get("next_nonce")
            if nonce is not None:
                new_base = int(nonce) * self._CLIENT_ORDER_INDEX_TIME_MULTIPLIER
                if new_base > self._last_client_order_index:
                    self._last_client_order_index = new_base
                    self.logger().debug(f"[_refresh_signer_nonce] Synced client_order_index base to {new_base}")
        except Exception as ex:
            self.logger().warning(f"[_refresh_signer_nonce] Failed: {ex}")

    async def _process_account_all_orders_ws_event_message(self, event_message: Dict[str, Any]) -> None:
        """Process the 'orders' dict from an account_all WS event.

        The account_all channel may include:
            "orders": { "{MARKET_INDEX}": [ Order, ... ], ... }
        where Order has both order_index (exchange-assigned) and client_order_index (ours).
        We use this to populate _client_order_index_to_order_index and emit OrderUpdates.
        """
        orders_by_market = event_message.get("orders")
        if not isinstance(orders_by_market, dict):
            return

        for market_orders in orders_by_market.values():
            if not isinstance(market_orders, list):
                market_orders = [market_orders] if isinstance(market_orders, dict) else []
            for order_entry in market_orders:
                if not isinstance(order_entry, dict):
                    continue
                order_index = str(order_entry.get("order_index") or order_entry.get("order_id") or order_entry.get("i") or "")
                client_index = str(order_entry.get("client_order_index") or order_entry.get("client_order_id") or order_entry.get("I") or "")
                if order_index and client_index:
                    self._client_order_index_to_order_index[client_index] = order_index

                # Find the matching tracked order and emit an OrderUpdate.
                for tracked_order in list(self._order_tracker.all_updatable_orders.values()):
                    tracked_eid = str(tracked_order.exchange_order_id)
                    if tracked_eid != client_index and tracked_eid != order_index:
                        continue
                    raw_status = str(order_entry.get("status") or "open").replace("-", "_")
                    order_status = CONSTANTS.ORDER_STATE.get(raw_status) or CONSTANTS.ORDER_STATE.get(
                        str(order_entry.get("status") or "open")
                    )
                    if order_status is None:
                        break
                    resolved_eid = order_index if order_index else tracked_eid
                    ts_raw = order_entry.get("updated_at") or order_entry.get("timestamp") or 0
                    order_update = OrderUpdate(
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=float(ts_raw) / 1000 if ts_raw > 1_000_000_000_000 else float(ts_raw),
                        new_state=order_status,
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=resolved_eid,
                    )
                    self._order_tracker.process_order_update(order_update)
                    break

    async def get_all_pairs_prices(self) -> List[Dict[str, Any]]:
        """
        Retrieves the prices (mark price) for all trading pairs.
        Required for Rate Oracle support.

        https://docs.lighter.fi/api-documentation/api/rest-api/markets/get-prices
        Prices Info
        ```
         {
            "success": true,
            "data": [
                {
                "funding": "0.00010529",
                "mark": "1.084819",
                "mid": "1.08615",
                "next_funding": "0.00011096",
                "open_interest": "3634796",
                "oracle": "1.084524",
                "symbol": "XPL",
                "timestamp": 1759222967974,
                "volume_24h": "20896698.0672",
                "yesterday_price": "1.3412"
                }
            ],
            "error": null,
            "code": null
        }
        ```

        Sample output:
        ```
        [
            {
            "symbol": "XPL",
            "price": "1.084819"
            },
        ]
        ```

        :return: A list of dictionaries containing symbol and a price
        """
        response = await self._api_get(
            path_url=CONSTANTS.GET_PRICES_PATH_URL,
            return_err=True,
        )

        if not response.get("success") is True:
            self.logger().error(f"[get_all_pairs_prices] Failed to fetch all pairs prices: {response}")
            return []

        results = []
        for price_data in response.get("data", []):
            results.append({
                "trading_pair": await self.trading_pair_associated_to_exchange_symbol(symbol=price_data["symbol"]),
                "price": price_data["mark"]
            })

        return results
