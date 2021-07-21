(function (global, factory) {
  typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports, require('react')) :
  typeof define === 'function' && define.amd ? define(['exports', 'react'], factory) :
  (factory((global.Recompose = {}),global.React));
}(this, (function (exports,React) { 'use strict';

  var React__default = 'default' in React ? React['default'] : React;

  var setStatic = function setStatic(key, value) {
    return function (BaseComponent) {
      /* eslint-disable no-param-reassign */
      BaseComponent[key] = value;
      /* eslint-enable no-param-reassign */

      return BaseComponent;
    };
  };

  var setDisplayName = function setDisplayName(displayName) {
    return setStatic('displayName', displayName);
  };

  var getDisplayName = function getDisplayName(Component) {
    if (typeof Component === 'string') {
      return Component;
    }

    if (!Component) {
      return undefined;
    }

    return Component.displayName || Component.name || 'Component';
  };

  var wrapDisplayName = function wrapDisplayName(BaseComponent, hocName) {
    return hocName + "(" + getDisplayName(BaseComponent) + ")";
  };

  var mapProps = function mapProps(propsMapper) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);

      var MapProps = function MapProps(props) {
        return factory(propsMapper(props));
      };

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'mapProps'))(MapProps);
      }

      return MapProps;
    };
  };

  function _extends() {
    _extends = Object.assign || function (target) {
      for (var i = 1; i < arguments.length; i++) {
        var source = arguments[i];

        for (var key in source) {
          if (Object.prototype.hasOwnProperty.call(source, key)) {
            target[key] = source[key];
          }
        }
      }

      return target;
    };

    return _extends.apply(this, arguments);
  }

  var withProps = function withProps(input) {
    var hoc = mapProps(function (props) {
      return _extends({}, props, typeof input === 'function' ? input(props) : input);
    });

    {
      return function (BaseComponent) {
        return setDisplayName(wrapDisplayName(BaseComponent, 'withProps'))(hoc(BaseComponent));
      };
    }

    return hoc;
  };

  function _inheritsLoose(subClass, superClass) {
    subClass.prototype = Object.create(superClass.prototype);
    subClass.prototype.constructor = subClass;
    subClass.__proto__ = superClass;
  }

  /**
   * Copyright (c) 2013-present, Facebook, Inc.
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE file in the root directory of this source tree.
   */

  function componentWillMount() {
    // Call this.constructor.gDSFP to support sub-classes.
    var state = this.constructor.getDerivedStateFromProps(this.props, this.state);
    if (state !== null && state !== undefined) {
      this.setState(state);
    }
  }

  function componentWillReceiveProps(nextProps) {
    // Call this.constructor.gDSFP to support sub-classes.
    var state = this.constructor.getDerivedStateFromProps(nextProps, this.state);
    if (state !== null && state !== undefined) {
      this.setState(state);
    }
  }

  function componentWillUpdate(nextProps, nextState) {
    try {
      var prevProps = this.props;
      var prevState = this.state;
      this.props = nextProps;
      this.state = nextState;
      this.__reactInternalSnapshotFlag = true;
      this.__reactInternalSnapshot = this.getSnapshotBeforeUpdate(
        prevProps,
        prevState
      );
    } finally {
      this.props = prevProps;
      this.state = prevState;
    }
  }

  // React may warn about cWM/cWRP/cWU methods being deprecated.
  // Add a flag to suppress these warnings for this special case.
  componentWillMount.__suppressDeprecationWarning = true;
  componentWillReceiveProps.__suppressDeprecationWarning = true;
  componentWillUpdate.__suppressDeprecationWarning = true;

  function polyfill(Component) {
    var prototype = Component.prototype;

    if (!prototype || !prototype.isReactComponent) {
      throw new Error('Can only polyfill class components');
    }

    if (
      typeof Component.getDerivedStateFromProps !== 'function' &&
      typeof prototype.getSnapshotBeforeUpdate !== 'function'
    ) {
      return Component;
    }

    // If new component APIs are defined, "unsafe" lifecycles won't be called.
    // Error if any of these lifecycles are present,
    // Because they would work differently between older and newer (16.3+) versions of React.
    var foundWillMountName = null;
    var foundWillReceivePropsName = null;
    var foundWillUpdateName = null;
    if (typeof prototype.componentWillMount === 'function') {
      foundWillMountName = 'componentWillMount';
    } else if (typeof prototype.UNSAFE_componentWillMount === 'function') {
      foundWillMountName = 'UNSAFE_componentWillMount';
    }
    if (typeof prototype.componentWillReceiveProps === 'function') {
      foundWillReceivePropsName = 'componentWillReceiveProps';
    } else if (typeof prototype.UNSAFE_componentWillReceiveProps === 'function') {
      foundWillReceivePropsName = 'UNSAFE_componentWillReceiveProps';
    }
    if (typeof prototype.componentWillUpdate === 'function') {
      foundWillUpdateName = 'componentWillUpdate';
    } else if (typeof prototype.UNSAFE_componentWillUpdate === 'function') {
      foundWillUpdateName = 'UNSAFE_componentWillUpdate';
    }
    if (
      foundWillMountName !== null ||
      foundWillReceivePropsName !== null ||
      foundWillUpdateName !== null
    ) {
      var componentName = Component.displayName || Component.name;
      var newApiName =
        typeof Component.getDerivedStateFromProps === 'function'
          ? 'getDerivedStateFromProps()'
          : 'getSnapshotBeforeUpdate()';

      throw Error(
        'Unsafe legacy lifecycles will not be called for components using new component APIs.\n\n' +
          componentName +
          ' uses ' +
          newApiName +
          ' but also contains the following legacy lifecycles:' +
          (foundWillMountName !== null ? '\n  ' + foundWillMountName : '') +
          (foundWillReceivePropsName !== null
            ? '\n  ' + foundWillReceivePropsName
            : '') +
          (foundWillUpdateName !== null ? '\n  ' + foundWillUpdateName : '') +
          '\n\nThe above lifecycles should be removed. Learn more about this warning here:\n' +
          'https://fb.me/react-async-component-lifecycle-hooks'
      );
    }

    // React <= 16.2 does not support static getDerivedStateFromProps.
    // As a workaround, use cWM and cWRP to invoke the new static lifecycle.
    // Newer versions of React will ignore these lifecycles if gDSFP exists.
    if (typeof Component.getDerivedStateFromProps === 'function') {
      prototype.componentWillMount = componentWillMount;
      prototype.componentWillReceiveProps = componentWillReceiveProps;
    }

    // React <= 16.2 does not support getSnapshotBeforeUpdate.
    // As a workaround, use cWU to invoke the new lifecycle.
    // Newer versions of React will ignore that lifecycle if gSBU exists.
    if (typeof prototype.getSnapshotBeforeUpdate === 'function') {
      if (typeof prototype.componentDidUpdate !== 'function') {
        throw new Error(
          'Cannot polyfill getSnapshotBeforeUpdate() for components that do not define componentDidUpdate() on the prototype'
        );
      }

      prototype.componentWillUpdate = componentWillUpdate;

      var componentDidUpdate = prototype.componentDidUpdate;

      prototype.componentDidUpdate = function componentDidUpdatePolyfill(
        prevProps,
        prevState,
        maybeSnapshot
      ) {
        // 16.3+ will not execute our will-update method;
        // It will pass a snapshot value to did-update though.
        // Older versions will require our polyfilled will-update value.
        // We need to handle both cases, but can't just check for the presence of "maybeSnapshot",
        // Because for <= 15.x versions this might be a "prevContext" object.
        // We also can't just check "__reactInternalSnapshot",
        // Because get-snapshot might return a falsy value.
        // So check for the explicit __reactInternalSnapshotFlag flag to determine behavior.
        var snapshot = this.__reactInternalSnapshotFlag
          ? this.__reactInternalSnapshot
          : maybeSnapshot;

        componentDidUpdate.call(this, prevProps, prevState, snapshot);
      };
    }

    return Component;
  }

  var pick = function pick(obj, keys) {
    var result = {};

    for (var i = 0; i < keys.length; i++) {
      var key = keys[i];

      if (obj.hasOwnProperty(key)) {
        result[key] = obj[key];
      }
    }

    return result;
  };

  /**
   * Copyright (c) 2013-present, Facebook, Inc.
   * All rights reserved.
   *
   * This source code is licensed under the BSD-style license found in the
   * LICENSE file in the root directory of this source tree. An additional grant
   * of patent rights can be found in the PATENTS file in the same directory.
   *
   * @typechecks
   * 
   */

  var hasOwnProperty = Object.prototype.hasOwnProperty;

  /**
   * inlined Object.is polyfill to avoid requiring consumers ship their own
   * https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/is
   */
  function is(x, y) {
    // SameValue algorithm
    if (x === y) {
      // Steps 1-5, 7-10
      // Steps 6.b-6.e: +0 != -0
      // Added the nonzero y check to make Flow happy, but it is redundant
      return x !== 0 || y !== 0 || 1 / x === 1 / y;
    } else {
      // Step 6.a: NaN == NaN
      return x !== x && y !== y;
    }
  }

  /**
   * Performs equality by iterating through keys on an object and returning false
   * when any key has values which are not strictly equal between the arguments.
   * Returns true when the values of all keys are strictly equal.
   */
  function shallowEqual(objA, objB) {
    if (is(objA, objB)) {
      return true;
    }

    if (typeof objA !== 'object' || objA === null || typeof objB !== 'object' || objB === null) {
      return false;
    }

    var keysA = Object.keys(objA);
    var keysB = Object.keys(objB);

    if (keysA.length !== keysB.length) {
      return false;
    }

    // Test for A's keys different from B.
    for (var i = 0; i < keysA.length; i++) {
      if (!hasOwnProperty.call(objB, keysA[i]) || !is(objA[keysA[i]], objB[keysA[i]])) {
        return false;
      }
    }

    return true;
  }

  var shallowEqual_1 = shallowEqual;

  var withPropsOnChange = function withPropsOnChange(shouldMapOrKeys, propsMapper) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);
      var shouldMap = typeof shouldMapOrKeys === 'function' ? shouldMapOrKeys : function (props, nextProps) {
        return !shallowEqual_1(pick(props, shouldMapOrKeys), pick(nextProps, shouldMapOrKeys));
      };

      var WithPropsOnChange =
      /*#__PURE__*/
      function (_Component) {
        _inheritsLoose(WithPropsOnChange, _Component);

        function WithPropsOnChange() {
          var _this;

          for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
            args[_key] = arguments[_key];
          }

          _this = _Component.call.apply(_Component, [this].concat(args)) || this;
          _this.state = {
            computedProps: propsMapper(_this.props),
            prevProps: _this.props
          };
          return _this;
        }

        WithPropsOnChange.getDerivedStateFromProps = function getDerivedStateFromProps(nextProps, prevState) {
          if (shouldMap(prevState.prevProps, nextProps)) {
            return {
              computedProps: propsMapper(nextProps),
              prevProps: nextProps
            };
          }

          return {
            prevProps: nextProps
          };
        };

        var _proto = WithPropsOnChange.prototype;

        _proto.render = function render() {
          return factory(_extends({}, this.props, this.state.computedProps));
        };

        return WithPropsOnChange;
      }(React.Component);

      polyfill(WithPropsOnChange);

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'withPropsOnChange'))(WithPropsOnChange);
      }

      return WithPropsOnChange;
    };
  };

  var mapValues = function mapValues(obj, func) {
    var result = {};
    /* eslint-disable no-restricted-syntax */

    for (var key in obj) {
      if (obj.hasOwnProperty(key)) {
        result[key] = func(obj[key], key);
      }
    }
    /* eslint-enable no-restricted-syntax */


    return result;
  };

  var withHandlers = function withHandlers(handlers) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);

      var WithHandlers =
      /*#__PURE__*/
      function (_Component) {
        _inheritsLoose(WithHandlers, _Component);

        function WithHandlers() {
          var _this;

          for (var _len = arguments.length, _args = new Array(_len), _key = 0; _key < _len; _key++) {
            _args[_key] = arguments[_key];
          }

          _this = _Component.call.apply(_Component, [this].concat(_args)) || this;
          _this.handlers = mapValues(typeof handlers === 'function' ? handlers(_this.props) : handlers, function (createHandler) {
            return function () {
              var handler = createHandler(_this.props);

              if (typeof handler !== 'function') {
                console.error( // eslint-disable-line no-console
                'withHandlers(): Expected a map of higher-order functions. ' + 'Refer to the docs for more info.');
              }

              return handler.apply(void 0, arguments);
            };
          });
          return _this;
        }

        var _proto = WithHandlers.prototype;

        _proto.render = function render() {
          return factory(_extends({}, this.props, this.handlers));
        };

        return WithHandlers;
      }(React.Component);

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'withHandlers'))(WithHandlers);
      }

      return WithHandlers;
    };
  };

  var defaultProps = function defaultProps(props) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);

      var DefaultProps = function DefaultProps(ownerProps) {
        return factory(ownerProps);
      };

      DefaultProps.defaultProps = props;

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'defaultProps'))(DefaultProps);
      }

      return DefaultProps;
    };
  };

  var omit = function omit(obj, keys) {
    var rest = _extends({}, obj);

    for (var i = 0; i < keys.length; i++) {
      var key = keys[i];

      if (rest.hasOwnProperty(key)) {
        delete rest[key];
      }
    }

    return rest;
  };

  var renameProp = function renameProp(oldName, newName) {
    var hoc = mapProps(function (props) {
      var _extends2;

      return _extends({}, omit(props, [oldName]), (_extends2 = {}, _extends2[newName] = props[oldName], _extends2));
    });

    {
      return function (BaseComponent) {
        return setDisplayName(wrapDisplayName(BaseComponent, 'renameProp'))(hoc(BaseComponent));
      };
    }

    return hoc;
  };

  var keys = Object.keys;

  var mapKeys = function mapKeys(obj, func) {
    return keys(obj).reduce(function (result, key) {
      var val = obj[key];
      /* eslint-disable no-param-reassign */

      result[func(val, key)] = val;
      /* eslint-enable no-param-reassign */

      return result;
    }, {});
  };

  var renameProps = function renameProps(nameMap) {
    var hoc = mapProps(function (props) {
      return _extends({}, omit(props, keys(nameMap)), mapKeys(pick(props, keys(nameMap)), function (_, oldName) {
        return nameMap[oldName];
      }));
    });

    {
      return function (BaseComponent) {
        return setDisplayName(wrapDisplayName(BaseComponent, 'renameProps'))(hoc(BaseComponent));
      };
    }

    return hoc;
  };

  var flattenProp = function flattenProp(propName) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);

      var FlattenProp = function FlattenProp(props) {
        return factory(_extends({}, props, props[propName]));
      };

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'flattenProp'))(FlattenProp);
      }

      return FlattenProp;
    };
  };

  var withState = function withState(stateName, stateUpdaterName, initialState) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);

      var WithState =
      /*#__PURE__*/
      function (_Component) {
        _inheritsLoose(WithState, _Component);

        function WithState() {
          var _this;

          for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
            args[_key] = arguments[_key];
          }

          _this = _Component.call.apply(_Component, [this].concat(args)) || this;
          _this.state = {
            stateValue: typeof initialState === 'function' ? initialState(_this.props) : initialState
          };

          _this.updateStateValue = function (updateFn, callback) {
            return _this.setState(function (_ref) {
              var stateValue = _ref.stateValue;
              return {
                stateValue: typeof updateFn === 'function' ? updateFn(stateValue) : updateFn
              };
            }, callback);
          };

          return _this;
        }

        var _proto = WithState.prototype;

        _proto.render = function render() {
          var _extends2;

          return factory(_extends({}, this.props, (_extends2 = {}, _extends2[stateName] = this.state.stateValue, _extends2[stateUpdaterName] = this.updateStateValue, _extends2)));
        };

        return WithState;
      }(React.Component);

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'withState'))(WithState);
      }

      return WithState;
    };
  };

  var withStateHandlers = function withStateHandlers(initialState, stateUpdaters) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);

      var WithStateHandlers =
      /*#__PURE__*/
      function (_Component) {
        _inheritsLoose(WithStateHandlers, _Component);

        function WithStateHandlers() {
          var _this;

          for (var _len = arguments.length, _args = new Array(_len), _key = 0; _key < _len; _key++) {
            _args[_key] = arguments[_key];
          }

          _this = _Component.call.apply(_Component, [this].concat(_args)) || this;
          _this.state = typeof initialState === 'function' ? initialState(_this.props) : initialState;
          _this.stateUpdaters = mapValues(stateUpdaters, function (handler) {
            return function (mayBeEvent) {
              for (var _len2 = arguments.length, args = new Array(_len2 > 1 ? _len2 - 1 : 0), _key2 = 1; _key2 < _len2; _key2++) {
                args[_key2 - 1] = arguments[_key2];
              }

              // Having that functional form of setState can be called async
              // we need to persist SyntheticEvent
              if (mayBeEvent && typeof mayBeEvent.persist === 'function') {
                mayBeEvent.persist();
              }

              _this.setState(function (state, props) {
                return handler(state, props).apply(void 0, [mayBeEvent].concat(args));
              });
            };
          });
          return _this;
        }

        var _proto = WithStateHandlers.prototype;

        _proto.render = function render() {
          return factory(_extends({}, this.props, this.state, this.stateUpdaters));
        };

        return WithStateHandlers;
      }(React.Component);

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'withStateHandlers'))(WithStateHandlers);
      }

      return WithStateHandlers;
    };
  };

  var noop = function noop() {};

  var withReducer = function withReducer(stateName, dispatchName, reducer, initialState) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);

      var WithReducer =
      /*#__PURE__*/
      function (_Component) {
        _inheritsLoose(WithReducer, _Component);

        function WithReducer() {
          var _this;

          for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
            args[_key] = arguments[_key];
          }

          _this = _Component.call.apply(_Component, [this].concat(args)) || this;
          _this.state = {
            stateValue: _this.initializeStateValue()
          };

          _this.dispatch = function (action, callback) {
            if (callback === void 0) {
              callback = noop;
            }

            return _this.setState(function (_ref) {
              var stateValue = _ref.stateValue;
              return {
                stateValue: reducer(stateValue, action)
              };
            }, function () {
              return callback(_this.state.stateValue);
            });
          };

          return _this;
        }

        var _proto = WithReducer.prototype;

        _proto.initializeStateValue = function initializeStateValue() {
          if (initialState !== undefined) {
            return typeof initialState === 'function' ? initialState(this.props) : initialState;
          }

          return reducer(undefined, {
            type: '@@recompose/INIT'
          });
        };

        _proto.render = function render() {
          var _extends2;

          return factory(_extends({}, this.props, (_extends2 = {}, _extends2[stateName] = this.state.stateValue, _extends2[dispatchName] = this.dispatch, _extends2)));
        };

        return WithReducer;
      }(React.Component);

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'withReducer'))(WithReducer);
      }

      return WithReducer;
    };
  };

  var identity = function identity(Component) {
    return Component;
  };

  var branch = function branch(test, left, right) {
    if (right === void 0) {
      right = identity;
    }

    return function (BaseComponent) {
      var leftFactory;
      var rightFactory;

      var Branch = function Branch(props) {
        if (test(props)) {
          leftFactory = leftFactory || React.createFactory(left(BaseComponent));
          return leftFactory(props);
        }

        rightFactory = rightFactory || React.createFactory(right(BaseComponent));
        return rightFactory(props);
      };

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'branch'))(Branch);
      }

      return Branch;
    };
  };

  var renderComponent = function renderComponent(Component) {
    return function (_) {
      var factory = React.createFactory(Component);

      var RenderComponent = function RenderComponent(props) {
        return factory(props);
      };

      {
        RenderComponent.displayName = wrapDisplayName(Component, 'renderComponent');
      }

      return RenderComponent;
    };
  };

  var Nothing =
  /*#__PURE__*/
  function (_Component) {
    _inheritsLoose(Nothing, _Component);

    function Nothing() {
      return _Component.apply(this, arguments) || this;
    }

    var _proto = Nothing.prototype;

    _proto.render = function render() {
      return null;
    };

    return Nothing;
  }(React.Component);

  var renderNothing = function renderNothing(_) {
    return Nothing;
  };

  var shouldUpdate = function shouldUpdate(test) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);

      var ShouldUpdate =
      /*#__PURE__*/
      function (_Component) {
        _inheritsLoose(ShouldUpdate, _Component);

        function ShouldUpdate() {
          return _Component.apply(this, arguments) || this;
        }

        var _proto = ShouldUpdate.prototype;

        _proto.shouldComponentUpdate = function shouldComponentUpdate(nextProps) {
          return test(this.props, nextProps);
        };

        _proto.render = function render() {
          return factory(this.props);
        };

        return ShouldUpdate;
      }(React.Component);

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'shouldUpdate'))(ShouldUpdate);
      }

      return ShouldUpdate;
    };
  };

  var pure = function pure(BaseComponent) {
    var hoc = shouldUpdate(function (props, nextProps) {
      return !shallowEqual_1(props, nextProps);
    });

    {
      return setDisplayName(wrapDisplayName(BaseComponent, 'pure'))(hoc(BaseComponent));
    }

    return hoc(BaseComponent);
  };

  var onlyUpdateForKeys = function onlyUpdateForKeys(propKeys) {
    var hoc = shouldUpdate(function (props, nextProps) {
      return !shallowEqual_1(pick(nextProps, propKeys), pick(props, propKeys));
    });

    {
      return function (BaseComponent) {
        return setDisplayName(wrapDisplayName(BaseComponent, 'onlyUpdateForKeys'))(hoc(BaseComponent));
      };
    }

    return hoc;
  };

  var onlyUpdateForPropTypes = function onlyUpdateForPropTypes(BaseComponent) {
    var propTypes = BaseComponent.propTypes;

    {
      if (!propTypes) {
        /* eslint-disable */
        console.error('A component without any `propTypes` was passed to ' + '`onlyUpdateForPropTypes()`. Check the implementation of the ' + ("component with display name \"" + getDisplayName(BaseComponent) + "\"."));
        /* eslint-enable */
      }
    }

    var propKeys = Object.keys(propTypes || {});
    var OnlyUpdateForPropTypes = onlyUpdateForKeys(propKeys)(BaseComponent);

    {
      return setDisplayName(wrapDisplayName(BaseComponent, 'onlyUpdateForPropTypes'))(OnlyUpdateForPropTypes);
    }

    return OnlyUpdateForPropTypes;
  };

  var withContext = function withContext(childContextTypes, getChildContext) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);

      var WithContext =
      /*#__PURE__*/
      function (_Component) {
        _inheritsLoose(WithContext, _Component);

        function WithContext() {
          var _this;

          for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
            args[_key] = arguments[_key];
          }

          _this = _Component.call.apply(_Component, [this].concat(args)) || this;

          _this.getChildContext = function () {
            return getChildContext(_this.props);
          };

          return _this;
        }

        var _proto = WithContext.prototype;

        _proto.render = function render() {
          return factory(this.props);
        };

        return WithContext;
      }(React.Component);

      WithContext.childContextTypes = childContextTypes;

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'withContext'))(WithContext);
      }

      return WithContext;
    };
  };

  var getContext = function getContext(contextTypes) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);

      var GetContext = function GetContext(ownerProps, context) {
        return factory(_extends({}, ownerProps, context));
      };

      GetContext.contextTypes = contextTypes;

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'getContext'))(GetContext);
      }

      return GetContext;
    };
  };

  var lifecycle = function lifecycle(spec) {
    return function (BaseComponent) {
      var factory = React.createFactory(BaseComponent);

      if (spec.hasOwnProperty('render')) {
        console.error('lifecycle() does not support the render method; its behavior is to ' + 'pass all props and state to the base component.');
      }

      var Lifecycle =
      /*#__PURE__*/
      function (_Component) {
        _inheritsLoose(Lifecycle, _Component);

        function Lifecycle() {
          return _Component.apply(this, arguments) || this;
        }

        var _proto = Lifecycle.prototype;

        _proto.render = function render() {
          return factory(_extends({}, this.props, this.state));
        };

        return Lifecycle;
      }(React.Component);

      Object.keys(spec).forEach(function (hook) {
        return Lifecycle.prototype[hook] = spec[hook];
      });

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'lifecycle'))(Lifecycle);
      }

      return Lifecycle;
    };
  };

  var isClassComponent = function isClassComponent(Component) {
    return Boolean(Component && Component.prototype && typeof Component.prototype.render === 'function');
  };

  var toClass = function toClass(baseComponent) {
    var _class, _temp;

    return isClassComponent(baseComponent) ? baseComponent : (_temp = _class =
    /*#__PURE__*/
    function (_Component) {
      _inheritsLoose(ToClass, _Component);

      function ToClass() {
        return _Component.apply(this, arguments) || this;
      }

      var _proto = ToClass.prototype;

      _proto.render = function render() {
        if (typeof baseComponent === 'string') {
          return React__default.createElement(baseComponent, this.props);
        }

        return baseComponent(this.props, this.context);
      };

      return ToClass;
    }(React.Component), _class.displayName = getDisplayName(baseComponent), _class.propTypes = baseComponent.propTypes, _class.contextTypes = baseComponent.contextTypes, _class.defaultProps = baseComponent.defaultProps, _temp);
  };

  function toRenderProps(hoc) {
    var RenderPropsComponent = function RenderPropsComponent(props) {
      return props.children(props);
    };

    return hoc(RenderPropsComponent);
  }

  var fromRenderProps = function fromRenderProps(RenderPropsComponent, propsMapper, renderPropName) {
    if (renderPropName === void 0) {
      renderPropName = 'children';
    }

    return function (BaseComponent) {
      var baseFactory = React__default.createFactory(BaseComponent);
      var renderPropsFactory = React__default.createFactory(RenderPropsComponent);

      var FromRenderProps = function FromRenderProps(ownerProps) {
        var _renderPropsFactory;

        return renderPropsFactory((_renderPropsFactory = {}, _renderPropsFactory[renderPropName] = function () {
          return baseFactory(_extends({}, ownerProps, propsMapper.apply(void 0, arguments)));
        }, _renderPropsFactory));
      };

      {
        return setDisplayName(wrapDisplayName(BaseComponent, 'fromRenderProps'))(FromRenderProps);
      }

      return FromRenderProps;
    };
  };

  var setPropTypes = function setPropTypes(propTypes) {
    return setStatic('propTypes', propTypes);
  };

  var compose = function compose() {
    for (var _len = arguments.length, funcs = new Array(_len), _key = 0; _key < _len; _key++) {
      funcs[_key] = arguments[_key];
    }

    return funcs.reduce(function (a, b) {
      return function () {
        return a(b.apply(void 0, arguments));
      };
    }, function (arg) {
      return arg;
    });
  };

  var createSink = function createSink(callback) {
    var Sink =
    /*#__PURE__*/
    function (_Component) {
      _inheritsLoose(Sink, _Component);

      function Sink() {
        var _this;

        for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
          args[_key] = arguments[_key];
        }

        _this = _Component.call.apply(_Component, [this].concat(args)) || this;
        _this.state = {};
        return _this;
      }

      Sink.getDerivedStateFromProps = function getDerivedStateFromProps(nextProps) {
        callback(nextProps);
        return null;
      };

      var _proto = Sink.prototype;

      _proto.render = function render() {
        return null;
      };

      return Sink;
    }(React.Component);

    polyfill(Sink);
    return Sink;
  };

  var componentFromProp = function componentFromProp(propName) {
    var Component = function Component(props) {
      return React.createElement(props[propName], omit(props, [propName]));
    };

    Component.displayName = "componentFromProp(" + propName + ")";
    return Component;
  };

  function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    var sourceKeys = Object.keys(source);
    var key, i;

    for (i = 0; i < sourceKeys.length; i++) {
      key = sourceKeys[i];
      if (excluded.indexOf(key) >= 0) continue;
      target[key] = source[key];
    }

    return target;
  }

  var nest = function nest() {
    for (var _len = arguments.length, Components = new Array(_len), _key = 0; _key < _len; _key++) {
      Components[_key] = arguments[_key];
    }

    var factories = Components.map(React.createFactory);

    var Nest = function Nest(_ref) {
      var children = _ref.children,
          props = _objectWithoutPropertiesLoose(_ref, ["children"]);

      return factories.reduceRight(function (child, factory) {
        return factory(props, child);
      }, children);
    };

    {
      var displayNames = Components.map(getDisplayName);
      Nest.displayName = "nest(" + displayNames.join(', ') + ")";
    }

    return Nest;
  };

  /**
   * Copyright 2015, Yahoo! Inc.
   * Copyrights licensed under the New BSD License. See the accompanying LICENSE file for terms.
   */

  var REACT_STATICS = {
      childContextTypes: true,
      contextTypes: true,
      defaultProps: true,
      displayName: true,
      getDefaultProps: true,
      mixins: true,
      propTypes: true,
      type: true
  };

  var KNOWN_STATICS = {
    name: true,
    length: true,
    prototype: true,
    caller: true,
    callee: true,
    arguments: true,
    arity: true
  };

  var defineProperty = Object.defineProperty;
  var getOwnPropertyNames = Object.getOwnPropertyNames;
  var getOwnPropertySymbols = Object.getOwnPropertySymbols;
  var getOwnPropertyDescriptor = Object.getOwnPropertyDescriptor;
  var getPrototypeOf = Object.getPrototypeOf;
  var objectPrototype = getPrototypeOf && getPrototypeOf(Object);

  var hoistNonReactStatics = function hoistNonReactStatics(targetComponent, sourceComponent, blacklist) {
      if (typeof sourceComponent !== 'string') { // don't hoist over string (html) components

          if (objectPrototype) {
              var inheritedComponent = getPrototypeOf(sourceComponent);
              if (inheritedComponent && inheritedComponent !== objectPrototype) {
                  hoistNonReactStatics(targetComponent, inheritedComponent, blacklist);
              }
          }

          var keys = getOwnPropertyNames(sourceComponent);

          if (getOwnPropertySymbols) {
              keys = keys.concat(getOwnPropertySymbols(sourceComponent));
          }

          for (var i = 0; i < keys.length; ++i) {
              var key = keys[i];
              if (!REACT_STATICS[key] && !KNOWN_STATICS[key] && (!blacklist || !blacklist[key])) {
                  var descriptor = getOwnPropertyDescriptor(sourceComponent, key);
                  try { // Avoid failures from read-only properties
                      defineProperty(targetComponent, key, descriptor);
                  } catch (e) {}
              }
          }

          return targetComponent;
      }

      return targetComponent;
  };

  var hoistStatics = function hoistStatics(higherOrderComponent, blacklist) {
    return function (BaseComponent) {
      var NewComponent = higherOrderComponent(BaseComponent);
      hoistNonReactStatics(NewComponent, BaseComponent, blacklist);
      return NewComponent;
    };
  };

  var commonjsGlobal = typeof window !== 'undefined' ? window : typeof global !== 'undefined' ? global : typeof self !== 'undefined' ? self : {};

  function unwrapExports (x) {
  	return x && x.__esModule && Object.prototype.hasOwnProperty.call(x, 'default') ? x['default'] : x;
  }

  function createCommonjsModule(fn, module) {
  	return module = { exports: {} }, fn(module, module.exports), module.exports;
  }

  var lib = createCommonjsModule(function (module, exports) {

  Object.defineProperty(exports, "__esModule", {
    value: true
  });
  var createChangeEmitter = exports.createChangeEmitter = function createChangeEmitter() {
    var currentListeners = [];
    var nextListeners = currentListeners;

    function ensureCanMutateNextListeners() {
      if (nextListeners === currentListeners) {
        nextListeners = currentListeners.slice();
      }
    }

    function listen(listener) {
      if (typeof listener !== 'function') {
        throw new Error('Expected listener to be a function.');
      }

      var isSubscribed = true;

      ensureCanMutateNextListeners();
      nextListeners.push(listener);

      return function () {
        if (!isSubscribed) {
          return;
        }

        isSubscribed = false;

        ensureCanMutateNextListeners();
        var index = nextListeners.indexOf(listener);
        nextListeners.splice(index, 1);
      };
    }

    function emit() {
      currentListeners = nextListeners;
      var listeners = currentListeners;
      for (var i = 0; i < listeners.length; i++) {
        listeners[i].apply(listeners, arguments);
      }
    }

    return {
      listen: listen,
      emit: emit
    };
  };
  });

  unwrapExports(lib);
  var lib_1 = lib.createChangeEmitter;

  var ponyfill = createCommonjsModule(function (module, exports) {

  Object.defineProperty(exports, "__esModule", {
  	value: true
  });
  exports['default'] = symbolObservablePonyfill;
  function symbolObservablePonyfill(root) {
  	var result;
  	var _Symbol = root.Symbol;

  	if (typeof _Symbol === 'function') {
  		if (_Symbol.observable) {
  			result = _Symbol.observable;
  		} else {
  			result = _Symbol('observable');
  			_Symbol.observable = result;
  		}
  	} else {
  		result = '@@observable';
  	}

  	return result;
  }});

  unwrapExports(ponyfill);

  var lib$1 = createCommonjsModule(function (module, exports) {

  Object.defineProperty(exports, "__esModule", {
    value: true
  });



  var _ponyfill2 = _interopRequireDefault(ponyfill);

  function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { 'default': obj }; }

  var root; /* global window */


  if (typeof self !== 'undefined') {
    root = self;
  } else if (typeof window !== 'undefined') {
    root = window;
  } else if (typeof commonjsGlobal !== 'undefined') {
    root = commonjsGlobal;
  } else {
    root = module;
  }

  var result = (0, _ponyfill2['default'])(root);
  exports['default'] = result;
  });

  unwrapExports(lib$1);

  var symbolObservable = lib$1;

  var _config = {
    fromESObservable: null,
    toESObservable: null
  };

  var configureObservable = function configureObservable(c) {
    _config = c;
  };

  var config = {
    fromESObservable: function fromESObservable(observable) {
      return typeof _config.fromESObservable === 'function' ? _config.fromESObservable(observable) : observable;
    },
    toESObservable: function toESObservable(stream) {
      return typeof _config.toESObservable === 'function' ? _config.toESObservable(stream) : stream;
    }
  };

  var componentFromStreamWithConfig = function componentFromStreamWithConfig(config$$1) {
    return function (propsToVdom) {
      return (
        /*#__PURE__*/
        function (_Component) {
          _inheritsLoose(ComponentFromStream, _Component);

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
            _this.propsEmitter = lib_1();
            _this.props$ = config$$1.fromESObservable((_config$fromESObserva = {
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
            }, _config$fromESObserva[symbolObservable] = function () {
              return this;
            }, _config$fromESObserva));
            _this.vdom$ = config$$1.toESObservable(propsToVdom(_this.props$));
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
        }(React.Component)
      );
    };
  };

  var componentFromStream = function componentFromStream(propsToVdom) {
    return componentFromStreamWithConfig(config)(propsToVdom);
  };

  var identity$1 = function identity(t) {
    return t;
  };

  var mapPropsStreamWithConfig = function mapPropsStreamWithConfig(config$$1) {
    var componentFromStream$$1 = componentFromStreamWithConfig({
      fromESObservable: identity$1,
      toESObservable: identity$1
    });
    return function (transform) {
      return function (BaseComponent) {
        var factory = React.createFactory(BaseComponent);
        var fromESObservable = config$$1.fromESObservable,
            toESObservable = config$$1.toESObservable;
        return componentFromStream$$1(function (props$) {
          var _ref;

          return _ref = {
            subscribe: function subscribe(observer) {
              var subscription = toESObservable(transform(fromESObservable(props$))).subscribe({
                next: function next(childProps) {
                  return observer.next(factory(childProps));
                }
              });
              return {
                unsubscribe: function unsubscribe() {
                  return subscription.unsubscribe();
                }
              };
            }
          }, _ref[symbolObservable] = function () {
            return this;
          }, _ref;
        });
      };
    };
  };

  var mapPropsStream = function mapPropsStream(transform) {
    var hoc = mapPropsStreamWithConfig(config)(transform);

    {
      return function (BaseComponent) {
        return setDisplayName(wrapDisplayName(BaseComponent, 'mapPropsStream'))(hoc(BaseComponent));
      };
    }

    return hoc;
  };

  var createEventHandlerWithConfig = function createEventHandlerWithConfig(config$$1) {
    return function () {
      var _config$fromESObserva;

      var emitter = lib_1();
      var stream = config$$1.fromESObservable((_config$fromESObserva = {
        subscribe: function subscribe(observer) {
          var unsubscribe = emitter.listen(function (value) {
            return observer.next(value);
          });
          return {
            unsubscribe: unsubscribe
          };
        }
      }, _config$fromESObserva[symbolObservable] = function () {
        return this;
      }, _config$fromESObserva));
      return {
        handler: emitter.emit,
        stream: stream
      };
    };
  };
  var createEventHandler = createEventHandlerWithConfig(config);

  // Higher-order component helpers

  exports.mapProps = mapProps;
  exports.withProps = withProps;
  exports.withPropsOnChange = withPropsOnChange;
  exports.withHandlers = withHandlers;
  exports.defaultProps = defaultProps;
  exports.renameProp = renameProp;
  exports.renameProps = renameProps;
  exports.flattenProp = flattenProp;
  exports.withState = withState;
  exports.withStateHandlers = withStateHandlers;
  exports.withReducer = withReducer;
  exports.branch = branch;
  exports.renderComponent = renderComponent;
  exports.renderNothing = renderNothing;
  exports.shouldUpdate = shouldUpdate;
  exports.pure = pure;
  exports.onlyUpdateForKeys = onlyUpdateForKeys;
  exports.onlyUpdateForPropTypes = onlyUpdateForPropTypes;
  exports.withContext = withContext;
  exports.getContext = getContext;
  exports.lifecycle = lifecycle;
  exports.toClass = toClass;
  exports.toRenderProps = toRenderProps;
  exports.fromRenderProps = fromRenderProps;
  exports.setStatic = setStatic;
  exports.setPropTypes = setPropTypes;
  exports.setDisplayName = setDisplayName;
  exports.compose = compose;
  exports.getDisplayName = getDisplayName;
  exports.wrapDisplayName = wrapDisplayName;
  exports.shallowEqual = shallowEqual_1;
  exports.isClassComponent = isClassComponent;
  exports.createSink = createSink;
  exports.componentFromProp = componentFromProp;
  exports.nest = nest;
  exports.hoistStatics = hoistStatics;
  exports.componentFromStream = componentFromStream;
  exports.componentFromStreamWithConfig = componentFromStreamWithConfig;
  exports.mapPropsStream = mapPropsStream;
  exports.mapPropsStreamWithConfig = mapPropsStreamWithConfig;
  exports.createEventHandler = createEventHandler;
  exports.createEventHandlerWithConfig = createEventHandlerWithConfig;
  exports.setObservableConfig = configureObservable;

  Object.defineProperty(exports, '__esModule', { value: true });

})));
