# AGENTS.md

Guidance for AI agents helping a user set up Hummingbot and run trading strategies from this repo.

## What this repo gives you

Hummingbot is a framework for automated trading bots. The recommended way to run one is the **`hbot`
command-line interface** — fully non-interactive and scriptable: every command emits compact
**Markdown** (tables for lists, key-value for records — for humans and agents alike) and returns a
**stable exit code**. No API server, no message broker, no MCP — `hbot` itself is the interface you
drive over the shell.

## Start here: the skills

This repo ships agent skills under **`.agents/skills/`**. Read the relevant one in full before
acting — they contain the exact commands, the JSON/exit-code contract, secret handling, and the
common pitfalls:

- **`.agents/skills/hummingbot-cli/SKILL.md`** — the operating manual for the `hbot` CLI. Install,
  the mental model (one bot per install; three config types), passwords/secrets, the command map,
  the core loop, and anti-patterns. **Read this first.**
- **`.agents/skills/pure-market-making/SKILL.md`** — how to set up and run a market-making bot.
  Steers to the `pmm_mister` controller, picks sane defaults, and avoids the order-sizing /
  minimum-notional traps. **Read this when the user wants to market-make or provide liquidity.**

More strategy skills (arbitrage, cross-exchange market making, directional trading) will be added
alongside these.

## Quick setup (full detail in the hummingbot-cli skill)

Requires Anaconda or Miniconda.

```bash
git clone https://github.com/hummingbot/hummingbot.git
cd hummingbot
make install            # create the conda env, build extensions, expose `hbot`
conda activate hummingbot
hbot --help
```

## Working rules

- **Always `conda activate hummingbot`** before running `hbot`.
- **Output is compact Markdown** (tables for lists, key-value for records) — the same for humans and
  agents; there is no `--json` flag. **Branch on the exit code**, not on the text
  (`0` ok · `1` error · `2` not-found · `3` not-running · `4` config/password · `5` timeout).
- **Never put the keystore password or API keys on the command line.** Use `HBOT_PASSWORD` in the
  environment or `--password-stdin`; add connector keys via `hbot connect` over stdin.
- **Don't guess** strategy or field names — confirm with `hbot strategy list` and
  `hbot strategy show <strategy>`.
- **"Running" ≠ "healthy."** `hbot status` reports a recent-errors count, and a bot can be alive but
  not quoting (e.g. orders below the connector minimum). Verify with `hbot logs`.

## Reference

Full CLI reference: **`hummingbot/cli/README.md`**.
