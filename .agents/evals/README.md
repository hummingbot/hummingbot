# hbot skills — eval framework

Measures how well an agent, equipped only with this repo and its skills (`AGENTS.md` +
`.agents/skills/`), takes a real user from a **fresh clone** to a **running, correctly-configured
bot** — including when the user is confused, careless, or wrong.

The unit under test is **the skills + CLI as an onboarding experience**, not the trading engine.
A scenario passes if the agent reaches the right outcome *and* handles the user well along the way.

## Roles

Each scenario is a three-agent run:

| role | who | given |
|---|---|---|
| **AUT** (agent under test) | a fresh agent, no prior context | a clean clone, `AGENTS.md`, the skills, and a shell. This is what we score. |
| **User-sim** | an LLM playing a persona | the persona spec from `personas.md` + the scenario's opening line and hidden facts (e.g. the real API key, their actual intent). Answers the AUT in character; never volunteers what a real user wouldn't. |
| **Judge** | an LLM (or human) | the full transcript + the final environment state, scored against `rubric.md` and the scenario's must-pass checks. |

## Environment tiers

- **Tier 1 — behavioral (no live exchange, no real funds).** Tests the conversation and decisions:
  did the agent steer a clueless user, refuse to put a key on argv, catch a min-notional
  misconfig, validate a pair, recognize a malformed key and not loop? Most scenarios are Tier 1.
  A bad/empty key is *expected* to fail at `connect` — that failure is the thing being tested.
- **Tier 2 — live end-to-end (real Hyperliquid creds, small size).** Only the happy-path scenario.
  Actually connects, starts a bot, confirms it quotes, then stops. Requires user-provided creds
  (`HBOT_PASSWORD` + a funded Hyperliquid API wallet); never commit them.

## Clean environment

```bash
.agents/evals/setup_clean_env.sh [branch] [workdir]
# clones this repo at <branch> (default: current branch) into <workdir>
# (default: a fresh temp dir), runs `make install` into a throwaway conda env,
# and prints the env name + path. Tear down between scenarios with --teardown.
```

The AUT operates inside that clone with that conda env activated. Reset it between scenarios so no
state leaks (keystore, configs, running bots).

## Running an eval

**Manual / orchestrated (default):** follow `run_eval.md`. For each scenario: provision a clean env,
give the AUT its system prompt (repo + skills only) and the user-sim its persona, relay messages
turn-by-turn until the AUT declares done or hits the turn cap, then run the judge. Save the transcript
and score under `results/<scenario>-<date>.md`.

**Automated:** `Workflow({scriptPath: ".agents/evals/eval_workflow.mjs"})` runs the scenarios as a
fan-out (one pipeline per scenario: AUT⇄user-sim conversation → judge). Tier-2 (the live happy-path)
is gated behind `args.live` — pass `args: {live: true}` to include it; otherwise only the Tier-1
behavioral scenarios run, so it never trades without explicit opt-in.

## What "good" looks like

A high-scoring agent: reads `hummingbot-cli` first; branches on exit codes; discovers fields
with `hbot strategy show` instead of guessing; validates the pair (`list_markets.py`); sizes orders
above the exchange minimum; never echoes or argv-passes secrets; steers an unsure user to
`pmm_mister` with conservative defaults; verifies the bot is *quoting* (not just alive) via `logs`;
and, when something can't work (bad key, unsupported HIP-3 pair), says so plainly instead of faking
success.

## Files

```
README.md          # this file
rubric.md          # scoring dimensions + pass bar
personas.md        # user personas the user-sim plays
scenarios/         # one file per scenario (persona, opening, hidden facts, must-pass checks)
run_eval.md        # the orchestration protocol (manual run)
eval_workflow.mjs   # automated runner (Workflow script)
setup_clean_env.sh # provision/teardown a clean clone + conda env
results/           # saved transcripts + scores (gitignored)
```
