(function (global, factory) {
  typeof exports === 'object' && typeof module !== 'undefined' ? module.exports = factory(require('react')) :
  typeof define === 'function' && define.amd ? define(['react'], factory) :
  (global.withSideEffect = factory(global.React));
}(this, (function (React) { 'use strict';

  var React__default = 'default' in React ? React['default'] : React;

  function _inheritsLoose(subClass, superClass) {
    subClass.prototype = Object.create(superClass.prototype);
    subClass.prototype.constructor = subClass;
    subClass.__proto__ = superClass;
  }

  function _defineProperty(obj, key, value) {
    if (key in obj) {
      Object.defineProperty(obj, key, {
        value: value,
        enumerable: true,
        configurable: true,
        writable: true
      });
    } else {
      obj[key] = value;
    }

    return obj;
  }

  function withSideEffect(reducePropsToState, handleStateChangeOnClient) {
    if (process.env.NODE_ENV !== "production") {
      if (typeof reducePropsToState !== 'function') {
        throw new Error('Expected reducePropsToState to be a function.');
      }

      if (typeof handleStateChangeOnClient !== 'function') {
        throw new Error('Expected handleStateChangeOnClient to be a function.');
      }
    }

    function getDisplayName(WrappedComponent) {
      return WrappedComponent.displayName || WrappedComponent.name || 'Component';
    }

    return function wrap(WrappedComponent) {
      if (process.env.NODE_ENV !== "production") {
        if (typeof WrappedComponent !== 'function') {
          throw new Error('Expected WrappedComponent to be a React component.');
        }
      }

      var mountedInstances = [];
      var state;

      function emitChange() {
        state = reducePropsToState(mountedInstances.map(function (instance) {
          return instance.props;
        }));
        handleStateChangeOnClient(state);
      }

      var SideEffect =
      /*#__PURE__*/
      function (_PureComponent) {
        _inheritsLoose(SideEffect, _PureComponent);

        function SideEffect() {
          return _PureComponent.apply(this, arguments) || this;
        }

        // Try to use displayName of wrapped component
        SideEffect.peek = function peek() {
          return state;
        };

        var _proto = SideEffect.prototype;

        _proto.componentDidMount = function componentDidMount() {
          mountedInstances.push(this);
          emitChange();
        };

        _proto.componentDidUpdate = function componentDidUpdate() {
          emitChange();
        };

        _proto.componentWillUnmount = function componentWillUnmount() {
          var index = mountedInstances.indexOf(this);
          mountedInstances.splice(index, 1);
          emitChange();
        };

        _proto.render = function render() {
          return React__default.createElement(WrappedComponent, this.props);
        };

        return SideEffect;
      }(React.PureComponent);

      _defineProperty(SideEffect, "displayName", "SideEffect(" + getDisplayName(WrappedComponent) + ")");

      return SideEffect;
    };
  }

  return withSideEffect;

})));
