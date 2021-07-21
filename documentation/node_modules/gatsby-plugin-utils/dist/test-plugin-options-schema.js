"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.testPluginOptionsSchema = testPluginOptionsSchema;

var _regenerator = _interopRequireDefault(require("@babel/runtime/regenerator"));

var _asyncToGenerator2 = _interopRequireDefault(require("@babel/runtime/helpers/asyncToGenerator"));

var _joi = require("./joi");

var _validate = require("./validate");

function testPluginOptionsSchema(_x, _x2) {
  return _testPluginOptionsSchema.apply(this, arguments);
}

function _testPluginOptionsSchema() {
  _testPluginOptionsSchema = (0, _asyncToGenerator2.default)( /*#__PURE__*/_regenerator.default.mark(function _callee(pluginSchemaFunction, pluginOptions) {
    var pluginSchema, errors;
    return _regenerator.default.wrap(function _callee$(_context) {
      while (1) {
        switch (_context.prev = _context.next) {
          case 0:
            pluginSchema = pluginSchemaFunction({
              Joi: _joi.Joi
            });
            _context.prev = 1;
            _context.next = 4;
            return (0, _validate.validateOptionsSchema)(pluginSchema, pluginOptions);

          case 4:
            _context.next = 10;
            break;

          case 6:
            _context.prev = 6;
            _context.t0 = _context["catch"](1);
            errors = _context.t0.details.map(function (detail) {
              return detail.message;
            });
            return _context.abrupt("return", {
              isValid: false,
              errors: errors
            });

          case 10:
            return _context.abrupt("return", {
              isValid: true,
              errors: []
            });

          case 11:
          case "end":
            return _context.stop();
        }
      }
    }, _callee, null, [[1, 6]]);
  }));
  return _testPluginOptionsSchema.apply(this, arguments);
}