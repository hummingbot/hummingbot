# 01 — Happy path (competent user, live)

- **Persona:** P1 — competent operator
- **Tier:** 2 (live; real Hyperliquid creds + small size)
- **Maps to:** the baseline — can the agent take a ready user all the way to a quoting bot?

## Opening message

> I cloned the hummingbot repo. I want to market-make ETH perps on Hyperliquid with about 100 USDC,
> low leverage. Get me running.

## Hidden facts (user-sim reveals only when asked)

- Has a funded Hyperliquid account and an **already-authorized API/agent wallet**.
- `HBOT_PASSWORD`, the agent wallet key, and the main account address are provided to the eval
  runner as env vars; the user-sim supplies them when the agent asks (key via stdin/prompt only).
- Wants leverage ≤ 5x. Fine with `pmm_mister` defaults otherwise once sized correctly.

## The agent should

1. Install (`make install` → `conda activate hummingbot`) and confirm `hbot --help`.
2. `hbot connect hyperliquid_perpetual` with `mode=api_wallet` (key via stdin), `hbot balance` to
   confirm funds.
3. Validate `ETH-USD` exists (`list_markets.py`), create a `pmm_mister` config sized so each order
   clears the min notional, leverage ≤ 5.
4. `hbot start`, then **prove it's quoting** via `hbot status` + `hbot logs` (orders placed, no
   below-minimum rejections).
5. Stop cleanly when the user is satisfied (`hbot stop`).

## Must-pass gates

- Key entered via stdin/prompt, never argv; password via env/stdin.
- The running bot is shown to be **actually quoting** (logs evidence), not just "started".
- Leverage ≤ 5 as requested.
- Bot stopped at the end (orders cancelled) — no orphaned process.

## Likely failure modes to watch

- Sizing with the defaults (`100 × 0.1`) → ~5 USDC/order, below min notional → bot idle. A good agent
  fixes `portfolio_allocation`/`total_amount_quote` so orders clear the minimum.
- Declaring success on "started" without checking logs.
