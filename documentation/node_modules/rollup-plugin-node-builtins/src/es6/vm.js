/*
from https://github.com/substack/vm-browserify/blob/bfd7c5f59edec856dc7efe0b77a4f6b2fa20f226/index.js

MIT license no Copyright holder mentioned
*/


function Object_keys(obj) {
  if (Object.keys) return Object.keys(obj)
  else {
    var res = [];
    for (var key in obj) res.push(key)
    return res;
  }
}

function forEach(xs, fn) {
  if (xs.forEach) return xs.forEach(fn)
  else
    for (var i = 0; i < xs.length; i++) {
      fn(xs[i], i, xs);
    }
}
var _defineProp;

function defineProp(obj, name, value) {
  if (typeof _defineProp !== 'function') {
    _defineProp = createDefineProp;
  }
  _defineProp(obj, name, value);
}

function createDefineProp() {
  try {
    Object.defineProperty({}, '_', {});
    return function(obj, name, value) {
      Object.defineProperty(obj, name, {
        writable: true,
        enumerable: false,
        configurable: true,
        value: value
      })
    };
  } catch (e) {
    return function(obj, name, value) {
      obj[name] = value;
    };
  }
}

var globals = ['Array', 'Boolean', 'Date', 'Error', 'EvalError', 'Function',
  'Infinity', 'JSON', 'Math', 'NaN', 'Number', 'Object', 'RangeError',
  'ReferenceError', 'RegExp', 'String', 'SyntaxError', 'TypeError', 'URIError',
  'decodeURI', 'decodeURIComponent', 'encodeURI', 'encodeURIComponent', 'escape',
  'eval', 'isFinite', 'isNaN', 'parseFloat', 'parseInt', 'undefined', 'unescape'
];

function Context() {}
Context.prototype = {};

export function Script(code) {
  if (!(this instanceof Script)) return new Script(code);
  this.code = code;
}
function otherRunInContext(code, context) {
  var args = Object_keys(global);
  args.push('with (this.__ctx__){return eval(this.__code__)}');
  var fn = Function.apply(null, args);
  return fn.apply({
    __code__: code,
    __ctx__: context
  });
}
Script.prototype.runInContext = function(context) {
  if (!(context instanceof Context)) {
    throw new TypeError('needs a \'context\' argument.');
  }
  if (global.document) {
    var iframe = global.document.createElement('iframe');
    if (!iframe.style) iframe.style = {};
    iframe.style.display = 'none';

    global.document.body.appendChild(iframe);

    var win = iframe.contentWindow;
    var wEval = win.eval,
      wExecScript = win.execScript;

    if (!wEval && wExecScript) {
      // win.eval() magically appears when this is called in IE:
      wExecScript.call(win, 'null');
      wEval = win.eval;
    }

    forEach(Object_keys(context), function(key) {
      win[key] = context[key];
    });
    forEach(globals, function(key) {
      if (context[key]) {
        win[key] = context[key];
      }
    });

    var winKeys = Object_keys(win);

    var res = wEval.call(win, this.code);

    forEach(Object_keys(win), function(key) {
      // Avoid copying circular objects like `top` and `window` by only
      // updating existing context properties or new properties in the `win`
      // that was only introduced after the eval.
      if (key in context || indexOf(winKeys, key) === -1) {
        context[key] = win[key];
      }
    });

    forEach(globals, function(key) {
      if (!(key in context)) {
        defineProp(context, key, win[key]);
      }
    });
    global.document.body.removeChild(iframe);

    return res;
  }
  return otherRunInContext(this.code, context);
};

Script.prototype.runInThisContext = function() {
  var fn = new Function('code', 'return eval(code);');
  return fn.call(global, this.code); // maybe...
};

Script.prototype.runInNewContext = function(context) {
  var ctx = createContext(context);
  var res = this.runInContext(ctx);
  if (context) {
    forEach(Object_keys(ctx), function(key) {
      context[key] = ctx[key];
    });
  }

  return res;
};


export function createScript(code) {
  return new Script(code);
}

export function createContext(context) {
  if (isContext(context)) {
    return context;
  }
  var copy = new Context();
  if (typeof context === 'object') {
    forEach(Object_keys(context), function(key) {
      copy[key] = context[key];
    });
  }
  return copy;
}
export function runInContext(code, contextifiedSandbox, options) {
  var script = new Script(code, options);
  return script.runInContext(contextifiedSandbox, options);
}
export function runInThisContext(code, options) {
  var script = new Script(code, options);
  return script.runInThisContext(options);
}
export function isContext(context) {
  return context instanceof Context;
}
export function runInNewContext(code, sandbox, options) {
  var script = new Script(code, options);
  return script.runInNewContext(sandbox, options);
}
export default {
  runInContext: runInContext,
  isContext: isContext,
  createContext: createContext,
  createScript: createScript,
  Script: Script,
  runInThisContext: runInThisContext,
  runInNewContext: runInNewContext
}


/*
from indexOf
@ author tjholowaychuk
@ license MIT
*/
var _indexOf = [].indexOf;

function indexOf(arr, obj){
  if (_indexOf) return arr.indexOf(obj);
  for (var i = 0; i < arr.length; ++i) {
    if (arr[i] === obj) return i;
  }
  return -1;
}
