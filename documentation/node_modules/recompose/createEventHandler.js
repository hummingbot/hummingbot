"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = exports.createEventHandlerWithConfig = void 0;

var _symbolObservable = _interopRequireDefault(require("symbol-observable"));

var _changeEmitter = require("change-emitter");

var _setObservableConfig = require("./setObservableConfig");

var createEventHandlerWithConfig = function createEventHandlerWithConfig(config) {
  return function () {
    var _config$fromESObserva;

    var emitter = (0, _changeEmitter.createChangeEmitter)();
    var stream = config.fromESObservable((_config$fromESObserva = {
      subscribe: function subscribe(observer) {
        var unsubscribe = emitter.listen(function (value) {
          return observer.next(value);
        });
        return {
          unsubscribe: unsubscribe
        };
      }
    }, _config$fromESObserva[_symbolObservable.default] = function () {
      return this;
    }, _config$fromESObserva));
    return {
      handler: emitter.emit,
      stream: stream
    };
  };
};

exports.createEventHandlerWithConfig = createEventHandlerWithConfig;
var createEventHandler = createEventHandlerWithConfig(_setObservableConfig.config);
var _default = createEventHandler;
exports.default = _default;