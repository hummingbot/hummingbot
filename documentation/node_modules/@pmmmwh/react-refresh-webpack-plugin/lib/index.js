const validateOptions = require('schema-utils');
const { DefinePlugin, ModuleFilenameHelpers, ProvidePlugin, Template } = require('webpack');
const ConstDependency = require('webpack/lib/dependencies/ConstDependency');
const { refreshGlobal, webpackVersion } = require('./globals');
const {
  createError,
  getParserHelpers,
  getRefreshGlobal,
  getSocketIntegration,
  injectRefreshEntry,
  injectRefreshLoader,
  normalizeOptions,
} = require('./utils');
const schema = require('./options.json');

// Mapping of react-refresh globals to Webpack runtime globals
const REPLACEMENTS = {
  $RefreshRuntime$: {
    expr: `${refreshGlobal}.runtime`,
    req: [`${refreshGlobal}.runtime`],
    type: 'object',
  },
  $RefreshSetup$: {
    expr: `${refreshGlobal}.setup`,
    req: [`${refreshGlobal}.setup`],
    type: 'function',
  },
  $RefreshCleanup$: {
    expr: `${refreshGlobal}.cleanup`,
    req: [`${refreshGlobal}.cleanup`],
    type: 'function',
  },
  $RefreshReg$: {
    expr: `${refreshGlobal}.register`,
    req: [`${refreshGlobal}.register`],
    type: 'function',
  },
  $RefreshSig$: {
    expr: `${refreshGlobal}.signature`,
    req: [`${refreshGlobal}.signature`],
    type: 'function',
  },
};

class ReactRefreshPlugin {
  /**
   * @param {import('./types').ReactRefreshPluginOptions} [options] Options for react-refresh-plugin.
   */
  constructor(options = {}) {
    validateOptions(schema, options, {
      name: 'React Refresh Plugin',
      baseDataPath: 'options',
    });

    /**
     * @readonly
     * @type {import('./types').NormalizedPluginOptions}
     */
    this.options = normalizeOptions(options);
  }

