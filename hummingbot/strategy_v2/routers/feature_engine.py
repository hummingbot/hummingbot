from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import pandas as pd

from hummingbot.strategy_v2.routers.data_types import MarketFeatures

if TYPE_CHECKING:
    from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class RouterFeatureEngine:
    @staticmethod
    def build_features(
        candles: pd.DataFrame,
        active_executors: List[ExecutorInfo],
        timestamp: float,
        mid_price: Optional[float] = None,
        atr_length: int = 14,
        bb_length: int = 20,
        ema_fast_length: int = 12,
        ema_slow_length: int = 26,
        range_length: int = 50,
    ) -> MarketFeatures:
        if candles is None or candles.empty or len(candles) < max(atr_length, bb_length, ema_slow_length, range_length):
            return MarketFeatures(
                timestamp=timestamp,
                mid_price=float(mid_price or 0),
                active_executor_count=len(active_executors),
                active_net_pnl_pct=RouterFeatureEngine._active_net_pnl_pct(active_executors),
                active_strategy=RouterFeatureEngine._active_strategy(active_executors),
                enough_data=False,
            )

        df = candles.copy()
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series([0.0] * len(df), index=df.index)

        prev_close = close.shift(1)
        true_range = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr = true_range.rolling(atr_length).mean().iloc[-1]

        bb_mid = close.rolling(bb_length).mean()
        bb_std = close.rolling(bb_length).std()
        bb_width_pct = ((bb_std.iloc[-1] * 4) / bb_mid.iloc[-1]) if bb_mid.iloc[-1] else 0

        ema_fast = close.ewm(span=ema_fast_length, adjust=False).mean()
        ema_slow = close.ewm(span=ema_slow_length, adjust=False).mean()
        ema_slope_pct = (ema_fast.iloc[-1] - ema_fast.iloc[-4]) / close.iloc[-1] if len(ema_fast) >= 4 and close.iloc[-1] else 0

        volume_mean = volume.rolling(range_length).mean().iloc[-1]
        volume_std = volume.rolling(range_length).std().iloc[-1]
        volume_zscore = (volume.iloc[-1] - volume_mean) / volume_std if volume_std and not pd.isna(volume_std) else 0

        range_high = high.tail(range_length).max()
        range_low = low.tail(range_length).min()
        range_width = range_high - range_low
        close_price = close.iloc[-1]
        range_position = (close_price - range_low) / range_width if range_width else 0.5
        resolved_mid_price = float(mid_price or close_price)

        return MarketFeatures(
            timestamp=timestamp,
            mid_price=resolved_mid_price,
            close_price=float(close_price),
            atr_pct=float(atr / close_price) if close_price else 0,
            bb_width_pct=float(bb_width_pct) if not pd.isna(bb_width_pct) else 0,
            ema_fast=float(ema_fast.iloc[-1]),
            ema_slow=float(ema_slow.iloc[-1]),
            ema_slope_pct=float(ema_slope_pct) if not pd.isna(ema_slope_pct) else 0,
            volume_zscore=float(volume_zscore) if not pd.isna(volume_zscore) else 0,
            range_high=float(range_high),
            range_low=float(range_low),
            range_position=float(range_position),
            active_executor_count=len(active_executors),
            active_net_pnl_pct=RouterFeatureEngine._active_net_pnl_pct(active_executors),
            active_strategy=RouterFeatureEngine._active_strategy(active_executors),
            enough_data=True,
        )

    @staticmethod
    def _active_net_pnl_pct(active_executors: List[ExecutorInfo]) -> float:
        if not active_executors:
            return 0
        return float(sum(executor.net_pnl_pct for executor in active_executors))

    @staticmethod
    def _active_strategy(active_executors: List[ExecutorInfo]) -> Optional[str]:
        if not active_executors:
            return None
        executor_type = active_executors[0].type
        if executor_type == "grid_executor":
            return "grid_strike"
        if executor_type == "position_executor":
            side = active_executors[0].side
            side_name = getattr(side, "name", str(side))
            return "trend_short" if side_name == "SELL" else "trend_long"
        if executor_type == "arbitrage_executor":
            return "arbitrage_controller"
        return executor_type
