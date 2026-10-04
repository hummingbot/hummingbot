import asyncio
import hashlib
import re
import time
from copy import deepcopy
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import SECOND, s_decimal_NaN
from hummingbot.connector.derivative.derive_perpetual import (
    derive_perpetual_constants as CONSTANTS,
    derive_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_api_order_book_data_source import (
    DerivePerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_api_user_stream_data_source import (
    DerivePerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_auth import DerivePerpetualAuth
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.other.derive_common_utils import describe_error, estimate_max_fee, parse_subaccount_id
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

s_decimal_0 = Decimal(0)


class DerivePerpetualDerivative(PerpetualDerivativePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            session_private_key: str = None,
            subacct_id: int = None,
            account_type: str = None,
            derive_perpetual_wallet_address: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.derive_perpetual_wallet_address = derive_perpetual_wallet_address
        self.session_private_key = session_private_key
        # Credentials arrive as strings, and most v3 routes refuse one where an integer is
        # declared. The id is normalised once here rather than at each request body carrying it.
        self._subacct_id = parse_subaccount_id(subacct_id)
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._account_type = account_type
        self._position_mode = None
        self._last_trade_history_timestamp = None
        self._last_trades_poll_timestamp = 1.0
        self._instrument_ticker = []
        self._resting_close_warning_logged = False
        self._positions_poll_lock = asyncio.Lock()
        self._positions_catch_up_task: Optional[asyncio.Task] = None
        self._positions_catch_up_polls_left = 0
        self.real_time_balance_update = False
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        # Note: domain here refers to the entire exchange name. i.e. derive_perpetual_ or derive_perpetual_testnet
        return self._domain

    @staticmethod
    def derive_perpetual_order_type(order_type: OrderType) -> str:
        return order_type.name.lower()

    @property
    def authenticator(self) -> DerivePerpetualAuth:
        return DerivePerpetualAuth(
            self.derive_perpetual_wallet_address,
            self.session_private_key,
            self._subacct_id,
            self._trading_required,
            self._domain)

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
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_currencies_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_CURRENCIES_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_PATH_URL

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
        return 120

    async def _make_network_check_request(self):
        await self._api_get(path_url=self.check_network_request_path)

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self):
        """
        This method needs to be overridden to provide the accurate information depending on the exchange.
        """
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    async def _make_trading_pairs_request(self) -> Any:
        """
        Fetches every instrument of this connector's type.

        v3 returns {instruments, pagination} and caps page_size, so a single request is no longer
        guaranteed to return everything. Walk the pages rather than assuming one is enough.
        """
        info = []
        page = 1
        while True:
            payload = {
                # Expired instruments cannot be traded and only bloat the symbol map.
                "expired": False,
                "instrument_type": CONSTANTS.INSTRUMENT_TYPE,
                "page": page,
                "page_size": CONSTANTS.INSTRUMENTS_PAGE_SIZE,
            }
            exchange_info = await self._api_post(
                path_url=self.trading_currencies_request_path, data=payload
            )
            result = exchange_info["result"]
            info.extend(result["instruments"])

            num_pages = (result.get("pagination") or {}).get("num_pages", 1)
            if page >= num_pages:
                break
            page += 1

        self._instrument_ticker = info
        return info

    async def _make_trading_rules_request(self) -> Any:
        """
        Trading rules come from the same instrument list as the trading pairs.

        This used to issue its own single-page request with page_size 1000, bypassing the paged
        fetch, and returned the whole {instruments, pagination} wrapper rather than the
        instrument list, so anything iterating the result got the wrapper's keys.
        """
        return await self._make_trading_pairs_request()

    async def get_all_pairs_prices(self) -> Dict[str, Any]:
        res = []
        tasks = []
        if len(self._instrument_ticker) == 0:
            await self._make_trading_pairs_request()
        for token in self._instrument_ticker:
            payload = {"instrument_name": token["instrument_name"]}
            tasks.append(self._api_post(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, data=payload))
        results = await safe_gather(*tasks, return_exceptions=True)
        for result in results:
            pair_price_data = result["result"]

            data = {
                "symbol": {
                    "instrument_name": pair_price_data["instrument_name"],
                    "best_bid": pair_price_data["best_bid_price"],
                    "best_ask": pair_price_data["best_ask_price"],
                }
            }
            res.append(data)
        return res

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List):
        mapping = bidict()

        for _info in filter(web_utils.is_exchange_information_valid, exchange_info):
            ex_name = _info["instrument_name"]

            # The quote was hardcoded to USDC, which silently mislabels any contract quoted in
            # anything else. The instrument definition carries it.
            base = _info.get("base_currency") or ex_name.split("-")[0]
            quote = _info.get("quote_currency") or "USDC"
            trading_pair = combine_to_hb_trading_pair(base, quote)
            mapping[ex_name] = trading_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _update_trading_rules(self):
        exchange_info = await self._make_trading_pairs_request()
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return DerivePerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return DerivePerpetualAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def start_network(self):
        await super().start_network()
        await self._verify_session_key()
        self._rate_limits_polling_task = safe_ensure_future(self._rate_limits_polling_loop())

    async def _verify_session_key(self) -> None:
        """
        Checks the session key is registered against the configured wallet before trading, and
        reads how long it has left.

        Without this the first authenticated call fails with a bare 14026, which does not say
        whether the key is unregistered, expired, or simply paired with a different wallet than
        the one entered. public/get_wallets_from_session_key is a public lookup that answers
        exactly that, so the mismatch can be named instead of guessed at.
        """
        if not self._trading_required:
            return

        try:
            signer = self._auth.session_key_wallet.address
        except Exception:
            return

        if signer.lower() == (self.derive_perpetual_wallet_address or "").lower():
            # The owner wallet is signing for itself. That is a valid setup with no session key
            # behind it, and the lookup below would report the wallet as an unknown key.
            return

        try:
            response = await self._api_post(
                path_url=CONSTANTS.SESSION_KEY_WALLETS_PATH_URL,
                data={"public_session_key": signer},
            )
        except Exception:
            # A failed lookup is not itself a reason to refuse to start.
            self.logger().debug("Could not verify the Derive session key.", exc_info=True)
            return

        if "error" in response:
            code = response["error"].get("code")
            self.logger().error(
                self._session_key_hint(code)
                or f"Derive rejected the session key {signer}: {describe_error(response['error'])}"
            )
            return

        wallets = [w.lower() for w in (response.get("result") or {}).get("wallets", [])]
        if not wallets:
            return

        if self.derive_perpetual_wallet_address.lower() not in wallets:
            self.logger().error(
                f"The session key {signer} is registered, but to a different wallet. It is "
                f"registered to {', '.join(wallets)}, while this connector is configured with "
                f"{self.derive_perpetual_wallet_address}. Enter the Derive wallet the key belongs to, which is "
                f"the account address shown at derive.xyz rather than the session key's own "
                f"address."
            )
            return

        await self._update_session_key_expiry(signer)

    async def _update_session_key_expiry(self, signer: str) -> None:
        """
        Reads the session key's expiry so that no order is signed to outlive it.

        A resting order is signed for as long as the API allows, because v3 expires an order when
        its signature does. An action that outlives its key is refused with 14038, so that window
        has to be held inside the key's own lifetime.
        """
        expiry = None
        try:
            response = await self._api_post(
                path_url=CONSTANTS.SESSION_KEYS_PATH_URL,
                data={"wallet": self.derive_perpetual_wallet_address},
                is_auth_required=True,
            )
            if "error" in response:
                reason = describe_error(response["error"])
            else:
                session_keys = (response.get("result") or {}).get("public_session_keys") or []
                expiry = next(
                    (
                        int(session_key["expiry_sec"])
                        for session_key in session_keys
                        if str(session_key.get("public_session_key", "")).lower() == signer.lower()
                    ),
                    None,
                )
                reason = "private/session_keys did not list this key"
        except asyncio.CancelledError:
            raise
        except Exception as error:
            reason = str(error) or type(error).__name__

        if expiry is None:
            # Not knowing the expiry is no reason to refuse to start, but it has to be visible:
            # resting orders are then signed past the lifetime of any key shorter-lived than the
            # API's ceiling. The first one refused for that makes _place_order read it again.
            self.logger().warning(
                f"Could not read the expiry of the Derive session key ({reason}). Until it is known, "
                f"resting orders are signed for the longest the exchange allows; if the key expires "
                f"sooner the exchange refuses them with 14038, and the expiry is read again then."
            )
            return

        self._auth.session_key_expiry_sec = expiry

    async def _session_key_expiry_was_stale(self, order_result: Dict[str, Any]) -> bool:
        """
        True when an order was refused for outliving its session key and the key's expiry, read
        again, differs from the one the order was signed against - so signing it again succeeds.

        The expiry is otherwise read once, at startup. If that lookup failed, or the key has been
        given a nearer expiry since, every resting order would be refused with 14038 until the
        connector was restarted.
        """
        if (order_result.get("error") or {}).get("code") != CONSTANTS.ERR_SIGNATURE_EXPIRY_AFTER_SESSION_KEY:
            return False
        signed_against = self._auth.session_key_expiry_sec
        await self._update_session_key_expiry(self._auth.session_key_wallet.address)
        return self._auth.session_key_expiry_sec not in (None, signed_against)

    @staticmethod
    def _error_code(exception: Exception) -> Optional[int]:
        """
        Pulls the v3 JSON-RPC error code out of an exception raised from a response body.

        v3 gives every failure a stable numeric code, so matching on those replaces both the
        string matching and the Binance error codes this connector used to carry.
        """
        match = re.search(r"['\"]?code['\"]?\s*[:=]\s*(-?\d+)", str(exception))
        return int(match.group(1)) if match else None

    async def _session_key_entered_as_wallet_hint(self) -> Optional[str]:
        """
        Explains the likeliest cause of "Account not found" on a first connection. A session key
        has an address of its own, and it is easily entered where the wallet address belongs. The
        key then signs as the owner of an account it does not have, so the exchange answers 14000
        and says nothing about session keys.

        public/get_wallets_from_session_key tells which wallet the key belongs to, so the address
        to enter instead can be named. None when the address entered is not a registered key.
        """
        signer = self._auth.signer_address
        if signer is None or signer.lower() != (self.derive_perpetual_wallet_address or "").lower():
            return None
        try:
            response = await self._api_post(
                path_url=CONSTANTS.SESSION_KEY_WALLETS_PATH_URL,
                data={"public_session_key": signer},
            )
            wallets = (response.get("result") or {}).get("wallets") or []
        except asyncio.CancelledError:
            raise
        except Exception:
            return None
        if not wallets:
            return None
        return (
            f"Derive account error {CONSTANTS.ERR_ACCOUNT_NOT_FOUND}: the wallet address entered, {signer}, is the "
            f"address of the session key itself. Derive has that key registered to {', '.join(wallets)}: enter "
            f"that as the wallet address, and keep the session key as it is."
        )

    @staticmethod
    def _session_key_hint(code: Optional[int]) -> Optional[str]:
        """
        Turns a v3 session-key or account error code into something actionable.

        v3 session keys are scoped, so "unauthorized" usually means the key is registered but
        lacks the trading scope rather than that the credentials are wrong.
        """
        if code in CONSTANTS.SESSION_KEY_ERROR_CODES:
            return f"Derive session key error {code}: {CONSTANTS.SESSION_KEY_ERROR_HINTS[code]}"
        if code in CONSTANTS.ACCOUNT_ERROR_HINTS:
            return f"Derive account error {code}: {CONSTANTS.ACCOUNT_ERROR_HINTS[code]}"
        return None

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return self._error_code(status_update_exception) in CONSTANTS.ORDER_NOT_EXIST_ERROR_CODES

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return self._error_code(cancelation_exception) in CONSTANTS.ORDER_NOT_EXIST_ERROR_CODES

    def _estimate_order_max_fee(
        self,
        instrument: Dict[str, Any],
        trading_pair: str,
        limit_price: Decimal,
        can_take: bool = True,
    ) -> Decimal:
        """
        Derives the max_fee to sign an order with.

        The fee ceiling is part of the signed payload, so a flat value (this used to send 1000 for
        every order) is either wildly over-permissive or, on an expensive instrument, too low - in
        which case the order is rejected with 11023 or cancelled with signed_max_fee_too_low.

        The engine costs the fee off max(limit price, index price). The index comes from the
        funding info, which the ticker stream keeps current. The local mid only stands in until
        that has arrived: it is not the index, and on a book with no orders there is no mid at
        all, which would leave a bid well below the market costed off its own limit price.
        """
        try:
            index_price = self._perpetual_trading.get_funding_info(trading_pair).index_price
        except KeyError:
            index_price = None
        if not self._is_usable_price(index_price):
            try:
                index_price = self.get_mid_price(trading_pair)
            except Exception:
                index_price = None

        return estimate_max_fee(
            taker_fee_rate=Decimal(str(instrument.get("taker_fee_rate", "0"))),
            maker_fee_rate=Decimal(str(instrument.get("maker_fee_rate", "0"))),
            base_fee=Decimal(str(instrument.get("base_fee", "0"))),
            index_price=index_price if self._is_usable_price(index_price) else limit_price,
            limit_price=limit_price,
            amount_step=instrument.get("amount_step"),
            can_take=can_take,
        )

    @staticmethod
    def _is_usable_price(price: Optional[Decimal]) -> bool:
        try:
            return price is not None and not Decimal(price).is_nan() and Decimal(price) > s_decimal_0
        except Exception:
            return False

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        trade_base_fee = build_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            order_side=order_side,
            order_type=order_type,
            amount=amount,
            price=price,
            base_currency=base_currency.upper(),
            quote_currency=quote_currency.upper()
        )
        return trade_base_fee

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_trade_history(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

        # === loops and sync related methods === #
    async def _rate_limits_polling_loop(self):
        """
        Updates the rate limits.
        """
        try:
            await self._update_rate_limits()
        except NotImplementedError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().info(
                "Unexpected error while Updating rate limits."
            )

    async def _update_rate_limits(self):
        await self._initialize_rate_limits()

    async def _initialize_rate_limits(self):
        # Update rate limits
        for r_limit_id in CONSTANTS.ENDPOINTS["limits"]["non_matching"]:
            limit_id = None
            rate_limits_copy = deepcopy(self._throttler._rate_limits)

            if self._account_type == CONSTANTS.MARKET_MAKER_ACCOUNTS_TYPE:
                limit_id = r_limit_id
                interval = SECOND
                limit = CONSTANTS.MARKET_MAKER_NON_MATCHING
            else:
                limit_id = r_limit_id
                interval = SECOND
                limit = CONSTANTS.TRADER_NON_MATCHING

            if limit_id is not None and interval is not None:
                for r_l in rate_limits_copy:
                    if r_l.limit_id == limit_id:
                        rate_limits_copy.remove(r_l)
                rate_limits_copy.append(
                    RateLimit(
                        limit_id=limit_id,
                        limit=limit,
                        time_interval=interval,
                    )
                )
            self._throttler.set_rate_limits(rate_limits_copy)

    async def _update_order_status(self):
        await self._update_orders()

    async def _update_lost_orders_status(self):
        await self._update_lost_orders()

    async def _update_trading_fees(self):
        """
        Loads the per-instrument maker/taker rates published with the instrument definitions.

        Without this every order was costed at the connector's default schema, which was written
        as 0.01/0.03 - percentages in a field that holds decimals, so 1% and 3% rather than the
        0.01%/0.03% intended.
        """
        if len(self._instrument_ticker) == 0:
            await self._make_trading_pairs_request()

        for instrument in self._instrument_ticker:
            maker_fee = instrument.get("maker_fee_rate")
            taker_fee = instrument.get("taker_fee_rate")
            if maker_fee is None or taker_fee is None:
                continue
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                    symbol=instrument["instrument_name"]
                )
            except KeyError:
                continue
            self._trading_fees[trading_pair] = TradeFeeSchema(
                maker_percent_fee_decimal=Decimal(str(maker_fee)),
                taker_percent_fee_decimal=Decimal(str(taker_fee)),
            )

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        oid = await tracked_order.get_exchange_order_id()
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "instrument_name": symbol,
            "order_id": oid,
            "subaccount_id": int(self._subacct_id)
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=api_params,
            is_auth_required=True)

        if "error" in cancel_result:
            error = cancel_result["error"]
            # The base class recognises the "does not exist" code in this error and counts the
            # order as not found. Counting it here as well would write the order off in half
            # the attempts the tracker allows.
            raise IOError(describe_error(error))
        if "result" in cancel_result:
            if cancel_result["result"]["order_status"] == "cancelled":
                return True
        return False

    # === Orders placing ===

    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.LIMIT,
            price: Decimal = s_decimal_NaN,
            **kwargs) -> str:
        """
        Creates a promise to create a buy order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode('utf-8'))
        hex_order_id = f"0x{md5.hexdigest()}"
        if order_type is OrderType.MARKET:
            # Priced at the bare mid, an IOC market buy cannot cross the spread and simply does
            # not fill. Cross by the same slippage buffer the spot connector uses.
            mid_price = self.get_mid_price(trading_pair)
            market_price = mid_price * (Decimal("1") + Decimal(str(CONSTANTS.MARKET_ORDER_SLIPPAGE)))
            price = self.quantize_order_price(trading_pair, market_price)

        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

    def sell(self,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType = OrderType.LIMIT,
             price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode('utf-8'))
        hex_order_id = f"0x{md5.hexdigest()}"
        if order_type is OrderType.MARKET:
            mid_price = self.get_mid_price(trading_pair)
            market_price = mid_price * (Decimal("1") - Decimal(str(CONSTANTS.MARKET_ORDER_SLIPPAGE)))
            price = self.quantize_order_price(trading_pair, market_price)

        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
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
        Creates an order on the derivative exchange using the specified parameters.
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        if len(self._instrument_ticker) == 0:
            await self._make_trading_pairs_request()
        instrument = next((pair for pair in self._instrument_ticker if symbol == pair["instrument_name"]), None)
        if order_type is OrderType.LIMIT_MAKER:
            # A LIMIT_MAKER order has to be rejected rather than filled if it would cross.
            param_order_type = CONSTANTS.TIME_IN_FORCE_POST_ONLY
        elif order_type is OrderType.MARKET:
            param_order_type = CONSTANTS.TIME_IN_FORCE_IOC
        else:
            param_order_type = CONSTANTS.TIME_IN_FORCE_GTC
        type_str = DerivePerpetualDerivative.derive_perpetual_order_type(order_type)

        price_type = "limit" if type_str == "limit_maker" or type_str == "limit" else "market"
        quantized_price = self.quantize_order_price(trading_pair, Decimal(str(price)))
        quantized_amount = self.quantize_order_amount(trading_pair, Decimal(str(amount)))
        max_fee = self._estimate_order_max_fee(
            instrument=instrument,
            trading_pair=trading_pair,
            limit_price=quantized_price,
            # A post-only order never takes, so it never incurs the per-order base fee.
            can_take=param_order_type != CONSTANTS.TIME_IN_FORCE_POST_ONLY,
        )
        # reduce_only is what stops a close from running through zero into the opposite position,
        # but v3 only accepts it on an order that cannot rest: market, IOC or FOK. On a resting
        # close it is refused with 11024, so a GTC or post-only close goes out without it, as it
        # did under v2.
        reduce_only = position_action == PositionAction.CLOSE and (
            price_type == "market" or param_order_type in CONSTANTS.REDUCE_ONLY_TIME_IN_FORCE
        )
        if position_action == PositionAction.CLOSE and not reduce_only and not self._resting_close_warning_logged:
            # Nothing the connector can send protects a resting close, so the exposure is stated
            # once rather than left to be discovered.
            self._resting_close_warning_logged = True
            self.logger().warning(
                "Derive only accepts reduce_only on orders that cannot rest (market, IOC, FOK), so a "
                "limit or post-only close is not reduce-only. If the position is closed some other "
                "way first, cancel the resting close: left on the book it would open a position in "
                "the opposite direction."
            )
        api_params = {
            "asset_address": instrument["base_asset_address"],
            "sub_id": instrument["base_asset_sub_id"],
            "limit_price": str(quantized_price),
            "type": "order",
            "max_fee": str(max_fee),
            "amount": str(quantized_amount),
            "instrument_name": symbol,
            "label": order_id,
            "is_bid": True if trade_type is TradeType.BUY else False,
            "direction": "buy" if trade_type is TradeType.BUY else "sell",
            "order_type": price_type,
            "reduce_only": reduce_only,
            "referral_code": CONSTANTS.REFERRAL_CODE,
            "mmp": False,
            "time_in_force": param_order_type,
            "recipient_id": self._subacct_id,
        }

        order_result = await self._api_post(
            path_url = CONSTANTS.CREATE_ORDER_URL,
            data=api_params,
            is_auth_required=True)

        if await self._session_key_expiry_was_stale(order_result):
            # The order is signed as the request goes out, so sending it again signs it against
            # the expiry that has just been read.
            order_result = await self._api_post(
                path_url = CONSTANTS.CREATE_ORDER_URL,
                data=api_params,
                is_auth_required=True)

        if "error" in order_result:
            error = order_result["error"]
            code = error.get("code")
            message = describe_error(error)
            if code == CONSTANTS.ERR_SELF_CROSSING:
                self.logger().warning(f"Order {order_id} would have crossed one of this account's own orders: {message}")
            elif code == CONSTANTS.ERR_POST_ONLY_WOULD_CROSS:
                self.logger().warning(
                    f"Post-only order {order_id} would have crossed the book and was rejected: {message}"
                )
            elif code == CONSTANTS.ERR_MAX_FEE_TOO_LOW:
                message = (
                    f"the signed max_fee was below the fee the trade would incur ({message}). This "
                    f"usually means the index price moved sharply between pricing and signing."
                )
            elif code == CONSTANTS.ERR_INVALID_PARAMS and "risk universe" in str(error.get("data") or "").lower():
                message = f"{message}. {CONSTANTS.RISK_UNIVERSE_HINT}"
            else:
                message = self._session_key_hint(code) or message
            raise IOError(f"Error submitting order {order_id}: {message}")

        o_data = order_result['result'].get("order")
        return (str(o_data["order_id"]), o_data["creation_timestamp"] * 1e-3)

    async def _update_trade_history(self):
        orders = list(self._order_tracker.all_fillable_orders.values())
        all_fillable_orders = self._order_tracker.all_fillable_orders_by_exchange_order_id
        all_fills_response = []
        if len(orders) > 0:
            try:
                all_fills_response = await self._api_get(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    params={
                        "subaccount_id": self._subacct_id
                    },
                    is_auth_required=True,
                    limit_id=CONSTANTS.MY_TRADES_PATH_URL)
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                self.logger().warning(
                    f"Failed to fetch trade updates. Error: {request_error}",
                    exc_info = request_error,
                )
            for trade_fill in all_fills_response["result"]["trades"]:
                await self._process_trade_rs_event_message(order_fill=trade_fill, all_fillable_order=all_fillable_orders)

    async def _process_trade_rs_event_message(self, order_fill: Dict[str, Any], all_fillable_order):
        exchange_order_id = str(order_fill.get("order_id"))
        fillable_order = all_fillable_order.get(exchange_order_id)
        if fillable_order is not None:
            fee_asset = fillable_order.quote_asset
            # The fill's own direction always matches the order's trade type, so deriving the
            # position action from it is tautological - it was always CLOSE while the comparison
            # was against a string, and always OPEN once that was fixed. The order already
            # carries the PositionAction it was placed with.
            position_action = fillable_order.position
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=Decimal(order_fill["trade_fee"]), token=fee_asset)]
            )

            trade_update = TradeUpdate(
                trade_id=str(order_fill["trade_id"]),
                client_order_id=fillable_order.client_order_id,
                exchange_order_id=str(order_fill["order_id"]),
                trading_pair=fillable_order.trading_pair,
                fee=fee,
                fill_base_amount=Decimal(order_fill["trade_amount"]),
                fill_quote_amount=Decimal(order_fill["trade_price"]) * Decimal(order_fill["trade_amount"]),
                fill_price=Decimal(order_fill["trade_price"]),
                fill_timestamp=order_fill["timestamp"] * 1e-3,
            )

            self._order_tracker.process_trade_update(trade_update)

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
                    app_warning_msg="Could not fetch user events from DerivePerpetual. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        user_channels = [
            f"{self._subacct_id}.{CONSTANTS.USER_ORDERS_ENDPOINT_NAME}",
            f"{self._subacct_id}.{CONSTANTS.USEREVENT_ENDPOINT_NAME}",
            "positions",
            "collaterals",
        ]
        async for event_message in self._iter_user_event_queue():
            try:
                if isinstance(event_message, dict):
                    if "channel" in event_message:
                        channel: str = event_message.get("channel", None)
                        results = event_message.get("data", None)
                    else:
                        if "collaterals" in event_message["result"]:
                            channel = "collaterals"
                            results = event_message.get("result", {})
                        elif "positions" in event_message["result"]:
                            channel = "positions"
                            results = event_message.get("result", {})
                        else:
                            channel = "none"

                elif event_message is asyncio.CancelledError:
                    raise asyncio.CancelledError
                else:
                    raise Exception(event_message)
                if channel not in user_channels:
                    self.logger().error(
                        f"Unexpected message in user stream: {event_message}.", exc_info=True)
                    continue
                if channel == user_channels[0] and results is not None:
                    for order_msg in results:
                        self._process_order_message(order_msg)
                elif channel == user_channels[1] and results is not None:
                    for trade_msg in results:
                        await self._process_trade_message(trade_msg)
                elif channel == user_channels[2] and results is not None:
                    await self._process_update_positions(results)
                elif channel == user_channels[3] and results is not None:
                    for balance_msg in results["collaterals"]:
                        self._process_update_balances(balance_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _process_update_positions(self, results):
        for asset in results["positions"]:
            trading_pair = asset["instrument_name"]
            try:
                hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(trading_pair)
                if hb_trading_pair in self.trading_pairs:
                    # Decimal(x, 0) passes 0 as the *context*, not a rounding argument, and
                    # raises. The amount is already an absolute quantity, so it also must not be
                    # rescaled by the amount step.
                    amount = Decimal(str(asset.get("amount")))
                    position_side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
                    pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
                    position = self._perpetual_trading.get_position(hb_trading_pair, position_side)
                    if position is not None:
                        if amount == Decimal("0"):
                            self._perpetual_trading.remove_position(pos_key)
                        else:
                            # average_price is the position's entry price. index_price is the
                            # current index and has nothing to do with where the position was
                            # opened, so using it reported entry prices that drift with the market.
                            entry_price = Decimal(str(asset.get("average_price")))
                            unrealized_pnl = Decimal(str(asset.get("unrealized_pnl")))
                            position.update_position(position_side=position_side,
                                                     unrealized_pnl=unrealized_pnl,
                                                     entry_price=entry_price,
                                                     amount=amount)
                    else:
                        await self._update_positions()
            except KeyError:
                continue

    def _process_update_balances(self, balance_msg):
        asset_name = balance_msg["asset_name"]
        self._account_balances[asset_name] = Decimal(balance_msg["amount"])
        self._account_available_balances[asset_name] = Decimal(balance_msg["amount"])

    async def _process_trade_message(self, trade: Dict[str, Any], client_order_id: Optional[str] = None):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        Example Trade:
        """
        exchange_order_id = str(trade.get("order_id", ""))
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

        if tracked_order is None:
            all_orders = self._order_tracker.all_fillable_orders
            for k, v in all_orders.items():
                await v.get_exchange_order_id()
            _cli_tracked_orders = [o for o in all_orders.values() if exchange_order_id == o.exchange_order_id]
            if not _cli_tracked_orders:
                self.logger().debug(f"Ignoring trade message with id {client_order_id}: not in in_flight_orders.")
                return
            tracked_order = _cli_tracked_orders[0]
        trading_pair = tracked_order.trading_pair
        symbol = await self.trading_pair_associated_to_exchange_symbol(symbol=trade["instrument_name"])
        if symbol == trading_pair:
            fee_asset = tracked_order.quote_asset
            # The fill's own direction always matches the order's trade type, so deriving the
            # position action from it is tautological - it was always CLOSE while the comparison
            # was against a string, and always OPEN once that was fixed. The order already
            # carries the PositionAction it was placed with.
            position_action = tracked_order.position
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=Decimal(trade["trade_fee"]), token=fee_asset)]
            )
            trade_update: TradeUpdate = TradeUpdate(
                trade_id=str(trade["trade_id"]),
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(trade["order_id"]),
                trading_pair=tracked_order.trading_pair,
                fill_timestamp=trade["timestamp"] * 1e-3,
                fill_price=Decimal(trade["trade_price"]),
                fill_base_amount=Decimal(trade["trade_amount"]),
                fill_quote_amount=Decimal(trade["trade_price"]) * Decimal(trade["trade_amount"]),
                fee=fee,
            )
            self._order_tracker.process_trade_update(trade_update)
            self._schedule_positions_catch_up()

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancelation or failure event if needed.

        :param order_msg: The order response from either REST or web socket API (they are of the same format)

        Example Order:
        """
        client_order_id = str(order_msg.get("label", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return
        current_state = order_msg["order_status"]
        order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_msg["last_update_timestamp"] * 1e-3,
            new_state=CONSTANTS.ORDER_STATE[current_state],
            client_order_id=order_msg["label"],
            exchange_order_id=str(order_msg["order_id"]),
        )
        self._order_tracker.process_order_update(order_update=order_update)

    async def _format_trading_rules(self, exchange_info_dict: List) -> List[TradingRule]:
        """
        Queries the necessary API endpoint and initialize the TradingRule object for each trading pair being traded.

        Parameters
        ----------
        exchange_info_dict:
            Trading rules dictionary response from the derivative

        {
            "result": {
                "instruments": [
                {
                    "instrument_type": "perp",
                    "instrument_name": "OP-USDC",
                    "scheduled_activation": 1728508925,
                    "scheduled_deactivation": 9223372036854776000,
                    "is_active": true,
                    "tick_size": "0.01",
                    "minimum_amount": "0.1",
                    "maximum_amount": "1000",
                    "amount_step": "0.01",
                    "mark_price_fee_rate_cap": "0",
                    "maker_fee_rate": "0.0015",
                    "taker_fee_rate": "0.0015",
                    "base_fee": "0.1",
                    "base_currency": "OP",
                    "quote_currency": "USD",
                    "option_details": null,
                    "perp_details": null,
                    "erc20_details": {
                    "decimals": 18,
                    "underlying_erc20_address": "0x15CEcd5190A43C7798dD2058308781D0662e678E",
                    "borrow_index": "1",
                    "supply_index": "1"
                    },
                    "base_asset_address": "0xE201fCEfD4852f96810C069f66560dc25B2C7A55",
                    "base_asset_sub_id": "0",
                    "pro_rata_fraction": "0",
                    "fifo_min_allocation": "0",
                    "pro_rata_amount_step": "1"
                }
                ],
                "pagination": {
                "num_pages": 1,
                "count": 1
                }
            },
            "id": "0f9131b4-2502-4f8e-afa4-adfce67a6509"
        }
        """

        trading_pair_rules = exchange_info_dict
        retval = []
        for rule in filter(web_utils.is_exchange_information_valid, trading_pair_rules):
            if rule["instrument_type"] != "perp":
                continue
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule["instrument_name"])
                min_order_size = rule["minimum_amount"]
                step_size = rule["amount_step"]
                tick_size = rule["tick_size"]
                collateral_token = "USDC"
                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=Decimal(min_order_size),
                        min_price_increment=Decimal(str(tick_size)),
                        min_base_amount_increment=Decimal(step_size),
                        buy_order_collateral_token=collateral_token,
                        sell_order_collateral_token=collateral_token,
                    )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {exchange_info_dict}. Skipping.",
                                    exc_info=True)
        return retval

    async def _update_balances(self):
        """
        Calls the REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_post(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            data={"subaccount_id": self._subacct_id},
            is_auth_required=True)
        if "error" in account_info:
            error = account_info["error"]
            message = f"Error fetching account balances: {describe_error(error)}"
            # The hint travels with the exception as well as the log: this is the call `connect`
            # validates credentials with, and its error text is all the user is shown.
            hint = self._session_key_hint(error.get("code"))
            if error.get("code") == CONSTANTS.ERR_ACCOUNT_NOT_FOUND:
                hint = await self._session_key_entered_as_wallet_hint() or hint
            if hint:
                message = f"{message}. {hint}"
            self.logger().error(message)
            # This used to be a bare `raise` outside any except block, which itself raises a
            # RuntimeError and buries the API error.
            raise IOError(message)

        balances = account_info["result"].get("collaterals") or []
        for balance_entry in balances:
            asset_name = balance_entry["asset_name"]
            total_balance = Decimal(str(balance_entry["amount"]))
            # v3 exposes no per-asset available balance. Derive is cross-margined, so
            # availability is a property of the whole subaccount: the Subaccount schema carries
            # subaccount_value, initial_margin and open_orders_margin as account-level USD
            # figures, and Collateral has no free-amount field at all.
            #
            # open_orders_margin is not that field. It is a USD margin figure, it is negative in
            # practice, and subtracting it from a token amount both inverts the sign and mixes
            # units - on the captured fixture it turns 15 tokens held into 102.88 "available".
            # Reporting the full holding is the honest reading until an account-level free-margin
            # figure can be verified against a funded subaccount.
            free_balance = total_balance
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        oid = await tracked_order.get_exchange_order_id()
        client_order_id = tracked_order.client_order_id
        order_update = await self._api_post(
            path_url=CONSTANTS.ORDER_STATUS_PATH_URL,
            data={
                "subaccount_id": self._subacct_id,
                "order_id": oid
            },
            is_auth_required=True)
        if "error" in order_update:
            error = order_update["error"]
            code = error.get("code")
            message = describe_error(error)
            if code in CONSTANTS.ORDER_NOT_EXIST_ERROR_CODES:
                # Raising is how the base class learns the order is gone. It counts every error
                # raised from here that way, and retires the order after a few, so nothing else
                # is raised: a rate limit or a backend hiccup must not write off a live order.
                #
                # It is also what a poll gets for an order that has only just finished: on
                # testnet private/get_order did not know a filled or cancelled order for 4 to 6
                # seconds, and then reported it. The base class writes an order off on the
                # fourth miss and polls no faster than every 5 seconds, so that passes.
                raise IOError(f"Error fetching the status of order {client_order_id}: {message}")
            self.logger().warning(
                f"Error fetching the status of order {client_order_id}: {self._session_key_hint(code) or message}"
            )
            return OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=tracked_order.current_state,
                client_order_id=client_order_id,
                exchange_order_id=oid,
            )

        result = order_update["result"]
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=result["last_update_timestamp"] * 1e-3,
            # A status this connector does not map leaves the order as it is tracked, for the same
            # reason: failing here would count towards retiring it.
            new_state=CONSTANTS.ORDER_STATE.get(result["order_status"], tracked_order.current_state),
            client_order_id=result.get("label") or client_order_id,
            exchange_order_id=str(result["order_id"]),
        )

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates: List[TradeUpdate] = []
        exchange_order_id = str(order.exchange_order_id)
        if order.exchange_order_id is not None:
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "instrument_name": trading_pair,
                    "order_id": exchange_order_id,
                    "subaccount_id": self._subacct_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_PATH_URL)

            for trade in all_fills_response["result"]["trades"]:
                fee_asset = order.quote_asset
                if str(trade["order_id"]) == exchange_order_id:
                    # The fill's own direction always matches the order's trade type, so deriving the
                    # position action from it is tautological - it was always CLOSE while the comparison
                    # was against a string, and always OPEN once that was fixed. The order already
                    # carries the PositionAction it was placed with.
                    position_action = order.position
                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema(),
                        position_action=position_action,
                        percent_token=fee_asset,
                        flat_fees=[TokenAmount(amount=Decimal(trade["trade_fee"]), token=fee_asset)])
                    trade_update = TradeUpdate(
                        trade_id=str(trade["trade_id"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(trade["trade_amount"]),
                        fill_quote_amount=Decimal(trade["trade_amount"]) * Decimal(trade["trade_price"]),
                        fill_price=Decimal(trade["trade_price"]),
                        fill_timestamp=trade["timestamp"] * 1e-3,
                    )
                    trade_updates.append(trade_update)

        # This used to fall off the end returning None, so the base class never saw the fills it
        # had asked for and they only landed via the separate trade-history poll.
        return trade_updates

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        await self.trading_pair_symbol_map()
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        payload = {"instrument_name": exchange_symbol}
        response = await self._api_post(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, data=payload, is_auth_required=False,
                                        limit_id=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL)

        # v3 slim ticker: mark price is "M".
        return float(response["result"]["M"])

    async def get_last_traded_prices(self, trading_pairs: List[str] = None) -> Dict[str, float]:
        if trading_pairs is None:
            trading_pairs = []

        symbol_map = await self.trading_pair_symbol_map()
        exchange_symbols = await asyncio.gather(*[
            self.exchange_symbol_associated_to_pair(trading_pair=pair) for pair in trading_pairs
        ])
        payloads = [{"instrument_name": symbol} for symbol in exchange_symbols]
        responses = await asyncio.gather(*[
            self._api_post(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, data=payload)
            for payload in payloads
        ])
        last_traded_prices = {}
        # The slim ticker does not echo the instrument name back, so pair each response with the
        # symbol it was requested for.
        for exchange_symbol, ticker in zip(exchange_symbols, responses):
            if exchange_symbol in symbol_map.keys():
                mapped_name = await self.trading_pair_associated_to_exchange_symbol(exchange_symbol)
                last_traded_prices[mapped_name] = Decimal(str(ticker["result"]["M"]))
        return last_traded_prices

    def _schedule_positions_catch_up(self):
        """
        Polls positions for a while after a fill.

        The REST view of a position trails the fill that changed it by up to several seconds (see
        POSITIONS_CATCH_UP_INTERVAL), so a single poll made as the fill arrives reports the
        position as it was before - and the next status poll can be two minutes away while the
        user stream is healthy. A fill that arrives during the catch-up extends it.
        """
        self._positions_catch_up_polls_left = CONSTANTS.POSITIONS_CATCH_UP_POLLS
        if self._positions_catch_up_task is None or self._positions_catch_up_task.done():
            self._positions_catch_up_task = safe_ensure_future(self._catch_up_positions())

    async def _catch_up_positions(self):
        while self._positions_catch_up_polls_left > 0:
            self._positions_catch_up_polls_left -= 1
            await self._sleep(CONSTANTS.POSITIONS_CATCH_UP_INTERVAL)
            try:
                await self._update_positions()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().debug("Could not refresh the positions after a fill.", exc_info=True)

    async def stop_network(self):
        if self._positions_catch_up_task is not None:
            self._positions_catch_up_task.cancel()
            self._positions_catch_up_task = None
        await super().stop_network()

    async def _update_positions(self):
        # The status poll and the user stream both land here, so two polls can be in flight at
        # once. They are taken one at a time: an older answer arriving after a newer one would
        # otherwise be applied over it, removing a position that has since been reopened.
        async with self._positions_poll_lock:
            await self._poll_positions()

    async def _poll_positions(self):
        # Taken before the request, so that a position opened while it is in flight is not
        # mistaken below for one that has gone.
        previously_tracked = set(self._perpetual_trading.account_positions.keys())
        positions = await self._api_post(path_url=CONSTANTS.POSITION_INFORMATION_URL,
                                         data={"subaccount_id": self._subacct_id},
                                         is_auth_required=True,
                                         limit_id=CONSTANTS.POSITION_INFORMATION_URL)
        if isinstance(positions, dict) and "error" in positions:
            # Returning quietly here left the connector reporting whatever positions it last saw,
            # with nothing in the log to say the poll had failed.
            error = positions["error"]
            code = error.get("code")
            hint = self._session_key_hint(code)
            raise IOError(f"Error fetching positions: {describe_error(error)}" + (f". {hint}" if hint else ""))
        if "result" in positions:
            data: List[dict] = positions["result"]["positions"]
            reported = set()
            for position in data:
                trading_pair = position.get("instrument_name")
                try:
                    hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(trading_pair)
                except KeyError:
                    # Ignore results for which their symbols is not tracked by the connector
                    continue
                position_side = PositionSide.LONG if Decimal(position.get("amount")) > 0 else PositionSide.SHORT
                unrealized_pnl = Decimal(position.get("unrealized_pnl"))
                # average_price is where the position was opened; index_price is the current
                # index and drifts with the market.
                entry_price = Decimal(str(position.get("average_price")))
                amount = Decimal(str(position.get("amount", 0)))
                # leverage is nullable and optional in the v3 schema. Derive is cross-margined, so
                # a position does not always have a figure of its own; when it has none, keep the
                # value already held rather than fail the whole poll on Decimal(None).
                reported_leverage = position.get("leverage")
                if reported_leverage in (None, ""):
                    leverage = Decimal(str(self._perpetual_trading.get_leverage(hb_trading_pair)))
                else:
                    leverage = Decimal(str(reported_leverage))
                pos_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
                if amount != 0:
                    _position = Position(
                        trading_pair=hb_trading_pair,
                        position_side=position_side,
                        unrealized_pnl=unrealized_pnl,
                        entry_price=entry_price,
                        amount=amount,
                        leverage=leverage
                    )
                    # The exchange's figure stays on the position. It is a measurement - the
                    # position's size against the subaccount's margin, 0.0069 for instance - not
                    # a setting. Stored as the pair's leverage it reached every later order,
                    # where Hummingbot budgets against it and records it in an integer column.
                    self._perpetual_trading.set_position(pos_key, _position)
                    reported.add(pos_key)
                else:
                    self._perpetual_trading.remove_position(pos_key)

            # v3 lists active positions only: one that has been closed stops appearing rather than
            # coming back with a zero amount. Waiting for that zero left a closed position in the
            # connector until it was restarted.
            for pos_key in previously_tracked - reported:
                self._perpetual_trading.remove_position(pos_key)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        # NOTE: This is default to ONEWAY as there is nothing available on current version of Vega
        return self._position_mode

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        # NOTE: There is no setting to set leverage in derive
        msg = "ok"
        success = True
        return success, msg

    def _instrument_for_trading_pair(self, trading_pair: str) -> Optional[Dict[str, Any]]:
        """Finds the cached instrument definition backing a Hummingbot trading pair."""
        try:
            base, quote = trading_pair.split("-")
        except ValueError:
            return None
        for instrument in self._instrument_ticker:
            if instrument.get("base_currency") == base and instrument.get("quote_currency") == quote:
                return instrument
        return None

    def get_max_leverage(self, trading_pair: str) -> Optional[Decimal]:
        """
        Returns the instrument's maximum leverage as published in its margin requirements.
        """
        instrument = self._instrument_for_trading_pair(trading_pair)
        if instrument is None:
            return None
        requirements = (instrument.get("perp_details") or {}).get("srm_perp_margin_requirements") or {}
        max_leverage = requirements.get("max_leverage")
        return Decimal(str(max_leverage)) if max_leverage is not None else None

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """
        Derive margins each subaccount as a whole rather than per position, so there is no
        per-instrument leverage to set. Report that rather than a bare "ok", and surface the
        instrument's own ceiling so the caller can see what the venue will actually allow.

        The parameter order here follows PerpetualDerivativePyBase. The previous signature was
        (mode, trading_pair), which only went unnoticed because it ignored both arguments.
        """
        max_leverage = self.get_max_leverage(trading_pair)
        ceiling = f" The maximum for {trading_pair} is {max_leverage}x." if max_leverage else ""
        msg = (
            f"Derive is cross-margined per subaccount, so leverage cannot be set per position and "
            f"the requested {leverage}x was not applied.{ceiling}"
        )
        # Reporting success here would have _execute_set_leverage cache the requested leverage
        # locally and log that it was set, leaving the strategy sizing against a number the
        # exchange never applied.
        return False, msg

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        payment_response = await self._api_post(
            path_url=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL,
            data={
                "page": 1,
                "page_size": 100,
                "start_timestamp": self._last_funding_time(),
                "instrument_name": symbol,
                "subaccount_id": self._subacct_id
            },
            is_auth_required=True,
            limit_id=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL)
        payload = {
            "instrument_name": symbol,
        }
        funding_info_response = await self._api_post(
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            data=payload)
        if "error" in payment_response:
            error = payment_response["error"]
            raise IOError(f"Error fetching funding history: {describe_error(error)}")
        events = payment_response["result"]["events"]
        if len(events) < 1:
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
            return timestamp, funding_rate, payment
        # The order the events come back in is not specified, so take the latest explicitly.
        funding_payment = max(events, key=lambda event: event["timestamp"])
        _payment = Decimal(funding_payment["funding"])
        # v3 slim ticker: "f" is the current hourly funding rate. perp_details is not part of
        # the slim payload any more.
        funding_rate = Decimal(str(funding_info_response["result"]["f"]))
        timestamp = funding_payment["timestamp"] * 1e-3
        if _payment != Decimal("0"):
            payment = _payment
        else:
            timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
        return timestamp, funding_rate, payment

    def _last_funding_time(self) -> int:
        """
        Start of the previous funding interval, in milliseconds.

        v3 documents "f" on the ticker as the current *hourly* funding rate and perp_details
        carries hourly min/max bounds, so funding still settles hourly.
        """
        interval = CONSTANTS.FUNDING_INTERVAL_SECONDS
        return int(((time.time() // interval) - 1) * interval * 1e3)
