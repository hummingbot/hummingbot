"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.coerceValue = coerceValue;

var _inspect = _interopRequireDefault(require("../jsutils/inspect"));

var _printPathArray = _interopRequireDefault(require("../jsutils/printPathArray"));

var _Path = require("../jsutils/Path");

var _GraphQLError = require("../error/GraphQLError");

var _coerceInputValue = require("./coerceInputValue");

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

/* istanbul ignore file */

/**
 * Deprecated. Use coerceInputValue() directly for richer information.
 *
 * This function will be removed in v15
 */
function coerceValue(inputValue, type, blameNode, path) {
  var errors = [];
  var value = (0, _coerceInputValue.coerceInputValue)(inputValue, type, function (errorPath, invalidValue, error) {
    var errorPrefix = 'Invalid value ' + (0, _inspect.default)(invalidValue);
    var pathArray = [].concat((0, _Path.pathToArray)(path), errorPath);

    if (pathArray.length > 0) {
      errorPrefix += " at \"value".concat((0, _printPathArray.default)(pathArray), "\"");
    }

    errors.push(new _GraphQLError.GraphQLError(errorPrefix + ': ' + error.message, blameNode, undefined, undefined, undefined, error.originalError));
  });
  return errors.length > 0 ? {
    errors: errors,
    value: undefined
  } : {
    errors: undefined,
    value: value
  };
}
