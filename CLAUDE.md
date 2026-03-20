> **This file (`CLAUDE.md`) is Claude Code's brain.** Persistent memory and single source of truth for Claude Code sessions. Only improve it — add new knowledge, correct outdated info, reorganize for clarity.

## Mission: Max Profit

**Our primary goal is profit.** We want to generate as much profit as quickly as possible by exploiting market inefficiencies. Everything we do — every feature, every config change, every optimization — must be aimed towards maximizing profitable trades.

### What this means in practice

1. **SIMPLICITY OVER ELEGANCE** — If it works with 5 params, don't add 10. Every new feature = new bug surface. Ask: "Does this DIRECTLY increase profit?"
2. **NO FEATURE CREEP** — Implement ONE thing at a time. Test it works before adding next. Resist "while we're at it..."
3. **PROTECT WHAT WORKS** — If something is profitable, DON'T TOUCH IT unless there's a clear, measurable reason.
4. **SANITY CHECKS BEFORE IMPLEMENTING** — How many new params does this add? How will we know if it's working? What's the rollback plan? Does this need Optuna or can it be heuristic?
5. **DIMENSIONALITY AWARENESS** — More params = harder to optimize. Prefer derived values over optimized values. If Optuna can't converge, simplify.

### Communication rule

**Always call out flaws, mistakes, and bad ideas — immediately and directly.** No sugar coating. If an idea is wrong, over-engineered, or will lose money, say so plainly and explain why. Bruised ego is cheap; lost profit is not.

### Working style

- **Autonomous bug fixing** — If a bug is obvious, just fix it. Don't ask, don't context-switch the user. Fix it, mention what you did, move on.
- **Elegance check** — After implementing, ask "is there a more elegant way?" BUT skip this for simple/trivial fixes.

### Change protocol

1. **DEFINE IS-STATE** — What does it do NOW? Document before touching.
2. **PLAN IMPROVEMENTS** — What's the change? Why is it better? What could break?
3. **ITERATE / SIMPLIFY** — Is this the simplest version? What can we REMOVE?
4. **THEN IMPLEMENT** — Only after 1-3 are solid. One change at a time.
5. **VERIFY BEFORE DONE** — Run tests, check logs, prove it works.

## Current Project

**`limitless-recon`** is the active project. When no other project is specified, always default to working on `limitless-recon`.

## Git Workflow

**We run on the live production machine.** Code changes can break running systems. Always work in a feature branch, not directly on `main`.

1. **Branch** — `git checkout -b <descriptive-branch>` before making changes
2. **Work & test** — Make changes, verify they work
3. **Commit** — Only after everything is verified working
4. **Merge to main** — `git checkout main && git merge <branch>`
5. **Push** — `git push origin main` to sync with GitHub
6. **Clean up** — Delete the feature branch

## Planning

**Plan-first is the default.** Any non-trivial task gets a plan before code. **`plan.md`** (repo root) is the single source of truth for all plans.

## Lessons

Mistakes and hard-won rules. Review at session start. When something breaks, add a rule to prevent it.

- **runtime.json is live-mutated — never commit it with code changes** — The evaluator and hot-eval write to runtime.json continuously. When a change touches both code and runtime.json values: (1) commit code/docs in a separate commit WITHOUT runtime.json, (2) patch runtime.json values separately via edit or script so live mutations aren't clobbered. Only commit runtime.json alongside code if explicitly told to. Always read runtime.json fresh before patching — never assume values match what you last saw.

