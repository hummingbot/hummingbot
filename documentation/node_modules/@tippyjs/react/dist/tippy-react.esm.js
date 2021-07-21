import tippy, { createSingleton } from 'tippy.js';
export { default as tippy } from 'tippy.js';
import React, { useLayoutEffect, useEffect, useRef, useState, cloneElement, useMemo, forwardRef as forwardRef$1 } from 'react';
import { createPortal } from 'react-dom';

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

var isBrowser = typeof window !== 'undefined' && typeof document !== 'undefined';
function preserveRef(ref, node) {
  if (ref) {
    if (typeof ref === 'function') {
      ref(node);
    }

    if ({}.hasOwnProperty.call(ref, 'current')) {
      ref.current = node;
    }
  }
}
function ssrSafeCreateDiv() {
  return isBrowser && document.createElement('div');
}
function toDataAttributes(attrs) {
  var dataAttrs = {
    'data-placement': attrs.placement
  };

  if (attrs.referenceHidden) {
    dataAttrs['data-reference-hidden'] = '';
  }

  if (attrs.escaped) {
    dataAttrs['data-escaped'] = '';
  }

  return dataAttrs;
}
function deepPreserveProps(instanceProps, componentProps) {
  var _instanceProps$popper, _componentProps$poppe;

  return Object.assign({}, componentProps, {
    popperOptions: Object.assign({}, instanceProps.popperOptions, componentProps.popperOptions, {
      modifiers: [].concat((((_instanceProps$popper = instanceProps.popperOptions) == null ? void 0 : _instanceProps$popper.modifiers) || []).filter(function (modifier) {
        return modifier.name.indexOf('tippy') >= 0;
      }), ((_componentProps$poppe = componentProps.popperOptions) == null ? void 0 : _componentProps$poppe.modifiers) || [])
    })
  });
}

var useIsomorphicLayoutEffect = isBrowser ? useLayoutEffect : useEffect;
function useMutableBox(initialValue) {
  // Using refs instead of state as it's recommended to not store imperative
  // values in state due to memory problems in React(?)
  var ref = useRef();

  if (!ref.current) {
    ref.current = typeof initialValue === 'function' ? initialValue() : initialValue;
  }

  return ref.current;
}

function updateClassName(box, action, classNames) {
  classNames.split(/\s+/).forEach(function (name) {
    if (name) {
      box.classList[action](name);
    }
  });
}

var classNamePlugin = {
  name: 'className',
  defaultValue: '',
  fn: function fn(instance) {
    var box = instance.popper.firstElementChild;

    var isDefaultRenderFn = function isDefaultRenderFn() {
      var _instance$props$rende;

      return !!((_instance$props$rende = instance.props.render) == null ? void 0 : _instance$props$rende.$$tippy);
    };

    function add() {
      if (instance.props.className && !isDefaultRenderFn()) {
        if (process.env.NODE_ENV !== 'production') {
          console.warn(['@tippyjs/react: Cannot use `className` prop in conjunction with', '`render` prop. Place the className on the element you are', 'rendering.'].join(' '));
        }

        return;
      }

      updateClassName(box, 'add', instance.props.className);
    }

    function remove() {
      if (isDefaultRenderFn()) {
        updateClassName(box, 'remove', instance.props.className);
      }
    }

    return {
      onCreate: add,
      onBeforeUpdate: remove,
      onAfterUpdate: add
    };
  }
};

