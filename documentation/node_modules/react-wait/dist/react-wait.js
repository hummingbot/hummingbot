var t,
  n = require("react"),
  e = (t = n) && "object" == typeof t && "default" in t ? t.default : t,
  r = function(t) {
    return t.length > 0;
  },
  i = function(t, n) {
    return t.includes(n);
  },
  u = function(t, n) {
    return i(t, n) ? t : t.concat([n]);
  },
  a = function(t, n) {
    return t.filter(function(t) {
      return t !== n;
    });
  },
  c = e.createContext();
function o(t) {
  return n.useContext(c).waiters.includes(t.on) ? t.fallback : t.children;
}
(exports.Waiter = function(t) {
  var f = n.useState([]),
    s = f[0],
    l = f[1];
  return e.createElement(
    c.Provider,
    {
      value: {
        waiters: s,
        createWaitingContext: function(t) {
          return {
            isWaiting: function() {
              return i(s, t);
            },
            startWaiting: function() {
              return l(u(s, t));
            },
            endWaiting: function() {
              return l(a(s, t));
            },
            Wait: function(n) {
              return e.createElement(o, Object.assign({}, { on: t }, n));
            }
          };
        },
        anyWaiting: function() {
          return r(s);
        },
        isWaiting: function(t) {
          return i(s, t);
        },
        startWaiting: function(t) {
          l(u(s, t));
        },
        endWaiting: function(t) {
          l(a(s, t));
        }
      }
    },
    t.children
  );
}),
  (exports.useWait = function() {
    var t = n.useContext(c);
    return Object.assign({}, t, { Wait: o });
  });
//# sourceMappingURL=react-wait.js.map
