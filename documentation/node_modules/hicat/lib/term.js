/**
 * print() : print(str)
 * Prints the given string `str` to the terminal. If it is too long, it is ran
 * through a pager.
 */

exports.print = function (str) {
  var count = str.split("\n").length;
  var max = 24;
  if (max && count > max) {
    exports.page(str);
  } else {
    process.stdout.write(str);
  }
};

exports.lessOpts = [
  '-R', // raw control chars
  '-S'  // squeeze long lines
];

/**
 * page() : page(str)
 * (private) Prints the `str` through a pager.
 */

exports.page = function (str) {
  var spawn = require('child_process').spawn;
  var child = spawn('less', exports.lessOpts, { stdio: [ 'pipe', 1, 2 ] });
  child.stdin.write(str);
  child.stdin.end();
};
