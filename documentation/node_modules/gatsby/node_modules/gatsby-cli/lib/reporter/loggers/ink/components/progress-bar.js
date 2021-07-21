"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.ProgressBar = ProgressBar;

var _react = _interopRequireDefault(require("react"));

var _ink = require("ink");

var _calcElapsedTime = require("../../../../util/calc-elapsed-time");

const maxWidth = 30;
const minWidth = 10;

const getLength = prop => String(prop).length;

function ProgressBar({
  message,
  current,
  total,
  startTime
}) {
  const percentage = total ? Math.round(current / total * 100) : 0;
  const terminalWidth = process.stdout.columns || 80;
  const availableWidth = terminalWidth - getLength(message) - getLength(current) - getLength(total) - getLength(percentage) - 11; // margins + extra characters

  const progressBarWidth = Math.max(minWidth, Math.min(maxWidth, availableWidth));
  return /*#__PURE__*/_react.default.createElement(_ink.Box, {
    flexDirection: "row"
  }, /*#__PURE__*/_react.default.createElement(_ink.Box, {
    marginRight: 3,
    width: progressBarWidth
  }, "[", /*#__PURE__*/_react.default.createElement(_ink.Box, {
    width: progressBarWidth - 2
  }, `=`.repeat((progressBarWidth - 2) * percentage / 100)), "]"), /*#__PURE__*/_react.default.createElement(_ink.Box, {
    marginRight: 1
  }, (0, _calcElapsedTime.calcElapsedTime)(startTime), " s"), /*#__PURE__*/_react.default.createElement(_ink.Box, {
    marginRight: 1
  }, current, "/", total), /*#__PURE__*/_react.default.createElement(_ink.Box, {
    marginRight: 1
  }, `` + percentage, "%"), /*#__PURE__*/_react.default.createElement(_ink.Box, {
    textWrap: "truncate"
  }, message));
}