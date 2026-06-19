# Mean Reversion Backtest

This backtest replays historical Coinbase candles and runs the `mean_reversion_v1` controller against them.

## What it uses

- Historical candles: `coinbase_advanced_trade`
- Simulated trading connector: `coinbase_advanced_trade_paper_trade`
- Strategy config: `conf/controllers/mean_reversion_v1.yml`

The backtester uses the candle history for signals and simulates entries/exits through the V2 executor engine.

## Run it

From the repo root:

```bash
conda run -n hummingbot python scripts/backtest_mean_reversion_v1.py --days 30
```

To generate a chart:

```bash
conda run -n hummingbot python scripts/backtest_mean_reversion_v1.py --days 30 --chart --output backtest_mean_reversion_v1.html
```

To write the per-tick decision trace CSV:

```bash
conda run -n hummingbot python scripts/backtest_mean_reversion_v1.py --days 30 --trace-output data/backtest_mean_reversion_v1_trace.csv
```

## Visualize the decision trace

Use the standalone trace visualizer to turn the CSV into a self-contained Plotly HTML report:

```bash
conda run -n hummingbot python scripts/visualize_mean_reversion_trace.py --input data/backtest_mean_reversion_v1_trace.csv --output data/backtest_mean_reversion_v1_trace.html
```

Useful options:

- `--start-ts` and `--end-ts` filter the trace by Unix timestamp seconds
- `--entry-z-score`, `--rsi-long-threshold`, and `--rsi-short-threshold` control the threshold lines in the diagnostics panel
- `--min-std-pct`, `--max-std-pct`, `--min-volume-ratio`, and `--max-trend-deviation` control the remaining diagnostics thresholds

The report includes:

- a price and fair value timeline with markers for `signal=1`, `signal=-1`, `CreateExecutorAction`, and `StopExecutorAction`
- filter diagnostics for `z_score`, `rsi`, `std_pct`, `trend_deviation`, and `volume_ratio`
- outcome context for `executor_realized_pnl`, `cumulative_volume`, `active_executors`, and `open_position_holds` when those columns are present
- a summary table of rows with nonzero signals, action rows, or rows that have a `no_action_reason`

## Useful options

- `--days 7` changes the historical window
- `--resolution 1m` changes the backtest stepping resolution
- `--interval 5m` changes the controller candle interval
- `--amount 100` changes the quote size used by the controller
- `--use-ema` switches fair value from SMA to EMA
- `--disable-trend-filter` turns off the trend filter
- `--trace-output data/backtest_mean_reversion_v1_trace.csv` writes a per-tick trace CSV

## Expected output

The script prints:

- total executors created
- executors that had a position
- net PnL
- accuracy
- sharpe ratio
- max drawdown
- profit factor
- close types

If trace output is enabled, it also writes a CSV with one row per backtest tick.

## Decision trace CSV

The decision trace CSV is meant for debugging controller behavior tick by tick.

Important columns:

- `timestamp`: backtest tick timestamp
- `close`: replay close price for that tick
- `signal`: strategy directional intent
- `no_action_reason`: why the controller did not create an executor on that tick
- `action_types`: executor actions emitted on that tick
- `executor_ids`: executor ids created or stopped on that tick
- `fair_value`, `z_score`, `std_pct`, `rsi`, `trend_deviation`, `volume_ratio`: the main strategy features used by `mean_reversion_v1`

### Signal values

The `signal` column is ternary:

- `1`: long entry signal
- `0`: no entry signal
- `-1`: short entry signal

For `mean_reversion_v1`, those values are produced as follows:

- `1` means price is sufficiently below fair value, RSI is low enough, volatility is within bounds, volume is sufficient, and the optional trend filter passes.
- `-1` means price is sufficiently above fair value, RSI is high enough, volatility is within bounds, volume is sufficient, and the optional trend filter passes.
- `0` means at least one entry condition failed, or the indicators were still warming up.

### Reading signal vs action

`signal` is only the model's directional intent. It does not guarantee a trade.

Use these columns together:

- `signal`: what the strategy wanted to do
- `no_action_reason`: why no executor was created, such as `waiting_for_signal`, `cooldown_active`, or `max_executors_reached`
- `action_types`: whether a `CreateExecutorAction` or `StopExecutorAction` was actually emitted

Typical interpretation:

- `signal = 1`, empty `action_types`, `no_action_reason = cooldown_active`: long setup exists, but the controller is still in cooldown.
- `signal = -1`, `action_types = CreateExecutorAction`: short entry was actually created on that tick.
- `signal = 0`, `no_action_reason = waiting_for_signal`: no entry setup existed on that tick.

## Notes

- Do not use `coinbase_advanced_trade` as the simulated trading connector for this backtest. The backtesting provider resolves `coinbase_advanced_trade_paper_trade` to the Coinbase connector internally.
- If you change controller parameters, keep the backtest script and controller config aligned so the live strategy and historical simulation match.
