"""
AMM liquidity provision handler for Gateway connectors.
"""
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.core.data_type.common import PositionAction
from hummingbot.logger import HummingbotLogger

from ..models import PoolInfo, Position

if TYPE_CHECKING:
    from ..core.gateway_connector import GatewayConnector


class AMMHandler:
    """
    Handles AMM liquidity provision operations.
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
        Initialize AMM handler.

        :param connector: Parent GatewayConnector instance
        """
        self.connector = connector
        self._positions: Dict[str, Dict[str, Any]] = {}  # Track position metadata

    async def get_pool_info(
        self,
        base_token: str,
        quote_token: str,
        fee_tier: Optional[Decimal] = None
    ) -> Optional[PoolInfo]:
        """
        Get pool information.

        :param base_token: Base token symbol
        :param quote_token: Quote token symbol
        :param fee_tier: Optional fee tier
        :return: PoolInfo or None
        """
        try:
            params = {
                "network": self.connector.config.network,
                "baseToken": base_token,
                "quoteToken": quote_token,
            }

            if fee_tier is not None:
                params["feeTier"] = float(fee_tier)

            response = await self.connector.client.request(
                "GET",
                f"connectors/{self.connector.config.name}/pool-info",
                params=params
            )

            return PoolInfo.from_dict(response)

        except Exception as e:
            self.logger().error(f"Error getting pool info: {str(e)}")
            return None

    async def get_pool_price(
        self,
        base_token: str,
        quote_token: str,
        fee_tier: Optional[Decimal] = None,
        interval: Optional[int] = None,
        period: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get pool price information.

        :param base_token: Base token symbol
        :param quote_token: Quote token symbol
        :param fee_tier: Optional fee tier
        :param interval: Price interval in seconds
        :param period: Price period in seconds
        :return: Price data
        """
        try:
            params = {
                "network": self.connector.config.network,
                "baseToken": base_token,
                "quoteToken": quote_token,
            }

            if fee_tier is not None:
                params["feeTier"] = float(fee_tier)
            if interval is not None:
                params["interval"] = interval
            if period is not None:
                params["period"] = period

            return await self.connector.client.request(
                "GET",
                f"connectors/{self.connector.config.name}/pool-price",
                params=params
            )

        except Exception as e:
            self.logger().error(f"Error getting pool price: {str(e)}")
            return {}

    async def get_positions(self) -> List[Position]:
        """
        Get all liquidity positions.

        :return: List of positions
        """
        try:
            response = await self.connector.client.request(
                "GET",
                f"connectors/{self.connector.config.name}/positions",
                params={
                    "network": self.connector.config.network,
                    "address": self.connector.config.wallet_address,
                }
            )

            positions = []
            for pos_data in response.get("positions", []):
                positions.append(Position.from_dict(pos_data))

            return positions

        except Exception as e:
            self.logger().error(f"Error getting positions: {str(e)}")
            return []

    async def add_liquidity(
        self,
        position_id: str,
        base_token: str,
        quote_token: str,
        base_amount: Decimal,
        quote_amount: Decimal,
        fee_tier: Optional[Decimal] = None,
        **kwargs
    ) -> str:
        """
        Add liquidity to a pool.

        :param position_id: Client position ID
        :param base_token: Base token symbol
        :param quote_token: Quote token symbol
        :param base_amount: Base token amount
        :param quote_amount: Quote token amount
        :param fee_tier: Optional fee tier
        :param kwargs: Additional parameters
        :return: Transaction hash (empty string for async)
        """
        # Store position metadata
        self._positions[position_id] = {
            "trading_pair": f"{base_token}-{quote_token}",
            "position_action": PositionAction.OPEN,
            "base_asset": base_token,
            "quote_asset": quote_token,
            "base_amount": base_amount,
            "quote_amount": quote_amount,
            "fee_tier": fee_tier,
            "pool_address": kwargs.get("pool_address")
        }

        # Build request parameters
        params = {
            "network": self.connector.config.network,
            "address": self.connector.config.wallet_address,
            "baseToken": base_token,
            "quoteToken": quote_token,
            "baseAmount": float(base_amount),
            "quoteAmount": float(quote_amount),
        }

        if fee_tier is not None:
            params["feeTier"] = float(fee_tier)

        # Add pool address if provided
        if "pool_address" in kwargs:
            params["poolAddress"] = kwargs["pool_address"]

        # Execute transaction
        return await self.connector.client.execute_transaction(
            chain=self.connector.config.chain,
            network=self.connector.config.network,
            connector=self.connector.config.name,
            method="add-liquidity",
            params=params,
            order_id=position_id,
            callback=lambda event, pid, data: self._position_callback(event, pid, data, "add")
        )

    async def remove_liquidity(
        self,
        position_id: str,
        position_uid: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Remove liquidity from a position.

        :param position_id: Client position ID
        :param position_uid: Exchange position ID
        :param kwargs: Additional parameters
        :return: Transaction hash (empty string for async)
        """
        # Find existing position metadata
        position_meta = self._positions.get(position_id)
        if not position_meta:
            # Create minimal metadata for tracking
            position_meta = {
                "position_id": position_id,
                "exchange_position_id": position_uid,
                "position_action": PositionAction.CLOSE
            }
            self._positions[position_id] = position_meta
        else:
            position_meta["position_action"] = PositionAction.CLOSE

        # Build request parameters
        params = {
            "network": self.connector.config.network,
            "address": self.connector.config.wallet_address,
            "positionId": position_uid or position_meta.get("exchange_position_id"),
        }

        # Execute transaction
        return await self.connector.client.execute_transaction(
            chain=self.connector.config.chain,
            network=self.connector.config.network,
            connector=self.connector.config.name,
            method="remove-liquidity",
            params=params,
            order_id=position_id,
            callback=lambda event, pid, data: self._position_callback(event, pid, data, "remove")
        )

    async def collect_fees(
        self,
        position_id: str,
        position_uid: Optional[str] = None
    ) -> str:
        """
        Collect fees from a position.

        :param position_id: Client position ID
        :param position_uid: Exchange position ID
        :return: Transaction hash (empty string for async)
        """
        params = {
            "network": self.connector.config.network,
            "address": self.connector.config.wallet_address,
            "positionId": position_uid,
        }

        return await self.connector.client.execute_transaction(
            chain=self.connector.config.chain,
            network=self.connector.config.network,
            connector=self.connector.config.name,
            method="collect-fees",
            params=params,
            order_id=position_id,
            callback=lambda event, pid, data: self._position_callback(event, pid, data, "collect")
        )

    async def _position_callback(
        self,
        event_type: str,
        position_id: str,
        data: Any,
        action: str
    ):
        """
        Handle position transaction events.

        :param event_type: Event type (tx_hash, confirmed, failed)
        :param position_id: Position ID
        :param data: Event data
        :param action: Action type (add, remove, collect)
        """
        position_meta = self._positions.get(position_id)
        if not position_meta:
            return

        # Get position order from connector
        position_order = self.connector._in_flight_positions.get(position_id)
        if not position_order:
            return

        if event_type == "tx_hash":
            # Update transaction hash on position order
            position_order.update_exchange_order_id(data)
            position_order.update_creation_transaction_hash(data)

        elif event_type == "confirmed":
            # Process successful transaction
            if action == "add":
                # Position opened successfully
                self.connector._emit_position_opened_event(position_order)
            elif action == "remove":
                # Position closed successfully
                self.connector._emit_position_closed_event(position_order)
            elif action == "collect":
                # Fees collected successfully
                self.connector._emit_fees_collected_event(position_order)

            # Remove from tracking if closed
            if action == "remove":
                del self._positions[position_id]

        elif event_type == "failed":
            # Handle failed transaction
            self.connector._handle_position_failure(
                position_id=position_id,
                reason=str(data)
            )
            # Remove from tracking
            if position_id in self._positions:
                del self._positions[position_id]
