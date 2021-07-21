"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.addMethod = addMethod;
exports.lazy = exports.ref = exports.boolean = void 0;

var _mixed = _interopRequireDefault(require("./mixed"));

exports.mixed = _mixed.default;

var _boolean = _interopRequireDefault(require("./boolean"));

exports.bool = _boolean.default;

var _string = _interopRequireDefault(require("./string"));

exports.string = _string.default;

var _number = _interopRequireDefault(require("./number"));

exports.number = _number.default;

var _date = _interopRequireDefault(require("./date"));

exports.date = _date.default;

var _object = _interopRequireDefault(require("./object"));

exports.object = _object.default;

var _array = _interopRequireDefault(require("./array"));

exports.array = _array.default;

var _Reference = _interopRequireDefault(require("./Reference"));

var _Lazy = _interopRequireDefault(require("./Lazy"));

var _ValidationError = _interopRequireDefault(require("./ValidationError"));

exports.ValidationError = _ValidationError.default;

var _reach = _interopRequireDefault(require("./util/reach"));

exports.reach = _reach.default;

var _isSchema = _interopRequireDefault(require("./util/isSchema"));

exports.isSchema = _isSchema.default;

var _setLocale = _interopRequireDefault(require("./setLocale"));

exports.setLocale = _setLocale.default;
var boolean = _boolean.default;
exports.boolean = boolean;

var ref = function ref(key, options) {
  return new _Reference.default(key, options);
};

exports.ref = ref;

var lazy = function lazy(fn) {
  return new _Lazy.default(fn);
};

exports.lazy = lazy;

function addMethod(schemaType, name, fn) {
  if (!schemaType || !(0, _isSchema.default)(schemaType.prototype)) throw new TypeError('You must provide a yup schema constructor function');
  if (typeof name !== 'string') throw new TypeError('A Method name must be provided');
  if (typeof fn !== 'function') throw new TypeError('Method function must be provided');
  schemaType.prototype[name] = fn;
}