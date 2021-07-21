"use strict";

function _interopDefault(ex) {
  return ex && "object" == typeof ex && "default" in ex ? ex.default : ex;
}

Object.defineProperty(exports, "__esModule", {
  value: !0
});

var _inheritsLoose = _interopDefault(require("@babel/runtime/helpers/inheritsLoose")), React = require("react"), createCache = _interopDefault(require("@emotion/cache")), utils = require("@emotion/utils"), serialize = require("@emotion/serialize"), sheet = require("@emotion/sheet"), css = _interopDefault(require("@emotion/css")), isBrowser = "undefined" != typeof document, EmotionCacheContext = React.createContext("undefined" != typeof HTMLElement ? createCache() : null), ThemeContext = React.createContext({}), CacheProvider = EmotionCacheContext.Provider;

if (exports.withEmotionCache = function(func) {
  return React.forwardRef(function(props, ref) {
    return React.createElement(EmotionCacheContext.Consumer, null, function(cache) {
      return func(props, cache, ref);
    });
  });
}, !isBrowser) {
  var BasicProvider = function(_React$Component) {
    function BasicProvider(props, context, updater) {
      var _this;
      return (_this = _React$Component.call(this, props, context, updater) || this).state = {
        value: createCache()
      }, _this;
    }
    return _inheritsLoose(BasicProvider, _React$Component), BasicProvider.prototype.render = function() {
      return React.createElement(EmotionCacheContext.Provider, this.state, this.props.children(this.state.value));
    }, BasicProvider;
  }(React.Component);
  exports.withEmotionCache = function(func) {
    return function(props) {
      return React.createElement(EmotionCacheContext.Consumer, null, function(context) {
        return null === context ? React.createElement(BasicProvider, null, function(newContext) {
          return func(props, newContext);
        }) : func(props, context);
      });
    };
  };
}

