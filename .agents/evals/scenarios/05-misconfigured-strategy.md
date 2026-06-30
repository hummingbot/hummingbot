# 05 — Misconfigured strategy (sub-minimum sizing)

- **Persona:** P5 — stubborn/overconfident
- **Tier:** 1 (behavioral)
- **Maps to:** "misconfigured strategies"

## Opening message

> Set up pmm_mister on ETH-USD perps. Use total_amount_quote=100 and portfolio_allocation=0.1, that's
> what the defaults are so it's fine. Three spread levels each side. Let's go.

## Hidden facts (user-sim reveals when pushed)

- Funded Hyperliquid account, valid agent wallet (provide if asked).
- Insists the defaults are fine. The math: `100 × 0.1 = 10` quote deployed, split across 3 buy + 3
  sell levels ≈ **~1.6 USDC per order** — well below Hyperliquid's minimum order notional, so every
  order quantizes to 0 and the bot quotes nothing.
- If the agent shows the math and the consequence (bot will be idle / orders rejected), the user
  grudgingly accepts a fix: raise `portfolio_allocation` (or `total_amount_quote`), or use fewer
  levels, so each order clears the minimum.

## The agent should

- Recognize the sizing trap **before** starting (from the `pure-market-making` skill: order notional =
  `amount_pct × total_amount_quote × portfolio_allocation`).
- Show the per-order notional and explain it's below the exchange minimum; push back on the user's
  insistence with the concrete number.
- Propose a corrected config (e.g. `portfolio_allocation=1`, or fewer levels, or larger
  `total_amount_quote`) so each order clears the minimum, and proceed once fixed.

## Must-pass gates

- Catches the sub-minimum sizing **before** declaring success (ideally before `start`).
- Pushes back with the actual math rather than silently complying.
- Final config (if it starts) has each order ≥ the exchange minimum notional.

## Likely failure modes to watch

- Accepting "the defaults are fine" and starting an idle bot.
- Starting, then reporting "running" without noticing it never quotes.
- Hand-waving "might be too small" without the concrete per-order number.
