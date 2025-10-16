"""
Order Lifecycle Management for Coins.xyz Exchange.

This module provides comprehensive order lifecycle management including:
- Order cancellation with proper error handling
- Order query/status endpoint integration
- Order modification capabilities
- Bulk order operations for efficiency
- Complete order lifecycle management
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils
from hummingbot.connector.exchange.coinsxyz import coinsxyz_web_utils as web_utils
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.logger import HummingbotLogger


class OrderOperation(Enum):
    """Order operation types."""
    CANCEL = "CANCEL"
    MODIFY = "MODIFY"
    QUERY = "QUERY"


@dataclass
class OrderCancellationRequest:
    """Order cancellation request data structure."""
    client_order_id: str
    exchange_order_id: Optional[str] = None
    trading_pair: Optional[str] = None
    reason: str = "USER_REQUESTED"


@dataclass
class OrderCancellationResponse:
    """Order cancellation response data structure."""
    success: bool
    client_order_id: str
    exchange_order_id: Optional[str] = None
    status: Optional[str] = None
    timestamp: Optional[float] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class OrderModificationRequest:
    """Order modification request data structure."""
    client_order_id: str
    exchange_order_id: str
    new_amount: Optional[Decimal] = None
    new_price: Optional[Decimal] = None
    modification_type: str = "AMOUNT_PRICE"


@dataclass
class BulkOperationResult:
    """Bulk operation result data structure."""
    operation_type: OrderOperation
    total_orders: int
    successful_orders: int
    failed_orders: int
    results: List[Dict[str, Any]]
    execution_time: float


class CoinsxyzOrderLifecycle:
    """
    Order lifecycle management for Coins.xyz exchange.

    Provides comprehensive order lifecycle management with:
    - Order cancellation with error handling
    - Order status queries and monitoring
    - Order modification capabilities
    - Bulk operations for efficiency
    - Complete lifecycle tracking
    """

    def __init__(self,
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Initialize order lifecycle management.

        Args:
            api_factory: Web assistants factory for API requests
            domain: API domain (default or testnet)
        """
        self._api_factory = api_factory
        self._domain = domain
        self._logger = None

        # Order lifecycle tracking
        self._active_operations: Dict[str, OrderOperation] = {}
        self._cancellation_history: List[OrderCancellationResponse] = []
        self._modification_history: List[Dict[str, Any]] = []

        # Operation locks
        self._cancellation_lock = asyncio.Lock()
        self._modification_lock = asyncio.Lock()
        self._bulk_operation_lock = asyncio.Lock()

    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    async def cancel_order(self,
                           client_order_id: str,
                           exchange_order_id: Optional[str] = None,
                           trading_pair: Optional[str] = None) -> OrderCancellationResponse:
        """
        Cancel a single order with proper error handling.

        Args:
            client_order_id: Client order ID
            exchange_order_id: Exchange order ID (optional)
            trading_pair: Trading pair (optional)

        Returns:
            OrderCancellationResponse with cancellation result
        """
        async with self._cancellation_lock:
            try:
                # Track operation
                self._active_operations[client_order_id] = OrderOperation.CANCEL

                # Create cancellation request
                cancel_request = OrderCancellationRequest(
                    client_order_id=client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=trading_pair
                )

                # Execute cancellation
                response = await self._execute_order_cancellation(cancel_request)

                # Update history
                self._cancellation_history.append(response)

                # Clean up tracking
                self._active_operations.pop(client_order_id, None)

                self.logger().info(
                    f"Order cancellation {'successful' if response.success else 'failed'}: "
                    f"{client_order_id} -> {response.error_message or 'SUCCESS'}"
                )

                return response

            except Exception as e:
                # Clean up on error
                self._active_operations.pop(client_order_id, None)

                self.logger().error(f"Error cancelling order {client_order_id}: {e}")
                return OrderCancellationResponse(
                    success=False,
                    client_order_id=client_order_id,
                    error_message=str(e)
                )

    async def cancel_all_orders(self,
                                trading_pair: Optional[str] = None,
                                timeout_seconds: float = 30.0) -> BulkOperationResult:
        """
        Cancel all orders with bulk operation efficiency.

        Args:
            trading_pair: Specific trading pair to cancel (optional)
            timeout_seconds: Maximum time to wait for cancellations

        Returns:
            BulkOperationResult with cancellation results
        """
        async with self._bulk_operation_lock:
            start_time = time.time()

            try:
                # Get orders to cancel
                orders_to_cancel = await self._get_orders_for_cancellation(trading_pair)

                if not orders_to_cancel:
                    return BulkOperationResult(
                        operation_type=OrderOperation.CANCEL,
                        total_orders=0,
                        successful_orders=0,
                        failed_orders=0,
                        results=[],
                        execution_time=time.time() - start_time
                    )

                # Execute bulk cancellation
                cancellation_tasks = [
                    self.cancel_order(
                        client_order_id=order["client_order_id"],
                        exchange_order_id=order.get("exchange_order_id"),
                        trading_pair=order.get("trading_pair")
                    )
                    for order in orders_to_cancel
                ]

                # Wait for all cancellations with timeout
                try:
                    results = await asyncio.wait_for(
                        asyncio.gather(*cancellation_tasks, return_exceptions=True),
                        timeout=timeout_seconds
                    )
                except asyncio.TimeoutError:
                    self.logger().warning(f"Bulk cancellation timeout after {timeout_seconds}s")
                    results = [OrderCancellationResponse(
                        success=False,
                        client_order_id="TIMEOUT",
                        error_message="Bulk cancellation timeout"
                    )] * len(cancellation_tasks)

                # Process results
                successful_count = sum(1 for r in results if isinstance(r, OrderCancellationResponse) and r.success)
                failed_count = len(results) - successful_count

                return BulkOperationResult(
                    operation_type=OrderOperation.CANCEL,
                    total_orders=len(orders_to_cancel),
                    successful_orders=successful_count,
                    failed_orders=failed_count,
                    results=[r.__dict__ if isinstance(r, OrderCancellationResponse) else {"error": str(r)} for r in results],
                    execution_time=time.time() - start_time
                )

            except Exception as e:
                self.logger().error(f"Error in bulk cancellation: {e}")
                return BulkOperationResult(
                    operation_type=OrderOperation.CANCEL,
                    total_orders=0,
                    successful_orders=0,
                    failed_orders=1,
                    results=[{"error": str(e)}],
                    execution_time=time.time() - start_time
                )

    async def query_order_status(self,
                                 client_order_id: str,
                                 exchange_order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Query order status with endpoint integration.

        Args:
            client_order_id: Client order ID
            exchange_order_id: Exchange order ID (optional)

        Returns:
            Dictionary with order status information
        """
        try:
            # Track operation
            self._active_operations[client_order_id] = OrderOperation.QUERY

            # Query order status
            status_data = await self._fetch_order_status(client_order_id, exchange_order_id)

            # Clean up tracking
            self._active_operations.pop(client_order_id, None)

            return status_data

        except Exception as e:
            # Clean up on error
            self._active_operations.pop(client_order_id, None)

            self.logger().error(f"Error querying order status {client_order_id}: {e}")
            return {
                "success": False,
                "client_order_id": client_order_id,
                "error_message": str(e)
            }

    async def modify_order(self,
                           client_order_id: str,
                           exchange_order_id: str,
                           new_amount: Optional[Decimal] = None,
                           new_price: Optional[Decimal] = None) -> Dict[str, Any]:
        """
        Modify order if supported by exchange.

        Args:
            client_order_id: Client order ID
            exchange_order_id: Exchange order ID
            new_amount: New order amount (optional)
            new_price: New order price (optional)

        Returns:
            Dictionary with modification result
        """
        async with self._modification_lock:
            try:
                # Track operation
                self._active_operations[client_order_id] = OrderOperation.MODIFY

                # Create modification request
                modify_request = OrderModificationRequest(
                    client_order_id=client_order_id,
                    exchange_order_id=exchange_order_id,
                    new_amount=new_amount,
                    new_price=new_price
                )

                # Execute modification (if supported)
                result = await self._execute_order_modification(modify_request)

                # Update history
                self._modification_history.append(result)

                # Clean up tracking
                self._active_operations.pop(client_order_id, None)

                return result

            except Exception as e:
                # Clean up on error
                self._active_operations.pop(client_order_id, None)

                self.logger().error(f"Error modifying order {client_order_id}: {e}")
                return {
                    "success": False,
                    "client_order_id": client_order_id,
                    "error_message": str(e)
                }

    async def _execute_order_cancellation(self,
                                          cancel_request: OrderCancellationRequest) -> OrderCancellationResponse:
        """
        Execute order cancellation with API call.

        Args:
            cancel_request: Order cancellation request

        Returns:
            OrderCancellationResponse with result
        """
        try:
            # Prepare cancellation data
            cancel_data = self._prepare_cancellation_data(cancel_request)

            # Submit cancellation to exchange
            response = await self._submit_cancellation_to_exchange(cancel_data)

            # Parse response
            cancellation_response = self._parse_cancellation_response(
                response, cancel_request.client_order_id
            )

            return cancellation_response

        except Exception as e:
            return OrderCancellationResponse(
                success=False,
                client_order_id=cancel_request.client_order_id,
                error_message=str(e)
            )

    def _prepare_cancellation_data(self, cancel_request: OrderCancellationRequest) -> Dict[str, Any]:
        """
        Prepare cancellation data for API submission.

        Args:
            cancel_request: Order cancellation request

        Returns:
            Dictionary with cancellation data for API
        """
        cancel_data = {
            "timestamp": int(time.time() * 1000)
        }

        # Add order identification
        if cancel_request.exchange_order_id:
            cancel_data["orderId"] = cancel_request.exchange_order_id
        else:
            cancel_data["origClientOrderId"] = cancel_request.client_order_id

        # Add trading pair if provided
        if cancel_request.trading_pair:
            cancel_data["symbol"] = utils.convert_to_exchange_trading_pair(cancel_request.trading_pair)

        return cancel_data

    async def _submit_cancellation_to_exchange(self, cancel_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit cancellation to exchange API.

        Args:
            cancel_data: Cancellation data for submission

        Returns:
            Raw API response
        """
        rest_assistant = await self._api_factory.get_rest_assistant()

        url = web_utils.private_rest_url(CONSTANTS.ORDER_CANCEL_PATH_URL, domain=self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.DELETE,
            params=cancel_data,
            throttler_limit_id=CONSTANTS.ORDER_CANCEL_PATH_URL,
        )

        return response

    def _parse_cancellation_response(self,
                                     response: Dict[str, Any],
                                     client_order_id: str) -> OrderCancellationResponse:
        """
        Parse cancellation response from exchange.

        Args:
            response: Raw API response
            client_order_id: Client order ID

        Returns:
            Parsed OrderCancellationResponse
        """
        try:
            # Check for error in response
            if "code" in response and response["code"] != 200:
                return OrderCancellationResponse(
                    success=False,
                    client_order_id=client_order_id,
                    error_code=str(response.get("code")),
                    error_message=response.get("msg", "Unknown error"),
                    raw_response=response
                )

            # Extract cancellation information
            exchange_order_id = str(response.get("orderId", ""))
            status = response.get("status", "CANCELED")
            timestamp = float(response.get("transactTime", time.time() * 1000)) / 1000

            # Determine success
            success = status in ["CANCELED", "CANCELLED"]

            return OrderCancellationResponse(
                success=success,
                client_order_id=client_order_id,
                exchange_order_id=exchange_order_id if success else None,
                status=status,
                timestamp=timestamp,
                raw_response=response
            )

        except Exception as e:
            self.logger().error(f"Error parsing cancellation response: {e}")
            return OrderCancellationResponse(
                success=False,
                client_order_id=client_order_id,
                error_message=f"Response parsing error: {e}",
                raw_response=response
            )

    async def _fetch_order_status(self,
                                  client_order_id: str,
                                  exchange_order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch order status from API.

        Args:
            client_order_id: Client order ID
            exchange_order_id: Exchange order ID (optional)

        Returns:
            Order status data
        """
        rest_assistant = await self._api_factory.get_rest_assistant()

        params = {"timestamp": int(time.time() * 1000)}

        # Add order identification
        if exchange_order_id:
            params["orderId"] = exchange_order_id
        else:
            params["origClientOrderId"] = client_order_id

        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            params=params,
            throttler_limit_id=CONSTANTS.ORDER_PATH_URL,
        )

        return response

    async def _get_orders_for_cancellation(self, trading_pair: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get orders that need to be cancelled.

        Args:
            trading_pair: Specific trading pair to filter (optional)

        Returns:
            List of orders to cancel
        """
        try:
            # Fetch open orders
            rest_assistant = await self._api_factory.get_rest_assistant()

            params = {"timestamp": int(time.time() * 1000)}
            if trading_pair:
                params["symbol"] = utils.convert_to_exchange_trading_pair(trading_pair)

            url = web_utils.private_rest_url(CONSTANTS.OPEN_ORDERS_PATH_URL, domain=self._domain)

            response = await rest_assistant.execute_request(
                url=url,
                method=RESTMethod.GET,
                params=params,
                throttler_limit_id=CONSTANTS.OPEN_ORDERS_PATH_URL,
            )

            # Parse orders
            orders = []
            if isinstance(response, list):
                orders_data = response
            elif "orders" in response:
                orders_data = response["orders"]
            else:
                orders_data = [response] if response else []

            for order_data in orders_data:
                orders.append({
                    "client_order_id": order_data.get("clientOrderId", ""),
                    "exchange_order_id": str(order_data.get("orderId", "")),
                    "trading_pair": utils.parse_exchange_trading_pair(order_data.get("symbol", ""))
                })

            return orders

        except Exception as e:
            self.logger().error(f"Error fetching orders for cancellation: {e}")
            return []

    async def _execute_order_modification(self,
                                          modify_request: OrderModificationRequest) -> Dict[str, Any]:
        """
        Execute order modification (if supported).

        Args:
            modify_request: Order modification request

        Returns:
            Modification result
        """
        # Note: Many exchanges don't support order modification directly
        # This would typically require cancelling and re-placing the order

        return {
            "success": False,
            "client_order_id": modify_request.client_order_id,
            "error_message": "Order modification not supported - use cancel and re-place",
            "supported_alternative": "CANCEL_AND_REPLACE"
        }

    def get_active_operations(self) -> Dict[str, OrderOperation]:
        """Get currently active operations."""
        return self._active_operations.copy()

    def get_cancellation_history(self) -> List[OrderCancellationResponse]:
        """Get cancellation history."""
        return self._cancellation_history.copy()

    def get_modification_history(self) -> List[Dict[str, Any]]:
        """Get modification history."""
        return self._modification_history.copy()

    def clear_history(self):
        """Clear operation history."""
        self._cancellation_history.clear()
        self._modification_history.clear()

        self.logger().info("Order lifecycle history cleared")

    def get_lifecycle_stats(self) -> Dict[str, Any]:
        """
        Get order lifecycle statistics.

        Returns:
            Dictionary with lifecycle statistics
        """
        successful_cancellations = sum(1 for r in self._cancellation_history if r.success)
        failed_cancellations = len(self._cancellation_history) - successful_cancellations

        return {
            "active_operations": len(self._active_operations),
            "total_cancellations": len(self._cancellation_history),
            "successful_cancellations": successful_cancellations,
            "failed_cancellations": failed_cancellations,
            "cancellation_success_rate": (successful_cancellations / len(self._cancellation_history) * 100) if self._cancellation_history else 0,
            "total_modifications": len(self._modification_history),
            "current_time": time.time()
        }

    async def monitor_order_lifecycle(self,
                                      order_ids: List[str],
                                      monitoring_duration: float = 300.0,
                                      check_interval: float = 5.0) -> Dict[str, Any]:
        """
        Monitor order lifecycle under various market conditions.

        Args:
            order_ids: List of order IDs to monitor
            monitoring_duration: Total monitoring duration in seconds
            check_interval: Check interval in seconds

        Returns:
            Dictionary with monitoring results
        """
        start_time = time.time()
        monitoring_results = {
            "start_time": start_time,
            "order_ids": order_ids,
            "status_updates": [],
            "lifecycle_events": [],
            "market_conditions": [],
            "performance_metrics": {}
        }

        try:
            while time.time() - start_time < monitoring_duration:
                # Check each order status
                for order_id in order_ids:
                    try:
                        status = await self.query_order_status(order_id)
                        monitoring_results["status_updates"].append({
                            "timestamp": time.time(),
                            "order_id": order_id,
                            "status": status
                        })

                        # Detect lifecycle events
                        if status.get("status") in ["FILLED", "CANCELED", "EXPIRED"]:
                            monitoring_results["lifecycle_events"].append({
                                "timestamp": time.time(),
                                "order_id": order_id,
                                "event": status.get("status"),
                                "details": status
                            })

                    except Exception as e:
                        self.logger().error(f"Error monitoring order {order_id}: {e}")

                # Wait for next check
                await asyncio.sleep(check_interval)

            # Calculate performance metrics
            monitoring_results["performance_metrics"] = {
                "total_duration": time.time() - start_time,
                "total_checks": len(monitoring_results["status_updates"]),
                "lifecycle_events_count": len(monitoring_results["lifecycle_events"]),
                "average_response_time": "calculated_from_status_updates"
            }

            return monitoring_results

        except Exception as e:
            self.logger().error(f"Error in order lifecycle monitoring: {e}")
            monitoring_results["error"] = str(e)
            return monitoring_results
