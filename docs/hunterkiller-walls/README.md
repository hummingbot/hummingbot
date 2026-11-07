# Hummingbot wall grid example

```sh
curl --fail-with-body --max-time 20 https://hunterkiller.io/api/v1/levels/BTCUSDT
```

The keyless rollout is pending a live receipt; a 401 is a failure, not data.
[API key signup](https://hunterkiller.io/signup) and the
[agent documentation](https://hunterkiller.io/for-agents) describe the key path.
Free data is 2 hours behind on six coins. A supplied live key can consume credits.

`hk_wall_grid.py` is a Hummingbot 2.17 V2 paper only script. Copy it and
`strategies/hk_strategy_core.py` to the framework's `scripts/` folder. Install
the transport with `python -m pip install ./packages/langchain` from this repo.
Create a V2 config for `hk_wall_grid`. Only `binance_paper_trade` and `BTC-USDT`
are accepted. Optional `api_key` is a secret config field, never auto discovered.

The script quotes inside a frozen served wall pair, budgets 100 USDT by default
including its held inventory and uses at most two quotes per side. It cancels
before replacement and closes its own paper inventory at a wall break, a feed
gap or 24 hours. It tracks its own fills and base fees. Start in a fresh paper
session; inventory is not restored after a restart. Exchange minimum size can
leave dust. No live execution is enabled.

## Historical public wall proxy

This is a historical public wall proxy, not an API replay or live performance.
The input ledger retains public wall publications but not original snapshot
age. Unknown time and delay remain null; ambiguous observations are gaps.

| UTC period | Grid quote model equity change, USDT |
| --- | ---: |
| November 5, 2026 | -0.99 |
| November 6, 2026 | -0.80 |
| Full window | -1.79 |

The shared quote model uses real Bybit BTC/USDT spot candles. It is an offline
OHLCV replay, not a native Hummingbot backtest. Starting simulated cash was
1000 USDT and the notional budget was 100 USDT. It recorded 25 fills, including
6 sell fills at a loss, after assumed 0.10 percent fees and 0.05 percent slippage
on market closes. The daily figures mark open inventory at the candle close;
the final day includes closing costs.

This model refreshes once per 5 minute candle, while the script refreshes every
30 seconds. It cannot reconstruct queue position, depth, latency or partial
fills. It does not establish a trading advantage. The script's config, native
order types, inventory handling and stop behavior are covered by offline native
framework tests.

[Every fill, both losing periods, full limitations and reproduction](https://github.com/Irishman-Management-LLC/hunterkiller-examples/blob/71fcc2c41fbd/strategies/RESULTS.md)
are public. Exact API input capture began November 7 for a second table no
earlier than November 21, with coverage gaps disclosed.

Affiliation: this example is maintained by Hunter Killer.

Canonical source and complete reproduction: https://github.com/Irishman-Management-LLC/hunterkiller-examples/tree/71fcc2c41fbd/examples/hummingbot .

The optional transport is not uploaded to PyPI yet. Clone the canonical repository and install `python -m pip install ./packages/langchain`; the shared helper sits beside the strategy in this contribution. No package upload or working keyless claim is made here.
