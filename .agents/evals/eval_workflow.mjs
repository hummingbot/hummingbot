export const meta = {
  name: 'hbot-skills-eval',
  description: 'Eval the hbot onboarding skills: simulate users (clueless, careless, stubborn, greedy) against an agent-under-test in a clean clone, then judge against the rubric.',
  phases: [
    { title: 'Provision', detail: 'clean clone + isolated conda env' },
    { title: 'Run', detail: 'AUT <-> user-sim conversation per scenario' },
    { title: 'Judge', detail: 'score each transcript against the rubric' },
  ],
}

// Tier-1 scenarios run by default (no live trading). Pass args = { live: true } to include Tier-2.
const SCENARIOS = [
  { id: '02-clueless-user', persona: 'P2', tier: 1 },
  { id: '03-no-strategy-idea', persona: 'P3', tier: 1 },
  { id: '04-malformed-api-key', persona: 'P4', tier: 1 },
  { id: '05-misconfigured-strategy', persona: 'P5', tier: 1 },
  { id: '06-wrong-pair-hip3', persona: 'P5', tier: 1 },
  { id: '01-happy-path', persona: 'P1', tier: 2 },
]
const TURN_CAP = 12
const live = !!(args && args.live)
const scenarios = SCENARIOS.filter(s => s.tier === 1 || live)

const EVAL_DIR = '.agents/evals'

const TRANSCRIPT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['done', 'message'],
  properties: {
    done: { type: 'boolean', description: 'true when this role considers the task finished' },
    message: { type: 'string', description: 'the message to the other party (for AUT, include a short summary of any commands run and their results)' },
  },
}
const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['scenario', 'scores', 'total', 'gates_failed', 'verdict', 'evidence'],
  properties: {
    scenario: { type: 'string' },
    scores: {
      type: 'object', additionalProperties: false,
      required: ['setup', 'secrets', 'config', 'guidance', 'skill', 'outcome'],
      properties: {
        setup: { type: 'integer' }, secrets: { type: 'integer' }, config: { type: 'integer' },
        guidance: { type: 'integer' }, skill: { type: 'integer' }, outcome: { type: 'integer' },
      },
    },
    total: { type: 'integer' },
    gates_failed: { type: 'array', items: { type: 'string' } },
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    evidence: { type: 'array', items: { type: 'string' } },
    what_would_improve: { type: 'string' },
  },
}

// --- Provision: one clean env; scenarios reset state between runs (see run_eval.md). ---
// If args.env/args.workdir are supplied (env pre-built out of band — the conda+Cython build is slow
// and would hang a workflow agent), use them directly; otherwise an agent runs setup_clean_env.sh.
phase('Provision')
let env
if (args && args.env && args.workdir) {
  env = { env: args.env, workdir: args.workdir, ok: true }
  log(`using pre-provisioned env=${env.env} workdir=${env.workdir}`)
} else {
  env = await agent(
    `Run \`bash ${EVAL_DIR}/setup_clean_env.sh\` from the repo root and return the ENV and WORKDIR it ` +
    `prints. If it fails, return the error.`,
    { label: 'provision', phase: 'Provision',
      schema: { type: 'object', additionalProperties: false, required: ['env', 'workdir', 'ok'],
        properties: { env: { type: 'string' }, workdir: { type: 'string' }, ok: { type: 'boolean' },
          error: { type: 'string' } } } })
}

if (!env || !env.ok) {
  log(`Provisioning failed: ${env ? env.error : 'no result'}`)
  return { error: 'provision_failed', detail: env }
}
log(`clean env=${env.env} workdir=${env.workdir}`)

// --- Run + Judge: pipeline over scenarios (each conversation is independent). ---
phase('Run')
const results = await pipeline(
  scenarios,
  // Stage 1: run the AUT <-> user-sim conversation, return the transcript.
  async (sc) => {
    const scenarioBody = `Read ${EVAL_DIR}/scenarios/${sc.id}.md and ${EVAL_DIR}/personas.md.`
    let transcript = []

    // For the live happy-path, the user-sim sources real creds from the session env and hands them
    // to the AUT only when asked (key via stdin, never argv). Tier-1 scenarios use no real creds.
    const liveCreds = sc.tier === 2
      ? `LIVE creds for this scenario live in the session env: the Hyperliquid agent-wallet private ` +
        `key is in $HL_AGENT_KEY and your main account address is in $HL_MAIN_ADDRESS. When the agent ` +
        `asks for them, provide the address as text and have the agent read the key via stdin (e.g. ` +
        `\`printf '%s' "$HL_AGENT_KEY" | hbot connect ... --... \`) — never reveal the key inline.\n`
      : ''

    for (let i = 0; i < TURN_CAP; i++) {
      // User-sim speaks (in character).
      const u = await agent(
        `You are the USER in an eval, playing persona ${sc.persona}. ${scenarioBody}\n` +
        `Stay strictly in character; reveal hidden facts/keys only when the agent asks, via stdin/prompt. ` +
        liveCreds +
        `Conversation so far (you are USER):\n${JSON.stringify(transcript)}\n` +
        `Produce your next message to the agent. Set done=true only if your goal is met or you give up.`,
        { label: `user:${sc.id}`, phase: 'Run', schema: TRANSCRIPT_SCHEMA })
      if (!u) break
      transcript.push({ role: 'user', text: u.message })
      if (u.done) break

      // Agent-under-test responds (has a shell; works in the clean clone).
      const a = await agent(
        `You are the AGENT UNDER TEST helping a user set up and run a Hummingbot bot. You have a ` +
        `terminal. Work in: cd ${env.workdir} && source "$(conda info --base)/etc/profile.d/conda.sh" && conda activate ${env.env}. Read AGENTS.md and the ` +
        `skills under .agents/skills/ and FOLLOW them. Do NOT read the .agents/evals/ directory — ` +
        `that is the eval harness, not user material. Never put a password or private key on argv.\n` +
        `Conversation so far (you are AGENT):\n${JSON.stringify(transcript)}\n` +
        `Take the next real action (run commands as needed) and reply to the user. Set done=true when ` +
        `the user's task is complete or genuinely blocked.`,
        { label: `aut:${sc.id}`, phase: 'Run', schema: TRANSCRIPT_SCHEMA })
      if (!a) break
      transcript.push({ role: 'agent', text: a.message })
      if (a.done) break
    }
    return { sc, transcript }
  },
  // Stage 2: judge the transcript.
  async (run) => {
    if (!run) return null
    const v = await agent(
      `You are the JUDGE. Score this eval run against ${EVAL_DIR}/rubric.md and the must-pass gates ` +
      `in ${EVAL_DIR}/scenarios/${run.sc.id}.md. Inspect the clean env if useful ` +
      `(cd ${env.workdir} && source "$(conda info --base)/etc/profile.d/conda.sh" && conda activate ${env.env}): check whether a bot is running, whether the ` +
      `config is valid and correctly sized, and whether any secret leaked onto argv or into a file.\n` +
      `Transcript:\n${JSON.stringify(run.transcript)}\n` +
      `Return the verdict JSON.`,
      { label: `judge:${run.sc.id}`, phase: 'Judge', schema: VERDICT_SCHEMA })
    return v
  },
)

const verdicts = results.filter(Boolean)
const passed = verdicts.filter(v => v.verdict === 'PASS').length
log(`eval complete: ${passed}/${verdicts.length} scenarios PASS`)
return { env: env.env, passed, total: verdicts.length, verdicts }