function TippyGenerator(tippy) {
  function Tippy(_ref) {
    var children = _ref.children,
        content = _ref.content,
        visible = _ref.visible,
        singleton = _ref.singleton,
        render = _ref.render,
        reference = _ref.reference,
        _ref$disabled = _ref.disabled,
        disabled = _ref$disabled === void 0 ? false : _ref$disabled,
        _ref$ignoreAttributes = _ref.ignoreAttributes,
        ignoreAttributes = _ref$ignoreAttributes === void 0 ? true : _ref$ignoreAttributes,
        __source = _ref.__source,
        __self = _ref.__self,
        restOfNativeProps = _objectWithoutPropertiesLoose(_ref, ["children", "content", "visible", "singleton", "render", "reference", "disabled", "ignoreAttributes", "__source", "__self"]);

    var isControlledMode = visible !== undefined;
    var isSingletonMode = singleton !== undefined;

    var _useState = useState(false),
        mounted = _useState[0],
        setMounted = _useState[1];

    var _useState2 = useState({}),
        attrs = _useState2[0],
        setAttrs = _useState2[1];

    var _useState3 = useState(),
        singletonContent = _useState3[0],
        setSingletonContent = _useState3[1];

    var mutableBox = useMutableBox(function () {
      return {
        container: ssrSafeCreateDiv(),
        renders: 1
      };
    });
    var props = Object.assign({
      ignoreAttributes: ignoreAttributes
    }, restOfNativeProps, {
      content: mutableBox.container
    });

    if (isControlledMode) {
      if (process.env.NODE_ENV !== 'production') {
        ['trigger', 'hideOnClick', 'showOnCreate'].forEach(function (nativeStateProp) {
          if (props[nativeStateProp] !== undefined) {
            console.warn(["@tippyjs/react: Cannot specify `" + nativeStateProp + "` prop in", "controlled mode (`visible` prop)"].join(' '));
          }
        });
      }

      props.trigger = 'manual';
      props.hideOnClick = false;
    }

    if (isSingletonMode) {
      disabled = true;
    }

    var computedProps = props;
    var plugins = props.plugins || [];

    if (render) {
      computedProps = Object.assign({}, props, {
        plugins: isSingletonMode ? [].concat(plugins, [{
          fn: function fn() {
            return {
              onTrigger: function onTrigger(_, event) {
                var _singleton$data$child = singleton.data.children.find(function (_ref2) {
                  var instance = _ref2.instance;
                  return instance.reference === event.currentTarget;
                }),
                    content = _singleton$data$child.content;

                setSingletonContent(content);
              }
            };
          }
        }]) : plugins,
        render: function render() {
          return {
            popper: mutableBox.container
          };
        }
      });
    }

    var deps = [reference].concat(children ? [children.type] : []); // CREATE

    useIsomorphicLayoutEffect(function () {
      var element = reference;

      if (reference && reference.hasOwnProperty('current')) {
        element = reference.current;
      }

      var instance = tippy(element || mutableBox.ref || ssrSafeCreateDiv(), Object.assign({}, computedProps, {
        plugins: [classNamePlugin].concat(props.plugins || [])
      }));
      mutableBox.instance = instance;

      if (disabled) {
        instance.disable();
      }

      if (visible) {
        instance.show();
      }

      if (isSingletonMode) {
        singleton.hook({
          instance: instance,
          content: content,
          props: computedProps
        });
      }

      setMounted(true);
      return function () {
        instance.destroy();
        singleton == null ? void 0 : singleton.cleanup(instance);
      };
    }, deps); // UPDATE

    useIsomorphicLayoutEffect(function () {
      // Prevent this effect from running on 1st render
      if (mutableBox.renders === 1) {
        mutableBox.renders++;
        return;
      }

      var instance = mutableBox.instance;
      instance.setProps(deepPreserveProps(instance.props, computedProps));

      if (disabled) {
        instance.disable();
      } else {
        instance.enable();
      }

      if (isControlledMode) {
        if (visible) {
          instance.show();
        } else {
          instance.hide();
        }
      }

      if (isSingletonMode) {
        singleton.hook({
          instance: instance,
          content: content,
          props: computedProps
        });
      }
    });
    useIsomorphicLayoutEffect(function () {
      var _instance$props$poppe;

      if (!render) {
        return;
      }

      var instance = mutableBox.instance;
      instance.setProps({
        popperOptions: Object.assign({}, instance.props.popperOptions, {
          modifiers: [].concat(((_instance$props$poppe = instance.props.popperOptions) == null ? void 0 : _instance$props$poppe.modifiers) || [], [{
            name: '$$tippyReact',
            enabled: true,
            phase: 'beforeWrite',
            requires: ['computeStyles'],
            fn: function fn(_ref3) {
              var _state$modifiersData;

              var state = _ref3.state;
              var hideData = (_state$modifiersData = state.modifiersData) == null ? void 0 : _state$modifiersData.hide; // WARNING: this is a high-risk path that can cause an infinite
              // loop. This expression _must_ evaluate to false when required

              if (attrs.placement !== state.placement || attrs.referenceHidden !== (hideData == null ? void 0 : hideData.isReferenceHidden) || attrs.escaped !== (hideData == null ? void 0 : hideData.hasPopperEscaped)) {
                setAttrs({
                  placement: state.placement,
                  referenceHidden: hideData == null ? void 0 : hideData.isReferenceHidden,
                  escaped: hideData == null ? void 0 : hideData.hasPopperEscaped
                });
              }

              state.attributes.popper = {};
            }
          }])
        })
      });
    }, [attrs.placement, attrs.referenceHidden, attrs.escaped].concat(deps));
    return /*#__PURE__*/React.createElement(React.Fragment, null, children ? /*#__PURE__*/cloneElement(children, {
      ref: function ref(node) {
        mutableBox.ref = node;
        preserveRef(children.ref, node);
      }
    }) : null, mounted && /*#__PURE__*/createPortal(render ? render(toDataAttributes(attrs), singletonContent, mutableBox.instance) : content, mutableBox.container));
  }

  return Tippy;
}

