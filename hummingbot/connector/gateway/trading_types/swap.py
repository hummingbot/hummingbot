"""
Swap handler for Gateway connectors.
All connectors support swap operations.
"""
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger

from ..core.transaction_monitor import TransactionMonitor
from ..gateway_in_flight_order import GatewayInFlightOrder
from ..models import PriceQuote, TransactionResult

if TYPE_CHECKING:
    from ..core.gateway_connector import GatewayConnector


class SwapHandler:
    """
    Handles swap operations for any connector.
    """

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            from hummingbot.logger import HummingbotLogger
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    def __init__(self, connector: "GatewayConnector"):
        """
        Initialize swap handler.

        :param connector: Parent GatewayConnector instance
        """
        self.connector = connector

    async def get_price(
        self,
        trading_pair: str,
        is_buy: bool,
        amount: Decimal,
        ignore_shim: bool = False
    ) -> Optional[Decimal]:
        """
        Get swap price quote.

        :param trading_pair: Trading pair
        :param is_buy: True for buy, False for sell
        :param amount: Amount to swap
        :param ignore_shim: Ignore any shim/wrapper logic
        :return: Price or None
        """
        try:
            base, quote = trading_pair.split("-")
            side = TradeType.BUY if is_buy else TradeType.SELL

            # Build connector path - include trading type if not already included
            connector_path = self.connector.config.name
            if "/" not in connector_path:
                connector_path = f"{connector_path}/swap"

            response = await self.connector.client.request(
                "GET",
                f"connectors/{connector_path}/quote-swap",
                params={
                    "network": self.connector.config.network,
                    "baseToken": base,
                    "quoteToken": quote,
                    "amount": float(amount),
                    "side": side.name
                }
            )

            # Cache compute units if available
            if "computeUnits" in response:
                self.connector.client.cache_compute_units(
                    "execute-swap",
                    self.connector.config.name,
                    self.connector.config.network,
                    response["computeUnits"]
                )

            quote_obj = PriceQuote.from_dict(response)
            return quote_obj.price

        except Exception as e:
            self.logger().error(f"Error getting price quote: {str(e)}")
            return None

    async def execute_swap(
        self,
        order_id: str,
        trading_pair: str,
        order_type: OrderType,
        trade_type: TradeType,
        price: Decimal,
        amount: Decimal,
        **kwargs
    ) -> str:
        """
        Execute a swap transaction.

        :param order_id: Client order ID
        :param trading_pair: Trading pair
        :param order_type: Order type (LIMIT or MARKET)
        :param trade_type: Trade type (BUY or SELL)
        :param price: Price (for limit orders)
        :param amount: Amount to swap
        :param kwargs: Additional parameters
        :return: Transaction hash (empty string for async)
        """
        base, quote = trading_pair.split("-")

        # Build connector path - include trading type if not already included
        connector_path = self.connector.config.name
        if "/" not in connector_path:
            connector_path = f"{connector_path}/swap"

        # Check if we have a quote ID from gateway swap command
        quote_id = kwargs.get("quote_id")
        if quote_id:
            # Use execute-quote endpoint with quote ID
            execute_params = {
                "walletAddress": self.connector.config.wallet_address,
                "network": self.connector.config.network,
                "quoteId": quote_id
            }
            method = "execute-quote"
        else:
            # Build standard swap parameters
            params = {
                "network": self.connector.config.network,
                "address": self.connector.config.wallet_address,
                "baseToken": base,
                "quoteToken": quote,
                "amount": float(amount),
                "side": trade_type.name,
            }

            # Add optional parameters from kwargs
            if "pool_address" in kwargs and kwargs["pool_address"]:
                params["poolAddress"] = kwargs["pool_address"]
            if "route" in kwargs and kwargs["route"]:
                params["route"] = kwargs["route"]
            if "minimum_out" in kwargs and kwargs["minimum_out"]:
                params["minimumOut"] = kwargs["minimum_out"]

            # Add slippage for market orders
            if order_type == OrderType.MARKET:
                slippage = kwargs.get("slippage", 0.01)  # 1% default
                params["slippagePct"] = slippage * 100
            else:
                # For limit orders, add limit price
                params["limitPrice"] = float(price)

            execute_params = params
            method = "execute-swap"

        # Execute transaction using TransactionMonitor
        try:
            response = await self.connector.client.connector_request(
                "POST", connector_path, method, data=execute_params
            )

            if "error" in response:
                raise Exception(response["error"])

            # Start monitoring with TransactionMonitor
            monitor = TransactionMonitor(self.connector.client)
            safe_ensure_future(
                monitor.monitor_transaction(
                    response=response,
                    chain=self.connector.config.chain,
                    network=self.connector.config.network,
                    order_id=order_id,
                    callback=self._transaction_callback
                )
            )

            return ""  # Async execution

        except Exception as e:
            # If transaction submission fails, notify callback
            if self._transaction_callback:
                self._transaction_callback("failed", order_id, str(e))
            raise

    async def _transaction_callback(self, event_type: str, order_id: str, data: Any):
        """
        Handle transaction events.

        :param event_type: Event type (tx_hash, confirmed, failed)
        :param order_id: Order ID
        :param data: Event data
        """
        order = self.connector._order_tracker.fetch_order(order_id)
        if not order:
            return

        if event_type == "tx_hash":
            # Update order with transaction hash as exchange_order_id
            order.update_exchange_order_id(data)
            # Also update creation transaction hash for Gateway-specific tracking
            order.update_creation_transaction_hash(data)

        elif event_type == "confirmed":
            # Process successful transaction
            tx_result = TransactionResult.from_dict(data) if isinstance(data, dict) else data

            # Create trade update
            trade_update = TradeUpdate(
                trade_id=tx_result.tx_hash,
                client_order_id=order_id,
                exchange_order_id=order.exchange_order_id,
                trading_pair=order.trading_pair,
                fill_timestamp=tx_result.timestamp or time.time(),
                fill_price=order.price,
                fill_base_amount=order.amount,
                fill_quote_amount=order.amount * order.price,
                fee=self._get_trade_fee(tx_result, order)
            )

            # Process the trade fill
            self.connector._process_trade_update(trade_update)

            # Mark order as filled
            order_update = OrderUpdate(
                trading_pair=order.trading_pair,
                update_timestamp=time.time(),
                new_state=OrderState.FILLED,
                client_order_id=order_id,
                exchange_order_id=order.exchange_order_id,
                misc_updates={"filled_amount": float(order.amount)}
            )
            self.connector._process_order_update(order_update)

        elif event_type == "failed":
            # Handle failed transaction
            self.connector._handle_order_failure(
                order_id=order_id,
                reason=str(data)
            )

    def _get_trade_fee(self, tx_result: TransactionResult, order: GatewayInFlightOrder) -> TradeFeeBase:
        """Calculate trade fee from transaction result."""
        fee_amount = Decimal("0")

        # Determine native currency based on chain
        native_currency_map = {
            "ethereum": "ETH",
            "solana": "SOL",
            "avalanche": "AVAX",
            "polygon": "MATIC",
            "binance-smart-chain": "BNB",
            "arbitrum": "ETH",
            "optimism": "ETH"
        }

        if tx_result.gas_used and tx_result.gas_price:
            # Ethereum-style fee
            fee_amount = Decimal(str(tx_result.gas_used)) * tx_result.gas_price
            fee_token = native_currency_map.get(self.connector.chain, "ETH")
        elif tx_result.compute_units_used and order.priority_fee_per_cu:
            # Solana-style fee
            fee_amount = (Decimal(str(tx_result.compute_units_used)) *
                          Decimal(str(order.priority_fee_per_cu))) / Decimal("1e9")
            fee_token = native_currency_map.get(self.connector.chain, "SOL")
        else:
            fee_token = order.quote_asset

        return TradeFeeBase.new_spot_fee(
            fee_schema=self.connector.trade_fee_schema(),
            trade_type=order.trade_type,
            percent=Decimal("0"),
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_token)]
        )
