/* eslint-disable no-global-assign, no-unused-vars */
/* global $RefreshRuntime$, $RefreshSetup$ */

/**
 * Code prepended to each JS-like module to setup react-refresh globals.
 *
 * All globals are injected via Webpack parser hooks.
 *
 * The function declaration syntax below is needed for `Template.getFunctionContent` to parse this.
 */
module.exports = function () {
  $RefreshRuntime$ = require('react-refresh/runtime');
  $RefreshSetup$(module.id);
};
