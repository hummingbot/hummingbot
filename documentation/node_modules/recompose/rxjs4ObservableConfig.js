"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _symbolObservable = _interopRequireDefault(require("symbol-observable"));

var _rx = _interopRequireDefault(require("rx"));

var config = {
  fromESObservable: function fromESObservable(observable) {
    return _rx.default.Observable.create(function (observer) {
      var _observable$subscribe = observable.subscribe({
        next: function next(val) {
          return observer.onNext(val);
        },
        error: function error(_error) {
          return observer.onError(_error);
        },
        complete: function complete() {
          return observer.onCompleted();
        }
      }),
          unsubscribe = _observable$subscribe.unsubscribe;

      return unsubscribe;
    });
  },
  toESObservable: function toESObservable(rxObservable) {
    var _ref;

    return _ref = {
      subscribe: function subscribe(observer) {
        var subscription = rxObservable.subscribe(function (val) {
          return observer.next(val);
        }, function (error) {
          return observer.error(error);
        }, function () {
          return observer.complete();
        });
        return {
          unsubscribe: function unsubscribe() {
            return subscription.dispose();
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