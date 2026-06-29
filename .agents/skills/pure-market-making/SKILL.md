---
name: pure-market-making
description: >-
  Set up and run a market-making bot on Hummingbot via the `hbot` CLI. Use this when a user wants to
  market-make, provide liquidity, or quote two-sided orders on a spot or perpetual exchange. Steers
  toward the modern `pmm_mister` controller, helps pick sane defaults, and avoids the common sizing
  pitfalls (orders below the exchange's minimum notional). Builds on the `hummingbot-cli` skill.
metadata:
  author: hummingbot
  homepage: https://github.com/hummingbot/hummingbot
  requires: hummingbot-cli
  reference: hummingbot/cli/README.md
---

# pure-market-making

Market making = continuously quoting a **buy** below mid and a **sell** above mid, capturing the
spread while managing inventory. This skill gets a user from zero to a running market-making bot.

> **Prerequisite:** operate the CLI via the **`hummingbot-cli`** skill (install, the `--json`/exit-code
> contract, passwords, the core loop). This skill is the market-making recipe on top of it.

## Which strategy to use

Hummingbot has several market-making implementations. **Default to `pmm_mister`** unless the user has
a specific reason otherwise:

| strategy | type | use it when |
|---|---|---|
| **`pmm_mister`** ✅ | controller | **The default.** Modern PMM, works on **both spot and perpetual**. Adds order-level **take-profit / stop-loss**, inventory holding with target/min/max base %, and global TP/SL. Most capable. |
| `pmm_v1` | controller | A simpler controller-based PMM. Use only if the user wants the plain controller without `pmm_mister`'s TP/SL and inventory features. |
| `pure_market_making` | v1-strategy | The original V1 PMM strategy. Legacy; use only for parity with an existing V1 setup. |
| `simple_pmm.py` | v2-script | Minimal tutorial script. Use for *learning/reading* how a PMM is built, not for production. |

**Why `pmm_mister`:** it improves on the original V1 pure-market-making strategy by letting the user
set **order-level take-profit and stop-loss**, **hold inventory** (skew quotes to keep a target base
%), and run on **spot or perps** with the same config. Steer users here and help them configure it.

## Configure `pmm_mister` with sane defaults

`pmm_mister` has **no required fields** — every field has a default — so the job is overriding a
small set for the user's venue, pair, and risk. Inspect the live field list anytime with
`hbot strategy show pmm_mister --json` (`fields` = name→default, `live_fields` = changeable while
running — nearly all of them are).

The fields that matter for a first bot:

| field | default | what it does |
|---|---|---|
| `connector_name` | `binance` | the exchange. Spot (e.g. `binance`) or perp (e.g. `binance_perpetual`, `hyperliquid_perpetual`). |
| `trading_pair` | `BTC-USDT` | the market. Must exist on the connector (see "Trading rules" below). |
| `total_amount_quote` | `100` | capital **reference** in quote currency. |
| `portfolio_allocation` | `0.1` | fraction of `total_amount_quote` actually deployed into orders. |
| `buy_spreads` / `sell_spreads` | `0.0005` | distance from mid, as a fraction (`0.0005` = 5 bps). A comma list makes **multiple order levels**. |
| `buy_amounts_pct` / `sell_amounts_pct` | `1` | relative size weight per level (must match the number of spreads). |
| `target_base_pct` | `0.5` | inventory target: hold this fraction of deployed value in the **base** asset. |
| `min_base_pct` / `max_base_pct` | `0.3` / `0.7` | quoting skews to keep base% inside this band (the "hold inventory" behavior). |
| `take_profit` | `0.0001` | **order-level** take-profit (1 bp). Each filled level arms a TP order. |
| `leverage` | `20` | **perp only** — sets margin (notional ÷ leverage). Ignored on spot. **Does not change order size.** |
| `position_mode` | `ONEWAY` | perp position mode. |
| `global_tp_enabled` / `global_sl_enabled` | `False` | optional account-wide TP/SL on top of order-level TP. |

### The sizing gotcha — read this before starting

Order notional per level is computed as:

```
order_quote(level) = (level's normalized amount_pct) × total_amount_quote × portfolio_allocation
```

So the **defaults deploy only `100 × 0.1 = 10` quote total**, split across all buy+sell levels —
roughly **5 quote per order**. On most venues that's **below the minimum order notional**, so each
order gets quantized to `0` and **silently skipped** — the bot looks alive but never quotes.

To avoid it, make sure **every level's notional ≥ the exchange's minimum order size**:

- Raise `total_amount_quote` and/or `portfolio_allocation` so each side clears the minimum.
- Fewer spread levels = larger notional per level.
- **`leverage` does NOT help here** — it only reduces the *margin* you must post (perp); the order
  notional is still `total_amount_quote × portfolio_allocation`. On spot, you need the full notional
  as balance; on perp you need `notional ÷ leverage` as margin.

A safe single-level starter (≈50 quote per side, clears typical 5–10 quote minimums):

```bash
hbot strategy create pmm_mister --name conf_mm.yml \
  --set connector_name=hyperliquid_perpetual \
  --set trading_pair=ETH-USD \
  --set total_amount_quote=100 \
  --set portfolio_allocation=1 \
  --set buy_spreads=0.001 \
  --set sell_spreads=0.001 \
  --set leverage=5
#   -> 100 quote deployed, ~50 per side (one level each), margin ≈ 20 at 5x
```

For spot, drop `leverage`/`position_mode` (ignored) and size `total_amount_quote × portfolio_allocation`
to your available quote balance.

## Trading rules & pair availability (known gap)

Before configuring, you want the connector's **available pairs** and **minimum order size** — but
there is **no `hbot` command for trading rules yet**. Until there is, work around it:

- Confirm the pair string format the connector expects (e.g. `ETH-USD` vs `ETH-USDT`); a wrong/unknown
  pair fails at `start`.
- Size generously above the typical 5–10 quote minimum (see above) so the first run quotes.
- After `start`, check `hbot logs -f` for order-rejection or below-minimum messages, and `hbot status`
  for the recent-errors count — that's how you'll see a min-notional problem today.

> **Recommended follow-up for maintainers:** add a command that surfaces a connector's trading rules
> (min order size / notional, price & amount increments, available pairs) so agents can size orders
> correctly *before* starting — e.g. `hbot connect <exchange> --rules <pair>` or `hbot strategy rules`.
> Until then this skill sizes conservatively and verifies via logs.

## End-to-end happy path

```bash
# 1. connect the venue and confirm funds (see the hummingbot-cli skill for keys/password handling)
hbot connect hyperliquid_perpetual
hbot balance

# 2. create the config (sane single-level starter above), then verify it
hbot strategy create pmm_mister --name conf_mm.yml \
  --set connector_name=hyperliquid_perpetual --set trading_pair=ETH-USD \
  --set total_amount_quote=100 --set portfolio_allocation=1 \
  --set buy_spreads=0.001 --set sell_spreads=0.001 --set leverage=5
hbot strategy show-config conf_mm.yml

# 3. start and confirm it's actually quoting (not just alive)
hbot start conf_mm.yml
hbot status                 # check run state AND the recent-errors count
hbot logs -f                # confirm orders are placed (no "below minimum"); Ctrl-C to stop

# 4. tune live — nearly every pmm_mister field is live-updatable (~10s to apply)
hbot update buy_spreads 0.002       # widen quotes
hbot update sell_spreads 0.002
hbot update portfolio_allocation 0.5 # deploy less capital
hbot update target_base_pct 0.6      # hold more base inventory

# 5. observe and stop
hbot trades ; hbot history
hbot stop                            # graceful: cancels open orders (and closes per TP/SL logic)
```

## Tuning guidance

- **Wider spreads** = fewer fills, more spread captured per fill, less inventory churn. **Tighter
  spreads** = more fills, more volume, more inventory risk. Start wider and tighten.
- **Inventory drift:** if the bot accumulates too much base, lower `target_base_pct` (or tighten
  `max_base_pct`) so it skews toward selling; raise it to lean long.
- **Order-level `take_profit`** locks in small gains per filled level; raise it for trendier markets,
  lower it for tight range-bound ones.
- **Multiple levels:** `buy_spreads=0.001,0.002,0.003` with matching `buy_amounts_pct=1,1,1` ladders
  three buy orders — but remember each level's notional must still clear the exchange minimum.

## Anti-patterns & safety

- **Don't ship the defaults unchanged** — `total_amount_quote=100, portfolio_allocation=0.1` quotes
  ~5/side and is likely below minimum notional. Always size deliberately.
- **Perp = leverage = liquidation risk.** `pmm_mister` defaults to **20x**; lower it (e.g. 3–5x) for a
  first run, and make sure the user *intends* leveraged/perp trading. Spot has no liquidation.
- **Don't assume "running" = "quoting."** Verify via `hbot logs` that orders are actually placed; a
  min-notional or bad-pair problem leaves the bot alive but idle.
- **Start small and on paper/low size first.** Confirm the full loop (quote → fill → TP → stop cancels
  orders) before scaling `total_amount_quote`.
- Follow the `hummingbot-cli` skill's secret handling — never put the keystore password or API keys on
  the command line.

## Reference

Full CLI reference: **`hummingbot/cli/README.md`**. `pmm_mister` source:
`controllers/generic/pmm_mister.py`.
