---
name: hyperliquid-connector
description: >-
  Set up the Hyperliquid connector (spot or perpetual) with Hummingbot and use it via the `hbot` CLI:
  choose the wallet mode, generate and authorize an API/agent wallet, optionally approve a builder
  fee, find tradable markets / funding / open interest, and build the correct `BASE-QUOTE` pair
  format (including HIP-3 builder-deployed markets). Use this when the user trades on Hyperliquid.
  Builds on `hummingbot-cli`. Bundles helper scripts in `scripts/`.
metadata:
  author: hummingbot
  homepage: https://github.com/hummingbot/hummingbot
  requires: hummingbot-cli
  reference: hummingbot/cli/README.md
---

# hyperliquid-connector

Hyperliquid is a fully on-chain DEX with **perpetual** (`hyperliquid_perpetual`) and **spot**
(`hyperliquid`) connectors. Setup has venue-specific friction the generic CLI skill doesn't cover:
wallet mode, agent-wallet authorization, the builder fee, market/pair discovery. Handle that here,
then hand off to the strategy skill (e.g. `pure-market-making`).

> **Prerequisite:** the **`hummingbot-cli`** skill (install, the Markdown-output + exit-code contract, the
> `hbot connect` flow, secret handling). Never put a private key on the command line or into an agent
> chat — **the user runs `hbot connect hyperliquid_perpetual` interactively in their own terminal**; it
> prompts for the key (hidden) and stores it encrypted, so the agent never sees it. Prefer an
> **`api_wallet`** (agent wallet): it can trade but **cannot withdraw**, so a leak can't move funds.

## Bundled scripts (`scripts/`)

There is no `hbot` command for trading rules or on-chain wallet actions, so this skill ships small,
dependency-light helpers (they use only `eth_account`, a Hummingbot dependency):

| script | what it does | needs a key? |
|---|---|---|
| `list_markets.py` | tradable pairs + trading rules (`BASE-QUOTE`, max leverage, size decimals); `--hip3` for builder dexs | no (public) |
| `market_stats.py` | per-perp funding rate, open interest, mark price, 24h volume | no (public) |
| `create_agent_wallet.py` | generate an API/agent wallet, and (optionally) authorize it via `approveAgent` | only to `--authorize` (main key, stdin) |
| `approve_builder_fee.py` | (optional) authorize a non-zero builder fee | yes (main key, stdin) |

All key-signing scripts **dry-run by default** (print the signed payload + recovered signer for
verification) and only submit on-chain with `--submit`. Run them from the skill's `scripts/` dir.

## 1. Wallet: how `hbot connect hyperliquid_perpetual` authenticates

Run `hbot connect hyperliquid_perpetual --fields` to see the exact prompts. It asks for:

| field | what to enter |
|---|---|
| **mode** | `arb_wallet` or `api_wallet` (see below) |
| **use_vault** | `Yes` only if trading a Hyperliquid **Vault**; otherwise `No` |
| **address** | your **main account** address (the Arbitrum wallet that holds the funds), or the Vault address if `use_vault=Yes` |
| **secret_key** | the **private key that signs** — depends on mode (below) |

Two modes:

- **`api_wallet` (recommended for bots):** an **API/agent wallet** is a separate key authorized to
  trade on your account **without withdrawal permission**. Enter your **main account address** as
  `address` and the **agent wallet's private key** as `secret_key`. Safer: the key can't move funds.
- **`arb_wallet`:** sign directly with your main Arbitrum wallet's private key (`address` and
  `secret_key` are the same wallet). Simpler, but that key has full control — avoid for automation.

### Create an agent wallet

Two ways:

- **UI:** generate + authorize at <https://app.hyperliquid.xyz/API>, which returns the agent key.
- **Script:** `create_agent_wallet.py` generates the keypair locally and can authorize it on-chain:

  ```bash
  python scripts/create_agent_wallet.py                       # just generate a keypair
  # authorize it (signs approveAgent with your MAIN wallet key; dry-run first):
  printf '%s' "$MAIN_WALLET_KEY" | python scripts/create_agent_wallet.py --authorize            # dry run
  printf '%s' "$MAIN_WALLET_KEY" | python scripts/create_agent_wallet.py --authorize --submit    # on-chain
  ```

  It prints the agent **address** and **private key** (store it). Then `hbot connect
  hyperliquid_perpetual` with `mode=api_wallet`, `address=<your main account>`,
  `secret_key=<the agent key>`. The main wallet key is read from `$HL_MAIN_KEY` or stdin — never argv.

The spot connector (`hyperliquid`) authenticates the same way; confirm with
`hbot connect hyperliquid --fields`.

> **Funds note:** Hyperliquid trades against your **Hyperliquid account balance** (USDC on the L1),
> not your raw Arbitrum balance — the user must have deposited/bridged into Hyperliquid first.
> Confirm with `hbot balance hyperliquid_perpetual` after connecting.
>
> **Unified account (no spot↔perp transfer needed):** Hyperliquid uses a **unified account** — your
> USDC balance is shared as collateral across spot and perps, so you do **not** need to move funds
> from spot to perp to trade perps. Note the perp clearinghouse may report `accountValue` of `$0`
> while the USDC sits in spot; that's expected on a unified account and perps still draw on the shared
> balance. (Only if a perp order is rejected for insufficient margin would a `usdClassTransfer`
> spot→perp be needed — rare.)

## 2. Builder fee (usually nothing to do)

