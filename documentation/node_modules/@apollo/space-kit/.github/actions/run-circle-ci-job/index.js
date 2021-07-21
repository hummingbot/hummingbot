/* eslint-env node */
/* eslint-disable @typescript-eslint/no-var-requires */
const core = require("@actions/core");
const github = require("@actions/github");
const fetch = require("node-fetch");
const btoa = require("btoa");

async function run() {
  const url = `https://circleci.com/api/v1.1/project/github/apollographql/space-kit/tree/${
    github.context.payload.pull_request.head.ref
  }`;
  const job = core.getInput("job");

  core.debug(
    `curl -u \${CIRCLE_API_TOKEN}: -d 'build_parameters[CIRCLE_JOB]=${job}' ${url}`
  );

  try {
    const result = await fetch(url, {
      body: JSON.stringify({ build_parameters: { CIRCLE_JOB: job } }),
      headers: {
        Authorization: `Basic ${btoa(`${process.env.CIRCLE_API_TOKEN}:`)}`,
        "Content-Type": "application/json",
      },
      method: "POST",
    });

    if (!result.ok) {
      core.setFailed(`${result.status}: ${result.statusText}`);
    }
  } catch (error) {
    core.setFailed(error.message);
  }
}

run();
