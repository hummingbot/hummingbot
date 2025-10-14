"""
Order Data Source for Coins.xyz Exchange.

This module provides comprehensive order management including:
- Open orders endpoint with order status tracking
- Trade history endpoint with pagination support
- Order data structures and parsing utilities
- Order status mapping to Hummingbot standards
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils
from hummingbot.connector.exchange.coinsxyz import coinsxyz_web_utils as web_utils
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.logger import HummingbotLogger


@dataclass
class OrderData:
    """Order data structure for Coins.xyz orders."""
    client_order_id: str
    exchange_order_id: str
    trading_pair: str
    order_type: OrderType
    trade_type: TradeType
    amount: Decimal
    price: Decimal
    executed_amount: Decimal
    remaining_amount: Decimal
    status: str
    creation_timestamp: float
    update_timestamp: float
    fees: List[Dict[str, Any]]


@dataclass
class TradeData:
    """Trade data structure for Coins.xyz trades."""
    trade_id: str
    order_id: str
    client_order_id: str
    trading_pair: str
    trade_type: TradeType
    amount: Decimal
    price: Decimal
    fee_amount: Decimal
    fee_asset: str
    timestamp: float


class CoinsxyzOrderDataSource:
    """
    Order data source for Coins.xyz exchange.

    Provides comprehensive order management with:
    - Open orders retrieval with status tracking
    - Trade history with pagination support
    - Order data parsing and validation
    - Hummingbot format conversion
    - Order status mapping and tracking
    """

    def __init__(self,
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Initialize order data source.

        Args:
            api_factory: Web assistants factory for API requests
            domain: API domain (default or testnet)
        """
        self._api_factory = api_factory
        self._domain = domain
        self._logger = None

        # Order tracking
        self._tracked_orders: Dict[str, OrderData] = {}
        self._order_status_cache: Dict[str, str] = {}
        self._last_order_update = 0.0

        # Trade history tracking
        self._trade_history: List[TradeData] = []
        self._last_trade_timestamp = 0.0
        self._trade_pagination_cache: Dict[str, Any] = {}

        # Update locks
        self._orders_update_lock = asyncio.Lock()
        self._trades_update_lock = asyncio.Lock()

    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    async def get_open_orders(self,
                              trading_pair: Optional[str] = None,
                              force_update: bool = False) -> List[OrderData]:
        """
        Get open orders with status tracking.

        Args:
            trading_pair: Specific trading pair to filter (optional)
            force_update: Force refresh from API

        Returns:
            List of OrderData objects for open orders
        """
        async with self._orders_update_lock:
            try:
                # Fetch open orders from API
                orders_data = await self._fetch_open_orders(trading_pair)

                # Parse and update tracked orders
                open_orders = []
                for order_entry in orders_data:
                    order_data = self._parse_order_data(order_entry)
                    if order_data:
                        # Update tracked orders
                        self._tracked_orders[order_data.client_order_id] = order_data
                        self._order_status_cache[order_data.client_order_id] = order_data.status
                        open_orders.append(order_data)

                self._last_order_update = time.time()

                self.logger().info(f"Retrieved {len(open_orders)} open orders")
                return open_orders

            except Exception as e:
                self.logger().error(f"Error fetching open orders: {e}")
                return []

    async def get_order_status(self, client_order_id: str) -> Optional[str]:
        """
        Get order status for a specific order.

        Args:
            client_order_id: Client order ID

        Returns:
            Order status string or None if not found
        """
        try:
            # Check cache first
            if client_order_id in self._order_status_cache:
                return self._order_status_cache[client_order_id]

            # Fetch from API
            order_data = await self._fetch_order_status(client_order_id)
            if order_data:
                parsed_order = self._parse_order_data(order_data)
                if parsed_order:
                    self._order_status_cache[client_order_id] = parsed_order.status
                    return parsed_order.status

            return None

        except Exception as e:
            self.logger().error(f"Error fetching order status for {client_order_id}: {e}")
            return None

    async def get_trade_history(self,
                                trading_pair: Optional[str] = None,
                                start_time: Optional[int] = None,
                                end_time: Optional[int] = None,
                                limit: int = 100) -> List[TradeData]:
        """
        Get trade history with pagination support.

        Args:
            trading_pair: Specific trading pair to filter (optional)
            start_time: Start timestamp for filtering
            end_time: End timestamp for filtering
            limit: Maximum number of trades to return

        Returns:
            List of TradeData objects
        """
        async with self._trades_update_lock:
            try:
                # Fetch trade history from API
                trades_data = await self._fetch_trade_history(
                    trading_pair=trading_pair,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit
                )

                # Parse trade data
                trades = []
                for trade_entry in trades_data:
                    trade_data = self._parse_trade_data(trade_entry)
                    if trade_data:
                        trades.append(trade_data)

                # Update trade history cache
                if trades:
                    self._trade_history.extend(trades)
                    # Keep only recent trades in memory (last 1000)
                    self._trade_history = self._trade_history[-1000:]
                    self._last_trade_timestamp = max(trade.timestamp for trade in trades)

                self.logger().info(f"Retrieved {len(trades)} trade records")
                return trades

            except Exception as e:
                self.logger().error(f"Error fetching trade history: {e}")
                return []

    async def _fetch_open_orders(self, trading_pair: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch open orders from API.

        Args:
            trading_pair: Trading pair to filter

        Returns:
            Raw order data from API
        """
        rest_assistant = await self._api_factory.get_rest_assistant()

        params = {}
        if trading_pair:
            params["symbol"] = await utils.convert_to_exchange_trading_pair(trading_pair)

        url = web_utils.private_rest_url(CONSTANTS.OPEN_ORDERS_PATH_URL, domain=self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            params=params,
            throttler_limit_id=CONSTANTS.OPEN_ORDERS_PATH_URL,
        )

        # Handle different response formats
        if isinstance(response, list):
            return response
        elif "orders" in response:
            return response["orders"]
        elif "data" in response:
            return response["data"] if isinstance(response["data"], list) else [response["data"]]
        else:
            return [response] if response else []

    async def _fetch_order_status(self, client_order_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch order status from API.

        Args:
            client_order_id: Client order ID

        Returns:
            Raw order data from API
        """
        rest_assistant = await self._api_factory.get_rest_assistant()

        params = {"origClientOrderId": client_order_id}

        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            params=params,
            throttler_limit_id=CONSTANTS.ORDER_PATH_URL,
        )

        return response

    async def _fetch_trade_history(self,
                                   trading_pair: Optional[str] = None,
                                   start_time: Optional[int] = None,
                                   end_time: Optional[int] = None,
                                   limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch trade history from API.

        Args:
            trading_pair: Trading pair to filter
            start_time: Start timestamp
            end_time: End timestamp
            limit: Maximum number of trades

        Returns:
            Raw trade data from API
        """
        rest_assistant = await self._api_factory.get_rest_assistant()

        params = {"limit": limit}

        if trading_pair:
            params["symbol"] = await utils.convert_to_exchange_trading_pair(trading_pair)
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        url = web_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL, domain=self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            params=params,
            throttler_limit_id=CONSTANTS.MY_TRADES_PATH_URL,
        )

        # Handle different response formats
        if isinstance(response, list):
            return response
        elif "trades" in response:
            return response["trades"]
        elif "data" in response:
            return response["data"] if isinstance(response["data"], list) else [response["data"]]
        else:
            return [response] if response else []

    def _parse_order_data(self, order_entry: Dict[str, Any]) -> Optional[OrderData]:
        """
        Parse order data from API response.

        Args:
            order_entry: Raw order data from API

        Returns:
            OrderData object or None if parsing fails
        """
        try:
            # Extract order fields
            client_order_id = str(order_entry.get("clientOrderId", order_entry.get("origClientOrderId", "")))
            exchange_order_id = str(order_entry.get("orderId", ""))
            symbol = order_entry.get("symbol", "")

            # Convert symbol to trading pair
            trading_pair = utils.parse_exchange_trading_pair(symbol)

            # Parse order type and trade type
            order_type = self._parse_order_type(order_entry.get("type", "LIMIT"))
            trade_type = TradeType.BUY if order_entry.get("side", "").upper() == "BUY" else TradeType.SELL

            # Parse amounts and prices
            amount = Decimal(str(order_entry.get("origQty", "0")))
            price = Decimal(str(order_entry.get("price", "0")))
            executed_amount = Decimal(str(order_entry.get("executedQty", "0")))
            remaining_amount = amount - executed_amount

            # Parse timestamps
            creation_timestamp = float(order_entry.get("time", 0)) / 1000
            update_timestamp = float(order_entry.get("updateTime", order_entry.get("time", 0))) / 1000

            # Parse status
            status = order_entry.get("status", "UNKNOWN")

            # Parse fees
            fees = []
            if "fills" in order_entry:
                for fill in order_entry["fills"]:
                    fees.append({
                        "asset": fill.get("commissionAsset", ""),
                        "amount": Decimal(str(fill.get("commission", "0")))
                    })

            return OrderData(
                client_order_id=client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                price=price,
                executed_amount=executed_amount,
                remaining_amount=remaining_amount,
                status=status,
                creation_timestamp=creation_timestamp,
                update_timestamp=update_timestamp,
                fees=fees
            )

        except Exception as e:
            self.logger().warning(f"Error parsing order data {order_entry}: {e}")
            return None

    def _parse_trade_data(self, trade_entry: Dict[str, Any]) -> Optional[TradeData]:
        """
        Parse trade data from API response.

        Args:
            trade_entry: Raw trade data from API

        Returns:
            TradeData object or None if parsing fails
        """
        try:
            # Extract trade fields
            trade_id = str(trade_entry.get("id", trade_entry.get("tradeId", "")))
            order_id = str(trade_entry.get("orderId", ""))
            client_order_id = str(trade_entry.get("clientOrderId", ""))
            symbol = trade_entry.get("symbol", "")

            # Convert symbol to trading pair
            trading_pair = utils.parse_exchange_trading_pair(symbol)

            # Parse trade type
            trade_type = TradeType.BUY if trade_entry.get("isBuyer", True) else TradeType.SELL

            # Parse amounts and prices
            amount = Decimal(str(trade_entry.get("qty", "0")))
            price = Decimal(str(trade_entry.get("price", "0")))

            # Parse fees
            fee_amount = Decimal(str(trade_entry.get("commission", "0")))
            fee_asset = trade_entry.get("commissionAsset", "")

            # Parse timestamp
            timestamp = float(trade_entry.get("time", 0)) / 1000

            return TradeData(
                trade_id=trade_id,
                order_id=order_id,
                client_order_id=client_order_id,
                trading_pair=trading_pair,
                trade_type=trade_type,
                amount=amount,
                price=price,
                fee_amount=fee_amount,
                fee_asset=fee_asset,
                timestamp=timestamp
            )

        except Exception as e:
            self.logger().warning(f"Error parsing trade data {trade_entry}: {e}")
            return None

    def _parse_order_type(self, order_type_str: str) -> OrderType:
        """
        Parse order type from string.

        Args:
            order_type_str: Order type string from API

        Returns:
            OrderType enum value
        """
        order_type_map = {
            "LIMIT": OrderType.LIMIT,
            "MARKET": OrderType.MARKET,
            "STOP_LOSS": OrderType.LIMIT,
            "STOP_LOSS_LIMIT": OrderType.LIMIT,
            "TAKE_PROFIT": OrderType.LIMIT,
            "TAKE_PROFIT_LIMIT": OrderType.LIMIT,
            "LIMIT_MAKER": OrderType.LIMIT_MAKER
        }

        return order_type_map.get(order_type_str.upper(), OrderType.LIMIT)

    def map_order_status_to_hummingbot(self, exchange_status: str) -> OrderState:
        """
        Map exchange order status to Hummingbot OrderState.

        Args:
            exchange_status: Order status from exchange

        Returns:
            Hummingbot OrderState
        """
        return CONSTANTS.ORDER_STATE.get(exchange_status.upper(), OrderState.OPEN)

    def create_order_update(self, order_data: OrderData) -> OrderUpdate:
        """
        Create OrderUpdate from OrderData.

        Args:
            order_data: OrderData object

        Returns:
            OrderUpdate object for Hummingbot
        """
        return OrderUpdate(
            trading_pair=order_data.trading_pair,
            update_timestamp=order_data.update_timestamp,
            new_state=self.map_order_status_to_hummingbot(order_data.status),
            client_order_id=order_data.client_order_id,
            exchange_order_id=order_data.exchange_order_id
        )

    def create_trade_update(self, trade_data: TradeData) -> TradeUpdate:
        """
        Create TradeUpdate from TradeData.

        Args:
            trade_data: TradeData object

        Returns:
            TradeUpdate object for Hummingbot
        """
        return TradeUpdate(
            trade_id=trade_data.trade_id,
            client_order_id=trade_data.client_order_id,
            exchange_order_id=trade_data.order_id,
            trading_pair=trade_data.trading_pair,
            fill_timestamp=trade_data.timestamp,
            fill_price=trade_data.price,
            fill_base_amount=trade_data.amount,
            fill_quote_amount=trade_data.amount * trade_data.price,
            fee=trade_data.fee_amount,
            fee_asset=trade_data.fee_asset
        )

    def get_tracked_orders(self) -> Dict[str, OrderData]:
        """Get all tracked orders."""
        return self._tracked_orders.copy()

    def clear_order_cache(self):
        """Clear order tracking cache."""
        self._tracked_orders.clear()
        self._order_status_cache.clear()
        self._last_order_update = 0.0

        self.logger().info("Order cache cleared")

    def clear_trade_cache(self):
        """Clear trade history cache."""
        self._trade_history.clear()
        self._last_trade_timestamp = 0.0
        self._trade_pagination_cache.clear()

        self.logger().info("Trade cache cleared")
