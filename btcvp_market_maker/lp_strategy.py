"""LP strategy: manage 3 liquidity positions with ±3% range and auto-rebalance."""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

from .config import Config
from .dex_client import DexClient
from .price_feed import BTCPriceFeed

logger = logging.getLogger(__name__)


@dataclass
class LPPosition:
    """Represents a single LP position in the pool."""
    id: int
    lp_tokens: int = 0  # Amount of LP tokens held for this position
    initial_btcvp_amount: Decimal = Decimal("0")
    initial_usdc_amount: Decimal = Decimal("0")
    target_price: Decimal = Decimal("0")  # The center price when position was created
    active: bool = False


class LPStrategy:
    """
    Manages multiple LP positions for BTCvp/USDC pool.
    
    Strategy (Uniswap V2 - full range by default, so we simulate concentrated
    liquidity via position sizing and rebalancing):
    
    For Uniswap V2, liquidity is distributed across the full price range.
    We manage the "±3% range" concept by:
    1. Adding liquidity at the correct ratio for current price
    2. Monitoring when the price drifts beyond 3% from our entry
    3. When single-sided ratio exceeds threshold (80%), remove and re-add
    
    The "single-sided 20%" trigger:
    - In Uni V2, as price moves, the token ratio shifts
    - If BTCvp becomes 80%+ of position value → price dropped too much → rebalance
    - If USDC becomes 80%+ of position value → price rose too much → rebalance
    """

    def __init__(self, config: Config, dex_client: DexClient, price_feed: BTCPriceFeed):
        self.config = config
        self.dex = dex_client
        self.price_feed = price_feed
        self.positions: List[LPPosition] = [
            LPPosition(id=i) for i in range(config.lp_position_count)
        ]

    async def execute(self):
        """Main LP management loop iteration.
        
        1. Check each position's health
        2. Rebalance positions that have drifted beyond threshold
        3. Open new positions if slots are empty
        """
        if not self.price_feed.is_ready:
            logger.warning("Price feed not ready, skipping LP management")
            return

        target_price = self.price_feed.price
        pool_price = self.dex.get_pool_price()

        logger.info(f"LP check - Target price: {target_price:.2f}, Pool price: {pool_price:.2f}")

        for position in self.positions:
            if position.active:
                needs_rebalance = self._check_rebalance_needed(position, pool_price)
                if needs_rebalance:
                    logger.info(f"Position {position.id} needs rebalance")
                    self._rebalance_position(position, target_price)
            else:
                logger.info(f"Position {position.id} inactive, opening new position")
                self._open_position(position, target_price)

    def _check_rebalance_needed(self, position: LPPosition, current_price: Decimal) -> bool:
        """Check if position needs rebalancing.
        
        In Uni V2, the value ratio shifts with price:
        - value_btcvp = btcvp_amount * current_price  
        - value_usdc = usdc_amount
        - ratio = value_btcvp / (value_btcvp + value_usdc)
        
        If ratio > threshold or ratio < (1 - threshold), rebalance needed.
        Also rebalance if price moved beyond ±3% from position's target price.
        """
        if position.lp_tokens == 0:
            return True

        # Check price drift from position's entry price
        if position.target_price > 0:
            price_drift = abs(current_price - position.target_price) / position.target_price
            if price_drift > self.config.lp_range_pct:
                logger.info(
                    f"Position {position.id}: price drifted {price_drift*100:.2f}% "
                    f"from entry {position.target_price:.2f} (threshold: {self.config.lp_range_pct*100:.1f}%)"
                )
                return True

        # Check token ratio in our position
        total_supply = self.dex.get_lp_total_supply()
        if total_supply == 0:
            return False

        btcvp_reserve, usdc_reserve = self.dex.get_reserves()
        our_share = Decimal(position.lp_tokens) / Decimal(total_supply)
        
        our_btcvp = our_share * Decimal(btcvp_reserve) / Decimal(10 ** self.config.btcvp_decimals)
        our_usdc = our_share * Decimal(usdc_reserve) / Decimal(10 ** self.config.usdc_decimals)

        # Calculate value in USDC terms
        btcvp_value = our_btcvp * current_price
        total_value = btcvp_value + our_usdc

        if total_value == 0:
            return True

        btcvp_ratio = btcvp_value / total_value

        # If single-sided > 80% → rebalance
        if btcvp_ratio > self.config.lp_rebalance_threshold:
            logger.info(f"Position {position.id}: BTCvp ratio {btcvp_ratio*100:.1f}% > threshold")
            return True
        if (1 - btcvp_ratio) > self.config.lp_rebalance_threshold:
            logger.info(f"Position {position.id}: USDC ratio {(1-btcvp_ratio)*100:.1f}% > threshold")
            return True

        return False

    def _open_position(self, position: LPPosition, target_price: Decimal):
        """Open a new LP position.
        
        Add liquidity at the current pool ratio, sized according to config.
        """
        amount_per_position = self.config.lp_amount_per_position
        
        # For Uni V2, we need to add both tokens in the current pool ratio
        # Total value = amount_per_position USDC equivalent
        # Split: half in BTCvp value, half in USDC
        usdc_amount_human = amount_per_position / Decimal("2")
        btcvp_amount_human = usdc_amount_human / target_price

        usdc_amount_raw = int(usdc_amount_human * Decimal(10 ** self.config.usdc_decimals))
        btcvp_amount_raw = int(btcvp_amount_human * Decimal(10 ** self.config.btcvp_decimals))

        # Check balances
        btcvp_balance = self.dex.get_token_balance(self.config.btcvp_address)
        usdc_balance = self.dex.get_token_balance(self.config.usdc_address)

        if btcvp_balance < btcvp_amount_raw:
            logger.warning(
                f"Insufficient BTCvp for position {position.id}: "
                f"have {btcvp_balance / 10**self.config.btcvp_decimals:.8f}, "
                f"need {btcvp_amount_human:.8f}"
            )
            return
        if usdc_balance < usdc_amount_raw:
            logger.warning(
                f"Insufficient USDC for position {position.id}: "
                f"have {usdc_balance / 10**self.config.usdc_decimals:.2f}, "
                f"need {usdc_amount_human:.2f}"
            )
            return

        # Slippage protection: accept 3% less than desired
        slippage = Decimal("1") - self.config.slippage_tolerance
        btcvp_min = int(Decimal(btcvp_amount_raw) * slippage)
        usdc_min = int(Decimal(usdc_amount_raw) * slippage)

        logger.info(
            f"Opening position {position.id}: "
            f"{btcvp_amount_human:.8f} BTCvp + {usdc_amount_human:.2f} USDC "
            f"at price {target_price:.2f}"
        )

        try:
            # Get LP balance before
            lp_before = self.dex.get_lp_balance()

            receipt = self.dex.add_liquidity(
                btcvp_amount=btcvp_amount_raw,
                usdc_amount=usdc_amount_raw,
                btcvp_min=btcvp_min,
                usdc_min=usdc_min,
            )

            # Get LP balance after to track position size
            lp_after = self.dex.get_lp_balance()
            position.lp_tokens = lp_after - lp_before
            position.initial_btcvp_amount = btcvp_amount_human
            position.initial_usdc_amount = usdc_amount_human
            position.target_price = target_price
            position.active = True

            logger.info(
                f"Position {position.id} opened: {position.lp_tokens} LP tokens minted"
            )
        except Exception as e:
            logger.error(f"Failed to open position {position.id}: {e}")

    def _rebalance_position(self, position: LPPosition, target_price: Decimal):
        """Rebalance: remove current liquidity, then add new position at current price."""
        # Step 1: Remove existing liquidity
        if position.lp_tokens > 0:
            logger.info(f"Removing position {position.id}: {position.lp_tokens} LP tokens")
            try:
                self.dex.remove_liquidity(
                    lp_amount=position.lp_tokens,
                    btcvp_min=0,  # Accept any amount on removal
                    usdc_min=0,
                )
                logger.info(f"Position {position.id} removed successfully")
            except Exception as e:
                logger.error(f"Failed to remove position {position.id}: {e}")
                return

        # Step 2: Reset position state
        position.lp_tokens = 0
        position.active = False

        # Step 3: Open new position at current target price
        self._open_position(position, target_price)

    def get_status(self) -> dict:
        """Get current LP strategy status for monitoring."""
        pool_price = self.dex.get_pool_price()
        status = {
            "pool_price": float(pool_price),
            "positions": [],
        }
        for p in self.positions:
            status["positions"].append({
                "id": p.id,
                "active": p.active,
                "lp_tokens": p.lp_tokens,
                "target_price": float(p.target_price),
                "initial_btcvp": float(p.initial_btcvp_amount),
                "initial_usdc": float(p.initial_usdc_amount),
            })
        return status
