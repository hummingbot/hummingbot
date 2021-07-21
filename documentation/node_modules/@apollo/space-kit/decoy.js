/* eslint-env node */
/* eslint-disable @typescript-eslint/no-var-requires */
const fetch = require("node-fetch");
const btoa = require("btoa");

async function run() {
  const url = `https://circleci.com/api/v1.1/project/github/apollographql/space-kit/tree/${"undefined"}`;
  const job = "check-label";
  // console.log(JSON.stringify(github.context.payload.pull_request));
  console.log(`curl -d 'build_parameters[CIRCLE_JOB]=${job}' ${url}`);

  try {
    const result = await fetch(url, {
      body: { build_parameters: { CIRCLE_JOB: job } },
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
    console.error(error);
    // core.setFailed(error.message);
  }
}

run();
