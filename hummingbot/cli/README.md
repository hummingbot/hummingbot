# `hbot` — Hummingbot command-line interface

`hbot` runs, controls, and monitors **one Hummingbot bot per install**. It is fully
non-interactive and scriptable: every command prints a table by default, accepts `--json` for
machine-readable output, and returns a **stable exit code**. No MQTT broker or interactive prompts
required.

```bash
hbot --help          # top-level commands
hbot --version
hbot <command> -h    # full help for one command (detail lives here, not in the menu)
```

> One bot per install. To run several bots, use several installs/containers. Starting a second bot
> in the same install fails unless you pass `--replace`.

---

## Mental model

**Three config kinds**, one per source folder. The CLI calls these *types*:

| type | lives in | what it is |
|---|---|---|
| `v1-strategy` | `conf/strategies/` | a classic V1 strategy config |
| `v2-script` | `conf/scripts/` | a V2 script config |
| `controller` | `conf/controllers/` | a V2 controller config (its fields can be tuned live) |

Config **file names are unique across the three folders**, so a bare filename is unambiguous — you
almost never type a type flag. `start` / `set` / `show-config` / `clone` / `update` all detect the
type from the folder that holds the file; a `--v1-strategy` / `--v2-script` / `--controller` flag is
only needed to disambiguate a legacy name that exists under more than one folder.

**"config" vs "settings".** `config` always means a *strategy config file* (managed by `hbot
strategy`). Global client settings (rate source, gateway host, log level, …) are `hbot settings`.

**Controllers** can't run standalone, so `start` generates a tiny V2 loader script for them
automatically; the loader's name becomes the bot's trades-DB and log name. You don't manage the
loader — just `start` the controller config.

---

## Command ontology

```
hbot
│
├─ ── set up (exchanges & funds) ──
│  ├─ connect [exchange]      show connections, or add an exchange's API keys
│  └─ balance [exchange]      show exchange balances, with USD value
│
├─ strategy ── author config files ──
│  ├─ list                    strategies you can create configs from
│  ├─ show <strategy>         a strategy's fields, and which are required
│  ├─ create <strategy>       make a config (fill fields inline with --set)
│  ├─ clone <config>          copy a config to a new name, tweak fields
│  ├─ list-configs            your saved config files
│  ├─ show-config <config>    a config file's contents
│  └─ set <config> <k> <v>    change a field in a config file
│
├─ ── run & control ──
│  ├─ start <config>          start a bot (type auto-detected); --replace to swap
│  ├─ update [key] [value]    view / live-change the running bot's config
│  └─ stop                    stop gracefully (cancels orders); --force to kill
│
├─ ── observe ([name] = a past/stopped bot) ──
│  ├─ status                  run state, live status, recent errors
│  ├─ logs [name]             tail the log (-f to follow)
│  ├─ trades [name]           recorded fills
│  └─ history [name]          PnL, fees, volume per market
│
├─ gateway ── on-chain (DEX) ──
│  ├─ status | start | stop | pull | logs    manage the Gateway service
│  ├─ settings [namespace] [path] [value]    view/change Gateway settings
│  ├─ connect <chain> | disconnect <chain>   wallets (key read from stdin)
│  ├─ balance <network> [wallet]             on-chain balances
│  └─ token-list | token-find | token-add | token-remove   per-network token lists
│
└─ settings [key] [value]     global client settings (conf/conf_client.yml)
```

At most two levels deep; every menu is alphabetical.

---

## Walkthrough

```bash
# 1. connect an exchange (keys are encrypted with your keystore password)
hbot connect hyperliquid_perpetual --fields          # what keys does it need?
hbot connect hyperliquid_perpetual                   # add the keys
hbot balance                                          # confirm funds

# 2. author a config from a strategy
hbot strategy show pmm_simple                         # see the fields
hbot strategy create pmm_simple --name conf_eth.yml \
     --set connector_name=hyperliquid_perpetual \
     --set trading_pair=ETH-USD \
     --set total_amount_quote=100
#  -> Created controller/conf_eth.yml
#     Ready to start: hbot start conf_eth.yml --controller

# 3. run it
hbot start conf_eth.yml                                # type auto-detected
hbot status                                            # is it healthy?
hbot logs -f                                           # watch live (Ctrl-C to stop)

# 4. tune, observe, stop
hbot update buy_spreads 0.001                          # live for controllers (~10s)
hbot trades ; hbot history                             # fills + PnL
hbot stop                                              # graceful, cancels orders

# 5. review a stopped bot later, by name
hbot history conf_eth ; hbot trades conf_eth
```

---

## Authoring configs

```bash
# create from a strategy's defaults; --set fills fields, --values-stdin bulk-fills from JSON
hbot strategy create dman_v3 --name conf_a.yml --set connector_name=binance --set trading_pair=BTC-USDT
echo '{"connector_name":"binance","trading_pair":"BTC-USDT"}' | hbot strategy create dman_v3 --values-stdin

# clone a config you already filled in (same strategy, second pair); a cloned
# controller gets a FRESH id so it won't collide with the original when run
hbot strategy clone conf_eth.yml --name conf_btc.yml --set trading_pair=BTC-USD

# browse & edit existing files
hbot strategy list-configs
hbot strategy show-config conf_eth.yml
hbot strategy set conf_eth.yml total_amount_quote 250
```

