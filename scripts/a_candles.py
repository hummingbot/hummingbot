from typing import Dict

import random
import pandas as pd
import pandas_ta as ta  # noqa: F401

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class A(ScriptStrategyBase):
    maker_pair = "ETH-USDT"
    maker_exchange = "kucoin_paper_trade"
    markets = {maker_exchange: {maker_pair}}

    # 订阅K线数据
    candles = CandlesFactory.get_candle(
        CandlesConfig(
            connector="binance_perpetual",
            trading_pair=maker_pair,
            interval="1m",
            max_records="100",
        )
    )

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.candles.start()

    def on_tick(self):
        """1秒执行一次心跳"""
        # 每30秒执行一次
        if self.current_timestamp % 30 == 0:
            # 随机修改测试
            pairs = ["BTC-USDT", "ETH-USDT", "DOGE-USDT"]
            pair = random.choice(pairs)
            self.maker_pair = pair
            self.markets = {self.maker_exchange: {self.maker_pair}}
            self.notify_hb_app_with_timestamp(f"修改交易对为：{self.maker_pair}")
            self.candles.stop()
            self.candles = CandlesFactory.get_candle(
                CandlesConfig(
                    connector="binance_perpetual",
                    trading_pair=self.maker_pair,
                    interval="1m",
                    max_records="100",
                )
            )
            self.candles.start()

    def on_stop(self):
        """结束时运行"""
        self.candles.stop()

        # return super().on_stop()

    def format_status(self) -> str:
        """
        Displays the three candlesticks involved in the script with RSI, BBANDS and EMA.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."

        lines = []
        if self.all_candles_ready:
            lines.extend(
                [
                    "\n############################################ Market Data ############################################\n"
                ]
            )
            for candles in [
                self.candles,
            ]:
                candles_df = candles.candles_df
                # Let's add some technical indicators
                # candles_df.ta.rsi(length=14, append=True)
                # candles_df.ta.bbands(length=20, std=2, append=True)
                # candles_df.ta.ema(length=14, offset=None, append=True)
                # candles_df["timestamp"] = pd.to_datetime(candles_df["timestamp"], unit="ms")
                # 转为上海时区
                candles_df["timestamp"] = (
                    pd.to_datetime(candles_df["timestamp"], unit="ms")
                    .dt.tz_localize("UTC")
                    .dt.tz_convert("Asia/Shanghai")
                )
                lines.extend([f"Candles: {candles.name} | Interval: {candles.interval}"])
                lines.extend(["    " + line for line in candles_df.tail().to_string(index=False).split("\n")])
                lines.extend(
                    [
                        "\n-----------------------------------------------------------------------------------------------------------\n"
                    ]
                )
        else:
            lines.extend(["", "  No data collected."])

        return "\n".join(lines)

    @property
    def all_candles_ready(self):
        """
        Checks if the candlesticks are full.
        :return:
        """
        return all(
            [
                self.candles.is_ready,
            ]
        )
