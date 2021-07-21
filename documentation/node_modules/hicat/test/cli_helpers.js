/* jshint expr: true */

var exec = require('child_process').exec;
var bin = './bin/hicat';

/**
 * runs(): runs
 *
 *   describe('running', function () {
 *     run('--help');
 *     success();
 *   });
 */

exports.run = function (args) {
  before(function (next) {
    exec(bin + ' ' + args, function (_exit, _cout, _cerr) {
      global.result = {
        code: _exit && _exit.code || 0,
        error: _exit,
        out: _cout,
        stripped: _cout.replace(/\033\[[^m]*m/g, ''),
        stderr: _cerr
      };
      next();
    });
  });

  after(function () {
    delete global.result;
  });
};

/**
 * success(): asserts success
 *
 *   describe('running', function () {
 *     run('--help');
 *     success();
 *   });
 */

exports.success = function () {
  it('is successful', function () {
    expect(global.result.code).eql(0);
    expect(global.result.error).falsy;
  });
};

/**
 * pipe(): runs and pipes things into stdin
 *
 *   describe('pipes', function () {
 *     pipe('var x = 2', ['--no-pager'])
 *     success();
 *   });
 */

exports.pipe = function (input, args) {
  before(function (next) {
    var spawn = require('child_process').spawn;
    var child = spawn(bin, args || [], { stdio: 'pipe' });
    var result = global.result = { out: '', stderr: '' };

    if (input) {
      child.stdin.write(input);
      child.stdin.end();
    }

    child.stdout.on('data', function (data) { result.out += data; });
    child.stderr.on('data', function (data) { result.stderr += data; });
    child.on('close', function (code) {
      result.code = code;
      next();
    });
  });

  after(function () {
    delete global.result;
  });
};
