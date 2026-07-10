"""Swap strategy: maintain BTCvp price peg to BTC via swap trades."""

import logging
from decimal import Decimal
from typing import Optional

from .config import Config
from .dex_client import DexClient
from .price_feed import BTCPriceFeed

logger = logging.getLogger(__name__)


class SwapStrategy:
    """
    Maintains BTCvp/USDC pool price pegged to BTC/USDC.
    
    Logic:
    - Get BTC target price from oracle
    - Get current pool price of BTCvp in USDC
    - If pool price deviates from target by more than threshold:
      - Pool price too HIGH (BTCvp overvalued) → sell BTCvp for USDC (increases BTCvp supply in pool)
      - Pool price too LOW (BTCvp undervalued) → buy BTCvp with USDC (decreases BTCvp supply in pool)
    """

    def __init__(self, config: Config, dex_client: DexClient, price_feed: BTCPriceFeed):
        self.config = config
        self.dex = dex_client
        self.price_feed = price_feed

    async def execute(self) -> Optional[dict]:
        """Check price deviation and execute swap if needed.
        
        Returns transaction receipt if a swap was executed, None otherwise.
        """
        if not self.price_feed.is_ready:
            logger.warning("Price feed not ready, skipping swap check")
            return None

        target_price = self.price_feed.price  # BTC price in USDC
        pool_price = self.dex.get_pool_price()  # BTCvp price in USDC

        if pool_price == 0:
            logger.warning("Pool price is 0, skipping")
            return None

        # Calculate deviation: positive means pool price is higher than target
        deviation = (pool_price - target_price) / target_price

        logger.info(
            f"Price check - Target: {target_price:.2f} USDC, "
            f"Pool: {pool_price:.2f} USDC, "
            f"Deviation: {deviation * 100:.4f}%"
        )

        threshold = self.config.swap_price_deviation_threshold

        if abs(deviation) < threshold:
            logger.info(f"Deviation {abs(deviation)*100:.4f}% < threshold {threshold*100:.2f}%, no action needed")
            return None

        # Calculate swap amount - scale with deviation magnitude
        # Larger deviation = larger swap to correct faster
        deviation_multiplier = min(abs(deviation) / threshold, Decimal("3"))  # Cap at 3x
        base_amount_usdc = self.config.swap_amount_usdc * deviation_multiplier

        if deviation > 0:
            # Pool price too high → sell BTCvp to push price down
            return self._sell_btcvp(base_amount_usdc, target_price)
        else:
            # Pool price too low → buy BTCvp to push price up
            return self._buy_btcvp(base_amount_usdc, target_price)

    def _sell_btcvp(self, amount_usdc: Decimal, target_price: Decimal) -> Optional[dict]:
        """Sell BTCvp for USDC to push pool price down."""
        # Calculate BTCvp amount equivalent to USDC amount at target price
        btcvp_amount_human = amount_usdc / target_price
        btcvp_amount_raw = int(btcvp_amount_human * Decimal(10 ** self.config.btcvp_decimals))

        # Check balance
        balance = self.dex.get_token_balance(self.config.btcvp_address)
        if balance < btcvp_amount_raw:
            logger.warning(
                f"Insufficient BTCvp balance: have {balance / 10**self.config.btcvp_decimals:.8f}, "
                f"need {btcvp_amount_human:.8f}"
            )
            # Use available balance if it's at least 10% of target
            if balance > btcvp_amount_raw // 10:
                btcvp_amount_raw = balance
            else:
                return None

        # Calculate minimum output with slippage tolerance
        expected_out = self.dex.get_amounts_out(
            btcvp_amount_raw,
            [self.config.btcvp_address, self.config.usdc_address],
        )
        min_out = int(expected_out[1] * (1 - float(self.config.slippage_tolerance)))

        logger.info(
            f"Selling {btcvp_amount_raw / 10**self.config.btcvp_decimals:.8f} BTCvp, "
            f"expected {expected_out[1] / 10**self.config.usdc_decimals:.2f} USDC"
        )

        try:
            receipt = self.dex.swap_exact_tokens(
                token_in=self.config.btcvp_address,
                token_out=self.config.usdc_address,
                amount_in=btcvp_amount_raw,
                min_amount_out=min_out,
            )
            logger.info("BTCvp sell swap completed successfully")
            return receipt
        except Exception as e:
            logger.error(f"Swap failed: {e}")
            return None

    def _buy_btcvp(self, amount_usdc: Decimal, target_price: Decimal) -> Optional[dict]:
        """Buy BTCvp with USDC to push pool price up."""
        usdc_amount_raw = int(amount_usdc * Decimal(10 ** self.config.usdc_decimals))

        # Check USDC balance
        balance = self.dex.get_token_balance(self.config.usdc_address)
        if balance < usdc_amount_raw:
            logger.warning(
                f"Insufficient USDC balance: have {balance / 10**self.config.usdc_decimals:.2f}, "
                f"need {amount_usdc:.2f}"
            )
            if balance > usdc_amount_raw // 10:
                usdc_amount_raw = balance
            else:
                return None

        # Calculate minimum output with slippage tolerance
        expected_out = self.dex.get_amounts_out(
            usdc_amount_raw,
            [self.config.usdc_address, self.config.btcvp_address],
        )
        min_out = int(expected_out[1] * (1 - float(self.config.slippage_tolerance)))

        logger.info(
            f"Buying BTCvp with {usdc_amount_raw / 10**self.config.usdc_decimals:.2f} USDC, "
            f"expected {expected_out[1] / 10**self.config.btcvp_decimals:.8f} BTCvp"
        )

        try:
            receipt = self.dex.swap_exact_tokens(
                token_in=self.config.usdc_address,
                token_out=self.config.btcvp_address,
                amount_in=usdc_amount_raw,
                min_amount_out=min_out,
            )
            logger.info("BTCvp buy swap completed successfully")
            return receipt
        except Exception as e:
            logger.error(f"Swap failed: {e}")
            return None
