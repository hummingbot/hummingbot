'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});

var _asyncToGenerator2;

function _load_asyncToGenerator() {
  return _asyncToGenerator2 = _interopRequireDefault(require('babel-runtime/helpers/asyncToGenerator'));
}

var _baseReporter;

function _load_baseReporter() {
  return _baseReporter = _interopRequireDefault(require('../base-reporter.js'));
}

var _progressBar;

function _load_progressBar() {
  return _progressBar = _interopRequireDefault(require('./progress-bar.js'));
}

var _spinnerProgress;

function _load_spinnerProgress() {
  return _spinnerProgress = _interopRequireDefault(require('./spinner-progress.js'));
}

var _util;

function _load_util() {
  return _util = require('./util.js');
}

var _misc;

function _load_misc() {
  return _misc = require('../../util/misc.js');
}

var _treeHelper;

function _load_treeHelper() {
  return _treeHelper = require('./helpers/tree-helper.js');
}

var _inquirer;

function _load_inquirer() {
  return _inquirer = _interopRequireDefault(require('inquirer'));
}

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var _require = require('util');

const inspect = _require.inspect;

const readline = require('readline');
const chalk = require('chalk');
const read = require('read');
const tty = require('tty');

// fixes bold on windows
if (process.platform === 'win32' && process.env.TERM && !/^xterm/i.test(process.env.TERM)) {
  chalk.styles.bold.close += '\u001b[m';
}

class ConsoleReporter extends (_baseReporter || _load_baseReporter()).default {
  constructor(opts) {
    super(opts);

    this._lastCategorySize = 0;
    this.format = chalk;
    this.isSilent = !!opts.isSilent;
  }

  _prependEmoji(msg, emoji) {
    if (this.emoji && emoji && this.isTTY) {
      msg = `${emoji}  ${msg}`;
    }
    return msg;
  }

  _logCategory(category, color, msg) {
    this._lastCategorySize = category.length;
    this._log(`${this.format[color](category)} ${msg}`);
  }

  _verbose(msg) {
    this._logCategory('verbose', 'grey', `${process.uptime()} ${msg}`);
  }

  _verboseInspect(obj) {
    this.inspect(obj);
  }

  table(head, body) {
    //
    head = head.map(field => this.format.underline(field));

    //
    const rows = [head].concat(body);

    // get column widths
    const cols = [];
    for (let i = 0; i < head.length; i++) {
      const widths = rows.map(row => this.format.stripColor(row[i]).length);
      cols[i] = Math.max(...widths);
    }

    //
    const builtRows = rows.map(row => {
      for (let i = 0; i < row.length; i++) {
        const field = row[i];
        const padding = cols[i] - this.format.stripColor(field).length;

        row[i] = field + ' '.repeat(padding);
      }
      return row.join(' ');
    });

    this.log(builtRows.join('\n'));
  }

  step(current, total, msg, emoji) {
    msg = this._prependEmoji(msg, emoji);

    if (msg.endsWith('?')) {
      msg = `${(0, (_misc || _load_misc()).removeSuffix)(msg, '?')}...?`;
    } else {
      msg += '...';
    }

    this.log(`${this.format.dim(`[${current}/${total}]`)} ${msg}`);
  }

  inspect(value) {
    if (typeof value !== 'number' && typeof value !== 'string') {
      value = inspect(value, {
        breakLength: 0,
        colors: true,
        depth: null,
        maxArrayLength: null
      });
    }

    this.log('' + value);
  }

  list(key, items, hints) {
    const gutterWidth = (this._lastCategorySize || 2) - 1;

    if (hints) {
      for (const item of items) {
        this._log(`${' '.repeat(gutterWidth)}- ${item}`);
        this._log(`  ${' '.repeat(gutterWidth)} ${hints[item]}`);
      }
    } else {
      for (const item of items) {
        this._log(`${' '.repeat(gutterWidth)}- ${item}`);
      }
    }
  }

  header(command, pkg) {
    this.log(this.format.bold(`${pkg.name} ${command} v${pkg.version}`));
  }

  footer(showPeakMemory) {
    const totalTime = (this.getTotalTime() / 1000).toFixed(2);
    let msg = `Done in ${totalTime}s.`;
    if (showPeakMemory) {
      const peakMemory = (this.peakMemory / 1024 / 1024).toFixed(2);
      msg += ` Peak memory usage ${peakMemory}MB.`;
    }
    this.log(this._prependEmoji(msg, '✨'));
  }

  log(msg) {
    this._lastCategorySize = 0;
    this._log(msg);
  }

  _log(msg) {
    if (this.isSilent) {
      return;
    }
    (0, (_util || _load_util()).clearLine)(this.stdout);
    this.stdout.write(`${msg}\n`);
  }

  success(msg) {
    this._logCategory('success', 'green', msg);
  }

  error(msg) {
    (0, (_util || _load_util()).clearLine)(this.stderr);
    this.stderr.write(`${this.format.red('error')} ${msg}\n`);
  }

  info(msg) {
    this._logCategory('info', 'blue', msg);
  }

  command(command) {
    this.log(this.format.dim(`$ ${command}`));
  }

  warn(msg) {
    (0, (_util || _load_util()).clearLine)(this.stderr);
    this.stderr.write(`${this.format.yellow('warning')} ${msg}\n`);
  }

  question(question) {
    let options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};

    if (!process.stdout.isTTY) {
      return Promise.reject(new Error("Can't answer a question unless a user TTY"));
    }

