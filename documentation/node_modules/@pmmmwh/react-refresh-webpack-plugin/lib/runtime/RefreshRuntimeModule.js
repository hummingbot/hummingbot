const RuntimeGlobals = require('webpack/lib/RuntimeGlobals');
const RuntimeModule = require('webpack/lib/RuntimeModule');
const Template = require('webpack/lib/Template');
const { refreshGlobal } = require('../globals');
const getRefreshGlobal = require('../utils/getRefreshGlobal');

class ReactRefreshRuntimeModule extends RuntimeModule {
  constructor() {
    // Second argument is the `stage` for this runtime module -
    // we'll use the same stage as Webpack's HMR runtime module for safety.
    super('react refresh', 5);
  }

  /**
   * @returns {string} runtime code
   */
  generate() {
    const { runtimeTemplate } = this.compilation;
    return Template.asString([
      `${RuntimeGlobals.interceptModuleExecution}.push(${runtimeTemplate.basicFunction('options', [
        `${runtimeTemplate.supportsConst() ? 'const' : 'var'} originalFactory = options.factory;`,
        `options.factory = ${runtimeTemplate.basicFunction(
          'moduleObject, moduleExports, webpackRequire',
          [
            `${refreshGlobal}.init();`,
            'try {',
            Template.indent(
              'originalFactory.call(this, moduleObject, moduleExports, webpackRequire);'
            ),
            '} finally {',
            Template.indent(`${refreshGlobal}.cleanup(options.id);`),
            '}',
          ]
        )}`,
      ])})`,
      '',
      getRefreshGlobal(runtimeTemplate),
    ]);
  }
}

module.exports = ReactRefreshRuntimeModule;
