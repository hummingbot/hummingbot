"""Main entry point for BTCvp Market Maker Bot."""

import asyncio
import logging
import signal
import sys

from .config import Config
from .dex_client import DexClient
from .lp_strategy import LPStrategy
from .price_feed import BTCPriceFeed
from .swap_strategy import SwapStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("btcvp_bot.log"),
    ],
)
logger = logging.getLogger(__name__)


class BTCvpMarketMaker:
    """Main bot orchestrator."""

    def __init__(self):
        self.config = Config()
        self.dex_client = DexClient(self.config)
        self.price_feed = BTCPriceFeed(
            url=self.config.btc_price_url,
            update_interval=self.config.poll_interval / 2,
        )
        self.swap_strategy = SwapStrategy(self.config, self.dex_client, self.price_feed)
        self.lp_strategy = LPStrategy(self.config, self.dex_client, self.price_feed)
        self._running = False

    async def start(self):
        """Start the bot."""
        logger.info("=" * 60)
        logger.info("BTCvp Market Maker Bot Starting")
        logger.info("=" * 60)
        logger.info(f"Chain: Pharos (ID: {self.config.chain_id})")
        logger.info(f"RPC: {self.config.rpc_url}")
        logger.info(f"Pool: {self.config.pool_address}")
        logger.info(f"Poll interval: {self.config.poll_interval}s")
        logger.info(f"Swap threshold: {self.config.swap_price_deviation_threshold * 100}%")
        logger.info(f"LP positions: {self.config.lp_position_count}")
        logger.info(f"LP range: ±{self.config.lp_range_pct * 100}%")
        logger.info("=" * 60)

        # Initialize
        await self.dex_client.initialize()
        await self.price_feed.start()

        # Wait for first price
        logger.info("Waiting for price feed...")
        for _ in range(30):
            if self.price_feed.is_ready:
                break
            await asyncio.sleep(1)

        if not self.price_feed.is_ready:
            logger.error("Price feed failed to initialize after 30s")
            return

        logger.info(f"Price feed ready. BTC price: {self.price_feed.price}")

        # Main loop
        self._running = True
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)

            await asyncio.sleep(self.config.poll_interval)

    async def _tick(self):
        """Single iteration of the bot's main loop."""
        logger.info("-" * 40)

        # 1. Execute swap strategy (price peg maintenance)
        await self.swap_strategy.execute()

        # 2. Execute LP strategy (liquidity management)
        await self.lp_strategy.execute()

        # 3. Log status
        self._log_status()

    def _log_status(self):
        """Log current bot status."""
        pool_price = self.dex_client.get_pool_price()
        target_price = self.price_feed.price

        if target_price:
            deviation = (pool_price - target_price) / target_price * 100
            logger.info(
                f"Status: Pool={pool_price:.2f} Target={target_price:.2f} "
                f"Dev={deviation:+.4f}%"
            )

        lp_status = self.lp_strategy.get_status()
        active_positions = sum(1 for p in lp_status["positions"] if p["active"])
        logger.info(f"LP: {active_positions}/{self.config.lp_position_count} positions active")

    async def stop(self):
        """Stop the bot gracefully."""
        logger.info("Stopping BTCvp Market Maker Bot...")
        self._running = False
        await self.price_feed.stop()
        logger.info("Bot stopped.")


async def main():
    bot = BTCvpMarketMaker()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def shutdown_handler():
        asyncio.ensure_future(bot.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        await bot.start()
    except KeyboardInterrupt:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
