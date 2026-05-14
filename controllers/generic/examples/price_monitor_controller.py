from typing import List

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict, PriceType
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction


class PriceMonitorControllerConfig(ControllerConfigBase):
    controller_name: str = "examples.price_monitor_controller"
    exchanges: list = Field(default=["binance_paper_trade", "kucoin_paper_trade", "gate_io_paper_trade"])
    trading_pair: str = Field(default="ETH-USDT")
    log_interval: int = Field(default=60)  # seconds between price logs

    def update_markets(self, markets: MarketDict) -> MarketDict:
        # Add the trading pair to all exchanges
        for exchange in self.exchanges:
            markets[exchange] = markets.get(exchange, set()) | {self.trading_pair}
        return markets


class PriceMonitorController(ControllerBase):
    def __init__(self, config: PriceMonitorControllerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.last_log_time = 0

    async def update_processed_data(self):
        price_data = {}
        current_time = self.market_data_provider.time()

        # Log prices at specified intervals
        if current_time - self.last_log_time >= self.config.log_interval:
            self.last_log_time = current_time

            for connector_name in self.config.exchanges:
                try:
                    best_ask = self.market_data_provider.get_price_by_type(connector_name, self.config.trading_pair, PriceType.BestAsk)
                    best_bid = self.market_data_provider.get_price_by_type(connector_name, self.config.trading_pair, PriceType.BestBid)
                    mid_price = self.market_data_provider.get_price_by_type(connector_name, self.config.trading_pair, PriceType.MidPrice)

                    price_info = {
                        "best_ask": best_ask,
                        "best_bid": best_bid,
                        "mid_price": mid_price,
                        "spread": best_ask - best_bid if best_ask and best_bid else None,
                        "spread_pct": ((best_ask - best_bid) / mid_price * 100) if best_ask and best_bid and mid_price else None
                    }

                    price_data[connector_name] = price_info

                    # Log to console
                    self.logger().info(f"Connector: {connector_name}")
                    self.logger().info(f"Best ask: {best_ask}")
                    self.logger().info(f"Best bid: {best_bid}")
                    self.logger().info(f"Mid price: {mid_price}")
                    if price_info["spread"]:
                        self.logger().info(f"Spread: {price_info['spread']:.6f} ({price_info['spread_pct']:.3f}%)")

                except Exception as e:
                    self.logger().error(f"Error getting price data for {connector_name}: {e}")
                    price_data[connector_name] = {"error": str(e)}

        self.processed_data = {
            "price_data": price_data,
            "last_log_time": self.last_log_time,
            "trading_pair": self.config.trading_pair
        }

    def determine_executor_actions(self) -> list[ExecutorAction]:
        # This controller is for monitoring only, no trading actions
        return []

    def to_format_status(self) -> List[str]:
        lines = []
        lines.extend(["", f"PRICE MONITOR - {self.config.trading_pair}"])
        lines.extend(["=" * 60])

        if hasattr(self, 'processed_data') and self.processed_data.get("price_data"):
            for connector_name, price_info in self.processed_data["price_data"].items():
                lines.extend([f"\n{connector_name.upper()}:"])

                if "error" in price_info:
                    lines.extend([f"  Error: {price_info['error']}"])
                else:
                    lines.extend([f"  Best Ask: {price_info.get('best_ask', 'N/A')}"])
                    lines.extend([f"  Best Bid: {price_info.get('best_bid', 'N/A')}"])
                    lines.extend([f"  Mid Price: {price_info.get('mid_price', 'N/A')}"])

                    if price_info.get('spread') is not None:
                        lines.extend([f"  Spread: {price_info['spread']:.6f} ({price_info['spread_pct']:.3f}%)"])
        else:
            # Get current prices for display
            for connector_name in self.config.exchanges:
                try:
                    best_ask = self.market_data_provider.get_price_by_type(connector_name, self.config.trading_pair, PriceType.BestAsk)
                    best_bid = self.market_data_provider.get_price_by_type(connector_name, self.config.trading_pair, PriceType.BestBid)
                    mid_price = self.market_data_provider.get_price_by_type(connector_name, self.config.trading_pair, PriceType.MidPrice)

                    lines.extend([f"\n{connector_name.upper()}:"])
                    lines.extend([f"  Best Ask: {best_ask}"])
                    lines.extend([f"  Best Bid: {best_bid}"])
                    lines.extend([f"  Mid Price: {mid_price}"])

                    if best_ask and best_bid and mid_price:
                        spread = best_ask - best_bid
                        spread_pct = spread / mid_price * 100
                        lines.extend([f"  Spread: {spread:.6f} ({spread_pct:.3f}%)"])

                except Exception as e:
                    lines.extend([f"\n{connector_name.upper()}:"])
                    lines.extend([f"  Error: {str(e)}"])

        next_log_time = self.last_log_time + self.config.log_interval
        time_until_next_log = max(0, next_log_time - self.market_data_provider.time())
        lines.extend([f"\nNext price log in: {time_until_next_log:.0f} seconds"])

        return lines
