#!/usr/bin/env python3
"""Build an interactive Plotly HTML report from the mean_reversion_v1 trace CSV."""

import argparse
from pathlib import Path

import pandas as pd
try:
    import plotly.graph_objects as go
    import plotly.io as pio
    from plotly.subplots import make_subplots
except ImportError as exc:
    raise ImportError(
        "plotly is required for trace visualization. Install it in the active environment."
    ) from exc


REQUIRED_COLUMNS = {
    "timestamp",
    "close",
    "signal",
    "no_action_reason",
    "action_types",
    "fair_value",
    "z_score",
    "rsi",
    "std_pct",
    "trend_deviation",
    "volume_ratio",
}

OUTCOME_COLUMNS = [
    "executor_realized_pnl",
    "cumulative_volume",
    "active_executors",
    "open_position_holds",
]

SUMMARY_COLUMNS = [
    "timestamp_utc",
    "close",
    "fair_value",
    "signal",
    "action_types",
    "no_action_reason",
    "row_tags",
    "action_count",
    "executor_ids",
    "active_executors",
    "open_position_holds",
    "executor_realized_pnl",
    "cumulative_volume",
    "z_score",
    "rsi",
    "std_pct",
    "trend_deviation",
    "volume_ratio",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize the mean_reversion_v1 decision trace as an interactive HTML report."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/backtest_mean_reversion_v1_trace.csv",
        help="Input decision trace CSV.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/backtest_mean_reversion_v1_trace.html",
        help="Output HTML report path.",
    )
    parser.add_argument(
        "--start-ts",
        type=float,
        default=None,
        help="Optional inclusive lower bound for timestamp filtering, in Unix seconds.",
    )
    parser.add_argument(
        "--end-ts",
        type=float,
        default=None,
        help="Optional inclusive upper bound for timestamp filtering, in Unix seconds.",
    )
    parser.add_argument(
        "--entry-z-score",
        type=float,
        default=2.0,
        help="Entry z-score threshold used for diagnostics.",
    )
    parser.add_argument(
        "--rsi-long-threshold",
        type=float,
        default=35.0,
        help="Long-side RSI threshold used for diagnostics.",
    )
    parser.add_argument(
        "--rsi-short-threshold",
        type=float,
        default=65.0,
        help="Short-side RSI threshold used for diagnostics.",
    )
    parser.add_argument(
        "--min-std-pct",
        type=float,
        default=0.001,
        help="Minimum std_pct threshold used for diagnostics.",
    )
    parser.add_argument(
        "--max-std-pct",
        type=float,
        default=0.05,
        help="Maximum std_pct threshold used for diagnostics.",
    )
    parser.add_argument(
        "--min-volume-ratio",
        type=float,
        default=0.25,
        help="Minimum volume_ratio threshold used for diagnostics.",
    )
    parser.add_argument(
        "--max-trend-deviation",
        type=float,
        default=0.015,
        help="Maximum trend_deviation threshold used for diagnostics.",
    )
    return parser.parse_args()


def validate_columns(df: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing:
        raise ValueError(
            "Trace CSV is missing required columns: " + ", ".join(missing)
        )


def to_numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce")


def clean_text_series(df: pd.DataFrame, column: str) -> pd.Series:
    return df[column].fillna("").astype(str).str.strip()


def build_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["timestamp_num"] = to_numeric_series(df, "timestamp")
    df["timestamp_dt"] = pd.to_datetime(df["timestamp_num"], unit="s", utc=True, errors="coerce")
    df["timestamp_utc"] = df["timestamp_dt"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    return df


def filter_rows(df: pd.DataFrame, start_ts: float | None, end_ts: float | None) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if start_ts is not None:
        mask &= df["timestamp_num"] >= start_ts
    if end_ts is not None:
        mask &= df["timestamp_num"] <= end_ts
    return df.loc[mask].copy()


def count_non_empty(values: pd.Series) -> dict[str, int]:
    cleaned = values.fillna("").astype(str).str.strip()
    cleaned = cleaned[cleaned != ""]
    return cleaned.value_counts().to_dict()


def print_counts(label: str, counts: dict[str, int]) -> None:
    if not counts:
        print(f"{label}: none")
        return
    print(f"{label}:")
    for key, value in counts.items():
        print(f"  {key}: {value}")


def build_price_figure(df: pd.DataFrame) -> go.Figure:
    close = to_numeric_series(df, "close")
    fair_value = to_numeric_series(df, "fair_value")
    signal = to_numeric_series(df, "signal").fillna(0.0)
    action_types = clean_text_series(df, "action_types")

    long_mask = signal > 0
    short_mask = signal < 0
    create_mask = action_types.str.contains("CreateExecutorAction", na=False)
    stop_mask = action_types.str.contains("StopExecutorAction", na=False)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["timestamp_dt"],
            y=close,
            mode="lines",
            name="close",
            line=dict(color="#1f77b4", width=1.6),
            hovertemplate="time=%{x}<br>close=%{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["timestamp_dt"],
            y=fair_value,
            mode="lines",
            name="fair_value",
            line=dict(color="#ff7f0e", width=1.6),
            hovertemplate="time=%{x}<br>fair_value=%{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.loc[long_mask, "timestamp_dt"],
            y=close.loc[long_mask],
            mode="markers",
            name="signal=1",
            marker=dict(symbol="triangle-up", size=10, color="#2ca02c", line=dict(color="white", width=0.5)),
            hovertemplate="time=%{x}<br>signal=1<br>close=%{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.loc[short_mask, "timestamp_dt"],
            y=close.loc[short_mask],
            mode="markers",
            name="signal=-1",
            marker=dict(symbol="triangle-down", size=10, color="#d62728", line=dict(color="white", width=0.5)),
            hovertemplate="time=%{x}<br>signal=-1<br>close=%{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.loc[create_mask, "timestamp_dt"],
            y=close.loc[create_mask],
            mode="markers",
            name="CreateExecutorAction",
            marker=dict(symbol="circle", size=9, color="#17becf", line=dict(color="#0d6e7c", width=1)),
            hovertemplate="time=%{x}<br>CreateExecutorAction<br>close=%{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.loc[stop_mask, "timestamp_dt"],
            y=close.loc[stop_mask],
            mode="markers",
            name="StopExecutorAction",
            marker=dict(symbol="x", size=10, color="#111111", line=dict(width=1.4)),
            hovertemplate="time=%{x}<br>StopExecutorAction<br>close=%{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Mean Reversion Trace: Price, Fair Value, Signals, and Actions",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=50, r=20, t=70, b=40),
        xaxis=dict(rangeslider=dict(visible=True)),
    )
    fig.update_yaxes(title_text="price")
    return fig