Hummingbot attaches a Foundation **builder code** to mainnet Hyperliquid orders. In open-source
Hummingbot this is **0 bps unless the user has separately approved the builder** (a non-zero fee is
only enforced by the Condor-hosted image). So for a normal `hbot` user there is **no builder fee and
nothing to approve** — mention it only if asked. (On testnet / with a Vault the builder field is
omitted entirely.) If a user *does* want to authorize a non-zero fee, `approve_builder_fee.py` does it
(dry-run by default; `--submit` to send).

## 3. Find tradable markets, funding & open interest

**For a single pair's trading rules, use the `hbot` commands** (fuzzy pair matching, including HIP-3
dex-prefixed markets — `spcx` or `xyz:spcx-usd` → `XYZ:SPCX-USD`):

```bash
hbot rules hyperliquid_perpetual eth-usd      # min order size, min notional ($10), tick/step sizes
hbot ticker hyperliquid_perpetual eth-usd     # best bid/ask/mid + last
hbot book hyperliquid_perpetual eth-usd -n 5
```

**For bulk discovery + funding/OI, use the bundled scripts** (public endpoint, no keys needed):

```bash
python scripts/list_markets.py --type perp --filter ETH   # browse pairs + rules
python scripts/list_markets.py --hip3                     # enumerate HIP-3 builder dexs
python scripts/market_stats.py --top 10                   # funding rate (hr + APR), OI, 24h volume
python scripts/market_stats.py --filter SOL               # funding/OI for one market
```

`hbot rules` gives the authoritative per-pair rules straight from the connector; `list_markets.py`
is better for browsing the whole universe, and `market_stats.py` adds funding/open-interest/volume to
pick a liquid market and understand the cost of holding a perp position.

> **Minimum order size:** Hyperliquid enforces a flat **$10 minimum order notional** (per order, both
> spot and perp). Size so each order clears $10 — for `pmm_mister`, recall order notional ≈
> `amount_pct × total_amount_quote × portfolio_allocation` (see the `pure-market-making` skill). A
> below-$10 order is rejected, leaving the bot alive but not quoting.

## 4. Pair format

- **Perp:** `BASE-USD` — e.g. `ETH-USD`, `BTC-USD`. (Hyperliquid perps are USD-margined; bare coin.)
- **Spot:** `BASE-QUOTE` — e.g. `PURR-USDC`, `HYPE-USDC`.
- Use the exact `hummingbot_pair` from `list_markets.py`; don't guess casing or quote currency.

## 5. HIP-3 builder-deployed markets (advanced / experimental)

HIP-3 perps (e.g. tokenized equities like `xyz:TSLA`, `xyz:NVDA`, FX like `xyz:EUR`) live in
**separate dex universes**, not the default market list, and can have **lower fees** (growth mode cuts
protocol fees ~90%). Enumerate them with:

```bash
python scripts/list_markets.py --hip3        # builder dexs + their assets (exchange symbol <dex>:<ASSET>)
```

> **Important:** these use the `<dex>:<ASSET>` exchange-symbol format, and **the Hummingbot
> Hyperliquid connector's support for HIP-3 markets is UNVERIFIED** — it may not map the dex-prefixed
> symbol into a `BASE-QUOTE` pair the connector accepts. Treat HIP-3 as experimental: try it on
> testnet/small size, watch `hbot logs` for symbol-resolution errors, and fall back to a standard
> market if `start` rejects the pair. Don't promise a user a HIP-3 market works until verified.

## End-to-end setup (then hand off to the strategy skill)

```bash
# 1. (optional) generate + authorize an agent wallet, or do it at https://app.hyperliquid.xyz/API
printf '%s' "$MAIN_WALLET_KEY" | python scripts/create_agent_wallet.py --authorize --submit

# 2. connect (key via prompt/stdin), then confirm the Hyperliquid balance is funded
hbot connect hyperliquid_perpetual              # mode=api_wallet, address=main acct, secret=agent key
hbot balance hyperliquid_perpetual

# 3. pick a real, liquid market and read its rules + funding
python scripts/list_markets.py --type perp --filter ETH    # -> ETH-USD  max_lev=25  sz_dec=4
python scripts/market_stats.py --filter ETH

# 4. hand off: configure & run via the strategy skill (e.g. pure-market-making with pmm_mister)
#    connector_name=hyperliquid_perpetual, trading_pair=ETH-USD, conservative leverage (3-5x),
#    sized so each order clears the minimum notional.
```

## Anti-patterns & safety

- **Don't use `arb_wallet` for an unattended bot** — that key can withdraw funds. Prefer an
  `api_wallet` (agent wallet), which can trade but not withdraw.
- **Never put a private key on argv.** Use the `hbot connect` prompt, or `$HL_MAIN_KEY`/stdin for the
  scripts. Dry-run signing scripts before `--submit`.
- **Don't assume the user's funds are tradable** — Hyperliquid trades the L1 account balance; confirm
  with `hbot balance` before starting.
- **Don't guess pairs** — validate with `list_markets.py`. Perps are `BASE-USD`, not `BASE-USDT`.
- **Don't promise HIP-3 markets work** until verified against the connector (see §5).
- **Perp = leverage = liquidation.** Set a conservative leverage for a first run and confirm the user
  intends leveraged trading; spot has no liquidation.

## Reference

CLI reference: **`hummingbot/cli/README.md`**. HL connector:
`hummingbot/connector/derivative/hyperliquid_perpetual/`. Hyperliquid API:
<https://hyperliquid.gitbook.io/hyperliquid-docs>.
