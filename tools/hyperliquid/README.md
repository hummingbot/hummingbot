# Hyperliquid builder-code pre-flight (HGP-87)

`builder_code_preflight.py` is a zero-risk smoke test to run **before** enabling
builder-code attribution on a funded Hyperliquid wallet. It exercises the real
connector auth/signing code — **no order is ever placed**.

## Why this and not a testnet order?

The connector **omits** the builder field on testnet by design, so a testnet order
exercises none of the builder path. The checks below are the meaningful validation.

## What it checks

1. **Offline sign-and-recover** (default — no network, no funds, throwaway key):
   builds an order action with the builder field exactly as the connector does on
   mainnet, signs it with the real `HyperliquidAuth` / `HyperliquidPerpetualAuth`,
   then independently recovers the signer from the signature. Proves the signature is
   valid, that it covers the builder field, and that tampering the fee after signing
   breaks recovery. This mirrors Hyperliquid's own server-side signature check.

2. **Live read-only approval query** (`--live`, requires `--user`): POSTs
   `maxBuilderFee` to the public `/info` endpoint (no auth, no order, no funds) and
   applies the `get_builder_info` approval logic. At 0 bps the pair is approved
   trivially (`approved_max >= 0`), which is why the Foundation default needs no
   `ApproveBuilderFee` action.

## Usage

Run from the repo root (inside the `hummingbot` conda env):

```bash
# Offline check for both connectors with a sample builder address, 0 bps:
python tools/hyperliquid/builder_code_preflight.py

# Offline check with your real builder address / fee:
python tools/hyperliquid/builder_code_preflight.py --builder 0xYourBuilder --fee-bps 0

# Also run the live read-only maxBuilderFee query against mainnet:
python tools/hyperliquid/builder_code_preflight.py --live \
    --user 0xYourWallet --builder 0xYourBuilder

# Single connector:
python tools/hyperliquid/builder_code_preflight.py --connector perp
```

Exit code is `0` when all checks pass, `1` otherwise.

## Recommended graduated rollout

1. Run this pre-flight (offline, then `--live` with your address). Confirm all pass.
2. Set `FOUNDATION_BUILDER_ADDRESS` (or a `builder` config override) to your real
   builder address, keeping the fee at 0 bps.
3. Place **one** tiny order on a liquid pair with your real wallet.
4. Confirm attribution in `info` → `{"type":"userFills","user":"0x…"}` and in the
   daily dump `stats-data.hyperliquid.xyz/Mainnet/builder_fills/{builder}/{YYYYMMDD}.csv.lz4`.
   At 0 bps no fee is charged.
