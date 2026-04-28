# Builder/Referral Codes — Design Doc

Covers builder fee integration for two connectors:
1. **Hyperliquid** (`hyperliquid` + `hyperliquid_perpetual`) — builder codes
2. **Jupiter** (gateway) — platform fees

---

# Part 1: Hyperliquid Builder Codes

## What Are Builder Codes?

Builder codes let app developers earn a fee on every fill they route through Hyperliquid on behalf of users.

| | |
|---|---|
| **Fee parameter** | Per-order: `{"b": "<builder_address>", "f": <fee>}` appended to order action |
| **Fee unit** | Tenths of basis points — `f=10` = 1 bp = 0.01% |
| **Max fee** | Perps: 0.1% · Spot: 1% |
| **Builder requirement** | Must hold ≥100 USDC in perps account |
| **User approval** | One-time `ApproveBuilderFee` signed by **primary wallet** (not API wallet) |
| **Check approval** | `POST /info` `{"type": "maxBuilderFee", "user": "0x...", "builder": "0x..."}` → returns approved fee or 0 |

**References:** [Hyperliquid docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes) · [Python SDK example](https://github.com/hyperliquid-dex/hyperliquid-python-sdk/blob/master/examples/basic_builder_fee.py)

---

## Design Principles

1. **Two-tier model** — Standalone Hummingbot works without builder codes. App layers (Condor, etc.) enforce them as a hard gate.
2. **Builder-agnostic connector** — The connector accepts any `builder_address`. No address is hardcoded. Each app injects its own.
3. **Mandatory when configured** — If a builder address is set, user must approve or the connector won't start.
4. **No silent fallback** — Don't fall back to "no builder" if approval fails. This would let users bypass fees.

---

## Hummingbot Connector Changes

### Files
- `hyperliquid_perpetual/hyperliquid_perpetual_utils.py` — config map
- `hyperliquid_perpetual/hyperliquid_perpetual_auth.py` — order signing
- `hyperliquid_perpetual/hyperliquid_perpetual_derivative.py` — place order + startup check
- Same three files under `exchange/hyperliquid/` for spot connector

### 1. Config Map (`utils.py`)

Add two optional fields to `HyperliquidPerpetualConfigMap`:

```python
builder_address: Optional[str] = None   # builder's Ethereum address (lowercase)
builder_fee_bps: int = 10               # fee in tenths of bps (10 = 1bp = 0.01%)
```

Both are `is_connect_key=True`, `prompt_on_new=False` — not shown during normal `connect` flow, but injectable via API or Condor.

### 2. Order Signing (`auth.py`)

In `_sign_order_params()`, append builder to the order action before signing if configured:

```python
order_action = {"type": "order", "orders": [...], "grouping": grouping}
if builder := params.get("builder"):
    order_action["builder"] = builder  # {"b": "0x...", "f": 10}
```

Builder is included in the msgpack hash, so it's part of the signed payload.

### 3. Place Order (`derivative.py`)

In `_place_order()`, add builder to `api_params` if configured:

```python
if self._builder_address:
    api_params["builder"] = {
        "b": self._builder_address.lower(),
        "f": self._builder_fee_bps
    }
```

### 4. Startup Approval Check (`derivative.py`)

On `start()`, if builder is configured, query `maxBuilderFee`:
- **Approved and sufficient** → proceed normally
- **Not approved or fee too low** → raise with a clear message:
  > "Approve builder `0x...` at https://app.hyperliquid.xyz/API before starting this connector."

Connector does not start if approval is missing.

---

## Enforcement Flow

```
Connector start
    │
    ├── builder_address set?
    │       │
    │      No ──→ Start normally (no builder fee)
    │       │
    │      Yes
    │       │
    │       ▼
    │   Check maxBuilderFee API
    │       │
    │   approved ≥ required? ──No──→ FAIL with approval instructions
    │       │
    │      Yes
    │       ▼
    │   Start with builder enabled
    │   (injected per-order at signing time)
```

---

## Implementation Checklist — Hummingbot

- [ ] Add `builder_address` / `builder_fee_bps` to perpetual + spot config maps
- [ ] Inject builder into order action in `_sign_order_params()` (both connectors)
- [ ] Add startup approval check in `start()` / `_initialize_trading_rules()`
- [ ] Unit tests: approved / not approved / fee too low / no builder configured
- [ ] Test that standalone Hummingbot with no builder fields is unaffected

---

# Part 1b: Condor Integration

## Overview

Condor enforces builder codes as a **hard gate** — no Hyperliquid bot can be deployed or trade executed without prior user approval. Condor injects its own builder address transparently at deploy time.

Other apps built on the Hummingbot API follow the same three-step pattern with their own addresses. There is nothing Condor-specific about the mechanism.

---

## Server Config

Builder config is stored per Hummingbot server instance (admin sets once, applies to all users on that server):

```
hl_builder_address: "0x<condor_wallet>"   # Condor's Ethereum address
hl_builder_fee_bps: 10                    # 1 bp = 0.01%
```

Support env var overrides: `HL_BUILDER_ADDRESS`, `HL_BUILDER_FEE_BPS`.

---

## Hard Gate: Approval Required

Before any Hyperliquid bot deploy or trade execution in Condor:

1. Check user state cache for prior approval
2. If no cache → query `maxBuilderFee` live via Hummingbot API (or Hyperliquid directly)
3. Approved and sufficient → cache result, proceed
4. Not approved → **block with Telegram prompt** (see below)

Cache is per-process, keyed by `{user_id, builder_address}`. On Condor restart it re-checks live on first HL action.

---

## Telegram Approval Flow

```
User: /deploy_bot hyperliquid_perpetual ...

Condor → gate check
         ├── cached? → proceed
         ├── live check → approved? → cache + proceed
         └── not approved → send prompt + block

── Prompt ──────────────────────────────────────
⚠️ One-time setup required before trading on Hyperliquid:

1. Go to https://app.hyperliquid.xyz/API
2. Click Approve Builder Fee
3. Enter address: 0x<condor_address>
4. Set max fee: 0.01% (1 basis point)
5. Sign with your primary wallet (not API wallet)

Then tap: [✅ I've Approved]
─────────────────────────────────────────────────

User: taps [✅ I've Approved]

Condor → re-check live
         ├── approved → cache + "✅ Done! You can now deploy bots."
         └── not yet → "Still pending — check the steps above."
```

---

## Bot Deploy: Builder Injection

When Condor deploys a Hyperliquid bot via the Hummingbot API, it appends builder fields to the connector config before sending. The user never sees these fields.

```
DeployBotRequest
    │
    ├── is_hyperliquid_connector?
    │       └── Yes → append builder_address + builder_fee_bps to config
    │
    └── POST /bot/start to Hummingbot API
```

Non-HL connectors are untouched.

---

## Extensibility

Any app on the Hummingbot API uses the same pattern:

1. **Store** their own builder address + fee in their app config
2. **Gate** HL actions behind an approval check
3. **Inject** their builder fields into connector config at deploy time

The Hummingbot connector is neutral — it just reads whatever `builder_address` is in its config.

---

## Implementation Checklist — Condor

**Phase 1: Config & Gate**
- [ ] Add `hl_builder_address` + `hl_builder_fee_bps` to server config
- [ ] Implement `require_hl_builder_approval()` gate (cache → live check → block)
- [ ] Implement `fetch_max_builder_fee()` helper

**Phase 2: Deploy Injection**
- [ ] Implement `inject_builder_config()` — appends builder fields for HL connectors
- [ ] Call gate + inject in bot deploy handler
- [ ] Call gate in direct trade execution handler

**Phase 3: Telegram UX**
- [ ] Send formatted approval prompt on gate failure
- [ ] Inline button `[✅ I've Approved]` → triggers re-check
- [ ] `/check_hl_approval` command for manual re-check
- [ ] Show approval status in `/account` or `/status`

**Phase 4: Tests**
- [ ] Gate: approved / not approved / fee too low / no builder configured
- [ ] Inject: HL connectors get builder fields; non-HL untouched
- [ ] Full deploy flow with builder injection

---

# Part 2: Pacifica Builder Codes

## What Are Pacifica Builder Codes?

Pacifica has a builder program nearly identical in concept to Hyperliquid's, with key implementation differences.

| | Hyperliquid | Pacifica |
|---|---|---|
| **Builder identifier** | Ethereum address (`0x...`) | Alphanumeric string, max 16 chars (e.g. `HBOT`) |
| **Fee unit** | Integer — tenths of bps (`10` = 1bp) | Decimal rate string (`"0.001"` = 0.1%) |
| **Fee placement** | Appended to outer order action after signing | Included **inside** the `data` object — part of the signed payload |
| **User approval** | Requires primary wallet (not API wallet) | Can be signed by API/agent wallet |
| **Check approval** | `POST /info` `{"type": "maxBuilderFee", ...}` | `GET /api/v1/account/builder_codes/approvals?account=...` |
| **Points incentive** | No | Yes — 10M points pool for builder program (active through June 2026) |
| **Onboarding** | No registration needed | Must register via ops@pacifica.fi or Discord |

**References:** [Pacifica Builder Program docs](https://pacifica.gitbook.io/docs/programs/builder-program.md)

---

## Key Technical Difference: Signing

This is the critical difference from Hyperliquid. In Pacifica, `builder_code` must be inside the `data` object that gets signed — not appended afterwards:

```json
// Data to sign (builder_code inside data)
{
    "timestamp": 1716200000000,
    "expiry_window": 30000,
    "type": "create_market_order",
    "data": {
        "symbol": "BTC",
        "amount": "0.1",
        "side": "bid",
        "builder_code": "HBOT"   // ← inside data, signed with everything else
    }
}
```

This means the connector's auth/signing module needs to inject `builder_code` before signing, not after.

---

## Hummingbot Connector Changes

### Files
- `connector/derivative/pacifica_perpetual/pacifica_perpetual_utils.py` — config map
- `connector/derivative/pacifica_perpetual/pacifica_perpetual_auth.py` — order signing
- `connector/derivative/pacifica_perpetual/pacifica_perpetual_derivative.py` — place order + startup check

### 1. Config Map (`utils.py`)

```python
builder_code: Optional[str] = None   # alphanumeric, max 16 chars (e.g. "HBOT")
builder_fee_rate: Optional[str] = None  # decimal rate string (e.g. "0.001" = 0.1%)
```

### 2. Order Signing (`auth.py`)

Inject `builder_code` into the `data` dict **before** generating the signature:

```python
if builder_code := params.get("builder_code"):
    data["builder_code"] = builder_code  # added before signing
```

### 3. Startup Approval Check (`derivative.py`)

On `start()`, if builder is configured:
- `GET /api/v1/account/builder_codes/approvals?account=<wallet>`
- Check if `builder_code` appears in response with `max_fee_rate >= builder_fee_rate`
- If not approved → fail with clear message pointing to approval flow

---

## User Approval Flow

Approval is signed and submitted via REST — importantly, **API/agent wallet can sign** (unlike Hyperliquid which requires primary wallet). This opens the possibility of Condor submitting the approval on behalf of the user if it holds the API key.

```
POST /api/v1/account/builder_codes/approve
{
    "account": "<wallet>",
    "signature": "<sig>",
    "timestamp": <ms>,
    "builder_code": "HBOT",
    "max_fee_rate": "0.001"
}
```

**Important:** User's `max_fee_rate` must be ≥ builder's `fee_rate` or orders are rejected with `403`.

---

## Condor Integration

Same three-step pattern as Hyperliquid, with differences:

| | Hyperliquid | Pacifica |
|---|---|---|
| **Config stored** | `hl_builder_address` + `hl_builder_fee_bps` | `pacifica_builder_code` + `pacifica_builder_fee_rate` |
| **Approval check endpoint** | `POST /info` maxBuilderFee | `GET /api/v1/account/builder_codes/approvals` |
| **Can Condor auto-approve?** | No (requires primary wallet) | Potentially yes (API wallet allowed) |
| **Onboarding required?** | No | Yes — register with Pacifica first |

**Auto-approve opportunity:** Since Pacifica allows API wallet signing, Condor could potentially submit the approval transaction itself when a user connects their Pacifica account — eliminating the manual step entirely. Worth confirming with Pacifica's team.

---

## Implementation Checklist — Pacifica

- [ ] Register Hummingbot builder code with Pacifica (ops@pacifica.fi)
- [ ] Add `builder_code` + `builder_fee_rate` to `PacificaPerpetualConfigMap`
- [ ] Inject `builder_code` into `data` dict before signing in auth module
- [ ] Add startup approval check via `GET .../builder_codes/approvals`
- [ ] Add to Condor server config: `pacifica_builder_code` + `pacifica_builder_fee_rate`
- [ ] Explore auto-approval via API wallet in Condor
- [ ] Unit tests: approval check / injection / no builder configured

---

# Part 3: GRVT Broker ID

## Overview

GRVT uses a **broker ID model** — fundamentally different from Hyperliquid and Pacifica. There is no on-chain approval flow, no per-user authorization, and no fee rate config. The broker ID is a simple string identifier sent as order metadata through a traditional off-chain partnership agreement.

**Connector status:** ✅ Already merged — PR #8107 merged April 13, 2026.

---

## How It Works

The `broker` field is sent in the order `metadata` object, **outside the signed payload**:

```json
{
    "signature": { "r": "...", "s": "...", "v": 27, ... },
    "metadata": {
        "client_order_id": "HBOT-...",
        "broker": "HBOT"    ← not signed, just metadata
    }
}
```

The `HBOT_BROKER_ID = "HBOT"` constant is already hardcoded in `grvt_perpetual_constants.py` and injected on every order in `grvt_perpetual_auth.py`.

---

## Key Differences vs Hyperliquid / Pacifica

| | Hyperliquid | Pacifica | GRVT |
|---|---|---|---|
| **Mechanism** | On-chain builder code | On-chain builder code | Off-chain broker ID |
| **User approval** | Required (primary wallet) | Required (API wallet OK) | None |
| **Fee config** | Per-order in signed payload | Per-order in signed data | Off-chain agreement |
| **Revenue model** | Permissionless, on-chain | Permissionless, on-chain | Partnership agreement |
| **Already in Hummingbot** | Not yet | Not yet | ✅ Yes |
| **Condor work needed** | Gate + inject | Gate + inject | None |

---

## What Needs to Happen

The connector-level work is **done**. Revenue sharing with GRVT requires:

1. **Formal enrollment** in GRVT's broker program (contact GRVT team to register `HBOT` and set up fee sharing terms)
2. **Condor**: No technical changes needed — broker ID is already sent on every order automatically
3. **Extensibility note**: Since broker ID is not user-scoped, Condor can't inject a per-app broker ID at deploy time — all Hummingbot orders share the same `HBOT` ID. Multi-app differentiation would require GRVT to support sub-broker IDs (worth discussing with them)

---

# Part 4: Jupiter Platform Fees

## What Are Platform Fees?

Jupiter's swap API supports a `platformFeeBps` parameter — a percentage of the output token collected as a fee, routed to a fee account controlled by the app builder.

| | |
|---|---|
| **Fee parameter** | `platformFeeBps` in quote request + `feeAccount` in swap request |
| **Fee unit** | Basis points of output token |
| **Max fee** | No hard cap (market-enforced) |
| **User approval** | None — fully transparent, no onboarding |
| **Fee collection** | Output token sent to builder's ATA for that mint |

---

## Gateway Config

Add to `gateway/conf/jupiter.yml`:

```yaml
platformFeeBps: 25           # 0.25%
feeAccount: "YOUR_USDC_ATA"  # Solana associated token account for fee collection
```

Per-mint accounts for multi-token support:

```yaml
feeAccountMints:
  "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC_FEE_ATA"
  "So11111111111111111111111111111111111111112":   "SOL_FEE_ATA"
```

---

## Code Changes

- `getQuote()` — add `platformFeeBps` to quote params
- `buildSwapTransaction()` — add `feeAccount` to swap request
- `getFeeAccountForQuote()` — pick correct ATA based on output mint

---

## Implementation Checklist — Jupiter

- [ ] Add `platformFeeBps` + `feeAccount` / `feeAccountMints` to `JupiterConfig`
- [ ] Update `getQuote()` with fee param
- [ ] Update `buildSwapTransaction()` with fee account
- [ ] Add `getFeeAccountForQuote()` helper
- [ ] Unit tests for fee param injection and account selection

---

# Summary

| | Hyperliquid | Pacifica | GRVT | Jupiter |
|---|---|---|---|---|
| **Mechanism** | On-chain builder code | On-chain builder code | Off-chain broker ID | Platform fee in swap |
| **User approval** | Required (primary wallet) | Required (API wallet OK) | None | None |
| **Fee config** | Address + tenths-of-bps int | Alphanumeric code + decimal rate | String ID (off-chain agreement) | BPS + token ATA |
| **User friction** | One-time onboarding | One-time onboarding | Zero | Zero |
| **Already in Hummingbot** | ❌ Partial (BROKER_ID only) | ❌ Not yet | ✅ Yes (HBOT sent on all orders) | ❌ Not yet |
| **Condor work needed** | Gate + inject | Gate + inject | None | N/A (Gateway) |
| **External enrollment** | No | Yes (ops@pacifica.fi) | Yes (broker agreement) | No |
| **Implementation effort** | High | Medium | Low (enroll only) | Low |
