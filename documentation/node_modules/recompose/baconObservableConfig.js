"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _symbolObservable = _interopRequireDefault(require("symbol-observable"));

var _baconjs = _interopRequireDefault(require("baconjs"));

var config = {
  fromESObservable: function fromESObservable(observable) {
    return _baconjs.default.fromBinder(function (sink) {
      var _observable$subscribe = observable.subscribe({
        next: function next(val) {
          return sink(new _baconjs.default.Next(val));
        },
        error: function error(err) {
          return sink(new _baconjs.default.Error(err));
        },
        complete: function complete() {
          return sink(new _baconjs.default.End());
        }
      }),
          unsubscribe = _observable$subscribe.unsubscribe;

      return unsubscribe;
    });
  },
  toESObservable: function toESObservable(stream) {
    var _ref;

    return _ref = {
      subscribe: function subscribe(observer) {
        var unsubscribe = stream.subscribe(function (event) {
          if (event.hasValue()) {
            observer.next(event.value());
          } else if (event.isError()) {
            observer.error(event.error);
          } else if (event.isEnd()) {
            observer.complete();
          }
        });
        return {
          unsubscribe: unsubscribe
        };
      }
    }, _ref[_symbolObservable.default] = function () {
      return this;
    }, _ref;
  }
};
var _default = config;
exports.default = _default;