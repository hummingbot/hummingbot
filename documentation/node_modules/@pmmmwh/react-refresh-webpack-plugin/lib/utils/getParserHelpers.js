const { webpackVersion } = require('../globals');

/**
 * @callback EvaluateToString
 * @param {string} value
 * @returns {function(*): *}
 */

/**
 * @callback ToConstantDependency
 * @param {*} parser
 * @param {string} value
 * @param {string[]} [runtimeRequirements]
 * @returns {function(*): boolean}
 */

/**
 * @typedef {Object} ParserHelpers
 * @property {EvaluateToString} evaluateToString
 * @property {ToConstantDependency} toConstantDependency
 */

/**
 * Gets parser helpers for specific webpack versions.
 * @returns {ParserHelpers} The needed parser helpers.
 */
function getParserHelpers() {
  if (webpackVersion === 4) {
    const {
      evaluateToString,
      toConstantDependencyWithWebpackRequire,
    } = require('webpack/lib/ParserHelpers');
    return {
      evaluateToString,
      toConstantDependency: toConstantDependencyWithWebpackRequire,
    };
  }

  if (webpackVersion === 5) {
    return require('webpack/lib/javascript/JavascriptParserHelpers');
  }
}

module.exports = getParserHelpers;
