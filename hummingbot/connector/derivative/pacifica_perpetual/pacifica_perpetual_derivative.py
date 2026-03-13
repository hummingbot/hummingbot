import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from bidict import bidict

import hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_web_utils as web_utils
from hummingbot.connector.constants import DAY
from hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_api_order_book_data_source import (
    PacificaPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_auth import PacificaPerpetualAuth
from hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_user_stream_data_source import (
    PacificaPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

s_decimal_0 = Decimal(0)


class PacificaPerpetualPriceRecord(NamedTuple):
    """
    Price record for the specific trading pair

    :param timestamp: the timestamp of the price (in seconds)
    :param index_price: the index price
    :param mark_price: the mark price
    """
    timestamp: float
    index_price: Decimal
    mark_price: Decimal


class PacificaPerpetualDerivative(PerpetualDerivativePyBase):

    web_utils = web_utils

    TRADING_FEES_INTERVAL = DAY

    def __init__(
        self,
        pacifica_perpetual_agent_wallet_public_key: str,
        pacifica_perpetual_agent_wallet_private_key: str,
        pacifica_perpetual_user_wallet_public_key: str,
        pacifica_perpetual_api_config_key: str = "",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
    ):
        self.agent_wallet_public_key = pacifica_perpetual_agent_wallet_public_key
        self.agent_wallet_private_key = pacifica_perpetual_agent_wallet_private_key
        self.user_wallet_public_key = pacifica_perpetual_user_wallet_public_key
        self.api_config_key = pacifica_perpetual_api_config_key

        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs

        self._prices: Dict[str, Optional[PacificaPerpetualPriceRecord]] = {
            trading_pair: None for trading_pair in trading_pairs
        }

        self._order_history_last_poll_timestamp: Dict[str, float] = {}

        self._fee_tier = 0

        super().__init__(balance_asset_limit=balance_asset_limit, rate_limits_share_pct=rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> PacificaPerpetualAuth:
        return PacificaPerpetualAuth(
            agent_wallet_public_key=self.agent_wallet_public_key,
            agent_wallet_private_key=self.agent_wallet_private_key,
            user_wallet_public_key=self.user_wallet_public_key,
        )

    @property
    def rate_limits_rules(self):
        if not self.api_config_key:
            return CONSTANTS.RATE_LIMITS

        tier2_limit = CONSTANTS.FEE_TIER_LIMITS.get(self._fee_tier, CONSTANTS.PACIFICA_TIER_2_LIMIT)

        global_limit = RateLimit(
            limit_id=CONSTANTS.PACIFICA_LIMIT_ID,
            limit=tier2_limit,
            time_interval=CONSTANTS.PACIFICA_LIMIT_INTERVAL
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

        if self.api_config_key:
            pf_headers = {"PF-API-KEY": self.api_config_key}
            if headers:
                headers.update(pf_headers)
            else:
                headers = pf_headers

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
        """
        GET API CONFIG KEYS response examples
        {'success': True, 'data': {'active_api_keys': [], 'api_key_limit': 5}, 'error': None, 'code': None}
        {'success': True, 'data': {'active_api_keys': ['2fFZuXXX_CXB5XXXDGMRXXXDiCKTer'], 'api_key_limit': 5}, 'error': None, 'code': None}
        CREATE API CONFIG KEY response example
        {'success': True, 'data': {'api_key': '2fFZuXXX_CXB5XXXDGMRXXXDiCKTer'}, 'error': None, 'code': None}
        """
        self.logger().info(f"api_config_key: {self.api_config_key}")
        if self.api_config_key:
            # Key already provided in config
            return

        # Try to fetch existing keys

        # We can use _api_post safely here because self.api_config_key is not set yet,
        # so _api_request will not attempt to inject the header.
        response = await self._api_post(
            path_url=CONSTANTS.GET_ACCOUNT_API_CONFIG_KEYS,
            data={
                "type": "list_api_keys",
            },
            is_auth_required=True,
            limit_id=CONSTANTS.PACIFICA_LIMIT_ID
        )

        if response.get("success") is True and response.get("data"):
            if response["data"]["active_api_keys"]:
                self.api_config_key = response["data"]["active_api_keys"][0]
                self.logger().info(f"Using existing API Config Key: {self.api_config_key}")
                if self._throttler:
                    self._throttler.set_rate_limits(self.rate_limits_rules)
                return
            else:
                self.logger().info("No active API Config Keys found")

        # If no keys found or list failed (maybe due to no keys?), try to create one
        response = await self._api_post(
            path_url=CONSTANTS.CREATE_ACCOUNT_API_CONFIG_KEY,
            data={
                "type": "create_api_key",
            },
            is_auth_required=True,
            limit_id=CONSTANTS.PACIFICA_LIMIT_ID
        )

        if response.get("success") is True and response.get("data"):
            self.api_config_key = response["data"]["api_key"]
            self.logger().info(f"Created new API Config Key: {self.api_config_key}")
            if self._throttler:
                self._throttler.set_rate_limits(self.rate_limits_rules)
                self.logger().info("New API Config Key is in use now")
        else:
            self.logger().error(f"Failed to create API Config Key: {response}")

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
        # TODO (dizpers): it might be too much to request full exchange info just to check network
        # it's happening once every 10 seconds
        # Pacifica doesn't have special ping / time endpoint
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs(self) -> Optional[List[str]]:
        return self._trading_pairs

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
        https://docs.pacifica.fi/api-documentation/api/error-codes

        """
        return '"code":5' in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return PacificaPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return PacificaPerpetualUserStreamDataSource(
            connector=self,
            api_factory=self._web_assistants_factory,
            auth=self._auth,
            domain=self._domain,
        )

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        https://docs.pacifica.fi/api-documentation/api/rest-api/markets/get-market-info

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
        https://docs.pacifica.fi/api-documentation/api/rest-api/orders/create-market-order
        https://docs.pacifica.fi/api-documentation/api/rest-api/orders/create-limit-order
        """

        # TODO (dizpers): should we add the support of STOP orders?

        # the exchange APIs let you pass client order id, which must be a UUID string
        # in order to do that, we should change the behaviour of
        # hummingbot.connector.utils.py:get_new_client_order_id(...) function
        # which is used to generate client order IDs in self.buy() / self.sell() functions

        # all of the above seems unreasonable for now
        # so we would use exchange order id for all types of operations

        data = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "side": "bid" if trade_type == TradeType.BUY else "ask",
            "amount": str(amount),
            "reduce_only": position_action == PositionAction.CLOSE,
        }

        api_endpoint_url = CONSTANTS.CREATE_MARKET_ORDER_PATH_URL
        if order_type.is_limit_type():
            api_endpoint_url = CONSTANTS.CREATE_LIMIT_ORDER_PATH_URL

            data["price"] = str(price)
            data["type"] = "create_order"
            # Good Till Cancelled
            data["tif"] = "GTC"
            if order_type == OrderType.LIMIT_MAKER:
                # Add Liquidiy Only
                data["tif"] = "ALO"
        elif order_type == OrderType.MARKET:
            data["type"] = "create_market_order"
            data["slippage_percent"] = CONSTANTS.MARKET_ORDER_MAX_SLIPPAGE

        response = await self._api_post(
            path_url=api_endpoint_url,
            data=data,
            is_auth_required=True,
        )

        exchange_order_id = str(response["data"]["order_id"])

        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        """
        https://docs.pacifica.fi/api-documentation/api/rest-api/orders/cancel-order
        """
        data = {
            "order_id": int(tracked_order.exchange_order_id),
            "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
            "type": "cancel_order",
        }
        await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            data=data,
            is_auth_required=True
        )

        return True

    async def _update_balances(self):
        """
        https://docs.pacifica.fi/api-documentation/api/rest-api/account/get-account-info
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
        account = self.user_wallet_public_key

        response = await self._api_get(
            path_url=CONSTANTS.GET_ACCOUNT_INFO_PATH_URL,
            params={"account": account},
            return_err=True
        )

        if not response.get("success"):
            self.logger().error(f"[_update_balances] Failed to update balances (api responded with failure): {response}")
            return

        data = response.get("data")
        if not data:
            self.logger().error(f"[_update_balances] Failed to update balances (no data): {response}")
            return

        # Pacifica is a USDC-collateralized exchange
        asset = "USDC"

        # there's only one asset
        # so maybe there's no need for clear() calls
        # TODO (dizpers)
        self._account_balances.clear()
        self._account_available_balances.clear()

        self._account_balances[asset] = Decimal(str(data["account_equity"]))
        self._account_balances[asset] = Decimal(str(data["account_equity"]))
        self._account_available_balances[asset] = Decimal(str(data["available_to_spend"]))
        self._fee_tier = data.get("fee_level", 0)

    async def _update_positions(self):
        """
        https://docs.pacifica.fi/api-documentation/api/rest-api/account/get-positions
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

        https://docs.pacifica.fi/api-documentation/api/rest-api/markets/get-prices
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
            path_url=CONSTANTS.GET_POSITIONS_PATH_URL,
            params={"account": self.user_wallet_public_key},
            return_err=True,
        )

        if not response.get("success") is True:
            self.logger().error(f"[_update_positions] Failed to update positions (api responded with failure): {response}")
            return

        position_symbols = [position_entry["symbol"] for position_entry in response.get("data", [])]
        position_trading_pairs = [
            await self.trading_pair_associated_to_exchange_symbol(position_symbol) for position_symbol in position_symbols
        ]
        if any([self.get_pacifica_price(position_trading_pair) is None for position_trading_pair in position_trading_pairs]):
            self.logger().info("[_update_positions] Prices cache is empty. Going to fetch prices via HTTP.")
            # we should update the cache
            # in future we could also consider to add some cache invalidation rules (e.g. timestamp too old)
            prices_response = await self._api_get(
                path_url=CONSTANTS.GET_PRICES_PATH_URL,
                return_err=True,
            )
            if not prices_response.get("success") is True:
                self.logger().error(f"[_update_positions] Failed to update prices cache using HTTP API: {response}")
                return
            for price_entry in prices_response.get("data", []):
                if price_entry["symbol"] not in position_symbols:
                    continue
                hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(price_entry["symbol"])
                self.set_pacifica_price(
                    trading_pair=hb_trading_pair,
                    timestamp=price_entry["timestamp"] / 1000,
                    index_price=Decimal(price_entry["oracle"]),
                    mark_price=Decimal(price_entry["mark"]),
                )

        # if there're 2 positions available, it will only show those 2
        # if one of those 2 positions is closed -- you will see only 1
        # so it make sense to clear the storage of positions
        # and fill it with the positions from the response
        self._perpetual_trading.account_positions.clear()

        for position_entry in response.get("data", []):
            hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(position_entry["symbol"])
            position_side = PositionSide.LONG if position_entry["side"] == "bid" else PositionSide.SHORT
            position_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
            amount = Decimal(position_entry["amount"])
            entry_price = Decimal(position_entry["entry_price"])

            mark_price = self.get_pacifica_price(hb_trading_pair).mark_price

            if position_side == PositionSide.LONG:
                unrealized_pnl = (mark_price - entry_price) * amount
            else:
                unrealized_pnl = (entry_price - mark_price) * amount

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
        Retrieves trade updates for a specific order using the account trade history endpoint.
        Uses the order's creation timestamp as the start time to filter the trade history.

        https://docs.pacifica.fi/api-documentation/api/rest-api/account/get-trade-history

        Example API response:
        ```
        {
            "success": true,
            "data": [
                {
                    "history_id": 19329801,
                    "order_id": 315293920,
                    "client_order_id": "acf...",
                    "symbol": "LDO",
                    "amount": "0.1",
                    "price": "1.1904",
                    "entry_price": "1.176247",
                    "fee": "0",
                    "pnl": "-0.001415",
                    "event_type": "fulfill_maker",
                    "side": "close_short",
                    "created_at": 1759215599188,
                    "cause": "normal"
                }
            ],
            "next_cursor": "11111Z5RK",
            "has_more": true
        }
        ```
        """
        trade_updates = []

        # Use cached last poll timestamp or order creation time as start_time
        last_poll_timestamp = self._order_history_last_poll_timestamp.get(order.exchange_order_id)
        if last_poll_timestamp:
            start_time = int(last_poll_timestamp * 1000)
        else:
            start_time = int(order.creation_timestamp * 1000)

        current_time = self.current_timestamp
        end_time = int(current_time * 1000)

        params = {
            "account": self.user_wallet_public_key,
            "start_time": start_time,
            "end_time": end_time,
            "limit": 100,
        }

        while True:
            response = await self._api_get(
                path_url=CONSTANTS.GET_TRADE_HISTORY_PATH_URL,
                params=params,
            )

            if not response.get("success") or not response.get("data"):
                break

            for trade_message in response["data"]:
                exchange_order_id = str(trade_message["order_id"])

                if exchange_order_id != order.exchange_order_id:
                    continue

                fill_timestamp = trade_message["created_at"] / 1000
                fill_price = Decimal(trade_message["price"])
                fill_base_amount = Decimal(trade_message["amount"])

                trade_id = self.get_pacifica_finance_trade_id(
                    order_id=trade_message["order_id"],
                    timestamp=fill_timestamp,
                    fill_base_amount=fill_base_amount,
                    fill_price=fill_price,
                )

                fee_amount = Decimal(trade_message["fee"])
                fee_asset = order.quote_asset

                position_action = PositionAction.OPEN if trade_message["side"] in ("open_long", "open_short", ) else PositionAction.CLOSE

                fee = TradeFeeBase.new_perpetual_fee(
                    fee_schema=self.trade_fee_schema(),
                    position_action=position_action,
                    percent_token=fee_asset,
                    flat_fees=[TokenAmount(
                        amount=fee_amount,
                        token=fee_asset
                    )]
                )

                is_taker = trade_message["event_type"] == "fulfill_taker"

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

            if response.get("has_more") and response.get("next_cursor"):
                params["cursor"] = response["next_cursor"]
            else:
                break

        self._order_history_last_poll_timestamp[order.exchange_order_id] = current_time

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        https://docs.pacifica.fi/api-documentation/api/rest-api/orders/get-order-history-by-id

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
        response = await self._api_get(
            path_url=CONSTANTS.GET_ORDER_HISTORY_PATH_URL,
            params={
                "order_id": tracked_order.exchange_order_id,
            },
        )

        order_status = CONSTANTS.ORDER_STATE[response["data"][0]["order_status"]]

        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=response["data"][0]["created_at"] / 1000,
            new_state=order_status,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
        )

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """
        https://docs.pacifica.fi/api-documentation/api/rest-api/markets/get-candle-data

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
            "start_time": int(time.time() * 1000) - 60 * 1000,
        }

        response = await self._api_get(
            path_url=CONSTANTS.GET_CANDLES_PATH_URL,
            params=params,
        )

        return float(response["data"][0]["c"])

    async def _update_trading_fees(self):
        """
        https://docs.pacifica.fi/api-documentation/api/rest-api/account/get-account-info
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
            params={"account": self.user_wallet_public_key},
            return_err=True
        )

        # comparison with True is needed, bc we might expect a string to be there
        # while the only indicator of success here is True boolean value
        if not response.get("success") is True:
            self.logger().error(f"[_update_trading_fees] Failed to update trading fees (api responded with failure): {response}")
            return

        data = response.get("data")
        if not data:
            self.logger().error(f"[_update_trading_fees] Failed to update trading fees (no data): {response}")
            return

        trade_fee_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal(data["maker_fee"]),
            taker_percent_fee_decimal=Decimal(data["taker_fee"]),
        )

        for trading_pair in self._trading_pairs:
            self._trading_fees[trading_pair] = trade_fee_schema

        self.logger().info("Trading fees updated")

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        """
        https://docs.pacifica.fi/api-documentation/api/rest-api/account/get-funding-history

        Example API response:
            {
                "success": true,
                "data": [
                    {
                        "history_id": 2287920,
                        "symbol": "PUMP",
                        "side": "ask",
                        "amount": "39033804",
                        "payout": "2.617479",
                        "rate": "0.0000125",
                        "created_at": 1759222804122
                    },
                    ...
                ],
                "next_cursor": "11114Lz77",
                "has_more": true
            }
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

        response = await self._api_get(
            path_url=CONSTANTS.GET_FUNDING_HISTORY_PATH_URL,
            params={
                "account": self.user_wallet_public_key,
                "limit": 100,
            },
            return_err=True
        )

        if not response.get("success") is True:
            self.logger().error(f"Failed to fetch last fee payment (api responded with failure): {response}")
            return 0, Decimal("-1"), Decimal("-1")

        data = response.get("data")
        if not data:
            self.logger().debug(f"Failed to fetch last fee payment (no data): {response}")
            return 0, Decimal("-1"), Decimal("-1")

        # check if the first page has the trading pair we need
        for funding_history_item in data:
            if funding_history_item["symbol"] == symbol:
                return funding_history_item["created_at"], Decimal(funding_history_item["rate"]), Decimal(funding_history_item["payout"])

        # so it's not presented on the first page
        # we should check other pages, but no more than 1 hour back
        # 1 hour back from the time of first item on first page
        # has_more == True if there're more pages
        # cursor is used to query next page (pass it to GET params)

        timestamp_of_first_record_on_first_page = data[0]["created_at"]

        # this is timestamp in ms
        # let's calculate 1hr back from it
        one_hour_back_timestamp = timestamp_of_first_record_on_first_page - 60 * 60 * 1000

        # let's also extend it by 5 minutes
        # in case the exchange the gap between entries is a bit bigger than 1hr
        one_hour_back_timestamp -= 5 * 60 * 1000

        # now let's query the pages one by one
        # until we reach the page with the first record older than one hour back
        has_more = response.get("has_more", False)
        cursor = response.get("next_cursor")
        while has_more:
            response = await self._api_get(
                path_url=CONSTANTS.GET_FUNDING_HISTORY_PATH_URL,
                params={
                    "account": self.user_wallet_public_key,
                    "limit": 100,
                    "cursor": cursor,
                },
                return_err=True
            )

            if not response.get("success") is True:
                self.logger().error(f"Failed to fetch last fee payment (api responded with failure): {response}")
                return 0, Decimal("-1"), Decimal("-1")

            data = response.get("data")
            if not data:
                self.logger().debug(f"Failed to fetch last fee payment (no data): {response}")
                return 0, Decimal("-1"), Decimal("-1")

            if data[0]["created_at"] < one_hour_back_timestamp:
                # this page doesn't have the record we need
                # the timestamp of first record on this page is alrady behind the limit
                return 0, Decimal("-1"), Decimal("-1")

            for funding_history_item in data:
                if funding_history_item["symbol"] == symbol:
                    return funding_history_item["created_at"], Decimal(funding_history_item["rate"]), Decimal(funding_history_item["payout"])

            has_more = response.get("has_more", False)
            cursor = response.get("next_cursor")

        return 0, Decimal("-1"), Decimal("-1")

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

        data = {
            "symbol": symbol,
            "leverage": leverage,
            "type": "update_leverage",
        }
        response: Dict[str, Any] = await self._api_post(
            path_url=CONSTANTS.SET_LEVERAGE_PATH_URL,
            data=data,
            return_err=True,
            is_auth_required=True,
        )

        success = response.get("success") is True
        msg = ""
        if not success:
            msg = (f"Error when setting leverage: "
                   f"msg={response.get('error', 'error')}, "
                   f"code={response.get('code', 'code')}")

        return success, msg

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        return True, ""

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
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
                if channel == CONSTANTS.WS_ACCOUNT_ORDER_UPDATES_CHANNEL:
                    await self._process_account_order_updates_ws_event_message(event_message)
                elif channel == CONSTANTS.WS_ACCOUNT_POSITIONS_CHANNEL:
                    await self._process_account_positions_ws_event_message(event_message)
                elif channel == CONSTANTS.WS_ACCOUNT_INFO_CHANNEL:
                    await self._process_account_info_ws_event_message(event_message)
                elif channel == CONSTANTS.WS_ACCOUNT_TRADES_CHANNEL:
                    await self._process_account_trades_ws_event_message(event_message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop: {e}", exc_info=True)
                await self._sleep(5.0)

    async def _process_account_order_updates_ws_event_message(self, event_message: Dict[str, Any]):
        """
        https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/account-order-updates
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
        tracked_orders = {order.exchange_order_id: order for order in self._order_tracker.all_updatable_orders.values()}

        for order_update_message in event_message["data"]:
            exchange_order_id = str(order_update_message["i"])
            tracked_order = tracked_orders.get(exchange_order_id)
            if tracked_order:
                order_status = CONSTANTS.ORDER_STATE[order_update_message["os"]]
                order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=order_update_message["ut"] / 1000,
                    new_state=order_status,
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                )
                self._order_tracker.process_order_update(order_update)

    async def _process_account_positions_ws_event_message(self, event_message: Dict[str, Any]):
        """
        https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/account-positions
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
        # Pacifica provides full snapshot of positions
        # if there're 2 positions available, it will only show those 2
        # if one of those 2 positions is closed -- you will see only 1
        # so it make sense to clear the storage of positions
        # and fill it with the positions from the response

        # the implementation is actually the same as the one for
        # HTTP calls self._update_positions()
        self._perpetual_trading.account_positions.clear()

        for position_entry in event_message["data"]:
            hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(position_entry["s"])
            position_side = PositionSide.LONG if position_entry["d"] == "bid" else PositionSide.SHORT
            position_key = self._perpetual_trading.position_key(hb_trading_pair, position_side)
            amount = Decimal(position_entry["a"])
            entry_price = Decimal(position_entry["p"])

            mark_price = self.get_pacifica_price(hb_trading_pair).mark_price

            if position_side == PositionSide.LONG:
                unrealized_pnl = (mark_price - entry_price) * amount
            else:
                unrealized_pnl = (entry_price - mark_price) * amount

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
        https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/account-info
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
        # Pacifica is a USDC-collateralized exchange
        asset = "USDC"

        # there's only one asset
        # so maybe there's no need for clear() calls
        # TODO (dizpers)
        self._account_balances.clear()
        self._account_available_balances.clear()

        self._account_balances[asset] = Decimal(event_message["data"]["ae"])
        self._account_available_balances[asset] = Decimal(event_message["data"]["as"])

    async def _process_account_trades_ws_event_message(self, event_message: Dict[str, Any]):
        """
        https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/account-trades
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

        for trade_message in event_message["data"]:
            exchange_order_id = str(trade_message["i"])
            tracked_order = tracked_orders.get(exchange_order_id)
            if not tracked_order:
                continue

            trade_id = self.get_pacifica_finance_trade_id(
                order_id=trade_message["i"],
                timestamp=trade_message["t"] / 1000,
                fill_base_amount=Decimal(trade_message["a"]),
                fill_price=Decimal(trade_message["p"]),
            )

            # it would always be USDC
            fee_asset = tracked_order.quote_asset

            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=PositionAction.OPEN if trade_message["ts"] in ("open_long", "open_short", ) else PositionAction.CLOSE,
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
                fill_timestamp=trade_message["t"] / 1000,
            )

            self._order_tracker.process_trade_update(trade_update)

    def set_pacifica_price(self, trading_pair: str, timestamp: float, index_price: Decimal, mark_price: Decimal):
        """
        Set the price information for the given trading pair

        :param trading_pair: the trading pair
        :param timestamp: the timestamp of the price (in seconds)
        :param index_price: the index price
        :param mark_price: the mark price
        """
        existing = self._prices.get(trading_pair)
        if existing is None or timestamp >= existing.timestamp:
            self._prices[trading_pair] = PacificaPerpetualPriceRecord(
                timestamp=timestamp,
                index_price=index_price,
                mark_price=mark_price
            )

    def get_pacifica_price(self, trading_pair: str) -> Optional[PacificaPerpetualPriceRecord]:
        """
        Get the price information for the given trading pair

        :param trading_pair: the trading pair

        :return: the price information for the given trading pair or None if the trading pair is not found
        """
        return self._prices.get(trading_pair)

    def get_pacifica_finance_trade_id(self, order_id: int, timestamp: float, fill_base_amount: Decimal, fill_price: Decimal) -> str:
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
        await super().start_network()

    async def get_all_pairs_prices(self) -> List[Dict[str, Any]]:
        """
        Retrieves the prices (mark price) for all trading pairs.
        Required for Rate Oracle support.

        https://docs.pacifica.fi/api-documentation/api/rest-api/markets/get-prices
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
