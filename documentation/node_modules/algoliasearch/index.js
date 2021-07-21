'use strict';

// default entrypoint is the node module
// this is overridden by the `browser` field in package.json
// https://github.com/substack/node-browserify#browser-field
module.exports = require('./src/server/builds/node');
