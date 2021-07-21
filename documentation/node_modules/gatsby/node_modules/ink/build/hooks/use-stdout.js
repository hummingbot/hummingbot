"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _react = require("react");

var _StdoutContext = _interopRequireDefault(require("../components/StdoutContext"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var _default = () => (0, _react.useContext)(_StdoutContext.default);

exports.default = _default;