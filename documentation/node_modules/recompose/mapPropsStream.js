"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = exports.mapPropsStreamWithConfig = void 0;

var _react = require("react");

var _symbolObservable = _interopRequireDefault(require("symbol-observable"));

var _componentFromStream = require("./componentFromStream");

var _setDisplayName = _interopRequireDefault(require("./setDisplayName"));

var _wrapDisplayName = _interopRequireDefault(require("./wrapDisplayName"));

var _setObservableConfig = require("./setObservableConfig");

var identity = function identity(t) {
  return t;
};

var mapPropsStreamWithConfig = function mapPropsStreamWithConfig(config) {
  var componentFromStream = (0, _componentFromStream.componentFromStreamWithConfig)({
    fromESObservable: identity,
    toESObservable: identity
  });
  return function (transform) {
    return function (BaseComponent) {
      var factory = (0, _react.createFactory)(BaseComponent);
      var fromESObservable = config.fromESObservable,
          toESObservable = config.toESObservable;
      return componentFromStream(function (props$) {
        var _ref;

        return _ref = {
          subscribe: function subscribe(observer) {
            var subscription = toESObservable(transform(fromESObservable(props$))).subscribe({
              next: function next(childProps) {
                return observer.next(factory(childProps));
              }
            });
            return {
              unsubscribe: function unsubscribe() {
                return subscription.unsubscribe();
              }
            };
          }
        }, _ref[_symbolObservable.default] = function () {
          return this;
        }, _ref;
      });
    };
  };
};

exports.mapPropsStreamWithConfig = mapPropsStreamWithConfig;

var mapPropsStream = function mapPropsStream(transform) {
  var hoc = mapPropsStreamWithConfig(_setObservableConfig.config)(transform);

  if (process.env.NODE_ENV !== 'production') {
    return function (BaseComponent) {
      return (0, _setDisplayName.default)((0, _wrapDisplayName.default)(BaseComponent, 'mapPropsStream'))(hoc(BaseComponent));
    };
  }

  return hoc;
};

var _default = mapPropsStream;
exports.default = _default;