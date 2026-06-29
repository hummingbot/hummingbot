---
name: hummingbot-cli
description: >-
  Operate the `hbot` command-line interface to run, control, and monitor a Hummingbot trading
  bot from source — non-interactively. Use this when a user wants to set up Hummingbot, connect
  an exchange, author a strategy config, start/stop a bot, or check status, logs, trades, and PnL.
  This is the direct CLI (no API server, no MQTT broker, no MCP) — `hbot` IS the interface.
metadata:
  author: hummingbot
  homepage: https://github.com/hummingbot/hummingbot
  reference: hummingbot/cli/README.md
---

# hummingbot-cli

`hbot` runs **one bot per install**, fully non-interactively. Every command prints a table by
default, accepts `--json` for machine-readable output, and returns a **stable exit code**. There is
no broker, no API server, and no interactive prompt — drive it entirely over the shell.

> For a market-making bot specifically, follow the **`pure-market-making`** skill, which builds on
> this one with the exact `pmm_mister` recipe. This skill is the general operating manual.

## Install (from a fresh clone)

Requires Anaconda or Miniconda.

```bash
git clone https://github.com/hummingbot/hummingbot.git
cd hummingbot
make install          # create the conda env, build extensions, expose `hbot`
conda activate hummingbot
hbot --help           # confirm it works
```

After this, `hbot` is on PATH inside the `hummingbot` env. Always `conda activate hummingbot` before
running `hbot`. (Docker users: `make deploy && make link-cli` instead — same commands afterward.)

## The contract every command honors (this is why it's agent-friendly)

- **`--json` on ANY command** → `{"ok": true, ...}` on success, `{"ok": false, "error": "...", "code": N}`
  on failure. Parse this, don't scrape tables.
- **Branch on the exit code, never on text:**

  | code | name | meaning |
  |---|---|---|
  | 0 | SUCCESS | ok |
  | 1 | ERROR | generic failure |
  | 2 | NOT_FOUND | bot/config/file doesn't exist |
  | 3 | NOT_RUNNING | the bot exists but its process isn't alive |
  | 4 | CONFIG_ERROR | bad/missing config, value, or password |
  | 5 | TIMEOUT | operation didn't finish in time |

- **Commands never hang waiting for input.** A missing/wrong password fails fast with code 4.

## Passwords & secrets

The keystore password unlocks the encrypted API keys. Provide it **without a prompt and never on
argv**:

- `export HBOT_PASSWORD=...` in the environment, or
- pipe it: `printf '%s' "$PW" | hbot start conf.yml --password-stdin`.

On a brand-new install there is no keystore yet — the **first** password you provide (first `connect`
/ `balance` / `start`) becomes the keystore password. Every later command must reuse it. Treat exchange
API keys and wallet private keys as secrets: pass them via stdin/file, never in the command line.

## Mental model

**One bot per install.** Starting a second bot fails unless you pass `--replace`.

**Three config kinds**, one per folder; file names are unique across all three, so a bare filename is
unambiguous and you almost never type a type flag:

| type | folder | what it is |
|---|---|---|
| `v1-strategy` | `conf/strategies/` | classic V1 strategy config |
| `v2-script` | `conf/scripts/` | V2 script config |
| `controller` | `conf/controllers/` | V2 controller config (fields tunable live) |

`start`/`set`/`show-config`/`clone`/`update` auto-detect the type from the folder. **"config" always
means a strategy config file** (managed by `hbot strategy`); global client settings (rate source, log
level) are `hbot settings`. Controllers can't run standalone — `start` generates a tiny V2 loader
script automatically; you just `start` the controller config.

## Command map

```
hbot
├─ connect [exchange]        show connections, or add an exchange's API keys
├─ balance [exchange]        exchange balances, with USD value
├─ strategy
│  ├─ list                   strategies you can create configs from
│  ├─ show <strategy>        a strategy's fields + which are required (--json for machine use)
│  ├─ create <strategy>      make a config (fill fields with --set k=v or --values-stdin)
│  ├─ clone <config>         copy a config to a new name, tweak fields
│  ├─ list-configs           your saved config files
│  ├─ show-config <config>   a config file's contents
│  └─ set <config> <k> <v>   change a field in a config file
├─ start <config>            start a bot (type auto-detected); --replace to swap a running one
├─ update [key] [value]      view / live-change the running bot's config
├─ stop                      stop gracefully (cancels orders); --force to kill
├─ status                    run state, live status, recent errors
├─ logs [name]               tail the log (-f to follow)
├─ trades [name]             recorded fills
├─ history [name]            PnL, fees, volume per market
└─ settings [key] [value]    global client settings
```

`[name]` on observe commands = a config stem from a previous `start`, so a stopped bot's
trades/logs/history stay viewable by name indefinitely.

## Discovering specifics at runtime (don't guess)

- `hbot <command> -h` — full help for one command (detail lives here, not in the menu).
- `hbot strategy list` — exact strategy names you can create from.
- `hbot strategy show <strategy> --json` — authoritative field list: `fields` (name→default),
  `required` (must be filled before start), `live_fields` (changeable while running). Pair this with
  `strategy create --values-stdin` to bulk-fill from a JSON object.

## The core loop

```bash
hbot connect binance                                   # add API keys (encrypted with keystore pw)
hbot balance                                           # confirm funds
hbot strategy show pmm_simple --json                   # inspect fields
hbot strategy create pmm_simple --name conf_my_bot.yml \
     --set connector_name=binance --set trading_pair=BTC-USDT --set total_amount_quote=100
hbot start conf_my_bot.yml                             # type auto-detected
hbot status                                            # healthy? also counts recent errors
hbot logs -f                                           # watch (Ctrl-C to stop; bound it when scripting)
hbot update total_amount_quote 250                     # live for controllers (~10s); reply says when it applies
hbot trades ; hbot history                             # fills + PnL
hbot stop                                              # graceful, cancels open orders
hbot history conf_my_bot                               # review a stopped bot later, by name
```

## Anti-patterns (avoid these)

- **Don't** put passwords or private keys on the command line / argv. Use `HBOT_PASSWORD` or
  `--password-stdin`; keys go in via `connect` over stdin.
- **Don't** scrape table text — add `--json` and branch on `code`.
- **Don't** assume `status` returning "running" means healthy — it reports a **recent-errors count**;
  a bot can be alive and erroring. Check it.
- **Don't** leave `hbot logs -f` running unbounded in a script — it follows until interrupted. Use
  plain `logs` (returns immediately) or wrap `-f` in a timeout.
- **Don't** start a second bot in the same install expecting both to run — it's one bot per install;
  pass `--replace` to swap, or use a separate install/container.
- **Don't** invent strategy or field names — confirm with `strategy list` / `strategy show --json`.

## Reference

Full ontology, walkthrough, JSON/exit-code contract, Docker, and file layout:
**`hummingbot/cli/README.md`**.
