from typing import List

import pandas as pd
from pydantic import Field

from hummingbot.core.data_type.common import MarketDict, PriceType
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction


class MarketStatusControllerConfig(ControllerConfigBase):
    controller_name: str = "examples.market_status_controller"
    exchanges: list = Field(default=["binance_paper_trade", "kucoin_paper_trade", "gate_io_paper_trade"])
    trading_pairs: list = Field(default=["ETH-USDT", "BTC-USDT", "POL-USDT", "AVAX-USDT", "WLD-USDT", "DOGE-USDT", "SHIB-USDT", "XRP-USDT", "SOL-USDT"])

    def update_markets(self, markets: MarketDict) -> MarketDict:
        # Add all combinations of exchanges and trading pairs
        for exchange in self.exchanges:
            markets[exchange] = markets.get(exchange, set()) | set(self.trading_pairs)
        return markets


class MarketStatusController(ControllerBase):
    def __init__(self, config: MarketStatusControllerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

    @property
    def ready_to_trade(self) -> bool:
        """
        Check if all configured exchanges and trading pairs are ready for trading.
        """
        try:
            for exchange in self.config.exchanges:
                for trading_pair in self.config.trading_pairs:
                    # Try to get price data to verify connectivity
                    price = self.market_data_provider.get_price_by_type(exchange, trading_pair, PriceType.MidPrice)
                    if price is None:
                        return False
            return True
        except Exception:
            return False

    async def update_processed_data(self):
        market_status_data = {}
        if self.ready_to_trade:
            try:
                market_status_df = self.get_market_status_df_with_depth()
                market_status_data = {
                    "market_status_df": market_status_df,
                    "ready_to_trade": True
                }
            except Exception as e:
                self.logger().error(f"Error getting market status: {e}")
                market_status_data = {
                    "error": str(e),
                    "ready_to_trade": False
                }
        else:
            market_status_data = {"ready_to_trade": False}

        self.processed_data = market_status_data

    def determine_executor_actions(self) -> list[ExecutorAction]:
        # This controller is for monitoring only, no trading actions
        return []

    def to_format_status(self) -> List[str]:
        if not self.ready_to_trade:
            return ["Market connectors are not ready."]

        lines = []
        lines.extend(["", "  Market Status Data Frame:"])

        try:
            market_status_df = self.get_market_status_df_with_depth()
            lines.extend(["    " + line for line in market_status_df.to_string(index=False).split("\n")])
        except Exception as e:
            lines.extend([f"    Error: {str(e)}"])

        return lines

    def get_market_status_df_with_depth(self):
        """
        Create a DataFrame with market status information including prices and volumes.
        """
        data = []
        for exchange in self.config.exchanges:
            for trading_pair in self.config.trading_pairs:
                try:
                    best_ask = self.market_data_provider.get_price_by_type(exchange, trading_pair, PriceType.BestAsk)
                    best_bid = self.market_data_provider.get_price_by_type(exchange, trading_pair, PriceType.BestBid)
                    mid_price = self.market_data_provider.get_price_by_type(exchange, trading_pair, PriceType.MidPrice)

                    # Calculate volumes at +/-1% from mid price
                    volume_plus_1 = None
                    volume_minus_1 = None
                    if mid_price:
                        try:
                            price_plus_1 = mid_price * 1.01
                            price_minus_1 = mid_price * 0.99
                            volume_plus_1 = self.market_data_provider.get_volume_for_price(exchange, trading_pair, float(price_plus_1), True)
                            volume_minus_1 = self.market_data_provider.get_volume_for_price(exchange, trading_pair, float(price_minus_1), False)
                        except Exception:
                            volume_plus_1 = "N/A"
                            volume_minus_1 = "N/A"

                    data.append({
                        "Exchange": exchange.replace("_paper_trade", "").title(),
                        "Market": trading_pair,
                        "Best Bid": best_bid,
                        "Best Ask": best_ask,
                        "Mid Price": mid_price,
                        "Volume (+1%)": volume_plus_1,
                        "Volume (-1%)": volume_minus_1
                    })
                except Exception as e:
                    self.logger().error(f"Error getting market status: {e}")
                    data.append({
                        "Exchange": exchange.replace("_paper_trade", "").title(),
                        "Market": trading_pair,
                        "Best Bid": "Error",
                        "Best Ask": "Error",
                        "Mid Price": "Error",
                        "Volume (+1%)": "Error",
                        "Volume (-1%)": "Error"
                    })

        market_status_df = pd.DataFrame(data)
        market_status_df.sort_values(by=["Market"], inplace=True)
        return market_status_df
