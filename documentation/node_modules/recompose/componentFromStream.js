"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = exports.componentFromStreamWithConfig = void 0;

var _inheritsLoose2 = _interopRequireDefault(require("@babel/runtime/helpers/inheritsLoose"));

var _react = require("react");

var _changeEmitter = require("change-emitter");

var _symbolObservable = _interopRequireDefault(require("symbol-observable"));

var _setObservableConfig = require("./setObservableConfig");

var componentFromStreamWithConfig = function componentFromStreamWithConfig(config) {
  return function (propsToVdom) {
    return (
      /*#__PURE__*/
      function (_Component) {
        (0, _inheritsLoose2.default)(ComponentFromStream, _Component);

        function ComponentFromStream() {
          var _config$fromESObserva;

          var _this;

          for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
            args[_key] = arguments[_key];
          }

          _this = _Component.call.apply(_Component, [this].concat(args)) || this;
          _this.state = {
            vdom: null
          };
          _this.propsEmitter = (0, _changeEmitter.createChangeEmitter)();
          _this.props$ = config.fromESObservable((_config$fromESObserva = {
            subscribe: function subscribe(observer) {
              var unsubscribe = _this.propsEmitter.listen(function (props) {
                if (props) {
                  observer.next(props);
                } else {
                  observer.complete();
                }
              });

              return {
                unsubscribe: unsubscribe
              };
            }
          }, _config$fromESObserva[_symbolObservable.default] = function () {
            return this;
          }, _config$fromESObserva));
          _this.vdom$ = config.toESObservable(propsToVdom(_this.props$));
          return _this;
        }

        var _proto = ComponentFromStream.prototype;

        _proto.componentWillMount = function componentWillMount() {
          var _this2 = this;

          // Subscribe to child prop changes so we know when to re-render
          this.subscription = this.vdom$.subscribe({
            next: function next(vdom) {
              _this2.setState({
                vdom: vdom
              });
            }
          });
          this.propsEmitter.emit(this.props);
        };

        _proto.componentWillReceiveProps = function componentWillReceiveProps(nextProps) {
          // Receive new props from the owner
          this.propsEmitter.emit(nextProps);
        };

        _proto.shouldComponentUpdate = function shouldComponentUpdate(nextProps, nextState) {
          return nextState.vdom !== this.state.vdom;
        };

        _proto.componentWillUnmount = function componentWillUnmount() {
          // Call without arguments to complete stream
          this.propsEmitter.emit(); // Clean-up subscription before un-mounting

          this.subscription.unsubscribe();
        };

        _proto.render = function render() {
          return this.state.vdom;
        };

        return ComponentFromStream;
      }(_react.Component)
    );
  };
};

exports.componentFromStreamWithConfig = componentFromStreamWithConfig;

var componentFromStream = function componentFromStream(propsToVdom) {
  return componentFromStreamWithConfig(_setObservableConfig.config)(propsToVdom);
};

var _default = componentFromStream;
exports.default = _default;