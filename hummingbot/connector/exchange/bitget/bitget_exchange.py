import asyncio
from decimal import ROUND_UP, Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from bidict import bidict

import hummingbot.connector.exchange.bitget.bitget_constants as CONSTANTS
from hummingbot.connector.exchange.bitget import bitget_account, bitget_utils, bitget_web_utils as web_utils
from hummingbot.connector.exchange.bitget.bitget_api_order_book_data_source import BitgetAPIOrderBookDataSource
from hummingbot.connector.exchange.bitget.bitget_api_user_stream_data_source import BitgetAPIUserStreamDataSource
from hummingbot.connector.exchange.bitget.bitget_auth import BitgetAuth
from hummingbot.connector.exchange.bitget.bitget_classic import BitgetClassicAccountMixin
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

s_decimal_NaN = Decimal("nan")


class BitgetExchange(BitgetClassicAccountMixin, ExchangePyBase):
    """
    Bitget spot, for both kinds of account. A Unified Trading Account (UTA) trades through the V3 API and a
    Classic account through V2; the connector reads which one the API key belongs to before its first private
    call and routes the private calls accordingly (Classic ones live in BitgetClassicAccountMixin). Market data
    comes from the V3 public API for both.
    """

    web_utils = web_utils

    def __init__(
        self,
        bitget_api_key: str = None,
        bitget_secret_key: str = None,
        bitget_passphrase: str = None,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ) -> None:
        self._api_key = bitget_api_key
        self._secret_key = bitget_secret_key
        self._passphrase = bitget_passphrase
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        # Quote amount of each Classic market buy, which the V2 API sizes in quote currency.
        self._expected_market_amounts: Dict[str, Decimal] = {}
        self._unified_account: Optional[bool] = None
        self._account_mode_lock = asyncio.Lock()

        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def account_group_id(self) -> Optional[str]:
        """
        Bitget's UTA is a single cross-margined wallet, and this connector is one of two views
        onto it - bitget_perpetual reads the same account. Both report the wallet in full,
        so without this they are summed twice. See bitget_account for how the id is keyed.
        A Classic account keeps separate spot and futures wallets, so it has no group.
        """
        if not self._unified_account:
            return None
        return bitget_account.account_group_id(self._api_key)

    async def _is_unified_account(self) -> bool:
        """
        Whether the API key's account is a Unified Trading Account. Read once, before the first private call: the
        V3 account endpoints answer a Classic account with 40084, and any other failure is raised for a retry.
        """
        if self._unified_account is None:
            async with self._account_mode_lock:
                if self._unified_account is None:
                    try:
                        response = await self._api_get(path_url=CONSTANTS.ASSETS_ENDPOINT, is_auth_required=True)
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
        if not bitget_account.needs_user_id(self._api_key):
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
            bitget_account.remember_user_id(self._api_key, str(user_id))
        else:
            bitget_account.user_id_read_failed(self._api_key)

    @property
    def authenticator(self) -> BitgetAuth:
        return BitgetAuth(
            api_key=self._api_key,
            secret_key=self._secret_key,
            passphrase=self._passphrase,
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
        return CONSTANTS.PUBLIC_SYMBOLS_ENDPOINT

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.PUBLIC_SYMBOLS_ENDPOINT

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

    @staticmethod
    def _formatted_error(code: int, message: str) -> str:
        return f"Error: {code} - {message}"

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(
        self,
        request_exception: Exception
    ) -> bool:
        error_description = str(request_exception)
        ts_error_target_str = "Request timestamp expired"

        return ts_error_target_str in error_description

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
        # Error example:
        # { "code": "43001", "msg": "订单不存在", "requestTime": 1710327684832, "data": null }

        if isinstance(cancelation_exception, IOError):
            return any(
                value in str(cancelation_exception)
                for value in CONSTANTS.RET_CODES_ORDER_NOT_EXISTS
            )

        return False

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        if not await self._is_unified_account():
            return await self._classic_place_cancel(order_id, tracked_order)
        # V3 UTA cancel-order identifies the order by clientOid/orderId across the unified account;
        # category/symbol are not required (CancelOrderRequestV3 = {orderId?, clientOid?}).
        cancel_order_response = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_ENDPOINT,
            data={
                "clientOid": tracked_order.client_order_id
            },
            is_auth_required=True,
        )
        response_code = cancel_order_response["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                response_code,
                f"Can't cancel order {order_id}: {cancel_order_response}"
            ))

        return True

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
        if not await self._is_unified_account():
            return await self._classic_place_order(order_id, trading_pair, amount, trade_type, order_type, price)
        if order_type is OrderType.MARKET and trade_type is TradeType.BUY:
            current_price: Decimal = self.get_price(trading_pair, True)
            step_size = Decimal(self.trading_rules[trading_pair].min_base_amount_increment)
            amount = (amount * current_price).quantize(step_size, rounding=ROUND_UP)
        # LIMIT_MAKER maps to a post-only limit order (orderType "limit" + timeInForce "post_only").
        time_in_force = (
            CONSTANTS.POST_ONLY_TIME_IN_FORCE
            if order_type is OrderType.LIMIT_MAKER
            else CONSTANTS.DEFAULT_TIME_IN_FORCE
        )
        data = {
            "category": CONSTANTS.CATEGORY,
            "side": CONSTANTS.TRADE_TYPES[trade_type],
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "qty": str(amount),
            "orderType": CONSTANTS.ORDER_TYPES[order_type],
            "timeInForce": time_in_force,
            "clientOid": order_id,
        }
        if order_type.is_limit_type():
            data["price"] = str(price)

        create_order_response = await self._api_post(
            path_url=CONSTANTS.PLACE_ORDER_ENDPOINT,
            data=data,
            is_auth_required=True,
            headers={
                "X-CHANNEL-API-CODE": CONSTANTS.API_CODE,
            }
        )
        response_code = create_order_response["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                response_code,
                f"Error submitting order {order_id}: {create_order_response}"
            ))

        return str(create_order_response["data"]["orderId"]), self.current_timestamp

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
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

    async def _update_trading_fees(self) -> None:
        """
        Loads the account's own maker/taker rates from the private fee-rate endpoint.

        The V3 SPOT instruments response carries no fee fields at all, so reading them from there
        left _trading_fees empty and every order was costed at the hardcoded DEFAULT_FEES rather
        than the account's VIP tier or BGB discount. fee-rate is per symbol, but it is only polled
        every TRADING_FEES_INTERVAL and only for the pairs this connector trades.
        """
        if not await self._is_unified_account():
            return await self._classic_update_trading_fees()
        for trading_pair in self._trading_pairs or []:
            try:
                symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
                fee_response = await self._api_get(
                    path_url=CONSTANTS.FEE_RATE_ENDPOINT,
                    params={"category": CONSTANTS.CATEGORY, "symbol": symbol},
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

    async def _make_trading_rules_request(self) -> Any:
        # V3 market/instruments requires the category query parameter (SPOT for this connector).
        return await self._api_get(
            path_url=self.trading_rules_request_path,
            params={"category": CONSTANTS.CATEGORY},
        )

    async def _make_trading_pairs_request(self) -> Any:
        return await self._api_get(
            path_url=self.trading_pairs_request_path,
            params={"category": CONSTANTS.CATEGORY},
        )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BitgetAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BitgetAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    async def _update_balances(self) -> None:
        if not await self._is_unified_account():
            return await self._classic_update_balances()
        # The balance command reads account_group_id right after this, so the user id is needed here.
        await self._update_account_uid()
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        wallet_balance_response: Dict[str, Union[str, List[Dict[str, Any]]]] = await self._api_get(
            path_url=CONSTANTS.ASSETS_ENDPOINT,
            is_auth_required=True,
        )
        response_code = wallet_balance_response["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                response_code,
                f"Error while balance update: {wallet_balance_response}"
            ))

        # The V3 assets response wraps the per-coin list in data["assets"] (AccountAssetsV3).
        for balance_data in wallet_balance_response["data"]["assets"]:
            self._set_account_balances(balance_data)
            remote_asset_names.add(balance_data["coin"])

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        if not await self._is_unified_account():
            return await self._classic_all_trade_updates_for_order(order)
        trade_updates = []

        if order.exchange_order_id is not None:
            try:
                # Reading only the first page would drop the earlier fills of a heavily
                # partially-filled order.
                fills_data = await self._paginated_rows(
                    path_url=CONSTANTS.USER_FILLS_ENDPOINT,
                    params={"orderId": order.exchange_order_id},
                )

                for fill_data in fills_data:
                    trade_update = self._parse_trade_update(
                        trade_msg=fill_data,
                        tracked_order=order,
                        source_type="rest"
                    )
                    trade_updates.append(trade_update)
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(
                    request_exception=ex
                ):
                    raise
        if len(trade_updates) > 0:
            self.logger().info(
                f"{len(trade_updates)} trades updated for order {order.client_order_id}"
            )

        return trade_updates

    async def _paginated_rows(self, path_url: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Reads every page of a cursor-paginated V3 response (rows in data.list, next page via data.cursor)."""
        rows: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        for _ in range(CONSTANTS.MAX_PAGINATION_PAGES):
            page_params = dict(params, limit=str(CONSTANTS.PAGINATION_LIMIT))
            if cursor:
                page_params["cursor"] = cursor

            response = await self._api_get(path_url=path_url, params=page_params, is_auth_required=True)

            # A Bitget error can come back with HTTP 200 and no data, which would otherwise read as an
            # empty page and silently drop the order's fills.
            if response.get("code") != CONSTANTS.RET_CODE_OK:
                raise IOError(self._formatted_error(response.get("code"), f"Error reading {path_url}: {response}"))

            payload = response.get("data")
            if isinstance(payload, dict):
                page_rows = payload.get("list") or []
                cursor = payload.get("cursor") or None
            else:
                page_rows = payload or []
                cursor = None
            rows.extend(page_rows)

            # The cursor also comes back alongside the last page, so only a full page means more rows.
            if len(page_rows) < CONSTANTS.PAGINATION_LIMIT or not cursor:
                break
        else:
            self.logger().warning(
                f"Stopped paging {path_url} at {CONSTANTS.MAX_PAGINATION_PAGES} pages; the "
                f"remaining rows were not read."
            )

        return rows

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        if not await self._is_unified_account():
            return await self._classic_request_order_status(tracked_order)
        order_info_response = await self._request_order_update(tracked_order=tracked_order)

        order_update = self._create_order_update(
            order=tracked_order,
            order_update_response=order_info_response
        )

        return order_update

    def _create_order_update(
        self, order: InFlightOrder, order_update_response: Dict[str, Any]
    ) -> OrderUpdate:
        updated_order_data = order_update_response["data"]

        if not updated_order_data:
            raise ValueError(f"Can't parse order status data. Data: {updated_order_data}")

        # V3 order-info returns data as a single OrderInfoV3 object; the legacy endpoint returned a
        # one-element list. Support both. Field renames: status->orderStatus, size->qty.
        updated_info = updated_order_data[0] if isinstance(updated_order_data, list) else updated_order_data

        reported_status = updated_info.get("orderStatus", updated_info.get("status"))
        new_state = self._order_state_for(reported_status)
        if new_state is None:
            # An unmapped status means the order exists but its state could not be read - it is
            # emphatically not a missing order. Raising here would be classified as
            # "order not found": the active-order handler counts every status-update exception
            # towards the lost-order limit, and _is_order_not_found_during_status_update_error
            # treats ValueError as proof of absence (that is how the genuinely empty response is
            # reported). Hold the state we already have instead; _order_state_for has logged the
            # unknown status, and the next poll re-reads it. A same-state update fires no events.
            new_state = order.current_state
        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=new_state,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
        )

        return order_update

    async def _request_order_update(self, tracked_order: InFlightOrder) -> Dict[str, Any]:
        order_info_response = await self._api_get(
            path_url=CONSTANTS.ORDER_INFO_ENDPOINT,
            params={
                "clientOid": tracked_order.client_order_id
            },
            is_auth_required=True,
        )

        return order_info_response

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        resp_json = await self._api_get(
            path_url=CONSTANTS.PUBLIC_TICKERS_ENDPOINT,
            params={
                "category": CONSTANTS.CATEGORY,
                "symbol": await self.exchange_symbol_associated_to_pair(trading_pair)
            },
        )

        ticker = resp_json["data"][0]
        # V3 renames the last price field lastPr -> lastPrice.
        return float(ticker.get("lastPrice", ticker.get("lastPr")))

    def _parse_trade_update(
        self,
        trade_msg: Dict,
        tracked_order: InFlightOrder,
        source_type: Literal["websocket", "rest"]
    ) -> Optional[TradeUpdate]:
        self.logger().debug(f"Data for {source_type} trade update: {trade_msg}")

        # V3 UTA renames fill fields: tradeId->execId, priceAvg->execPrice, size->execQty,
        # amount->execValue, feeDetail[].totalFee->feeDetail[].fee, uTime->updatedTime. The legacy
        # names are kept as fallbacks so this parser works for both REST fills and websocket pushes.
        # The fee is taken as a positive magnitude (hummingbot represents the deduction via the fee
        # type); Bitget V3 already reports feeDetail.fee as a positive value, abs() normalises the
        # legacy negative convention too.
        fee_detail = trade_msg.get("feeDetail")
        trade_fee_data = (fee_detail[0] if isinstance(fee_detail, list) else fee_detail) or {}
        fee_amount = abs(Decimal(str(trade_fee_data.get("fee", trade_fee_data.get("totalFee", "0")))))
        fee_coin = trade_fee_data.get("feeCoin")
        side = TradeType.BUY if trade_msg["side"] == "buy" else TradeType.SELL

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=side,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_coin)],
        )

        trade_id: str = str(trade_msg.get("execId", trade_msg.get("tradeId")))
        trading_pair = tracked_order.trading_pair
        fill_price = Decimal(str(trade_msg.get("execPrice", trade_msg.get("priceAvg"))))
        base_amount = Decimal(str(trade_msg.get("execQty", trade_msg.get("size"))))
        quote_amount = Decimal(str(trade_msg.get("execValue", trade_msg.get("amount"))))

        if (
            "execQty" not in trade_msg
            and tracked_order.trade_type is TradeType.BUY
            and tracked_order.order_type is OrderType.MARKET
            and fill_price > Decimal("0")
        ):
            # Spot market buys are submitted sized in quote currency, and the legacy payload
            # echoed that quote size back under "size". V3 reports the executed base quantity in
            # execQty, so only the legacy shape needs converting - and it converts at the price
            # the fill actually executed at, never at the price estimated when the order was
            # placed, which would misstate the filled quantity whenever the two differ.
            base_amount = (quote_amount / fill_price).quantize(
                Decimal(self.trading_rules[trading_pair].min_base_amount_increment),
                rounding=ROUND_UP
            )

        fill_ts = trade_msg.get("updatedTime", trade_msg.get("uTime", trade_msg.get("createdTime")))
        trade_update: TradeUpdate = TradeUpdate(
            trade_id=trade_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(trade_msg["orderId"]),
            trading_pair=trading_pair,
            fill_timestamp=int(fill_ts) * 1e-3,
            fill_price=fill_price,
            fill_base_amount=base_amount,
            fill_quote_amount=quote_amount,
            fee=fee
        )

        return trade_update

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

    async def _user_stream_event_listener(self) -> None:
        if not await self._wait_for_account_mode():
            return await self._classic_user_stream_event_listener()
        async for event_message in self._iter_user_event_queue():
            try:
                # V3 UTA push envelope uses arg.topic (the V2 API used arg.channel).
                arg = event_message["arg"]
                channel = arg.get("topic")
                data = event_message["data"]

                self.logger().debug(f"Channel: {channel} - Data: {data}")

                if channel == CONSTANTS.WS_ORDERS_ENDPOINT:
                    for order_msg in data:
                        self._process_order_event_message(order_msg)
                elif channel == CONSTANTS.WS_FILL_ENDPOINT:
                    for fill_msg in data:
                        self._process_fill_event_message(fill_msg)
                elif channel == CONSTANTS.WS_ACCOUNT_ENDPOINT:
                    # The V3 account channel pushes account snapshots; the per-coin balances are
                    # nested in each entry's "coin" array (coin/available/locked/balance).
                    for account_msg in data:
                        for coin_balance in account_msg.get("coin", []):
                            self._set_account_balances(coin_balance)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")

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

    def _process_order_event_message(self, order_msg: Dict[str, Any]) -> None:
        """
        Updates the in-flight order state from the V3 UTA "order" channel (BitgetUaOrder).

        The order channel carries order state only (orderStatus, cumExecQty, avgPrice, ...);
        individual fills are delivered on the separate "fill" channel and handled by
        _process_fill_event_message.
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
                update_timestamp=int(order_msg["updatedTime"]) * 1e-3,
                new_state=order_status,
                client_order_id=client_order_id,
                exchange_order_id=order_msg["orderId"],
            )
            self._order_tracker.process_order_update(new_order_update)

    def _process_fill_event_message(self, fill_msg: Dict[str, Any]) -> None:
        try:
            order_id = str(fill_msg.get("orderId", ""))
            trade_id = str(fill_msg.get("tradeId", ""))
            # Match on clientOid first: a market order can fill before its place-order response
            # arrives, and until then the tracked order has no exchange order id to match on.
            client_order_id = fill_msg.get("clientOid")
            fillable_order = (
                self._order_tracker.all_fillable_orders.get(str(client_order_id)) if client_order_id else None
            ) or self._order_tracker.all_fillable_orders_by_exchange_order_id.get(order_id)

            if not fillable_order:
                self.logger().debug(
                    f"Ignoring fill message for order {order_id}: not in in_flight_orders."
                )
                return

            trade_update = self._parse_trade_update(
                trade_msg=fill_msg,
                tracked_order=fillable_order,
                source_type="websocket"
            )
            if trade_update:
                self._order_tracker.process_trade_update(trade_update)

                self.logger().debug(
                    f"Processed fill event for order {fillable_order.client_order_id}: "
                    f"Trade {trade_id}: {fill_msg.get('size')} at {fill_msg.get('priceAvg')}."
                )
        except Exception as e:
            self.logger().error(f"Error processing fill event: {e}", exc_info=True)

    def _set_account_balances(self, data: Dict[str, Any]) -> None:
        # V3 UTA renames the held-balance field "frozen" -> "locked"; both spellings are tolerated
        # so the same helper can parse REST (account/assets) and websocket (account channel) payloads.
        symbol = data["coin"]
        available = Decimal(str(data["available"]))
        frozen = Decimal(str(data.get("locked", data.get("frozen", "0"))))
        self._account_balances[symbol] = frozen + available
        self._account_available_balances[symbol] = available

    def _initialize_trading_pair_symbols_from_exchange_info(
        self,
        exchange_info: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        mapping = bidict()
        for symbol_data in exchange_info["data"]:
            if bitget_utils.is_exchange_information_valid(exchange_info=symbol_data):
                try:
                    exchange_symbol = symbol_data["symbol"]
                    base = symbol_data["baseCoin"]
                    quote = symbol_data["quoteCoin"]
                    trading_pair = combine_to_hb_trading_pair(base, quote)
                    mapping[exchange_symbol] = trading_pair
                except Exception as exception:
                    self.logger().error(
                        f"There was an error parsing a trading pair information ({exception})"
                    )
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(
        self,
        exchange_info_dict: Dict[str, List[Dict[str, Any]]]
    ) -> List[TradingRule]:
        trading_rules = []
        for rule in exchange_info_dict["data"]:
            if bitget_utils.is_instrument_tradable(exchange_info=rule):
                try:
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                        symbol=rule["symbol"]
                    )
                    # V3 instruments renames minTradeUSDT -> minOrderAmount; precision fields
                    # (pricePrecision/quantityPrecision/quotePrecision) keep their names.
                    min_notional = rule.get("minOrderAmount", rule.get("minTradeUSDT"))
                    # minOrderQty is the exchange's own minimum order size and is not always the
                    # same as the quantity step: instruments with quantityPrecision 0 still accept
                    # 0.0001, so deriving the minimum from the precision would overstate it by
                    # orders of magnitude and make the executors reject valid orders.
                    min_order_size = Decimal(str(rule.get("minOrderQty", rule.get("minTradeAmount"))))
                    precision_step = Decimal(f"1e-{rule['quantityPrecision']}")
                    if min_order_size > 0:
                        # quantityPrecision is not always consistent with minOrderQty: the tokenized
                        # stock pairs report precision 0 while accepting 0.0001. Taking the finer of
                        # the two keeps the step from rounding the exchange's own minimum down to
                        # zero, which would reject every order those pairs actually accept.
                        quantity_step = min(precision_step, min_order_size)
                    else:
                        # Nearly every V3 spot pair reports minOrderQty "0" (no base-size minimum);
                        # a zero step would make order quantization divide by zero.
                        quantity_step = precision_step
                        min_order_size = precision_step
                    trading_rules.append(
                        TradingRule(
                            trading_pair=trading_pair,
                            min_order_size=min_order_size,
                            min_price_increment=Decimal(f"1e-{rule['pricePrecision']}"),
                            min_base_amount_increment=quantity_step,
                            min_quote_amount_increment=Decimal(f"1e-{rule['quotePrecision']}"),
                            min_notional_size=Decimal(str(min_notional)),
                        )
                    )
                except Exception:
                    self.logger().exception(
                        f"Error parsing the trading pair rule: {rule}. Skipping."
                    )
        return trading_rules
