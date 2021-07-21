const Template = require('webpack/lib/Template');
const { refreshGlobal } = require('../globals');

/**
 * @typedef {Object} RuntimeTemplate
 * @property {function(string, string[]): string} basicFunction
 * @property {function(): boolean} supportsConst
 * @property {function(string, string=): string} returningFunction
 */

/** @type {RuntimeTemplate} */
const FALLBACK_RUNTIME_TEMPLATE = {
  basicFunction(args, body) {
    return `function(${args}) {\n${Template.indent(body)}\n}`;
  },
  supportsConst() {
    return false;
  },
  returningFunction(returnValue, args = '') {
    return `function(${args}) { return ${returnValue}; }`;
  },
};

/**
 * Generates the refresh global runtime template.
 * @param {RuntimeTemplate} [runtimeTemplate] The runtime template helpers.
 * @returns {string} The refresh global runtime template.
 */
function getRefreshGlobal(runtimeTemplate = FALLBACK_RUNTIME_TEMPLATE) {
  const declaration = runtimeTemplate.supportsConst() ? 'const' : 'var';
  return Template.asString([
    `${refreshGlobal} = {`,
    Template.indent([
      `init: ${runtimeTemplate.basicFunction('', [
        `${refreshGlobal}.cleanup = ${runtimeTemplate.returningFunction('undefined')};`,
        `${refreshGlobal}.register = ${runtimeTemplate.returningFunction('undefined')};`,
        `${refreshGlobal}.runtime = {};`,
        `${refreshGlobal}.signature = ${runtimeTemplate.returningFunction(
          runtimeTemplate.returningFunction('type', 'type')
        )};`,
      ])},`,
      `setup: ${runtimeTemplate.basicFunction('currentModuleId', [
        `${declaration} prevCleanup = ${refreshGlobal}.cleanup;`,
        `${declaration} prevReg = ${refreshGlobal}.register;`,
        `${declaration} prevSig = ${refreshGlobal}.signature;`,
        '',
        `${refreshGlobal}.register = ${runtimeTemplate.basicFunction('type, id', [
          `${declaration} typeId = currentModuleId + " " + id;`,
          `${refreshGlobal}.runtime.register(type, typeId);`,
        ])}`,
        '',
        `${refreshGlobal}.signature = ${refreshGlobal}.runtime.createSignatureFunctionForTransform;`,
        '',
        `${refreshGlobal}.cleanup = ${runtimeTemplate.basicFunction('cleanupModuleId', [
          'if (currentModuleId === cleanupModuleId) {',
          Template.indent([
            `${refreshGlobal}.register = prevReg;`,
            `${refreshGlobal}.signature = prevSig;`,
            `${refreshGlobal}.cleanup = prevCleanup;`,
          ]),
          '}',
        ])}`,
      ])},`,
    ]),
    '};',
  ]);
}

module.exports = getRefreshGlobal;
