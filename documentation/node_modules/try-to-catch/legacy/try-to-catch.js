'use strict';

function _toConsumableArray(arr) { return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _nonIterableSpread(); }

function _nonIterableSpread() { throw new TypeError("Invalid attempt to spread non-iterable instance"); }

function _iterableToArray(iter) { if (Symbol.iterator in Object(iter) || Object.prototype.toString.call(iter) === "[object Arguments]") return Array.from(iter); }

function _arrayWithoutHoles(arr) { if (Array.isArray(arr)) { for (var i = 0, arr2 = new Array(arr.length); i < arr.length; i++) { arr2[i] = arr[i]; } return arr2; } }

var success = function success(a) {
  return [null, a];
};

var fail = function fail(a) {
  return [a];
};

var noArg = function noArg(f, a) {
  return function () {
    return f.apply(void 0, _toConsumableArray(a));
  };
};

module.exports = function (fn) {
  check(fn);

  for (var _len = arguments.length, args = new Array(_len > 1 ? _len - 1 : 0), _key = 1; _key < _len; _key++) {
    args[_key - 1] = arguments[_key];
  }

  return Promise.resolve().then(noArg(fn, args)).then(success).catch(fail);
};

function check(fn) {
  if (typeof fn !== 'function') throw Error('fn should be a function!');
}