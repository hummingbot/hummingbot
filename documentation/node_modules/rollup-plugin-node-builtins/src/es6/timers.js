// License https://jryans.mit-license.org/

import {setImmediate, clearImmediate} from './setimmediate';
export {setImmediate, clearImmediate};
// DOM APIs, for completeness
var apply = Function.prototype.apply;

export function clearInterval(timeout) {
  if (typeof timeout === 'number' && typeof global.clearInterval === 'function') {
    global.clearInterval(timeout);
  } else {
    clearFn(timeout)
  }
}
export function clearTimeout(timeout) {
  if (typeof timeout === 'number' && typeof global.clearTimeout === 'function') {
    global.clearTimeout(timeout);
  } else {
    clearFn(timeout)
  }
}
function clearFn(timeout) {
  if (timeout && typeof timeout.close === 'function') {
    timeout.close();
  }
}
export function setTimeout() {
  return new Timeout(apply.call(global.setTimeout, window, arguments), clearTimeout);
}
export function setInterval() {
  return new Timeout(apply.call(global.setInterval, window, arguments), clearInterval);
}

function Timeout(id) {
  this._id = id;
}
Timeout.prototype.unref = Timeout.prototype.ref = function() {};
Timeout.prototype.close = function() {
  clearFn(this._id);
}

// Does not start the time, just sets up the members needed.
export function enroll(item, msecs) {
  clearTimeout(item._idleTimeoutId);
  item._idleTimeout = msecs;
}

export function unenroll(item) {
  clearTimeout(item._idleTimeoutId);
  item._idleTimeout = -1;
}
export var _unrefActive = active;
export function active(item) {
  clearTimeout(item._idleTimeoutId);

  var msecs = item._idleTimeout;
  if (msecs >= 0) {
    item._idleTimeoutId = setTimeout(function onTimeout() {
      if (item._onTimeout)
        item._onTimeout();
    }, msecs);
  }
}

export default {
  setImmediate: setImmediate,
  clearImmediate: clearImmediate,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout,
  setInterval: setInterval,
  clearInterval: clearInterval,
  active: active,
  unenroll: unenroll,
  _unrefActive: _unrefActive,
  enroll: enroll
};
