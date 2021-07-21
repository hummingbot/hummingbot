"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.OutboundLink = OutboundLink;
exports.trackCustomEvent = trackCustomEvent;

var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));

var _objectWithoutPropertiesLoose2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutPropertiesLoose"));

var _react = _interopRequireDefault(require("react"));

var _propTypes = _interopRequireDefault(require("prop-types"));

var createFunctionWithTimeout = function createFunctionWithTimeout(callback, opt_timeout) {
  if (opt_timeout === void 0) {
    opt_timeout = 1000;
  }

  var called = false;

  var raceCallback = function raceCallback() {
    if (!called) {
      called = true;
      callback();
    }
  };

  setTimeout(raceCallback, opt_timeout);
  return raceCallback;
};

function OutboundLink(props) {
  var eventCategory = props.eventCategory,
      eventAction = props.eventAction,
      eventLabel = props.eventLabel,
      eventValue = props.eventValue,
      rest = (0, _objectWithoutPropertiesLoose2.default)(props, ["eventCategory", "eventAction", "eventLabel", "eventValue"]);
  return /*#__PURE__*/_react.default.createElement("a", (0, _extends2.default)({}, rest, {
    onClick: function onClick(e) {
      if (typeof props.onClick === "function") {
        props.onClick(e);
      }

      var redirect = true;

      if (e.button !== 0 || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.defaultPrevented) {
        redirect = false;
      }

      if (props.target && props.target.toLowerCase() !== "_self") {
        redirect = false;
      }

      if (window.ga) {
        window.ga("send", "event", {
          eventCategory: eventCategory || "Outbound Link",
          eventAction: eventAction || "click",
          eventLabel: eventLabel || props.href,
          eventValue: eventValue,
          transport: redirect ? "beacon" : "",
          hitCallback: function hitCallback() {
            if (redirect) {
              document.location = props.href;
            }
          }
        });
      } else {
        if (redirect) {
          document.location = props.href;
        }
      }

      return false;
    }
  }));
}

OutboundLink.propTypes = {
  href: _propTypes.default.string,
  target: _propTypes.default.string,
  eventCategory: _propTypes.default.string,
  eventAction: _propTypes.default.string,
  eventLabel: _propTypes.default.string,
  eventValue: _propTypes.default.number,
  onClick: _propTypes.default.func
};
/**
 * This allows the user to create custom events within their Gatsby projects.
 *
 * @param {import('gatsby-plugin-google-analytics').CustomEventArgs} args
 * @see https://developers.google.com/analytics/devguides/collection/analyticsjs/field-reference#events
 */

function trackCustomEvent(_ref) {
  var category = _ref.category,
      action = _ref.action,
      label = _ref.label,
      value = _ref.value,
      _ref$nonInteraction = _ref.nonInteraction,
      nonInteraction = _ref$nonInteraction === void 0 ? false : _ref$nonInteraction,
      transport = _ref.transport,
      hitCallback = _ref.hitCallback,
      _ref$callbackTimeout = _ref.callbackTimeout,
      callbackTimeout = _ref$callbackTimeout === void 0 ? 1000 : _ref$callbackTimeout;

  if (typeof window !== "undefined" && window.ga) {
    var trackingEventOptions = {
      eventCategory: category,
      eventAction: action,
      eventLabel: label,
      eventValue: value,
      nonInteraction: nonInteraction,
      transport: transport
    };

    if (hitCallback && typeof hitCallback === "function") {
      trackingEventOptions.hitCallback = createFunctionWithTimeout(hitCallback, callbackTimeout);
    }

    window.ga("send", "event", trackingEventOptions);
  }
}