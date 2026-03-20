from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

import hummingbot.core.utils.estimate_fee as fee_utils
from hummingbot.connector.exchange.bithumb import (
    bithumb_auth as bithumb_auth_module,
    bithumb_constants as CONSTANTS,
    bithumb_web_utils as web_utils,
)
from hummingbot.connector.exchange.bithumb.bithumb_api_order_book_data_source import BithumbAPIOrderBookDataSource
from hummingbot.connector.exchange.bithumb.bithumb_api_user_stream_data_source import BithumbAPIUserStreamDataSource
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BithumbExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    web_utils = web_utils

    def __init__(
        self,
        bithumb_api_key: str,
        bithumb_secret_key: str,
        payment_currency: str = CONSTANTS.DEFAULT_PAYMENT_CURRENCY,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self._api_key = bithumb_api_key
        self._secret_key = bithumb_secret_key
        self._payment_currency = payment_currency.upper()
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._domain = domain

        super().__init__(balance_asset_limit=balance_asset_limit, rate_limits_share_pct=rate_limits_share_pct)

        self._real_time_balance_update = False

    # -------------------------------------------------------------------------
    # Required properties
    # -------------------------------------------------------------------------

    @property
    def authenticator(self):
        return bithumb_auth_module.BithumbAuth(self._api_key, self._secret_key)

    @property
    def name(self) -> str:
        return "bithumb"

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
    def trading_rules_request_path(self) -> str:
        return f"/public/ticker/ALL_{self._payment_currency}"

    @property
    def trading_pairs_request_path(self) -> str:
        return f"/public/ticker/ALL_{self._payment_currency}"

    @property
    def check_network_request_path(self) -> str:
        return f"/public/ticker/ALL_{self._payment_currency}"

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    # -------------------------------------------------------------------------
    # Factory methods
    # -------------------------------------------------------------------------

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BithumbAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs or [],
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BithumbAPIUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    # -------------------------------------------------------------------------
    # Trading pair symbol mapping
    # -------------------------------------------------------------------------

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        """
        Bithumb /public/ticker/ALL_KRW response:
          { "status": "0000", "data": { "BTC": {...}, "ETH": {...}, "date": "..." } }
        """
        mapping = bidict()
        data = exchange_info.get("data", {})
        for key, value in data.items():
            if key == "date":
                continue
            bithumb_symbol = f"{key}_{self._payment_currency}"
            hb_pair = combine_to_hb_trading_pair(key, self._payment_currency)
            mapping[bithumb_symbol] = hb_pair
        self._set_trading_pair_symbol_map(mapping)

    # -------------------------------------------------------------------------
    # Trading rules
    # -------------------------------------------------------------------------

    async def _format_trading_rules(self, exchange_info: Dict[str, Any]) -> List[TradingRule]:
        """
        Bithumb does not expose per-pair min/max size rules via public API.
        Use conservative defaults:
          - min_notional_size = 1000 KRW
          - min increments = 1 (KRW) for price, 0.00000001 for base amount
        """
        rules: List[TradingRule] = []
        data = exchange_info.get("data", {})
        for key in data:
            if key == "date":
                continue
            hb_pair = combine_to_hb_trading_pair(key, self._payment_currency)
            rules.append(
                TradingRule(
                    trading_pair=hb_pair,
                    min_price_increment=Decimal("1"),
                    min_base_amount_increment=Decimal("0.00000001"),
                    min_notional_size=Decimal("1000"),
                    supports_market_orders=True,
                )
            )
        return rules

    # -------------------------------------------------------------------------
    # Last traded prices
    # -------------------------------------------------------------------------

    async def get_all_pairs_prices(self) -> List[Dict[str, Any]]:
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(f"/public/ticker/ALL_{self._payment_currency}"),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.TICKER_ALL_PATH_URL,
        )
        results = []
        data = response.get("data", {})
        for key, value in data.items():
            if key == "date":
                continue
            results.append({
                "symbol": f"{key}_{self._payment_currency}",
                "closing_price": value.get("closing_price", "0"),
            })
        return results

    # -------------------------------------------------------------------------
    # Error classification helpers
    # -------------------------------------------------------------------------

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return "order_not_found" in str(status_update_exception).lower()

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return "order_not_found" in str(cancelation_exception).lower()

    # -------------------------------------------------------------------------
    # Balance
    # -------------------------------------------------------------------------

    async def _update_balances(self):
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.private_rest_url(CONSTANTS.BALANCE_PATH_URL),
            data={"currency": "ALL"},
            method=RESTMethod.POST,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.BALANCE_PATH_URL,
        )
        if response.get("status") != "0000":
            raise IOError(f"Bithumb balance error: {response}")

        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        data = response.get("data", {})
        for key, raw_value in data.items():
            if not key.startswith("available_"):
                continue
            currency = key[len("available_"):].upper()
            available = Decimal(str(raw_value))
            total_key = f"total_{currency.lower()}"
            total = Decimal(str(data.get(total_key, raw_value)))
            self._account_available_balances[currency] = available
            self._account_balances[currency] = total
            remote_asset_names.add(currency)

        for stale in local_asset_names - remote_asset_names:
            del self._account_available_balances[stale]
            del self._account_balances[stale]

    # -------------------------------------------------------------------------
    # Order placement
    # -------------------------------------------------------------------------

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Optional[Decimal] = None,
        position_action: Optional[PositionAction] = None,
    ) -> Tuple[str, float]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        parts = symbol.split("_")
        order_currency = parts[0]
        payment_currency = parts[1] if len(parts) > 1 else self._payment_currency
        order_side = "bid" if trade_type == TradeType.BUY else "ask"

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()

        if order_type == OrderType.MARKET:
            if trade_type == TradeType.BUY:
                # Market buy: units = KRW amount to spend
                path = CONSTANTS.TRADE_MARKET_BUY_PATH_URL
                data = {
                    "order_currency": order_currency,
                    "payment_currency": payment_currency,
                    "units": str(amount),
                }
            else:
                # Market sell: units = base quantity to sell
                path = CONSTANTS.TRADE_MARKET_SELL_PATH_URL
                data = {
                    "order_currency": order_currency,
                    "payment_currency": payment_currency,
                    "units": str(amount),
                }
        else:
            path = CONSTANTS.TRADE_PLACE_PATH_URL
            data = {
                "order_currency": order_currency,
                "payment_currency": payment_currency,
                "units": str(amount),
                "price": str(price),
                "type": order_side,
            }

        response = await rest_assistant.execute_request(
            url=web_utils.private_rest_url(path),
            data=data,
            method=RESTMethod.POST,
            is_auth_required=True,
            throttler_limit_id=path,
        )

        if response.get("status") != "0000":
            raise IOError(f"Bithumb place order error [{response.get('status')}]: {response.get('message', response)}")

        resp_data = response.get("data", {})
        exchange_order_id = str(resp_data.get("order_id", ""))
        try:
            order_date_ms = int(resp_data.get("order_date", 0))
            timestamp = order_date_ms * 1e-3
        except (TypeError, ValueError):
            timestamp = self.current_timestamp

        return exchange_order_id, timestamp

    # -------------------------------------------------------------------------
    # Order cancellation
    # -------------------------------------------------------------------------

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        parts = symbol.split("_")
        order_currency = parts[0]
        payment_currency = parts[1] if len(parts) > 1 else self._payment_currency
        order_side = "bid" if tracked_order.trade_type == TradeType.BUY else "ask"

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.private_rest_url(CONSTANTS.TRADE_CANCEL_PATH_URL),
            data={
                "order_id": tracked_order.exchange_order_id,
                "order_currency": order_currency,
                "payment_currency": payment_currency,
                "type": order_side,
            },
            method=RESTMethod.POST,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.TRADE_CANCEL_PATH_URL,
        )

        if response.get("status") != "0000":
            raise IOError(
                f"Bithumb cancel error [{response.get('status')}]: {response.get('message', response)}"
            )

        return True, tracked_order.exchange_order_id

    # -------------------------------------------------------------------------
    # Order status
    # -------------------------------------------------------------------------

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        parts = symbol.split("_")
        order_currency = parts[0]
        payment_currency = parts[1] if len(parts) > 1 else self._payment_currency

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.private_rest_url(CONSTANTS.ORDER_DETAIL_PATH_URL),
            data={
                "order_id": tracked_order.exchange_order_id,
                "order_currency": order_currency,
                "payment_currency": payment_currency,
            },
            method=RESTMethod.POST,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.ORDER_DETAIL_PATH_URL,
        )

        if response.get("status") == "5100":
            raise IOError("order_not_found")
        if response.get("status") != "0000":
            raise IOError(
                f"Bithumb order detail error [{response.get('status')}]: {response.get('message', response)}"
            )

        data = response.get("data", {})
        order_status_str = data.get("order_status", "placed")
        new_state = CONSTANTS.ORDER_STATE.get(order_status_str, tracked_order.current_state)

        try:
            transaction_date_ms = int(data.get("transaction_date", 0))
            update_timestamp = transaction_date_ms * 1e-3
        except (TypeError, ValueError):
            update_timestamp = self.current_timestamp

        return OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=new_state,
        )

    # -------------------------------------------------------------------------
    # Trade fills
    # -------------------------------------------------------------------------

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
        parts = symbol.split("_")
        order_currency = parts[0]
        payment_currency = parts[1] if len(parts) > 1 else self._payment_currency

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.private_rest_url(CONSTANTS.ORDER_DETAIL_PATH_URL),
            data={
                "order_id": order.exchange_order_id,
                "order_currency": order_currency,
                "payment_currency": payment_currency,
            },
            method=RESTMethod.POST,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.ORDER_DETAIL_PATH_URL,
        )

        if response.get("status") != "0000":
            return []

        data = response.get("data", {})
        contracts = data.get("contract", [])
        trade_updates = []

        for idx, contract in enumerate(contracts):
            try:
                fill_price = Decimal(str(contract.get("price", "0")))
                fill_amount = Decimal(str(contract.get("units", "0")))
                fee_amount = Decimal(str(contract.get("fee", "0")))
                fee_currency = str(contract.get("fee_currency", payment_currency)).upper()
                tx_date = contract.get("transaction_date", "0")
                fill_timestamp = int(tx_date) * 1e-3
            except (ValueError, TypeError):
                continue

            trade_id = f"{order.exchange_order_id}_{idx}"

            fee = AddedToCostTradeFee(
                flat_fees=[TokenAmount(token=fee_currency, amount=fee_amount)]
            )

            trade_updates.append(
                TradeUpdate(
                    trade_id=trade_id,
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    trading_pair=order.trading_pair,
                    fill_timestamp=fill_timestamp,
                    fill_price=fill_price,
                    fill_base_amount=fill_amount,
                    fill_quote_amount=fill_price * fill_amount,
                    fee=fee,
                )
            )

        return trade_updates

    # -------------------------------------------------------------------------
    # Fee calculation
    # -------------------------------------------------------------------------

    async def _update_trading_fees(self):
        pass

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: Optional[PositionAction] = None,
        amount: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker_val = is_maker if is_maker is not None else (order_type == OrderType.LIMIT_MAKER)
        return fee_utils.build_trade_fee(
            exchange=self.name,
            is_maker=is_maker_val,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount or Decimal("0"),
            price=price or Decimal("0"),
        )

    # -------------------------------------------------------------------------
    # User stream event listener
    # -------------------------------------------------------------------------

    async def _user_stream_event_listener(self):
        """
        Bithumb has no private WebSocket.
        Heartbeat events from BithumbAPIUserStreamDataSource are silently discarded.
        All state updates occur through the exchange's REST polling loop.
        """
        async for event_message in self._iter_user_event_queue():
            # Ignore heartbeats; real updates come from polling
            if event_message.get("type") == "heartbeat":
                continue
