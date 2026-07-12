# Strategy Research Catalog

This catalog separates **source maturity** from **proven profitability**. No GitHub strategy is treated as profitable merely because it is popular, backtested once, or included in a mature framework.

## Admission policy

Every collected strategy follows:

```text
collected -> shadow -> backtest_passed -> paper_enabled -> live_canary -> live_enabled
```

Promotion requires an adapter, cost model, stop/protect path, walk-forward evidence, paper evidence, and a bounded risk profile. GPL and LGPL sources are research references unless their licensing implications are explicitly accepted; incompatible code is not copied into the Apache-2.0 Hummingbot core.

## Source set

| Source | What is reused | Boundary |
|---|---|---|
| [Hummingbot](https://github.com/hummingbot/hummingbot) | Controllers, executors, PMM, grid, arbitrage, hedge and LP patterns | Native source of truth |
| [Hummingbot Dashboard](https://github.com/hummingbot/dashboard) | Backtest and instance-management workflow | UI/product reference |
| [Freqtrade Strategies](https://github.com/freqtrade/freqtrade-strategies) | Indicator combinations and research checklist | Examples explicitly do not guarantee profitability; GPL code is not copied |
| [Jesse Examples](https://github.com/jesse-ai/example-strategies) | Donchian, Turtle, Dual Thrust, RSI2 and crossover patterns | Examples explicitly do not claim profitability |
| [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) | Book-imbalance, market-making and research/live parity ideas | Design reference unless licensing is reviewed |
| [QuantConnect LEAN](https://github.com/QuantConnect/Lean) | Futures momentum and portfolio algorithms | Cross-asset research reference |
| [VeighNa](https://github.com/vnpy/vnpy) | CTA lifecycle and operational patterns | Framework reference |

The machine-readable catalog is [`reports/strategy_catalog.json`](../reports/strategy_catalog.json). It is consumed directly by the management admin and records family, source, evidence level, regime fit, risk, adapter state and promotion status.

## Current coverage

The catalog covers structural arbitrage, grid, trend, mean reversion, market making, liquidity provision, portfolio hedge, execution algorithms and observation features. Position-sizing schemes without an independent market edge are outside the product scope.

## Product rule

The system optimizes for **net, risk-adjusted, out-of-sample performance after switching cost**. Strategy count is not a KPI. A smaller set of validated strategies is more valuable than a large set of unverified implementations.
