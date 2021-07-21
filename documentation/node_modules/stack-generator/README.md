stack-generator
===============
[![Build Status](https://travis-ci.org/stacktracejs/stack-generator.svg?branch=master)](https://travis-ci.org/stacktracejs/stack-generator) [![Coverage Status](https://img.shields.io/coveralls/stacktracejs/stack-generator.svg)](https://coveralls.io/r/stacktracejs/stack-generator) [![GitHub license](https://img.shields.io/github/license/stacktracejs/stack-generator.svg)](https://opensource.org/licenses/MIT)

Generate artificial backtrace by walking arguments.callee.caller chain. **Works everywhere except strict-mode**.

## Usage
```
StackGenerator.backtrace()

=> [StackFrame({functionName: 'foo', args: []}), StackFrame(..), StackFrame(..)]
```

## Installation
```
npm install stack-generator
bower install stack-generator
https://raw.githubusercontent.com/stacktracejs/stack-generator/master/dist/stack-generator.min.js
```

## Browser Support
[![Sauce Test Status](https://saucelabs.com/browser-matrix/stacktracejs.svg)](https://saucelabs.com/u/stacktracejs)

## Contributing
Want to be listed as a *Contributor*? Start with the [Contributing Guide](CONTRIBUTING.md)!

## License
This project is licensed to the [Public Domain](http://unlicense.org)
