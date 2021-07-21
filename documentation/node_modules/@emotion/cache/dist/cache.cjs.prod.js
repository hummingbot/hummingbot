"use strict";

function _interopDefault(ex) {
  return ex && "object" == typeof ex && "default" in ex ? ex.default : ex;
}

Object.defineProperty(exports, "__esModule", {
  value: !0
});

var sheet = require("@emotion/sheet"), Stylis = _interopDefault(require("@emotion/stylis")), weakMemoize = _interopDefault(require("@emotion/weak-memoize")), delimiter = "/*|*/", needle = delimiter + "}";

function toSheet(block) {
  block && Sheet.current.insert(block + "}");
}

var Sheet = {
  current: null
}, ruleSheet = function(context, content, selectors, parents, line, column, length, ns, depth, at) {
  switch (context) {
   case 1:
    switch (content.charCodeAt(0)) {
     case 64:
      return Sheet.current.insert(content + ";"), "";

     case 108:
      if (98 === content.charCodeAt(2)) return "";
    }
    break;

   case 2:
    if (0 === ns) return content + delimiter;
    break;

   case 3:
    switch (ns) {
     case 102:
     case 112:
      return Sheet.current.insert(selectors[0] + content), "";

     default:
      return content + (0 === at ? delimiter : "");
    }

   case -2:
    content.split(needle).forEach(toSheet);
  }
}, removeLabel = function(context, content) {
  if (1 === context && 108 === content.charCodeAt(0) && 98 === content.charCodeAt(2)) return "";
}, isBrowser = "undefined" != typeof document, rootServerStylisCache = {}, getServerStylisCache = isBrowser ? void 0 : weakMemoize(function() {
  var getCache = weakMemoize(function() {
    return {};
  }), prefixTrueCache = {}, prefixFalseCache = {};
  return function(prefix) {
    return void 0 === prefix || !0 === prefix ? prefixTrueCache : !1 === prefix ? prefixFalseCache : getCache(prefix);
  };
}), createCache = function(options) {
  void 0 === options && (options = {});
  var stylisOptions, key = options.key || "css";
  void 0 !== options.prefix && (stylisOptions = {
    prefix: options.prefix
  });
  var container, _insert, stylis = new Stylis(stylisOptions), inserted = {};
  if (isBrowser) {
    container = options.container || document.head;
    var nodes = document.querySelectorAll("style[data-emotion-" + key + "]");
    Array.prototype.forEach.call(nodes, function(node) {
      node.getAttribute("data-emotion-" + key).split(" ").forEach(function(id) {
        inserted[id] = !0;
      }), node.parentNode !== container && container.appendChild(node);
    });
  }
  if (isBrowser) stylis.use(options.stylisPlugins)(ruleSheet), _insert = function(selector, serialized, sheet, shouldCache) {
    var name = serialized.name;
    Sheet.current = sheet, stylis(selector, serialized.styles), shouldCache && (cache.inserted[name] = !0);
  }; else {
    stylis.use(removeLabel);
    var serverStylisCache = rootServerStylisCache;
    (options.stylisPlugins || void 0 !== options.prefix) && (stylis.use(options.stylisPlugins), 
    serverStylisCache = getServerStylisCache(options.stylisPlugins || rootServerStylisCache)(options.prefix));
    _insert = function(selector, serialized, sheet, shouldCache) {
      var name = serialized.name, rules = function(selector, serialized) {
        var name = serialized.name;
        return void 0 === serverStylisCache[name] && (serverStylisCache[name] = stylis(selector, serialized.styles)), 
        serverStylisCache[name];
      }(selector, serialized);
      return void 0 === cache.compat ? (shouldCache && (cache.inserted[name] = !0), rules) : shouldCache ? void (cache.inserted[name] = rules) : rules;
    };
  }
  var cache = {
    key: key,
    sheet: new sheet.StyleSheet({
      key: key,
      container: container,
      nonce: options.nonce,
      speedy: options.speedy
    }),
    nonce: options.nonce,
    inserted: inserted,
    registered: {},
    insert: _insert
  };
  return cache;
};

exports.default = createCache;
