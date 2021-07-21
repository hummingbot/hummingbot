"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _react = _interopRequireWildcard(require("react"));

var _propTypes = _interopRequireDefault(require("prop-types"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function _getRequireWildcardCache() { if (typeof WeakMap !== "function") return null; var cache = new WeakMap(); _getRequireWildcardCache = function () { return cache; }; return cache; }

function _interopRequireWildcard(obj) { if (obj && obj.__esModule) { return obj; } if (obj === null || typeof obj !== "object" && typeof obj !== "function") { return { default: obj }; } var cache = _getRequireWildcardCache(); if (cache && cache.has(obj)) { return cache.get(obj); } var newObj = {}; var hasPropertyDescriptor = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var key in obj) { if (Object.prototype.hasOwnProperty.call(obj, key)) { var desc = hasPropertyDescriptor ? Object.getOwnPropertyDescriptor(obj, key) : null; if (desc && (desc.get || desc.set)) { Object.defineProperty(newObj, key, desc); } else { newObj[key] = obj[key]; } } } newObj.default = obj; if (cache) { cache.set(obj, newObj); } return newObj; }

function ownKeys(object, enumerableOnly) { var keys = Object.keys(object); if (Object.getOwnPropertySymbols) { var symbols = Object.getOwnPropertySymbols(object); if (enumerableOnly) symbols = symbols.filter(function (sym) { return Object.getOwnPropertyDescriptor(object, sym).enumerable; }); keys.push.apply(keys, symbols); } return keys; }

function _objectSpread(target) { for (var i = 1; i < arguments.length; i++) { var source = arguments[i] != null ? arguments[i] : {}; if (i % 2) { ownKeys(Object(source), true).forEach(function (key) { _defineProperty(target, key, source[key]); }); } else if (Object.getOwnPropertyDescriptors) { Object.defineProperties(target, Object.getOwnPropertyDescriptors(source)); } else { ownKeys(Object(source)).forEach(function (key) { Object.defineProperty(target, key, Object.getOwnPropertyDescriptor(source, key)); }); } } return target; }

function _objectWithoutProperties(source, excluded) { if (source == null) return {}; var target = _objectWithoutPropertiesLoose(source, excluded); var key, i; if (Object.getOwnPropertySymbols) { var sourceSymbolKeys = Object.getOwnPropertySymbols(source); for (i = 0; i < sourceSymbolKeys.length; i++) { key = sourceSymbolKeys[i]; if (excluded.indexOf(key) >= 0) continue; if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue; target[key] = source[key]; } } return target; }

function _objectWithoutPropertiesLoose(source, excluded) { if (source == null) return {}; var target = {}; var sourceKeys = Object.keys(source); var key, i; for (i = 0; i < sourceKeys.length; i++) { key = sourceKeys[i]; if (excluded.indexOf(key) >= 0) continue; target[key] = source[key]; } return target; }

function _defineProperty(obj, key, value) { if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }

const childrenToArray = children => Array.isArray(children) ? children : [children]; // This component allows developers to render output before main output from all the other components.
// The reason it's called <Static> is it's append-only output. Output from <Static> components
// is written permanently to stdout and is never updated afterwards. If <Static> component
// receives new children, Ink will detect the changes and write them to stdout.
// In order for this mechanism to work perfectly, <Static> children must never update their output
// once they've been appended to <Static>.
//
// A good example of where this component might be useful is interface like Jest's.
// When running tests, Jest keeps writing completed tests to output, while continuously
// rendering test stats at the end of the output.


class Static extends _react.Component {
  constructor(...args) {
    super(...args);

    _defineProperty(this, "state", {
      lastIndex: null
    });
  }

  render() {
    const _this$props = this.props,
          {
      children
    } = _this$props,
          otherProps = _objectWithoutProperties(_this$props, ["children"]);

    const {
      lastIndex
    } = this.state;
    let newChildren = children;

    if (typeof lastIndex === 'number') {
      newChildren = childrenToArray(children).slice(lastIndex);
    }

    return _react.default.createElement("div", {
      unstable__static: true,
      style: _objectSpread({
        position: 'absolute',
        flexDirection: 'column'
      }, otherProps)
    }, newChildren);
  }

  componentDidMount() {
    this.saveLastIndex(this.props.children);
  }

  componentDidUpdate(prevProps, prevState) {
    if (prevState.lastIndex === this.state.lastIndex) {
      this.saveLastIndex(this.props.children);
    }
  }

  saveLastIndex(children) {
    const nextIndex = childrenToArray(children).length;

    if (this.state.lastIndex !== nextIndex) {
      this.setState({
        lastIndex: nextIndex
      });
    }
  }

}

exports.default = Static;

_defineProperty(Static, "propTypes", {
  children: _propTypes.default.node
});