def build_diagnostics_figure(df: pd.DataFrame, args: argparse.Namespace) -> go.Figure:
    specs = [
        ("z_score", "z_score", [("upper entry", args.entry_z_score), ("lower entry", -args.entry_z_score)]),
        ("rsi", "rsi", [("long threshold", args.rsi_long_threshold), ("short threshold", args.rsi_short_threshold)]),
        ("std_pct", "std_pct", [("min std_pct", args.min_std_pct), ("max std_pct", args.max_std_pct)]),
        ("trend_deviation", "trend_deviation", [("max trend_deviation", args.max_trend_deviation)]),
        ("volume_ratio", "volume_ratio", [("min volume_ratio", args.min_volume_ratio)]),
    ]
    fig = make_subplots(
        rows=len(specs),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=[title for title, _, _ in specs],
    )

    for row, (column, label, thresholds) in enumerate(specs, start=1):
        series = to_numeric_series(df, column)
        fig.add_trace(
            go.Scatter(
                x=df["timestamp_dt"],
                y=series,
                mode="lines",
                name=label,
                line=dict(width=1.4),
                hovertemplate=f"time=%{{x}}<br>{label}=%{{y:.6g}}<extra></extra>",
                showlegend=False,
            ),
            row=row,
            col=1,
        )
        for threshold_label, threshold_value in thresholds:
            fig.add_hline(
                y=threshold_value,
                row=row,
                col=1,
                line_dash="dash",
                line_width=1,
                line_color="#666666",
                annotation_text=threshold_label,
                annotation_position="top left",
            )
        if column == "z_score":
            fig.add_hline(y=0.0, row=row, col=1, line_dash="dot", line_width=1, line_color="#999999")
        fig.update_yaxes(title_text=label, row=row, col=1)

    fig.update_layout(
        title="Mean Reversion Trace: Filter Diagnostics",
        hovermode="x unified",
        margin=dict(l=50, r=20, t=70, b=40),
        showlegend=False,
    )
    return fig


def build_outcome_figure(df: pd.DataFrame) -> go.Figure | None:
    present_columns = [column for column in OUTCOME_COLUMNS if column in df.columns]
    if not present_columns:
        return None

    fig = make_subplots(
        rows=len(present_columns),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=[column for column in present_columns],
    )

    for row, column in enumerate(present_columns, start=1):
        fig.add_trace(
            go.Scatter(
                x=df["timestamp_dt"],
                y=to_numeric_series(df, column),
                mode="lines",
                name=column,
                line=dict(width=1.4),
                hovertemplate=f"time=%{{x}}<br>{column}=%{{y:.6g}}<extra></extra>",
                showlegend=False,
            ),
            row=row,
            col=1,
        )
        fig.update_yaxes(title_text=column, row=row, col=1)

    fig.update_layout(
        title="Mean Reversion Trace: Outcome Context",
        hovermode="x unified",
        margin=dict(l=50, r=20, t=70, b=40),
        showlegend=False,
    )
    return fig


