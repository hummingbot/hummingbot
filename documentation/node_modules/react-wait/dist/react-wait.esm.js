import n, { useState as t, useContext as r } from "react";
var i = function(n) {
    return n.length > 0;
  },
  e = function(n, t) {
    return n.includes(t);
  },
  u = function(n, t) {
    return e(n, t) ? n : n.concat([t]);
  },
  c = function(n, t) {
    return n.filter(function(n) {
      return n !== t;
    });
  },
  a = n.createContext();
function o(n) {
  return r(a).waiters.includes(n.on) ? n.fallback : n.children;
}
function f(r) {
  var f = t([]),
    s = f[0],
    g = f[1];
  return n.createElement(
    a.Provider,
    {
      value: {
        waiters: s,
        createWaitingContext: function(t) {
          return {
            isWaiting: function() {
              return e(s, t);
            },
            startWaiting: function() {
              return g(u(s, t));
            },
            endWaiting: function() {
              return g(c(s, t));
            },
            Wait: function(r) {
              return n.createElement(o, Object.assign({}, { on: t }, r));
            }
          };
        },
        anyWaiting: function() {
          return i(s);
        },
        isWaiting: function(n) {
          return e(s, n);
        },
        startWaiting: function(n) {
          g(u(s, n));
        },
        endWaiting: function(n) {
          g(c(s, n));
        }
      }
    },
    r.children
  );
}
function s() {
  var n = r(a);
  return Object.assign({}, n, { Wait: o });
}
export { f as Waiter, s as useWait };
//# sourceMappingURL=react-wait.esm.js.map
