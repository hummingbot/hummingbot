stacktrace-gps - Turn partial code location into precise code location
===================
[![Build Status](https://travis-ci.org/stacktracejs/stacktrace-gps.svg?branch=master)](https://travis-ci.org/stacktracejs/stacktrace-gps) [![Coverage Status](https://img.shields.io/coveralls/stacktracejs/stacktrace-gps.svg)](https://coveralls.io/r/stacktracejs/stacktrace-gps) [![GitHub license](https://img.shields.io/github/license/stacktracejs/stacktrace-gps.svg)](https://opensource.org/licenses/MIT)

This library accepts a code location (in the form of a [StackFrame](https://github.com/stacktracejs/stackframe)) and
returns a new StackFrame with a more accurate location (using [source maps](http://www.html5rocks.com/en/tutorials/developertools/sourcemaps/)) and guessed function names.

This is primarily a browser-centric library, but can be used with node.js. See the [Offline Usage section](#offline-usage) below.

## Usage
```js
var stackframe = new StackFrame({fileName: 'http://localhost:3000/file.min.js', lineNumber: 1, columnNumber: 3284});
var callback = function myCallback(foundFunctionName) { console.log(foundFunctionName); };

// Such meta. Wow
var errback = function myErrback(error) { console.log(StackTrace.fromError(error)); };

var gps = new StackTraceGPS();

// Pinpoint actual function name and source-mapped location
gps.pinpoint(stackframe).then(callback, errback);
//===> Promise(StackFrame({functionName: 'fun', fileName: 'file.js', lineNumber: 203, columnNumber: 9}), Error)

// Better location/name information from source maps
gps.getMappedLocation(stackframe).then(callback, errback);
//===> Promise(StackFrame({fileName: 'file.js', lineNumber: 203, columnNumber: 9}), Error)

// Get function name from location information
gps.findFunctionName(stackframe).then(callback, errback);
//===> Promise(StackFrame({functionName: 'fun', fileName: 'http://localhost:3000/file.min.js', lineNumber: 1, columnNumber: 3284}), Error)
```

### Offline Usage
With a bit of preparation, you can use this library offline in any environment. Any encountered fileNames not in the cache return resolved
Promises with the original StackFrame. StackTraceGPS will make a best effort to provide as good of response with what is given and will
fallback to the original StackFrame if nothing better could be found.

```js
var stack = ErrorStackParser.parse(new Error('boom'));
console.assert(stack[0] == new StackFrame({fileName: 'http://localhost:9999/file.min.js', lineNumber: 1, columnNumber: 32}));

var sourceCache = {'http://localhost:9999/file.min.js': 'var foo=function(){};function bar(){}var baz=eval("XXX");\n//# sourceMappingURL=file.js.map'};
var sourceMap = '{"version":3,"sources":["./file.js"],"sourceRoot":"http://localhost:4000/","names":["foo","bar","baz","eval"],"mappings":"AAAA,GAAIA,KAAM,YACV,SAASC,QACT,GAAIC,KAAMC,KAAK","file":"file.min.js"}';
var sourceMapConsumerCache = {'http://localhost:4000/file.js.map': new SourceMap.SourceMapConsumer(sourceMap)};

var gps = new StackTraceGPS({offline: true, sourceCache: sourceCache, sourceMapConsumerCache: sourceMapConsumerCache});
gps.pinpoint(stack[0]).then(function(betterStackFrame) {
    console.assert(betterStackFrame === new StackFrame({functionName: 'bar', fileName: 'http://localhost:9999/file.js', lineNumber: 2, columnNumber: 9}));
});
```

## Installation
```
npm install stacktrace-gps
bower install stacktrace-gps
https://raw.githubusercontent.com/stacktracejs/stacktrace-gps/master/dist/stacktrace-gps.min.js
```

## API

#### `new StackTraceGPS(/*optional*/ options)` => StackTraceGPS
options: Object
* **sourceCache: Object (String URL : String Source)** - Pre-populate source cache to avoid network requests
* **sourceMapConsumerCache: Object (Source Mapping URL : SourceMap.SourceMapConsumer)** - Pre-populate source cache to avoid network requests
* **offline: Boolean (default false)** - Set to `true` to prevent all network requests
* **ajax: Function (String URL => Promise(responseText))** - Function to be used for making X-Domain requests
* **atob: Function (String => String)** - Function to convert base64-encoded strings to their original representation

#### `.pinpoint(stackframe)` => Promise(StackFrame)
Enhance function name and use source maps to produce a better StackFrame.
* **stackframe** - [StackFrame](https://github.com/stacktracejs/stackframe) or like object
e.g. {fileName: 'path/to/file.js', lineNumber: 100, columnNumber: 5}

#### `.findFunctionName(stackframe)` => Promise(StackFrame)
Enhance function name and use source maps to produce a better StackFrame.
* **stackframe** - [StackFrame](https://github.com/stacktracejs/stackframe) or like object

#### `.getMappedLocation(stackframe)` => Promise(StackFrame)
Enhance function name and use source maps to produce a better StackFrame.
* **stackframe** - [StackFrame](https://github.com/stacktracejs/stackframe) or like object

## Browser Support
[![Sauce Test Status](https://saucelabs.com/browser-matrix/stacktracejs.svg)](https://saucelabs.com/u/stacktracejs)

Functions that rely on [Source Maps](http://www.html5rocks.com/en/tutorials/developertools/sourcemaps/)
(`pinpoint` and `getMappedLocation`) require recent browsers.

## Contributing
Want to be listed as a *Contributor*? Start with the [Contributing Guide](CONTRIBUTING.md)!
