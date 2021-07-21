var _bindInstanceProperty = require("@babel/runtime-corejs3/core-js/instance/bind");

var _getIterator = require("@babel/runtime-corejs3/core-js/get-iterator");

var _Array$isArray = require("@babel/runtime-corejs3/core-js/array/is-array");

var _getIteratorMethod = require("@babel/runtime-corejs3/core-js/get-iterator-method");

var _Symbol = require("@babel/runtime-corejs3/core-js/symbol");

var unsupportedIterableToArray = require("./unsupportedIterableToArray");

function _createForOfIteratorHelperLoose(o, allowArrayLike) {
  var _context;

  var it;

  if (typeof _Symbol === "undefined" || _getIteratorMethod(o) == null) {
    if (_Array$isArray(o) || (it = unsupportedIterableToArray(o)) || allowArrayLike && o && typeof o.length === "number") {
      if (it) o = it;
      var i = 0;
      return function () {
        if (i >= o.length) return {
          done: true
        };
        return {
          done: false,
          value: o[i++]
        };
      };
    }

    throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
  }

  it = _getIterator(o);
  return _bindInstanceProperty(_context = it.next).call(_context, it);
}

module.exports = _createForOfIteratorHelperLoose;