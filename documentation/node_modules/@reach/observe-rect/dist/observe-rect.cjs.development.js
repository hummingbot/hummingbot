'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

var props = ["bottom", "height", "left", "right", "top", "width"];

var rectChanged = function rectChanged(a, b) {
  if (a === void 0) {
    a = {};
  }

  if (b === void 0) {
    b = {};
  }

  return props.some(function (prop) {
    return a[prop] !== b[prop];
  });
};

var observedNodes = /*#__PURE__*/new Map();
var rafId;

var run = function run() {
  var changedStates = [];
  observedNodes.forEach(function (state, node) {
    var newRect = node.getBoundingClientRect();

    if (rectChanged(newRect, state.rect)) {
      state.rect = newRect;
      changedStates.push(state);
    }
  });
  changedStates.forEach(function (state) {
    state.callbacks.forEach(function (cb) {
      return cb(state.rect);
    });
  });
  rafId = window.requestAnimationFrame(run);
};

function observeRect(node, cb) {
  return {
    observe: function observe() {
      var wasEmpty = observedNodes.size === 0;

      if (observedNodes.has(node)) {
        observedNodes.get(node).callbacks.push(cb);
      } else {
        observedNodes.set(node, {
          rect: undefined,
          hasRectChanged: false,
          callbacks: [cb]
        });
      }

      if (wasEmpty) run();
    },
    unobserve: function unobserve() {
      var state = observedNodes.get(node);

      if (state) {
        // Remove the callback
        var index = state.callbacks.indexOf(cb);
        if (index >= 0) state.callbacks.splice(index, 1); // Remove the node reference

        if (!state.callbacks.length) observedNodes["delete"](node); // Stop the loop

        if (!observedNodes.size) cancelAnimationFrame(rafId);
      }
    }
  };
}

exports.default = observeRect;
//# sourceMappingURL=observe-rect.cjs.development.js.map
