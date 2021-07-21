"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.showAnalyticsNotification = showAnalyticsNotification;

var _boxen = _interopRequireDefault(require("boxen"));

const defaultConfig = {
  padding: 1,
  borderColor: `blue`,
  borderStyle: `double`
};
const defaultMessage = `Gatsby collects anonymous usage analytics\n` + `to help improve Gatsby for all users.\n` + `\n` + `If you'd like to opt-out, you can use \`gatsby telemetry --disable\`\n` + `To learn more, checkout https://gatsby.dev/telemetry`;
/**
 * Analytics notice for the end-user
 */

function showAnalyticsNotification(config = defaultConfig, message = defaultMessage) {
  console.log((0, _boxen.default)(message, config));
}