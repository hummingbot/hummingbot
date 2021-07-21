# stacktrace.js
Generate, parse and enhance JavaScript stack traces in all browsers

[![Build Status](https://img.shields.io/travis/stacktracejs/stacktrace.js/master.svg?style=flat-square)](https://travis-ci.org/stacktracejs/stacktrace.js) 
[![Coverage Status](https://img.shields.io/coveralls/stacktracejs/stacktrace.js.svg?style=flat-square)](https://coveralls.io/r/stacktracejs/stacktrace.js?branch=master) 
[![GitHub license](https://img.shields.io/github/license/stacktracejs/stacktrace.js.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![CDNJS](https://img.shields.io/cdnjs/v/stacktrace.js.svg?style=flat-square)](https://cdnjs.com/libraries/stacktrace.js)
[![size with dependencies](https://img.shields.io/badge/size-29.9k-green.svg?style=flat-square)](https://github.com/stacktracejs/stacktrace.js/releases)
[![gzip size](https://img.shields.io/badge/gzipped-9.1k-green.svg?style=flat-square)](https://github.com/stacktracejs/stacktrace.js/releases)
[![module format](https://img.shields.io/badge/module%20format-umd-lightgrey.svg?style=flat-square&colorB=ff69b4)](https://github.com/stacktracejs/stacktrace.js/releases)

Debug and profile your JavaScript with a [stack trace](http://en.wikipedia.org/wiki/Stack_trace) of function calls leading to an error (or any condition you specify).

stacktrace.js uses browsers' `Error.stack` mechanism to generate stack traces, parses them, enhances them with
[source maps](http://www.html5rocks.com/en/tutorials/developertools/sourcemaps/) and uses
[Promises](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise)
to return an Array of [StackFrames](https://github.com/stacktracejs/stackframe).

#### Upgrading? Check the [0.x -> 1.x Migration Guide](https://www.stacktracejs.com/#!/docs/v0-migration-guide)

## Usage
#### Get a stack trace from current location
```js
var callback = function(stackframes) {
    var stringifiedStack = stackframes.map(function(sf) {
        return sf.toString();
    }).join('\n');
    console.log(stringifiedStack);
};

var errback = function(err) { console.log(err.message); };

StackTrace.get().then(callback).catch(errback);
//===> Promise(Array[StackFrame], Error)
//===> callback([
//    StackFrame({functionName: 'func1', args: [], fileName: 'file.js', lineNumber: 203, columnNumber: 9}), 
//    StackFrame({functionName: 'func2', args: [], fileName: 'http://localhost:3000/file.min.js', lineNumber: 1, columnNumber: 3284})
//])
```

#### You can also get a stack trace synchronously
**HEADS UP:** This method does not resolve source maps or guess anonymous function names.

```js
StackTrace.getSync();
//==> [
//      StackFrame({functionName: 'func1', args: [], fileName: 'file.js', lineNumber: 203, columnNumber: 9}), 
//      StackFrame({functionName: 'func2', args: [], fileName: 'http://localhost:3000/file.min.js', lineNumber: 1, columnNumber: 3284})
//]
```

#### window.onerror integration
Automatically handle errors
```js
window.onerror = function(msg, file, line, col, error) {
    // callback is called with an Array[StackFrame]
    StackTrace.fromError(error).then(callback).catch(errback);
};
```

#### Get stack trace from an Error
```js
var error = new Error('BOOM!');

StackTrace.fromError(error).then(callback).catch(errback);
//===> Promise(Array[StackFrame], Error)
```

#### Generate a stacktrace from walking arguments.callee
This might capture arguments information, but isn't supported in ES5 strict-mode
```js
StackTrace.generateArtificially().then(callback).catch(errback);
//===> Promise(Array[StackFrame], Error)
```

#### Trace every time a given function is invoked
```js
// callback is called with an Array[StackFrame] every time wrapped function is called
var myFunc = function(arg) { return 'Hello ' + arg; };
var myWrappedFunc = StackTrace.instrument(myFunc, callback, errback);
//===> Instrumented Function
myWrappedFunc('world');
//===> 'Hello world'

// Use this if you overwrote you original function
myFunc = StackTrace.deinstrument(myFunc);
//===> De-instrumented Function
```

## Get stacktrace.js
```
npm install stacktrace-js
bower install stacktrace-js
component install stacktracejs/stacktrace.js
http://cdnjs.com/libraries/stacktrace.js
```

## API

#### `StackTrace.get(/*optional*/ options)` => [Promise](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise)(Array[[StackFrame](https://github.com/stacktracejs/stackframe)])
Generate a backtrace from invocation point, then parse and enhance it.

**(Optional) options: Object**
* *filter: Function([StackFrame](https://github.com/stacktracejs/stackframe) => Boolean)* - Only include stack entries matching for which `filter` returns `true`
* *sourceCache: Object (String URL => String Source)* - Pre-populate source cache to avoid network requests
* *offline: Boolean (default: false)* - Set to `true` to prevent all network requests

#### `StackTrace.getSync(/*optional*/ options)` => Array[[StackFrame](https://github.com/stacktracejs/stackframe)]
Generate a backtrace from invocation point, then parse it. This method does not use source maps or guess anonymous functions.  

**(Optional) options: Object**
* *filter: Function([StackFrame](https://github.com/stacktracejs/stackframe) => Boolean)* - Only include stack entries matching for which `filter` returns `true`

#### `StackTrace.fromError(error, /*optional*/ options)` => [Promise](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise)(Array[[StackFrame](https://github.com/stacktracejs/stackframe)])
Given an Error object, use [error-stack-parser](https://github.com/stacktracejs/error-stack-parser)
to parse it and enhance location information with [stacktrace-gps](https://github.com/stacktracejs/stacktrace-gps).

**error: Error**

**(Optional) options: Object**
* *filter: Function([StackFrame](https://github.com/stacktracejs/stackframe) => Boolean)* - Only include stack entries matching for which `filter` returns `true`
* *sourceCache: Object (String URL => String Source)* - Pre-populate source cache to avoid network requests
* *offline: Boolean (default: false)* - Set to `true` to prevent all network requests

#### `StackTrace.generateArtificially(/*optional*/ options)` => [Promise](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise)(Array[[StackFrame](https://github.com/stacktracejs/stackframe)])
Use [stack-generator](https://github.com/stacktracejs/stack-generator) to generate a backtrace by walking the `arguments.callee.caller` chain.

**(Optional) options: Object**
* *filter: Function([StackFrame](https://github.com/stacktracejs/stackframe) => Boolean)* - Only include stack entries matching for which `filter` returns `true`
* *sourceCache: Object (String URL => String Source)* - Pre-populate source cache to avoid network requests
* *offline: Boolean (default: false)* - Set to `true` to prevent all network requests

#### `StackTrace.instrument(fn, callback, /*optional*/ errback)` => Function
* Given a function, wrap it such that invocations trigger a callback that is called with a stack trace.

* **fn: Function** - to wrap, call callback on invocation and call-through
* **callback: Function** - to call with stack trace (generated by `StackTrace.get()`) when fn is called
* **(Optional) errback: Function** - to call with Error object if there was a problem getting a stack trace.
Fails silently (though `fn` is still called) if a stack trace couldn't be generated.

#### `StackTrace.deinstrument(fn)` => Function
Given a function that has been instrumented, revert the function to it's original (non-instrumented) state.

* **fn: Function** - Instrumented Function

#### `StackTrace.report(stackframes, url, message, requestOptions)` => [Promise](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise)(String)
Given an an error message and Array of StackFrames, serialize and POST to given URL. Promise is resolved with response text from POST request.

Example JSON POST data:
```
{
  message: 'BOOM',
  stack: [
    {functionName: 'fn', fileName: 'file.js', lineNumber: 32, columnNumber: 1},
    {functionName: 'fn2', fileName: 'file.js', lineNumber: 543, columnNumber: 32},
    {functionName: 'fn3', fileName: 'file.js', lineNumber: 8, columnNumber: 1}
  ]
}
```

* **stackframes: Array([StackFrame](https://github.com/stacktracejs/stackframe))** - Previously wrapped Function
* **url: String** - URL to POST stack JSON to
* **message: String** - The error message
* **requestOptions: Object** - HTTP request options object. Only `headers: {key: val}` is supported.

## Browser Support
[![Sauce Test Status](https://saucelabs.com/browser-matrix/stacktracejs.svg)](https://saucelabs.com/u/stacktracejs)

> **HEADS UP**: You won't get the benefit of [source maps](http://www.html5rocks.com/en/tutorials/developertools/sourcemaps/)
in IE9- or other very old browsers.

## Using node.js/io.js only?
I recommend the [stack-trace node package](https://www.npmjs.com/package/stack-trace) specifically built for node.
It has a very similar API and also supports source maps.

## Contributing
This project adheres to the [Open Code of Conduct](http://todogroup.org/opencodeofconduct/#stacktrace.js/me@eriwen.com). By participating, you are expected to honor this code.

Want to be listed as a *Contributor*? Start with the [Contributing Guide](https://github.com/stacktracejs/stacktrace.js/blob/master/.github/CONTRIBUTING.md)!

This project is made possible due to the efforts of these fine people:

* [Eric Wendelin](https://www.eriwen.com)
* [Victor Homyakov](https://github.com/victor-homyakov)
* [Oliver Salzburg](https://github.com/oliversalzburg)
* [Many others](https://github.com/stacktracejs/stacktrace.js/graphs/contributors)
