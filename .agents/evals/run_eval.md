# Running an eval (orchestration protocol)

This is the manual/orchestrated procedure. `eval_workflow.mjs` automates the same steps.

## Per scenario

1. **Provision a clean env** (or reset one between scenarios so no keystore/config/bot state leaks):
   ```bash
   .agents/evals/setup_clean_env.sh --branch feat/hbot-cli
   #  -> ENV=hbot-eval-1234   WORKDIR=/tmp/hbot-eval-xxxx/hummingbot
   ```
   Between scenarios on a shared clone, reset state instead of reinstalling:
   `rm -rf <WORKDIR>/conf/connectors/* <WORKDIR>/conf/{strategies,scripts,controllers}/* <WORKDIR>/data/bot`
   and stop any running bot (`conda run -n <ENV> bash -c 'cd <WORKDIR> && hbot stop --force'`).

2. **Spawn the three roles:**
   - **AUT** — a fresh agent with a shell, cwd = `<WORKDIR>`, `conda activate <ENV>`. System prompt:
     *"You are helping a user set up and run a Hummingbot trading bot. Read `AGENTS.md` and the
     skills under `.agents/skills/` and follow them. You have a terminal. The user will talk to you."*
     **No other context** — this is what we're testing.
   - **User-sim** — plays the scenario's persona (`personas.md`) with its opening line and hidden
     facts. Answers the AUT in character; reveals secrets only when asked, via the channel the AUT
     uses (stdin/prompt, never argv).
   - **Judge** — scores at the end.

3. **Relay turns** between user-sim and AUT until the AUT declares done or you hit the **turn cap
   (12)**. Keep a full transcript (every message + every command the AUT runs and its output).

4. **Judge** the transcript + final env state against `rubric.md` and the scenario's must-pass gates.
   Save `results/<scenario>-<YYYYMMDD>.md` with the transcript and the judge JSON.

## Tiers

- **Tier 1** scenarios (02–06) need no live exchange. A bad/empty key failing at `connect` is the
  point; no real funds move.
- **Tier 2** (01, and optionally the live tail of 06) needs real creds. Provide them to the runner as
  env vars (`HBOT_PASSWORD`, the agent-wallet key, the main address); the user-sim hands them to the
  AUT only when asked. **Never commit creds.** Use small size; ensure `hbot stop` runs at the end.

## Credentials for live runs

The eval operator exports the secrets before running; they are never written to a scenario file:

```bash
export HBOT_PASSWORD=...                 # keystore password for the clean env
export HL_AGENT_KEY=...                   # authorized Hyperliquid API/agent wallet private key
export HL_MAIN_ADDRESS=0x...              # main account address (holds funds)
```

The user-sim reads these and provides them in-character when the AUT asks. The AUT must still take
the key via stdin/prompt (a leak onto argv is a must-pass gate failure even in a live run).

## Aggregating

After all scenarios: tabulate per-dimension scores, list every must-pass gate failure, and summarize
the top recurring weaknesses (these become skill/CLI improvements — e.g. "agents repeatedly missed the
min-notional trap" → make `pure-market-making` lead with it, or add a sizing helper).
