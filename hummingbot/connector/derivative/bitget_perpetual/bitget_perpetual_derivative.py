import asyncio
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from bidict import bidict

import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bitget_perpetual import (
    bitget_perpetual_utils,
    bitget_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_api_order_book_data_source import (
    BitgetPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_api_user_stream_data_source import (
    BitgetPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_auth import BitgetPerpetualAuth
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_classic import BitgetPerpetualClassicAccountMixin
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_constants import MarginMode
from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.exchange.bitget import bitget_account
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_candidate import PerpetualOrderCandidate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class BitgetPerpetualBudgetChecker(PerpetualBudgetChecker):
    """
    The unified margin pool is reported in full under each collateral token that shares it (see
    _set_unified_margin_balances), so margin locked for one candidate is locked under all of them. Otherwise a
    USDT-margined and a USDC-margined order could each be approved against the same funds.
    """

    def _lock_available_collateral(self, order_candidate: PerpetualOrderCandidate):
        if order_candidate.position_close:
            return
        pooled_tokens = self._exchange.pooled_margin_tokens
        for token, amount in order_candidate.collateral_dict.items():
            for locked_token in (pooled_tokens if token in pooled_tokens else {token}):
                self._locked_collateral[locked_token] += amount


class BitgetPerpetualDerivative(BitgetPerpetualClassicAccountMixin, PerpetualDerivativePyBase):
    """
    Bitget futures, for both kinds of account. A Unified Trading Account (UTA) trades through the V3 API and a
    Classic account through V2; the connector reads which one the API key belongs to before its first private
    call and routes the private calls accordingly (Classic ones live in BitgetPerpetualClassicAccountMixin).
    Market data comes from the V3 public API for both.
    """

    web_utils = web_utils

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        bitget_perpetual_api_key: str = None,
        bitget_perpetual_secret_key: str = None,
        bitget_perpetual_passphrase: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ) -> None:

        self.bitget_perpetual_api_key = bitget_perpetual_api_key
        self.bitget_perpetual_secret_key = bitget_perpetual_secret_key
        self.bitget_perpetual_passphrase = bitget_perpetual_passphrase
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trade_history_timestamp = None
        self._unified_account: Optional[bool] = None
        self._account_mode_lock = asyncio.Lock()

        self._margin_mode = MarginMode.CROSS
        # Collateral tokens that currently report the same unified margin pool
        self._pooled_margin_tokens: Set[str] = set()

        super().__init__(balance_asset_limit, rate_limits_share_pct)
        self._budget_checker = BitgetPerpetualBudgetChecker(self)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def pooled_margin_tokens(self) -> Set[str]:
        """The collateral tokens whose balances are all the one unified margin pool, so they share one budget."""
        return self._pooled_margin_tokens

    @property
    def account_group_id(self) -> Optional[str]:
        """
        Bitget's UTA is a single cross-margined wallet, and this connector is one of two views
        onto it - bitget reads the same account. Both report the wallet in full, so
        without this they are summed twice. See bitget_account for how the id is keyed.
        A Classic account keeps separate spot and futures wallets, so it has no group.
        """
        if not self._unified_account:
            return None
        return bitget_account.account_group_id(self.bitget_perpetual_api_key)

    async def _is_unified_account(self) -> bool:
        """
        Whether the API key's account is a Unified Trading Account. Read once, before the first private call: the
        V3 account endpoints answer a Classic account with 40084, and any other failure is raised for a retry.
        """
        if self._unified_account is None:
            async with self._account_mode_lock:
                if self._unified_account is None:
                    try:
                        response = await self._api_get(
                            path_url=CONSTANTS.ACCOUNTS_INFO_ENDPOINT, is_auth_required=True
                        )
                        code = str(response.get("code"))
                    except IOError as error:
                        # Match the code field itself: the body's requestTime can contain the same digits.
                        if f'"code":"{CONSTANTS.RET_CODE_CLASSIC_ACCOUNT}"' not in str(error).replace(" ", ""):
                            raise
                        code = CONSTANTS.RET_CODE_CLASSIC_ACCOUNT
                    if code not in (CONSTANTS.RET_CODE_OK, CONSTANTS.RET_CODE_CLASSIC_ACCOUNT):
                        raise IOError(self._formatted_error(code, "Could not read the account mode"))
                    self._unified_account = code == CONSTANTS.RET_CODE_OK
                    self.logger().info(
                        f"Bitget account mode: {'Unified Trading Account' if self._unified_account else 'Classic'}."
                    )
        return self._unified_account

    async def _update_account_uid(self) -> None:
        api_key = self.bitget_perpetual_api_key
        if not bitget_account.needs_user_id(api_key):
            return
        user_id = None
        try:
            response = await self._api_get(path_url=CONSTANTS.USER_INFO_ENDPOINT, is_auth_required=True)
            user_id = (response.get("data") or {}).get("userId")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().debug(
                "Could not read the account user id; grouping balances by API key for now.", exc_info=True
            )
        if user_id:
            bitget_account.remember_user_id(api_key, str(user_id))
        else:
            bitget_account.user_id_read_failed(api_key)

    @property
    def authenticator(self) -> BitgetPerpetualAuth:
        return BitgetPerpetualAuth(
            api_key=self.bitget_perpetual_api_key,
            secret_key=self.bitget_perpetual_secret_key,
            passphrase=self.bitget_perpetual_passphrase,
            time_provider=self._time_synchronizer
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.ORDER_ID_MAX_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.PUBLIC_CONTRACTS_ENDPOINT

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PUBLIC_TIME_ENDPOINT

    @property
    def trading_pairs(self) -> Optional[List[str]]:
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

    @staticmethod
    def _formatted_error(code: int, message: str) -> str:
        return f"Error: {code} - {message}"

    async def start_network(self):
        # Initialize symbol mappings before starting network
        # This ensures get_funding_info can convert trading pairs to exchange symbols
        await self._initialize_trading_pair_symbol_map()
        await super().start_network()
        if self.is_trading_required:
            await self.set_margin_mode(self._margin_mode)
            await self._initialize_position_mode()

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    def _is_request_exception_related_to_time_synchronizer(
        self,
        request_exception: Exception
    ) -> bool:
        error_description = str(request_exception)
        ts_error_target_str = "Request timestamp expired"

        return ts_error_target_str in error_description

    def _collateral_token_based_on_trading_pair(self, trading_pair: str) -> str:
        """
        Returns the collateral token based on the trading pair
        (For example this method need for order cancellation)

        :return: The collateral token
        """
        base, quote = split_hb_trading_pair(trading_pair=trading_pair)

        if quote == "USD":
            collateral_token = base
        else:
            collateral_token = quote

        return collateral_token

    async def _fetch_account_position_mode(self) -> Optional[PositionMode]:
        """
        Fetches the current position mode from the Bitget exchange account.
        Uses the first trading pair to query the account info.
        """
        if not await self._is_unified_account():
            return await self._classic_fetch_account_position_mode()
        if not self.trading_pairs:
            return None
        trading_pair = self.trading_pairs[0]
        # V3 UTA account settings are account-level (no symbol/productType/marginCoin params).
        account_info_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_INFO_ENDPOINT,
            is_auth_required=True,
        )
        if account_info_response["code"] != CONSTANTS.RET_CODE_OK:
            self.logger().error(self._formatted_error(
                account_info_response["code"],
                f"Error getting position mode for {trading_pair}: {account_info_response['msg']}"
            ))
            return None

        position_modes = {
            "one_way_mode": PositionMode.ONEWAY,
            "hedge_mode": PositionMode.HEDGE,
            # V3 holdMode spellings
            "single_hold": PositionMode.ONEWAY,
            "double_hold": PositionMode.HEDGE,
        }

        # V3 renames posMode -> holdMode in the account settings payload.
        settings_data = account_info_response["data"]
        hold_mode = settings_data.get("holdMode", settings_data.get("posMode"))
        position_mode = position_modes[hold_mode]
        self.logger().info(f"Position mode for {trading_pair}: {position_mode}")
        return position_mode

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules.get(trading_pair, None)
        if trading_rule is None:
            collateral_token = self._collateral_token_based_on_trading_pair(
                trading_pair=trading_pair
            )
        else:
            collateral_token = trading_rule.buy_order_collateral_token

        return collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return self.get_buy_collateral_token(trading_pair=trading_pair)

    async def product_type_associated_to_trading_pair(self, trading_pair: str) -> str:
        """
        Returns the product type associated with the trading pair
        """
        _, quote = split_hb_trading_pair(trading_pair)

        if quote == "USDT":
            return CONSTANTS.USDT_PRODUCT_TYPE

        if quote == "USDC":
            return CONSTANTS.USDC_PRODUCT_TYPE

        return CONSTANTS.USD_PRODUCT_TYPE

    def _is_order_not_found_during_status_update_error(
        self,
        status_update_exception: Exception
    ) -> bool:
        # Error example:
        # { "code": "00000", "msg": "success", "requestTime": 1710327684832, "data": [] }

        if isinstance(status_update_exception, IOError):
            return any(
                value in str(status_update_exception)
                for value in CONSTANTS.RET_CODES_ORDER_NOT_EXISTS
            )

        if isinstance(status_update_exception, ValueError):
            return True

        return False

    def _is_order_not_found_during_cancelation_error(
        self,
        cancelation_exception: Exception
    ) -> bool:
        if isinstance(cancelation_exception, IOError):
            return any(
                value in str(cancelation_exception)
                for value in CONSTANTS.RET_CODES_ORDER_NOT_EXISTS
            )

        return False

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        if not await self._is_unified_account():
            return await self._classic_place_cancel(order_id, tracked_order)
        # clientOid exists before the place-order response does, so a racing cancel never sends a null orderId
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_ENDPOINT,
            data={
                "clientOid": tracked_order.client_order_id
            },
            is_auth_required=True,
        )
        response_code = cancel_result["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(response_code, cancel_result["msg"]))

        return True

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
        if not await self._is_unified_account():
            return await self._classic_place_order(
                order_id, trading_pair, amount, trade_type, order_type, price, position_action
            )
        product_type = await self.product_type_associated_to_trading_pair(trading_pair)
        margin_modes = {
            MarginMode.CROSS: "crossed",
            MarginMode.ISOLATED: "isolated"
        }
        # V3 UTA place-order: productType -> category, size -> qty, force -> timeInForce, and the
        # marginCoin is implicit for the unified account. LIMIT_MAKER maps to a post-only limit order.
        time_in_force = (
            CONSTANTS.POST_ONLY_TIME_IN_FORCE
            if order_type is OrderType.LIMIT_MAKER
            else CONSTANTS.DEFAULT_TIME_IN_FORCE
        )
        data = {
            "category": product_type,
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "qty": str(amount),
            "timeInForce": time_in_force,
            "clientOid": order_id,
            "side": trade_type.name.lower(),
            "marginMode": margin_modes[self._margin_mode],
            "orderType": "limit" if order_type.is_limit_type() else "market",
        }
        if order_type.is_limit_type():
            data["price"] = str(price)

        if position_action is PositionAction.CLOSE and self.position_mode is not PositionMode.HEDGE:
            # A one-way close needs reduceOnly. It is sized against the position as it was when the
            # order was built; if the position shrinks before the order fills, the remainder would
            # otherwise trade through zero and open a position the other way. A hedge-mode close
            # must not send it: posSide already limits the order to that position, and Bitget
            # rejects posSide and reduceOnly together (25238).
            data["reduceOnly"] = "yes"

        if self.position_mode is PositionMode.HEDGE:
            # V3 hedge mode uses posSide (long/short) instead of the V2 tradeSide (open/close).
            # The order side is always the caller's side; posSide names the position the order
            # acts on. Opening, a BUY builds the long and a SELL builds the short. Closing, the
            # caller already sends the offsetting side (a SELL closes a long, a BUY closes a
            # short), so posSide is the opposite of the order side.
            if position_action is PositionAction.CLOSE:
                data["posSide"] = "long" if trade_type is TradeType.SELL else "short"
            else:
                data["posSide"] = "long" if trade_type is TradeType.BUY else "short"

        resp = await self._api_post(
            path_url=CONSTANTS.PLACE_ORDER_ENDPOINT,
            data=data,
            is_auth_required=True,
            headers={
                "X-CHANNEL-API-CODE": CONSTANTS.API_CODE,
            }
        )

        if resp["code"] != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                resp["code"],
                f"Error submitting order {order_id}: {resp['msg']}"
            ))

        return str(resp["data"]["orderId"]), self.current_timestamp

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None
    ) -> TradeFeeBase:
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        if trading_pair in self._trading_fees:
            fee_schema: TradeFeeSchema = self._trading_fees[trading_pair]
            fee_rate = (
                fee_schema.maker_percent_fee_decimal
                if is_maker
                else fee_schema.taker_percent_fee_decimal
            )
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=fee_schema,
                trade_type=order_side,
                percent=fee_rate,
            )
        else:
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
        Loads the account's own maker/taker rates from the private fee-rate endpoint.

        The V3 instruments response does carry makerFeeRate/takerFeeRate for futures, but those
        are the public base rates: being a public endpoint it cannot reflect the account's VIP
        tier or BGB discount. fee-rate is per symbol, but it is only polled every
        TRADING_FEES_INTERVAL and only for the pairs this connector trades.
        """
        if not await self._is_unified_account():
            return await self._classic_update_trading_fees()
        for trading_pair in self._trading_pairs or []:
            try:
                symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
                product_type = await self.product_type_associated_to_trading_pair(trading_pair)
                fee_response = await self._api_get(
                    path_url=CONSTANTS.FEE_RATE_ENDPOINT,
                    params={"category": product_type, "symbol": symbol},
                    is_auth_required=True,
                )
                fee_data = fee_response.get("data") or {}
                maker_fee = fee_data.get("makerFeeRate")
                taker_fee = fee_data.get("takerFeeRate")

                if maker_fee is None or taker_fee is None:
                    continue

                self._trading_fees[trading_pair] = TradeFeeSchema(
                    maker_percent_fee_decimal=Decimal(str(maker_fee)),
                    taker_percent_fee_decimal=Decimal(str(taker_fee)),
                    buy_percent_fee_deducted_from_returns=True,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                # One unavailable pair must not stop the others; _get_fee falls back to
                # DEFAULT_FEES for any pair with no schema.
                self.logger().exception(
                    f"Error fetching the trading fee for {trading_pair}. Falling back to the "
                    f"default fee schema for this pair."
                )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BitgetPerpetualAPIOrderBookDataSource(
            self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BitgetPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.

        Under the V3 UTA account this is a single /api/v3/account/assets call returning one unified
        wallet (data.assets[*] = {coin, available, locked, balance, ...}). The legacy per-product-type
        accounts shape (marginCoin/crossedMaxAvailable/accountEquity + nested assetList) is still
        parsed as a fallback.
        """
        if not await self._is_unified_account():
            return await self._classic_update_balances()
        # The balance command reads account_group_id right after this, so the user id is needed here.
        await self._update_account_uid()
        accounts_info_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_INFO_ENDPOINT,
            is_auth_required=True,
        )

        if accounts_info_response["code"] != CONSTANTS.RET_CODE_OK:
            raise IOError(
                self._formatted_error(
                    accounts_info_response["code"],
                    accounts_info_response["msg"]
                )
            )

        self._account_available_balances.clear()
        self._account_balances.clear()

        data = accounts_info_response["data"]

        if isinstance(data, dict):
            self._set_unified_margin_balances(account=data, coins=data.get("assets", []))
        else:
            for balance_data in data:
                self._accumulate_balance(
                    balance_data["marginCoin"],
                    Decimal(balance_data["crossedMaxAvailable"]),
                    Decimal(balance_data["accountEquity"]),
                )
                for base_asset in balance_data.get("assetList", []):
                    self._accumulate_balance(
                        base_asset["coin"],
                        Decimal(base_asset["available"]),
                        Decimal(base_asset["balance"]),
                    )

    def _set_unified_margin_balances(self, account: Dict[str, Any], coins: List[Dict[str, Any]]) -> None:
        """
        UTA margin is one cross-collateral pool valued in USD (effEquity, net of haircuts), so it is reported
        under the collateral token of the USDT- and USDC-margined pairs traded, USDT when none is configured.
        When that is both, they share one budget (see BitgetPerpetualBudgetChecker). A coin-margined
        pair keeps its coin's own balance; the rest of the wallet is the spot connector's to list.
        """
        pairs = [split_hb_trading_pair(trading_pair) for trading_pair in self._trading_pairs or []]
        margin_tokens = {quote for _, quote in pairs if quote in ("USDT", "USDC")} or {"USDT"}
        per_coin_tokens = {base for base, quote in pairs if quote == "USD"}

        if account.get("effEquity") is not None:
            equity = Decimal(str(account["effEquity"]))
            available = max(equity - Decimal(str(account.get("imr") or 0)), s_decimal_0)
            for token in margin_tokens:
                self._account_balances[token] = equity
                self._account_available_balances[token] = available
            self._pooled_margin_tokens = margin_tokens
        else:
            self._pooled_margin_tokens = set()
            per_coin_tokens |= margin_tokens

        for coin_balance in coins:
            if coin_balance["coin"] in per_coin_tokens:
                available = Decimal(str(coin_balance["available"]))
                self._account_balances[coin_balance["coin"]] = Decimal(str(coin_balance.get("balance", available)))
                self._account_available_balances[coin_balance["coin"]] = available

    def _accumulate_balance(self, coin: str, available: Decimal, total: Decimal) -> None:
        new_total = self._account_balances.get(coin, Decimal(0)) + total
        new_available = self._account_available_balances.get(coin, Decimal(0)) + available
        if new_total or new_available:
            self._account_available_balances[coin] = new_available
            self._account_balances[coin] = new_total

    async def _paginated_rows(
        self,
        path_url: str,
        params: Dict[str, Any],
        limit_id: Optional[str] = None,
        stop_after: Optional[Callable[[List[Dict[str, Any]]], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Reads every page of a cursor-paginated V3 response.

        v3 wraps rows in data.list and returns data.cursor, which is echoed back to fetch the
        next page. Reading only the first page silently truncates fills and funding records, and
        for positions it is worse: _update_positions prunes anything it did not see, so live
        positions on a later page would be deleted from local state.

        Paging stops when a page comes back shorter than the requested limit. A non-empty cursor
        does not by itself mean more rows exist - it is a position marker, and the API returns
        one alongside a complete single page - so terminating on it would either loop or cost an
        extra request every poll. If the endpoint ignores the limit and returns its own page
        size, a short page ends the loop after one request, which is the behaviour this replaces.

        :param path_url: the endpoint to read
        :param params: query parameters, without a cursor
        :param limit_id: the throttler limit id, when it differs from path_url
        :param stop_after: called with each page's rows; returning True ends the read after that page
        :return: the concatenated rows from every page
        """
        rows: List[Dict[str, Any]] = []
        page_size = CONSTANTS.PAGINATION_LIMIT
        cursor: Optional[str] = None

        for _ in range(CONSTANTS.MAX_PAGINATION_PAGES):
            page_params = dict(params)
            page_params["limit"] = str(page_size)
            if cursor:
                page_params["cursor"] = cursor

            response = await self._api_get(
                path_url=path_url,
                params=page_params,
                is_auth_required=True,
                limit_id=limit_id or path_url,
            )

            # A Bitget error can come back with HTTP 200 and no data, which would otherwise read as an
            # empty page: positions the read did not return are pruned, and fills would go missing.
            if response.get("code") != CONSTANTS.RET_CODE_OK:
                raise IOError(self._formatted_error(response.get("code"), f"Error reading {path_url}: {response}"))

            payload = response.get("data")
            if isinstance(payload, dict):
                page_rows = payload.get("list") or []
                cursor = payload.get("cursor") or None
            else:
                # The legacy shape returned the rows directly under data and never paginated.
                page_rows = payload or []
                cursor = None

            rows.extend(page_rows)

            if len(page_rows) < page_size or not cursor or (stop_after is not None and stop_after(page_rows)):
                break
        else:
            self.logger().warning(
                f"Stopped paging {path_url} at {CONSTANTS.MAX_PAGINATION_PAGES} pages; the "
                f"remaining rows were not read."
            )

        return rows

    async def _update_positions(self):
        """
        Retrieves all positions using the REST API.
        """
        if not await self._is_unified_account():
            return await self._classic_update_positions()
        product_types: set[str] = {
            await self.product_type_associated_to_trading_pair(trading_pair)
            for trading_pair in self._trading_pairs
        }
        position_sides = {
            "long": PositionSide.LONG,
            "short": PositionSide.SHORT
        }

        # A position that has been closed simply drops out of the V3 current-position list rather
        # than being returned with a zero size, so track what the poll reported and drop anything
        # stale afterwards. Without this, a position closed while the private stream was down
        # would be reported as open forever and keep blocking position-mode/leverage changes.
        reported_position_keys: set[str] = set()
        # Only positions already tracked when this poll started are candidates for removal. The
        # private stream writes positions concurrently, so one opened after its category was
        # queried would otherwise be missing from the reported set and wrongly pruned below.
        stale_candidate_keys: set[str] = set(self._perpetual_trading.account_positions.keys())
        symbol_map = await self.trading_pair_symbol_map()

        for product_type in product_types:
            # Every page matters here: the reconciliation below removes positions this poll did
            # not report, so a truncated read would delete positions that are still open.
            all_positions_data = await self._paginated_rows(
                path_url=CONSTANTS.ALL_POSITIONS_ENDPOINT,
                params={"category": product_type},
            )

            for position in all_positions_data:
                # V3 current-position (CurrentPositionV3) fields.
                symbol = position["symbol"]
                if symbol not in symbol_map:
                    # Dated futures share these categories but are kept out of the symbol map.
                    continue
                trading_pair = symbol_map[symbol]
                position_side = position_sides[position["posSide"]]
                unrealized_pnl = Decimal(str(position["unrealisedPnl"]))
                entry_price = Decimal(str(position["avgPrice"]))
                amount = Decimal(str(position["total"]))
                leverage = Decimal(str(position["leverage"]))

                pos_key = self._perpetual_trading.position_key(
                    trading_pair,
                    position_side
                )

                if amount != s_decimal_0:
                    position_amount = (
                        amount * (
                            Decimal("-1.0")
                            if position_side == PositionSide.SHORT
                            else Decimal("1.0")
                        )
                    )
                    position = Position(
                        trading_pair=trading_pair,
                        position_side=position_side,
                        unrealized_pnl=unrealized_pnl,
                        entry_price=entry_price,
                        amount=position_amount,
                        leverage=leverage,
                    )
                    self._perpetual_trading.set_position(pos_key, position)
                    reported_position_keys.add(pos_key)
                else:
                    self._perpetual_trading.remove_position(pos_key)

        # Only prune positions whose product type this poll actually covered, so positions on a
        # category that was not queried are left untouched.
        for pos_key in stale_candidate_keys - reported_position_keys:
            tracked_position = self._perpetual_trading.account_positions.get(pos_key)
            if tracked_position is None:
                continue
            tracked_product_type = await self.product_type_associated_to_trading_pair(
                tracked_position.trading_pair
            )
            if tracked_product_type in product_types:
                self._perpetual_trading.remove_position(pos_key)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        if not await self._is_unified_account():
            return await self._classic_all_trade_updates_for_order(order)
        trade_updates = []

        if order.exchange_order_id is not None:
            try:
                # Reading only the first page would drop the earlier fills of a heavily
                # partially-filled order.
                all_fills_data = await self._paginated_rows(
                    path_url=CONSTANTS.ORDER_FILLS_ENDPOINT,
                    params={"orderId": order.exchange_order_id},
                )

                for fill_data in all_fills_data:
                    trade_update = self._parse_trade_update(
                        trade_msg=fill_data,
                        tracked_order=order
                    )
                    trade_updates.append(trade_update)
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(
                    request_exception=ex
                ):
                    raise

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        if not await self._is_unified_account():
            return await self._classic_request_order_status(tracked_order)
        try:
            order_status_data = await self._request_order_status_data(tracked_order=tracked_order)
            updated_order_data = order_status_data["data"]

            if len(updated_order_data) == 0:
                raise ValueError(f"Can't parse order status data. Data: {updated_order_data}")

            # V3 order-info returns a single object; state -> orderStatus.
            if isinstance(updated_order_data, list):
                updated_order_data = updated_order_data[0]
            client_order_id = str(updated_order_data["clientOid"])

            reported_status = updated_order_data.get("orderStatus", updated_order_data.get("state"))
            new_state = self._order_state_for(reported_status)
            if new_state is None:
                # An unmapped status means the order exists but its state could not be read - it
                # is emphatically not a missing order. Raising here would be classified as
                # "order not found": the active-order handler counts every status-update
                # exception towards the lost-order limit, and
                # _is_order_not_found_during_status_update_error treats ValueError as proof of
                # absence (that is how the genuinely empty response is reported). Hold the state
                # we already have instead; _order_state_for has logged the unknown status and the
                # next poll re-reads it. A same-state update fires no events.
                new_state = tracked_order.current_state

            order_update: OrderUpdate = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=new_state,
                client_order_id=client_order_id,
                exchange_order_id=updated_order_data["orderId"],
            )

            return order_update

        except IOError as ex:
            if self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                order_update = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=tracked_order.current_state,
                )
            else:
                raise

        return order_update

    async def _request_order_status_data(self, tracked_order: InFlightOrder) -> Dict:
        # V3 UTA order-info identifies the order by orderId/clientOid across the unified account.
        query_params = {}
        if tracked_order.exchange_order_id:
            query_params["orderId"] = tracked_order.exchange_order_id
        else:
            query_params["clientOid"] = tracked_order.client_order_id

        order_detail_response = await self._api_get(
            path_url=CONSTANTS.ORDER_DETAIL_ENDPOINT,
            params=query_params,
            is_auth_required=True,
        )

        return order_detail_response

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        product_type = await self.product_type_associated_to_trading_pair(trading_pair)
        ticker_response = await self._api_get(
            path_url=CONSTANTS.PUBLIC_TICKER_ENDPOINT,
            params={
                "symbol": symbol,
                "category": product_type
            },
        )

        ticker = ticker_response["data"][0]
        # V3 renames the last price field lastPr -> lastPrice.
        return float(ticker.get("lastPrice", ticker.get("lastPr")))

    async def set_margin_mode(
        self,
        mode: MarginMode
    ) -> None:
        """
        Record the desired margin mode (cross/isolated).

        Under the V3 UTA account there is no per-symbol cross/isolated margin-mode endpoint: the
        margin mode is applied per order via the ``marginMode`` field on place-order (see
        ``_place_order``). The V3 ``/api/v3/account/adjust-account-mode`` endpoint sets the
        account-wide margin model (single- vs multi-currency / portfolio margin), which is a
        different concept and must not be driven from the cross/isolated selection.

        We therefore only store the requested mode locally so it is sent with every order. This also
        keeps ``start_network`` from raising on an unsupported account-level request, which would
        otherwise abort startup and have the network loop repeatedly cancel the order book / user
        stream websocket tasks before they can subscribe (leaving the connector stuck "not ready").
        A Classic account does have the V2 per-symbol endpoint, so there the mode is also set on the exchange.
        """
        self._margin_mode = mode
        try:
            unified_account = await self._is_unified_account()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Raising here would abort start_network the same way; the mode still goes out with every order.
            self.logger().warning(
                "Could not read the account mode, so the margin mode is only applied per order.", exc_info=True
            )
            return
        if not unified_account:
            return await self._classic_set_margin_mode(mode)
        self.logger().info(f"Margin mode set to {CONSTANTS.MARGIN_MODE_TYPES[mode]} (applied per order).")

    async def _execute_set_position_mode(self, mode: PositionMode):
        """Bitget derives productType from trading_pair, so we must loop over all trading pairs."""
        async with self._set_position_mode_lock:
            try:
                exchange_mode = await self._fetch_account_position_mode()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().warning(f"Could not fetch position mode from exchange: {e}")
                exchange_mode = None

            self.logger().info(
                f"Setting position mode: requested={mode}, current_exchange={exchange_mode}")

            if exchange_mode == mode:
                self._perpetual_trading.set_position_mode(mode)
                self._fire_position_mode_events(mode, success=True)
                self.logger().info(f"Position mode already set to {mode} on exchange.")
                return

            all_success = True
            msg = ""
            for trading_pair in self.trading_pairs:
                success, msg = await self._trading_pair_position_mode_set(mode, trading_pair)
                if not success:
                    all_success = False
                    self.logger().network(f"Error switching {trading_pair} mode to {mode}: {msg}")
                    break

            if all_success:
                self._perpetual_trading.set_position_mode(mode)
                self.logger().info(f"Position mode switched to {mode}.")
            else:
                self.logger().error(f"Failed to set position mode to {mode}: {msg}")
            self._fire_position_mode_events(mode, success=all_success, message=msg)

    async def _trading_pair_position_mode_set(
        self,
        mode: PositionMode,
        trading_pair: str
    ) -> Tuple[bool, str]:
        if not await self._is_unified_account():
            return await self._classic_trading_pair_position_mode_set(mode, trading_pair)
        if len(self.account_positions) > 0:
            return False, "Cannot change position because active positions exist"

        try:
            position_mode = CONSTANTS.POSITION_MODE_TYPES[mode]
            product_type = await self.product_type_associated_to_trading_pair(trading_pair)

            # V3 set-hold-mode: productType -> category, posMode -> holdMode.
            response = await self._api_post(
                path_url=CONSTANTS.SET_POSITION_MODE_ENDPOINT,
                data={
                    "category": product_type,
                    "holdMode": position_mode,
                },
                is_auth_required=True,
            )

            if response["code"] != CONSTANTS.RET_CODE_OK:
                return (
                    False,
                    self._formatted_error(response["code"], response["msg"])
                )
        except Exception as exception:
            return (
                False,
                f"There was an error changing the position mode ({exception})"
            )

        return True, ""

    async def _set_trading_pair_leverage(
        self,
        trading_pair: str,
        leverage: int
    ) -> Tuple[bool, str]:
        if not await self._is_unified_account():
            return await self._classic_set_trading_pair_leverage(trading_pair, leverage)
        if len(self.account_positions) > 0:
            return False, "cannot change leverage because active positions exist"

        try:
            product_type = await self.product_type_associated_to_trading_pair(trading_pair)
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

            # V3 set-leverage params: category, symbol, leverage, coin (the position/margin currency).
            response: Dict[str, Any] = await self._api_post(
                path_url=CONSTANTS.SET_LEVERAGE_ENDPOINT,
                data={
                    "symbol": symbol,
                    "category": product_type,
                    "coin": self.get_buy_collateral_token(trading_pair),
                    "leverage": str(leverage)
                },
                is_auth_required=True,
            )

            if response["code"] != CONSTANTS.RET_CODE_OK:
                return False, self._formatted_error(response["code"], response["msg"])
        except Exception as exception:
            return (
                False,
                f"There was an error setting the leverage for {trading_pair} ({exception})"
            )

        return True, ""

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        if not await self._is_unified_account():
            return await self._classic_fetch_last_fee_payment(trading_pair)
        timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")

        product_type = await self.product_type_associated_to_trading_pair(trading_pair)
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        # V3 financial-records: productType -> category, paginated under data.list (ts replaces the
        # legacy cTime). Funding-settlement rows use uppercase V3 "type" values split by direction
        # (CONTRACT_MAIN_SETTLE_FEE_USER_IN/OUT for cross, MARGIN_SETTLE_FEE_USER_IN/OUT for
        # isolated). The endpoint rejects the legacy lowercase single "type" filter with "40020
        # Parameter type error", so we fetch the records unfiltered and pick the latest funding
        # settlement for this symbol locally.

        def is_settlement(record: Dict[str, Any]) -> bool:
            return record.get("symbol") == symbol and "SETTLE_FEE" in str(record.get("type", ""))

        # The records are unfiltered, so the settlement can sit beyond the first page, but this runs
        # for every pair at every funding poll. The rows come newest first, so the read stops at the
        # first settlement, which is the latest, or once rows predate the lookback: an older settlement
        # is not a payment the poll still has to report.
        cutoff_ms = (self._time() - CONSTANTS.FUNDING_PAYMENT_LOOKBACK_SECONDS) * 1e3

        def read_enough(page: List[Dict[str, Any]]) -> bool:
            return any(is_settlement(record) for record in page) or int(page[-1].get("ts") or 0) < cutoff_ms

        payment_data = await self._paginated_rows(
            path_url=CONSTANTS.ACCOUNT_BILLS_ENDPOINT,
            params={"category": product_type},
            stop_after=read_enough,
        )
        funding_payments = [record for record in payment_data if is_settlement(record)]

        if funding_payments:
            last_data = funding_payments[0]
            funding_info = self._perpetual_trading._funding_info.get(trading_pair)
            payment: Decimal = Decimal(str(last_data["amount"]))
            funding_rate: Decimal = funding_info.rate if funding_info is not None else Decimal(0)
            timestamp: float = int(last_data["ts"]) * 1e-3

        return timestamp, funding_rate, payment

    async def _wait_for_account_mode(self) -> bool:
        """
        The user stream listener starts with the network and is never restarted, so it waits out a failed account
        mode read instead of raising: a dead listener would leave every later push unread in the queue.
        """
        while True:
            try:
                return await self._is_unified_account()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().warning(
                    "Could not read the account mode; retrying before reading the user stream.", exc_info=True
                )
                await self._sleep(CONSTANTS.ACCOUNT_MODE_RETRY_INTERVAL_SECONDS)

    async def _user_stream_event_listener(self):
        if not await self._wait_for_account_mode():
            return await self._classic_user_stream_event_listener()
        async for event_message in self._iter_user_event_queue():
            try:
                # V3 UTA push envelope uses arg.topic (the V2 API used arg.channel). Fills now arrive
                # on the dedicated "fill" channel; the "order" channel carries order state only.
                arg = event_message["arg"]
                channel = arg.get("topic")
                data = event_message["data"]

                if channel == CONSTANTS.WS_POSITIONS_ENDPOINT:
                    # The envelope's action distinguishes a full snapshot from a delta.
                    await self._process_account_position_event(
                        data, is_snapshot=event_message.get("action") == "snapshot"
                    )
                elif channel == CONSTANTS.WS_ORDERS_ENDPOINT:
                    for order_msg in data:
                        self._process_order_event_message(order_msg)
                        self._process_balance_update_from_order_event(order_msg)
                elif channel == CONSTANTS.WS_FILL_ENDPOINT:
                    for fill_msg in data:
                        self._process_trade_event_message(fill_msg)
                elif channel == CONSTANTS.WS_ACCOUNT_ENDPOINT:
                    # The V3 account channel nests per-coin balances in each entry's "coin" array.
                    for account_msg in data:
                        self._set_unified_margin_balances(account=account_msg, coins=account_msg.get("coin", []))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")

    async def _process_account_position_event(
        self, position_entries: List[Dict[str, Any]], is_snapshot: bool = True
    ):
        """
        Updates position

        :param position_entries: The position event message payload
        :param is_snapshot: True when the message lists every open position, so that positions
            missing from it can be treated as closed. An "update" carries only what changed, and
            pruning on one of those would delete unrelated positions that are still open.
        """
        all_position_keys = []
        position_sides = {
            "long": PositionSide.LONG,
            "short": PositionSide.SHORT
        }
        symbol_map = await self.trading_pair_symbol_map()

        for position in position_entries:
            # V3 UTA position channel (BitgetUaPositionUpdate): symbol (not instId), posSide, size
            # (not total), avgPrice, unrealisedPnl.
            symbol = position["symbol"]
            if symbol not in symbol_map:
                # Dated futures share the account but are kept out of the symbol map.
                continue
            trading_pair = symbol_map[symbol]
            position_side = position_sides[position["posSide"]]
            entry_price = Decimal(str(position["avgPrice"]))
            amount = Decimal(str(position["size"]))
            leverage = Decimal(str(position["leverage"]))
            unrealized_pnl = Decimal(str(position["unrealisedPnl"]))

            pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
            all_position_keys.append(pos_key)

            if amount != s_decimal_0:
                position_amount = (
                    amount * (
                        Decimal("-1.0")
                        if position_side == PositionSide.SHORT
                        else Decimal("1.0")
                    )
                )
                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=position_amount,
                    leverage=leverage,
                )
                self._perpetual_trading.set_position(pos_key, position)
            else:
                self._perpetual_trading.remove_position(pos_key)

        if not is_snapshot:
            # A delta only carries the positions that changed; anything absent is untouched, not
            # closed. Closures still arrive as an entry with size 0, handled above.
            return

        # On a snapshot, a position that is simply absent has been closed.
        position_keys = list(self.account_positions.keys())
        positions_to_remove = (
            position_key
            for position_key in position_keys
            if position_key not in all_position_keys
        )
        for position_key in positions_to_remove:
            self._perpetual_trading.remove_position(position_key)

    def _order_state_for(self, status: Optional[str]) -> Optional[OrderState]:
        """
        Maps an order status (V3, or V2 on a Classic account) onto an OrderState, or returns None
        when the exchange reports a status this connector does not know about.

        Callers decide whether to skip the update or raise. What must not happen is the bare
        KeyError a direct lookup raises: on the user-stream path that is swallowed by the
        listener's catch-all handler, so the order update disappears with nothing in the log
        pointing at the status that caused it.

        :param status: the orderStatus reported by the exchange
        :return: the mapped OrderState, or None if the status is unknown
        """
        state = CONSTANTS.STATE_TYPES.get(status)
        if state is None:
            self.logger().warning(
                f"Received an unrecognised order status from the exchange: {status!r}. The order "
                f"update was ignored. This usually means a status was added to the API that the "
                f"connector does not map yet."
            )
        return state

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.

        :param order_msg: The order event message payload
        """
        order_status = self._order_state_for(order_msg.get("orderStatus"))
        if order_status is None:
            return
        client_order_id = str(order_msg["clientOid"])
        updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if updatable_order is not None:
            new_order_update: OrderUpdate = OrderUpdate(
                trading_pair=updatable_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=order_status,
                client_order_id=client_order_id,
                exchange_order_id=order_msg["orderId"],
            )
            self._order_tracker.process_order_update(new_order_update)

    def _process_balance_update_from_order_event(self, order_msg: Dict[str, Any]):
        # V3 order channel (BitgetUaOrder): orderStatus, marginCoin, qty (was size), price, leverage.
        # This only adjusts the locally-cached available balance for opening limit orders; the REST
        # balance poll is the source of truth, so we bail out (rather than raise) when the event is
        # not applicable or the numeric fields are missing/empty (e.g. market orders carry no price).
        order_status = self._order_state_for(order_msg.get("orderStatus"))
        symbol = order_msg.get("marginCoin")
        states_to_consider = [OrderState.OPEN, OrderState.CANCELED]
        is_opening = order_msg.get("tradeSide") in [
            "open",
            "buy_single",
            "sell_single",
        ]

        if not (
            symbol in self._account_available_balances
            and order_status in states_to_consider
            and is_opening
        ):
            return

        try:
            order_amount = Decimal(str(order_msg["qty"]))
            order_price = Decimal(str(order_msg["price"]))
            leverage = Decimal(str(order_msg["leverage"]))
        except (KeyError, TypeError, ArithmeticError):
            return
        if leverage == Decimal(0):
            return

        margin_amount = (order_amount * order_price) / leverage
        multiplier = Decimal(-1) if order_status == OrderState.OPEN else Decimal(1)
        self._account_available_balances[symbol] += margin_amount * multiplier

    def _process_trade_event_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received.
        Triggers order completed event if the total executed amount equals to the specified order amount.

        :param trade_msg: The trade event message payload
        """

        client_order_id = str(trade_msg["clientOid"])
        fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)

        # The V3 UTA "fill" channel shares the BitgetUaUserTrade shape with the REST fills endpoint,
        # so the same parser is used for both.
        if fillable_order and "execId" in trade_msg:
            trade_update = self._parse_trade_update(
                trade_msg=trade_msg,
                tracked_order=fillable_order
            )
            if trade_update:
                self._order_tracker.process_trade_update(trade_update)

    def _parse_trade_update(self, trade_msg: Dict, tracked_order: InFlightOrder) -> TradeUpdate:
        # Shared by REST fills and the V3 UTA "fill" channel (both BitgetUaUserTrade).
        # V3 fills (FillV3) rename fields: tradeId->execId, price->execPrice, baseVolume->execQty,
        # cTime->createdTime, and feeDetail[].{totalFee/totalDeductionFee}->feeDetail[].fee. Legacy
        # names are kept as fallbacks so V2-shaped payloads keep parsing.
        # The fee is taken as a positive magnitude (the perpetual fee type already conveys the
        # deduction); Bitget V3 reports feeDetail.fee as positive, and abs() normalises the legacy
        # negative convention as well.
        fee_detail = trade_msg["feeDetail"][0]
        fee_asset = fee_detail["feeCoin"]
        if "fee" in fee_detail:
            fee_amount = abs(Decimal(str(fee_detail["fee"])))
        else:
            fee_amount = abs(Decimal((
                fee_detail["totalDeductionFee"]
                if fee_detail.get("deduction") == "yes"
                else fee_detail["totalFee"]
            )))
        position_actions = {
            "open": PositionAction.OPEN,
            "close": PositionAction.CLOSE,
        }
        position_action = position_actions.get(trade_msg.get("tradeSide"), PositionAction.NIL)
        flat_fees = (
            [] if fee_amount == Decimal("0")
            else [TokenAmount(amount=fee_amount, token=fee_asset)]
        )

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=flat_fees,
        )

        exec_price = Decimal(str(trade_msg.get("execPrice", trade_msg.get("price"))))
        exec_qty = Decimal(str(trade_msg.get("execQty", trade_msg.get("baseVolume"))))
        # REST fills carry "createdTime"; the V3 "fill" websocket channel carries "execTime"
        # (execution time) / "updatedTime" instead. Fall back across them, then to the local clock.
        exec_time_raw = (
            trade_msg.get("createdTime")
            or trade_msg.get("execTime")
            or trade_msg.get("updatedTime")
            or trade_msg.get("cTime")
        )
        exec_time = int(exec_time_raw) * 1e-3 if exec_time_raw is not None else self.current_timestamp

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=str(trade_msg.get("execId", trade_msg.get("tradeId"))),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=trade_msg["orderId"],
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=exec_time,
            fill_price=exec_price,
            fill_base_amount=exec_qty,
            fill_quote_amount=exec_price * exec_qty,
            fee=fee,
        )

        return trade_update

    async def _make_trading_pairs_request(self) -> Any:
        all_exchange_info: List[Dict[str, Any]] = []

        for product_type in CONSTANTS.ALL_PRODUCT_TYPES:
            exchange_info = await self._api_get(
                path_url=self.trading_pairs_request_path,
                params={
                    "category": product_type
                }
            )
            all_exchange_info.extend(exchange_info["data"])

        return all_exchange_info

    async def _make_trading_rules_request(self) -> Any:
        return await self._make_trading_pairs_request()

    def _initialize_trading_pair_symbols_from_exchange_info(
        self,
        exchange_info: List[Dict[str, Any]]
    ) -> None:
        mapping = bidict()
        for symbol_data in exchange_info:
            if bitget_perpetual_utils.is_exchange_information_valid(exchange_info=symbol_data):
                try:
                    symbol = symbol_data["symbol"]
                    base = symbol_data["baseCoin"]
                    quote = symbol_data["quoteCoin"]
                    trading_pair = combine_to_hb_trading_pair(base, quote)
                    mapping[symbol] = trading_pair
                except Exception as exception:
                    self.logger().error(
                        f"There was an error parsing a trading pair information ({exception}). Symbol: {symbol}. Trading pair: {trading_pair}"
                    )
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(
        self,
        exchange_info_dict: Dict[str, List[Dict[str, Any]]]
    ) -> List[TradingRule]:
        """
        Converts JSON API response into a local dictionary of trading rules.

        :param instrument_info_dict: The JSON API response.

        :returns: A dictionary of trading pair to its respective TradingRule.
        """
        trading_rules = []
        for rule in exchange_info_dict:
            if bitget_perpetual_utils.is_instrument_tradable(exchange_info=rule):
                try:
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                        symbol=rule["symbol"]
                    )
                    # V3 instruments field names (with V2 fallbacks): minTradeUSDT -> minOrderAmount,
                    # minTradeNum -> minOrderQty, pricePlace -> pricePrecision, sizeMultiplier ->
                    # quantityMultiplier. supportMarginCoins is gone; the collateral coin is the
                    # quote coin for USDT/USDC futures and the base coin for coin-margined futures.
                    max_order_qty = rule.get("maxOrderQty")
                    max_order_size = Decimal(str(max_order_qty)) if max_order_qty else None
                    min_order_value = rule.get("minOrderAmount", rule.get("minTradeUSDT"))
                    min_order_size = rule.get("minOrderQty", rule.get("minTradeNum"))

                    # The multipliers are the steps the exchange enforces, and can be coarser than the
                    # precision: SHIBUSDT has quantityPrecision 0 but only takes multiples of 10000.
                    price_multiplier = Decimal(str(rule.get("priceMultiplier") or 0))
                    quantity_multiplier = Decimal(str(rule.get("quantityMultiplier") or 0))

                    if price_multiplier > 0:
                        min_price_increment = price_multiplier
                    elif "pricePrecision" in rule:
                        min_price_increment = Decimal(f"1e-{int(rule['pricePrecision'])}")
                    else:
                        min_price_increment = Decimal(f"1e-{int(rule['pricePlace'])}")

                    if quantity_multiplier > 0:
                        min_base_amount_increment = quantity_multiplier
                    elif "quantityPrecision" in rule:
                        min_base_amount_increment = Decimal(f"1e-{int(rule['quantityPrecision'])}")
                    else:
                        min_base_amount_increment = Decimal(str(rule["sizeMultiplier"]))

                    if "supportMarginCoins" in rule:
                        margin_coin = rule["supportMarginCoins"][0]
                    else:
                        base, quote = split_hb_trading_pair(trading_pair)
                        margin_coin = base if rule.get("category") == CONSTANTS.USD_PRODUCT_TYPE else quote

                    trading_rules.append(
                        TradingRule(
                            trading_pair=trading_pair,
                            min_order_value=Decimal(str(min_order_value)),
                            max_order_size=max_order_size,
                            min_order_size=Decimal(str(min_order_size)),
                            min_price_increment=min_price_increment,
                            min_base_amount_increment=min_base_amount_increment,
                            buy_order_collateral_token=margin_coin,
                            sell_order_collateral_token=margin_coin,
                        )
                    )
                except Exception:
                    self.logger().exception(
                        f"Error parsing the trading pair rule: {rule}. Skipping."
                    )

        return trading_rules
