"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _symbolObservable = _interopRequireDefault(require("symbol-observable"));

var _xstream = _interopRequireDefault(require("xstream"));

var noop = function noop() {};

var config = {
  fromESObservable: function fromESObservable(observable) {
    return _xstream.default.create({
      subscription: null,
      start: function start(listener) {
        this.subscription = observable.subscribe(listener);
      },
      stop: function stop() {
        this.subscription.unsubscribe();
      }
    });
  },
  toESObservable: function toESObservable(stream) {
    var _ref;

    return _ref = {
      subscribe: function subscribe(observer) {
        var listener = {
          next: observer.next || noop,
          error: observer.error || noop,
          complete: observer.complete || noop
        };
        stream.addListener(listener);
        return {
          unsubscribe: function unsubscribe() {
            return stream.removeListener(listener);
          }
        };
      }
    }, _ref[_symbolObservable.default] = function () {
      return this;
    }, _ref;
  }
};
var _default = config;
exports.default = _default;