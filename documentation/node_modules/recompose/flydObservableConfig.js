"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _symbolObservable = _interopRequireDefault(require("symbol-observable"));

var _flyd = _interopRequireDefault(require("flyd"));

var noop = function noop() {};

var config = {
  fromESObservable: function fromESObservable(observable) {
    var stream = _flyd.default.stream();

    var _observable$subscribe = observable.subscribe({
      next: function next(value) {
        return stream(value);
      },
      error: function error(_error) {
        return stream({
          error: _error
        });
      },
      complete: function complete() {
        return stream.end(true);
      }
    }),
        unsubscribe = _observable$subscribe.unsubscribe;

    _flyd.default.on(unsubscribe, stream.end);

    return stream;
  },
  toESObservable: function toESObservable(stream) {
    var _ref;

    return _ref = {
      subscribe: function subscribe(observer) {
        var sub = _flyd.default.on(observer.next || noop, stream);

        _flyd.default.on(function (_) {
          return observer.complete();
        }, sub.end);

        return {
          unsubscribe: function unsubscribe() {
            return sub.end(true);
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