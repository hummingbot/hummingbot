from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestPositionHold
from hummingbot.strategy_v2.controllers.controller_base import ControllerConfigBase
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class BacktestingResult:
    """Wraps backtesting output and provides analysis / plotting helpers."""

    def __init__(self, backtesting_result: Dict, controller_config: ControllerConfigBase):
        self.processed_data: pd.DataFrame = backtesting_result["processed_data"]["features"]
        self.results: Dict = backtesting_result["results"]
        self.executors: List[ExecutorInfo] = backtesting_result["executors"]
        self.position_holds: List[BacktestPositionHold] = backtesting_result.get("position_holds", [])
        self.position_held_timeseries: List[Dict] = backtesting_result.get("position_held_timeseries", [])
        self.pnl_timeseries: List[Dict] = backtesting_result.get("pnl_timeseries", [])
        self.controller_config = controller_config

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_results_summary(self, results: Optional[Dict] = None) -> str:
        if results is None:
            results = self.results
        net_pnl_quote = results["net_pnl_quote"]
        net_pnl_pct = results["net_pnl"]
        max_drawdown = results["max_drawdown_usd"]
        max_drawdown_pct = results["max_drawdown_pct"]
        total_volume = results["total_volume"]
        sharpe_ratio = results["sharpe_ratio"]
        profit_factor = results["profit_factor"]
        total_executors = results["total_executors"]
        accuracy_long = results["accuracy_long"]
        accuracy_short = results["accuracy_short"]
        total_fees = results.get("total_fees_quote", 0)
        unrealized_pnl = results.get("unrealized_pnl_quote", 0)
        position_realized_pnl = results.get("position_realized_pnl_quote", 0)
        close_types = results.get("close_types", {})
        if not isinstance(close_types, dict):
            close_types = {}
        take_profit = close_types.get("TAKE_PROFIT", 0)
        stop_loss = close_types.get("STOP_LOSS", 0)
        time_limit = close_types.get("TIME_LIMIT", 0)
        trailing_stop = close_types.get("TRAILING_STOP", 0)
        early_stop = close_types.get("EARLY_STOP", 0)
        position_hold = close_types.get("POSITION_HOLD", 0)
        return (
            f"Net PNL: ${net_pnl_quote:.2f} ({net_pnl_pct * 100:.2f}%) | "
            f"Total Fees: ${total_fees:.2f} | "
            f"Unrealized PNL: ${unrealized_pnl:.2f} | "
            f"Position Realized PNL: ${position_realized_pnl:.2f} | "
            f"Max Drawdown: ${max_drawdown:.2f} ({max_drawdown_pct * 100:.2f}%)\n"
            f"Total Volume ($): {total_volume:.2f} | Sharpe Ratio: {sharpe_ratio:.2f} | "
            f"Profit Factor: {profit_factor:.2f}\n"
            f"Total Executors: {total_executors} | Accuracy Long: {accuracy_long:.2f} | "
            f"Accuracy Short: {accuracy_short:.2f}\n"
            f"Close Types: TP: {take_profit} | SL: {stop_loss} | TL: {time_limit} | "
            f"Trailing: {trailing_stop} | Early Stop: {early_stop} | Position Hold: {position_hold}\n"
            f"Open Position Holds: {sum(1 for ph in self.position_holds if not ph.is_closed)}"
        )

    # ------------------------------------------------------------------
    # DataFrames
    # ------------------------------------------------------------------

    @property
    def executors_df(self) -> pd.DataFrame:
        if not self.executors:
            return pd.DataFrame()
        return pd.DataFrame([e.to_dict() for e in self.executors])

    # ------------------------------------------------------------------
    # Plotly figure
    # ------------------------------------------------------------------

    def get_backtesting_figure(self):
        """Build a 3-row Plotly figure: price+executors, cumulative PNL, position held."""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError:
            raise ImportError("plotly is required for charting: pip install plotly")

        has_holds = len(self.position_held_timeseries) > 0
        n_rows = 3 if has_holds else 2
        row_heights = [0.55, 0.2, 0.25] if has_holds else [0.7, 0.3]
        subtitles = ["", "", ""] if has_holds else ["", ""]

        specs = [[{"secondary_y": True}] for _ in range(n_rows)]
        fig = make_subplots(
            rows=n_rows, cols=1, shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=subtitles,
            row_heights=row_heights,
            specs=specs,
        )

        df = self.processed_data.copy()
        df.index = pd.to_datetime(df["timestamp"], unit="s")

        # --- Row 1: Candlestick ---
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["open"], high=df["high"],
                low=df["low"], close=df["close"],
                increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
                increasing_fillcolor="#26a69a", decreasing_fillcolor="#ef5350",
                name="Price",
            ),
            row=1, col=1,
        )

        # --- Row 1: Executor entry/exit markers ---
        self._add_executor_markers(fig, row=1, col=1)

        # --- Row 1: Grid levels and fills (if any grid executors) ---
        self._add_grid_visualization(fig, row=1, col=1)

        # --- Row 2: Cumulative PNL ---
        self._add_cumulative_pnl(fig, row=2, col=1)

        # --- Row 3: Position held over time ---
        if has_holds:
            self._add_position_held_chart(fig, df, row=3, col=1)

        # --- Layout ---
        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor="#0e1117",
            paper_bgcolor="#0e1117",
            font=dict(color="#e0e0e0", size=11),
            height=950, width=1400,
            margin=dict(l=60, r=30, t=120, b=40),
            hovermode="x unified",
            showlegend=True,
            legend=dict(
                orientation="h", yanchor="bottom", y=1.06,
                xanchor="center", x=0.5,
                font=dict(size=10),
            ),
            title=dict(
                text=f"{self.controller_config.controller_name} | "
                     f"{getattr(self.controller_config, 'trading_pair', '')} | "
                     f"PnL: ${self.results['net_pnl_quote']:.2f} "
                     f"({self.results['net_pnl'] * 100:.2f}%) | "
                     f"Volume: ${self.results.get('total_volume', 0):,.0f}",
                font=dict(size=14),
                y=0.99, yanchor="top",
            ),
        )

        # Axis styling
        axis_common = dict(gridcolor="#1e2530", zerolinecolor="#2a3441")
        fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
        for r in range(1, n_rows + 1):
            fig.update_xaxes(**axis_common, row=r, col=1)
            fig.update_yaxes(**axis_common, row=r, col=1)

        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="PnL ($)", row=2, col=1)
        fig.update_yaxes(title_text="Volume ($)", row=2, col=1, secondary_y=True,
                         showgrid=False)
        if has_holds:
            fig.update_yaxes(title_text="Position ($)", row=3, col=1)

        return fig

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_executor_markers(self, fig, row=1, col=1):
        """Add entry/exit markers for non-hold executors (TP, SL, TL, etc).
        Position hold executors only get an entry marker (no exit line)."""
        try:
            import plotly.graph_objects as go
        except ImportError:
            return

        # Collect points by category for batch plotting
        categories = {
            "Hold Buy": {"entries": [], "exits": [], "pnls": [], "color": "#42a5f5", "symbol": "circle", "dash": "dot"},
            "Hold Sell": {"entries": [], "exits": [], "pnls": [], "color": "#ab47bc", "symbol": "circle", "dash": "dot"},
            "Early Stop Buy": {"entries": [], "exits": [], "pnls": [], "color": "#e0e0e0", "symbol": "x", "dash": "dash"},
            "Early Stop Sell": {"entries": [], "exits": [], "pnls": [], "color": "#e0e0e0", "symbol": "x", "dash": "dash"},
            "TP Buy": {"entries": [], "exits": [], "pnls": [], "color": "#26a69a", "symbol": "triangle-up", "dash": None},
            "TP Sell": {"entries": [], "exits": [], "pnls": [], "color": "#ef5350", "symbol": "triangle-down", "dash": None},
            "SL Buy": {"entries": [], "exits": [], "pnls": [], "color": "#ff6d00", "symbol": "triangle-up", "dash": None},
            "SL Sell": {"entries": [], "exits": [], "pnls": [], "color": "#ff6d00", "symbol": "triangle-down", "dash": None},
            "Other Buy": {"entries": [], "exits": [], "pnls": [], "color": "#78909c", "symbol": "triangle-up", "dash": None},
            "Other Sell": {"entries": [], "exits": [], "pnls": [], "color": "#78909c", "symbol": "triangle-down", "dash": None},
        }

        for executor in self.executors:
            if executor.close_timestamp is None:
                continue

            is_buy = executor.side == TradeType.BUY
            side_label = "Buy" if is_buy else "Sell"

            if executor.close_type == CloseType.POSITION_HOLD:
                key = f"Hold {side_label}"
            elif executor.close_type == CloseType.EARLY_STOP:
                key = f"Early Stop {side_label}"
            elif executor.close_type == CloseType.TAKE_PROFIT:
                key = f"TP {side_label}"
            elif executor.close_type == CloseType.STOP_LOSS:
                key = f"SL {side_label}"
            else:
                key = f"Other {side_label}"

            # For entry price: prefer average price, fall back to config entry_price
            entry_price = executor.custom_info.get("current_position_average_price")
            if entry_price is None:
                entry_price = getattr(executor.config, "entry_price", None)
            if entry_price is None:
                entry_price = executor.custom_info.get("close_price")

            # For exit price: unfilled early stops use entry_price (horizontal line at order price)
            if executor.filled_amount_quote == 0 and executor.close_type == CloseType.EARLY_STOP:
                exit_price = entry_price
            else:
                exit_price = executor.custom_info.get("close_price")
                if exit_price is None:
                    exit_price = entry_price

            if entry_price is None or exit_price is None:
                continue

            # Skip unfilled executors except early stops (show them as horizontal lines)
            if executor.filled_amount_quote == 0 and executor.close_type != CloseType.EARLY_STOP:
                continue

            entry_time = pd.to_datetime(executor.timestamp, unit="s")
            exit_time = pd.to_datetime(executor.close_timestamp, unit="s")
            categories[key]["entries"].append((entry_time, entry_price))
            categories[key]["exits"].append((exit_time, exit_price))
            categories[key]["pnls"].append(float(executor.net_pnl_quote))

        for label, data in categories.items():
            if not data["entries"]:
                continue
            entry_x, entry_y = zip(*data["entries"])
            exit_x, exit_y = zip(*data["exits"])
            pnls = data["pnls"]

            # Entry-to-exit lines
            category_dash = data.get("dash")
            for i in range(len(entry_x)):
                # Use actual PnL to determine color, not price comparison
                # (close_price can be slightly below entry for TP buys due to fee accounting)
                is_profit = pnls[i] >= 0
                if category_dash:
                    line_color = data["color"]
                    line_dash = category_dash
                    line_width = 1
                else:
                    line_color = "#26a69a" if is_profit else "#ef5350"
                    line_dash = "solid"
                    line_width = 1.5
                fig.add_trace(
                    go.Scatter(
                        x=[entry_x[i], exit_x[i]],
                        y=[float(entry_y[i]), float(exit_y[i])],
                        mode="lines",
                        line=dict(color=line_color, width=line_width, dash=line_dash),
                        showlegend=False, hoverinfo="skip",
                    ),
                    row=row, col=col,
                )

            # Exit markers
            fig.add_trace(
                go.Scatter(
                    x=list(exit_x), y=[float(p) for p in exit_y],
                    mode="markers",
                    marker=dict(color=data["color"], size=7, symbol=data["symbol"]),
                    name=label,
                ),
                row=row, col=col,
            )

    def _add_cumulative_pnl(self, fig, row=2, col=1):
        try:
            import plotly.graph_objects as go
        except ImportError:
            return

        # Use pnl_timeseries if available — includes executor + position PnL at every tick
        if self.pnl_timeseries:
            pnl_df = pd.DataFrame(self.pnl_timeseries)
            pnl_df["dt"] = pd.to_datetime(pnl_df["timestamp"], unit="s")

            # Total PnL line (executor realized + position realized + position unrealized)
            fig.add_trace(
                go.Scatter(
                    x=pnl_df["dt"], y=pnl_df["total_pnl"],
                    mode="lines", line=dict(color="#ffd54f", width=2),
                    fill="tozeroy", fillcolor="rgba(255,213,79,0.1)",
                    name="Total PnL",
                ),
                row=row, col=col,
            )
            # Executor realized PnL line
            fig.add_trace(
                go.Scatter(
                    x=pnl_df["dt"], y=pnl_df["executor_realized_pnl"],
                    mode="lines", line=dict(color="#26a69a", width=1.5, dash="dot"),
                    name="Executor Realized PnL",
                ),
                row=row, col=col,
            )
            # Position realized PnL line (from buy/sell netting)
            fig.add_trace(
                go.Scatter(
                    x=pnl_df["dt"], y=pnl_df["position_realized_pnl"],
                    mode="lines", line=dict(color="#42a5f5", width=1.5, dash="dot"),
                    name="Position Realized PnL",
                ),
                row=row, col=col,
            )
            # Position unrealized PnL line (from open net position)
            fig.add_trace(
                go.Scatter(
                    x=pnl_df["dt"], y=pnl_df["position_unrealized_pnl"],
                    mode="lines", line=dict(color="#ab47bc", width=1.5, dash="dot"),
                    name="Position Unrealized PnL",
                ),
                row=row, col=col,
            )
            # Active executors count (shown as subtle filled area)
            if "active_executors" in pnl_df.columns:
                # Scale to ~20% of PnL y-range so it stays in the background
                pnl_range = max(abs(pnl_df["total_pnl"].max()), abs(pnl_df["total_pnl"].min()), 1)
                max_active = max(pnl_df["active_executors"].max(), 1)
                scale = pnl_range * 0.3 / max_active
                fig.add_trace(
                    go.Scatter(
                        x=pnl_df["dt"],
                        y=pnl_df["active_executors"] * scale,
                        mode="lines", line=dict(color="rgba(255,255,255,0.2)", width=0),
                        fill="tozeroy", fillcolor="rgba(255,255,255,0.07)",
                        name="Active Executors",
                        hovertemplate="Active: %{customdata}<extra></extra>",
                        customdata=pnl_df["active_executors"],
                    ),
                    row=row, col=col,
                )
            # Cumulative volume on secondary y-axis
            if "cumulative_volume" in pnl_df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=pnl_df["dt"],
                        y=pnl_df["cumulative_volume"],
                        mode="lines", line=dict(color="#80cbc4", width=1.5, dash="dashdot"),
                        name="Cumulative Volume",
                        hovertemplate="Volume: $%{y:,.0f}<extra></extra>",
                    ),
                    row=row, col=col, secondary_y=True,
                )
        else:
            # Fallback: use executor-level PnL (excludes POSITION_HOLD)
            closed = [e for e in self.executors
                      if e.close_timestamp is not None and e.filled_amount_quote > 0
                      and e.close_type != CloseType.POSITION_HOLD]
            if not closed:
                fig.add_hline(y=0, line_dash="dot", line_color="#555", row=row, col=col)
                return
            closed.sort(key=lambda e: e.close_timestamp)
            timestamps = pd.to_datetime([e.close_timestamp for e in closed], unit="s")
            pnl = np.array([float(e.net_pnl_quote) for e in closed])
            cum_pnl = np.cumsum(pnl)
            fig.add_trace(
                go.Scatter(
                    x=timestamps, y=cum_pnl,
                    mode="lines", line=dict(color="#ffd54f", width=2),
                    fill="tozeroy", fillcolor="rgba(255,213,79,0.1)",
                    name="Cum. PnL",
                ),
                row=row, col=col,
            )

        fig.add_hline(y=0, line_dash="dot", line_color="#555", row=row, col=col)

    def _add_position_held_chart(self, fig, df: pd.DataFrame, row=3, col=1):
        """Plot position held over time from the tick-level timeseries."""
        try:
            import plotly.graph_objects as go
        except ImportError:
            return

        if not self.position_held_timeseries:
            return

        ts_df = pd.DataFrame(self.position_held_timeseries)
        ts_df["dt"] = pd.to_datetime(ts_df["timestamp"], unit="s")

        # Long position area
        fig.add_trace(
            go.Scatter(
                x=ts_df["dt"], y=ts_df["long_amount"],
                mode="lines", line=dict(color="#26a69a", width=0),
                fill="tozeroy", fillcolor="rgba(38,166,154,0.3)",
                name="Long Held",
            ),
            row=row, col=col,
        )
        # Short position area (negative)
        if ts_df["short_amount"].sum() > 0:
            fig.add_trace(
                go.Scatter(
                    x=ts_df["dt"], y=-ts_df["short_amount"],
                    mode="lines", line=dict(color="#ef5350", width=0),
                    fill="tozeroy", fillcolor="rgba(239,83,80,0.3)",
                    name="Short Held",
                ),
                row=row, col=col,
            )
        # Net position line
        fig.add_trace(
            go.Scatter(
                x=ts_df["dt"], y=ts_df["net_amount"],
                mode="lines", line=dict(color="#e0e0e0", width=1.5),
                name="Net Position",
            ),
            row=row, col=col,
        )
        # Unrealized PnL on secondary y-axis via a separate trace
        fig.add_trace(
            go.Scatter(
                x=ts_df["dt"], y=ts_df["unrealized_pnl"],
                mode="lines", line=dict(color="#ffd54f", width=1.5, dash="dot"),
                name="Unrealized PnL",
            ),
            row=row, col=col,
        )
        fig.add_hline(y=0, line_dash="dot", line_color="#555", row=row, col=col)

    def _add_grid_visualization(self, fig, row=1, col=1):
        """Draw grid level lines and entry/TP fill markers for grid executors."""
        try:
            import plotly.graph_objects as go
        except ImportError:
            return

        # Collect grid data from all executors that have it
        grid_executors = [
            e for e in self.executors
            if e.custom_info.get("grid_level_prices")
        ]
        if not grid_executors:
            return

        # Aggregate fill markers across all executors to avoid per-executor legend entries
        all_entry_x, all_entry_y, all_entry_text = [], [], []
        all_tp_x, all_tp_y, all_tp_text = [], [], []
        first_executor = True

        for executor in grid_executors:
            level_prices = executor.custom_info["grid_level_prices"]
            tp_prices = executor.custom_info.get("grid_tp_prices", [])
            fill_events = executor.custom_info.get("fill_events", [])
            grid_side = executor.custom_info.get("grid_side", "BUY")

            start_dt = pd.to_datetime(executor.timestamp, unit="s")
            end_dt = pd.to_datetime(
                executor.close_timestamp if executor.close_timestamp else executor.timestamp,
                unit="s",
            )

            # --- Grid level lines (entry prices) ---
            for i, price in enumerate(level_prices):
                fig.add_trace(
                    go.Scatter(
                        x=[start_dt, end_dt], y=[price, price],
                        mode="lines",
                        line=dict(color="rgba(100,181,246,0.35)", width=1, dash="dash"),
                        showlegend=(first_executor and i == 0),
                        legendgroup="grid_level",
                        name="Grid Level",
                        hoverinfo="y",
                    ),
                    row=row, col=col,
                )

            # --- TP level lines ---
            for i, tp_price in enumerate(tp_prices):
                fig.add_trace(
                    go.Scatter(
                        x=[start_dt, end_dt], y=[tp_price, tp_price],
                        mode="lines",
                        line=dict(color="rgba(255,183,77,0.25)", width=1, dash="dot"),
                        showlegend=(first_executor and i == 0),
                        legendgroup="tp_level",
                        name="TP Level",
                        hoverinfo="y",
                    ),
                    row=row, col=col,
                )

            # --- Limit price line ---
            grid_limit_price = executor.custom_info.get("grid_limit_price")
            if grid_limit_price is not None:
                fig.add_trace(
                    go.Scatter(
                        x=[start_dt, end_dt], y=[grid_limit_price, grid_limit_price],
                        mode="lines",
                        line=dict(color="rgba(239,83,80,0.7)", width=1.5, dash="dashdot"),
                        showlegend=first_executor,
                        legendgroup="limit_price",
                        name="Limit Price",
                        hoverinfo="y",
                    ),
                    row=row, col=col,
                )

            # --- Executor boundary marker (vertical line at start) ---
            exec_idx = grid_executors.index(executor) + 1
            y_min = min(level_prices) if level_prices else 0
            y_max = max(tp_prices) if tp_prices else (max(level_prices) if level_prices else 0)
            fig.add_trace(
                go.Scatter(
                    x=[start_dt, start_dt], y=[y_min, y_max],
                    mode="lines+text",
                    line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dot"),
                    text=[f"#{exec_idx}", ""],
                    textposition="top center",
                    textfont=dict(size=9, color="rgba(255,255,255,0.6)"),
                    showlegend=(first_executor),
                    legendgroup="exec_boundary",
                    name="Executor Start",
                    hovertext=f"Executor #{exec_idx} start",
                    hoverinfo="text",
                ),
                row=row, col=col,
            )

            # --- Collect fill markers ---
            for ev in fill_events:
                dt = pd.to_datetime(ev["timestamp"], unit="s")
                if ev["side"] == "entry":
                    all_entry_x.append(dt)
                    all_entry_y.append(ev["price"])
                    all_entry_text.append(f"E#{exec_idx} L{ev['level_idx']} entry ${ev['amount_quote']:.1f}")
                else:
                    all_tp_x.append(dt)
                    all_tp_y.append(ev["price"])
                    all_tp_text.append(f"E#{exec_idx} L{ev['level_idx']} TP ${ev['amount_quote']:.1f}")

            first_executor = False

        # Use grid_side from last executor for symbol direction (consistent across a backtest)
        entry_symbol = "triangle-up" if grid_side == "BUY" else "triangle-down"
        tp_symbol = "triangle-down" if grid_side == "BUY" else "triangle-up"

        # --- Single trace for all entry fills ---
        if all_entry_x:
            fig.add_trace(
                go.Scatter(
                    x=all_entry_x, y=all_entry_y,
                    mode="markers",
                    marker=dict(color="#26a69a", size=8, symbol=entry_symbol,
                                line=dict(width=1, color="#1b5e20")),
                    name="Grid Entry Fill",
                    legendgroup="grid_entry_fill",
                    text=all_entry_text, hoverinfo="text+y",
                ),
                row=row, col=col,
            )

        # --- Single trace for all TP fills ---
        if all_tp_x:
            fig.add_trace(
                go.Scatter(
                    x=all_tp_x, y=all_tp_y,
                    mode="markers",
                    marker=dict(color="#ffd54f", size=8, symbol=tp_symbol,
                                line=dict(width=1, color="#f57f17")),
                    name="Grid TP Fill",
                    legendgroup="grid_tp_fill",
                    text=all_tp_text, hoverinfo="text+y",
                ),
                row=row, col=col,
            )