function useSingletonGenerator(createSingleton) {
  return function useSingleton(_temp) {
    var _ref = _temp === void 0 ? {} : _temp,
        _ref$disabled = _ref.disabled,
        disabled = _ref$disabled === void 0 ? false : _ref$disabled,
        _ref$overrides = _ref.overrides,
        overrides = _ref$overrides === void 0 ? [] : _ref$overrides;

    var _useState = useState(false),
        mounted = _useState[0],
        setMounted = _useState[1];

    var mutableBox = useMutableBox({
      children: [],
      renders: 1
    });
    useIsomorphicLayoutEffect(function () {
      if (!mounted) {
        setMounted(true);
        return;
      }

      var children = mutableBox.children,
          sourceData = mutableBox.sourceData;

      if (!sourceData) {
        if (process.env.NODE_ENV !== 'production') {
          console.error(['@tippyjs/react: The `source` variable from `useSingleton()` has', 'not been passed to a <Tippy /> component.'].join(' '));
        }

        return;
      }

      var instance = createSingleton(children.map(function (child) {
        return child.instance;
      }), Object.assign({}, sourceData.props, {
        popperOptions: sourceData.instance.props.popperOptions,
        overrides: overrides,
        plugins: [classNamePlugin].concat(sourceData.props.plugins || [])
      }));
      mutableBox.instance = instance;

      if (disabled) {
        instance.disable();
      }

      return function () {
        instance.destroy();
        mutableBox.children = children.filter(function (_ref2) {
          var instance = _ref2.instance;
          return !instance.state.isDestroyed;
        });
      };
    }, [mounted]);
    useIsomorphicLayoutEffect(function () {
      if (!mounted) {
        return;
      }

      if (mutableBox.renders === 1) {
        mutableBox.renders++;
        return;
      }

      var children = mutableBox.children,
          instance = mutableBox.instance,
          sourceData = mutableBox.sourceData;

      if (!(instance && sourceData)) {
        return;
      }

      var _sourceData$props = sourceData.props,
          content = _sourceData$props.content,
          props = _objectWithoutPropertiesLoose(_sourceData$props, ["content"]);

      instance.setProps(deepPreserveProps(instance, Object.assign({}, props, {
        overrides: overrides
      })));
      instance.setInstances(children.map(function (child) {
        return child.instance;
      }));

      if (disabled) {
        instance.disable();
      } else {
        instance.enable();
      }
    });
    return useMemo(function () {
      var source = {
        data: mutableBox,
        hook: function hook(data) {
          mutableBox.sourceData = data;
        },
        cleanup: function cleanup() {
          mutableBox.sourceData = null;
        }
      };
      var target = {
        hook: function hook(data) {
          if (!mutableBox.children.find(function (_ref3) {
            var instance = _ref3.instance;
            return data.instance === instance;
          })) {
            mutableBox.children.push(data);
          }
        },
        cleanup: function cleanup(instance) {
          mutableBox.children = mutableBox.children.filter(function (data) {
            return data.instance !== instance;
          });
        }
      };
      return [source, target];
    }, []);
  };
}

var forwardRef = (function (Tippy, defaultProps) {
  return /*#__PURE__*/forwardRef$1(function TippyWrapper(_ref, _ref2) {
    var children = _ref.children,
        props = _objectWithoutPropertiesLoose(_ref, ["children"]);

    return (
      /*#__PURE__*/
      // If I spread them separately here, Babel adds the _extends ponyfill for
      // some reason
      React.createElement(Tippy, Object.assign({}, defaultProps, props), children ? /*#__PURE__*/cloneElement(children, {
        ref: function ref(node) {
          preserveRef(_ref2, node);
          preserveRef(children.ref, node);
        }
      }) : null)
    );
  });
});

var useSingleton = /*#__PURE__*/useSingletonGenerator(createSingleton);
var index = /*#__PURE__*/forwardRef( /*#__PURE__*/TippyGenerator(tippy));

export default index;
export { useSingleton };
//# sourceMappingURL=tippy-react.esm.js.map
