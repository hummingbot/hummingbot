#!/usr/bin/env node

function isTrue(value) {
  return !!value && value !== "0" && value !== "false"
}

var envDisable = isTrue(process.env.DISABLE_OPENCOLLECTIVE) || isTrue(process.env.OPEN_SOURCE_CONTRIBUTOR) || isTrue(process.env.CI);
var logLevel = process.env.npm_config_loglevel;
var logLevelDisplay = ['silent', 'error', 'warn'].indexOf(logLevel) > -1;

if (!envDisable && !logLevelDisplay) {
  var pkg = require(require('path').resolve('./package.json'));
  if (pkg.collective) {
    console.log(`\u001b[96m\u001b[1mThank you for using ${pkg.name}!\u001b[96m\u001b[1m`);
    console.log(`\u001b[0m\u001b[96mIf you rely on this package, please consider supporting our open collective:\u001b[22m\u001b[39m`);
    console.log(`> \u001b[94m${pkg.collective.url}/donate\u001b[0m\n`);
  }
}
