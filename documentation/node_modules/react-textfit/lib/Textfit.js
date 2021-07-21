'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _extends = Object.assign || function (target) { for (var i = 1; i < arguments.length; i++) { var source = arguments[i]; for (var key in source) { if (Object.prototype.hasOwnProperty.call(source, key)) { target[key] = source[key]; } } } return target; };

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

var _react = require('react');

var _react2 = _interopRequireDefault(_react);

var _propTypes = require('prop-types');

var _propTypes2 = _interopRequireDefault(_propTypes);

var _shallowEqual = require('./utils/shallowEqual');

var _shallowEqual2 = _interopRequireDefault(_shallowEqual);

var _series = require('./utils/series');

var _series2 = _interopRequireDefault(_series);

var _whilst = require('./utils/whilst');

var _whilst2 = _interopRequireDefault(_whilst);

var _throttle = require('./utils/throttle');

var _throttle2 = _interopRequireDefault(_throttle);

var _uniqueId = require('./utils/uniqueId');

var _uniqueId2 = _interopRequireDefault(_uniqueId);

var _innerSize = require('./utils/innerSize');

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _objectWithoutProperties(obj, keys) { var target = {}; for (var i in obj) { if (keys.indexOf(i) >= 0) continue; if (!Object.prototype.hasOwnProperty.call(obj, i)) continue; target[i] = obj[i]; } return target; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

function assertElementFitsWidth(el, width) {
    // -1: temporary bugfix, will be refactored soon
    return el.scrollWidth - 1 <= width;
}

function assertElementFitsHeight(el, height) {
    // -1: temporary bugfix, will be refactored soon
    return el.scrollHeight - 1 <= height;
}

function noop() {}

var TextFit = function (_React$Component) {
    _inherits(TextFit, _React$Component);

    function TextFit(props) {
        _classCallCheck(this, TextFit);

        var _this = _possibleConstructorReturn(this, (TextFit.__proto__ || Object.getPrototypeOf(TextFit)).call(this, props));

        _this.state = {
            fontSize: null,
            ready: false
        };

        _this.handleWindowResize = function () {
            _this.process();
        };

        if ('perfectFit' in props) {
            console.warn('TextFit property perfectFit has been removed.');
        }
        return _this;
    }

    _createClass(TextFit, [{
        key: 'componentWillMount',
        value: function componentWillMount() {
            this.handleWindowResize = (0, _throttle2.default)(this.handleWindowResize, this.props.throttle);
        }
    }, {
        key: 'componentDidMount',
        value: function componentDidMount() {
            var autoResize = this.props.autoResize;

            if (autoResize) {
                window.addEventListener('resize', this.handleWindowResize);
            }
            this.process();
        }
    }, {
        key: 'componentDidUpdate',
        value: function componentDidUpdate(prevProps) {
            var ready = this.state.ready;

            if (!ready) return;
            if ((0, _shallowEqual2.default)(this.props, prevProps)) return;
            this.process();
        }
    }, {
        key: 'componentWillUnmount',
        value: function componentWillUnmount() {
            var autoResize = this.props.autoResize;

            if (autoResize) {
                window.removeEventListener('resize', this.handleWindowResize);
            }
            // Setting a new pid will cancel all running processes
            this.pid = (0, _uniqueId2.default)();
        }
    }, {
        key: 'process',
        value: function process() {
            var _this2 = this;

            var _props = this.props,
                min = _props.min,
                max = _props.max,
                mode = _props.mode,
                forceSingleModeWidth = _props.forceSingleModeWidth,
                onReady = _props.onReady;

            var el = this._parent;
            var wrapper = this._child;

            var originalWidth = (0, _innerSize.innerWidth)(el);
            var originalHeight = (0, _innerSize.innerHeight)(el);

            if (originalHeight <= 0 || isNaN(originalHeight)) {
                console.warn('Can not process element without height. Make sure the element is displayed and has a static height.');
                return;
            }

            if (originalWidth <= 0 || isNaN(originalWidth)) {
                console.warn('Can not process element without width. Make sure the element is displayed and has a static width.');
                return;
            }

            var pid = (0, _uniqueId2.default)();
            this.pid = pid;

            var shouldCancelProcess = function shouldCancelProcess() {
                return pid !== _this2.pid;
            };

            var testPrimary = mode === 'multi' ? function () {
                return assertElementFitsHeight(wrapper, originalHeight);
            } : function () {
                return assertElementFitsWidth(wrapper, originalWidth);
            };

            var testSecondary = mode === 'multi' ? function () {
                return assertElementFitsWidth(wrapper, originalWidth);
            } : function () {
                return assertElementFitsHeight(wrapper, originalHeight);
            };

            var mid = void 0;
            var low = min;
            var high = max;

            this.setState({ ready: false });

            (0, _series2.default)([
            // Step 1:
            // Binary search to fit the element's height (multi line) / width (single line)
            function (stepCallback) {
                return (0, _whilst2.default)(function () {
                    return low <= high;
                }, function (whilstCallback) {
                    if (shouldCancelProcess()) return whilstCallback(true);
                    mid = parseInt((low + high) / 2, 10);
                    _this2.setState({ fontSize: mid }, function () {
                        if (shouldCancelProcess()) return whilstCallback(true);
                        if (testPrimary()) low = mid + 1;else high = mid - 1;
                        return whilstCallback();
                    });
                }, stepCallback);
            },
            // Step 2:
            // Binary search to fit the element's width (multi line) / height (single line)
            // If mode is single and forceSingleModeWidth is true, skip this step
            // in order to not fit the elements height and decrease the width
            function (stepCallback) {
                if (mode === 'single' && forceSingleModeWidth) return stepCallback();
                if (testSecondary()) return stepCallback();
                low = min;
                high = mid;
                return (0, _whilst2.default)(function () {
                    return low < high;
                }, function (whilstCallback) {
                    if (shouldCancelProcess()) return whilstCallback(true);
                    mid = parseInt((low + high) / 2, 10);
                    _this2.setState({ fontSize: mid }, function () {
                        if (pid !== _this2.pid) return whilstCallback(true);
                        if (testSecondary()) low = mid + 1;else high = mid - 1;
                        return whilstCallback();
                    });
                }, stepCallback);
            },
            // Step 3
            // Limits
            function (stepCallback) {
                // We break the previous loop without updating mid for the final time,
                // so we do it here:
                mid = Math.min(low, high);

                // Ensure we hit the user-supplied limits
                mid = Math.max(mid, min);
                mid = Math.min(mid, max);

                // Sanity check:
                mid = Math.max(mid, 0);

                if (shouldCancelProcess()) return stepCallback(true);
                _this2.setState({ fontSize: mid }, stepCallback);
            }], function (err) {
                // err will be true, if another process was triggered
                if (err || shouldCancelProcess()) return;
                _this2.setState({ ready: true }, function () {
                    return onReady(mid);
                });
            });
        }
    }, {
        key: 'render',
        value: function render() {
            var _this3 = this;

            var _props2 = this.props,
                children = _props2.children,
                text = _props2.text,
                style = _props2.style,
                min = _props2.min,
                max = _props2.max,
                mode = _props2.mode,
                forceWidth = _props2.forceWidth,
                forceSingleModeWidth = _props2.forceSingleModeWidth,
                throttle = _props2.throttle,
                autoResize = _props2.autoResize,
                onReady = _props2.onReady,
                props = _objectWithoutProperties(_props2, ['children', 'text', 'style', 'min', 'max', 'mode', 'forceWidth', 'forceSingleModeWidth', 'throttle', 'autoResize', 'onReady']);

            var _state = this.state,
                fontSize = _state.fontSize,
                ready = _state.ready;

            var finalStyle = _extends({}, style, {
                fontSize: fontSize
            });

            var wrapperStyle = {
                display: ready ? 'block' : 'inline-block'
            };
            if (mode === 'single') wrapperStyle.whiteSpace = 'nowrap';

            return _react2.default.createElement(
                'div',
                _extends({ ref: function ref(c) {
                        return _this3._parent = c;
                    }, style: finalStyle }, props),
                _react2.default.createElement(
                    'div',
                    { ref: function ref(c) {
                            return _this3._child = c;
                        }, style: wrapperStyle },
                    text && typeof children === 'function' ? ready ? children(text) : text : children
                )
            );
        }
    }]);

    return TextFit;
}(_react2.default.Component);

TextFit.propTypes = {
    children: _propTypes2.default.node,
    text: _propTypes2.default.string,
    min: _propTypes2.default.number,
    max: _propTypes2.default.number,
    mode: _propTypes2.default.oneOf(['single', 'multi']),
    forceSingleModeWidth: _propTypes2.default.bool,
    throttle: _propTypes2.default.number,
    onReady: _propTypes2.default.func
};
TextFit.defaultProps = {
    min: 1,
    max: 100,
    mode: 'multi',
    forceSingleModeWidth: true,
    throttle: 50,
    autoResize: true,
    onReady: noop
};
exports.default = TextFit;