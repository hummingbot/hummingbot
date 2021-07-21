'use strict';

const { readdirSync } = require('fs');
const { spawnSync } = require('child_process');
const path = require('path');

let benchmarks = [];

if (!!process.env.npm_config_benchmarks) {
  benchmarks = process.env.npm_config_benchmarks
    .split(';')
    .map((item) => (item + '.js'));
}

// Run each file in this directory or the list given on the command line except
// index.js as a Node.js process.
(benchmarks.length > 0 ? benchmarks : readdirSync(__dirname))
  .filter((item) => (item !== 'index.js' && item.match(/\.js$/)))
  .map((item) => path.join(__dirname, item))
  .forEach((item) => {
    const child = spawnSync(process.execPath, [
      '--expose-gc',
      item
    ], { stdio: 'inherit' });
    if (child.signal) {
      console.error(`Tests aborted with ${child.signal}`);
      process.exitCode = 1;
    } else {
      process.exitCode = child.status;
    }
    if (child.status !== 0) {
      process.exit(process.exitCode);
    }
  });
