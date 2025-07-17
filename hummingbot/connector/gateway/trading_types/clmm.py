"""
CLMM (Concentrated Liquidity Market Maker) handler for Gateway connectors.
"""
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.core.data_type.common import PositionAction

from .amm import AMMHandler

if TYPE_CHECKING:
    from ..core.gateway_connector import GatewayConnector  # noqa: F401


class CLMMHandler(AMMHandler):
    """
    Handles CLMM liquidity provision operations.
    Extends AMM handler with concentrated liquidity specific features.
    """

    async def add_liquidity(
        self,
        position_id: str,
        base_token: str,
        quote_token: str,
        base_amount: Decimal,
        quote_amount: Decimal,
        fee_tier: Optional[Decimal] = None,
        lower_price: Optional[Decimal] = None,
        upper_price: Optional[Decimal] = None,
        tick_lower: Optional[int] = None,
        tick_upper: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Add concentrated liquidity to a pool.

        :param position_id: Client position ID
        :param base_token: Base token symbol
        :param quote_token: Quote token symbol
        :param base_amount: Base token amount
        :param quote_amount: Quote token amount
        :param fee_tier: Fee tier
        :param lower_price: Lower price bound
        :param upper_price: Upper price bound
        :param tick_lower: Lower tick (alternative to lower_price)
        :param tick_upper: Upper tick (alternative to upper_price)
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
            "tick_lower": tick_lower,
            "tick_upper": tick_upper,
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

        # Add price range parameters
        if tick_lower is not None and tick_upper is not None:
            params["tickLower"] = tick_lower
            params["tickUpper"] = tick_upper
        elif lower_price is not None and upper_price is not None:
            params["lowerPrice"] = float(lower_price)
            params["upperPrice"] = float(upper_price)
        else:
            raise ValueError("Either tick range or price range must be specified")

        # Add pool address if provided
        if "pool_address" in kwargs:
            params["poolAddress"] = kwargs["pool_address"]

        # Execute transaction
        return await self.connector.client.execute_transaction(
            chain=self.connector.config.chain,
            network=self.connector.config.network,
            connector=self.connector.config.name,
            method="open-position",
            params=params,
            order_id=position_id,
            callback=lambda event, pid, data: self._position_callback(event, pid, data, "open")
        )

    async def remove_liquidity(
        self,
        position_id: str,
        position_uid: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Remove concentrated liquidity from a position.

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
            method="close-position",
            params=params,
            order_id=position_id,
            callback=lambda event, pid, data: self._position_callback(event, pid, data, "close")
        )

    async def get_pool_ticks(
        self,
        base_token: str,
        quote_token: str,
        fee_tier: Decimal,
        tick_spacing: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get tick data for a CLMM pool.

        :param base_token: Base token symbol
        :param quote_token: Quote token symbol
        :param fee_tier: Fee tier
        :param tick_spacing: Optional tick spacing
        :return: List of tick data
        """
        try:
            params = {
                "network": self.connector.config.network,
                "baseToken": base_token,
                "quoteToken": quote_token,
                "feeTier": float(fee_tier),
            }

            if tick_spacing is not None:
                params["tickSpacing"] = tick_spacing

            response = await self.connector.client.request(
                "GET",
                f"connectors/{self.connector.config.name}/pool-ticks",
                params=params
            )

            return response.get("ticks", [])

        except Exception as e:
            self.logger().error(f"Error getting pool ticks: {str(e)}")
            return []

    async def estimate_position_fees(
        self,
        position_uid: str
    ) -> Dict[str, Decimal]:
        """
        Estimate uncollected fees for a position.

        :param position_uid: Exchange position ID
        :return: Fee amounts by token
        """
        try:
            response = await self.connector.client.request(
                "GET",
                f"connectors/{self.connector.config.name}/estimate-fees",
                params={
                    "network": self.connector.config.network,
                    "address": self.connector.config.wallet_address,
                    "positionId": position_uid,
                }
            )

            return {
                "base": Decimal(str(response.get("token0Fees", 0))),
                "quote": Decimal(str(response.get("token1Fees", 0)))
            }

        except Exception as e:
            self.logger().error(f"Error estimating fees: {str(e)}")
            return {"base": Decimal("0"), "quote": Decimal("0")}

    async def _position_callback(
        self,
        event_type: str,
        position_id: str,
        data: Any,
        action: str
    ):
        """
        Handle CLMM position transaction events.

        :param event_type: Event type (tx_hash, confirmed, failed)
        :param position_id: Position ID
        :param data: Event data
        :param action: Action type (open, close, collect)
        """
        # Use parent class callback but with CLMM-specific action names
        action_map = {
            "open": "add",
            "close": "remove",
            "collect": "collect"
        }
        await super()._position_callback(
            event_type,
            position_id,
            data,
            action_map.get(action, action)
        )