  /**
   * Applies the plugin.
   * @param {import('webpack').Compiler} compiler A webpack compiler object.
   * @returns {void}
   */
  apply(compiler) {
    // Throw if we encounter an unsupported Webpack version,
    // since things will most likely not work.
    if (webpackVersion !== 4 && webpackVersion !== 5) {
      throw createError(`Webpack v${webpackVersion} is not supported!`);
    }

    // Skip processing in non-development mode, but allow manual force-enabling
    if (
      // Webpack do not set process.env.NODE_ENV, so we need to check for mode.
      // Ref: https://github.com/webpack/webpack/issues/7074
      (compiler.options.mode !== 'development' ||
        // We also check for production process.env.NODE_ENV,
        // in case it was set and mode is non-development (e.g. 'none')
        (process.env.NODE_ENV && process.env.NODE_ENV === 'production')) &&
      !this.options.forceEnable
    ) {
      return;
    }

    // Inject react-refresh context to all Webpack entry points
    compiler.options.entry = injectRefreshEntry(compiler.options.entry, this.options);

    // Inject necessary modules to bundle's global scope
    /** @type {Record<string, string>} */
    let providedModules = {
      __react_refresh_utils__: require.resolve('./runtime/RefreshUtils'),
    };

    if (this.options.overlay === false) {
      // Stub errorOverlay module so calls to it can be erased
      const definePlugin = new DefinePlugin({
        __react_refresh_error_overlay__: false,
        __react_refresh_init_socket__: false,
      });
      definePlugin.apply(compiler);
    } else {
      providedModules = {
        ...providedModules,
        ...(this.options.overlay.module && {
          __react_refresh_error_overlay__: require.resolve(this.options.overlay.module),
        }),
        ...(this.options.overlay.sockIntegration && {
          __react_refresh_init_socket__: getSocketIntegration(this.options.overlay.sockIntegration),
        }),
      };
    }

    const providePlugin = new ProvidePlugin(providedModules);
    providePlugin.apply(compiler);

    const matchObject = ModuleFilenameHelpers.matchObject.bind(undefined, this.options);
    const { evaluateToString, toConstantDependency } = getParserHelpers();
    compiler.hooks.compilation.tap(
      this.constructor.name,
      (compilation, { normalModuleFactory }) => {
        // Only hook into the current compiler
        if (compilation.compiler !== compiler) {
          return;
        }

        // Set template for ConstDependency which is used by parser hooks
        compilation.dependencyTemplates.set(ConstDependency, new ConstDependency.Template());

        // Tap into version-specific compilation hooks
        switch (webpackVersion) {
          case 4: {
            const outputOptions = compilation.mainTemplate.outputOptions;
            compilation.mainTemplate.hooks.require.tap(
              this.constructor.name,
              // Constructs the module template for react-refresh
              (source, chunk, hash) => {
                // Check for the output filename
                // This is to ensure we are processing a JS-related chunk
                let filename = outputOptions.filename;
                if (typeof filename === 'function') {
                  // Only usage of the `chunk` property is documented by Webpack.
                  // However, some internal Webpack plugins uses other properties,
                  // so we also pass them through to be on the safe side.
                  filename = filename({
                    contentHashType: 'javascript',
                    chunk,
                    hash,
                  });
                }

                // Check whether the current compilation is outputting to JS,
                // since other plugins can trigger compilations for other file types too.
                // If we apply the transform to them, their compilation will break fatally.
                // One prominent example of this is the HTMLWebpackPlugin.
                // If filename is falsy, something is terribly wrong and there's nothing we can do.
                if (!filename || !filename.includes('.js')) {
                  return source;
                }

                // Split template source code into lines for easier processing
                const lines = source.split('\n');
                // Webpack generates this line when the MainTemplate is called
                const moduleInitializationLineNumber = lines.findIndex((line) =>
                  line.includes('modules[moduleId].call(')
                );
                // Unable to find call to module execution -
                // this happens if the current module does not call MainTemplate.
                // In this case, we will return the original source and won't mess with it.
                if (moduleInitializationLineNumber === -1) {
                  return source;
                }

                const moduleInterceptor = Template.asString([
                  `${refreshGlobal}.init();`,
                  'try {',
                  Template.indent(lines[moduleInitializationLineNumber]),
                  '} finally {',
                  Template.indent(`${refreshGlobal}.cleanup(moduleId);`),
                  '}',
                ]);

                return Template.asString([
                  ...lines.slice(0, moduleInitializationLineNumber),
                  '',
                  outputOptions.strictModuleExceptionHandling
                    ? Template.indent(moduleInterceptor)
                    : moduleInterceptor,
                  '',
                  ...lines.slice(moduleInitializationLineNumber + 1, lines.length),
                ]);
              }
            );

            compilation.mainTemplate.hooks.requireExtensions.tap(
              this.constructor.name,
              // Setup react-refresh globals as extensions to Webpack's require function
              (source) => {
                return Template.asString([source, '', getRefreshGlobal()]);
              }
            );

            normalModuleFactory.hooks.afterResolve.tap(
              this.constructor.name,
              // Add react-refresh loader to process files that matches specified criteria
              (data) => {
                return injectRefreshLoader(data, matchObject);
              }
            );

            compilation.hooks.normalModuleLoader.tap(
              // `Infinity` ensures this check will run only after all other taps
              { name: this.constructor.name, stage: Infinity },
              // Check for existence of the HMR runtime -
              // it is the foundation to this plugin working correctly
              (context) => {
                if (!context.hot) {
                  throw createError(
                    [
                      'Hot Module Replacement (HMR) is not enabled!',
                      'React Refresh requires HMR to function properly.',
                    ].join(' ')
                  );
                }
              }
            );

            break;
          }
          case 5: {
            const NormalModule = require('webpack/lib/NormalModule');
            const RuntimeGlobals = require('webpack/lib/RuntimeGlobals');
            const ReactRefreshRuntimeModule = require('./runtime/RefreshRuntimeModule');

            compilation.hooks.additionalTreeRuntimeRequirements.tap(
              this.constructor.name,
              // Setup react-refresh globals with a Webpack runtime module
              (chunk, runtimeRequirements) => {
                runtimeRequirements.add(RuntimeGlobals.interceptModuleExecution);
                compilation.addRuntimeModule(chunk, new ReactRefreshRuntimeModule());
              }
            );

            normalModuleFactory.hooks.afterResolve.tap(
              this.constructor.name,
              // Add react-refresh loader to process files that matches specified criteria
              (resolveData) => {
                injectRefreshLoader(resolveData.createData, matchObject);
              }
            );

            NormalModule.getCompilationHooks(compilation).loader.tap(
              // `Infinity` ensures this check will run only after all other taps
              { name: this.constructor.name, stage: Infinity },
              // Check for existence of the HMR runtime -
              // it is the foundation to this plugin working correctly
              (context) => {
                if (!context.hot) {
                  throw createError(
                    [
                      'Hot Module Replacement (HMR) is not enabled!',
                      'React Refresh requires HMR to function properly.',
                    ].join(' ')
                  );
                }
              }
            );

            break;
          }
          default: {
            throw createError(`Encountered unexpected Webpack version (v${webpackVersion})`);
          }
        }

        /**
         * Transform global calls into Webpack runtime calls.
         * @param {*} parser
         * @returns {void}
         */
        const parserHandler = (parser) => {
          Object.entries(REPLACEMENTS).forEach(([key, info]) => {
            parser.hooks.expression
              .for(key)
              .tap(this.constructor.name, toConstantDependency(parser, info.expr, info.req));

            if (info.type) {
              parser.hooks.evaluateTypeof
                .for(key)
                .tap(this.constructor.name, evaluateToString(info.type));
            }
          });
        };

        normalModuleFactory.hooks.parser
          .for('javascript/auto')
          .tap(this.constructor.name, parserHandler);
        normalModuleFactory.hooks.parser
          .for('javascript/dynamic')
          .tap(this.constructor.name, parserHandler);
        normalModuleFactory.hooks.parser
          .for('javascript/esm')
          .tap(this.constructor.name, parserHandler);
      }
    );
  }
}

module.exports.ReactRefreshPlugin = ReactRefreshPlugin;
module.exports = ReactRefreshPlugin;
