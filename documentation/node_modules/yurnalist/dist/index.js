'use strict';

var _consoleReporter;

function _load_consoleReporter() {
  return _consoleReporter = _interopRequireDefault(require('./reporters/console/console-reporter'));
}

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

const defaultOptions = {
  emoji: true,
  peekMemoryCounter: false
};

function createReporter() {
  let options = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {};

  const reporter = new (_consoleReporter || _load_consoleReporter()).default({
    emoji: options.emoji && process.stdout.isTTY && process.platform === 'darwin',
    verbose: options.verbose,
    noProgress: options.noProgress,
    isSilent: options.silent
  });

  if (options.peekMemoryCounter) {
    reporter.initPeakMemoryCounter();
  }

  return reporter;
}

const reporter = createReporter(defaultOptions);

function bindMethods(methods, instance) {
  return methods.reduce((result, name) => {
    try {
      /* $FlowFixMe: Indexible signature not found */
      result[name] = instance[name].bind(instance);
      return result;
    } catch (e) {
      throw new ReferenceError(`Unable to bind method: ${name}`);
    }
  }, {});
}

const boundMethods = bindMethods(['table', 'step', 'inspect', 'list', 'header', 'footer', 'log', 'success', 'error', 'info', 'command', 'warn', 'question', 'tree', 'activitySet', 'activity', 'select', 'progress', 'close', 'lang'], reporter);

module.exports = Object.assign({}, boundMethods, { createReporter });