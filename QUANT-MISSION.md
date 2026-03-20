# QUANT-MISSION.md — Trading Bot Operations

## Objective
Generate trading profits on Hyperliquid perpetual futures using BTC-ALT divergence signals. Signal-driven directional trading.

## Current Status: REBUILDING SIGNAL ENGINE

The Limitless binary options system is **retired** (thin books, binary mechanics, net loss $9.90). We've pivoted to Hyperliquid perps.

The hbot pipeline (controller → strategy → connector → exchange) is **proven working**. What's broken is the **signal engine** — it was ported wrong. The correct trading logic needs to be rebuilt from the system-map docs.

---

## Systems

### Hummingbot (Execution Engine)
- **Source:** `/home/tiger/hummingbot/` (fork: `blacksn0w13/hummingbot`, branch `master`)
- **Conda env:** `hummingbot` at `/opt/miniconda3/envs/hummingbot/`
- **Tmux session:** `hbot`
- **Controller:** `controllers/directional_trading/hyperliquid_stat_arb.py` (NEEDS REBUILD)
- **Signal engine:** `controllers/directional_trading/hyperliquid_signal_engine.py` (NEEDS REBUILD)
- **System-map docs:** `controllers/directional_trading/system-map/` (4 files — source of truth for porting)
- **Spec:** `controllers/directional_trading/SPEC-hyperliquid-stat-arb.md` (OUTDATED — needs rewrite)
- **Config YAMLs:**
  - `conf/controllers/conf_hyperliquid_stat_arb_1.yml` (PLACEHOLDER values)
  - `conf/scripts/conf_v2_hyperliquid_1.yml` → `v2_with_controllers.py`
- **Start command:** `start --v2 conf_v2_hyperliquid_1.yml`

### Hyperliquid Connector (hbot built-in, with our patches)
- **Files:** `hummingbot/connector/derivative/hyperliquid_perpetual/`
- **Our patches to `hyperliquid_perpetual_derivative.py`:**
  1. HIP-3 markets disabled by default (eliminates 141 rate-limited API calls)
  2. `split(':')` fix for multi-colon HIP-3 symbols
  3. bidict ValueDuplicationError wrapped in try/except
  4. Balance fallback to `spotClearinghouseState` (unified margin / testnet)
- **Debug addition to `strategy_v2_base.py`:** `status={con.status_dict}` in "not ready" warning

### Wallet
- `0xa2285201c21a5AC7aBdBcAcc8806437De2f29976`
- Mainnet: ~$7.70 USDC (spot)
- Testnet: ~$999 USDC (spot clearinghouse — testnet oracles are broken, unusable)

### Old Systems (DISABLED)
- Limitless connector: `conf/connectors/limitless.yml.disabled`
- Binary options controller: `conf/controllers/binary_options.yml.disabled`
- Old hyperliquid generic controller: `conf/controllers/hyperliquid.yml.disabled`
- Old strategy configs: `*.yml.disabled` in `conf/scripts/`
- Broken multi-file controller package: `controllers/generic/hyperliquid/` (TO SCRAP)

---

## What's Proven Working ✅
- hbot pipeline: strategy starts, WebSocket subscribes, order books initialize (BTC-USD + ETH-USD)
- Leverage setting works (testnet confirmed)
- Balance detection works (with spot fallback patch)
- One test order went through on testnet
- Controller loads and imports clean

## What's Broken ❌
- **Signal engine is WRONG:** Ported the Type 1/2/3 event classification system that was disabled in Limitless 6 weeks ago. Stripped the actual trading signals (`MispricingProfile.should_trade()`, `BtcImpliedProfile.should_trade()`)
- **No RuntimeBridge:** All thresholds hardcoded in YAML defaults instead of hot-reloadable from `runtime.json`
- **Threshold values are guesses:** z_score 1.5, btc_z 1.75 — no data backing, no calibration
- **Testnet unusable:** Oracles stale, "price too far from oracle" on most orders

---

## The Actual Strategy (What Needs To Be Built)

