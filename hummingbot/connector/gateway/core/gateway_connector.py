"""
Single unified Gateway connector class using composition for different trading types.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import TradeFeeBase, TradeFeeSchema
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger

from ..models import ConnectorConfig, GatewayInFlightOrder, GatewayInFlightPosition, TradingType
from ..trading_types import AMMHandler, CLMMHandler, SwapHandler
from .gateway_client import GatewayClient


class GatewayConnector(ConnectorBase):
    """
    Single connector class that uses composition for different trading types.
    """

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    def __init__(
        self,
        connector_name: str,
        network: str,
        wallet_address: Optional[str] = None,
        trading_required: bool = True
    ):
        """
        Initialize Gateway connector.

        :param connector_name: Connector name (e.g., "raydium/amm")
        :param network: Network name (e.g., "mainnet-beta")
        :param wallet_address: Optional wallet address
        :param trading_required: Whether trading is required
        """
        # Set attributes first
        self.connector_name = connector_name
        self.network = network
        self.wallet_address = wallet_address
        self._trading_required = trading_required

        # Chain will be determined from connector
        self.chain: Optional[str] = None

        # Get client config for ConnectorBase
        from hummingbot.client.hummingbot_application import HummingbotApplication
        app = HummingbotApplication.main_application()
        client_config = app.client_config_map if app else None
        super().__init__(client_config)

        # Get or create Gateway client
        self._client = None
        self._config: Optional[ConnectorConfig] = None

        # Trading handlers
        self._trading_handlers = {}

        # State tracking
        self._ready = False
        self._balances = {}
        self._allowances = {}
        self._last_poll_timestamp = 0
        self._poll_interval = 10.0

        # Token list cache
        self._tokens: Dict[str, Dict[str, Any]] = {}

        # Order tracking
        self._in_flight_orders: Dict[str, GatewayInFlightOrder] = {}

        # Position tracking (for AMM/CLMM)
        self._in_flight_positions: Dict[str, GatewayInFlightPosition] = {}

        # Initialize in background
        safe_ensure_future(self._initialize())

    @property
    def client(self) -> GatewayClient:
        """Get Gateway client instance."""
        if self._client is None:
            # Get from main application
            from hummingbot.client.hummingbot_application import HummingbotApplication
            app = HummingbotApplication.main_application()
            if app:
                self._client = GatewayClient.get_instance(app.client_config_map)
            else:
                # Default for testing - create a minimal config
                self._client = GatewayClient.get_instance(None)
        return self._client

    @property
    def config(self) -> ConnectorConfig:
        """Get connector configuration."""
        if self._config is None:
            raise RuntimeError("Connector not initialized")
        return self._config

    @property
    def name(self) -> str:
        """Return connector name."""
        if hasattr(self, 'chain') and self.chain:
            return f"{self.connector_name}_{self.chain}_{self.network}"
        else:
            return f"{self.connector_name}_{self.network}"

    @property
    def ready(self) -> bool:
        """Check if connector is ready."""
        return self._ready

    async def _initialize(self):
        """Initialize connector configuration and handlers."""
        try:
            # Load configuration from Gateway
            self._config = await ConnectorConfig.from_gateway(
                self.client,
                self.connector_name,
                self.network,
                self.wallet_address
            )

            # Update chain and wallet address from config
            self.chain = self._config.chain
            if self._config.wallet_address:
                self.wallet_address = self._config.wallet_address

            # Initialize trading handlers based on capabilities
            self._init_trading_handlers()

            # Load token list
            await self._update_token_list()

            # Mark as ready
            self._ready = True
            self.logger().info(f"Gateway connector {self.name} initialized successfully")

        except Exception as e:
            self.logger().error(f"Failed to initialize Gateway connector: {str(e)}")
            raise

    def _init_trading_handlers(self):
        """Initialize appropriate trading handlers based on connector capabilities."""
        self._trading_handlers = {}

        # All connectors support swap operations
        self._trading_handlers["swap"] = SwapHandler(self)

        # Additional handlers for specific trading types
        for trading_type in self.config.trading_types:
            if trading_type == TradingType.AMM:
                self._trading_handlers["amm"] = AMMHandler(self)
            elif trading_type == TradingType.CLMM:
                self._trading_handlers["clmm"] = CLMMHandler(self)

    async def start_network(self):
        """Start network operations."""
        if not self._ready:
            await self._initialize()
        self._set_polling_interval(self._poll_interval)

    async def stop_network(self):
        """Stop network operations."""
        self._set_polling_interval(0)

    async def check_network(self) -> bool:
        """Check network connectivity."""
        try:
            # Try to get Gateway status
            response = await self.client.request("GET", "")
            return response.get("status") == "ok"
        except Exception:
            return False

    def tick(self, timestamp: float):
        """
        Periodic tick for updates.

        :param timestamp: Current timestamp
        """
        if timestamp - self._last_poll_timestamp > self._poll_interval:
            self._last_poll_timestamp = timestamp
            safe_ensure_future(self._update_balances())

    def supported_order_types(self) -> List[OrderType]:
        """Get supported order types."""
        # Gateway connectors support market and limit orders
        return [OrderType.LIMIT, OrderType.MARKET]

    async def _update_balances(self):
        """Update account balances."""
        try:
            # Get list of tokens to check
            tokens = list(self._tokens.keys())
            if not tokens:
                return

            # Get balances from Gateway
            response = await self.client.get_balances(
                self.chain,
                self.network,
                self.wallet_address,
                tokens
            )

            # Update internal balances
            for token, balance_str in response.get("balances", {}).items():
                self._balances[token] = Decimal(str(balance_str))

        except Exception as e:
            self.logger().error(f"Error updating balances: {str(e)}")

    async def _update_token_list(self):
        """Update token list from Gateway."""
        try:
            tokens = await self.client.get_tokens(self.chain, self.network)
            self._tokens = {t["symbol"]: t for t in tokens}
        except Exception as e:
            self.logger().error(f"Error updating token list: {str(e)}")

    # Trading interface methods

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.MARKET,
        price: Decimal = None,
        **kwargs
    ) -> str:
        """Place a buy order."""
        order_id = self.create_market_order_id(TradeType.BUY, trading_pair)

        # Create in-flight order synchronously

        order = GatewayInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=None,  # Will be set when we get tx hash
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=TradeType.BUY,
            price=price or Decimal("0"),
            amount=amount,
            creation_timestamp=self.current_timestamp,
            connector_name=self.connector_name,
            method="execute-swap"
        )
        self._in_flight_orders[order_id] = order

        # Execute swap in background without blocking
        safe_ensure_future(self._execute_buy(
            order_id, trading_pair, amount, order_type, price, **kwargs
        ))

        return order_id

    async def _execute_buy(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal],
        **kwargs
    ):
        """Execute buy order asynchronously."""
        try:
            await self._trading_handlers["swap"].execute_swap(
                order_id=order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.BUY,
                price=price,
                amount=amount,
                **kwargs
            )
        except Exception as e:
            # Handle failure
            self._handle_order_failure(order_id, str(e))

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.MARKET,
        price: Decimal = None,
        **kwargs
    ) -> str:
        """Place a sell order."""
        order_id = self.create_market_order_id(TradeType.SELL, trading_pair)

        # Create in-flight order synchronously

        order = GatewayInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=None,  # Will be set when we get tx hash
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=TradeType.SELL,
            price=price or Decimal("0"),
            amount=amount,
            creation_timestamp=self.current_timestamp,
            connector_name=self.connector_name,
            method="execute-swap"
        )
        self._in_flight_orders[order_id] = order

        # Execute swap in background without blocking
        safe_ensure_future(self._execute_sell(
            order_id, trading_pair, amount, order_type, price, **kwargs
        ))

        return order_id

    async def _execute_sell(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal],
        **kwargs
    ):
        """Execute sell order asynchronously."""
        try:
            await self._trading_handlers["swap"].execute_swap(
                order_id=order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.SELL,
                price=price,
                amount=amount,
                **kwargs
            )
        except Exception as e:
            # Handle failure
            self._handle_order_failure(order_id, str(e))

    def cancel(self, trading_pair: str, order_id: str):
        """
        Cancel an order.
        Gateway orders cannot be cancelled once submitted.
        """
        # Gateway orders are atomic and cannot be cancelled
        # Mark as cancelled locally
        if order_id in self._in_flight_orders:
            self.stop_tracking_order(order_id)
            self.trigger_event(
                self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                CancellationResult(order_id, True)
            )
            self.logger().info(f"Order {order_id} marked as cancelled (Gateway orders cannot be cancelled)")
        return order_id

    async def get_order_price(
        self,
        trading_pair: str,
        is_buy: bool,
        amount: Decimal,
        ignore_shim: bool = False
    ) -> Optional[Decimal]:
        """Get price quote for an order."""
        return await self._trading_handlers["swap"].get_price(
            trading_pair,
            is_buy,
            amount,
            ignore_shim
        )

    def get_balance(self, currency: str) -> Decimal:
        """Get balance for a currency."""
        return self._balances.get(currency, Decimal("0"))

    def get_all_balances(self) -> Dict[str, Decimal]:
        """Get all balances."""
        return self._balances.copy()

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        """Get in-flight orders."""
        return self._in_flight_orders.copy()

    def get_order(self, client_order_id: str) -> Optional[InFlightOrder]:
        """Get a specific order."""
        return self._in_flight_orders.get(client_order_id)

    @property
    def tracking_states(self) -> Dict[str, Any]:
        """Get tracking states for restoration."""
        return {
            "orders": {
                oid: order.to_json() for oid, order in self._in_flight_orders.items()
            },
            "positions": {
                pid: {
                    "client_position_id": pos.client_position_id,
                    "exchange_position_id": pos.exchange_position_id,
                    "trading_pair": pos.trading_pair,
                    "position_action": pos.position_action.name,
                    "base_asset": pos.base_asset,
                    "quote_asset": pos.quote_asset,
                    "base_amount": str(pos.base_amount),
                    "quote_amount": str(pos.quote_amount),
                    "creation_timestamp": pos.creation_timestamp,
                }
                for pid, pos in self._in_flight_positions.items()
            }
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        """Restore tracking states."""
        # Restore orders
        for order_id, order_json in saved_states.get("orders", {}).items():
            order = GatewayInFlightOrder.from_json(order_json)
            self._in_flight_orders[order_id] = order

        # Restore positions
        for pos_id, pos_data in saved_states.get("positions", {}).items():
            position = GatewayInFlightPosition(
                client_position_id=pos_data["client_position_id"],
                exchange_position_id=pos_data.get("exchange_position_id"),
                trading_pair=pos_data["trading_pair"],
                position_action=PositionAction[pos_data["position_action"]],
                base_asset=pos_data["base_asset"],
                quote_asset=pos_data["quote_asset"],
                base_amount=Decimal(pos_data["base_amount"]),
                quote_amount=Decimal(pos_data["quote_amount"]),
                creation_timestamp=pos_data["creation_timestamp"]
            )
            self._in_flight_positions[pos_id] = position

    def quantize_order_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        """Quantize order amount."""
        # Gateway handles amount precision
        return amount

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        """Quantize order price."""
        # Gateway handles price precision
        return price

    def get_order_book(self, trading_pair: str) -> OrderBook:
        """Get order book (not supported for Gateway)."""
        raise NotImplementedError("Order book not available for Gateway connectors")

    @property
    def limit_orders(self) -> List[LimitOrder]:
        """Get limit orders."""
        return []

    def get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = Decimal("0"),
        is_maker: Optional[bool] = None
    ) -> TradeFeeBase:
        """Get fee estimate."""
        # Gateway fees are dynamic and included in transaction
        return TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order_side,
            percent=Decimal("0"),
            flat_fees=[]
        )

    def trade_fee_schema(self) -> TradeFeeSchema:
        """Get trade fee schema."""
        return TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0"),
            taker_percent_fee_decimal=Decimal("0"),
            buy_percent_fee_deducted_from_returns=False
        )

    # AMM/CLMM specific methods

    async def add_liquidity(
        self,
        trading_pair: str,
        base_amount: Decimal,
        quote_amount: Decimal,
        fee_tier: Optional[Decimal] = None,
        lower_price: Optional[Decimal] = None,
        upper_price: Optional[Decimal] = None,
        **kwargs
    ) -> str:
        """Add liquidity to a pool."""
        handler = self._trading_handlers.get("clmm") or self._trading_handlers.get("amm")
        if not handler:
            raise ValueError(f"Connector {self.connector_name} does not support liquidity provision")

        base, quote = trading_pair.split("-")
        position_id = f"pos_{self.current_timestamp}"

        if isinstance(handler, CLMMHandler) and lower_price is not None:
            # CLMM with price range
            await handler.add_liquidity(
                position_id=position_id,
                base_token=base,
                quote_token=quote,
                base_amount=base_amount,
                quote_amount=quote_amount,
                fee_tier=fee_tier,
                lower_price=lower_price,
                upper_price=upper_price,
                **kwargs
            )
        else:
            # AMM without range
            await handler.add_liquidity(
                position_id=position_id,
                base_token=base,
                quote_token=quote,
                base_amount=base_amount,
                quote_amount=quote_amount,
                fee_tier=fee_tier,
                **kwargs
            )

        return position_id

    async def remove_liquidity(self, position_id: str, position_uid: Optional[str] = None) -> str:
        """Remove liquidity from a position."""
        handler = self._trading_handlers.get("clmm") or self._trading_handlers.get("amm")
        if not handler:
            raise ValueError(f"Connector {self.connector_name} does not support liquidity provision")

        return await handler.remove_liquidity(position_id, position_uid)

    async def get_positions(self) -> List[Any]:
        """Get all liquidity positions."""
        handler = self._trading_handlers.get("clmm") or self._trading_handlers.get("amm")
        if not handler:
            return []

        return await handler.get_positions()

    # Internal event handling

    def _process_order_update(self, order_update: OrderUpdate):
        """Process order update."""
        order = self._in_flight_orders.get(order_update.client_order_id)
        if order:
            order.update_with_order_update(order_update)
            if order_update.new_state in ["FILLED", "CANCELED", "FAILED"]:
                self.stop_tracking_order(order_update.client_order_id)

    def _process_trade_update(self, trade_update):
        """Process trade update."""
        self.trigger_event(
            self.MARKET_ORDER_FILLED_EVENT_TAG,
            trade_update
        )

    def _handle_order_failure(self, order_id: str, reason: str):
        """Handle order failure."""
        order = self._in_flight_orders.get(order_id)
        if order:
            self.logger().error(f"Order {order_id} failed: {reason}")
            self.stop_tracking_order(order_id)
            self.trigger_event(
                self.MARKET_ORDER_FAILURE_EVENT_TAG,
                (order_id, order)
            )

    def _emit_position_opened_event(self, position: GatewayInFlightPosition):
        """Emit position opened event."""
        # Custom event for position opened
        self.logger().info(f"Position {position.client_position_id} opened")

    def _emit_position_closed_event(self, position: GatewayInFlightPosition):
        """Emit position closed event."""
        # Custom event for position closed
        self.logger().info(f"Position {position.client_position_id} closed")

    def _emit_fees_collected_event(self, position: GatewayInFlightPosition):
        """Emit fees collected event."""
        # Custom event for fees collected
        self.logger().info(f"Fees collected for position {position.client_position_id}")

    def _handle_position_failure(self, position_id: str, reason: str):
        """Handle position failure."""
        self.logger().error(f"Position {position_id} failed: {reason}")
