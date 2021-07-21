## v2.0.0

### ES6 Support

ES6 code is now parsed and enhanced!

### Extensible StackFrames

StackFrames returned are now able to report on whether a function call was a `Constructor`, `native` code, or `eval` code. 

### MIT License

The community [has voted](https://github.com/stacktracejs/stacktrace.js/issues/187) to change the license of the project to the [MIT License](https://opensource.org/licenses/MIT)

## v1.3.0
* `Stacktrace.getSync()` gets a stack trace, synchronously. It does not attempt to map sources or guess function names, because those typically require network requests.

## v1.2.0

* `StackTrace.report` now accepts an error message argument, and will add a `message: "given thing"` to the JSON payload if it is provided.
* Various bug fixes from v1.1.0

## v1.1.0

### Better parsing
Updated [error-stack-parser](https://github.com/stacktracejs/error-stack-parser) to v1.3 which parses eval stack entries in a better way and fixes a bunch of bugs. 

### Better resource handling
Updated [stacktrace-gps](https://github.com/stacktracejs/stacktrace-gps). Now reuses the same instance to avoid duplicate requests for the same resource by default. 

### Better dev experience
JSCS and automated PR testing have been implemented to ensure consistent styles and quick feedback.

> Possibly breaking changes: ErrorStackParser now provides it's own polyfill for `Array.map` and `Array.filter`. `eval` information is will display differently in stack traces.

## v1.0.0

### stacktrace.js is reborn

stacktrace.js is now modularized into 5 projects:

* [stacktrace-gps](https://github.com/stacktracejs/stacktrace-gps) - turn partial code location into precise code location
* [error-stack-parser](https://github.com/stacktracejs/error-stack-parser) - extract meaning from JS Errors
* [stack-generator](https://github.com/stacktracejs/stack-generator) - generate artificial backtrace in old browsers
* [stackframe](https://github.com/stacktracejs/stackframe) - JS Object representation of a stack frame

... and putting it all together: [stacktrace.js](stacktracejs/stacktrace.js) for instrumenting your code and generating stack traces!

### Key Features

* Fully asynchronous API, using [Promises](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise). Use your own polyfill or use [our distribution with polyfills included](https://github.com/stacktracejs/stacktrace.js/blob/master/dist/stacktrace-with-polyfills.min.js). See the [Migration Guide](http://www.stacktracejs.com/docs/v0-migration-guide)
* [Source Maps](http://www.html5rocks.com/en/tutorials/developertools/sourcemaps/) support
* Forward-compatible: stacktrace.js no longer assumes a given browser formats Error stacks in a given way. This prevents new browser versions from breaking error parsing
* Stack entries are now fully parsed and returned as [StackFrame objects](https://github.com/stacktracejs/stackframe). Prefer the old format? - just call `.toString()`!
* Use only what you need. All 5 projects work independently as well as together!
* iOS 8+ Safari support

### Available everywhere

```
npm install stacktrace-js
bower install stacktrace-js
component install stacktracejs/stacktrace.js
https://cdnjs.cloudflare.com/ajax/libs/stacktrace.js/1.0.0/stacktrace.min.js
```

### Better for contributors

* gulp build
* TravisCI + Sauce for testing a bunch of browsers
* EditorConfig for style adherence

## v0.6.2

* Ignore test/ dir in bower
* Migrate references eriwen/javascript-stacktrace -> stacktracejs/stacktrace.js

## v0.6.1

* Fix printStackTrace throws exception with "use strict" code and PhantomJS

## v0.6.0

* Added AMD support using a UMD pattern (thanks @jeffrose)

## v0.5.3

* Fix Chrome 27 detection; Chrome no longer has Error#arguments

## v0.5.1

* Fix Bower integration; Added proper bower.json file

## v0.5.0

* Lots and lots of stuff