    return new Promise((resolve, reject) => {
      read({
        prompt: `${this.format.dim('question')} ${question}: `,
        silent: !!options.password,
        output: this.stdout,
        input: this.stdin
      }, (err, answer) => {
        if (err) {
          if (err.message === 'canceled') {
            process.exit(1);
          } else {
            reject(err);
          }
        } else {
          if (!answer && options.required) {
            this.error(this.lang('answerRequired'));
            resolve(this.question(question, options));
          } else {
            resolve(answer);
          }
        }
      });
    });
  }
  // handles basic tree output to console
  tree(key, trees) {
    //
    const output = (_ref, titlePrefix, childrenPrefix) => {
      let name = _ref.name,
          children = _ref.children,
          hint = _ref.hint,
          color = _ref.color;

      const formatter = this.format;
      const out = (0, (_treeHelper || _load_treeHelper()).getFormattedOutput)({
        prefix: titlePrefix,
        hint,
        color,
        name,
        formatter
      });
      this.stdout.write(out);

      if (children && children.length) {
        (0, (_treeHelper || _load_treeHelper()).recurseTree)((0, (_treeHelper || _load_treeHelper()).sortTrees)(children), childrenPrefix, output);
      }
    };
    (0, (_treeHelper || _load_treeHelper()).recurseTree)((0, (_treeHelper || _load_treeHelper()).sortTrees)(trees), '', output);
  }

  activitySet(total, workers) {
    if (!this.isTTY || this.noProgress) {
      return super.activitySet(total, workers);
    }

    const spinners = [];

    for (let i = 1; i < workers; i++) {
      this.log('');
    }

    for (let i = 0; i < workers; i++) {
      const spinner = new (_spinnerProgress || _load_spinnerProgress()).default(this.stderr, i);
      spinner.start();

      let prefix = null;
      let current = 0;
      const updatePrefix = () => {
        spinner.setPrefix(`${this.format.dim(`[${current === 0 ? '-' : current}/${total}]`)} `);
      };
      const clear = () => {
        prefix = null;
        current = 0;
        updatePrefix();
        spinner.setText('waiting...');
      };
      clear();

      spinners.unshift({
        clear,

        setPrefix(_current, _prefix) {
          current = _current;
          prefix = _prefix;
          spinner.setText(prefix);
          updatePrefix();
        },

        tick(msg) {
          if (prefix) {
            msg = `${prefix}: ${msg}`;
          }
          spinner.setText(msg);
        },

        end() {
          spinner.stop();
        }
      });
    }

    return {
      spinners,
      end: () => {
        for (const spinner of spinners) {
          spinner.end();
        }
        readline.moveCursor(this.stdout, 0, -workers + 1);
      }
    };
  }

  activity() {
    if (!this.isTTY) {
      return {
        tick() {},
        end() {}
      };
    }

    const spinner = new (_spinnerProgress || _load_spinnerProgress()).default(this.stderr);
    spinner.start();

    return {
      tick(name) {
        spinner.setText(name);
      },

      end() {
        spinner.stop();
      }
    };
  }

  select(header, question, options) {
    if (!this.isTTY) {
      return Promise.reject(new Error("Can't answer a question unless a user TTY"));
    }

    const rl = readline.createInterface({
      input: this.stdin,
      output: this.stdout,
      terminal: true
    });

    const questions = options.map(opt => opt.name);
    const answers = options.map(opt => opt.value);

    function toIndex(input) {
      const index = answers.indexOf(input);

      if (index >= 0) {
        return index;
      } else {
        return +input;
      }
    }

    return new Promise(resolve => {
      this.info(header);

      for (let i = 0; i < questions.length; i++) {
        this.log(`  ${this.format.dim(`${i + 1})`)} ${questions[i]}`);
      }

      const ask = () => {
        rl.question(`${question}: `, input => {
          let index = toIndex(input);

          if (isNaN(index)) {
            this.log('Not a number');
            ask();
            return;
          }

          if (index <= 0 || index > options.length) {
            this.log('Outside answer range');
            ask();
            return;
          }

          // get index
          index--;
          rl.close();
          resolve(answers[index]);
        });
      };

      ask();
    });
  }

  progress(count) {
    if (this.noProgress || count <= 0) {
      return function () {
        // noop
      };
    }

    if (!this.isTTY) {
      return function () {
        // TODO what should the behaviour here be? we could buffer progress messages maybe
      };
    }

    const bar = new (_progressBar || _load_progressBar()).default(count, this.stderr);

    bar.render();

    return function () {
      bar.tick();
    };
  }

  prompt(message, choices) {
    var _this = this;

    let options = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {};
    return (0, (_asyncToGenerator2 || _load_asyncToGenerator()).default)(function* () {
      if (!process.stdout.isTTY) {
        return Promise.reject(new Error("Can't answer a question unless a user TTY"));
      }

      let pageSize;
      if (process.stdout instanceof tty.WriteStream) {
        pageSize = process.stdout.rows - 2;
      }

      const rl = readline.createInterface({
        input: _this.stdin,
        output: _this.stdout,
        terminal: true
      });

      const prompt = (_inquirer || _load_inquirer()).default.createPromptModule({
        input: _this.stdin,
        output: _this.stdout
      });

      let rejectRef = function () {};
      const killListener = function () {
        rejectRef();
      };

      const handleKillFromInquirer = new Promise(function (resolve, reject) {
        rejectRef = reject;
      });

      rl.addListener('SIGINT', killListener);

      var _options$name = options.name;
      const name = _options$name === undefined ? 'prompt' : _options$name;
      var _options$type = options.type;
      const type = _options$type === undefined ? 'input' : _options$type,
            validate = options.validate;

      const answers = yield Promise.race([prompt([{ name, type, message, choices, pageSize, validate }]), handleKillFromInquirer]);

      rl.removeListener('SIGINT', killListener);
      rl.close();

      return answers[name];
    })();
  }
}
exports.default = ConsoleReporter;