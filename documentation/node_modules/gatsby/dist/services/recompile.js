"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.recompile = recompile;

var _reporter = _interopRequireDefault(require("gatsby-cli/lib/reporter"));

var _redux = require("../redux");

/* eslint-disable no-unused-expressions */
async function recompile({
  webpackWatching
}) {
  if (!webpackWatching) {
    _reporter.default.panic(`Missing compiler`);
  } // Promisify the event-based API. We do this using emitter
  // because you can't "untap" a webpack watcher, and we just want
  // one compilation.


  return new Promise(resolve => {
    function finish(stats) {
      _redux.emitter.off(`COMPILATION_DONE`, finish);

      resolve(stats);
    }

    _redux.emitter.on(`COMPILATION_DONE`, finish);

    webpackWatching.resume(); // Suspending is just a flag, so it's safe to re-suspend right away

    webpackWatching.suspend();
  });
}
//# sourceMappingURL=recompile.js.map