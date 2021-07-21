"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.validateOptionsSchema = validateOptionsSchema;

var _regenerator = _interopRequireDefault(require("@babel/runtime/regenerator"));

var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));

var _asyncToGenerator2 = _interopRequireDefault(require("@babel/runtime/helpers/asyncToGenerator"));

var validationOptions = {
  // Show all errors at once, rather than only the first one every time
  abortEarly: false,
  cache: true
};

function validateOptionsSchema(_x, _x2, _x3) {
  return _validateOptionsSchema.apply(this, arguments);
}

function _validateOptionsSchema() {
  _validateOptionsSchema = (0, _asyncToGenerator2.default)( /*#__PURE__*/_regenerator.default.mark(function _callee(pluginSchema, pluginOptions, options) {
    var _options, validateExternalRules, value;

    return _regenerator.default.wrap(function _callee$(_context) {
      while (1) {
        switch (_context.prev = _context.next) {
          case 0:
            if (options === void 0) {
              options = {
                validateExternalRules: true
              };
            }

            _options = options, validateExternalRules = _options.validateExternalRules;
            _context.next = 4;
            return pluginSchema.validateAsync(pluginOptions, (0, _extends2.default)({}, validationOptions, {
              externals: validateExternalRules
            }));

          case 4:
            value = _context.sent;
            return _context.abrupt("return", value);

          case 6:
          case "end":
            return _context.stop();
        }
      }
    }, _callee);
  }));
  return _validateOptionsSchema.apply(this, arguments);
}