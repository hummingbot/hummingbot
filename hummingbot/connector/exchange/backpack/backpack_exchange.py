import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.backpack import (
    backpack_constants as CONSTANTS,
    backpack_web_utils as web_utils,
)
from hummingbot.connector.exchange.backpack.backpack_api_order_book_data_source import (
    BackpackAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.backpack.backpack_api_user_stream_data_source import (
    BackpackAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BackpackExchange(ExchangePyBase):
    """
    Hummingbot connector for Backpack Exchange spot trading.
    """
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
        self,
        backpack_api_key: str = None,
        backpack_api_secret: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key = backpack_api_key
        self._api_secret = backpack_api_secret
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._domain = domain
        self._trading_pair_symbol_map: Optional[bidict] = None
        super().__init__()

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> Optional[BackpackAuth]:
        if self._trading_required:
            return BackpackAuth(
                self._api_key,
                self._api_secret,
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
        return CONSTANTS.STATUS_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BackpackAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BackpackAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Parse exchange market info into trading rules.
        """
        trading_rules = []

        for market in exchange_info_dict:
            try:
                symbol = market.get("symbol", "")
                trading_pair = self.exchange_symbol_to_trading_pair(symbol)

                filters = market.get("filters", {})
                price_filter = filters.get("price", {})
                lot_filter = filters.get("quantity", {})

                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(str(lot_filter.get("minQuantity", "0.001"))),
                        max_order_size=Decimal(str(lot_filter.get("maxQuantity", "1000000"))),
                        min_price_increment=Decimal(str(price_filter.get("tickSize", "0.01"))),
                        min_base_amount_increment=Decimal(str(lot_filter.get("stepSize", "0.001"))),
                        min_notional_size=Decimal(str(market.get("minNotional", "10"))),
                    )
                )
            except Exception as e:
                self.logger().warning(f"Error parsing trading rule for {market}: {e}")

        return trading_rules

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
        """
        Place an order on Backpack.
        """
        symbol = self.trading_pair_to_exchange_symbol(trading_pair)

        order_data = {
            "symbol": symbol,
            "side": "Bid" if trade_type == TradeType.BUY else "Ask",
            "orderType": "Limit" if order_type == OrderType.LIMIT else "Market",
            "quantity": str(amount),
            "clientId": order_id,
        }

        if order_type == OrderType.LIMIT:
            order_data["price"] = str(price)
            order_data["timeInForce"] = "GTC"

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.ORDER_URL, self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data=order_data,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.ORDER_URL,
        )

        exchange_order_id = response.get("id", "")
        transact_time = response.get("createdAt", 0)

        return exchange_order_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        """
        Cancel an order on Backpack.
        """
        symbol = self.trading_pair_to_exchange_symbol(tracked_order.trading_pair)

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_URL, self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.DELETE,
            params={
                "symbol": symbol,
                "orderId": tracked_order.exchange_order_id,
            },
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.CANCEL_ORDER_URL,
        )

        return response.get("status") == "Cancelled"

    async def _update_balances(self):
        """
        Update account balances.
        """
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.BALANCES_URL, self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.BALANCES_URL,
        )

        self._account_available_balances.clear()
        self._account_balances.clear()

        for asset, balance_data in response.items():
            total = Decimal(str(balance_data.get("total", 0)))
            available = Decimal(str(balance_data.get("available", 0)))

            self._account_balances[asset] = total
            self._account_available_balances[asset] = available

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Get all trade updates for an order.
        """
        trade_updates = []

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.FILLS_URL, self._domain)

        symbol = self.trading_pair_to_exchange_symbol(order.trading_pair)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            params={"symbol": symbol, "orderId": order.exchange_order_id},
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.FILLS_URL,
        )

        for fill in response:
            fee_asset = fill.get("feeSymbol", "USDC")
            fee_amount = Decimal(str(fill.get("fee", 0)))

            trade_updates.append(
                TradeUpdate(
                    trade_id=fill.get("tradeId", ""),
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=AddedToCostTradeFee(
                        flat_fees=[TokenAmount(token=fee_asset, amount=fee_amount)]
                    ),
                    fill_base_amount=Decimal(str(fill.get("quantity", 0))),
                    fill_quote_amount=Decimal(str(fill.get("quantity", 0))) * Decimal(str(fill.get("price", 0))),
                    fill_price=Decimal(str(fill.get("price", 0))),
                    fill_timestamp=fill.get("timestamp", 0),
                )
            )

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Request order status from Backpack.
        """
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.private_rest_url(CONSTANTS.ORDER_URL, self._domain)

        symbol = self.trading_pair_to_exchange_symbol(tracked_order.trading_pair)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            params={
                "symbol": symbol,
                "orderId": tracked_order.exchange_order_id,
            },
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.ORDER_URL,
        )

        new_state = CONSTANTS.ORDER_STATE.get(
            response.get("status", ""),
            tracked_order.current_state,
        )

        return OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=response.get("updatedAt", 0),
            new_state=new_state,
        )

    def exchange_symbol_to_trading_pair(self, symbol: str) -> str:
        """
        Convert exchange symbol to Hummingbot trading pair format.
        Backpack uses BTC_USDC format.
        """
        return symbol.replace("_", "-")

    def trading_pair_to_exchange_symbol(self, trading_pair: str) -> str:
        """
        Convert Hummingbot trading pair to exchange symbol format.
        """
        return trading_pair.replace("-", "_")

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """
        Get the last traded price for a trading pair.
        """
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        symbol = self.trading_pair_to_exchange_symbol(trading_pair)
        url = web_utils.public_rest_url(f"{CONSTANTS.TICKER_URL}?symbol={symbol}", self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.TICKER_URL,
        )

        return float(response.get("lastPrice", 0))
