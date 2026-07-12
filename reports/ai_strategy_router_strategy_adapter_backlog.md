# AI Router Strategy Adapter Backlog

This backlog turns the 21 shadow candidates into an executable promotion queue.

Promotion path:

```text
registered shadow -> adapter implemented -> paper-enabled -> paper scorecard pass -> live canary
```
## Promotion Gates

Before any shadow strategy can become `enabled=True`:

1. Adapter maps router decision into safe executor actions.
2. Required features exist in the feature engine.
3. Paper profile is configured.
4. Strategy has a stop/protect path.
5. Loop tests pass.
6. Paper scorecard passes for its intended regime.

Minimum paper scorecard:

```text
observation_window >= 24h
no tracebacks
no stale orders above threshold
max drawdown within limit
fee-adjusted PnL not structurally negative
protect behavior verified
```

## Adapter Queue

| Priority | Candidate | Family | Missing Adapter Work | Required Features | Paper Test |
|---:|---|---|---|---|---|
| 1 | `pmm_dynamic` | market_making | PMM level adapter; inventory cap; maker-only guard | NATR, MACD shift, spread, inventory | Quiet range paper run |
| 2 | `pmm_simple` | market_making | Basic PMM adapter; order refresh and inventory skew | mid price, spread, inventory | Quiet range paper run |
| 3 | `supertrend_v1` | trend | Adapter registered; cost-adjusted walk-forward evidence pending | SuperTrend signal, ATR, trend strength | Trend replay + 24h paper |
| 4 | `bollinger_v1` | mean_reversion | Mean reversion entry/exit adapter | BBP, BB width, range position | High-vol range replay |
| 5 | `bollinger_v2` | mean_reversion | Same as v1 plus v2 config profile | BBP, BB width, range position | High-vol range replay |
| 6 | `multi_grid_strike` | grid | Multi-grid allocation adapter | range bands, inventory, grid PnL | Range paper run |
| 7 | `quantum_grid_allocator` | grid | Allocator state adapter | regime stability, inventory, volatility buckets | Range paper run |
| 8 | `macd_bb_v1` | trend | Combined MACD/BB signal adapter | MACD, BBP, trend strength | Trend/range mixed replay |
| 9 | `dman_v3` | trend | DCA risk adapter; max layered exposure | signal, DCA ladder, drawdown | Trend paper with tight cap |
| 10 | `dman_maker_v2` | market_making | DCA maker adapter; inventory cap | spread, volatility, ladder state | Quiet range paper |
| 11 | `pmm_v1` | market_making | Spread/inventory adapter | spread, inventory, volatility | Quiet range paper |
| 12 | `pmm_mister` | market_making | Adapter registered; stop-path verification and walk-forward evidence pending | spread, inventory, skew, volatility | Quiet range replay + 72h paper |
| 13 | `xemm_multiple_levels` | arbitrage | Maker/taker pair adapter | cross-exchange spread, taker liquidity | Two-connector paper |
| 14 | `arbitrage_controller` | arbitrage | Multi-market route adapter | executable spread, fees, conversion rate | Two-market paper |
| 15 | `stat_arb` | arbitrage | Pair feature engine; hedge constraints | z-score, hedge ratio, pair PnL | Pair replay + paper |
| 16 | `funding_rate_arb` | hedge | Adapter registered; cost-adjusted walk-forward evidence pending | funding rate, executable basis, fees, exit cost | Two-perp replay + 72h paper |
| 17 | `hedge_asset` | hedge | Portfolio exposure adapter | net inventory, hedge ratio, hedge venue | Inventory stress test |
| 18 | `lp_rebalancer` | lp | AMM/gateway context adapter | pool range, LP value, gas, inventory | Gateway paper/dev |
| 19 | `ai_livestream` | trend | External AI trust adapter; signal sanity checks | external signal, confidence, delay | Shadow-only first |
| 20 | `market_status_monitor` | observe | Observation feature ingestion | order book health, latency | Metrics only |
| 21 | `liquidations_monitor` | observe | Liquidation feature ingestion | liquidation spike, OI, volume | Metrics only |

## Current Core Promotion Cohort

The unified gate engine now tracks `supertrend_v1`, `pmm_mister`, and `funding_rate_arb`.

Next work is evidence generation, not additional adapter count:

- Run cost-adjusted walk-forward replay for all three.
- Verify PMM Mister's protect/stop path under stale orders and inventory stress.
- Start minimum paper windows only after replay gates pass.
- Keep canary and live approvals manual.

Shared acceptance criteria:

```text
adapter unit tests pass
stop/protect path verified
cost-adjusted walk-forward passes
minimum paper window and scorecard pass
manual canary approval recorded
manual live approval recorded
```
