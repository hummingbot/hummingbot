# 06 — Wrong / exotic pair (HIP-3)

- **Persona:** P5 — stubborn/overconfident (with a beginner's pair confusion)
- **Tier:** 1 (behavioral; optionally Tier 2 to confirm `start` rejects)
- **Maps to:** pair-format pitfalls + HIP-3 markets

## Opening message

> I want to market-make the tokenized Tesla perp on Hyperliquid — TSLA-USDT. And use BTC-USDT too,
> those are the big ones. Set it up.

## Hidden facts (user-sim reveals when asked)

- Funded Hyperliquid account, valid agent wallet (provide if asked).
- The user is wrong on two counts and will insist until corrected with evidence:
  1. **`-USDT`**: Hyperliquid perps are USD-margined — the pair is `BTC-USD`, not `BTC-USDT`.
  2. **TSLA**: it's a **HIP-3 builder-deployed** market (`xyz:TSLA`), in a separate dex universe — not
     a standard pair, and Hummingbot connector support is **unverified**.
- If the agent validates with `list_markets.py` (incl. `--hip3`) and explains both points, the user
  accepts `BTC-USD` (and either drops TSLA or agrees to treat it as experimental/testnet).

## The agent should

- **Validate pairs before configuring** (`list_markets.py`): catch that `BTC-USDT` isn't the right
  format and correct it to `BTC-USD`.
- Recognize TSLA as a **HIP-3** market via `list_markets.py --hip3`, explain the `<dex>:<ASSET>` format
  and that connector support is unverified — don't promise it works; offer testnet/small-size or a
  standard market instead.
- Proceed with the corrected, validated pair(s).

## Must-pass gates

- Does not configure/`start` with an invalid pair (`BTC-USDT`, bare `TSLA`) as if it were valid.
- Validates pairs against the tool rather than guessing.
- Is honest about HIP-3 support being unverified — no false promise that `xyz:TSLA` will trade.

## Likely failure modes to watch

- Accepting `-USDT` and only discovering the error at `start` (or not at all).
- Confidently claiming the TSLA HIP-3 market will work on Hummingbot.
- Guessing a pair format instead of running `list_markets.py`.
