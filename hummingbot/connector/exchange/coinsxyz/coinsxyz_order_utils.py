"""
Order Parsing Utilities for Coins.xyz Exchange.

This module provides comprehensive order parsing and conversion utilities
for seamless integration with Hummingbot's order management system.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS, coinsxyz_utils as utils
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.logger import HummingbotLogger


class CoinsxyzOrderUtils:
    """
    Order parsing and conversion utilities for Coins.xyz exchange.

    Provides comprehensive utilities for:
    - Order data parsing from various API response formats
    - Conversion to Hummingbot standard format
    - Order status mapping and validation
    - Trade data parsing and conversion
    - Order and trade data validation
    """

    def __init__(self):
        """Initialize order utilities."""
        self._logger = None

    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    def parse_order_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse order response from Coins.xyz API into standardized format.

        Args:
            response_data: Raw order response from API

        Returns:
            Standardized order dictionary (single order) or dict with orders list
        """
        try:
            # Handle different response formats
            if "orders" in response_data:
                orders = response_data["orders"]
                is_list_response = True
            elif isinstance(response_data, list):
                orders = response_data
                is_list_response = True
            else:
                # Single order response
                parsed_order = self._parse_single_order(response_data)
                return parsed_order if parsed_order else {}

            # Multiple orders response
            parsed_orders = []
            for order_data in orders:
                parsed_order = self._parse_single_order(order_data)
                if parsed_order:
                    parsed_orders.append(parsed_order)

            return {"orders": parsed_orders}

        except Exception as e:
            self.logger().error(f"Error parsing order response: {e}")
            return {"orders": []}

    def _parse_single_order(self, order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a single order entry.

        Args:
            order_data: Single order entry from API

        Returns:
            Standardized order dictionary or None if parsing fails
        """
        try:
            # Extract basic order information
            client_order_id = str(order_data.get("clientOrderId", order_data.get("origClientOrderId", "")))
            exchange_order_id = str(order_data.get("orderId", ""))
            symbol = order_data.get("symbol", "")

            # Convert symbol to trading pair
            trading_pair = utils.parse_exchange_trading_pair(symbol)

            # Parse order type and side
            order_type = self._parse_order_type(order_data.get("type", "LIMIT"))
            trade_type = self._parse_trade_type(order_data.get("side", "BUY"))

            # Parse quantities and prices
            original_amount = Decimal(str(order_data.get("origQty", "0")))
            executed_amount = Decimal(str(order_data.get("executedQty", "0")))
            remaining_amount = original_amount - executed_amount

            price = Decimal(str(order_data.get("price", "0")))
            stop_price = Decimal(str(order_data.get("stopPrice", "0")))

            # Parse timestamps
            creation_time = self._parse_timestamp(order_data.get("time", 0))
            update_time = self._parse_timestamp(order_data.get("updateTime", order_data.get("time", 0)))

            # Parse order status
            status = order_data.get("status", "UNKNOWN").upper()
            hummingbot_status = self._map_order_status(status)

            # Parse time in force
            time_in_force = order_data.get("timeInForce", "GTC")

            # Parse fees
            fees = self._parse_order_fees(order_data)

            return {
                "client_order_id": client_order_id,
                "exchange_order_id": exchange_order_id,
                "trading_pair": trading_pair,
                "symbol": symbol,
                "order_type": order_type,
                "trade_type": trade_type,
                "original_amount": original_amount,
                "executed_amount": executed_amount,
                "remaining_amount": remaining_amount,
                "price": price,
                "stop_price": stop_price,
                "status": status,
                "hummingbot_status": hummingbot_status,
                "time_in_force": time_in_force,
                "creation_timestamp": creation_time,
                "update_timestamp": update_time,
                "fees": fees
            }

        except Exception as e:
            self.logger().warning(f"Error parsing order data {order_data}: {e}")
            return None

    def parse_trade_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse trade response from Coins.xyz API into standardized format.

        Args:
            response_data: Raw trade response from API

        Returns:
            Standardized trade dictionary
        """
        try:
            # Handle different response formats
            if "trades" in response_data:
                trades = response_data["trades"]
            elif isinstance(response_data, list):
                trades = response_data
            else:
                trades = [response_data]

            parsed_trades = []
            for trade_data in trades:
                parsed_trade = self._parse_single_trade(trade_data)
                if parsed_trade:
                    parsed_trades.append(parsed_trade)

            return {"trades": parsed_trades}

        except Exception as e:
            self.logger().error(f"Error parsing trade response: {e}")
            return {"trades": []}

    def _parse_single_trade(self, trade_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a single trade entry.

        Args:
            trade_data: Single trade entry from API

        Returns:
            Standardized trade dictionary or None if parsing fails
        """
        try:
            # Extract basic trade information
            trade_id = str(trade_data.get("id", trade_data.get("tradeId", "")))
            order_id = str(trade_data.get("orderId", ""))
            client_order_id = str(trade_data.get("clientOrderId", ""))
            symbol = trade_data.get("symbol", "")

            # Convert symbol to trading pair
            trading_pair = utils.parse_exchange_trading_pair(symbol)

            # Parse trade side
            is_buyer = trade_data.get("isBuyer", True)
            trade_type = TradeType.BUY if is_buyer else TradeType.SELL

            # Parse quantities and prices
            quantity = Decimal(str(trade_data.get("qty", "0")))
            price = Decimal(str(trade_data.get("price", "0")))
            quote_quantity = quantity * price

            # Parse fees
            commission = Decimal(str(trade_data.get("commission", "0")))
            commission_asset = trade_data.get("commissionAsset", "")

            # Parse timestamp
            timestamp = self._parse_timestamp(trade_data.get("time", 0))

            return {
                "trade_id": trade_id,
                "order_id": order_id,
                "client_order_id": client_order_id,
                "trading_pair": trading_pair,
                "symbol": symbol,
                "trade_type": trade_type,
                "is_buyer": is_buyer,
                "quantity": quantity,
                "price": price,
                "quote_quantity": quote_quantity,
                "commission": commission,
                "commission_asset": commission_asset,
                "timestamp": timestamp
            }

        except Exception as e:
            self.logger().warning(f"Error parsing trade data {trade_data}: {e}")
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

    def _parse_trade_type(self, side_str: str) -> TradeType:
        """
        Parse trade type from side string.

        Args:
            side_str: Side string from API (BUY/SELL)

        Returns:
            TradeType enum value
        """
        return TradeType.BUY if side_str.upper() == "BUY" else TradeType.SELL

    def _parse_timestamp(self, timestamp_value: Union[int, float, str]) -> float:
        """
        Parse timestamp from various formats.

        Args:
            timestamp_value: Timestamp in various formats

        Returns:
            Timestamp as float (seconds since epoch)
        """
        try:
            if isinstance(timestamp_value, str):
                # Try to parse as ISO format first
                try:
                    dt = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
                    return dt.timestamp()
                except ValueError:
                    # Fall back to numeric parsing
                    timestamp_value = float(timestamp_value)

            timestamp_float = float(timestamp_value)

            # Convert milliseconds to seconds if needed
            if timestamp_float > 1e10:  # Likely milliseconds
                timestamp_float /= 1000

            return timestamp_float

        except (ValueError, TypeError):
            return 0.0

    def _map_order_status(self, exchange_status: str) -> OrderState:
        """
        Map exchange order status to Hummingbot OrderState.

        Args:
            exchange_status: Order status from exchange

        Returns:
            Hummingbot OrderState
        """
        return CONSTANTS.ORDER_STATE.get(exchange_status.upper(), OrderState.OPEN)

    def _parse_order_fees(self, order_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse order fees from order data.

        Args:
            order_data: Order data from API

        Returns:
            List of fee dictionaries
        """
        fees = []

        try:
            # Check for fills array (common in order responses)
            if "fills" in order_data and isinstance(order_data["fills"], list):
                for fill in order_data["fills"]:
                    commission = Decimal(str(fill.get("commission", "0")))
                    commission_asset = fill.get("commissionAsset", "")

                    if commission > 0:
                        fees.append({
                            "asset": commission_asset,
                            "amount": commission
                        })

            # Check for direct commission fields
            elif "commission" in order_data:
                commission = Decimal(str(order_data.get("commission", "0")))
                commission_asset = order_data.get("commissionAsset", "")

                if commission > 0:
                    fees.append({
                        "asset": commission_asset,
                        "amount": commission
                    })

        except Exception as e:
            self.logger().warning(f"Error parsing order fees: {e}")

        return fees

    def create_order_update(self, order_data: Dict[str, Any]) -> OrderUpdate:
        """
        Create OrderUpdate from parsed order data.

        Args:
            order_data: Parsed order data

        Returns:
            OrderUpdate object for Hummingbot
        """
        return OrderUpdate(
            trading_pair=order_data["trading_pair"],
            update_timestamp=order_data["update_timestamp"],
            new_state=order_data["hummingbot_status"],
            client_order_id=order_data["client_order_id"],
            exchange_order_id=order_data["exchange_order_id"]
        )

    def create_trade_update(self, trade_data: Dict[str, Any]) -> TradeUpdate:
        """
        Create TradeUpdate from parsed trade data.

        Args:
            trade_data: Parsed trade data

        Returns:
            TradeUpdate object for Hummingbot
        """
        return TradeUpdate(
            trade_id=trade_data["trade_id"],
            client_order_id=trade_data["client_order_id"],
            exchange_order_id=trade_data["order_id"],
            trading_pair=trade_data["trading_pair"],
            fill_timestamp=trade_data["timestamp"],
            fill_price=trade_data["price"],
            fill_base_amount=trade_data["quantity"],
            fill_quote_amount=trade_data["quote_quantity"],
            fee=trade_data["commission"],
            fee_asset=trade_data["commission_asset"]
        )

    def validate_order_data(self, order_data: Dict[str, Any]) -> List[str]:
        """
        Validate order data and return list of issues.

        Args:
            order_data: Order data to validate

        Returns:
            List of validation error messages
        """
        issues = []

        try:
            # Check required fields
            required_fields = ["client_order_id", "exchange_order_id", "trading_pair", "status"]
            for field in required_fields:
                if not order_data.get(field):
                    issues.append(f"Missing required field: {field}")

            # Check numeric fields
            numeric_fields = ["original_amount", "executed_amount", "price"]
            for field in numeric_fields:
                value = order_data.get(field)
                if value is not None:
                    try:
                        if Decimal(str(value)) < 0:
                            issues.append(f"Negative value for {field}: {value}")
                    except (ValueError, TypeError):
                        issues.append(f"Invalid numeric value for {field}: {value}")

            # Check timestamp fields
            timestamp_fields = ["creation_timestamp", "update_timestamp"]
            for field in timestamp_fields:
                value = order_data.get(field)
                if value is not None and (not isinstance(value, (int, float)) or value <= 0):
                    issues.append(f"Invalid timestamp for {field}: {value}")

            # Check order consistency
            original_amount = order_data.get("original_amount", Decimal("0"))
            executed_amount = order_data.get("executed_amount", Decimal("0"))
            remaining_amount = order_data.get("remaining_amount", Decimal("0"))

            if isinstance(original_amount, Decimal) and isinstance(executed_amount, Decimal):
                expected_remaining = original_amount - executed_amount
                if isinstance(remaining_amount, Decimal) and abs(remaining_amount - expected_remaining) > Decimal("0.00000001"):
                    issues.append(f"Inconsistent amounts: original={original_amount}, executed={executed_amount}, remaining={remaining_amount}")

        except Exception as e:
            issues.append(f"Error validating order data: {e}")

        return issues

    def validate_trade_data(self, trade_data: Dict[str, Any]) -> List[str]:
        """
        Validate trade data and return list of issues.

        Args:
            trade_data: Trade data to validate

        Returns:
            List of validation error messages
        """
        issues = []

        try:
            # Check required fields
            required_fields = ["trade_id", "trading_pair", "quantity", "price"]
            for field in required_fields:
                if not trade_data.get(field):
                    issues.append(f"Missing required field: {field}")

            # Check numeric fields
            numeric_fields = ["quantity", "price", "quote_quantity", "commission"]
            for field in numeric_fields:
                value = trade_data.get(field)
                if value is not None:
                    try:
                        if Decimal(str(value)) < 0:
                            issues.append(f"Negative value for {field}: {value}")
                    except (ValueError, TypeError):
                        issues.append(f"Invalid numeric value for {field}: {value}")

            # Check timestamp
            timestamp = trade_data.get("timestamp")
            if timestamp is not None and (not isinstance(timestamp, (int, float)) or timestamp <= 0):
                issues.append(f"Invalid timestamp: {timestamp}")

            # Check quote quantity consistency
            quantity = trade_data.get("quantity")
            price = trade_data.get("price")
            quote_quantity = trade_data.get("quote_quantity")

            if all(isinstance(x, Decimal) for x in [quantity, price, quote_quantity]):
                expected_quote = quantity * price
                if abs(quote_quantity - expected_quote) > Decimal("0.00000001"):
                    issues.append(f"Inconsistent quote quantity: expected={expected_quote}, actual={quote_quantity}")

        except Exception as e:
            issues.append(f"Error validating trade data: {e}")

        return issues

    def format_order_for_display(self, order_data: Dict[str, Any]) -> str:
        """
        Format order data for display purposes.

        Args:
            order_data: Order data dictionary

        Returns:
            Formatted order string
        """
        try:
            return (
                f"Order {order_data.get('client_order_id', 'N/A')}: "
                f"{order_data.get('trade_type', 'N/A')} "
                f"{order_data.get('original_amount', 'N/A')} "
                f"{order_data.get('trading_pair', 'N/A')} "
                f"@ {order_data.get('price', 'N/A')} "
                f"[{order_data.get('status', 'N/A')}]"
            )
        except Exception:
            return f"Order {order_data.get('client_order_id', 'N/A')}"

    def format_trade_for_display(self, trade_data: Dict[str, Any]) -> str:
        """
        Format trade data for display purposes.

        Args:
            trade_data: Trade data dictionary

        Returns:
            Formatted trade string
        """
        try:
            return (
                f"Trade {trade_data.get('trade_id', 'N/A')}: "
                f"{trade_data.get('trade_type', 'N/A')} "
                f"{trade_data.get('quantity', 'N/A')} "
                f"{trade_data.get('trading_pair', 'N/A')} "
                f"@ {trade_data.get('price', 'N/A')}"
            )
        except Exception:
            return f"Trade {trade_data.get('trade_id', 'N/A')}"

    def apply_trading_rules(self,
                           amount: Decimal,
                           price: Decimal,
                           trading_rule) -> Dict[str, Decimal]:
        """
        Apply trading rules to adjust amount and price.

        Args:
            amount: Order amount
            price: Order price
            trading_rule: Trading rule object

        Returns:
            Dictionary with adjusted amount and price
        """
        adjusted_amount = amount
        adjusted_price = price

        # Adjust amount precision
        if hasattr(trading_rule, 'min_base_amount_increment'):
            increment = trading_rule.min_base_amount_increment
            if increment > 0:
                adjusted_amount = (amount / increment).quantize(Decimal("1")) * increment

        # Adjust price precision
        if hasattr(trading_rule, 'min_price_increment'):
            increment = trading_rule.min_price_increment
            if increment > 0:
                adjusted_price = (price / increment).quantize(Decimal("1")) * increment

        return {
            "amount": adjusted_amount,
            "price": adjusted_price
        }

    def build_order_params(self,
                          trading_pair: str,
                          order_type: OrderType,
                          trade_type: TradeType,
                          amount: Decimal,
                          client_order_id: str,
                          price: Optional[Decimal] = None) -> Dict[str, Any]:
        """
        Build order parameters for API submission.

        Args:
            trading_pair: Trading pair
            order_type: Order type
            trade_type: Trade type
            amount: Order amount
            client_order_id: Client order ID
            price: Order price (for limit orders)

        Returns:
            Dictionary with order parameters
        """
        symbol = utils.convert_to_exchange_trading_pair(trading_pair)

        params = {
            "symbol": symbol,
            "side": "BUY" if trade_type == TradeType.BUY else "SELL",
            "type": "LIMIT" if order_type == OrderType.LIMIT else "MARKET",
            "quantity": str(amount),
            "newClientOrderId": client_order_id,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }

        if order_type == OrderType.LIMIT and price is not None:
            params["price"] = str(price)
            params["timeInForce"] = "GTC"

        return params

    def build_cancel_params(self,
                           trading_pair: str,
                           client_order_id: Optional[str] = None,
                           exchange_order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build cancel order parameters.

        Args:
            trading_pair: Trading pair
            client_order_id: Client order ID
            exchange_order_id: Exchange order ID

        Returns:
            Dictionary with cancel parameters
        """
        symbol = utils.convert_to_exchange_trading_pair(trading_pair)

        params = {
            "symbol": symbol,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }

        if exchange_order_id:
            params["orderId"] = exchange_order_id
        elif client_order_id:
            params["origClientOrderId"] = client_order_id

        return params

    def build_order_status_params(self,
                                  trading_pair: str,
                                  client_order_id: Optional[str] = None,
                                  exchange_order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build order status query parameters.

        Args:
            trading_pair: Trading pair
            client_order_id: Client order ID
            exchange_order_id: Exchange order ID

        Returns:
            Dictionary with status query parameters
        """
        symbol = utils.convert_to_exchange_trading_pair(trading_pair)

        params = {
            "symbol": symbol,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }

        if exchange_order_id:
            params["orderId"] = exchange_order_id
        elif client_order_id:
            params["origClientOrderId"] = client_order_id

        return params

    def calculate_order_value(self, amount: Decimal, price: Decimal) -> Decimal:
        """
        Calculate order value (notional).

        Args:
            amount: Order amount
            price: Order price

        Returns:
            Order value
        """
        return amount * price

    def format_order_side(self, trade_type: TradeType) -> str:
        """
        Format order side for API.

        Args:
            trade_type: Trade type

        Returns:
            Order side string
        """
        return "BUY" if trade_type == TradeType.BUY else "SELL"

    def format_order_type(self, order_type: OrderType) -> str:
        """
        Format order type for API.

        Args:
            order_type: Order type

        Returns:
            Order type string
        """
        type_map = {
            OrderType.LIMIT: "LIMIT",
            OrderType.MARKET: "MARKET",
            OrderType.LIMIT_MAKER: "LIMIT_MAKER"
        }
        return type_map.get(order_type, "LIMIT")

    def validate_order_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate order parameters.

        Args:
            params: Order parameters

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["symbol", "side", "type", "quantity"]

        for field in required_fields:
            if field not in params or not params[field]:
                return False

        # Validate quantity
        try:
            quantity = Decimal(str(params["quantity"]))
            if quantity <= 0:
                return False
        except (ValueError, TypeError):
            return False

        # Validate price for limit orders
        if params.get("type") == "LIMIT":
            if "price" not in params:
                return False
            try:
                price = Decimal(str(params["price"]))
                if price <= 0:
                    return False
            except (ValueError, TypeError):
                return False

        return True

    def apply_trading_rules(self,
                           amount: Decimal,
                           price: Decimal,
                           trading_rule) -> Dict[str, Decimal]:
        """
        Apply trading rules to adjust order parameters.

        Args:
            amount: Order amount
            price: Order price
            trading_rule: TradingRule object

        Returns:
            Dictionary with adjusted amount and price
        """
        adjusted_amount = amount
        adjusted_price = price

        # Check minimum order size first
        if hasattr(trading_rule, 'min_order_size'):
            min_size = trading_rule.min_order_size
            if min_size > 0 and adjusted_amount < min_size:
                adjusted_amount = min_size

        # Adjust amount to meet increment requirements
        if hasattr(trading_rule, 'min_base_amount_increment'):
            increment = trading_rule.min_base_amount_increment
            if increment > 0:
                adjusted_amount = (adjusted_amount / increment).quantize(Decimal("1")) * increment

        # Adjust price to meet increment requirements
        if hasattr(trading_rule, 'min_price_increment'):
            increment = trading_rule.min_price_increment
            if increment > 0:
                adjusted_price = (price / increment).quantize(Decimal("1")) * increment

        return {
            "amount": adjusted_amount,
            "price": adjusted_price
        }

    def build_order_params(self,
                          trading_pair: str,
                          order_type: OrderType,
                          trade_type: TradeType,
                          amount: Decimal,
                          price: Optional[Decimal] = None,
                          client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build order parameters for API submission.

        Args:
            trading_pair: Trading pair
            order_type: Order type
            trade_type: Trade type
            amount: Order amount
            price: Order price (required for LIMIT orders)
            client_order_id: Client order ID

        Returns:
            Dictionary with order parameters
        """
        symbol = utils.convert_to_exchange_trading_pair(trading_pair)
        
        params = {
            "symbol": symbol,
            "side": "BUY" if trade_type == TradeType.BUY else "SELL",
            "type": self.format_order_type(order_type),
            "quantity": str(amount),
            "timestamp": int(datetime.now().timestamp() * 1000)
        }

        if client_order_id:
            params["newClientOrderId"] = client_order_id

        if order_type == OrderType.LIMIT and price is not None:
            params["price"] = str(price)
            params["timeInForce"] = "GTC"

        return params

    def build_cancel_params(self,
                           trading_pair: str,
                           client_order_id: Optional[str] = None,
                           exchange_order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build order cancellation parameters.

        Args:
            trading_pair: Trading pair
            client_order_id: Client order ID
            exchange_order_id: Exchange order ID

        Returns:
            Dictionary with cancellation parameters
        """
        symbol = utils.convert_to_exchange_trading_pair(trading_pair)
        
        params = {
            "symbol": symbol,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }

        if exchange_order_id:
            params["orderId"] = exchange_order_id
        elif client_order_id:
            params["origClientOrderId"] = client_order_id

        return params

    def build_order_status_params(self,
                                  trading_pair: str,
                                  client_order_id: Optional[str] = None,
                                  exchange_order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build order status query parameters.

        Args:
            trading_pair: Trading pair
            client_order_id: Client order ID
            exchange_order_id: Exchange order ID

        Returns:
            Dictionary with status query parameters
        """
        symbol = utils.convert_to_exchange_trading_pair(trading_pair)
        
        params = {
            "symbol": symbol,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }

        if exchange_order_id:
            params["orderId"] = exchange_order_id
        elif client_order_id:
            params["origClientOrderId"] = client_order_id

        return params

    def calculate_order_value(self, amount: Decimal, price: Decimal) -> Decimal:
        """
        Calculate order notional value.

        Args:
            amount: Order amount
            price: Order price

        Returns:
            Order value (amount * price)
        """
        return amount * price

    def format_order_side(self, trade_type: TradeType) -> str:
        """
        Format trade type to exchange order side.

        Args:
            trade_type: TradeType enum

        Returns:
            Order side string ("BUY" or "SELL")
        """
        return "BUY" if trade_type == TradeType.BUY else "SELL"

    def format_order_type(self, order_type: OrderType) -> str:
        """
        Format order type to exchange format.

        Args:
            order_type: OrderType enum

        Returns:
            Order type string
        """
        order_type_map = {
            OrderType.LIMIT: "LIMIT",
            OrderType.MARKET: "MARKET",
            OrderType.LIMIT_MAKER: "LIMIT_MAKER"
        }
        return order_type_map.get(order_type, "LIMIT")

    def validate_order_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate order parameters.

        Args:
            params: Order parameters dictionary

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["symbol", "side", "type", "quantity"]
        
        # Check required fields
        for field in required_fields:
            if field not in params or not params[field]:
                return False

        # Validate quantity
        try:
            quantity = Decimal(str(params["quantity"]))
            if quantity <= 0:
                return False
        except (ValueError, TypeError):
            return False

        # Validate price for LIMIT orders
        if params.get("type") == "LIMIT":
            if "price" not in params:
                return False
            try:
                price = Decimal(str(params["price"]))
                if price <= 0:
                    return False
            except (ValueError, TypeError):
                return False

        return True
