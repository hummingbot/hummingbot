# SPEC — Hummingbot MM Flat-Only Market Switching Gate

## Objective
Prevent market switching for a coin while that coin has real exposure (filled inventory/open position).
Allow switching only when the coin is flat (no exposure), even if resting quote orders exist.

## Scope
Modify only controller/market-selection logic in Hummingbot binary options controller.

- In scope:
  - `controllers/generic/binary_options/controller.py`
  - `controllers/generic/binary_options/market_manager.py`
  - `controllers/generic/binary_options/config.py`
  - `conf/controllers/binary_options.yml`
  - unit tests under `controllers/generic/binary_options/tests/`

- Out of scope:
  - connector internals
  - websocket subscriptions/transport
  - executor model redesign
  - quote pricing logic

## Required behavior

### 1) Switch policy config
Add a simple policy field to controller config:
- `switch_policy` (string)
- default: `flat_only`

Supported now:
- `flat_only` only

### 2) Exposure-aware switch gate
In market evaluation (where market switch would be applied):
- if `switch_policy == flat_only` and coin has exposure -> DO NOT switch
- if coin is flat -> switching remains allowed per existing score+hysteresis rules

### 3) Exposure definition
For this patch, "has exposure" = coin has any active non-closed executor position/inventory signal.
Resting maker quotes alone should not count as exposure.

Implement from controller state (`executors_info` / tracker) in a pragmatic way that is testable.
Pass exposure guard/callback into `MarketManager` (dependency injection) rather than hard-coding controller internals in `MarketManager`.

### 4) Preserve existing selection model
Do not change current scoring formula or websocket flow.
Only add the flat-only gate before committing a switch.

## Design guidance

### Config
In `BinaryOptionsControllerConfig`:
- add `switch_policy: str = Field(default="flat_only", description="flat_only")`

In YAML config:
- add `switch_policy: flat_only`

### Controller
- add helper like `_coin_has_exposure(coin: str) -> bool`
- create callback/guard for `MarketManager` to query exposure by coin
- ensure callback is available during evaluate flow

### MarketManager
- accept optional exposure guard callback and switch policy in init
- before applying switch for a coin:
  - if policy is `flat_only` and guard says exposure exists: skip switch and keep locked market

## Tests
Add/adjust unit tests to cover at least:
1) `flat_only` + exposure => no switch
2) `flat_only` + no exposure => switch allowed by score/hysteresis
3) existing behavior unaffected for scoring/hysteresis when flat

## Validation
- run targeted tests for market manager/controller modules
- run lint/format hooks if repo enforces them

## Deliverable
- patch implementing flat-only market switch gate
- concise summary of changed files
- confirmation of tests run and pass/fail
