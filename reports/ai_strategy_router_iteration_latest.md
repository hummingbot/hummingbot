# AI Router Iteration Report

- Generated: 2026-07-01 08:33:36
- Loop iteration: 1
- Container: hummingbot-ai-router-paper | Up 4 minutes
- Router: range_low_vol / continue -> grid_strike
- Orders/Fills: 84 / 47
- Equity estimate: -0.594098574288003197021612395 USDT | base=0.00009210000000000004981327850249 BTC | fees=0.6128428182879999877697551797 USDT

## Tests

- py_compile: PASS
- router synthetic: PASS

## Strategy Universe

- Total: 26
- Enabled: 5 | grid_strike, bollingrid, trend_long, trend_short, protect_mode
- Shadow: 21
- Families: {'arbitrage': 3, 'grid': 4, 'hedge': 2, 'lp': 1, 'market_making': 5, 'mean_reversion': 2, 'observe': 2, 'protect': 1, 'trend': 6}

## Gaps / Next Actions

- [medium] strategy_adapters: 21 shadow strategies still need adapters. Action: Prioritize adapters by current shadow score and market regime coverage.
- [low] release: Router-related code has uncommitted or unpinned changes. Action: Commit or tag a release snapshot before promoting beyond paper; rerun --deploy-paper after later code edits.
