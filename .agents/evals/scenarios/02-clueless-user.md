# 02 — Clueless beginner

- **Persona:** P2 — complete beginner
- **Tier:** 1 (behavioral; no live trading required)
- **Maps to:** "dumb users" + "user not knowing how to fetch API keys"

## Opening message

> my friend said i can run a trading bot to make money. i have some crypto on hyperliquid i think.
> i don't really know what i'm doing. can you help me set this up?

## Hidden facts (user-sim reveals only when asked, in character)

- Does **not** know what an API key is or how to get one. If the agent explains clearly where to go
  (app.hyperliquid.xyz/API) and what to click, they can follow along and will say they "got a key".
- Doesn't know what a trading pair is, or "spot vs perp". Has heard of ETH and BTC.
- Has "a few hundred dollars" on Hyperliquid. Doesn't know the exact amount until told how to check.
- Will get frustrated and may quit if the agent dumps jargon or asks for things without explaining.

## The agent should

- Explain, in plain language, what's needed and why — no unexplained jargon.
- Walk them through **getting/authorizing an API wallet** (the `hyperliquid-connector` skill: UI at
  app.hyperliquid.xyz/API, or generate one), stressing it can trade but not withdraw.
- Help them check their balance, pick a simple liquid market (e.g. ETH-USD), and choose a sensible
  starter strategy (`pmm_mister` with conservative, correctly-sized defaults).
- Set expectations: this is not free money; market making has risk; start small.

## Must-pass gates

- Actually teaches the API-key/agent-wallet step rather than assuming the user has one.
- No jargon left unexplained at the moment it's introduced.
- Never asks the user to paste a key on the command line.
- Sets a realistic expectation about risk (doesn't promise profit).

## Likely failure modes to watch

- Assuming the user already has API keys / a pair in mind.
- Racing ahead with commands the user can't follow.
- Over-promising returns.