- `--set key=value` is repeatable; `--values-stdin` reads a JSON object (pairs with `strategy show
  --json`'s `fields`). Both validate and coerce values.
- `create` is **atomic**: a bad field or value leaves no file behind; a partial config (some required
  still unfilled) is allowed and reports what remains.
- Config names are unique across types: an explicit colliding `--name` fails **with a suggested free
  name**; the default name auto-rolls to the next free `conf_<strategy>_N.yml`.
- **create** starts from a *strategy's* defaults; **clone** starts from a *config file* you already
  filled in (comments preserved). Otherwise they behave identically.

---

## Running & observing

- **One bot per install.** `start` fails if one is already running; pass `--replace` to stop it
  first and start the new one. The config's type is auto-detected from its folder.
- `update key value` writes the running bot's config file; controllers apply live-updatable fields
  within ~10s, other fields (and v1/v2 scripts) take effect on next start — the reply says which.
- `status` reports run state, the strategy's live status, and a count of **recent errors** (a bot can
  be alive *and* erroring — check it). `stop` is graceful and cancels open orders.
- `logs` / `trades` / `history` accept a bot **name** (a config stem from a previous `start`) to
  inspect a past/stopped bot. `history` also fetches live balances, so it's the slowest.
- `logs -f` follows until interrupted — bound it (e.g. a timeout) if you're scripting. Plain `logs`
  returns immediately.

---

## JSON & exit codes

Add `--json` to **any** command for machine-readable output: `{"ok": true, ...}` on success,
`{"ok": false, "error": "...", "code": N}` on failure. Branch on the exit code, not on text:

| code | name | meaning |
|---|---|---|
| 0 | SUCCESS | ok |
| 1 | ERROR | generic failure |
| 2 | NOT_FOUND | the bot/config/file doesn't exist |
| 3 | NOT_RUNNING | the bot exists but its process isn't alive |
| 4 | CONFIG_ERROR | bad/missing config, value, or password |
| 5 | TIMEOUT | operation didn't finish in time |

## Passwords & secrets

The keystore password unlocks your encrypted keys. Provide it without a prompt, and **never on
argv**: set `HBOT_PASSWORD` in the environment, or pipe it with `--password-stdin`
(`printf '%s' "$PW" | hbot start conf_eth.yml --password-stdin`). A missing/wrong password fails fast
with exit code 4 — commands never hang waiting for input.

---

## Gateway (on-chain / DEX)

Gateway is a separate service Hummingbot talks to for on-chain trading. `hbot gateway` manages it and
mirrors the top-level setup verbs for the on-chain world:

```bash
hbot gateway status                               # is it running?
hbot gateway start                                # launch it (secure HTTPS/mTLS mode)
hbot gateway connect solana                       # add a wallet (private key read from stdin)
hbot gateway token-add solana-mainnet-beta <mint> # track a token by address
hbot gateway balance solana-mainnet-beta          # on-chain balances
```

---

## Running in Docker

`hbot`'s "one bot per install" model maps to **one container = one bot**: use the image as the
container's bot process, with `conf/`, `data/`, and `logs/` as mounted volumes.

```yaml
services:
  bot:
    image: hummingbot/hummingbot
    environment: [HBOT_PASSWORD]
    volumes:
      - ./conf:/home/hummingbot/conf
      - ./data:/home/hummingbot/data
      - ./logs:/home/hummingbot/logs
    command: hbot start conf_my_bot.yml        # the container's process IS the bot
```

Drive it from outside with `docker exec bot hbot status` / `hbot logs -f` / `hbot trades`. Don't run
`hbot` *and* the interactive client in the same container — that's two bots fighting over one
`conf`/`data`/`logs`.

**Gateway: run it as a sibling service, not docker-in-docker.** `hbot gateway start/stop/pull/logs`
drive the *host's* Docker, so they don't work from inside a container (they fail with clear guidance,
not a crash). Because `hbot gateway` is URL-first, the fix is to run Gateway as its own service and
point `hbot` at it — every other gateway command (`status`, `balance`, `connect`, `token-*`,
`settings`) then talks to it over the network:

```yaml
services:
  gateway:
    image: hummingbot/gateway
    # ports / certs / gateway-files volume as needed
  bot:
    image: hummingbot/hummingbot
    environment: [HBOT_PASSWORD]
    depends_on: [gateway]
    # point hbot at the Gateway service (once), then skip `hbot gateway start`:
    #   hbot settings gateway.gateway_api_host gateway
```

---

## Files & state

```
conf/strategies/   conf/scripts/   conf/controllers/   # your config files (.yml), by type
conf/conf_client.yml                                   # global settings (hbot settings)
data/bot/                                              # current bot: meta.json, bot.pid, status.json, bot.log
data/<name>.sqlite                                     # a bot's trades DB (name = config stem)
logs/logs_<name>.log                                   # a bot's structured log
```

`status` reads `data/bot/status.json` (a snapshot the running bot writes every few seconds);
`trades` / `history` read the SQLite DB; `logs` tails `logs/logs_<name>.log`. Because these are named
by the config stem, a stopped bot's trades/logs/history stay viewable **by name** indefinitely.
