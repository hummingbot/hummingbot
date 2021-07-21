"use strict";

function _interopDefault(ex) {
  return ex && "object" == typeof ex && "default" in ex ? ex.default : ex;
}

Object.defineProperty(exports, "__esModule", {
  value: !0
});

var _defineProperty = _interopDefault(require("@babel/runtime/helpers/defineProperty")), React = require("react"), isPropValid = _interopDefault(require("@emotion/is-prop-valid")), core = require("@emotion/core"), utils = require("@emotion/utils"), serialize = require("@emotion/serialize"), testOmitPropsOnStringTag = isPropValid, testOmitPropsOnComponent = function(key) {
  return "theme" !== key && "innerRef" !== key;
}, getDefaultShouldForwardProp = function(tag) {
  return "string" == typeof tag && tag.charCodeAt(0) > 96 ? testOmitPropsOnStringTag : testOmitPropsOnComponent;
};

function ownKeys(object, enumerableOnly) {
  var keys = Object.keys(object);
  if (Object.getOwnPropertySymbols) {
    var symbols = Object.getOwnPropertySymbols(object);
    enumerableOnly && (symbols = symbols.filter(function(sym) {
      return Object.getOwnPropertyDescriptor(object, sym).enumerable;
    })), keys.push.apply(keys, symbols);
  }
  return keys;
}

function _objectSpread(target) {
  for (var i = 1; i < arguments.length; i++) {
    var source = null != arguments[i] ? arguments[i] : {};
    i % 2 ? ownKeys(source, !0).forEach(function(key) {
      _defineProperty(target, key, source[key]);
    }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(target, Object.getOwnPropertyDescriptors(source)) : ownKeys(source).forEach(function(key) {
      Object.defineProperty(target, key, Object.getOwnPropertyDescriptor(source, key));
    });
  }
  return target;
}

var isBrowser = "undefined" != typeof document, createStyled = function createStyled(tag, options) {
  var identifierName, shouldForwardProp, targetClassName;
  void 0 !== options && (identifierName = options.label, targetClassName = options.target, 
  shouldForwardProp = tag.__emotion_forwardProp && options.shouldForwardProp ? function(propName) {
    return tag.__emotion_forwardProp(propName) && options.shouldForwardProp(propName);
  } : options.shouldForwardProp);
  var isReal = tag.__emotion_real === tag, baseTag = isReal && tag.__emotion_base || tag;
  "function" != typeof shouldForwardProp && isReal && (shouldForwardProp = tag.__emotion_forwardProp);
  var defaultShouldForwardProp = shouldForwardProp || getDefaultShouldForwardProp(baseTag), shouldUseAs = !defaultShouldForwardProp("as");
  return function() {
    var args = arguments, styles = isReal && void 0 !== tag.__emotion_styles ? tag.__emotion_styles.slice(0) : [];
    if (void 0 !== identifierName && styles.push("label:" + identifierName + ";"), null == args[0] || void 0 === args[0].raw) styles.push.apply(styles, args); else {
      styles.push(args[0][0]);
      for (var len = args.length, i = 1; i < len; i++) styles.push(args[i], args[0][i]);
    }
    var Styled = core.withEmotionCache(function(props, context, ref) {
      return React.createElement(core.ThemeContext.Consumer, null, function(theme) {
        var finalTag = shouldUseAs && props.as || baseTag, className = "", classInterpolations = [], mergedProps = props;
        if (null == props.theme) {
          for (var key in mergedProps = {}, props) mergedProps[key] = props[key];
          mergedProps.theme = theme;
        }
        "string" == typeof props.className ? className = utils.getRegisteredStyles(context.registered, classInterpolations, props.className) : null != props.className && (className = props.className + " ");
        var serialized = serialize.serializeStyles(styles.concat(classInterpolations), context.registered, mergedProps), rules = utils.insertStyles(context, serialized, "string" == typeof finalTag);
        className += context.key + "-" + serialized.name, void 0 !== targetClassName && (className += " " + targetClassName);
        var finalShouldForwardProp = shouldUseAs && void 0 === shouldForwardProp ? getDefaultShouldForwardProp(finalTag) : defaultShouldForwardProp, newProps = {};
        for (var _key in props) shouldUseAs && "as" === _key || finalShouldForwardProp(_key) && (newProps[_key] = props[_key]);
        newProps.className = className, newProps.ref = ref || props.innerRef;
        var ele = React.createElement(finalTag, newProps);
        if (!isBrowser && void 0 !== rules) {
          for (var _ref, serializedNames = serialized.name, next = serialized.next; void 0 !== next; ) serializedNames += " " + next.name, 
          next = next.next;
          return React.createElement(React.Fragment, null, React.createElement("style", ((_ref = {})["data-emotion-" + context.key] = serializedNames, 
          _ref.dangerouslySetInnerHTML = {
            __html: rules
          }, _ref.nonce = context.sheet.nonce, _ref)), ele);
        }
        return ele;
      });
    });
    return Styled.displayName = void 0 !== identifierName ? identifierName : "Styled(" + ("string" == typeof baseTag ? baseTag : baseTag.displayName || baseTag.name || "Component") + ")", 
    Styled.defaultProps = tag.defaultProps, Styled.__emotion_real = Styled, Styled.__emotion_base = baseTag, 
    Styled.__emotion_styles = styles, Styled.__emotion_forwardProp = shouldForwardProp, 
    Object.defineProperty(Styled, "toString", {
      value: function() {
        return "." + targetClassName;
      }
    }), Styled.withComponent = function(nextTag, nextOptions) {
      return createStyled(nextTag, void 0 !== nextOptions ? _objectSpread({}, options || {}, {}, nextOptions) : options).apply(void 0, styles);
    }, Styled;
  };
};

exports.default = createStyled;