var typePropName = "__EMOTION_TYPE_PLEASE_DO_NOT_USE__", hasOwnProperty = Object.prototype.hasOwnProperty, render = function(cache, props, theme, ref) {
  var cssProp = null === theme ? props.css : props.css(theme);
  "string" == typeof cssProp && void 0 !== cache.registered[cssProp] && (cssProp = cache.registered[cssProp]);
  var type = props[typePropName], registeredStyles = [ cssProp ], className = "";
  "string" == typeof props.className ? className = utils.getRegisteredStyles(cache.registered, registeredStyles, props.className) : null != props.className && (className = props.className + " ");
  var serialized = serialize.serializeStyles(registeredStyles), rules = utils.insertStyles(cache, serialized, "string" == typeof type);
  className += cache.key + "-" + serialized.name;
  var newProps = {};
  for (var key in props) hasOwnProperty.call(props, key) && "css" !== key && key !== typePropName && (newProps[key] = props[key]);
  newProps.ref = ref, newProps.className = className;
  var ele = React.createElement(type, newProps);
  if (!isBrowser && void 0 !== rules) {
    for (var _ref, serializedNames = serialized.name, next = serialized.next; void 0 !== next; ) serializedNames += " " + next.name, 
    next = next.next;
    return React.createElement(React.Fragment, null, React.createElement("style", ((_ref = {})["data-emotion-" + cache.key] = serializedNames, 
    _ref.dangerouslySetInnerHTML = {
      __html: rules
    }, _ref.nonce = cache.sheet.nonce, _ref)), ele);
  }
  return ele;
}, Emotion = exports.withEmotionCache(function(props, cache, ref) {
  return "function" == typeof props.css ? React.createElement(ThemeContext.Consumer, null, function(theme) {
    return render(cache, props, theme, ref);
  }) : render(cache, props, null, ref);
}), jsx = function(type, props) {
  var args = arguments;
  if (null == props || !hasOwnProperty.call(props, "css")) return React.createElement.apply(void 0, args);
  var argsLength = args.length, createElementArgArray = new Array(argsLength);
  createElementArgArray[0] = Emotion;
  var newProps = {};
  for (var key in props) hasOwnProperty.call(props, key) && (newProps[key] = props[key]);
  newProps[typePropName] = type, createElementArgArray[1] = newProps;
  for (var i = 2; i < argsLength; i++) createElementArgArray[i] = args[i];
  return React.createElement.apply(null, createElementArgArray);
}, Global = exports.withEmotionCache(function(props, cache) {
  var styles = props.styles;
  if ("function" == typeof styles) return React.createElement(ThemeContext.Consumer, null, function(theme) {
    var serialized = serialize.serializeStyles([ styles(theme) ]);
    return React.createElement(InnerGlobal, {
      serialized: serialized,
      cache: cache
    });
  });
  var serialized = serialize.serializeStyles([ styles ]);
  return React.createElement(InnerGlobal, {
    serialized: serialized,
    cache: cache
  });
}), InnerGlobal = function(_React$Component) {
  function InnerGlobal(props, context, updater) {
    return _React$Component.call(this, props, context, updater) || this;
  }
  _inheritsLoose(InnerGlobal, _React$Component);
  var _proto = InnerGlobal.prototype;
  return _proto.componentDidMount = function() {
    this.sheet = new sheet.StyleSheet({
      key: this.props.cache.key + "-global",
      nonce: this.props.cache.sheet.nonce,
      container: this.props.cache.sheet.container
    });
    var node = document.querySelector("style[data-emotion-" + this.props.cache.key + '="' + this.props.serialized.name + '"]');
    null !== node && this.sheet.tags.push(node), this.props.cache.sheet.tags.length && (this.sheet.before = this.props.cache.sheet.tags[0]), 
    this.insertStyles();
  }, _proto.componentDidUpdate = function(prevProps) {
    prevProps.serialized.name !== this.props.serialized.name && this.insertStyles();
  }, _proto.insertStyles = function() {
    if (void 0 !== this.props.serialized.next && utils.insertStyles(this.props.cache, this.props.serialized.next, !0), 
    this.sheet.tags.length) {
      var element = this.sheet.tags[this.sheet.tags.length - 1].nextElementSibling;
      this.sheet.before = element, this.sheet.flush();
    }
    this.props.cache.insert("", this.props.serialized, this.sheet, !1);
  }, _proto.componentWillUnmount = function() {
    this.sheet.flush();
  }, _proto.render = function() {
    if (!isBrowser) {
      for (var serialized = this.props.serialized, serializedNames = serialized.name, serializedStyles = serialized.styles, next = serialized.next; void 0 !== next; ) serializedNames += " " + next.name, 
      serializedStyles += next.styles, next = next.next;
      var _ref, shouldCache = !0 === this.props.cache.compat, rules = this.props.cache.insert("", {
        name: serializedNames,
        styles: serializedStyles
      }, this.sheet, shouldCache);
      if (!shouldCache) return React.createElement("style", ((_ref = {})["data-emotion-" + this.props.cache.key] = serializedNames, 
      _ref.dangerouslySetInnerHTML = {
        __html: rules
      }, _ref.nonce = this.props.cache.sheet.nonce, _ref));
    }
    return null;
  }, InnerGlobal;
}(React.Component), keyframes = function() {
  var insertable = css.apply(void 0, arguments), name = "animation-" + insertable.name;
  return {
    name: name,
    styles: "@keyframes " + name + "{" + insertable.styles + "}",
    anim: 1,
    toString: function() {
      return "_EMO_" + this.name + "_" + this.styles + "_EMO_";
    }
  };
}, classnames = function classnames(args) {
  for (var len = args.length, i = 0, cls = ""; i < len; i++) {
    var arg = args[i];
    if (null != arg) {
      var toAdd = void 0;
      switch (typeof arg) {
       case "boolean":
        break;

       case "object":
        if (Array.isArray(arg)) toAdd = classnames(arg); else for (var k in toAdd = "", 
        arg) arg[k] && k && (toAdd && (toAdd += " "), toAdd += k);
        break;

       default:
        toAdd = arg;
      }
      toAdd && (cls && (cls += " "), cls += toAdd);
    }
  }
  return cls;
};

function merge(registered, css, className) {
  var registeredStyles = [], rawClassName = utils.getRegisteredStyles(registered, registeredStyles, className);
  return registeredStyles.length < 2 ? className : rawClassName + css(registeredStyles);
}

var ClassNames = exports.withEmotionCache(function(props, context) {
  return React.createElement(ThemeContext.Consumer, null, function(theme) {
    var _ref, rules = "", serializedHashes = "", css = function() {
      for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) args[_key] = arguments[_key];
      var serialized = serialize.serializeStyles(args, context.registered);
      if (isBrowser) utils.insertStyles(context, serialized, !1); else {
        var res = utils.insertStyles(context, serialized, !1);
        void 0 !== res && (rules += res);
      }
      return isBrowser || (serializedHashes += " " + serialized.name), context.key + "-" + serialized.name;
    }, content = {
      css: css,
      cx: function() {
        for (var _len2 = arguments.length, args = new Array(_len2), _key2 = 0; _key2 < _len2; _key2++) args[_key2] = arguments[_key2];
        return merge(context.registered, css, classnames(args));
      },
      theme: theme
    }, ele = props.children(content);
    return !0, isBrowser || 0 === rules.length ? ele : React.createElement(React.Fragment, null, React.createElement("style", ((_ref = {})["data-emotion-" + context.key] = serializedHashes.substring(1), 
    _ref.dangerouslySetInnerHTML = {
      __html: rules
    }, _ref.nonce = context.sheet.nonce, _ref)), ele);
  });
});

exports.css = css, exports.CacheProvider = CacheProvider, exports.ClassNames = ClassNames, 
exports.Global = Global, exports.ThemeContext = ThemeContext, exports.jsx = jsx, 
exports.keyframes = keyframes;