def build_summary_table(df: pd.DataFrame) -> str:
    signal = to_numeric_series(df, "signal").fillna(0.0)
    action_types = clean_text_series(df, "action_types")
    no_action_reason = clean_text_series(df, "no_action_reason")

    signal_mask = signal.ne(0.0)
    action_mask = action_types.ne("")
    reason_mask = no_action_reason.ne("")
    mask = signal_mask | action_mask | reason_mask
    summary = df.loc[mask].copy()

    if summary.empty:
        return "<p>No rows matched the summary criteria.</p>"

    summary["row_tags"] = [
        ",".join(
            tag
            for tag, enabled in (
                ("signal", bool(signal_mask.loc[idx])),
                ("action", bool(action_mask.loc[idx])),
                ("no_action_reason", bool(reason_mask.loc[idx])),
            )
            if enabled
        )
        for idx in summary.index
    ]

    available_columns = [column for column in SUMMARY_COLUMNS if column in summary.columns or column == "row_tags"]
    table = summary[available_columns].copy()

    for column in [
        "close",
        "fair_value",
        "signal",
        "action_count",
        "active_executors",
        "open_position_holds",
        "executor_realized_pnl",
        "cumulative_volume",
        "z_score",
        "rsi",
        "std_pct",
        "trend_deviation",
        "volume_ratio",
    ]:
        if column in table.columns:
            table[column] = pd.to_numeric(table[column], errors="coerce").round(6)

    return table.to_html(index=False, classes="trace-table", border=0, escape=True)


def build_html_report(figures: list[tuple[str, go.Figure]], summary_html: str, stats_html: str) -> str:
    parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        '<meta charset="utf-8" />',
        "<title>mean_reversion_v1 trace report</title>",
        "<style>",
        "body { font-family: Arial, Helvetica, sans-serif; margin: 0; padding: 20px; color: #111; background: #fff; }",
        "h1 { margin: 0 0 12px 0; font-size: 28px; }",
        "h2 { margin: 28px 0 10px 0; font-size: 20px; }",
        "p { margin: 6px 0; line-height: 1.45; }",
        ".section { margin-bottom: 30px; }",
        ".stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }",
        ".stat { border: 1px solid #ddd; padding: 10px 12px; background: #fafafa; }",
        ".trace-table { border-collapse: collapse; width: 100%; font-size: 12px; }",
        ".trace-table th, .trace-table td { border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }",
        ".trace-table th { background: #f2f2f2; position: sticky; top: 0; }",
        "</style>",
        "</head>",
        "<body>",
        "<h1>mean_reversion_v1 trace report</h1>",
        '<div class="section stats">',
        stats_html,
        "</div>",
    ]

    for index, (title, figure) in enumerate(figures):
        parts.append(f'<div class="section"><h2>{title}</h2>')
        parts.append(
            pio.to_html(
                figure,
                full_html=False,
                include_plotlyjs=index == 0,
                config={"displaylogo": False, "responsive": True},
            )
        )
        parts.append("</div>")

    parts.extend(
        [
            '<div class="section"><h2>Summary rows</h2>',
            summary_html,
            "</div>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(parts)


def build_stats_html(df: pd.DataFrame) -> str:
    signal = to_numeric_series(df, "signal").fillna(0.0)
    counts = {
        "rows": len(df),
        "signal=1": int((signal > 0).sum()),
        "signal=0": int((signal == 0).sum()),
        "signal=-1": int((signal < 0).sum()),
    }
    items = "".join(f'<div class="stat"><strong>{key}</strong><br>{value}</div>' for key, value in counts.items())
    return items


def main() -> None:
    args = parse_args()
    if args.start_ts is not None and args.end_ts is not None and args.end_ts < args.start_ts:
        raise ValueError("--end-ts must be greater than or equal to --start-ts")

    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_csv(input_path)
    validate_columns(df)
    df = build_timestamps(df)
    df = filter_rows(df, args.start_ts, args.end_ts)
    df = df.sort_values("timestamp_num").reset_index(drop=True)
    if df.empty:
        raise ValueError("No rows remain after applying the timestamp filters.")

    signal = to_numeric_series(df, "signal").fillna(0.0)
    action_types = clean_text_series(df, "action_types")
    no_action_reason = clean_text_series(df, "no_action_reason")

    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print(f"Rows after filtering: {len(df)}")
    print(
        "Signal counts: "
        f"signal=1 -> {int((signal > 0).sum())}, "
        f"signal=0 -> {int((signal == 0).sum())}, "
        f"signal=-1 -> {int((signal < 0).sum())}"
    )
    print_counts("action_types counts", count_non_empty(action_types))
    print_counts("no_action_reason counts", count_non_empty(no_action_reason))

    figures = [
        ("Price and signal timeline", build_price_figure(df)),
        ("Filter diagnostics", build_diagnostics_figure(df, args)),
    ]
    outcome_figure = build_outcome_figure(df)
    if outcome_figure is not None:
        figures.append(("Outcome context", outcome_figure))

    summary_html = build_summary_table(df)
    stats_html = build_stats_html(df)
    report_html = build_html_report(figures, summary_html, stats_html)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_html, encoding="utf-8")
    print("HTML report written successfully.")


if __name__ == "__main__":
    main()
