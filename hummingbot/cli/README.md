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
almost never type a type flag. `import` / `start` / `config` / `update` all detect the type from the
folder that holds the file; a `--v1-strategy` / `--v2-script` / `--controller` flag is only needed to
disambiguate a legacy name that exists under more than one folder.

**The loaded strategy.** Like the interactive client, `hbot` keeps a *currently loaded* config.
`create <strategy>` and `import <file>` both load one (without starting it); `start <file>` loads and
runs it. Once loaded, `hbot config` shows/edits it, and `hbot start` with no argument runs it. The
pointer lives in `data/bot/loaded.json`; a running bot's own config always takes precedence.

**`config` — one command, two scopes.** `hbot config` shows **global** client settings (rate source,
log level, timeouts — `conf/conf_client.yml`, not encrypted) and, when a strategy is loaded, that
**strategy's** config too. `config <key> <value>` edits whichever scope the key belongs to (global
keys win). This is the v1 CLI's *only* config surface — there is no separate `settings` command.

**Controllers** can't run standalone, so `start` generates a tiny V2 loader script for them
automatically; the loader's name becomes the bot's trades-DB and log name. You don't manage the
loader — just `start` the controller config.

---

## Command ontology

The v1 surface mirrors the interactive Hummingbot client's commands (minus the `gateway` suite). Flat
— no sub-commands — and every menu is alphabetical.

```
hbot
│
├─ ── set up (connectors & funds) ──
│  ├─ connect [connector]        show connections, or add a connector's API keys
│  └─ balance [connector]        balances + USD value (perps: positions + net value)
│
├─ ── market data (public; no keystore; fuzzy pair match) ──
│  ├─ ticker <connector> <pair>  best bid/ask/mid + last price
│  └─ rate <pair>                rate-oracle conversion rate (BASE-QUOTE)
│
├─ ── create, load & configure ──
│  ├─ create <strategy>          create a strategy config (--set k=v, or --with-defaults to scaffold)
│  ├─ import <config>            load an existing config as the current strategy
│  └─ config [key] [value]       global client settings + the loaded strategy's config
│
├─ ── run & control ──
│  ├─ start [config]             start a bot (defaults to the imported config); --replace to swap
│  ├─ update [key] [value]       view / live-change the running bot's config
│  └─ stop                       stop gracefully (cancels orders); --force to kill
│
└─ ── observe ([name] = a past/stopped bot) ──
   ├─ status                     run state, live status, recent errors
   ├─ logs [name]                tail the log (-f to follow)
   └─ history [name]             PnL, fees, volume per market
```

See [Roadmap](#roadmap) for commands intentionally left out of v1 (`positions`, `rules`, `book`,
`connectors`, `trades`, config `clone`/`list`/`show`, `gateway`).

---

## Walkthrough

```bash
# 1. connect a connector (keys are encrypted with your keystore password)
hbot connect hyperliquid_perpetual --fields          # what keys does it need?
hbot connect hyperliquid_perpetual                   # add the keys
hbot balance                                          # confirm funds

# 2. create a strategy config (agents: fill required fields in one shot)
hbot create pmm_simple --name conf_eth.yml \
     --set connector_name=hyperliquid_perpetual --set trading_pair=ETH-USD
#   ...or scaffold it and fill fields afterwards:
hbot create pmm_simple --name conf_eth.yml --with-defaults   # defaults + blanks, and loads it
hbot config                                                  # review global + this strategy's fields
hbot config total_amount_quote 250                           # fill / adjust a field before launch

#   (already have a .yml? skip create and load it:  hbot import conf_eth.yml)

# 3. run it
hbot start                                             # runs the loaded config (or: hbot start conf_eth.yml)
hbot status                                            # is it healthy?
hbot logs -f                                           # watch live (Ctrl-C to stop)

# 4. tune, observe, stop
hbot update buy_spreads 0.001                          # live for controllers (~10s)
hbot history                                           # PnL, fees, volume
hbot stop                                              # graceful, cancels orders

# 5. review a stopped bot later, by name
hbot history conf_eth
```

