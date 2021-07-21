"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = devAssert;

function devAssert(condition, message) {
  var booleanCondition = Boolean(condition);

  if (!booleanCondition) {
    throw new Error(message);
  }
}