- **Audit the full pipeline, not just the trader** — Runtime params flow through tracker → trader → evaluator. When checking if a param is "dead", search ALL scripts that read `runtime.overrides` / `runtime.json`, not just trader.py.
- **Runtime overrides: no whitelist, use blocklist** — RuntimeConfig._load() passes ALL keys from runtime.json into overrides except `trading_enabled`, `paused`, and `coins`. When adding a new runtime param, just add it to runtime.json and handle it in trader.apply_runtime_overrides().
- **Every auto-tuned param needs a bidirectional path** — Any evaluator param adjustment MUST have both increase AND decrease conditions, or a safety-net reset for ceiling/floor values.
- **Every new param must exist in its config file** — When adding a new configurable param: (1) add to the config loader with its default, (2) add to the config file, (3) use `rcfg["key"]` not `rcfg.get("key", default)`.
- **Per-cycle multipliers are a latent bug** — Always express auto-tuning drift as a **rate per hour** and scale by actual elapsed time. Store `last_eval_at` per coin and use `_time_scaled_mult(rate, elapsed_h)`.
- **Runtime tunables need top-level keys to be active** — The `_tunables` block in runtime.json is documentation only. Every tunable must exist as a **top-level numeric key** in runtime.json. When adding a new tunable: (1) add description to `_tunables`, (2) add top-level key with value, (3) verify consuming code reads it.
- **BTC-path signals must use btc_z_threshold, not edge_z_threshold** — When signals pass through multiple components, each gate must use the threshold that matches the signal's entry path.
- **Entry gates AND slippage reduction must use raw values, not risk-clamped values** — Risk clamps are for sizing/PnL estimation AFTER the entry decision. ALL comparisons of edge vs slippage must use raw signal strength.
- **σ-based gates must use the right σ, per entry path** — Match the σ to the dimension being gated. SPOT uses `mispricing_std`, BTC-ONLY uses `btc_mispricing_std`, COMBINED gates both legs independently. TP/SL exits and vol-range gates use `hourly_vol`.
- **btc_reversal must use spot dollar prices, not YES probabilities** — btc_reversal compares `btc_entry_spot_price` vs current `btc_spot_price` (dollars), and `min_btc_delta` must be wired through `apply_runtime_overrides()`.
- **Runtime params must be wired end-to-end or they're dead code** — When adding a tunable param, verify the FULL chain: runtime.json → `apply_runtime_overrides()` or `_resolve_coin_param()` → actual gate. Grep for the param name across all scripts — if it only appears in runtime.json and nowhere in .py files, it's dead.
- **Positions MUST track market_id for rollover detection** — `check_positions()` must compare `pos.market_id` vs `prices.market_id` every tick and close immediately on mismatch.
- **Deep ITM entries: static ceiling + slippage gate** — `max_edge_entry_price` is a static backstop (default 0.93). Do NOT Optuna-tune it. The slippage gate handles execution cost dynamically.
- **One-way variance ratchets kill signals silently** — Any auto-adjustment that can only move in one direction will eventually saturate. If you need faster adaptation, shorten the EMA halflife — don't add a one-way ratchet.
- **Live signal processing must match backtester exactly** — Any signal transformation in live must also exist in the backtester, or Optuna will tune params for a signal distribution that doesn't exist in production.
- **COMBINED entries need their own gate, not individual component gates** — COMBINED uses edge_z_threshold on the additive combined_z. A weak BTC confirmation that agrees with spot is still valuable.
- **Bounded buffers can't be observation counters** — Use an uncapped counter (like `vol_tick_count`), NEVER `len(bounded_buffer)`.
- **NEVER hardcode numeric values — always read from config/param_space** — Every number must trace back to runtime.json, config.json, or param_space. Trading thresholds (entry gates, dead-market filters, re-discovery triggers) must use the SAME variable the trader uses — no separate hardcoded copies. Missing value = crash (no fallback defaults), so misconfiguration is caught immediately.
- **NEVER touch the production Anaconda environment** — Production runs on `/opt/miniconda3/bin/python3`. Don't `pip install`, `conda install`, or modify that env. If a `ModuleNotFoundError` crash happens in production, diagnose and report — user will install into the correct conda env.
- **Backtester snapshot replay: never discard data with train/test splits** — With 2h lookback windows and heavy entry gating (z-threshold, price range, execution cost ratio), a 70/30 split leaves ~36min of test data producing <5 trades for most coins → `-inf` scores → Optuna blind. Use all ticks for simulation. Data is too scarce for holdout validation; overfitting risk is acceptable.

## Limitless Recon — Quick Reference

- **`skills/limitless-recon/SKILL.md`** — Commands, key files, config, deps, env vars. Start here.
- **`skills/limitless-recon/ARCHITECTURE.md`** — Signal types, sizing pipeline, roster system, evaluator param tiers, supervisor modes, fair value model.

All code lives under `skills/limitless-recon/scripts/`. Key scripts: `divergence_tracker.py` (core engine), `trader.py` (positions), `evaluator.py` (analysis + tuning), `backtester.py` (Optuna), `supervisor.py` (orchestrator).

**Keep docs in sync:** When changing scripts, config, CLI flags, search spaces, or eval behavior — update SKILL.md and ARCHITECTURE.md in the same commit. Also sync clawd-trades skill if changes affect tunable knobs, param_space structure, or gather_stats report format.

## OpenClaw Context

This workspace runs on **OpenClaw**, a local-first AI assistant platform. Identity file is `SOUL.md` (not CLAUDE.md). Config: `~/.openclaw/openclaw.json`. Skills live in `skills/<name>/` with a `SKILL.md` each (40-80 lines, self-contained). Host: Dell XPS 12, i7-4500U, 7.7 GB RAM, connected via Telegram.

## Memory Systems — DO NOT MIX

Two separate memory systems exist. Never cross-write between them.

1. **OpenClaw memory** — `workspace/memory/` + `workspace/MEMORY.md` — used by the OpenClaw agent (heartbeat, daily logs, personal memory). This is IN the git repo. **Claude Code must NEVER write here.**
2. **Claude Code memory** — `/root/.claude/projects/-root--openclaw-workspace/memory/` — Claude Code's own persistent memory (feedback, user prefs, project context). This is OUTSIDE the repo. **Write Claude Code memories here only.**
