# Hummingbot agent skills

The definitive getting-started guide for running Hummingbot strategies with the **`hbot`** CLI.
These skills let an AI agent take a new user from a fresh clone to a running trading bot — no API
server, no message broker, no MCP. `hbot` is the interface; the agent drives it over the shell.

> Reading this in an agent? Start with **`hummingbot-cli`**, then open the skill for the strategy
> the user wants. Repo-level entry point: **`AGENTS.md`** at the repo root.

## Getting started (the flow these skills follow)

1. **Install** — clone the repo, `make install`, `conda activate hummingbot` (full steps in
   `hummingbot-cli`).
2. **Connect & fund** — `hbot connect <exchange>` to store encrypted API keys, `hbot balance` to
   confirm funds.
3. **Pick a strategy** — choose the skill that matches the user's goal (table below).
4. **Configure** — `hbot strategy create <strategy> --set ...` with sane, venue-appropriate defaults.
5. **Run & observe** — `hbot start`, then `hbot status` / `logs` / `trades` / `history`.
6. **Tune & stop** — `hbot update <key> <value>` live, `hbot stop` to wind down (cancels orders).

## Skills

| skill | use it when |
|---|---|
| **`hummingbot-cli`** | Always read first. The operating manual for the `hbot` CLI: install, the `--json`/exit-code contract, password & secret handling, the command map, the core loop, and anti-patterns. |
| **`pure-market-making`** | The user wants to market-make or provide liquidity. Steers to the `pmm_mister` controller (spot + perp, order-level TP/SL, inventory holding), picks sane defaults, and avoids the order-sizing / minimum-notional traps. |

### Planned

- `hyperliquid-trader` — Hyperliquid-specific setup: fetch tradable pairs, identify markets
  (incl. HIP-3 lower-fee markets), create an agent/API wallet, approve the builder fee, and build the
  correct trading-pair format.
- `arbitrage`, `cross-exchange-market-making`, `directional-trading` — additional strategy recipes,
  each building on `hummingbot-cli` the same way `pure-market-making` does.

## Conventions

- Each skill is a directory with a `SKILL.md` (YAML frontmatter: `name`, `description`, `metadata`).
- Strategy skills depend on `hummingbot-cli` and link to it rather than repeating CLI mechanics.
- Full CLI reference lives in **`hummingbot/cli/README.md`**.
