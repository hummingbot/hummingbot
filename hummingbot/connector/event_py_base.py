import asyncio
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.data_type.common import EventPosition, EventResolution, OrderType, OutcomeType, TradeType
from hummingbot.core.data_type.event_in_flight_order import EventInFlightOrder
from hummingbot.core.utils.async_utils import safe_ensure_future


class EventPyBase(ExchangePyBase, ABC):
    """
    Python-based async implementation for event/prediction market connectors.

    This extends ExchangePyBase to provide:
    - Exchange functionality with metrics collection
    - Event-specific order management
    - Position tracking for outcomes
    - Resolution monitoring
    - Prediction market operations
    """

    def __init__(
        self,
        trading_pairs: List[str] = None,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100")
    ):
        # Initialize ExchangePyBase which handles metrics and config properly
        super().__init__(balance_asset_limit, rate_limits_share_pct)

        self._trading_pairs = trading_pairs or []
        self._market_resolution_task: Optional[asyncio.Task] = None
        self._market_data_task: Optional[asyncio.Task] = None

        # Event-specific tracking
        self._pending_resolutions: Dict[str, float] = {}  # market_id -> timestamp
        self._resolution_poll_interval = 300  # 5 minutes default

    @property
    @abstractmethod
    def resolution_poll_interval(self) -> int:
        """
        Interval in seconds for checking market resolutions.

        Returns:
            Polling interval in seconds
        """
        raise NotImplementedError

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        Dictionary of connector status components.

        Returns:
            Status dictionary with event-specific checks
        """
        status_d = super().status_dict
        status_d["event_markets_initialized"] = len(self._event_markets) > 0
        status_d["resolution_monitoring"] = self._market_resolution_task is not None and not self._market_resolution_task.done()
        return status_d

    def start_tracking_order(
        self,
        order_id: str,
        exchange_order_id: Optional[str],
        trading_pair: str,
        trade_type: TradeType,
        price: Decimal,
        amount: Decimal,
        order_type: OrderType,
        market_id: str,
        outcome: OutcomeType,
        **kwargs
    ):
        """
        Start tracking an event market order.

        Args:
            order_id: Client order identifier
            exchange_order_id: Exchange order identifier
            trading_pair: Trading pair string
            trade_type: BUY or SELL
            price: Price per share (0-1)
            amount: Number of shares
            order_type: Order type
            market_id: Event market identifier
            outcome: YES or NO outcome
            **kwargs: Additional parameters
        """
        self._order_tracker.start_tracking_order(
            EventInFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                price=price,
                amount=amount,
                creation_timestamp=self.current_timestamp,
                market_id=market_id,
                outcome=outcome,
                **kwargs
            )
        )

    async def start_network(self):
        """
        Start network connections and background tasks.
        """
        await super().start_network()

        # Start event-specific tasks
        self._market_data_task = safe_ensure_future(self._update_market_data_loop())
        if self.is_trading_required:
            self._market_resolution_task = safe_ensure_future(self._monitor_resolutions_loop())

    async def stop_network(self):
        """
        Stop network connections and background tasks.
        """
        # Cancel event-specific tasks
        if self._market_data_task:
            self._market_data_task.cancel()
            self._market_data_task = None

        if self._market_resolution_task:
            self._market_resolution_task.cancel()
            self._market_resolution_task = None

        await super().stop_network()

    async def _update_market_data_loop(self):
        """
        Background task to update market data periodically.
        """
        while True:
            try:
                # Update active markets
                markets = await self.get_active_markets()
                for market in markets:
                    self.update_market_info(market)

                # Update positions
                await self._update_event_positions()

                await asyncio.sleep(60)  # Update every minute

            except Exception as e:
                self.logger().error(f"Error updating market data: {e}")
                await asyncio.sleep(60)

    async def _monitor_resolutions_loop(self):
        """
        Background task to monitor market resolutions.
        """
        while True:
            try:
                current_time = self.current_timestamp

                # Check pending resolutions
                for market_id in list(self._pending_resolutions.keys()):
                    last_check = self._pending_resolutions[market_id]

                    # Check resolution every poll interval
                    if current_time - last_check >= self.resolution_poll_interval:
                        resolution = await self.get_resolution_status(market_id)

                        if resolution != EventResolution.PENDING:
                            # Market resolved
                            self._resolution_status[market_id] = resolution

                            # Trigger resolution event
                            await self._handle_market_resolution(market_id, resolution)

                            # Remove from pending
                            del self._pending_resolutions[market_id]
                        else:
                            # Update last check time
                            self._pending_resolutions[market_id] = current_time

                await asyncio.sleep(self.resolution_poll_interval)

            except Exception as e:
                self.logger().error(f"Error monitoring resolutions: {e}")
                await asyncio.sleep(self.resolution_poll_interval)

    async def _update_event_positions(self):
        """
        Update event market positions.
        """
        try:
            # Get current positions from exchange
            positions = await self._get_current_positions()

            for position in positions:
                self.update_position(position)

        except Exception as e:
            self.logger().error(f"Error updating positions: {e}")

    async def _handle_market_resolution(self, market_id: str, resolution: EventResolution):
        """
        Handle market resolution event.

        Args:
            market_id: Resolved market identifier
            resolution: Resolution result
        """
        self.logger().info(f"Market {market_id} resolved: {resolution}")

        # Update market info
        market = self._event_markets.get(market_id)
        if market:
            updated_market = market._replace(status=resolution)
            self.update_market_info(updated_market)

        # Auto-claim winnings if enabled
        try:
            success = await self.claim_winnings(market_id)
            if success:
                self.logger().info(f"Successfully claimed winnings for market {market_id}")
        except Exception as e:
            self.logger().error(f"Error claiming winnings for market {market_id}: {e}")

    def add_market_for_resolution_monitoring(self, market_id: str):
        """
        Add a market to resolution monitoring.

        Args:
            market_id: Market to monitor for resolution
        """
        if market_id not in self._pending_resolutions:
            self._pending_resolutions[market_id] = self.current_timestamp

    def remove_market_from_resolution_monitoring(self, market_id: str):
        """
        Remove a market from resolution monitoring.

        Args:
            market_id: Market to stop monitoring
        """
        self._pending_resolutions.pop(market_id, None)

    @abstractmethod
    async def _get_current_positions(self) -> List[EventPosition]:
        """
        Get current event market positions from the exchange.

        Returns:
            List of current EventPosition objects
        """
        raise NotImplementedError

    @abstractmethod
    async def _place_event_order(
        self,
        market_id: str,
        outcome: OutcomeType,
        trade_type: TradeType,
        amount: Decimal,
        price: Decimal,
        order_type: OrderType = OrderType.PREDICTION_LIMIT,
        **kwargs
    ) -> str:
        """
        Place an order on the exchange.

        Args:
            market_id: Event market identifier
            outcome: YES or NO outcome
            trade_type: BUY or SELL
            amount: Number of shares
            price: Price per share
            order_type: Order type
            **kwargs: Additional parameters

        Returns:
            Client order ID
        """
        raise NotImplementedError

    @abstractmethod
    async def _cancel_event_order(self, client_order_id: str) -> bool:
        """
        Cancel an order on the exchange.

        Args:
            client_order_id: Client order identifier

        Returns:
            True if cancellation was successful
        """
        raise NotImplementedError

    async def execute_buy(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = None,
        **kwargs
    ) -> str:
        """
        Execute a buy order for event markets.

        Args:
            order_id: Client order ID
            trading_pair: Trading pair in format "MARKET_ID-OUTCOME-QUOTE"
            amount: Number of shares
            order_type: Order type
            price: Price per share
            **kwargs: Additional parameters

        Returns:
            Exchange order ID
        """
        # Parse trading pair
        market_id, outcome, quote_asset = self.parse_trading_pair(trading_pair)

        # Validate order
        if not self.validate_prediction_order(market_id, outcome, amount, price):
            raise ValueError(f"Invalid order parameters for {trading_pair}")

        # Place order
        exchange_order_id = await self._place_event_order(
            market_id=market_id,
            outcome=outcome,
            trade_type=TradeType.BUY,
            amount=amount,
            price=price,
            order_type=order_type,
            **kwargs
        )

        # Start tracking
        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            trade_type=TradeType.BUY,
            price=price,
            amount=amount,
            order_type=order_type,
            market_id=market_id,
            outcome=outcome,
            **kwargs
        )

        # Add market to resolution monitoring if not already monitored
        self.add_market_for_resolution_monitoring(market_id)

        return exchange_order_id

    async def execute_sell(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = None,
        **kwargs
    ) -> str:
        """
        Execute a sell order for event markets.

        Args:
            order_id: Client order ID
            trading_pair: Trading pair in format "MARKET_ID-OUTCOME-QUOTE"
            amount: Number of shares
            order_type: Order type
            price: Price per share
            **kwargs: Additional parameters

        Returns:
            Exchange order ID
        """
        # Parse trading pair
        market_id, outcome, quote_asset = self.parse_trading_pair(trading_pair)

        # Validate order
        if not self.validate_prediction_order(market_id, outcome, amount, price):
            raise ValueError(f"Invalid order parameters for {trading_pair}")

        # Place order
        exchange_order_id = await self._place_event_order(
            market_id=market_id,
            outcome=outcome,
            trade_type=TradeType.SELL,
            amount=amount,
            price=price,
            order_type=order_type,
            **kwargs
        )

        # Start tracking
        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            trade_type=TradeType.SELL,
            price=price,
            amount=amount,
            order_type=order_type,
            market_id=market_id,
            outcome=outcome,
            **kwargs
        )

        # Add market to resolution monitoring if not already monitored
        self.add_market_for_resolution_monitoring(market_id)

        return exchange_order_id

    async def execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        Cancel an order.

        Args:
            trading_pair: Trading pair
            order_id: Client order ID

        Returns:
            Client order ID that was cancelled
        """
        success = await self._cancel_event_order(order_id)
        if not success:
            raise ValueError(f"Failed to cancel order {order_id}")
        return order_id
