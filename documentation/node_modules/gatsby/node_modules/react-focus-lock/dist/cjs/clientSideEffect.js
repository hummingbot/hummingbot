"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard");

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;

var React = _interopRequireWildcard(require("react"));

/* eslint-disable */
// NOT USED
function withSideEffect(reducePropsToState, handleStateChangeOnClient) {
  if (process.env.NODE_ENV !== 'production') {
    if (typeof reducePropsToState !== 'function') {
      throw new Error('Expected reducePropsToState to be a function.');
    }

    if (typeof handleStateChangeOnClient !== 'function') {
      throw new Error('Expected handleStateChangeOnClient to be a function.');
    }
  }

  return function wrap(WrappedComponent) {
    if (process.env.NODE_ENV !== 'production') {
      if (typeof WrappedComponent !== 'function') {
        throw new Error('Expected WrappedComponent to be a React component.');
      }
    }

    var mountedInstances = [];

    function emitChange() {
      console.log('emitting');
      var state = reducePropsToState(mountedInstances.map(function (instance) {
        return instance.current;
      }));
      handleStateChangeOnClient(state);
    }

    var SideEffect = function SideEffect(props) {
      var lastProps = React.useRef(props);
      React.useEffect(function () {
        lastProps.current = props;
      }); // handle mounted instances

      React.useEffect(function () {
        console.log('ins added');
        mountedInstances.push(lastProps);
        return function () {
          console.log('ins removed');
          var index = mountedInstances.indexOf(lastProps);
          mountedInstances.splice(index, 1);
        };
      }, []); // notify updates
      // React.useEffect(emitChange, [props.disabled]);

      return /*#__PURE__*/React.createElement(WrappedComponent, props);
    };

    return SideEffect;
  };
}

var _default = withSideEffect;
exports["default"] = _default;