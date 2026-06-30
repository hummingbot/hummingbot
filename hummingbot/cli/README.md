# `hbot` — Hummingbot command-line interface

`hbot` runs, controls, and monitors **one Hummingbot bot per install**. It is fully
non-interactive and scriptable: every command emits compact **Markdown** (tables for lists,
key-value for records — readable by humans and agents alike) and returns a **stable exit code**.
No `--json` flag, no MQTT broker, no interactive prompts required.

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
strategy`). Global client settings (rate source, log level, …) are `hbot settings`.

**Controllers** can't run standalone, so `start` generates a tiny V2 loader script for them
automatically; the loader's name becomes the bot's trades-DB and log name. You don't manage the
loader — just `start` the controller config.

---

## Command ontology

```
hbot
│
├─ ── set up (exchanges & funds) ──
│  ├─ connectors             list available connectors (spot / perpetual)
│  ├─ connect [exchange]      show connections, or add an exchange's API keys
│  ├─ balance [exchange]      balances + USD value (perps: positions + net value)
│  └─ positions <exchange>    open positions on a perpetual exchange
│
├─ ── market data (public; no keystore; fuzzy pair match) ──
│  ├─ rules <exchange> <pair>      trading rules: min order size, min notional, tick/step
│  ├─ ticker <exchange> <pair>     best bid/ask/mid + last price
│  └─ book <exchange> <pair>       bid/ask depth (-n N levels)
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

- `--set key=value` is repeatable; `--values-stdin` reads a JSON object on stdin (the field names come
  from `strategy show`). Both validate and coerce values.
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

## Output & exit codes

Every command emits compact **Markdown** — a table for a list of records, a `- key: value` block for
a single record — on stdout. Errors print to stderr as `Error: <message> (code N)`. There is **no
`--json` flag**: the Markdown is the format for humans and agents alike. The machine contract is the
**exit code** — branch on it, not on the text:

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

On a brand-new install there's no keystore yet — the **first** password you provide (the first time
you run `hbot connect` / `balance` / `start`) becomes your keystore password, just like the
interactive client's first launch. Every later command must use that same password.

---

## Running in Docker

`hbot` works the same in Docker as from source — same commands, same flow. `make deploy` brings up a
`hummingbot` container as an **idle "hbot host"** (it stays up; you drive it with `hbot` commands),
and `make link-cli` puts an `hbot` wrapper on your host PATH that dispatches into the container:

```bash
make deploy        # start the container (an idle hbot host)
make link-cli      # install the host `hbot` command (-> docker exec into the container)

hbot connect binance              # exactly the same commands as a source install
hbot strategy create pmm_simple --name conf_my_bot.yml --set ...
hbot start conf_my_bot.yml
hbot status ; hbot logs -f ; hbot stop
```

The wrapper (`bin/hbot-host`) auto-detects: a `hummingbot` conda env → run there; else a running
`hummingbot` container → `docker exec` into it. So one `hbot <command>` works regardless of how you
installed. (Without the wrapper, `docker exec -it hummingbot hbot <command>` does the same thing.)

> The idle-host container must run a real init (the compose file sets `init: true`) so the bot
> process — which reparents to PID 1 after the `docker exec` that started it returns — gets **reaped**
> on exit. A bare `tail` PID 1 won't reap it, leaving a zombie that makes `hbot stop` wait its full
> timeout. If you `docker run` your own idle host, pass `--init`.

### One dedicated bot per container

For orchestration (one container = one bot, restart policies), make the bot the container's main
process with `hbot start --foreground` — then `docker stop` sends SIGTERM and the bot shuts down
gracefully (cancelling orders):

```yaml
services:
  bot:
    image: hummingbot/hummingbot
    environment: [HBOT_PASSWORD]
    volumes:
      - ./conf:/home/hummingbot/conf
      - ./data:/home/hummingbot/data
      - ./logs:/home/hummingbot/logs
    command: hbot start conf_my_bot.yml --foreground   # the bot IS the container's PID 1
```

(Without `--foreground`, `hbot start` launches the bot *detached* and returns — fine on a host, but
as a container's command it would exit immediately and stop the container.) Either way, don't run
`hbot` *and* the interactive client in the same container — that's two bots fighting over one
`conf`/`data`/`logs`.

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
