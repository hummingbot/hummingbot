!(function(t, n) {
  "object" == typeof exports && "undefined" != typeof module
    ? n(exports, require("react"))
    : "function" == typeof define && define.amd
    ? define(["exports", "react"], n)
    : n((t.reactWait = {}), t.react);
})(this, function(t, n) {
  var e = "default" in n ? n.default : n,
    i = function(t) {
      return t.length > 0;
    },
    r = function(t, n) {
      return t.includes(n);
    },
    u = function(t, n) {
      return r(t, n) ? t : t.concat([n]);
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
  (t.Waiter = function(t) {
    var f = n.useState([]),
      s = f[0],
      d = f[1];
    return e.createElement(
      c.Provider,
      {
        value: {
          waiters: s,
          createWaitingContext: function(t) {
            return {
              isWaiting: function() {
                return r(s, t);
              },
              startWaiting: function() {
                return d(u(s, t));
              },
              endWaiting: function() {
                return d(a(s, t));
              },
              Wait: function(n) {
                return e.createElement(o, Object.assign({}, { on: t }, n));
              }
            };
          },
          anyWaiting: function() {
            return i(s);
          },
          isWaiting: function(t) {
            return r(s, t);
          },
          startWaiting: function(t) {
            d(u(s, t));
          },
          endWaiting: function(t) {
            d(a(s, t));
          }
        }
      },
      t.children
    );
  }),
    (t.useWait = function() {
      var t = n.useContext(c);
      return Object.assign({}, t, { Wait: o });
    });
});
//# sourceMappingURL=react-wait.umd.js.map