> **create → config → start.** `create` scaffolds a config from a strategy and *loads* it; `config`
> shows and fills its fields; `start` runs the loaded config. Two ways to fill on create: give every
> required field with `--set key=value` / `--values-stdin` for a **ready-to-run** config (agents), or
> `--with-defaults` to write a **scaffold** (defaults + blank required fields) and finish it with
> `config` (humans). Running `create <strategy>` with a missing required field lists exactly what's
> needed — which also serves as field discovery. Already have a `.yml` (dashboard, API, an example)?
> `import` it instead.

---

## Running & observing

- **One bot per install.** `start` fails if one is already running; pass `--replace` to stop it
  first and start the new one. The config's type is auto-detected from its folder.
- `update key value` writes the running bot's config file; controllers apply live-updatable fields
  within ~10s, other fields (and v1/v2 scripts) take effect on next start — the reply says which.
- `status` reports run state, the strategy's live status, and a count of **recent errors** (a bot can
  be alive *and* erroring — check it). `stop` is graceful and cancels open orders.
- `logs` / `history` accept a bot **name** (a config stem from a previous `start`) to inspect a
  past/stopped bot. `history` also fetches live balances, so it's the slowest.
- `logs -f` follows until interrupted — bound it (e.g. a timeout) if you're scripting. Plain `logs`
  returns immediately.

---

## Roadmap

v1 is a **faithful subset of the interactive Hummingbot client's commands** — the goal is to give
existing source/Docker users the commands they already know, non-interactively. Some commands the
previous CLI shipped are intentionally deferred so v1 stays close to the client's surface. They'll
return in later versions:

| deferred | what it did | v1 alternative |
|---|---|---|
| config `list` / `show` | list creatable strategies; preview a strategy's fields | `create <strategy>` (missing-required error lists fields); `create --with-defaults` + `config` reveals them all |
| config `clone <config>` | copy a config to a new name, tweak fields | `create` a fresh one, or copy the `.yml` by hand |
| `positions <connector>` | open perp positions, standalone | shown inline under `balance` for perp connectors |
| `rules <connector> <pair>` | trading rules (min size/notional, tick/step) | — |
| `book <connector> <pair>` | order-book depth | `ticker` for top-of-book |
| `connectors` | list available connectors | `connect` with no argument lists connections |
| `trades [name]` | recorded fills table | `history` for PnL/fees/volume |
| `gateway …` | Gateway (DEX/AMM) helpers | out of scope for the CLI |

Removing these is not a capability loss in the engine — only in the CLI surface — and each is tracked
to come back once the core client parity is solid.

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

> **Recommended for automated/agent-driven setup.** The image ships with the conda env and compiled
> Cython extensions prebuilt, so there's no Miniconda download, `conda env create`, ToS prompt, or
> multi-minute extension compile — just `make deploy && make link-cli`. Reach for the source install
> only when you're building or modifying the code.

`hbot` works the same in Docker as from source — same commands, same flow. `make deploy` brings up a
`hummingbot` container as an **idle "hbot host"** (it stays up; you drive it with `hbot` commands),
and `make link-cli` puts an `hbot` wrapper on your host PATH that dispatches into the container:

```bash
make deploy        # start the container (an idle hbot host)
make link-cli      # install the host `hbot` command (-> docker exec into the container)

hbot connect binance              # exactly the same commands as a source install
hbot import conf_my_bot.yml       # load a config you've placed in conf/
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
conf/conf_client.yml                                   # global settings (hbot config)
data/bot/                                              # current bot: meta.json, bot.pid, status.json, bot.log, loaded.json
data/<name>.sqlite                                     # a bot's trades DB (name = config stem)
logs/logs_<name>.log                                   # a bot's structured log
```

`status` reads `data/bot/status.json` (a snapshot the running bot writes every few seconds);
`history` reads the SQLite DB; `logs` tails `logs/logs_<name>.log`; `import` / `start` record the
loaded config in `data/bot/loaded.json`. Because the DB and log are named by the config stem, a
stopped bot's logs/history stay viewable **by name** indefinitely.