The original Limitless system tracked BTC-ALT divergence. The core logic:

1. **Watch BTC and ALT prices every tick**
2. **Track correlation/beta** — how ALT normally follows BTC (rolling EMA)
3. **When BTC moves, compute implied ALT price:** `implied = current_ALT × exp(beta × btc_return)`
4. **The gap between implied and actual = edge**
5. **Z-score on that gap** — EMA + variance tracking (same math as `BtcImpliedProfile`)
6. **Z-score big enough → trade** in the direction of the gap
7. **Gap closes → take profit.** Doesn't close → stop loss or time limit

On Limitless this was wrapped in Black-Scholes (because binary options price in probabilities). On perps we don't need that — the edge is directly in dollar terms.

### Source of truth for porting:
- `controllers/directional_trading/system-map/` — full extraction of original `divergence_tracker.py`
- `controllers/generic/binary_options/fair_value.py` — `BtcImpliedProfile` class (the actual signal)
- `controllers/generic/binary_options/action_router.py` — entry decision logic
- `controllers/generic/binary_options/config.py` — `RuntimeBridge` pattern

### What to strip (binary-options-specific):
- Black-Scholes (`compute_model_prob`, `_norm_cdf`)
- Strike prices, expiry times, hours_left
- YES/NO price mechanics
- Market slug management, roster rotation
- `MispricingProfile` (spot vs market_yes — doesn't apply to perps)

### What to keep and adapt:
- `BtcImpliedProfile` — core divergence tracking (replace probability output with dollar output)
- `RuntimeBridge` — hot-reloadable thresholds from `runtime.json`
- EMA + variance z-score math
- Per-coin params, cooldowns, position limits
- Exit monitor (BTC reversal detection)

---

## Plan

### Step 1 — Data Collection (NEXT)
Run observation mode on mainnet. No trading. Log ETH price, BTC price, beta, implied price, divergence, z-score every tick. Collect hours of data to understand actual signal ranges.

### Step 2 — Spec
Write spec based on actual data: tradeable spread levels, expected hold times, win rate vs fees (0.025% taker), position sizing, all thresholds documented with reasoning.

### Step 3 — Build
Claude Code implements against the spec. Signal engine, RuntimeBridge, proper thresholds. Single-file controller in `controllers/directional_trading/`.

### Step 4 — Paper Validate
Run on mainnet logging would-be trades without executing. Compare signals vs actual price moves.

### Step 5 — Go Live Tiny
$1-2 positions. Measure actual vs expected.

---

## Reference: Hyperliquid Mechanics
- **Fees:** Maker 0% (-0.02% rebate), Taker 0.025%
- **Pair format:** `BTC-USD`, `ETH-USD`, `SOL-USD`
- **Wallet modes:** `arb_wallet`, `api_wallet` (Phil prefers `api_wallet` — safer)
- **Testnet:** `hyperliquid_perpetual_testnet` connector, `api.hyperliquid-testnet.xyz` — currently broken oracles
- **Mainnet:** `hyperliquid_perpetual` connector, `api.hyperliquid.xyz`

## Reference: Limitless System (Archived)
- Binary options controller: `controllers/generic/binary_options/` (9 modules, 160 tests)
- Original standalone bot: `skills/limitless-recon/`
- System map extraction: `controllers/directional_trading/system-map/`
- All Limitless specs: `docs/limitless/specs/`

---

## Rules
- **ALL thresholds in runtime.json** — never hardcoded in Python
- **RuntimeBridge for hot-reload** — no process restart to change params
- **Spec before code** — no more bolting things together
- **Read the system-map docs** before writing signal engine code
- **Don't guess trading parameters** — size, leverage, SL, TP are Phil's decisions
- **Don't switch to mainnet without explicit approval**
- **Claude Code writes code, Clawd writes specs and coordinates**
- All param changes journaled to `skills/clawd-trades/data/trading_log.jsonl`

---
⚠️ UPDATE RULE: On every relevant action, update this file.
